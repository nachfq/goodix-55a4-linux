"""Refusal checks for the offline runner, without compiling community code."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "scripts/07-test-tls-flow.py"
spec = importlib.util.spec_from_file_location("tls_flow_runner", path)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RunnerRefusalTests(unittest.TestCase):
    def test_default_mode_checks_no_inputs_and_runs_no_tools(self):
        with patch.object(runner.sys, "argv", ["07-test-tls-flow.py"]), \
                patch.object(runner, "check_inputs") as check, \
                patch.object(runner.subprocess, "run") as execute, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(), 0)
        check.assert_not_called()
        execute.assert_not_called()

    def test_changed_patch_stops_before_git_or_compiler(self):
        with patch.object(runner.Path, "read_bytes", return_value=b"changed"), \
                patch.object(runner, "git") as git:
            with self.assertRaisesRegex(RuntimeError, "patch differs"):
                runner.check_inputs()
        git.assert_not_called()

    def test_ambiguous_function_definition_is_rejected(self):
        source = "static void\nexample (void)\n{\n}\n"
        self.assertEqual(runner.function(source, "example"), source.strip())
        with self.assertRaisesRegex(RuntimeError, "exactly one"):
            runner.function(source + source, "example")

    def test_changed_compile_metadata_is_not_executed(self):
        with patch.object(runner.Path, "read_bytes", return_value=b"changed"):
            with self.assertRaisesRegex(RuntimeError, "metadata/config differs"):
                runner.syntax_commands()

    def test_syntax_commands_cannot_write_objects_or_dependencies(self):
        rows = [{"file": name, "command": "gcc -I../libfprint-tls-fixed -MD -MQ old.o "
                 "-MF old.d -o old.o -c ../libfprint-tls-fixed/" + name}
                for name in ("goodix.c", "goodix55x4.c", "goodixtls.c")]
        metadata = json.dumps(rows).encode()
        with tempfile.TemporaryDirectory() as tmp, patch.object(runner, "ROOT", Path(tmp)), \
                patch.object(runner, "METADATA_HASH", runner.hashlib.sha256(metadata).hexdigest()), \
                patch.object(runner, "CONFIG_HASH", runner.hashlib.sha256(b"config").hexdigest()):
            build = Path(tmp) / "work/libfprint-tls-fixed-build"
            build.mkdir(parents=True)
            (build / "compile_commands.json").write_bytes(metadata)
            (build / "config.h").write_bytes(b"config")
            commands = runner.syntax_commands()
        self.assertEqual(len(commands), 3)
        for directory, command in commands:
            self.assertIn("-fsyntax-only", command)
            self.assertIn("-I../libfprint-flow-fixed", command)
            for forbidden in ("-MD", "-MQ", "-MF", "-o", "-c", "old.o", "old.d"):
                self.assertNotIn(forbidden, command)


if __name__ == "__main__":
    unittest.main()
