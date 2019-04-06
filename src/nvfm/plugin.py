# -*- coding: future_fstrings -*-
from collections import defaultdict
import getpass
import os
from pathlib import Path
import platform
from stat import S_ISDIR

import pynvim

from .color import ColorManager
from .panel import LeftPanel, MainPanel, RightPanel
from .util import logger, stat_path

HOST = platform.node()
USER = getpass.getuser()


class EventManager:

    def __init__(self):
        self._handlers = defaultdict(list)

    def subscribe(self, name, handler):
        logger.debug(('sub', handler, name))
        self._handlers[name].append(handler)

    def publish(self, name, *args, **kwargs):
        logger.debug(('pub', len(self._handlers[name]), name, args, kwargs))
        for handler in self._handlers[name]:
            logger.debug(('fire', handler))
            handler(*args, **kwargs)


@pynvim.plugin
class Plugin:

    def __init__(self, vim):
        logger.debug('plugin init')
        self._vim = vim
        self._color_manager = ColorManager(vim)
        # TODO Doesn't work
        self._start_path = Path(os.environ.get('NVFM_START_PATH', os.getcwd()))
        self._panels = None
        self.views = {}
        self._events = EventManager()

    @pynvim.function('NvfmStartup', sync=True)
    def func_nvfm_startup(self, args):
        logger.debug('nvfm startup')
        logger.debug([b.name for b in self._vim.buffers])
        # TODO Do this in color manager init
        self._color_manager.define_highlights()
        wins = self._vim.windows
        self._panels = [
            LeftPanel(self, wins[0]),
            MainPanel(self, wins[1]),
            RightPanel(self, wins[2]),
        ]
        self.go_to(self._start_path)

    @pynvim.function('NvfmEnter', sync=True)
    def func_nvfm_enter(self, args):
        """Enter the directory indicated by args[0]."""
        if len(args) == 0:
            target = self._panels[1].view.focus_item
            if target is None:
                return
        else:
            what = args[0]
            # '..' in paths isn't collapsed automatically
            if what == '..':
                target = self._panels[1].view._path.parent
            else:
                target = self._panels[1].view._path / what
        stat_res, stat_error = stat_path(target, lstat=False)
        if (stat_error is not None) or not S_ISDIR(stat_res.st_mode):
            # TODO Handle regular file
            return
        self.go_to(target)

    def go_to(self, path):
        """The user enters `target`."""
        logger.debug(('enter', path))
        left, main, right = self._panels
        main.show_item(path)
        self.focus_changed()
        logger.error('no directory entered!')

    # If sync=True,the syntax highlighting is not applied
    # TODO Maybe use eval=... argument
    @pynvim.autocmd('CursorMoved', sync=True)
    def focus_changed(self):
        # TODO Error when moving around .dotfiles/LS_COLORS
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
        main.view.focus(cur_line)
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
            pathinfo += f'%#TabLineCurrent#{path.name}/%#TabLinePath#'
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
        self._vim.vars['statusline2'] = \
            '%d/%d' % (p.focus_linenum, len(p.children))
