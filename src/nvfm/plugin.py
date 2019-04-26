# -*- coding: future_fstrings -*-
import getpass
import os
from pathlib import Path
import platform
from stat import S_ISDIR

import pynvim

from .color import ColorManager
from .event import Event, EventManager, Global
from .option import Options
from .panel import LeftPanel, MainPanel, RightPanel
from .util import logger, stat_path

HOST = platform.node()
USER = getpass.getuser()


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


class Views:

    def __init__(self):
        self._views = {}

    # TODO Are some dunder methods redundant?
    def __getitem__(self, key):
        return self._views[key]

    def __setitem__(self, key, val):
        self._views[key] = val

    def __delitem__(self, key):
        self._views[key].remove()
        del self._views[key]

    def __getattr__(self, key):
        return getattr(self._views, key)


@pynvim.plugin
class Plugin:

    def __init__(self, vim):
        logger.debug('plugin init')
        self.vim = vim
        self.colors = ColorManager(vim)
        self._panels = None
        self._main_panel = None
        self._winid_to_win = None
        self.views = Views()
        self.events = EventManager()
        self.options = Options()
        self.history = History()
        self.events.manage(self)

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
        self._winid_to_win = {p.win.handle: p.win for p in self._panels}
        self._main_panel = self._panels[1]
        self.go_to(Path(os.environ.get('NVFM_START_PATH', os.getcwd())))

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
        self._main_panel.view = self._main_panel.view_by_path(path)

    @pynvim.function('NvfmHistory', sync=True)
    def func_nvfm_history(self, args):
        step = args[0]
        path = self.history.go(step)
        if path is not None:
            self.go_to(path)

    @pynvim.function('NvfmSet', sync=True)
    def func_nvfm_set(self, args):
        key, val = args
        self.options[key] = val

    @pynvim.function('NvfmRefresh', sync=True)
    def func_nvfm_refresh(self, args): # pylint:disable=unused-argument
        """Refresh all views.

        This marks all views as dirty and refreshes the visible ones.
        """
        for view in self.views.values():
            view.dirty = True
        for panel in self._panels:
            panel.refresh()

    # If sync=True,the syntax highlighting is not applied
    @pynvim.autocmd('CursorMoved', sync=True, eval='win_getid()')
    def cursor_moved(self, win_id):
        # TODO Error when moving around .dotfiles/LS_COLORS
        self.events.publish(
            Event('cursor_moved', Global), self._winid_to_win[win_id])
        self._update_tabline()
        self._update_status_main()

    @MainPanel.on('view_loaded')
    def add_history(self, view):
        self.history.add(view.path)

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
            f'{view.focus}/{len(view.children)} ' \
            f'sort: {self.options["sort"].__name__}'
