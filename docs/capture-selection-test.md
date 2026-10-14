# Test 004: capture attempt stopped at USB selection

Owner-reported on 2026-10-14 after running the prepared one-shot sudo command:

```text
Type CAPTURE 27c6:55a4 ONE IMAGE to begin, or anything else to stop: CAPTURE 27c6:55a4 ONE IMAGE
Capture trial failed at USB_SELECTION; no biometric rejection can be inferred.
Capture stopped: Capture/close did not complete successfully; trial is inconclusive
```

The native helper reached descriptor discovery/selection, but not its INIT,
OPEN or CAPTURE stages. No selected libfprint device was constructed, and its
Goodix activation commands, TLS, calibration and image acquisition were not run.
The library was loaded by the process; this is distinct from its driver accessing
the sensor. The excerpt does not give a shell exit status or prove exactly which
part of the combined selection check failed. No key state was rechecked here;
the latest reported MATCH still belongs to the prior provisioning trial.

## Confirmed host-side bug and correction

The original helper treated `g_usb_endpoint_get_kind()` as `bmAttributes` and
checked `(kind & 3) == 2` to require bulk transfer. In cached GUsb 0.4.9 this
getter reads `bDescriptorType`, whose value for an endpoint descriptor is 5.
Consequently a valid bulk endpoint fails the old test: `(5 & 3) != 2`.
This is a confirmed validation defect, capable of producing USB_SELECTION on a
valid reader. The generic pasted result alone does not prove that every earlier
selection/open/configuration check succeeded.

Local primary evidence: disassembly of the unchanged cached GUsb 0.4.9 library's
`_g_usb_endpoint_new` copies the libusb endpoint descriptor into the object;
`g_usb_endpoint_get_kind` reads its byte at descriptor offset 1. The existing
libusb header defines that byte as `bDescriptorType`, and `bmAttributes` at offset
3. This refines the ambiguous GIR description “type of endpoint”; no additional
source repository or package was downloaded.

The corrected [helper](../scripts/helpers/capture-one.c) uses libusb's active
configuration descriptor directly. It ties the lookup to the GUsb-selected
reader's bus/address and exact VID/PID, requires the same configuration value,
interface 0/alternate 0, reviewed class, and exactly two bulk endpoints `0x82`
and `0x01`. It never opens a second libusb device handle, switches configuration,
detaches a kernel driver, claims an interface or sends vendor commands during
this precheck. The initial GUsb descriptor handle is closed before construction
of the fingerprint device. Later driver activation effects are unchanged.

Selection failures now have fixed distinct categories: missing/multiple readers,
open, configuration, descriptor retrieval, layout or precheck-close failure.
Native diagnostics remain suppressed; no strings returned by the device or raw
logs are exposed. The same capture invocation/typed confirmation remains in use.

## Checks and current artifacts

This focused fix changes the helper/launcher/build recipe only. The complete
driver library and patch0003 remain unchanged. Its prior independent review
covers the earlier helper, not this subsequent correction. This correction was
checked directly by the implementer; no new independent review is claimed.

- Helper rebuilt with existing Nix inputs, including already cached libusb 1.0.29
  development metadata, with `-Wall -Wextra -Werror`; exit 0, static ELF inspection.
- Twenty focused Python checks passed, including safe USB failure reports.
- Complete corrected helper/library passed the existing isolated sealed runtime
  smoke. Its actual synthetic descriptor test accepts descriptor type 5 with
  bulk attributes 2 and rejects interrupt transfer, wrong endpoint, missing
  endpoint, wrong alternate/class and inactive configuration. Finger-lift,
  private synthetic PGM and exclusive-write checks also passed. No host USB access.
- Source/artifact pins and whitespace checks passed. The old executable is
  preserved under ignored `work/capture-one-build/capture-one-before-usb-fix`.

Current helper-source SHA-256:
`568ae51c97ab53987039264bbed4e871878501a9760a50e83ddba051e4724741`.
Current executable SHA-256, 28192 bytes:
`2a78efe686dbdb3104eb7e17399f94e065a3414813a71ad0d1afc3f1a0479570`.
Unchanged library SHA-256:
`e37a3d6e7d6eefd35f201643d6cc399ba6317d9a19b527e83e252dc05f211098`.

No corrected physical trial was run by the assistant. The owner subsequently
reported selection and image acquisition success; see [Test 005](first-capture-test.md).
The failed trial above remains historical evidence. Enrollment, verification,
power-cycle persistence and original-state recovery remain untested.
