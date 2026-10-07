# Pinned source review — 2026-10-07

## Scope and checkout state

The owner authorized downloading the two pinned dependencies into an ignored
directory and reviewing them statically. They are now available locally:

| Directory | Content |
| --- | --- |
| `work/libfprint/` | Clean base at `d1ca62a801aa565e67d1a2a47aaa7a33232b7990` |
| `work/goodix-fp-dump/` | Clean source at `cc43bb3b3154a0bccc0412ae024013c7e1923139` |
| `work/libfprint-patched/` | Separate Git worktree at the same libfprint base, with the reviewed Hydrogell patch applied as uncommitted changes |

Both repositories were initialized with empty Git templates, fetched by exact
commit with `--depth=1`, and checked out detached with hooks disabled. Their
HEADs were checked against the requested hashes. No submodules were downloaded.
The dump project's firmware submodule remains uninitialized at its referenced
commit `7b9a828d1d14dee587d9c900505233188c23a92d`.

`git apply --check` succeeded before applying the patch to the separate worktree.
The clean base was preserved. All three directories are excluded by `/work/` in
the root `.gitignore`; no downloaded code is being published in this repository.

No community Python modules were imported, no build system or installer was
executed, and no USB commands were sent in this stage. This review focuses on
initialization, PSK provisioning, firmware entry points, and a retry defect. It
does not complete the memory-safety, matching, dependency, or upstream-divergence audit.

## 1. What Hydrogell's provisioning path actually calls

