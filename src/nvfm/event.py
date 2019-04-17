from collections import defaultdict

from .util import logger


class Event:

    def __init__(self, *key):
        self.key = key

    def __repr__(self):
        return 'Event(%s)' % ', '.join(map(str, self.key))

    def __eq__(self, other):
        return other.key == self.key

    def __hash__(self):
        return self.key.__hash__()

    def __call__(self, func):
        func._event = self # pylint: disable=protected-access
        return func


class EventEmitter:

    @classmethod
    def event(cls, name):
        """Return key for the event."""
        return Event(name, cls)


class EventManager:

    def __init__(self):
        self._handlers = defaultdict(list)

    def subscribe(self, name, handler):
        logger.debug(('event:sub', handler, name))
        self._handlers[name].append(handler)

    def unsubscribe(self, name, handler):
        logger.debug(('event:unsub', handler, name))
        self._handlers[name].remove(handler)

    def publish(self, event, *args, **kwargs):
        logger.debug(
            ('event:pub', len(self._handlers[event]), event, args, kwargs))
        if type(event) is str: # pylint: disable=unidiomatic-typecheck
            self._fire(event, *args, **kwargs)
        else:
            name, obj = event.key
            if type(obj) != type: # pylint: disable=unidiomatic-typecheck
                # obj is an instance
                self._fire(Event(name, obj), *args, **kwargs)
                obj = type(obj)
            # obj is a class
            self._fire(Event(name, obj), *args, **kwargs)
            for base in obj.__bases__:
                # TODO exclude [object] base
                self._fire(Event(name, base), *args, **kwargs)

    def _fire(self, name, *args, **kwargs):
        for handler in self._handlers[name]:
            logger.debug(('event:fire', name, handler.__name__, args, kwargs))
            handler(*args, **kwargs)

    def watch(self, obj):
        for func in (getattr(obj, x) for x in dir(obj)):
            if not callable(func) or getattr(func, '_event', None) is None:
                continue
            # pylint: disable=protected-access
            self.subscribe(func._event, func)
