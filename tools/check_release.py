"""Public repository hygiene, privacy and integrity verifier for bb10-call-recorder."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

SENSITIVE = {
    'pem_private_key': re.compile(r'BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY'),
    'ssh_host_or_user_key': re.compile(r'ssh-(?:rsa|ed25519)\s+[A-Za-z0-9+/]{64,}'),
    'cn_imsi': re.compile(r'\b460[0-9]{12}\b'),
    'imei_15': re.compile(r'(?<![0-9a-fA-F])\b86[0-9]{13}\b(?![0-9a-fA-F])'),
    'cn_mobile_number': re.compile(r'(?<![0-9])\+?86[- ]?1[3-9][0-9]{9}(?![0-9])'),
    'win_user_path': re.compile(r'[A-Za-z]:[\\/]+Users[\\/]+', re.I),
    'local_workspace_path': re.compile(r'[A-Za-z]:[\\/]+LifeSpace[\\/]+', re.I),
    'mac_user_path': re.compile(r'(?<![A-Za-z0-9])/Users/[A-Za-z0-9._-]+/'),
}

BINARY_SUFFIXES = {'.png', '.ico', '.bar', '.pyc', '.exe', '.dll', '.zip', '.so'}
EXCLUDED_DIRS = {
    '.git', '__pycache__', '.venv', 'private', 'downloads',
    'build', 'dist', '.wrangler',
}
EXCLUDED_PREFIXES = (
    'mobile/native/build/',
    'mobile/native/assets/runtime/',
)
EXCLUDED_FILES = {
    'mobile/native/bar-descriptor.build.xml',
}


def iter_public_files():
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(ROOT).parts
        if any(part in EXCLUDED_DIRS for part in rel_parts):
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel in EXCLUDED_FILES or any(rel.startswith(p) for p in EXCLUDED_PREFIXES):
            continue
        yield path, rel


def check(require_bar=False, check_git=False):
    required = (
        'project.json',
        'LICENSE',
        'NOTICE.md',
        'README.md',
        'README.en.md',
        'CONTRIBUTING.md',
        'docs/ARCHITECTURE.md',
        'device/service.py',
        'device/install.py',
        'device/qsa_fallback.py',
        'device/wav_writer.py',
        'mobile/runtime/entry.py',
        'mobile/native/bar-descriptor.xml',
        'mobile/native/CMakeLists.txt',
        'assets/icon.png',
        'assets/app.ico',
        'assets/support/octoooo-favicon.png',
    )
    for rel in required:
        if not (ROOT / rel).is_file():
            raise RuntimeError('Missing required file: ' + rel)

    project = json.loads((ROOT / 'project.json').read_text(encoding='utf-8'))
    if project.get('name') != 'bb10-call-recorder' or project.get('package_id') != 'com.octolab.bb10recorder':
        raise RuntimeError('Unexpected project.json identity')

    # Verify strict zero-internet permission guarantee on the BB10 app descriptor
    xml_root = ET.fromstring((ROOT / 'mobile/native/bar-descriptor.xml').read_text(encoding='utf-8'))
    perms = [el.text.strip() for el in xml_root.findall('.//{http://www.qnx.com/schemas/application/1.0}permission') if el.text]
    if 'access_internet' in perms:
        raise RuntimeError('Security violation: bar-descriptor.xml must NEVER request access_internet')

    file_hashes = {}
    for path, rel in iter_public_files():
        raw = path.read_bytes()
        file_hashes[rel] = hashlib.sha256(raw).hexdigest()
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        text = raw.decode('utf-8')
        for label, pattern in SENSITIVE.items():
            if pattern.search(text):
                raise RuntimeError('Sensitive pattern ' + label + ' detected in ' + rel)

    if require_bar:
        from bar_installer import resolve_bundled_bar
        resolve_bundled_bar()

    if check_git:
        res = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, capture_output=True, text=True, check=True)
        if res.stdout.strip():
            raise RuntimeError('Git working tree is not clean:\n' + res.stdout.strip())

    return {
        'ok': True,
        'project': project['name'],
        'version': project['version'],
        'mobile_version': project['mobile_version'],
        'checked_public_files': len(file_hashes),
        'zero_internet_permission_verified': True,
        'files': file_hashes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-bar', action='store_true', help='Require pinned compiled BAR in assets/mobile/')
    parser.add_argument('--check-git', action='store_true', help='Require a clean git working tree')
    args = parser.parse_args()
    report = check(require_bar=args.require_bar, check_git=args.check_git)
    summary = {k: v for k, v in report.items() if k != 'files'}
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    sys.exit(main())
