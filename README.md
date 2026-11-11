# Wave microphone mute → Home Assistant

Make a light or another Home Assistant automation follow your Elgato Wave microphone's mute button. The bridge runs on your Windows PC, reads microphone mute state from Wave Link 3, and sends a webhook when that state changes.

A simple use: turn an ON-AIR light off when muted and on when unmuted. You choose what the Home Assistant automations do.

No Stream Deck hardware, Stream Deck software, Streamer.bot, Home Assistant token, or custom HA integration is required by this bridge. Wave Link itself must be running.

## Compatibility

| Component | Status |
| --- | --- |
| Windows, Python 3.13, Wave Link 3.3.0.4529 | Tested |
| Elgato Wave:3 touch mute | Tested |
| Wave:3 software microphone mute | Tested; reports the same input mute field |
| Other Wave microphones / interfaces | Not yet verified; discovery supports inputs exposing a boolean `isMuted` field |
| Mixer channel mute, per-mix mute, Windows mute, meeting-app mute | Not mapped |
| macOS / Linux / Wave Link 2 | Not supported by this implementation |

This uses an **unofficial local API**. It is not an Elgato product. Other devices and future Wave Link versions need their own verification. The program matches one exact device/input pair, never a name substring or all microphones at once.

## Requirements

- Windows PC with Wave Link 3 running under your Windows account.
- A microphone listed in Wave Link's input devices.
- Python 3.10 or newer available as `python` in PowerShell. Only 3.13 has been tested here.
- Home Assistant reachable from that PC on your local network.

## 1. Install and choose a microphone

Download/extract this project to a permanent folder. Open PowerShell there:

```powershell
.\setup.ps1
.\.venv\Scripts\python.exe configure.py
```

Setup creates an isolated Python environment and runs the tests. The configuration wizard reads Wave Link's inputs, lets you choose your microphone, asks for your Home Assistant URL, and writes **private `config.json`** with two randomly generated webhook IDs. It does not change your microphone or send webhooks. It refuses to overwrite an existing configuration.

If PowerShell blocks a downloaded script, review it and use `Unblock-File .\setup.ps1` (and the other scripts you intend to run). Follow your organization's execution policy if it still prevents scripts.

`config.example.json` documents the fields for manual setup. Do not use its placeholder IDs unchanged.

## 2. Create the Home Assistant automations

Open `config.json` locally. Create two automations in Home Assistant, each with a **Webhook** trigger:

| Trigger's webhook ID | Allowed method | Example action |
| --- | --- | --- |
| Value of `muted_webhook` | POST | Turn your ON-AIR light off |
| Value of `unmuted_webhook` | POST | Turn your ON-AIR light on |

Keep **Only accessible from the local network** enabled. Copy the IDs exactly; the bridge constructs `/api/webhook/<ID>` from your `ha_base`. Do not paste the full webhook URL into an ID field.

See [examples/home-assistant.yaml](examples/home-assistant.yaml) for two complete example automations. Replace the placeholder IDs and light entity. In the HA UI's YAML editor, paste one automation at a time without its leading list dash. Save and enable both automations. If editing `automations.yaml` directly, reload automations afterwards.

For WLED, you can replace the unmuted action with `select.select_option`, using your WLED preset select entity and an existing preset such as `White Solid`. Preset names and entity IDs depend on your setup.

