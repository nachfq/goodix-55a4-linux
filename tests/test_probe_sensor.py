"""Offline protocol tests. No PyUSB imports, source imports, or hardware access."""

import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "scripts/03-probe-sensor.py"
spec = importlib.util.spec_from_file_location("probe", path)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class FakeDevice:
    def __init__(self, reads=()):
        self.reads = iter(reads)
        self.writes = []
        self.read_count = 0

    def write(self, endpoint, packet, timeout):
        self.writes.append(packet)
        return len(packet)

    def read(self, endpoint, size, timeout):
        self.read_count += 1
        item = next(self.reads)
        if isinstance(item, Exception):
            raise item
        return item


class ProtocolTests(unittest.TestCase):
    def test_query_wire_bytes_match_reviewed_reference(self):
        vectors = {
            0x00: "a0 08 00 a8 00 05 00 00 00 00 00 88",
            0xA8: "a0 06 00 a6 a8 03 00 00 00 ff",
            0xE4: "a0 0c 00 ac e4 09 00 07 00 02 bb 00 00 00 00 f9",
        }
        for command, vector in vectors.items():
            with self.subTest(command=command):
                payload, checksum = probe.QUERIES[command]
                expected = bytes.fromhex(vector)
                self.assertEqual(probe.encode_frame(command, payload, checksum),
                                 expected + bytes(64 - len(expected)))

    def test_corrupt_and_truncated_packets_stop(self):
        valid = bytes.fromhex("a0 06 00 a6 b0 03 00 a8 01 4e")
        self.assertEqual(probe.decode_message(valid), (0xB0, b"\xa8\x01"))
        for packet in (b"", valid[:4], valid[:-1], valid + b"\x00",
                       b"\xb2" + valid[1:], valid[:3] + b"\x00" + valid[4:],
                       valid[:-1] + b"\x00"):
            with self.subTest(packet=packet):
                with self.assertRaises(probe.ProtocolError):
                    probe.decode_message(packet)

    def test_ack_accepts_config_flag_but_rejects_wrong_command(self):
        probe.check_ack(0xA8, b"\xa8\x01")
        probe.check_ack(0xA8, b"\xa8\x03")
        for payload in (b"", b"\xa8", b"\xe4\x01", b"\xa8\x00"):
            with self.assertRaises(probe.ProtocolError):
                probe.check_ack(0xA8, payload)

    def test_firmware_rejects_terminal_control_characters(self):
        self.assertEqual(probe.parse_firmware(b"GF3268_RTSEC_APP_10063\x00"),
                         "GF3268_RTSEC_APP_10063")
        for value in (b"", b"\x1b[31m", b"\xff", b"a" * 129):
            with self.assertRaises(probe.ProtocolError):
                probe.parse_firmware(value)

    def test_key_state_distinguishes_mismatch_and_malformed_reply(self):
        header = bytes.fromhex("00 07 00 02 bb 20 00 00 00")
        self.assertTrue(probe.parse_key_state(header + probe.EXPECTED_HASH))
        self.assertFalse(probe.parse_key_state(header + bytes(32)))
        for reply in (b"", b"\x01", header + bytes(31), header + bytes(33),
                      b"\x00" * 9 + probe.EXPECTED_HASH):
            with self.assertRaises(probe.ProtocolError):
                probe.parse_key_state(reply)

    def test_transport_never_sends_write_or_capture_commands(self):
        device = FakeDevice()
        transport = probe.QueryTransport(device, 0x82, 0x01)
        for command in (0xE0, 0xF0, 0xA4, 0x20, 0xA2, 0x90):
            with self.assertRaises(probe.ProtocolError):
                transport.send(command)
        self.assertEqual(device.writes, [])

    def test_fragmented_ack_and_padded_coalesced_reply(self):
        ack = probe.encode_frame(0xB0, b"\xa8\x01")
        reply = probe.encode_frame(0xA8, b"GF3268_RTSEC_APP_10063\x00")
        device = FakeDevice([ack[:2], ack[2:] + reply])
        transport = probe.QueryTransport(device, 0x82, 0x01)
        self.assertEqual(probe.parse_firmware(transport.query(0xA8)),
                         "GF3268_RTSEC_APP_10063")
        self.assertEqual(device.read_count, 2)

    def test_reject_wrong_reply_and_unbounded_input(self):
        ack = probe.encode_frame(0xB0, b"\xa8\x01")
        reply = probe.encode_frame(0xE4, b"wrong reply")
        with self.assertRaises(probe.ProtocolError):
            probe.QueryTransport(FakeDevice([ack + reply]), 0x82, 0x01).query(0xA8)
        device = FakeDevice([b"\xa0\x00\x01\xa1"] + [b"\x01"] * 7)
        with self.assertRaises(probe.ProtocolError):
            probe.QueryTransport(device, 0x82, 0x01).receive()
        self.assertEqual(device.read_count, 8)

    def test_packet_completing_on_last_allowed_read_is_accepted(self):
        packet = bytes.fromhex("a0 06 00 a6 b0 03 00 a8 01 4e")
        device = FakeDevice([packet[i:i + 1] for i in range(7)] + [packet[7:]])
        self.assertEqual(probe.QueryTransport(device, 0x82, 0x01).receive(),
                         (0xB0, b"\xa8\x01"))
        self.assertEqual(device.read_count, 8)

    def test_nop_silence_is_optional_but_partial_reply_is_not(self):
        class FakeTimeout(Exception):
            pass

        silent = FakeDevice([FakeTimeout()])
        self.assertFalse(probe.QueryTransport(silent, 0x82, 0x01).nop(FakeTimeout))
        partial = FakeDevice([b"\xa0\x06", FakeTimeout()])
        with self.assertRaisesRegex(probe.ProtocolError, "truncated"):
            probe.QueryTransport(partial, 0x82, 0x01).nop(FakeTimeout)
        ack = probe.encode_frame(0xB0, b"\x00\x01")
        self.assertTrue(probe.QueryTransport(FakeDevice([ack]), 0x82, 0x01).nop(FakeTimeout))


if __name__ == "__main__":
    unittest.main()
