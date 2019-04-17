from collections import defaultdict

from .util import logger


class EventEmitter:

    @classmethod
    def event(cls, name):
        """Return key for the event."""
        return (name, cls)


class EventManager:

    def __init__(self):
        self._handlers = defaultdict(list)

    def subscribe(self, name, handler):
        logger.debug(('event:sub', handler, name))
        self._handlers[name].append(handler)

    def unsubscribe(self, name, handler):
        logger.debug(('event:unsub', handler, name))
        self._handlers[name].remove(handler)

    def publish(self, key, *args, **kwargs):
        logger.debug(('event:pub', len(self._handlers[key]), key, args, kwargs))
        if type(key) is str:
            self._fire(key, *args, **kwargs)
        else:
            name, obj = key
            if type(obj) != type:
                # obj is an instance
                self._fire((name, obj), *args, **kwargs)
                obj = type(obj)
            # obj is a class
            self._fire((name, obj), *args, **kwargs)
            for base in obj.__bases__:
                # TODO exclude [object] base
                self._fire((name, base), *args, **kwargs)

    def _fire(self, name, *args, **kwargs):
        for handler in self._handlers[name]:
            logger.debug(('event:fire', name, handler.__name__, args, kwargs))
            handler(*args, **kwargs)
