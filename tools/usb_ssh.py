"""Standalone USB-SSH discovery and execution for paired rooted BB10 phones."""
import ipaddress
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import uuid

from desktop_paths import frozen, prepare_external_programs, private_root, resource_root, ssh_binaries, volte_private_root

ALIASES = ('bb10-root', 'q10-root')
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


class ConnectionError(RuntimeError):
    pass


class SshConnection:
    def __init__(self, ssh, scp, host, config_path, extra_options=None):
        self.ssh = ssh
        self.scp = scp
        self.host = host
        self.config_path = str(config_path) if config_path else ''
        self.options = [
            '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=yes',
            '-o', 'ConnectTimeout=12',
            '-o', 'ServerAliveInterval=5',
            '-o', 'ServerAliveCountMax=2',
            '-o', 'ClearAllForwardings=yes',
            '-o', 'Ciphers=aes128-ctr,aes192-ctr,aes256-ctr',
            '-o', 'MACs=hmac-sha1',
            '-o', 'HostKeyAlgorithms=+ssh-rsa',
            '-o', 'PubkeyAcceptedAlgorithms=+ssh-rsa',
        ]
        if extra_options:
            self.options[:0] = list(extra_options)
        if self.config_path:
            self.options.extend(['-F', self.config_path])

    def effective_config(self):
        prepare_external_programs()
        res = subprocess.run(
            [self.ssh, '-G'] + self.options + [self.host],
            capture_output=True,
            timeout=8,
            creationflags=NO_WINDOW,
        )
        if res.returncode != 0:
            return {}
        text = res.stdout.decode('utf-8', 'replace')
        return dict(line.split(' ', 1) for line in text.splitlines() if ' ' in line)

    def run_sh(self, script_lines, timeout=60):
        prepare_external_programs()
        path_header = 'export PATH=/proc/boot:/bin:/usr/bin:/base/bin:/base/usr/bin\n'
        if isinstance(script_lines, (list, tuple)):
            body = path_header + '\n'.join(script_lines) + '\n'
        else:
            body = path_header + str(script_lines).replace('\r\n', '\n')
            if not body.endswith('\n'):
                body += '\n'
        res = subprocess.run(
            [self.ssh, '-T'] + self.options + [self.host, '/bin/sh -s'],
            input=body.encode('utf-8'),
            capture_output=True,
            timeout=timeout,
            creationflags=NO_WINDOW,
        )
        stdout = res.stdout.decode('utf-8', 'replace')
        stderr = res.stderr.decode('utf-8', 'replace')
        if res.returncode != 0:
            raise ConnectionError(stderr.strip() or stdout.strip() or ('ssh_failed:' + str(res.returncode)))
        return stdout

    def upload(self, local_path, remote_path, timeout=90):
        prepare_external_programs()
        res = subprocess.run(
            [self.scp, '-S', self.ssh, '-O', '-q'] + self.options + [str(local_path), self.host + ':' + remote_path],
            capture_output=True,
            timeout=timeout,
            creationflags=NO_WINDOW,
        )
        if res.returncode != 0:
            err = res.stderr.decode('utf-8', 'replace').strip()
            raise ConnectionError(err or ('scp_failed:' + str(res.returncode)))


def _aliases_in_config(path):
    found = []
    try:
        for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
            words = shlex.split(line, comments=True)
            if words and words[0].lower() == 'host':
                found.extend(w for w in words[1:] if w in ALIASES)
    except (OSError, UnicodeError, ValueError):
        pass
    return list(dict.fromkeys(found))


def _kit_configs(folder):
    if not folder.is_dir():
        return []
    return ([folder / 'ssh_config', folder / 'root-kit/ssh_config']
            + sorted(folder.glob('root-kit-*/ssh_config'))
            + sorted(folder.glob('recovery-*/ssh_config'))
            + sorted(folder.glob('*pairing*/ssh_config')))


def save_preferred_connection(host, config_path):
    folder = private_root()
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / ('connection-' + uuid.uuid4().hex + '.json')
    tmp.write_text(json.dumps({'host': host, 'config': str(config_path)}, indent=2) + '\n', encoding='utf-8')
    tmp.replace(folder / 'connection.json')


def _read_saved_connection(folder):
    try:
        data = json.loads((folder / 'connection.json').read_text(encoding='utf-8'))
        host = data.get('host', '')
        cfg = data.get('config', '')
        if isinstance(host, str) and isinstance(cfg, str) and (not cfg or Path(cfg).is_file()):
            return (host, cfg)
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return None


