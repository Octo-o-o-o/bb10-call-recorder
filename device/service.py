"""Recorder service, configuration store and catalog manager (Python 3.2+)."""
import json
import os
import re
import signal
import sys
import time

import native_io as nio
import pcm_mixer
import pps_calls
import qsa_fallback
import wav_writer

BASE = '/var/bb10_call_recorder'
ADDON_START = '/var/addons/bb10-call-recorder/init/start.sh'
VOLTE_BASE = '/var/bb10_volte'
VOLTE_TAP_FLAG = VOLTE_BASE + '/audio-tap.json'
INTERNAL_VOICE_DIR = '/accounts/1000/shared/voice/bb10-call-recorder'
SDCARD_ROOT = '/accounts/1000/removable/sdcard'
SDCARD_VOICE_DIR = SDCARD_ROOT + '/voice/bb10-call-recorder'
SAFE_ID = re.compile(r'^[0-9]{8}_[0-9]{6}_[a-z0-9]{4,16}$')

DEFAULT_CONFIG = {
    'schema': 1,
    'enabled': True,
    'trigger_mode': 'auto',        # 'auto' | 'manual'
    'channel_mode': 'stereo',      # 'stereo' | 'mono'
    'storage_location': 'internal',  # 'internal' | 'sdcard'
    'include_number': False,
    'consent_acknowledged': False,
    'language': 'zh',
}


def paths(base=BASE):
    return {
        'base': base,
        'config': base + '/config.json',
        'state': base + '/state.json',
        'pid': base + '/daemon.pid',
        'command': base + '/command.json',
    }


def load_config(base=BASE):
    cfg = dict(DEFAULT_CONFIG)
    raw = nio.load_json(paths(base)['config'], {})
    if isinstance(raw, dict):
        if raw.get('enabled') in (True, False):
            cfg['enabled'] = raw['enabled']
        if raw.get('trigger_mode') in ('auto', 'manual'):
            cfg['trigger_mode'] = raw['trigger_mode']
        if raw.get('channel_mode') in ('stereo', 'mono'):
            cfg['channel_mode'] = raw['channel_mode']
        if raw.get('storage_location') in ('internal', 'sdcard'):
            cfg['storage_location'] = raw['storage_location']
        if raw.get('include_number') in (True, False):
            cfg['include_number'] = raw['include_number']
        if raw.get('consent_acknowledged') in (True, False):
            cfg['consent_acknowledged'] = raw['consent_acknowledged']
        if raw.get('language') in ('zh', 'en'):
            cfg['language'] = raw['language']
    return cfg


def save_config(updates, base=BASE):
    nio.ensure_dir(base, mode=0o700)
    cfg = load_config(base)
    if isinstance(updates, dict):
        for key in ('enabled', 'trigger_mode', 'channel_mode',
                    'storage_location', 'include_number', 'consent_acknowledged', 'language'):
            if key in updates:
                cfg[key] = updates[key]
    validated = dict(DEFAULT_CONFIG)
    validated.update(cfg)
    nio.save_json(paths(base)['config'], validated, mode=0o600)
    return load_config(base)


def output_directory(cfg):
    if cfg.get('storage_location') == 'sdcard' and os.path.isdir(SDCARD_ROOT):
        return SDCARD_VOICE_DIR
    return INTERNAL_VOICE_DIR


def index_path(folder):
    return folder + '/index.json'


def list_recordings(base=BASE):
    cfg = load_config(base)
    folders = [INTERNAL_VOICE_DIR]
    if os.path.isdir(SDCARD_ROOT):
        folders.append(SDCARD_VOICE_DIR)
    items = []
    seen = set()
    for folder in folders:
        idx = nio.load_json(index_path(folder), {'schema': 1, 'items': []})
        entries = idx.get('items', []) if isinstance(idx, dict) else []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            rec_id = str(entry.get('id', ''))
            wav_path = str(entry.get('path', ''))
            if not SAFE_ID.match(rec_id) or rec_id in seen:
                continue
            if not os.path.isfile(wav_path) or os.path.islink(wav_path):
                continue
            seen.add(rec_id)
            item = dict(entry)
            item['bytes'] = int(os.path.getsize(wav_path))
            items.append(item)
    items.sort(key=lambda x: x.get('started_at', 0), reverse=True)
    return {'recordings': items[:200], 'active_folder': output_directory(cfg)}


