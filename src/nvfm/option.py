from .config import sort_funcs


class Options:

    def __init__(self):
        self._options = {o.name: o() for o in Option.__subclasses__()}

    def __getitem__(self, key):
        return self._options[key].get()

    def __setitem__(self, key, val):
        self._options[key].set(val)


class Option:

    default = None

    def __init__(self):
        self._val = self.convert(self.default)

    def set(self, val):
        self._val = self.convert(val)

    def get(self):
        return self._val

    @staticmethod
    def convert(val):
        return val


class SortOption(Option):

    name = 'sort'
    default = staticmethod(next(iter(sort_funcs.values())))

    @staticmethod
    def convert(val):
        return val if callable(val) else sort_funcs[val]


class ColumnsOption(Option):

    name = 'columns'
    default = ['mode', 'size']
