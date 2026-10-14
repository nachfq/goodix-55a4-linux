"""Offline refusal, frozen-template and final-decision checks; no USB/library loads."""
import contextlib
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

PATH = Path(__file__).resolve().parents[1] / "scripts/14-enroll-verify.py"
spec = importlib.util.spec_from_file_location("enroll_verify", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FrozenSeriesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "work").mkdir()
        self.patches = [mock.patch.object(module, "ROOT", self.root)]
        for patch in self.patches:
            patch.start()
        self.directory = module.private_directory(os.getuid(), os.getgid(), True)

    def tearDown(self):
        os.close(self.directory)
        for patch in self.patches:
            patch.stop()
        self.temp.cleanup()

    def put(self, name, data, mode=0o600):
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode, dir_fd=self.directory)
        os.write(fd, data)
        os.close(fd)

    def series(self):
        self.put("template.bin", b"FP3private-synthetic-template")
        module.persist_manifest(self.directory, os.getuid(), os.getgid())

    def test_frozen_roundtrip_private_metadata(self):
        self.series()
        self.assertEqual(module.frozen_template(self.directory, os.getuid()), b"FP3private-synthetic-template")
        metadata = json.loads(module.private_bytes(self.directory, "series.json", os.getuid(), 8192))
        self.assertEqual(metadata["sigfm_threshold"], 72)
        self.assertEqual(metadata["stages"], 16)
        self.assertEqual(metadata["minimum_matches"], 5)
        self.assertNotIn("private-synthetic-template", json.dumps(metadata))
        self.assertEqual(stat.S_IMODE(os.stat("series.json", dir_fd=self.directory).st_mode), 0o600)

    def test_changed_template_refused(self):
        self.series()
        path = self.root / "work/private-verification/template.bin"
        path.write_bytes(b"FP3changed-template")
        with self.assertRaisesRegex(RuntimeError, "changed"):
            module.frozen_template(self.directory, os.getuid())

    def test_changed_build_refused(self):
        self.series()
        with mock.patch.object(module, "LIBRARY_SHA256", "a" * 64), self.assertRaisesRegex(RuntimeError, "changed"):
            module.frozen_template(self.directory, os.getuid())

    def test_enrollment_never_overwrites(self):
        self.series()
        fcntl.flock(self.directory, fcntl.LOCK_UN)
        with self.assertRaises(RuntimeError):
            module.private_directory(os.getuid(), os.getgid(), True)
        with self.assertRaises(FileExistsError):
            module.persist_manifest(self.directory, os.getuid(), os.getgid())

    def test_symlink_refused(self):
        (self.root / "secret").write_bytes(b"FP3secret")
        os.symlink(self.root / "secret", "template.bin", dir_fd=self.directory)
        with self.assertRaises(OSError):
            module.private_bytes(self.directory, "template.bin", os.getuid(), module.MAX_TEMPLATE)

    def test_hardlink_refused(self):
        self.put("template.bin", b"FP3fake")
        os.link("template.bin", "second", src_dir_fd=self.directory, dst_dir_fd=self.directory)
        with self.assertRaises(RuntimeError):
            module.private_bytes(self.directory, "template.bin", os.getuid(), module.MAX_TEMPLATE)

    def test_permissions_refused(self):
        self.put("template.bin", b"FP3fake", 0o644)
        os.chmod("template.bin", 0o644, dir_fd=self.directory)
        with self.assertRaises(RuntimeError):
            module.private_bytes(self.directory, "template.bin", os.getuid(), module.MAX_TEMPLATE)

    def test_oversize_refused(self):
        self.put("template.bin", b"FP3abcdefgh")
        with self.assertRaises(RuntimeError):
            module.private_bytes(self.directory, "template.bin", os.getuid(), 4)

    def test_bad_format_refused(self):
        self.put("template.bin", b"not-fp3")
        with self.assertRaises(RuntimeError):
            module.persist_manifest(self.directory, os.getuid(), os.getgid())

    def test_verify_requires_complete_series(self):
        os.close(self.directory)
        self.directory = os.open(self.root / "work/private-verification", os.O_RDONLY | os.O_DIRECTORY)
        with self.assertRaises(RuntimeError):
            module.private_directory(os.getuid(), os.getgid(), False)

    def test_existing_directory_public_mode_refused(self):
        os.fchmod(self.directory, 0o755)
        with self.assertRaises(RuntimeError):
            module.private_directory(os.getuid(), os.getgid(), True)

    def test_directory_link_refused(self):
        os.close(self.directory)
        path = self.root / "work/private-verification"
        path.rmdir()
        path.symlink_to(self.root / "work", target_is_directory=True)
        self.directory = os.open(self.root / "work", os.O_RDONLY | os.O_DIRECTORY)
        with self.assertRaises(OSError):
            module.private_directory(os.getuid(), os.getgid(), True)


