import logging
import os


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
