import os
from pathlib import Path
import re

import pytest

from nvfm.plugin import Plugin, History
from nvfm.util import stat_path
from nvfm.view import DirectoryView

from .test_helpers import make_tree


@pytest.fixture
def tree(tmpdir_factory):
    root = Path(str(tmpdir_factory.mktemp('tree')))
    make_tree(root, '''
    base/
        aa/
            aa_aa/
                aa_aa_f
        bb=bb_line_1\\nbb_line_2
        cc/
        dd
        ee/
            ff/
            gg/
            hh
    ''')
    return root / 'base'


def test_startup(vim):
    assert vim.options


def test_tabline(vim):
    tabline = vim.options['tabline']
    # Strip vim's tabline markup
    tabline = re.sub('%#.*?#', '', tabline)
    assert os.getcwd() in tabline


def test_panels(tree, vim_ctx):
    os.environ['NVFM_START_PATH'] = str(tree)
    with vim_ctx() as vim:
        assert len(vim.windows) == 3
        left, mid, right = vim.windows

        lines = left.buffer[:]
        assert len(lines) == 1
        assert 'base' in lines[0]

        lines = mid.buffer[:]
        assert len(lines) == 5
        assert 'aa' in lines[0]
        assert 'bb' in lines[1]
        assert 'cc' in lines[2]

        lines = right.buffer[:]
        assert len(lines) == 1
        assert 'aa_aa' in lines[0]


def test_navigation(tree, vim_ctx):
    os.environ['NVFM_START_PATH'] = str(tree)
    with vim_ctx() as vim:
        left, mid, right = vim.windows
        vim.feedkeys('j')
        assert right.buffer[:] == ['bb_line_1', 'bb_line_2']
        vim.feedkeys('j')
        assert re.match(r'\(.*empty.*\)', '\n'.join(right.buffer[:]))
        vim.feedkeys('j')
        assert re.match(r'\(.*empty.*\)', '\n'.join(right.buffer[:]))
        # Go to top
        vim.feedkeys('gg')
        # Enter dir "aaa"
        vim.feedkeys('l')
        assert 'aa' in left.buffer[:][0]
        assert 'aa_aa' in mid.buffer[:][0]
        assert 'aa_aa_f' in right.buffer[:][0]
        vim.feedkeys('h')
        assert 'base' in left.buffer[:][0]
        assert 'aa' in mid.buffer[:][0]
        assert 'aa_aa' in right.buffer[:][0]


def test_navigate_to_root(tree, vim_ctx):
    os.environ['NVFM_START_PATH'] = str(tree)
    with vim_ctx() as vim:
        for _ in tree.parts:
            vim.feedkeys('h')
        left, mid, right = vim.windows
        assert re.match(r'\(.*nothing.*\)', '\n'.join(left.buffer[:]))


def test_format_line_extra(tree):
    """If a dir has only one child, show the child in the dir view"""
    path = tree / 'aa'
    stat_res, stat_error = stat_path(path)
    line, hls = DirectoryView._format_line(str(path), stat_res, 'some_hl_group')
    assert 'aa/aa_aa/aa_aa_f' in line


def test_format_line_extra2(tree):
    """Display number of items in a directory"""
    path = tree / 'ee'
    stat_res, stat_error = stat_path(path)
    line, hls = DirectoryView._format_line(str(path), stat_res, 'some_hl_group')
    assert 'ee/ +3' in line


def test_format_line_extra3(tree):
    path = tree / 'cc'
    stat_res, stat_error = stat_path(path)
    line, hls = DirectoryView._format_line(str(path), stat_res, 'some_hl_group')
    assert 'cc/ +0' in line


def test_history():
    history = History()
    history.add('foo')
    assert history.go(-1) is None
    assert history.go(1) is None
    assert history.go(0) == 'foo'
    history.add('bar')
    assert history.go(0) == 'bar'
    assert history.go(-1) == 'foo'
    assert history.go(-1) is None
    history.add('baz')
    history.add('spam')
    assert history.all == ['foo', 'baz', 'spam']
    assert history.go(0) == 'spam'
    assert history.go(1) is None
    assert history.go(-1) == 'baz'
    assert history.go(-1) == 'foo'
    assert history.go(-1) is None
    assert history.go(1) == 'baz'
    history.add('ham')
    assert history.go(0) == 'ham'
    assert history.all == ['foo', 'baz', 'ham']


def test_focus(tree, vim_ctx):
    os.environ['NVFM_START_PATH'] = str(tree)
    with vim_ctx() as vim:
        vim.call('NvfmEnter', str(tree / 'ee'))
        left, mid, right = vim.windows
        assert left.cursor == [5, 0]
        assert mid.cursor == [1, 0]
        assert right.cursor == [1, 0]
        vim.feedkeys('j') # focus gg/ inside base/ee/
        vim.feedkeys('h') # enter base/
        assert left.cursor == [1, 0]
        assert mid.cursor == [5, 0]
        assert right.cursor == [2, 0]
        vim.feedkeys('l') # enter base/ee/
        assert left.cursor == [5, 0]
        assert mid.cursor == [2, 0]
        assert right.cursor == [1, 0]
