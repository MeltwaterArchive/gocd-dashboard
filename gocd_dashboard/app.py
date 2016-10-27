"""Routes."""

import flask
import flask_gravatar
import jinja2

import gocd_dashboard.blueprints


def create_app(info=None):
    app = flask.Flask(__name__)

    flask_gravatar.Gravatar(app, rating='g', use_ssl=True)

    # Register blueprints - currently only the user interface
    app.register_blueprint(gocd_dashboard.blueprints.ui)

    # Load debug extensions when FLASK_DEBUG is on.
    if app.config['DEBUG']:
        debug_app(app)

    return app


def debug_app(app):
    """Add the debug toolbar extension to the application."""
    app.jinja_env.undefined = jinja2.StrictUndefined

    try:
        import flask_debugtoolbar
    except ImportError:
        flask_debugtoolbar = None
    else:
        app.config['SECRET_KEY'] = 'debug-secret-key'
        flask_debugtoolbar.DebugToolbarExtension(app)
