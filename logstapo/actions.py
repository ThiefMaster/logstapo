import getpass
import smtplib
import socket
from collections import defaultdict
from email.mime.text import MIMEText

from logstapo.config import ConfigError, current_config
from logstapo.util import underlined, debug_echo, ensure_collection


def run_actions(results):
    """Run logstapo actions on the remaining log lines.

    :param results: Result dict as returned by `process_logs`
    """
    config = current_config.data
    results_for_actions = defaultdict(dict)
    for name, logresults in results.items():
        if not any(logresults):
            continue
        for action in config['logs'][name]['actions']:
            results_for_actions[action][name] = logresults
    for action, data in results_for_actions.items():
        config['actions'][action].run(data)


class Action(object):
    def __init__(self, data):  # pragma: no cover
        raise NotImplementedError

    def __repr__(self):
        return '<{}()>'.format(type(self).__name__)

    def run(self, data):  # pragma: no cover
        """Performs whatever the action is supposed to do.

        This method MUST honor ``current_config['dry_run']`` and not
        actually perform modifications, send emails, etc. in case it
        is True.

        :param data: A dict mapping log names to the data returned by
                     `process_log`.
        """
        raise NotImplementedError

    @staticmethod
    def from_config(type_, data):
        """Creates a new Action instance from config data.

        :param type_: The type of the action.  Used to lookup the
                      implementation
        :param data: The action-specific config data.
        """
        try:
            action = ACTIONS[type_]
        except KeyError:
            raise ConfigError('type does not exist: ' + type_)
        return action(data)


class SMTPAction(Action):
    def __init__(self, data):
        self.host = data.get('host', 'localhost')
        self.port = data.get('port', 0)
        self.ssl = data.get('ssl', False)
        self.starttls = data.get('starttls', False)
        self.username = data.get('username')
        self.password = data.get('password')
        self.sender = data.get('from') or self._get_sender()
        try:
            self.recipients = sorted(ensure_collection(data['to'], set))
        except KeyError:
            raise ConfigError('email recipient (to) missing')
        self.subject = data.get('subject', 'unusual system events')
        self.group_by_source = data.get('group', False)
        if self.ssl and self.starttls:
            raise ConfigError('ssl and starttls are mutually exclusive')
        if bool(self.username) != bool(self.password):
            raise ConfigError('username and password must both be set or unset')

    def __repr__(self):
        return ('<SMTPAction(host={host!r}, port={port}, ssl={ssl}, starttls={starttls}, subject={subject!r})'
                .format(**self.__dict__))

    def _get_sender(self):
        return '{}@{}'.format(getpass.getuser(), socket.getfqdn())

    def _build_msg(self, data):
        msg = []
        for i, (logname, (lines, unparsable)) in enumerate(sorted(data.items())):
            if not lines and not unparsable:
                # This should never happen - run_action filters such entries
                continue
            if self.group_by_source:
                lines = sorted(lines, key=lambda x: x[1]['source'].lower())
            if i > 0:
                msg += [''] * 3
            msg += underlined("Logstapo results for '{}'".format(logname))
            msg.append('')
            if unparsable:
                msg += underlined('Unparsable lines', '~')
                msg += unparsable
            if unparsable and lines:
                msg.append('')
            if lines:
                msg += underlined('Unusual lines', '-')
                msg += [x[0] for x in lines]
        return '\n'.join(msg)

    def run(self, data):
        msg = MIMEText(self._build_msg(data))
        msg['Subject'] = self.subject
        msg['From'] = self.sender
        msg['To'] = ', '.join(self.recipients)

        cls = smtplib.SMTP_SSL if self.ssl else smtplib.SMTP
        debug_echo('using {} client'.format(cls.__name__))
        if current_config['dry_run']:
            debug_echo('not sending email due to dry-run')
            return
        smtp = cls(self.host, self.port)
        smtp.set_debuglevel(current_config['debug'])
        with smtp:
            smtp.ehlo()
            if self.starttls:
                debug_echo('issuing STARTTLS')
                smtp.starttls()
                smtp.ehlo()
            if self.username and self.password:
                debug_echo('logging in as ' + self.username)
                smtp.login(self.username, self.password)
            debug_echo('sending email')
            smtp.send_message(msg)


# TODO: use entry points instead of hardcoded list
ACTIONS = {'smtp': SMTPAction}
