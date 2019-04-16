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
from .config import sort_funcs

HOST = platform.node()
USER = getpass.getuser()


class EventManager:

    def __init__(self):
        self._handlers = defaultdict(list)

    def subscribe(self, name, handler):
        logger.debug(('sub', handler, name))
        self._handlers[name].append(handler)

    def unsubscribe(self, name, handler):
        logger.debug(('unsub', handler, name))
        self._handlers[name].remove(handler)

    def publish(self, name, *args, **kwargs):
        logger.debug(('pub', len(self._handlers[name]), name, args, kwargs))
        for handler in self._handlers[name]:
            logger.debug(('fire', handler))
            handler(*args, **kwargs)


class History:

    def __init__(self):
        self._history = []
        self._pointer = -1

    def __repr__(self):
        s = ', '.join(('*' + str(x) if i == self._pointer else str(x))
                      for i, x in enumerate(self._history))
        return f'History({s})'

    @property
    def all(self):
        return self._history[:]

    def add(self, item):
        if self._history and self._history[self._pointer] == item:
            return
        if self._pointer < len(self._history) - 1:
            self._history = self._history[:self._pointer + 1]
        self._history.append(item)
        self._pointer = len(self._history) - 1

    def go(self, step):
        new_p = self._pointer + step
        if new_p < 0 or new_p > len(self._history) - 1:
            return None
        self._pointer = new_p
        return self._history[new_p]


@pynvim.plugin
class Plugin:

    def __init__(self, vim):
        logger.debug('plugin init')
        self.vim = vim
        self.colors = ColorManager(vim)
        # TODO Needed?
        self._start_path = Path(os.environ.get('NVFM_START_PATH', os.getcwd()))
        self._panels = None
        self._main_panel = None
        self.views = {}
        self.events = EventManager()
        self.history = History()
        self.sort_func = sort_funcs[0]
        self.events.subscribe(
            'view_loaded', lambda panel, view:
            panel is self._main_panel and self.history.add(panel.view.path))

    @pynvim.function('NvfmStartup', sync=True)
    def func_nvfm_startup(self, args):
        logger.debug(('nvfm startup', args))
        logger.debug([b.name for b in self.vim.buffers])
        # TODO Do this in color manager init
        self.colors.define_highlights()
        wins = self.vim.windows
        self._panels = [
            LeftPanel(self, wins[0]),
            MainPanel(self, wins[1]),
            RightPanel(self, wins[2]),
        ]
        self._main_panel = self._panels[1]
        self.go_to(self._start_path)

    @pynvim.function('NvfmEnter', sync=True)
    def func_nvfm_enter(self, args):
        """Enter directory or view file.

        Enter the directory indicated by args[0]. If args[0] is None, use
        currently selected item. If args[1] is True, resolve symlinks.
        """
        # TODO Is there support for default args?
        what = args[0] if args else None
        resolve_symlinks = args[1] if len(args) >= 2 else False
        if what is None:
            target = self._main_panel.view.focused_item
            if target is None:
                return
        elif what == '..':
            # '..' in paths isn't collapsed automatically
            target = self._main_panel.view.path.parent
        else:
            target = self._main_panel.view.path / what
        stat_res, stat_error = stat_path(target, lstat=False)
        if (stat_error is not None) or not S_ISDIR(stat_res.st_mode):
            self.launch(target)
            return
        if resolve_symlinks:
            target = target.resolve()
        self.go_to(target)

    def go_to(self, path):
        """The user enters `target`."""
        logger.debug(('enter', path))
        self._main_panel.load_view_by_path(path)
        self.cursor_moved()
        logger.error('no directory entered!')

    @pynvim.function('NvfmHistory', sync=True)
    def func_nvfm_history(self, args):
        step = args[0]
        path = self.history.go(step)
        if path is not None:
            self.go_to(path)

    # If sync=True,the syntax highlighting is not applied
    # TODO Maybe use eval=... argument
    @pynvim.autocmd('CursorMoved', sync=True)
    def cursor_moved(self):
        # TODO Error when moving around .dotfiles/LS_COLORS
        # TODO Restrict event to affected (main) window
        self.events.publish('main_cursor_moved', *self._main_panel.win.cursor)
        self._update_tabline()
        self._update_status_main()

    def launch(self, target):
        # TODO Proper application launcher implementation
        with open(os.environ.get('NVFM_CMD_FILE'), 'w') as f:
            f.write('$EDITOR ' + str(target))
        self.vim.command('suspend!')

    def _update_tabline(self):
        """Update display of vim tabline."""
        path = self._main_panel.view.path
        selected = self._main_panel.view.focused_item
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
            selected_hl = self.colors.file_hl_group(selected)
            pathinfo += f'%#{selected_hl}#{selected_str}'
        # Make sure the hl is reset at the end
        pathinfo += '%#TabLineFill#'
        self.vim.options['tabline'] = pathinfo

    def _update_status_main(self):
        view = self._main_panel.view
        self.vim.vars['statusline2'] = \
            '%d/%d' % (view.focus, len(view.children))
