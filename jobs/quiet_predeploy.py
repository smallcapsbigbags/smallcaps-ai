"""Preserve release checks and their exit codes without flooding provider logs.

Never print captured output (it can contain database or deployment information).
Only fixed stage names, return codes and safe exception types leave this wrapper.
"""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import time

ALLOWED = {'jobs.validate_runtime', 'jobs.prepare_rnsrepo_public',
           'jobs.audit_production', 'jobs.release_acceptance',
           'jobs.monitoring_acceptance', 'jobs.company_acceptance',
           'jobs.daily_editor_acceptance', 'jobs.newsroom_acceptance',
           'jobs.radar_acceptance'}


def run(module: str, args: list[str]) -> int:
    if module not in ALLOWED:
        raise ValueError('Not a release-check module')
    started = time.monotonic()
    record = {'stage': module, 'status': 'starting'}
    print('rnsrepo_predeploy ' + json.dumps(record), flush=True)
    with tempfile.TemporaryFile() as output:
        try:
            completed = subprocess.run([sys.executable, '-m', module, *args],
                stdout=output, stderr=subprocess.STDOUT, timeout=120, check=False)
            rc = completed.returncode
            record.update(status='passed' if rc == 0 else 'failed', returncode=rc)
        except subprocess.TimeoutExpired:
            rc = 124
            record.update(status='failed', error_type='TimeoutExpired', returncode=rc)
    record['elapsed_seconds'] = round(time.monotonic()-started, 3)
    print('rnsrepo_predeploy ' + json.dumps(record), flush=True)
    return rc


if __name__ == '__main__':
    raise SystemExit(run(sys.argv[1], sys.argv[2:]))
