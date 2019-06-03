from .event import EventEmitter
from .util import logger


class View(EventEmitter):

    VIEW_PREFIX = 'nvfm:view:'
    cursor = None

    def __init__(self, session, vim, path):
        logger.debug(('new view', path))
        self._s = session
        self._vim = vim
        self.path = path
        self.buf = self._create_buf()
        self._buf_configured = False
        self.dirty = 2
        self._s.events.manage(self, register_handlers=False)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.path)

    def _create_buf(self):
        return self._vim.request(
            'nvim_create_buf',
            True, # listed
            False, # scratch
        )

    def protocol_init(self):
        if self.dirty >= 2:
            logger.debug('view:init:%s', self)
            self.init()
            self.dirty = 1

    def init(self):
        pass

    def configure_buf(self):
        # XXX Still required?
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

    def protocol_draw(self):
        if self.dirty >= 1:
            logger.debug('view:draw:%s buf=%s', self, self.buf)
            self.draw()
            self.dirty = 0

    def draw(self):
        pass

    def unload(self):
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
