# StreamCondor

StreamCondor is a lightweight system-tray app that monitors livestreams and opens them with [Streamlink](https://streamlink.github.io/).

## Features

- 🔔 Real-time stream monitoring
- 🎯 Multi-platform support (Twitch, YouTube, and other Streamlink-supported sites)
- 🖥️ System tray integration with status icons
- 🎨 Custom player support (mpv, VLC, or your preferred player)
- ⚙️ Per-stream quality, notification, and argument overrides
- 🌐 Favicon fetching and caching
- 📋 Quick launch from clipboard URL

Supported OS: Linux, Windows, macOS (desktop environments with a system tray)

## Screenshots

![System Tray menu](./media/tray.png)
![Streams Settings window](./media/settings1.png)
![App Settings window](./media/settings2.png)
![Stream Setting window](./media/stream1.png)
![Stream Setting window](./media/stream2.png)
![Stream Setting window](./media/stream3.png)

## Requirements

- Python 3.12+
- A desktop environment with system tray support
- Streamlink-compatible media player (optional, but recommended)

## Install (PyPI)

```bash
pip install streamcondor
```

Run:

```bash
streamcondor
```

## Run from source

```bash
git clone https://github.com/tarzasai/StreamCondor.git
cd StreamCondor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
streamcondor
```

Alternative without editable install:

```bash
PYTHONPATH="$PWD/src" .venv/bin/python -m streamcondor.main
```

## Command-line options

```text
-c, --config PATH         Path to custom configuration file
-l, --log-level LEVEL     DEBUG | INFO | WARNING | ERROR (default: INFO)
    --denoise-logging     Reduce dependency log noise
```

Example:

```bash
streamcondor --log-level DEBUG --denoise-logging
```

## Configuration

StreamCondor stores a JSON config file per user.

- Linux: `~/.config/StreamCondor.json`
- Windows: `%APPDATA%\StreamCondor.json`
- macOS: `~/Library/Application Support/StreamCondor.json`

If the file does not exist, StreamCondor creates one with defaults.

Minimal example:

```json
{
	"check_interval_mins": 5,
	"default_quality": "best",
	"default_notify": false,
	"streams": {
		"https://www.twitch.tv/some_channel": {
			"url": "https://www.twitch.tv/some_channel",
			"name": "some_channel",
			"type": "twitch"
		}
	}
}
```

## Development

Bootstrap a local development environment:

```bash
./setup_dev.sh
```

Run tests (recommended from repository root):

```bash
PYTHONPATH=src .venv/bin/python -m pytest
```

Or use the helper script:

```bash
./run_tests.sh
```

## Troubleshooting

- No tray icon: verify your desktop environment provides a system tray (some Wayland setups need extra integration).
- Stream does not open: ensure `streamlink` and your target media player are installed and available in `PATH`.
- Plugin/auth-related issues: check your Streamlink user config and plugin setup.
- To troubleshoot with logs:

```bash
streamcondor --log-level DEBUG
```

## Reporting issues

Open an issue at https://github.com/tarzasai/StreamCondor/issues and include:

- OS and desktop environment
- Steps to reproduce
- Relevant terminal logs

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Streamlink](https://streamlink.github.io/)
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- Contributors and testers

This is a third-party tool and is not affiliated with any streaming platform.
