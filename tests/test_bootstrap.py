import sys

from player import bootstrap


def test_windowed_streams_exist_before_application_import(monkeypatch, tmp_path):
    path = tmp_path / 'startup.log'
    monkeypatch.setenv('AIPLAYER_STARTUP_LOG', str(path))
    monkeypatch.setenv('AIPLAYER_STARTUP_CHECK', '1')
    monkeypatch.setattr(sys, 'stdout', None)
    monkeypatch.setattr(sys, 'stderr', None)
    def start():
        print('windowed dependency can write diagnostics', file=sys.stderr)
        return 0
    assert bootstrap.run(start) == 0
    assert sys.stdout is None and sys.stderr is None
    assert 'windowed dependency' in path.read_text()
    assert 'EXIT 0' in path.read_text()


def test_startup_failure_is_recorded_and_reported(monkeypatch, tmp_path):
    path = tmp_path / 'startup.log'
    monkeypatch.setenv('AIPLAYER_STARTUP_LOG', str(path))
    messages = []
    monkeypatch.setattr(bootstrap, 'show_startup_error', lambda error, log: messages.append((str(error), log)))
    def fail():
        raise ImportError('missing native dependency')
    assert bootstrap.run(fail) == 1
    assert 'ImportError: missing native dependency' in path.read_text()
    assert messages == [('missing native dependency', path)]
