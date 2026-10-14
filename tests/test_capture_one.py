"""Offline launcher checks: no libfprint load, enumeration or hardware access."""
import contextlib
import fcntl
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location("capture_one", Path(__file__).resolve().parents[1] / "scripts/10-capture-one.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CaptureLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "work").mkdir()
        self.root_patch = mock.patch.object(MODULE, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.addCleanup(self.temp.cleanup)

    def test_default_does_not_check_or_spawn(self):
        with mock.patch.object(sys, "argv", ["capture"]), mock.patch.object(MODULE, "checked_inputs", side_effect=AssertionError), mock.patch.object(MODULE.subprocess, "Popen", side_effect=AssertionError), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(MODULE.main(), 0)

    def test_pins_required_and_mismatch_rejected(self):
        path = self.root / "input"
        path.write_bytes(b"reviewed")
        with self.assertRaises(RuntimeError):
            MODULE.checked_bytes(path, None)
        with self.assertRaises(RuntimeError):
            MODULE.checked_bytes(path, "0" * 64)
        self.assertEqual(MODULE.checked_bytes(path, hashlib.sha256(b"reviewed").hexdigest()), b"reviewed")

    def test_input_symlink_and_directory_symlink_rejected(self):
        path = self.root / "input"
        path.write_bytes(b"reviewed")
        (self.root / "link").symlink_to(path)
        digest = hashlib.sha256(b"reviewed").hexdigest()
        with self.assertRaises(OSError):
            MODULE.checked_bytes(self.root / "link", digest)
        (self.root / "dirlink").symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            MODULE.checked_bytes(self.root / "dirlink/input", digest)

    def test_sealed_copy_refuses_modification(self):
        fd = MODULE.sealed(b"frozen")
        self.addCleanup(os.close, fd)
        os.lseek(fd, 0, os.SEEK_SET)
        self.assertEqual(os.read(fd, 6), b"frozen")
        with self.assertRaises(OSError):
            os.write(fd, b"changed")
        self.assertEqual(fcntl.fcntl(fd, fcntl.F_GET_SEALS) & fcntl.F_SEAL_WRITE, fcntl.F_SEAL_WRITE)

    def test_child_environment_has_no_inherited_debug_or_ld_paths(self):
        with mock.patch.dict(os.environ, {"G_MESSAGES_DEBUG": "all", "LD_LIBRARY_PATH": "/untrusted", "LD_PRELOAD": "/untrusted.so", "GOODIX55X4_TOUCH_DIFF": "0"}):
            environment = MODULE.child_environment(42)
        self.assertEqual(environment["LD_PRELOAD"], "/proc/self/fd/42")
        self.assertNotIn("LD_LIBRARY_PATH", environment)
        self.assertNotIn("G_MESSAGES_DEBUG", environment)
        self.assertNotIn("GOODIX55X4_TOUCH_DIFF", environment)

    def test_private_permissions_and_symlink_refusal(self):
        base, output, name = MODULE.private_directory(os.getuid(), os.getgid())
        try:
            self.assertEqual(stat.S_IMODE(os.fstat(output).st_mode), 0o700)
            self.assertEqual(os.fstat(output).st_uid, os.getuid())
            self.assertTrue(name.startswith("trial-"))
        finally:
            os.close(output)
            os.rmdir(name, dir_fd=base)
            os.close(base)
        private = self.root / "work/private-captures"
        private.rmdir()
        private.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            MODULE.private_directory(os.getuid(), os.getgid())

    def test_existing_public_directory_refused(self):
        private = self.root / "work/private-captures"
        private.mkdir(mode=0o755)
        with self.assertRaises(RuntimeError):
            MODULE.private_directory(os.getuid(), os.getgid())

    def test_output_verification_exclusive_private_and_shape(self):
        base, output, name = MODULE.private_directory(os.getuid(), os.getgid())
        self.addCleanup(os.close, output)
        self.addCleanup(os.close, base)
        path = self.root / "work/private-captures" / name / "image.pgm"
        path.write_bytes(b"P5\n2 1\n255\n" + bytes([3, 4]))
        path.chmod(0o600)
        MODULE.verify_output(output, os.getuid(), (2, 1))
        path.chmod(0o644)
        with self.assertRaises(RuntimeError):
            MODULE.verify_output(output, os.getuid(), (2, 1))
        path.unlink()
        path.symlink_to(self.root / "missing")
        with self.assertRaises(OSError):
            MODULE.verify_output(output, os.getuid(), (2, 1))

    def test_unreviewed_report_never_disclosed(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(RuntimeError):
            MODULE.report_line("secret-device-hash")
        self.assertNotIn("secret-device-hash", output.getvalue())
        with self.assertRaises(RuntimeError):
            MODULE.report_line("RESULT IMAGE 9999 2")

    def test_usb_failures_have_specific_safe_explanations(self):
        for failure, explanation in MODULE.USB_FAILURES.items():
            with self.subTest(failure=failure), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertIsNone(MODULE.report_line("FAIL " + failure))
                self.assertIn(explanation, output.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaises(RuntimeError):
            MODULE.report_line("FAIL USB_LAYOUT unreviewed-device-bytes")
        self.assertNotIn("unreviewed-device-bytes", output.getvalue())
        with self.assertRaises(RuntimeError):
            MODULE.report_line("SELFTEST IMAGE 2 2")

    def test_lift_prompt_is_whitelisted_without_claiming_success(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertIsNone(MODULE.report_line("PROMPT LIFT"))
        self.assertIn("Remove your finger now", output.getvalue())
        self.assertIn("pending", output.getvalue())
        with self.assertRaises(RuntimeError):
            MODULE.report_line("PROMPT LIFT " + "private-data")

    def synthetic_report(self, payload, exit_code=0):
        read, write = os.pipe()
        child = subprocess.Popen([sys.executable, "-c", "import os,sys;os.write(int(sys.argv[1]),bytes.fromhex(sys.argv[2]));sys.exit(int(sys.argv[3]))", str(write), payload.hex(), str(exit_code)], pass_fds=(write,), start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(write)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                return MODULE.monitor(child, read)
        finally:
            MODULE.terminate(child)
            os.close(read)

    def test_monitor_requires_close_success_and_one_result(self):
        self.assertEqual(self.synthetic_report(b"STAGE CAPTURE\nSTAGE CLOSE\nCLOSED\nRESULT IMAGE 2 1\n"), (2, 1))
        for payload in [b"RESULT IMAGE 2 1\n", b"CLOSED\nRESULT IMAGE 2 1\nRESULT IMAGE 2 1\n", b"FAIL CAPTURE\nCLOSED\nRESULT IMAGE 2 1\n", b"CLOSED\nRESULT IMAGE 2 1\ntruncated"]:
            with self.subTest(payload=payload), self.assertRaises(RuntimeError):
                self.synthetic_report(payload)
        with self.assertRaises(RuntimeError):
            self.synthetic_report(b"CLOSED\nRESULT IMAGE 2 1\n", 1)

    def test_noninteractive_run_stops_before_inputs_or_child(self):
        with mock.patch.object(sys.stdin, "isatty", return_value=False), mock.patch.object(MODULE, "checked_inputs", side_effect=AssertionError), mock.patch.object(MODULE.subprocess, "Popen", side_effect=AssertionError), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            MODULE.run()

    def test_cancelled_confirmation_stops_before_output_or_child(self):
        with contextlib.redirect_stdout(io.StringIO()), mock.patch.object(sys.stdin, "isatty", return_value=True), mock.patch.object(sys.stdout, "isatty", return_value=True), mock.patch.object(MODULE, "caller", return_value=(os.getuid(), os.getgid())), mock.patch.object(MODULE, "checked_inputs", return_value=(b"fake", b"fake")), mock.patch("builtins.input", return_value="STOP"), mock.patch.object(MODULE.subprocess, "Popen", side_effect=AssertionError):
            MODULE.run()
        self.assertFalse((self.root / "work/private-captures").exists())

    def test_failure_removes_partial_image_and_trial_directory(self):
        def fake_monitor(_child, _report):
            files = list((self.root / "work/private-captures").glob("trial-*"))
            (files[0] / "image.pgm").write_bytes(b"private-partial")
            raise RuntimeError("synthetic capture failure")
        child = mock.Mock()
        child.poll.return_value = 1
        with contextlib.redirect_stdout(io.StringIO()), mock.patch.object(sys.stdin, "isatty", return_value=True), mock.patch.object(sys.stdout, "isatty", return_value=True), mock.patch.object(MODULE, "caller", return_value=(os.getuid(), os.getgid())), mock.patch.object(MODULE, "checked_inputs", return_value=(b"fake", b"fake")), mock.patch("builtins.input", return_value=MODULE.CONFIRMATION), mock.patch.object(MODULE.subprocess, "Popen", return_value=child), mock.patch.object(MODULE, "monitor", side_effect=fake_monitor), self.assertRaises(RuntimeError):
            MODULE.run()
        self.assertEqual(list((self.root / "work/private-captures").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
