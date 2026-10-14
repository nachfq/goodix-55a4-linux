#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Three no-hardware FpContext inventory fixtures using cached runtime inputs."""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CHILD = ROOT / 'scripts/helpers/usb-inventory-test-child.py'
CHILD_SHA256 = '796591446ea842b3372ea40e65c48d4760bda07edc3b84a111ea43d1f897e570'


def run():
    if os.geteuid() == 0:
        raise RuntimeError('Run as the regular user, without sudo')
    spec = importlib.util.spec_from_file_location('session', ROOT / 'scripts/17-fprintd-session.py')
    session = importlib.util.module_from_spec(spec); spec.loader.exec_module(session)
    assets = session.inputs()
    child = session.previous().checked_bytes(CHILD, CHILD_SHA256)
    metadata = session.metadata_module()
    # Invented descriptor, not copied from the real sensor. No strings/biometrics.
    d = bytearray(18); d[:2] = b'\x12\x01'; d[2:4] = b'\x00\x02'; d[7] = 64
    d[8:12] = b'\xc6\x27\xa4\x55'; d[17] = 1
    descriptors = bytes(d) + bytes((9,2,32,0,1,1,0,128,50,9,4,0,0,2,255,0,0,0,
                                    7,5,1,2,64,0,0,7,5,130,2,64,0,0))
    session.parse_descriptors(descriptors)
    with tempfile.TemporaryDirectory(prefix='usb-inventory-fixture-', dir=ROOT / 'work') as tmp:
        folder = Path(tmp)
        (folder / 'child.py').write_bytes(child)
        (folder / 'libfprint-2.so.2.0.0').write_bytes(assets['libfprint-2.so.2.0.0'])
        for name in ('child.py', 'libfprint-2.so.2.0.0'): (folder / name).chmod(0o444)
        metadata.create(folder / 'sys', '/dev/bus/usb/003/003', descriptors)
        metadata.check(folder / 'sys', '/dev/bus/usb/003/003', descriptors)
        for view, permit, expected in ((False, False, 0), (True, False, 0), (True, True, 1)):
            command = ['/usr/bin/bwrap','--unshare-all','--die-with-parent','--new-session',
                       '--cap-drop','ALL','--ro-bind','/nix/store','/nix/store',
                       '--ro-bind',str(folder),'/experiment','--proc','/proc',
                       '--dev','/dev','--tmpfs','/run','--tmpfs','/tmp','--clearenv',
                       '--setenv','OPENBLAS_NUM_THREADS','1','--setenv','OMP_NUM_THREADS','1',
                       '--setenv','DEBUGINFOD_URLS','']
            if view: command += ['--ro-bind', str(folder / 'sys'), '/sys']
            if permit: command += ['--setenv', 'SYSTEMD_DEVICE_VERIFY_SYSFS', '0']
            command += ['--',session.PYTHON,'-I','-B','-S','/experiment/child.py',str(expected)]
            result = subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,
                                    timeout=15,env={'DEBUGINFOD_URLS':''})
            if result.returncode or result.stdout != b'PASS SYNTHETIC_USB_INVENTORY\n':
                # This fixture has no USB nodes or private user data; diagnostic
                # output is bounded and must stay in ignored local test logs.
                raise RuntimeError('Offline inventory fixture failed: ' +
                                   result.stderr[:2000].decode('utf8',errors='replace'))
    print('PASS: missing sysfs/default verification give zero readers; verified synthetic view gives one goodixtls55x4.')
    print('Actual FpContext enumeration; no USB nodes, device open, capture, bus or host sysfs.')


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--run',action='store_true')
    args = parser.parse_args()
    try:
        if args.run: run()
        else: print(__doc__ + ' Default describes only; --run opens no hardware.')
        return 0
    except (OSError,RuntimeError,subprocess.SubprocessError) as error:
        print('Offline inventory fixture stopped:',error,file=sys.stderr); return 1


if __name__ == '__main__':
    sys.exit(main())
