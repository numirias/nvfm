import logging
import math
import os
import re


def hexdump(bytes, columns=16):
    from subprocess import run, PIPE
    text = run(['xxd', '-c', str(columns)], stdout=PIPE, stderr=PIPE, input=bytes)
    data = text.stdout
    return data

def convert_size(bytes):
    if not bytes:
        return '0'
    units = ('', 'K', 'M', 'G', 'T', 'P')
    i = int(math.floor(math.log(bytes, 1024)))
    power = math.pow(1024, i)
    num = round(bytes / power, 2)
    if i == 0:
        return '%iB' % round(num)
    return '{n:.1f}{unit}'.format(n=num, unit=units[i])

def natural_sort_key(s, _nsre=re.compile('([0-9]+)')):
    # https://stackoverflow.com/questions/4836710/does-python-have-a-built-in-function-for-string-natural-sort
    return [int(text) if text.isdigit() else text.lower()
            for text in _nsre.split(s)]

def list_files(path):
    """List all files in path."""
    files = list(path.iterdir())

    filemap = {f.name:f for f in files}
    import time
    t = time.time()
    # TODO faster sort
    sorted_names = sorted(filemap, key=natural_sort_key)
    sorted_files = [filemap[k] for k in sorted_names]
    logger.debug(('sort', '%f' % (time.time() - t)))

    return sorted_files

def stat_path(path, lstat=True):
    error, stat_res = None, None
    f = path.lstat if lstat else path.stat
    try:
        stat_res = f()
    except OSError as e:
        error = e
    return (stat_res, error)


def make_logger():
    logger = logging.getLogger('nvfm')
    logger.setLevel(logging.ERROR)
    log_file = os.environ.get('NVFM_LOG_FILE')
    if log_file:
        handler = logging.FileHandler(log_file)
        logger.setLevel(os.environ.get('NVFM_LOG_LEVEL', logging.ERROR))
        logger.addHandler(handler)
    logger.debug('nvfm logger started.')
    return logger


logger = make_logger()
