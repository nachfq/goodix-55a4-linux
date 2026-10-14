"""Synthetic filesystem and process guards; no USB/native service execution."""
import contextlib
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

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fprintd_session', ROOT / 'scripts/17-fprintd-session.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def descriptors(vid=0x27c6, pid=0x55a4):
    device = bytearray(18); device[:2] = bytes((18, 1)); device[8:12] = vid.to_bytes(2, 'little') + pid.to_bytes(2, 'little')
    return bytes(device) + bytes((9, 2, 32, 0, 1, 1, 0, 128, 50,
                                 9, 4, 0, 0, 2, 255, 0, 0, 0,
                                 7, 5, 1, 2, 64, 0, 0, 7, 5, 130, 2, 64, 0, 0))


class USBGuardTests(unittest.TestCase):
    def test_standard_layout_accepts_only_target_bulk_pair(self):
        module.parse_descriptors(descriptors())
        for replacement in (descriptors(pid=0x55b4), descriptors()[:-1], descriptors() + b'\0',
                            descriptors().replace(b'\x07\x05\x82\x02', b'\x07\x05\x83\x02'),
                            descriptors().replace(b'\x07\x05\x01\x02', b'\x07\x05\x01\x03')):
            with self.subTest(replacement=replacement[-7:]), self.assertRaises(RuntimeError):
                module.parse_descriptors(replacement)

    def test_extra_interface_refused(self):
        with self.assertRaises(RuntimeError):
            module.parse_descriptors(descriptors() + bytes((9, 4, 1, 0, 0, 255, 0, 0, 0)))

    def test_missing_multiple_or_bound_sensor_refused_before_node_open(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.object(module.os, 'open') as opened:
                with self.assertRaises(RuntimeError): module.select_usb(root)
                for name in ('1-1', '2-1'):
                    device = root / name; device.mkdir()
                    (device/'idVendor').write_text('27c6'); (device/'idProduct').write_text('55a4')
                with self.assertRaises(RuntimeError): module.select_usb(root)
                opened.assert_not_called()

    def test_kernel_owned_refused_without_detach(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); device=root/'1-1'; device.mkdir()
            for name,value in {'idVendor':'27c6','idProduct':'55a4','bConfigurationValue':'1'}.items():
                (device/name).write_text(value)
            (device/'descriptors').write_bytes(descriptors())
            interface=root/'1-1:1.0'; interface.mkdir(); (interface/'driver').symlink_to('/does-not-exist')
            with mock.patch.object(module.os, 'open') as opened, self.assertRaises(RuntimeError):
                module.select_usb(root)
            opened.assert_not_called()


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(); self.root=Path(self.temporary.name)
        self.fd=os.open(self.root, os.O_RDONLY|os.O_DIRECTORY)
    def tearDown(self):
        os.close(self.fd); self.temporary.cleanup()
    def template(self):
        path=self.root/'finger'; path.write_bytes(b'FP3synthetic-fixture'); path.chmod(0o600); return path
    def test_snapshot_detects_mutation(self):
        path=self.template(); original=module.scan_state(self.fd)
        self.assertEqual(len(original),1)
        path.write_bytes(b'FP3changed-fixture'); self.assertNotEqual(original,module.scan_state(self.fd))
    def test_symlink_and_hardlink_refused(self):
        path=self.template(); (self.root/'alias').symlink_to(path)
        with self.assertRaises(RuntimeError): module.scan_state(self.fd)
        (self.root/'alias').unlink(); os.link(path,self.root/'alias')
        with self.assertRaises(RuntimeError): module.scan_state(self.fd)
    def test_unknown_format_refused(self):
        (self.root/'bad').write_bytes(b'not-a-private-print')
        with self.assertRaises(RuntimeError): module.scan_state(self.fd)
    def test_bounded_depth_and_empty_directory_count(self):
        path=self.root
        for _ in range(10): path=path/'nested'; path.mkdir()
        with self.assertRaises(RuntimeError): module.scan_state(self.fd)
    def test_too_many_empty_directories_refused(self):
        for index in range(module.MAX_ENTRIES+1): (self.root/str(index)).mkdir()
        with self.assertRaises(RuntimeError): module.scan_state(self.fd)
    def test_owner_and_modes_normalized_for_only_private_state(self):
        directory=self.root/'sub'; directory.mkdir(); path=directory/'finger';path.write_bytes(b'FP3synthetic-fixture')
        module.scan_state(self.fd,(os.getuid(),os.getgid()))
        self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE(directory.stat().st_mode),0o700)
    def test_cleanup_refuses_symlink_and_preserves_external_file(self):
        with tempfile.TemporaryDirectory() as other:
            target=Path(other)/'preserve';target.write_text('preserve')
            (self.root/'link').symlink_to(target)
            with self.assertRaises(RuntimeError): module.remove_state(self.fd)
            self.assertEqual(target.read_text(),'preserve')
    def test_frozen_state_checks_template_and_runtime_pins(self):
        self.template(); snapshot=module.scan_state(self.fd)
        manifest=json.loads(json.dumps(module.snapshot_manifest(snapshot)))
        fake=mock.Mock();fake.private_bytes.return_value=json.dumps(manifest).encode()
        self.assertEqual(module.frozen_state(fake,self.fd,self.fd,os.getuid()),snapshot)
        with mock.patch.object(module,'CHILD_SHA256','different'),self.assertRaises(RuntimeError):
            module.frozen_state(fake,self.fd,self.fd,os.getuid())
    def test_exclusive_manifest_cannot_overwrite(self):
        state=self.root/'state';state.mkdir();(state/'finger').write_bytes(b'FP3synthetic-fixture')
        child=os.open(state,os.O_RDONLY|os.O_DIRECTORY)
        try:
            module.persist(self.fd,child,os.getuid(),os.getgid())
            original=(self.root/'series.json').read_bytes()
            with self.assertRaises(FileExistsError):
                module.persist(self.fd,child,os.getuid(),os.getgid())
            self.assertEqual((self.root/'series.json').read_bytes(),original)
        finally:
            os.close(child)



