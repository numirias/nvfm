from .util import logger


class View:

    VIEW_PREFIX = 'nvfm_view:'
    cursor = None

    def __init__(self, session, vim, path):
        logger.debug(('new view', path))
        self._s = session
        self._vim = vim
        self.path = path
        self.buf = self._create_buf()
        self._buf_configured = False
        self.dirty = True

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.path)

    def _create_buf(self):
        return self._vim.request(
            'nvim_create_buf',
            True, # listed
            False, # scratch
        )

    def configure_buf(self):
        if self._buf_configured:
            return
        buf = self.buf
        # TODO Do bulk request
        buf.request('nvim_buf_set_option', 'buftype', 'nowrite')
        buf.request('nvim_buf_set_option', 'bufhidden', 'hide')
        if self.path is not None:
            buf.name = self.VIEW_PREFIX + str(self.path)
        self._buf_configured = True

    def configure_win(self, win):
        pass

    def load(self):
        """Load the view. Redraw if it's dirty."""
        if self.dirty:
            self.draw()
            self.dirty = False

    def unload(self):
        pass

    def draw(self):
        pass

    def draw_message(self, msg, hl_group=None):
        if hl_group is None:
            hl_group = 'NvfmMessage'
        buf = self.buf
        buf[:] = [msg]
        buf.add_highlight(hl_group, 0, 0, -1, src_id=-1)

    def remove(self):
        """Called when the view is removed from the view list."""
        self._vim.command('bwipeout! %d' % self.buf.number)
