# Test 003: owner-run known-key provisioning — 2026-10-14

Evidence supplied by the owner after executing the previously reviewed
[08-provision-key.py](../scripts/08-provision-key.py) with one-shot sudo.
The owner explicitly authorized one persistent write, entered its typed
confirmation and provided the terminal output. The assistant did not perform
the privileged trial or independently query the device afterward.

| Step | Owner-reported result |
| --- | --- |
| Firmware query | `GF3268_RTSEC_APP_10062` |
| Expected key state before write | `MISMATCH` |
| Typed confirmation | `WRITE 27c6:55a4 KEY` |
| Expected key state after write | `MATCH` |
| Cleanup | `USB resources released.` |

Reviewed outcome excerpt:

```text
Firmware: GF3268_RTSEC_APP_10062
Expected key state: MISMATCH.
Expected key state after write: MATCH
USB resources released.
```

The script sends the fixed public 96-byte blob with command `0xe0`, write flags
`0xbb010003`, then queries state using `0xe4` / `0xbb020007`. It reaches the
post-write result only after checking the write acknowledgement and successful
status. The reported run therefore establishes immediate expected-key-state
evidence after that operation, assuming the reviewed script was used.
See [the operation report](first-capture-plan.md) for exact payload hashes,
timeouts, source attribution and limits. No device hash or biometric data was
included in the owner's output or this report.

The terminal excerpt does not include the shell exit status. The script specifies
0 for the successful path; that status was not separately observed. No automatic
retry was reported or performed by the assistant. Its earlier regular-user attempt
failed with USB permission error 13 before sending any vendor command.

## What this changes

The expected key-state prerequisite was met in this trial. The previously
observed mismatch no longer blocks a subsequent attempt to establish the driver's
TLS session on the basis of this immediate observation. Do not write the key again
merely to repeat this result; a read-only query can inspect the state if needed.

This does **not** demonstrate a real TLS handshake, persistence after power cycling,
restoration of the prior state, arbitrary key replacement, Windows coexistence,
image capture, enrollment, verification or authentication support. The firmware
identifier reported before writing matches the previous query trial; no firmware
erase/update or reset command is implemented by the provisioning script.

Next proposed work: prepare the first standalone private capture by addressing
the remaining driver lifetime/deadline/init/USB-error/privacy findings, building
the complete corrected library and preparing bounded acquisition without service
installation or PAM. Explain its reset/configuration/capture operations before
hardware execution; this one-write authorization does not authorize those stages.
