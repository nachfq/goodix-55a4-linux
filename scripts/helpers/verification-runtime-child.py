"""Internal synthetic full-library test. Never run directly on the host."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import subprocess
import sys


def module(name):
    spec = importlib.util.spec_from_file_location(name, "/experiment/" + name + ".py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def run():
    if len(sys.argv) != 4:
        raise RuntimeError("Run only through the isolated runtime script")
    isolation = module("isolation")
    isolation.check_isolation(json.loads(sys.argv[1]), sys.argv[2])
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    binary = Path("/experiment/enroll-verify").read_bytes()
    if hashlib.sha256(binary).hexdigest() != sys.argv[3]:
        raise RuntimeError("Binary hash differs inside sandbox")
    launcher = module("launcher")
    library_fd = launcher.sealed(isolation.LIBRARY.read_bytes())
    binary_fd = launcher.sealed(binary, executable=True)
    read, write = os.pipe()
    try:
        env = launcher.child_environment(library_fd)
        env["G_DEBUG"] = "fatal-criticals"
        result = subprocess.run([f"/proc/self/fd/{binary_fd}", "--self-test", str(write)],
                                env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, pass_fds=(binary_fd, library_fd, write),
                                timeout=20)
        os.close(write)
        write = None
        report = os.read(read, 4096)
        expected = (b"PROMPT LIFT\nPROMPT TOUCH\nFAIL TIMEOUT\n"
                    b"SELFTEST TEMPLATE_ROUNDTRIP_PASS\n")
        if result.returncode != 0 or report != expected or result.stderr:
            raise RuntimeError("Synthetic helper unexpected status/report: " + repr((result.returncode, report, result.stderr[:1024])))
    finally:
        os.close(read)
        if write is not None:
            os.close(write)
        os.close(binary_fd)
        os.close(library_fd)
    print("PASS: isolated sealed runtime, synthetic template round-trip, prompts and deadline")


if __name__ == "__main__":
    run()
