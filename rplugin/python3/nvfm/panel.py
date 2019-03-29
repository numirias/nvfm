from .util import logger
from .view import FileView, DirectoryView, MessageView


def win_set_buf(win, buf):
    return win.request('nvim_win_set_buf', buf)


class Panel:
    """A panel corresponds to a window that displays a directory or file
    preview."""

    def __init__(self, plugin, win, buf):
        self._plugin = plugin
        self._win = win
        self._buf = buf
        self._view = None

    def __repr__(self):
        return 'Panel(win=%s)' % self._win

    @property
    def buf(self):
        return self._buf

    @buf.setter
    def buf(self, buf):
        self._buf = buf
        win_set_buf(self._win, buf)

    # def unload_view(self):
    #     if self._view is not None:
    #         self._view.unload()

    def view(self, item, focus_item=None):
        """View `item` in the panel.

        `item` can be a file or a directory. `focused_item` can be set to the
        item that should be highlighted.

        """
        logger.debug(('view', item, self))
        view = self._plugin.views.get(item)
        # TODO Check if we are already in the correct view
        if view is not None:
            # logger.debug(('loading existing view'))
            view.load_into(self)
            return

        if item is None:
            # TODO Use the same view always
            view = MessageView(self._plugin, item, '(nothing to show)', 'Comment')
        elif item.is_dir():
            view = DirectoryView(self._plugin, item, focus=focus_item)
        else:
            view = FileView(self._plugin, item)

        logger.debug(('create view', view, item))
        if view is not None:
            self._plugin.views[item] = view
        view.load_into(self)
