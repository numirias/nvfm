import getpass
import os
# TODO Wrap Path for static stat etc
from pathlib import Path
import platform
import stat

import pynvim

from .util import logger, hexdump, convert_size, natural_sort_key, list_files
from .color import ColorManager

HOST = platform.node()
USER = getpass.getuser()


# Files above this size will be truncated before preview
PREVIEW_SIZE_LIMIT = 100_000

# Max number of bytes in a hexdump preview
HEXDUMP_LIMIT = 16*256


def win_set_buf(win, buf):
    return win.request('nvim_win_set_buf', buf)


class Panel:

    def __init__(self, plugin, win, buf, use_cursorline=True):
        self._plugin = plugin
        self._win = win
        self._buf = buf
        self.path = None
        self.children = []
        self.focus_linenum = None
        # Method to focus the current line (TODO: explain why)
        self._use_cursorline = use_cursorline

    @property
    def focus_item(self):
        try:
            return self.children[self.focus_linenum - 1]
        except IndexError:
            return None

    def is_empty_dir(self):
        return not self.children

    def save_focus(self):
        """Cache item currently focused in this panel."""
        # TODO Check if self.path is dir
        if self.path is None:
            # We are not in a dir
            return
        if not self.children:
            # There are no items in this dir
            return
        self._plugin.focus_cache[self.path] = self.focus_item
        self._plugin.focus_cache[self.path.parent] = self.path
        logger.debug(('saved focus for', self.path))

    def view(self, item, focus_item=None):
        """View `item` in the panel.

        `item` can be a file or a directory. `focused_item` can be set to the
        item that should be highlighted.

        """
        # Reset cur line, so CursorMoved notices that the current line has changed
        self.focus_linenum = None
        self.children = []
        self.path = item
        if item is None:
            self._view_nothing()
            return
        if item.is_dir():
            # Make right window display the preview buffer if it isn't already
            if self._win.buffer == self._buf:
                logger.debug(('STAY'))
            else:
                win_set_buf(self._win, self._buf)
            self._view_dir(focus_item)
        else:
            # TODO maybe we need to call win_set_buf for view_nothing() and view_file() too
            try:
                self._view_file()
            except FileNotFoundError as e:
                self.render_message(str(e), hl='Error')

    def _view_nothing(self):
        self._buf[:] = []

    def _view_dir(self, focus_item):
        try:
            items = list_files(self.path)
        except PermissionError as e:
            self.render_message(str(e), hl='Error')
            return
        if not items:
            self.render_message('(directory empty)', hl='Comment')
            return
        self.children = items
        self._render_dir(focus_item)

    def _view_file(self):
        path = self.path
        st = path.stat()
        mode = stat.filemode(st.st_mode)
        size = st.st_size

        if size > PREVIEW_SIZE_LIMIT:
            self._render_head(path)
        else:
            # TODO Get rid of vimscript
            self._plugin._vim.call('ViewFile', str(path))
        # self._vim.vars['statusline3'] = mode

    def _render_dir(self, focus_item):
        """Render current directory."""
        focus_item = focus_item or self._plugin.focus_cache.get(self.path)
        lines = []
        highlights = []
        focus_linenum = None
        for linenum, item in enumerate(self.children):
            line = self._format_line(item)
            # TODO Change focus_linenum to focus_item
            if item == focus_item:
                focus_linenum = linenum
                if not self._use_cursorline:
                    # Pad with spaces so we can background-highlight the line.
                    # (Using "cursorline" for that is buggy)
                    line = line.ljust(self._win.width)
            hl_group = self._plugin._color_manager.file_hl_group(item)
            if hl_group is not None:
                highlights.append((linenum, hl_group))
            lines.append(line)

        self._buf[:] = lines
        # Attempt to restore focus
        if focus_linenum is not None:
            if self._use_cursorline:
                self._win.cursor = [focus_linenum + 1, 0]
            else:
                self._buf.add_highlight('SelectedEntry', focus_linenum, 0, -1, src_id=-1)
        self._apply_highlights(highlights)

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

    def render_message(self, msg, hl='Normal'):
        self._buf[:] = [msg]
        self._buf.add_highlight(hl, 0, 0, -1, src_id=-1)

    def _render_head(self, path):
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
                # bytes += f.read(PREVIEW_SIZE_LIMIT - HEXDUMP_LIMIT)

        if need_hexdump:
            lines = hexdump(data[:HEXDUMP_LIMIT])
        else:
            lines = [x.decode('utf-8') for x in data.splitlines()]

        filename = str(path) + '.preview'
        num = self._vim.call('bufnr', filename)
        if num == -1:
            num = self._vim.call('bufnr', filename, 1)
        win = self._vim.windows[2]
        buf = self._vim.buffers[num]
        win_set_buf(win, buf)

        self._vim.call('ViewHexdump')
        buf[:] = lines


