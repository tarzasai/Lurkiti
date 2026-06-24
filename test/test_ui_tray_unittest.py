import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from PyQt6.QtWidgets import QApplication


class TestUITray(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    @patch('lurkiti.ui.trayicon.get_stream_icon')
    @patch('lurkiti.ui.trayicon.launch_process')
    def test_tray_toggle_and_launch(self, mock_launch, mock_fav):
        tmp = tempfile.NamedTemporaryFile('w+', delete=False)
        tmp.write(json.dumps({'streams': {}, 'check_interval_mins': 60, 'autostart_monitoring': False, 'windows': {'settings_window': {'x':100,'y':100,'width':700,'height':600}}}))
        tmp.flush(); tmp.close()
        from lurkiti.model import Configuration
        cfg = Configuration(Path(tmp.name))
        from lurkiti.ui.trayicon import TrayIcon
        ti = TrayIcon(None, str(cfg.config_path))
        # toggle notifications
        orig = ti.notify
        ti._toggle_notifications()
        self.assertNotEqual(ti.notify, orig)
        # simulate launch
        s = MagicMock()
        s.url = 'https://x'
        # ensure string attributes so build_launch_command can do replacements
        s.name = 'mock'
        s.type = ''
        s.quality = 'best'
        s.player = ''
        s.sl_args = ''
        s.mp_args = ''
        ti._launch_stream(s)
        mock_launch.assert_called()
        # Clean up monitor thread to avoid crashes on teardown
        ti.monitor.stop()
        ti.monitor.wait()
        ti.monitor.quit()
