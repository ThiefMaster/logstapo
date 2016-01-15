import re
from io import StringIO

import click
import pytest

from logstapo.actions import Action
from logstapo.cli import main
from logstapo import config


@pytest.mark.parametrize(('pattern', 'regex'), (
    # globs
    ('?', r'^.$'),
    ('*foo+bar', r'^.*{}$'.format(re.escape('foo+bar'))),
    ('/test*', r'^{}.*$'.format(re.escape('/test'))),
    ('foo', r'^foo$'),
    ('bl*ah?', r'^bl.*ah.$'),
    # regexps
    ('/blah/', r'^blah$'),
    ('/bl*ah?/', r'^bl*ah?$'),
))
@pytest.mark.parametrize('negate', (True, False))
def test_pattern(pattern, regex, negate):
    prefix = '^' if negate else ''
    patternobj = config._Pattern(prefix + pattern)
    assert patternobj.negate == negate
    assert patternobj.regex.pattern == regex
    assert not patternobj.always_match


@pytest.mark.parametrize('negate', (True, False))
def test_pattern_wildcard(negate):
    prefix = '^' if negate else ''
    patternobj = config._Pattern(prefix + '*')
    assert patternobj.negate == negate
    assert patternobj.always_match


def test_pattern_none():
    patternobj = config._Pattern()
    assert not patternobj.negate
    assert patternobj.always_match


@pytest.mark.parametrize(('pattern', 'string', 'expected'), (
    ('foo*', 'foobar', True),
    ('^foo*', 'foobar', False),
    ('*', 'foobar', True),
    ('^*', 'foobar', False),
    ('/test1{3}/', 'test111', True),
    ('^/test1{3}/', 'test', True),
    ('/test1{3}/', 'test111x', False),
))
def test_pattern_test(pattern, string, expected):
    patternobj = config._Pattern(pattern)
    assert patternobj.test(string) == expected


def test_current_config():
    with click.Context(main).scope() as ctx:
        ctx.params['config'] = {'foo': 'bar'}
        assert config.current_config == {'foo': 'bar'}


def test_current_config_no_ctx():
    with pytest.raises(RuntimeError):
        list(config.current_config.keys())


def test_parse_config():
    io = StringIO('foo: bar')
    assert config.parse_config(io) == {'foo': 'bar'}


def test_parse_config_invalid():
    io = StringIO('non: [sense')
    with pytest.raises(config.ConfigError):
        config.parse_config(io)


def test_process_regexps_invalid():
    # groups missing
    with pytest.raises(config.ConfigError):
        config._process_regexps({'test': 'foo'})
    # invalid regex
    with pytest.raises(config.ConfigError):
        config._process_regexps({'test': '???(?P<source>.)(?P<message>.)'})
    # invalid placeholder
    with pytest.raises(config.ConfigError):
        config._process_regexps({'test': '%(none)(?P<source>.)(?P<message>.)'})


def test_process_regexps():
    rv = config._process_regexps({'__msg': '(?P<message>.)', 'test': '(?P<source>.)%(msg)'})
    assert rv == {'test': re.compile('(?P<source>.)(?P<message>.)')}


def test_process_actions(mocker):
    class DummyAction(Action):
        def __init__(self, data, type_):
            self.type = type_
            self.data = data

        def __eq__(self, other):
            return self.type == other.type and self.data == other.data

    mocker.patch('logstapo.actions.Action.from_config', lambda type_, data: DummyAction(data, type_))
    actions, auto_actions = config._process_actions({'foo': {'type': 'FOO', 'hello': 'world'},
                                                     'bar': {'type': 'BAR', 'auto': False}})
    assert actions == {'foo': DummyAction({'hello': 'world'}, 'FOO'),
                       'bar': DummyAction({}, 'BAR')}
    assert auto_actions == {'foo'}


def test_process_actions_invalid(mocker):
    # no type
    with pytest.raises(config.ConfigError):
        config._process_actions({'foo': {'auto': False}})
    # invalid type
    with pytest.raises(config.ConfigError):
        mocker.patch('logstapo.actions.Action.from_config', side_effect=config.ConfigError)
        config._process_actions({'foo': {'type': 'invalid'}})


@pytest.mark.parametrize(('data', 'expected'), (
    ({'file': 'foo'}, {'foo'}),
    ({'files': 'foo'}, {'foo'}),
    ({'file': ['foo']}, {'foo'}),
    ({'files': 'foo', 'file': 'bar'}, {'foo', 'bar'}),
    ({'files': 'foo', 'file': ['bar']}, {'foo', 'bar'}),
    ({'files': ['foo']}, {'foo'}),
    ({'files': ['foo', 'bar']}, {'foo', 'bar'}),
    ({'file': 'foo', 'files': ['bar']}, {'foo', 'bar'}),
    ({'file': ['foo', 'bar']}, {'foo', 'bar'}),
    ({'file': ['foo', 'bar'], 'files': ['bar']}, {'foo', 'bar'}),
))
def test_process_log_files(data, expected):
    assert config._process_log_files(data) == expected


def test_process_log_files_invalid():
    with pytest.raises(config.ConfigError):
        config._process_log_files({})
    with pytest.raises(config.ConfigError):
        config._process_log_files({'files': []})
    with pytest.raises(config.ConfigError):
        config._process_log_files({'file': []})