@pynvim.plugin
class Plugin:

    def __init__(self, vim):
        self._vim = vim
        self._color_manager = ColorManager(vim)
        # Map directories to last focused file in that directory
        self._start_path = Path(os.environ.get('NVFM_START_PATH', '.'))
        self._panels = None
        self.focus_cache = {}

    @pynvim.function('NvfmStartup', sync=True)
    def func_nvfm_startup(self, args):
        logger.debug('nvfm startup')
        logger.debug([b.name for b in self._vim.buffers])
        self._color_manager.define_highlights()

        self._panels = [Panel(self, w, w.buffer) for w in self._vim.windows]
        self._panels[2]._use_cursorline = False

        self._enter_dir(self._start_path)

    @pynvim.function('NvfmEnter', sync=True)
    def func_nvfm_enter(self, args):
        what = args[0]
        logger.debug(('enter', what))
        if isinstance(what, int):
            idx = args[0] - 1
            try:
                target = self._panels[1].children[idx]
            except IndexError:
                logger.warn('nothing to enter')
                return
        else:
            # '..' in paths isn't collapsed automatically
            if what == '..':
                target = self._panels[1].path.parent
            else:
                target = self._panels[1].path / what
        if not target.is_dir():
            # TODO Enter file?
            return
        self._enter_dir(target)

    def _enter_dir(self, path):
        """The user enters `target`."""
        left, main, right = self._panels
        main.save_focus()
        logger.debug(('enter', path))

        main.view(path)
        if main.path != Path('/'):
            left.view(path.parent, focus_item=path)
        else:
            left.view(None)
        if main.is_empty_dir():
            right.view(None)

    # If sync=True,the syntax highlighting is not applied
    @pynvim.autocmd('CursorMoved', pattern='nvfm_main', sync=False)
    def focus_changed(self):
        left, main, right = self._panels

        cursor = main._win.cursor
        cur_line = cursor[0]
        if cursor[1] > 0:
            main._win.cursor = [cur_line, 0]
        if cur_line == main.focus_linenum:
            # CursorMoved was triggered, but the cursor didn't move
            logger.debug('focus didn\'t change')
            return
        main.focus_linenum = cur_line
        right.view(main.focus_item)
        self._update_tabline()
        self._update_status_main()

    def _update_tabline(self):
        """Update display of vim tabline."""
        path = self._panels[1].path
        selected = self._panels[1].focus_item
        pathinfo = f'{USER}@{HOST}:%#TabLinePath#{path.parent}'
        if path.parent.name:
            pathinfo += '/'
        if path.name:
            pathinfo += f'%#TabLineCurrent#{path.name}%#TabLinePath#/'
        if selected:
            selected_str = selected.name + ('/' if selected.is_dir() else '')
            selected_hl = f'color{self._color_manager.file_hl_group(selected)}'
            pathinfo += f'%#{selected_hl}#{selected_str}'
        # Make sure the hl is reset at the end
        pathinfo += '%#TabLineFill#'
        self._vim.options['tabline'] = pathinfo

    def _set_status(self, status):
        self._vim.vars['statusline3'] = status
        # TODO Recommended by vim docs to force update, but there should be a
        # more performant way
        self._vim.options['ro'] = self._vim.options['ro']

    def _update_status_main(self):
        p = self._panels[1]
        self._vim.vars['statusline2'] = '%d/%d' % (p.focus_linenum, len(p.children))
