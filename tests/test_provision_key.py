"""Synthetic provisioning checks. No device is opened and no key is written."""
import contextlib
import importlib.util
import io
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "scripts/08-provision-key.py"
spec = importlib.util.spec_from_file_location("key_preparation", path)
script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script)


def key_reply(matched):
    value = script.probe.EXPECTED_HASH if matched else b"\x17" * 32
    return b"\x00" + struct.pack("<II", script.probe.PSK_FLAGS, 32) + value


class FakeTransport:
    def __init__(self, states=(False, True), firmware=script.EXPECTED_FIRMWARE):
        self.states = iter(states)
        self.firmware = firmware
        self.commands = []
        self.writes = 0

    def query(self, command):
        self.commands.append(command)
        if command == 0xA8:
            return self.firmware.encode()
        return key_reply(next(self.states))

    def write_known_key(self):
        self.writes += 1


class FakeUSB:
    def __init__(self, status=b"\x00", short_at=None):
        self.packets = []
        self.reply = iter([script.probe.encode_frame(0xB0, b"\xe0\x01"),
                           script.probe.encode_frame(0xE0, status)])
        self.short_at = short_at

    def write(self, endpoint, data, timeout):
        self.packets.append(bytes(data))
        return len(data) - 1 if len(self.packets) == self.short_at else len(data)

    def read(self, endpoint, size, timeout):
        return next(self.reply)


class ProvisionTests(unittest.TestCase):
    def test_default_plan_never_opens_usb(self):
        with patch.object(script.sys, "argv", ["08-provision-key.py"]), \
                patch.object(script, "run") as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(script.main(), 0)
        run.assert_not_called()

    def test_existing_match_skips_confirmation_and_write(self):
        device = FakeTransport(states=(True,))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(script.provision(device, confirm=lambda _: self.fail("Unexpected confirmation")), 0)
        self.assertEqual(device.writes, 0)

    def test_wrong_firmware_stops_before_key_or_write(self):
        device = FakeTransport(firmware="GF3268_RTSEC_APP_10041")
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(script.probe.ProtocolError):
            script.provision(device, confirm=lambda _: script.CONFIRMATION)
        self.assertEqual(device.commands, [0xA8])
        self.assertEqual(device.writes, 0)

    def test_cancelled_confirmation_never_writes(self):
        device = FakeTransport()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(script.provision(device, confirm=lambda _: "yes"), 130)
        self.assertEqual(device.writes, 0)

    def test_write_and_private_postcheck(self):
        device = FakeTransport()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(script.provision(device, confirm=lambda _: script.CONFIRMATION), 0)
        self.assertEqual(device.writes, 1)
        self.assertEqual(device.commands, [0xA8, 0xE4, 0xE4])
        self.assertNotIn((b"\x17" * 32).hex(), output.getvalue())
        self.assertNotIn(script.probe.EXPECTED_HASH.hex(), output.getvalue())

    def test_postwrite_mismatch_is_not_retried(self):
        device = FakeTransport(states=(False, False))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(script.provision(device, confirm=lambda _: script.CONFIRMATION), 3)
        self.assertEqual(device.writes, 1)

    def test_ambiguous_write_failure_has_no_postcheck_or_retry(self):
        device = FakeTransport()
        def failed_write():
            device.writes += 1
            raise TimeoutError("synthetic timeout")
        device.write_known_key = failed_write
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaises(TimeoutError):
            script.provision(device, confirm=lambda _: script.CONFIRMATION)
        self.assertEqual(device.writes, 1)
        self.assertEqual(device.commands, [0xA8, 0xE4])

    def test_fixed_payload_and_two_packets_match_reference(self):
        usb = FakeUSB()
        transport = script.ProvisionTransport(usb, 0x82, 0x01)
        transport.write_known_key()
        self.assertEqual([len(p) for p in usb.packets], [64, 64])
        wire = b"".join(usb.packets)
        size = int.from_bytes(wire[1:3], "little") + 4
        command, payload = script.probe.decode_message(wire[:size])
        self.assertEqual(command, 0xE0)
        self.assertEqual(payload[:8], struct.pack("<II", 0xBB010003, 96))
        self.assertEqual(payload[8:], script.BLOB)
        self.assertEqual(script.hashlib.sha256(payload).hexdigest(),
                         "eeccaf0a3d9516735ad56628495d1206a4a7f1e4938381818bcc39a2bd6d47cd")
        self.assertEqual(wire[size:], bytes(len(wire) - size))
        with self.assertRaises(script.probe.ProtocolError):
            transport.write_known_key()
        self.assertEqual(len(usb.packets), 2)

    def test_short_transfer_does_not_send_remaining_or_retry(self):
        for short_at in (1, 2):
            with self.subTest(short_at=short_at):
                usb = FakeUSB(short_at=short_at)
                transport = script.ProvisionTransport(usb, 0x82, 0x01)
                with self.assertRaises(script.probe.ProtocolError):
                    transport.write_known_key()
                with self.assertRaises(script.probe.ProtocolError):
                    transport.write_known_key()
                self.assertEqual(len(usb.packets), short_at)

    def test_bad_reply_prevents_success_and_second_write(self):
        transport = script.ProvisionTransport(FakeUSB(status=b"\x01"), 0x82, 0x01)
        with self.assertRaises(script.probe.ProtocolError):
            transport.write_known_key()
        with self.assertRaises(script.probe.ProtocolError):
            transport.write_known_key()

    def test_modified_blob_refused_before_transfer(self):
        usb = FakeUSB()
        transport = script.ProvisionTransport(usb, 0x82, 0x01)
        with patch.object(script, "BLOB", b"\x00" * 96), self.assertRaises(script.probe.ProtocolError):
            transport.write_known_key()
        self.assertEqual(usb.packets, [])

    def usb_run(self, owned):
        class Interface(list):
            bAlternateSetting = bInterfaceNumber = 0
            bInterfaceClass = 0xFF
        interface = Interface([SimpleNamespace(bEndpointAddress=value, bmAttributes=2)
                               for value in (0x82, 0x01)])
        device = SimpleNamespace(
            get_active_configuration=lambda: [interface],
            is_kernel_driver_active=lambda _: owned,
            read=lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError()),
            write=lambda endpoint, data, timeout: len(data))
        calls = []
        util = SimpleNamespace(ENDPOINT_TYPE_BULK=2, endpoint_type=lambda value: value,
                               claim_interface=lambda dev, n: calls.append("claim"),
                               release_interface=lambda dev, n: calls.append("release"),
                               dispose_resources=lambda dev: calls.append("dispose"))
        core = SimpleNamespace(find=lambda **kwargs: [device], USBTimeoutError=TimeoutError)
        usb = SimpleNamespace(core=core, util=util)
        with patch.dict(script.sys.modules, {"usb": usb, "usb.core": core, "usb.util": util}), \
                patch.object(script.sys.stdin, "isatty", return_value=True), \
                patch.object(script.probe, "pause"), \
                patch.object(script, "provision", side_effect=script.probe.ProtocolError("synthetic failure")), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(script.probe.ProtocolError):
            script.run()
        return calls

    def test_claimed_interface_is_released_on_later_failure(self):
        self.assertEqual(self.usb_run(owned=False), ["claim", "release", "dispose"])

    def test_kernel_owner_is_not_detached_or_claimed(self):
        self.assertEqual(self.usb_run(owned=True), ["dispose"])


if __name__ == "__main__":
    unittest.main()
