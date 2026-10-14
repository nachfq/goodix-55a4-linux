# First private capture: prepared stack and trial status

The owner's one-shot key experiment reported immediate **MATCH**; see
[Test 003](key-provisioning-test.md). This satisfies the expected key-state check
for an attempt. It does not prove TLS with the sensor, a fingerprint image,
enrollment, matching, persistence or authentication support.

The owner later ran the prepared command; it stopped at USB selection.
A helper validation bug was corrected afterward; see [Test 004](capture-selection-test.md)
for current executable pins and checks. The subsequent owner-run attempt
reported one 108 x 88 image and successful close; see [Test 005](first-capture-test.md).
Enrollment and verification have not been attempted.

The owner authorized preparing the remaining host-side corrections, full library
build and one-image acquisition helper on 2026-10-14. This delivery does not run
the helper's hardware mode. It uses existing downloaded sources and cached Nix
inputs, without installing a driver or changing services or authentication.

## Read the implementation

- [Third correction](../patches/0003-goodix-capture-safety.patch): applies after
  the existing community patch and local patches 0001 and 0002, against libfprint
  `d1ca62a801aa565e67d1a2a47aaa7a33232b7990`. The separate ignored worktree is
  `work/libfprint-capture-fixed`; older trees and build artifacts are preserved.
- [Offline TLS checks](../scripts/09-test-capture-safety.py) and
  [device checks](../scripts/helpers/test-device-safety.py): actual implementation
  functions under sanitizers, with synthetic USB/SSM inputs. The TLS tests use
  real OpenSSL and local socketpairs, not the sensor.
- [Build](../scripts/11-build-capture.py): verifies fixed source/patch/helper pins,
  configures fresh ignored output and builds only the complete shared library and
  standalone helper. No install or execution of build products.
- [Capture launcher](../scripts/10-capture-one.py) and
  [small C helper](../scripts/helpers/capture-one.c): plan by default; a separate
  explicit run verifies and seals the reviewed artifacts before any USB access.

The driver changes retain the LGPL-2.1-or-later notices and attribution from the
[pinned source inventory](sources.md). The helper is original MIT project code.
This remains a partial review of experimental community code, not a complete
driver/dependency/firmware security audit.

## Corrections relevant to this experiment

The local TLS worker uses nonblocking descriptors, finite polling and a stop flag.
Teardown shuts down the sockets to wake it, joins it, then frees OpenSSL/server
resources. Partial initialization checks each acquired resource and unwinds only
valid handles. Main-context proxy reads no longer block the event loop, and TLS
record flights are accumulated before the fixed handshake sequence advances.
Unsupported fragmentation fails instead of silently advancing.

Commands and the full handshake have deadlines. USB errors terminate the pending
command; old read callbacks cannot deliver into a new command after cancellation.
Plaintext image reads accumulate the expected 14260 bytes across TLS records,
with a separate deadline. The decoder checks that exact length before reading.
The four trailing bytes' meaning is not established by this project; accepting
the expected layout does not validate their semantics.

The experiment restricts the driver to USB `27c6:55a4` and exact reported firmware
`GF3268_RTSEC_APP_10062`. Key-state diagnostics omit returned bytes. USB claim and
release errors propagate. Close waits for the LED-off command to finish or fail
before releasing the interface; a failure remains a failed trial. Calibration
does not turn an exhausted unstable baseline into a successful calibration.

The helper constructs only the selected device subtype, rather than a general
libfprint context. The experimental library exports that one internal type
function for this purpose; it is not a stable upstream API. USB descriptor
discovery inventories the bus, but only the exact selected device is opened.
The variant also skips libfprint's normal sysfs wakeup/persist updates for this
driver. It never changes USB configuration or detaches a kernel driver.

## Exact proposed hardware operation

First read the plan from the repository root; these modes open no device:

```sh
python3 scripts/10-capture-one.py --plan
python3 scripts/10-capture-one.py --check-inputs
```

The prepared owner-run command, **not executed during preparation**, is:

