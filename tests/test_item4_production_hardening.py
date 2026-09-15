from pathlib import Path


def test_sml_worker_has_failure_boundary_and_shutdown():
    text = Path('sml/worker.py').read_text()
    assert 'SIGTERM' in text and 'SIGINT' in text
    assert 'backoff' in text and 'except Exception' in text


def test_replay_cli_is_read_only_and_uses_loop_replay():
    text = Path('scripts/replay_investigation.py').read_text()
    assert 'mode=ro' in text
    assert 'LoopReplay' in text
    assert 'LoopVerifier' in text


def test_release_container_runs_non_root_and_has_healthcheck():
    text = Path('Dockerfile').read_text()
    assert 'USER appuser' in text
    assert 'HEALTHCHECK' in text


def test_release_compose_persists_data_and_healthchecks_api():
    text = Path('docker-compose.release.yml').read_text()
    assert 'itxn_data:/app/data' in text
    assert 'healthcheck:' in text


def test_source_tree_not_directly_coupled_to_sml():
    for path in Path('src').rglob('*.py'):
        text=path.read_text(encoding='utf-8')
        assert 'import sml' not in text and 'from sml' not in text
