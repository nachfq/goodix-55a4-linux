"""Internal sandbox helper. Never run directly on the host."""
import hashlib
import json
import os
from pathlib import Path
import resource
import sys

LIBRARY = Path("/experiment/libfprint-2.so.2.0.0")
CALLS = (("fp_device_get_type", "FpDevice"),
         ("fp_print_get_type", "FpPrint"),
         ("fp_context_get_type", "FpContext"))


def check_isolation(host_namespaces, expected_hash):
    if set(host_namespaces) != {"mnt", "net", "pid"}:
        raise RuntimeError("Missing host namespace identities")
    for name, identity in host_namespaces.items():
        if os.readlink(f"/proc/self/ns/{name}") == identity:
            raise RuntimeError("Namespace is not isolated: " + name)
    for path in ("/dev/bus/usb", "/run", "/home", "/sys", "/nix/var"):
        if os.path.lexists(path):
            raise RuntimeError("Unexpected host access path: " + path)
    # These fixed mount points contain no escaped spaces in mountinfo.
    mounts = {fields[4]: set(fields[5].split(","))
              for line in Path("/proc/self/mountinfo").read_text().splitlines()
              if len(fields := line.split()) > 6}
    for path in ("/nix/store", str(LIBRARY), "/experiment/child.py"):
        if "ro" not in mounts.get(path, set()):
            raise RuntimeError("Expected read-only mount: " + path)
    if hashlib.sha256(LIBRARY.read_bytes()).hexdigest() != expected_hash:
        raise RuntimeError("Sandbox artifact hash differs")


def load_types():
    # Import/load happens only after the namespace and mount checks succeed.
    import ctypes
    library = ctypes.CDLL(str(LIBRARY), mode=os.RTLD_NOW | os.RTLD_LOCAL)
    type_name = library.g_type_name
    type_name.argtypes = [ctypes.c_size_t]  # GType is gsize on this x86-64 build.
    type_name.restype = ctypes.c_char_p
    names = []
    for symbol, expected in CALLS:
        get_type = getattr(library, symbol)
        get_type.argtypes = []
        get_type.restype = ctypes.c_size_t
        identifier = get_type()
        actual = type_name(identifier) if identifier else None
        if actual != expected.encode("ascii"):
            raise RuntimeError("Unexpected GType from " + symbol)
        names.append(expected)
    return names


def run(host_namespaces, expected_hash):
    check_isolation(host_namespaces, expected_hash)
    # Limits apply only to this disposable child, not the host or other processes.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    names = load_types()
    print(json.dumps({"isolation": "checked", "dependencies": "resolved", "types": names}))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            raise RuntimeError("Run through scripts/06-load-library.py, never directly")
        run(json.loads(sys.argv[1]), sys.argv[2])
    except (OSError, RuntimeError, ValueError) as error:
        print("Sandbox child stopped: " + str(error), file=sys.stderr)
        sys.exit(1)
