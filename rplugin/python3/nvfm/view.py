import os
import stat

from .util import logger, hexdump, convert_size, natural_sort_key, list_files


# Files above this size will be truncated before preview
PREVIEW_SIZE_LIMIT = 100_000

# Max number of bytes in a hexdump preview
HEXDUMP_LIMIT = 16*256

class View:

    def __init__(self, plugin, path):
        self._plugin = plugin
        self._vim = plugin._vim
        self._path = path
        self._buf = self._make_buf(path)

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
            buf.name = 'preview' + str(path)
        return buf

    def load_into(self, panel):
        logger.debug(('load', self, 'into', panel))
        if panel.buf == self._buf:
            return
        panel.buf = self._buf
        panel._view = self

    def draw_message(self, msg, hl_group='Normal'):
        buf = self._buf
        buf[:] = [msg]
        buf.add_highlight(hl_group, 0, 0, -1, src_id=-1)


class MessageView(View):

    def __init__(self, plugin, path, msg, hl_group):
        super().__init__(plugin, path)
        self._msg = msg
        self._hl_group = hl_group
        self.draw()

    def draw(self):
        buf = self._buf
        buf[:] = [self._msg]
        buf.add_highlight(self._hl_group, 0, 0, -1, src_id=-1)


class FileView(View):

    def __init__(self, plugin, path):
        super().__init__(plugin, path)
        try:
            self.draw()
        except OSError as e:
            self.draw_message(str(e), 'Error')

    def draw(self):
        # TODO Better heuristics to detect binary files
        buf = self._buf
        path = self._path
        st = path.stat()
        mode = stat.filemode(st.st_mode)
        size = st.st_size

        data, need_hexdump = self._read_file(path)
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

    def  __init__(self, plugin, path, focus=None):
        super().__init__(plugin, path)
        self.focus_linenum = None
        try:
            self.children = list_files(path)
        except OSError as e:
            self.children = []
            self.draw_message(str(e), 'Error')
            return
        if not self.children:
            self.draw_message('(directory empty)', 'Comment')
            return
        self.draw(focus)

    def load_into(self, panel):
        super().load_into(panel)

        if self.children:
            # XXX Is this needed every time, or just initially?
            panel._win.request('nvim_win_set_option', 'cursorline', True)

        # logger.debug(('prev cursor', panel._win.cursor))
        # logger.debug(('load', panel, self._path, 'line', self.focus_linenum))
        if self.focus_linenum is not None:
            # logger.debug(('restore focus', self, self._path, self.focus_linenum, panel))
            # Note: The updated cursorline position might not be immediately
            # visible if another event didn't trigger the draw (like a tabline
            # update)
            panel._win.cursor = [self.focus_linenum, 0]

    # def unload(self):
    #     pass

    def is_empty(self):
        return not self.children

    def focus(self, linenum):
        if linenum == self.focus_linenum:
            return
        self.focus_linenum = linenum

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
            line = self._format_line(item)
            # TODO Change focus_linenum to focus_item
            if item == focus_item:
                focus_linenum = linenum
            hl_group = self._plugin._color_manager.file_hl_group(item)
            if hl_group is not None:
                highlights.append((linenum, hl_group))
            lines.append(line)
        self._buf[:] = lines
        self._apply_highlights(highlights)
        # Attempt to restore focus
        if focus_linenum is not None:
            self.focus_linenum = focus_linenum + 1

    def _format_line(self, path):
        try:
            st = path.lstat()
        except FileNotFoundError:
            ... # TODO
        # TODO FIle doesn't exist
        # TODO Orphaned symlink
        mode = stat.filemode(st.st_mode)
        size = convert_size(st.st_size)
        name = path.name
        if path.is_dir():
            name += '/'
        if path.is_symlink():
            name += ' -> ' + os.readlink(path)
        return f'{mode} {size:>6} {name}'

    def _apply_highlights(self, highlights):
        buf = self._buf
        for linenum, colorcode in highlights:
            # TODO We can skip colorNormal
            # TODO don't hardcode horizontal hl offset
            # TODO Bulk
            logger.debug(('add_highlight', f'color{colorcode}', linenum))
            buf.add_highlight(f'color{colorcode}', linenum, 18, -1, src_id=-1)
