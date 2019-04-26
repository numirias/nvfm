import logging
import math
import os
from pathlib import Path


def hexdump(bytes, columns=16):
    from subprocess import run, PIPE
    text = run(['xxd', '-c', str(columns)],
               stdout=PIPE,
               stderr=PIPE,
               input=bytes)
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

def runtime_path():
    return str(Path(__file__).absolute().parent / 'runtime')


logger = make_logger()
