import unittest
from unittest.mock import patch, MagicMock
import time

from lurkiti.model import Configuration, Stream
from lurkiti.monitor import StreamMonitor
from lurkiti.session import StreamProbe


class _SyncExecutor:
    '''Runs submitted checks inline so tests can assert right after scheduling.'''

    def __init__(self, *args, **kwargs):
        pass

    def submit(self, fn, *args):
        fn(*args)

    def shutdown(self, **kwargs):
        pass


class TestMonitor(unittest.TestCase):
    def setUp(self):
        # Minimal configuration with two streams written to a temp file
        import tempfile
        import json
        from pathlib import Path

        tmp = tempfile.NamedTemporaryFile('w+', delete=False)
        cfg = {
            'streams': {
                'https://a.example/': {'url': 'https://a.example/', 'name': 'A', 'type': 't1'},
                'https://b.example/': {'url': 'https://b.example/', 'name': 'B', 'type': 't2'},
            },
            'check_interval_mins': 1,
            'autostart_monitoring': False
        }
        json.dump(cfg, tmp)
        tmp.flush()
        tmp.close()
        self.tmpfile = Path(tmp.name)
        self.cfg = Configuration(self.tmpfile)
        self.monitor = StreamMonitor(self.cfg)
        gap = patch('lurkiti.monitor._SITE_GAP_SECONDS', 0)
        gap.start()
        self.addCleanup(gap.stop)

    def test_rate_limited_check_keeps_previous_status(self):
        import requests
        from test.test_helpers import mock_is_stream_live
        response = requests.Response()
        response.status_code = 429
        err = Exception('Unable to open URL')
        err.__cause__ = requests.HTTPError(response=response)
        self.monitor.stream_status['https://a.example/'] = True
        with mock_is_stream_live(side_effect=err):
            emitted = []
            self.monitor.stream_offline.connect(lambda s: emitted.append(s))
            self.monitor._check_single_stream(self.cfg.streams['https://a.example/'])
        self.assertEqual(emitted, [])
        self.assertTrue(self.monitor.stream_status['https://a.example/'])

    def test_site_gap_grows_on_rate_limit_and_decays_on_success(self):
        import requests
        from test.test_helpers import mock_is_stream_live
        response = requests.Response()
        response.status_code = 429
        err = Exception('Unable to open URL')
        err.__cause__ = requests.HTTPError(response=response)
        stream = self.cfg.streams['https://a.example/']
        with patch('lurkiti.monitor._SITE_GAP_SECONDS', 0.5):
            with mock_is_stream_live(side_effect=err):
                self.monitor._check_single_stream(stream)
                self.monitor._check_single_stream(stream)
            self.assertEqual(self.monitor._site_gap, {'a.example': 1.0})
            with mock_is_stream_live(return_value=StreamProbe('t', False)):
                self.monitor._check_single_stream(stream)
                self.assertEqual(self.monitor._site_gap, {'a.example': 0.5})
                self.monitor._check_single_stream(stream)
            self.assertEqual(self.monitor._site_gap, {})

    def test_check_single_stream_online_emits(self):
        from test.test_helpers import mock_is_stream_live
        # Simulate is_stream_live returning online
        with mock_is_stream_live(return_value=StreamProbe('youtube', True)):
            emitted = []
            self.monitor.stream_online.connect(lambda s, m=None: emitted.append(('online', s)))
            self.monitor._check_single_stream(self.cfg.streams['https://a.example/'])
            self.assertEqual(len(emitted), 1)
            self.assertEqual(emitted[0][0], 'online')

    def test_check_single_stream_offline_emits(self):
        from test.test_helpers import mock_is_stream_live
        # First set previous status to True, then simulate offline
        self.monitor.stream_status['https://a.example/'] = True
        with mock_is_stream_live(return_value=StreamProbe('youtube', False)):
            emitted = []
            self.monitor.stream_offline.connect(lambda s: emitted.append(('offline', s)))
            self.monitor._check_single_stream(self.cfg.streams['https://a.example/'])
            self.assertEqual(len(emitted), 1)
            self.assertEqual(emitted[0][0], 'offline')

    def test_check_streams_respects_interval_and_selects_oldest(self):
        from test.test_helpers import mock_is_stream_live
        # Make both streams appear online, call _check_streams twice with interval
        with mock_is_stream_live(return_value=StreamProbe('youtube', True)), \
                patch('lurkiti.monitor.ThreadPoolExecutor', _SyncExecutor):
            # first call: both last_check are 0, both are checked
            self.monitor._check_streams()
        # one stream should have a last_check set
        self.assertTrue(any(v > 0 for v in self.monitor.last_check_time.values()))
        # set both streams as just-checked and ensure no further checks occur
        now = time.time()
        for url in self.monitor.cfg.streams:
            self.monitor.last_check_time[url] = now
        prev = dict(self.monitor.last_check_time)
        self.monitor._check_streams()
        self.assertEqual(prev, self.monitor.last_check_time)

    def test_pause_resume_stop_and_get_online_streams(self):
        # Create simple config
        import tempfile, json
        from pathlib import Path
        tmp = tempfile.NamedTemporaryFile('w+', delete=False)
        cfg = {
            'streams': {
                'https://x.example/': {'url': 'https://x.example/', 'name': 'X', 'type': 'a'},
                'https://y.example/': {'url': 'https://y.example/', 'name': 'Y', 'type': 'b'},
            },
            'check_interval_mins': 1,
            'autostart_monitoring': False
        }
        json.dump(cfg, tmp)
        tmp.flush(); tmp.close()
        from lurkiti.model import Configuration
        cfgobj = Configuration(Path(tmp.name))
        mon = StreamMonitor(cfgobj)
        # No streams online initially
        self.assertEqual(mon.get_alive_streams(), [])
        # Set statuses and verify sorting by type then name
        mon.stream_status['https://y.example/'] = True
        mon.stream_status['https://x.example/'] = True
        online = mon.get_alive_streams()
        self.assertEqual([s.url for s in online], ['https://x.example/', 'https://y.example/'])
        # Pause/resume/stop simple checks
        mon.pause()
        self.assertTrue(mon.paused)
        mon.resume()
        self.assertFalse(mon.paused)
        mon.stop()
        self.assertFalse(mon.running)

    def test_run_loop_and_exception_handling(self):
        # Patch msleep to avoid sleeping, and simulate an exception from sls
        import tempfile, json
        from pathlib import Path
        tmp = tempfile.NamedTemporaryFile('w+', delete=False)
        cfg = {
            'streams': {
                'https://err.example/': {'url': 'https://err.example/', 'name': 'Err', 'type': 'err'},
            },
            'check_interval_mins': 0,
            'autostart_monitoring': True
        }
        json.dump(cfg, tmp)
        tmp.flush(); tmp.close()
        from lurkiti.model import Configuration
        cfgobj = Configuration(Path(tmp.name))
        mon = StreamMonitor(cfgobj)
        from test.test_helpers import mock_is_stream_live
        # Force is_stream_live to raise
        with mock_is_stream_live(side_effect=Exception('boom')), \
                patch('lurkiti.monitor.ThreadPoolExecutor', _SyncExecutor):
            # Break the loop after a couple iterations by driving the wake wait.
            called = {'count': 0}
            def fake_wait(timeout=None):
                called['count'] += 1
                if called['count'] > 1:
                    mon.stop()
                return False
            mon._wake.wait = fake_wait
            # Run in the current thread (not starting the QThread) — should run a
            # couple iterations and then stop.
            mon.run()
            # Ensure that an attempt to check was made and we recorded a status (False)
            self.assertIn('https://err.example/', mon.stream_status)

    def test_checks_run_in_parallel_up_to_limit(self):
        import json, tempfile, threading
        from pathlib import Path
        from lurkiti import monitor as monitor_mod
        urls = [f'https://s{i}.example/' for i in range(monitor_mod._MAX_PARALLEL_CHECKS + 2)]
        tmp = tempfile.NamedTemporaryFile('w+', delete=False)
        json.dump({
            'streams': {u: {'url': u, 'name': u, 'type': 't'} for u in urls},
            'check_interval_mins': 1,
            'autostart_monitoring': False,
        }, tmp)
        tmp.close()
        mon = StreamMonitor(Configuration(Path(tmp.name)))
        release = threading.Event()
        started = []
        lock = threading.Lock()

        def slow_probe(url, *args):
            with lock:
                started.append(url)
            release.wait(5)
            return StreamProbe('t', False)

        from test.test_helpers import mock_is_stream_live
        with mock_is_stream_live(side_effect=slow_probe):
            mon._check_streams()
            deadline = time.time() + 5
            while len(started) < monitor_mod._MAX_PARALLEL_CHECKS and time.time() < deadline:
                time.sleep(0.01)
            # All slots busy: a second pass must not schedule more or re-check in-flight streams
            mon._check_streams()
            time.sleep(0.05)
            self.assertEqual(len(started), monitor_mod._MAX_PARALLEL_CHECKS)
            self.assertEqual(len(set(started)), len(started))
            release.set()
            mon._executor.shutdown(wait=True)
        self.assertEqual(len(mon.last_check_time), monitor_mod._MAX_PARALLEL_CHECKS)
        self.assertEqual(mon._in_flight, {})

    def test_one_check_in_flight_per_site(self):
        import json, tempfile
        from pathlib import Path
        urls = ['https://www.site.example/a', 'https://site.example/b', 'https://other.example/c']
        tmp = tempfile.NamedTemporaryFile('w+', delete=False)
        json.dump({
            'streams': {u: {'url': u, 'name': u, 'type': 't'} for u in urls},
            'check_interval_mins': 1,
            'autostart_monitoring': False,
        }, tmp)
        tmp.close()
        mon = StreamMonitor(Configuration(Path(tmp.name)))
        submitted = []

        class _RecordingExecutor(_SyncExecutor):
            def submit(self, fn, *args):
                submitted.append(args[0])

        with patch('lurkiti.monitor.ThreadPoolExecutor', _RecordingExecutor):
            mon._check_streams()
        self.assertEqual(sorted(submitted), ['https://other.example/c', 'https://www.site.example/a'])


if __name__ == '__main__':
    unittest.main()
