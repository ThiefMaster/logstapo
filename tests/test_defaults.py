from logstapo import defaults


def test_defaults():
    # in case you wonder why there's a test for this:
    # changing the default config file path would break invocations
    # where the config file path is not specified so it should be
    # considered immutable
    assert defaults.CONFIG_FILE_PATH == '/etc/logstapo.yml'
