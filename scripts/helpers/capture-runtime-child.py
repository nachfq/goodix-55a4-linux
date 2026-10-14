"""Internal offline synthetic writer test. Never run on the host."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import stat
import subprocess
import sys
import tempfile


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
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    binary = Path("/experiment/capture-one").read_bytes()
    if hashlib.sha256(binary).hexdigest() != sys.argv[3]:
        raise RuntimeError("Binary hash differs inside sandbox")
    capture = module("launcher")
    library_fd = capture.sealed(isolation.LIBRARY.read_bytes())
    binary_fd = capture.sealed(binary, executable=True)
    try:
        with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
            output = os.open(tmp, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                for attempt in range(2):
                    read, write = os.pipe()
                    command = [f"/proc/self/fd/{binary_fd}", "--self-test", str(write),
                               str(output), str(os.getuid()), str(os.getgid())]
                    try:
                        result = subprocess.run(command, env=capture.child_environment(library_fd),
                                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                                stderr=subprocess.PIPE,
                                                pass_fds=(binary_fd, library_fd, output, write), timeout=10)
                        os.close(write)
                        write = None
                        report = os.read(read, 1024)
                        expected = (b"SELFTEST PROMPT LIFT\nSELFTEST IMAGE 2 2\nSELFTEST EXCLUSIVE_OUTPUT_PASS\n"
                                    if attempt == 0 else b"SELFTEST PROMPT LIFT\nSELFTEST OUTPUT_REFUSED\n")
                        if result.returncode != attempt or report != expected or result.stderr:
                            raise RuntimeError("Synthetic helper did not report the expected result")
                    finally:
                        os.close(read)
                        if write is not None:
                            os.close(write)
                    image = Path(tmp) / "image.pgm"
                    info = image.stat()
                    if (image.read_bytes() != b"P5\n2 2\n255\n\x00\x40\x80\xff" or
                            stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.getuid()):
                        raise RuntimeError("Synthetic PGM format/permissions/owner differ")
            finally:
                os.close(output)
    finally:
        os.close(binary_fd)
        os.close(library_fd)
    print("PASS: isolated sealed runtime, private synthetic PGM, overwrite refused")


if __name__ == "__main__":
    run()
