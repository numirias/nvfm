import os
import stat
from stat import S_ISDIR, S_ISLNK

from .util import convert_size, hexdump, list_files, logger, stat_path

# Files above this size will be truncated before preview
PREVIEW_SIZE_LIMIT = 100_000

# Max number of bytes in a hexdump preview
HEXDUMP_LIMIT = 16*256


class View:

    VIEW_PREFIX = 'nvfm_view:'

    def __init__(self, plugin, path, **kwargs):
        self._plugin = plugin
        self._vim = plugin._vim
        self._path = path
        self._buf = self._make_buf(path)
        self.setup(**kwargs)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self._path)

    def _make_buf(self, path):
        buf = self._vim.request(
            'nvim_create_buf',
            True, # listed
            False, # scratch
        )
        logger.debug(('new buf', buf))
        # TODO Do bulk request
        buf.request('nvim_buf_set_option', 'buftype', 'nowrite')
        buf.request('nvim_buf_set_option', 'bufhidden', 'hide')
        if path is not None:
            buf.name = self.VIEW_PREFIX + str(path)
        return buf

    def load_after(self, panel):
        """Event: The view has been loaded into `panel`."""

    def setup(self, *args, **kwargs):
        """Event: Do things to setup the buffer."""

    def draw_message(self, msg, hl_group=None):
        if hl_group is None:
            hl_group = 'NvfmMessage'
        logger.debug(repr(hl_group))
        buf = self._buf
        buf[:] = [msg]
        buf.add_highlight(hl_group, 0, 0, -1, src_id=-1)


class MessageView(View):

    def setup(self, message, hl_group=None):
        self.draw_message(message, hl_group)

    def load_after(self, panel):
        panel._win.request('nvim_win_set_option', 'wrap', True)


class FileView(View):

    def setup(self):
        try:
            self.draw()
        except OSError as e:
            self.draw_message(str(e), 'Error')
            return
        self._detect_filetype()

    def draw(self):
        # TODO Better heuristics to detect binary files
        buf = self._buf
        path = self._path
        st = path.stat()
        mode = stat.filemode(st.st_mode)
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
        cur = self._vim.current
        buf_save = cur.buffer
        cur.buffer = self._buf
        self._vim.command('filetype detect')
        cur.buffer = buf_save

    def _read_file(self, path):
        with open(path, 'rb') as f:
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

    def setup(self, focus=None):
        self.focus_linenum = None
        try:
            self.children = list_files(self._path)
        except OSError as e:
            # TODO Do we need to catch the OSError anymore?
            self.children = []
            self.draw_message(str(e), 'Error')
            return
        if not self.children:
            self.draw_message('(directory empty)')
            return
        self.draw(focus)

    def load_after(self, panel):
        if self.children:
            # XXX Is this needed every time, or just initially?
            panel._win.request('nvim_win_set_option', 'cursorline', True)

        if self.focus_linenum is not None:
            # Note: The updated cursorline position might not be immediately
            # visible if another event didn't trigger the draw (like a tabline
            # update)
            panel._win.cursor = [self.focus_linenum, 0]

    @property
    def empty(self):
        return not self.children

    def focus(self, linenum):
        # TODO Prevent this from firing multiple times
        # if linenum == self.focus_linenum:
        #     return
        self.focus_linenum = linenum
        self._plugin._events.publish('focus_dir_item', self, self.focus_item)

    @property
    def focus_item(self):
        try:
            return self.children[self.focus_linenum - 1]
        except IndexError:
            return None

        self.focus_linenum = None

    def draw(self, focus_item=None):
        """Render current directory."""
        # focus_item = focus_item or self._plugin.focus_cache.get(self.path)
        lines = []
        highlights = []
        focus_linenum = None
        for linenum, item in enumerate(self.children):
            stat_res, stat_error = stat_path(item)
            if stat_error is None:
                line = self._format_line(item, stat_res)
            else:
                line = str(stat_error)
            lines.append(line)
            # TODO Change focus_linenum to focus_item
            if item == focus_item:
                focus_linenum = linenum
            hl_group = self._plugin._color_manager.file_hl_group(item, stat_res, stat_error)

            highlights.append((linenum, 'FileMeta', 0, 10))
            if hl_group is not None:
                highlights.append((linenum, hl_group, 18, -1))
        self._buf[:] = lines
        self._apply_highlights(highlights)
        # Attempt to restore focus
        if focus_linenum is not None:
            self.focus_linenum = focus_linenum + 1

    def _format_line(self, path, stat_res):
        # TODO Orphaned symlink
        mode = stat_res.st_mode
        size = convert_size(stat_res.st_size)
        name = path.name
        if S_ISDIR(mode):
            name += '/'
        if S_ISLNK(mode):
            try:
                target = os.readlink(path)
            except OSError:
                target = '?'
            name += ' -> ' + target
        return f'{stat.filemode(mode)} {size:>6} {name}'

    def _apply_highlights(self, highlights):
        # TODO Apply highlights lazily
        buf = self._buf
        for linenum, hl_group, start, stop in highlights:
            # TODO We can skip colorNormal
            # TODO don't hardcode horizontal hl offset
            # TODO Bulk
            logger.debug(('add_highlight', hl_group, linenum))
            buf.add_highlight(hl_group, linenum, start, stop, src_id=-1)
