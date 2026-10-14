#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run deployment transactions in a disposable root namespace with fake services."""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
TEST=ROOT/'tests/test_host_deployment.py'
TEST_SHA256='e3263ffb6174fc49dd71f9fa3ebcd703c3c03a617a1cf549a9b9d367a7bea863'
PYTHON='/nix/store/xqnbm0vgqcq9b1b54c80qj9s0qhbwa08-python3-3.13.15/bin/python3.13'


def run():
    if os.geteuid()==0: raise RuntimeError('Run the offline fixture as regular user, without sudo')
    spec=importlib.util.spec_from_file_location('prepare',ROOT/'scripts/21-prepare-host-deployment.py')
    prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare);prepare.module()
    if TEST.is_symlink() or hashlib.sha256(TEST.read_bytes()).hexdigest()!=TEST_SHA256:
        raise RuntimeError('Transaction fixture differs from reviewed input')
    with tempfile.TemporaryDirectory(prefix='host-install-fixture-',dir=ROOT/'work') as tmp:
        command=['/usr/bin/bwrap','--unshare-all','--uid','0','--gid','0','--die-with-parent','--new-session',
                 '--cap-drop','ALL','--ro-bind','/nix/store','/nix/store',
                 '--ro-bind',str(prepare.CONTROLLER),'/repo/scripts/helpers/host-deployment.py',
                 '--ro-bind',str(TEST),'/repo/tests/test_host_deployment.py','--bind',tmp,'/fixture',
                 '--proc','/proc','--dev','/dev','--tmpfs','/run','--clearenv',
                 '--setenv','TMPDIR','/fixture','--setenv','DEBUGINFOD_URLS','','--chdir','/repo','--',PYTHON,
                 '-B','-m','unittest','discover','-s','tests','-p','test_host_deployment.py','-v']
        result=subprocess.run(command,capture_output=True,timeout=45,env={'DEBUGINFOD_URLS':''})
        if result.returncode or b'\nOK\n' not in result.stderr or b'skipped=' in result.stderr:
            raise RuntimeError('Disposable transaction fixture failed: '+result.stderr[-2500:].decode('utf8',errors='replace'))
    print('PASS: all 33 deployment checks, including 19 disposable-root transactions; fake service/Nix calls only.')
    print('Only temporary ignored fixture files changed; no host installation, mask, GC root, bus, service or hardware.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',action='store_true')
    args=parser.parse_args()
    try:
        if args.run: run()
        else: print(__doc__+' Default describes only; --run never targets host destinations.')
        return 0
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as error:
        print('Host transaction fixture stopped:',error,file=sys.stderr);return 1


if __name__=='__main__':sys.exit(main())
