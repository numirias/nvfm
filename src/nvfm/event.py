# pylint: disable=protected-access
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
        func._event = self
        return func


class EventEmitter:

    _event_manager = None

    @classmethod
    def on(cls, name):
        return Event(name, cls)

    def emit(self, name, *args, **kwargs):
        self._event_manager.publish(Event(name, type(self)), *args, **kwargs)


class Global(EventEmitter):
    pass


class EventManager:

    def __init__(self):
        self._handlers = defaultdict(list)

    def subscribe(self, event, handler):
        logger.debug(('event:sub', handler, event))
        self._handlers[event].append(handler)

    def unsubscribe(self, event, handler):
        logger.debug(('event:unsub', handler, event))
        self._handlers[event].remove(handler)

    def publish(self, event, *args, **kwargs):
        logger.debug(
            ('event:pub', len(self._handlers[event]), event, args, kwargs))
        name, obj = event.key
        if type(obj) is not type: # pylint: disable=unidiomatic-typecheck
            # obj is an instance
            self._fire(Event(name, obj), *args, **kwargs)
            obj = type(obj)
        # obj is a class
        self._fire(Event(name, obj), *args, **kwargs)
        for base in obj.__bases__:
            self._fire(Event(name, base), *args, **kwargs)

    def _fire(self, name, *args, **kwargs):
        for handler in self._handlers[name]:
            logger.debug(('event:fire', name, handler.__name__, args, kwargs))
            handler(*args, **kwargs)

    def manage(self, obj):
        """Manage the events of `obj`.

        To use event handlers and emit events, an object must be managed.
        """
        obj._event_manager = self
        # Find all event handlers on `obj` and register them
        for func in (getattr(obj, x) for x in dir(obj)):
            if not callable(func) or getattr(func, '_event', None) is None:
                continue
            # `func` is an event handler, make it subscribe to its event
            self.subscribe(func._event, func)
