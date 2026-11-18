"""Low-level QNX / BB10 file, disk-space and process helpers (Python 3.2+)."""
import errno
import hashlib
import json
import os
import subprocess
import tempfile
import time


MIN_FREE_BYTES = 200 * 1024 * 1024  # 200 MiB safety floor


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def read_bytes(path, max_bytes=4194304):
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0))
    try:
        chunks = []
        remaining = max_bytes
        while remaining > 0:
            piece = os.read(fd, min(65536, remaining))
            if not piece:
                break
            chunks.append(piece)
            remaining -= len(piece)
        return b''.join(chunks)
    finally:
        os.close(fd)


def atomic_write(path, data, mode=0o600):
    tmp = path + '.tmp.' + str(os.getpid())
    if os.path.islink(path) or os.path.islink(tmp):
        raise RuntimeError('Refusing symlink target: ' + path)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        getattr(os, 'replace', os.rename)(tmp, path)
    except Exception:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            pass
        raise


def load_json(path, default=None):
    try:
        if os.path.islink(path) or not os.path.isfile(path):
            return default
        return json.loads(read_bytes(path).decode('utf-8'))
    except Exception:
        return default


def save_json(path, payload, mode=0o600):
    raw = (json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + '\n').encode('ascii')
    atomic_write(path, raw, mode=mode)


def ensure_dir(path, mode=0o755, shared_media=False):
    if os.path.islink(path):
        raise RuntimeError('Refusing symlink directory: ' + path)
    if not os.path.isdir(path):
        parent = os.path.dirname(path.rstrip('/'))
        if parent and parent != path and not os.path.isdir(parent):
            ensure_dir(parent, mode=mode, shared_media=shared_media)
        try:
            os.mkdir(path, mode)
        except OSError as exc:
            if exc.errno != errno.EEXIST or not os.path.isdir(path):
                raise
    os.chmod(path, mode)
    if shared_media and hasattr(os, 'chown'):
        parent = os.path.dirname(path.rstrip('/'))
        try:
            uid = 1000 if path.startswith('/accounts/1000/') else -1
            parent_gid = os.stat(parent).st_gid if parent and os.path.isdir(parent) else 1001
            os.chown(path, uid, parent_gid if parent_gid > 0 else 1001)
            os.chmod(path, mode | 0o2000)
        except OSError:
            pass


def make_shared_readable(path, mode=0o664):
    try:
        if hasattr(os, 'chown'):
            uid = 1000 if path.startswith('/accounts/1000/') else -1
            parent = os.path.dirname(path.rstrip('/'))
            gid = os.stat(parent).st_gid if parent and os.path.isdir(parent) else 1001
            os.chown(path, uid, gid if gid > 0 else 1001)
        os.chmod(path, mode)
    except OSError:
        pass


def free_space_bytes(path):
    target = path
    while target and not os.path.exists(target):
        parent = os.path.dirname(target.rstrip('/'))
        if parent == target:
            break
        target = parent
    if hasattr(os, 'statvfs'):
        st = os.statvfs(target or '/')
        return int(st.f_bavail) * int(st.f_frsize)
    return 1024 * 1024 * 1024


def run_command(argv, timeout=10):
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        child = subprocess.Popen(argv, stdout=out, stderr=err)
        deadline = time.time() + timeout
        while child.poll() is None and time.time() < deadline:
            time.sleep(0.05)
        if child.poll() is None:
            child.kill()
            child.wait()
            raise RuntimeError('Command timed out: ' + argv[0])
        out.seek(0)
        err.seek(0)
        stdout_bytes = out.read()
        stderr_bytes = err.read()
        if child.returncode != 0:
            raise RuntimeError('Command failed (%d): %s' % (
                child.returncode, stderr_bytes.decode('utf-8', 'replace').strip()))
        return stdout_bytes