The previously inspected [provisioning wrapper](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/scripts/provision_psk.py#L33-L65)
uses these functions from the pinned dependency:

| Step | Observed source behavior | Effect relevant to a test |
| --- | --- | --- |
| `init_device(0x55a4)` | Constructs a USB device and sends NOP | Includes USB configuration, buffer draining, and a protocol command |
| `check_psk(device)` | Sends command `0xe4` with flags `0xbb020007` and compares the returned bytes with `PMK_HASH` | Checks for the expected key state; does not recover the original key |
| `write_psk(device)` | Sends command `0xe0`, flags `0xbb010003`, and a 96-byte `PSK_WHITE_BOX` blob, then checks again | The key-write operation; must remain separate from a diagnostic query |

Evidence: [`driver_55x4.py`, lines 19–70](https://github.com/goodix-fp-linux-dev/goodix-fp-dump/blob/cc43bb3b3154a0bccc0412ae024013c7e1923139/driver_55x4.py#L19-L70)
and [`goodix.py`, lines 699–786](https://github.com/goodix-fp-linux-dev/goodix-fp-dump/blob/cc43bb3b3154a0bccc0412ae024013c7e1923139/goodix.py#L699-L786).
The write serializer uses little-endian flags and payload length followed by the
blob. The read selector `0xbb020007` differs from the write selector `0xbb010003`;
they should not be described as interchangeable raw slot addresses.

Static parsing of the literal constants, without importing project modules,
confirmed a 32-byte all-zero PSK and a 96-byte white-box blob. The C
[TLS callback](https://github.com/TheWeirdDev/libfprint/blob/d1ca62a801aa565e67d1a2a47aaa7a33232b7990/libfprint/drivers/goodixtls/goodixtls.c#L56-L76)
also supplies the all-zero key.

This verifies the host-side arguments used by the provisioning path. It does
not establish all firmware-side effects, Windows coexistence, persistence on
this unit, or a way to restore the original key. No original-key backup is
performed by the reviewed wrapper.

## 2. Initialization is more than a query

[`USBProtocol.__init__`, lines 31–106](https://github.com/goodix-fp-linux-dev/goodix-fp-dump/blob/cc43bb3b3154a0bccc0412ae024013c7e1923139/protocol.py#L31-L106)
finds the device, queries USB status and descriptors, obtains the active
configuration, and locates bulk endpoints. If a kernel driver is active on the
selected interface, it detaches it. It then calls `set_configuration()`.

[`Device.__init__` and `nop`, lines 148–200](https://github.com/goodix-fp-linux-dev/goodix-fp-dump/blob/cc43bb3b3154a0bccc0412ae024013c7e1923139/goodix.py#L148-L200)
drain pending reads until a timeout and send NOP. There is no key-write or
firmware-erase call in this initialization path, but it changes USB runtime state.
Its buffer-draining loop has no overall iteration limit if data keeps arriving.

The patched C driver also performs operations beyond querying: opening sends an
LED-off command; activation enables the chip, reads firmware/key state, resets
the sensor, selects idle mode, and uploads configuration before TLS and capture.
The reviewed 55x4 activation path checks the key and fails if it differs; it does
not invoke key provisioning. The base sequence is visible in
[`goodix55x4.c`, lines 250–331](https://github.com/TheWeirdDev/libfprint/blob/d1ca62a801aa565e67d1a2a47aaa7a33232b7990/libfprint/drivers/goodixtls/goodix55x4.c#L250-L331);
the open/close LED additions are in the
[Hydrogell patch](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/patches/55a4-driver.patch#L1088-L1121).

## 3. The dump program's main entry point can replace firmware

[`run_55a4.py`](https://github.com/goodix-fp-linux-dev/goodix-fp-dump/blob/cc43bb3b3154a0bccc0412ae024013c7e1923139/run_55a4.py)
calls `driver_55x4.main(0x55a4)`. After an interactive warning, that function
compares the firmware with target `GF3268_RTSEC_APP_10041`.

If the reported firmware matches the broader valid-family pattern but differs
from the target, the code calls `erase_firmware()`. On a subsequent bootloader
path it can provision the key and call `update_firmware()`.
Evidence: [`driver_55x4.py`, lines 209–282](https://github.com/goodix-fp-linux-dev/goodix-fp-dump/blob/cc43bb3b3154a0bccc0412ae024013c7e1923139/driver_55x4.py#L209-L282).

The erase function sends `mcu_erase_app`; the update function writes firmware in
256-byte chunks and can erase again after an update failure
([lines 73–114](https://github.com/goodix-fp-linux-dev/goodix-fp-dump/blob/cc43bb3b3154a0bccc0412ae024013c7e1923139/driver_55x4.py#L73-L114)).
An absent firmware submodule is not a safeguard: the erase path occurs before
opening the firmware file in the update path.

This behavior belongs to the full dump entry point. Hydrogell's provisioning
wrapper does not call `main()`, `erase_firmware()`, or `update_firmware()`.
Do not use `run_55a4.py` as our initial diagnostic.

## 4. TLS image retry limit is reset inside its own retry path

The assembled patch contains a concrete control-flow defect:

1. On a TLS-restart response to an image request, it checks `reimage_tries >= 2`.
2. It increments `reimage_tries`.
3. It immediately calls `goodix_reset_state()`, which sets that same counter to zero.

Evidence: [patch lines 38–66](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/patches/55a4-driver.patch#L38-L66)
and [250–254](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/patches/55a4-driver.patch#L250-L254).
In the assembled local `goodix.c`, the relevant lines are 373–396 and 1417–1429.
Normal command completion also calls `goodix_reset_state()` at line 108.

Therefore the intended two-retry bound does not accumulate across these retries.
If the sensor repeatedly requests TLS restart and each handshake succeeds, this
guard does not terminate recovery. Other errors or cancellation may still end
the operation. This is a static finding, not an observed hang on this laptop.
No fix has been applied. A future fix should separate per-command reset from
per-image retry state and test repeated restart responses without real hardware.

## 5. Dependency and license inventory

The Python requirements are unpinned: `pyusb`, `crcmod`, `python-periphery`,
`spidev`, `pycryptodome`, and `crccheck`. The generic USB module imports SPI
dependencies too. This does not mean every requirement is necessary for a
purpose-built firmware/key-state query.

The libfprint source requires OpenCV and doctest in
[`libfprint/sigfm/meson.build`](https://github.com/TheWeirdDev/libfprint/blob/d1ca62a801aa565e67d1a2a47aaa7a33232b7990/libfprint/sigfm/meson.build).
Local read-only checks found GCC/G++, Ninja, and pkg-config, but not Meson or
CMake on PATH. Neither `opencv4` nor `doctest` was found by pkg-config. GLib/GIO,
GObject, GUsb, OpenSSL, pixman, NSS, GUdev, udev, and Cairo were found. This is not
a successful build or a final package installation plan; other discovery methods
and build requirements have not been exhausted.

The dump repository's root license is MIT. The libfprint root `COPYING` contains
LGPL 2.1, and the reviewed 55x4 driver header specifies LGPL 2.1 or later.
Individual files and any code we later incorporate still need attribution review.

## Proposed next small test — not implemented or executed

Prepare a narrow diagnostic that reports only firmware version and whether the
returned key-state hash matches the public expected value. It should have a
fixed command allowlist, bounded reads, explicit cleanup, and no firmware-write,
key-write, capture, enrollment, or automatic-repair path. Do not publish device
hashes; report only expected/not-expected/error.

Before hardware execution, review its exact USB setup and commands, permissions,
and any dependency installation with the owner. A key mismatch should stop the
test and produce a report, never trigger provisioning. This can establish whether
capture prerequisites are present without running the full dump program.
