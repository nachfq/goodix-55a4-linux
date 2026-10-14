#!/usr/bin/env python3
"""One owner-run, private image acquisition with the reviewed local library."""
import argparse
import fcntl
import hashlib
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
import uuid

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "work/libfprint-capture-fixed-build/libfprint/libfprint-2.so.2.0.0"
EXECUTABLE = ROOT / "work/capture-one-build/capture-one"
SOURCE = ROOT / "scripts/helpers/capture-one.c"
# Filled only after the complete reviewed build, never from a command-line override.
LIBRARY_SHA256 = "e37a3d6e7d6eefd35f201643d6cc399ba6317d9a19b527e83e252dc05f211098"
EXECUTABLE_SHA256 = "2a78efe686dbdb3104eb7e17399f94e065a3414813a71ad0d1afc3f1a0479570"
SOURCE_SHA256 = "568ae51c97ab53987039264bbed4e871878501a9760a50e83ddba051e4724741"
WALL_SECONDS = 90
CONFIRMATION = "CAPTURE 27c6:55a4 ONE IMAGE"
STAGES = {
    "PROMPT LIFT": "Remove your finger now. Acquisition is still pending; waiting for finger-up and cleanup.",
    "STAGE INIT": "Constructing the selected reader.",
    "STAGE OPEN": "Opening its existing interface without detaching a kernel driver.",
    "STAGE CAPTURE": "Activation/calibration started. Keep your finger OFF until the sensor light turns on; then rest it on the reader, without pressing the power button.",
    "STAGE CLOSE": "Closing the reader; remove your finger.",
    "CLOSED": "The driver reported successful close.",
}
FAILURES = {"DISCOVERY", "USB_SELECTION", "INIT", "DRIVER", "OPEN", "CAPTURE", "CLOSE", "OUTPUT", "CANCEL_GRACE"}
USB_FAILURES = {
    "USB_MISSING": "No 27c6:55a4 reader was found.",
    "USB_MULTIPLE": "Multiple matching readers found; refusing to choose one.",
    "USB_OPEN": "Could not open the reader for descriptor checks.",
    "USB_CONFIGURATION": "Could not read an active USB configuration.",
    "USB_DESCRIPTORS": "Could not obtain the selected reader's active descriptors.",
    "USB_LAYOUT": "The active interface/endpoints do not match the reviewed bulk layout.",
    "USB_PRECHECK_CLOSE": "Could not close the descriptor-check handle.",
}
FAILURES.update(USB_FAILURES)


def plan():
    print("Lesson 10: one private image, not enrollment or verification")
    print("Default/--plan and --check-inputs do not load a library or open USB.")
    print("--run requires a terminal and exact typed confirmation before USB access.")
    print("It uses sealed copies of the pinned executable/library and an empty environment.")
    print("USB descriptors are inventoried; only exactly one 27c6:55a4 is opened.")
    print("The driver may reset/enable the sensor, query firmware/key state, configure TLS,")
    print("upload runtime configuration, calibrate/background-capture, detect a finger,")
    print("acquire multiple frames for one returned image, control the LED and sleep.")
    print("No key/firmware write, OS USB configuration switch or kernel-driver detach.")
    print("No fprintd, D-Bus, PAM, enrollment, matching, installation or raw logs.")
    print("Keep your finger off during calibration; touch only after the reader lights.")
    print("Remove your finger immediately when prompted; do not wait for the close stage.")
    print("One PGM is saved only after successful capture AND close, under ignored")
    print("work/private-captures/ with directory 0700/file 0600 owned by the caller.")
    print("Do not share the image. It is biometric data; a frame is not recognition proof.")
    print("Stage cancellation deadlines: init10s/open15s/capture45s/close10s, grace3s.")
    print("Parent hard limit90s. A forced exit releases host handles but cannot prove")
    print("the sensor slept or its LED went dark. Errors/timeouts are inconclusive.")


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
        raise RuntimeError("Capture build pins have not been recorded yet")
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


def checked_inputs():
    library = checked_bytes(LIBRARY, LIBRARY_SHA256)
    executable = checked_bytes(EXECUTABLE, EXECUTABLE_SHA256)
    checked_bytes(SOURCE, SOURCE_SHA256)
    if not library.startswith(b"\x7fELF") or not executable.startswith(b"\x7fELF"):
        raise RuntimeError("Pinned artifacts are not ELF files")
    return library, executable


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


def private_directory(uid, gid):
    work = open_directory(ROOT / "work")
    base = None
    try:
        try:
            os.mkdir("private-captures", 0o700, dir_fd=work)
        except FileExistsError:
            pass
        base = os.open("private-captures", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=work)
        info = os.fstat(base)
        if info.st_uid not in {uid, os.geteuid()} or stat.S_IMODE(info.st_mode) != 0o700:
            raise RuntimeError("Private capture directory has unexpected owner/permissions")
        os.fchown(base, uid, gid)
        name = "trial-" + uuid.uuid4().hex
        os.mkdir(name, 0o700, dir_fd=base)
        output = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=base)
        os.fchmod(output, 0o700)
        os.fchown(output, uid, gid)
        return base, output, name
    except BaseException:
        if base is not None:
            os.close(base)
        raise
    finally:
        os.close(work)