def candidate_configs(custom_config=''):
    candidates = []
    seen = set()

    def add(host, cfg):
        key = (host, str(Path(cfg).resolve()) if cfg else '')
        if key not in seen:
            seen.add(key)
            candidates.append(key)

    if custom_config:
        p = Path(custom_config)
        if not p.is_file():
            raise ConnectionError('ssh_config_not_found')
        hosts = _aliases_in_config(p) or ['bb10-root']
        for h in hosts:
            add(h, p)
        return candidates

    private_folders = [private_root(), volte_private_root()]
    roots = [resource_root()] if not frozen() else []
    for parent in list(Path(sys.executable).resolve().parents)[:5]:
        if (parent / 'project.json').is_file():
            roots.append(parent)
    for root in roots:
        private_folders.append(root / 'private')
        sibling = root.parent / 'q10-unicom-volte'
        if sibling.is_dir():
            private_folders.append(sibling / 'private')

    for folder in private_folders:
        saved = _read_saved_connection(folder)
        if saved:
            add(*saved)

    search_paths = []
    for folder in private_folders:
        search_paths.extend(_kit_configs(folder))
    search_paths.append(Path.home() / '.ssh/config')
    search_paths.append(Path(sys.executable).parent / 'ssh_config')
    for root in roots:
        if root.parent.name == 'opensource':
            search_paths.append(root.parent.parent / 'tools/volte_session/private/ssh_config')

    for path in search_paths:
        if not path.is_file():
            continue
        for host in ALIASES:
            if host in _aliases_in_config(path):
                add(host, path)
    return candidates


def _detect_dynamic_usb_peer():
    if sys.platform != 'win32':
        return None
    ps = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    if not ps.is_file():
        return None
    cmd = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "@(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
        "Where-Object { $_.IPAddress -like '169.254.*' -and $_.PrefixLength -eq 30 } | "
        "ForEach-Object { $_.IPAddress }) | ConvertTo-Json -Compress"
    )
    try:
        res = subprocess.run([str(ps), '-NoProfile', '-Command', cmd],
                             capture_output=True, timeout=6, creationflags=NO_WINDOW)
        raw = res.stdout.decode('utf-8', 'ignore').strip()
        if res.returncode != 0 or not raw:
            return None
        parsed = json.loads(raw)
        rows = parsed if isinstance(parsed, list) else [parsed]
        valid = []
        for src in rows:
            src = str(src or '')
            subnet = ipaddress.IPv4Network(src + '/30', strict=False)
            hosts = list(subnet.hosts())
            if len(hosts) == 2 and src == str(hosts[1]):
                peer = str(hosts[0])
                if peer != '169.254.0.1':
                    valid.append((peer, src))
        if len(valid) == 1:
            return valid[0]
    except Exception:
        return None
    return None


def connect_phone(custom_config=''):
    ssh, scp = ssh_binaries()
    candidates = candidate_configs(custom_config=custom_config)
    if not candidates:
        raise ConnectionError('no_paired_ssh_config')

    dynamic_link = None
    dynamic_checked = False
    last_error = 'ssh_unreachable'

    for host, cfg in candidates:
        conn = SshConnection(ssh, scp, host, cfg)
        try:
            eff = conn.effective_config()
            if eff.get('user', 'root') != 'root':
                continue
            out = conn.run_sh(['echo BB10_RECORDER_ROOT_READY', 'cat /etc/os.version 2>/dev/null || true'], timeout=10)
            lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
            if lines and lines[0] == 'BB10_RECORDER_ROOT_READY':
                if custom_config:
                    save_preferred_connection(host, cfg)
                return conn
        except Exception as exc:
            last_error = str(exc)

        if not dynamic_checked:
            dynamic_link = _detect_dynamic_usb_peer()
            dynamic_checked = True
        if dynamic_link:
            peer, source = dynamic_link
            eff = conn.effective_config()
            trust_alias = eff.get('hostkeyalias', 'none')
            if trust_alias == 'none':
                trust_alias = '169.254.0.1'
            extra = [
                '-o', 'HostName=' + peer,
                '-o', 'BindAddress=' + source,
                '-o', 'ProxyCommand=none',
                '-o', 'ProxyJump=none',
                '-o', 'HostKeyAlias=' + trust_alias,
            ]
            dyn_conn = SshConnection(ssh, scp, host, cfg, extra_options=extra)
            try:
                out = dyn_conn.run_sh(['echo BB10_RECORDER_ROOT_READY', 'cat /etc/os.version 2>/dev/null || true'], timeout=10)
                lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
                if lines and lines[0] == 'BB10_RECORDER_ROOT_READY':
                    if custom_config:
                        save_preferred_connection(host, cfg)
                    return dyn_conn
            except Exception as exc:
                last_error = str(exc)

    raise ConnectionError(last_error)
