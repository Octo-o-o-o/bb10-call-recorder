"""BB10 PPS phone call parser and recording trigger state machine (Python 3.2+).

Verified against BB10 10.3.3.3216 ImsPhoneMonitor.cpp:
  Directory: /pps/services/phone/private/calls/ (fallback: public/calls)
  Attributes:
    - callstate: incoming | connecting | remote_ringing | connected |
                 multiparty | held | disconnected | failed | log_only | unknown
    - calltype:  emergency | voice | ...
    - callernumber: peer string
    - additional_info: JSON with connection_info.connection_type
                       ('ir_92' for VoLTE, 'circuit_switched' for 2G/3G CS)
"""
import json
import os
import re

import native_io as nio

PRIVATE_CALLS_DIR = '/pps/services/phone/private/calls'
PUBLIC_CALLS_DIR = '/pps/services/phone/public/calls'
ACTIVE_SPEECH_STATES = ('connected', 'multiparty')
HELD_STATES = ('held',)
PRE_CONNECT_STATES = ('incoming', 'connecting', 'remote_ringing', 'unknown')
TERMINAL_STATES = ('disconnected', 'failed', 'log_only')
SAFE_OBJECT_NAME = re.compile(r'^[A-Za-z0-9_.-]{1,80}$')


def parse_pps_object(raw):
    if isinstance(raw, bytes):
        text = raw.decode('utf-8', 'replace')
    else:
        text = str(raw)
    attrs = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('@'):
            continue
        line = re.sub(r'^\[[^\]]*\]', '', line)
        if ':' not in line:
            continue
        key, rest = line.split(':', 1)
        if ':' in rest:
            encoding, val = rest.split(':', 1)
            if encoding == 'json':
                try:
                    attrs[key] = json.loads(val)
                    continue
                except ValueError:
                    pass
            elif encoding == 'n':
                try:
                    attrs[key] = int(val)
                    continue
                except ValueError:
                    pass
            elif encoding == 'b':
                attrs[key] = (val.strip().lower() == 'true')
                continue
            attrs[key] = val
        else:
            attrs[key] = rest
    return attrs


def parse_call_entry(call_id, raw):
    attrs = parse_pps_object(raw)
    state = str(attrs.get('callstate', attrs.get('state', 'unknown'))).strip().lower()
    call_type = str(attrs.get('calltype', '')).strip().lower()
    raw_number = str(attrs.get('callernumber', attrs.get('number', ''))).strip()
    info = attrs.get('additional_info')
    if isinstance(info, str):
        try:
            info = json.loads(info)
        except ValueError:
            info = {}
    conn_info = info.get('connection_info', {}) if isinstance(info, dict) else {}
    if not isinstance(conn_info, dict):
        conn_info = {}
    conn_type = str(conn_info.get('connection_type', '')).strip().lower()
    conn_path = str(conn_info.get('connection_path', '')).strip().lower()
    is_emergency = (
        call_type == 'emergency' or
        raw_number in ('110', '112', '119', '120', '122', '911', '999') or
        raw_number.startswith('urn:service:sos')
    )
    return {
        'id': call_id,
        'state': state,
        'calltype': call_type,
        'is_emergency': is_emergency,
        'connection_type': conn_type,
        'connection_path': conn_path,
        'is_volte_hint': (conn_type == 'ir_92' or conn_path.startswith('ims')),
        'number': raw_number,
    }


def mask_number(number, keep_number=False):
    clean = re.sub(r'[^0-9+]', '', str(number or ''))
    if not clean:
        return 'unknown'
    if keep_number:
        return clean[:24]
    if len(clean) <= 4:
        return '****'
    return clean[:3] + '****' + clean[-2:]


def read_calls_snapshot(private_dir=PRIVATE_CALLS_DIR, public_dir=PUBLIC_CALLS_DIR):
    calls = []
    source_dir = private_dir if os.path.isdir(private_dir) else public_dir
    if not os.path.isdir(source_dir):
        return {'source': None, 'calls': []}
    try:
        names = sorted(os.listdir(source_dir))
    except (IOError, OSError):
        return {'source': source_dir, 'calls': []}
    for name in names[:16]:
        if name.startswith('.') or not SAFE_OBJECT_NAME.match(name):
            continue
        path = source_dir + '/' + name
        try:
            raw = nio.read_bytes(path, 65536)
        except (IOError, OSError):
            continue
        calls.append(parse_call_entry(name, raw))
    return {'source': source_dir, 'calls': calls}


def evaluate_recording_decision(calls):
    """Determine whether an active, non-emergency connected call exists.

     rules:
      - If ANY call is an emergency call: immediately refuse/stop recording.
      - Recording starts ONLY when at least one call is in ACTIVE_SPEECH_STATES.
      - If a recording is ALREADY running and remaining call(s) are in HELD_STATES,
        keep the session alive (`hold_only=True`) until speech resumes or ends.
      - Ringing/dialing (`incoming`, `connecting`, `remote_ringing`) NEVER starts
        a recording prematurely.
    """
    if any(c.get('is_emergency') for c in calls):
        return {'eligible': False, 'hold_only': False, 'reason': 'emergency_call_excluded', 'primary': None}
    speaking = [c for c in calls if c.get('state') in ACTIVE_SPEECH_STATES]
    if speaking:
        primary = speaking[0]
        return {'eligible': True, 'hold_only': False, 'reason': 'connected', 'primary': primary}
    held = [c for c in calls if c.get('state') in HELD_STATES]
    if held:
        return {'eligible': False, 'hold_only': True, 'reason': 'call_on_hold', 'primary': held[0]}
    ringing = [c for c in calls if c.get('state') in PRE_CONNECT_STATES]
    if ringing:
        return {'eligible': False, 'hold_only': False, 'reason': 'waiting_for_answer', 'primary': ringing[0]}
    return {'eligible': False, 'hold_only': False, 'reason': 'idle', 'primary': None}