def child_limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (75, 75))
    os.umask(0o077)


def child_command(binary_fd, report_fd, output_fd, uid, gid):
    return [f"/proc/self/fd/{binary_fd}", str(report_fd), str(output_fd), str(uid), str(gid)]


def child_environment(library_fd):
    # The sealed ELF's SONAME satisfies the executable's libfprint DT_NEEDED.
    # Dependencies/interpreter retain their reviewed absolute Nix store paths.
    return {"LD_PRELOAD": f"/proc/self/fd/{library_fd}", "LANG": "C", "LC_ALL": "C",
            "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}


def report_line(line):
    if line in STAGES:
        print(STAGES[line], flush=True)
        return None
    if line.startswith("FAIL ") and line[5:] in FAILURES:
        if line[5:] in USB_FAILURES:
            print(USB_FAILURES[line[5:]], flush=True)
        print("Capture trial failed at " + line[5:] + "; no biometric rejection can be inferred.", flush=True)
        return None
    match = re.fullmatch(r"RESULT IMAGE ([1-9][0-9]{0,3}) ([1-9][0-9]{0,3})", line)
    if match and all(int(value) <= 4096 for value in match.groups()):
        return tuple(map(int, match.groups()))
    raise RuntimeError("Unexpected child report; diagnostics are deliberately not displayed")


def verify_output(directory, uid, dimensions):
    fd = os.open("image.pgm", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != uid or info.st_nlink != 1:
            raise RuntimeError("Captured image has unexpected owner/permissions/type")
        width, height = dimensions
        header = f"P5\n{width} {height}\n255\n".encode("ascii")
        if os.read(fd, len(header)) != header or info.st_size != len(header) + width * height:
            raise RuntimeError("Captured image shape/header is inconsistent")
    finally:
        os.close(fd)


def monitor(child, report_fd):
    result = None
    closed = False
    failed = False
    buffer = b""
    total = 0
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
                if total > 4096:
                    raise RuntimeError("Child report limit exceeded")
                buffer += block
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    text = line.decode("ascii", errors="strict")
                    dimensions = report_line(text)
                    if dimensions:
                        if result is not None:
                            raise RuntimeError("More than one image reported")
                        result = dimensions
                    closed |= text == "CLOSED"
                    failed |= text.startswith("FAIL ")
            if eof and child.poll() is None:
                time.sleep(min(0.05, max(0, remaining)))
        if buffer or child.returncode != 0 or failed or not closed or result is None:
            raise RuntimeError("Capture/close did not complete successfully; trial is inconclusive")
    return result


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


def run():
    plan()
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError("--run requires an interactive terminal")
    uid, gid = caller()
    library, executable = checked_inputs()
    if input("Type " + CONFIRMATION + " to begin, or anything else to stop: ") != CONFIRMATION:
        print("Stopped before opening USB.")
        return
    descriptors = []
    base = output = None
    name = None
    child = None
    success = False
    try:
        base, output, name = private_directory(uid, gid)
        library_fd = sealed(library)
        descriptors.append(library_fd)
        binary_fd = sealed(executable, executable=True)
        descriptors.append(binary_fd)
        report_read, report_write = os.pipe2(os.O_CLOEXEC)
        descriptors.extend([report_read, report_write])
        child = subprocess.Popen(child_command(binary_fd, report_write, output, uid, gid),
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, env=child_environment(library_fd),
                                 pass_fds=(library_fd, binary_fd, report_write, output),
                                 cwd="/", start_new_session=True, preexec_fn=child_limits)
        os.close(report_write)
        descriptors.remove(report_write)
        dimensions = monitor(child, report_read)
        verify_output(output, uid, dimensions)
        success = True
        print(f"One image received: {dimensions[0]} x {dimensions[1]} pixels.")
        print("Private file: " + str(ROOT / "work/private-captures" / name / "image.pgm"))
        print("Capture is not enrollment or verification; do not upload this image.")
    finally:
        terminate(child)
        for descriptor in descriptors:
            os.close(descriptor)
        if output is not None:
            if not success:
                try:
                    os.unlink("image.pgm", dir_fd=output)
                except FileNotFoundError:
                    pass
            os.close(output)
        if base is not None:
            if not success and name:
                os.rmdir(name, dir_fd=base)
            os.close(base)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--plan", action="store_true")
    modes.add_argument("--check-inputs", action="store_true")
    modes.add_argument("--run", action="store_true")
    args = parser.parse_args()
    try:
        if args.run:
            run()
        elif args.check_inputs:
            checked_inputs()
            print("Pinned source, library and executable match. No library loaded or USB opened.")
        else:
            plan()
        return 0
    except subprocess.TimeoutExpired:
        print("Capture timed out; child stopped and incomplete image removed. Sensor sleep is unproven.", file=sys.stderr)
        return 124
    except KeyboardInterrupt:
        print("Capture interrupted; child stopped and incomplete image removed.", file=sys.stderr)
        return 130
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        print("Capture stopped: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
