#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 nachfq
# Framing and query payloads adapted from goodix-fp-linux-dev/goodix-fp-dump
# at cc43bb3b3154a0bccc0412ae024013c7e1923139 (goodix.py, driver_55x4.py).
# See LICENSES/goodix-fp-dump-MIT.txt for the original MIT notice.
"""Lesson 3: inspect the plan first; USB access requires --run and Enter."""

import argparse
import ctypes.util
import importlib.util
import struct
import sys

VID, PID = 0x27C6, 0x55A4
PSK_FLAGS = 0xBB020007  # Read selector, not the provisioning write selector.
EXPECTED_HASH = bytes.fromhex(
    "81b8ff490612022a121a9449ee3aad2792f32b9f3141182cd01019945ee50361"
)
# These are the only vendor commands the transport can send.
QUERIES = {
    0x00: (b"\x00" * 4, False),                 # NOP, checksum marker 0x88.
    0xA8: (b"\x00\x00", True),                # Firmware version.
    0xE4: (struct.pack("<II", PSK_FLAGS, 0), True),  # Expected key-state hash.
}


class ProtocolError(Exception):
    """Stop on unexpected data; never repair sensor state automatically."""


def encode_frame(command, payload, checksum=True):
    """A protocol message inside an a0 transport packet, padded to 64 bytes."""
    message = bytes([command]) + struct.pack("<H", len(payload) + 1) + payload
    message += bytes([(0xAA - sum(message)) & 0xFF if checksum else 0x88])
    header = b"\xa0" + struct.pack("<H", len(message))
    packet = header + bytes([sum(header) & 0xFF]) + message
    return packet + bytes((-len(packet)) % 64)


def decode_message(packet):
    """Validate one unpadded transport packet; return command and payload."""
    if len(packet) < 8 or packet[0] != 0xA0:
        raise ProtocolError("Missing or unexpected protocol packet header.")
    if packet[3] != sum(packet[:3]) & 0xFF:
        raise ProtocolError("Invalid transport checksum.")
    outer_length = int.from_bytes(packet[1:3], "little")
    if len(packet) != outer_length + 4:
        raise ProtocolError("Invalid transport length.")
    message = packet[4:]
    inner_length = int.from_bytes(message[1:3], "little")
    if inner_length < 1 or len(message) != inner_length + 3:
        raise ProtocolError("Invalid protocol length.")
    if sum(message) & 0xFF != 0xAA:
        raise ProtocolError("Invalid protocol checksum.")
    return message[0], message[3:-1]


def check_ack(command, payload):
    if len(payload) != 2 or payload[0] != command or not payload[1] & 1:
        raise ProtocolError("Missing or unexpected command acknowledgement.")


def parse_firmware(payload):
    value = payload.split(b"\x00", 1)[0]
    allowed = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-"
    if not 1 <= len(value) <= 128 or any(c not in allowed for c in value):
        raise ProtocolError("Firmware reply is not a printable version identifier.")
    return value.decode("ascii")


def parse_key_state(payload):
    """Return only a comparison result; never display the device's hash."""
    if len(payload) < 9 or payload[0] != 0:
        raise ProtocolError("Key-state query was unsuccessful or truncated.")
    flags, length = struct.unpack("<II", payload[1:9])
    if flags != PSK_FLAGS or length != 32 or len(payload) != 9 + length:
        raise ProtocolError("Unexpected key-state selector or response length.")
    return payload[9:] == EXPECTED_HASH


def explain():
    print("Lesson 3: firmware and expected-key-state query")
    print("Default mode only describes the plan. No USB device is opened.")
    print("With --run, each step waits for Enter:")
    print("  1. Find exactly one 27c6:55a4 and read its active USB configuration.")
    print("     Claim the bulk interface; stop if a kernel driver owns it.")
    print("  2. Drain pending input (up to 4 reads), then send NOP.")
    print("  3. Query firmware version (0xa8).")
    print("  4. Query expected key state (0xe4, read selector 0xbb020007).")
    print("Finally release the interface and close the USB handle.")
    print("No configuration switch, driver detach, sensor reset, key/firmware write,")
    print("TLS handshake, fingerprint capture, service changes, or saved logs.")
    print("These are host-side query commands; firmware behavior remains untested here.")
    for command, (payload, checksum) in QUERIES.items():
        packet = encode_frame(command, payload, checksum)
        size = int.from_bytes(packet[1:3], "little") + 4
        print(f"  TX 0x{command:02x}: {packet[:size].hex(' ')} (zero-padded to 64 bytes)")


def check_dependencies():
    pyusb = importlib.util.find_spec("usb") is not None
    libusb = ctypes.util.find_library("usb-1.0") is not None
    print(f"PyUSB module: {'available' if pyusb else 'missing'}")
    print(f"libusb shared library: {'found' if libusb else 'not found'}")
    print("This check does not import PyUSB or open a USB device.")
    return pyusb and libusb


