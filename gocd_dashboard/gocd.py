import json

import attr
import requests


def pp(data):
    print(json.dumps(data, indent=2))


@attr.s(frozen=True)
class GoCD:
    url = attr.ib()
    username = attr.ib()
    password = attr.ib()
    log = attr.ib()

    def get(self, endpoint, *args, **kwargs):
        url = self.url + endpoint.format(*args, **kwargs)
        self.log.debug("Fetching {}".format(url))
        resp = requests.get(url, auth=(self.username, self.password))
        resp.raise_for_status()
        return resp.json()

    def pipeline_history(self, name):
        """Get the history for a pipeline."""
        return self.get('/go/api/pipelines/{}/history.json', name)

    def pipeline_latest_counter(self, name):
        """The most recent counter for a pipeline."""
        return self.pipeline_history(name)['pipelines'][0]['counter']

    def pipeline_instance(self, name, counter=None):
        """Get a pipeline instance."""
        if counter is None:
            counter = self.pipeline_latest_counter(name)

        return self.get('/go/api/pipelines/{}/instance/{}.json', name, counter)

    def pipeline(self, *args, **kwargs):
        return Pipeline.from_json(self.pipeline_instance(*args, **kwargs))

    def group(self, name, pipelines):
        return Group(name=name, pipelines=[self.pipeline(n) for n in pipelines])

    def groups(self, groups):
        return [self.group(n, p) for (n, p) in groups.items()]


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
