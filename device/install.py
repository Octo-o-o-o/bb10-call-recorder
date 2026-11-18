"""Install, start, stop and uninstall the BB10 Call Recorder background service."""
import json
import os
import shutil
import signal
import subprocess
import sys
import time

import native_io as nio
import service

DEVICE_MODULES = (
    'native_io.py',
    'pps_calls.py',
    'wav_writer.py',
    'qsa_fallback.py',
    'pcm_mixer.py',
    'service.py',
    'install.py',
    'boot.sh',
)
ADDON_DIR = '/var/addons/bb10-call-recorder/init'
ADDON_START = ADDON_DIR + '/start.sh'


def stop_daemon(base=service.BASE):
    alive, pid = service.daemon_alive(base)
    if not alive or not pid:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return False
    deadline = time.time() + 5.0
    while time.time() < deadline:
        still_alive, _ = service.daemon_alive(base)
        if not still_alive:
            return True
        time.sleep(0.1)
    return False


def start_daemon(base=service.BASE):
    alive, pid = service.daemon_alive(base)
    if alive:
        return {'started': False, 'already_running': True, 'pid': pid}
    boot_script = base + '/device/boot.sh'
    if os.path.isfile('/proc/boot/pathtrust'):
        nio.run_command(['/proc/boot/pathtrust', '!' + boot_script], timeout=10)
    devnull = os.open('/dev/null', os.O_RDWR)
    try:
        subprocess.Popen(['/bin/sh', boot_script], stdin=devnull, stdout=devnull, stderr=devnull, close_fds=True)
    finally:
        os.close(devnull)
    deadline = time.time() + 6.0
    while time.time() < deadline:
        alive, pid = service.daemon_alive(base)
        if alive:
            return {'started': True, 'pid': pid}
        time.sleep(0.15)
    return {'started': False, 'pid': None}


def install_from(source_dir, base=service.BASE, autostart=True):
    if os.geteuid() != 0:
        raise RuntimeError('root_required')
    stop_daemon(base)
    target_device = base + '/device'
    nio.ensure_dir(base, mode=0o700)
    nio.ensure_dir(target_device, mode=0o700)
    installed = {}
    for name in DEVICE_MODULES:
        src = source_dir.rstrip('/') + '/' + name
        raw = nio.read_bytes(src)
        dst = target_device + '/' + name
        mode = 0o700 if name.endswith('.sh') else 0o600
        nio.atomic_write(dst, raw, mode=mode)
        installed[name] = nio.sha256_hex(raw)
        if os.path.isfile('/proc/boot/pathtrust'):
            nio.run_command(['/proc/boot/pathtrust', '!' + dst], timeout=10)

    if not os.path.isfile(service.paths(base)['config']):
        service.save_config({}, base=base)
    nio.ensure_dir(service.INTERNAL_VOICE_DIR, mode=0o775, shared_media=True)

    if autostart and os.path.isdir('/var/addons'):
        nio.ensure_dir('/var/addons/bb10-call-recorder', mode=0o755)
        nio.ensure_dir(ADDON_DIR, mode=0o755)
        launcher = (b'#!/bin/sh\n'
                    b'/proc/boot/pathtrust "!/var/bb10_call_recorder/device/boot.sh" || exit 1\n'
                    b'exec /bin/sh /var/bb10_call_recorder/device/boot.sh\n')
        nio.atomic_write(ADDON_START, launcher, mode=0o755)
        if os.path.isfile('/proc/boot/pathtrust'):
            nio.run_command(['/proc/boot/pathtrust', '!' + ADDON_START], timeout=10)

    nio.save_json(base + '/manifest.json', {'schema': 1, 'files': installed}, mode=0o600)
    daemon_info = start_daemon(base) if autostart else {'started': False}
    return {'installed': True, 'files': len(installed), 'daemon': daemon_info}


def uninstall(base=service.BASE, keep_recordings=True):
    if os.geteuid() != 0:
        raise RuntimeError('root_required')
    stop_daemon(base)
    try:
        service.set_volte_tap(False)
    except Exception:
        pass
    if os.path.isfile(ADDON_START) and not os.path.islink(ADDON_START):
        os.unlink(ADDON_START)
    addon_root = '/var/addons/bb10-call-recorder'
    if os.path.isdir(addon_root) and not os.path.islink(addon_root):
        shutil.rmtree(addon_root, ignore_errors=True)
    if os.path.isdir(base) and not os.path.islink(base):
        shutil.rmtree(base, ignore_errors=True)
    if not keep_recordings and os.path.isdir(service.INTERNAL_VOICE_DIR):
        shutil.rmtree(service.INTERNAL_VOICE_DIR, ignore_errors=True)
    return {'uninstalled': True, 'recordings_preserved': bool(keep_recordings)}


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    action = args[0] if args else 'status'
    here = os.path.dirname(os.path.abspath(__file__))
    if action == 'install':
        src = args[1] if len(args) >= 2 else here
        print(json.dumps(install_from(src), sort_keys=True))
        return 0
    if action == 'start':
        print(json.dumps(start_daemon(), sort_keys=True))
        return 0
    if action == 'stop':
        print(json.dumps({'stopped': stop_daemon()}, sort_keys=True))
        return 0
    if action == 'uninstall':
        print(json.dumps(uninstall(keep_recordings=True), sort_keys=True))
        return 0
    if action == 'status':
        print(json.dumps(service.read_status(), sort_keys=True))
        return 0
    raise SystemExit('Unknown action: ' + repr(action))


if __name__ == '__main__':
    sys.exit(main())
