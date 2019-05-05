from collections import OrderedDict
import locale
import stat

from .util import convert_size

sort_funcs = OrderedDict()

def sort_func(name):
    def wrapper(f):
        sort_funcs[name] = f
        sort_funcs[name + '_reverse'] = lambda x: reversed(list(f(x)))
        return f
    return wrapper


filter_funcs = OrderedDict()

def filter_func(name):
    def wrapper(f):
        filter_funcs[name] = f
        return f
    return wrapper


@sort_func('alpha')
def sort_alpha(items):
    locale_ = locale.getlocale()
    locale.setlocale(locale.LC_ALL, '')
    items = sorted(items, key=lambda x: locale.strxfrm(x.name))
    locale.setlocale(locale.LC_ALL, locale_)
    return items


@sort_func('last_modified')
def sort_last_modified(items):
    return reversed(
        sorted(items, key=lambda x: x.stat(follow_symlinks=False).st_mtime))


@sort_func('size')
def sort_size(items):
    return sorted(items, key=lambda x: x.stat(follow_symlinks=False).st_size)


@filter_func('standard')
def filter_standard(query, candidate):
    return query.lower() in candidate.name.lower()


def format_meta(stat_res, columns):
    from .util import logger
    logger.debug(('cols', columns))
    formatters = {
        'mode': '{mode}',
        'size': '{size:>7}',
    }
    s = ''.join([formatters[c] for c in columns])
    return s.format(
        mode=stat.filemode(stat_res.st_mode),
        size=convert_size(stat_res.st_size),
    )
