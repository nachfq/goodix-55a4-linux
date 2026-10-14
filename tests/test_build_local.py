"""Offline build-walkthrough checks: synthetic Git inputs and fake build tools."""
import hashlib
import json
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import subprocess
import tempfile
import time
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/04-build-local.sh"
BASE_COMMIT = "d1ca62a801aa565e67d1a2a47aaa7a33232b7990"
PATCH_HASH = "73720a4418ed7ceb640011f51d4f2bac206118bc480ab6f1784f6618b479ef15"
FIX_PATCH_HASH = "d3187cbc8c86a3a6881411428e781be9b4a90de68f7a3ae822e1e183bb5594b7"
COMBINED_DIFF_HASH = "aaa19320440568ba9d7a9622f1c50a47c2262f2e484e1e74e6745445a3acfb16"
DIFF_ARGS = [
    "-c", "diff.algorithm=myers", "-c", "diff.indentHeuristic=true",
    "-c", "diff.suppressBlankEmpty=false", "diff", "--no-ext-diff",
    "--no-textconv", "--no-renames", "--no-color", "--src-prefix=a/",
    "--dst-prefix=b/", "--unified=3", "--inter-hunk-context=0", "--abbrev=7", "HEAD",
]

# Each fake tool records calls. No compiler, real Meson or real Ninja is invoked.
FAKE_TOOL = r'''#!/usr/bin/python3
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['FAKE_CALLS'], 'a') as output:
    output.write(json.dumps([name, *args]) + '\n')
if name == 'meson':
    if args == ['--version']:
        print(os.environ.get('FAKE_MESON_VERSION', '1.0.0'))
    elif args[0] == 'setup':
        if os.environ.get('FAIL_SETUP'):
            sys.exit(23)
        build = pathlib.Path(args[1])
        info = build / 'meson-info'
        info.mkdir()
        target = {'name': 'fprint-2', 'type': 'shared library',
                  'filename': [str(build / 'libfprint/libfprint-2.so.2.0.0')]}
        if os.environ.get('BAD_TARGET'):
            target['type'] = 'executable'
        (info / 'intro-targets.json').write_text(json.dumps([target]))
        if os.environ.get('CHANGE_AFTER_SETUP'):
            (pathlib.Path(args[2]) / 'driver.c').write_text('unexpected source\n')
    else:
        sys.exit(99)
elif name == 'pkg-config':
    if args[0] == '--exists':
        sys.exit(1 if args[1].startswith(os.environ.get('MISSING_METADATA', '!')) else 0)
    print('2.56.0')
elif name == 'ninja':
    if os.environ.get('FAIL_NINJA'):
        sys.exit(24)
    assert args[0] == '-C' and args[2] == 'libfprint/libfprint-2.so.2.0.0'
    artifact = pathlib.Path(args[1]) / args[2]
    artifact.parent.mkdir()
    artifact.write_text('synthetic artifact, never executed\n')
elif name == 'readelf':
    print('Synthetic ELF metadata; no real build')
else:
    sys.exit('Unexpected execution of discovery-only tool ' + name)
'''


class BuildLocalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.base = self.repo / "work/libfprint"
        self.source = self.repo / "work/libfprint-patched"
        self.build = self.repo / "work/libfprint-build"
        self.fixed_source = self.repo / "work/libfprint-tls-fixed"
        self.fixed_build = self.repo / "work/libfprint-tls-fixed-build"
        self.fix_patch = self.repo / "patches/0001-goodixtls-safe-errors.patch"
        self.calls = self.repo / "calls.jsonl"
        self.base.mkdir(parents=True)
        self.git(self.repo, "init", "-q", "--template=")
        (self.repo / ".gitignore").write_text("/work/\n")
        self.git(self.base, "init", "-q", "--template=")
        (self.base / "driver.c").write_text("original source\n")
        self.git(self.base, "add", "driver.c")
        self.git(self.base, "-c", "user.name=Offline Test", "-c",
                 "user.email=offline@example.invalid", "commit", "-qm", "Synthetic base")
        commit = self.git(self.base, "rev-parse", "HEAD").strip()
        self.git(self.base, "worktree", "add", "--detach", "-q", str(self.source), "HEAD")
        (self.source / "driver.c").write_text("reviewed synthetic patch\n")
        patch = self.git(self.source, *DIFF_ARGS).encode()
        (self.repo / "work/55a4-driver.patch").write_bytes(patch)
        patch_hash = hashlib.sha256(patch).hexdigest()
        self.git(self.base, "worktree", "add", "--detach", "-q", str(self.fixed_source), "HEAD")
        self.git(self.fixed_source, "apply", str(self.repo / "work/55a4-driver.patch"))
        self.git(self.fixed_source, "add", "driver.c")
        (self.fixed_source / "driver.c").write_text("reviewed synthetic patch\nreviewed TLS error fix\n")
        # The incremental fix compares against the staged community patch; the
        # complete diff against HEAD must cover both staged and unstaged changes.
        fix_patch = self.git(self.fixed_source, *DIFF_ARGS[:-1]).encode()
        self.fix_patch.parent.mkdir()
        self.fix_patch.write_bytes(fix_patch)
        fix_hash = hashlib.sha256(fix_patch).hexdigest()
        combined_hash = hashlib.sha256(self.git(self.fixed_source, *DIFF_ARGS).encode()).hexdigest()
        # Substitute pins in a temporary script copy; the production pins stay fixed.
        script_text = (SCRIPT.read_text().replace(BASE_COMMIT, commit).replace(PATCH_HASH, patch_hash)
                       .replace(FIX_PATCH_HASH, fix_hash).replace(COMBINED_DIFF_HASH, combined_hash))
        scripts = self.repo / "scripts"
        scripts.mkdir()
        self.script = scripts / SCRIPT.name
        self.script.write_text(script_text)
        bindir = self.repo / "fake-bin"
        bindir.mkdir()
        for tool in ("git", "sha256sum", "python3", "mkdir", "dirname", "cat"):
            (bindir / tool).symlink_to(shutil.which(tool))
        for tool in ("cc", "c++", "meson", "ninja", "pkg-config", "glib-mkenums", "readelf"):
            target = bindir / tool
            target.write_text(FAKE_TOOL)
            target.chmod(0o755)
        self.env = dict(os.environ, PATH=str(bindir), FAKE_CALLS=str(self.calls))
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_OPTIONAL_LOCKS="0")
        self.bindir = bindir

    def git(self, directory, *args):
        result = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-C", str(directory), *args], check=True,
                                capture_output=True, text=True,
                                env=dict(os.environ, GIT_CONFIG_NOSYSTEM="1",
                                         GIT_CONFIG_GLOBAL=os.devnull))
        return result.stdout

    def run_mode(self, mode="--check-dependencies", *args):
        return subprocess.run(["/usr/bin/bash", str(self.script), mode, *args], env=self.env,
                              capture_output=True, text=True, timeout=10)

    def recorded(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def run_interactive(self, interrupt=False, eof=False, tls_error_fix=False):
        if os.geteuid() == 0:
            self.skipTest("Interactive success/failure checks need a regular user; root refusal is tested separately")
        master, slave = pty.openpty()
        args = ["/usr/bin/bash", str(self.script), "--run"]
        if tls_error_fix:
            args.append("--tls-error-fix")
        proc = subprocess.Popen(args,
                                stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                env=self.env)
        os.close(slave)
        try:
            if interrupt or eof:
                # Wait for the first prompt before sending SIGINT; no preflight runs.
                data = b""
                deadline = time.monotonic() + 5
                while b"Enter to continue" not in data:
                    self.assertLess(time.monotonic(), deadline, "Missing interactive prompt")
                    ready, _, _ = select.select([proc.stdout], [], [], 0.1)
                    if ready:
                        chunk = os.read(proc.stdout.fileno(), 65536)
                        self.assertTrue(chunk, "Process stopped before prompt")
                        data += chunk
                if eof:
                    os.write(master, b"\x04")
                else:
                    proc.send_signal(signal.SIGINT)
            else:
                data = b""
                os.write(master, b"\n" * 7)
            output, _ = proc.communicate(timeout=10)
            return proc.returncode, (data + output).decode()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
            if proc.stdout:
                proc.stdout.close()
            os.close(master)

    def test_plan_is_default_and_executes_no_tools(self):
        result = subprocess.run(["/usr/bin/bash", str(self.script)], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Compilation establishes compilation only", result.stdout)
        self.assertEqual(self.recorded(), [])
        self.assertFalse(self.build.exists())

    def test_good_dependency_check_is_read_only_and_accepts_worktree_git_file(self):
        self.assertTrue((self.source / ".git").is_file())
        result = self.run_mode()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.build.exists())
        self.assertFalse(any(call[0] in ("ninja", "readelf") or call[1:2] == ["setup"]
                             for call in self.recorded()))
        self.assertEqual(self.git(self.base, "status", "--porcelain"), "")

    def test_tls_fix_plan_selects_separate_inputs_and_executes_no_tools(self):
        result = self.run_mode("--plan", "--tls-error-fix")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Selected variant: community baseline plus TLS error fix", result.stdout)
        for path in (self.fixed_source, self.fixed_build, self.fix_patch):
            self.assertIn(str(path), result.stdout)
        self.assertIn("Community patch SHA-256:", result.stdout)
        self.assertIn("TLS error-fix patch SHA-256:", result.stdout)
        self.assertIn("Canonical assembled diff against base HEAD SHA-256:", result.stdout)
        self.assertEqual(self.recorded(), [])
        self.assertFalse(self.fixed_build.exists())

    def test_tls_fix_check_preserves_outputs_and_requires_fresh_selected_output(self):
        self.build.mkdir()
        sentinel = self.build / "keep.txt"
        sentinel.write_text("baseline artifact")
        result = self.run_mode("--check-dependencies", "--tls-error-fix")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sentinel.read_text(), "baseline artifact")
        self.assertFalse(self.fixed_build.exists())
        self.assertFalse(any(call[0] in ("ninja", "readelf") or call[1:2] == ["setup"]
                             for call in self.recorded()))
        self.fixed_build.mkdir()
        fixed_sentinel = self.fixed_build / "keep.txt"
        fixed_sentinel.write_text("previous fixed artifact")
        result = self.run_mode("--check-dependencies", "--tls-error-fix")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Output already exists: " + str(self.fixed_build), result.stderr)
        self.assertEqual(fixed_sentinel.read_text(), "previous fixed artifact")
        self.assertEqual(sentinel.read_text(), "baseline artifact")

    def test_tls_fix_rejects_damaged_patch_and_combined_source(self):
        cases = [(self.fix_patch, "TLS error-fix patch SHA-256"),
                 (self.fixed_source / "driver.c", "exact reviewed combined diff")]
        for path, message in cases:
            with self.subTest(path=path):
                original = path.read_bytes()
                path.write_bytes(original + b"unexpected change\n")
                result = self.run_mode("--check-dependencies", "--tls-error-fix")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertFalse(self.fixed_build.exists())
                self.assertFalse(any(call[0] == "ninja" or call[1:2] == ["setup"]
                                     for call in self.recorded()))
                path.write_bytes(original)

    def test_baseline_does_not_require_the_optional_fix_patch(self):
        self.fix_patch.unlink()
        result = self.run_mode()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unknown_modes_selectors_and_extra_arguments_fail_before_tools(self):
        for args in (("--unknown",), ("--tls-error-fix",), ("--plan", "--unknown"),
                     ("--plan", "--tls-error-fix", "--unknown")):
            with self.subTest(args=args):
                result = self.run_mode(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(self.recorded(), [])
                self.assertFalse(self.build.exists())
                self.assertFalse(self.fixed_build.exists())

    def test_missing_tool_and_metadata_are_reported_without_building(self):
        (self.bindir / "c++").unlink()
        self.env["MISSING_METADATA"] = "opencv4"
        result = self.run_mode()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing tool: c++", result.stdout)
        self.assertIn("Discovery failed: opencv4", result.stdout)
        self.assertIn("do not prove", result.stdout)
        self.assertFalse(self.build.exists())

    def test_old_meson_is_rejected(self):
        self.env["FAKE_MESON_VERSION"] = "0.55.3"
        self.assertNotEqual(self.run_mode().returncode, 0)

    def test_git_index_inspection_failure_stops_preflight(self):
        actual_git = shutil.which("git")
        wrapper = self.bindir / "git"
        wrapper.unlink()
        wrapper.write_text(
            "#!/usr/bin/python3\nimport os, sys\n"
            "if sys.argv[-2:] == ['ls-files', '-v']: sys.exit(42)\n"
            f"os.execv({actual_git!r}, [{actual_git!r}, *sys.argv[1:]])\n"
        )
        wrapper.chmod(0o755)
        result = self.run_mode()
        self.assertEqual(result.returncode, 42, result.stderr)
        self.assertIn("exit status 42", result.stderr)
        self.assertFalse(self.build.exists())

    def test_changed_patch_and_tracked_source_and_base_are_rejected(self):
        cases = [(self.repo / "work/55a4-driver.patch", "Patch SHA-256"),
                 (self.source / "driver.c", "Patched source differs"),
                 (self.base / "driver.c", "clean base has local changes")]
        for path, message in cases:
            with self.subTest(path=path):
                old = path.read_bytes()
                path.write_bytes(old + b"unexpected change\n")
                result = self.run_mode()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertFalse(self.build.exists())
                path.write_bytes(old)

    def test_wrong_commit_is_rejected(self):
        self.git(self.source, "-c", "user.name=Offline Test", "-c",
                 "user.email=offline@example.invalid", "commit", "--allow-empty", "-qm", "Other commit")
        result = self.run_mode()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unexpected HEAD", result.stderr)

    def test_untracked_including_ignored_source_files_are_rejected(self):
        for name in ("extra.h", ".gitignore"):
            with self.subTest(name=name):
                path = self.source / name
                path.write_text("extra.h\n")
                result = self.run_mode()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Untracked or ignored", result.stderr)
                path.unlink()

    def test_existing_output_is_preserved_and_unignored_output_is_rejected(self):
        self.build.mkdir()
        sentinel = self.build / "keep.txt"
        sentinel.write_text("owner data")
        result = self.run_mode()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Output already exists", result.stderr)
        self.assertEqual(sentinel.read_text(), "owner data")
        sentinel.unlink()
        self.build.rmdir()
        (self.repo / ".gitignore").write_text("")
        result = self.run_mode()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be ignored", result.stderr)

    def test_run_requires_tty_or_refuses_root(self):
        result = self.run_mode("--run")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refuses root" if os.geteuid() == 0 else "interactive terminal", result.stderr)
        self.assertEqual(self.recorded(), [])

    def test_root_guard_is_enforced_before_any_tool(self):
        # Simulate the guard's root branch only in the temporary script copy.
        self.script.write_text(self.script.read_text().replace("(( EUID != 0 ))", "false"))
        result = self.run_mode("--run")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refuses root", result.stderr)
        self.assertEqual(self.recorded(), [])

    def test_hidden_index_flags_are_rejected(self):
        for flag in ("--assume-unchanged", "--skip-worktree"):
            with self.subTest(flag=flag):
                self.git(self.source, "update-index", flag, "driver.c")
                result = self.run_mode()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Hidden index flags", result.stderr)
                self.git(self.source, "update-index", "--no-assume-unchanged", "--no-skip-worktree", "driver.c")

    def test_enter_steps_build_only_shared_library(self):
        status, output = self.run_interactive()
        self.assertEqual(status, 0, output)
        calls = self.recorded()
        setup = next(call for call in calls if call[:2] == ["meson", "setup"])
        for option in ("--backend=ninja", "--wrap-mode=nofallback", "-Ddrivers=goodixtls55x4",
                       "-Dintrospection=false", "-Ddoc=false", "-Dgtk-examples=false",
                       "-Dinstalled-tests=false", "-Dudev_rules=disabled", "-Dudev_hwdb=disabled"):
            self.assertIn(option, setup)
        self.assertEqual([call for call in calls if call[0] == "ninja"],
                         [["ninja", "-C", str(self.build), "libfprint/libfprint-2.so.2.0.0"]])
        self.assertEqual([call[0] for call in calls[-2:]], ["ninja", "readelf"])
        self.assertIn("no installation or hardware test", output)
        self.assertEqual(self.git(self.base, "status", "--porcelain"), "")

    def test_enter_steps_tls_fix_build_only_selected_worktree_and_output(self):
        self.build.mkdir()
        sentinel = self.build / "keep.txt"
        sentinel.write_text("baseline artifact")
        status, output = self.run_interactive(tls_error_fix=True)
        self.assertEqual(status, 0, output)
        calls = self.recorded()
        setup = next(call for call in calls if call[:2] == ["meson", "setup"])
        self.assertEqual(setup[2:4], [str(self.fixed_build), str(self.fixed_source)])
        self.assertEqual([call for call in calls if call[0] == "ninja"],
                         [["ninja", "-C", str(self.fixed_build), "libfprint/libfprint-2.so.2.0.0"]])
        self.assertEqual([call for call in calls if call[0] == "readelf"],
                         [["readelf", "-d", str(self.fixed_build / "libfprint/libfprint-2.so.2.0.0")]])
        self.assertEqual(sentinel.read_text(), "baseline artifact")
        self.assertTrue((self.fixed_build / "libfprint/libfprint-2.so.2.0.0").is_file())

    def test_interruption_before_first_step_runs_no_tools(self):
        status, output = self.run_interactive(interrupt=True)
        self.assertEqual(status, 130, output)
        self.assertEqual(self.recorded(), [])
        self.assertFalse(self.build.exists())

    def test_eof_before_first_step_runs_no_tools(self):
        status, output = self.run_interactive(eof=True)
        self.assertEqual(status, 130, output)
        self.assertIn("Stopped at prompt (EOF)", output)
        self.assertEqual(self.recorded(), [])
        self.assertFalse(self.build.exists())

    def test_setup_failure_bad_target_source_change_and_compile_failure_stop(self):
        cases = [("FAIL_SETUP", 23, False), ("BAD_TARGET", 1, False),
                 ("CHANGE_AFTER_SETUP", 1, False), ("FAIL_NINJA", 24, True)]
        for setting, expected_status, ninja_expected in cases:
            with self.subTest(setting=setting):
                self.env[setting] = "1"
                status, output = self.run_interactive()
                self.assertEqual(status, expected_status, output)
                names = [call[0] for call in self.recorded()]
                self.assertEqual("ninja" in names, ninja_expected)
                self.assertNotIn("readelf", names)
                self.assertTrue(self.build.is_dir())
                # Only temporary synthetic fixture data is removed between trials.
                shutil.rmtree(self.build)
                self.calls.unlink()
                (self.source / "driver.c").write_text("reviewed synthetic patch\n")
                del self.env[setting]


if __name__ == "__main__":
    unittest.main()
