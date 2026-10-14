# Path to the first real capture — prepared 2026-10-14

The next host fixes/build/one-image preparation were subsequently authorized;
see [the standalone capture delivery](private-capture.md). The key experiment
below is complete and should not be repeated merely to try an image.

The owner wants to try the reader, not keep treating offline checks as hardware
progress. The immediate hardware prerequisite is the expected key state. A
separate script is prepared for that operation. The owner subsequently authorized
one attempt and chose to execute the privileged command personally after the
assistant's unprivileged attempt failed before sending sensor commands. The owner
then reported **MISMATCH before writing and MATCH in the immediate postcheck**;
see [the trial](key-provisioning-test.md). No capture has been performed.

## First hardware experiment: known-key provisioning only

Read [scripts/08-provision-key.py](../scripts/08-provision-key.py). This is our
bounded script, not the community installer or full dump entry point. It reuses
our previously owner-tested query/framing helpers without adding write capability
to `03-probe-sensor.py` itself. No community Python modules are imported.

The prepared invocation from the repo root is:

```sh
sudo -- "$PWD/work/probe-venv/bin/python" "$PWD/scripts/08-provision-key.py" --write-key
```

The owner has now authorized this one-shot experiment. Do not repeat it after
an error without reviewing what happened.
Regular-user access previously failed; one-shot sudo needs no persistent udev rule.
The script has two interactive stops: before opening USB, and an exact typed
`WRITE 27c6:55a4 KEY` confirmation before the persistent write. It cannot run
unattended through a non-interactive stdin. The owner can execute it personally,
or explicitly delegate the reviewed hardware operation.

Sequence:

1. Find exactly one `27c6:55a4`, inspect its current configuration, and claim the
   reviewed interface 0 with bulk IN `0x82` / OUT `0x01`. Do not detach a kernel
   driver or switch configuration. Drain up to four input reads, then send NOP.
2. Query firmware `0xa8`; require exactly `GF3268_RTSEC_APP_10062`. A different
   version stops before writing, even if the broader community regex accepts it.
3. Query expected key state `0xe4`, read selector `0xbb020007`. Malformed replies
   stop. `MATCH` exits without a write or write-confirmation prompt.
4. On `MISMATCH`, require the exact typed confirmation. Send a **single logical
   command `0xe0`** with little-endian write flags `0xbb010003`, length 96 and the
   fixed public white-box blob. The framed message is zero-padded and split into
   two 64-byte USB writes, each with a 1-second timeout. There is no automatic retry.
5. Check acknowledgement/status, then query key state again. Report only
   `MATCH`/`MISMATCH`, never the returned device hash. Release USB resources on exit.

The value represented by this public blob is the known 32-byte all-zero PSK.
The blob is not generated from the owner's device or fingerprint. Source:
[driver_55x4.py at cc43bb3](https://github.com/goodix-fp-linux-dev/goodix-fp-dump/blob/cc43bb3b3154a0bccc0412ae024013c7e1923139/driver_55x4.py#L19-L70)
and [the write serializer](https://github.com/goodix-fp-linux-dev/goodix-fp-dump/blob/cc43bb3b3154a0bccc0412ae024013c7e1923139/goodix.py#L699-L745).
MIT attribution is preserved in the script and [LICENSES](../LICENSES/goodix-fp-dump-MIT.txt).

- Blob: 96 bytes; SHA-256 `ba1a86037c1d3c71c3af344955bd69a9a9861d9e911fa24985b677e8dbd72d43`.
- Raw write payload: 104 bytes; SHA-256 `eeccaf0a3d9516735ad56628495d1206a4a7f1e4938381818bcc39a2bd6d47cd`.

No firmware erase/update, sensor reset, TLS handshake, image capture, enrollment,
service stop/reconfiguration, PAM, sudo-authentication or lock-screen integration.
The write is described by the community author as persistent in the sensor across
OS changes; that persistence has not been demonstrated on this unit. We have no
original-key backup or demonstrated factory-state recovery. Preserving this blob
and script preserves the known-key provisioning method, not a guaranteed recovery
or the ability to choose an arbitrary replacement key.

A timeout/short transfer/error after starting the write is inconclusive: the sensor
may already have changed. Stop and inspect; do not automatically send another
write. A successful immediate `MATCH` does not prove persistence after a power
cycle or fingerprint support. Exit 3 means a post-write mismatch, not a biometric
rejection. An error does not authorize erase/update as a recovery shortcut.

## Preparation evidence

Default plan and existing `work/probe-venv` dependency check passed; PyUSB and
libusb are available. The check imports no PyUSB and opens no device. Static AST
inspection of the pinned reference extracted the blob without importing it and
confirmed its length, SHA-256 and serialized payload.

Thirteen synthetic checks cover wrong firmware, existing match, cancelled confirmation,
one write followed by private checking, post-write mismatch, ambiguous failure,
exact payload/two packets, short transfer, bad reply, repeated-write refusal and
modified-blob refusal, cleanup after failure and kernel-owner refusal. These do not prove that the firmware accepts the command.
Full offline suite: 59 Python tests passed. No new downloads or installs.

## Assistant attempt and owner handoff

After explicit authorization, the assistant invoked the unchanged script as the
regular user in a PTY. It stopped with USB error 13 at reading the active
configuration, before NOP, firmware/key queries or the write confirmation. Exit
status: 1; USB resources disposed. No key-write command was sent. A separate
`sudo -n -- true` check required a system password, so the assistant did not start
privileged provisioning. The owner requested the command to execute it in their
own terminal and supplied the successful immediate MATCH postcheck. The script
and its query helper were unchanged from the reviewed preparation; the owner-run
result and its limits are recorded in [Test 003](key-provisioning-test.md).

## After the key experiment: one private image

The owner reported an immediate post-provisioning `MATCH`. The owner subsequently
reported one acquired 108 x 88 image with successful close; see
[Test 005](first-capture-test.md). The image remains private, without installing
into fprintd or PAM. Host preparation is now complete in the separate capture
variant; [the operation/evidence report](private-capture.md) identifies exact pins
and the prepared command.

- Remaining lifetime/deadline/init/USB-error/privacy corrections relevant to this
  experiment were implemented and tested. They are host evidence, not sensor
  compatibility or a complete audit.
- The full resulting library and standalone helper compiled with existing Nix
  inputs. Their final sealed runtime passed an offline synthetic-image smoke.
  The earlier flow-only syntax evidence remains historical, not the latest build.
- The helper has private output permissions, finite stage/process limits and
  cleanup. Its reset/configuration/TLS/calibration operations are documented.
- **Completed by the owner after preparation:** one corrected hardware trial
  returned a 108 x 88 image and reported successful close. No image, USB dump or
  raw log was published. Repeatability and image quality remain unmeasured.

Acquisition now has one successful trial. The next proposed experiment is enrollment and explicit verification
against the enrolled finger and other fingers. No matching result has been observed.
The preparation agreement does not authorize executing every later step, acquiring
packages or making additional persistent writes.
