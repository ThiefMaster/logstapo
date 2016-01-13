import re
import textwrap
from collections import OrderedDict
from unittest.mock import call

import pytest

from logstapo.config import _Pattern
from logstapo.logs import process_logs, process_log


@pytest.mark.parametrize(('names', 'expected'), (
    (None, ['a', 'b', 'c']),
    (['c', 'a'], ['c', 'a']),
    ([], []),
))
def test_process_logs(mocker, mock_config, names, expected):
    mock_config({'logs': OrderedDict([('b', object()), ('a', object()), ('c', object())])})
    process_log = mocker.patch('logstapo.logs.process_log')
    process_logs(names)
    process_log.assert_has_calls([call(x) for x in expected])


@pytest.mark.parametrize('dry_run', (True, False))
def test_process_log(mocker, mock_config, dry_run):
    test_log_def = {'garbage': [_Pattern('crap')],
                    'ignore': {_Pattern('foo'): [_Pattern('boring')],
                               _Pattern('bar'): [_Pattern('zzz')]},
                    'regexps': ['test'],
                    'files': ['foo']}
    config = {'verbosity': 0,
              'debug': False,
              'dry_run': dry_run,
              'regexps': {'test': re.compile('^(?P<source>[^/]+)/(?P<message>.+)$')},
              'logs': {'test': test_log_def}}
    dummy_logs = textwrap.dedent('''
        crap
        foo/zzz
        foo/123
        foo/boring
        bar/boring
        bar/456
        bar/zzz
        wtf
    ''')
    mock_config(config)
    mocker.patch('logstapo.logs.debug_echo')
    mocker.patch('logstapo.logs.verbose_echo')
    mocker.patch('logstapo.logs.warning_echo')
    logtail = mocker.patch('logstapo.logs.logtail', return_value=dummy_logs.strip().split('\n'))
    other, invalid = process_log('test')
    expected = [(x, dict(zip(('source', 'message'), x.split('/'))))
                for x in ['foo/zzz', 'foo/123', 'bar/boring', 'bar/456']]
    assert other == expected
    assert invalid == ['wtf']
    logtail.assert_called_once_with('foo', dry_run=dry_run)
