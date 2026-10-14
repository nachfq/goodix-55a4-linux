#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Restore only the saved sudo/SDDM PAM files; default mode describes the action."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

BACKUP = Path('/etc/thinkpad-fingerprint-auth')
TARGETS = ('sudo', 'sddm')


def checked(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1 or info.st_mode & 0o022:
        raise RuntimeError('Unsafe authentication file: ' + str(path))
    return path.read_bytes()


def replace(path, data, mode):
    fd, temporary = tempfile.mkstemp(prefix='.thinkpad-fingerprint-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            os.fchown(stream.fileno(), 0, 0)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def restore():
    if os.geteuid() != 0:
        raise RuntimeError('Run with normal root authorization')
    for directory in (Path('/etc'), Path('/etc/pam.d'), BACKUP):
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise RuntimeError('Unsafe authentication directory')
    if {p.name for p in BACKUP.iterdir()} != {'manifest.json', 'restore.py', *TARGETS}:
        raise RuntimeError('Foreign backup entries; review before removal')
    manifest = json.loads(checked(BACKUP / 'manifest.json'))
    if set(manifest) != {'format', 'files'} or manifest['format'] != 1 or set(manifest['files']) != set(TARGETS):
        raise RuntimeError('Backup manifest differs')
    originals = {}
    for name in TARGETS:
        record = manifest['files'][name]
        original = checked(BACKUP / name)
        if hashlib.sha256(original).hexdigest() != record['before']:
            raise RuntimeError('Saved original changed')
        current = checked(Path('/etc/pam.d') / name)
        if hashlib.sha256(current).hexdigest() not in (record['before'], record['after']):
            raise RuntimeError('PAM file changed later; refusing overwrite')
        originals[name] = original
    # An interrupted restoration can be repeated: both before/after are accepted.
    for name in TARGETS:
        replace(Path('/etc/pam.d') / name, originals[name], manifest['files'][name]['mode'])
    for name in (*TARGETS, 'manifest.json', 'restore.py'):
        (BACKUP / name).unlink()
    BACKUP.rmdir()
    print('Restored the original sudo/SDDM PAM files and removed only their backup namespace.')
    print('Fingerprint screen unlock and enrolled templates remain unchanged.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--remove', action='store_true')
    args = parser.parse_args()
    if not args.remove:
        print(__doc__ + ' Use --remove with root authorization to restore.')
        return 0
    try:
        restore()
        return 0
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        print('PAM restoration stopped:', error, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
