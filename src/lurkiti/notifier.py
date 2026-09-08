import asyncio
import logging
import threading
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal
from desktop_notifier import DesktopNotifier, Button, Icon, Urgency

from lurkiti.model import Stream

log = logging.getLogger(__name__)


class Notifier(QObject):
  '''
  Desktop notifications with an action button, backed by desktop-notifier.

  Interaction callbacks only fire while an asyncio loop is running to receive the
  platform's DBus/Cocoa signals, so the async backend is driven on a dedicated
  background loop. Callbacks run on that loop thread and emit `launch_requested`,
  which Qt delivers on the receiver's (main) thread.
  '''

  launch_requested = pyqtSignal(Stream)

  def __init__(self, app_name: str = 'Lurkiti'):
    super().__init__()
    self._backend = None
    self._loop = None
    self._thread = None
    try:
      self._loop = asyncio.new_event_loop()
      self._thread = threading.Thread(target=self._run_loop, name='lurkiti-notifier', daemon=True)
      self._thread.start()
      self._backend = DesktopNotifier(app_name=app_name)
    except Exception as err:
      log.error(f'Failed to initialize desktop-notifier: {err}')
      self._backend = None

  def _run_loop(self) -> None:
    asyncio.set_event_loop(self._loop)
    self._loop.run_forever()

  @property
  def available(self) -> bool:
    return self._backend is not None

  def notify_stream_online(self, header: str, body: str, stream: Stream, icon_path: Path | None, persistent: bool = False) -> bool:
    '''Show a stream-online notification with a Launch button. Returns True on success.'''
    if self._backend is None:
      return False
    coro = self._backend.send(
      title=header,
      message=body,
      icon=Icon(path=icon_path) if icon_path else None,
      buttons=[Button('Launch', on_pressed=lambda: self.launch_requested.emit(stream))],
      on_clicked=lambda: self.launch_requested.emit(stream),
      urgency=Urgency.Critical if persistent else Urgency.Normal,
      timeout=0 if persistent else 10,
    )
    try:
      future = asyncio.run_coroutine_threadsafe(coro, self._loop)
      future.add_done_callback(self._log_send_result)
      return True
    except Exception as err:
      log.error(f'desktop-notifier send failed: {err}')
      return False

  @staticmethod
  def _log_send_result(future) -> None:
    err = future.exception()
    if err is not None:
      log.error(f'desktop-notifier send failed: {err}')

  def shutdown(self) -> None:
    if self._backend is not None and self._loop is not None:
      try:
        asyncio.run_coroutine_threadsafe(self._backend.clear_all(), self._loop).result(timeout=2)
      except Exception as err:
        log.debug(f'Error clearing notifications on shutdown: {err}')
    if self._loop is not None:
      self._loop.call_soon_threadsafe(self._loop.stop)
    if self._thread is not None:
      self._thread.join(timeout=2)

