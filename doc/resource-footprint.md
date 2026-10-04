# Resource Footprint

This document describes the system resources a running Lurkiti instance consumes,
the amounts observed on a live instance, and the reason each cost exists. Unlike a
video player, Lurkiti does no decoding or rendering of its own: it is a tray UI
plus a periodic Streamlink probe, so its footprint is dominated by the Python + Qt
+ Streamlink runtime rather than by media processing.

## Measurement Context

Figures below were captured from a live instance that had been monitoring streams
from the tray for ~5 days.

- Interpreter: Python 3.14, PyQt6 / Qt 6.11.2, Wayland
- Method: `/proc/<pid>/task` for threads, `/proc/<pid>/smaps_rollup` and `smaps`
  for memory, `/proc/<pid>/stat` for cumulative CPU time

> Absolute numbers vary by host and Qt platform. Unlike a GPU video app, Lurkiti's
> thread count and memory do **not** scale with CPU core count or window size;
> they are essentially flat regardless of how many streams are configured.

## Summary (per instance)

| Resource | Observed | Notes |
| --- | --- | --- |
| Threads | 6 | Flat; does not grow with the number of configured streams |
| RSS | ~374 MB | Resident set after days of uptime (~180 MB fresh; grows with uptime) |
| PSS | ~300 MB | Proportional set (shared pages divided across users) |
| CPU | ~0% idle | 0% between checks (monitor thread blocked); brief spikes only when a stream is probed |

Launched players (Streamlink, mpv/VLC, Clippiti) run as separate processes and
are **not** included above.

## Threads

| Thread | Count | Source | Reason | Tunable |
| --- | --- | --- | --- | --- |
| `python3` (main) | 1 | `QApplication` | UI event loop, tray, menus | No |
| `StreamMonitor` | 1 | `monitor.py` (`QThread`) | Off-thread liveness probing | No (keeps UI responsive) |
| `lurkiti-notifie` | 1 | `notifier.py` asyncio loop | Receives DBus/Cocoa callbacks for the Launch button | No (needed for action buttons) |
| `QDBusConnection` | 1 | Qt / DBus | Desktop integration (notifications, tray) | No |
| `WaylandEventThr` | 2 | Qt Wayland platform | Windowing/event delivery | No (platform-provided) |

The monitor deliberately probes **one stream per tick** on a short sleep, so the
thread count does not grow with the number of configured streams — only the time
to cycle through all of them does.

## Memory

Measured split of the ~374 MB RSS:

| Region | Observed | Reason | Tunable |
| --- | --- | --- | --- |
| Anonymous (Python heap) | ~283 MB | Interpreter objects + Streamlink, its plugins, the cached CLI parser, Pydantic models, and `requests`/BeautifulSoup/Pillow | Indirect (fewer sideloaded plugins = less) |
| File-backed libraries | ~89 MB | Resident code for Python, PyQt6/Qt6, and C extensions (`libcrypto`, Pillow's `_imaging`, etc.), mostly shared-clean across apps | No |

The dominant cost is the **Python heap**: importing Streamlink and its plugin set
(plus the HTTP/HTML/image stack used for favicons) pulls in a large amount of
code and object state. This is paid once at startup — `load_sl_user_stuff()` builds
the CLI parser and loads plugins a single time — so subsequent probes are cheap
and reuse the cached parser and session. The runtime footprint is therefore
roughly flat after startup.

## CPU

The monitor thread is event-driven: it sleeps until the next stream is actually
due (up to minutes away) and is woken immediately — via a `threading.Event` — on
control changes (pause/resume/stop) and on any configuration change (including
`always_on` toggles and interval edits). Between due checks it consumes no CPU;
brief spikes occur only when a due stream is probed (a Streamlink resolve +
liveness check), throttled to one stream per `check_interval_mins`. A small sleep
floor keeps an initial backlog (or a zero/tiny interval) from hot-spinning.

Measured on the event-driven build: over a 30 s idle window (no probe due) both
the `StreamMonitor` thread and the whole process used **0.000%** CPU; a window
that happened to include a liveness probe measured ~1.3% for that interval — i.e.
the only CPU cost is the probe work itself, not any polling baseline. (An earlier
build polled on a fixed ~150 ms heartbeat and averaged ~0.3% even while idle.)

## Launched Players

Players (Streamlink, mpv/VLC, or Clippiti) run as **independent detached
processes** and are not part of Lurkiti's own footprint. Lurkiti spawns them
fire-and-forget in their own session and sets `SIGCHLD` to `SIG_IGN` so exited
players are reaped by the kernel and never accumulate as zombie entries.

A watched Clippiti instance has its own, much larger footprint (embedded mpv +
GPU decode); see Clippiti's `doc/resource-footprint.md` for that.

## Applied Optimizations

- **Single-probe round-robin monitoring** — avoids bursting N concurrent
  Streamlink checks; cost scales in *time*, not in threads or memory.
- **Event-driven monitor loop** — the monitor sleeps until the next check is due
  and is woken immediately on control or configuration changes, so there is no
  fixed polling heartbeat and idle CPU is effectively zero.
- **One-time Streamlink setup** — plugins and the CLI parser are built once and
  cached; runtime reload is explicit (settings button), not per-check.
- **Detached, auto-reaped players** — no lingering child processes and no
  per-player bookkeeping in the app.
- **On-disk favicon cache** — icons are fetched once per stream type and reused
  across restarts.

## Conclusion

Lurkiti's steady-state footprint is small in CPU and flat in threads (6), with
memory (~374 MB RSS / ~300 MB PSS) dominated by the Python + Streamlink + Qt
runtime loaded at startup rather than by anything the app does per check. The
largest single contributor — the Python heap holding Streamlink and its plugins —
is fixed overhead of the chosen stack. The heavy media work lives entirely in the
external player processes, which are intentionally outside the app's lifecycle.
