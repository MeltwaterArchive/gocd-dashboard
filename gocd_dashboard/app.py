"""Routes."""

import flask

import gocd_dashboard.blueprints


def create_app(info):
    app = flask.Flask(__name__)

    # Register blueprints - currently only the user interface
    app.register_blueprint(gocd_dashboard.blueprints.ui)

    # Load debug extensions when FLASK_DEBUG is on.
    if app.config['DEBUG']:
        debug_app(app)

    return app


def debug_app(app):
    """Add the debug toolbar extension to the application."""
    try:
        import flask_debugtoolbar
    except ImportError:
        pass
    else:
        # app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False
        app.config['SECRET_KEY'] = 'debug-secret-key'
        flask_debugtoolbar.DebugToolbarExtension(app)
