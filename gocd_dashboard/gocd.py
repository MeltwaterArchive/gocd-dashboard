import itertools
import re

import attr
import requests_futures.sessions

import flask

from gocd_dashboard.utils import Repr


@attr.s(frozen=True)
class GoCD:
    """
    GoCD client for fetching statuses of a set of pipelines.

    Uses requests-futures to make async requests, due to the number of api
    endpoints this will call. The API is a bit funny due to this...
    """

    server = attr.ib()
    username = attr.ib()
    password = attr.ib()

    session = attr.ib(
        default=attr.Factory(requests_futures.sessions.FuturesSession))
    cache = attr.ib(default=attr.Factory(dict))

    # HTTP Requests.

    def url(self, endpoint, *args, **kwargs):
        return self.server + endpoint.format(*args, **kwargs)

    def get(self, *args, **kwargs):
        """
        Make a request using requests-futures and return a Future.

        Responses are cached by url, create a new client for each request.
        """
        url = self.url(*args, **kwargs)

        if url not in self.cache:
            flask.current_app.logger.info(url)
            self.cache[url] = self.session.get(
                url, auth=(self.username, self.password))

        return self.cache[url]

    @staticmethod
    def wait(response):
        """
        Wait for a response from requests-futures and return the JSON content.

        This is used a lot to make multiple requests at the same time.
        """
        response = response.result()
        response.raise_for_status()
        return response.json()

    def wait_pipeline(self, future):
        """Create a Pipeline object from a Future."""
        return Pipeline.from_json(self.wait(future), self)

    # API Endpoints.

    def pipeline_history(self, name):
        return self.get('/go/api/pipelines/{}/history.json', name)

    def latest_pipeline(self, history):
        pipeline = history['pipelines'][0]
        return self.pipeline_instance(pipeline['name'], pipeline['counter'])

    def pipeline_instance(self, name, counter):
        return self.get('/go/api/pipelines/{}/instance/{}.json', name, counter)

    # Data structure creation.

    def load_pipelines(self, pipelines):
        """Creates a Pipeline object from the latest instance for each name."""
        history = (self.pipeline_history(name) for name in pipelines)
        futures = (self.latest_pipeline(self.wait(h)) for h in history)
        return [self.wait_pipeline(f) for f in futures]


class Pipeline(Repr):
    @classmethod
    def from_json(cls, data, gocd):
        stages = list(map(Stage.from_json, data['stages']))

        revisions = data['build_cause']['material_revisions']
        git_materials = cls.git_materials_from_json(revisions)
        pipeline_materials = cls.pipeline_materials_from_json(revisions, gocd)

        return cls(data['name'], data['counter'], stages,
                   git_materials, pipeline_materials, gocd)

    @classmethod
    def git_materials_from_json(cls, revisions):
        """
        We want all git materials. The GoCD compare page shows commits from
        changed pipelines, not commits from changed materials.
        """
        materials = cls.filter_revisions_by_type(revisions, 'Git')
        return tuple(GitMaterial.from_json(r) for r in materials)

    @classmethod
    def pipeline_materials_from_json(cls, revisions, gocd):
        materials = cls.filter_revisions_by_type(revisions, 'Pipeline')
        return tuple(PipelineMaterial.from_json(r, gocd) for r in materials)

    @staticmethod
    def filter_revisions_by_type(revisions, material_type):
        return [r for r in revisions if r['material']['type'] == material_type]

    def __init__(self, name, counter, stages,
                 git_materials, pipeline_materials, gocd):
        self.name = name
        self.counter = counter
        self.stages = stages
        self.git_materials = git_materials
        self.pipeline_materials = pipeline_materials
        self._gocd = gocd

    # GoCD information.

    @property
    def title(self):
        return "{}/{}".format(self.name, self.counter)

    @property
    def value_stream_map(self):
        return self._gocd.url('/go/pipelines/value_stream_map/{}/{}',
                              self.name, self.counter)

    def link_stage(self, name, counter):
        return self._gocd.url('/go/pipelines/{}/{}/{}/{}',
                              self.name, self.counter, name, counter)

    # Git materials.

    @property
    def git_material(self):
        if len(self.git_materials) == 1:
            return self.git_materials[0]

    @property
    def all_git_materials(self):
        """Recursively collect git materials."""
        pipelines = (p for p in self.all_pipeline_materials() if p.changed)
        children = (p.pipeline.all_git_materials for p in pipelines)
        return itertools.chain(self.git_materials, *children)

    def all_commit_authors(self):
        authors = (m.commit_authors for m in self.all_git_materials)
        return set(itertools.chain(*authors))

    # Pipeline materials

    @property
    def pipeline_material(self):
        if len(self.pipeline_materials) == 1:
            return self.pipeline_materials[0]

    def all_pipeline_materials(self):
        children = (p.pipeline.all_pipeline_materials()
                    for p in self.pipeline_materials)
        materials = itertools.chain(self.pipeline_materials, *children)
        return sorted(materials, key=lambda p: p.name)

    # Results

    @property
    def result(self):
        if self.passed:
            return 'Passed'
        elif self.running:
            return 'Running'
        else:
            return 'Failed'

    @property
    def passed(self):
        return all(s.status in ('passed', None) for s in self.stages)

    @property
    def running(self):
        return any(s.status == 'running' for s in self.stages)

    @property
    def running_stage(self):
        return self._first_stage('running')

    @property
    def failed(self):
        return any(s.status == 'failed' for s in self.stages)

    @property
    def failed_stage(self):
        return self._first_stage('failed')

    def _first_stage(self, status):
        return next((s for s in self.stages if s.status == status), None)


