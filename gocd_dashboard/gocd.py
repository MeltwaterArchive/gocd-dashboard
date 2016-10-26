import itertools
import re

import attr
import requests_futures.sessions

from gocd_dashboard.debug import debug


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

    def url(self, endpoint, *args, **kwargs):
        return self.server + endpoint.format(*args, **kwargs)

    def get(self, *args, **kwargs):
        """Make a request using requests-futures and return a Future."""
        return self.session.get(self.url(*args, **kwargs),
                                auth=(self.username, self.password))

    @staticmethod
    def wait(response):
        """
        Wait for a response from requests-futures and return the JSON content.

        This is used a lot to make multiple requests at the same time.
        """
        response = response.result()
        response.raise_for_status()
        return response.json()

    # API Endpoints.

    def pipeline_history(self, name):
        """Get the history for a pipeline."""
        return self.get('/go/api/pipelines/{}/history.json', name)

    def pipeline_instance(self, name, counter):
        """Get a pipeline instance."""
        return self.get('/go/api/pipelines/{}/instance/{}.json',
                        name, counter)

    def latest_pipeline_instance(self, name, history):
        """Get the most recent pipeline instance."""
        counter = history['pipelines'][0]['counter']
        return self.pipeline_instance(name, counter)

    # Data structure creation.

    def wait_pipelines(self, responses):
        """Make a `Pipeline` object from a .pipeline_instance() response."""
        return [Pipeline.from_json(self.wait(r), self) for r in responses]

    def load_pipelines(self, pipelines):
        histories = [(n, self.pipeline_history(n)) for n in pipelines]
        responses = [self.latest_pipeline_instance(n, self.wait(h))
                     for (n, h) in histories]
        return self.wait_pipelines(responses)

    def load_groups(self, groups):
        return [Group(name=group['name'],
                      pipelines=self.load_pipelines(group['pipelines']))
                for group in groups]


@attr.s(frozen=True)
class Group:
    name = attr.ib()
    pipelines = attr.ib()

    def result(self):
        return 'Passed' if self.passed() else 'Failed'

    def passed(self):
        return all(s.passed() for s in self.pipelines)


@attr.s(frozen=True)
class Pipeline:
    name = attr.ib()
    counter = attr.ib()
    stages = attr.ib()
    git_materials = attr.ib()
    pipeline_materials = attr.ib()

    gocd = attr.ib(repr=False)

    @classmethod
    def from_json(cls, data, gocd):
        revisions = data['build_cause']['material_revisions']
        return cls(
            name=data['name'],
            counter=data['counter'],
            stages=list(map(Stage.from_json, data['stages'])),
            git_materials=cls.git_materials_from_json(revisions),
            pipeline_materials=cls.pipelines_from_materials(revisions, gocd),
            gocd=gocd)

    @staticmethod
    def git_materials_from_json(material_revisions):
        return [GitMaterial.from_json(revision)
                for revision in material_revisions
                if revision['material']['type'] == 'Git']

    @classmethod
    def pipelines_from_materials(cls, material_revisions, gocd):
        responses = [cls.from_material(m, gocd)
                     for m in material_revisions
                     if m['material']['type'] == 'Pipeline']
        return sorted(gocd.wait_pipelines(responses), key=lambda p: p.name)

    @classmethod
    def from_material(cls, material, gocd):
        assert len(material['modifications']) == 1
        name, counter = material['modifications'][0]['revision'].split('/')[:2]
        return gocd.pipeline_instance(name, counter)

    # Instance methods.

    def link(self):
        return self.gocd.url('/go/pipelines/value_stream_map/{}/{}',
                             self.name, self.counter)

    def all_git_materials(self):
        """Recursively collect git materials."""
        return sorted(itertools.chain(
            self.git_materials,
            *(p.all_git_materials() for p in self.pipeline_materials)),
            key=lambda m: m.url)

    # Results

    def result(self):
        return 'Passed' if self.passed() else 'Failed'

    def passed(self):
        return all(s.passed() for s in self.stages)

    def failed_stage(self):
        return next((s for s in self.stages if not s.passed()), None)


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

    def passed(self):
        return self.result in ('Passed', None)

    def link(self, pipeline):
        return pipeline.gocd.url('/go/pipelines/{}/{}/{}/{}',
                                 pipeline.name, pipeline.counter,
                                 self.name, self.counter)


@attr.s(frozen=True)
class GitMaterial:
    type = 'git'

    url = attr.ib()
    modifications = attr.ib()

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
        return cls(url=url, modifications=modifications,
                   gh=(gh_org and gh_repo), gh_org=gh_org, gh_repo=gh_repo)

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

    def name(self):
        return self.gh_name() if self.gh else self.url

    def link(self):
        return self.gh_link() if self.gh else self.url

    def gh_name(self):
        return '{}/{}'.format(self.gh_org, self.gh_repo)

    def gh_link(self, *args):
        if not self.gh:
            return None
        return '/'.join(
            ('https://github.com', self.gh_org, self.gh_repo) + args)


@attr.s(frozen=True)
class GitModification:
    message = attr.ib()
    commit = attr.ib()

    # Name and email of the person who wrote the commit.
    author_name = attr.ib()
    author_email = attr.ib()

    RE_AUTHOR = re.compile('(.+) <(.+)>')

    @classmethod
    def from_json(cls, modification):
        author_name, author_email = cls.parse_author(modification['user_name'])

        return cls(message=modification['comment'],
                   commit=modification['revision'],
                   author_name=author_name,
                   author_email=author_email)

    @classmethod
    def parse_author(cls, author):
        match = cls.RE_AUTHOR.match(author)
        if not match:
            return author
        return match.groups()

    def title(self):
        return self.message.split('\n', 2)[0]

    def gh_link(self, material):
        return material.gh_link('commit', self.commit)
