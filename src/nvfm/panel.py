# -*- coding: future_fstrings -*-
from pathlib import Path

from .event import EventEmitter, Global
from .view import make_view, DirectoryView


class Panel(EventEmitter):
    """A panel corresponds to a window that displays a directory or file
    preview."""

    def __init__(self, plugin, win):
        self._plugin = plugin
        self.win = win
        self._view = None
        plugin.events.manage(self)

    def __repr__(self):
        return '%s(win=%s)' % (self.__class__.__name__, self.win)

    @property
    def view(self):
        return self._view

    @view.setter
    def view(self, view):
        if self._view is view:
            return
        self._view = view
        if view.buf is None:
            view.create_buf()
            self._load_buf(view.buf)
            view.buf_created()
        else:
            self._load_buf(view.buf)
        view.load_done(self)
        self.emit('view_loaded', self.view)
        self.update_cursor()

    def _load_buf(self, buf):
        self.win.request('nvim_win_set_buf', buf)

    def update_cursor(self):
        """Update window's cursor position as specified by the view."""
        cursor = self.view.cursor
        if cursor is not None:
            # Note: The updated cursorline position might not be immediately
            # visible if another event didn't trigger the draw (like a tabline
            # update)
            self.win.cursor = cursor

    def view_by_path(self, item):
        """Return a view that displays `path`.

        If a matching view doesn't exist, it's created.
        """
        view = self._plugin.views.get(item)
        if view is None:
            view = make_view(self._plugin, item)
            self._plugin.views[item] = view
        return view


class MainPanel(Panel):

    @Global.on('cursor_moved')
    def _cursor_moved(self, win):
        if win is not self.win:
            return
        linenum, col = win.cursor
        # Ensure cursor is always in the left-most column
        if col > 0:
            self.win.cursor = [linenum, 0]
        if linenum == self.view.focus:
            return
        self.view.focus = linenum
        self.emit('focus_changed', self.view)


class LeftPanel(Panel):

    @MainPanel.on('view_loaded')
    def _main_view_loaded(self, view):
        """A view was loaded in the main panel. Preview its parent."""
        path = view.path
        if path == Path('/'):
            self.view = self.view_by_path(None)
        else:
            self.view = self.view_by_path(path.parent)
            self.view.focused_item = path
            self.update_cursor()


class RightPanel(Panel):

    @MainPanel.on('focus_changed')
    def _main__focus_changed(self, view):
        self.view = self.view_by_path(view.focused_item)

    @MainPanel.on('view_loaded')
    def _main_view_loaded(self, view):
        """A view was loaded in the main panel. Preview its focused item."""
        if isinstance(view, DirectoryView):
            if view.empty:
                self.view = self.view_by_path(None)
            else:
                self.view = self.view_by_path(view.focused_item)