class RelayTests(unittest.TestCase):
    def run_report(self, payload, status=0, limit=3, pause=0.02):
        # Use a real subprocess pipe/selector, the same path as hardware mode.
        # This child only writes synthetic fixed tags; no library, USB or bus.
        code = ("import os,sys,time; data=bytes.fromhex(sys.argv[1]); "
                "os.write(1,data[:5]); time.sleep(float(sys.argv[3])); "
                "os.write(1,data[5:]); sys.exit(int(sys.argv[2]))")
        child = subprocess.Popen([sys.executable, '-I', '-B', '-c', code,
                                  payload.hex(), str(status), str(pause)],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                return module.relay(child, limit)
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=2)
            child.stdout.close()

    def test_real_pipe_fragmented_detection_report_completes(self):
        self.assertEqual(self.run_report(b'READY\nDEVICE_FOUND\nCLOSED\nRESULT DETECTED\n'), 'DETECTED')

    def test_real_pipe_comparison_results_require_close(self):
        for result in ('MATCH', 'NO_MATCH'):
            with self.subTest(result=result):
                self.assertEqual(self.run_report(('CLOSED\nRESULT '+result+'\n').encode()), result)
                with self.assertRaises(RuntimeError):
                    self.run_report(('RESULT '+result+'\n').encode())

    def test_real_pipe_failures_are_inconclusive(self):
        for payload, status in ((b'FAIL STARTUP\n', 0),
                                (b'CLOSED\nRESULT DETECTED\n', 1),
                                (b'CLOSED\nRESULT DETECTED', 0),
                                (b'CLOSED\nRESULT DETECTED\nRESULT DETECTED\n', 0),
                                (b'FAIL OBSERVER\nCLOSED\nRESULT NO_MATCH\n', 0)):
            with self.subTest(payload=payload, status=status), self.assertRaises(RuntimeError):
                self.run_report(payload, status)

    def test_real_pipe_unknown_output_is_not_echoed(self):
        with self.assertRaisesRegex(RuntimeError, 'raw diagnostics hidden'):
            self.run_report(b'private-unexpected-message\n')

    def test_real_pipe_deadline_is_inconclusive(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            self.run_report(b'READY\n', limit=0.05, pause=1)


class SandboxTests(unittest.TestCase):
    def command(self, mode='smoke', smoke=True, usb=None):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);(folder/'session.json').write_text(json.dumps({'mode':mode}))
            return module.sandbox(folder,Path('/private/state'),99 if usb else None,usb,smoke)
    def test_smoke_has_no_host_bus_usb_sysfs_or_usr_tree(self):
        command=self.command(); self.assertIn('--unshare-all',command);self.assertNotIn('--dev-bind',command)
        self.assertNotIn('--cap-add',command)
        for forbidden in ('/sys','/run/dbus/system_bus_socket','/home','/lib','/lib64'):
            self.assertNotIn(forbidden,command)
        # /usr is now a chmod target in the synthetic tree, never a host bind.
        sources={command[i+1] for i,c in enumerate(command)
                 if c in {'--bind','--ro-bind','--dev-bind'}}
        self.assertNotIn('/usr',sources)
    def test_hardware_binds_only_open_node_fd(self):
        command=self.command('detect',False,'/dev/bus/usb/001/002')
        at=command.index('--dev-bind');self.assertEqual(command[at+1:at+3],['/proc/self/fd/99','/dev/bus/usb/001/002'])
        self.assertNotIn('/dev/bus/usb',command);self.assertNotIn('--unshare-user',command)
        self.assertEqual([command[i+1] for i,c in enumerate(command) if c=='--cap-add'],['CAP_SETUID','CAP_SETGID','CAP_KILL'])
        at=command.index('/sys')
        self.assertEqual(command[at-2],'--ro-bind')
        self.assertEqual(Path(command[at-1]).name,'sys')
        self.assertNotEqual(command[at-1],'/sys')
    def test_verify_state_is_readonly(self):
        command=self.command('verify',False,'/dev/bus/usb/001/002'); at=command.index('/private/state')
        self.assertEqual(command[at-1],'--ro-bind')
    def test_polkit_can_traverse_only_synthetic_runtime_directories(self):
        expected={'/nix','/etc','/etc/polkit-1','/etc/polkit-1/rules.d',
                  '/usr','/usr/share','/usr/share/polkit-1',
                  '/usr/share/polkit-1/actions','/usr/share/polkit-1/rules.d','/empty'}
        for mode,smoke,usb in [('smoke',True,None),('detect',False,'/dev/bus/usb/001/002')]:
            command=self.command(mode,smoke,usb)
            changes={command[i+2]:command[i+1] for i,c in enumerate(command) if c=='--chmod'}
            self.assertEqual(changes,{path:'0755' for path in expected})
            # chmod must never reach a bind-mounted host asset or private state.
            mounted={command[i+2] for i,c in enumerate(command)
                     if c in {'--bind','--ro-bind','--dev-bind'}}
            self.assertFalse(set(changes) & mounted)
            self.assertNotIn('/experiment',changes)
            self.assertNotIn('/state',changes)
    def test_plan_never_reads_usb_or_launches_daemon(self):
        with mock.patch.object(module,'select_usb') as usb, mock.patch.object(module.subprocess,'Popen') as popen,contextlib.redirect_stdout(io.StringIO()):
            module.plan()
        usb.assert_not_called();popen.assert_not_called()


if __name__=='__main__':
    unittest.main()