class QueryTransport:
    def __init__(self, device, endpoint_in, endpoint_out):
        self.device, self.endpoint_in, self.endpoint_out = device, endpoint_in, endpoint_out
        self.buffer = bytearray()
        self.allow_padding = False

    def send(self, command):
        if command not in QUERIES:
            raise ProtocolError("Command is outside the diagnostic allowlist.")
        payload, checksum = QUERIES[command]
        packet = encode_frame(command, payload, checksum)
        if self.device.write(self.endpoint_out, packet, timeout=1000) != len(packet):
            raise ProtocolError("Short USB write.")

    def receive(self, timeout=1000):
        # Bound reads and lengths; support fragmented or coalesced small replies.
        for attempt in range(9):
            if self.allow_padding:
                self.buffer = self.buffer.lstrip(b"\x00")
            if len(self.buffer) >= 4:
                if self.buffer[0] != 0xA0:
                    raise ProtocolError("Unexpected transport type.")
                size = int.from_bytes(self.buffer[1:3], "little") + 4
                if not 8 <= size <= 4096:
                    raise ProtocolError("Response packet length is out of bounds.")
                if len(self.buffer) >= size:
                    packet = bytes(self.buffer[:size])
                    del self.buffer[:size]
                    decoded = decode_message(packet)
                    self.allow_padding = True
                    return decoded
            if attempt == 8:
                break
            self.buffer.extend(self.device.read(self.endpoint_in, 4096, timeout=timeout))
        raise ProtocolError("Response did not complete within the read limit.")

    def query(self, command):
        self.send(command)
        kind, payload = self.receive()
        if kind != 0xB0:
            raise ProtocolError("Expected an acknowledgement before the reply.")
        check_ack(command, payload)
        kind, payload = self.receive()
        if kind != command:
            raise ProtocolError("Reply does not match the requested command.")
        return payload

    def nop(self, timeout_error):
        self.send(0x00)
        try:
            kind, payload = self.receive(timeout=100)
        except timeout_error:
            if self.buffer:
                raise ProtocolError("NOP reply was truncated before timeout.") from None
            return False  # The reference permits silence, but not partial data.
        if kind != 0xB0:
            raise ProtocolError("Unexpected NOP response.")
        check_ack(0x00, payload)
        return True


def pause(message):
    input(f"\n{message}\nEnter to continue; Ctrl+C to stop. ")


def run_probe():
    # Lazy imports: plan/dependency modes and protocol tests never load PyUSB.
    import usb.core
    import usb.util

    if not sys.stdin.isatty():
        raise ProtocolError("--run requires an interactive terminal.")
    device = None
    interface_number = None
    claimed = False
    try:
        pause("1/4 — Open the sensor and claim its existing bulk interface.")
        devices = list(usb.core.find(find_all=True, idVendor=VID, idProduct=PID))
        if len(devices) != 1:
            raise ProtocolError("Expected exactly one matching sensor.")
        device = devices[0]
        configuration = device.get_active_configuration()
        interfaces = [item for item in configuration
                      if item.bAlternateSetting == 0 and item.bInterfaceClass in (0x0A, 0xFF)]
        if len(interfaces) != 1:
            raise ProtocolError("Expected one data/vendor interface at alternate setting zero.")
        interface = interfaces[0]
        interface_number = interface.bInterfaceNumber
        endpoints = [ep for ep in interface
                     if usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK]
        incoming = [ep.bEndpointAddress for ep in endpoints
                    if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN]
        outgoing = [ep.bEndpointAddress for ep in endpoints
                    if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT]
        if len(incoming) != 1 or len(outgoing) != 1:
            raise ProtocolError("Expected one bulk endpoint in each direction.")
        if device.is_kernel_driver_active(interface_number):
            raise ProtocolError("Kernel driver owns this interface; no driver was detached.")
        usb.util.claim_interface(device, interface_number)
        claimed = True
        transport = QueryTransport(device, incoming[0], outgoing[0])
        print(f"Claimed interface {interface_number}; IN=0x{incoming[0]:02x}, OUT=0x{outgoing[0]:02x}.")

        pause("2/4 — Drain pending input, then send NOP (0x00).")
        for _ in range(4):
            try:
                device.read(incoming[0], 4096, timeout=100)
            except usb.core.USBTimeoutError:
                break
        else:
            raise ProtocolError("Input did not become quiet; stop rather than draining forever.")
        if transport.nop(usb.core.USBTimeoutError):
            print("NOP acknowledged.")
        else:
            print("NOP had no response, as allowed by the reference tool.")

        pause("3/4 — Send firmware version query (0xa8).")
        print(f"Firmware: {parse_firmware(transport.query(0xA8))}")

        pause("4/4 — Query expected key state (0xe4). Returned hash is kept private.")
        matched = parse_key_state(transport.query(0xE4))
        print(f"Expected key state: {'MATCH' if matched else 'MISMATCH'}")
        print("Report this result before choosing any further operation.")
        return 0 if matched else 3
    finally:
        if device is not None:
            try:
                if claimed:
                    usb.util.release_interface(device, interface_number)
            finally:
                usb.util.dispose_resources(device)
                print("USB resources released.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="describe the plan (default); no USB access")
    mode.add_argument("--check-dependencies", action="store_true", help="check PyUSB and libusb availability; no USB access")
    mode.add_argument("--run", action="store_true", help="interactive firmware/key-state queries on the sensor")
    args = parser.parse_args()
    if args.check_dependencies:
        return 0 if check_dependencies() else 2
    explain()
    if not args.run:
        return 0
    if not check_dependencies():
        print("Dependencies are missing. Discuss local setup before retrying.", file=sys.stderr)
        return 2
    try:
        return run_probe()
    except (KeyboardInterrupt, EOFError):
        print("\nStopped by the operator.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"Probe failed ({type(error).__name__}): {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
