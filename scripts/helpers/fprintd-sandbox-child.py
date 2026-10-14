"""Internal private fprintd session. Never execute directly on the host.

Only fixed protocol tags leave this process. Native diagnostics and biometric
identifiers are kept in bounded memory and are never copied into the report.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import selectors
import signal
import socket
import stat
import subprocess
import sys
import time


EXPERIMENT = Path("/experiment")
ADDRESS = "unix:path=/run/fprintd-test/bus"
FINGER = "right-index-finger"
OUTPUT_LIMIT = 16384
REQUIRED_ARTIFACTS = {
    "fprintd", "fprintd-list", "fprintd-enroll", "fprintd-verify",
    "dbus-daemon", "polkitd", "libpolkit-gobject-1.so.0",
    "libduktape.so.207", "libfprint-2.so.2.0.0", "libfprint-observer.so", "dbus.conf", "usb-metadata.py",
}
OBSERVER_RECORDS = {b"VERIFY_OK MATCH\n", b"VERIFY_OK NO_MATCH\n", b"VERIFY_ERROR\n",
                    b"CLOSE_OK\n", b"CLOSE_ERROR\n", b"OBSERVER_ERROR\n"}
STORE = r"/nix/store/[a-z0-9]{32}-[^/\s]+"
DEVICE = r"/net/reactivated/Fprint/Device/[0-9]+"


class SessionError(RuntimeError):
    """A fixed, publishable failure category, without native diagnostics."""


def require(condition, category):
    if not condition:
        raise SessionError(category)


def emit(tag):
    print(tag, flush=True)


def validate_config(config):
    require(isinstance(config, dict), "CONFIG")
    mode = config.get("mode")
    require(mode in {"smoke", "detect", "enroll", "verify"}, "CONFIG")
    require(config.get("expected") in ({"same", "other"} if mode == "verify" else {None}), "CONFIG")
    require(isinstance(config.get("username"), str) and
            re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", config["username"]), "CONFIG")
    namespaces = config.get("host_namespaces")
    require(isinstance(namespaces, dict) and set(namespaces) == {"mnt", "net", "pid"} and
            all(isinstance(v, str) and re.fullmatch(r"[a-z]+:\[[0-9]+\]", v)
                for v in namespaces.values()), "CONFIG")
    artifacts = config.get("artifacts")
    require(isinstance(artifacts, dict) and REQUIRED_ARTIFACTS <= artifacts.keys(), "CONFIG")
    require(all(isinstance(k, str) and re.fullmatch(r"[a-zA-Z0-9_.-]+", k) and
                isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v)
                for k, v in artifacts.items()), "CONFIG")
    require(isinstance(config.get("loader"), str) and
            re.fullmatch(r"/nix/store/[a-z0-9]{32}-glibc-[^/\s]+/lib/ld-linux-x86-64\.so\.2",
                         config["loader"]), "CONFIG")
    require(isinstance(config.get("gdbus"), str) and
            re.fullmatch(STORE + r"/bin/gdbus", config["gdbus"]), "CONFIG")
    library_path = config.get("library_path")
    require(isinstance(library_path, str), "CONFIG")
    directories = library_path.split(":")
    require(directories[0] == "/experiment" and len(directories) > 1 and
            all(re.fullmatch(STORE + r"/(lib|lib64)", directory)
                for directory in directories[1:]), "CONFIG")
    require(type(config.get("polkit_uid")) is int and
            config["polkit_uid"] == (0 if mode == "smoke" else 102), "CONFIG")
    node = config.get("usb_node")
    require(node is None if mode == "smoke" else
            isinstance(node, str) and re.fullmatch(r"/dev/bus/usb/[0-9]{3}/[0-9]{3}", node), "CONFIG")
    return config


def mount_table():
    # Launcher-generated mount paths contain no escaped characters.
    result = {}
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        fields = line.split()
        require(len(fields) > 6 and "-" in fields, "ISOLATION")
        separator = fields.index("-")
        result[fields[4]] = (set(fields[5].split(",")), fields[separator + 1])
    return result


def enclosing_mount(path, mounts):
    candidates = [name for name in mounts if path == name or
                  path.startswith(name.rstrip("/") + "/")]
    require(bool(candidates), "ISOLATION")
    return mounts[max(candidates, key=len)]


def check_isolation(config):
    for name, identity in config["host_namespaces"].items():
        require(os.readlink(f"/proc/self/ns/{name}") != identity, "ISOLATION")
    require(os.getuid() == 0 and os.geteuid() == 0, "ISOLATION")
    for path in ("/home", "/nix/var", "/run/dbus/system_bus_socket",
                 "/var/run/dbus/system_bus_socket", "/run/systemd", "/run/user"):
        require(not os.path.lexists(path), "ISOLATION")
    mounts = mount_table()
    for path in ("/nix/store", "/experiment/session.json", "/etc/passwd",
                 "/etc/group", "/etc/nsswitch.conf", "/etc/fprintd.conf",
                 "/usr/share/polkit-1/actions/net.reactivated.fprint.device.policy"):
        require("ro" in enclosing_mount(path, mounts)[0], "ISOLATION")
    for path in ("/run", "/tmp", "/dev"):
        require(path in mounts and mounts[path][1] == "tmpfs", "ISOLATION")
    require("/proc" in mounts and mounts["/proc"][1] == "proc", "ISOLATION")
    require("/state" in mounts, "ISOLATION")
    require(("ro" in mounts["/state"][0]) == (config["mode"] == "verify"), "ISOLATION")
    for directory in ("/etc/polkit-1/rules.d", "/usr/share/polkit-1/rules.d"):
        require(Path(directory).is_dir() and not any(Path(directory).iterdir()), "ISOLATION")
    require(not any(Path("/run").iterdir()), "ISOLATION")
    node = config["usb_node"]
    usb = Path("/dev/bus/usb")
    if node is None:
        require(not usb.exists() and not os.path.lexists('/sys'), "ISOLATION")
    else:
        info = os.stat(node, follow_symlinks=False)
        bus, address = map(int, node.rsplit("/", 2)[1:])
        require(1 <= bus <= 999 and 1 <= address <= 127 and stat.S_ISCHR(info.st_mode) and
                os.major(info.st_rdev) == 189 and
                os.minor(info.st_rdev) == (bus - 1) * 128 + address - 1, "ISOLATION")
        entries = {str(path) for path in usb.glob("*/*")}
        require(entries == {node} and node in mounts, "ISOLATION")
    for name, digest in config["artifacts"].items():
        path = EXPERIMENT / name
        require("ro" in enclosing_mount(str(path), mounts)[0] and
                stat.S_ISREG(path.lstat().st_mode), "ISOLATION")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        require(actual == digest, "ARTIFACT")
    if node is not None:
        check_metadata_view(config, mounts)


def check_metadata_view(config, mounts):
    require('/sys' in mounts and 'ro' in mounts['/sys'][0] and
            mounts['/sys'][1] != 'sysfs' and
            not any(path.startswith('/sys/') for path in mounts), 'ISOLATION')
    require('usb-descriptors' in config['artifacts'], 'ARTIFACT')
    spec = importlib.util.spec_from_file_location('private_usb_metadata', EXPERIMENT / 'usb-metadata.py')
    metadata = importlib.util.module_from_spec(spec); spec.loader.exec_module(metadata)
    try:
        metadata.check('/sys', config['usb_node'], (EXPERIMENT / 'usb-descriptors').read_bytes())
    except (OSError, RuntimeError):
        raise SessionError('ISOLATION') from None


def native_environment(config):
    env = {
        "DBUS_SYSTEM_BUS_ADDRESS": ADDRESS, "STATE_DIRECTORY": "/state",
        "LANG": "C", "LC_ALL": "C", "GIO_USE_VFS": "local",
        "GIO_MODULE_DIR": "/empty", "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1", "DEBUGINFOD_URLS": "",
        "PATH": str(Path(config["gdbus"]).parent),
    }
    if config['mode'] != 'smoke':
        # check_isolation verified the exact read-only synthetic view before any
        # native load. Permit libudev to consume it without mounting host sysfs.
        env['SYSTEMD_DEVICE_VERIFY_SYSFS'] = '0'
    return env


def drop_capabilities(polkit=False):
    # Run only after isolation checks, in the disposable native subprocess.
    # Polkit needs SETUID/SETGID to become the installed account (uid 102).
    import ctypes

    class Header(ctypes.Structure):
        _fields_ = [("version", ctypes.c_uint32), ("pid", ctypes.c_int)]

    class Data(ctypes.Structure):
        _fields_ = [("effective", ctypes.c_uint32), ("permitted", ctypes.c_uint32),
                    ("inheritable", ctypes.c_uint32)]

    libc = ctypes.CDLL(None, use_errno=True)
    mask = (1 << 6) | (1 << 7) if polkit else 0
    data = (Data * 2)(Data(mask, mask, 0), Data(0, 0, 0))
    if libc.capset(ctypes.byref(Header(0x20080522, 0)), data) != 0:
        raise OSError("capability drop failed")
    if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
        raise OSError("no-new-privileges failed")


class Native:
    def __init__(self, config):
        self.config = config
        self.env = native_environment(config)
        self.processes = []
        self.observer_read, self.observer_write = socket.socketpair(
            socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_NONBLOCK)
        self.observer_records = []
        self.observer_fault = False
        self.observer_closed = False

    def close_observer(self):
        if not self.observer_closed:
            self.observer_read.close()
            self.observer_write.close()
            self.observer_closed = True

    def drain_observer(self):
        if self.observer_closed:
            return
        while True:
            try:
                record = self.observer_read.recv(65)
            except BlockingIOError:
                return
            except OSError:
                self.observer_fault = True
                return
            if record not in OBSERVER_RECORDS or len(self.observer_records) >= 8:
                self.observer_fault = True
                return
            self.observer_records.append(record)

    def check_observer(self, mode, result):
        self.drain_observer()
        expected = []
        if mode == "enroll":
            expected = [b"CLOSE_OK\n"]
        elif mode == "verify":
            require(result in {"MATCH", "NO_MATCH"}, "OBSERVER")
            expected = [("VERIFY_OK " + result + "\n").encode("ascii"), b"CLOSE_OK\n"]
        require(not self.observer_fault and self.observer_records == expected, "OBSERVER")

    def command(self, name, arguments=(), preload=False, loader_option=None):
        command = [self.config["loader"], "--inhibit-cache", "--library-path",
                   self.config["library_path"]]
        if preload:
            library = "/experiment/libfprint-2.so.2.0.0"
            if name == "fprintd":
                library = "/experiment/libfprint-observer.so:" + library
            command += ["--preload", library]
        if loader_option:
            command.append(loader_option)
        command += [name if name.startswith("/nix/store/") else "/experiment/" + name]
        return command + list(arguments)

    def start(self, name, arguments=(), preload=False, capture=False):
        env = self.env.copy()
        passed = ()
        if name == "fprintd":
            env["FPRINTD_OBSERVER_FD"] = str(self.observer_write.fileno())
            passed = (self.observer_write.fileno(),)
        child = subprocess.Popen(
            self.command(name, arguments, preload), env=env, pass_fds=passed,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
            preexec_fn=lambda: drop_capabilities(name == "polkitd" and
                                                self.config["polkit_uid"] != 0))
        self.processes.append((name, child))
        return child

    def capture(self, name, arguments=(), preload=False, timeout=5, loader_option=None):
        child = subprocess.Popen(
            self.command(name, arguments, preload, loader_option), env=self.env,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            preexec_fn=drop_capabilities)
        self.processes.append((name, child))
        try:
            result = read_output(child, timeout)
        finally:
            if child.poll() is not None:
                self.processes.remove((name, child))
                child.stdout.close()
                child.stderr.close()
        return result

    def call(self, destination, path, method, arguments=(), timeout=5):
        status, output, error = self.capture(
            self.config["gdbus"], ("call", "--address", ADDRESS, "--dest", destination,
                                    "--object-path", path, "--method", method, *arguments),
            timeout=timeout)
        require(status == 0 and not error, "DBUS")
        return output.decode("ascii", errors="strict").strip()

    def wait_owner(self, name, deadline):
        while time.monotonic() < deadline:
            require(all(child.poll() is None for process, child in self.processes
                        if process in {"dbus-daemon", "polkitd", "fprintd"}), "STARTUP")
            try:
                response = self.call("org.freedesktop.DBus", "/org/freedesktop/DBus",
                                     "org.freedesktop.DBus.NameHasOwner", (name,), timeout=1)
            except SessionError as error:
                if str(error) not in {"DBUS", "TIMEOUT"}:
                    raise
            else:
                require(response in {"(true,)", "(false,)"}, "DBUS")
                if response == "(true,)":
                    return
            time.sleep(0.1)
        raise SessionError("TIMEOUT")

    def shutdown(self):
        # Stop only processes created by this session, in dependency order.
        # A forced kill or failed fprintd exit invalidates every pending result.
        clean = True
        deadline = time.monotonic() + 10
        for name, child in reversed(self.processes):
            status = child.poll()
            service = name in {"fprintd", "polkitd", "dbus-daemon"}
            if service and status is not None:
                clean = False  # Service disappeared before requested teardown.
            if status is None:
                try:
                    child.terminate()
                    status = child.wait(timeout=min(3, max(0, deadline - time.monotonic())))
                except (OSError, subprocess.TimeoutExpired):
                    clean = False
                    try:
                        child.kill()
                        child.wait(timeout=min(1, max(0, deadline - time.monotonic())))
                    except (OSError, subprocess.TimeoutExpired):
                        pass
                    status = child.poll()
            # CLI success without stderr is the ReleaseDevice gate. Expected
            # SIGTERM shutdown alone is never described as a biometric close.
            if service and status not in {0, -signal.SIGTERM}:
                clean = False
            for stream in (child.stdout, child.stderr):
                if stream:
                    stream.close()
        self.processes.clear()
        self.drain_observer()  # Daemon has stopped: no later records can arrive.
        self.close_observer()
        return clean


def read_output(child, timeout, observer=None):
    """Read both pipes without an unbounded communicate() allocation."""
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    pending = bytearray()
    deadline = time.monotonic() + timeout
    with selectors.DefaultSelector() as selector:
        selector.register(child.stdout, selectors.EVENT_READ, "stdout")
        selector.register(child.stderr, selectors.EVENT_READ, "stderr")
        while selector.get_map():
            require(time.monotonic() < deadline, "TIMEOUT")
            if observer is not None:
                observer.tick()
            for key, _event in selector.select(min(0.2, max(0, deadline - time.monotonic()))):
                data = os.read(key.fileobj.fileno(), 4096)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                buffers[key.data].extend(data)
                require(sum(map(len, buffers.values())) <= OUTPUT_LIMIT, "OUTPUT")
                if observer is not None and key.data == "stdout":
                    pending.extend(data)
                    while b"\n" in pending:
                        line, _, remainder = pending.partition(b"\n")
                        pending = bytearray(remainder)
                        observer.line(line)
        if observer is not None and pending:
            observer.line(pending)
    try:
        status = child.wait(timeout=max(0.01, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        raise SessionError("TIMEOUT") from None
    return status, bytes(buffers["stdout"]), bytes(buffers["stderr"])


def devices(native):
    answer = native.call("net.reactivated.Fprint", "/net/reactivated/Fprint/Manager",
                         "net.reactivated.Fprint.Manager.GetDevices")
    if re.fullmatch(r"\(@ao \[\],\)", answer):
        return []
    paths = re.findall(DEVICE, answer)
    require(len(paths) <= 1, 'DEVICE_MULTIPLE')
    require(len(paths) == 1 and re.fullmatch(
        r"\(\[(?:objectpath )?'" + DEVICE + r"'\],\)", answer), "DEVICE_PROTOCOL")
    return paths


def validate_loader_output(output, error, status):
    require(status == 0 and not error, "LOADER")
    text = output.decode("ascii", errors="strict")
    require("not found" not in text and bool(text.strip()), "LOADER")
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("linux-vdso.so.1 "):
            continue
        path = line.split("=>", 1)[-1].strip().split(" ", 1)[0]
        require(path.startswith(("/nix/store/", "/experiment/")) and
                "/../" not in path, "LOADER")


def smoke_loading(native):
    require(native.config["mode"] == "smoke", "CONFIG")
    def diagnostic(name, status, output, error):
        # Synthetic, USB-free loader trial only. Hardware never emits native
        # diagnostics; these bounded messages must remain in private test logs.
        print("Offline loader check: " + repr((name, status, output[:512], error[:1024])),
              file=sys.stderr, flush=True)
    for name in ("fprintd", "fprintd-list", "fprintd-enroll", "fprintd-verify",
                 "dbus-daemon", "polkitd", native.config["gdbus"]):
        preload = name.startswith("fprintd")
        status, output, error = native.capture(name, preload=preload, loader_option="--list")
        try:
            validate_loader_output(output, error, status)
        except SessionError:
            diagnostic(name, status, output, error)
            raise
    # fprintd-list has no option parser: --help is a username. Its actual
    # private-bus NoDevices call below validates the executable instead.
    for name in ("fprintd", "fprintd-enroll", "fprintd-verify"):
        status, output, error = native.capture(name, ("--help",), preload=True)
        if status != 0 or not output or error:
            diagnostic(name, status, output, error)
        require(status == 0 and output and not error, "LOADER")


def check_private_authorization(native):
    # Test actual authority/policy for uid 0; no agent or interactive prompt.
    fields = Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()
    start_time = int(fields[19])  # field 22; the split begins at field 3
    subject = "('unix-process', {'pid': <uint32 %d>, 'start-time': <uint64 %d>, 'uid': <int32 0>})" % (os.getpid(), start_time)
    for action in ("enroll", "verify", "setusername"):
        reply = native.call("org.freedesktop.PolicyKit1", "/org/freedesktop/PolicyKit1/Authority",
                            "org.freedesktop.PolicyKit1.Authority.CheckAuthorization",
                            (subject, "net.reactivated.fprint.device." + action, "{}", "0", "''"))
        require(re.fullmatch(r"\(\(true, false, (?:@a\{ss\} )?\{\}\),\)", reply), "POLKIT")


class CLIReport:
    def __init__(self, mode, native=None, device=None):
        self.mode = mode
        self.native = native
        self.device = device
        self.result = None
        self.progress = 0
        self.retry = False
        self.device_seen = False
        self.finger_seen = False
        self.seen_present = False
        self.accepted_scan = False
        self.last_prompt = "CALIBRATION"
        self.last_tick = 0

    def prompt(self, tag):
        if tag != self.last_prompt:
            emit(tag)
            self.last_prompt = tag

    def tick(self):
        if self.native is None or not self.finger_seen or self.result is not None:
            return
        now = time.monotonic()
        if now - self.last_tick < 0.2:
            return
        self.last_tick = now
        reply = self.native.call("net.reactivated.Fprint", self.device,
                                 "org.freedesktop.DBus.Properties.GetAll",
                                 ("net.reactivated.Fprint.Device",), timeout=1)
        present = re.findall(r"'finger-present': <(true|false)>", reply)
        needed = re.findall(r"'finger-needed': <(true|false)>", reply)
        require(len(present) == len(needed) == 1, "PROTOCOL")
        self.properties(present[0] == "true", needed[0] == "true")

    def properties(self, present, needed):
        if present:
            self.seen_present = True
            if not needed:
                self.prompt("LIFT")
            elif self.last_prompt == "TOUCH":
                self.last_prompt = None
        elif needed and (self.seen_present or self.accepted_scan):
            self.prompt("TOUCH")

    def line(self, raw):
        try:
            line = raw.decode("ascii")
        except UnicodeError:
            raise SessionError("PROTOCOL") from None
        if not line:
            return
        if re.fullmatch("Using device " + DEVICE, line):
            require(not self.device_seen, "PROTOCOL")
            self.device_seen = True
            return
        if line == "Enrolling right-index-finger finger." and self.mode == "enroll":
            require(not self.finger_seen, "PROTOCOL")
            self.finger_seen = True
            return
        if line == "Verify started!" and self.mode == "verify":
            require(not self.finger_seen, "PROTOCOL")
            self.finger_seen = True
            return
        prefix = "Enroll result: " if self.mode == "enroll" else "Verify result: "
        if line.startswith(prefix):
            require(self.result is None and self.device_seen and self.finger_seen, "PROTOCOL")
            status = line[len(prefix):]
            if self.mode == "verify":
                match = re.fullmatch(r"(verify-[a-z-]+) \((done|not done)\)", status)
                require(match is not None, "PROTOCOL")
                status, done = match.groups()
                require(done == ("not done" if status in {
                    "verify-retry-scan", "verify-swipe-too-short", "verify-finger-not-centered",
                    "verify-remove-and-retry"} else "done"), "PROTOCOL")
            if self.mode == "enroll" and status == "enroll-stage-passed":
                self.progress += 1
                require(self.progress <= 16, "PROTOCOL")
                emit(f"PROGRESS {self.progress} 16")
                self.accepted_scan = True
                self.prompt("LIFT")
            elif status in {"enroll-retry-scan", "enroll-swipe-too-short", "enroll-finger-not-centered",
                            "enroll-remove-and-retry", "verify-retry-scan", "verify-swipe-too-short",
                            "verify-finger-not-centered", "verify-remove-and-retry"}:
                self.retry = True
                emit("RETRY")
                self.prompt("LIFT")
            elif self.mode == "enroll" and status == "enroll-completed":
                # fprintd may report the final accepted stage separately or as
                # completion; native completion and clean Release are required.
                require(self.progress in {15, 16}, "PROTOCOL")
                if self.progress == 15:
                    self.progress = 16
                    emit("PROGRESS 16 16")
                self.result = "ENROLLED"
                self.prompt("LIFT")
            elif self.mode == "verify" and status in {"verify-match", "verify-no-match"}:
                self.result = "MATCH" if status == "verify-match" else "NO_MATCH"
                self.prompt("LIFT")
            elif status in {"enroll-failed", "enroll-data-full", "enroll-disconnected", "enroll-unknown-error",
                            "verify-disconnected", "verify-unknown-error"}:
                raise SessionError("NATIVE")
            else:
                raise SessionError("PROTOCOL")
            return
        # Verification prints the chosen registered finger before starting.
        if self.mode == "verify" and (line == "Listing enrolled fingers:" or
                                      re.fullmatch(r" - #[0-9]+: right-index-finger", line) or
                                      line == "Verifying: right-index-finger"):
            return
        raise SessionError("PROTOCOL")

    def finish(self, status, error):
        require(not error and self.device_seen and self.finger_seen and self.result, "CLI")
        require(not (self.mode == "verify" and self.retry), "RETRY")
        require(status == (1 if self.result == "NO_MATCH" else 0), "CLI")
        return self.result


def operation(native):
    mode = native.config["mode"]
    if mode == "smoke":
        smoke_loading(native)
    boot_deadline = time.monotonic() + 15
    Path("/run/fprintd-test").mkdir(mode=0o755)
    native.start("dbus-daemon", ("--nofork", "--config-file=/experiment/dbus.conf"))
    native.wait_owner("org.freedesktop.DBus", boot_deadline)
    require(stat.S_ISSOCK(Path("/run/fprintd-test/bus").stat().st_mode), "DBUS")
    os.chmod("/run/fprintd-test/bus", 0o666)
    native.start("polkitd", ("--no-debug",))
    native.wait_owner("org.freedesktop.PolicyKit1", boot_deadline)
    check_private_authorization(native)
    native.start("fprintd", ("--no-timeout",), preload=True)
    native.wait_owner("net.reactivated.Fprint", boot_deadline)
    if mode != "smoke":
        emit("READY")
    found = devices(native)
    if mode == "smoke":
        require(not found, "DEVICE")
        status, output, error = native.capture("fprintd-list", (native.config["username"],), preload=True)
        require(status == 1 and output.strip() == b"No devices available" and not error, "CLI")
        native.check_observer(mode, "SMOKE")
        return "SMOKE"
    require(len(found) == 1, "DEVICE_EMPTY")
    emit("DEVICE_FOUND")
    if mode == "detect":
        status, output, error = native.capture("fprintd-list", (native.config["username"],), preload=True,
                                               timeout=15)
        require(status == 0 and not error and output.startswith(b"found 1 devices\n"), "CLI")
        native.check_observer(mode, "DETECTED")
        return "DETECTED"
    emit("CALIBRATION")
    child = native.start("fprintd-" + mode, ("-f", FINGER, native.config["username"]),
                         preload=True, capture=True)
    report = CLIReport(mode, native, found[0])
    status, _output, error = read_output(child, 600 if mode == "enroll" else 60, report)
    result = report.finish(status, error)
    native.check_observer(mode, result)  # CLI waits for Release/close_finish.
    return result


def run():
    require(len(sys.argv) == 1, "CONFIG")
    config = validate_config(json.loads(Path("/experiment/session.json").read_text()))
    check_isolation(config)  # Before ctypes, loader, bus or any native process.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (700, 700))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    def cancelled(_number, _frame):
        raise SessionError("CANCELLED")
    for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(number, cancelled)
    native = Native(config)
    result = None
    failure = None
    try:
        result = operation(native)
    except (OSError, ValueError, UnicodeError, SessionError, subprocess.SubprocessError) as error:
        failure = str(error) if isinstance(error, SessionError) else "INTERNAL"
    finally:
        for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(number, signal.SIG_IGN)
        closed = native.shutdown()
    if not closed:
        failure = "CLOSE"
    if failure is None:
        try:
            native.check_observer(config["mode"], result)
        except SessionError:
            failure = "OBSERVER"
    if failure:
        emit("FAIL " + failure)
        return 1
    if config["mode"] == "smoke":
        emit("PASS PRIVATE_FPRINTD_SMOKE")
    else:
        emit("CLOSED")
        emit("RESULT " + result)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except (OSError, ValueError, KeyError, SessionError, subprocess.SubprocessError):
        emit("FAIL ISOLATION")
        sys.exit(1)
