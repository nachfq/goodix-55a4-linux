#!/usr/bin/env python3
"""One private host-template enrollment or declared-category verification."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import resource
import selectors
import signal
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "work/libfprint-verification-fixed-build/libfprint/libfprint-2.so.2.0.0"
EXECUTABLE = ROOT / "work/enroll-verify-build/enroll-verify"
SOURCE = ROOT / "scripts/helpers/enroll-verify.c"
INCLUDED_SOURCE = ROOT / "scripts/helpers/capture-one.c"
# Exact complete local build. No command-line pin overrides.
LIBRARY_SHA256 = "161c4a9fa432963b30d7303e1f6d8152269254f52850d14a77aae3e53399c2cd"
EXECUTABLE_SHA256 = "a276aba080be21255bdb6774a2865546b1288125b30ad634a8a328f167b985e7"
SOURCE_SHA256 = "846ca704990bc5e68e2836d7e3bcc2312a7852e66827a066ad0240dc88a44788"
INCLUDED_SOURCE_SHA256 = "568ae51c97ab53987039264bbed4e871878501a9760a50e83ddba051e4724741"
MAX_TEMPLATE = 4 * 1024 * 1024
WALL_SECONDS = 650
FAILURES = {"DISCOVERY", "USB_MISSING", "USB_MULTIPLE", "USB_OPEN", "USB_CONFIGURATION",
            "USB_DESCRIPTORS", "USB_LAYOUT", "USB_PRECHECK_CLOSE", "INIT", "DRIVER", "OPEN",
            "ENROLL", "VERIFY", "CLOSE", "OUTPUT", "CANCEL_GRACE", "TIMEOUT", "CANCELLED",
            "RETRY", "RETRY_LIMIT", "PROGRESS", "DECISION", "TEMPLATE"}
STAGES = {
    "STAGE INIT": "Constructing the selected reader.",
    "STAGE OPEN": "Opening its existing interface; no kernel-driver detach.",
    "STAGE ENROLL": "Calibration: keep your finger OFF until the LED lights. Then scan your RIGHT INDEX finger; lift when prompted and touch again only on the next explicit touch prompt.",
    "STAGE VERIFY": "Calibration: keep your finger OFF until the LED lights. Then scan the finger chosen for this declared-category trial.",
    "PROMPT LIFT": "Lift your finger now; wait for completion or the next explicit touch prompt.",
    "PROMPT TOUCH": "Touch the reader again with your RIGHT INDEX finger. The LED may remain on between scans.",
    "STAGE CLOSE": "Closing the reader; keep your finger off.",
    "CLOSED": "The driver reported successful close.",
    "RETRY SCAN": "Enrollment scan was inconclusive; lift and wait for the next explicit touch prompt.",
}


def plan():
    print("Lesson 14: a frozen private host template and one controlled comparison")
    print("Default/--plan/--check-inputs do not load a library or open USB.")
    print("--run --enroll stores one RIGHT INDEX template after 16 accepted scans and successful close.")
    print("--run --verify --expected same|other compares one scan against that same frozen template.")
    print("Expected category is your declaration, not a measurement of finger identity.")
    print("Both modes require exact typed confirmation before USB access.")
    print("The reviewed driver may reset/enable, configure TLS, calibrate, capture frames,")
    print("control the LED, match on the host and sleep. No key/firmware write or installation.")
    print("No fprintd, D-Bus, PAM, authentication settings, raw images or raw logs.")
    print("Template and its frozen-series manifest stay in ignored work/private-verification/,")
    print("directory 0700/files 0600 owned by the caller. Never upload the template.")
    print("Enrollment never overwrites it; verification never updates it or tunes thresholds.")
    print("A declared-other MATCH is a false-accept observation: STOP authentication progress.")
    print("Only final operation success plus successful close permits MATCH/NO_MATCH.")
    print("Errors, retries, cancellation and timeouts are INCONCLUSIVE, never biometric rejection.")
    print("Limits: init10s/open15s, each enrollment scan45s/total600s, verify45s, close10s,")
    print("cancellation grace3s; parent650s. Forced exit cannot prove sensor sleep/LED off.")


def open_directory(path):
    """Traverse an absolute path without following symlinks in any component."""
    path = Path(path)
    if not path.is_absolute():
        raise RuntimeError("Directory must be absolute")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for component in path.parts[1:]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise

def checked_bytes(path, digest):
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise RuntimeError("Verification build pins have not been recorded yet")
    parent = open_directory(path.parent)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
    finally:
        os.close(parent)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 32 * 1024 * 1024:
            raise RuntimeError("Input is not a bounded regular file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(32 * 1024 * 1024 + 1)
    finally:
        os.close(fd)
    if len(data) > 32 * 1024 * 1024:
        raise RuntimeError("Input exceeds the bounded size")
    if hashlib.sha256(data).hexdigest() != digest:
        raise RuntimeError("Reviewed build input differs from its recorded SHA-256")
    return data

def caller():
    uid = os.getuid()
    if os.geteuid() == 0:
        text = os.environ.get("SUDO_UID", "")
        if not text.isdecimal() or int(text) == 0:
            raise RuntimeError("Root execution requires one-shot sudo from the repository owner")
        uid = int(text)
        account = pwd.getpwuid(uid)
        if os.environ.get("SUDO_USER") != account.pw_name:
            raise RuntimeError("Sudo caller identity is inconsistent")
    else:
        account = pwd.getpwuid(uid)
    if uid != ROOT.stat().st_uid:
        raise RuntimeError("Run as the repository owner, optionally through one-shot sudo")
    return uid, account.pw_gid

def sealed(data, executable=False):
    fd = os.memfd_create("capture-reviewed-input", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
        os.fchmod(fd, 0o500 if executable else 0o400)
        fcntl.fcntl(fd, fcntl.F_ADD_SEALS, fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL)
        return fd
    except BaseException:
        os.close(fd)
        raise

def child_environment(library_fd):
    # The sealed ELF's SONAME satisfies the executable's libfprint DT_NEEDED.
    # Dependencies/interpreter retain their reviewed absolute Nix store paths.
    return {"LD_PRELOAD": f"/proc/self/fd/{library_fd}", "LANG": "C", "LC_ALL": "C",
            "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}

def terminate(child):
    if child is not None and child.poll() is None:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            child.wait(timeout=4)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait(timeout=2)

def checked_inputs():
    library = checked_bytes(LIBRARY, LIBRARY_SHA256)
    executable = checked_bytes(EXECUTABLE, EXECUTABLE_SHA256)
    checked_bytes(SOURCE, SOURCE_SHA256)
    checked_bytes(INCLUDED_SOURCE, INCLUDED_SOURCE_SHA256)
    if not library.startswith(b"\x7fELF") or not executable.startswith(b"\x7fELF"):
        raise RuntimeError("Pinned artifacts are not ELF files")
    return library, executable


def private_directory(uid, gid, enroll):
    work = open_directory(ROOT / "work")
    directory = None
    created = False
    try:
        if enroll:
            try:
                os.mkdir("private-verification", 0o700, dir_fd=work)
                created = True
            except FileExistsError:
                pass
        directory = os.open("private-verification", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=work)
        if created:
            os.fchmod(directory, 0o700)
            os.fchown(directory, uid, gid)
        info = os.fstat(directory)
        if info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o700:
            raise RuntimeError("Private verification directory has unexpected owner/permissions")
        fcntl.flock(directory, fcntl.LOCK_EX | fcntl.LOCK_NB)
        names = os.listdir(directory)
        if enroll and names:
            raise RuntimeError("Enrollment requires an empty private directory; existing series is never overwritten")
        if not enroll and set(names) != {"template.bin", "series.json"}:
            raise RuntimeError("Frozen series is missing/incomplete or contains unexpected files")
        return directory
    except BaseException:
        if directory is not None:
            os.close(directory)
        raise
    finally:
        os.close(work)


def private_bytes(directory, name, uid, limit):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or
                info.st_uid != uid or info.st_nlink != 1 or info.st_size > limit):
            raise RuntimeError("Private series file has unexpected owner/permissions/type/size")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) != info.st_size or len(data) > limit:
            raise RuntimeError("Private series file changed or exceeds the bounded size")
        return data
    finally:
        os.close(fd)


def series_manifest(template):
    return {"format": 1, "finger": "right-index", "stages": 16, "sigfm_threshold": 72,
            "minimum_matches": 5, "template_sha256": hashlib.sha256(template).hexdigest(),
            "library_sha256": LIBRARY_SHA256, "helper_sha256": EXECUTABLE_SHA256,
            "source_sha256": SOURCE_SHA256, "included_source_sha256": INCLUDED_SOURCE_SHA256}


def frozen_template(directory, uid):
    template = private_bytes(directory, "template.bin", uid, MAX_TEMPLATE)
    if len(template) <= 3 or not template.startswith(b"FP3"):
        raise RuntimeError("Private template format is invalid")
    manifest = json.loads(private_bytes(directory, "series.json", uid, 8192))
    if manifest != series_manifest(template):
        raise RuntimeError("Frozen series inputs or template changed; stop before USB")
    return template


def persist_manifest(directory, uid, gid):
    template = private_bytes(directory, "template.bin", uid, MAX_TEMPLATE)
    if len(template) <= 3 or not template.startswith(b"FP3"):
        raise RuntimeError("Enrolled template format is invalid")
    data = (json.dumps(series_manifest(template), sort_keys=True) + "\n").encode("ascii")
    fd = os.open("series.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory)
    try:
        os.fchmod(fd, 0o600)
        os.fchown(fd, uid, gid)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(fd)
    finally:
        os.close(fd)
    os.fsync(directory)


def child_limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (600, 600))
    os.umask(0o077)


def report_line(line):
    if line in STAGES:
        print(STAGES[line], flush=True)
        return None
    if line.startswith("FAIL ") and line[5:] in FAILURES:
        print("INCONCLUSIVE: " + line[5:] + "; this is not a biometric rejection.", flush=True)
        return None
    progress = re.fullmatch(r"PROGRESS ([1-9]|1[0-6]) 16", line)
    if progress:
        print("Accepted enrollment scan " + progress[1] + "/16. Lift your finger.", flush=True)
        return None
    if line in {"RESULT ENROLLED", "RESULT MATCH", "RESULT NO_MATCH"}:
        return line[7:]
    raise RuntimeError("Unexpected child report; raw diagnostics are deliberately hidden")


def monitor(child, report_fd, enroll):
    result = None
    closed = False
    failed = False
    buffer = b""
    total = 0
    last_progress = 0
    end = time.monotonic() + WALL_SECONDS
    os.set_blocking(report_fd, False)
    with selectors.DefaultSelector() as selector:
        selector.register(report_fd, selectors.EVENT_READ)
        eof = False
        while not eof or child.poll() is None:
            remaining = end - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(child.args, WALL_SECONDS)
            for key, _events in selector.select(min(remaining, 0.2)):
                block = os.read(key.fd, 1024)
                if not block:
                    selector.unregister(report_fd)
                    eof = True
                    continue
                total += len(block)
                if total > 16384:
                    raise RuntimeError("Child report limit exceeded")
                buffer += block
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    text = line.decode("ascii", errors="strict")
                    value = report_line(text)
                    if value:
                        if result is not None or not closed or failed:
                            raise RuntimeError("Premature, failed or duplicate result")
                        if (enroll and value != "ENROLLED") or (not enroll and value == "ENROLLED"):
                            raise RuntimeError("Result does not match selected experiment")
                        result = value
                    if text.startswith("PROGRESS "):
                        progress = int(text.split()[1])
                        if not enroll or progress != last_progress + 1:
                            raise RuntimeError("Inconsistent enrollment progress")
                        last_progress = progress
                    closed |= text == "CLOSED"
                    failed |= text.startswith("FAIL ")
            if eof and child.poll() is None:
                time.sleep(min(0.05, max(0, remaining)))
        if (buffer or child.returncode != 0 or failed or not closed or result is None or
                (enroll and last_progress != 16)):
            raise RuntimeError("Operation/close did not complete successfully; trial is INCONCLUSIVE")
    return result


def classify(result, expected):
    if result not in {"MATCH", "NO_MATCH"} or expected not in {"same", "other"}:
        raise RuntimeError("Invalid verification classification")
    if expected == "other" and result == "MATCH":
        return "FALSE_ACCEPT: declared-other finger matched. STOP authentication progress; do not tune or re-enroll to hide this result.", 3
    if expected == "same" and result == "NO_MATCH":
        return "FALSE_REJECT observation: declared-same finger did not match. This single trial is not an accuracy estimate.", 4
    return "Consistent with the declared category; one trial is not authentication proof.", 0


def run(enroll, expected):
    plan()
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError("--run requires an interactive terminal")
    uid, gid = caller()
    library, executable = checked_inputs()
    mode = "enroll" if enroll else "verify"
    confirmation = "ENROLL 27c6:55a4 RIGHT INDEX" if enroll else "VERIFY 27c6:55a4 " + expected.upper()
    descriptors = []
    directory = None
    child = None
    success = False
    try:
        directory = private_directory(uid, gid, enroll)
        template = None if enroll else frozen_template(directory, uid)
        if input("Type " + confirmation + " to begin, or anything else to stop: ") != confirmation:
            print("Stopped before opening USB.")
            return 0
        library_fd = sealed(library)
        descriptors.append(library_fd)
        binary_fd = sealed(executable, executable=True)
        descriptors.append(binary_fd)
        template_fd = 0 if enroll else sealed(template)
        if not enroll:
            descriptors.append(template_fd)
        report_read, report_write = os.pipe2(os.O_CLOEXEC)
        descriptors.extend([report_read, report_write])
        passed = [library_fd, binary_fd, report_write, directory]
        if not enroll:
            passed.append(template_fd)
        child = subprocess.Popen([f"/proc/self/fd/{binary_fd}", mode, str(report_write), str(directory),
                                  str(template_fd), str(uid), str(gid)],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 env=child_environment(library_fd), pass_fds=tuple(passed), cwd="/",
                                 start_new_session=True, preexec_fn=child_limits)
        os.close(report_write)
        descriptors.remove(report_write)
        result = monitor(child, report_read, enroll)
        if enroll:
            persist_manifest(directory, uid, gid)
            success = True
            print("ENROLLED: one private RIGHT INDEX template frozen after successful close. Never share template.bin.")
            return 0
        if frozen_template(directory, uid) != template:
            raise RuntimeError("Frozen template changed during trial; result withheld")
        success = True
        print("Completed verification: " + result + "; declared category: " + expected + ".")
        message, status = classify(result, expected)
        print(message)
        return status
    finally:
        terminate(child)
        for fd in descriptors:
            os.close(fd)
        if directory is not None:
            if enroll and not success:
                for name in ("template.bin", "series.json"):
                    try:
                        os.unlink(name, dir_fd=directory)
                    except FileNotFoundError:
                        pass
            os.close(directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--plan", action="store_true")
    modes.add_argument("--check-inputs", action="store_true")
    modes.add_argument("--run", action="store_true")
    operations = parser.add_mutually_exclusive_group()
    operations.add_argument("--enroll", action="store_true")
    operations.add_argument("--verify", action="store_true")
    parser.add_argument("--expected", choices=("same", "other"))
    args = parser.parse_args()
    if args.run and not (args.enroll or args.verify):
        parser.error("--run requires --enroll or --verify")
    if args.verify and not args.expected:
        parser.error("--verify requires --expected same|other")
    if args.expected and not args.verify:
        parser.error("--expected is only for --verify")
    try:
        if args.run:
            return run(args.enroll, args.expected)
        if args.check_inputs:
            checked_inputs()
            print("Pinned source/helper/library match; no library loaded or USB opened.")
        else:
            plan()
        return 0
    except subprocess.TimeoutExpired:
        print("INCONCLUSIVE: timed out; child stopped. Sensor sleep is unproven.", file=sys.stderr)
        return 124
    except KeyboardInterrupt:
        print("INCONCLUSIVE: interrupted; child stopped.", file=sys.stderr)
        return 130
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        print("Experiment stopped: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
