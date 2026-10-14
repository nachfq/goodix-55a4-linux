#!/usr/bin/env python3
"""Build only an observation shim and synthetic fixtures with existing Nix inputs."""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'work/fprintd-observer-build'
PINS = {'scripts/helpers/fprintd-observer.c': '41f15358cc1d5019e7908d7bdf2e6d5c94706c09254d214809b4721bf4b21679', 'scripts/helpers/fprintd-observer.map': '1c04fd92b95243fa62bada2764b28f9478acf401cc89359edd427de0c30fd9d7', 'tests/fprintd-observer-fixture.c': '6888a9dcba7de14e416e4dbb4180c87c4c58afaa20a1126ac8472724be96b1ae', 'tests/fprintd-observer-caller.c': 'f413aedcc05ad23b1299c8ea358e9f2545b1802f8a5f4718b58ec998966882f6'}  # Reviewed source bytes, filled before building.


def check_inputs():
    spec = importlib.util.spec_from_file_location('verification_build', ROOT / 'scripts/15-build-verification.py')
    previous = importlib.util.module_from_spec(spec); spec.loader.exec_module(previous)
    previous.check_inputs()
    for name, digest in PINS.items():
        path = ROOT / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError('Observer source differs from its reviewed pin: ' + name)
    if not PINS:
        raise RuntimeError('Observer source pins are incomplete')


def execute(command):
    subprocess.run(list(map(str, command)), check=True, timeout=60)


def build():
    if os.geteuid() == 0 or not Path(sys.executable).resolve().is_relative_to('/nix/store'):
        raise RuntimeError('Use the existing Nix environment as regular user, without sudo')
    check_inputs()
    if os.path.lexists(OUTPUT):
        raise RuntimeError('Fresh ignored output required; no automatic removal/reuse')
    subprocess.run(['git', 'check-ignore', '--no-index', '-q', str(OUTPUT / 'artifact')], check=True, cwd=ROOT)
    OUTPUT.mkdir(mode=0o700)
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'gio-2.0', 'gusb'], text=True, timeout=10))
    common = ['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
              '-I' + str(ROOT / 'work/libfprint-verification-fixed/libfprint'),
              '-I' + str(ROOT / 'work/libfprint-verification-fixed-build/libfprint')]
    version = '-Wl,--version-script=' + str(ROOT / 'scripts/helpers/fprintd-observer.map')
    execute([*common, '-shared', '-fPIC', ROOT / 'scripts/helpers/fprintd-observer.c',
             version, '-ldl', *flags, '-o', OUTPUT / 'libfprint-observer.so'])
    execute([*common, '-shared', '-fPIC', ROOT / 'tests/fprintd-observer-fixture.c',
             version, *flags, '-o', OUTPUT / 'libobserver-fixture.so'])
    execute([*common, ROOT / 'tests/fprintd-observer-caller.c', '-L' + str(OUTPUT),
             '-lobserver-fixture', '-Wl,-rpath,' + str(OUTPUT), *flags, '-o', OUTPUT / 'observer-caller'])
    check_inputs()
    for name in ('libfprint-observer.so', 'libobserver-fixture.so', 'observer-caller'):
        print(name, 'SHA-256:', hashlib.sha256((OUTPUT / name).read_bytes()).hexdigest())
    print('Compiled only; no native load, bus, device or installation.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--run', action='store_true'); actions.add_argument('--check-inputs', action='store_true')
    args = parser.parse_args()
    try:
        if args.run: build()
        elif args.check_inputs: check_inputs(); print('Observer source pins match; no load or build.')
        else: print(__doc__ + ' --run compiles fresh ignored outputs, never executes them.')
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print('Observer build stopped:', error, file=sys.stderr); return 1


if __name__ == '__main__':
    sys.exit(main())
