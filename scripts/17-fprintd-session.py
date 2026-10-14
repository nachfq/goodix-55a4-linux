#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""A temporary private fprintd/Polkit bus. Hardware execution is owner-run only."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
CHILD = ROOT / 'scripts/helpers/fprintd-sandbox-child.py'
CHILD_SHA256 = 'ab4f91316327b6e242abe21e07e71592050743a1cf3577814a14ed063892075d'
METADATA = ROOT / 'scripts/helpers/usb-metadata.py'
METADATA_SHA256 = '97f48f6f855cc365c8bd35dd0283643928cc720dba545c1242b19efab6e3a337'
LOADER = '/nix/store/m07h00fl6538s4gavrp66a20ka4hg7fy-glibc-2.42-67/lib/ld-linux-x86-64.so.2'
PYTHON = '/nix/store/xqnbm0vgqcq9b1b54c80qj9s0qhbwa08-python3-3.13.15/bin/python3.13'
GDBUS = '/nix/store/710l5vynifaaz5nghq087zwr8zvf6nrc-glib-2.88.3-bin/bin/gdbus'
LIBRARY_PATH = ':'.join([
    '/experiment',
    '/nix/store/wpwksxna2lp2y0px8xnxwgs0rfary570-glib-2.88.3/lib',
    '/nix/store/z0n70pxyzi87why1bcq81zgd7b924nfj-gcc-15.2.0-lib/lib',
    '/nix/store/m07h00fl6538s4gavrp66a20ka4hg7fy-glibc-2.42-67/lib',
    '/nix/store/aadqqqrfvi7mdnk28h366irf6f1s09mb-systemd-minimal-libs-260.2/lib',
    '/nix/store/ac5ncnyqg8wvpbbhc8knlck2i1vv3p5y-dbus-1.16.2-lib/lib',
    '/nix/store/x06hz419w6lkhh8qxaa353zw1h47snfx-expat-2.8.3/lib',
    '/nix/store/4qhmizki1n0i0rp64203wnqff73anv8l-audit-4.2.1-lib/lib',
    '/nix/store/0q9vgj48awrcm6l14fccdbjjqsbmh921-libcap-ng-0.9.3/lib',
])
# Exact installed binaries and policy are copied into a disposable read-only mount.
INPUTS = {'fprintd': ('/usr/lib/fprintd', '0cc52495262817b08f44dfe30181e5e2d065fd7a7867b89b643d20764a321949'),
 'fprintd-list': ('/usr/bin/fprintd-list',
                  '6400e302fce39a4f1c201ff87ef4cfe26507b99bec4bab99afc14dd647bd3a59'),
 'fprintd-enroll': ('/usr/bin/fprintd-enroll',
                    'adf2728bf891cbb2eb7b971a6a50084a1beb6afe8c98715f1249e9630eea2eeb'),
 'fprintd-verify': ('/usr/bin/fprintd-verify',
                    '3bb517fa96fd93d01e3c6aefadff6185ec191b91924163778b5251e71adf73ce'),
 'dbus-daemon': ('/usr/bin/dbus-daemon', 'e9ffeaea83965fa53077f716e352d3038794200bacb8eee043fe55117ce2c7d7'),
 'polkitd': ('/usr/lib/polkit-1/polkitd', '35fe074d5370afccd79b0d4b50b5d88c88822c075f28e96563d700707aee7c60'),
 'libpolkit-gobject-1.so.0': ('/usr/lib/libpolkit-gobject-1.so.0.0.0',
                              'ba7407fd501b1e6d1d12b795ca78909addf444c723270c442cd6efe935354a0a'),
 'libduktape.so.207': ('/usr/lib/libduktape.so.207.20700',
                       'af2c5a3acc2a8e341660128b47fe6f5b1579404501af46dfe14836432d6781d8'),
 'fprint-policy': ('/usr/share/polkit-1/actions/net.reactivated.fprint.device.policy',
                   '06b50c015ba54c7b847ff873222c8bd5e9a68ec3ba0d6d48949fe846fbd0a033'),
 'libfprint-observer.so': ('work/fprintd-observer-build/libfprint-observer.so',
                           '172e8a7ff187c7fa2965060f12e41d418b67cae706b329a8fe75b3e62cf96365')}  # Filled from inspected installed paths; no acquisition or fallback.
