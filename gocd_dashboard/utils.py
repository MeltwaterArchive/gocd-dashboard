import functools
import pprint

import flask


def once(function):
    @functools.wraps(function)
    def wrapper(self):
        return function(self)
    return wrapper


def debug(*objects):
    flask.current_app.logger.debug('\n'.join(map(pprint.pformat, objects)))


class Repr:
    def __repr__(self):
        return "<{} {}>".format(
            self.__class__.__name__,
            ', '.join(k + '=' + repr(v) for k, v in self.__dict__.items()))