@pytest.mark.parametrize(('data', 'name', 'expected'), (
    ({}, 'foo', ('foo',)),
    ({}, 'bar', ('bar',)),
    ({'regex': 'foo'}, 'bar', ('foo',)),
    ({'regex': 'foo'}, 'foo', ('foo',)),
    ({'regex': ['foo', 'bar']}, 'foo', ('foo', 'bar')),
    ({'regex': ['bar', 'foo']}, 'foo', ('bar', 'foo'))
))
def test_process_log_regexps(data, name, expected):
    available = {'foo': object(), 'bar': object()}
    assert config._process_log_regexps(data, name, available) == expected


def test_process_log_regexps_invalid():
    with pytest.raises(config.ConfigError):
        config._process_log_regexps({}, 'test', {'foo': object()})
    with pytest.raises(config.ConfigError):
        config._process_log_regexps({'regex': 'bar'}, 'foo', {'foo': object()})


@pytest.mark.parametrize(('data', 'expected'), (
    ({}, {'bar'}),
    ({'actions': ''}, set()),
    ({'action': ''}, set()),
    ({'action': 'foo'}, {'foo'}),
    ({'action': ['foo'], 'actions': 'bar'}, {'foo', 'bar'}),
    ({'actions': ['foo'], 'action': 'bar'}, {'foo', 'bar'}),
    ({'actions': 'foo', 'action': 'bar'}, {'foo', 'bar'}),
))
def test_process_log_actions(data, expected):
    available = {'foo': object(), 'bar': object()}
    auto_actions = {'bar'}
    assert config._process_log_actions(data, 'test', auto_actions, available) == expected


def test_process_log_actions_invalid():
    with pytest.raises(config.ConfigError):
        config._process_log_actions({'action': 'test'}, 'test', set(), {'foo': object()})


@pytest.mark.parametrize(('data', 'expected'), (
    ([], []),
    ('foo', ['foo']),
    (['foo'], ['foo']),
))
def test_unify_patterns(mocker, data, expected):
    class DummyPattern(object):
        def __init__(self, pattern):
            self.pattern = pattern

        def __eq__(self, other):
            return self.pattern == other.pattern

    mocker.patch('logstapo.config._Pattern', DummyPattern)
    assert config._unify_patterns(data) == [DummyPattern(p) for p in expected]


@pytest.mark.parametrize(('data', 'expected'), (
    ([], {}),
    ('foo', {None: ['foo']}),
    (['foo', 'bar'], {None: ['foo', 'bar']}),
    ({'foo': 'bar'}, {'foo': ['bar']}),
    ({'foo': ['xxx', 'bar']}, {'foo': ['xxx', 'bar']}),
))
def test_unify_nested_patterns(mocker, data, expected):
    class DummyPattern(object):
        def __init__(self, pattern=None):
            self.pattern = pattern

        def __eq__(self, other):
            return self.pattern == other.pattern

        def __hash__(self):
            return hash(self.pattern)

    mocker.patch('logstapo.config._Pattern', DummyPattern)
    assert config._unify_nested_patterns(data) == {DummyPattern(k): [DummyPattern(p) for p in v]
                                                   for k, v in expected.items()}


@pytest.mark.parametrize('has_actions', (True, False))
def test_process_config(mocker, has_actions):
    class DummyPattern(object):
        def __init__(self, pattern=None):
            self.pattern = pattern

        def __eq__(self, other):
            return self.pattern == other.pattern

        def __hash__(self):
            return hash(self.pattern)

    warning_echo = mocker.patch('logstapo.config.warning_echo')
    mocker.patch('logstapo.config._Pattern', DummyPattern)
    action_from_config = mocker.patch('logstapo.actions.Action.from_config')
    data = {'regexps': {'__src': '(?P<source>.)', 'rex': '%(src)(?P<message>.)'},
            'logs': {'test': {'file': 'test.log',
                              'regex': 'rex',
                              'actions': 'spam' if has_actions else [],
                              'garbage': 'crap*',
                              'ignore': 'boring'}},
            'actions': {'spam': {'type': 'smtp', 'to': 'test@example.com'}} if has_actions else {}}
    rv = config.process_config(data)
    assert warning_echo.called == (not has_actions)
    # regexps
    assert rv['regexps'] == {'rex': re.compile('(?P<source>.)(?P<message>.)')}
    # logs
    assert rv['logs'] == {'test': {'files': ('test.log',),
                                   'regexps': ('rex',),
                                   'actions': ('spam',) if has_actions else (),
                                   'ignore': {DummyPattern(): [DummyPattern('boring')]},
                                   'garbage': [DummyPattern('crap*')]}}
    # actions
    if has_actions:
        assert rv['actions'].keys() == {'spam'}
        action_from_config.assert_called_once_with('smtp', {'to': 'test@example.com'})
    else:
        assert not rv['actions']
        assert not action_from_config.called


def test_process_config_invalid():
    with pytest.raises(config.ConfigError):
        config.process_config({})
    data = {'regexps': {'test': '(?P<source>.)(?P<message>.)'},
            'logs': {'test': {}}}
    with pytest.raises(config.ConfigError):
        config.process_config(data)
