import json

import attr
import requests_futures.sessions


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

    log = attr.ib()
    session = attr.ib(
        default=attr.Factory(requests_futures.sessions.FuturesSession))

    def get(self, endpoint, *args, **kwargs):
        url = self.url + endpoint.format(*args, **kwargs)
        self.log.debug("Fetching {}".format(url))
        return self.session.get(url, auth=(self.username, self.password))

    @staticmethod
    def wait(response):
        response = response.result()
        response.raise_for_status()
        return response.json()

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

    def pipelines(self, pipelines):
        histories = [(n, self.pipeline_history(n)) for n in pipelines]
        responses = [self.latest_pipeline_instance(n, self.wait(h))
                     for (n, h) in histories]
        return [Pipeline.from_json(self.wait(r)) for r in responses]

    def groups(self, groups):
        return [Group(name=group.get('name'),
                      pipelines=self.pipelines(group.get('pipelines')))
                for group in groups]


@attr.s(frozen=True)
class Group:
    name = attr.ib()
    pipelines = attr.ib()


@attr.s(frozen=True)
class Pipeline:
    name = attr.ib()
    counter = attr.ib()
    stages = attr.ib()

    @classmethod
    def from_json(cls, data):
        return cls(
            name=data.get('name'),
            counter=data.get('counter'),
            stages=[Stage.from_json(s) for s in data.get('stages')]
        )

    def passed(self):
        return all([s.passed() for s in self.stages])


@attr.s(frozen=True)
class Stage:
    name = attr.ib()
    result = attr.ib()

    @classmethod
    def from_json(cls, data):
        return cls(name=data.get('name'), result=data.get('result'))

    def passed(self):
        return self.result == 'Passed'
