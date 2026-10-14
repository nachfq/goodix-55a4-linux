#!/usr/bin/env python3
"""Smoke-test the complete enrollment/verification executable in a sandbox without host USB."""
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


def run():
    if os.geteuid() == 0 or not Path(sys.executable).resolve().is_relative_to("/nix/store"):
        raise RuntimeError("Use the existing Nix Python as the regular user, without sudo")
    spec = importlib.util.spec_from_file_location("verification", ROOT / "scripts/14-enroll-verify.py")
    verification = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verification)
    library, binary = verification.checked_inputs()
    namespaces = {name: os.readlink(f"/proc/self/ns/{name}") for name in ("mnt", "net", "pid")}
    with tempfile.TemporaryDirectory(prefix="verification-runtime-", dir=ROOT / "work") as tmp:
        folder = Path(tmp)
        files = {
            "libfprint-2.so.2.0.0": library,
            "enroll-verify": binary,
            "child.py": (ROOT / "scripts/helpers/verification-runtime-child.py").read_bytes(),
            "isolation.py": (ROOT / "scripts/helpers/load-library-child.py").read_bytes(),
            "launcher.py": (ROOT / "scripts/14-enroll-verify.py").read_bytes(),
        }
        command = ["/usr/bin/bwrap", "--unshare-all", "--die-with-parent", "--new-session",
                   "--cap-drop", "ALL", "--ro-bind", "/nix/store", "/nix/store", "--dir", "/experiment"]
        for name, data in files.items():
            path = folder / name
            path.write_bytes(data)
            path.chmod(0o500 if name == "enroll-verify" else 0o400)
            command += ["--ro-bind", str(path), "/experiment/" + name]
        command += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--clearenv",
                    "--setenv", "OPENBLAS_NUM_THREADS", "1", "--setenv", "OMP_NUM_THREADS", "1",
                    "--chdir", "/experiment", "--", str(Path(sys.executable).resolve()),
                    "-I", "-B", "-S", "/experiment/child.py", json.dumps(namespaces),
                    hashlib.sha256(library).hexdigest(), hashlib.sha256(binary).hexdigest()]
        result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, check=False, timeout=35)
    if result.returncode != 0:
        raise RuntimeError("Isolated synthetic runtime failed: " + result.stderr[:3000])
    if result.stdout.strip() != "PASS: isolated sealed runtime, synthetic template round-trip, prompts and deadline" or result.stderr:
        raise RuntimeError("Unexpected sandbox result; no host fallback")
    print(result.stdout.strip())
    print("No USB nodes, host sysfs, service sockets, home or network; no sensor opened.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    try:
        if args.run:
            run()
        else:
            print("Offline smoke only: load the complete pinned enrollment/verification executable/library")
            print("inside bubblewrap, test synthetic template serialization, finger prompts and cancellation.")
            print("Private namespaces and mounts exclude host USB/sysfs/services/network/home.")
            print("Default prints only; --run executes the bounded sandbox, never hardware.")
        return 0
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print("Runtime smoke stopped:", str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
