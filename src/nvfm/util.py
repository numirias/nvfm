import logging
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