```sh
sudo -- /usr/bin/python3 "$PWD/scripts/10-capture-one.py" --run
```

One-shot sudo supplies device permission without a persistent permission rule.
The script explains its effects and requires exactly
`CAPTURE 27c6:55a4 ONE IMAGE` before starting. It does not repeat key provisioning.

1. Verify and freeze the exact executable/library in sealed in-memory files.
   Create a fresh ignored private output directory. Discard native stdout/stderr;
   expose only a small fixed stage/result vocabulary through a separate pipe.
2. Find exactly one matching reader. Inspect its current active configuration,
   interface 0/alternate 0 and bulk IN `0x82`/OUT `0x01`; refuse unexpected layout.
   Claim the interface with no kernel-driver bind/detach flags.
3. Activate: NOP `0x00`, chip enable `0x96`, NOP, firmware query `0xa8` and private
   key-state query `0xe4`. Mismatch or different firmware fails. Then reset `0xa2`
   (`reset_sensor=TRUE`, `soft_reset_mcu=FALSE`, sleep field 20), idle `0x70`,
   MCU configuration upload `0x90`, TLS request `0xd0`, proxied TLS1.2 and
   establishment confirmation `0xd4`.
4. Calibrate with background frames and FDT baseline; switch the indicator on.
   **Keep your finger off until the light comes on**, then rest it on the reader
   without pressing the power button. Finger detection may acquire multiple
   frames before returning one image. The prior two-recovery TLS budget remains;
   these are session reconnects, not key writes.
5. When the script says to lift your finger, remove it immediately; do not wait
   for its CLOSE stage. That prompt comes from public finger-status flags after
   image delivery begins and is not a final successful result. Follow the
   finger-lift sequence and deactivate with sleep `0x60`/`0x92`,
   stop/join TLS, attempt LED-off `0xae`, and release USB. Save exactly one PGM
   only after successful capture **and** close. No template is enrolled or saved.

These commands change sensor runtime state; the complete effects of its firmware
are not known. There is no key-write, firmware erase/update, OS USB configuration
switch, fprintd/D-Bus call, PAM/sudo-auth/lock-screen change, or installer in this
experiment. It uploads nothing. The public PSK does not protect against an
attacker who can observe and reconstruct this sensor transport.

## Deadlines, privacy and interpretation

The helper's stage limits are initialization 10 s, open 15 s, capture 45 s and
close 10 s, with a 3 s cancellation grace. The parent has a 90 s limit, then
bounded termination. A forced process exit releases host handles but does not
prove the sensor slept or the indicator went dark. No automatic new trial or
persistent write follows failure. Errors/timeouts are inconclusive, never a
correct rejection of an unregistered finger.

Output is `work/private-captures/trial-…/image.pgm`, with directory mode 0700,
file mode 0600, owned by the invoking repository owner even with sudo. The
exclusive no-symlink writer refuses overwrite; failed trials remove partial
image output. Core dumps and raw logs are disabled for the child. The image is
biometric data: keep it local and do not include it in commits or chat output.
The script prints only its path and dimensions, not its pixels or a hash.

Success would establish that this experimental stack returned an image. The
normal libfprint capture API also runs its image/minutiae preprocessing; a
processing failure can therefore prevent an image result even after acquisition.
Neither capture nor preprocessing success establishes that the registered finger
is accepted or others rejected. Enrollment and controlled verification are later
experiments, before any authentication integration.

## Verification record

Assistant-observed on 2026-10-14 with the existing cached Nix environment:

- Strict source/patch/helper pins and patch applicability passed. Older source
  and build pins were rechecked unchanged. New canonical effective-source SHA-256:
  `cd1acfb1aaee0d000396d9ed94a95d8f9d6fcf174f4bf874528e8f7c7b6ed34c`.
- Patch0003 SHA-256:
  `a16bc19971e539809a231744efed1af5cf4b87e51745fbd4201bbdef8de436de`.
