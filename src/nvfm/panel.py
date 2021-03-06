# -*- coding: future_fstrings -*-
from pathlib import Path

from .event import EventEmitter, Global
from .util import logger
from .view import DirectoryView, EmptyView


class Panel(EventEmitter):
    """A panel corresponds to a window that displays a directory or file
    preview."""

    def __init__(self, session, win):
        self._s = session
        self.win = win
        self._view = EmptyView()
        session.events.manage(self)

    def __repr__(self):
        return '%s(win=%s)' % (self.__class__.__name__, self.win)

    @property
    def view(self):
        return self._view

    @view.setter
    def view(self, view):
        """Load `view` into this panel."""
        if self._view is view:
            return
        self._view.unload()
        self._view = view
        view.protocol_init()
        self.win.request('nvim_win_set_buf', view.buf)
        view.configure_buf()
        view.configure_win(self.win)
        view.protocol_draw()
        self.emit('view_loaded', self.view)
        self.update_vim_cursor()

    def reload_view(self):
        self.view.protocol_init()
        self.view.protocol_draw()
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
        self.view.cursor = win.cursor
        self.emit('focus_changed', self.view)

    @DirectoryView.on('cursor_adjusted')
    def _cursor_adjusted(self, view):
        if view is self._view:
            self.update_vim_cursor()


class LeftPanel(Panel):

    @MainPanel.on('view_loaded')
    def _main_view_loaded(self, main_view):
        """A view was loaded in the main panel. Preview its parent."""
        main_path = main_view.path
        if main_path == Path('/'):
            self.view = self._s.views[None]
        else:
            view = self._s.views[main_path.parent]
            view.focused_item = main_path
            self.view = view


class RightPanel(Panel):

    @MainPanel.on('focus_changed')
    def _main_focus_changed(self, view):
        self.view = self._s.views[view.focused_item]

    @MainPanel.on('view_loaded')
    def _main_view_loaded(self, view):
        """A view was loaded in the main panel. Preview its focused item."""
        if isinstance(view, DirectoryView):
            if view.empty:
                self.view = self._s.views[None]
            else:
                self.view = self._s.views[view.focused_item]
