#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 nachfq
# Fixed provisioning blob/serialization adapted from goodix-fp-dump at
# cc43bb3b3154a0bccc0412ae024013c7e1923139 (driver_55x4.py, goodix.py).
# Original MIT notice: LICENSES/goodix-fp-dump-MIT.txt.
"""Prepare the known sensor key; actual writing requires --write-key and confirmation."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fingerprint_query", ROOT / "scripts/03-probe-sensor.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)  # Our query helpers; no PyUSB import or USB access.
EXPECTED_FIRMWARE = "GF3268_RTSEC_APP_10062"
WRITE_FLAGS = 0xBB010003
BLOB = bytes.fromhex(
    "ec35ae3abb45ed3f12c4751f1e5c2cc05b3c5452e9104d9f2a3118644f37a04b"
    "6fd66b1d97cf80f1345f76c84f03ff30bb51bf308f2a9875c41e6592cd2a2f9e"
    "60809b17b5316037b69bb2fa5d4c8ac31edb3394046ec06bbdacc57da6a756c5")
BLOB_HASH = "ba1a86037c1d3c71c3af344955bd69a9a9861d9e911fa24985b677e8dbd72d43"
CONFIRMATION = "WRITE 27c6:55a4 KEY"


def write_payload():
    if len(BLOB) != 96 or hashlib.sha256(BLOB).hexdigest() != BLOB_HASH:
        raise probe.ProtocolError("Public provisioning blob differs from its reviewed pin.")
    return struct.pack("<II", WRITE_FLAGS, len(BLOB)) + BLOB


def explain():
    print("Lesson 8: one explicit persistent key write, not a fingerprint capture")
    print("Default/--plan and dependency check open no USB device.")
    print("--write-key requires an interactive terminal and reviewed authorization:")
    print("  Claim the existing 27c6:55a4 interface 0 (IN 0x82, OUT 0x01).")
    print("  No driver detach or USB configuration change; bounded drain and NOP.")
    print("  Query firmware 0xa8; require exactly " + EXPECTED_FIRMWARE + ".")
    print("  Query key state 0xe4 (read selector 0xbb020007); skip writing on MATCH.")
    print("  On MISMATCH, require typed confirmation: " + CONFIRMATION)
    print("  Send command 0xe0, write flags 0xbb010003, length 96, fixed public blob.")
    print("  Blob SHA-256: " + BLOB_HASH)
    print("  One logical write, split into two 64-byte USB packets; no automatic retry.")
    print("  Check ACK/status, then query state again; report MATCH/MISMATCH only.")
    print("The author describes this as persistent in the sensor, across OS changes.")
    print("No original-key backup/recovery is available. Reprovisioning is not proven here.")
    print("No firmware erase/update, sensor reset, TLS, capture, fprintd/PAM changes or logs.")
    print("A write timeout/error may mean the sensor already changed; do not retry blindly.")


class ProvisionTransport(probe.QueryTransport):
    def __init__(self, *args):
        super().__init__(*args)
        self.write_attempted = False

    def write_known_key(self):
        if self.write_attempted:
            raise probe.ProtocolError("A write was already attempted; automatic retry is forbidden.")
        packet = probe.encode_frame(0xE0, write_payload())
        self.write_attempted = True  # Set before sending: even a failed transfer is ambiguous.
        for offset in range(0, len(packet), 64):
            chunk = packet[offset:offset + 64]
            if self.device.write(self.endpoint_out, chunk, timeout=1000) != len(chunk):
                raise probe.ProtocolError("Short provisioning USB write; state is uncertain.")
        kind, payload = self.receive()
        if kind != 0xB0:
            raise probe.ProtocolError("Expected provisioning acknowledgement.")
        probe.check_ack(0xE0, payload)
        kind, payload = self.receive()
        if kind != 0xE0 or not payload or payload[0] != 0:
            raise probe.ProtocolError("Provisioning reply did not report success.")


def provision(transport, confirm=input):
    firmware = probe.parse_firmware(transport.query(0xA8))
    print("Firmware: " + firmware)
    if firmware != EXPECTED_FIRMWARE:
        raise probe.ProtocolError("Firmware differs from the reviewed unit; no write permitted.")
    if probe.parse_key_state(transport.query(0xE4)):
        print("Expected key state: MATCH. No write needed or attempted.")
        return 0
    print("Expected key state: MISMATCH.")
    print("Next operation is persistent; previous state cannot be restored by this script.")
    if confirm("Type " + CONFIRMATION + " to write, or anything else to stop: ") != CONFIRMATION:
        print("Stopped before writing.")
        return 130
    try:
        transport.write_known_key()
        matched = probe.parse_key_state(transport.query(0xE4))
    except Exception:
        print("A write was attempted. Sensor state is uncertain; no automatic retry.", file=sys.stderr)
        raise
    print("Expected key state after write: " + ("MATCH" if matched else "MISMATCH"))
    print("This verifies the immediate response, not persistence across power cycles or fingerprint support.")
    return 0 if matched else 3


def run():
    import usb.core
    import usb.util
    if not sys.stdin.isatty():
        raise probe.ProtocolError("--write-key requires an interactive terminal.")
    device = None
    claimed = False
    try:
        probe.pause("Open the sensor for firmware/key checks. No write until typed confirmation.")
        devices = list(usb.core.find(find_all=True, idVendor=probe.VID, idProduct=probe.PID))
        if len(devices) != 1:
            raise probe.ProtocolError("Expected exactly one matching sensor.")
        device = devices[0]
        interfaces = [item for item in device.get_active_configuration()
                      if item.bAlternateSetting == 0 and item.bInterfaceNumber == 0
                      and item.bInterfaceClass in (0x0A, 0xFF)]
        if len(interfaces) != 1:
            raise probe.ProtocolError("Expected the reviewed interface 0.")
        endpoints = {ep.bEndpointAddress for ep in interfaces[0]
                     if usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK}
        if endpoints != {0x82, 0x01} or device.is_kernel_driver_active(0):
            raise probe.ProtocolError("Unexpected endpoints or attached kernel driver; no detach.")
        usb.util.claim_interface(device, 0)
        claimed = True
        transport = ProvisionTransport(device, 0x82, 0x01)
        for _ in range(4):
            try:
                device.read(0x82, 4096, timeout=100)
            except usb.core.USBTimeoutError:
                break
        else:
            raise probe.ProtocolError("Input did not become quiet; no write attempted.")
        transport.nop(usb.core.USBTimeoutError)
        return provision(transport)
    finally:
        if device is not None:
            try:
                if claimed:
                    usb.util.release_interface(device, 0)
            finally:
                usb.util.dispose_resources(device)
                print("USB resources released.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--plan", action="store_true")
    modes.add_argument("--check-dependencies", action="store_true")
    modes.add_argument("--write-key", action="store_true", help="explicit persistent-write experiment")
    args = parser.parse_args()
    if args.check_dependencies:
        return 0 if probe.check_dependencies() else 2
    explain()
    if not args.write_key:
        return 0
    try:
        write_payload()
        if not probe.check_dependencies():
            return 2
        return run()
    except (KeyboardInterrupt, EOFError):
        print("Stopped. If interruption occurred during/after the write, state is uncertain.", file=sys.stderr)
        return 130
    except Exception as error:
        print("Provisioning stopped (" + type(error).__name__ + "): " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
