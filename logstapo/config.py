import itertools
import re
from collections import UserDict
from copy import deepcopy

import click
import yaml

from logstapo.util import warning_echo, ensure_collection, combine_placeholders


INITIAL_CONFIG = {'verbosity': 0,
                  'debug': False,
                  'dry_run': False,
                  'regexps': {},
                  'logs': {},
                  'actions': {}}


class ConfigError(Exception):
    pass


class _Pattern(object):
    def __init__(self, pattern=None):
        self.pattern = pattern
        self.negate = False
        self.regex = None
        self.always_match = pattern is None
        if not self.always_match:
            self._parse_pattern(pattern)

    def _parse_pattern(self, pattern):
        # negate
        if pattern[0] == '^':
            self.negate = True
            pattern = pattern[1:]
        # short-circuit always-matching patterns
        if pattern == '*':
            self.always_match = True
            return
        if pattern[0] == '/' and pattern[-1] == '/':
            # regex
            regex_pattern = pattern[1:-1]
        else:
            # glob
            regex_pattern = re.escape(pattern).replace(r'\?', '.').replace(r'\*', '.*')
        self.regex = re.compile('^{}$'.format(regex_pattern))

    def test(self, string):
        if self.always_match:
            return True
        found = self.regex.match(string) is not None
        return found ^ self.negate

    def __repr__(self):
        if self.always_match:
            return '<Pattern (always-matching)>'
        elif self.negate:
            return '<Pattern !{!r}>'.format(self.regex.pattern)
        else:
            return '<Pattern {!r}>'.format(self.regex.pattern)


def _unify_patterns(value):
    if not value:
        return []
    elif isinstance(value, str):
        return [_Pattern(value)]
    else:
        return list(map(_Pattern, value))


def _unify_nested_patterns(value):
    if not value:
        return {}
    elif isinstance(value, str):
        return {_Pattern(): [_Pattern(value)]}
    elif isinstance(value, dict):
        return {_Pattern(key): _unify_patterns(value) for key, value in value.items()}
    else:
        return {_Pattern(): _unify_patterns(value)}


def parse_config(file, *, verbosity=None, debug=None):
    """Parse the application config file.

    This raises an exception if the config file cannot be parsed or
    does not contain all required entries.

    :param file: A file-like object containing the YAML config
    :param verbosity: Verbosity override - if specified the config
                      value is ignored.
    :param debug: Debug override - if specified the config value is
                  ignored.
    """
    try:
        data = yaml.safe_load(file)
    except yaml.YAMLError as exc:
        raise ConfigError('yaml parse error: {}'.format(exc))
    config = deepcopy(INITIAL_CONFIG)
    # verbosity
    try:
        config['verbosity'] = int(data['verbosity'])
        assert 0 <= config['verbosity'] <= 2
    except KeyError:
        pass
    except (TypeError, ValueError, AssertionError):
        raise ConfigError('verbosity must be in range 0..2')
    if verbosity is not None:
        config['verbosity'] = verbosity
    # debug
    try:
        config['debug'] = bool(data['debug'])
    except KeyError:
        pass
    except (TypeError, ValueError):
        raise ConfigError('debug must be true/false')
    if debug is not None:
        config['debug'] = debug
    if config['debug']:
        config['verbosity'] = 2
    # regexps
    try:
        regexps = data['regexps']
    except KeyError:
        raise ConfigError('required section missing: regexps')
    else:
        placeholders = {name[2:]: regex for name, regex in regexps.items() if name.startswith('__')}
        for name, regex in regexps.items():
            if name.startswith('__'):
                continue
            try:
                regex = combine_placeholders(regex, placeholders)
            except KeyError as exc:
                raise ConfigError('placeholder does not exist: {}'.format(exc)) from exc
            try:
                config['regexps'][name] = re.compile(regex)
            except re.error as exc:
                raise ConfigError('regex could not be compiled: {} ({})\n{}'.format(name, exc, regex))
    # actions
    auto_actions = set()
    try:
        actions = data['actions'] or {}
    except KeyError:
        raise ConfigError('required section missing: actions')
    else:
        for name, actiondata in actions.items():
            actiondata = dict(actiondata)
            try:
                type_ = actiondata.pop('type')
            except KeyError:
                raise ConfigError('invalid action definition ({}): no type specified'.format(name))
            if actiondata.pop('auto', True):
                auto_actions.add(name)
            try:
                from logstapo.actions import Action
                config['actions'][name] = Action.from_config(type_, actiondata)
            except ConfigError as exc:
                raise ConfigError('invalid action definition ({}): {}'.format(name, exc)) from exc
    # logs
    try:
        logs = data['logs']
    except KeyError:
        raise ConfigError('required section missing: logs')
    else:
        for name, logdata in logs.items():
            # files
            files = set(itertools.chain.from_iterable(ensure_collection(logdata.get(key, ''), set)
                                                      for key in ('file', 'files')))
            if not files:
                raise ConfigError('invalid log definition ({}): no files specified'.format(name))
            # regexps
            regexps = ensure_collection(logdata.get('regex', name), tuple)
            if any(x not in config['regexps'] for x in regexps):
                regex = next(x for x in regexps if x not in config['regexps'])
                raise ConfigError('invalid log definition ({}): invalid regex specified: {}'.format(name, regex))
            # patterns
            garbage = _unify_patterns(logdata.get('garbage'))
            ignore = _unify_nested_patterns(logdata.get('ignore'))
            # actions
            if not any(x in logdata for x in ('action', 'actions')):
                actions = auto_actions
            else:
                actions = set(itertools.chain.from_iterable(ensure_collection(logdata.get(key, ''), set)
                                                            for key in ('action', 'actions')))
                if any(x not in config['actions'] for x in actions):
                    action = next(x for x in actions if x not in config['actions'])
                    raise ConfigError('invalid log definition ({}): invalid action specified: {}'.format(name, action))
            if not actions:
                warning_echo('useless log definition ({}): no actions defined'.format(name))
            config['logs'][name] = {'files': tuple(sorted(files)),
                                    'regexps': regexps,
                                    'garbage': garbage,
                                    'ignore': ignore,
                                    'actions': tuple(sorted(actions))}
    return config


class _ConfigDict(UserDict):
    # noinspection PyMissingConstructor
    def __init__(self):
        # do not call super __init__ as it would set self.data
        pass

    @property
    def data(self):
        return click.get_current_context().params['config']


current_config = _ConfigDict()
