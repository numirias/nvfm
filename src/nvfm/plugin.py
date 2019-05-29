# -*- coding: future_fstrings -*-
import getpass
import os
from pathlib import Path
import platform
from stat import S_ISDIR

import pynvim

from .color import ColorManager
from .config import filter_funcs
from .event import Event, EventManager, Global
from .history import History
from .option import Options
from .panel import LeftPanel, MainPanel, RightPanel
from .util import logger, stat_path
from .view import DirectoryView, Views

HOST = platform.node()
USER = getpass.getuser()


class Session:

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
        try:
            self.cmd_path = Path(os.environ['NVFM_TMP']) / 'cmd'
        except KeyError:
            raise Exception('"NVFM_TMP" needs to be set in the environment.')

    @property
    def cwd(self):
        return self.main_panel.view.path


@pynvim.plugin
class Plugin:

    def __init__(self, vim):
        logger.debug('nvfm plugin init')
        self._vim = vim
        # The current session
        self._s = None

    @pynvim.function('NvfmStartup', sync=True)
    def func_nvfm_startup(self, args): # pylint:disable=unused-argument
        self._s = Session(self._vim)
        self._s.events.manage(self)

    @pynvim.function('NvfmEnter', sync=True)
    def func_nvfm_enter(self, args):
        """Enter directory or view file.

        Enter the directory indicated by args[0]. If args[0] is None, use
        currently selected item. If args[1] is True, resolve symlinks.
        """
        main_view = self._s.main_panel.view
        # TODO Is there support for default args?
        what = args[0] if args else None
        resolve_symlinks = args[1] if len(args) >= 2 else False
        if what is None:
            target = main_view.focused_item
            if target is None:
                return
        elif what == '..':
            # '..' in paths isn't collapsed automatically
            target = main_view.path.parent
        else:
            target = main_view.path / what
        stat_res, stat_error = stat_path(target, lstat=False)
        if (stat_error is not None) or not S_ISDIR(stat_res.st_mode):
            self.launch(target)
            return
        if resolve_symlinks:
            target = target.resolve()
        self.go_to(target)

    def go_to(self, path):
        """The user enters `target`."""
        if not path.absolute():
            path = self._s.cwd / Path(path)
        logger.debug('enter %r', path)
        self._s.main_panel.view = self._s.views[path]
        # TODO Escape
        self._vim.command('cd ' + str(path))

    @pynvim.function('NvfmHistory', sync=True)
    def func_nvfm_history(self, args):
        step = args[0]
        try:
            path = self._s.history.go(step)
        except IndexError:
            return
        self.go_to(path)

    @pynvim.function('NvfmSet', sync=True)
    def func_nvfm_set(self, args):
        key, val = args
        self._s.options[key] = val

    @pynvim.function('NvfmRefresh', sync=True)
    def func_nvfm_refresh(self, args): # pylint:disable=unused-argument
        """Refresh all views.

        This marks all views as dirty and reloads the visible ones.
        """
        self._s.views.mark_all_dirty()
        for panel in self._s.panels:
            panel.reload_view()

    @pynvim.function('NvfmFilter', sync=True)
    def func_nvfm_filter(self, args):
        query = args[0]
        if not args[0]:
            self._s.main_panel.view.clear_filter()
        else:
            method = args[1] if len(args) > 1 else 'standard'
            self._s.main_panel.view.filter(filter_funcs[method], query)
        self._s.events.publish(
            Event('cursor_moved', Global), self._s.main_panel.win)
        # Required because the screen isn't redrawn during user input
        self._vim.command('redraw')

    # TODO eval cursor position to avoid RPC roundtrip?
    # TODO Did I mean sync=False?
    # If sync=True, the syntax highlighting is not applied
    @pynvim.autocmd('CursorMoved', sync=True, eval='win_getid()')
    def cursor_moved(self, win_id):
        # pylint:disable=unidiomatic-typecheck
        if type(self._s.main_panel.view) is not DirectoryView:
            # TODO Refactor
            return
        # TODO Refactor
        if self._s.main_panel.win.buffer.name.startswith('term:'):
            return
        # TODO Error when moving around .dotfiles/LS_COLORS
        self._s.events.publish(
            Event('cursor_moved', Global), self._s.wins[win_id])
        # TODO Do tabline/statusline update elsewhere, e.g. on focus_changed
        self._update_tabline()
        self._update_status_main()

    @pynvim.autocmd('BufWinEnter', sync=True, eval='win_getid()')
    def buf_win_enter(self, win_id):
        # This autocmd works around the problem that opening a terminal in the
        # main panel (e.g. when FZF is launched), some window properties get
        # reset. So we restore them here.
        # TODO Add test
        if self._s is None:
            return
        if self._s.wins[win_id] != self._s.main_panel.win:
            return
        logger.debug('bufwinenter %s', win_id)
        main_panel = self._s.main_panel
        main_panel.view.configure_win(main_panel.win)

    @MainPanel.on('view_loaded')
    def add_history(self, view):
        self._s.history.add(view.path)

    def launch(self, target):
        # TODO Proper application launcher implementation
        with open(self._s.cmd_path, 'w') as f:
            f.write('$EDITOR ' + str(target))
        # Suspend vim, so the bash wrapper can take over and launch the editor
        self._vim.command('suspend!')

    def _update_tabline(self):
        """Update display of vim tabline."""
        main_view = self._s.main_panel.view
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
            selected_hl = self._s.colors.file_hl_group(selected)
            pathinfo += f'%#{selected_hl}#{selected_str}'
        # Make sure the hl is reset at the end
        pathinfo += '%#TabLineFill#'
        self._vim.options['tabline'] = pathinfo

    def _update_status_main(self):
        view = self._s.main_panel.view
        self._vim.vars['statusline1'] = \
            f'{view.focus}/{len(view.items)} ' \
            f'sort: {self._s.options["sort"].name}'
