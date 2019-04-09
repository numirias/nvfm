from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import time

import pynvim
import pytest

import nvfm


@pytest.fixture(scope='module')
def plugin_dir(tmpdir_factory):
    return tmpdir_factory.mktemp('test_plugin')


@pytest.fixture(scope='module', autouse=True)
def set_environment(plugin_dir):
    os.environ['NVIM_RPLUGIN_MANIFEST'] = str(plugin_dir.join('rplugin.vim'))
    os.environ['NVIM_PYTHON_LOG_FILE'] = '/tmp/log'
    os.environ['NVIM_PYTHON_LOG_LEVEL'] = 'DEBUG'
    os.environ['NVFM_LOG_FILE'] = '/tmp/nvfm.log'
    os.environ['NVFM_LOG_LEVEL'] = 'DEBUG'
    yield


def start_vim(socket_base):
    import random
    socket_path = str(socket_base.join('nvim_socket' + hex(random.randint(0x10000000,0xffffffff))[2:]))
    argv = ['nvfm', '--listen', socket_path, '--headless']
    subprocess.Popen(argv)
    print('waiting for socket creation...')
    for i in range(50):
        if Path(socket_path).is_socket():
            break
        time.sleep(.05)
    else:
        raise TimeoutError('nvim did not create a socket at %s.' % socket_path)
    vim = pynvim.attach('socket', path=socket_path)
    print('attached to socket at:', socket_path)
    print('rtp:', vim.eval('&rtp'))
    print('py3 plugins:', vim.call('remote#host#PluginsForHost', 'python3'))
    return vim


@pytest.fixture(scope='function')
def vim_ctx(plugin_dir):
    @contextmanager
    def func():
        vim = start_vim(plugin_dir)
        try:
            yield vim
        finally:
            vim.quit()
    return func


@pytest.fixture(scope='function')
def vim(plugin_dir):
    vim = start_vim(plugin_dir)
    yield vim
    vim.quit()
