"""Offline deployment guards; transactions run only as root in a user namespace.

Every destination and integration pin is synthetic. No systemctl, native binary,
Nix acquisition, service, bus, USB, or biometric operation is allowed here.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / 'scripts/helpers/host-deployment.py'
spec = importlib.util.spec_from_file_location('host_deployment', CONTROLLER)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def namespace_root():
    """Never permit transaction tests as host root, even in an ordinary container."""
    try:
        rows = [line.split() for line in Path('/proc/self/uid_map').read_text().splitlines()]
        return os.geteuid() == 0 and len(rows) == 1 and rows[0][0] == '0' and int(rows[0][1]) > 0 and rows[0][2] == '1'
    except (OSError, ValueError, IndexError):
        return False


class FakeSystemd:
    def __init__(self, active=False, activated_during_mask=False, mask_state='masked', mask_fragment=None):
        self.events = []
        self.active = active
        self.activated_during_mask = activated_during_mask
        self.mask_state = mask_state
        self.mask_fragment = mask_fragment

    def check(self, removing=False):
        self.events.append(('check', removing))
        if self.active:
            raise RuntimeError('Synthetic active service')

    def reload(self):
        self.events.append(('reload', os.path.lexists(module.MASK)))

    def command(self, *args):
        self.events.append(('command', args))
        if len(args) != 4 or args[:2] != ('show', 'fprintd.service') or args[3] != '--value':
            raise AssertionError('Unexpected service request')
        replies = {'ActiveState': 'active' if self.activated_during_mask else 'inactive',
                   'LoadState': self.mask_state,
                   'FragmentPath': self.mask_fragment or str(module.MASK)}
        return replies[args[2].split('=', 1)[1]]


class DeploymentFixture:
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='fingerprint-deployment-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.host = self.root / 'host'
        self.host.mkdir()
        for name in ('opt', 'etc/systemd/system', 'nix/gcroots', 'var/lib', 'run/systemd/system'):
            (self.host / name).mkdir(parents=True, exist_ok=True)
        self.source = self.root / 'bundle'
        self.source.mkdir()
        self.paths = {
            'PREFIX': self.host / 'opt/thinkpad-fingerprint',
            'DROPIN': self.host / 'etc/systemd/system/fprintd.service.d/90-thinkpad-fingerprint.conf',
            'GCROOTS': self.host / 'nix/gcroots/thinkpad-fingerprint',
            'STATE': self.host / 'var/lib/thinkpad-fingerprint',
            'MASK': self.host / 'run/systemd/system/fprintd.service',
        }
        integration = self.root / 'stock-service'
        integration.write_bytes(b'Synthetic integration file; never a real service.\n')
        self.roots = {'/nix/store/' + 'a' * 32 + '-synthetic-runtime': 'sha256:' + '0' * 52}
        self.payload = {
            'fprintd': b'Synthetic daemon; not executable code.\n',
            'lib/libfprint-2.so.2.0.0': b'Synthetic library.\n',
            'lib/libpolkit-gobject-1.so.0': b'Synthetic Polkit library.\n',
        }
        self.patches = contextlib.ExitStack()
        self.addCleanup(self.patches.close)
        self.patches.enter_context(mock.patch.multiple(module, **self.paths))
        self.patches.enter_context(mock.patch.object(module, 'HOST_PINS', {str(integration): module.digest(integration.read_bytes())}))
        self.patches.enter_context(mock.patch.object(module, 'NIX_ROOTS', list(self.roots)))
        self.patches.enter_context(mock.patch.object(module, 'PAYLOAD_PINS', {name: module.digest(data) for name, data in self.payload.items()}))
        self.nix_hash = self.patches.enter_context(mock.patch.object(module, 'nix_hash', side_effect=lambda target: self.roots[target]))
        self.patches.enter_context(mock.patch.object(module, 'private_sessions', return_value=None))
        self.patches.enter_context(mock.patch.object(module.subprocess, 'run', side_effect=AssertionError('External commands forbidden in deployment tests')))
        self.make_bundle()

    def make_bundle(self):
        for name in module.DIRS:
            (self.source / name).mkdir(exist_ok=True)
        self.data = dict(self.payload, **{
            'manage.py': CONTROLLER.read_bytes(),
            'fprintd.conf': module.CONFIG,
            'fprintd-dropin.conf': module.unit(),
            'NOTICE': b'Synthetic attribution fixture.\n',
            'COPYING': b'Synthetic license fixture.\n',
        })
        for name, value in self.data.items():
            (self.source / name).write_bytes(value)
        self.manifest = {'format': 1, 'files': {name: module.digest(data) for name, data in self.data.items()},
                         'roots': self.roots, 'host_pins': module.HOST_PINS}
        self.save_manifest()

    def save_manifest(self):
        (self.source / 'manifest.json').write_text(json.dumps(self.manifest))

    def tree(self):
        return {path.relative_to(self.host).as_posix():
                ('link', os.readlink(path)) if path.is_symlink() else
                ('file', path.read_bytes(), stat.S_IMODE(path.stat().st_mode)) if path.is_file() else
                ('directory', stat.S_IMODE(path.stat().st_mode))
                for path in self.host.rglob('*')}

    def assert_bundle_refused(self):
        with self.assertRaises((RuntimeError, OSError, ValueError)):
            module.bundle(self.source)


class FixtureTests(DeploymentFixture, unittest.TestCase):
    def test_exact_synthetic_bundle_passes_without_runtime_execution(self):
        manifest, data = module.bundle(self.source)
        self.assertEqual(manifest, self.manifest)
        self.assertEqual(data, self.data)
        self.nix_hash.assert_not_called()

    def test_manifest_refuses_missing_or_extra_artifacts_and_roots(self):
        for field, key in (('files', 'unexpected'), ('roots', '/nix/store/unreviewed')):
            with self.subTest(field=field):
                self.manifest[field][key] = 'sha256:' + '0' * 52 if field == 'roots' else '0' * 64
                self.save_manifest()
                self.assert_bundle_refused()
                del self.manifest[field][key]
        del self.manifest['files']['NOTICE']
        self.save_manifest()
        self.assert_bundle_refused()

    def test_manifest_rehash_cannot_authorize_changed_reviewed_payload(self):
        path = self.source / 'fprintd'
        path.write_bytes(b'Changed synthetic payload.\n')
        self.manifest['files']['fprintd'] = module.digest(path.read_bytes())
        self.save_manifest()
        self.assert_bundle_refused()

    def test_config_and_manager_rehash_cannot_authorize_controller_changes(self):
        for name in ('fprintd.conf', 'fprintd-dropin.conf', 'manage.py'):
            with self.subTest(name=name):
                (self.source / name).write_bytes(self.data[name] + b'changed\n')
                self.manifest['files'][name] = module.digest((self.source / name).read_bytes())
                self.save_manifest()
                self.assert_bundle_refused()
                (self.source / name).write_bytes(self.data[name])
                self.manifest['files'][name] = module.digest(self.data[name])

    def test_bundle_refuses_symlink_hardlink_and_extra_entry(self):
        path = self.source / 'NOTICE'
        path.unlink()
        path.symlink_to(self.source / 'COPYING')
        self.assert_bundle_refused()
        path.unlink()
        os.link(self.source / 'COPYING', path)
        self.assert_bundle_refused()
        path.unlink()
        path.write_bytes(self.data['NOTICE'])
        (self.source / 'unexpected').write_bytes(b'Foreign fixture.\n')
        self.assert_bundle_refused()

    def test_invalid_nix_content_pin_refused(self):
        self.roots[next(iter(self.roots))] = 'unreviewed'
        self.save_manifest()
        self.assert_bundle_refused()

    def test_default_plan_has_no_service_or_destination_mutation(self):
        before = self.tree()
        with mock.patch.object(sys, 'argv', ['manage.py']), mock.patch.object(module, 'install') as install, \
                mock.patch.object(module, 'remove') as remove, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(module.main(), 0)
        install.assert_not_called()
        remove.assert_not_called()
        self.nix_hash.assert_not_called()
        self.assertEqual(before, self.tree())
        self.assertIn('Preparation only', output.getvalue())

    def test_regular_user_install_and_remove_refused_before_input_reads(self):
        with mock.patch.object(module.os, 'geteuid', return_value=1000), mock.patch.object(module, 'bundle') as bundle:
            for action in (lambda: module.install(self.source), module.remove):
                with self.assertRaisesRegex(RuntimeError, 'sudo'):
                    action()
        bundle.assert_not_called()

    def test_noninteractive_mutation_refused_before_controller_actions(self):
        for args in (['--install', str(self.source)], ['--remove'], ['--remove', '--purge-state']):
            with self.subTest(args=args), mock.patch.object(sys, 'argv', ['manage.py', *args]), \
                    mock.patch.object(sys.stdin, 'isatty', return_value=False), \
                    mock.patch.object(module, 'install') as install, mock.patch.object(module, 'remove') as remove, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(module.main(), 1)
                install.assert_not_called()
                remove.assert_not_called()

    def test_confirmation_mismatch_never_dispatches_mutation(self):
        for args in (['--install', str(self.source)], ['--remove'], ['--remove', '--purge-state']):
            with self.subTest(args=args), contextlib.redirect_stdout(io.StringIO()), \
                    mock.patch.object(sys, 'argv', ['manage.py', *args]), \
                    mock.patch.object(sys.stdin, 'isatty', return_value=True), \
                    mock.patch.object(sys.stdout, 'isatty', return_value=True), \
                    mock.patch('builtins.input', return_value='wrong confirmation'), \
                    mock.patch.object(module, 'install') as install, mock.patch.object(module, 'remove') as remove:
                self.assertEqual(module.main(), 0)
                install.assert_not_called()
                remove.assert_not_called()

    def test_purge_requires_remove_action(self):
        with mock.patch.object(sys, 'argv', ['manage.py', '--purge-state']), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
            module.main()
        self.assertEqual(stopped.exception.code, 2)


class UnitTests(unittest.TestCase):
    def test_service_keeps_separate_systemd_state_directory_environment(self):
        unit = module.unit().decode()
        self.assertIn('StateDirectory=\nStateDirectory=thinkpad-fingerprint/fprint\n', unit)
        self.assertIn('StateDirectoryMode=0700\nUMask=0077\n', unit)
        unset = next(line for line in unit.splitlines() if line.startswith('UnsetEnvironment='))
        self.assertNotIn('STATE_DIRECTORY', unset.split('=', 1)[1].split())
        self.assertIn('ReadWritePaths=\nDeviceAllow=\nDeviceAllow=char-usb_device rw\n', unit)
        self.assertIn('StandardOutput=null\nStandardError=null\nLimitCORE=0\n', unit)
        self.assertIn('FP_DRIVERS_WHITELIST=goodixtls55x4', unit)
        self.assertIn('--inhibit-cache --library-path', unit)
        self.assertIn('--preload /opt/thinkpad-fingerprint/lib/libfprint-2.so.2.0.0', unit)

    def test_reviewed_runtime_pin_inventory_is_explicit(self):
        self.assertEqual(len(module.NIX_ROOTS), 13)
        self.assertEqual(len(set(module.NIX_ROOTS)), 13)
        self.assertEqual(set(module.PAYLOAD_PINS), {'fprintd', 'lib/libfprint-2.so.2.0.0', 'lib/libpolkit-gobject-1.so.0'})
        for value in (*module.PAYLOAD_PINS.values(), *module.HOST_PINS.values()):
            self.assertRegex(value, r'^[0-9a-f]{64}$')

    def test_systemd_check_refuses_active_unit_or_foreign_fragment_and_overrides(self):
        expected = {'ActiveState': 'inactive', 'SubState': 'dead',
                    'FragmentPath': '/usr/lib/systemd/system/fprintd.service', 'DropInPaths': ''}
        systemd = module.Systemd()

        def reply(*args):
            return expected[args[2].split('=', 1)[1]]

        with mock.patch.object(systemd, 'command', side_effect=reply):
            systemd.check()
            for property_name, changed in (('ActiveState', 'active'), ('SubState', 'running'),
                                           ('FragmentPath', '/foreign.service'), ('DropInPaths', '/foreign.conf')):
                with self.subTest(property=property_name):
                    original = expected[property_name]
                    expected[property_name] = changed
                    with self.assertRaises(RuntimeError):
                        systemd.check()
                    expected[property_name] = original
            expected['DropInPaths'] = str(module.DROPIN)
            systemd.check(removing=True)


@unittest.skipUnless(namespace_root(), 'Mutation tests require root in an isolated unprivileged user namespace; host root is refused')
class TransactionTests(DeploymentFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        # Namespace runner supplies TMPDIR=/fixture on its fresh root filesystem.
        # Production path traversal, ownership and mode guards remain intact.
        self.systemd = FakeSystemd()
        self.output = self.patches.enter_context(contextlib.redirect_stdout(io.StringIO()))

    def install(self):
        module.install(self.source, self.systemd)

    def add_state(self):
        directory = module.STATE / 'fprint/test-user'
        directory.mkdir(mode=0o700)
        path = directory / 'synthetic-template'
        path.write_bytes(b'Harmless state fixture; not biometric data.\n')
        path.chmod(0o600)
        return path

    def assert_refused_unchanged(self, operation):
        before = self.tree()
        with self.assertRaises((RuntimeError, OSError, ValueError)):
            operation()
        self.assertEqual(before, self.tree())

    def test_install_remove_preserve_state_and_reinstall_explicit_purge(self):
        self.install()
        manifest, _ = module.bundle(module.PREFIX, installed=True)
        module.roots_check(module.GCROOTS, manifest)
        self.assertEqual(stat.S_IMODE(module.STATE.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((module.STATE / 'fprint').stat().st_mode), 0o700)
        self.assertFalse(os.path.lexists(module.MASK))
        self.assertEqual(self.systemd.events[0], ('check', False))
        self.assertEqual([event for event in self.systemd.events if event[0] == 'reload'], [('reload', True), ('reload', False)])
        path = self.add_state()
        state = path.read_bytes()
        module.remove(systemd=self.systemd)
        self.assertEqual(path.read_bytes(), state)
        for name in ('PREFIX', 'DROPIN', 'GCROOTS'):
            self.assertFalse(os.path.lexists(getattr(module, name)))
        self.install()
        self.assertEqual(path.read_bytes(), state)
        module.remove(purge=True, systemd=self.systemd)
        self.assertFalse(module.STATE.exists())
        self.assertFalse(os.path.lexists(module.MASK))

    def test_existing_foreign_destination_is_never_overwritten(self):
        for name in ('PREFIX', 'GCROOTS', 'DROPIN'):
            with self.subTest(name=name):
                path = getattr(module, name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'Foreign fixture.\n')
                self.assert_refused_unchanged(self.install)
                path.unlink()

    def test_symlink_destination_refused_and_external_target_preserved(self):
        target = self.host / 'external'
        target.mkdir()
        (target / 'preserve').write_bytes(b'Keep fixture.\n')
        for name in ('PREFIX', 'GCROOTS', 'STATE'):
            with self.subTest(name=name):
                path = getattr(module, name)
                path.symlink_to(target, target_is_directory=True)
                self.assert_refused_unchanged(self.install)
                path.unlink()

    def test_symlink_destination_ancestor_refused(self):
        parent = module.PREFIX.parent
        parent.rmdir()
        target = self.host / 'foreign-opt'
        target.mkdir()
        parent.symlink_to(target, target_is_directory=True)
        self.assert_refused_unchanged(self.install)

    def test_untrusted_destination_directory_refused(self):
        module.PREFIX.parent.chmod(0o777)
        self.assert_refused_unchanged(self.install)

    def test_tampered_source_and_cached_dependency_refused_before_mutation(self):
        (self.source / 'fprintd').write_bytes(b'Tampered.\n')
        self.assert_refused_unchanged(self.install)
        (self.source / 'fprintd').write_bytes(self.data['fprintd'])
        self.nix_hash.side_effect = lambda target: 'sha256:' + '1' * 52
        self.assert_refused_unchanged(self.install)

    def test_changed_stock_integration_pin_refused(self):
        path = Path(next(iter(module.HOST_PINS)))
        path.write_bytes(b'Changed synthetic stock integration.\n')
        self.assert_refused_unchanged(self.install)

    def test_preexisting_mask_and_active_unit_refused(self):
        module.MASK.symlink_to('/dev/null')
        self.assert_refused_unchanged(self.install)
        module.MASK.unlink()
        self.systemd.active = True
        self.assert_refused_unchanged(self.install)

    def test_activation_during_transaction_refused_and_temporary_mask_removed(self):
        self.systemd.activated_during_mask = True
        self.assert_refused_unchanged(self.install)
        self.assertEqual([event for event in self.systemd.events if event[0] == 'reload'], [('reload', True), ('reload', False)])

    def test_ineffective_or_foreign_mask_refused_before_install_and_remove(self):
        # A higher-priority /etc unit can appear only after daemon-reload even
        # though the initial check saw the cached vendor unit and no overrides.
        foreign = str(self.host / 'etc/systemd/system/fprintd.service')
        for removing in (False, True):
            if removing:
                self.install()
            for load_state in ('loaded', 'masked'):
                with self.subTest(removing=removing, load_state=load_state):
                    self.systemd.mask_state = load_state
                    self.systemd.mask_fragment = foreign
                    self.assert_refused_unchanged(
                        (lambda: module.remove(systemd=self.systemd)) if removing else self.install)
                    self.assertFalse(os.path.lexists(module.MASK))
            self.systemd.mask_state = 'masked'
            self.systemd.mask_fragment = None

    def test_foreign_private_state_refused_on_install(self):
        module.STATE.mkdir(mode=0o700)
        (module.STATE / 'foreign').write_bytes(b'Keep foreign state.\n')
        self.assert_refused_unchanged(self.install)

    def test_tampered_installed_payload_and_foreign_gc_root_refused(self):
        self.install()
        path = module.PREFIX / 'fprintd'
        original = path.read_bytes()
        path.write_bytes(b'Tampered installed fixture.\n')
        self.assert_refused_unchanged(lambda: module.remove(systemd=self.systemd))
        path.write_bytes(original)
        gcroot = module.GCROOTS / Path(next(iter(self.roots))).name
        gcroot.unlink()
        gcroot.symlink_to('/nix/store/foreign-fixture')
        self.assert_refused_unchanged(lambda: module.remove(systemd=self.systemd))

    def test_foreign_dropin_sibling_refused_before_remove(self):
        self.install()
        (module.DROPIN.parent / 'foreign.conf').write_bytes(b'Foreign override.\n')
        self.assert_refused_unchanged(lambda: module.remove(systemd=self.systemd))

    def test_changed_state_refused_for_preserve_and_purge_removal(self):
        self.install()
        path = self.add_state()
        path.chmod(0o644)
        for purge in (False, True):
            with self.subTest(purge=purge):
                self.assert_refused_unchanged(lambda: module.remove(purge=purge, systemd=self.systemd))

    def test_state_symlink_hardlink_and_marker_refused_before_purge(self):
        self.install()
        path = self.add_state()
        link = path.parent / 'alias'
        link.symlink_to(path)
        self.assert_refused_unchanged(lambda: module.remove(purge=True, systemd=self.systemd))
        link.unlink()
        os.link(path, link)
        self.assert_refused_unchanged(lambda: module.remove(purge=True, systemd=self.systemd))
        link.unlink()
        (module.STATE / '.owner').write_bytes(b'Foreign owner fixture.\n')
        self.assert_refused_unchanged(lambda: module.remove(purge=True, systemd=self.systemd))

    def test_state_directory_mode_must_be_private(self):
        self.install()
        (module.STATE / 'fprint').chmod(0o755)
        self.assert_refused_unchanged(lambda: module.remove(purge=True, systemd=self.systemd))

    def test_write_failure_rolls_back_only_new_install_paths(self):
        original_write = module.write
        for name in ('fprintd', 'manifest.json', 'installation.json', 'dropin'):
            with self.subTest(name=name):
                before = self.tree()
                target = module.DROPIN if name == 'dropin' else module.PREFIX / name

                def fail_write(path, data, mode=0o644):
                    if Path(path) == target:
                        raise OSError('Synthetic injected write failure')
                    return original_write(path, data, mode)

                with mock.patch.object(module, 'write', side_effect=fail_write), self.assertRaisesRegex(OSError, 'Synthetic'):
                    self.install()
                self.assertEqual(before, self.tree())
                self.assertFalse(os.path.lexists(module.MASK))

    def test_write_failure_preserves_preexisting_owned_state(self):
        self.install()
        path = self.add_state()
        module.remove(systemd=self.systemd)
        before = self.tree()
        original_write = module.write

        def fail_write(target, data, mode=0o644):
            if Path(target) == module.PREFIX / 'installation.json':
                raise OSError('Synthetic injected write failure')
            return original_write(target, data, mode)

        with mock.patch.object(module, 'write', side_effect=fail_write), self.assertRaises(OSError):
            self.install()
        self.assertEqual(before, self.tree())
        self.assertTrue(path.exists())

    def test_fsync_failure_removes_partially_written_own_file_and_rolls_back(self):
        original_fsync = module.os.fsync
        targets = (module.PREFIX / 'fprintd', module.PREFIX / 'manifest.json',
                   module.STATE / '.owner', module.PREFIX / 'installation.json', module.DROPIN)
        for target in targets:
            with self.subTest(target=target.name):
                before = self.tree()

                def fail_fsync(descriptor):
                    if Path(os.readlink('/proc/self/fd/' + str(descriptor))) == target:
                        raise OSError('Synthetic fsync failure after file contents written')
                    return original_fsync(descriptor)

                with mock.patch.object(module.os, 'fsync', side_effect=fail_fsync), self.assertRaisesRegex(OSError, 'Synthetic'):
                    self.install()
                self.assertEqual(before, self.tree())
                self.assertFalse(os.path.lexists(module.MASK))


if __name__ == '__main__':
    unittest.main()
