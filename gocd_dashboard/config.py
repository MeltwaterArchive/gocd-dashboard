import os
import json

import attr

import gocd_dashboard.gocd


@attr.s(frozen=True)
class Config:

    gocd_server = attr.ib()
    gocd_username = attr.ib()
    gocd_password = attr.ib()

    group_definitions = attr.ib(convert=tuple)

    @classmethod
    def from_file(cls, path):
        with open(path, 'r') as f:
            data = json.loads(f.read())

        groups = ((g['name'], g['pipelines']) for g in data['groups'])

        return cls(gocd_server=data['gocd']['server'],
                   gocd_username=data['gocd']['username'],
                   gocd_password=data['gocd']['password'],
                   group_definitions=groups)

    @classmethod
    def load(cls):
        return cls.from_file(os.getenv('GOCD_DASHBOARD_CONFIG', 'config.json'))

    def gocd(self):
        return gocd_dashboard.gocd.GoCD(server=self.gocd_server,
                                        username=self.gocd_username,
                                        password=self.gocd_password)

    def groups(self):
        for name, pipelines in self.group_definitions:
            yield Group(name, self.gocd().load_pipelines(pipelines))


@attr.s(frozen=True)
class Group:
    name = attr.ib()
    pipelines = attr.ib()

    def result(self):
        return 'Passed' if self.passed() else 'Failed'

    def passed(self):
        return all(s.passed for s in self.pipelines)
