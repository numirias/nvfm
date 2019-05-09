from datetime import datetime
from functools import partial

from .config import sort_funcs


class Options:

    def __init__(self):
        self._options = {o.key: o() for o in Option.__subclasses__()}

    def __getitem__(self, key):
        return self._options[key]

    def __setitem__(self, key, val):
        self._options[key].value = val


class Option:
    """An option.

    The options value can be set and retrieved via `option.value`. Options must
    implement a `default` attribute. Options may implement a `convert()` method
    to convert a value before it is set. The method `after_value_set()` is
    called after a value was set and can be used to update attributes based on
    the changed value.
    """
    _val = None

    def __init__(self):
        self.value = self.default

    @property
    def value(self):
        return self._val

    @value.setter
    def value(self, val):
        self._val = self.convert(val)
        self.after_value_set()

    @staticmethod
    def convert(val):
        return val

    @property
    def default(self):
        raise NotImplementedError()

    @staticmethod
    def after_value_set():
        pass


class SortOption(Option):

    key = 'sort'
    name = None

    @property
    def default(self):
        return next(iter(sort_funcs.values()))

    @staticmethod
    def convert(val):
        return val if callable(val) else sort_funcs[val]

    def after_value_set(self):
        self.name = self.value.__name__


class ColumnsOption(Option):

    key = 'columns'
    default = ['mode', 'user', 'size', 'mtime']
    template = '(no template)'

    def after_value_set(self):
        formatters = {
            'mode': '{mode}',
            'size': '{size:>7}',
            'atime': ' {atime}',
            'ctime': ' {ctime}',
            'mtime': ' {mtime}',
            'ino': '{ino}',
            'nlink': '{nlink}',
            'user': ' {uid:>5.5s}',
            'group': ' {gid:>5.5s}',
        }
        self.template = ''.join([formatters[c] for c in self.value])


class TimeFormat(Option):

    key = 'time_format'
    default = 'ago'

    @classmethod
    def convert(cls, val):
        if not isinstance(val, str):
            raise ValueError('Invalid value for option "time_format"')
        if val == 'ago':
            return cls.format_ago
        return partial(cls.format_strftime, format=val or '%Y-%m-%d %H:%m')

    @classmethod
    def format_ago(cls, time):
        s = cls._format_ago_str(time)
        return s.rjust(8)

    @staticmethod
    def _format_ago_str(time):
        # TODO Don't calculate "now" here
        now = datetime.now()
        then = datetime.fromtimestamp(time)
        diff = now - then
        second_diff = diff.seconds
        day_diff = diff.days
        if day_diff == 0:
            if second_diff < 10:
                return 'now'
            if second_diff < 60:
                return '%is ago' % second_diff
            if second_diff < 3600:
                return '%im ago' % (second_diff // 60)
            if second_diff < 86400:
                return '%ih ago' % (second_diff // 3600)
        if 0 < day_diff < 30:
            return '%id ago' % day_diff
        if now.year == then.year:
            return then.strftime('%d %b')
        return then.strftime('%b %Y')

    @staticmethod
    def format_strftime(time, format):
        return datetime.fromtimestamp(time).strftime(format)
