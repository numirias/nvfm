# -*- coding: future_fstrings -*-
import os
from pathlib import Path
from stat import S_ISBLK, S_ISCHR, S_ISDIR, S_ISFIFO, S_ISREG, S_ISSOCK

from .base_view import View
from .directory_view import DirectoryView
from .util import hexdump, stat_path

# Files above this size will be truncated before preview
PREVIEW_SIZE_LIMIT = 10**5

# Max number of bytes in a hexdump preview
HEXDUMP_LIMIT = 16 * 256


class Views:

    def __init__(self, session, vim):
        self._s = session
        self._vim = vim
        self._views = {}

    def __getitem__(self, key):
        try:
            return self._views[key]
        except KeyError:
            pass
        view = make_view(self._s, self._vim, key)
        view.protocol_init()
        self._views[key] = view
        return view

    def __setitem__(self, key, val):
        self._views[key] = val

    def __delitem__(self, key):
        self._views[key].remove()
        del self._views[key]

    def __getattr__(self, key):
        return getattr(self._views, key)

    def mark_all_dirty(self):
        for view in self._views.values():
            view.dirty = 2


def make_view(session, vim, item):
    """Create and return a View() instance that displays `item`."""
    args = (session, vim, item)
    if item is None:
        # TODO Use the same view always
        return MessageView(*args, message='(nothing to show)')
    stat_res, stat_error = stat_path(item, lstat=False)
    if stat_error is not None:
        return MessageView(
            *args, message=str(stat_error), hl_group='NvfmError')
    mode = stat_res.st_mode
    if S_ISDIR(mode):
        return DirectoryView(*args)
    # TODO Check the stat() of the link
    if S_ISREG(mode):
        return FileView(*args)
    return MessageView(*args, message='(%s)' % filetype_str(mode))


def filetype_str(mode):
    if S_ISCHR(mode):
        msg = 'character special device file'
    elif S_ISBLK(mode):
        msg = 'block special device file'
    elif S_ISFIFO(mode):
        msg = 'FIFO (named pipe)'
    elif S_ISSOCK(mode):
        msg = 'socket'
    else:
        msg = 'unknown file type'
    return msg

class EmptyView(View):

    # pylint:disable=super-init-not-called
    def __init__(self):
        self.path = Path(os.getcwd())


class MessageView(View):

    def __init__(self, *args, **kwargs):
        self._message = kwargs.pop('message')
        self._hl_group = kwargs.pop('hl_group', None)
        super().__init__(*args, **kwargs)

    def draw(self):
        self.draw_message(self._message, self._hl_group)

    def configure_win(self, win):
        win.request('nvim_win_set_option', 'wrap', True)


class FileView(View):

    def draw(self):
        try:
            self._draw()
        except OSError as e:
            self.draw_message(str(e), 'Error')

    def _draw(self):
        # TODO Better heuristics to detect binary files
        buf = self.buf
        path = self.path
        st = path.stat()
        size = st.st_size

        data, need_hexdump = self._read_file(path)
        if not data:
            self.draw_message('(file empty)', 'NvfmMessage')
            return
        if need_hexdump:
            # columns = 8 if self._win.width < 68 else 16
            columns = 16
            data = hexdump(data[:HEXDUMP_LIMIT], columns=columns)
            buf.request('nvim_buf_set_option', 'filetype', 'xxd')
        lines = data.decode('utf-8').splitlines()
        if size > PREVIEW_SIZE_LIMIT:
            # TODO Better indicator for truncated file view
            lines += ['...']
        buf[:] = lines
        self._detect_filetype()

    def _detect_filetype(self):
        cur = self._vim.current
        buf_save = cur.buffer
        cur.buffer = self.buf
        self._vim.command('filetype detect')
        cur.buffer = buf_save

    @staticmethod
    def _read_file(path):
        with open(str(path), 'rb') as f:
            data = f.read(PREVIEW_SIZE_LIMIT)
            try:
                data.decode('utf-8')
            except UnicodeDecodeError:
                # This is not valid utf-8, so do a hexdump
                need_hexdump = True
            else:
                need_hexdump = False
                # No hexdump, so read up to preview size limit
        return data, need_hexdump
