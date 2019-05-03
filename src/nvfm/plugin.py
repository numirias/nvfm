# -*- coding: future_fstrings -*-
import getpass
import os
from pathlib import Path
import platform
from stat import S_ISDIR

import pynvim

from .color import ColorManager
from .event import Event, EventManager, Global
from .history import History
from .option import Options
from .panel import LeftPanel, MainPanel, RightPanel
from .util import logger, stat_path
from .view import Views

HOST = platform.node()
USER = getpass.getuser()


class State:

    def __init__(self, vim):
        wins = vim.windows
        self.events = EventManager()
        self.left_panel = LeftPanel(self, wins[0])
        self.main_panel = MainPanel(self, wins[1])
        self.right_panel = RightPanel(self, wins[2])
        self.panels = [self.left_panel, self.main_panel, self.right_panel]
        self.wins = {p.win.handle: p.win for p in self.panels}
        self.views = Views(self, vim)
        self.options = Options()
        self.history = History()
        self.colors = ColorManager(vim)


@pynvim.plugin
class Plugin:

    def __init__(self, vim):
        logger.debug('nvfm plugin init')
        self._vim = vim
        self._state = None

    @pynvim.function('NvfmStartup', sync=True)
    def func_nvfm_startup(self, args): # pylint:disable=unused-argument
        self._state = State(self._vim)
        self._state.events.manage(self)
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
            target = self._state.main_panel.view.focused_item
            if target is None:
                return
        elif what == '..':
            # '..' in paths isn't collapsed automatically
            target = self._state.main_panel.view.path.parent
        else:
            target = self._state.main_panel.view.path / what
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
        self._state.main_panel.view = self._state.views[path]

    @pynvim.function('NvfmHistory', sync=True)
    def func_nvfm_history(self, args):
        step = args[0]
        try:
            path = self._state.history.go(step)
        except IndexError:
            return
        self.go_to(path)

    @pynvim.function('NvfmSet', sync=True)
    def func_nvfm_set(self, args):
        key, val = args
        self._state.options[key] = val

    @pynvim.function('NvfmRefresh', sync=True)
    def func_nvfm_refresh(self, args): # pylint:disable=unused-argument
        """Refresh all views.

        This marks all views as dirty and refreshes the visible ones.
        """
        for view in self._state.views.values():
            view.dirty = True
        for panel in self._state.panels:
            panel.refresh()

    @pynvim.function('NvfmFilter', sync=True)
    def func_nvfm_filter(self, args):
        query = args[0]
        if query:
            self._state.main_panel.view.filter(query)
        else:
            self._state.main_panel.view.clear_filter()
        self._state.events.publish(
            Event('cursor_moved', Global), self._state.main_panel.win)
        # Required because the screen isn't redrawn during user input
        self._vim.command('redraw')

    # TODO eval cursor position to avoid RPC roundtrip?
    # If sync=True,the syntax highlighting is not applied
    @pynvim.autocmd('CursorMoved', sync=True, eval='win_getid()')
    def cursor_moved(self, win_id):
        # TODO Error when moving around .dotfiles/LS_COLORS
        self._state.events.publish(
            Event('cursor_moved', Global), self._state.wins[win_id])
        # TODO Do tabline/statusline update elsewhere, e.g. on focus_changed
        self._update_tabline()
        self._update_status_main()

    @MainPanel.on('view_loaded')
    def add_history(self, view):
        self._state.history.add(view.path)

    def launch(self, target):
        # TODO Proper application launcher implementation
        with open(os.environ.get('NVFM_CMD_FILE'), 'w') as f:
            f.write('$EDITOR ' + str(target))
        self._vim.command('suspend!')

    def _update_tabline(self):
        """Update display of vim tabline."""
        main_view = self._state.main_panel.view
        path = main_view.path
        selected = main_view.focused_item
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
            selected_hl = self._state.colors.file_hl_group(selected)
            pathinfo += f'%#{selected_hl}#{selected_str}'
        # Make sure the hl is reset at the end
        pathinfo += '%#TabLineFill#'
        self._vim.options['tabline'] = pathinfo

    def _update_status_main(self):
        view = self._state.main_panel.view
        self._vim.vars['statusline2'] = \
            f'{view.focus}/{len(view.items)} ' \
            f'sort: {self._state.options["sort"].__name__}'
