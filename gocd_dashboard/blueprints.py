"""App blueprints."""

import json
import os

import attr
import flask

import gocd_dashboard.gocd

ui = flask.Blueprint('ui', __name__)


@attr.s(frozen=True)
class Config:
    pipelines = attr.ib()
    gocd = attr.ib()

    @classmethod
    def from_file(cls, path):
        with open(path, 'r') as f:
            data = json.loads(f.read())

        gocd = gocd_dashboard.gocd.GoCD(
            log=flask.current_app.logger, **data.get('gocd'))

        return cls(gocd=gocd, pipelines=data.get('pipelines'))

    @classmethod
    def load(cls):
        return cls.from_file(os.getenv('GOCD_DASHBOARD_CONFIG', 'config.json'))

    def groups(self):
        return self.gocd.groups(self.pipelines)


@ui.route('/')
def dashboard():
    config = Config.load()
    return flask.render_template('home.html', groups=config.groups())

