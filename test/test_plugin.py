import os
from pathlib import Path
import re

import pytest

from nvfm.directory_view import format_line
from nvfm.plugin import History, Plugin
from nvfm.util import stat_path
from nvfm.view import DirectoryView

from .test_helpers import make_tree


@pytest.fixture
def tree(tmpdir_factory):
    root = Path(str(tmpdir_factory.mktemp('tree')))
    make_tree(root, '''
    base/
        aa1/
            aa2/
                aa3
        bb=bb_line_1\\nbb_line_2
        cc/
        dd
        ee/
            ff/
                ii/
                jj/
            gg/
                aa/
                bbXXbb/
                    qqq/
                cc
                gx
                XX/
                zz/
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
        assert 'aa1' in lines[0]
        assert 'bb' in lines[1]
        assert 'cc' in lines[2]

        lines = right.buffer[:]
        assert len(lines) == 1
        assert 'aa2' in lines[0]


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
        vim.feedkeys('gg')
        vim.feedkeys('l')
        assert 'aa1' in left.buffer[:][0]
        assert 'aa2' in mid.buffer[:][0]
        assert 'aa3' in right.buffer[:][0]
        vim.feedkeys('h')
        assert 'base' in left.buffer[:][0]
        assert 'aa1' in mid.buffer[:][0]
        assert 'aa2' in right.buffer[:][0]


def test_navigate_to_root(tree, vim_ctx):
    os.environ['NVFM_START_PATH'] = str(tree)
    with vim_ctx() as vim:
        for _ in tree.parts:
            vim.feedkeys('h')
        left, mid, right = vim.windows
        assert re.match(r'\(.*nothing.*\)', '\n'.join(left.buffer[:]))


def test_format_line_extra(tree):
    """If a dir has only one child, show the child in the dir view"""
    path = tree / 'aa1'
    stat_res, stat_error = stat_path(path)
    line, hls = format_line(str(path), stat_res, 'some_hl_group', '', lambda x: '')
    assert 'aa1/aa2/aa3' in line


def test_format_line_extra2(tree):
    """Display number of items in a directory"""
    path = tree / 'ee'
    stat_res, stat_error = stat_path(path)
    line, hls = format_line(str(path), stat_res, 'some_hl_group', '', lambda x: '')
    assert 'ee/ +3' in line


def test_format_line_extra3(tree):
    path = tree / 'cc'
    stat_res, stat_error = stat_path(path)
    line, hls = format_line(str(path), stat_res, 'some_hl_group', '', lambda x: '')
    assert 'cc/ +0' in line


def test_history():
    history = History()
    history.add('foo')
    with pytest.raises(IndexError):
        assert history.go(-1)
    with pytest.raises(IndexError):
        assert history.go(1)
    assert history.go(0) == 'foo'
    history.add('bar')
    assert history.go(0) == 'bar'
    assert history.go(-1) == 'foo'
    with pytest.raises(IndexError):
        assert history.go(-1)
    history.add('baz')
    history.add('spam')
    assert history.all == ['foo', 'baz', 'spam']
    assert history.go(0) == 'spam'
    with pytest.raises(IndexError):
        assert history.go(1)
    assert history.go(-1) == 'baz'
    assert history.go(-1) == 'foo'
    with pytest.raises(IndexError):
        assert history.go(-1)
    assert history.go(1) == 'baz'
    history.add('ham')
    assert history.go(0) == 'ham'
    assert history.all == ['foo', 'baz', 'ham']


def test_navigate_history(tree, vim_ctx):
    os.environ['NVFM_START_PATH'] = str(tree)
    with vim_ctx() as vim:
        left, mid, right = vim.windows
        vim.feedkeys('l')
        vim.feedkeys('b')
        assert 'aa1' in mid.buffer[:][0]
        vim.feedkeys('b')
        assert 'aa2' in mid.buffer[:][0]
        vim.feedkeys('l')
        assert 'aa3' in mid.buffer[:][0]
        vim.feedkeys('b')
        assert 'aa2' in mid.buffer[:][0]
        vim.feedkeys('B')
        assert 'aa3' in mid.buffer[:][0]


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


def test_sort_option(tree, vim_ctx):
    os.environ['NVFM_START_PATH'] = str(tree / 'ee')
    with vim_ctx() as vim:
        left, mid, right = vim.windows
        vim.feedkeys('sa')
        assert 'aa1' in left.buffer[:][0]
        assert 'ff' in mid.buffer[:][0]
        assert 'ii' in right.buffer[:][0]
        assert mid.cursor[0] == 1
        vim.feedkeys('sA')
        assert mid.cursor[0] == 3
        assert 'aa1' in left.buffer[:][-1]
        assert 'ff' in mid.buffer[:][-1]
        assert 'ii' in right.buffer[:][-1]


def test_refresh_empty_dir(tree, vim_ctx):
    os.environ['NVFM_START_PATH'] = str(tree / 'cc')
    with vim_ctx() as vim:
        left, mid, right = vim.windows
        vim.call('NvfmRefresh')
        assert re.match(r'\(.*empty.*\)', '\n'.join(mid.buffer[:]))


def test_refresh_all(tree, vim_ctx):
    os.environ['NVFM_START_PATH'] = str(tree / 'ee')
    with vim_ctx() as vim:
        left, mid, right = vim.windows
        vim.feedkeys('j')
        vim.feedkeys('sA')
        vim.feedkeys('j') # focus ff/ again
        assert 'jj' in right.buffer[:][0]
        # Since the cursor in the right window is at its default position and
        # was never explicitly set, it should remain at the top position, even
        # after the sorting order changed.
        assert right.cursor[0] == 1


def test_dont_save_default_focus(tree, vim_ctx):
    os.environ['NVFM_START_PATH'] = str(tree / 'ee')
    with vim_ctx() as vim:
        left, mid, right = vim.windows
        assert right.cursor[0] == 1
        vim.feedkeys('sa')
        assert right.cursor[0] == 1
        vim.feedkeys('sA')
        assert right.cursor[0] == 1


def test_filter(tree, vim_ctx):
    os.environ['NVFM_START_PATH'] = str(tree / 'ee/gg')
    with vim_ctx() as vim:
        def openfolds():
            vim.vars['openfolds'] = []
            vim.command('folddoopen call add(g:openfolds, line("."))')
            return vim.vars['openfolds']
        left, mid, right = vim.windows
        vim.feedkeys('fx') # filter for "x" but don't confirm yet
        assert 'qqq' in right.buffer[:][0]
        vim.feedkeys('\n') # confirm filter
        assert mid.cursor[0] == 2 # assert that cursor has jumped to first result
        assert openfolds() == [2, 4, 5]
        vim.feedkeys('fxx\n') # search for "xx"
        assert openfolds() == [2, 5]
        vim.feedkeys('\x1b') # clear search with esc
        assert openfolds() == list(range(1, 7))
        vim.feedkeys('fx\n') # search for "x"
        assert openfolds() == [2, 4, 5]
        vim.feedkeys('hl') # go to previous dir and back
        assert openfolds() == list(range(1, 7)) # assert that search is cleared
        vim.feedkeys('ffail\n') # search for "fail"
        assert openfolds() == []


def test_cursor_adjustment(tree, vim_ctx):
    os.environ['NVFM_START_PATH'] = str(tree)
    with vim_ctx() as vim:
        left, mid, right = vim.windows
        mid.cursor = [1, 2]
        assert mid.cursor == [1, 0]


def test_column_option(tree, vim_ctx):
    os.environ['NVFM_START_PATH'] = str(tree)
    with vim_ctx() as vim:
        left, mid, right = vim.windows
        assert re.match(r'.*drwx.*\s+\d.*\s+', mid.buffer[0])
        vim.call('NvfmSet', 'columns', ['size'])
        vim.call('NvfmRefresh')
        assert not re.match(r'.*drwx.*', mid.buffer[0])
        vim.call('NvfmSet', 'columns', ['mode'])
        vim.call('NvfmRefresh')
        assert re.match(r'.*drwx.*', mid.buffer[0])


def test_time_format_option(tree, vim_ctx):
    os.environ['NVFM_START_PATH'] = str(tree)
    with vim_ctx() as vim:
        left, mid, right = vim.windows
        assert re.match(r'.*\snow\s.*', mid.buffer[0])
