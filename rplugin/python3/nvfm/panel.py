from stat import (S_ISBLK, S_ISCHR, S_ISDIR, S_ISFIFO, S_ISLNK, S_ISREG,
                  S_ISSOCK)

from .util import logger, stat_path
from .view import DirectoryView, FileView, MessageView


def win_set_buf(win, buf):
    return win.request('nvim_win_set_buf', buf)


class Panel:
    """A panel corresponds to a window that displays a directory or file
    preview."""

    def __init__(self, plugin, win, buf):
        self._plugin = plugin
        self._win = win
        self._buf = buf
        self.view = None

    def __repr__(self):
        return 'Panel(win=%s)' % self._win

    @property
    def buf(self):
        return self._buf

    @buf.setter
    def buf(self, buf):
        self._buf = buf
        win_set_buf(self._win, buf)

    def show_item(self, item, focus_item=None):
        """View `item` in the panel.

        `item` can be a file or a directory. `focused_item` can be set to the
        item that should be highlighted.

        """
        logger.debug(('view', item, self))
        view = self._plugin.views.get(item)
        if view is not None:
            # logger.debug(('loading existing view'))
            self._load_view(view)
            return
        if item is None:
            # TODO Use the same view always
            view = MessageView(self._plugin, item,
                message='(nothing to show)', hl_group='Comment')
        else:
            stat_res, stat_error = stat_path(item, lstat=False)
            if stat_error is not None:
                view = MessageView(self._plugin, item,
                    message=str(stat_error), hl_group='Error')
            else:
                mode = stat_res.st_mode
                if S_ISDIR(mode):
                    view = DirectoryView(self._plugin, item, focus=focus_item)
                # TODO Check the stat() of the link
                elif S_ISREG(mode):
                    view = FileView(self._plugin, item)
                else:
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
                    view = MessageView(self._plugin, item,
                        message='(%s)' % msg, hl_group='Comment')

        logger.debug(('create view', view, item))
        if view is not None:
            self._plugin.views[item] = view
        self._load_view(view)

    def _load_view(self, view):
        logger.debug(('load', view, 'into', self))
        if self.view is view:
            # TODO Check that this happens
            return
        self.buf = view._buf
        self.view = view
        view.event_loaded(self)