def append_recording_index(folder, meta):
    nio.ensure_dir(folder, mode=0o775, shared_media=True)
    path = index_path(folder)
    current = nio.load_json(path, {'schema': 1, 'items': []})
    items = current.get('items', []) if isinstance(current, dict) else []
    filtered = [x for x in items if isinstance(x, dict) and x.get('id') != meta.get('id')]
    filtered.insert(0, meta)
    nio.save_json(path, {'schema': 1, 'items': filtered[:500]}, mode=0o664)
    nio.make_shared_readable(path, mode=0o664)


def delete_recording(rec_id, base=BASE):
    if not SAFE_ID.match(str(rec_id or '')):
        raise ValueError('invalid_recording_id')
    removed = False
    for folder in (INTERNAL_VOICE_DIR, SDCARD_VOICE_DIR):
        if not os.path.isdir(folder):
            continue
        path = index_path(folder)
        current = nio.load_json(path, {'schema': 1, 'items': []})
        items = current.get('items', []) if isinstance(current, dict) else []
        kept = []
        for entry in items:
            if isinstance(entry, dict) and entry.get('id') == rec_id:
                wav_path = str(entry.get('path', ''))
                norm_wav = wav_path.replace('\\', '/')
                norm_dir = folder.replace('\\', '/').rstrip('/') + '/'
                if norm_wav.startswith(norm_dir) and os.path.isfile(wav_path) and not os.path.islink(wav_path):
                    os.unlink(wav_path)
                    removed = True
            else:
                kept.append(entry)
        if len(kept) != len(items):
            nio.save_json(path, {'schema': 1, 'items': kept}, mode=0o644)
    return {'deleted': removed, 'id': rec_id}


def volte_tap_status(volte_base=VOLTE_BASE):
    installed = os.path.isdir(volte_base)
    flag_path = volte_base + '/audio-tap.json'
    opt_in = False
    if os.path.isfile(flag_path) and not os.path.islink(flag_path):
        data = nio.load_json(flag_path, {})
        opt_in = bool(isinstance(data, dict) and data.get('schema') == 1 and data.get('enabled') is True)
    return {
        'volte_installed': installed,
        'volte_tap_configured': opt_in,
    }


def set_volte_tap(enabled, volte_base=VOLTE_BASE):
    if not os.path.isdir(volte_base):
        raise RuntimeError('volte_not_installed')
    flag_path = volte_base + '/audio-tap.json'
    if enabled:
        nio.save_json(flag_path, {
            'schema': 1,
            'enabled': True,
            'owner': 'com.octolab.bb10recorder',
            'updated_at': int(time.time()),
        }, mode=0o600)
    else:
        if os.path.exists(flag_path) and not os.path.islink(flag_path):
            os.unlink(flag_path)
    return volte_tap_status(volte_base)


def daemon_alive(base=BASE):
    info = nio.load_json(paths(base)['pid'], {})
    pid = info.get('pid') if isinstance(info, dict) else None
    if not isinstance(pid, int) or pid <= 1:
        return False, None
    try:
        os.kill(pid, 0)
        return True, pid
    except OSError:
        return False, None


