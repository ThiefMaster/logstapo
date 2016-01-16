import textwrap
from unittest.mock import MagicMock

import pytest

from logstapo.actions import run_actions, Action, SMTPAction
from logstapo.config import ConfigError


def test_run_actions(mock_config):
    logs_config = {
        'both': {'actions': ['a']},
        'one1': {'actions': ['a', 'b']},
        'one2': {'actions': ['b']},
        'none': {'actions': ['c']},
        'nact': {'actions': []},
    }
    actions = {
        'a': MagicMock(spec=Action),
        'b': MagicMock(spec=Action),
        'c': MagicMock(spec=Action)
    }
    mock_config({'logs': logs_config, 'actions': actions})
    res = {
        'both': (['x', 'y'], ['z']),
        'one1': (['x', 'y'], []),
        'one2': ([], ['z']),
        'none': ([], []),
        'nact': (['x', 'y'], ['z']),
    }
    run_actions(res)
    actions['a'].run.assert_called_once_with({'both': res['both'],
                                              'one1': res['one1']})
    actions['b'].run.assert_called_once_with({'one1': res['one1'],
                                              'one2': res['one2']})
    assert not actions['c'].run.called


def test_action_from_config(mocker):
    actions = mocker.patch('logstapo.actions.ACTIONS', {'smtp': MagicMock(spec=Action)})
    Action.from_config('smtp', {'foo': 'bar'})
    actions['smtp'].assert_called_once_with({'foo': 'bar'})
    with pytest.raises(ConfigError):
        Action.from_config('test', {})


def test_smtpaction_invalid():
    with pytest.raises(ConfigError):
        SMTPAction({})
    with pytest.raises(ConfigError):
        SMTPAction({'to': 'foo@bar.com', 'ssl': True, 'starttls': True})
    with pytest.raises(ConfigError):
        SMTPAction({'to': 'foo@bar.com', 'username': 'test'})
    with pytest.raises(ConfigError):
        SMTPAction({'to': 'foo@bar.com', 'password': 'test'})


@pytest.mark.parametrize(('recipients', 'expected'), (
    ('foo@bar.com', {'foo@bar.com'}),
    (['foo@bar.com'], {'foo@bar.com'}),
    (['test@example.com', 'foo@bar.com'], {'foo@bar.com', 'test@example.com'})
))
def test_smtpaction_recipients(recipients, expected):
    action = SMTPAction({'to': recipients})
    assert action.recipients == sorted(expected)


@pytest.mark.parametrize(('from_', 'expected'), (
    (None, 'USER@DOMAIN'),
    ('foo', 'foo'),
))
def test_smtpaction_sender(mocker, from_, expected):
    mocker.patch('getpass.getuser', lambda: 'USER')
    mocker.patch('socket.getfqdn', lambda: 'DOMAIN')
    action = SMTPAction({'to': 'foo@bar.com', 'from': from_})
    assert action.sender == expected


@pytest.mark.parametrize('dry_run', (True, False))
@pytest.mark.parametrize('auth', (True, False))
@pytest.mark.parametrize(('ssl', 'starttls'), (
    (False, False),
    (False, True),
    (True, False),
))
def test_smtpaction_run(mocker, mock_config, dry_run, auth, ssl, starttls):
    mock_config({'debug': False, 'dry_run': dry_run})
    mocker.patch('logstapo.actions.debug_echo')
    mocker.patch('logstapo.actions.SMTPAction._build_msg', return_value='...')
    smtplib = mocker.patch('logstapo.actions.smtplib', autospec=True)
    # XXX: why doesn't autospec handle this?
    smtplib.SMTP.__name__ = 'SMTP'
    smtplib.SMTP_SSL.__name__ = 'SMTP_SSL'
    data = {'host': 'somehost', 'port': 12345, 'ssl': ssl, 'starttls': starttls,
            'from': 'sender@bar.com', 'to': 'foo@bar.com', 'subject': 'log stuff'}
    if auth:
        data.update({'username': 'user', 'password': 'pass'})
    action = SMTPAction(data)
    action.run({})
    cls = smtplib.SMTP_SSL if ssl else smtplib.SMTP
    if dry_run:
        assert not cls.called
    else:
        cls.assert_called_once_with('somehost', 12345)
        smtp = cls()
        assert smtp.starttls.called == starttls
        if auth:
            smtp.login.assert_called_once_with('user', 'pass')
        assert smtp.send_message.called
        msg = smtp.send_message.call_args[0][0]
        assert msg['To'] == 'foo@bar.com'
        assert msg['From'] == 'sender@bar.com'
        assert msg['Subject'] == 'log stuff'
        assert msg.get_payload() == '...'


@pytest.mark.parametrize('group_by_source', (True, False))
def test_smtpaction_build_msg(group_by_source):
    action = SMTPAction({'to': 'foo@bar.com', 'group': group_by_source})
    data = {
        'a': ([('a1', {'source': 'sa1'}),
               ('a2', {'source': 'sa2'}),
               ('a3', {'source': 'sa1'})],
              ['uA']),
        'b': ([], ['uB']),
        'c': ([('c1', {'source': 'sc'})], []),
        'd': ([], [])
    }
    msg = action._build_msg(data)
    if group_by_source:
        assert msg == textwrap.dedent('''
            Logstapo results for 'a'
            =-=-=-=-=-=-=-=-=-=-=-=-

            Unparsable lines
            ~~~~~~~~~~~~~~~~
            uA

            Unusual lines
            -------------
            a1
            a3
            a2



            Logstapo results for 'b'
            =-=-=-=-=-=-=-=-=-=-=-=-

            Unparsable lines
            ~~~~~~~~~~~~~~~~
            uB



            Logstapo results for 'c'
            =-=-=-=-=-=-=-=-=-=-=-=-

            Unusual lines
            -------------
            c1
        ''').strip()
    else:
        assert msg == textwrap.dedent('''
            Logstapo results for 'a'
            =-=-=-=-=-=-=-=-=-=-=-=-

            Unparsable lines
            ~~~~~~~~~~~~~~~~
            uA

            Unusual lines
            -------------
            a1
            a2
            a3



            Logstapo results for 'b'
            =-=-=-=-=-=-=-=-=-=-=-=-

            Unparsable lines
            ~~~~~~~~~~~~~~~~
            uB



            Logstapo results for 'c'
            =-=-=-=-=-=-=-=-=-=-=-=-

            Unusual lines
            -------------
            c1
        ''').strip()
