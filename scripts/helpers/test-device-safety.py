#!/usr/bin/env python3
"""Extract capture-variant device functions for offline ASan/UBSan checks.

Requires the already prepared Nix shell. Does not load a driver or open USB.
The ignored worktree is an integration input, not a fixed published source pin.
"""
import os
import importlib.util
import hashlib
import json
from pathlib import Path
import re
import resource
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "work/libfprint-capture-fixed/libfprint/drivers/goodixtls/goodix55x4.c"
FUNCTIONS = ("check_firmware_version", "check_preset_psk_read", "decode_frame",
             "frame_diff_score", "retry_calibration", "on_scan_empty_img",
             "learn_fdt_thresholds", "check_fdt_baseline", "dev_init", "close_led_done", "dev_deinit", "scan_complete", "sleep_complete",
             "scan_empty_complete", "goodix55x4_led_done", "dev_deactivate",
             "sleep_run_state")


def extract(text, name):
    pattern = (r"(?m)^static (?:void|gboolean|double)\s+" + re.escape(name)
               + r"\s*\([^;]*?\)\s*\{")
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise RuntimeError("Expected one actual definition: " + name)
    end = text.index("\n}", matches[0].end()) + 2
    return text[matches[0].start():end]


def no_core():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def main():
    if os.geteuid() == 0 or not Path(sys.executable).resolve().is_relative_to("/nix/store"):
        raise RuntimeError("Use the existing Nix Python as the regular user")
    spec = importlib.util.spec_from_file_location("capture_build", ROOT / "scripts/11-build-capture.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.check_inputs()
    # Reuse only generated flags/headers; syntax-check the complete changed unit.
    build = ROOT / "work/libfprint-tls-fixed-build"
    if (hashlib.sha256((build / "compile_commands.json").read_bytes()).hexdigest() !=
            "806c48cb0e9a610c0b0b8633417c186e8df91a4d99bd8937526aed6065831c8a" or
            hashlib.sha256((build / "config.h").read_bytes()).hexdigest() !=
            "da687355004242049fbd1f92f7a575b30a79e3de0e3a0aa15b473cc714e55a5d"):
        raise RuntimeError("Prior generated syntax-check inputs differ from reviewed pins")
    rows = json.loads((build / "compile_commands.json").read_text())
    entries = [row for row in rows if Path(row["file"]).name == "goodix55x4.c"]
    if len(entries) != 1:
        raise RuntimeError("Expected one complete-device compile entry")
    words = shlex.split(entries[0]["command"])
    args = []
    i = 0
    while i < len(words):
        if words[i] in ("-o", "-MF", "-MQ", "-MT"):
            i += 2
            continue
        if words[i] not in ("-c", "-MD", "-MMD"):
            args.append(words[i].replace("../libfprint-tls-fixed", "../libfprint-capture-fixed"))
        i += 1
    subprocess.run(args + ["-fsyntax-only"], cwd=build, check=True, timeout=60)
    print("PASS: complete changed goodix55x4.c syntax")
    text = SOURCE.read_text()
    header = SOURCE.with_suffix(".h").read_text()
    expected = re.search(r"const guint8 goodix_55x4_psk_0\[\] = \{.*?\n\};", header, re.S)
    if not expected:
        raise RuntimeError("Expected public expected-key hash definition")
    bodies = "\n\n".join(extract(text, name) for name in FUNCTIONS)
    base_transport = (ROOT / "work/libfprint-flow-fixed/libfprint/drivers/goodixtls/goodix.c").read_text()
    formatter = re.search(r"(?m)^gchar \*\ndata_to_str \([^;]*?\)\n\{.*?\n\}", base_transport, re.S)
    if not formatter:
        raise RuntimeError("Expected actual original diagnostic formatter")
    bodies = formatter[0] + "\n\n" + bodies
    harness = (ROOT / "tests/device-safety-harness.c").read_text()
    unit = text.split("#include", 1)[0] + harness.replace(
        "/* INSERT EXPECTED HASH */", expected[0]).replace(
        "/* INSERT DRIVER FUNCTIONS */", bodies)
    flags = shlex.split(subprocess.check_output(
        ["pkg-config", "--cflags", "--libs", "gio-2.0"], text=True, timeout=10))
    env = dict(os.environ, ASAN_OPTIONS="detect_leaks=1:halt_on_error=1",
               UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
    with tempfile.TemporaryDirectory(prefix="device-safety-", dir=ROOT / "work") as tmp:
        source = Path(tmp) / "device.c"
        binary = Path(tmp) / "device"
        source.write_text(unit)
        subprocess.run(["cc", "-std=c11", "-g", "-O1", "-Wall", "-Wextra",
                        "-Wno-unused-parameter", "-Wno-unused-function",
                        "-Werror=implicit-function-declaration",
                        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                        str(source), "-o", str(binary), *flags], check=True, timeout=60)
        subprocess.run([str(binary)], check=True, timeout=10, env=env, preexec_fn=no_core)
        original = (ROOT / "work/libfprint-flow-fixed/libfprint/drivers/goodixtls/goodix55x4.c").read_text()
        controls = (("dev_init", "dev.error", "should not be NULL"),
                    ("check_preset_psk_read", 'strstr(ssm.error->message, "a7")', "should be NULL"))
        for name, assertion, expectation in controls:
            source.write_text(unit.replace(extract(text, name), extract(original, name)))
            subprocess.run(["cc", "-std=c11", "-g", "-O1", "-Wno-unused-parameter",
                            "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                            str(source), "-o", str(binary), *flags], check=True, timeout=60)
            result = subprocess.run([str(binary)], capture_output=True, text=True,
                                    timeout=10, env=env, preexec_fn=no_core)
            output = result.stdout + result.stderr
            if result.returncode == 0 or assertion not in output or expectation not in output:
                raise RuntimeError("Original negative control did not fail expected assertion: " + name)
            print("PASS: restoring original " + name + " fails its regression assertion")


if __name__ == "__main__":
    main()
