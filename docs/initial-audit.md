# Preliminary audit — 2026-10-07

This report records the initial review before downloading the dependencies.
The later [pinned source review](source-review.md) corroborates the PSK constants
and host-side write arguments and adds findings from the assembled driver.

## Scope and provisional conclusion

Static inspection of preparation, installation, uninstallation, key provisioning,
build, test, and CI scripts in the local Hydrogell checkout, along with relevant
sections of the patch and documentation. Reviewed revision:
`fe27b4812d60b4709d3dfb2b72f1e1f2704ede18`.

This is not a complete driver audit or a security certification. No community
scripts, compilers, or provisioning commands were executed. No packages were
installed and no service configuration, PAM settings, or sensor state was changed.
During this audit, system checks were limited to listing the USB device and the
two relevant package versions. A subsequent installed-stack detection check is
recorded separately in the [baseline test](baseline-test.md).

The community installer combines actions this project needs to evaluate
separately. Complete the source review before considering community-code execution
on the hardware.

## Reproducible findings in the available code

The following links pin the inspected revision.

### 1. Separate library, but additional installation effects

[`scripts/install-system.sh`, lines 18–41](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/scripts/install-system.sh#L18-L41)
copies the library to `/opt/libfprint-goodix/lib64` and creates
`/etc/systemd/system/fprintd.service.d/10-goodix55a4.conf`, setting
`LD_LIBRARY_PATH` for the service. This selects a library for fprintd;
it does not isolate the process or device.

The same script stops fprintd, provisions a key, may load an SELinux module,
and restarts the service. In addition,
[lines 119–128](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/scripts/install-system.sh#L119-L128)
attempt to enable `with-fingerprint` when `authselect` exists. That condition
was not checked on this laptop. The full installer exceeds our initial scope.

### 2. Uninstallation does not restore all previous state

[`scripts/uninstall-system.sh`](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/scripts/uninstall-system.sh)
removes the library, drop-in, and SELinux module. It does not restore the sensor
key. It also leaves templates and PAM configuration in place. There is therefore
no evidence of a complete rollback to the factory state.

### 3. Automatic provisioning; underlying write implementation still pending review

[`scripts/provision_psk.py`, lines 33–65](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/scripts/provision_psk.py#L33-L65)
calls `init_device(0x55a4)`, then `check_psk()`, and, if that returns false,
`write_psk()`. This flow does not ask for confirmation.

Those functions belong to a dependency that has not yet been inspected. Comments
claim that only `0xbb010003` is written and Windows uses `0xbb010002`; neither
the actual operation scope nor recovery of the original key has been verified.
Review the effects of `init_device()` as well as the function named `write`.

[`install-system.sh`, lines 59–71](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/scripts/install-system.sh#L59-L71)
allows installation to continue after provisioning fails. A final installation
message would not demonstrate that the sensor is usable.

### 4. Pinned Git revisions, unpinned Python dependencies

[`install.sh`](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/install.sh)
pins the two base repositories with full commit hashes and checks the checkout.
However, it installs `pyusb`, `crcmod`, and `python-periphery` without versions
or package hashes. [`setup.sh`](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/setup.sh)
also installs `numpy` and `opencv-python-headless` in the same way.

In `setup.sh`, pinning happens only when creating each clone: an existing tree is
not checked again against the expected revision. The script also runs
`git checkout -- .` in the libfprint copy, discarding changes to tracked files
there. It is unsuitable as an entry point for maintaining our own modifications.

### 5. The patch changes acquisition, TLS, and matching

[`patches/55a4-driver.patch`](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/patches/55a4-driver.patch)
affects five files: `goodix.c`, `goodix55x4.c`, `goodix55x4.h`, `goodixtls.c`,
and `sigfm.cpp`. It changes transfers and state handling, image processing,
and SIGFM matching rules. Reviewing only the USB ID is insufficient.

Lines 1176–1197 select `PSK:@SECLEVEL=0` and show TLS 1.2 configuration.
Lines 1198–1290 change correspondence ordering and angular comparison.
Their effect on acceptance and rejection needs investigation.

An image is passed to `fpi_image_device_image_captured` at patch line 772.
This supports host-side image processing in this implementation. It does not,
by itself, establish all possible capabilities of the silicon.

### 6. The rejection test confuses failures with valid rejections

[`scripts/fp-stress.sh`, lines 70–83](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/scripts/fp-stress.sh#L70-L83)
classifies any output without `verify-match` as `nomatch`, without distinguishing
timeouts, communication errors, or missing devices. When rejection was expected,
that result increments the correct-rejection counter.

The initial enrollment check helps but does not eliminate failures during a
session. Our tests must count errors as inconclusive and require an explicit
non-match result before counting a rejection.

### 7. The CI definition does not test recognition

The [reviewed workflow](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/.github/workflows/ci.yml)
defines shell analysis, Python syntax checks, patch application, Fedora and
Ubuntu builds, and a captured-file check. It defines no hardware or false-accept
tests. Remote run results were not consulted; only the definition was inspected.

## Claims still awaiting corroboration

| Claim | Available evidence | What remains to be verified |
| --- | --- | --- |
| PSK of 32 zero bytes | Hydrogell documentation and comments | TLS callback and blob in the pinned dependencies |
| Persistent writes only to `0xbb010003` | Comments and protocol documentation | Full transitive implementation and firmware effects |
| Windows coexistence | Author's account with limited testing | Independent evidence and recovery; separate slots alone are insufficient |
| Templates under `/var/lib/fprint` | Community documentation and script | Used fprintd implementation/configuration, format, and effective permissions; see the later baseline unit inspection |
| Working enrollment and verification | Author's published results | Reproducible local tests separating errors from biometric decisions |
| No official support | Previously reported check | Current official support list and code |

None of these claims has been tested with fingerprints on this laptop.
