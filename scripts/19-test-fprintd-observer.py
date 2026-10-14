#!/usr/bin/env python3
"""Offline observation-shim tests: six synthetic versioned API completion cases."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PINS = {'libobserver-fixture.so': ('work/fprintd-observer-build/libobserver-fixture.so', 'ed0c40d773713a7bf19fa8ea95181fb53c2848030cd41673c64f98b0eca5b73d'), 'observer-caller': ('work/fprintd-observer-build/observer-caller', 'fd9edbd1a9b2dc25829f114381437ddd461429d04539b035e23ad79437ccd2fb'), 'observer-test-child.py': ('scripts/helpers/fprintd-observer-test-child.py', '48fa8f2ce05684df9bb5a69379122e51669b6febfe63b92b4af4d1d3e1d4d6ba')}


def run():
    if os.geteuid() == 0:
        raise RuntimeError('Run the offline sandbox as regular user, without sudo')
    spec = importlib.util.spec_from_file_location('session', ROOT / 'scripts/17-fprintd-session.py')
    session = importlib.util.module_from_spec(spec); spec.loader.exec_module(session)
    assets = session.inputs()
    for name, (path, digest) in PINS.items():
        assets[name] = session.previous().checked_bytes(ROOT / path, digest)
    assets['session-body.py'] = assets['child.py']
    assets['child.py'] = assets.pop('observer-test-child.py')
    assets['dbus.conf'] = session.DBUS_CONFIG.encode()
    config = session.configuration(assets, 'smoke', None, 'synthetic', None, True)
    with tempfile.TemporaryDirectory(prefix='observer-test-', dir=ROOT / 'work') as tmp:
        folder = Path(tmp)
        for name, data in assets.items():
            path = folder / name; path.write_bytes(data); path.chmod(0o555 if name == 'observer-caller' else 0o444)
        (folder / 'passwd').write_text('root:x:0:0::/:/dev/null\npolkitd:x:0:0::/:/dev/null\n')
        (folder / 'group').write_text('root:x:0:\npolkitd:x:0:\n')
        (folder / 'nsswitch.conf').write_text('passwd: files\ngroup: files\n')
        (folder / 'fprintd.conf').write_text('[storage]\ntype=file\n')
        (folder / 'session.json').write_text(json.dumps(config))
        (folder / 'state').mkdir(mode=0o700)
        command = session.sandbox(folder, folder / 'state', None, None, True)
        result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                check=False, timeout=25, env={'DEBUGINFOD_URLS': ''})
    if result.returncode or result.stdout != b'PASS SYNTHETIC_OBSERVER\n' or result.stderr:
        raise RuntimeError('Isolated synthetic observer failed: ' + result.stderr[:1024].decode(errors='replace'))
    print('PASS: six versioned synthetic verify/close cases; no driver, USB or bus started.')


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    try:
        if args.run: run()
        else: print(__doc__ + ' Default prints only; --run needs existing pinned build inputs.')
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print('Observer test stopped:', error, file=sys.stderr); return 1


if __name__ == '__main__':
    sys.exit(main())
