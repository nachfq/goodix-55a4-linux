#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare a frozen local host-deployment bundle; never install or access USB."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'work/host-deployment-bundle'
CONTROLLER=ROOT/'scripts/helpers/host-deployment.py'
CONTROLLER_SHA256='6f3de5c4ee1c0f8abbf59248f0a6092314df0a751eb422f1b7d30993b549b2df'
COPYING_SHA256='5df07007198989c622f5d41de8d703e7bef3d0e79d62e24332ee739a452af62a'


def module():
    if CONTROLLER.is_symlink() or hashlib.sha256(CONTROLLER.read_bytes()).hexdigest()!=CONTROLLER_SHA256:
        raise RuntimeError('Deployment controller differs from reviewed input')
    spec=importlib.util.spec_from_file_location('host_deployment',CONTROLLER)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def inputs():
    spec=importlib.util.spec_from_file_location('private_session',ROOT/'scripts/17-fprintd-session.py')
    previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
    assets=previous.inputs();deploy=module()
    for name,expected in deploy.HOST_PINS.items():
        if deploy.digest(deploy.read(Path(name)))!=expected:
            raise RuntimeError('Installed host integration differs from inspected version')
    if deploy.LIB_DIRS!=previous.LIBRARY_PATH.split(':')[1:] or deploy.LOADER!=previous.LOADER:
        raise RuntimeError('Host loader differs from private tested runtime')
    copying=previous.previous().checked_bytes(ROOT/'LICENSES/libfprint-LGPL-2.1.txt',COPYING_SHA256)
    notice=(
        'Local experimental Goodix 27c6:55a4 deployment; not an upstream driver release.\n'
        'libfprint/SIGFM/Goodix: LGPL-2.1-or-later; original authors and notices are preserved in source.\n'
        'Sources: TheWeirdDev/libfprint d1ca62a801aa565e67d1a2a47aaa7a33232b7990,\n'
        'Hydrogell/goodix-27c6-55a4-fingerprint-linux fe27b4812d60b4709d3dfb2b72f1e1f2704ede18,\n'
        'plus attributed local patches0001-0004 in nachfq/goodix-55a4-linux.\n'
        'https://github.com/nachfq/goodix-55a4-linux\n'
        'fprintd and libpolkit are frozen local copies of installed Arch packages;\n'
        'their original packages, source/licensing information and host tools remain installed.\n'
        'Nix runtime inputs remain in the shared store, protected by deployment-specific roots on installation.\n'
        'Controller code is original MIT. Bundle is for local use; no binary distribution is performed here.\n'
    ).encode()
    values={'fprintd':assets['fprintd'],
            'lib/libfprint-2.so.2.0.0':assets['libfprint-2.so.2.0.0'],
            'lib/libpolkit-gobject-1.so.0':assets['libpolkit-gobject-1.so.0'],
            'manage.py':CONTROLLER.read_bytes(),'fprintd.conf':deploy.CONFIG,
            'fprintd-dropin.conf':deploy.unit(),'NOTICE':notice,'COPYING':copying}
    return deploy,values


def prepare():
    if os.geteuid()==0: raise RuntimeError('Prepare as regular user, without sudo')
    deploy,values=inputs()
    if os.path.lexists(OUTPUT): raise RuntimeError('Fresh bundle required; no overwrite or automatic deletion')
    subprocess.run(['git','check-ignore','--no-index','-q',str(OUTPUT/'manifest.json')],cwd=ROOT,check=True,timeout=10)
    roots={path:deploy.nix_hash(path) for path in deploy.NIX_ROOTS}
    result=subprocess.run(['/usr/bin/nix-store','--query','--requisites',*deploy.NIX_ROOTS],
                          capture_output=True,text=True,check=True,timeout=15,env={'PATH':'/usr/bin','DEBUGINFOD_URLS':''})
    closure=set(result.stdout.splitlines())
    if not closure or not set(roots)<=closure or any(not Path(path).exists() for path in closure):
        raise RuntimeError('Cached runtime closure incomplete; no automatic acquisition')
    manifest={'format':1,'files':{n:deploy.digest(v) for n,v in values.items()},'roots':roots,'host_pins':deploy.HOST_PINS}
    OUTPUT.mkdir(mode=0o700)
    for name in deploy.DIRS: (OUTPUT/name).mkdir(mode=0o755)
    for name,value in values.items():
        path=OUTPUT/name;path.write_bytes(value);path.chmod(0o755 if name=='fprintd' else 0o644)
    (OUTPUT/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    (OUTPUT/'manifest.json').chmod(0o644)
    deploy.bundle(OUTPUT)
    print('Prepared:',OUTPUT)
    print(f'Existing Nix retention: {len(roots)} direct roots cover {len(closure)} cached store paths; no GC roots created.')
    print('No package/source download, host installation, service change, bus connection, library load or USB access.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group();modes.add_argument('--prepare',action='store_true');modes.add_argument('--check-inputs',action='store_true')
    args=parser.parse_args()
    try:
        if args.prepare: prepare()
        elif args.check_inputs: inputs();print('Exact local inputs match; no native load, dependency acquisition, service or USB.')
        else:
            print(__doc__);module().plan()
            print('--prepare creates only ignored work/host-deployment-bundle/ from existing verified files.')
        return 0
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as error:
        print('Deployment preparation stopped:',error,file=sys.stderr);return 1


if __name__=='__main__':sys.exit(main())
