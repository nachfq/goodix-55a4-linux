"""Offline refusal checks: never invoke compilers or a fingerprint reader."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("capture_build", ROOT / "scripts/11-build-capture.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class CaptureBuildTests(unittest.TestCase):
    def test_default_plan_does_not_build_or_read_inputs(self):
        with patch.object(build.sys, "argv", ["11-build-capture.py"]), \
                patch.object(build, "build") as run, patch.object(build, "check_inputs") as check, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(build.main(), 0)
        run.assert_not_called()
        check.assert_not_called()

    def test_root_refused_before_source_or_output_changes(self):
        with patch.object(build.os, "geteuid", return_value=0), \
                patch.object(build, "check_inputs") as check, patch.object(build, "execute") as run:
            with self.assertRaisesRegex(RuntimeError, "regular user"):
                build.build()
        check.assert_not_called()
        run.assert_not_called()

    def test_symlink_output_refused_without_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "work").mkdir()
            output = root / "work/output"
            output.symlink_to(root / "missing")
            with patch.object(build, "ROOT", root), patch.object(build, "BUILD", output), \
                    patch.object(build, "HELPER_BUILD", root / "work/helper"), \
                    patch.object(build, "git") as git:
                with self.assertRaisesRegex(RuntimeError, "Output already exists"):
                    build.check_output()
            self.assertTrue(output.is_symlink())
            git.assert_not_called()

    def test_wrong_target_refused_instead_of_default_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            info = output / "meson-info"
            info.mkdir()
            library = output / "libfprint/libfprint-2.so.2.0.0"
            for rows in ([], [{"name": "fprint-2", "type": "executable", "filename": [str(library)]}],
                         [{"name": "fprint-2", "type": "shared library", "filename": ["wrong"]}]):
                (info / "intro-targets.json").write_text(json.dumps(rows))
                with patch.object(build, "BUILD", output), patch.object(build, "LIBRARY", library):
                    with self.assertRaisesRegex(RuntimeError, "Unexpected library target"):
                        build.selected_target()

    def test_hidden_index_flags_refused(self):
        def git(source, *args):
            if args == ("rev-parse", "--show-toplevel"):
                return str(build.SOURCE).encode() + b"\n"
            if args == ("rev-parse", "HEAD"):
                return build.COMMIT.encode() + b"\n"
            if args == ("ls-files", "-v"):
                return b"h libfprint/meson.build\n"
            self.fail("Should stop before inspecting source content")
        with patch.object(build, "git", side_effect=git):
            with self.assertRaisesRegex(RuntimeError, "Hidden source"):
                build.check_inputs()


if __name__ == "__main__":
    unittest.main()
