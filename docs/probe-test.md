# Test 002: bounded firmware and expected-key-state query

Evidence recorded on 2026-10-08 from output supplied by the owner. Hardware:
ThinkPad E14 Gen 2, Goodix USB `27c6:55a4`. The owner ran the experiment;
the assistant did not execute it on the sensor.

## Scope and observed results

The repository's [probe](../scripts/03-probe-sensor.py) claims the existing bulk
interface, drains bounded pending input, sends NOP, queries firmware (`0xa8`),
and queries expected key state (`0xe4`, selector `0xbb020007`). It implements no
key/firmware write, sensor reset, TLS handshake, capture, or enrollment path.

The owner prepared an ignored Python environment under `work/probe-venv` with
PyUSB `1.3.1`. A regular-user run failed while opening the device with
`[Errno 13] Access denied (insufficient permissions)`. That failed attempt did
not reach the vendor-query steps.

A subsequent run used one-shot sudo with that environment and the same script:

```sh
sudo -- "$PWD/work/probe-venv/bin/python" "$PWD/scripts/03-probe-sensor.py" --run
```

This command records the completed trial, not a request to repeat it or extend
privileged access. No persistent permission rule was introduced.

| Observation | Owner-reported result |
| --- | --- |
| Interface claim | Interface `0`; bulk IN `0x82`, OUT `0x01` |
| NOP | No response; permitted by the reference behavior and probe |
| Firmware query | `GF3268_RTSEC_APP_10062` |
| Expected key state | `MISMATCH` |
| Cleanup | `USB resources released.` |

The reported output does not include the shell exit status. The script specifies
exit status `3` for a completed query with mismatch; that status was not separately
observed. No returned hash, fingerprint data, or raw USB capture is stored here.

## Interpretation and limits

The bounded transport successfully obtained firmware and key-state responses on
this laptop in that trial. `MISMATCH` means the returned state differed from the
probe's public expected hash. It does not establish an absent key, a defective
reader, or a biometric rejection. No finger recognition was attempted.

Static inspection shows the assembled driver accepts the reported firmware-family
string but requires the expected key state during activation. Passing a string
check is not proof that every command is compatible with firmware `10062`.
The pinned full dump entry point instead targets `10041` and can erase another
valid-family firmware. See the [pinned source review](source-review.md), especially
its firmware and provisioning paths; do not substitute that entry point for this
bounded probe.

Neither original-key recovery nor full firmware-side effects have been
demonstrated. The probe does not perform persistent writes from the host side,
but this trial is not a complete audit of sensor firmware behavior. Compilation
is the next separate experiment; provisioning and community-driver hardware
execution remain outside its scope.
