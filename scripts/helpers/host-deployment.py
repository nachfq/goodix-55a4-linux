#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Contained host fprintd deployment. No action unless explicitly selected."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

PREFIX = Path('/opt/thinkpad-fingerprint')
DROPIN = Path('/etc/systemd/system/fprintd.service.d/90-thinkpad-fingerprint.conf')
GCROOTS = Path('/nix/var/nix/gcroots/thinkpad-fingerprint')
STATE = Path('/var/lib/thinkpad-fingerprint')
MASK = Path('/run/systemd/system/fprintd.service')
LOADER = '/nix/store/m07h00fl6538s4gavrp66a20ka4hg7fy-glibc-2.42-67/lib/ld-linux-x86-64.so.2'
LIB_DIRS = [
'/nix/store/wpwksxna2lp2y0px8xnxwgs0rfary570-glib-2.88.3/lib',
'/nix/store/z0n70pxyzi87why1bcq81zgd7b924nfj-gcc-15.2.0-lib/lib',
'/nix/store/m07h00fl6538s4gavrp66a20ka4hg7fy-glibc-2.42-67/lib',
'/nix/store/aadqqqrfvi7mdnk28h366irf6f1s09mb-systemd-minimal-libs-260.2/lib',
'/nix/store/ac5ncnyqg8wvpbbhc8knlck2i1vv3p5y-dbus-1.16.2-lib/lib',
'/nix/store/x06hz419w6lkhh8qxaa353zw1h47snfx-expat-2.8.3/lib',
'/nix/store/4qhmizki1n0i0rp64203wnqff73anv8l-audit-4.2.1-lib/lib',
'/nix/store/0q9vgj48awrcm6l14fccdbjjqsbmh921-libcap-ng-0.9.3/lib']
NIX_ROOTS = sorted({str(Path(p).parent) for p in LIB_DIRS} | {
'/nix/store/ir0vzwz929f00q98b877rlzm9c2wg44g-libusb-1.0.29',
'/nix/store/dmylqf4vc0fhfgrz9wfqw3ajcan5vb0b-json-glib-1.10.8',
'/nix/store/hqyx3k5a1bad45r979v23bnpglv4vx0l-gusb-0.4.9',
'/nix/store/14cfdqp8w2iw188vhjfaz2wg8pzbghp3-openssl-3.6.3',
'/nix/store/5mb12a455y0i02zchi5filyf6igcx1mg-opencv-4.13.0'})
HOST_PINS = {
'/usr/lib/systemd/system/fprintd.service':'2f78f930b17791c234fdeb6410cf887450c54a9c44fdf8ddbae4696e79e7104d',
'/usr/share/dbus-1/system-services/net.reactivated.Fprint.service':'fc6ccfab6235d96cee67f0bf3998190b6005252726676f21303ddfef61390831',
'/usr/share/dbus-1/system.d/net.reactivated.Fprint.conf':'0c18d42e3b6e7ef00158d24a5cd3755cd4062ce2c8fa1399d9c7aa3da74535e4'}
PAYLOAD_PINS = {
'fprintd':'0cc52495262817b08f44dfe30181e5e2d065fd7a7867b89b643d20764a321949',
'lib/libfprint-2.so.2.0.0':'161c4a9fa432963b30d7303e1f6d8152269254f52850d14a77aae3e53399c2cd',
'lib/libpolkit-gobject-1.so.0':'ba7407fd501b1e6d1d12b795ca78909addf444c723270c442cd6efe935354a0a'}
CONFIG = b'[storage]\ntype=file\n'
MARKER = b'{"format":1,"project":"thinkpad-fingerprint-host"}\n'
FILES = {'fprintd','lib/libfprint-2.so.2.0.0','lib/libpolkit-gobject-1.so.0',
         'manage.py','fprintd.conf','NOTICE','COPYING','fprintd-dropin.conf'}
DIRS = {'lib','empty'}
MAX_FILE = 32 * 1024 * 1024


def digest(data): return hashlib.sha256(data).hexdigest()


