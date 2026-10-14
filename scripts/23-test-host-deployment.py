#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check bundle relocation and service syntax offline, without installing it."""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'work/host-deployment-bundle'
PYTHON='/nix/store/xqnbm0vgqcq9b1b54c80qj9s0qhbwa08-python3-3.13.15/bin/python3.13'
CHILD=ROOT/'scripts/helpers/host-load-test-child.py'
CHILD_SHA256='96f179a408e375de98bf86860a99266885e0f4df0cfa7c8b2d25301ef1ce441c'


def run():
    if os.geteuid()==0: raise RuntimeError('Run offline checks as regular user, without sudo')
    spec=importlib.util.spec_from_file_location('prepare',ROOT/'scripts/21-prepare-host-deployment.py')
    prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)
    deploy=prepare.module();deploy.bundle(BUNDLE)
    if CHILD.is_symlink() or hashlib.sha256(CHILD.read_bytes()).hexdigest()!=CHILD_SHA256:
        raise RuntimeError('Offline load fixture source changed')
    command=['/usr/bin/bwrap','--unshare-all','--uid','0','--gid','0','--die-with-parent','--new-session',
             '--cap-drop','ALL','--ro-bind','/nix/store','/nix/store',
             '--ro-bind',str(BUNDLE),str(deploy.PREFIX),'--ro-bind',str(CHILD),'/test.py',
             '--proc','/proc','--dev','/dev','--tmpfs','/run','--tmpfs','/tmp','--clearenv',
             '--setenv','OPENBLAS_NUM_THREADS','1','--setenv','OMP_NUM_THREADS','1',
             '--setenv','DEBUGINFOD_URLS','','--',PYTHON,'-I','-B','-S','/test.py']
    result=subprocess.run(command,capture_output=True,timeout=35,env={'DEBUGINFOD_URLS':''})
    if result.returncode or result.stdout!=b'PASS RELOCATED_HOST_LOAD\n' or result.stderr:
        raise RuntimeError('Offline relocation failed: '+result.stderr[:2000].decode('utf8',errors='replace'))
    with tempfile.TemporaryDirectory(prefix='host-unit-verify-',dir=ROOT/'work') as tmp:
        folder=Path(tmp);(folder/'fprintd.service').write_bytes(deploy.read(Path('/usr/lib/systemd/system/fprintd.service')))
        (folder/'fprintd.service.d').mkdir()
        (folder/'fprintd.service.d/90-thinkpad-fingerprint.conf').write_bytes(deploy.unit())
        command=['/usr/bin/bwrap','--unshare-all','--uid','0','--gid','0','--die-with-parent','--new-session',
                 '--cap-drop','ALL','--ro-bind','/usr','/usr','--symlink','usr/lib','/lib',
                 '--symlink','usr/lib','/lib64','--ro-bind','/nix/store','/nix/store',
                 '--ro-bind',str(folder),'/unit','--proc','/proc','--dev','/dev','--tmpfs','/run','--tmpfs','/tmp',
                 '--dir','/empty','--clearenv','--setenv','SYSTEMD_LOG_LEVEL','warning',
                 '--setenv','SYSTEMD_ENVIRONMENT_GENERATOR_PATH','/empty','--setenv','DEBUGINFOD_URLS','',
                 '--chdir','/','--','/usr/bin/systemd-analyze','--man=no','--generators=no',
                 'verify','/unit/fprintd.service']
        result=subprocess.run(command,capture_output=True,timeout=20,env={'DEBUGINFOD_URLS':''})
        if result.returncode or result.stderr:
            raise RuntimeError('Offline unit verification failed: '+result.stderr[:2000].decode('utf8',errors='replace'))
    print('PASS: exact relocated daemon/library loader maps and daemon help; generated unit verified by systemd-analyze.')
    print('Private namespaces: no host bus, USB nodes, host sysfs, native device open, installation or service activation.')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',action='store_true')
    args=parser.parse_args()
    try:
        if args.run: run()
        else: print(__doc__+' Default describes only. --run requires the prepared local bundle.')
        return 0
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as error:
        print('Host deployment offline check stopped:',error,file=sys.stderr);return 1


if __name__=='__main__':sys.exit(main())
