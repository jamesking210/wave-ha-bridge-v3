# Wave microphone mute → Home Assistant

Use your Wave microphone's mute control to turn an ON-AIR light off when muted and on when unmuted.

This guide walks you through installing the bridge on Windows, connecting it to Home Assistant, testing it, and making it start when you sign in. You can use the same webhooks for other Home Assistant actions.

**Tested with:** Elgato Wave:3, Wave Link 3.3.0.4529, and Python 3.13 on Windows. Other Wave models need the mute test in Step 4 before use.

## Before you start

You need:

- A Windows PC with **Wave Link 3** installed and running.
- Your microphone connected and visible in Wave Link.
- **Python 3.10 or newer** installed. Python 3.13 is the tested version.
- Home Assistant accessible from this PC on your local network.
- A light already working in Home Assistant. Confirm you can turn it on and off there first.

The bridge does not require Stream Deck, Streamer.bot, a Home Assistant access token, or a custom HA integration.

> **Already using this bridge?** You do not need to repeat setup to use this README. Keep your existing `config.json`. Stop the scheduled task before running any foreground tests.

## Setup steps

1. [Download the project](#1-download-the-project)
2. [Install the Python dependency](#2-install-the-python-dependency)
3. [Choose your microphone](#3-choose-your-microphone)
4. [Check mute detection](#4-check-mute-detection)
5. [Create the Home Assistant automations](#5-create-the-home-assistant-automations)
6. [Test the light](#6-test-the-light)
7. [Start automatically at login](#7-start-automatically-at-login)

---

## 1. Download the project

1. At the top of [this repository](https://github.com/jamesking210/wave-ha-bridge-v3), click **Code → Download ZIP**.
2. Extract the ZIP.
3. Move the project files into a permanent folder. This guide uses:

   ```text
   C:\scripts\wave-ha-bridge-v3
   ```

Make sure `bridge.py`, `setup.ps1`, and `README.md` are directly inside that folder—not inside another nested folder.

Open **PowerShell** and enter:

```powershell
Set-Location "C:\scripts\wave-ha-bridge-v3"
Get-ChildItem
```

**Checkpoint:** You should see `bridge.py`, `configure.py`, and `setup.ps1` in the list.

All following commands run in this same PowerShell window and folder. If you chose a different folder, use that path instead.

## 2. Install the Python dependency

Check that Python is available:

```powershell
python --version
```

**Checkpoint:** You should see `Python 3.10` or a newer version.

If the command is not found or opens the Microsoft Store, install Python from [python.org](https://www.python.org/downloads/windows/) and make sure it is available on PATH. Close and reopen PowerShell, return to the project folder, and check again.

Now run:

```powershell
.\setup.ps1
```

This creates a private Python environment in `.venv`, installs the dependency, and runs the project's tests.

**Checkpoint:** The test output should end with **OK**. Do not continue if setup reports an error.

<details>
<summary>PowerShell says scripts are blocked</summary>

Review the downloaded scripts, then unblock the scripts used by this guide:

```powershell
Unblock-File .\setup.ps1
Unblock-File .\install-startup.ps1
Unblock-File .\uninstall-startup.ps1
```

Try `.\setup.ps1` again. If your computer's execution policy still blocks it, follow your Windows or organization policy. Unblocking a download does not override an enforced execution policy.

</details>

## 3. Choose your microphone

Leave Wave Link open, then run:

```powershell
.\.venv\Scripts\python.exe configure.py
```

The wizard will:

1. Connect to Wave Link.
2. List the available microphone inputs.
3. Ask you to enter the number beside your Wave microphone.
4. Ask for your Home Assistant base URL.

For the URL, enter the local address you use to reach Home Assistant, for example:

```text
http://homeassistant.local:8123
```

You can also use your Home Assistant server's LAN IP address. Enter only the server address and port—do not include a dashboard path or `/api/webhook/`.

**Checkpoint:** You should see:

```text
Created private config.json with two random webhook IDs.
```

The generated `config.json` contains your microphone selection and two private webhook IDs. **Do not upload this file to GitHub or share its contents.** The wizard will not overwrite an existing file.

## 4. Check mute detection

First, check that the bridge reads your mute control correctly. This test **does not send anything to Home Assistant**.

Run:

```powershell
.\.venv\Scripts\python.exe bridge.py --capture
```

Leave it running and perform these checks:

| What you do | What you should see |
| --- | --- |
| Mute the microphone using its hardware control | `Input state: MUTED` and `DRY RUN: would send muted` |
| Wait about five seconds, then unmute it | `Input state: UNMUTED` and `DRY RUN: would send unmuted` |
| Repeat with the software microphone mute control you use in Wave Link | The same matching mute/unmute messages |

The initial state also appears when the program starts. It does not repeatedly print an unchanged state.

**Checkpoint:** The displayed state agrees with the microphone for both controls.

Press **Ctrl+C** to stop the test.

If a control does not produce the correct state, stop here and check [Troubleshooting](#troubleshooting). Mixer-channel, individual mix, Windows, and meeting-app mute are different controls and are not mapped by this bridge.

Once the test passes, open the configuration:

```powershell
notepad .\config.json
```

Find:

```json
"semantics_verified": false
```

Change only `false` to `true`, keeping any comma at the end of the line. Save the file.

This setting confirms that you checked mute detection. Live mode refuses to run until it is true.

## 5. Create the Home Assistant automations

You will create **two automations**: one for muted and one for unmuted.

Keep `config.json` open locally so you can copy the generated IDs. Copy only the text between the quotation marks for each ID.

### Find your light's entity ID

In Home Assistant, open **Developer Tools → States**, find your light, and note its entity ID. It will look like:

```text
light.your_on_air_light
```

Use your actual entity ID in both examples below.

### A. Turn the light off when muted

In Home Assistant:

1. Open **Settings → Automations & scenes**.
2. Create a new, empty automation.
3. Open its menu and choose **Edit in YAML**.
4. Replace the editor contents with this example:

```yaml
alias: Wave microphone muted
triggers:
  - trigger: webhook
    webhook_id: "PASTE_YOUR_MUTED_WEBHOOK_ID_HERE"
    allowed_methods:
      - POST
    local_only: true
actions:
  - action: light.turn_off
    target:
      entity_id: light.your_on_air_light
mode: restart
```

Replace:

- `PASTE_YOUR_MUTED_WEBHOOK_ID_HERE` with the value of **`muted_webhook`** from your private `config.json`.
- `light.your_on_air_light` with your light's entity ID.

Save the automation and make sure it is enabled.

### B. Turn the light on when unmuted

Create a **second** empty automation. Open its YAML editor and paste:

```yaml
alias: Wave microphone unmuted
triggers:
  - trigger: webhook
    webhook_id: "PASTE_YOUR_UNMUTED_WEBHOOK_ID_HERE"
    allowed_methods:
      - POST
    local_only: true
actions:
  - action: light.turn_on
    target:
      entity_id: light.your_on_air_light
mode: restart
```

Replace:

- `PASTE_YOUR_UNMUTED_WEBHOOK_ID_HERE` with the value of **`unmuted_webhook`** from `config.json`.
- `light.your_on_air_light` with the same light's entity ID.

Save and enable this automation too.

**Checkpoint:** You now have two enabled automations with **different webhook IDs** that match your configuration. Keep `local_only: true`; the PC and Home Assistant must communicate over the local network.

<details>
<summary>Optional: select a WLED preset when unmuted</summary>

First create the preset in WLED and confirm Home Assistant can select it.

In the **unmuted** automation, replace the `actions` section with:

```yaml
actions:
  - action: select.select_option
    target:
      entity_id: select.your_wled_preset
    data:
      option: "White Solid"
```

Replace the entity ID with your WLED preset select entity and `White Solid` with the exact name of your existing preset. Keep the muted automation's light-off action.

</details>

The repository also includes [both automations in one example file](examples/home-assistant.yaml) for people editing `automations.yaml` directly. The separate examples above are ready for the UI editor.

## 6. Test the light

Back in PowerShell, run:

```powershell
.\.venv\Scripts\python.exe bridge.py --live
```

**Live mode sends the microphone's current state immediately**, so your light may change as soon as the program starts.

Now test:

| Microphone state | Expected result |
| --- | --- |
| Muted | Light turns off |
| Unmuted | Light turns on, or selects your configured WLED preset |

Repeat with the hardware control and your tested software microphone mute control.

**Checkpoint:** The actual light follows mute and unmute. The console should also show `HA accepted muted` or `HA accepted unmuted`.

If the console says `HA accepted` but the light does not change, check the automation's **Traces**, webhook ID, and target entity in Home Assistant. HTTP acceptance alone does not prove the automation ran.

Once both directions work, press **Ctrl+C** to stop the foreground bridge.

## 7. Start automatically at login

Run:

```powershell
.\install-startup.ps1 -Live
```

This installs and starts a Windows scheduled task named **WaveHA-Bridge-v3**. It runs in the background under your Windows account.

Check it:

```powershell
Get-ScheduledTask -TaskName WaveHA-Bridge-v3
```

**Checkpoint:** Its state should be **Running**. Test mute and unmute once more with the foreground window no longer running.

Setup is complete. Keep the project folder in place and make sure Wave Link starts when you sign in. The bridge retries if Wave Link is not ready yet; it does not launch Wave Link itself.

---

## Using it later

Run these commands from the project folder. Each block is a separate action.

**View recent activity:**

```powershell
Get-Content .\logs\bridge.log -Tail 30 -Wait
```

Press Ctrl+C to stop watching the log; this does not stop the background bridge.

**Stop the bridge:**

```powershell
Stop-ScheduledTask -TaskName WaveHA-Bridge-v3
```

**Start the bridge:**

```powershell
Start-ScheduledTask -TaskName WaveHA-Bridge-v3
```

**Remove automatic startup:**

```powershell
.\uninstall-startup.ps1
```

This stops and removes the task but keeps your files.

## Troubleshooting

| Problem | What to do |
| --- | --- |
| PowerShell cannot find a project file | Return to the folder containing `bridge.py` using `Set-Location`. |
| Configuration says it already exists | Keep it if this is your working setup. To change microphones, stop the task, back up and rename `config.json`, then repeat Steps 3–6. New webhook IDs must also be updated in HA. |
| Wave Link is unavailable or its port file is missing | Open Wave Link 3 under the same Windows account. Confirm the microphone is connected. |
| State is UNKNOWN or never changes | Check the selected input and hardware connection. Your model or control may not expose the required mute state. Do not enable live mode until the test passes. |
| Live mode says semantics are not verified | Complete Step 4, then set `semantics_verified` to JSON boolean `true` and save. |
| HA delivery failed | Check the base URL, port, firewall, and that the PC can reach HA over the LAN. |
| HA accepted, but the light does nothing | Check HA automation traces, matching webhook IDs, enabled automations, and the light entity. |
| A bridge is already running | Stop the scheduled task and any foreground bridge before another manual test. |
| It works manually but not after login | Check Task Scheduler and `logs/bridge.log`. Confirm Wave Link starts and the project folder has not moved. |

### Capture events for troubleshooting

Stop the scheduled task first:

```powershell
Stop-ScheduledTask -TaskName WaveHA-Bridge-v3
```

Run a one-minute dry-run capture and operate the mute control during that minute:

```powershell
.\.venv\Scripts\python.exe bridge.py --capture --seconds 60
```

After it finishes, restart the task:

```powershell
Start-ScheduledTask -TaskName WaveHA-Bridge-v3
```

Captures are stored in `logs/events.jsonl`. They can contain device identifiers; redact them before posting an issue. Never share `config.json` or your webhook IDs.

## Compatibility and behavior

- **Verified:** Wave:3 hardware touch mute and software microphone mute on Wave Link 3.3.0.4529, Windows, Python 3.13.
- **Other Wave models:** may work if Wave Link exposes an input-level boolean `isMuted`; verify each control before enabling live mode.
- **Not covered:** mixer-channel, per-mix, Windows endpoint, or conferencing-app mute.
- **Not supported:** Wave Link 2, macOS, or Linux.
- This is an unofficial community bridge, not an Elgato product.

The bridge discovers Wave Link's port on each connection, listens for input changes, and refreshes state every five seconds. It reconnects automatically and retries failed webhook requests using the latest known state.

Unchanged states are deduplicated. A new process sends its fresh initial state once. When the microphone is missing or disconnected, the bridge sends nothing and HA retains its last state. Restart the bridge if you need to resync after an HA restart.

Use actions that **set** a state, such as turn on/off, rather than toggle: an HTTP timeout can occasionally cause a retry after HA has already accepted a request. This is not a safety-critical mute indicator.

<details>
<summary>Technical details and development</summary>

The local API connection uses:

- Port file: `%LOCALAPPDATA%\Packages\Elgato.WaveLink_g54w8ztgkx496\LocalState\ws-info.json`
- WebSocket: `ws://127.0.0.1:<discovered-port>`
- Origin: `streamdeck://` (a handshake header; no Stream Deck installation required)
- Read methods: `getApplicationInfo`, `getInputDevices`
- Notifications: `inputDeviceChanged`, `inputDevicesChanged`

The bridge matches exact device and input IDs. It never sends setters to change microphone settings. Reconnect backoff is capped at about 30 seconds. Logs rotate automatically; high-volume meter events are excluded from captures.

Run tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s . -p test_bridge.py
```

Build a public-file-only ZIP:

```powershell
.\package-release.ps1
```

The output is `dist/wave-ha-bridge-v3.zip`. Use its extracted contents for GitHub browser uploads. The working folder contains private configuration and logs that must not be published; `.gitignore` does not filter browser uploads.

Hardware/software mute and a physical light test passed on the verified setup. Physical reboot, port-change, unplug/replug, and HA outage testing still need broader coverage.

</details>

## References

- [Home Assistant webhook documentation](https://www.home-assistant.io/triggers/webhook/)
- [WaveLink.Client protocol notes](https://github.com/Agash/WaveLink.Client/blob/main/PROTOCOL.md)
- [Unofficial node-wave-link-sdk](https://github.com/DarrellVS/node-wave-link-sdk)
- [wavelink-knob connection notes](https://github.com/idlewatts/wavelink-knob)

Community documentation guided development; live Wave:3 events determined the tested mute mapping.
