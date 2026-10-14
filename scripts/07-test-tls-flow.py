#!/usr/bin/env python3
"""Check the separate TLS flow patch and run actual-function offline tests."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "work/libfprint-tls-fixed"
FIXED = ROOT / "work/libfprint-flow-fixed"
RELATIVE = Path("libfprint/drivers/goodixtls")
COMMIT = "d1ca62a801aa565e67d1a2a47aaa7a33232b7990"
BASE_DIFF = "aaa19320440568ba9d7a9622f1c50a47c2262f2e484e1e74e6745445a3acfb16"
FIXED_DIFF = "a632e29b42495053b1bd4320c6d29b25cf4c7135f325e19f66d4dc897be02134"
PATCH_HASH = "23a4dd473eb2b377938b5201a115943da67744473c1dd3c276ce5b36165344aa"
METADATA_HASH = "806c48cb0e9a610c0b0b8633417c186e8df91a4d99bd8937526aed6065831c8a"
CONFIG_HASH = "da687355004242049fbd1f92f7a575b30a79e3de0e3a0aa15b473cc714e55a5d"
DIFF_ARGS = ["-c", "diff.algorithm=myers", "-c", "diff.indentHeuristic=true",
             "-c", "diff.suppressBlankEmpty=false", "diff", "--no-ext-diff",
             "--no-textconv", "--no-renames", "--no-color", "--src-prefix=a/",
             "--dst-prefix=b/", "--unified=3", "--inter-hunk-context=0", "--abbrev=7", "HEAD"]
FUNCTIONS = ("goodix_receive_done", "goodix_receive_none", "goodix_receive_default",
             "goodix_receive_ack", "goodix_receive_protocol", "goodix_reimage_tls_ready",
             "goodix_reset_state", "goodix_send_mcu_get_image", "goodix_tls_finish",
             "goodix_tls_accept_error", "goodix_read_tls", "on_goodix_tls_server_ready",
             "on_goodix_tls_read_handshake", "on_tls_successfully_established",
             "tls_handshake_done", "goodix_tls_poll", "tls_handshake_run",
             "do_tls_handshake", "on_goodix_request_tls_connection", "goodix_tls_ready",
             "goodix_tls", "goodix_shutdown_tls")
CASES = ("retry-budget", "command-budget", "terminal-reset", "new-image-reset",
         "request-error", "initial-short-send", "initial-negative-send", "proxy-error",
         "proxy-short-send", "proxy-negative-send", "hello-eof", "final-eof",
         "initial-pack-error", "final-pack-error", "confirmation-error", "init-error",
         "worker-pending", "worker-failure-wait", "worker-success-proxy",
         "worker-error-fallback", "activation-error", "reentrant-finish",
         "duplicate-finish", "success")


def git(source, *args):
    return subprocess.check_output(["git", "--no-optional-locks", "-C", str(source),
                                    "-c", "core.fsmonitor=false", "-c", "core.fileMode=true",
                                    *args], timeout=10)


def check_inputs():
    patch = (ROOT / "patches/0002-goodix-tls-flow.patch").read_bytes()
    if hashlib.sha256(patch).hexdigest() != PATCH_HASH:
        raise RuntimeError("Flow patch differs from the reviewed pin")
    for source, expected in ((BASE, BASE_DIFF), (FIXED, FIXED_DIFF)):
        if git(source, "rev-parse", "HEAD").decode().strip() != COMMIT:
            raise RuntimeError("Unexpected source commit: " + str(source))
        if Path(git(source, "rev-parse", "--show-toplevel").decode().strip()) != source:
            raise RuntimeError("Unexpected checkout location")
        entries = git(source, "ls-files", "-v").decode().splitlines()
        if any(entry[0].islower() or entry[0] == "S" for entry in entries):
            raise RuntimeError("Hidden index flags; inspect source manually")
        if git(source, "diff", "--cached", "--name-only") or git(source, "ls-files", "--others"):
            raise RuntimeError("Unexpected index or untracked/ignored source inputs")
        if hashlib.sha256(git(source, *DIFF_ARGS)).hexdigest() != expected:
            raise RuntimeError("Effective source differs from the reviewed diff")
    git(BASE, "apply", "--check", str(ROOT / "patches/0002-goodix-tls-flow.patch"))


def function(source, name):
    pattern = (r"(?m)^(?:static )?(?:void|gboolean|GError \*)[ \t]*(?:\n)?"
               + re.escape(name) + r"\s*\([^;]*?\)\s*\{")
    matches = list(re.finditer(pattern, source))
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one definition of " + name)
    start = matches[0].start()
    end = source.index("\n}", matches[0].end()) + 2
    return source[start:end]


def generated_unit():
    source = (FIXED / RELATIVE / "goodix.c").read_text()
    header = (FIXED / RELATIVE / "goodix.h").read_text()
    server = (FIXED / RELATIVE / "goodixtls.h").read_text()
    protocol = (FIXED / RELATIVE / "goodix_proto.h").read_text()
    activation = (FIXED / RELATIVE / "goodix55x4.c").read_text()
    callbacks = header[header.index("typedef struct __attribute__"):
                       header.index("gchar *data_to_str")]
    server_types = server[server.index("struct _GoodixTlsServer;"):
                          server.index("// This is called only once to init")]
    private = re.search(r"typedef struct\n\{.*?\} FpiDeviceGoodixTlsPrivate;", source, re.S)
    stages = re.search(r"enum goodix_tls_handshake_stages \{.*?\n\};", source, re.S)
    if not private or not stages:
        raise RuntimeError("Expected actual private state and handshake stages")
    payloads = []
    for name in ("GoodixAck", "GoodixDefault"):
        start = protocol.index("typedef struct __attribute__((__packed__)) _" + name)
        end = protocol.index("} " + name + ";", start) + len("} " + name + ";")
        payloads.append(protocol[start:end])
    types = "\n".join([callbacks, server_types, private[0], stages[0], *payloads])
    bodies = "\n\n".join(function(source, name) for name in FUNCTIONS)
    bodies += "\n\n" + function(activation, "tls_activation_complete")
    harness = (ROOT / "tests/tls-flow-harness.c").read_text()
    for marker in ("/* INSERT DRIVER TYPES */", "/* INSERT DRIVER FUNCTIONS */"):
        if harness.count(marker) != 1:
            raise RuntimeError("Expected one harness insertion marker: " + marker)
    # Preserve notices for the extracted C bodies and header; generated code is ignored.
    notices = "\n".join(text.split("#", 1)[0] for text in (source, activation, server))
    return notices + harness.replace("/* INSERT DRIVER TYPES */", types).replace(
        "/* INSERT DRIVER FUNCTIONS */", bodies)


def syntax_commands():
    build = ROOT / "work/libfprint-tls-fixed-build"
    metadata = (build / "compile_commands.json").read_bytes()
    config = (build / "config.h").read_bytes()
    if (hashlib.sha256(metadata).hexdigest() != METADATA_HASH or
            hashlib.sha256(config).hexdigest() != CONFIG_HASH):
        raise RuntimeError("Prior generated build metadata/config differs from the local pin")
    rows = json.loads(metadata)
    wanted = {"goodix.c", "goodix55x4.c", "goodixtls.c"}
    commands = []
    for row in rows:
        if Path(row["file"]).name not in wanted:
            continue
        words = shlex.split(row["command"])
        # Reuse flags/generated headers, but compile no object or dependency file.
        args = []
        i = 0
        while i < len(words):
            if words[i] in ("-o", "-MF", "-MQ", "-MT"):
                i += 2
                continue
            if words[i] not in ("-c", "-MD", "-MMD"):
                args.append(words[i].replace("../libfprint-tls-fixed", "../libfprint-flow-fixed"))
            i += 1
        commands.append((build, [*args, "-fsyntax-only"]))
    if len(commands) != 3:
        raise RuntimeError("Expected exactly three changed-C-unit compilation entries")
    return commands


def no_core_dump():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def run():
    if os.geteuid() == 0 or not Path(sys.executable).resolve().is_relative_to("/nix/store"):
        raise RuntimeError("Use existing Nix Python as your regular user, without sudo")
    check_inputs()
    for directory, command in syntax_commands():
        subprocess.run(command, cwd=directory, check=True, timeout=60)
    print("PASS: syntax of three complete changed C units; no objects produced.", flush=True)
    unit = generated_unit()
    flags = shlex.split(subprocess.check_output(
        ["pkg-config", "--cflags", "--libs", "gio-2.0"], text=True, timeout=10))
    env = dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1",
               UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
    with tempfile.TemporaryDirectory(prefix="tls-flow-", dir=ROOT / "work") as tmp:
        source = Path(tmp) / "flow.c"
        binary = Path(tmp) / "flow"
        def compile_unit(text):
            source.write_text(text)
            subprocess.run(["cc", "-std=c11", "-g", "-O1", "-Wall", "-Wextra",
                            "-Werror=implicit-function-declaration", "-Wno-unused-parameter",
                            "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                            str(source), "-o", str(binary), *flags], check=True, timeout=60)

        compile_unit(unit)
        for case in CASES:
            subprocess.run([str(binary), case], env=env, check=True, timeout=10,
                           preexec_fn=no_core_dump)
            print("PASS: " + case, flush=True)
        original = (BASE / RELATIVE / "goodix.c").read_text()
        fixed = (FIXED / RELATIVE / "goodix.c").read_text()
        # Restore one original function at a time, not an entire baseline driver.
        controls = (("goodix_reset_state", "retry-budget", "reimage_tries"),
                    ("on_tls_successfully_established", "confirmation-error", "tls.failures"))
        for name, case, assertion in controls:
            compile_unit(unit.replace(function(fixed, name), function(original, name)))
            result = subprocess.run([str(binary), case], env=env, capture_output=True,
                                    text=True, timeout=10, preexec_fn=no_core_dump)
            output = result.stdout + result.stderr
            if result.returncode == 0 or "assertion failed" not in output or assertion not in output:
                raise RuntimeError("Original-function control did not fail the expected assertion: "
                                   + name + "\n" + output[:2000])
            print("PASS: restoring original " + name + " is detected by " + case, flush=True)
    print(f"{len(CASES)} isolated cases passed with ASan/UBSan; no real TLS handshake or USB.")


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
            check_inputs()
            print("Source/patch pins and applicability checked; no compilation or execution.")
        else:
            print("Plan only: validate the separate flow patch and both effective source pins.")
            print("--run uses the existing Nix environment and prior generated build metadata.")
            print("Syntax-check three changed complete C units, then extract actual flow functions")
            print("and run 24 synthetic failure/retry cases with real GLib and ASan/UBSan,")
            print("plus two negative controls restoring the original affected functions.")
            print("Transport, server results, SSM and device callbacks are test stand-ins.")
            print("No whole-library build/load, USB, downloads, provisioning or system changes.")
            print("Temporary generated units/executables stay under ignored work/ and are removed.")
        return 0
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print("TLS flow tests stopped: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
