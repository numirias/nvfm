# -*- coding: future_fstrings -*-
import os
from stat import (S_ISBLK, S_ISCHR, S_ISDIR, S_ISFIFO, S_ISLNK, S_ISREG,
                  S_ISSOCK, S_IXUSR)

from .util import logger, stat_path


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
                    r = next(parts) # noqa
                    g = next(parts) # noqa
                    b = next(parts) # noqa
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


def parse_colors():
    """Parse $LS_COLORS and return mappings of extensions to colors."""
    var = os.environ.get('LS_COLORS', '')
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

        if pattern.startswith('*'):
            ext_map[pattern[1:]] = val
        else:
            special_map[pattern] = val
    logger.debug(''.join(list('%s %s\n' % (k, v) for k, v in ext_map.items())))
    return ext_map, special_map


class ColorManager:

    def __init__(self, vim):
        self._vim = vim
        self._colors, self._colors_special = parse_colors()

    def define_highlights(self):
        """Define highlight groups for file coloring."""
        for ansi_code in dict.fromkeys([*self._colors.values(),
                                        *self._colors_special.values()]):
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

    def file_hl_group(self, file, stat_res=None, stat_error=None):
        """Return the highlight group that `file` should be colored in."""
        if stat_error is not None:
            return 'Error'
        if stat_res is None:
            return self.file_hl_group(file, *stat_path(file))
        mode = stat_res.st_mode
        if not S_ISREG(mode):  # Not a regular file
            if S_ISLNK(mode):
                if self._colors_special.get('ln') == 'target':
                    # TODO
                    # resolved = file.resolve()
                    # if resolved == file:
                    #     # Don't try to resolve another time
                    #     # TODO
                    #     raise Exception('recursion! %s' % resolved)
                    return self.file_hl_group(file,
                                              *stat_path(file, lstat=False))
                else:
                    ansi_color = self._colors_special.get('ln')
            elif S_ISCHR(mode):
                ansi_color = self._colors_special.get('cd')
            elif S_ISDIR(mode):
                ansi_color = self._colors_special.get('di')
            elif S_ISFIFO(mode):
                ansi_color = self._colors_special.get('pi')
            elif S_ISBLK(mode):
                ansi_color = self._colors_special.get('bd')
            elif S_ISSOCK(mode):
                ansi_color = self._colors_special.get('so')
            else:
                # TODO Does this happen?
                return 'Error'
        elif mode & S_IXUSR:  # Executable
            ansi_color = self._colors_special.get('ex')
        else: # Regular file
            needle = file.name.lower()
            for pattern, colorcode in self._colors.items():
                if needle.endswith(pattern):
                    ansi_color = colorcode
                    break
            else:
                # TODO Could not find a target color
                return None
        if ansi_color is None:
            return None
        hl_group = 'color' + ansi_color.replace(';', '_')
        return hl_group
