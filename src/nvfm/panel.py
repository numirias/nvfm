# -*- coding: future_fstrings -*-
from pathlib import Path

from .event import EventEmitter, Global
from .util import logger
from .view import DirectoryView, CursorAdjusted


class Panel(EventEmitter):
    """A panel corresponds to a window that displays a directory or file
    preview."""

    def __init__(self, state, win):
        self._state = state
        self.win = win
        self._view = None
        state.events.manage(self)

    def __repr__(self):
        return '%s(win=%s)' % (self.__class__.__name__, self.win)

    @property
    def view(self):
        return self._view

    @view.setter
    def view(self, view):
        if self._view is view:
            return
        if self._view is not None:
            self._view.unload()
        self._view = view
        self.win.request('nvim_win_set_buf', view.buf)
        view.configure_buf()
        view.load()
        view.configure_win(self.win)
        self.emit('view_loaded', self.view)
        self.update_vim_cursor()

    def refresh(self):
        # TODO Refactor
        self.view.load()
        self.update_vim_cursor()

    def update_vim_cursor(self):
        """Update window's cursor position as specified by the view."""
        cursor = self.view.cursor
        if cursor is None:
            return
        # Note: The updated cursorline might not be immediately visible if
        # another event didn't trigger the draw (like a tabline update)
        logger.debug(('set cursor', self, cursor))
        self.win.cursor = cursor


class MainPanel(Panel):

    @Global.on('cursor_moved')
    def _cursor_moved(self, win):
        """The user has changed the focus."""
        if win is not self.win:
            # The cursor moved in another panel's window
            return
        try:
            self.view.cursor = win.cursor
        except CursorAdjusted:
            self.update_vim_cursor()
        self.emit('focus_changed', self.view)


class LeftPanel(Panel):

    @MainPanel.on('view_loaded')
    def _main_view_loaded(self, view):
        """A view was loaded in the main panel. Preview its parent."""
        path = view.path
        if path == Path('/'):
            self.view = self._state.views[None]
        else:
            self.view = self._state.views[path.parent]
            self.view.focused_item = path
            self.update_vim_cursor()


class RightPanel(Panel):

    @MainPanel.on('focus_changed')
    def _main_focus_changed(self, view):
        self.view = self._state.views[view.focused_item]

    @MainPanel.on('view_loaded')
    def _main_view_loaded(self, view):
        """A view was loaded in the main panel. Preview its focused item."""
        if isinstance(view, DirectoryView):
            if view.empty:
                self.view = self._state.views[None]
            else:
                self.view = self._state.views[view.focused_item]
