"""Keep immutable bundle resources separate from persistent per-user files."""
import os
from pathlib import Path
import re
import shutil
import sys


def desktop_release_version(project):
    revision = project.get('desktop_revision')
    if revision is not None and (type(revision) is not int or revision < 1):
        raise ValueError('Invalid desktop revision')
    return project['version'] + ('-r' + str(revision) if revision else '')


def frozen():
    return bool(getattr(sys, 'frozen', False))


def resource_root():
    return Path(sys._MEIPASS) if frozen() else Path(__file__).resolve().parents[1]


def private_root():
    if not frozen():
        return resource_root() / 'private'
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/bb10-call-recorder/private'
    local = Path(os.environ.get('LOCALAPPDATA') or (Path.home() / 'AppData' / 'Local'))
    return local / 'bb10-call-recorder' / 'private'


def volte_private_root():
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/bb10-volte/private'
    local = Path(os.environ.get('LOCALAPPDATA') or (Path.home() / 'AppData' / 'Local'))
    return local / 'bb10-volte' / 'private'


def prepare_external_programs():
    if frozen() and sys.platform == 'win32':
        import ctypes
        if not ctypes.windll.kernel32.SetDllDirectoryW(None):
            raise OSError('Cannot restore the Windows DLL search path')


def ssh_binaries():
    vendor = resource_root() / 'vendor/openssh'
    if (vendor / 'ssh.exe').is_file() and (vendor / 'scp.exe').is_file():
        return str(vendor / 'ssh.exe'), str(vendor / 'scp.exe')
    ssh = shutil.which('ssh') or 'ssh'
    scp = shutil.which('scp') or 'scp'
    return ssh, scp
