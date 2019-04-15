import locale


sort_funcs = []

def sort_func(f):
    sort_funcs.append(f)
    return f


@sort_func
def alphasort(items):
    locale_ = locale.getlocale()
    locale.setlocale(locale.LC_ALL, '')
    items = sorted(items, key=lambda x: locale.strxfrm(x.name))
    locale.setlocale(locale.LC_ALL, locale_)
    return items
