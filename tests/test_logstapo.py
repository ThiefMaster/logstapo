import os

import py
from click.testing import CliRunner

from logstapo.cli import main


TEST_MAIL_BODY = '''
Logstapo results for 'syslog'
=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

Unusual lines
-------------
Dec 28 01:30:12 hydra login[3728]: pam_unix(login:session): session opened for user root by LOGIN(uid=0)
Dec 28 01:30:12 hydra login[3766]: ROOT LOGIN  on '/dev/tty1'
Jan  9 23:57:31 hydra root[21527]: test
Dec 28 01:29:46 hydra sshd[3702]: Server listening on 0.0.0.0 port 22.
Dec 28 01:29:46 hydra sshd[3702]: Server listening on :: port 22.
Dec 28 01:57:53 hydra sshd[3795]: Accepted publickey for root from fe80::123 port 45459 ssh2: RSA SHA256:whatever
Dec 28 02:49:00 hydra su[9915]: Successful su for root by root
Dec 28 02:49:00 hydra su[9915]: + /dev/pts/3 root:root
Dec 28 02:49:00 hydra su[9915]: pam_unix(su:session): session opened for user root by (uid=0)
Jan 10 01:48:26 hydra test: meow!
Dec 28 02:19:53 hydra useradd[18048]: new user: name=ntp, UID=123, GID=123, home=/dev/null, shell=/sbin/nologin
'''.strip()


def test_logstapo(tmpdir, smtpserver):
    testdir = py.path.local(os.path.dirname(__file__))
    logdir = tmpdir.join('logs')
    logdir.mkdir()
    for file in testdir.join('logs').visit():
        file.copy(logdir)
    config = tmpdir.join('logstapo.yml')
    config_yaml = (testdir.join('logstapo_test.yml').read_text('ascii')
                   .replace('$LOGDIR', logdir.strpath)
                   .replace('$SMTP_HOST', smtpserver.addr[0])
                   .replace('$SMTP_PORT', str(smtpserver.addr[1])))
    config.write(config_yaml)
    runner = CliRunner()
    rv = runner.invoke(main, ['-c', config.strpath], catch_exceptions=False)
    assert not rv.output
    assert rv.exit_code == 0
    assert len(smtpserver.outbox) == 1
    mail = smtpserver.outbox[0]
    assert mail['Subject'] == 'Found unusual log entries'
    assert mail['From'] == 'root@example.com'
    assert mail['To'] == 'admins@example.com, root@example.com'
    assert mail.get_payload() == TEST_MAIL_BODY
