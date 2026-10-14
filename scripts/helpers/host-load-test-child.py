# SPDX-License-Identifier: MIT
"""Relocated daemon/library loading only; no device or D-Bus setup."""
import os
from pathlib import Path
import subprocess

PREFIX='/opt/thinkpad-fingerprint'
LOADER='/nix/store/m07h00fl6538s4gavrp66a20ka4hg7fy-glibc-2.42-67/lib/ld-linux-x86-64.so.2'


def run():
    for path in ('/sys','/dev/bus/usb','/run/dbus','/home','/usr','/etc'):
        if os.path.lexists(path): raise RuntimeError('Host path exposed to native load fixture')
    import importlib.util
    spec=importlib.util.spec_from_file_location('deployment',PREFIX+'/manage.py')
    deploy=importlib.util.module_from_spec(spec);spec.loader.exec_module(deploy)
    deploy.bundle(Path(PREFIX))
    command=[LOADER,'--inhibit-cache','--library-path',':'.join([PREFIX+'/lib',*deploy.LIB_DIRS]),
             '--preload',PREFIX+'/lib/libfprint-2.so.2.0.0']
    for program in (PREFIX+'/fprintd', PREFIX+'/lib/libfprint-2.so.2.0.0'):
        result=subprocess.run([*command,'--list',program],capture_output=True,timeout=10)
        if result.returncode or result.stderr or not result.stdout: raise RuntimeError('Relocated loader resolution failed')
        for line in result.stdout.decode().splitlines():
            line=line.strip()
            if line.startswith('linux-vdso.so.1 '): continue
            path=line.split('=>',1)[-1].strip().split(' ',1)[0]
            if not path.startswith(('/nix/store/',PREFIX+'/lib/')) or 'not found' in line:
                raise RuntimeError('Relocated loader used an unexpected dependency')
    result=subprocess.run([*command,PREFIX+'/fprintd','--help'],capture_output=True,timeout=10)
    if result.returncode or result.stderr or b'Usage:' not in result.stdout:
        raise RuntimeError('Relocated daemon help failed')
    print('PASS RELOCATED_HOST_LOAD')


if __name__=='__main__':run()
