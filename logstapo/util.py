import click
import math


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
        click.secho('[D] ' + message, err=True, fg='black', bold=True)


def verbose_echo(level, message, *, err=True):
    """Display a verbose message on stderr.

    The message is only displayed if verbose output is enabled and the
    verbosity level is equal or higher to the specified one.

    :param level: The minimum verbosity level that is required
    :param message: The message to display
    :param err: Whether the message should be written to stderr
                instead of stdout.
    """
    from logstapo.config import current_config
    config = current_config.data
    if config['debug'] or config['verbosity'] >= level:
        color = 'magenta' if level > 1 else 'blue'
        click.secho('[{}] {}'.format(level, message), err=err, fg=color, bold=True)


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
