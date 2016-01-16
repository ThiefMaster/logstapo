import itertools
import os
from contextlib import ExitStack
from glob import glob

from logstapo.util import debug_echo, warning_echo


def logtail(path, offset_path=None, *, dry_run=False):
    """Yield new lines from a logfile.

    :param path: The path to the file to read from
    :param offset_path: The path to the file where offset/inode
                        information will be stored.  If not set,
                        ``<file>.offset`` will be used.
    :param dry_run: If ``True``, the offset file will not be modified
                    or created.
    """
    if offset_path is None:
        offset_path = path + '.offset'

    try:
        logfile = open(path, encoding='utf-8', errors='replace')
    except OSError as exc:
        warning_echo('Could not read: {} ({})'.format(path, exc))
        return

    closer = ExitStack()
    closer.enter_context(logfile)
    with closer:
        line_iter = iter([])
        stat = os.stat(logfile.fileno())
        debug_echo('logfile inode={}, size={}'.format(stat.st_ino, stat.st_size))
        inode, offset = _parse_offset_file(offset_path)
        if inode is not None:
            if stat.st_ino == inode:
                debug_echo('inodes are the same')
                if offset == stat.st_size:
                    debug_echo('offset points to eof')
                    return
                elif offset > stat.st_size:
                    warning_echo('File shrunk since last read: {} ({} < {})'.format(path, stat.st_size, offset))
                    offset = 0
            else:
                debug_echo('inode changed, checking for rotated file')
                rotated_path = _check_rotated_file(path, inode)
                if rotated_path is not None:
                    try:
                        rotated_file = open(rotated_path, encoding='utf-8', errors='replace')
                    except OSError as exc:
                        warning_echo('Could not read rotated file: {} ({})'.format(rotated_path, exc))
                    else:
                        closer.enter_context(rotated_file)
                        rotated_file.seek(offset)
                        line_iter = itertools.chain(line_iter, iter(rotated_file))
                offset = 0
        logfile.seek(offset)
        line_iter = itertools.chain(line_iter, iter(logfile))
        for line in line_iter:
            line = line.strip()
            yield line
        pos = logfile.tell()
        debug_echo('reached end of logfile at {}'.format(pos))
        if not dry_run:
            debug_echo('writing offset file: ' + offset_path)
            _write_offset_file(offset_path, stat.st_ino, pos)
        else:
            debug_echo('dry run - not writing offset file')


def _check_rotated_file(path, inode):
    for func in (_check_rotated_numext, _check_rotated_dateext):
        rotated_path = func(path)
        if rotated_path is None:
            debug_echo('no rotated file found using ' + func.__name__)
            continue
        debug_echo('found rotated file candidate using {}: {}'.format(func.__name__, rotated_path))
        if os.stat(rotated_path).st_ino == inode:
            debug_echo('inodes match, using candidate')
            return rotated_path
        else:
            debug_echo('inodes do not match, discarding candidate')


def _check_rotated_numext(path):
    if os.path.isfile(path + '.1'):
        return path + '.1'


def _check_rotated_dateext(path):
    candidates = [x for x in glob(path + '-????????') if x[-8:].isdigit() and os.path.isfile(x)]
    if candidates:
        return sorted(candidates)[-1]


def _parse_offset_file(path):
    debug_echo('checking offset file ' + path)
    try:
        with open(path) as f:
            inode = int(f.readline())
            offset = int(f.readline())  # pragma: no branch
    except FileNotFoundError as exc:
        debug_echo('open() failed: {}'.format(exc))
        return None, 0
    except ValueError as exc:
        debug_echo('could not parse: {}'.format(exc))
        return None, 0
    else:
        debug_echo('inode={}, offset={}'.format(inode, offset))
        return inode, offset


def _write_offset_file(path, inode, offset):
    try:
        with open(path, 'w') as offset_file:
            os.fchmod(offset_file.fileno(), 0o600)
            offset_file.write('{}\n{}\n'.format(inode, offset))  # pragma: no branch
    except OSError as exc:
        warning_echo('Could not write: {} ({})'.format(path, exc))