Webhook IDs function as secrets. No HA access token is needed. Keep completed YAML and `config.json` private. See the [official HA webhook documentation](https://www.home-assistant.io/triggers/webhook/).

## 3. Verify mute semantics without sending anything

```powershell
.\.venv\Scripts\python.exe bridge.py --capture
```

This is **dry-run mode**. No webhooks are sent without `--live`.

1. Note the reported MUTED or UNMUTED state and compare it with your microphone.
2. Use the hardware mute control. Wait about five seconds. Confirm the displayed state matches. Toggle back and confirm again.
3. Repeat with the software microphone mute control you normally use.
4. Confirm unrelated channel/mix controls do not masquerade as microphone mute.
5. Press Ctrl+C to stop.

Expected output includes `Input state: MUTED` followed by `DRY RUN: would send muted`, or the corresponding unmuted messages. Unchanged state is not repeatedly sent.

If both controls behave correctly, edit **your local** `config.json` and set:

```json
"semantics_verified": true
```

If a control does not report the right state, leave this false. Check the chosen input and inspect local `logs/events.jsonl`. Do not guess based on audio levels or channel mute. Other microphone models may expose different behavior.

## 4. Test live, then start automatically

With both HA automations enabled:

```powershell
.\.venv\Scripts\python.exe bridge.py --live
```

The fresh current state is sent once on startup. Test mute and unmute and verify the actual light/action in HA. `HA accepted` means the HTTP request succeeded; it does not prove an automation ran. Check HA automation traces if the action does not happen.

Stop with Ctrl+C, then install the login task:

```powershell
.\install-startup.ps1 -Live
```

The task `WaveHA-Bridge-v3` runs hidden under the current user, starts at login, and waits/reconnects if Wave Link is not ready. It does not run before login or launch Wave Link for you. Without `-Live`, the installer creates a dry-run task. Reinstalling stops and replaces the existing task with the selected mode.

Keep the folder in place after installing. If you move it, rerun the installer from its new location. This project supports one installed bridge task per PC; do not run other mute bridges alongside it.

## Everyday commands

```powershell
Get-ScheduledTask -TaskName WaveHA-Bridge-v3
Get-Content .\logs\bridge.log -Tail 30 -Wait
Stop-ScheduledTask -TaskName WaveHA-Bridge-v3
Start-ScheduledTask -TaskName WaveHA-Bridge-v3
```

To capture a problem safely, stop the task, then run:

```powershell
.\.venv\Scripts\python.exe bridge.py --capture --seconds 60
```

Restart the task afterwards. `dry-run.cmd` is a double-click alternative. The process lock prevents two bridge workers in the same project folder. Captures can contain device identifiers; redact them before sharing.

Remove automatic startup with:

```powershell
.\uninstall-startup.ps1
```

This stops/removes the task but keeps your files. It does not modify any other bridge installation.

## How it works

```text
Wave microphone mute
    → Wave Link 3 local WebSocket
    → exact input isMuted boolean
    → muted / unmuted HTTP POST
    → your Home Assistant automation
```

- Reads `%LOCALAPPDATA%\Packages\Elgato.WaveLink_g54w8ztgkx496\LocalState\ws-info.json` on every connection; no fixed port or broad port scan.
- Connects only to `127.0.0.1` with `Origin: streamdeck://`. The header does not require Stream Deck.
- Checks `getApplicationInfo`, reads `getInputDevices`, and listens for `inputDeviceChanged` / `inputDevicesChanged`.
- Polls a fresh input snapshot every five seconds to recover missed events. Typical notification delivery is immediate; network retries and polling can add delay.
- Reconnects with backoff capped at about 30 seconds. It never writes microphone settings.
- Deduplicates states in memory. No old saved state is sent after restart; each new process sends its fresh initial state once.
- Retries a failed HA request after five seconds using the latest known state. Disconnects and missing inputs become UNKNOWN and send nothing.
- Normal logs rotate at 1 MB with three backups; optional event captures at 2 MB with two backups. Meter events are excluded from captures.

Network delivery is not exactly once: a timeout after HA accepted a request can cause a retry. Keep the HA actions idempotent (set on/off rather than toggle). A disconnection leaves HA in its last state; this is not a safety-critical indicator. If HA is restarted and forgets the light state without a microphone change, restart the bridge to resync.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No connection / missing port file | Wave Link 3 must run in the same Windows account. Its package path must match the path above. |
| UNKNOWN state | Selected device/input is missing or no longer exposes a boolean mute field. Reconnect the mic; rediscover if it was replaced. |
| Wrong control affects the light | Verify input mute separately from channel, mix, Windows, and app mute. |
| HA accepted but nothing happens | Matching webhook IDs, enabled automations, entity IDs, and HA automation traces. |
| HA delivery failed | Base URL, port/firewall, LAN access, and HTTP(S) connectivity. Exception types are logged without secret URLs. |
| Already running | Stop the scheduled task before foreground testing. |
| Works manually, not at login | Check Task Scheduler and logs; ensure Wave Link starts and the project folder has not moved. |

Changing microphones: stop the task, back up and rename private `config.json`, run `configure.py`, and repeat verification. New configuration generates new webhook IDs; update HA too, or deliberately retain your previous private IDs.

## Development and publishing

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s . -p test_bridge.py
.\package-release.ps1
```

The release script creates `dist/wave-ha-bridge-v3.zip` from an explicit list of public files. **Use that ZIP's contents for GitHub's browser upload**, not the whole working directory. `.gitignore` protects Git workflows; it does not filter files dragged into a browser.

Private runtime files (`config.json`, `.local/`, `logs/`, `.venv/`, caches, locks, and migration flags) are excluded. The example configuration contains placeholders only. Do not add completed HA YAML to the public repository.

The existing Wave:3 installation passed hardware/software event checks and a physical ON-AIR light test. Automated tests cover state matching, delivery/retry behavior, configuration validation, discovery filtering, and port validation. Physical reboot, port-change, unplug/replug, and HA outage scenarios still need broader hardware testing. Contributions reporting other Wave models should include OS and Wave Link version plus redacted event shapes, never webhook IDs or raw private captures.

No license has been selected for this repository yet. Choose an appropriate license before inviting redistribution; public GitHub visibility alone is not an open-source license.

## Protocol references

- [WaveLink.Client protocol notes](https://github.com/Agash/WaveLink.Client/blob/main/PROTOCOL.md)
- [Unofficial node-wave-link-sdk](https://github.com/DarrellVS/node-wave-link-sdk)
- [wavelink-knob connection notes](https://github.com/idlewatts/wavelink-knob)

Community documentation guided development. Actual events from the tested Wave:3 determined its mute mapping.
