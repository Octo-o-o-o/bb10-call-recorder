"""Mobile app management bridge executed under /bin/__root (Python 3.2+)."""
import base64
import json
import os
import sys


def _load_device_modules(bundle_root):
    device_dir = os.path.join(bundle_root, 'device')
    if os.path.isdir('/var/bb10_call_recorder/device') and not os.path.isdir(device_dir):
        device_dir = '/var/bb10_call_recorder/device'
    if device_dir not in sys.path:
        sys.path.insert(0, device_dir)
    import service
    import install
    return service, install, device_dir


def dispatch(bundle_root, action, payload_b64=''):
    service, install, device_dir = _load_device_modules(bundle_root)
    payload = {}
    if payload_b64:
        raw = base64.b64decode(payload_b64.encode('ascii'))
        payload = json.loads(raw.decode('utf-8'))
    if action == 'status':
        result = service.read_status()
        result['recordings'] = service.list_recordings()['recordings']
        return result
    if action == 'install':
        res = install.install_from(device_dir, autostart=True)
        out = service.read_status()
        out['install_result'] = res
        out['recordings'] = service.list_recordings()['recordings']
        return out
    if action == 'set-config':
        service.save_config(payload)
        if payload.get('enabled') and not service.daemon_alive()[0]:
            install.start_daemon()
        out = service.read_status()
        out['recordings'] = service.list_recordings()['recordings']
        return out
    if action == 'start-manual':
        if not service.daemon_alive()[0]:
            install.start_daemon()
        service.send_daemon_command('start_manual')
        out = service.read_status()
        out['recordings'] = service.list_recordings()['recordings']
        return out
    if action == 'stop-manual':
        service.send_daemon_command('stop_manual')
        out = service.read_status()
        out['recordings'] = service.list_recordings()['recordings']
        return out
    if action == 'set-volte-tap':
        service.set_volte_tap(bool(payload.get('enabled')))
        out = service.read_status()
        out['recordings'] = service.list_recordings()['recordings']
        return out
    if action == 'delete-recording':
        service.delete_recording(payload.get('id', ''))
        out = service.read_status()
        out['recordings'] = service.list_recordings()['recordings']
        return out
    if action == 'uninstall':
        install.uninstall(keep_recordings=True)
        out = service.read_status()
        out['recordings'] = service.list_recordings()['recordings']
        return out
    if action == 'qsa-selftest':
        import qsa_fallback
        import time
        cap = qsa_fallback.QsaMicCapture()
        cap.start()
        total_bytes = 0
        try:
            deadline = time.time() + 1.0
            while time.time() < deadline:
                chunk = cap.read_chunk(apply_gain=True)
                total_bytes += len(chunk)
        finally:
            cap.close()
        return {'qsa_16k_mono_ok': total_bytes > 0, 'bytes_read_1s': total_bytes, 'fragment': cap._fragment}
    raise ValueError('unsupported_action:' + str(action))


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    bundle_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    action = args[0] if args else 'status'
    payload_b64 = args[1] if len(args) >= 2 else ''
    try:
        response = {'ok': True, 'data': dispatch(bundle_root, action, payload_b64)}
    except Exception as exc:
        response = {'ok': False, 'error': str(exc)}
    print(json.dumps(response, ensure_ascii=True, sort_keys=True))
    return 0 if response.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
