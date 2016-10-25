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
    endpoints this will call.
    """

    url = attr.ib()
    username = attr.ib()
    password = attr.ib()

    session = attr.ib(
        default=attr.Factory(requests_futures.sessions.FuturesSession))

    def get(self, endpoint, *args, **kwargs):
        """Make a request using requests-futures and return a Future."""
        url = self.url + endpoint.format(*args, **kwargs)
        return self.session.get(url, auth=(self.username, self.password))

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
        counter = history['pipelines'][0]['counter']
        return self.pipeline_instance(name, counter)

    # Data structure creation.

    def pipeline(self, response):
        """Make a `Pipeline` object from a .pipeline_instance() response."""
        return Pipeline.from_json(self.wait(response), self)

    def pipelines(self, pipelines):
        """Async."""
        histories = [(n, self.pipeline_history(n)) for n in pipelines]
        responses = [self.latest_pipeline_instance(n, self.wait(h))
                     for (n, h) in histories]
        return [self.pipeline(response) for response in responses]

    def groups(self, groups):
        return [Group(name=group['name'],
                      pipelines=self.pipelines(group['pipelines']))
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
    materials = attr.ib()

    @classmethod
    def from_json(cls, data, gocd):
        return cls(
            name=data['name'],
            counter=data['counter'],
            stages=list(map(Stage.from_json, data['stages'])),
            materials=Materials.from_json(
                data['build_cause']['material_revisions'], gocd))

    def result(self):
        return 'Passed' if self.passed() else 'Failed'

    def passed(self):
        return all(s.passed() for s in self.stages)


@attr.s(frozen=True)
class Stage:
    name = attr.ib()
    result = attr.ib()

    @classmethod
    def from_json(cls, stage):
        return cls(name=stage['name'], result=stage.get('result', None))

    def passed(self):
        return self.result in ('Passed', None)


class Materials(list):
    @classmethod
    def from_json(cls, revisions, gocd):
        # noinspection PyCallingNonCallable
        return cls([cls.material_from_json(r, gocd) for r in revisions])

    @staticmethod
    def material_from_json(material, gocd):
        if material['material']['type'] == 'Pipeline':
            return PipelineMaterial.from_json(material, gocd)
        elif material['material']['type'] == 'Git':
            return GitMaterial.from_json(material)
        else:
            raise RuntimeError('Unknown type ' + material['material']['type'])

    @classmethod
    def children(cls, data, gocd):
        if data['material']['type'] != 'Pipeline':
            return []

        revisions = [m['revision'] for m in data['modifications']]
        instances = [r.split('/')[0:2] for r in revisions]
        responses = [gocd.pipeline_instance(n, c) for n, c in instances]
        pipelines = [gocd.pipeline(r) for r in responses]
        return itertools.chain(*[p.materials for p in pipelines])

    def pipelines(self):
        """Returns only pipeline materials."""
        return [m for m in self if m.type == 'Pipeline']


@attr.s(frozen=True)
class GitMaterial:
    type = 'git'

    repo = attr.ib()
    branch = attr.ib()
    modifications = attr.ib()

    @classmethod
    def from_json(cls, material):
        description = material['material']['description']
        match = re.match("^URL: (.+), Branch: (.+)$", description)

        modifications = [GitModification.from_json(m)
                         for m in material['modifications']]

        return cls(repo=match.group(1),
                   branch=match.group(2),
                   modifications=modifications)

    GITHUB = re.compile('^git@github\.com:([\w-]+)/([\w-]+)\.git$')

    def github_link(self, *args):
        match = self.GITHUB.match(self.repo)
        if match:
            url = "https://github.com/{}/{}".format(*match.groups())
            return '/'.join((url,) + args)


@attr.s(frozen=True)
class GitModification:
    message = attr.ib()
    commit = attr.ib()
    user = attr.ib()

    @classmethod
    def from_json(cls, modification):
        return cls(message=modification['comment'],
                   commit=modification['revision'],
                   user=modification['user_name'])

    def github_link(self, material):
        return material.github_link('commit', self.commit)


@attr.s(frozen=True)
class PipelineMaterial:
    type = 'pipeline'

    name = attr.ib()
    materials = attr.ib()

    @classmethod
    def from_json(cls, material, gocd):
        return cls(
            name=material['material']['description'],
            materials=Materials.children(material, gocd))
