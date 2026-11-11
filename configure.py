"""Read-only microphone discovery and private local configuration wizard."""
import json
import secrets
import time

import websocket

from bridge import ROOT, port_from_file, validate_config


def discover():
    ws = websocket.create_connection(
        f'ws://127.0.0.1:{port_from_file()}', origin='streamdeck://',
        timeout=2, http_no_proxy=['127.0.0.1'])
    try:
        results = {}
        for number, method in enumerate(('getApplicationInfo', 'getInputDevices'), 1):
            ws.send(json.dumps({'jsonrpc': '2.0', 'id': number, 'method': method, 'params': None}))
        deadline = time.monotonic() + 10
        while len(results) < 2 and time.monotonic() < deadline:
            try:
                raw = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            if not raw:
                raise ConnectionError('Wave Link closed the connection')
            obj = json.loads(raw)
            if isinstance(obj, dict) and obj.get('id') in (1, 2):
                if 'error' in obj:
                    raise ValueError('Wave Link rejected a discovery request')
                results[obj['id']] = obj.get('result', {})
        app = results.get(1, {})
        if app.get('appID') != 'EWL' or not str(app.get('version', '')).startswith('3.'):
            raise ValueError('Wave Link 3.x was not identified')
        if 2 not in results:
            raise TimeoutError('No input-device response')
        return app, results[2].get('inputDevices', [])
    finally:
        ws.close()


def candidates(devices):
    return [(device, item) for device in devices for item in device.get('inputs', [])
            if type(item.get('isMuted')) is bool and device.get('id') and item.get('id')]


def main():
    path = ROOT / 'config.json'
    if path.exists():
        print('config.json already exists. Setup will not overwrite it.')
        print('Back it up and rename it before configuring a different microphone.')
        return 1
    app, devices = discover()
    choices = candidates(devices)
    print('Connected to Wave Link ' + app['version'])
    if not choices:
        print('No input exposes a boolean mute state. This installation is not supported yet.')
        return 1
    for number, (device, item) in enumerate(choices, 1):
        print(f"{number}. {device.get('name', 'Device')} / {item.get('name', 'Input')}")
    while True:
        try:
            index = int(input('Select your Wave microphone number: ')) - 1
            if 0 <= index < len(choices):
                break
        except ValueError:
            pass
        print('Enter one of the listed numbers.')
    device, item = choices[index]
    config = {
        'device_id': device['id'], 'input_id': item['id'],
        'semantics_verified': False,
        'ha_base': input('Home Assistant base URL [http://homeassistant.local:8123]: ').strip() or 'http://homeassistant.local:8123',
        'muted_webhook': secrets.token_urlsafe(32),
        'unmuted_webhook': secrets.token_urlsafe(32),
    }
    validate_config(config)
    with path.open('x', encoding='utf-8') as file:
        json.dump(config, file, indent=2)
        file.write('\n')
    print('Created private config.json with two random webhook IDs.')
    print('Follow README.md to create HA automations, verify both mute controls, and enable live mode.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, websocket.WebSocketException) as exc:
        print('Setup failed (' + type(exc).__name__ + '). Check that Wave Link 3 is running in this Windows account.')
        raise SystemExit(1)
    except (KeyboardInterrupt, EOFError):
        print('\nSetup cancelled.')
        raise SystemExit(1)
