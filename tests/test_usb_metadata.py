"""Synthetic USB inventory boundary tests, without native code or host devices."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('usb_metadata',ROOT/'scripts/helpers/usb-metadata.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def descriptors():
    value=bytearray(18);value[:2]=b'\x12\x01';value[8:12]=b'\xc6\x27\xa4\x55'
    return bytes(value)


class MetadataTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)/'sys';self.node='/dev/bus/usb/003/003';self.data=descriptors()
        module.create(self.root,self.node,self.data)

    def test_only_canonical_selected_inventory_exists(self):
        module.check(self.root,self.node,self.data)
        files=module.files(self.node,self.data)
        self.assertIn(b'MINOR=258\n',files['devices/selected/reader/uevent'])
        self.assertNotIn('devices/selected/reader/speed',files)
        self.assertNotIn('devices/selected/reader/serial',files)

    def test_other_identity_or_unrepresentable_bus_refused(self):
        for node,data in [('/dev/sda',self.data),('/dev/bus/usb/256/003',self.data),
                          ('/dev/bus/usb/003/128',self.data),(None,self.data),
                          (self.node,b'\0'*18),(self.node,self.data[:-1])]:
            with self.subTest(node=node),self.assertRaises(RuntimeError):module.files(node,data)

    def test_extra_device_or_metadata_entry_refused(self):
        for name in ('devices/other','devices/selected/reader/serial'):
            entry=self.root/name;entry.mkdir()
            with self.assertRaises(RuntimeError):module.check(self.root,self.node,self.data)
            entry.rmdir()

    def test_changed_bus_descriptor_and_missing_entry_refused(self):
        for name in ('busnum','descriptors'):
            path=self.root/'devices/selected/reader'/name;data=path.read_bytes()
            path.chmod(0o600);path.write_bytes(b'changed');path.chmod(0o444)
            with self.assertRaises(RuntimeError):module.check(self.root,self.node,self.data)
            path.chmod(0o600);path.write_bytes(data);path.chmod(0o444)
        (self.root/'devices/selected/reader/devnum').unlink()
        with self.assertRaises(RuntimeError):module.check(self.root,self.node,self.data)

    def test_link_cannot_escape_into_host_paths(self):
        for name in module.LINKS:
            path=self.root/name;path.unlink();path.symlink_to('/etc/passwd')
            with self.assertRaises(RuntimeError):module.check(self.root,self.node,self.data)
            path.unlink();path.symlink_to(module.LINKS[name])

    def test_writable_file_directory_or_hardlink_refused(self):
        for path,mode in ((self.root,0o700),(self.root/'devices',0o777),
                          (self.root/'devices/selected/reader/dev',0o644)):
            original=path.stat().st_mode&0o777;path.chmod(mode)
            with self.assertRaises(RuntimeError):module.check(self.root,self.node,self.data)
            path.chmod(original)
        os.link(self.root/'devices/selected/reader/dev',self.root.parent/'linked')
        with self.assertRaises(RuntimeError):module.check(self.root,self.node,self.data)


if __name__=='__main__':unittest.main()
