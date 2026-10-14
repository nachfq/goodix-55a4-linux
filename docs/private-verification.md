# Private enrollment and controlled verification

## Scope and current evidence

On 2026-10-14 the owner accepted preparation after reporting the first real
108 x 88 image. This delivery prepares a separate local library and standalone
experiment. The owner subsequently reported completing enrollment; the local
private template and frozen-series manifest passed host-only integrity checks.
The owner then reported one NO_MATCH and one MATCH during the requested
declared-same verification step, followed by one NO_MATCH in the requested
declared-other trial. These are initial owner-reported observations, not
repeatability or accuracy validation.
No installation, fprintd/PAM/service configuration, additional dependencies or
persistent sensor provisioning belong to this delivery.

The experiment uses the attributed community driver, existing SIGFM matcher and
local corrections. It does not implement a new recognition algorithm. The
existing settings remain fixed: **16 enrollment stages, threshold 72, minimum
5 feature matches**. These settings have not been validated for this reader.

## Corrections and provenance

Apply [0004](../patches/0004-goodix-verification-safety.patch) after the community
patch and 0001–0003 on libfprint
`d1ca62a801aa565e67d1a2a47aaa7a33232b7990`, in the separate ignored
`work/libfprint-verification-fixed` tree. The successful capture tree/build are
preserved. The patch retains the original LGPL-2.1-or-later notices; see the
[license](../LICENSES/libfprint-LGPL-2.1.txt) and [patch guide](../patches/README.md).

Concrete defects corrected in the host code:

- `fp-print.c`: correct GPtrArray/buffer ownership during serialization; reject
  invalid/empty SIGFM prints, malformed GVariant structures and feature payloads;
  preserve the absent enrollment-date sentinel on a round-trip.
- `fpi-print.c`: copy image features into their print; validate probe/template
  types, counts and threshold before matching, reporting invalid data as error.
- `fp-image.c`: release image-owned features; extraction replaces them safely.
- `fpi-image-device.c`: initialize the decision as ERROR and transfer enrollment
  progress errors correctly, avoiding reuse after the callback frees them.
- `sigfm/binary.hpp` and `sigfm.cpp`: bound binary reads/counts/matrix dimensions,
  reject truncated/trailing/nonfinite or inconsistent SIGFM data, and contain C++
  exceptions at the C interface. Generic CV8/vector codecs retain compatibility.

These are a focused review, not a complete audit. `fp_print_equal` still lacks
SIGFM support and is deliberately excluded. Large feature collections retain
expensive matcher work; process limits mitigate a stalled trial. No biometric
accuracy, spoof resistance or authentication suitability is established.

## What hardware execution will do

The new helper reuses [capture-one.c](../scripts/helpers/capture-one.c)'s raw
libusb descriptor guard: select exactly one 27c6:55a4, validate its active interface
and bulk endpoints, then construct only `goodixtls55x4`. It does not enumerate
through fprintd or change USB configuration/detach a kernel driver.

The driver may enable/reset the chip, query firmware/key state, configure TLS,
upload runtime configuration, calibrate/background-capture, detect fingers,
acquire frames, control the LED and sleep. The previously written key is used;
this script performs **no key or firmware write**. Sensor reset here is a runtime
command, not a restoration of its previous persistent key.

Enrollment captures 16 accepted scans of the **right index finger**, extracts
features and returns one host-side template. Only final enrollment success and
successful driver close allow a private template to be saved. No image is saved.
Verification captures one probe and compares it on the computer with that template.
A match callback is preliminary: final success, exactly one consistent decision,
no retry/error and successful close are required before publishing MATCH/NO_MATCH.

Template and `series.json` stay under ignored `work/private-verification/`,
directory 0700, files 0600, owned by the caller. The manifest freezes the template
and library/helper hashes plus matcher settings; hashes of biometric data remain
private. Verification checks them before USB and again before reporting. It does
not update the template or tune thresholds. Enrollment refuses existing data.
The directory is locked against concurrent instances. Removing this private
folder later removes the local series; it does not undo the sensor key write.

Deadlines: initialization 10 s, open 15 s, each enrollment scan 45 s with total
600 s, verification 45 s, close 10 s, cancellation grace 3 s; parent wall limit
650 s. Enrollment retries do not restart the per-scan deadline. A forced process
exit releases host resources but cannot prove sleep or LED-off. Cancellation,
retry, malformed/transport errors and timeout are **inconclusive**, never correct
biometric rejections. No raw child diagnostics are printed/saved.

## First owner-run experiment: enroll

From the repository root, inspect the plan and exact artifacts without USB:

