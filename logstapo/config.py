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
            return not self.negate
        found = self.regex.match(string) is not None
        return found ^ self.negate

    def __repr__(self):
        if self.always_match:
            return '<Pattern (always-matching)>'
        elif self.negate:
            return '<Pattern !{!r}>'.format(self.regex.pattern)
        else:
            return '<Pattern {!r}>'.format(self.regex.pattern)


def parse_config(file):
    """Parse the application YAML config file.

    :return: The parsed YAML document
    :raise ConfigError: If the YAML parser cannot parse the file.
    """
    try:
        return yaml.safe_load(file)
    except yaml.YAMLError as exc:
        raise ConfigError('yaml parse error: {}'.format(exc))


def _process_regexps(data):
    placeholders = {name[2:]: regex for name, regex in data.items() if name.startswith('__')}
    regexps = {}
    for name, regex in data.items():
        if name.startswith('__'):
            continue
        try:
            regex = combine_placeholders(regex, placeholders)
        except KeyError as exc:
            raise ConfigError('placeholder does not exist: {}'.format(exc)) from exc
        try:
            compiled = re.compile(regex)
        except re.error as exc:
            raise ConfigError('regex could not be compiled: {} ({})\n{}'.format(name, exc, regex))
        if set(compiled.groupindex) < {'source', 'message'}:
            raise ConfigError("regex must contain named groups 'source' and 'message': {}".format(name))
        regexps[name] = compiled
    return regexps


def _process_actions(data):
    from logstapo.actions import Action
    auto_actions = set()
    actions = {}
    for name, actiondata in data.items():
        actiondata = dict(actiondata)
        try:
            type_ = actiondata.pop('type')
        except KeyError:
            raise ConfigError('invalid action definition ({}): no type specified'.format(name))
        if actiondata.pop('auto', True):
            auto_actions.add(name)
        try:
            actions[name] = Action.from_config(type_, actiondata)
        except ConfigError as exc:
            raise ConfigError('invalid action definition ({}): {}'.format(name, exc)) from exc
    return actions, auto_actions


def _process_log_files(logdata):
    files = set(itertools.chain.from_iterable(ensure_collection(logdata.get(key, ''), set)
                                              for key in ('file', 'files')))
    if not files:
        raise ConfigError('no files specified')
    return files


def _process_log_regexps(logdata, name, available):
    regexps = ensure_collection(logdata.get('regex', name), tuple)
    invalid = next((x for x in regexps if x not in available), None)
    if invalid is not None:
        raise ConfigError('invalid regex specified: {}'.format(invalid))
    return regexps


def _process_log_actions(logdata, name, auto_actions, available):
    if not any(x in logdata for x in ('action', 'actions')):
        return auto_actions
    actions = set(itertools.chain.from_iterable(ensure_collection(logdata.get(key, ''), set)
                                                for key in ('action', 'actions')))
    invalid = next((x for x in actions if x not in available), None)
    if invalid is not None:
        raise ConfigError('invalid action specified: {}'.format(invalid))
    return actions


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


def _process_logs(data, config_regexps, config_actions, auto_actions):
    logs = {}
    for name, logdata in data.items():
        try:
            # files
            files = _process_log_files(logdata)
            # regexps
            regexps = _process_log_regexps(logdata, name, config_regexps)
            # patterns
            garbage = _unify_patterns(logdata.get('garbage'))
            ignore = _unify_nested_patterns(logdata.get('ignore'))
            # actions
            actions = _process_log_actions(logdata, name, auto_actions, config_actions)
        except ConfigError as exc:
            raise ConfigError('invalid log definition ({}): {}'.format(name, exc)) from exc
        if not actions:
            warning_echo('useless log definition ({}): no actions defined'.format(name))
        logs[name] = {'files': tuple(sorted(files)),
                      'regexps': regexps,
                      'garbage': garbage,
                      'ignore': ignore,
                      'actions': tuple(sorted(actions))}
    return logs


def process_config(data):
    """Parse the application config file.

    This raises an exception if the config file cannot be parsed or
    does not contain all required entries.

    :param data: The dict containing the configuration
    :return: A canonicalized version of the dict containing exactly
             the data needed by logstapo.
    """
    config = deepcopy(INITIAL_CONFIG)
    try:
        regexps = data['regexps']
        logs = data['logs']
        actions = data.get('actions') or {}
    except KeyError as exc:
        raise ConfigError('required section missing: {}'.format(exc))
    config['regexps'] = _process_regexps(regexps)
    config['actions'], auto_actions = _process_actions(actions)
    config['logs'] = _process_logs(logs, config['regexps'], config['actions'], auto_actions)
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