def unit():
    library_path=':'.join([str(PREFIX/'lib'),*LIB_DIRS])
    return (f'[Service]\nExecStart=\nExecStart={LOADER} --inhibit-cache --library-path {library_path} '
            f'--preload {PREFIX}/lib/libfprint-2.so.2.0.0 {PREFIX}/fprintd\n'
            'StateDirectory=\nStateDirectory=thinkpad-fingerprint/fprint\nStateDirectoryMode=0700\nUMask=0077\n'
            f'BindReadOnlyPaths={PREFIX}/fprintd.conf:/etc/fprintd.conf\n'
            'ReadWritePaths=\nDeviceAllow=\nDeviceAllow=char-usb_device rw\n'
            'Environment=OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 DEBUGINFOD_URLS=\n'
            f'Environment=GIO_USE_VFS=local GIO_MODULE_DIR={PREFIX}/empty FP_DRIVERS_WHITELIST=goodixtls55x4\n'
            'UnsetEnvironment=LD_PRELOAD LD_LIBRARY_PATH G_MESSAGES_DEBUG LIBUSB_DEBUG DBUS_SYSTEM_BUS_ADDRESS '
            'SYSTEMD_DEVICE_VERIFY_SYSFS FPRINTD_OBSERVER_FD\n'
            'StandardOutput=null\nStandardError=null\nLimitCORE=0\n').encode()


@contextlib.contextmanager
def directory(path, trusted=False):
    path=Path(path)
    if not path.is_absolute(): raise RuntimeError('Absolute path required')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            new=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=new
            info=os.fstat(fd)
            if trusted and (info.st_uid != 0 or info.st_mode & 0o022):
                raise RuntimeError('Untrusted destination directory')
        yield fd
    finally: os.close(fd)


def read(path, limit=MAX_FILE):
    path=Path(path)
    with directory(path.parent) as parent:
        fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent)
        try:
            info=os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
                raise RuntimeError('Unexpected deployment file')
            with os.fdopen(fd,'rb',closefd=False) as stream: data=stream.read(limit+1)
        finally: os.close(fd)
    if len(data)>limit: raise RuntimeError('Deployment file exceeds limit')
    return data


def exact_tree(root, names, directories=DIRS, trusted=False):
    root=Path(root);seen=set()
    with directory(root,trusted): pass
    for parent,dirs,files in os.walk(root,followlinks=False):
        for name in dirs+files:
            path=Path(parent)/name;relative=path.relative_to(root).as_posix();info=path.lstat()
            if relative in directories:
                valid=stat.S_ISDIR(info.st_mode)
            elif relative in names:
                valid=stat.S_ISREG(info.st_mode) and info.st_nlink==1
            else: valid=False
            if not valid or (trusted and (info.st_uid!=0 or info.st_mode&0o022)):
                raise RuntimeError('Foreign or unsafe deployment entry')
            seen.add(relative)
    if seen!=set(names)|set(directories): raise RuntimeError('Deployment entries differ')


def bundle(path, installed=False):
    path=Path(path)
    extra={'installation.json'} if installed else set()
    exact_tree(path,FILES|{'manifest.json'}|extra,trusted=installed)
    if installed:
        if stat.S_IMODE(path.stat().st_mode)!=0o755: raise RuntimeError('Installed payload directory mode differs')
        for name in DIRS:
            if stat.S_IMODE((path/name).stat().st_mode)!=0o755: raise RuntimeError('Installed payload directory mode differs')
        for name in FILES|{'manifest.json'}|extra:
            expected=0o755 if name=='fprintd' else 0o644
            if stat.S_IMODE((path/name).stat().st_mode)!=expected: raise RuntimeError('Installed payload file mode differs')
    manifest=json.loads(read(path/'manifest.json',32768))
    if set(manifest)!={'format','files','roots','host_pins'} or manifest['format']!=1 or manifest['host_pins']!=HOST_PINS:
        raise RuntimeError('Deployment manifest differs')
    if set(manifest['files'])!=FILES or set(manifest['roots'])!=set(NIX_ROOTS):
        raise RuntimeError('Deployment manifest inputs differ')
    for root,hash_value in manifest['roots'].items():
        if not re.fullmatch(r'sha256:[0-9a-z]{52}',hash_value): raise RuntimeError('Invalid Nix content pin')
    data={name:read(path/name) for name in FILES}
    for name,value in data.items():
        if manifest['files'][name]!=digest(value): raise RuntimeError('Deployment artifact changed')
    for name,value in PAYLOAD_PINS.items():
        if digest(data[name])!=value: raise RuntimeError('Runtime artifact differs from reviewed pin')
    if data['fprintd.conf']!=CONFIG or data['fprintd-dropin.conf']!=unit() or digest(data['manage.py'])!=digest(read(Path(__file__).resolve())):
        raise RuntimeError('Deployment controller/configuration differs')
    return manifest,data


