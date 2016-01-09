from logstapo.actions import run_actions
from logstapo.logs import process_logs


def run():
    """Run logstapo on all configured logs and perform actions"""
    results = process_logs()
    run_actions(results)
