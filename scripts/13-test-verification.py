#!/usr/bin/env python3
"""Offline actual SIGFM + print-matcher regressions; synthetic data only."""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import resource
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'work/libfprint-verification-fixed/libfprint'
PINS = {'fpi-print.c': '3043f306dd147aff385b9b224716b9b6ed4c4c12161864779c2c070bc2531699',
 'fp-print.c': 'a0c96dac5bf9d74dd31dc0901b973bb8c567f7fccec06160d93d435de35e8588',
 'fp-image.c': 'c71f25ecaf8b99c3684c2a6ab969927e82fc3cd2450476dabec4b3889503ef1e',
 'fpi-image-device.c': 'df426565b6cd3d63b9b3cf22c16f017549adda18ab4b07568cade9361aa53231',
 'sigfm/sigfm.cpp': 'dfb58839c4a132e4a7d1c8dea9a803f0ff65891c0869ae4bf8ed9192a11f518c',
 'sigfm/binary.hpp': 'c02701af24406d3adcba0039696dc64c1624e74a1796c66d554a2986a86f0f3d',
 'sigfm/img-info.hpp': 'ee8db1e003da6312176b560152071fcbbf75304f0a07c8cffabe2cf1d003adc0',
 'sigfm/sigfm.hpp': 'b216a35ad40c6f579aff95a9b2734c8e528c0ba2ca1372aeaa95e676117e7c56'}
CONTROL_PINS = {'fpi-print.c': 'fa306b0b8e09ff9d8c58b535cccd03eb58d299d03804d5bf15b5e608fc15326b',
 'sigfm/binary.hpp': '8a352ae6979ec6a713ac5abc2cf4d98a479cd64915fccd9983ff30358c993186'}


def check_inputs():
    spec = importlib.util.spec_from_file_location("verification_build", ROOT / "scripts/15-build-verification.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    build.check_inputs()
    previous = ROOT / 'work/libfprint-capture-fixed/libfprint'
    for name, digest in CONTROL_PINS.items():
        if hashlib.sha256((previous / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Changed negative-control source: ' + name)
    for name, digest in PINS.items():
        path = SOURCE / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError('Changed core source: ' + name)


def match_unit(source=None):
    if source is None:
        source = (SOURCE / 'fpi-print.c').read_text()
    start = source.index('FpiMatchResult fpi_print_sigfm_match(')
    end = source.index('\n/**', start)
    # Attribution/license belongs to the production body, kept in generated C.
    license_text = source[:source.index('#include')]
    harness = (ROOT / 'tests/verification-match-harness.c').read_text()
    return license_text + harness.replace('/* INSERT MATCH IMPLEMENTATION */', source[start:end])


def run():
    if os.geteuid() == 0 or not Path(sys.executable).resolve().is_relative_to('/nix/store'):
        raise RuntimeError('Use the existing Nix Python as regular user, without sudo')
    check_inputs()
    flags = shlex.split(subprocess.check_output(
        ['pkg-config', '--cflags', '--libs', 'gio-2.0', 'opencv4'], text=True, timeout=10))
    sanitizers = ['-g', '-O1', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',
               UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1',
               OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    def limits():
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    with tempfile.TemporaryDirectory(prefix='verification-regression-', dir=ROOT / 'work') as directory:
        directory = Path(directory)
        c = directory / 'match.c'
        obj = directory / 'match.o'
        binary = directory / 'verification-core'
        c.write_text(match_unit())
        include = ['-I' + str(SOURCE / 'sigfm')]
        subprocess.run(['cc', '-std=c11', *sanitizers, *include, '-c', str(c), '-o', str(obj),
                        *flags], check=True, timeout=60)
        subprocess.run(['c++', '-std=c++17', *sanitizers, *include,
                        str(ROOT / 'tests/verification-core-harness.cpp'),
                        str(SOURCE / 'sigfm/sigfm.cpp'), str(obj), '-o', str(binary),
                        *flags], check=True, timeout=90)
        subprocess.run([str(binary)], check=True, env=env, timeout=40, preexec_fn=limits)
        # Restore actual prior bodies as bounded regression negative controls.
        previous = ROOT / 'work/libfprint-capture-fixed/libfprint'
        c.write_text(match_unit((previous / 'fpi-print.c').read_text()))
        subprocess.run(['cc', '-std=c11', *sanitizers, *include, '-c', str(c), '-o', str(obj),
                        *flags], check=True, timeout=60)
        subprocess.run(['c++', '-std=c++17', *sanitizers, *include,
                        str(ROOT / 'tests/verification-core-harness.cpp'),
                        str(SOURCE / 'sigfm/sigfm.cpp'), str(obj), '-o', str(binary),
                        *flags], check=True, timeout=90)
        failed = subprocess.run([str(binary), 'empty-probe'], env=env, timeout=10,
                                preexec_fn=limits, capture_output=True)
        if failed.returncode == 0 or not any(tag in failed.stderr for tag in
                                          (b'AddressSanitizer', b'runtime error:')):
            raise RuntimeError('Original empty-probe negative control did not reproduce a sanitizer failure')
        print('PASS negative control: original empty-probe matcher fails under ASan/UBSan')
        # Fixed matcher again, but actual prior binary reader header.
        c.write_text(match_unit())
        subprocess.run(['cc', '-std=c11', *sanitizers, *include, '-c', str(c), '-o', str(obj),
                        *flags], check=True, timeout=60)
        (directory / 'binary.hpp').write_bytes((previous / 'sigfm/binary.hpp').read_bytes())
        (directory / 'sigfm.cpp').write_bytes((SOURCE / 'sigfm/sigfm.cpp').read_bytes())
        # Both C++ translation units must see the same original inline reader
        # to avoid replacing its weak template symbol with the fixed harness copy.
        (directory / 'control.cpp').write_bytes(
            (ROOT / 'tests/verification-core-harness.cpp').read_bytes())
        subprocess.run(['c++', '-std=c++17', *sanitizers, *include,
                        str(directory / 'control.cpp'),
                        str(directory / 'sigfm.cpp'), str(obj), '-o', str(binary),
                        *flags], check=True, timeout=90)
        failed = subprocess.run([str(binary), 'truncated'], env=env, timeout=10,
                                preexec_fn=limits, capture_output=True)
        if failed.returncode == 0 or not any(tag in failed.stderr for tag in
                                          (b'AddressSanitizer', b'runtime error:')):
            raise RuntimeError('Original binary-reader negative control did not reproduce a sanitizer failure')
        print('PASS negative control: original truncated binary reader fails under ASan/UBSan')
    print('Offline core checks complete. No device, real template, enrollment or accuracy claim.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--run', action='store_true')
    group.add_argument('--check-inputs', action='store_true')
    group.add_argument('--plan', action='store_true')
    args = parser.parse_args()
    if args.run:
        run()
    elif args.check_inputs:
        check_inputs()
        print('Core source pins match; nothing compiled or loaded.')
    else:
        print('Compile actual SIGFM + extracted print-match with real OpenCV/GLib and ASan/UBSan.')
        print('Use synthetic features to test scores, empty/invalid inputs and binary round-trip/truncation.')
        print('Default opens no USB and loads no library. --run needs existing cached Nix dependencies.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print('Offline verification checks stopped:', error, file=sys.stderr)
        raise SystemExit(1)
