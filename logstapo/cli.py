import click

from logstapo import __version__
from logstapo.core import run
from logstapo.defaults import CONFIG_FILE_PATH
from logstapo.config import ConfigError, parse_config, process_config
from logstapo.util import error_echo


def _config_callback(ctx, param, value):
    try:
        data = parse_config(value)
        config = process_config(data)
    except ConfigError as exc:
        error_echo('Could not load config file')
        error_echo(str(exc))
        ctx.exit(1)
    else:
        config['verbosity'] = ctx.params['verbose']
        config['debug'] = ctx.params['debug']
        config['dry_run'] = ctx.params['dry_run']
        return config


@click.command(context_settings={'help_option_names': ('-h', '--help')})
@click.option('-c', '--config', type=click.File(), callback=_config_callback, default=CONFIG_FILE_PATH,
              help="The path to the application's config file")
@click.option('-n', '--dry-run', is_flag=True, is_eager=True,
              help="Perform a dry run (not modifying any offset files or executing actions)")
@click.option('-v', '--verbose', count=True, is_eager=True, type=click.IntRange(min=0, max=2),
              help="Enable more verbose output; can be specified up to 2 times.")
@click.option('-d', '--debug', is_flag=True, is_eager=True,
              help="Enable debug output (very spammy); implies -vv")
@click.version_option(__version__, '-V', '--version')
def main(**kwargs):
    """
    Logstapo is a tool that checks new entries in log files and
    performs actions based on them.
    """
    # kwargs is not used as the config is taken from the click context
    # to avoid passing it around all the time
    run()


if __name__ == '__main__':
    main()