@attr.s(frozen=True)
class Stage:
    name = attr.ib()
    counter = attr.ib()
    result = attr.ib()

    @classmethod
    def from_json(cls, stage):
        return cls(name=stage['name'],
                   counter=stage['counter'],
                   result=stage.get('result', None))

    @property
    def status(self):
        if self.result == 'Passed':
            return 'passed'
        elif self.result == 'Unknown':
            return 'running'
        elif self.result == 'Failed':
            return 'failed'
        else:
            return None

    def link(self, pipeline):
        return pipeline.link_stage(self.name, self.counter)


@attr.s(init=False)
class PipelineMaterial:
    name = attr.ib()
    counter = attr.ib()
    changed = attr.ib()

    @classmethod
    def from_json(cls, material, gocd):
        assert len(material['modifications']) == 1
        name, counter = material['modifications'][0]['revision'].split('/')[:2]
        return cls(name, counter, material['changed'], gocd)

    def __init__(self, name, counter, changed, gocd):
        self.name = name
        self.counter = counter
        self.changed = changed

        self._gocd = gocd
        self._future = gocd.pipeline_instance(name, counter)
        self._pipeline = None

    @property
    def pipeline(self):
        if self._pipeline is None:
            self._pipeline = self._gocd.wait_pipeline(self._future)
        return self._pipeline


@attr.s(frozen=True)
class GitMaterial:
    type = 'git'

    changed = attr.ib()
    url = attr.ib()
    modifications = attr.ib(repr=False)

    # GitHub organisation and repository, used to create links.
    gh = attr.ib(convert=bool)
    gh_org = attr.ib()
    gh_repo = attr.ib()

    RE_URL = re.compile('^URL: (.+), Branch: .+$')
    RE_GITHUB = re.compile('^git@github\.com:([\w-]+)/([\w-]+)\.git$')

    @classmethod
    def from_json(cls, material):
        url = cls.parse_url(material['material']['description'])
        gh_org, gh_repo = cls.parse_github(url)
        modifications = [GitModification.from_json(m)
                         for m in material['modifications']]
        return cls(changed=material['changed'], url=url,
                   modifications=modifications, gh=(gh_org and gh_repo),
                   gh_org=gh_org, gh_repo=gh_repo)

    @classmethod
    def parse_url(cls, description):
        url = re.match(cls.RE_URL, description)
        if url is None:
            raise RuntimeError("Could not parse '{}'".format(description))
        return url.group(1)

    @classmethod
    def parse_github(cls, url):
        match = cls.RE_GITHUB.match(url)
        return match.groups() if match else (None, None)

    @property
    def name(self):
        return self.gh_name() if self.gh else self.url

    @property
    def link(self):
        return self.gh_link() if self.gh else self.url

    def gh_name(self):
        return '{}/{}'.format(self.gh_org, self.gh_repo)

    def gh_link(self, *args):
        if self.gh:
            return '/'.join(
                ('https://github.com', self.gh_org, self.gh_repo) + args)

    @property
    def commit_authors(self):
        """A set of authors from this material's commits (modifications)."""
        return {(m.author_name, m.author_email) for m in self.modifications}


@attr.s(frozen=True)
class GitModification:
    message = attr.ib()
    revision = attr.ib()

    # Name and email of the person who wrote the commit.
    author_name = attr.ib()
    author_email = attr.ib()

    RE_AUTHOR = re.compile('(.+) <(.+)>')

    @classmethod
    def from_json(cls, modification):
        author_name, author_email = cls.parse_author(modification['user_name'])

        return cls(message=modification['comment'],
                   revision=modification['revision'],
                   author_name=author_name,
                   author_email=author_email)

    @classmethod
    def parse_author(cls, author):
        match = cls.RE_AUTHOR.match(author)
        if not match:
            return author
        return match.groups()

    @property
    def title(self):
        return self.message.split('\n', 2)[0]

    def gh_link(self, material):
        return material.gh_link('commit', self.revision)