def nix_hash(root):
    result=subprocess.run(['/usr/bin/nix-store','--query','--hash',root],capture_output=True,
                          text=True,check=True,timeout=15,env={'PATH':'/usr/bin','DEBUGINFOD_URLS':''})
    value=result.stdout.strip()
    if not re.fullmatch(r'sha256:[0-9a-z]{52}',value): raise RuntimeError('Unexpected Nix hash result')
    return value


def dependencies(manifest):
    for root,value in manifest['roots'].items():
        if nix_hash(root)!=value: raise RuntimeError('Cached Nix input missing or changed; no automatic acquisition')


class Systemd:
    def command(self,*args):
        return subprocess.run(['/usr/bin/systemctl',*args],check=True,capture_output=True,
                              text=True,timeout=20,env={'PATH':'/usr/bin','DEBUGINFOD_URLS':''}).stdout.strip()
    def check(self,removing=False):
        for name in ('ActiveState','SubState','FragmentPath','DropInPaths'):
            value=self.command('show','fprintd.service','--property='+name,'--value')
            wanted={'ActiveState':'inactive','SubState':'dead','FragmentPath':'/usr/lib/systemd/system/fprintd.service',
                    'DropInPaths':str(DROPIN) if removing else ''}[name]
            if value!=wanted: raise RuntimeError('Stop fprintd first; foreign service state/overrides are refused')
    def reload(self): self.command('daemon-reload')


def private_sessions():
    # Best-effort host-process check, no arguments or identifiers are reported.
    # It cannot exclude an unrelated client or a newly launched private trial.
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal(): continue
        try: command=(entry/'cmdline').read_bytes()
        except (FileNotFoundError,PermissionError,ProcessLookupError): continue
        if any(token in command for token in (b'fprintd-session-',b'/experiment/child.py',b'/experiment/enroll-verify')):
            raise RuntimeError('An experimental session is active; finish it first')


def write(path,data,mode=0o644):
    path=Path(path)
    with directory(path.parent,trusted=True) as parent:
        fd=os.open(path.name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode,dir_fd=parent)
        try:
            os.fchmod(fd,mode)
            with os.fdopen(fd,'wb',closefd=False) as stream: stream.write(data);stream.flush();os.fsync(fd)
        except BaseException:
            ours=os.fstat(fd)
            current=os.stat(path.name,dir_fd=parent,follow_symlinks=False)
            if (ours.st_dev,ours.st_ino)==(current.st_dev,current.st_ino): os.unlink(path.name,dir_fd=parent)
            raise
        finally: os.close(fd)


