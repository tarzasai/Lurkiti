import time
import logging
import threading
from PyQt6.QtCore import QThread, pyqtSignal

from lurkiti.model import Configuration, Stream, NotifyMode
from lurkiti.session import is_stream_live

log = logging.getLogger(__name__)

# How long the loop sleeps when nothing is due (paused, no streams, or all
# always_on). It is always woken earlier by wake() on control/config changes.
_IDLE_WAKE_CAP_SECONDS = 3600.0

# Floor applied only while checks are due, so draining a backlog (or a zero/tiny
# check interval) paces at most ~1 check per this many seconds instead of
# hot-spinning. It never delays wake() and never applies to idle sleeps.
_MIN_SLEEP_SECONDS = 0.15


class StreamMonitor(QThread):
  stream_online = pyqtSignal(Stream, object)
  stream_offline = pyqtSignal(Stream)

  def __init__(self, configuration: Configuration):
    super().__init__()
    self.cfg = configuration
    self.running = True
    self.paused = not self.cfg.autostart_monitoring
    self.stream_status: dict[str, bool] = {}
    self.last_check_time: dict[str, float] = {}
    self._wake = threading.Event()
    # Config edits (global or per-stream, e.g. toggling always_on or changing the
    # check interval) must take effect without waiting out the current sleep.
    self.cfg.config_changed.connect(self.wake)

  def run(self) -> None:
    while self.running:
      for url, stream in self.cfg.streams.items():
        if stream.always_on:
          self.stream_status[url] = True
      if not self.paused:
        self._check_streams()
      # Sleep until the next check is due, or until wake() is signalled.
      self._wake.wait(self._seconds_until_next_wake())
      self._wake.clear()

  def wake(self) -> None:
    '''Interrupt the current sleep so the loop re-evaluates the config at once.'''
    self._wake.set()

  def _seconds_until_next_wake(self) -> float:
    '''
    Seconds until the soonest due liveness check, mirroring the due logic in
    _check_streams: a small floor while checks are due (so a backlog drains
    without hot-spinning) and a long cap when nothing is checkable. wake()
    shortens any sleep when the configuration or run state changes.
    '''
    if self.paused:
      return _IDLE_WAKE_CAP_SECONDS
    interval = self.cfg.check_interval_mins * 60
    now = time.time()
    soonest = None
    for url, stream in self.cfg.streams.items():
      if stream.always_on:
        continue
      last_check = self.last_check_time.get(url, 0)
      if last_check == 0:
        return _MIN_SLEEP_SECONDS  # due now; floor avoids a hot spin
      wait = (last_check + interval) - now
      if soonest is None or wait < soonest:
        soonest = wait
    if soonest is None:
      return _IDLE_WAKE_CAP_SECONDS  # nothing checkable (empty or all always_on)
    return max(_MIN_SLEEP_SECONDS, soonest)

  def _check_streams(self) -> None:
    # Filter enabled streams that need checking
    streams_to_check = []
    for url, stream in self.cfg.streams.items():
      if stream.always_on:
        continue
      last_check = self.last_check_time.get(url, 0)
      time_since_check = time.time() - last_check
      # Check if never checked or check_interval_mins has elapsed
      if last_check == 0 or time_since_check >= (self.cfg.check_interval_mins * 60):
        streams_to_check.append((url, last_check, self.cfg.streams[url]))
    # Sort by last check time (oldest first, never checked go first)
    streams_to_check.sort(key=lambda x: x[1])
    # Check only the first stream that's due
    if streams_to_check:
      url, _, stream = streams_to_check[0]
      self._check_single_stream(stream)
      self.last_check_time[url] = time.time()

  def _check_single_stream(self, stream: Stream) -> None:
    try:
      probe = is_stream_live(
        stream.url,
        self.cfg.default_streamlink_args,
        stream.sl_args
      )
      is_online = probe.is_live
    except Exception as e:
      log.debug(f'Stream offline or error checking {stream.url}: {e}')
      probe = None
      is_online = False
    previous_status = self.stream_status.get(stream.url, False)
    # Detect status changes
    if is_online and not previous_status:
      log.info(f'Stream online: {stream.name}')
      self.stream_online.emit(stream, probe)
    elif not is_online and previous_status:
      log.info(f'Stream offline: {stream.name}')
      self.stream_offline.emit(stream)
    self.stream_status[stream.url] = is_online

  def stop(self) -> None:
    self.running = False
    self.wake()

  def pause(self) -> None:
    self.paused = True
    self.wake()

  def resume(self) -> None:
    self.paused = False
    self.wake()

  def live_streams_count(self) -> int:
    return sum(
      1 for url, status in self.stream_status.items()
        if status and url in self.cfg.streams and not self.cfg.streams[url].always_on
    )

  def vips_streams_count(self) -> int:
    return sum(
      1 for stream in self.cfg.streams.values()
        if stream.notify in (NotifyMode.YES, NotifyMode.PERSISTENT) and self.stream_status.get(stream.url, False)
    )

  def get_perma_streams(self) -> list[Stream]:
    perma = [stream for stream in self.cfg.streams.values() if stream.always_on]
    return sorted(perma, key=lambda s: (s.type or '', s.name or s.url or ''))

  def get_alive_streams(self) -> list[Stream]:
    alive = [stream for stream in self.cfg.streams.values() if not stream.always_on and self.stream_status.get(stream.url, False)]
    return sorted(alive, key=lambda s: (s.type or '', s.name or s.url or ''))
