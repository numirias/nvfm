# -*- coding: future_fstrings -*-

from pathlib import Path
from stat import S_ISBLK, S_ISCHR, S_ISDIR, S_ISFIFO, S_ISREG, S_ISSOCK

from .util import logger, stat_path
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
        # TODO Do we need to init with a buffer?
        self._view = None

    def __repr__(self):
        return 'Panel(win=%s)' % self.win

    @property
    def view(self):
        return self._view

    @view.setter
    def view(self, view):
        logger.debug(('load', view, 'into', self))
        if self._view is view:
            # TODO Does this happen?
            return
        self._view = view
        self.win.request('nvim_win_set_buf', view.buf)
        view.loaded_into(self)
        self._plugin.events.publish('view_loaded', self, self.view)

    def show_item(self, item, focus_item=None):
        """View `item` in the panel.

        `item` can be a file or a directory. `focused_item` can be set to the
        item that should be highlighted.

        """
        logger.debug(('view', item, 'in', self))
        view = self._plugin.views.get(item)
        if view is not None:
            logger.debug(('loading existing view'))
            self.view = view
            return
        view = self._make_view(item, focus_item)
        self._plugin.views[item] = view
        self.view = view

    def _make_view(self, item, focus_item):
        """Return a View object for `item`."""
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
            return DirectoryView(*args, focus=focus_item)
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
        if path != Path('/'):
            # TODO Dont carry focus_item as an argument
            self.show_item(path.parent, focus_item=path)
        else:
            self.show_item(None)


class MainPanel(Panel):
    pass


class RightPanel(Panel):

    def __init__(self, plugin, win):
        super().__init__(plugin, win)
        plugin.events.subscribe('focus_dir_item', self.event_focus_dir_item)
        plugin.events.subscribe('view_loaded', self.event_view_loaded)

    def event_focus_dir_item(self, view, item):
        # TODO
        assert view
        # TODO Assert that the event was fired by a view in the main panel
        self.show_item(item)

    def event_view_loaded(self, panel, view):
        if isinstance(panel, MainPanel) and isinstance(view, DirectoryView) \
                and view.empty:
            self.show_item(None)
