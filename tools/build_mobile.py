"""Build the BB10 Call Recorder native BAR using the pinned BB10 toolchain container."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PROJECT = json.loads((ROOT / 'project.json').read_text(encoding='utf-8'))
BUILDER = 'ghcr.io/xiazy/blackberry10-toolchain@sha256:60ce49510a37ed92368cca010bbaabf97b12d209b9fab179e8491b266bb2578f'


def stage_runtime_assets():
    native_root = ROOT / 'mobile/native'
    icon_dst = native_root / 'assets/icon.png'
    sibling_icon = ROOT.parent / 'q10-unicom-volte/mobile/native/assets/icon.png'
    if not icon_dst.is_file() and sibling_icon.is_file():
        shutil.copyfile(sibling_icon, icon_dst)

    runtime_dst = native_root / 'assets/runtime'
    if runtime_dst.exists():
        shutil.rmtree(runtime_dst)
    (runtime_dst / 'device').mkdir(parents=True, exist_ok=True)
    (runtime_dst / 'runtime').mkdir(parents=True, exist_ok=True)
    for item in (ROOT / 'device').iterdir():
        if item.is_file() and item.suffix in ('.py', '.sh'):
            shutil.copyfile(item, runtime_dst / 'device' / item.name)
    shutil.copyfile(ROOT / 'mobile/runtime/entry.py', runtime_dst / 'runtime/entry.py')


def build_bar(version=PROJECT['mobile_version']):
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+', version):
        raise ValueError('Version must have four numeric components')
    stage_runtime_assets()
    source = ROOT / 'mobile/native'
    (source / 'build').mkdir(parents=True, exist_ok=True)
    descriptor = (source / 'bar-descriptor.xml').read_text(encoding='utf-8')
    descriptor = re.sub(r'<versionNumber>[^<]+</versionNumber>',
                        '<versionNumber>' + '.'.join(version.split('.')[:3]) + '</versionNumber>', descriptor)
    descriptor = re.sub(r'<buildId>[^<]+</buildId>',
                        '<buildId>' + version.split('.')[3] + '</buildId>', descriptor)
    ET.fromstring(descriptor)
    (source / 'bar-descriptor.build.xml').write_text(descriptor, encoding='utf-8', newline='\n')
    if os.name != 'nt':
        subprocess.run(['chmod', '-R', 'a+rwX', str(source)], check=True)

    cmd = [
        'docker', 'run', '--rm', '--network', 'none', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges',
        '-v', str(source) + ':/src', '-w', '/src', BUILDER,
    ]
    subprocess.run(cmd + [
        'cmake', '-S', '/src', '-B', '/src/build/cmake',
        '-DCMAKE_TOOLCHAIN_FILE=/opt/bb10-toolchain.cmake',
        '-DBB10_RECORDER_VERSION=' + version,
    ], check=True)
    subprocess.run(cmd + ['cmake', '--build', '/src/build/cmake', '--parallel', '2'], check=True)
    subprocess.run(cmd + [
        'blackberry-nativepackager', '-devMode', '-package',
        'build/com.octolab.bb10recorder.bar', 'bar-descriptor.build.xml',
        '-configuration', 'Device-Debug',
    ], check=True)

    dist = ROOT / 'dist'
    dist.mkdir(parents=True, exist_ok=True)
    out_bar = dist / ('bb10-call-recorder-' + version + '.bar')
    shutil.copyfile(source / 'build/com.octolab.bb10recorder.bar', out_bar)
    return {'bar': str(out_bar), 'version': version, 'bytes': out_bar.stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default=PROJECT['mobile_version'])
    parser.add_argument('--stage-only', action='store_true')
    args = parser.parse_args()
    if args.stage_only:
        stage_runtime_assets()
        print(json.dumps({'staged': True}))
        return
    print(json.dumps(build_bar(args.version), indent=2))


if __name__ == '__main__':
    main()