def create_directory(path,mode=0o755):
    path=Path(path)
    with directory(path.parent,trusted=True) as parent:
        os.mkdir(path.name,mode,dir_fd=parent)
        fd=os.open(path.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
        try: os.fchmod(fd,mode)
        finally: os.close(fd)


def roots_check(root,manifest):
    with directory(root,trusted=True) as fd:
        if set(os.listdir(fd))!={Path(p).name for p in manifest['roots']}: raise RuntimeError('GC-root entries differ')
        for target in manifest['roots']:
            name=Path(target).name;info=os.stat(name,dir_fd=fd,follow_symlinks=False)
            if not stat.S_ISLNK(info.st_mode) or info.st_uid!=0 or os.readlink(name,dir_fd=fd)!=target:
                raise RuntimeError('Foreign GC root; refusing removal')


def state_check(root):
    root=Path(root)
    with directory(root,trusted=True) as fd:
        if stat.S_IMODE(os.fstat(fd).st_mode)!=0o700 or set(os.listdir(fd))!={'.owner','fprint'}:
            raise RuntimeError('Private host state differs')
    if read(root/'.owner',1024)!=MARKER: raise RuntimeError('Foreign private state marker')
    marker=(root/'.owner').lstat()
    if marker.st_uid!=0 or stat.S_IMODE(marker.st_mode)!=0o600:
        raise RuntimeError('Private state marker metadata differs')
    entries=[]
    with directory(root/'fprint',trusted=True) as fd:
        if stat.S_IMODE(os.fstat(fd).st_mode)!=0o700: raise RuntimeError('Private print directory mode differs')
    for parent,dirs,files in os.walk(root/'fprint',followlinks=False):
        for name in dirs+files:
            path=Path(parent)/name;info=path.lstat();relative=path.relative_to(root)
            if len(relative.parts)>8 or len(entries)>=1024 or info.st_uid!=0 or info.st_nlink>1 and stat.S_ISREG(info.st_mode):
                raise RuntimeError('Private host state exceeds boundary')
            mode=stat.S_IMODE(info.st_mode)
            if not ((stat.S_ISDIR(info.st_mode) and mode==0o700) or (stat.S_ISREG(info.st_mode) and mode==0o600)):
                raise RuntimeError('Unsafe private host state entry')
            entries.append(path)
    return entries


@contextlib.contextmanager
def masked(systemd):
    with directory(MASK.parent,trusted=True) as parent:
        if os.path.lexists(MASK): raise RuntimeError('Pre-existing runtime unit/mask; refusing changes')
        os.symlink('/dev/null',MASK.name,dir_fd=parent)
        identity=os.stat(MASK.name,dir_fd=parent,follow_symlinks=False)
        try:
            systemd.reload()
            # /etc units outrank /run; a stale initial check does not prove that
            # our runtime mask became the effective unit after this reload.
            if (systemd.command('show','fprintd.service','--property=LoadState','--value')!='masked' or
                    systemd.command('show','fprintd.service','--property=FragmentPath','--value')!=str(MASK)):
                raise RuntimeError('Own runtime mask is not effective; foreign unit/override refused')
            if systemd.command('show','fprintd.service','--property=ActiveState','--value')!='inactive':
                raise RuntimeError('Service activated during transaction; no process is stopped automatically')
            yield
        finally:
            info=os.stat(MASK.name,dir_fd=parent,follow_symlinks=False)
            if (info.st_dev,info.st_ino)!=(identity.st_dev,identity.st_ino) or not stat.S_ISLNK(info.st_mode) or os.readlink(MASK)!='/dev/null':
                raise RuntimeError('Runtime mask changed; manual review required')
            os.unlink(MASK.name,dir_fd=parent);systemd.reload()


def install(source,systemd=None):
    if os.geteuid()!=0: raise RuntimeError('Installation requires explicit one-shot sudo')
    manifest,data=bundle(source);dependencies(manifest)
    for path,expected in HOST_PINS.items():
        if digest(read(Path(path)))!=expected: raise RuntimeError('Installed host integration inputs changed; review a new bundle')
    systemd=systemd or Systemd();systemd.check();private_sessions()
    for path in (PREFIX,DROPIN,GCROOTS):
        if os.path.lexists(path): raise RuntimeError('Deployment destination already exists; no overwrite')
    if os.path.lexists(DROPIN.parent):
        with directory(DROPIN.parent,trusted=True) as fd:
            if os.listdir(fd): raise RuntimeError('Foreign drop-in directory entries; reload state may be stale')
    if os.path.lexists(STATE): state_check(STATE)
    for path in (PREFIX.parent,DROPIN.parent.parent,GCROOTS.parent,STATE.parent,MASK.parent):
        with directory(path,trusted=True): pass
    with directory(PREFIX.parent,trusted=True) as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        created=[];drop_directory=False;state_created=False
        with masked(systemd):
            try:
                create_directory(PREFIX);created.append(PREFIX)
                for name in DIRS: create_directory(PREFIX/name)
                for name,value in data.items(): write(PREFIX/name,value,0o755 if name=='fprintd' else 0o644)
                write(PREFIX/'manifest.json',json.dumps(manifest,sort_keys=True,indent=2).encode()+b'\n')
                if not DROPIN.parent.exists(): create_directory(DROPIN.parent);drop_directory=True
                create_directory(GCROOTS);created.append(GCROOTS)
                for target in manifest['roots']: (GCROOTS/Path(target).name).symlink_to(target)
                if not STATE.exists():
                    create_directory(STATE,0o700);state_created=True
                    create_directory(STATE/'fprint',0o700);write(STATE/'.owner',MARKER,0o600)
                record=json.dumps({'format':1,'created_dropin_directory':drop_directory},sort_keys=True).encode()+b'\n'
                write(PREFIX/'installation.json',record)
                write(DROPIN,data['fprintd-dropin.conf']);created.append(DROPIN)
                bundle(PREFIX,installed=True);roots_check(GCROOTS,manifest);state_check(STATE)
            except BaseException:
                # Only paths created by this invocation, with no active service.
                if DROPIN in created: DROPIN.unlink()
                if state_created:
                    (STATE/'.owner').unlink(missing_ok=True)
                    if (STATE/'fprint').exists(): (STATE/'fprint').rmdir()
                    STATE.rmdir()
                if GCROOTS in created:
                    for target in manifest['roots']: (GCROOTS/Path(target).name).unlink(missing_ok=True)
                    GCROOTS.rmdir()
                if drop_directory: DROPIN.parent.rmdir()
                if PREFIX in created:
                    for name in FILES|{'manifest.json','installation.json'}: (PREFIX/name).unlink(missing_ok=True)
                    for name in DIRS:
                        if (PREFIX/name).exists(): (PREFIX/name).rmdir()
                    PREFIX.rmdir()
                raise
    print('Installed contained payload and service override; host D-Bus activation is now enabled.')
    print('No CLI biometric trial was run. Next review owner-run fprintd-list before enrollment.')


def remove(purge=False,systemd=None):
    if os.geteuid()!=0: raise RuntimeError('Removal requires explicit one-shot sudo')
    manifest,_data=bundle(PREFIX,installed=True);roots_check(GCROOTS,manifest)
    if digest(read(DROPIN))!=digest(unit()): raise RuntimeError('Service drop-in changed; refusing removal')
    record=json.loads(read(PREFIX/'installation.json',1024))
    if set(record)!={'format','created_dropin_directory'} or record['format']!=1 or type(record['created_dropin_directory']) is not bool:
        raise RuntimeError('Installation record differs')
    state_entries=state_check(STATE)
    with directory(DROPIN.parent,trusted=True) as fd:
        if set(os.listdir(fd))!={DROPIN.name}:
            raise RuntimeError('Foreign drop-in sibling; refusing removal')
    systemd=systemd or Systemd();systemd.check(removing=True);private_sessions()
    with directory(PREFIX.parent,trusted=True) as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with masked(systemd):
            DROPIN.unlink()
            if record['created_dropin_directory']: DROPIN.parent.rmdir()
            for root in manifest['roots']: (GCROOTS/Path(root).name).unlink()
            GCROOTS.rmdir()
            for name in FILES|{'manifest.json','installation.json'}: (PREFIX/name).unlink()
            for name in DIRS: (PREFIX/name).rmdir()
            PREFIX.rmdir()
            if purge:
                for path in sorted(state_entries,key=lambda p:len(p.parts),reverse=True):
                    if path.is_dir(): path.rmdir()
                    else: path.unlink()
                (STATE/'fprint').rmdir();(STATE/'.owner').unlink();STATE.rmdir()
    print('Removed only this deployment; the currently installed stock fprintd unit can activate again.')
    print('Own private host prints deleted.' if purge else 'Private host prints preserved under /var/lib/thinkpad-fingerprint/.')
    print('No global Nix GC, experimental template deletion or sensor-key restoration.')


def plan():
    print('Preparation only in default mode: no host state is inspected or changed.')
    print('Install owns /opt/thinkpad-fingerprint, one fprintd drop-in, 13 Nix GC-root links, and separate private host state.')
    print('Explicit install/remove require sudo, a terminal, exact typed confirmation and inactive fprintd.')
    print('A temporary runtime mask prevents host D-Bus activation while files change; it is removed on ordinary exit.')
    print('After installation, standard CLI/other host clients can activate the modified fprintd through the real host bus/Polkit.')
    print('Real host USB inventory replaces the private synthetic view; only goodixtls55x4 is selected.')
    print('No packages, firmware/key writes, PAM/login/sudo/lock changes or experimental-template import.')
    print('Native diagnostics/core dumps suppressed. Standard CLI no-match has no experimental observer/close gates.')
    print('Remove preserves own host prints; --purge-state explicitly deletes only those prints too.')
    print('Neither removal nor Nix GC restores the persistent sensor key. Power-loss recovery requires review of partial paths/mask.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    actions=parser.add_mutually_exclusive_group()
    actions.add_argument('--install',type=Path,metavar='BUNDLE');actions.add_argument('--remove',action='store_true')
    parser.add_argument('--purge-state',action='store_true')
    args=parser.parse_args()
    if args.purge_state and not args.remove: parser.error('--purge-state requires --remove')
    try:
        if not args.install and not args.remove: plan();return 0
        if not sys.stdin.isatty() or not sys.stdout.isatty(): raise RuntimeError('Mutation requires an interactive terminal')
        plan()
        expected='INSTALL THINKPAD FINGERPRINT' if args.install else 'REMOVE THINKPAD FINGERPRINT'+(' AND HOST PRINTS' if args.purge_state else '')
        if input('Type '+expected+' to proceed, or anything else to stop: ')!=expected:
            print('Stopped before host service/filesystem operations.');return 0
        if args.install: install(args.install)
        else: remove(args.purge_state)
        return 0
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as error:
        print('Host deployment stopped:',error,file=sys.stderr);return 1


if __name__=='__main__':sys.exit(main())
