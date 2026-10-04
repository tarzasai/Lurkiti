# Runtime Workflows

This document summarizes the main application workflows.

## 1. Startup

```mermaid
sequenceDiagram
    participant User
    participant Main as main.py
    participant SL as Streamlink session
    participant Tray as TrayIcon
    participant Mon as StreamMonitor

    User->>Main: lurkiti [-c config] [-l level]
    Main->>Main: parse args + setup logging
    Main->>Main: create QApplication + excepthook
    Main->>Main: configure_child_reaping (SIGCHLD=SIG_IGN)
    Main->>SL: load_sl_user_stuff() (plugins + config + parser)
    Main->>Tray: TrayIcon(app, config_path)
    Tray->>Tray: load Configuration + State
    Tray->>Mon: create + start monitor thread
    Tray-->>User: tray icon visible
```

If no `--config` is given, the config path defaults to `<config-dir>/Lurkiti.json`.

## 2. Monitoring Loop

```mermaid
sequenceDiagram
    participant Mon as StreamMonitor (thread)
    participant SL as Streamlink session
    participant Tray as TrayIcon

    loop while not paused
        Mon->>Mon: mark always_on streams live
        Mon->>Mon: pick the single oldest "due" stream
        Note over Mon: due = never checked, or<br/>check_interval_mins elapsed
        Mon->>SL: is_stream_live(url, args)
        SL-->>Mon: StreamProbe(plugin, is_live, metadata)
        alt transition offline -> online
            Mon-->>Tray: stream_online(stream, probe)
        else transition online -> offline
            Mon-->>Tray: stream_offline(stream)
        end
        Mon->>Mon: wait until next due (or woken by wake())
    end
```

The loop is event-driven: it sleeps until the next stream is due (via a
`threading.Event`) and is woken immediately on `pause`/`resume`/`stop` and on any
configuration change (`config_changed`, e.g. an `always_on` toggle or interval
edit). Only one stream is probed per iteration, throttled by `check_interval_mins`,
so idle CPU is effectively zero between checks.

## 3. Going Live and Notification

```mermaid
sequenceDiagram
    participant Mon as StreamMonitor
    participant Tray as TrayIcon
    participant Cfg as Configuration
    participant Notif as Notifier

    Mon-->>Tray: stream_online(stream, probe)
    Tray->>Cfg: mark_stream_online(url)
    Tray->>Tray: update status icon (idle/live/vips)
    Tray->>Tray: decide notify (NotifyMode + default_notify)
    alt notification wanted
        alt desktop-notifier available
            Tray->>Notif: notify_stream_online(..., persistent?)
            Notif-->>Tray: launch_requested(stream) on Launch press
        else fallback
            Tray->>Tray: showMessage(tray balloon)
        end
    end
```

Per-stream `notify` (`default`/`no`/`yes`/`persistent`) overrides the global `default_notify`. `persistent` uses a critical-urgency notification with no timeout.

## 4. Launching a Stream

```mermaid
sequenceDiagram
    participant User
    participant Tray as TrayIcon
    participant Cmd as command.py
    participant Proc as Player process

    User->>Tray: click stream (menu / notification / tray action)
    Tray->>Cmd: build_launch_command(cfg, stream, alt_player?)
    alt player == "clippiti" and resolvable
        Cmd-->>Tray: Clippiti command (args before `--`, SL args after)
    else
        Cmd-->>Tray: Streamlink command (merged args + quality fallback)
    end
    Tray->>Cmd: launch_process(command)
    Cmd->>Proc: detached Popen (start_new_session)
    Tray->>Tray: mark_stream_watched(url)
```

`streamlink` is launched as `python -m streamlink` so the bundled/virtualenv copy is used. Quality resolves to the stream (or default) quality with `best` appended as a fallback.

## 5. Reloading Streamlink

```mermaid
flowchart TD
    A[Settings: Reload Streamlink] --> B[load_sl_user_stuff]
    B --> C[Reload sideloaded plugins]
    C --> D[Rebuild cached CLI parser]
    D --> E[Re-apply main config session options]
```

This picks up newly added plugins or config changes without restarting the app.

## 6. Shutdown

```mermaid
flowchart TD
    A[Quit from tray menu] --> B[Stop StreamMonitor thread]
    B --> C[Notifier.shutdown: clear + stop loop thread]
    C --> D[QApplication quits]
```