RUNTIME_PINS = {'/usr/bin/bwrap': '7c44fa8e7326e62e81ab3f70ff682bfc0eb3b447b39cf9fbb779a31948364762',
 '/nix/store/m07h00fl6538s4gavrp66a20ka4hg7fy-glibc-2.42-67/lib/ld-linux-x86-64.so.2': 'fc12fce42e865e7feaa49c686076debb51be1a711952a3180491340c1ae3e70f',
 '/nix/store/xqnbm0vgqcq9b1b54c80qj9s0qhbwa08-python3-3.13.15/bin/python3.13': '56f78bdc0ad95ef4c2723243bbffb99a64fbef8b190916eecf8b1660137adfca',
 '/nix/store/710l5vynifaaz5nghq087zwr8zvf6nrc-glib-2.88.3-bin/bin/gdbus': 'a9e0b32770f57df78973d39f7778b00af257a0fb43a21610bb7aca4331f92630'}  # Nix runtime executables and bubblewrap.
DBUS_CONFIG = '''<busconfig>
  <type>system</type><listen>unix:path=/run/fprintd-test/bus</listen>
  <auth>EXTERNAL</auth>
  <policy context="default"><allow user="*"/><allow own="*"/>
    <allow send_destination="*"/><allow receive_sender="*"/></policy>
</busconfig>'''
MAX_FILE = 4 * 1024 * 1024
MAX_ENTRIES = 64


