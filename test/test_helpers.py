from pathlib import Path
from textwrap import dedent


def _parts(line):
    i = 0
    while True:
        if line[i] != ' ':
            break
        i += 1
    rest = line[i:]
    content = None
    if rest.endswith('/'):
        name = rest[:-1]
        type = 'd'
    else:
        name = rest
        type = 'f'
        content = ''
    if '=' in name:
        name, content = name.split('=')
        content = content.encode('utf-8').decode('unicode_escape')
    return (i // 4, name, type, content)


def make_tree(root, s):
    """Produce a directory tree starting at `root` as given by `s`.

    This simplifies writing tests for different nested path structures.
    """
    s = dedent(s)
    cur_path = root
    cur_level = -1
    for line in s.splitlines():
        if not line:
            continue
        level, name, type, content = _parts(line)
        if level == cur_level:
            cur_path = cur_path.parent / name
        elif level > cur_level:
            cur_path = cur_path / name
        elif level < cur_level:
            for i in range(cur_level - level):
                cur_path = cur_path.parent
            cur_path = cur_path.parent / name
        cur_level = level
        if type == 'd':
            cur_path.mkdir()
        elif type == 'f':
            cur_path.write_text(content)


def test_make_tree(tmpdir_factory):
    root = Path(str(tmpdir_factory.mktemp('tree')))
    make_tree(root, '''
    xx/
    yy=foo\\n\\x3cbar
    aa/
        bb/
    cc/
        dd/
        ee/
            ff/
        gg/
            hh/
    ii/
    ''')
    assert (root / 'xx').is_dir()
    assert (root / 'yy').is_file()
    assert (root / 'yy').read_text() == 'foo\n\x3cbar'
    assert (root / 'aa/bb').is_dir()
    assert (root / 'cc/dd').is_dir()
    assert (root / 'cc/ee/ff').is_dir()
    assert (root / 'cc/gg/hh').is_dir()
    assert (root / 'ii').is_dir()