- **50 native sanitizer cases passed**: five real host-side TLS/resource/lifecycle
  cases (including nine injected initialization boundaries, fragmented flights,
  a silent-peer deadline and 100 stop/join cycles), fifteen new actual-function
  deadline/cancellation/USB-generation/image/abort cases, twenty-four preceding
  flow regressions, and six NOP/busy cases. Synthetic USB/SSM behavior remains a
  test boundary; these are not physical trials or a proof of complete concurrency
  correctness. Handshake messages split across TLS records are unsupported and
  fail closed; proxy flights are capped at 4 KiB.
- The device harness passed actual-function checks for claim/release and deferred
  LED close, private key-state errors, exact firmware, frame lengths/pixels,
  exhausted/stable calibration, malformed FDT, cancellation/timer cleanup,
  scan/sleep completion and LED failure. Two original-function negative controls
  failed their expected assertions. Complete changed device syntax passed.
- **78 Python offline tests passed**, covering preceding experiments plus capture
  launcher/build refusals, sealed inputs, private output and fixed report parsing.
- Fresh full-library target compilation and helper linking exited 0. After finding
  and fixing the NOP response-read/generation problem during integration, a
  targeted incremental library rebuild and helper recompile also exited 0.
  Generated registration includes only `goodixtls55x4`. Static ELF inspection
  confirmed the shared library SONAME and extra selected-type export. No native
  executable was run by either build step.
- The complete final executable/library passed the
  [offline runtime smoke](../scripts/12-test-capture-runtime.py) inside bubblewrap:
  isolated namespaces, no host USB/sysfs/service sockets/home/network, sealed ELF
  launch, actual synthetic finger-lift gate, private 2x2 PGM format/permissions
  and overwrite refusal. It constructs a synthetic image, not a USB context.
  Synthetic output and temporary copies were removed. No additional packages.

The table below identifies the original D9 artifacts, before the subsequent
[USB selection fix](capture-selection-test.md). That report gives the current helper
pin; the original executable was preserved separately and the library is unchanged.

| Original D9 artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `work/libfprint-capture-fixed-build/libfprint/libfprint-2.so.2.0.0` | 2204768 | `e37a3d6e7d6eefd35f201643d6cc399ba6317d9a19b527e83e252dc05f211098` |
| `work/capture-one-build/capture-one` | 28104 | `268113e2d7fbbe5c11012853156d19715fc350ff419a22d29207e92a2cd6f480` |

Helper-source SHA-256:
`bc1b760b6b646eb3bd854f10e394d6e44b908f24cbfaab1aa5ce358eafc165bb`.
These identify this local build, not promised cross-machine reproducibility.
The launcher refuses changed artifacts; it does not accept a command-line pin
or silently update it. Cached store dependencies can still disappear after GC.

Existing warnings remain, including unused helpers/unhandled state cases and an
uninitialized verification-path result outside this capture route. Unreachable
legacy rotation/PGM helper defects were found but not changed. No complete
matcher/parser/dependency audit is claimed. Raw build/test logs remain ignored.
At this original preparation handoff hardware capture had **not run**. The later
selection-only attempt and corrected helper are recorded in Test 004 above.
An independent first review verified the
frozen target (HEAD `621dde0`, main/merge-base `ceb73bf`, selected-file snapshot
SHA-256 `bffcd1063fbe0ffb2ab4f3aa04b8dd45682d140dfa795087a1d6e42cb3f6c627`).
It inspected code/test integration and passed nineteen scoped Python checks and
both input-check modes. It reviewed the native/build/smoke logs without repeating
native execution. It reported no confirmed actionable code defects and one stale
handoff-documentation finding (D9-R1), corrected above/in the linked plan. Its
one focused follow-up verified snapshot
`596c9f015f49a87ce46fe3abe31e2f28cdf4d418d6f5a34c222114d4924529e9`
and confirmed D9-R1 resolved, with no remaining findings. Only this review-outcome
record was updated afterward; executable sources, patches and artifact pins
were identical to the reviewed target at that handoff; the subsequent selection
correction has separate verification evidence above. This is independent
review evidence, not user acceptance, physical compatibility or publication.
