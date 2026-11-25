import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit
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

# Liveness checks are mostly network waits, so a few run at once, but never two
# against the same site: some sites answer concurrent probes with 429.
_MAX_PARALLEL_CHECKS = 4

# Pause before re-probing a site that answered 429; it doubles on every further
# 429 up to the cap.
_SITE_GAP_SECONDS = 0.5
_SITE_GAP_MAX_SECONDS = 5.0


def _site_of(url: str) -> str:
  host = (urlsplit(url).hostname or '').lower()
  return host.removeprefix('www.')


def _is_rate_limited(err: BaseException) -> bool:
  while err is not None:
    response = getattr(err, 'response', None)
    if getattr(response, 'status_code', None) == 429:
      return True
    err = err.__cause__
  return False


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
    self._in_flight: dict[str, str] = {}  # url -> site
    self._site_gap: dict[str, float] = {}
    self._in_flight_lock = threading.Lock()
    self._executor: ThreadPoolExecutor | None = None
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
    if self._executor is not None:
      self._executor.shutdown(wait=False, cancel_futures=True)
      self._executor = None

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
    with self._in_flight_lock:
      in_flight = dict(self._in_flight)
    if len(in_flight) >= _MAX_PARALLEL_CHECKS:
      return _IDLE_WAKE_CAP_SECONDS  # a finishing check calls wake()
    busy_sites = set(in_flight.values())
    interval = self.cfg.check_interval_mins * 60
    now = time.time()
    soonest = None
    for url, stream in self.cfg.streams.items():
      if stream.always_on or url in in_flight or _site_of(url) in busy_sites:
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
    with self._in_flight_lock:
      in_flight = dict(self._in_flight)
    busy_sites = set(in_flight.values())
    # Filter enabled streams that need checking
    streams_to_check = []
    for url, stream in self.cfg.streams.items():
      if stream.always_on or url in in_flight:
        continue
      last_check = self.last_check_time.get(url, 0)
      time_since_check = time.time() - last_check
      # Check if never checked or check_interval_mins has elapsed
      if last_check == 0 or time_since_check >= (self.cfg.check_interval_mins * 60):
        streams_to_check.append((url, last_check, self.cfg.streams[url]))
    # Sort by last check time (oldest first, never checked go first)
    streams_to_check.sort(key=lambda x: x[1])
    # Start the oldest due checks, up to the free worker slots
    free_slots = _MAX_PARALLEL_CHECKS - len(in_flight)
    if not streams_to_check or free_slots <= 0:
      return
    if self._executor is None:
      self._executor = ThreadPoolExecutor(max_workers=_MAX_PARALLEL_CHECKS, thread_name_prefix='lurkiti-check')
    for url, _, stream in streams_to_check:
      if free_slots <= 0:
        break
      site = _site_of(url)
      if site in busy_sites:
        continue
      busy_sites.add(site)
      free_slots -= 1
      with self._in_flight_lock:
        self._in_flight[url] = site
      self._executor.submit(self._run_check, url, stream)

  def _run_check(self, url: str, stream: Stream) -> None:
    try:
      self._check_single_stream(stream)
    finally:
      self.last_check_time[url] = time.time()
      gap = self._site_gap.get(_site_of(url))
      if gap:
        time.sleep(gap)
      with self._in_flight_lock:
        self._in_flight.pop(url, None)
      self.wake()

  def _check_single_stream(self, stream: Stream) -> None:
    started = time.monotonic()
    try:
      probe = is_stream_live(
        stream.url,
        self.cfg.default_streamlink_args,
        stream.sl_args
      )
      is_online = probe.is_live
    except Exception as e:
      if _is_rate_limited(e):
        site = _site_of(stream.url)
        gap = min(_SITE_GAP_MAX_SECONDS, max(_SITE_GAP_SECONDS, 2 * self._site_gap.get(site, 0)))
        self._site_gap[site] = gap
        log.warning(f'Rate limited checking {stream.name or stream.url}; keeping its previous status, pausing {gap:.1f}s between {site} checks')
        return
      log.debug(f'Stream offline or error checking {stream.url}: {e}')
      probe = None
      is_online = False
    site = _site_of(stream.url)
    if site in self._site_gap:
      gap = self._site_gap[site] / 2
      if gap < _SITE_GAP_SECONDS:
        del self._site_gap[site]
      else:
        self._site_gap[site] = gap
    log.debug(f'Checked {stream.name or stream.url} in {time.monotonic() - started:.2f}s: {"online" if is_online else "offline"}')
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
