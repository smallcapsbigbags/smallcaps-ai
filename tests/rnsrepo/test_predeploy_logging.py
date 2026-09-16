from unittest.mock import patch
import subprocess
from jobs.quiet_predeploy import run
import pytest


def test_failure_is_not_hidden_or_log_output_exposed(capsys):
    with patch('jobs.quiet_predeploy.subprocess.run', return_value=subprocess.CompletedProcess([], 7)):
        assert run('jobs.radar_acceptance', []) == 7
    log = capsys.readouterr().out
    assert 'failed' in log and '7' in log


def test_timeout_fails_and_unknown_modules_rejected():
    with patch('jobs.quiet_predeploy.subprocess.run', side_effect=subprocess.TimeoutExpired([], 120)):
        assert run('jobs.radar_acceptance', []) == 124
    with pytest.raises(ValueError): run('evil', [])


def test_pinned_corpus_is_offline_and_rejects_corruption(tmp_path):
    from pathlib import Path
    from jobs.rnsrepo_corpus import load_corpus, ROOT
    import gzip, json
    with patch('requests.Session.get', side_effect=AssertionError('No live-source requests in release tests')):
        corpus = load_corpus()
    assert len(corpus) == 10 and len(dict(corpus)['spr-results']) > 70000
    data = dict(corpus);data['spr-results'] = data['spr-results'].replace('243.7', '343.7')
    with gzip.open(tmp_path / 'corpus.json.gz', 'wt', encoding='utf-8') as f: json.dump(data, f)
    with pytest.raises(ValueError, match='Evaluation source changed'): load_corpus(tmp_path)
