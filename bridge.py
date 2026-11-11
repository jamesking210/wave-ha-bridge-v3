"""Wave Link 3 input mute -> Home Assistant. Default is dry-run."""
import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import random
import time
import urllib.request
import websocket

ROOT = Path(__file__).resolve().parent
PORT_FILE = Path(os.environ.get('LOCALAPPDATA', '')) / 'Packages/Elgato.WaveLink_g54w8ztgkx496/LocalState/ws-info.json'
LOG = logging.getLogger('bridge')


def port_from_file(path=PORT_FILE):
    port = json.loads(path.read_text(encoding='utf-8-sig'))['port']
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Invalid local port')
    return port


def input_mute(device, config):
    if device.get('id') != config['device_id']:
        return None
    for item in device.get('inputs', []):
        if item.get('id') == config['input_id']:
            value = item.get('isMuted')
            return value if type(value) is bool else None
    return None


def snapshot_mute(result, config):
    devices = result.get('inputDevices')
    if not isinstance(devices, list):
        return None
    for device in devices:
        value = input_mute(device, config)
        if value is not None:
            return value
    return None


def post_state(config, muted):
    key = 'muted_webhook' if muted else 'unmuted_webhook'
    url = config['ha_base'].rstrip('/') + '/api/webhook/' + config[key]
    request = urllib.request.Request(url, data=b'', method='POST')
    # LAN calls must not be sent through an environment-configured HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=3) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError('Webhook did not return success')


class Delivery:
    def __init__(self, config, live, sender=post_state):
        self.config, self.live, self.sender = config, live, sender
        self.current = self.delivered = None
        self.retry_at = 0

    def observe(self, value):
        if value is not self.current:
            self.current = value
            self.retry_at = 0
            LOG.info('Input state: %s', 'UNKNOWN' if value is None else ('MUTED' if value else 'UNMUTED'))

    def tick(self, now):
        if self.current is None or self.current is self.delivered or now < self.retry_at:
            return
        if not self.live:
            LOG.info('DRY RUN: would send %s', 'muted' if self.current else 'unmuted')
            self.delivered = self.current
            return
        try:
            self.sender(self.config, self.current)
        except Exception as exc:
            # Exception strings may include the webhook URL; log only its type.
            LOG.warning('HA delivery failed (%s); retry latest state in 5s', type(exc).__name__)
            self.retry_at = now + 5
        else:
            self.delivered = self.current
            LOG.info('HA accepted %s', 'muted' if self.current else 'unmuted')


def setup_logging(capture):
    (ROOT / 'logs').mkdir(exist_ok=True)
    LOG.setLevel(logging.INFO)
    for handler in (logging.StreamHandler(), RotatingFileHandler(ROOT / 'logs/bridge.log', maxBytes=1_000_000, backupCount=3, encoding='utf-8')):
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        LOG.addHandler(handler)
    events = logging.getLogger('events')
    events.setLevel(logging.INFO)
    if capture:
        events.addHandler(RotatingFileHandler(ROOT / 'logs/events.jsonl', maxBytes=2_000_000, backupCount=2, encoding='utf-8'))
    else:
        events.addHandler(logging.NullHandler())
    return events


