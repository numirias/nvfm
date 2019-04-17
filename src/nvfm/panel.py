# -*- coding: future_fstrings -*-
from pathlib import Path
from stat import S_ISBLK, S_ISCHR, S_ISDIR, S_ISFIFO, S_ISREG, S_ISSOCK

from .event import EventEmitter
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


class Panel(EventEmitter):
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

        if view.buf is None:
            self._create_and_load_buf(view)
            view.create_buf_post()
        else:
            self.win.request('nvim_win_set_buf', view.buf)
        self.update_cursor()
        view.load_done(self)
        self._plugin.events.publish(self.event('view_loaded'), self._view)

    def _create_and_load_buf(self, view):
        buf = self._plugin.vim.request(
            'nvim_create_buf',
            True, # listed
            False, # scratch
        )
        self.win.request('nvim_win_set_buf', buf)
        view.setup_buf(buf)

    def update_cursor(self):
        """Update window's cursor position as specified by the view."""
        cursor = self._view.cursor
        if cursor is not None:
            # Note: The updated cursorline position might not be immediately
            # visible if another event didn't trigger the draw (like a tabline
            # update)
            self.win.cursor = cursor

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
        plugin.events.subscribe(
            MainPanel.event('view_loaded'), self._main_view_loaded)

    def _main_view_loaded(self, view):
        path = view.path
        if path == Path('/'):
            self.load_view_by_path(None)
        else:
            self.load_view_by_path(path.parent)
            # TODO setter for focus_item?
            self._view.focused_item = path
            self.update_cursor()


class MainPanel(Panel):

    def __init__(self, plugin, win):
        super().__init__(plugin, win)
        self._plugin.events.subscribe('main_cursor_moved',
                                      self._main_cursor_moved)

    def _main_cursor_moved(self, linenum, col):
        # Ensure cursor is always in the left-most column.
        if col > 0:
            self.win.cursor = [linenum, 0]
        if linenum == self._view.focus:
            return
        self._view.focus = linenum
        self._plugin.events.publish('main_focus_changed', self._view)


class RightPanel(Panel):

    def __init__(self, plugin, win):
        super().__init__(plugin, win)
        plugin.events.subscribe(
                'main_focus_changed',
                lambda view: self.load_view_by_path(view.focused_item))
        plugin.events.subscribe(
            MainPanel.event('view_loaded'), self._main_view_loaded)

    def _main_view_loaded(self, view):
        """A view was loaded in the main panel. Preview its focused item."""
        if isinstance(view, DirectoryView):
            if view.empty:
                self.load_view_by_path(None)
            else:
                self.load_view_by_path(view.focused_item)
