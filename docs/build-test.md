# First local driver build

Date: 2026-10-09. This is assistant-observed compilation evidence on the owner's
machine, following explicit delegation. The owner authorized the predicted Nix
dependency acquisition and compilation, excluding driver installation and sensor
access. This is not a biometric or runtime compatibility test.

The TLS constructor defects recorded below were subsequently addressed by
[a separate local correction and regression trial](tls-error-fix.md).
This report describes the unchanged community baseline.

## Inputs and dependency setup

- libfprint base: `d1ca62a801aa565e67d1a2a47aaa7a33232b7990`.
- Patch and canonical patched-tree diff SHA-256:
  `73720a4418ed7ceb640011f51d4f2bac206118bc480ab6f1784f6618b479ef15`.
- Nixpkgs: `a5cc6f2c37bf518436dc8d1c288ccd0c43c2f4c4`, with the content pin
  in [nix/shell.nix](../nix/shell.nix).

Nix's dry run predicted 133 missing store paths: 149.1 MiB download and 500.7 MiB
unpacked. Dependencies were substituted from `https://cache.nixos.org`, without
an Arch package transaction. The already cached Nixpkgs source was reused.
Nix cache/state/data overrides and the reviewed dependency log are local under
ignored `work/nix/`; raw logs are not published here.

The shell's preflight exited 0. All required tools and metadata were found:
Meson 1.10.2, GLib/GIO/GObject 2.88.3, GUsb 0.4.9, OpenSSL 3.6.3,
OpenCV 4.13.0 and doctest 2.5.2. The compiler was GCC/G++ 15.2.0, with
Binutils 2.46. No driver source adaptation was needed.

## Configuration and compilation

The assistant operated the prompts in `scripts/04-build-local.sh --run` through
a terminal inside the Nix shell. The script verified its sources before setup
and again before compilation, confirming a fresh ignored output directory.
Meson configured libfprint 1.94.6 with only `goodixtls55x4`, introspection,
documentation, GTK examples and installed tests disabled, udev rules/hwdb
disabled, and `--wrap-mode=nofallback`. Compiler/dependency probes and generators
ran during setup. Optional Cairo/introspection discovery failures did not prevent
configuration with those features disabled.

The generated metadata selected the shared library `fprint-2`. Ninja completed
all 64 actions in that target's build graph; the final script status was 0.
The generated driver registration contains only `goodixtls55x4`.

Artifact: `work/libfprint-build/libfprint/libfprint-2.so.2.0.0`.
Size: 2,183,512 bytes. SHA-256 for this local artifact:
`ff5ed53d358cfb911441c111a5607379e2e34abe55e37870933a61f5d8a9dd8c`.
This hash identifies this build, not a promised byte-identical result on all hosts.

Static `readelf` inspection found an ELF64 x86-64 shared object with SONAME
`libfprint-2.so.2`. Direct dependencies include GLib/GIO/GObject, GUsb,
OpenSSL/libcrypto 3, OpenCV features2d/core 4.13, the C++ runtime and libc.
RUNPATH contains Nix store paths. Dependency resolution by a runtime loader has
not been tested; the artifact has not been loaded. Its dependencies have no
project-specific permanent GC root, so do not assume retention after GC.

After compilation the clean base remained clean and the patched source's
canonical diff still matched the reviewed patch hash. No installation, driver
execution, service configuration, PAM change, key provisioning, fingerprint
capture, enrollment, verification, or upstream test execution was performed.

## Warnings that affect the next decision

Compilation succeeded with warnings. One is a concrete memory-safety defect in
the pinned base's
[`goodixtls.c`, lines 41–52](https://github.com/TheWeirdDev/libfprint/blob/d1ca62a801aa565e67d1a2a47aaa7a33232b7990/libfprint/drivers/goodixtls/goodixtls.c#L41-L52):
`err_from_ssl()` allocates `strlen(msg)` bytes and then calls `strcpy`, which
also writes the terminating NUL. For a non-null message this writes one byte
beyond the requested allocation. Inspection also shows the manually allocated
`GError` leaves its domain unset and the returned OpenSSL reason is not checked
for null. These error-path defects are static findings; no runtime crash was
observed because the library was not executed. They are not caused by Nix.

Other warnings include a potentially uninitialized verification result, scalar
initializer issues, formatting mismatches, and unused code. Their runtime
consequences require separate source review; the warning list is not a complete
audit. The previously documented [TLS retry defect](source-review.md#4-tls-image-retry-limit-is-reset-inside-its-own-retry-path)
also remains unfixed.

Recommended next delivery: review and correct the TLS error construction in a
separate explicit patch with offline failure-path checks before loading the
driver. The successful baseline build is preserved unchanged for comparison.
Sensor provisioning and driver execution require their own agreed scope.
