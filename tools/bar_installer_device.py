"""Native QNX-only BAR provisioning agent for BB10 Call Recorder (Python 3.2)."""
import contextlib
try:
    import fcntl
except ImportError:
    fcntl = None
import binascii
import hashlib
import json
import os
import re
import stat
import struct
import subprocess
import sys
import time
import zipfile

BASE = '/var/bb10_recorder_app_install'
APP_ROOT = '/apps'
INSTALLER = '/var/rootdata/installer'
PPS = '/pps/system/installer/upd/current'
TERMINAL = ('completed', 'failed', 'conflict')
PACKAGE_NAME = 'com.octolab.bb10recorder'


class InstallError(Exception):
    pass


def require(condition, code):
    if not condition:
        raise InstallError(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def nonce():
    return binascii.hexlify(os.urandom(16)).decode('ascii')


def write_package(path, package_id, target_version, bar):
    manifest = ('Package-Id: ' + package_id + '\nPackage-Name: BB10 Call Recorder\nPackage-Version: ' + target_version + '\n').encode('ascii')
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in (('MANIFEST', manifest), ('pkg.bar', bar)):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 18, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100600 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    os.chmod(path, 0o600)
    fd = os.open(path, os.O_WRONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def regular(path, limit=16777216, private=False, allow_hardlinks=False):
    info = os.lstat(path)
    single_link = info.st_nlink == 1 or (allow_hardlinks and not private and info.st_nlink > 0)
    require(stat.S_ISREG(info.st_mode) and single_link and
            os.path.realpath(path) == path and info.st_size <= limit, 'unsafe_file')
    if private:
        require(info.st_uid == os.geteuid() and info.st_mode & 0o077 == 0, 'unsafe_private_file')
    with open(path, 'rb') as stream:
        data = stream.read(limit + 1)
    require(len(data) == info.st_size and len(data) <= limit, 'file_changed')
    return data


def private_directory(path, create=False):
    if create and not os.path.lexists(path):
        os.mkdir(path, 0o700)
    info = os.lstat(path)
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid() and
            info.st_mode & 0o077 == 0 and os.path.realpath(path) == path, 'unsafe_private_directory')


def load(path):
    return json.loads(regular(path, 262144, True).decode('ascii'))


def save(path, value):
    temporary = path + '.tmp-' + nonce()[:16]
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(json.dumps(value, sort_keys=True, separators=(',', ':')).encode('ascii'))
        stream.flush()
        os.fsync(stream.fileno())
    os.rename(temporary, path)
    fd = os.open(path, os.O_WRONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def headers(raw):
    values = {}
    for line in raw.decode('utf-8').splitlines():
        if not line:
            continue
        if ': ' in line and not line.startswith(' '):
            key, value = line.split(': ', 1)
            if key.startswith(('Package-', 'Application-')):
                values[key] = value
    return values


def version_tuple(value):
    require(isinstance(value, str) and re.match(r'\A[0-9]{1,5}(?:\.[0-9]{1,5}){3}\Z', value), 'invalid_version')
    return tuple(int(part) for part in value.split('.'))


def installed(release):
    matches = [name for name in os.listdir(APP_ROOT) if name.startswith(PACKAGE_NAME + '.')]
    if not matches:
        return {'state': 'absent', 'can_install': True}
    require(len(matches) == 1, 'app_identity_conflict')
    path = APP_ROOT + '/' + matches[0]
    require(os.path.realpath(path) == path and os.path.isdir(path), 'app_identity_conflict')
    raw = regular(path + '/META-INF/MANIFEST.MF', 262144, allow_hardlinks=True)
    info = headers(raw)
    for key, expected in release['identity'].items():
        if key not in ('Package-Version', 'Application-Version'):
            require(info.get(key) == expected, 'app_identity_conflict')
    current = version_tuple(info.get('Package-Version'))
    target = version_tuple(release['version'])
    if current > target:
        return {'state': 'newer_installed', 'can_install': False, 'version': info['Package-Version']}
    if current < target:
        return {'state': 'upgrade_available', 'can_install': True, 'version': info['Package-Version']}
    if digest(raw) != release['platform_manifest_sha256']:
        return {'state': 'reinstall_needed', 'can_install': True, 'version': info['Package-Version']}
    for member, expected in release['installed_files'].items():
        require(member.startswith(('native/', 'META-INF/')) and '..' not in member.split('/') and
                '\\' not in member, 'invalid_release')
        target_member = path + '/' + member
        if not os.path.lexists(target_member):
            return {'state': 'reinstall_needed', 'can_install': True, 'version': info['Package-Version']}
        blob = regular(target_member, expected['size'] + 1, allow_hardlinks=True)
        if len(blob) != expected['size'] or digest(blob) != expected['sha256']:
            return {'state': 'reinstall_needed', 'can_install': True, 'version': info['Package-Version']}
    return {'state': 'installed', 'can_install': False, 'version': info['Package-Version'],
            'installed_dir': path, 'all_files_verified': True}


@contextlib.contextmanager
def locked():
    require(fcntl is not None, 'native_lock_unavailable')
    path = BASE + '/lock'
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            raise InstallError('app_install_busy')
        yield
    finally:
        os.close(fd)


def read_pps(path):
    require(path.startswith('/pps/') and '?' not in path and os.path.realpath(path) == path and
            not os.path.islink(path), 'unsafe_pps_path')
    fd = os.open(path, os.O_RDONLY)
    try:
        raw = os.read(fd, 131073)
    finally:
        os.close(fd)
    require(len(raw) <= 131072, 'pps_response_too_large')
    return raw.decode('utf-8', 'replace')


def pps_dict(path):
    if not os.path.lexists(path):
        return {}
    raw = read_pps(path)
    return dict(line.split('::', 1) for line in raw.splitlines() if '::' in line)


def device_summary(release):
    app = installed(release)
    props = read_pps('/pps/services/deviceproperties') if os.path.lexists('/pps/services/deviceproperties') else ''
    model = re.search(r'^modelnumber::([A-Za-z0-9-]{1,40})$', props, re.M)
    os_path = os.path.realpath('/etc/os.version')
    os_ver = regular(os_path, 128).strip().decode('ascii', 'replace') if os.path.lexists(os_path) else 'unknown'
    app.update(schema=1, variant=model.group(1) if model else 'unknown',
               os_version=os_ver, target_version=release['version'], root_verified=True)
    return app


def provision(release, stage, identifier):
    require(isinstance(identifier, str) and re.match(r'\A[a-f0-9]{32}\Z', identifier), 'invalid_operation')
    with locked():
        before = installed(release)
        if before['state'] == 'installed':
            return device_summary(release)
        require(before['can_install'], 'newer_app_installed')
        installer_bytes = regular(INSTALLER, 1048576)
        require(digest(installer_bytes) == release['installer_sha256'], 'installer_unverified')
        bar = regular(stage + '/application.bar', release['bar_size'] + 1, True)
        require(len(bar) == release['bar_size'] and digest(bar) == release['bar_sha256'], 'bar_hash_mismatch')

        directory = BASE + '/jobs/' + identifier
        private_directory(directory, True)
        executable = directory + '/native-installer'
        fd = os.open(executable, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o700)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(installer_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        with open('/dev/null', 'wb') as sink:
            require(subprocess.call(['/proc/boot/pathtrust', '!' + executable], stdout=sink, stderr=sink) == 0,
                    'installer_pathtrust_failed')

        package_id = 'bb10-rec-app-' + identifier[:16]
        package = directory + '/package.zip'
        write_package(package, package_id, release['version'], bar)
        sud_job = PPS + '/job.' + package_id
        require(not os.path.lexists(sud_job), 'sud_job_exists')

        with open(directory + '/installer.log', 'wb') as log, open('/dev/null', 'rb') as source:
            environment = {
                'PATH': '/proc/boot:/bin:/usr/bin:/base/bin:/base/usr/bin',
                'LD_LIBRARY_PATH': '/base/usr/lib:/base/lib:/base/lib/dll:/radio/lib:/radio/lib/dll:/radio/usr/lib:/proc/boot',
            }
            previous_mask = os.umask(0o007)
            try:
                process = subprocess.Popen([executable, package], stdin=source, stdout=log, stderr=log,
                                           close_fds=True, start_new_session=True, env=environment)
            finally:
                os.umask(previous_mask)

            for _ in range(100):
                values = pps_dict(sud_job)
                if values.get('result'):
                    break
                if process.poll() is not None and values.get('result'):
                    break
                time.sleep(0.35)

        values = pps_dict(sud_job)
        if values.get('result') != 'success':
            raise InstallError('sud_install_failed:' + str(values.get('result', 'timeout')))
        after = device_summary(release)
        require(after.get('all_files_verified') is True, 'registered_app_mismatch')
        after['sud_success'] = True
        return after


def verify_os():
    path = os.path.realpath('/etc/os.version')
    require(path in ('/etc/os.version', '/base/etc/os.version'), 'os_not_supported')
    require(regular(path, 128).strip() == b'10.3.3.3216', 'os_not_supported')


def cleanup_stage(stage):
    for name in list(os.listdir(stage)):
        os.unlink(stage + '/' + name)
    os.rmdir(stage)


def main():
    require(os.geteuid() == 0 and os.uname()[0] == 'QNX' and struct.calcsize('P') == 4, 'root_qnx_required')
    verify_os()
    stage = os.path.dirname(os.path.abspath(__file__))
    require(re.match(r'\A/var/bb10_rec_app_stage_[a-f0-9]{32}\Z', stage), 'invalid_stage')
    private_directory(stage)
    release = load(stage + '/release.json')
    require(release.get('schema') == 1 and release['identity']['Package-Name'] == PACKAGE_NAME, 'invalid_release')
    private_directory(BASE, True)
    private_directory(BASE + '/jobs', True)
    action = sys.argv[1] if len(sys.argv) >= 2 else 'inspect'
    if action == 'install':
        require(len(sys.argv) == 3, 'invalid_request')
        return provision(release, stage, sys.argv[2])
    return device_summary(release)


if __name__ == '__main__':
    os.umask(0o077)
    stage_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        res = main()
        cleanup_stage(stage_dir)
        res['stage_removed'] = True
        print(json.dumps(res, sort_keys=True))
    except Exception as exc:
        try:
            if re.match(r'\A/var/bb10_rec_app_stage_[a-f0-9]{32}\Z', stage_dir) and os.path.isdir(stage_dir):
                cleanup_stage(stage_dir)
        except Exception:
            pass
        print(json.dumps({'schema': 1, 'state': 'error', 'can_install': False,
                          'error': str(exc) if isinstance(exc, InstallError) else ('unexpected:' + str(exc))}))
