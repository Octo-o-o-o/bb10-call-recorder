"""Build release archives (AutoRoot bootstrap ZIP, clean source ZIP, SHA256SUMS)."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from check_release import ROOT, check, iter_public_files
from desktop_paths import desktop_release_version


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_sha256_sidecar(path):
    path = Path(path)
    digest = sha256_file(path)
    sidecar = Path(str(path) + '.sha256')
    sidecar.write_text(digest + '  ' + path.name + '\n', encoding='ascii', newline='\n')
    return digest


def _zip_add_regular(zf, arcname, data, executable=False):
    info = zipfile.ZipInfo(arcname, date_time=(2026, 11, 18, 0, 0, 0))
    info.create_system = 3
    mode = 0o100755 if executable else 0o100644
    info.external_attr = mode << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    zf.writestr(info, data)


def build_bootstrap_zip(output_dir, bar_path=None):
    project = json.loads((ROOT / 'project.json').read_text(encoding='utf-8'))
    mob_ver = project['mobile_version']
    out_zip = Path(output_dir) / ('bb10-call-recorder-' + mob_ver + '-bootstrap.zip')
    manifest = (
        'Package-Id: bb10-call-recorder\n'
        'Package-Name: BB10 Call Recorder\n'
        'Package-Version: ' + mob_ver + '\n'
    ).encode('ascii')

    install_sh = (
        '#!/bin/sh\n'
        'set -e\n'
        'export PATH=/proc/boot:/bin:/usr/bin:/base/bin:/base/usr/bin\n'
        'export LD_LIBRARY_PATH=/base/usr/lib:/base/lib:/base/lib/dll:/radio/lib:/radio/lib/dll:/radio/usr/lib:/proc/boot\n'
        'export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONHOME=/usr PYTHONPATH=/usr/lib/python32.zip:/usr/lib/python3.2/lib-dynload\n'
        'HERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\n'
        'for f in "$HERE"/device/*.py; do\n'
        '  chmod 600 "$f" && /proc/boot/pathtrust "!$f"\n'
        'done\n'
        'chmod 700 "$HERE/device/boot.sh" && /proc/boot/pathtrust "!$HERE/device/boot.sh"\n'
        '/usr/bin/python3.2 -B "$HERE/device/install.py" install "$HERE/device"\n'
    ).encode('utf-8')

    with zipfile.ZipFile(out_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        _zip_add_regular(zf, 'MANIFEST', manifest)
        if bar_path and Path(bar_path).is_file():
            _zip_add_regular(zf, 'pkg.bar', Path(bar_path).read_bytes())
        _zip_add_regular(zf, 'addon/install.sh', install_sh, executable=True)
        for item in sorted((ROOT / 'device').iterdir()):
            if item.is_file() and item.suffix in ('.py', '.sh'):
                raw = item.read_bytes().replace(b'\r\n', b'\n')
                _zip_add_regular(zf, 'addon/device/' + item.name, raw, executable=(item.suffix == '.sh'))

    digest = write_sha256_sidecar(out_zip)
    return {'file': out_zip.name, 'sha256': digest, 'bytes': out_zip.stat().st_size}


def build_source_zip(output_dir):
    project = json.loads((ROOT / 'project.json').read_text(encoding='utf-8'))
    rel_ver = desktop_release_version(project)
    out_zip = Path(output_dir) / ('bb10-call-recorder-' + rel_ver + '-source.zip')
    prefix = 'bb10-call-recorder-' + rel_ver + '/'
    with zipfile.ZipFile(out_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for path, rel in iter_public_files():
            raw = path.read_bytes()
            if path.suffix.lower() in {'.py', '.sh', '.md', '.json', '.xml', '.txt', '.qml', '.cpp', '.h', '.yml', '.ps1', '.cmd'}:
                if path.suffix.lower() != '.cmd':
                    raw = raw.replace(b'\r\n', b'\n')
            _zip_add_regular(zf, prefix + rel, raw, executable=(path.suffix.lower() in ('.sh', '.cmd')))
    digest = write_sha256_sidecar(out_zip)
    return {'file': out_zip.name, 'sha256': digest, 'bytes': out_zip.stat().st_size}


def write_sha256sums(output_dir):
    output_dir = Path(output_dir)
    entries = []
    for item in sorted(output_dir.iterdir()):
        if not item.is_file():
            continue
        if item.name == 'SHA256SUMS.txt' or item.name.endswith('.sha256') or item.name.endswith('.build.json'):
            continue
        entries.append(sha256_file(item) + '  ' + item.name)
    sums_path = output_dir / 'SHA256SUMS.txt'
    sums_path.write_text('\n'.join(entries) + '\n', encoding='ascii', newline='\n')
    return {'file': sums_path.name, 'entries': len(entries), 'sha256': sha256_file(sums_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist')
    parser.add_argument('--bar', type=Path, help='Optional compiled .bar to copy into dist and embed in bootstrap.zip')
    args = parser.parse_args()

    check()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    project = json.loads((ROOT / 'project.json').read_text(encoding='utf-8'))
    bar_src = args.bar or (ROOT / 'assets/mobile/bb10-call-recorder.bar')
    bar_dist = None
    if bar_src and Path(bar_src).is_file():
        bar_dist = out / ('bb10-call-recorder-' + project['mobile_version'] + '.bar')
        if Path(bar_src).resolve() != bar_dist.resolve():
            shutil.copyfile(bar_src, bar_dist)
        write_sha256_sidecar(bar_dist)

    bootstrap = build_bootstrap_zip(out, bar_path=bar_dist)
    source = build_source_zip(out)
    sums = write_sha256sums(out)
    print(json.dumps({'bootstrap': bootstrap, 'source': source, 'sha256sums': sums}, indent=2))


if __name__ == '__main__':
    main()
