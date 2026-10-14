"""Offline refusal/cleanup checks; never load the community library here."""
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


parent = module("load_parent", ROOT / "scripts/06-load-library.py")
child = module("load_child", ROOT / "scripts/helpers/load-library-child.py")


class LoadRefusalTests(unittest.TestCase):
    def test_default_plan_does_not_check_or_run(self):
        with patch.object(parent.sys, "argv", ["06-load-library.py"]), \
                patch.object(parent, "checked_inputs") as check, \
                patch.object(parent.subprocess, "run") as execute, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(parent.main(), 0)
        check.assert_not_called()
        execute.assert_not_called()

    def test_host_python_refused_before_artifact_read(self):
        with patch.object(parent.os, "geteuid", return_value=1000), \
                patch.object(parent.sys, "executable", "/usr/bin/python3"), \
                patch.object(parent.Path, "read_bytes") as read:
            with self.assertRaisesRegex(RuntimeError, "Nix"):
                parent.checked_inputs()
        read.assert_not_called()

    def test_changed_artifact_refused_before_execution(self):
        with patch.object(parent.os, "geteuid", return_value=1000), \
                patch.object(parent.sys, "executable", "/nix/store/test-python/bin/python3"), \
                patch.object(parent.Path, "is_file", return_value=True), \
                patch.object(parent.os, "access", return_value=True), \
                patch.object(parent.Path, "read_bytes", return_value=b"changed"):
            with self.assertRaisesRegex(RuntimeError, "hash differs"):
                parent.checked_inputs()

    def trial(self, failure):
        frozen = []
        def execute(command, **kwargs):
            index = command.index("/experiment/libfprint-2.so.2.0.0")
            path = Path(command[index - 1])
            self.assertEqual(path.read_bytes(), b"reviewed bytes")
            frozen.append(path)
            self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
            self.assertTrue(kwargs["close_fds"])
            if isinstance(failure, Exception):
                raise failure
            return subprocess.CompletedProcess(command, failure, "", "bwrap refused")
        with tempfile.TemporaryDirectory(prefix="load-trial-test-") as tmp, \
                patch.object(parent, "ROOT", Path(tmp)), \
                patch.object(parent, "checked_inputs", return_value=(
                    Path("/nix/store/test-python/bin/python3"), b"reviewed bytes",
                    b"helper", {"mnt": "a", "net": "b", "pid": "c"})), \
                patch.object(parent.subprocess, "run", side_effect=execute) as runner, \
                contextlib.redirect_stdout(io.StringIO()):
            (Path(tmp) / "work").mkdir()
            with self.assertRaises((RuntimeError, subprocess.TimeoutExpired)):
                parent.run()
            self.assertEqual(runner.call_count, 1)  # No unsandboxed retry.
            self.assertFalse(frozen[0].exists())

    def test_sandbox_failure_has_no_fallback_and_cleans_snapshot(self):
        self.trial(1)

    def test_timeout_cleans_snapshot_without_retry(self):
        self.trial(subprocess.TimeoutExpired("bwrap", 20))

    def test_same_namespace_prevents_load(self):
        with patch.object(child.os, "readlink", return_value="host"), \
                patch.object(child, "load_types") as load:
            with self.assertRaisesRegex(RuntimeError, "not isolated"):
                child.run({"mnt": "host", "net": "host", "pid": "host"}, "hash")
        load.assert_not_called()

    def test_visible_usb_prevents_load(self):
        with patch.object(child.os, "readlink", return_value="private"), \
                patch.object(child.os.path, "lexists", side_effect=lambda p: p == "/dev/bus/usb"), \
                patch.object(child, "load_types") as load:
            with self.assertRaisesRegex(RuntimeError, "host access"):
                child.run({"mnt": "host", "net": "host", "pid": "host"}, "hash")
        load.assert_not_called()

    def test_writable_store_prevents_load(self):
        mounts = "1 0 0:1 / /nix/store rw - tmpfs tmpfs rw\n"
        with patch.object(child.os, "readlink", return_value="private"), \
                patch.object(child.os.path, "lexists", return_value=False), \
                patch.object(child.Path, "read_text", return_value=mounts), \
                patch.object(child, "load_types") as load:
            with self.assertRaisesRegex(RuntimeError, "read-only mount"):
                child.run({"mnt": "host", "net": "host", "pid": "host"}, "hash")
        load.assert_not_called()

    def test_wrong_type_is_a_failed_trial(self):
        import ctypes
        class FakeLibrary:
            @staticmethod
            def fp_device_get_type():
                return 1
            @staticmethod
            def g_type_name(identifier):
                return b"WrongType"
        with patch.object(ctypes, "CDLL", return_value=FakeLibrary()):
            with self.assertRaisesRegex(RuntimeError, "Unexpected GType"):
                child.load_types()


if __name__ == "__main__":
    unittest.main()
