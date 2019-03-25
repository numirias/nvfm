import os
import stat

from .util import logger


# Map file type character to identifier used in LS_COLORS
FILETYPE_KEY_MAP = {
    'l': 'ln',
    'd': 'di',
    's': 'so',
    'p': 'pi',
    'b': 'bd',
    'c': 'cd',
}


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

        if pattern.startswith('*'):
            ext_map[pattern[1:]] = val
        else:
            special_map[pattern] = val
    logger.debug(''.join(list('%s %s\n' % (k, v) for k, v in ext_map.items())))
    return ext_map, special_map


class ColorManager:

    def __init__(self, vim):
        self._vim = vim

        self._ext_color_map, self._special_color_map = parse_colors()

    def define_highlights(self):
        """Define highlight groups for file coloring."""
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

    def file_hl_group(self, file):
        """Return the highlight group that `file` should be colored in."""
        try:
            modeline = stat.filemode(file.lstat().st_mode)
        except FileNotFoundError:
            # TODO Doesn't work for e.g. orphaned links
            return 'Error'
        filechar = modeline[0]
        # logger.debug(('MODE', filechar, self._special_color_map))
        if filechar != '-':  # Not a regular file
            if filechar == 'l' and self._special_color_map['ln'] == 'target':
                return self.file_hl_group(file.resolve())
            else:
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
                return None
        hl_group = ansi_color.replace(';', '_')
        return hl_group

