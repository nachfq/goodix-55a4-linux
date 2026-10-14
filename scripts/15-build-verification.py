#!/usr/bin/env python3
"""Build the reviewed private enrollment/verification variant and helper, without device access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work/libfprint-verification-fixed"
BUILD = ROOT / "work/libfprint-verification-fixed-build"
HELPER_BUILD = ROOT / "work/enroll-verify-build"
COMMIT = "d1ca62a801aa565e67d1a2a47aaa7a33232b7990"
SOURCE_HASH = "4d6bb24524a87641fe770474410d56a439713aaf0436c5bd17b2dd5e804535a9"
PATCHES = (
    ("work/55a4-driver.patch", "73720a4418ed7ceb640011f51d4f2bac206118bc480ab6f1784f6618b479ef15"),
    ("patches/0001-goodixtls-safe-errors.patch", "d3187cbc8c86a3a6881411428e781be9b4a90de68f7a3ae822e1e183bb5594b7"),
    ("patches/0002-goodix-tls-flow.patch", "23a4dd473eb2b377938b5201a115943da67744473c1dd3c276ce5b36165344aa"),
    ("patches/0003-goodix-capture-safety.patch", "a16bc19971e539809a231744efed1af5cf4b87e51745fbd4201bbdef8de436de"),
    ("patches/0004-goodix-verification-safety.patch", "39477b84083169e20aec2be2c80f7d1c9c037e5a832d42cd1cb150ff3ca3cce7"),
)
LIBRARY = BUILD / "libfprint/libfprint-2.so.2.0.0"
HELPER = ROOT / "scripts/helpers/enroll-verify.c"
HELPER_HASH = "846ca704990bc5e68e2836d7e3bcc2312a7852e66827a066ad0240dc88a44788"
CAPTURE_HELPER_HASH = "568ae51c97ab53987039264bbed4e871878501a9760a50e83ddba051e4724741"
DIFF = ["-c", "diff.algorithm=myers", "-c", "diff.indentHeuristic=true",
        "-c", "diff.suppressBlankEmpty=false", "diff", "--no-ext-diff",
        "--no-textconv", "--no-renames", "--no-color", "--src-prefix=a/",
        "--dst-prefix=b/", "--unified=3", "--inter-hunk-context=0", "--abbrev=7", "HEAD"]


def git(source, *args):
    return subprocess.check_output(["git", "--no-optional-locks", "-C", str(source),
                                    "-c", "core.fsmonitor=false", "-c", "core.fileMode=true",
                                    *args], timeout=15)


def check_inputs():
    if Path(git(SOURCE, "rev-parse", "--show-toplevel").decode().strip()) != SOURCE:
        raise RuntimeError("Unexpected source checkout location")
    if git(SOURCE, "rev-parse", "HEAD").decode().strip() != COMMIT:
        raise RuntimeError("Unexpected base commit")
    entries = git(SOURCE, "ls-files", "-v").decode().splitlines()
    if any(entry[0].islower() or entry[0] == "S" for entry in entries):
        raise RuntimeError("Hidden source index flags")
    if git(SOURCE, "diff", "--cached", "--name-only") or git(SOURCE, "ls-files", "--others"):
        raise RuntimeError("Unexpected staged or untracked/ignored source inputs")
    for name, digest in PATCHES:
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError("Patch differs from reviewed pin: " + name)
    if hashlib.sha256(git(SOURCE, *DIFF)).hexdigest() != SOURCE_HASH:
        raise RuntimeError("Effective source differs from the reviewed pin")
    check_shared_helper()
    if hashlib.sha256(HELPER.read_bytes()).hexdigest() != HELPER_HASH:
        raise RuntimeError("Verification helper source differs from the reviewed pin")


def check_shared_helper():
    if hashlib.sha256((ROOT / "scripts/helpers/capture-one.c").read_bytes()).hexdigest() != CAPTURE_HELPER_HASH:
        raise RuntimeError("Shared capture helper differs from its tested pin")


def check_output():
    if not (ROOT / "work").is_dir() or (ROOT / "work").is_symlink():
        raise RuntimeError("work/ must be an existing real directory")
    for directory in (BUILD, HELPER_BUILD):
        if os.path.lexists(directory):
            raise RuntimeError("Output already exists; no deletion or reuse: " + str(directory))
        git(ROOT, "check-ignore", "--no-index", "-q", str(directory / "output"))


def selected_target():
    targets = json.loads((BUILD / "meson-info/intro-targets.json").read_text())
    rows = [row for row in targets if row.get("name") == "fprint-2"]
    if len(rows) != 1 or rows[0].get("type") != "shared library" or rows[0].get("filename") != [str(LIBRARY)]:
        raise RuntimeError("Unexpected library target/output; no default build fallback")
    return str(LIBRARY.relative_to(BUILD))


def execute(command):
    print("$ " + shlex.join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), check=True, timeout=180)


def build():
    if os.geteuid() == 0 or not Path(sys.executable).resolve().is_relative_to("/nix/store"):
        raise RuntimeError("Use the already available Nix environment as your regular user")
    check_inputs()
    check_output()
    BUILD.mkdir()
    HELPER_BUILD.mkdir(mode=0o700)
    execute(["meson", "setup", BUILD, SOURCE, "--backend=ninja", "--wrap-mode=nofallback",
             "-Ddrivers=goodixtls55x4", "-Dintrospection=false", "-Ddoc=false",
             "-Dgtk-examples=false", "-Dinstalled-tests=false",
             "-Dudev_rules=disabled", "-Dudev_hwdb=disabled"])
    target = selected_target()
    check_inputs()
    execute(["ninja", "-C", BUILD, target])
    flags = shlex.split(subprocess.check_output(
        ["pkg-config", "--cflags", "--libs", "gio-unix-2.0", "gusb", "libusb-1.0"], text=True, timeout=15))
    execute(["cc", "-std=c11", "-Wall", "-Wextra", "-O2", "-I" + str(SOURCE / "libfprint"),
             "-I" + str(BUILD / "libfprint"),
             HELPER, "-L" + str(BUILD / "libfprint"), "-lfprint-2", *flags,
             "-Wl,-rpath," + str(BUILD / "libfprint"), "-o", HELPER_BUILD / "enroll-verify"])
    for artifact in (LIBRARY, HELPER_BUILD / "enroll-verify"):
        execute(["readelf", "-h", "-d", artifact])
        print(artifact.relative_to(ROOT), "SHA-256:", hashlib.sha256(artifact.read_bytes()).hexdigest())
    check_inputs()
    print("Built and statically inspected only. No executable/library load or USB access.")
    print("Review these artifact hashes before setting the enrollment/verification launcher's pins.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--plan", action="store_true")
    modes.add_argument("--check-inputs", action="store_true")
    modes.add_argument("--run", action="store_true")
    args = parser.parse_args()
    try:
        if args.run:
            build()
        elif args.check_inputs:
            check_inputs()
            check_output()
            print("Source/patch/helper pins and fresh ignored outputs checked; no build/load/USB.")
        else:
            print("Build only the verification-safety variant and standalone helper with existing Nix inputs.")
            print("--check-inputs verifies pins and fresh output paths; --run executes compiler tooling.")
            print("Sources:", SOURCE)
            print("Fresh outputs:", BUILD, HELPER_BUILD)
            print("No acquisition, install, execution of the built helper, sensor or service changes.")
            print("Failures preserve partial output; no automatic repair/removal or unpinned fallback.")
        return 0
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print("Verification build stopped:", str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
