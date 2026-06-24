import unittest
import json
from pathlib import Path
from PyQt6.QtCore import QStandardPaths
from lurkiti.model import Configuration, Stream, StreamState, TrayIconAction

class TestConfigurationMore(unittest.TestCase):
    def test_stream_state_model_dump_excludes_is_online(self):
        state = StreamState(is_online=True, last_online_ts=123.0, last_watched_ts=456.0)
        dumped = state.model_dump(mode='json', exclude_none=True)
        self.assertNotIn('is_online', dumped)
        self.assertEqual(dumped['last_online_ts'], 123.0)
        self.assertEqual(dumped['last_watched_ts'], 456.0)

    def test_setters_and_persistence(self):
        # Create a minimal config file
        cfg_data = Configuration.__annotations__ if False else {
            'autostart_monitoring': False,
            'check_interval_mins': 60,
            'default_notify': False,
            'default_streamlink_args': '',
            'default_quality': 'best',
            'default_player': '',
            'default_player_args': '',
            'tray_icon_action': TrayIconAction.NOTHING.value,
            'streams': {}
        }
        tmp = Path('test_tmp_cfg.json')
        tmp.write_text(json.dumps(cfg_data))
        try:
            cfg = Configuration(tmp)
            cfg.autostart_monitoring = True
            cfg.default_notify = True
            cfg.default_streamlink_args = '--flag'
            cfg.default_quality = '720p'
            cfg.default_player = 'vlc'
            cfg.default_player_args = '--no-border'
            cfg.clippiti_path = '/usr/local/bin/clippiti'
            cfg.tray_icon_action = TrayIconAction.OPEN_URL
            cfg.check_interval_mins = 123
            # verify properties
            self.assertTrue(cfg.autostart_monitoring)
            self.assertTrue(cfg.default_notify)
            self.assertEqual(cfg.default_streamlink_args, '--flag')
            self.assertEqual(cfg.default_quality, '720p')
            self.assertEqual(cfg.default_player, 'vlc')
            self.assertEqual(cfg.default_player_args, '--no-border')
            self.assertEqual(cfg.clippiti_path, '/usr/local/bin/clippiti')
            self.assertEqual(cfg.tray_icon_action, TrayIconAction.OPEN_URL)
            self.assertEqual(cfg.check_interval_mins, 123)
            # stream operations
            s = Stream(url='https://x/', name='X', type='t')
            cfg.set_stream(s)
            self.assertIn('https://x/', cfg.streams)
            got = cfg.get_stream('https://x/')
            self.assertIsNotNone(got)
            self.assertEqual(got.name, 'X')
            cfg.del_stream(s)
            self.assertNotIn('https://x/', cfg.streams)
        finally:
            try:
                tmp.unlink()
            except Exception:
                pass

    def test_empty_string_to_none_validator(self):
        s = Stream(url='u', name='', type='t')
        # name should be converted to None by validator
        self.assertIsNone(s.name)

    def test_stream_state_tracking(self):
        cfg_data = {
            'autostart_monitoring': False,
            'check_interval_mins': 60,
            'default_notify': False,
            'default_streamlink_args': '',
            'default_quality': 'best',
            'default_player': '',
            'default_player_args': '',
            'tray_icon_action': TrayIconAction.NOTHING.value,
            'streams': {}
        }
        cfg_path = Path('test_tmp_cfg_state.json')
        state_path = Path('test_tmp_state.json')
        cfg_path.write_text(json.dumps(cfg_data))
        try:
            cfg = Configuration(cfg_path)
            cfg.state_path = state_path
            cfg.load_state()
            cfg.mark_stream_online('https://x/')
            cfg.mark_stream_watched('https://x/')
            self.assertIsNotNone(cfg.get_stream_last_online_ts('https://x/'))
            self.assertIsNotNone(cfg.get_stream_last_watched_ts('https://x/'))
            self.assertTrue(state_path.exists())
            persisted = json.loads(state_path.read_text())
            self.assertNotIn('is_online', persisted['streams']['https://x/'])
        finally:
            try:
                cfg_path.unlink()
            except Exception:
                pass
            try:
                state_path.unlink()
            except Exception:
                pass

    def test_state_path_uses_generic_state_location_root(self):
        cfg_data = {
            'autostart_monitoring': False,
            'check_interval_mins': 60,
            'default_notify': False,
            'default_streamlink_args': '',
            'default_quality': 'best',
            'default_player': '',
            'default_player_args': '',
            'tray_icon_action': TrayIconAction.NOTHING.value,
            'streams': {}
        }
        cfg_path = Path('test_tmp_cfg_state_location.json')
        cfg_path.write_text(json.dumps(cfg_data))
        try:
            cfg = Configuration(cfg_path)
            expected_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericStateLocation))
            if str(expected_dir) == '.':
                expected_dir = cfg_path.parent
            self.assertEqual(cfg.state_path.parent, expected_dir)
            self.assertEqual(cfg.state_path.name, 'Lurkiti.state.json')
        finally:
            try:
                cfg_path.unlink()
            except Exception:
                pass

if __name__ == '__main__':
    unittest.main()
