"""Offline private-session guards and native-output classification; no USB/bus."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import sys
import unittest
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "scripts/helpers/fprintd-sandbox-child.py"
SPEC = importlib.util.spec_from_file_location("fprintd_child", SOURCE)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def config(mode="smoke"):
    prefix = "/nix/store/" + "a" * 32
    return {
        "mode": mode, "expected": "same" if mode == "verify" else None,
        "username": "owner", "host_namespaces": {n: n + ":[100]" for n in ("mnt", "net", "pid")},
        "artifacts": {n: hashlib.sha256(b"synthetic").hexdigest() for n in module.REQUIRED_ARTIFACTS},
        "loader": prefix + "-glibc-2.42/lib/ld-linux-x86-64.so.2",
        "library_path": "/experiment:" + prefix + "-glibc-2.42/lib",
        "gdbus": prefix + "-glib-bin/bin/gdbus", "polkit_uid": 0 if mode == "smoke" else 102,
        "usb_node": None if mode == "smoke" else "/dev/bus/usb/001/002",
    }


class ConfigTests(unittest.TestCase):
    def test_valid_modes(self):
        for mode in ("smoke", "detect", "enroll", "verify"):
            self.assertEqual(module.validate_config(config(mode))["mode"], mode)

    def test_untrusted_configuration_refused(self):
        mutations = [
            ("mode", "install"), ("expected", "same"), ("username", "../secret"),
            ("username", "--help"), ("host_namespaces", {"mnt": "mnt:[100]"}),
            ("artifacts", {}), ("artifacts", {"../secret": "0" * 64}),
            ("loader", "/lib64/ld-linux-x86-64.so.2"),
            ("gdbus", "/usr/bin/gdbus"), ("library_path", "/experiment:/usr/lib"),
            ("library_path", "/experiment::/nix/store/" + "a" * 32 + "-glib/lib"),
            ("polkit_uid", 102), ("polkit_uid", False), ("usb_node", "/dev/bus/usb/001/002"),
        ]
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                subject = config()
                subject[key] = value
                with self.assertRaises(module.SessionError):
                    module.validate_config(subject)

    def test_hardware_requires_selected_node_and_real_polkit_uid(self):
        for key, value in (("usb_node", None), ("usb_node", "/dev/sda"), ("polkit_uid", 0)):
            subject = config("detect")
            subject[key] = value
            with self.assertRaises(module.SessionError):
                module.validate_config(subject)

    def test_verify_requires_declared_category(self):
        subject = config("verify")
        subject["expected"] = None
        with self.assertRaises(module.SessionError):
            module.validate_config(subject)

    def test_environment_does_not_inherit_host_bus_or_preload(self):
        with mock.patch.dict(os.environ, {"DBUS_SYSTEM_BUS_ADDRESS": "host-secret",
                                          "LD_PRELOAD": "/usr/lib/unsafe.so", "HOME": "/home/owner"}):
            env = module.native_environment(config())
        self.assertEqual(env["DBUS_SYSTEM_BUS_ADDRESS"], module.ADDRESS)
        self.assertEqual(env["STATE_DIRECTORY"], "/state")
        self.assertEqual(env["DEBUGINFOD_URLS"], "")
        self.assertNotIn("LD_PRELOAD", env)
        self.assertNotIn("HOME", env)
        self.assertNotIn("/usr/bin", env["PATH"])

    def test_synthetic_sysfs_permission_is_private_hardware_only(self):
        self.assertNotIn('SYSTEMD_DEVICE_VERIFY_SYSFS', module.native_environment(config()))
        with mock.patch.dict(os.environ, {'SYSTEMD_DEVICE_VERIFY_SYSFS':'host-value'}):
            self.assertEqual(module.native_environment(config('detect'))['SYSTEMD_DEVICE_VERIFY_SYSFS'], '0')


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.subject = config()
        self.mounts = {
            "/": ({"rw"}, "tmpfs"), "/experiment": ({"ro"}, "ext4"),
            "/nix/store": ({"ro"}, "ext4"), "/etc": ({"ro"}, "tmpfs"),
            "/usr/share/polkit-1/actions": ({"ro"}, "tmpfs"),
            "/state": ({"rw"}, "tmpfs"), "/run": ({"rw"}, "tmpfs"),
            "/tmp": ({"rw"}, "tmpfs"), "/dev": ({"rw"}, "tmpfs"),
            "/proc": ({"rw"}, "proc"),
        }
        self.exposed = set()
        self.nonempty = set()
        self.device_entries = []
        self.data = b"synthetic"
        test = self

        class FakePath:
            def __init__(self, value):
                self.value = str(value)

            def __str__(self):
                return self.value

            def __truediv__(self, value):
                return FakePath(self.value + "/" + value)

            def is_dir(self):
                return True

            def exists(self):
                return self.value in test.exposed

            def iterdir(self):
                return iter([FakePath(self.value + "/bad")] if self.value in test.nonempty else [])

            def glob(self, _pattern):
                return map(FakePath, test.device_entries)

            def lstat(self):
                return mock.Mock(st_mode=stat.S_IFREG | 0o444)

            def open(self, _mode):
                return io.BytesIO(test.data)

        self.patches = [mock.patch.object(module, "Path", FakePath),
                        mock.patch.object(module, "EXPERIMENT", FakePath("/experiment")),
                        mock.patch.object(module, "mount_table", lambda: self.mounts),
                        mock.patch.object(module.os, "readlink", lambda path: path.rsplit("/", 1)[-1] + ":[200]"),
                        mock.patch.object(module.os.path, "lexists", lambda path: path in self.exposed),
                        mock.patch.object(module.os, "getuid", lambda: 0),
                        mock.patch.object(module.os, "geteuid", lambda: 0),
                        mock.patch.object(module.os, "stat", lambda *_a, **_k: mock.Mock(
                            st_mode=stat.S_IFCHR | 0o600, st_rdev=os.makedev(189, 1)))]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)

    def test_complete_private_model_passes(self):
        module.check_isolation(self.subject)

    def test_unchanged_namespace_refused_before_native(self):
        for name in ("mnt", "net", "pid"):
            with self.subTest(name=name), mock.patch.object(module.os, "readlink", lambda path:
                self.subject["host_namespaces"][name] if path.endswith("/" + name) else "other:[200]"):
                with self.assertRaisesRegex(module.SessionError, "ISOLATION"):
                    module.check_isolation(self.subject)

    def test_host_access_paths_refused(self):
        for path in ("/home", "/sys", "/nix/var", "/run/dbus/system_bus_socket",
                     "/var/run/dbus/system_bus_socket", "/run/systemd", "/run/user"):
            with self.subTest(path=path):
                self.exposed.add(path)
                with self.assertRaises(module.SessionError):
                    module.check_isolation(self.subject)
                self.exposed.remove(path)

    def test_writable_input_submount_refused(self):
        self.mounts["/experiment/fprintd"] = ({"rw"}, "ext4")
        with self.assertRaises(module.SessionError):
            module.check_isolation(self.subject)

    def test_changed_artifact_refused(self):
        self.data = b"modified"
        with self.assertRaisesRegex(module.SessionError, "ARTIFACT"):
            module.check_isolation(self.subject)

    def test_private_proc_and_run_mounts_required(self):
        for path in ("/proc", "/run", "/dev", "/tmp"):
            original = self.mounts[path]
            self.mounts[path] = ({"rw"}, "ext4")
            with self.subTest(path=path), self.assertRaises(module.SessionError):
                module.check_isolation(self.subject)
            self.mounts[path] = original

    def test_host_rules_or_existing_bus_refused(self):
        for path in ("/etc/polkit-1/rules.d", "/usr/share/polkit-1/rules.d", "/run"):
            self.nonempty.add(path)
            with self.subTest(path=path), self.assertRaises(module.SessionError):
                module.check_isolation(self.subject)
            self.nonempty.remove(path)

    def test_usb_is_absent_in_smoke(self):
        self.exposed.add("/dev/bus/usb")
        with self.assertRaises(module.SessionError):
            module.check_isolation(self.subject)

    def test_hardware_only_exact_character_node(self):
        self.subject = config("detect")
        self.exposed.add("/dev/bus/usb")
        self.device_entries = [self.subject["usb_node"]]
        self.mounts[self.subject["usb_node"]] = ({"rw"}, "devtmpfs")
        with mock.patch.object(module, 'check_metadata_view') as checked:
            module.check_isolation(self.subject)
            checked.assert_called_once_with(self.subject, self.mounts)
        self.device_entries.append("/dev/bus/usb/001/003")
        with self.assertRaises(module.SessionError):
            module.check_isolation(self.subject)

    def test_verify_state_must_be_readonly(self):
        self.subject = config("verify")
        self.device_entries = [self.subject["usb_node"]]
        self.mounts[self.subject["usb_node"]] = ({"rw"}, "devtmpfs")
        with self.assertRaises(module.SessionError):
            module.check_isolation(self.subject)
        self.mounts["/state"] = ({"ro"}, "ext4")
        with mock.patch.object(module, 'check_metadata_view'):
            module.check_isolation(self.subject)

    def test_metadata_mount_refuses_live_sysfs_writable_or_nested_mount(self):
        subject=config('detect')
        for mounts in ({}, {'/sys':({'rw'},'ext4')}, {'/sys':({'ro'},'sysfs')},
                       {'/sys':({'ro'},'ext4'),'/sys/bus':({'ro'},'sysfs')}):
            with self.subTest(mounts=mounts), self.assertRaisesRegex(module.SessionError, 'ISOLATION'):
                module.check_metadata_view(subject,mounts)

    def test_metadata_descriptor_artifact_is_required(self):
        with self.assertRaisesRegex(module.SessionError, 'ARTIFACT'):
            module.check_metadata_view(config('detect'), {'/sys':({'ro'},'ext4')})


class NativeProtocolTests(unittest.TestCase):
    def report(self, mode="verify", result="verify-match", retry=False):
        report = module.CLIReport(mode)
        lines = ["Using device /net/reactivated/Fprint/Device/0"]
        if mode == "verify":
            lines += ["Listing enrolled fingers:", " - #0: right-index-finger", "Verify started!",
                      "Verifying: right-index-finger"]
            if retry:
                lines.append("Verify result: verify-retry-scan (not done)")
            lines.append("Verify result: " + result + " (done)")
        else:
            lines.append("Enrolling right-index-finger finger.")
            lines += ["Enroll result: enroll-stage-passed"] * 15
            lines.append("Enroll result: enroll-completed")
        with contextlib.redirect_stdout(io.StringIO()):
            for line in lines:
                report.line(line.encode())
        return report

    def test_native_match_and_nomatch_exit_contract(self):
        self.assertEqual(self.report().finish(0, b""), "MATCH")
        self.assertEqual(self.report(result="verify-no-match").finish(1, b""), "NO_MATCH")

    def test_enrollment_requires_all_sixteen_stages(self):
        report = self.report("enroll")
        self.assertEqual(report.progress, 16)
        self.assertEqual(report.finish(0, b""), "ENROLLED")
        short = module.CLIReport("enroll")
        with contextlib.redirect_stdout(io.StringIO()):
            short.line(b"Using device /net/reactivated/Fprint/Device/0")
            short.line(b"Enrolling right-index-finger finger.")
            with self.assertRaises(module.SessionError):
                short.line(b"Enroll result: enroll-completed")

    def test_separate_final_stage_and_completion_do_not_report_seventeenth(self):
        report = module.CLIReport("enroll")
        report.device_seen = report.finger_seen = True
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            for _stage in range(16):
                report.line(b"Enroll result: enroll-stage-passed")
            report.line(b"Enroll result: enroll-completed")
        self.assertEqual(report.finish(0, b""), "ENROLLED")
        self.assertEqual(output.getvalue().count("PROGRESS 16 16"), 1)
        self.assertNotIn("PROGRESS 17", output.getvalue())

    def test_retry_never_becomes_biometric_decision(self):
        for decision in ("verify-match", "verify-no-match"):
            report = self.report(result=decision, retry=True)
            with self.assertRaisesRegex(module.SessionError, "RETRY"):
                report.finish(0 if decision == "verify-match" else 1, b"")

    def test_release_error_withholds_result_without_disclosing_text(self):
        with self.assertRaisesRegex(module.SessionError, "CLI") as error:
            self.report().finish(0, b"ReleaseDevice failed: private-secret")
        self.assertNotIn("private-secret", str(error.exception))

    def test_status_mismatch_and_incomplete_terminal_refused(self):
        for line in (b"Verify result: verify-match (not done)",
                     b"Verify result: verify-no-match", b"Verify result: verify-cancelled (done)"):
            report = module.CLIReport("verify")
            report.device_seen = report.finger_seen = True
            with self.subTest(line=line), self.assertRaises(module.SessionError):
                report.line(line)
        with self.assertRaises(module.SessionError):
            self.report(result="verify-no-match").finish(0, b"")

    def test_unknown_report_is_not_echoed(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaisesRegex(module.SessionError, "PROTOCOL"):
            module.CLIReport("verify").line(b"secret fingerprint dump")
        self.assertEqual(output.getvalue(), "")

    def test_duplicate_and_premature_terminal_refused(self):
        report = self.report()
        with self.assertRaises(module.SessionError):
            report.line(b"Verify result: verify-match (done)")
        with self.assertRaises(module.SessionError):
            module.CLIReport("verify").line(b"Verify result: verify-match (done)")

    def test_calibration_never_prompts_touch_from_early_needed(self):
        report = module.CLIReport("enroll")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            report.line(b"Using device /net/reactivated/Fprint/Device/0")
            report.line(b"Enrolling right-index-finger finger.")
            report.properties(False, True)
            report.properties(False, True)
        self.assertEqual(output.getvalue(), "")

    def test_present_lift_then_needed_touch_and_no_duplicate_prompts(self):
        report = module.CLIReport("verify")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            report.properties(True, False)
            report.properties(True, False)
            report.properties(False, True)
            report.properties(False, True)
        self.assertEqual(output.getvalue(), "LIFT\nTOUCH\n")

    def test_accepted_stage_requires_properties_before_touch(self):
        report = module.CLIReport("enroll")
        output = io.StringIO()
        report.device_seen = report.finger_seen = True
        with contextlib.redirect_stdout(output):
            report.line(b"Enroll result: enroll-stage-passed")
            report.properties(True, False)
            self.assertNotIn("TOUCH", output.getvalue())
            report.properties(False, True)
        self.assertEqual(output.getvalue(), "PROGRESS 1 16\nLIFT\nTOUCH\n")

    def test_property_poll_uses_private_device_and_boolean_fields_only(self):
        native = mock.Mock()
        native.call.return_value = "({'name': <'PRIVATE'>, 'finger-present': <true>, 'finger-needed': <false>},)"
        report = module.CLIReport("verify", native, "/net/reactivated/Fprint/Device/0")
        report.finger_seen = True
        output = io.StringIO()
        with mock.patch.object(module.time, "monotonic", return_value=1), contextlib.redirect_stdout(output):
            report.tick()
            report.tick()
        self.assertEqual(output.getvalue(), "LIFT\n")
        native.call.assert_called_once_with("net.reactivated.Fprint", "/net/reactivated/Fprint/Device/0",
                                           "org.freedesktop.DBus.Properties.GetAll",
                                           ("net.reactivated.Fprint.Device",), timeout=1)
        native.call.return_value = "({'finger-needed': <true>},)"
        with mock.patch.object(module.time, "monotonic", return_value=2), self.assertRaises(module.SessionError):
            report.tick()

    def test_property_poll_stops_after_terminal_status(self):
        native = mock.Mock()
        report = module.CLIReport("verify", native, "/net/reactivated/Fprint/Device/0")
        report.finger_seen = True
        report.result = "MATCH"
        report.tick()
        native.call.assert_not_called()

    def test_capture_closes_finished_pipes_and_releases_process_tracking(self):
        native = module.Native(config())
        self.addCleanup(native.close_observer)
        child = mock.Mock()
        child.poll.return_value = 0
        with mock.patch.object(module.subprocess, "Popen", return_value=child), \
             mock.patch.object(module, "read_output", return_value=(0, b"(true,)", b"")):
            self.assertEqual(native.capture(native.config["gdbus"]), (0, b"(true,)", b""))
        self.assertEqual(native.processes, [])
        child.stdout.close.assert_called_once()
        child.stderr.close.assert_called_once()

    def test_full_loader_resolution_allows_only_frozen_locations(self):
        output = (b"linux-vdso.so.1 (0x0)\n"
                  b"libfprint-2.so.2 => /experiment/libfprint-2.so.2.0.0 (0x0)\n"
                  b"libc.so.6 => /nix/store/abc-glibc/lib/libc.so.6 (0x0)\n")
        module.validate_loader_output(output, b"", 0)
        for bad in (b"libc.so.6 => /usr/lib/libc.so.6 (0x0)\n", b"libusb.so => not found\n", b""):
            with self.subTest(output=bad), self.assertRaises(module.SessionError):
                module.validate_loader_output(bad, b"", 0)

    def test_commands_pin_loader_and_preload_only_fprintd(self):
        native = module.Native(config())
        self.addCleanup(native.close_observer)
        command = native.command("fprintd-enroll", ("-f", module.FINGER, "owner"), preload=True)
        self.assertEqual(command[0], config()["loader"])
        self.assertIn("--inhibit-cache", command)
        self.assertEqual(command[-4:], ["/experiment/fprintd-enroll", "-f", module.FINGER, "owner"])
        self.assertNotIn("--preload", native.command("dbus-daemon"))

    def test_smoke_never_treats_list_help_as_an_actual_username(self):
        native = mock.Mock(config=config())
        native.capture.return_value = (0, b"/nix/store/public/lib/libc.so.6 (0x0)\n", b"")
        module.smoke_loading(native)
        for call in native.capture.call_args_list:
            self.assertFalse(call.args[0] == "fprintd-list" and len(call.args) > 1 and
                             call.args[1] == ("--help",))

    def test_native_loader_diagnostics_only_possible_in_offline_smoke(self):
        native = mock.Mock(config=config("detect"))
        error = io.StringIO()
        with contextlib.redirect_stderr(error), self.assertRaisesRegex(module.SessionError, "CONFIG"):
            module.smoke_loading(native)
        self.assertEqual(error.getvalue(), "")
        native.capture.assert_not_called()

    def test_getdevices_empty_one_and_multiple(self):
        native = mock.Mock()
        native.call.return_value = "(@ao [],)"
        self.assertEqual(module.devices(native), [])
        native.call.return_value = "([objectpath '/net/reactivated/Fprint/Device/0'],)"
        self.assertEqual(module.devices(native), ["/net/reactivated/Fprint/Device/0"])
        native.call.return_value = "([objectpath '/net/reactivated/Fprint/Device/0', '/net/reactivated/Fprint/Device/1'],)"
        with self.assertRaises(module.SessionError):
            module.devices(native)

    def test_getdevices_unknown_protocol_is_distinguished_from_empty(self):
        native=mock.Mock()
        for answer in ('([],)','private unexpected text','([objectpath \'/other\'],)'):
            native.call.return_value=answer
            with self.assertRaisesRegex(module.SessionError,'DEVICE_PROTOCOL'):
                module.devices(native)


class BoundedOutputTests(unittest.TestCase):
    def child(self, source):
        child = subprocess.Popen([sys.executable, "-c", source], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def cleanup():
            if child.poll() is None:
                child.kill()
            child.wait()
            child.stdout.close()
            child.stderr.close()
        self.addCleanup(cleanup)
        return child

    def test_stdout_and_stderr_bounded_together(self):
        child = self.child("import os; os.write(1,b'x'*9000); os.write(2,b'y'*9000)")
        with self.assertRaisesRegex(module.SessionError, "OUTPUT"):
            module.read_output(child, 3)

    def test_deadline_with_live_process_is_inconclusive(self):
        child = self.child("import time; time.sleep(10)")
        with self.assertRaisesRegex(module.SessionError, "TIMEOUT"):
            module.read_output(child, 0.05)

    def test_native_stderr_is_held_separately(self):
        child = self.child("import os; os.write(1,b'ok\\n'); os.write(2,b'private-error')")
        self.assertEqual(module.read_output(child, 3), (0, b"ok\n", b"private-error"))


class ObserverTests(unittest.TestCase):
    def native(self, mode="verify"):
        native = module.Native(config(mode))
        self.addCleanup(native.close_observer)
        return native

    def send(self, native, *records):
        for record in records:
            native.observer_write.send(record)

    def test_private_nonblocking_seqpacket_channel(self):
        native = self.native()
        self.assertEqual(native.observer_read.family, socket.AF_UNIX)
        self.assertFalse(native.observer_read.getblocking())
        self.assertFalse(native.observer_write.getblocking())

    def test_native_match_and_nomatch_require_exact_matching_close(self):
        for decision in ("MATCH", "NO_MATCH"):
            native = self.native()
            self.send(native, ("VERIFY_OK " + decision + "\n").encode(), b"CLOSE_OK\n")
            with self.subTest(decision=decision):
                native.check_observer("verify", decision)

    def test_error_cannot_become_no_match(self):
        native = self.native()
        self.send(native, b"VERIFY_ERROR\n", b"CLOSE_OK\n")
        with self.assertRaisesRegex(module.SessionError, "OBSERVER"):
            native.check_observer("verify", "NO_MATCH")

    def test_missing_conflicting_duplicate_or_error_records_inconclusive(self):
        cases = [(), (b"CLOSE_OK\n",), (b"VERIFY_OK NO_MATCH\n",),
                 (b"VERIFY_OK MATCH\n", b"CLOSE_OK\n"),
                 (b"VERIFY_OK NO_MATCH\n", b"CLOSE_ERROR\n"),
                 (b"VERIFY_OK NO_MATCH\n", b"CLOSE_OK\n", b"CLOSE_OK\n"),
                 (b"VERIFY_OK NO_MATCH\n", b"VERIFY_OK NO_MATCH\n", b"CLOSE_OK\n"),
                 (b"VERIFY_OK NO_MATCH\n", b"CLOSE_OK\n", b"OBSERVER_ERROR\n")]
        for records in cases:
            native = self.native()
            self.send(native, *records)
            with self.subTest(records=records), self.assertRaisesRegex(module.SessionError, "OBSERVER"):
                native.check_observer("verify", "NO_MATCH")

    def test_enrollment_requires_close_without_verify_records(self):
        native = self.native("enroll")
        self.send(native, b"CLOSE_OK\n")
        native.check_observer("enroll", "ENROLLED")
        self.send(native, b"VERIFY_OK MATCH\n")
        with self.assertRaises(module.SessionError):
            native.check_observer("enroll", "ENROLLED")

    def test_smoke_detect_require_no_device_api_records(self):
        for mode in ("smoke", "detect"):
            native = self.native(mode)
            native.check_observer(mode, "SMOKE" if mode == "smoke" else "DETECTED")
            self.send(native, b"CLOSE_OK\n")
            with self.subTest(mode=mode), self.assertRaises(module.SessionError):
                native.check_observer(mode, "DETECTED")

    def test_shutdown_drains_late_records_before_closing_channel(self):
        native = self.native()
        self.send(native, b"VERIFY_OK MATCH\n", b"CLOSE_OK\n")
        native.check_observer("verify", "MATCH")
        self.send(native, b"CLOSE_ERROR\n")
        self.assertTrue(native.shutdown())
        self.assertTrue(native.observer_closed)
        self.assertEqual(native.observer_read.fileno(), -1)
        self.assertEqual(native.observer_write.fileno(), -1)
        with self.assertRaisesRegex(module.SessionError, "OBSERVER"):
            native.check_observer("verify", "MATCH")

    def test_unknown_oversized_or_flooded_packets_never_echoed(self):
        cases = [(b"private secret\n",), (b"x" * 100,), (b"CLOSE_OK\n",) * 9]
        for records in cases:
            native = self.native()
            self.send(native, *records)
            output = io.StringIO()
            with self.subTest(records=records), contextlib.redirect_stdout(output), \
                 self.assertRaisesRegex(module.SessionError, "OBSERVER"):
                native.check_observer("verify", "NO_MATCH")
            self.assertEqual(output.getvalue(), "")

    def test_only_daemon_inherits_observer_fd_and_shim(self):
        native = self.native()
        with mock.patch.object(module.subprocess, "Popen") as popen:
            native.start("fprintd", preload=True)
            daemon = popen.call_args
            native.start("fprintd-verify", preload=True)
            cli = popen.call_args
        descriptor = native.observer_write.fileno()
        self.assertEqual(daemon.kwargs["pass_fds"], (descriptor,))
        self.assertEqual(daemon.kwargs["env"]["FPRINTD_OBSERVER_FD"], str(descriptor))
        self.assertIn("/experiment/libfprint-observer.so:/experiment/libfprint-2.so.2.0.0", daemon.args[0])
        self.assertEqual(cli.kwargs["pass_fds"], ())
        self.assertNotIn("FPRINTD_OBSERVER_FD", cli.kwargs["env"])
        self.assertNotIn("FPRINTD_OBSERVER_FD", native.env)
        self.assertIn("/experiment/libfprint-2.so.2.0.0", cli.args[0])
        self.assertNotIn("/experiment/libfprint-observer.so:/experiment/libfprint-2.so.2.0.0", cli.args[0])

    def test_daemon_loader_list_also_resolves_observer(self):
        native = self.native("smoke")
        command = native.command("fprintd", preload=True, loader_option="--list")
        self.assertIn("--list", command)
        self.assertIn("/experiment/libfprint-observer.so:/experiment/libfprint-2.so.2.0.0", command)


class TeardownTests(unittest.TestCase):
    def child(self, status=None):
        child = mock.Mock()
        child.stdout = child.stderr = None
        child.poll.return_value = status
        child.wait.return_value = 0
        return child

    def test_dependency_order_and_expected_sigterm(self):
        native = module.Native(config())
        self.addCleanup(native.close_observer)
        called = []
        for name in ("dbus-daemon", "polkitd", "fprintd"):
            child = self.child()
            child.terminate.side_effect = lambda name=name: called.append(name)
            child.wait.return_value = -signal.SIGTERM
            native.processes.append((name, child))
        self.assertTrue(native.shutdown())
        self.assertEqual(called, ["fprintd", "polkitd", "dbus-daemon"])

    def test_forced_kill_invalidates_session(self):
        native = module.Native(config())
        self.addCleanup(native.close_observer)
        child = self.child()
        child.wait.side_effect = [subprocess.TimeoutExpired("private", 3), -signal.SIGKILL]
        child.poll.side_effect = [None, -signal.SIGKILL]
        native.processes = [("fprintd", child)]
        self.assertFalse(native.shutdown())
        child.kill.assert_called_once()

    def test_crashed_daemon_withholds_closed(self):
        native = module.Native(config())
        self.addCleanup(native.close_observer)
        native.processes = [("fprintd", self.child(-signal.SIGSEGV))]
        self.assertFalse(native.shutdown())

    def test_any_service_exiting_before_teardown_is_inconclusive(self):
        for name in ("dbus-daemon", "polkitd", "fprintd"):
            native = module.Native(config())
            self.addCleanup(native.close_observer)
            native.processes = [(name, self.child(0))]
            with self.subTest(name=name):
                self.assertFalse(native.shutdown())

    def run_mocked(self, close, result="MATCH", failure=None, mode="verify", observer_failure=None):
        subject = config(mode)
        native = mock.Mock()
        native.shutdown.return_value = close
        native.check_observer.side_effect = observer_failure
        output = io.StringIO()
        patches = [mock.patch.object(module.Path, "read_text", return_value=json.dumps(subject)),
                   mock.patch.object(module, "check_isolation"),
                   mock.patch.object(module.resource, "setrlimit"),
                   mock.patch.object(module.signal, "signal"),
                   mock.patch.object(module, "Native", return_value=native),
                   mock.patch.object(module, "operation", side_effect=failure, return_value=result),
                   mock.patch.object(module.sys, "argv", ["child.py"])]
        with contextlib.ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            stack.enter_context(contextlib.redirect_stdout(output))
            status = module.run()
        return status, output.getvalue(), native

    def test_final_result_requires_cleanup_and_only_fixed_tags(self):
        status, output, _native = self.run_mocked(True)
        self.assertEqual((status, output), (0, "CLOSED\nRESULT MATCH\n"))
        status, output, _native = self.run_mocked(False)
        self.assertEqual((status, output), (1, "FAIL CLOSE\n"))

    def test_native_exception_is_not_disclosed(self):
        status, output, native = self.run_mocked(True, failure=OSError("secret biometric path"))
        self.assertEqual((status, output), (1, "FAIL INTERNAL\n"))
        native.shutdown.assert_called_once()

    def test_smoke_marker_after_teardown(self):
        status, output, _native = self.run_mocked(True, "SMOKE", mode="smoke")
        self.assertEqual((status, output), (0, "PASS PRIVATE_FPRINTD_SMOKE\n"))

    def test_final_observer_error_withholds_native_no_match_and_closed(self):
        status, output, native = self.run_mocked(True, "NO_MATCH",
                                               observer_failure=module.SessionError("OBSERVER"))
        self.assertEqual((status, output), (1, "FAIL OBSERVER\n"))
        native.shutdown.assert_called_once()
        native.check_observer.assert_called_once_with("verify", "NO_MATCH")


if __name__ == "__main__":
    unittest.main()
