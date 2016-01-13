import pytest


@pytest.fixture
def mock_config(mocker):
    def _mock_config(config):
        mocker.patch('logstapo.config._ConfigDict.data', config)
    return _mock_config
