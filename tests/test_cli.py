import pytest
from click.testing import CliRunner
from logstapo.config import current_config

from logstapo.cli import main


@pytest.mark.parametrize('dry_run', (True, False))
@pytest.mark.parametrize('debug', (True, False))
@pytest.mark.parametrize('verbosity', (0, 1, 2))
def test_cli(tmpdir, mocker, dry_run, debug, verbosity):
    def _run(**kwargs):
        assert current_config['foo'] == 'bar'
        assert current_config['dry_run'] == dry_run
        assert current_config['verbosity'] == verbosity
        assert current_config['debug'] == debug

    error_echo = mocker.patch('logstapo.cli.error_echo')
    process_config = mocker.patch('logstapo.cli.process_config', side_effect=dict)
    run = mocker.patch('logstapo.cli.run', side_effect=_run)
    config = tmpdir.join('test.yml')
    config.write('foo: bar\n')
    runner = CliRunner()
    args = ['-c', config.strpath]
    if verbosity:
        args.append('-' + 'v' * verbosity)
    if debug:
        args.append('-d')
    if dry_run:
        args.append('-n')
    rv = runner.invoke(main, args, catch_exceptions=False)
    process_config.assert_called_once_with({'foo': 'bar'})
    assert run.called
    assert not rv.output
    assert rv.exit_code == 0
    assert not error_echo.called


def test_cli_invalid_config(mocker):
    error_echo = mocker.patch('logstapo.cli.error_echo')
    runner = CliRunner()
    rv = runner.invoke(main, ['-c', '/dev/null'], catch_exceptions=False)
    assert rv.exit_code == 1
    assert error_echo.called