```sh
python3 scripts/14-enroll-verify.py --plan
python3 scripts/14-enroll-verify.py --check-inputs
```

After reviewing that operation, run the enrollment in an interactive terminal:

```sh
sudo -- /usr/bin/python3 "$PWD/scripts/14-enroll-verify.py" --run --enroll
```

Type `ENROLL 27c6:55a4 RIGHT INDEX` at the confirmation. Keep your finger off during
initial calibration. Place your **right index** only when the physical LED lights;
rest it gently without pressing the power button. Lift immediately when prompted.
For later scans, wait for the explicit **touch again** message: the LED can remain
on across scans. Accepted scans count up to 16. An error remains inconclusive.
Share only the safe terminal result, never the template. Discuss the result before
starting verification. The assistant has not run these hardware commands.

## Subsequent controlled comparisons

After successful enrollment, inspect and agree on the first verification trial.
Use the same right index for `same`; choose an unenrolled finger for `other`.
The category is the operator's declaration, not independently measured identity.

```sh
sudo -- /usr/bin/python3 "$PWD/scripts/14-enroll-verify.py" --run --verify --expected same
sudo -- /usr/bin/python3 "$PWD/scripts/14-enroll-verify.py" --run --verify --expected other
```

Each command is one trial with its own exact confirmation (`VERIFY 27c6:55a4 SAME`
or `VERIFY 27c6:55a4 OTHER`). Keep off for calibration, touch on the LED, then lift
when prompted. Do not run both as an unattended sequence.

| Completed trial | Interpretation / exit status |
| --- | --- |
| same + MATCH | Consistent observation, 0 |
| other + NO_MATCH | Consistent observation, 0 |
| same + NO_MATCH | False-reject observation, 4 |
| other + MATCH | False-accept observation; **stop authentication progress**, 3 |
| Error/retry/close failure | Inconclusive, 1 |
| Parent timeout / interruption | Inconclusive, 124 / 130 |

