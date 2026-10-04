# Operations and Troubleshooting

## Local Development Commands

Create and activate environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Run app:

```bash
PYTHONPATH=src ./.venv/bin/python -m lurkiti.main --log-level DEBUG
```

Run tests:

```bash
./run_tests.sh
# Or directly:
QT_QPA_PLATFORM=offscreen PYTHONPATH=src ./.venv/bin/python -m pytest --forked
```

## Runtime Health Checklist

- `streamlink` Python package is importable in the active environment
- the desktop environment exposes a **system tray** (`QSystemTrayIcon.isSystemTrayAvailable()`)
- the configured player command exists on `PATH` (or an absolute path is set)
- the config file is readable/writable at the resolved path
- stream resolution succeeds for configured URLs (a valid Streamlink plugin matches)

## Typical Failures

- No tray icon appears:
  - the desktop environment has no system-tray support, or the tray is not yet available at launch
- Stream never shows as live:
  - URL is offline/private/invalid
  - no Streamlink plugin matches the URL (`NoPluginError`)
  - provider-specific authentication required (set it via Streamlink args or the Streamlink config/per-plugin config)
  - invalid per-stream Streamlink arguments
- Streamlink requests interactive input:
  - Lurkiti probes headlessly and cannot answer prompts; provide the value via Streamlink arguments or the Streamlink config file
- Player does not start:
  - player command not found, or invalid player arguments
  - for Clippiti: `clippiti_path` not set and `clippiti` not on `PATH`
- No desktop notification:
  - `desktop-notifier` backend unavailable; Lurkiti falls back to a tray balloon message

## Logging Tips

Use `--log-level DEBUG` for verbose diagnostics, and `--denoise-logging` to quiet
noisy dependencies.

When debug logging is enabled, each launched player's stdout/stderr is written to
a log under `<tmp>/lurkiti/`, and the exact command is written to a `cmd_*.log`
file there, so a failed launch can be inspected after the fact. Without debug
logging these transient logs are removed automatically.
