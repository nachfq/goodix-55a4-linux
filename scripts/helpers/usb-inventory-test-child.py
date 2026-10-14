# SPDX-License-Identifier: MIT
"""Native inventory fixture. Only execute inside the no-USB test sandbox."""
import ctypes as c
import os
from pathlib import Path
import sys


def run():
    if len(sys.argv) != 2 or sys.argv[1] not in {'0', '1'}:
        raise RuntimeError('Invalid fixture expectation')
    if any(os.path.lexists(p) for p in ('/dev/bus/usb', '/run/dbus', '/run/udev', '/home')):
        raise RuntimeError('Host device/service path in offline fixture')
    expected = int(sys.argv[1])
    assert Path('/proc/self/mountinfo').exists()
    lib = c.CDLL('/experiment/libfprint-2.so.2.0.0')
    lib.fp_context_new.argtypes = []; lib.fp_context_new.restype = c.c_void_p
    lib.fp_context_get_devices.argtypes = [c.c_void_p]; lib.fp_context_get_devices.restype = c.c_void_p
    lib.fp_device_get_driver.argtypes = [c.c_void_p]; lib.fp_device_get_driver.restype = c.c_char_p
    class Array(c.Structure):
        _fields_ = [('data', c.POINTER(c.c_void_p)), ('length', c.c_uint)]
    context = lib.fp_context_new()
    if not context:
        raise RuntimeError('Fixture context creation failed')
    devices = c.cast(lib.fp_context_get_devices(context), c.POINTER(Array)).contents
    if devices.length != expected:
        raise RuntimeError('Fixture inventory count differs')
    if expected and lib.fp_device_get_driver(devices.data[0]) != b'goodixtls55x4':
        raise RuntimeError('Fixture selected a different driver')
    # Process exit releases the offline context. No device open/capture API is used.
    print('PASS SYNTHETIC_USB_INVENTORY')


if __name__ == '__main__':
    run()
