# SPDX-License-Identifier: MIT
"""A disposable USB inventory view; never reads host sysfs or opens a device."""
import os
from pathlib import Path
import re
import stat


DIRECTORIES = {'bus', 'bus/usb', 'bus/usb/devices', 'devices', 'devices/selected',
               'devices/selected/reader'}
LINKS = {'bus/usb/devices/reader': '../../../devices/selected/reader',
         'devices/selected/reader/subsystem': '../../../bus/usb'}


def files(node, descriptors):
    match = re.fullmatch(r'/dev/bus/usb/([0-9]{3})/([0-9]{3})', node) if isinstance(node, str) else None
    if not match or not isinstance(descriptors, bytes) or not 18 <= len(descriptors) <= 16384:
        raise RuntimeError('Invalid private USB metadata inputs')
    bus, address = map(int, match.groups())
    if not 1 <= bus <= 255 or not 1 <= address <= 127 or descriptors[:2] != b'\x12\x01' or descriptors[8:12] != b'\xc6\x27\xa4\x55':
        raise RuntimeError('Private USB metadata identity differs')
    minor = (bus - 1) * 128 + address - 1
    version = int.from_bytes(descriptors[12:14], 'little')
    uevent = (f'MAJOR=189\nMINOR={minor}\nDEVNAME=bus/usb/{bus:03d}/{address:03d}\n'
              f'DEVTYPE=usb_device\nPRODUCT=27c6/55a4/{version:x}\n'
              f'TYPE={descriptors[4]}/{descriptors[5]}/{descriptors[6]}\n'
              f'BUSNUM={bus:03d}\nDEVNUM={address:03d}\n')
    attributes = {'descriptors': descriptors, 'busnum': f'{bus}\n'.encode(),
                  'devnum': f'{address}\n'.encode(), 'dev': f'189:{minor}\n'.encode(),
                  'bConfigurationValue': b'1\n', 'uevent': uevent.encode('ascii')}
    return {'devices/selected/reader/' + name: data for name, data in attributes.items()}


def create(root, node, descriptors):
    root = Path(root)
    root.mkdir(mode=0o755)
    for name in sorted(DIRECTORIES, key=lambda x: (x.count('/'), x)):
        (root / name).mkdir(mode=0o755)
    for name, target in LINKS.items():
        (root / name).symlink_to(target)
    for name, data in files(node, descriptors).items():
        path = root / name
        path.write_bytes(data)
        path.chmod(0o444)
    for name in DIRECTORIES | {''}:
        (root / name).chmod(0o755)


def check(root, node, descriptors):
    """Reject extra entries, noncanonical links, writable files and mutations."""
    root = Path(root)
    expected = files(node, descriptors)
    if not stat.S_ISDIR(root.lstat().st_mode) or stat.S_IMODE(root.lstat().st_mode) != 0o755:
        raise RuntimeError('Private USB metadata root differs')
    seen = set()
    for directory, dirs, names in os.walk(root, followlinks=False):
        for name in dirs + names:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            seen.add(relative)
            info = path.lstat()
            if relative in LINKS:
                valid = stat.S_ISLNK(info.st_mode) and os.readlink(path) == LINKS[relative]
            elif relative in DIRECTORIES:
                valid = stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o755
            elif relative in expected:
                valid = (stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                         stat.S_IMODE(info.st_mode) == 0o444 and info.st_size == len(expected[relative]) and
                         path.read_bytes() == expected[relative])
            else:
                valid = False
            if not valid:
                raise RuntimeError('Private USB metadata entry differs')
    if seen != DIRECTORIES | LINKS.keys() | expected.keys():
        raise RuntimeError('Private USB metadata inventory differs')
