import pprint

import flask


def debug(obj):
    flask.current_app.logger.debug(pprint.pformat(obj))
