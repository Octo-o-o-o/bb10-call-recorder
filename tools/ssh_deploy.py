"""Deploy, inspect and control BB10 Call Recorder on a paired USB-SSH phone."""
import argparse
import base64
import json
from pathlib import Path

from bar_installer import inspect_bar_over_ssh, install_bar_over_ssh
from desktop_paths import resource_root
from usb_ssh import connect_phone


def stage_and_run(action, payload=None, conn=None, custom_config=''):
    conn = conn or connect_phone(custom_config=custom_config)
    root = resource_root()
    stage = '/var/bb10_call_recorder_stage'
    files = {}
    for item in sorted((root / 'device').iterdir()):
        if item.is_file() and item.suffix in ('.py', '.sh'):
            files['device/' + item.name] = item.read_text(encoding='utf-8').replace('\r\n', '\n')
    files['runtime/entry.py'] = (root / 'mobile/runtime/entry.py').read_text(encoding='utf-8').replace('\r\n', '\n')

    lines = [
        'set -e',
        'umask 077',
        'rm -rf ' + stage,
        'mkdir -p ' + stage + '/device ' + stage + '/runtime',
    ]
    for rel, content in sorted(files.items()):
        dst = stage + '/' + rel
        if 'BB10_RECORDER_EOF' in content:
            raise ValueError('Marker collision in ' + rel)
        lines.append("cat > " + dst + " <<'BB10_RECORDER_EOF'\n" + content.rstrip('\n') + "\nBB10_RECORDER_EOF")
        lines.append('chmod 700 ' + dst if rel.endswith('.sh') else 'chmod 600 ' + dst)
        lines.append('/proc/boot/pathtrust "!' + dst + '"')

    payload_arg = ''
    if payload:
        encoded = base64.b64encode(json.dumps(payload).encode('utf-8')).decode('ascii')
        payload_arg = ' ' + encoded

    lines.append(
        'LD_LIBRARY_PATH=/base/usr/lib:/base/lib:/base/lib/dll:/radio/lib:/radio/lib/dll:/radio/usr/lib:/proc/boot '
        'PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONHOME=/usr '
        'PYTHONPATH=/usr/lib/python32.zip:/usr/lib/python3.2/lib-dynload '
        '/usr/bin/python3.2 -B ' + stage + '/runtime/entry.py ' + action + payload_arg
    )
    lines.append('rm -rf ' + stage)
    out = conn.run_sh(lines, timeout=45)
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith('{'):
            parsed = json.loads(line)
            if not parsed.get('ok', True):
                raise RuntimeError(parsed.get('error', 'device_action_failed'))
            return parsed.get('data', parsed)
    return {'raw': out}


def inspect_full_phone(custom_config=''):
    conn = connect_phone(custom_config=custom_config)
    status = stage_and_run('status', conn=conn)
    try:
        app_info = inspect_bar_over_ssh(conn)
    except Exception as exc:
        app_info = {'state': 'pin_unavailable', 'error': str(exc)}
    status['mobile_app'] = app_info
    return status


def install_all(custom_config='', bar_override=None):
    conn = connect_phone(custom_config=custom_config)
    app_result = install_bar_over_ssh(conn, bar_override=bar_override)
    if app_result.get('state') != 'installed':
        raise RuntimeError(app_result.get('error') or ('bar_install_state:' + str(app_result.get('state'))))
    stage_and_run('install', conn=conn)
    stage_and_run('set-config', {'consent_acknowledged': True, 'enabled': True, 'trigger_mode': 'auto'}, conn=conn)
    status = stage_and_run('status', conn=conn)
    status['mobile_app'] = app_result
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=(
        'status', 'install', 'install-bar', 'install-all',
        'start-manual', 'stop-manual', 'uninstall',
        'enable-tap', 'disable-tap', 'qsa-selftest',
    ))
    parser.add_argument('--ssh-config', default='', help='Optional path to paired ssh_config')
    parser.add_argument('--bar', type=Path, help='Optional path to .bar file override')
    args = parser.parse_args()

    if args.action == 'install-bar':
        conn = connect_phone(custom_config=args.ssh_config)
        print(json.dumps(install_bar_over_ssh(conn, bar_override=args.bar), indent=2))
        return
    if args.action == 'install-all':
        print(json.dumps(install_all(custom_config=args.ssh_config, bar_override=args.bar), indent=2))
        return
    if args.action == 'status':
        print(json.dumps(inspect_full_phone(custom_config=args.ssh_config), indent=2))
        return
    if args.action == 'install':
        conn = connect_phone(custom_config=args.ssh_config)
        stage_and_run('install', conn=conn)
        stage_and_run('set-config', {'consent_acknowledged': True, 'enabled': True, 'trigger_mode': 'auto'}, conn=conn)
        print(json.dumps(stage_and_run('status', conn=conn), indent=2))
        return

    mapped = args.action
    payload = None
    if args.action == 'enable-tap':
        mapped, payload = 'set-volte-tap', {'enabled': True}
    elif args.action == 'disable-tap':
        mapped, payload = 'set-volte-tap', {'enabled': False}
    print(json.dumps(stage_and_run(mapped, payload, custom_config=args.ssh_config), indent=2))


if __name__ == '__main__':
    main()