def read_status(base=BASE, volte_base=VOLTE_BASE):
    cfg = load_config(base)
    alive, pid = daemon_alive(base)
    runtime_state = nio.load_json(paths(base)['state'], {})
    if not isinstance(runtime_state, dict):
        runtime_state = {}
    calls_info = pps_calls.read_calls_snapshot()
    decision = pps_calls.evaluate_recording_decision(calls_info['calls'])
    folder = output_directory(cfg)
    tap = volte_tap_status(volte_base)
    return {
        'schema': 1,
        'installed': os.path.isfile(base + '/device/service.py'),
        'daemon_alive': alive,
        'daemon_pid': pid,
        'config': cfg,
        'recording_active': bool(alive and runtime_state.get('recording_active')),
        'active_engine': runtime_state.get('active_engine') if alive else None,
        'active_recording_id': runtime_state.get('active_id') if alive else None,
        'active_seconds': runtime_state.get('active_seconds', 0.0) if alive else 0.0,
        'call_state': decision['reason'],
        'call_eligible': decision['eligible'],
        'sd_available': os.path.isdir(SDCARD_ROOT),
        'output_folder': folder,
        'free_mb': int(nio.free_space_bytes(folder) // (1024 * 1024)),
        'volte_installed': tap['volte_installed'],
        'volte_tap_configured': tap['volte_tap_configured'],
    }


def send_daemon_command(action, base=BASE):
    if action not in ('start_manual', 'stop_manual'):
        raise ValueError('invalid_command')
    nio.ensure_dir(base, mode=0o700)
    nio.save_json(paths(base)['command'], {'action': action, 'at': time.time()}, mode=0o600)
    return {'queued': action}


def run_daemon(base=BASE, max_loops=None):
    try:
        if hasattr(os, 'setsid'):
            os.setsid()
    except OSError:
        pass
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
    nio.ensure_dir(base, mode=0o700)
    alive, existing = daemon_alive(base)
    if alive and existing != os.getpid():
        return 0
    nio.save_json(paths(base)['pid'], {'pid': os.getpid(), 'started_at': time.time()}, mode=0o600)
    stop_flag = {'stop': False}

    def _handle_sig(signum, frame):
        stop_flag['stop'] = True

    signal.signal(signal.SIGTERM, _handle_sig)
    signal.signal(signal.SIGINT, _handle_sig)

    session = None
    manual_override = None  # None | 'force_on' | 'force_off'
    loops = 0
    last_poll = 0.0
    cfg = load_config(base)
    decision = {'eligible': False, 'hold_only': False, 'reason': 'idle', 'primary': None}

    def _close_session():
        if session is None:
            return
        try:
            if session.get('qsa') is not None:
                session['qsa'].close()
        except Exception:
            pass
        writer = session.get('writer')
        if writer is not None:
            duration = writer.duration_seconds()
            try:
                writer.close(remove_if_empty=True)
            except Exception:
                pass
            if writer.data_bytes > 0 and os.path.isfile(writer.filepath):
                meta = dict(session['meta'])
                meta['duration_sec'] = duration
                meta['bytes'] = int(os.path.getsize(writer.filepath))
                meta['stopped_low_disk'] = bool(writer.stopped_low_disk)
                append_recording_index(session['folder'], meta)
        nio.save_json(paths(base)['state'], {
            'recording_active': False,
            'active_engine': None,
            'active_id': None,
            'active_seconds': 0.0,
            'updated_at': time.time(),
        }, mode=0o600)

    try:
        while not stop_flag['stop']:
            loops += 1
            if max_loops is not None and loops > max_loops:
                break

            now = time.time()
            if session is None or (now - last_poll) >= 0.25:
                last_poll = now
                cmd_path = paths(base)['command']
                if os.path.isfile(cmd_path):
                    cmd = nio.load_json(cmd_path, {})
                    try:
                        os.unlink(cmd_path)
                    except OSError:
                        pass
                    if isinstance(cmd, dict):
                        if cmd.get('action') == 'start_manual':
                            manual_override = 'force_on'
                        elif cmd.get('action') == 'stop_manual':
                            manual_override = 'force_off'

                cfg = load_config(base)
                snap = pps_calls.read_calls_snapshot()
                decision = pps_calls.evaluate_recording_decision(snap['calls'])

            if not decision['eligible'] and not (session is not None and decision['hold_only']):
                if session is not None:
                    _close_session()
                    session = None
                manual_override = None
                time.sleep(0.35)
                continue

            want_record = False
            if cfg.get('enabled') and cfg.get('consent_acknowledged'):
                if manual_override == 'force_on':
                    want_record = True
                elif manual_override == 'force_off':
                    want_record = False
                elif cfg.get('trigger_mode') == 'auto':
                    want_record = True
            elif manual_override == 'force_on' and cfg.get('consent_acknowledged'):
                want_record = True

            if not want_record:
                if session is not None:
                    _close_session()
                    session = None
                time.sleep(0.3)
                continue

            if session is None and decision['eligible']:
                try:
                    # Brief settle delay so IMS/Phone audio routing finishes binding first
                    time.sleep(0.25)
                    primary = decision['primary'] or {}
                    stamp = time.strftime('%Y%m%d_%H%M%S', time.localtime())
                    suffix = '%04x' % (int(time.time() * 1000) & 0xffff)
                    rec_id = '%s_%s' % (stamp, suffix)
                    folder = output_directory(cfg)
                    wav_path = folder + '/' + rec_id + '.wav'
                    qsa = qsa_fallback.QsaMicCapture()
                    qsa.start()
                    writer = wav_writer.StreamingWavWriter(wav_path, sample_rate=16000, channels=1)
                    peer = pps_calls.mask_number(primary.get('number', ''), keep_number=cfg.get('include_number', False))
                    session = {
                        'id': rec_id,
                        'folder': folder,
                        'qsa': qsa,
                        'writer': writer,
                        'engine': 'qsa_mic',
                        'last_state_sync': 0.0,
                        'meta': {
                            'id': rec_id,
                            'path': wav_path,
                            'filename': rec_id + '.wav',
                            'started_at': int(time.time()),
                            'engine': 'qsa_mic',
                            'sample_rate': 16000,
                            'channels': 1,
                            'peer': peer,
                            'connection_type': primary.get('connection_type') or 'unknown',
                        },
                    }
                except Exception:
                    time.sleep(0.5)
                    continue

            if session is not None:
                try:
                    chunk = session['qsa'].read_chunk(apply_gain=True)
                except Exception:
                    # Re-open QSA handle if audio routing changed mid-call (e.g. speakerphone toggle)
                    try:
                        session['qsa'].close()
                    except Exception:
                        pass
                    time.sleep(0.15)
                    try:
                        reopened = qsa_fallback.QsaMicCapture()
                        reopened.start()
                        session['qsa'] = reopened
                    except Exception:
                        time.sleep(0.3)
                    continue

                if chunk:
                    ok = session['writer'].write_pcm(chunk)
                    if not ok:
                        _close_session()
                        session = None
                        manual_override = 'force_off'
                        continue
                now2 = time.time()
                if (now2 - session['last_state_sync']) >= 2.0:
                    session['last_state_sync'] = now2
                    nio.save_json(paths(base)['state'], {
                        'recording_active': True,
                        'active_engine': session['engine'],
                        'active_id': session['id'],
                        'active_seconds': session['writer'].duration_seconds(),
                        'updated_at': now2,
                    }, mode=0o600)
    finally:
        if session is not None:
            _close_session()
        try:
            if os.path.isfile(paths(base)['pid']):
                os.unlink(paths(base)['pid'])
        except OSError:
            pass
    return 0


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    action = args[0] if args else 'status'
    if action == 'daemon':
        return run_daemon()
    if action == 'status':
        print(json.dumps(read_status(), sort_keys=True))
        return 0
    if action == 'list':
        print(json.dumps(list_recordings(), sort_keys=True))
        return 0
    if action == 'start-manual':
        print(json.dumps(send_daemon_command('start_manual'), sort_keys=True))
        return 0
    if action == 'stop-manual':
        print(json.dumps(send_daemon_command('stop_manual'), sort_keys=True))
        return 0
    if action == 'delete' and len(args) >= 2:
        print(json.dumps(delete_recording(args[1]), sort_keys=True))
        return 0
    if action == 'enable-volte-tap':
        print(json.dumps(set_volte_tap(True), sort_keys=True))
        return 0
    if action == 'disable-volte-tap':
        print(json.dumps(set_volte_tap(False), sort_keys=True))
        return 0
    if action == 'set-config' and len(args) >= 2:
        updates = json.loads(args[1])
        print(json.dumps(save_config(updates), sort_keys=True))
        return 0
    raise SystemExit('Unknown action: ' + repr(action))


if __name__ == '__main__':
    sys.exit(main())