A successful enrollment is not recognition proof. A handful of correct trials
cannot establish error rates. The [staged plan](plan.md#4-enrollment-and-verification-without-pam-integration)
proposes a later fixed-template series, with aggregate counts and errors separate.
Do not re-enroll or change thresholds to hide a false accept.

## Offline checks and build

[15-build-verification.py](../scripts/15-build-verification.py) pins the complete
source diff, all patches and both helper sources, requires fresh ignored output
paths and builds only the library and helper using already cached Nix inputs.
It does not install/load/run them. No download or package installation is needed.
A fresh clone lacks the ignored source/build inputs; scripts stop rather than
fetching or repairing them. The existing completed build is preserved.

[13-test-verification.py](../scripts/13-test-verification.py) compiles real SIGFM
and the actual extracted matcher with OpenCV/GLib and ASan/UBSan. Synthetic
features test positive/negative scores, error guards, ownership, binary round-trip,
every truncated prefix, malformed shapes and nonfinite values. Restoring the
prior matcher and binary reader provides two sanitizer failure controls.
These synthetic outcomes do not measure real recognition.

[16-test-verification-runtime.py](../scripts/16-test-verification-runtime.py)
runs the complete pinned executable/library, sealed, inside bubblewrap with
private namespaces and no host USB, sysfs, service sockets, home or network. Its
early selftest constructs synthetic features, exercises public `FpPrint`
serialization/deserialization, descriptor/prompt guards and cancellation; it
never creates a USB context. G_DEBUG=fatal-criticals catches GLib ownership errors.
Python tests separately cover the parent decision/error/close gates and private
series permissions, mutation and overwrite refusal.

Use the existing Nix invocation documented in [the Nix guide](nix-build.md), with
`python3 -B scripts/13-test-verification.py --run` or
`python3 -B scripts/16-test-verification-runtime.py --run`. Run without sudo.
The ordinary offline Python suite is `python3 -B -m unittest discover -s tests -v`.

## Preparation evidence — 2026-10-14

The assistant completed a full fresh library/helper build, then a targeted rebuild
after final core/helper corrections. Selected targets, static ELF inspection and
final input pins passed. Cached Nix inputs only; no hardware access or installation.
One intermediate synthetic runtime failed because the fixture attempted to store
a GVariant at the unaligned FP3 header offset. Copying its serialized bytes fixed
the fixture; the public API round-trip then passed with fatal GLib criticals.

- Actual SIGFM/OpenCV/GLib ASan/UBSan suite passed, including all 4340 truncated
  prefixes, positive score ≥72, synthetic negative score 0 and ownership guards.
- Both original-function negative controls reproduced sanitizer failures.
- Full Python suite: **116 tests passed** (37 focused enrollment/verification checks).
- Complete pinned runtime selftest in the no-host-USB sandbox: passed.
- Independent read-only D12 review: no actionable findings. Source/artifact pins
  were independently checked; existing test logs were inspected, not rerun by
  the reviewer. No hardware or biometric data was accessed. The native smoke
  covers serialization/prompts/cancellation; parent decision gates use synthetic
  reports. This is focused review, not a complete security/accuracy audit.

Canonical effective-source diff SHA-256: `4d6bb24524a87641fe770474410d56a439713aaf0436c5bd17b2dd5e804535a9`.
Build script 15 verifies the patch chain and source contents before/after compilation.

| Public build input/artifact | SHA-256 |
| --- | --- |
| `patches/0004-goodix-verification-safety.patch` | `39477b84083169e20aec2be2c80f7d1c9c037e5a832d42cd1cb150ff3ca3cce7` |
| `work/libfprint-verification-fixed-build/libfprint/libfprint-2.so.2.0.0` | `161c4a9fa432963b30d7303e1f6d8152269254f52850d14a77aae3e53399c2cd` |
| `work/enroll-verify-build/enroll-verify` | `a276aba080be21255bdb6774a2865546b1288125b30ad634a8a328f167b985e7` |
| `scripts/helpers/enroll-verify.c` | `846ca704990bc5e68e2836d7e3bcc2312a7852e66827a066ad0240dc88a44788` |

## Test 006 — owner-reported enrollment

The owner reported completing the prepared enrollment on 2026-10-14. They did
not supply its terminal transcript or shell exit status. A subsequent assistant
host-only check confirmed the private template and series manifest exist, have
the required ownership/permissions and format header, and match the frozen
artifact/template provenance. No content, biometric digest or private identifier
was printed or published. The assistant did not load the library, parse the
biometric features or access USB.

This supports a persisted local enrollment result, not successful recognition.
The next owner-run experiment is one declared-same verification with the enrolled
finger; discuss its output before an unenrolled-finger trial. No hardware
verification or authentication integration has been performed.

## Test 007 — first owner-reported same-finger comparisons

After receiving the declared-same command, the owner reported one NO_MATCH and
one MATCH on 2026-10-14. No complete terminal transcripts, exit statuses or
placement details were supplied; finger category follows the requested procedure
and remains an operator declaration. The assistant did not repeat hardware runs
or inspect biometric data.

For the enrolled finger, these labels represent one false-reject observation and
one consistent match observation. They show initial, inconsistent recognition
behavior, not an accuracy estimate or reliable authentication. Error/retry trials
are still inconclusive; do not include them as biometric rejection results.
Keep the same template and thresholds. Next perform one declared-other trial
with an unenrolled finger and discuss the safe output. A declared-other MATCH
stops progress toward authentication integration.

## Test 008 — first owner-reported other-finger comparison

After receiving the declared-other command, the owner reported NO_MATCH on
2026-10-14. No full terminal transcript, exit status or specific other-finger
identity was supplied. The category follows the requested procedure and remains
an operator declaration. The assistant did not run hardware or access biometrics.

First explicitly reported decisions, before the repeatability pilot:

| Declared category | MATCH | NO_MATCH | Reported decision count |
| --- | --- | --- | --- |
| Enrolled finger | 1 | 1 | 2 |
| Unenrolled finger | 0 | 1 | 1 |

This adds one consistent rejection observation. The sample is too small for an
accuracy claim; retry/error counts and full execution transcripts are unavailable.
No false accept has been reported in this one other-finger trial. Retain the
existing template and thresholds. The proposed next step is a small owner-run
repeatability pilot: five additional enrolled-finger trials and five with the
same unenrolled finger, recording each decision and errors separately, before
reviewing whether to extend the staged trial matrix. No such pilot or
authentication integration has been run or authorized by this result alone.

## Test 009 — qualitative owner report after the proposed pilot

The owner accepted the five-same/five-other pilot instructions and subsequently
reported that it works perfectly on 2026-10-14. Record this as positive qualitative
owner feedback. Per-attempt results, actual completed counts, error counts and
exit statuses were not supplied; do not invent a ten-trial tally or an error rate.
The earlier enrolled-finger NO_MATCH remains part of the history. The assistant
did not execute the trials or inspect biometric data.

The proposed next direction is a contained fprintd compatibility experiment,
with the experimental library kept separate and authentication configuration
unchanged. No daemon start, service override or installation has been authorized
or performed. A host-only ELF check found all 47 requested fp_* symbol names in
the experimental library; this does not establish ABI/dependency compatibility
or successful fprintd runtime behavior.
