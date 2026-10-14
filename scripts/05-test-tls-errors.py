#!/usr/bin/env python3
"""Compile and test only the actual TLS error constructor, offline."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "work/libfprint-patched"
FIXED = ROOT / "work/libfprint-tls-fixed"
RELATIVE = "libfprint/drivers/goodixtls/goodixtls.c"
PATCH_HASH = "d3187cbc8c86a3a6881411428e781be9b4a90de68f7a3ae822e1e183bb5594b7"
CASES = ("known-openssl", "empty-queue", "unknown-reason", "empty-message",
         "short-message", "long-message", "repeated")


def constructor(source):
    matches = re.findall(r"static GError \*\nerr_from_ssl \(void\)\n\{.*?\n\}", source, re.S)
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one TLS error constructor")
    return matches[0]


def run():
    if os.geteuid() == 0:
        raise RuntimeError("Run offline tests as your regular user")
    patch = (ROOT / "patches/0001-goodixtls-safe-errors.patch").read_bytes()
    if hashlib.sha256(patch).hexdigest() != PATCH_HASH:
        raise RuntimeError("Fix patch does not match the reviewed bytes")
    original = (BASE / RELATIVE).read_text()
    fixed = (FIXED / RELATIVE).read_text()
    # Validate that the tested fixed file is exactly this patch applied to baseline.
    with tempfile.TemporaryDirectory(prefix="tls-input-", dir=ROOT / "work") as tmp:
        path = Path(tmp) / RELATIVE
        path.parent.mkdir(parents=True)
        path.write_text(original)
        subprocess.run(["git", "apply", str(ROOT / "patches/0001-goodixtls-safe-errors.patch")],
                       cwd=tmp, check=True, timeout=10)
        if path.read_text() != fixed:
            raise RuntimeError("Fixed TLS file differs from baseline plus the reviewed fix")
    header = (FIXED / "libfprint/fp-device.h").read_text()
    enums = re.findall(r"typedef enum \{[^{}]*\} FpDeviceError;", header)
    if len(enums) != 1:
        raise RuntimeError("Expected the real FpDeviceError enumeration")
    harness = (ROOT / "tests/tls-errors-harness.c").read_text()
    harness = harness.replace("/* INSERT DEVICE ERROR ENUM */", enums[0])
    flags = shlex.split(subprocess.check_output(
        ["pkg-config", "--cflags", "--libs", "glib-2.0", "openssl"], text=True))
    env = dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1",
               UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
    # Disable competing fortify checks only for isolated test compilation so
    # ASan observes the original write. Production builds retain their hardening.
    compile_env = dict(os.environ)
    for key, value in list(compile_env.items()):
        if key.startswith("NIX_HARDENING_ENABLE"):
            compile_env[key] = " ".join(flag for flag in value.split()
                                        if flag not in ("fortify", "fortify3"))
    with tempfile.TemporaryDirectory(prefix="tls-regression-", dir=ROOT / "work") as tmp:
        for variant, text in (("baseline", original), ("fixed", fixed)):
            unit = Path(tmp) / (variant + ".c")
            binary = Path(tmp) / variant
            # Generated source retains attribution; it stays local and is deleted.
            notice = text.split("#include", 1)[0]
            unit.write_text(notice + harness.replace("/* INSERT ERROR CONSTRUCTOR */", constructor(text)))
            subprocess.run(["cc", "-std=c11", "-g", "-O1", "-Wall", "-Wextra",
                            "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                            "-U_FORTIFY_SOURCE", "-D_FORTIFY_SOURCE=0",
                            str(unit), "-o", str(binary), *flags], env=compile_env,
                           check=True, timeout=60)
            if variant == "baseline":
                result = subprocess.run([str(binary), "short-message"], env=env,
                                        capture_output=True, text=True, timeout=10)
                if result.returncode == 0 or "heap-buffer-overflow" not in result.stderr:
                    raise RuntimeError("Baseline did not reproduce the expected ASan heap overflow: "
                                       + str(result.returncode) + "\n" + result.stderr[:2000])
                print("Baseline: reproduced heap-buffer-overflow in the isolated constructor.", flush=True)
            else:
                for case in CASES:
                    subprocess.run([str(binary), case], env=env, check=True, timeout=10)
                    print("PASS: " + case, flush=True)
    print("Seven fixed-constructor cases passed under ASan/UBSan. No driver or USB initialization.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="compile and execute isolated regression tests")
    args = parser.parse_args()
    if args.run:
        run()
    else:
        print("Plan only: no compilation or execution. --run uses the existing toolchain and sources.")
        print("Validate the separate fix, extract the actual baseline/fixed error constructors,")
        print("reproduce the baseline ASan overflow, then check seven fixed cases under ASan/UBSan.")
        print("Temporary generated units and executables stay under ignored work/ and are removed.")
        print("Links GLib/OpenSSL only; no complete driver, USB access, downloads or system changes.")
