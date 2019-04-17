# -*- coding: future_fstrings -*-
import os
import stat
from stat import S_ISDIR, S_ISLNK
from pathlib import Path

from .util import convert_size, hexdump, logger

# Files above this size will be truncated before preview
PREVIEW_SIZE_LIMIT = 10**5

# Max number of bytes in a hexdump preview
HEXDUMP_LIMIT = 16 * 256


class View:

    VIEW_PREFIX = 'nvfm_view:'
    cursor = None

    def __init__(self, plugin, path):
        logger.debug(('new view', path))
        self._plugin = plugin
        self.path = path
        self.buf = None

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.path)

    def setup_buf(self, buf):
        # TODO Do bulk request
        buf.request('nvim_buf_set_option', 'buftype', 'nowrite')
        buf.request('nvim_buf_set_option', 'bufhidden', 'hide')
        if self.path is not None:
            buf.name = self.VIEW_PREFIX + str(self.path)
        self.buf = buf

    def load_done(self, panel):
        pass

    def create_buf_post(self):
        pass

    def draw_message(self, msg, hl_group=None):
        if hl_group is None:
            hl_group = 'NvfmMessage'
        logger.debug(repr(hl_group))
        buf = self.buf
        buf[:] = [msg]
        buf.add_highlight(hl_group, 0, 0, -1, src_id=-1)


class MessageView(View):

    def __init__(self, *args, **kwargs):
        self._message = kwargs.pop('message')
        self._hl_group = kwargs.pop('hl_group', None)
        super().__init__(*args, **kwargs)

    def create_buf_post(self):
        self.draw_message(self._message, self._hl_group)

    def load_done(self, panel):
        # XXX Is this needed every time, or just initially?
        panel.win.request('nvim_win_set_option', 'wrap', True)


class FileView(View):

    def create_buf_post(self):
        try:
            self.draw()
        except OSError as e:
            self.draw_message(str(e), 'Error')
            return
        self._detect_filetype()

    def draw(self):
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

    def _detect_filetype(self):
        cur = self._plugin.vim.current
        buf_save = cur.buffer
        cur.buffer = self.buf
        self._plugin.vim.command('filetype detect')
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
        self.focus = 1
        self.children = None

    @property
    def cursor(self):
        return [self.focus, 0]

    def create_buf_post(self):
        try:
            self.children = self._list_files(self.path, self._plugin.sort_func)
        except OSError as e:
            # TODO Do we need to catch the OSError anymore?
            self.children = []
            self.draw_message(str(e), 'Error')
            return
        if not self.children:
            self.draw_message('(directory empty)')
            return
        self.draw()

    def load_done(self, panel):
        if self.children:
            # XXX Is this needed every time, or just initially?
            panel.win.request('nvim_win_set_option', 'cursorline', True)

    @property
    def empty(self):
        return not self.children

    @property
    def focused_item(self):
        try:
            return Path(self.children[self.focus - 1].path)
        except IndexError:
            return None

    @focused_item.setter
    def focused_item(self, item):
        self.focus = [c.name for c in self.children].index(item.name) + 1

    def draw(self):
        """Render current directory."""
        lines = []
        hls = []
        for linenum, child in enumerate(self.children):
            try:
                stat_res = child.stat(follow_symlinks=False)
            except OSError as stat_error:
                line = str(stat_error)
            else:
                hl_group = self._plugin.colors.file_hl_group(child, stat_res)
                line, line_hls = self._format_line(child.path, stat_res,
                                                   hl_group)
                for hl in line_hls:
                    hls.append((linenum, *hl))
            lines.append(line)
        self.buf[:] = lines
        self._apply_highlights(hls)

    @staticmethod
    def _list_files(path, sort_func):
        """List all files in path."""
        return sort_func(os.scandir(str(path)))

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
                children = os.scandir(path_str)
            except OSError:
                break
            try:
                first = next(children)
            except StopIteration:
                extra += ' +0'
                break
            try:
                next(children)
            except StopIteration:
                pass
            else:
                extra += ' +' + str(2 + sum(1 for _ in children))
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
