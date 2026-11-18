"""Build the standalone offline Windows x64 GUI executable for BB10 Call Recorder."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import urllib.request
import uuid
import zipfile

from bar_installer import BUNDLED_BAR_REL, PIN_REL, resolve_bundled_bar
from check_release import ROOT, check
from desktop_paths import desktop_release_version


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fetch(item, cache_dir, offline=False):
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / item['file']
    if not path.is_file():
        if offline:
            raise RuntimeError('Offline build input missing: ' + str(path))
        temporary = path.with_name(path.name + '.' + uuid.uuid4().hex[:8] + '.partial')
        with urllib.request.urlopen(item['url'], timeout=45) as resp, temporary.open('xb') as out:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        if digest(temporary) != item['sha256']:
            temporary.unlink(missing_ok=True)
            raise RuntimeError('Downloaded input hash mismatch: ' + item['file'])
        temporary.replace(path)
    if digest(path) != item['sha256']:
        raise RuntimeError('Cached input hash mismatch: ' + str(path))
    return path


def runtime_data_files():
    files = {
        'project.json',
        'LICENSE',
        'NOTICE.md',
        'materials/windows-runtime.json',
        PIN_REL,
        BUNDLED_BAR_REL,
        'tools/bar_installer_device.py',
        'mobile/runtime/entry.py',
        'assets/icon.png',
        'assets/icon-96.png',
        'assets/app.ico',
    }
    for item in (ROOT / 'device').iterdir():
        if item.is_file() and item.suffix in ('.py', '.sh'):
            files.add(item.relative_to(ROOT).as_posix())
    for item in (ROOT / 'assets/support').glob('*.png'):
        files.add(item.relative_to(ROOT).as_posix())
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='Require cached hash-verified inputs without network')
    parser.add_argument('--cache-dir', type=Path, default=ROOT / 'downloads', help='Directory for cached OpenSSH/Tk inputs')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()

    assert sys.platform == 'win32' and platform.machine().lower() in ('amd64', 'x86_64')
    spec = json.loads((ROOT / 'materials/windows-runtime.json').read_text(encoding='utf-8'))
    assert platform.python_version() == spec['python'], 'Expected Python ' + spec['python']
    for line in (ROOT / 'tools/windows-freeze-requirements.txt').read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        pkg, ver = line.strip().split('==')
        assert importlib.metadata.version(pkg) == ver, 'Dependency mismatch: ' + pkg
    import tkinter as tk
    assert tk.Tcl().call('info', 'patchlevel') == spec['tcl']

    check(require_bar=True)
    resolve_bundled_bar()

    project = json.loads((ROOT / 'project.json').read_text(encoding='utf-8'))
    rel_ver = desktop_release_version(project)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    archive = fetch(spec['openssh'], args.cache_dir, offline=args.offline)
    vendor = ROOT / 'build/windows-vendor/openssh'
    vendor.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        for name, expected in spec['openssh']['files'].items():
            raw = zf.read(spec['openssh']['prefix'] + name)
            assert hashlib.sha256(raw).hexdigest() == expected, 'OpenSSH hash mismatch: ' + name
            (vendor / name).write_bytes(raw)

    work = ROOT / 'build/windows'
    work.mkdir(parents=True, exist_ok=True)

    license_parts = [
        ('bb10-call-recorder ' + rel_ver, ROOT / 'LICENSE'),
        ('Python ' + spec['python'], Path(sys.base_prefix) / 'LICENSE.txt'),
        ('PyInstaller ' + spec['pyinstaller'] + ' (bootloader exception included)',
         Path(importlib.metadata.distribution('pyinstaller').locate_file(
             'pyinstaller-' + spec['pyinstaller'] + '.dist-info/licenses/COPYING.txt'))),
    ]
    license_parts += [(item['component'], fetch(item, args.cache_dir, offline=args.offline)) for item in spec['licenses']]
    license_parts += [
        ('Microsoft Win32-OpenSSH LICENSE', vendor / 'LICENSE.txt'),
        ('Microsoft Win32-OpenSSH NOTICE', vendor / 'NOTICE.txt'),
    ]
    notices = work / 'THIRD-PARTY-NOTICES.txt'
    notices.write_text(
        '\n\n'.join(title + '\n' + '=' * len(title) + '\n' + p.read_text(encoding='utf-8') for title, p in license_parts),
        encoding='utf-8',
    )

    ver_tuple = tuple(int(p) for p in project['version'].split('.')) + (project.get('desktop_revision', 1),)
    version_file = work / 'version.txt'
    version_file.write_text(
        'VSVersionInfo(ffi=FixedFileInfo(filevers={0!r}, prodvers={0!r}, mask=0x3f, flags=0, OS=0x40004, '
        'fileType=0x1, subtype=0, date=(0,0)), kids=[StringFileInfo([StringTable("040904B0", ['
        'StringStruct("FileDescription", "BB10 Call Recorder Desktop Helper"), '
        'StringStruct("ProductName", "bb10-call-recorder"),'
        'StringStruct("FileVersion", "{1}"), StringStruct("ProductVersion", "{1}"),'
        'StringStruct("OriginalFilename", "bb10-call-recorder.exe")])]), '
        'VarFileInfo([VarStruct("Translation", [1033,1200])])])'.format(ver_tuple, rel_ver),
        encoding='utf-8',
    )

    build_name = project['name'] + '-' + rel_ver + '-windows-x64'
    cmd = [
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile', '--windowed', '--noupx',
        '--name', build_name, '--distpath', str(output_dir), '--workpath', str(work / 'pyinstaller'),
        '--specpath', str(work), '--paths', str(ROOT / 'tools'), '--paths', str(ROOT / 'device'),
        '--icon', str(ROOT / 'assets/app.ico'), '--version-file', str(version_file),
        '--exclude-module', 'PIL', '--exclude-module', 'pip', '--exclude-module', 'setuptools',
        '--exclude-module', 'unicorn',
    ]
    bundled = {rel: ROOT / rel for rel in runtime_data_files()}
    bundled.update({'vendor/openssh/' + name: vendor / name for name in spec['openssh']['files']})
    bundled['licenses/THIRD-PARTY-NOTICES.txt'] = notices
    for rel, src in sorted(bundled.items()):
        cmd += ['--add-data', str(src) + ':' + str(Path(rel).parent)]
    cmd.append(str(ROOT / 'tools/windows_main.py'))
    subprocess.run(cmd, cwd=ROOT, check=True)

    exe_path = output_dir / (build_name + '.exe')
    from PyInstaller.archive.readers import CArchiveReader
    reader = CArchiveReader(str(exe_path))
    index = {n.replace('\\', '/'): n for n in reader.toc}
    for rel, src in bundled.items():
        assert hashlib.sha256(reader.extract(index[rel])).hexdigest() == digest(src), 'Bundled asset mismatch: ' + rel
    forbidden = ('private/', 'downloads/', 'ssh_config', 'known_hosts', 'q10_root_rsa', 'id_rsa')
    assert not any(any(tok in n for tok in forbidden) for n in index), 'Private file leaked into EXE!'

    selftest = subprocess.run([str(exe_path), '--self-test'], capture_output=True, text=True, timeout=30, check=True)
    selftest_json = json.loads(selftest.stdout.strip())
    assert selftest_json.get('self_test') == 'ok'

    exe_sha = digest(exe_path)
    (output_dir / (exe_path.name + '.sha256')).write_text(exe_sha + '  ' + exe_path.name + '\n', encoding='ascii', newline='\n')
    report = {
        'artifact': exe_path.name,
        'version': rel_ver,
        'sha256': exe_sha,
        'bytes': exe_path.stat().st_size,
        'bundled_files': len(bundled),
        'self_test': selftest_json,
    }
    (output_dir / (build_name + '.build.json')).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
