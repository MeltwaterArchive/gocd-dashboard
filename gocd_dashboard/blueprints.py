"""App blueprints."""

import flask

import gocd_dashboard.config

ui = flask.Blueprint('ui', __name__)

@ui.route('/')
def dashboard():
    return flask.render_template('home.html',
                                 pipelines=gocd_dashboard.config.CONFIG)
