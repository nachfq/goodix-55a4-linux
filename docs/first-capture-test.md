# Test 005: first owner-reported sensor image

The owner supplied the successful output on 2026-10-14 after repeating the
prepared capture command with the corrected USB descriptor validation. This
is owner-reported execution, not an assistant-run hardware test.

Reviewed outcome excerpt, omitting the private path:

```text
Constructing the selected reader.
Opening its existing interface without detaching a kernel driver.
Activation/calibration started.
Remove your finger now. Acquisition is still pending; waiting for finger-up and cleanup.
Closing the reader; remove your finger.
The driver reported successful close.
One image received: 108 x 88 pixels.
```

The full owner output also reported a private PGM path. No image, trial-directory
identifier, pixel hash, template, raw USB trace or unreviewed native log is
included here. The assistant did not open or inspect that file, requery the
reader, or repeat acquisition. The shell exit status was not supplied.

## What this establishes

- The previously failing selection check passed for the reported trial.
- The selected driver opened, completed its capture API operation and reported
  successful close. The launcher reported one **108 x 88** image after checking
  the saved PGM header, dimensions, size, owner and private permissions.
- In the prepared code, the successful capture route requires firmware/key
  checks, activation, actual TLS establishment/decryption, calibration, image
  delivery and finger removal. The supplied result is consistent with that route
  succeeding on this sensor. Those individual phases are inferred from the
  implementation; the output is not an independent packet trace of each command.

Inputs remain those of [the corrected selection experiment](capture-selection-test.md):
libfprint base `d1ca62a801aa565e67d1a2a47aaa7a33232b7990`, community patch and
local patches 0001–0003, unchanged library SHA-256
`e37a3d6e7d6eefd35f201643d6cc399ba6317d9a19b527e83e252dc05f211098`,
corrected executable SHA-256
`2a78efe686dbdb3104eb7e17399f94e065a3414813a71ad0d1afc3f1a0479570`.
The launcher verifies and freezes those artifact bytes before execution. This record
assumes the owner used that prepared command; no additional provenance claim
is made from the pasted excerpt alone.

## Limits and next experiment

This is one successful image acquisition, not enrollment or biometric recognition.
The owner subsequently reported viewing the private image and that it resembles
a fingerprint. The assistant did not inspect the pixels; no objective image-quality
assessment or recognition test was performed. Repeatability across captures or
power cycles remains unmeasured. It does not establish original-key recovery,
Windows compatibility, a complete audit or reliable authentication.

The prepared experiment does not enroll/save templates, call fprintd, install a
driver or change PAM/sudo-authentication/locking. Its documented runtime commands
and limits are in [the operation report](private-capture.md).

Next proposed delivery: prepare local enrollment and controlled verification
using a private host-side template, then test the registered finger and other
fingers separately. Count timeouts/transport/processing errors as inconclusive;
only a completed verification with a no-match result is a biometric rejection.
Agree that next scope before implementation or execution; do not add authentication
integration or repeat key provisioning based on this capture result.
