import getpass
import os
# TODO Wrap Path for static stat etc
from pathlib import Path
import platform

import pynvim

from .util import logger, hexdump, convert_size, natural_sort_key, list_files
from .color import ColorManager
from .panel import Panel, DirectoryView, FileView

HOST = platform.node()
USER = getpass.getuser()


@pynvim.plugin
class Plugin:

    def __init__(self, vim):
        self._vim = vim
        self._color_manager = ColorManager(vim)
        # TODO Doesn't work
        self._start_path = Path(os.environ.get('NVFM_START_PATH', '.'))
        self._panels = None
        self.views = {}

    @pynvim.function('NvfmStartup', sync=True)
    def func_nvfm_startup(self, args):
        logger.debug('nvfm startup')
        logger.debug([b.name for b in self._vim.buffers])
        self._color_manager.define_highlights()

        self._panels = [Panel(self, w, w.buffer) for w in self._vim.windows]

        self._enter_dir(self._start_path)

    @pynvim.function('NvfmEnter', sync=True)
    def func_nvfm_enter(self, args):
        """Enter the directory indicated by args[0]."""
        what = args[0]
        logger.debug(('enter', what))
        if isinstance(what, int):
            idx = args[0] - 1
            try:
                # TODO We can work with the saved focus_linenum instead
                target = self._panels[1].view.children[idx]
            except IndexError:
                logger.warn('nothing to enter')
                return
        else:
            # '..' in paths isn't collapsed automatically
            if what == '..':
                target = self._panels[1].view._path.parent
            else:
                target = self._panels[1].view._path / what
        if not target.is_dir():
            # TODO Enter file?
            return
        self._enter_dir(target)

    def _enter_dir(self, path):
        """The user enters `target`."""
        logger.debug(('enter', path))
        left, main, right = self._panels
        main.show_item(path)
        if path != Path('/'):
            left.show_item(path.parent, focus_item=path)
        else:
            left.show_item(None)
        if main.view.is_empty():
            right.show_item(None)

        self.focus_changed()
        logger.error('no directory entered!')

    # If sync=True,the syntax highlighting is not applied
    # TODO Maybe use eval=... argument
    @pynvim.autocmd('CursorMoved', sync=True)
    def focus_changed(self):
        # TODO Restrict event to affected (main) window
        left, main, right = self._panels
        logger.debug(('focus changed', main.view._path))

        cursor = main._win.cursor
        cur_line = cursor[0]
        # Ensure cursor is always in left column
        if cursor[1] > 0:
            main._win.cursor = [cur_line, 0]
        if cur_line == main.view.focus_linenum:
            # CursorMoved was triggered, but the cursor didn't move
            logger.debug('focus didn\'t change')
            # TODO return
        # main.focus_linenum = cur_line
        main.view.focus(cur_line)
        right.show_item(main.view.focus_item)
        self._update_tabline()
        self._update_status_main()

    def _update_tabline(self):
        """Update display of vim tabline."""
        path = self._panels[1].view._path
        selected = self._panels[1].view.focus_item
        pathinfo = f'{USER}@{HOST}:%#TabLinePath#{path.parent}'
        if path.parent.name:
            pathinfo += '/'
        if path.name:
            pathinfo += f'%#TabLineCurrent#{path.name}%#TabLinePath#/'
        if selected:
            # TODO This fails for symlinks without permission
            selected_str = selected.name
            try:
                if selected.is_dir():
                    selected_str += '/'
            except OSError:
                pass
            selected_hl = self._color_manager.file_hl_group(selected)
            pathinfo += f'%#{selected_hl}#{selected_str}'
        # Make sure the hl is reset at the end
        pathinfo += '%#TabLineFill#'
        self._vim.options['tabline'] = pathinfo

    def _update_status_main(self):
        p = self._panels[1].view
        self._vim.vars['statusline2'] = '%d/%d' % (p.focus_linenum, len(p.children))
