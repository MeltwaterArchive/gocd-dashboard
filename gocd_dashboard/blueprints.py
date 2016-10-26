import flask

import gocd_dashboard.config

ui = flask.Blueprint('ui', __name__)


@ui.before_app_first_request
def config():
    flask.current_app.configuration = gocd_dashboard.config.Config.load()


@ui.route('/')
def dashboard():
    return flask.render_template(
        'home.html', groups=flask.current_app.configuration.groups())