def previous():
    spec = importlib.util.spec_from_file_location('private_experiment', ROOT / 'scripts/14-enroll-verify.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inputs():
    p = previous()
    spec = importlib.util.spec_from_file_location('observer_build', ROOT / 'scripts/18-build-fprintd-observer.py')
    build = importlib.util.module_from_spec(spec); spec.loader.exec_module(build)
    build.check_inputs()
    library, _unused = p.checked_inputs()
    assets = {'libfprint-2.so.2.0.0': library, 'child.py': p.checked_bytes(CHILD, CHILD_SHA256),
              'usb-metadata.py': p.checked_bytes(METADATA, METADATA_SHA256)}
    for name, (path, digest) in INPUTS.items():
        input_path = Path(path)
        if not input_path.is_absolute(): input_path = ROOT / input_path
        assets[name] = p.checked_bytes(input_path, digest)
    for path, digest in RUNTIME_PINS.items():
        p.checked_bytes(Path(path), digest)
    account = pwd.getpwnam('polkitd')
    if (account.pw_uid, account.pw_gid) != (102, 102):
        raise RuntimeError('Installed Polkit identity differs from reviewed configuration')
    if not INPUTS or not RUNTIME_PINS:
        raise RuntimeError('Runtime input pins are incomplete')
    return assets


def metadata_module():
    previous().checked_bytes(METADATA, METADATA_SHA256)
    spec = importlib.util.spec_from_file_location('private_usb_metadata', METADATA)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def plan():
    print('Lesson 17: installed fprintd and CLI on a private bus, not system integration')
    print('Default/--check-inputs do not load libraries, inspect USB or start services.')
    print('--smoke is offline: real daemon/Polkit/CLI, private namespaces, no USB or host bus.')
    print('--run --detect|--enroll|--verify requires one-shot sudo and exact confirmation.')
    print('Only one selected 27c6:55a4 node is visible; all other USB, host sysfs, home,')
    print('system/session buses, service sockets and network are excluded.')
    print('A read-only synthetic /sys contains only selected-reader inventory metadata,')
    print('built from its already checked cached descriptors and USB bus/address.')
    print('Polkit uses installed policy on its private bus; host rules/services are unchanged.')
    print('Hardware commands may initialize/reset/calibrate/use TLS, LEDs, frames and sleep.')
    print('No key/firmware writes, PAM/login/lock setup, downloads, packages or installation.')
    print('fprintd uses its own private RIGHT INDEX enrollment under ignored work/private-fprintd/.')
    print('The earlier standalone template is preserved, not imported or overwritten.')
    print('Private state is caller-owned 0700/0600 after exit; --cleanup removes only this series.')
    print('Each command starts/stops the private daemons; no background service remains.')
    print('Enrollment may need 16 scans; keep off for calibration, touch on LED, lift on prompts.')
    print('The observer checks actual library verification/close results; CLI no-match alone')
    print('cannot count as rejection. Errors/retries/cancellation/deadlines are inconclusive.')
    print('Forced exit cannot prove sensor sleep. Parent limits: detect/verify120s, enroll750s.')


def parse_descriptors(data):
    """Validate cached standard USB descriptors, never sending USB requests."""
    if not 18 <= len(data) <= 16384 or data[:2] != b'\x12\x01':
        raise RuntimeError('Unexpected cached USB descriptors')
    if data[8:12] != b'\xc6\x27\xa4\x55':
        raise RuntimeError('Cached USB identity differs')
    interfaces, endpoints = [], []
    at, active = 0, False
    while at < len(data):
        size = data[at]
        if size < 2 or at + size > len(data):
            raise RuntimeError('Truncated cached USB descriptor')
        row = data[at:at + size]
        if row[1] == 4:
            active = size == 9 and row[2:5] == bytes((0, 0, 2)) and row[5] in (10, 255)
            interfaces.append(active)
        elif row[1] == 5 and active:
            if size < 7 or row[3] & 3 != 2:
                raise RuntimeError('Unexpected USB endpoint type')
            endpoints.append(row[2])
        at += size
    if interfaces != [True] or sorted(endpoints) != [1, 130]:
        raise RuntimeError('Unexpected USB interface/endpoint layout')


def select_usb(sysfs=Path('/sys/bus/usb/devices'), dev=Path('/dev/bus/usb')):
    matches = []
    for path in sysfs.iterdir():
        try:
            vid = (path / 'idVendor').read_text().strip()
            pid = (path / 'idProduct').read_text().strip()
        except FileNotFoundError:
            continue
        if (vid, pid) == ('27c6', '55a4'):
            matches.append(path)
    if len(matches) != 1:
        raise RuntimeError('Exactly one 27c6:55a4 is required')
    path = matches[0]
    descriptors = (path / 'descriptors').read_bytes()
    parse_descriptors(descriptors)
    if (path / 'bConfigurationValue').read_text().strip() != '1':
        raise RuntimeError('Unexpected active USB configuration')
    interface = path.parent / (path.name + ':1.0')
    if os.path.lexists(interface / 'driver'):
        raise RuntimeError('A kernel driver owns the interface; no detach permitted')
    if (interface / 'bAlternateSetting').read_text().strip() != '0':
        raise RuntimeError('Unexpected USB alternate setting')
    bus, address = int((path / 'busnum').read_text()), int((path / 'devnum').read_text())
    if not 1 <= bus <= 255 or not 1 <= address <= 127:
        raise RuntimeError('Unexpected USB bus/address')
    node = dev / f'{bus:03d}' / f'{address:03d}'
    fd = os.open(node, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC)
    info = os.fstat(fd)
    if not stat.S_ISCHR(info.st_mode) or os.major(info.st_rdev) != 189 or os.minor(info.st_rdev) != (bus - 1) * 128 + address - 1:
        os.close(fd)
        raise RuntimeError('USB node identity differs')
    if info.st_uid != 0 or info.st_mode & 0o600 != 0o600:
        os.close(fd)
        raise RuntimeError('Selected USB node must be root-owned and root-readable/writable')
    return fd, f'/dev/bus/usb/{bus:03d}/{address:03d}', descriptors


def scan_state(fd, change_owner=None, prefix='', result=None, budget=None):
    """Bounded no-follow traversal: reject links/devices before ownership or hashing."""
    if result is None:
        result = {}
    if budget is None:
        budget = [0]
    if prefix.count('/') > 8:
        raise RuntimeError('Private state traversal exceeds limits')
    for name in sorted(os.listdir(fd)):
        budget[0] += 1
        if budget[0] > MAX_ENTRIES:
            raise RuntimeError('Private state traversal exceeds limits')
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', name):
            raise RuntimeError('Unexpected private state filename')
        key = prefix + name
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if stat.S_ISDIR(info.st_mode):
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                scan_state(child, change_owner, key + '/', result, budget)
                if change_owner:
                    os.fchown(child, *change_owner); os.fchmod(child, 0o700)
            finally:
                os.close(child)
        elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 3 < info.st_size <= MAX_FILE:
            file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                current = os.fstat(file_fd)
                if current.st_ino != info.st_ino or current.st_dev != info.st_dev:
                    raise RuntimeError('Private state changed during inspection')
                data = os.read(file_fd, MAX_FILE + 1)
                if len(data) != current.st_size or not data.startswith(b'FP3'):
                    raise RuntimeError('Unexpected private state content format')
                result[key] = hashlib.sha256(data).hexdigest()
                if change_owner:
                    os.fchown(file_fd, *change_owner); os.fchmod(file_fd, 0o600)
            finally:
                os.close(file_fd)
        else:
            raise RuntimeError('Unexpected private state type/link/size')
        if len(result) > MAX_ENTRIES or prefix.count('/') > 8:
            raise RuntimeError('Private state traversal exceeds limits')
    if change_owner:
        os.fchown(fd, *change_owner); os.fchmod(fd, 0o700)
    return result


def remove_state(fd, depth=0, budget=None):
    if budget is None:
        budget = [0]
    if depth > 8:
        raise RuntimeError('Cleanup depth exceeds limit')
    for name in os.listdir(fd):
        budget[0] += 1
        if budget[0] > MAX_ENTRIES + 1:
            raise RuntimeError('Cleanup entries exceed limit')
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if stat.S_ISDIR(info.st_mode):
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                remove_state(child, depth + 1, budget)
            finally:
                os.close(child)
            os.rmdir(name, dir_fd=fd)
        elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
            os.unlink(name, dir_fd=fd)
        else:
            raise RuntimeError('Refusing unexpected private cleanup entry')


def private_state(p, uid, gid, mode):
    work = p.open_directory(ROOT / 'work')
    try:
        try:
            os.mkdir('private-fprintd', 0o700, dir_fd=work)
        except FileExistsError:
            pass
        directory = os.open('private-fprintd', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=work)
    finally:
        os.close(work)
    try:
        info = os.fstat(directory)
        if info.st_uid not in (uid, 0) or stat.S_IMODE(info.st_mode) != 0o700:
            raise RuntimeError('Private directory ownership/permissions differ')
        fcntl.flock(directory, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if mode == 'enroll' and os.listdir(directory):
            raise RuntimeError('Enrollment never overwrites an existing series')
        if mode == 'enroll':
            os.mkdir('state', 0o700, dir_fd=directory)
        if mode == 'verify' and set(os.listdir(directory)) != {'state', 'series.json'}:
            raise RuntimeError('Frozen fprintd series is incomplete')
        state = os.open('state', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
        return directory, state
    except BaseException:
        os.close(directory)
        raise


def snapshot_manifest(snapshot):
    return {'format': 1, 'finger': 'right-index-finger', 'state': snapshot,
            'library': previous().LIBRARY_SHA256, 'inputs': INPUTS, 'child': CHILD_SHA256}


def check_private_metadata(fd, uid, depth=0):
    if depth > 8:
        raise RuntimeError('Private metadata traversal exceeds limit')
    info = os.fstat(fd)
    if info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o700:
        raise RuntimeError('Private state directory ownership/permissions differ')
    for name in os.listdir(fd):
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
        if stat.S_ISDIR(info.st_mode):
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            try: check_private_metadata(child, uid, depth + 1)
            finally: os.close(child)
        elif not stat.S_ISREG(info.st_mode) or info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o600:
            raise RuntimeError('Private state file ownership/permissions differ')


def frozen_state(p, directory, state, uid):
    current = scan_state(state)
    check_private_metadata(state, uid)
    if len(current) != 1:
        raise RuntimeError('Expected exactly one enrolled private print')
    stored = json.loads(p.private_bytes(directory, 'series.json', uid, 16384))
    # JSON converts tuple input pins to lists.
    expected = json.loads(json.dumps(snapshot_manifest(current)))
    if stored != expected:
        raise RuntimeError('Frozen state or experiment inputs differ; stop before USB')
    return current


def persist(directory, state, uid, gid):
    snapshot = scan_state(state)
    if len(snapshot) != 1:
        raise RuntimeError('Enrollment did not produce exactly one private print')
    data = (json.dumps(snapshot_manifest(snapshot), sort_keys=True) + '\n').encode()
    fd = os.open('series.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    try:
        os.fchmod(fd, 0o600); os.fchown(fd, uid, gid)
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(data); stream.flush(); os.fsync(fd)
    finally:
        os.close(fd)
    os.fsync(directory)


def configuration(assets, mode, expected, username, usb_node, smoke):
    return {'mode': mode, 'expected': expected, 'username': username, 'usb_node': usb_node,
            'host_namespaces': {n: os.readlink('/proc/self/ns/' + n) for n in ('mnt', 'net', 'pid')},
            'artifacts': {n: hashlib.sha256(v).hexdigest() for n, v in assets.items()},
            'loader': LOADER, 'library_path': LIBRARY_PATH, 'gdbus': GDBUS,
            'polkit_uid': 0 if smoke else 102}


def sandbox(folder, state, usb_fd, usb_node, smoke):
    flags = ['--unshare-all', '--uid', '0', '--gid', '0'] if smoke else [
        '--unshare-pid', '--unshare-ipc', '--unshare-net', '--unshare-uts', '--unshare-cgroup-try']
    command = ['/usr/bin/bwrap', *flags, '--die-with-parent', '--new-session', '--cap-drop', 'ALL']
    if not smoke:
        command += ['--cap-add', 'CAP_SETUID', '--cap-add', 'CAP_SETGID', '--cap-add', 'CAP_KILL']
    command += ['--ro-bind', '/nix/store', '/nix/store', '--ro-bind', str(folder), '/experiment',
                '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--tmpfs', '/run',
                '--ro-bind', str(folder / 'passwd'), '/etc/passwd',
                '--ro-bind', str(folder / 'group'), '/etc/group',
                '--ro-bind', str(folder / 'nsswitch.conf'), '/etc/nsswitch.conf',
                '--ro-bind', str(folder / 'fprintd.conf'), '/etc/fprintd.conf',
                '--ro-bind', str(folder / 'fprint-policy'), '/usr/share/polkit-1/actions/net.reactivated.fprint.device.policy',
                '--dir', '/etc/polkit-1/rules.d', '--dir', '/usr/share/polkit-1/rules.d', '--dir', '/empty']
    mode = json.loads((folder / 'session.json').read_text())['mode']
    command += ['--ro-bind' if mode == 'verify' else '--bind', str(state), '/state']
    if usb_fd is not None:
        command += ['--dev-bind', f'/proc/self/fd/{usb_fd}', usb_node]
        command += ['--ro-bind', str(folder / 'sys'), '/sys']
    # Implicit bwrap parent directories are 0700 in the root runtime. Polkit
    # drops to UID102 and must traverse NSS/policy/runtime paths. These are
    # synthetic directories only: never chmod a host bind or private state.
    for path in ('/nix', '/etc', '/etc/polkit-1', '/etc/polkit-1/rules.d',
                 '/usr', '/usr/share', '/usr/share/polkit-1',
                 '/usr/share/polkit-1/actions', '/usr/share/polkit-1/rules.d', '/empty'):
        command += ['--chmod', '0755', path]
    command += ['--clearenv', '--setenv', 'OPENBLAS_NUM_THREADS', '1', '--setenv', 'OMP_NUM_THREADS', '1',
                '--setenv', 'DEBUGINFOD_URLS', '', '--chdir', '/experiment', '--', PYTHON,
                '-I', '-B', '-S', '/experiment/child.py']
    return command


def relay(child, limit):
    selector = selectors.DefaultSelector()
    selector.register(child.stdout, selectors.EVENT_READ)
    end, buffer, total, result, closed, failed = time.monotonic() + limit, b'', 0, None, False, False
    messages = {'READY': 'Private fprintd and Polkit are ready.', 'DEVICE_FOUND': 'fprintd exposes the selected reader.',
                'LIFT': 'Lift your finger now.', 'TOUCH': 'Touch again with your RIGHT INDEX finger.',
                'CALIBRATION': 'Keep your finger OFF during calibration; touch only when the physical LED lights.',
                'RETRY': 'Scan retry: inconclusive; lift your finger.', 'CLOSED': 'Private session teardown completed.'}
    try:
        while selector.get_map() or child.poll() is None:
            if time.monotonic() >= end:
                raise subprocess.TimeoutExpired(child.args, limit)
            for key, _events in selector.select(.2):
                block = os.read(key.fd, 1024)
                if not block:
                    selector.unregister(key.fileobj); continue
                total += len(block)
                if total > 16384:
                    raise RuntimeError('Private session report exceeds limit')
                buffer += block
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1); tag = line.decode('ascii')
                    if tag in messages:
                        closed |= tag == 'CLOSED'; print(messages[tag], flush=True)
                    elif re.fullmatch(r'PROGRESS (?:[1-9]|1[0-6]) 16', tag):
                        print('Accepted enrollment scan ' + tag.split()[1] + '/16; lift now.', flush=True)
                    elif re.fullmatch(r'FAIL [A-Z_]{1,40}', tag):
                        failed = True; print('INCONCLUSIVE: ' + tag[5:], flush=True)
                    elif tag in {'RESULT DETECTED', 'RESULT ENROLLED', 'RESULT MATCH', 'RESULT NO_MATCH'}:
                        if result is not None or not closed or failed:
                            raise RuntimeError('Premature or inconsistent session result')
                        result = tag[7:]
                    else:
                        raise RuntimeError('Unexpected private session report; raw diagnostics hidden')
        if child.returncode != 0 or buffer or failed or not closed or result is None:
            raise RuntimeError('Private operation/teardown failed; trial inconclusive')
        return result
    finally:
        selector.close()


def run(mode, expected=None, smoke=False):
    p = previous(); assets = inputs(); uid, gid = p.caller()
    if not smoke and (os.geteuid() != 0 or not sys.stdin.isatty() or not sys.stdout.isatty()):
        raise RuntimeError('Hardware mode requires one-shot sudo and an interactive terminal')
    if smoke and os.geteuid() == 0:
        raise RuntimeError('Offline smoke runs as the regular user, without sudo')
    username = pwd.getpwuid(uid).pw_name
    if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', username):
        raise RuntimeError('Unsupported account name for this bounded experiment')
    directory = state_fd = usb_fd = child = None
    success = False
    before = None
    try:
        if mode in ('enroll', 'verify'):
            directory, state_fd = private_state(p, uid, gid, mode)
            if mode == 'verify':
                before = frozen_state(p, directory, state_fd, uid)
        if not smoke:
            plan()
            confirmation = 'FPRINTD 27c6:55a4 ' + mode.upper()
            if expected:
                confirmation += ' ' + expected.upper()
            if input('Type ' + confirmation + ' to begin, or anything else to stop: ') != confirmation:
                print('Stopped before USB inspection and private daemon startup.')
                return 0
            usb_fd, usb_node, descriptors = select_usb()
            assets['usb-descriptors'] = descriptors
        else:
            usb_node = None
        with tempfile.TemporaryDirectory(prefix='fprintd-session-', dir=ROOT / 'work') as tmp:
            folder = Path(tmp); folder.chmod(0o700)
            assets['dbus.conf'] = DBUS_CONFIG.encode()
            for name, data in assets.items():
                dest = folder / name; dest.write_bytes(data)
                dest.chmod(0o555 if name in ('fprintd', 'polkitd', 'dbus-daemon', 'fprintd-list', 'fprintd-enroll', 'fprintd-verify') else 0o444)
            pk_uid = 0 if smoke else 102
            (folder / 'passwd').write_text(f'root:x:0:0::/:/dev/null\npolkitd:x:{pk_uid}:{pk_uid}::/:/dev/null\n{username}:x:{uid}:{gid}::/:/dev/null\n')
            (folder / 'group').write_text(f'root:x:0:\npolkitd:x:{pk_uid}:\n{username}:x:{gid}:\n')
            (folder / 'nsswitch.conf').write_text('passwd: files\ngroup: files\n')
            (folder / 'fprintd.conf').write_text('[storage]\ntype=file\n')
            for name in ('passwd', 'group', 'nsswitch.conf', 'fprintd.conf'):
                (folder / name).chmod(0o444)
            config = configuration(assets, mode, expected, username, usb_node, smoke)
            (folder / 'session.json').write_text(json.dumps(config)); (folder / 'session.json').chmod(0o444)
            if usb_fd is not None:
                metadata_module().create(folder / 'sys', usb_node, descriptors)
            if state_fd is None:
                state_path = folder / 'state'; state_path.mkdir(mode=0o700)
            else:
                scan_state(state_fd, (0, 0))
                state_path = Path(f'/proc/self/fd/{state_fd}')
            command = sandbox(folder, state_path, usb_fd, usb_node, smoke)
            passed = tuple(fd for fd in (state_fd, usb_fd) if fd is not None)
            child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE if smoke else subprocess.DEVNULL,
                                     pass_fds=passed, start_new_session=True, env={'DEBUGINFOD_URLS': ''})
            if smoke:
                output, errors = child.communicate(timeout=70)
                if child.returncode or output != b'PASS PRIVATE_FPRINTD_SMOKE\n':
                    raise RuntimeError('Offline private runtime failed: ' + repr(output[:1024]) + ' ' + errors[:3000].decode('utf8', errors='replace'))
                print('PASS: private real fprintd/Polkit/CLI runtime, no USB or host bus.')
                success = True; return 0
            result = relay(child, 750 if mode == 'enroll' else 120)
        if state_fd is not None:
            scan_state(state_fd, (uid, gid)); os.fchown(directory, uid, gid)
            if mode == 'enroll':
                if result != 'ENROLLED': raise RuntimeError('Unexpected enrollment result')
                persist(directory, state_fd, uid, gid)
            elif frozen_state(p, directory, state_fd, uid) != before:
                raise RuntimeError('Private state changed; result withheld')
        wanted = {'detect': {'DETECTED'}, 'enroll': {'ENROLLED'}, 'verify': {'MATCH', 'NO_MATCH'}}[mode]
        if result not in wanted:
            raise RuntimeError('Result differs from selected operation')
        success = True
        print('Completed fprintd trial: ' + result)
        if mode == 'verify':
            message, status = p.classify(result, expected); print(message)
            return status
        return 0
    finally:
        p.terminate(child)
        if state_fd is not None:
            try:
                if mode == 'enroll' and not success:
                    remove_state(state_fd)
                    for name in ('series.json',):
                        try: os.unlink(name, dir_fd=directory)
                        except FileNotFoundError: pass
                    os.rmdir('state', dir_fd=directory)
                else:
                    scan_state(state_fd, (uid, gid))
            finally:
                os.fchown(directory, uid, gid); os.fchmod(directory, 0o700)
                os.close(state_fd); os.close(directory)
        if usb_fd is not None: os.close(usb_fd)


def cleanup():
    p = previous(); uid, _gid = p.caller()
    parent = p.open_directory(ROOT / 'work')
    try:
        directory = os.open('private-fprintd', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            if os.fstat(directory).st_uid not in (uid, 0):
                raise RuntimeError('Unexpected cleanup directory ownership')
            if os.fstat(directory).st_uid == 0 and os.geteuid() != 0:
                raise RuntimeError('Interrupted root-owned state requires one-shot sudo for cleanup')
            fcntl.flock(directory, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if not set(os.listdir(directory)).issubset({'state', 'series.json'}):
                raise RuntimeError('Unexpected cleanup contents')
            remove_state(directory)
        finally:
            os.close(directory)
        os.rmdir('private-fprintd', dir_fd=parent)
    finally:
        os.close(parent)
    print('Removed only the private fprintd series; standalone template and sensor key are unchanged.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--plan', action='store_true'); actions.add_argument('--check-inputs', action='store_true')
    actions.add_argument('--smoke', action='store_true'); actions.add_argument('--run', action='store_true')
    actions.add_argument('--cleanup', action='store_true')
    operations = parser.add_mutually_exclusive_group()
    operations.add_argument('--detect', action='store_true'); operations.add_argument('--enroll', action='store_true')
    operations.add_argument('--verify', action='store_true'); parser.add_argument('--expected', choices=('same', 'other'))
    args = parser.parse_args()
    if args.run and not (args.detect or args.enroll or args.verify): parser.error('--run requires an operation')
    if args.verify and not args.expected: parser.error('--verify requires --expected same|other')
    if args.expected and not args.verify: parser.error('--expected requires --verify')
    try:
        if args.smoke: return run('smoke', smoke=True)
        if args.run: return run('detect' if args.detect else 'enroll' if args.enroll else 'verify', args.expected)
        if args.cleanup: cleanup(); return 0
        if args.check_inputs: inputs(); print('Exact input pins match; no load, USB or bus opened.')
        else: plan()
        return 0
    except KeyboardInterrupt:
        print('INCONCLUSIVE: cancelled. Sensor sleep is not proven.', file=sys.stderr); return 130
    except subprocess.TimeoutExpired:
        print('INCONCLUSIVE: deadline exceeded. Sensor sleep is not proven.', file=sys.stderr); return 124
    except (OSError, RuntimeError, ValueError) as error:
        print('Private fprintd stopped: ' + str(error), file=sys.stderr); return 1


if __name__ == '__main__':
    sys.exit(main())
