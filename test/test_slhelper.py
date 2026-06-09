import unittest
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path
from streamcondor.model import Configuration, Stream
import streamcondor.slhelper as slhelper

class DummyCfg:
    def __init__(self):
        self.default_streamlink_args = '--flag'
        self.default_player = 'mpv'
        self.default_player_args = '--no-border'
        self.default_quality = 'best'

class TestSlHelper(unittest.TestCase):
    def test_build_sl_command_basic(self):
        cfg = DummyCfg()
        s = Stream(url='https://example.com/stream', name='N', type='twitch', quality='best', player=None, sl_args='--http-no-ssl-verify', mp_args='--no-osc')
        cmd = slhelper.build_sl_command(cfg, s)
        self.assertIsInstance(cmd, list)
        self.assertEqual(cmd[0], 'streamlink')
        self.assertIn('https://example.com/stream', cmd)

    def test_build_sl_command_player_args_are_raw_string(self):
        cfg = DummyCfg()
        s = Stream(
            url='https://example.com/stream',
            name='HannaDuval',
            type='livejasmin',
            quality='720p',
            player='mpv',
            sl_args='--http-no-ssl-verify',
            mp_args='--screenshot-template=$SC.name.%tY%tm%td%tH%tM%tS'
        )
        cmd = slhelper.build_sl_command(cfg, s)
        self.assertIn(
            '--player-args=--screenshot-template=HannaDuval.%tY%tm%td%tH%tM%tS',
            cmd
        )

    def test_build_sl_command_player_args_quotes_placeholder_with_spaces(self):
        cfg = DummyCfg()
        s = Stream(
            url='https://example.com/stream',
            name='2 strangers',
            type='livejasmin',
            quality='720p',
            player='mpv',
            sl_args='--http-no-ssl-verify',
            mp_args='--screenshot-template=$SC.name.%tY%tm%td%tH%tM%tS'
        )
        cmd = slhelper.build_sl_command(cfg, s)
        self.assertIn(
            "--player-args=--screenshot-template='2 strangers'.%tY%tm%td%tH%tM%tS",
            cmd
        )

    @patch('streamcondor.slhelper.subprocess.Popen')
    def test_launch_process_success(self, mock_popen):
        mock_popen.return_value = MagicMock()
        ok = slhelper.launch_process(['echo', 'hi'])
        self.assertTrue(ok)
        mock_popen.assert_called()

    @patch('streamcondor.slhelper.subprocess.Popen')
    def test_launch_process_keeps_list_tokens(self, mock_popen):
        mock_popen.return_value = MagicMock()
        ok = slhelper.launch_process(['streamlink', '--title', 'hello world'])
        self.assertTrue(ok)
        passed_tokens = mock_popen.call_args[0][0]
        self.assertIn('hello world', passed_tokens)

    @patch('streamcondor.slhelper.subprocess.Popen', side_effect=Exception('boom'))
    def test_launch_process_failure(self, mock_popen):
        ok = slhelper.launch_process('bad command')
        self.assertFalse(ok)


if __name__ == '__main__':
    unittest.main()
