import grp
import itertools
import math
import os
from pathlib import Path
import pwd
import stat
from stat import S_ISDIR, S_ISLNK

from .base_view import View
from .util import logger

USERS = {u.pw_uid: u.pw_name for u in pwd.getpwall()}
GROUPS = {g.gr_gid: g.gr_name for g in grp.getgrall()}


class DirectoryView(View):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TODO Make focus private?
        # Line number of focused item (starts at 1)
        self.focus = None
        # List of items in directory (of os.DirEntry, not pathlib.Path)
        self.items = None
        self._folds = None
        self._error = None

    def configure_win(self, win):
        if self.items:
            win.request('nvim_win_set_option', 'cursorline', True)

    def unload(self):
        self.clear_filter()

    def init(self):
        try:
            # Only save and restore focus if it has been explicitly set
            restore_focus = self.focus is not None
            if restore_focus:
                focused_item = self.focused_item
            self.items = self._list_files(
                self.path, self._s.options['sort'].value)
            if restore_focus:
                self.focused_item = focused_item
        except OSError as e:
            self.items = []
            self._error = e

    def draw(self):
        self._draw()

    def _draw(self):
        if self._error:
            self.draw_message(str(self._error), 'Error')
        elif not self.items:
            self.draw_message('(directory empty)')
        else:
            self._render_items()

    @property
    def cursor(self):
        return [self.focus or 1, 0]

    @cursor.setter
    def cursor(self, pos):
        self._set_focus(pos[0])
        if pos != self.cursor:
            self.emit('cursor_adjusted', self)

    def _set_focus(self, linenum):
        """Set focus to `linenum` if it is a legal line number."""
        if not self._folds:
            # Set requested line because there are no folds
            self.focus = linenum
            return
        for start, stop in self._folds:
            if start <= linenum <= stop:
                # Determine candidate line numbers that aren't in a fold
                if self.focus is None or linenum < self.focus:
                    candidates = (start - 1, stop + 1)
                else:
                    candidates = (stop + 1, start - 1)
                break
        else:
            # Set requested line because it's not in a fold
            self.focus = linenum
            return
        for c in candidates:
            if 1 <= c <= len(self.items):
                # Use this candidate because it's not out of bounds
                self.focus = c
                return
        # All candidates are out of bounds
        self.focus = None
        logger.debug('cursor moved oob')

    @property
    def empty(self):
        return not self.items

    @property
    def focused_item(self):
        """Return the currently focused item. Return `None` if no items exist
        or all items are hidden."""
        if not self.items:
            return None
        # Check if all items are hidden (a fold over all lines)
        if self._folds == [(1, len(self.items))]:
            return None
        try:
            return Path(self.items[(self.focus or 0) - 1].path)
        except IndexError:
            return None

    @focused_item.setter
    def focused_item(self, item):
        if item is None:
            return
        self.focus = [c.name for c in self.items].index(item.name) + 1

    def _render_items(self):
        """Render directory listing."""
        lines = []
        hls = []
        for linenum, item in enumerate(self.items):
            try:
                stat_res = item.stat(follow_symlinks=False)
            except OSError as stat_error:
                line = str(stat_error)
            else:
                line, line_hls = format_line(
                    item.path,
                    stat_res,
                    self._s.colors.file_hl_group(item, stat_res),
                    self._s.options['columns'].template,
                    self._s.options['time_format'].value,
                )
                for hl in line_hls:
                    hls.append((linenum, *hl))
            lines.append(line)
        self.buf[:] = lines
        self._apply_highlights(hls)

    @staticmethod
    def _list_files(path, sort_func):
        """List all files in path."""
        return list(sort_func(os.scandir(str(path))))

    def _apply_highlights(self, highlights):
        # TODO Apply highlights lazily
        for linenum, hl_group, start, stop in highlights:
            # TODO We can skip colorNormal
            # TODO don't hardcode horizontal hl offset
            # TODO Bulk
            logger.debug(('add_highlight', hl_group, linenum))
            self.buf.add_highlight(hl_group, linenum, start, stop, src_id=-1)

    def filter(self, func, query):
        """Hide all items that don't match `query`.

        Hiding is done by adding vim folds.
        """
        # TODO Handle changed sorting order and filtering
        self.clear_filter()
        folds = []
        # The line number in which the current fold started
        start_idx = None
        first_result = None
        for idx, item in enumerate(itertools.chain(self.items, (None,))):
            if item is None or func(query, item):
                if first_result is None:
                    first_result = idx + 1
                if start_idx is not None:
                    folds.append((start_idx + 1, idx))
                    start_idx = None
            else:
                if start_idx is None:
                    start_idx = idx
        for start, end in folds:
            # TODO Bulk request
            self._vim.command(':%d,%dfold' % (start, end))
        if first_result is not None:
            # TODO Doesn't reliably focus the first result
            self.focus = first_result
        self._folds = folds

    def clear_filter(self):
        if self._folds:
            # Eliminate all folds (zE)
            self._vim.command('normal! zE')
            self._folds = None


def format_line(path_str, stat_res, hl_group, template, format_time):
    # TODO Orphaned symlink
    mode = stat_res.st_mode
    hls = []
    extra = None
    name = Path(path_str).name
    if S_ISDIR(mode):
        name += '/'
        try:
            num_files = len(os.listdir(path_str))
        except OSError:
            size_str = '?'
        else:
            size_str = str(num_files)
            if num_files == 1:
                extra = format_dir_extra(mode, path_str)
    else:
        size_str = format_size(stat_res.st_size)
        if S_ISLNK(mode):
            extra = format_link_extra(path_str)
    meta = format_meta(stat_res, template, format_time, size_str)
    line = meta + ' '
    if hl_group is not None:
        hls.append((hl_group, len(line), len(line) + len(name)))
    line += name
    if extra:
        hls.append(('FileMeta', len(line), len(line) + len(extra)))
        line += extra
    hls.append(('FileMeta', 0, len(meta)))
    return line, hls

def format_meta(stat_res, template, format_time, size_str):
    return template.format(
        mode=stat.filemode(stat_res.st_mode),
        size=size_str,
        atime=format_time(stat_res.st_atime),
        ctime=format_time(stat_res.st_ctime),
        mtime=format_time(stat_res.st_mtime),
        ino=stat_res.st_ino,
        nlink=stat_res.st_nlink,
        uid=USERS.get(stat_res.st_uid, str(stat_res.st_uid)),
        gid=GROUPS.get(stat_res.st_gid, str(stat_res.st_gid)),
    )

def format_dir_extra(mode, path_str):
    extra = ''
    for _ in range(4):
        if not S_ISDIR(mode):
            break
        try:
            items = os.scandir(path_str)
        except OSError:
            break
        try:
            first = next(items)
        except StopIteration:
            break
        try:
            next(items)
        except StopIteration:
            pass
        else:
            break
        path_str = os.path.join(path_str, first.name)
        try:
            mode = first.stat().st_mode
        except OSError:
            break
        extra += first.name + ('/' if S_ISDIR(mode) else '')
    return extra

def format_link_extra(path_str):
    try:
        target = os.readlink(path_str)
    except OSError:
        target = '?'
    return ' -> ' + target

def format_size(bytes):
    if not bytes:
        return '0'
    units = ('', 'K', 'M', 'G', 'T', 'P')
    i = int(math.floor(math.log(bytes, 1024)))
    power = math.pow(1024, i)
    num = round(bytes / power, 2)
    if i == 0:
        return '%iB' % round(num)
    return '{n:.1f}{unit}'.format(n=num, unit=units[i])
