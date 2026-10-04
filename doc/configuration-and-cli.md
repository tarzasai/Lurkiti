# Configuration and CLI

## CLI Interface

`lurkiti [options]`

Lurkiti is a tray application with no positional arguments; all streams are
configured through the UI and stored in the config file.

Options:

- `-c`, `--config <path>`: explicit config file path
- `-l`, `--log-level <LEVEL>`: `DEBUG`, `INFO` (default), `WARNING`, or `ERROR`
- `--denoise-logging`: reduce log noise from dependencies (`urllib3`, `charset_normalizer`)

Example:

```bash
lurkiti --log-level DEBUG
lurkiti --config ~/.config/lurkiti-test.json
```

## Config Resolution

- With `-c/--config <path>`: that file is used.
- Otherwise: `<ConfigLocation>/Lurkiti.json`.

Typical config locations:

- Linux: `~/.config/Lurkiti.json`
- Windows: `%APPDATA%\Lurkiti.json`
- macOS: `~/Library/Application Support/Lurkiti.json`

Volatile runtime state is stored separately from settings:

- State file: `<GenericStateLocation>/Lurkiti.state.json` (falls back next to the config file if no state location is defined).
- Favicon cache: `<CacheLocation>/favicons/`.
- Transient player launch logs: `<tmp>/lurkiti/`.

The config and state files are JSON. Settings are saved whenever a value changes
(`config_changed` is emitted); state is saved when a stream's liveness or
watch/online timestamps change (`state_changed`).

## Global Settings (`ConfigModel`)

| Key | Default | Meaning |
| --- | --- | --- |
| `autostart_monitoring` | `false` | Start monitoring automatically on launch |
| `check_interval_mins` | `5` | Minutes between checks of the same stream |
| `default_notify` | `false` | Default notify setting for streams set to `default` |
| `default_streamlink_args` | `--title "{author} - {title}"` | Streamlink args applied to every launch |
| `default_quality` | `best` | Fallback quality when a stream has none |
| `default_player` | `""` | Default player command (empty = Streamlink default) |
| `default_player_args` | `""` | Default player arguments |
| `alternate_player` | `null` | Alternate player command (secondary launch) |
| `alternate_player_args` | `null` | Alternate player arguments |
| `clippiti_path` | `null` | Explicit path to the Clippiti executable |
| `tray_icon_action` | `nothing` | Left-click action (see `TrayIconAction`) |
| `always_on_submenu` | `false` | Group always-on streams in a tray submenu |
| `streams` | `{}` | Configured streams, keyed by URL |
| `windows` | `{}` | Saved window geometries |

`tray_icon_action` is one of: `nothing`, `open_url`, `open_config`,
`toggle_monitoring`, `toggle_notifications`.

## Per-Stream Settings (`Stream`)

| Key | Required | Meaning |
| --- | --- | --- |
| `url` | yes | Stream URL (also the config key) |
| `name` | yes | Display name |
| `type` | yes | Platform/site (e.g. `twitch`, `youtube`); used for the favicon |
| `quality` | no | Preferred quality (falls back to `default_quality`, then `best`) |
| `player` | no | Player command override (`clippiti` selects the Clippiti path) |
| `sl_args` | no | Extra Streamlink arguments (override/merge with defaults) |
| `mp_args` | no | Extra media-player arguments |
| `notify` | no | `default`, `no`, `yes`, or `persistent` (default `default`) |
| `always_on` | no | Always treat as live (pinned launcher entry, never probed) |

### Argument placeholders

Both default and per-stream Streamlink/player argument strings support
Lurkiti placeholders, substituted when the command is built:

- `$SC.name` → the stream's `name`
- `$SC.type` → the stream's `type`

`default_streamlink_args` additionally uses Streamlink's own `--title` template
tokens (e.g. `{author}`, `{title}`), which are expanded by Streamlink, not Lurkiti.

## Runtime State (`StreamState`)

Stored in the state file, per stream URL:

- `is_online` — current liveness (not persisted to disk; recomputed at runtime)
- `last_online_ts` — last time the stream was seen live (unix timestamp)
- `last_watched_ts` — last time the stream was launched (unix timestamp)

## Launching with Clippiti

When a stream's effective player is `clippiti` and a Clippiti executable is
available (via `clippiti_path` or found on `PATH`), the launch command targets
Clippiti instead of Streamlink. Clippiti takes its own arguments (e.g. `--mpv`)
before a `--` separator, with the merged Streamlink arguments forwarded after it;
`--title` and `--player` are stripped since Clippiti manages playback itself.
