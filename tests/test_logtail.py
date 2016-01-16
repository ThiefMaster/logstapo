from functools import partial

import pytest

from logstapo.logtail import logtail


def test_logtail_invalid(mocker, tmpdir):
    warning_echo = mocker.patch('logstapo.logtail.warning_echo')
    assert list(logtail(tmpdir.join('nosuchfile').strpath)) == []
    assert warning_echo.called


@pytest.mark.parametrize('rotated_suffix', ('.1', '-20150101'))
@pytest.mark.parametrize('custom_offset_path', (False, True))
def test_logtail(mocker, tmpdir, rotated_suffix, custom_offset_path):
    mocker.patch('logstapo.logtail.debug_echo')
    mocker.patch('logstapo.logtail.warning_echo')
    log = tmpdir.join('test.log')
    rotated = tmpdir.join('test.log' + rotated_suffix)
    if custom_offset_path:
        offset = tmpdir.join('offset_test.log')
        logtail_fn = partial(logtail, offset_path=offset.strpath)
    else:
        offset = tmpdir.join('test.log.offset')
        logtail_fn = logtail
    log.write('hello\nworld\n')
    assert not offset.check()
    assert list(logtail_fn(log.strpath)) == ['hello', 'world']
    assert offset.check()
    data = offset.read()
    assert list(logtail_fn(log.strpath)) == []
    assert data == offset.read()
    # append
    log.write('foo\n', 'a')
    assert list(logtail_fn(log.strpath)) == ['foo']
    assert list(logtail_fn(log.strpath)) == []
    # append and rotate
    log.write('foo\n', 'a')
    log.rename(rotated)
    log.write('new\n')
    assert list(logtail_fn(log.strpath)) == ['foo', 'new']


def test_logtail_bad_charset(mocker, tmpdir):
    mocker.patch('logstapo.logtail.debug_echo')
    mocker.patch('logstapo.logtail.warning_echo')
    log = tmpdir.join('test.log')
    garbage = bytes(bytearray(range(33, 256)))
    # proper utf8
    log.write('möp\n'.encode('utf-8'), mode='wb')
    # not utf8
    log.write('möp\n'.encode('latin1'), mode='ab')
    # pure garbage
    log.write(garbage, mode='ab')
    lines = list(logtail(log.strpath))
    assert lines == ['möp',
                     'm\N{REPLACEMENT CHARACTER}p',
                     ''.join(chr(x) if x < 128 else '\N{REPLACEMENT CHARACTER}' for x in garbage)]


def test_logtail_shrink(mocker, tmpdir):
    mocker.patch('logstapo.logtail.debug_echo')
    warning_echo = mocker.patch('logstapo.logtail.warning_echo')
    log = tmpdir.join('test.log')
    log.write('hello\nworld\n')
    assert list(logtail(log.strpath)) == ['hello', 'world']
    log.write('hello\nbar\n')
    assert not warning_echo.called
    assert list(logtail(log.strpath)) == ['hello', 'bar']
    assert warning_echo.called


@pytest.mark.parametrize('dry_run', (True, False))
def test_logtail_dryrun(mocker, tmpdir, dry_run):
    mocker.patch('logstapo.logtail.debug_echo')
    mocker.patch('logstapo.logtail.warning_echo')
    log = tmpdir.join('test.log')
    offset = tmpdir.join('test.log.offset')
    log.write('hello\nworld\n')
    assert list(logtail(log.strpath, dry_run=dry_run)) == ['hello', 'world']
    assert offset.check() == (not dry_run)


def test_logtail_rotated_unreadable(mocker, tmpdir):
    mocker.patch('logstapo.logtail.debug_echo')
    warning_echo = mocker.patch('logstapo.logtail.warning_echo')
    log = tmpdir.join('test.log')
    rotated = tmpdir.join('test.log.1')
    log.write('hello\nworld\n')
    assert list(logtail(log.strpath)) == ['hello', 'world']
    log.rename(rotated)
    rotated.chmod(0o000)
    log.write('new\n')
    assert not warning_echo.called
    assert list(logtail(log.strpath)) == ['new']
    assert warning_echo.called


def test_logtail_rotated_wrong_inode(mocker, tmpdir):
    mocker.patch('logstapo.logtail.debug_echo')
    mocker.patch('logstapo.logtail.warning_echo')
    log = tmpdir.join('test.log')
    rotated = tmpdir.join('test.log.1')
    log.write('hello\nworld\n')
    assert list(logtail(log.strpath)) == ['hello', 'world']
    # copy it so the rotated file has a different inode
    log.copy(rotated)
    rotated.write('bar\n', 'a')
    log.remove()
    log.write('foo\n')
    assert list(logtail(log.strpath)) == ['foo']


def test_logtail_bad_offset_file(mocker, tmpdir):
    mocker.patch('logstapo.logtail.debug_echo')
    warning_echo = mocker.patch('logstapo.logtail.warning_echo')
    log = tmpdir.join('test.log')
    offset = tmpdir.join('test.log.offset')
    log.write('hello\nworld\n')
    assert list(logtail(log.strpath)) == ['hello', 'world']
    offset.write('')
    assert list(logtail(log.strpath)) == ['hello', 'world']
    offset.chmod(0o400)
    log.write('foo\n', 'a')
    assert not warning_echo.called
    assert list(logtail(log.strpath)) == ['foo']
    assert warning_echo.called
    assert list(logtail(log.strpath)) == ['foo']