def run(config, live, capture, seconds):
    events = setup_logging(capture)
    delivery = Delivery(config, live)
    finish = time.monotonic() + seconds if seconds else float('inf')
    delay = 1
    LOG.info('Starting %s; exact configured microphone input only', 'LIVE' if live else 'DRY RUN')
    while time.monotonic() < finish:
        ws = None
        try:
            port = port_from_file()
            ws = websocket.create_connection(f'ws://127.0.0.1:{port}', origin='streamdeck://', timeout=1, http_no_proxy=['127.0.0.1'])
            LOG.info('Connected on discovered port %d', port)
            ws.send(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'getApplicationInfo', 'params': None}))
            identified = False
            pending = None
            serial = 1
            next_poll = 0
            deadline = time.monotonic() + 8
            delivery.observe(None)
            while time.monotonic() < finish:
                now = time.monotonic()
                if now > deadline:
                    raise TimeoutError('Fresh snapshot timeout')
                if identified and pending is None and now >= next_poll:
                    serial += 1
                    pending = serial
                    ws.send(json.dumps({'jsonrpc': '2.0', 'id': serial, 'method': 'getInputDevices', 'params': None}))
                try:
                    raw = ws.recv()
                except websocket.WebSocketTimeoutException:
                    delivery.tick(time.monotonic())
                    continue
                if not raw:
                    raise ConnectionError('Socket closed')
                obj = json.loads(raw)
                if not isinstance(obj, dict):
                    continue
                method = obj.get('method')
                if method != 'levelMeterChanged' and capture:
                    events.info(json.dumps({'time': time.time(), 'message': obj}))
                if obj.get('id') == 1:
                    result = obj.get('result', {})
                    if result.get('appID') != 'EWL' or not str(result.get('version', '')).startswith('3.'):
                        raise ValueError('Unexpected Wave Link server/version')
                    identified = True
                    LOG.info('Wave Link %s', result.get('version'))
                elif identified and pending is not None and obj.get('id') == pending:
                    if 'error' in obj:
                        raise ValueError('Input query rejected')
                    delivery.observe(snapshot_mute(obj.get('result', {}), config))
                    pending = None
                    next_poll = now + 5
                    deadline = now + 13
                    delay = 1
                elif identified and method == 'inputDeviceChanged':
                    value = input_mute(obj.get('params', {}), config)
                    if value is not None:
                        delivery.observe(value)
                elif identified and method == 'inputDevicesChanged':
                    delivery.observe(snapshot_mute(obj.get('params', {}), config))
                delivery.tick(time.monotonic())
        except (OSError, ValueError, KeyError, websocket.WebSocketException) as exc:
            delivery.observe(None)
            LOG.warning('Wave Link unavailable (%s); rediscovering', type(exc).__name__)
        finally:
            if ws:
                ws.close()
        if time.monotonic() < finish:
            time.sleep(min(delay + random.random(), max(0, finish-time.monotonic())))
            delay = min(delay * 2, 30)


def validate_config(config):
    from urllib.parse import urlsplit
    for key in ('device_id', 'input_id', 'ha_base', 'muted_webhook', 'unmuted_webhook'):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError('Missing field: ' + key)
    base = urlsplit(config['ha_base'])
    if base.scheme not in ('http', 'https') or not base.hostname or base.username or base.password or base.query or base.fragment or base.path not in ('', '/'):
        raise ValueError('ha_base must be an HTTP(S) server URL without credentials or path')
    import re
    for key in ('muted_webhook', 'unmuted_webhook'):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', config[key]):
            raise ValueError('Webhook IDs must contain only letters, digits, underscores or hyphens')
    if config['muted_webhook'] == config['unmuted_webhook']:
        raise ValueError('Webhook IDs must differ')
    if type(config.get('semantics_verified')) is not bool:
        raise ValueError('semantics_verified must be true or false')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Enable verified HA webhook delivery')
    parser.add_argument('--capture', action='store_true', help='Capture local protocol frames except meters')
    parser.add_argument('--seconds', type=float, default=0, help='Stop after this duration; 0 runs indefinitely')
    args = parser.parse_args()
    try:
        config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8-sig'))
        validate_config(config)
    except (OSError, ValueError, KeyError) as exc:
        parser.error('Missing or invalid config.json. Run configure.py first. ' + type(exc).__name__)
    if args.live and config.get('semantics_verified') is not True:
        parser.error('Live mode requires verified mute semantics in config.json')
    # Lock is released by Windows even after a crash; prevents duplicate workers.
    import msvcrt
    with (ROOT / '.bridge.lock').open('a+b') as lock:
        try:
            if (ROOT / '.bridge.lock').stat().st_size == 0:
                lock.write(b'0')
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            parser.exit(2, 'A v3 bridge is already running. Stop its scheduled task first.\n')
        try:
            run(config, args.live, args.capture, args.seconds)
        except KeyboardInterrupt:
            LOG.info('Stopped')


if __name__ == '__main__':
    main()
