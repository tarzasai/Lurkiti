import os
import sys
from pathlib import Path

# Ensure `src/` is on sys.path so tests can import project modules
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Configure Qt for headless test runs and quieter logs
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_LOGGING_RULES', 'qt.qpa.*=false')
# Prefer PyQt6 for pytest-qt to match project imports
os.environ.setdefault('PYTEST_QT_API', 'pyqt6')


import pytest
from test.test_helpers import mock_sls as _mock_sls_ctx, mock_is_stream_live as _mock_is_stream_live_ctx

from PyQt6.QtCore import QObject, pyqtSignal


class FakeNotifier(QObject):
    """Hermetic stand-in for lurkiti.notifier.Notifier (no DBus in tests)."""
    launch_requested = pyqtSignal(object)

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.calls = []
        self.return_value = True

    @property
    def available(self) -> bool:
        return True

    def notify_stream_online(self, header, body, stream, icon_path, persistent=False) -> bool:
        self.calls.append((header, body, stream, icon_path, persistent))
        return self.return_value

    def shutdown(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _fake_notifier(monkeypatch):
    """Replace the desktop-notifier backend with a fake in every test."""
    monkeypatch.setattr('lurkiti.ui.trayicon.Notifier', FakeNotifier, raising=False)
    yield



@pytest.fixture
def mock_sls():
    """Pytest fixture that yields a function returning a context manager for mocking sls.

    Usage:
        def test_x(mock_sls):
            with mock_sls(streams_return=['s']):
                 ...
    """
    def _factory(streams_return=None, resolve_return=None, resolve_side_effect=None):
        return _mock_sls_ctx(streams_return=streams_return, resolve_return=resolve_return, resolve_side_effect=resolve_side_effect)
    return _factory


@pytest.fixture
def mock_is_stream_live():
    """Fixture that yields a factory for a context manager to mock is_stream_live in monitor and ui.trayicon."""
    def _factory(return_value=None, side_effect=None):
        return _mock_is_stream_live_ctx(return_value=return_value, side_effect=side_effect)
    return _factory
