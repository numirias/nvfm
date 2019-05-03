# -*- coding: future_fstrings -*-
import itertools
import os
from pathlib import Path
import stat
from stat import (S_ISBLK, S_ISCHR, S_ISDIR, S_ISFIFO, S_ISLNK, S_ISREG,
                  S_ISSOCK)

from .util import convert_size, hexdump, logger, stat_path

# Files above this size will be truncated before preview
PREVIEW_SIZE_LIMIT = 10**5

# Max number of bytes in a hexdump preview
HEXDUMP_LIMIT = 16 * 256


class Views:

    def __init__(self, state, vim):
        self._state = state
        self._vim = vim
        self._views = {}

    def __getitem__(self, key):
        try:
            return self._views[key]
        except KeyError:
            pass
        view = make_view(self._state, self._vim, key)
        self._views[key] = view
        return view

    def __setitem__(self, key, val):
        self._views[key] = val

    def __delitem__(self, key):
        self._views[key].remove()
        del self._views[key]

    def __getattr__(self, key):
        return getattr(self._views, key)


def make_view(state, vim, item):
    """Create and return a View() instance that displays `item`."""
    args = (state, vim, item)
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
    return MessageView(*args, message='(%s)' % mode_to_type_str(mode))


def mode_to_type_str(mode):
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


class ViewHelpersMixin:

    def draw_message(self, msg, hl_group=None):
        if hl_group is None:
            hl_group = 'NvfmMessage'
        logger.debug(repr(hl_group))
        buf = self.buf
        buf[:] = [msg]
        buf.add_highlight(hl_group, 0, 0, -1, src_id=-1)


class View(ViewHelpersMixin):

    VIEW_PREFIX = 'nvfm_view:'
    cursor = None

    def __init__(self, state, vim, path):
        logger.debug(('new view', path))
        self._state = state
        self._vim = vim
        self.path = path
        self.buf = self._create_buf()
        self._buf_configured = False
        self.dirty = True

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.path)

    def _create_buf(self):
        return self._vim.request(
            'nvim_create_buf',
            True, # listed
            False, # scratch
        )

    def configure_buf(self):
        if self._buf_configured:
            return
        buf = self.buf
        # TODO Do bulk request
        buf.request('nvim_buf_set_option', 'buftype', 'nowrite')
        buf.request('nvim_buf_set_option', 'bufhidden', 'hide')
        if self.path is not None:
            buf.name = self.VIEW_PREFIX + str(self.path)
        self._buf_configured = True

    def configure_win(self, win):
        pass

    def load(self):
        """Load the view. Redraw if it's dirty."""
        if self.dirty:
            self.draw()
            self.dirty = False

    def unload(self):
        pass

    def draw(self):
        raise NotImplementedError()

    def remove(self):
        """Called when the view is removed from the view list."""
        self._vim.command('bwipeout! %d' % self.buf.number)


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


