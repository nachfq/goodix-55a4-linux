#!/usr/bin/env python3
"""Load the reviewed local library in a restricted, offline bubblewrap process."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "work/libfprint-tls-fixed-build/libfprint/libfprint-2.so.2.0.0"
# Pin this locally observed build, not a promise of cross-machine reproducibility.
LIBRARY_HASH = "3fa1a8120f9105a413c002f8718d69b52ae3ba56255223fd685fb78e4416efee"
CHILD = ROOT / "scripts/helpers/load-library-child.py"
BWRAP = Path("/usr/bin/bwrap")
NAMESPACES = ("mnt", "net", "pid")
TYPES = ("FpDevice", "FpPrint", "FpContext")


def plan():
    print("Lesson 6: load the corrected library without opening a reader")
    print("Default mode only explains the plan; no library is loaded.")
    print("--run requires your regular user and the existing Nix Python:")
    print("  1. Verify the exact local artifact hash and freeze a temporary copy under work/.")
    print("  2. Start /usr/bin/bwrap with separate namespaces and an empty environment.")
    print("     Mount only the read-only Nix store, library and helper; private /proc, /dev, /tmp.")
    print("     No host USB nodes, D-Bus sockets, home, sysfs or network interfaces.")
    print("  3. Check isolation before loading with RTLD_NOW (resolve dependencies immediately).")
    print("  4. Call only fp_device_get_type, fp_print_get_type, fp_context_get_type")
    print("     and g_type_name; expect FpDevice, FpPrint and FpContext.")
    print("No object construction, enumeration, capture, key writes, installation or downloads.")
    print("Native library constructors run inside the sandbox; this is not a complete audit.")
    print("The temporary copy is removed. No logs are saved by this script.")


def checked_inputs():
    if os.geteuid() == 0:
        raise RuntimeError("Use your regular user, without sudo")
    python = Path(sys.executable).resolve()
    if not python.is_relative_to("/nix/store"):
        raise RuntimeError("Use Python from the already agreed Nix environment")
    if not BWRAP.is_file() or not os.access(BWRAP, os.X_OK):
        raise RuntimeError("/usr/bin/bwrap is unavailable; there is no host fallback")
    data = LIBRARY.read_bytes()
    if hashlib.sha256(data).hexdigest() != LIBRARY_HASH:
        raise RuntimeError("Artifact hash differs; review the build before updating its pin")
    helper = CHILD.read_bytes()
    namespaces = {name: os.readlink(f"/proc/self/ns/{name}") for name in NAMESPACES}
    return python, data, helper, namespaces


def sandbox_command(python, library, helper, namespaces):
    return [str(BWRAP), "--unshare-all", "--die-with-parent", "--new-session",
            "--cap-drop", "ALL", "--ro-bind", "/nix/store", "/nix/store",
            "--dir", "/experiment",
            "--ro-bind", str(library), "/experiment/libfprint-2.so.2.0.0",
            "--ro-bind", str(helper), "/experiment/child.py",
            "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
            "--clearenv", "--setenv", "OPENBLAS_NUM_THREADS", "1",
            "--setenv", "OMP_NUM_THREADS", "1", "--chdir", "/experiment", "--",
            str(python), "-I", "-B", "-S", "/experiment/child.py",
            json.dumps(namespaces), LIBRARY_HASH]


def run():
    python, data, helper, namespaces = checked_inputs()
    print("Verified the reviewed artifact; starting the restricted child.", flush=True)
    with tempfile.TemporaryDirectory(prefix="library-load-", dir=ROOT / "work") as tmp:
        library_path = Path(tmp) / "library.so"
        helper_path = Path(tmp) / "child.py"
        library_path.write_bytes(data)
        helper_path.write_bytes(helper)
        result = subprocess.run(sandbox_command(python, library_path, helper_path, namespaces),
                                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                close_fds=True, timeout=20)
    if result.returncode != 0:
        raise RuntimeError(f"Sandbox trial failed ({result.returncode}): "
                           + result.stderr[:2000] + result.stdout[:2000])
    report = json.loads(result.stdout)
    if report != {"isolation": "checked", "dependencies": "resolved",
                  "types": list(TYPES)}:
        raise RuntimeError("Unexpected sandbox report; trial is inconclusive")
    if result.stderr:
        print("Sandbox diagnostics: " + result.stderr[:2000], file=sys.stderr)
    print("PASS: isolation checks; immediate dependency resolution; " + ", ".join(TYPES))
    print("Child exited; temporary files removed. No reader was opened or enumerated.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--plan", action="store_true")
    modes.add_argument("--check-dependencies", action="store_true")
    modes.add_argument("--run", action="store_true")
    args = parser.parse_args()
    try:
        if args.run:
            run()
        elif args.check_dependencies:
            checked_inputs()
            print("Nix Python, bubblewrap, helper and artifact pin found. No sandbox or load run.")
        else:
            plan()
        return 0
    except subprocess.TimeoutExpired:
        print("Sandbox timed out; inconclusive trial, no host fallback.", file=sys.stderr)
        return 124
    except KeyboardInterrupt:
        print("Trial interrupted.", file=sys.stderr)
        return 130
    except (OSError, RuntimeError, ValueError) as error:
        print("Load trial stopped: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
