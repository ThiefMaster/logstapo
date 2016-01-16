import math
import re

import click


def try_match(regexps, string):
    """Try to match a string with multiple regexps.

    :param regexps: A list of compiled regexps or a single regex
    :param string: The string to match
    :return: A regex match object or ``None``
    """
    try:
        iter(regexps)
    except TypeError:
        regexps = [regexps]
    for regex in regexps:
        match = regex.match(string)
        if match is not None:
            return match
    return None


def debug_echo(message):
    """Display a debug message on stderr.

    The message is only displayed if debug output is enabled.

    :param message: The message to display
    """
    from logstapo.config import current_config
    if current_config['debug']:
        click.secho('[D] ' + message, fg='black', bold=True)


def verbose_echo(level, message):
    """Display a verbose message on stderr.

    The message is only displayed if verbose output is enabled and the
    verbosity level is equal or higher to the specified one.

    :param level: The minimum verbosity level that is required
    :param message: The message to display
    """
    from logstapo.config import current_config
    config = current_config.data
    if config['debug'] or config['verbosity'] >= level:
        color = 'magenta' if level > 1 else 'blue'
        click.secho('[{}] {}'.format(level, message), fg=color, bold=True)


def warning_echo(message):
    """Display a warning message

    :param message: The message to display
    """
    click.secho('[W] ' + message, err=True, fg='yellow')


def error_echo(message):
    """Display a error message

    :param message: The message to display
    """
    click.secho('[E] ' + message, err=True, fg='red', bold=True)


def underlined(text, chars='=-'):
    """Underlines a text with extra chars

    :param text: The text to underline
    :param chars: The chars used for underlining.  They will be
                  repeated as often as necessary to fit the length of
                  the text.
    :return: a list containing `text` and the underline
    """
    underline = chars * math.ceil(len(text) / len(chars))
    return [text, underline[:len(text)]]


def ensure_collection(value, collection_type):
    """Ensures that `value` is a `collection_type` collection.

    :param value: A string or a collection
    :param collection_type: A collection type, e.g. `set` or `list`
    :return: a `collection_type` object containing the value
    """
    return collection_type((value,)) if value and isinstance(value, str) else collection_type(value)


def combine_placeholders(string, placeholders, _placeholder_re=re.compile(r'%\(([^)]+)\)')):
    """Replace ``%(blah)`` placeholders in a string.

    Each placeholder may contain other placeholders.

    :param string: A string that may contain placeholders
    :param placeholders: A dict containing placeholders and their
                         values.
    """
    def _repl(m):
        return placeholders[m.group(1)]

    # ensure we don't have cycles that would cause an infinite loop
    # resulting in massive memory use
    for name, value in placeholders.items():
        referenced = set()
        while True:
            matches = set(_placeholder_re.findall(value))
            if not matches:
                break
            elif matches & referenced:
                raise ValueError('placeholder leads to a cycle: ' + name)
            referenced |= matches
            value = _placeholder_re.sub(_repl, value)

    # perform the actual replacements
    while True:
        string, n = _placeholder_re.subn(_repl, string)
        if not n:
            break
    return string
