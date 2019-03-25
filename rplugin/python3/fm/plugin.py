import getpass
import math
import os
from pathlib import Path
import platform
import re
import stat

import pynvim

from .util import logger

HOST = platform.node()
USER = getpass.getuser()


# Files above this size will be truncated before preview
PREVIEW_SIZE_LIMIT = 100_000

# Max number of bytes in a hexdump preview
HEXDUMP_LIMIT = 16*256

# Map file type character to identifier used in LS_COLORS
FILETYPE_KEY_MAP = {
    'l': 'ln',
    'd': 'di',
    's': 'so',
    'p': 'pi',
    'b': 'bd',
    'c': 'cd',
}


def convert_size(bytes):
    if not bytes:
        return '0'
    units = ('', 'K', 'M', 'G', 'T', 'P')
    i = int(math.floor(math.log(bytes, 1024)))
    power = math.pow(1024, i)
    num = round(bytes / power, 2)
    if i == 0:
        return '%iB' % round(num)
    return '{n:.1f}{unit}'.format(n=num, unit=units[i])


def natural_sort_key(s, _nsre=re.compile('([0-9]+)')):
    # https://stackoverflow.com/questions/4836710/does-python-have-a-built-in-function-for-string-natural-sort
    return [int(text) if text.isdigit() else text.lower()
            for text in _nsre.split(s)]

def parse_colors():
    """Parse $LS_COLORS and return mappings of extensions to colors."""
    var = os.environ.get('LS_COLORS')
    items = var.split(':')
    ext_map = {}
    special_map = {}
    for item in items:
        try:
            pattern, val = item.split('=')
        except ValueError:
            # TODO
            continue
        pattern = pattern.lower()
        # markup_parts = val.split(';')
        # if len(markup_parts) == 3:
        #     color_code = markup_parts[2]
        # elif len(markup_parts) == 1:
        #     logger.debug(('color not parsed', color))
        #     continue
        # else:
        #     logger.debug(('color not parsed', color))
        #     continue
        color_code = val

        if pattern.startswith('*'):
            ext_map[pattern[1:]] = color_code
            continue
        special_map[pattern] = color_code
    logger.debug(''.join(list('%s %s\n' % (k, v) for k, v in ext_map.items())))
    return ext_map, special_map

def list_files(path):
    """List all files in path."""
    files = list(path.iterdir())

    filemap = {f.name:f for f in files}
    import time
    t = time.time()
    # TODO faster sort
    sorted_names = sorted(filemap, key=natural_sort_key)
    sorted_files = [filemap[k] for k in sorted_names]
    logger.debug(('sort', '%f' % (time.time() - t)))

    return sorted_files

def win_set_buf(win, buf):
    return win.request('nvim_win_set_buf', buf)


def ansi_to_vim_color(ansi):
    parts = iter(ansi.split(';'))
    fg = bg = None
    special = ''
    try:
        while True:
            part = next(parts)
            if part == '38':
                part = next(parts)
                if part == '5':
                    fg = next(parts)
                elif part == '2':
                    r = next(parts)
                    g = next(parts)
                    b = next(parts)
                    # TODO Handle rgb
            elif part == '48':
                part = next(parts)
                if part == '5':
                    bg = next(parts)
                elif part == '2':
                    r = next(parts)
                    g = next(parts)
                    b = next(parts)
                    # TODO Handle rgb
            elif part == '0':
                special = None
            elif part == '1':
                special += 'bold,'
            elif part == '2':
                pass # Don't handle "faint"
            elif part == '3':
                special += 'italic,'
            elif part == '4':
                special += 'underline,'
            elif part == '7':
                # Reverse video = swap fg and bg
                fg, bg = bg, fg
            elif part == 'target':
                # special = 'target'
                # TODO
                pass
            else:
                logger.error(('SKIP', part))
                pass
            # TODO Handle codes 30-37, 40-47, 90-97, 100-107
    except StopIteration:
        return (fg, bg, special)


