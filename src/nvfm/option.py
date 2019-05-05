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
            'atime': '{atime:>9}',
            'ctime': '{ctime:>9}',
            'mtime': '{mtime:>9}',
            'ino': '{ino}',
            'nlink': '{nlink}',
            'user': ' {uid:>5.5s}',
            'group': ' {gid:>5.5s}',
        }
        self.template = ''.join([formatters[c] for c in self.value])