class DecisionTests(unittest.TestCase):
    def monitor_text(self, text, enroll=False, status=0):
        read, write = os.pipe()
        child = subprocess.Popen([sys.executable, "-c", "import os,sys; os.write(int(sys.argv[1]),sys.argv[2].encode('ascii'));sys.exit(int(sys.argv[3]))", str(write), text, str(status)],
                                 pass_fds=(write,), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(write)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                return module.monitor(child, read, enroll)
        finally:
            module.terminate(child)
            os.close(read)

    def test_completed_match(self):
        self.assertEqual(self.monitor_text("STAGE VERIFY\nSTAGE CLOSE\nCLOSED\nRESULT MATCH\n"), "MATCH")

    def test_completed_nomatch(self):
        self.assertEqual(self.monitor_text("STAGE VERIFY\nSTAGE CLOSE\nCLOSED\nRESULT NO_MATCH\n"), "NO_MATCH")

    def test_no_result_before_close(self):
        with self.assertRaises(RuntimeError):
            self.monitor_text("RESULT MATCH\nCLOSED\n")

    def test_close_error_withholds_match(self):
        with self.assertRaises(RuntimeError):
            self.monitor_text("FAIL CLOSE\nCLOSED\nRESULT MATCH\n")

    def test_retry_is_inconclusive(self):
        with self.assertRaises(RuntimeError):
            self.monitor_text("FAIL RETRY\nCLOSED\n")

    def test_timeout_is_inconclusive(self):
        with self.assertRaises(RuntimeError):
            self.monitor_text("FAIL TIMEOUT\nCLOSED\nRESULT NO_MATCH\n")

    def test_exit_failure_withholds_nomatch(self):
        with self.assertRaises(RuntimeError):
            self.monitor_text("CLOSED\nRESULT NO_MATCH\n", status=1)

    def test_duplicate_result_refused(self):
        with self.assertRaises(RuntimeError):
            self.monitor_text("CLOSED\nRESULT MATCH\nRESULT MATCH\n")

    def test_unknown_raw_report_not_disclosed(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), self.assertRaisesRegex(RuntimeError, "raw diagnostics"):
            module.report_line("ERROR private-fingerprint-bytes")
        self.assertNotIn("private-fingerprint-bytes", stream.getvalue())

    def test_incomplete_line_refused(self):
        with self.assertRaises(RuntimeError):
            self.monitor_text("CLOSED\nRESULT MATCH")

    def test_valid_enrollment_progress(self):
        progress = "".join(f"PROGRESS {n} 16\n" for n in range(1, 17))
        self.assertEqual(self.monitor_text(progress + "CLOSED\nRESULT ENROLLED\n", enroll=True), "ENROLLED")

    def test_skipped_enrollment_progress_refused(self):
        with self.assertRaises(RuntimeError):
            self.monitor_text("PROGRESS 2 16\nCLOSED\nRESULT ENROLLED\n", enroll=True)

    def test_incomplete_enrollment_refused(self):
        with self.assertRaises(RuntimeError):
            self.monitor_text("PROGRESS 1 16\nCLOSED\nRESULT ENROLLED\n", enroll=True)

    def test_result_wrong_mode_refused(self):
        with self.assertRaises(RuntimeError):
            self.monitor_text("CLOSED\nRESULT ENROLLED\n")

    def test_false_accept_stops(self):
        message, status = module.classify("MATCH", "other")
        self.assertEqual(status, 3)
        self.assertIn("STOP", message)
        self.assertIn("FALSE_ACCEPT", message)

    def test_false_reject_separate(self):
        message, status = module.classify("NO_MATCH", "same")
        self.assertEqual(status, 4)
        self.assertIn("FALSE_REJECT", message)

    def test_consistent_categories(self):
        for result, category in (("MATCH", "same"), ("NO_MATCH", "other")):
            self.assertEqual(module.classify(result, category)[1], 0)

    def test_invalid_category_refused(self):
        with self.assertRaises(RuntimeError):
            module.classify("MATCH", "undeclared")


class LauncherTests(unittest.TestCase):
    def test_default_plan_no_input_checks_or_usb(self):
        with mock.patch.object(sys, "argv", [str(PATH)]), mock.patch.object(module, "checked_inputs", side_effect=AssertionError("loaded")), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(module.main(), 0)

    def test_run_refuses_nonterminal(self):
        with mock.patch.object(sys.stdin, "isatty", return_value=False), contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "terminal"):
            module.run(True, None)

    def test_verify_category_required(self):
        with mock.patch.object(sys, "argv", [str(PATH), "--run", "--verify"]), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            module.main()
        self.assertEqual(caught.exception.code, 2)

    def test_enroll_cannot_label_verification(self):
        with mock.patch.object(sys, "argv", [str(PATH), "--run", "--enroll", "--expected", "same"]), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            module.main()

    def test_empty_environment_single_thread(self):
        environment = module.child_environment(9)
        self.assertEqual(environment["LD_PRELOAD"], "/proc/self/fd/9")
        self.assertEqual(environment["OPENBLAS_NUM_THREADS"], "1")
        self.assertNotIn("HOME", environment)
        self.assertNotIn("DBUS_SESSION_BUS_ADDRESS", environment)

    def test_memfd_sealed_against_modification(self):
        fd = module.sealed(b"synthetic-private-template")
        try:
            with self.assertRaises(OSError):
                os.write(fd, b"change")
        finally:
            os.close(fd)

    def test_input_digest_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input"
            path.write_bytes(b"reviewed")
            self.assertEqual(module.checked_bytes(path, hashlib.sha256(b"reviewed").hexdigest()), b"reviewed")
            with self.assertRaises(RuntimeError):
                module.checked_bytes(path, "a" * 64)


if __name__ == "__main__":
    unittest.main()