@pynvim.plugin
class Plugin:

    def __init__(self, vim):
        self._vim = vim

        self._cur_dir = None
        self._cur_items = []
        self._cur_line = None

        # Map directories to last focused file in that directory
        self._focus_cache = {}
        self._start_path = Path(os.environ.get('NVFM_START_PATH', '.'))
        self._listing_format = None

    # @pynvim.autocmd('BufEnter', pattern='filelist', sync=True)
    # def event_vim_enter(self):
    @pynvim.function('NvfmStartup', sync=True)
    def func_nvfm_startup(self, args):
        logger.debug(('vimenter'))
        self._ext_color_map, self._special_color_map = parse_colors()
        self._define_highlights()
        logger.debug([b.name for b in self._vim.buffers])
        buffers = {Path(b.name).name: b for b in self._vim.buffers}
        self._buffers = buffers
        logger.debug(buffers)
        self._win_buf_map = {w: w.buffer for w in self._vim.windows}
        logger.debug(self._win_buf_map)

        self._enter_dir(self._start_path)

    @pynvim.function('NvfmEnter', sync=True)
    def func_nvfm_enter(self, args):
        logger.debug(('enter', ))
        what = args[0]
        if isinstance(what, int):
            idx = args[0] - 1
            try:
                target = self._cur_items[idx]
            except IndexError:
                logger.warn('nothing to enter')
                return
        else:
            # '..' in paths isn't collapsed automatically
            if what == '..':
                target = self._cur_dir.parent
            else:
                target = self._cur_dir / what
        if not target.is_dir():
            # TODO Enter file?
            return
        self._enter_dir(target)

    def _define_highlights(self):
        # for code in self._ext_color_map.values():
        for ansi_code in dict.fromkeys([*self._ext_color_map.values(), *self._special_color_map.values()]):
        # for code in range(255):
            # cmd = f'hi color{code} ctermfg={code}'
            code_safe = ansi_code.replace(';', '_')
            fg, bg, special = ansi_to_vim_color(ansi_code)
            args = ''
            if fg is not None:
                args += 'ctermfg=' + fg
            if bg is not None:
                args += ' ctermbg=' + bg
            if special:  # special is never None
                args += ' cterm=' + special
            if args:
                cmd = f'hi color{code_safe} {args}'
                logger.debug(cmd)
                self._vim.command(cmd)

    def _make_line_colors(self, files):
        """Return list of `(linenum, hl_group)` for each file in `files`."""
        # TODO Too slow
        line_colors = []
        for linenum, file in enumerate(files):
            hl_group = self._file_hl_group(file)
            if hl_group is not None:
                line_colors.append((linenum, hl_group))
        return line_colors

    def _file_hl_group(self, file):
        """Return the highlight group that `file` should be colored in."""
        modeline = stat.filemode(file.lstat().st_mode)
        filechar = modeline[0]
        # logger.debug(('MODE', filechar, self._special_color_map))

        if filechar != '-':  # Not a regular file
            ansi_color = self._special_color_map[FILETYPE_KEY_MAP[filechar]]
        elif 'x' in modeline:  # Executable
            ansi_color = self._special_color_map['ex']
        else: # Regular file
            needle = file.name.lower()
            for pattern, colorcode in self._ext_color_map.items():
                if needle.endswith(pattern):
                    ansi_color = colorcode
                    break
            else:
                # TODO Could not find a target color
                return 'Normal'

        hl_group = ansi_color.replace(';', '_')
        return hl_group

    def _enter_dir(self, dir):
        """The user enters `target`."""
        self._save_current_focus()
        # self._vim.vars['fm_focus'] = ''
        # target = target.resolve()
        # self._history.append((self._cur_dir, self._cur_line))
        logger.debug(('enter', dir))
        self._cur_dir = dir
        # Reset cur line, so CursorMoved notices that the current line has changed
        self._cur_line = None
        files = self._render_dir(dir, win_id=1)
        self._cur_items = files
        if not files:
            self.render_empty(2)
        if dir == Path('/'):
            self.render_empty(0)
        else:
            self._render_dir(dir.parent, win_id=0)
        logger.debug(('windows', list(self._vim.windows)))

    def render_empty(self, win_id):
        window = self._vim.windows[win_id]
        buf = self._win_buf_map[window]
        buf[:] = []

    def _save_current_focus(self):
        if self._cur_dir is None:
            # We are not in a dir
            return
        if not self._cur_items:
            # There are no items in this dir
            return
        self._focus_cache[self._cur_dir] = self._cur_items[self._vim.windows[1].cursor[0] - 1]
        logger.debug(('saved focus for', self._cur_dir))

        self._focus_cache[self._cur_dir.parent] = self._cur_dir

    def _render_dir(self, dir, win_id):
        """Render the content of directory `dir` in window `win_id`."""
        logger.debug(('render', win_id, dir))


        window = self._vim.windows[win_id]
        buf = self._win_buf_map[window]
        try:
            files = list_files(dir)
        except PermissionError as e:
            buf[:] = [str(e)]
            return []
        # logger.debug(('render', files))

        line_colors = self._make_line_colors(files)
        if not files:
            buf[:] = ['(directory empty)']
            return files

        if win_id == 0:
            focused_item = self._cur_dir
        else:
            focused_item = self._focus_cache.get(dir)
        if focused_item is not None:
            try:
                offset = files.index(focused_item)
            except ValueError:
                # TODO Does this make sense?
                focused_item = None
                offset = -1
        else:
            # When focused_item couldn't be retrieved from cache
            offset = -1

        lines = []

        for i, fp in enumerate(files):
            st = fp.lstat()
            # TODO FIle doesn't exist
            # TODO Orphaned symlink
            mode = stat.filemode(st.st_mode)
            size = convert_size(st.st_size)
            name = fp.name
            if fp.is_dir():
                name += '/'
            if fp.is_symlink():
                name += ' -> ' + os.readlink(fp)
            s = f'{mode} {size:>6} {name}'
            if i == offset:
                # Pad with spaces so we can background-highlight the line.
                # (Using "cursorline" for that is buggy)
                # s = ' {x: <{w}}'.format(x=fn, w=window.width)
                s = s.ljust(window.width)

            lines.append(s)
        buf[:] = lines

        # TODO Catch exception if doesn't exist (removed?)
        # Attempt to restore focus
        if focused_item is not None:
            if win_id == 0:
                # In the left pane, always focus the dir of the main pane
                window.cursor = [offset + 1, 0]
            elif win_id == 1:
                window.cursor = [offset + 1, 0]
            elif win_id == 2:
                buf.add_highlight('SelectedEntry', offset, 0, -1, src_id=-1)

        for linenum, colorcode in line_colors:
            # TODO We can skip colorNormal
            # TODO don't hardcode horizontal hl offset
            logger.debug(('add_highlight', f'color{colorcode}', linenum))
            buf.add_highlight(f'color{colorcode}', linenum, 18, -1, src_id=-1)

        return files

    # If sync=True,the syntax highlighting is not applied
    @pynvim.autocmd('CursorMoved', pattern='nvfm_main', sync=False)
    def focus_changed(self):
        # Don't track cursor movement when file list is empty
        if not self._cur_items:
            self._set_tabline(self._cur_dir)
            return
        win = self._vim.windows[1]
        cursor = win.cursor
        cur_line = cursor[0]
        if cursor[1] > 0:
            win.cursor = [cur_line, 0]
        # logger.debug(('moved', cur_line))
        if cur_line == self._cur_line:
            # TODO When does this happen?!
            logger.debug('same')
            return
        self._cur_line = cur_line
        item_focus = self._cur_items[cur_line - 1]
        # logger.debug(('view', str(item_focus.name)))
        self._set_tabline(self._cur_dir, item_focus)

        win = self._vim.windows[2]
        try:
            self.render_item(item_focus, win)
        except FileNotFoundError as e:
            self.render_message(str(e), win, hl='Error')

        self._vim.vars['statusline2'] = '%d/%d' % (cur_line, len(self._cur_items))

    def render_item(self, item, win):
        if item.is_dir():
            # Make right window display the preview buffer if it isn't already
            if win.buffer == self._win_buf_map[win]:
                logger.debug(('STAY'))
            else:
                win_set_buf(win, self._win_buf_map[win])
            self._render_dir(item, win_id=2)
        else:
            self._render_file_preview(item)

    def render_message(self, msg, win, hl):
        buf = self._win_buf_map[win]
        win_set_buf(win, buf)
        buf[:] = [msg]
        buf.add_highlight(hl, 0, 0, -1, src_id=-1)

    def _render_file_preview(self, fp):
        st = fp.stat()
        mode = stat.filemode(st.st_mode)
        size = st.st_size

        if size > PREVIEW_SIZE_LIMIT:
            self._render_head(fp)
        else:
            self._vim.call('ViewFile', str(fp))

        self._vim.vars['statusline3'] = mode

    def _render_head(self, fp):
        with open(fp, 'rb') as f:
            bytes = f.read(PREVIEW_SIZE_LIMIT)
            try:
                bytes.decode('utf-8')
            except UnicodeDecodeError:
                # This is not valid utf-8, so do a hexdump
                need_hexdump = True
            else:
                need_hexdump = False
                # No hexdump, so read up to preview size limit
                # bytes += f.read(PREVIEW_SIZE_LIMIT - HEXDUMP_LIMIT)

        if need_hexdump:
            lines = hexdump(bytes[:HEXDUMP_LIMIT])
        else:
            lines = [x.decode('utf-8') for x in bytes.splitlines()]

        filename = str(fp) + '.preview'
        num = self._vim.call('bufnr', filename)
        if num == -1:
            num = self._vim.call('bufnr', filename, 1)
        win = self._vim.windows[2]
        buf = self._vim.buffers[num]
        win_set_buf(win, buf)

        self._vim.call('ViewHexdump')
        buf[:] = lines

    def _set_tabline(self, path, selected=None):
        pathinfo = f'{USER}@{HOST}:%#TabLinePath#{path.parent}'
        if path.parent.name:
            pathinfo += '/'
        if path.name:
            pathinfo += f'%#TabLineCurrent#{path.name}%#TabLinePath#/'
        if selected:
            selected_str = selected.name + ('/' if selected.is_dir() else '')
            selected_hl = f'color{self._file_hl_group(selected)}'
            pathinfo += f'%#{selected_hl}#{selected_str}'
        # Make sure the hl is reset at the end
        pathinfo += '%#TabLineFill#'
        self._vim.options['tabline'] = pathinfo

    def _set_status(self, status):
        self._vim.vars['statusline3'] = status
        # TODO Recommended by vim docs to force update, but there should be a
        # more performant way
        self._vim.options['ro'] = self._vim.options['ro']

    def echo(self, *msgs):
        msg = ' '.join([str(m) for m in msgs])
        self._vim.out_write(msg + '\n')


def hexdump(bytes):
    from subprocess import run, PIPE
    text = run('xxd', stdout=PIPE, stderr=PIPE, input=bytes)
    lines = text.stdout.decode('utf-8').splitlines()
    return lines
