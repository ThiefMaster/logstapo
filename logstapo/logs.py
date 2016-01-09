import itertools

from logstapo.config import current_config
from logstapo.logtail import logtail
from logstapo.util import try_match, debug_echo, verbose_echo, warning_echo


def process_logs(names=None):
    """Let logstapo loose on logs.

    :param names: A list of log names to process.  If omitted all
                  configured logs are processed
    :return: A dict of `process_log` results
    """
    if names is None:
        names = sorted(current_config['logs'])
    return {name: process_log(name) for name in names}


def process_log(name):
    """Let logstapo loose on a specifig log.

    :param name: The name of the log to process
    :return: A ``(lines, failed)`` tuple. `lines` is a list of
            ``(line, data)`` tuples and `failed` is a list of raw
            lines that could not be parsed.
    """
    config = current_config.data  # avoid context lookup all the time
    verbosity = config['verbosity']
    data = config['logs'][name]
    garbage = data['garbage']
    ignore = data['ignore']
    regexps = [config['regexps'][regex_name] for regex_name in config['logs'][name]['regexps']]
    if verbosity >= 1:
        verbose_echo(1, "*** Processing log '{}' ({})".format(name, ', '.join(data['files'])), err=False)
        if garbage:
            verbose_echo(1, '  Garbage patterns:')
            for pattern in garbage:
                verbose_echo(1, '    - {}'.format(pattern.pattern))
        if ignore:
            verbose_echo(1, '  Ignore patterns:')
            for source, patterns in ignore.items():
                if source.pattern is None:
                    verbose_echo(1, '    - Any source'.format(source.pattern))
                else:
                    verbose_echo(1, '    - Source: {}'.format(source.pattern))
                for pattern in patterns:
                    verbose_echo(1, '      - {}'.format(pattern.pattern))
    lines = itertools.chain.from_iterable(_iter_log_lines(f, config['dry_run']) for f in data['files'])
    invalid = []
    other = []
    garbage_count = 0
    ignored_count = 0
    for line in lines:
        if garbage and any(x.test(line) for x in garbage):
            garbage_count += 1
            debug_echo('garbage: ' + line)
            continue
        parsed = _parse_line(line, regexps)
        if parsed is None:
            warning_echo('[{}] Could not parse: {}'.format(name, line))
            invalid.append(line)
            continue
        if _check_ignored(parsed, ignore):
            ignored_count += 1
            debug_echo('ignored: ' + line)
            continue
        verbose_echo(2, line)
        other.append((line, parsed))
    verbose_echo(1, 'Stats: {} garbage / {} invalid / {} ignored / {} other'.format(garbage_count, len(invalid),
                                                                                    ignored_count, len(other)))
    return other, invalid


def _parse_line(line, regexps):
    match = try_match(regexps, line)
    return match.groupdict() if match is not None else None


def _check_ignored(parsed, ignore):
    for source_pattern, patterns in ignore.items():
        if not source_pattern.test(parsed['source']):
            continue
        if any(x.test(parsed['message']) for x in patterns):
            return True
    return False


def _iter_log_lines(file, dry_run):
    yield from logtail(file, dry_run=dry_run)
