# -*- coding: future_fstrings -*-

from pathlib import Path
from stat import S_ISBLK, S_ISCHR, S_ISDIR, S_ISFIFO, S_ISREG, S_ISSOCK

from .util import stat_path
from .view import DirectoryView, FileView, MessageView


def mode_to_type_str(mode):
    if S_ISCHR(mode):
        msg = 'character special device file'
    elif S_ISBLK(mode):
        msg = 'block special device file'
    elif S_ISFIFO(mode):
        msg = 'FIFO (named pipe)'
    elif S_ISSOCK(mode):
        msg = 'socket'
    else:
        msg = 'unknown file type'
    return msg


class Panel:
    """A panel corresponds to a window that displays a directory or file
    preview."""

    def __init__(self, plugin, win):
        self._plugin = plugin
        self.win = win
        self._view = None

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
        view.load_into(self)
        self._plugin.events.publish('view_loaded', self, self.view)

    def load_view_by_path(self, item):
        """Load a view for `item` in this panel.

        `item` can be a file or directory.
        """
        view = self._plugin.views.get(item)
        if view is None:
            view = self._make_view(item)
            self._plugin.views[item] = view
        self.view = view

    def _make_view(self, item):
        """Create and return a View() that displays `item`."""
        args = (self._plugin, item)
        if item is None:
            # TODO Use the same view always
            return MessageView(*args, message='(nothing to show)')
        stat_res, stat_error = stat_path(item, lstat=False)
        if stat_error is not None:
            return MessageView(
                *args, message=str(stat_error), hl_group='NvfmError')
        mode = stat_res.st_mode
        if S_ISDIR(mode):
            return DirectoryView(*args)
        # TODO Check the stat() of the link
        if S_ISREG(mode):
            return FileView(*args)
        return MessageView(*args, message='(%s)' % mode_to_type_str(mode))


class LeftPanel(Panel):

    def __init__(self, plugin, win):
        super().__init__(plugin, win)
        plugin.events.subscribe('view_loaded', self.event_view_loaded)

    def event_view_loaded(self, panel, view):
        if not isinstance(panel, MainPanel):
            return
        path = view.path
        if path == Path('/'):
            self.load_view_by_path(None)
        else:
            self.load_view_by_path(path.parent)
            self._view.focus = self._view.linenum_of_item(path)


class MainPanel(Panel):

    def __init__(self, plugin, win):
        super().__init__(plugin, win)
        self._plugin.events.subscribe('main_cursor_moved',
                                      self._keep_cursor_left)

    def _keep_cursor_left(self, linenum, col):
        """Ensure cursor is always in the left-most column."""
        if col > 0:
            self.win.cursor = [linenum, 0]

    def load_view_by_path(self, item):
        if isinstance(self._view, DirectoryView):
            self._plugin.events.unsubscribe('main_cursor_moved',
                                            self._view.cursor_moved)
        super().load_view_by_path(item)
        if isinstance(self._view, DirectoryView):
            self._plugin.events.subscribe('main_cursor_moved',
                                          self._view.cursor_moved)


class RightPanel(Panel):

    def __init__(self, plugin, win):
        super().__init__(plugin, win)
        plugin.events.subscribe('main_focus_changed', self.main_focus_changed)
        plugin.events.subscribe('view_loaded', self.event_view_loaded)

    def main_focus_changed(self, focused_item):
        self.load_view_by_path(focused_item)

    def event_view_loaded(self, panel, view):
        if isinstance(panel, MainPanel) and isinstance(view, DirectoryView) \
                and view.empty:
            self.load_view_by_path(None)
