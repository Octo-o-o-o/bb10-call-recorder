"""Pin and install the native BB10 Call Recorder BAR over paired USB-SSH."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import uuid
import zipfile

from bar_installer_device import PACKAGE_NAME, headers
from desktop_paths import private_root, resource_root

PIN_REL = 'materials/mobile-app-artifact.json'
HELPER_REL = 'tools/bar_installer_device.py'
BUNDLED_BAR_REL = 'assets/mobile/bb10-call-recorder.bar'
INSTALLER_SHA256 = 'b5b98e0ad73c944810bd4d9135386f9d83b01a630fcbd077d9c2a2de9b65e740'
ENV = (
    'unset PYTHONOPTIMIZE PYTHONINSPECT PYTHONSTARTUP PYTHONUSERBASE PYTHONPATH PYTHONHOME LD_PRELOAD ENV BASH_ENV; '
    'export PATH=/proc/boot:/bin:/usr/bin:/base/bin:/base/usr/bin; '
    'export LD_LIBRARY_PATH=/base/usr/lib:/base/lib:/base/lib/dll:/radio/lib:/radio/lib/dll:/radio/usr/lib:/proc/boot; '
    'export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONHOME=/usr PYTHONPATH=/usr/lib/python32.zip:/usr/lib/python3.2/lib-dynload; '
)


def make_release_pin(bar_path, output_path=None):
    root = resource_root()
    bar_path = Path(bar_path)
    output_path = Path(output_path) if output_path else (root / PIN_REL)
    data = bar_path.read_bytes()
    with zipfile.ZipFile(bar_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(n.startswith('/') or '..' in n.split('/') or '\\' in n for n in names):
            raise ValueError('Unsafe BAR archive members')
        raw = archive.read('META-INF/MANIFEST.MF')
        info = headers(raw)
        identity_keys = (
            'Package-Name',
            'Package-Id',
            'Package-Author-Id',
            'Package-Architecture',
            'Package-Version',
            'Application-Id',
            'Application-Version',
        )
        identity = {k: info[k] for k in identity_keys}
        if (identity['Package-Name'] != PACKAGE_NAME or
                identity['Package-Author-Id'] != 'gYAOctoLabBB10VoLTE20261102' or
                identity['Application-Id'] != identity['Package-Id'] or
                identity['Package-Architecture'] != 'armle-v7' or
                identity['Package-Version'] != identity['Application-Version']):
            raise ValueError('Unexpected BAR identity: ' + json.dumps(identity))
        entry_elf = [n for n in names if n.endswith('/bb10recorder') or n == 'native/bb10recorder']
        if not entry_elf or not archive.read(entry_elf[0]).startswith(b'\x7fELF'):
            raise ValueError('BAR does not contain a compiled ARMv7 ELF binary')
        files = {
            n: {'sha256': hashlib.sha256(archive.read(n)).hexdigest(), 'size': archive.getinfo(n).file_size}
            for n in names if not n.endswith('/')
        }
    helper_bytes = (root / HELPER_REL).read_bytes().replace(b'\r\n', b'\n')
    pin = {
        'schema': 1,
        'version': identity['Package-Version'],
        'identity': identity,
        'filename': bar_path.name,
        'bar_sha256': hashlib.sha256(data).hexdigest(),
        'bar_size': len(data),
        'platform_manifest_sha256': hashlib.sha256(raw).hexdigest(),
        'installed_files': files,
        'helper_sha256': hashlib.sha256(helper_bytes).hexdigest(),
        'installer_sha256': INSTALLER_SHA256,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(pin, indent=2) + '\n', encoding='ascii', newline='\n')
    return pin


def load_release_pin():
    root = resource_root()
    pin_path = root / PIN_REL
    if not pin_path.is_file():
        raise RuntimeError('missing_mobile_app_pin')
    pin = json.loads(pin_path.read_text(encoding='ascii'))
    helper_bytes = (root / HELPER_REL).read_bytes().replace(b'\r\n', b'\n')
    if hashlib.sha256(helper_bytes).hexdigest() != pin['helper_sha256']:
        raise RuntimeError('helper_hash_mismatch')
    return pin, helper_bytes


def resolve_bundled_bar(bar_override=None):
    pin, _ = load_release_pin()
    path = Path(bar_override) if bar_override else (resource_root() / BUNDLED_BAR_REL)
    if not path.is_file():
        raise RuntimeError('bundled_bar_missing:' + str(path))
    blob = path.read_bytes()
    if len(blob) != pin['bar_size'] or hashlib.sha256(blob).hexdigest() != pin['bar_sha256']:
        raise RuntimeError('bundled_bar_hash_mismatch')
    return path, blob, pin


def _run_bar_agent(conn, action, bar_override=None):
    pin, helper_bytes = load_release_pin()
    blob = None
    if action == 'install':
        _, blob, pin = resolve_bundled_bar(bar_override)

    identifier = uuid.uuid4().hex
    local_stage = private_root() / 'bar-install' / identifier
    local_stage.mkdir(parents=True, exist_ok=True)
    agent_file = local_stage / 'agent.py'
    release_file = local_stage / 'release.json'
    agent_file.write_bytes(helper_bytes)
    release_file.write_text(json.dumps(pin, sort_keys=True), encoding='ascii', newline='\n')

    remote_stage = '/var/bb10_rec_app_stage_' + identifier
    conn.run_sh(['umask 077', 'rm -rf ' + shlex.quote(remote_stage), 'mkdir -m 700 ' + shlex.quote(remote_stage)], timeout=20)
    conn.upload(agent_file, remote_stage + '/agent.py', timeout=45)
    conn.upload(release_file, remote_stage + '/release.json', timeout=45)
    remote_files = ['agent.py', 'release.json']
    if blob is not None:
        bar_file = local_stage / 'application.bar'
        bar_file.write_bytes(blob)
        conn.upload(bar_file, remote_stage + '/application.bar', timeout=90)
        remote_files.append('application.bar')

    chmod_cmd = 'chmod 600 ' + ' '.join(shlex.quote(remote_stage + '/' + n) for n in remote_files)
    arg_tail = 'install ' + identifier if action == 'install' else 'inspect'
    run_cmd = (
        ENV +
        '/proc/boot/pathtrust ' + shlex.quote('!' + remote_stage + '/agent.py') +
        ' && /usr/bin/python3.2 -B ' + shlex.quote(remote_stage + '/agent.py') + ' ' + arg_tail
    )
    out = conn.run_sh([chmod_cmd, run_cmd], timeout=120 if action == 'install' else 40)
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith('{'):
            return json.loads(line)
    raise RuntimeError('invalid_bar_agent_output:' + out.strip()[:200])


def inspect_bar_over_ssh(conn):
    return _run_bar_agent(conn, 'inspect')


def install_bar_over_ssh(conn, bar_override=None):
    return _run_bar_agent(conn, 'install', bar_override=bar_override)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pin-bar', type=Path, help='Generate materials/mobile-app-artifact.json from a compiled BAR')
    parser.add_argument('--output', type=Path, help='Custom output path for pin JSON')
    args = parser.parse_args()
    if args.pin_bar:
        pin = make_release_pin(args.pin_bar, args.output)
        print(json.dumps({k: v for k, v in pin.items() if k != 'installed_files'}, indent=2))
        return
    parser.error('--pin-bar is required when invoking bar_installer.py directly')


if __name__ == '__main__':
    main()