class DirectoryView(View):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TODO Make focus private?
        # Line number of focused item (starts at 1)
        self.focus = None
        # List of items in directory (of os.DirEntry, not pathlib.Path)
        self.items = None
        self._folds = None

    def configure_win(self, win):
        if self.items:
            win.request('nvim_win_set_option', 'cursorline', True)

    def unload(self):
        self.clear_filter()

    def draw(self):
        # Only save and restore focus if it has been explicitly set
        restore_focus = self.focus is not None
        if restore_focus:
            focused_item = self.focused_item
        self._draw()
        if restore_focus:
            self.focused_item = focused_item

    def _draw(self):
        try:
            self.items = self._list_files(
                self.path, self._state.options['sort'])
        except OSError as e:
            self.items = []
            self.draw_message(str(e), 'Error')
            return
        if not self.items:
            self.draw_message('(directory empty)')
            return
        self._render_items()

    @property
    def cursor(self):
        return [self.focus or 1, 0]

    @cursor.setter
    def cursor(self, pos):
        self._set_focus(pos[0])
        if pos != self.cursor:
            raise CursorAdjusted()

    def _set_focus(self, linenum):
        """Set focus to `linenum` if it is a legal line number."""
        if not self._folds:
            # Set requested line because there are no folds
            self.focus = linenum
            return
        for start, stop in self._folds:
            if start <= linenum <= stop:
                # Determine candidate line numbers that aren't in a fold
                if self.focus is None or linenum < self.focus:
                    candidates = (start - 1, stop + 1)
                else:
                    candidates = (stop + 1, start - 1)
                break
        else:
            # Set requested line because it's not in a fold
            self.focus = linenum
            return
        for c in candidates:
            if 1 <= c <= len(self.items):
                # Use this candidate because it's not out of bounds
                self.focus = c
                return
        # All candidates are out of bounds
        self.focus = None
        logger.debug('cursor moved oob')

    @property
    def empty(self):
        return not self.items

    @property
    def focused_item(self):
        """Return the currently focused item. Return `None` if no items exist
        or all items are hidden."""
        if not self.items:
            return None
        # Check if all items are hidden (a fold over all lines)
        if self._folds == [(1, len(self.items))]:
            return None
        try:
            return Path(self.items[(self.focus or 0) - 1].path)
        except IndexError:
            return None

    @focused_item.setter
    def focused_item(self, item):
        if item is None:
            return
        self.focus = [c.name for c in self.items].index(item.name) + 1

    def _render_items(self):
        """Render directory listing."""
        lines = []
        hls = []
        for linenum, item in enumerate(self.items):
            try:
                stat_res = item.stat(follow_symlinks=False)
            except OSError as stat_error:
                line = str(stat_error)
            else:
                hl_group = self._state.colors.file_hl_group(item, stat_res)
                line, line_hls = self._format_line(item.path, stat_res,
                                                   hl_group)
                for hl in line_hls:
                    hls.append((linenum, *hl))
            lines.append(line)
        self.buf[:] = lines
        self._apply_highlights(hls)

    @staticmethod
    def _list_files(path, sort_func):
        """List all files in path."""
        return list(sort_func(os.scandir(str(path))))

    @staticmethod
    def _format_line(path_str, stat_res, hl_group):
        # TODO Orphaned symlink
        mode = stat_res.st_mode
        size = convert_size(stat_res.st_size)
        line = stat.filemode(mode) + ' ' + size.rjust(6) + ' '
        hls = []
        extra = None
        name = Path(path_str).name
        if S_ISDIR(mode):
            name += '/'
            extra = DirectoryView._format_dir_extra(mode, path_str)
        elif S_ISLNK(mode):
            extra = DirectoryView._format_link_extra(path_str)
        if hl_group is not None:
            hls.append((hl_group, len(line), len(line) + len(name)))
        line += name
        if extra:
            hls.append(('FileMeta', len(line), len(line) + len(extra)))
            line += extra
        hls.append(('FileMeta', 0, 10))
        return line, hls

    @staticmethod
    def _format_dir_extra(mode, path_str):
        extra = ''
        for _ in range(4):
            if not S_ISDIR(mode):
                break
            try:
                items = os.scandir(path_str)
            except OSError:
                break
            try:
                first = next(items)
            except StopIteration:
                extra += ' +0'
                break
            try:
                next(items)
            except StopIteration:
                pass
            else:
                extra += ' +' + str(2 + sum(1 for _ in items))
                break
            path_str = os.path.join(path_str, first.name)
            try:
                mode = first.stat().st_mode
            except OSError:
                break
            extra += first.name + ('/' if S_ISDIR(mode) else '')
        return extra

    @staticmethod
    def _format_link_extra(path_str):
        try:
            target = os.readlink(path_str)
        except OSError:
            target = '?'
        return ' -> ' + target

    def _apply_highlights(self, highlights):
        # TODO Apply highlights lazily
        for linenum, hl_group, start, stop in highlights:
            # TODO We can skip colorNormal
            # TODO don't hardcode horizontal hl offset
            # TODO Bulk
            logger.debug(('add_highlight', hl_group, linenum))
            self.buf.add_highlight(hl_group, linenum, start, stop, src_id=-1)

    def filter(self, query):
        """Hide all items that don't match `query`.

        Hiding is done by adding vim folds.
        """
        # TODO Handle changed sorting order and filtering
        self.clear_filter()
        folds = []
        # The line number in which the current fold started
        start_idx = None
        first_result = None
        for idx, item in enumerate(itertools.chain(self.items, (None,))):
            if item is None or query in item.name.lower():
                if first_result is None:
                    first_result = idx + 1
                if start_idx is not None:
                    folds.append((start_idx + 1, idx))
                    start_idx = None
            else:
                if start_idx is None:
                    start_idx = idx
        for start, end in folds:
            # TODO Bulk request
            self._vim.command(':%d,%dfold' % (start, end))
        if first_result is not None:
            # TODO Doesn't reliably focus the first result
            self.focus = first_result
        self._folds = folds

    def clear_filter(self):
        if self._folds:
            # Eliminate all folds (zE)
            self._vim.command('normal! zE')
            self._folds = None


class CursorAdjusted(Exception):
    pass
