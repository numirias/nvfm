from collections import OrderedDict
import locale


sort_funcs = OrderedDict()

def sort_func(name):
    def wrapper(f):
        sort_funcs[name] = f
        sort_funcs[name + '_reverse'] = lambda x: reversed(list(f(x)))
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
    return reversed(sorted(items, key=lambda x: x.stat(follow_symlinks=False).st_mtime))


@sort_func('size')
def sort_size(items):
    return sorted(items, key=lambda x: x.stat(follow_symlinks=False).st_size)
