# TLS retry and activation review — 2026-10-09

The owner accepted the [isolated load](library-load-test.md) and authorized this
focused source review. The assistant inspected existing files only: no driver
execution, compilation, new downloads, sensor access or configuration changes.
No fixes were applied in this delivery. Findings below are source evidence,
not observed hangs, crashes, key writes or biometric results on this notebook.

## Exact inputs and evidence locations

The effective files are in ignored `work/libfprint-tls-fixed/libfprint/drivers/goodixtls/`.
Their provenance is:

- Base: TheWeirdDev/libfprint commit `d1ca62a801aa565e67d1a2a47aaa7a33232b7990`.
  Relevant originals: [goodix.c](https://github.com/TheWeirdDev/libfprint/blob/d1ca62a801aa565e67d1a2a47aaa7a33232b7990/libfprint/drivers/goodixtls/goodix.c),
  [goodix55x4.c](https://github.com/TheWeirdDev/libfprint/blob/d1ca62a801aa565e67d1a2a47aaa7a33232b7990/libfprint/drivers/goodixtls/goodix55x4.c),
  [goodixtls.c](https://github.com/TheWeirdDev/libfprint/blob/d1ca62a801aa565e67d1a2a47aaa7a33232b7990/libfprint/drivers/goodixtls/goodixtls.c).
- Community patch: [Hydrogell commit fe27b48](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/patches/55a4-driver.patch),
  SHA-256 `73720a4418ed7ceb640011f51d4f2bac206118bc480ab6f1784f6618b479ef15`.
- Local [TLS error-construction patch](../patches/0001-goodixtls-safe-errors.patch),
  SHA-256 `d3187cbc8c86a3a6881411428e781be9b4a90de68f7a3ae822e1e183bb5594b7`.
- Entire canonical effective diff against the base, rechecked during this review:
  SHA-256 `aaa19320440568ba9d7a9622f1c50a47c2262f2e484e1e74e6745445a3acfb16`.

Line numbers below refer to these **effective local files**, not the shorter base
files. Each finding also identifies its base or community-patch origin. A fresh
clone has the report and local patch, but not these ignored source worktrees.
The previous constructor fix changes none of the paths below.

## Activation map

This is the driver-request sequence, not a description of every firmware-side
effect. `dev_activate()` starts the activation state machine; its successful
completion then starts TLS (`goodix55x4.c:366–448,1323–1327`).

| Phase | Operation / command | Boundary and expected stop |
| --- | --- | --- |
| Open | `goodix_dev_init()` claims interface 0, flags 0 | No detach/configuration switch in this helper; error handling is defective (R6) |
| Prepare | NOP `0x00`, chip enable `0x96`, NOP `0x00` | These precede the firmware/key checks; chip enable is already a runtime change |
| Firmware | Query `0xa8` | Accepts prefix `GF32` and substring `_RTSEC_APP_100`; this broad check accepts reported `10062`, without validating full compatibility |
| Key state | Read `0xe4`, selector `0xbb020007` | Validates success, flags, 32-byte length and expected hash; mismatch fails activation before reset/configuration/TLS |
| Reset / idle | Reset `0xa2`, idle `0x70` | Reset payload sets `reset_sensor=TRUE`, `soft_reset_mcu=FALSE`, sleep field 20 |
| Configure | Upload MCU configuration `0x90` | Uses the fixed `goodix_55x4_config` array; successful reply is required |
| TLS | Request `0xd0`, proxy TLS records through local socketpair, confirmation `0xd4` | Server uses TLS 1.2 and the known public all-zero PSK; failure/lifecycle paths need correction |
| Later image recovery | Image `0x20` receives restart `0xd0` | Recreates TLS and retries the image request; the intended two-recovery budget is broken (R1) |
| Deactivate / close | Delayed sleep `0x60`, Realtek sleep `0x92`, TLS cleanup; close attempts LED-off `0xae`, interface release | Failure completion and teardown need review/correction; no measured recovery guarantee |

Evidence: effective `goodix55x4.c:224–302,366–448,1214–1235,1282–1347`;
`goodix.c:1083–1104,1137–1188,1355–1383,1392–1414,1472–1722`;
`goodix_proto.h:31–55`, `goodix55x4.h:29–39`.

No call to `goodix_send_preset_psk_write()` or a firmware erase/update routine
was found in the inspected activation/recovery chain. The separate write helper
exists, but is not called there. MCU configuration and reset commands still
change device state: this trace does **not** establish their persistence or all
effects on firmware `10062`.

If the owner's previously reported `MISMATCH` still holds and the commands
complete as expected, this path fails at the key check. It does not provision
automatically. Removing that check would not make the zero-key TLS handshake
compatible with a different sensor key. Provisioning remains a separately scoped
persistent operation with no demonstrated original-key recovery.

## Findings and proposed offline validation

Priority describes what should be addressed before a community-driver USB trial,
not a claim of exploitability or an incident on this notebook. R1–R6 are runtime
correctness blockers; R7 concerns diagnostic privacy. All were open at the end
of this source-only review. The [subsequent flow correction](tls-flow-fix.md)
addresses R1 and tested R2 completion/result paths in a separate source variant;
R3–R7 remain open. The findings below describe the original reviewed inputs.

### R1 — Recovery budget resets during recovery

Effective `goodix.c:373–396,473–495,96–113,1417–1429`. Added by the community
patch ([lines 38–66](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/patches/55a4-driver.patch#L38-L66)
and [250–254](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux/blob/fe27b4812d60b4709d3dfb2b72f1e1f2704ede18/patches/55a4-driver.patch#L250-L254)).

On a restart reply the driver checks `reimage_tries >= 2`, increments it, then
calls `goodix_reset_state()`, which sets it to zero. Normal command completion
during the handshake calls that reset too. Repeated restarts with otherwise
advancing handshakes therefore never consume the intended budget. Merely removing
the reset at the first restart is insufficient.

Correction direction: keep the image operation's recovery budget separate from
per-command state, preserving it through handshake commands. Future validation:
inject three restart replies with intervening command completions; expect at most
two recoveries, one final error callback, and a fresh budget for a new image.

### R2 — TLS errors are lost or reported as success

Effective `goodix.c:1497–1505,1550–1568,1642–1671,1697–1702`;
`goodix55x4.c:429–437`. Inherited from the base, notably `goodix.c:1366–1375,
1419–1437,1509–1513,1559–1565` and `goodix55x4.c:313–321`.

`tls_handshake_done()` sends the successful-establishment command even when its
state machine failed. That command's callback ignores its own `error` and passes
`NULL` to the original TLS callback. Thus a proxy failure followed by confirmation,
or a confirmation timeout/send error, can be delivered as TLS success.

Other failure branches merely log and return: failed `SSL_accept`, failed TLS
initialization and `tls_activation_complete(error)` do not complete the pending
caller with that error. The initial request's error branch even sends confirmation
without its completion callback. These cases can leave activation pending.
Neither result is a biometric acceptance or rejection.

Correction direction: preserve the first error, complete the caller exactly once,
and send confirmation only after actual handshake success. Future validation:
inject failure in each phase, including confirmation ACK/timeout; require no false
success, no premature confirmation, one callback and correct error ownership.

### R3 — Teardown does not wait for the TLS worker

Effective `goodixtls.c:125–150,188`; `goodix.c:1709–1719`. Inherited from base
`goodixtls.c:128–153,191`, `goodix.c:1572–1583`.

The worker calls `SSL_accept()` and then reads its server's callback/user data.
Deinit calls `SSL_shutdown()`, frees the same SSL object and closes sockets;
the caller then frees the server, with no join or other synchronization. No
`pthread_join` or `pthread_detach` was found in these driver files. Finished
joinable workers also retain resources that are never collected.

The missing synchronization is source-confirmed. A race/use-after-free requires
teardown while the worker is still using those resources; no such crash has been
observed here. OpenSSL documents that shared objects generally cannot be used
concurrently without appropriate ownership/synchronization:
[OpenSSL 3.6 thread safety](https://docs.openssl.org/3.6/man7/openssl-threads/).

Correction direction: safely unblock the wait, establish worker completion, then
free SSL/server resources; track whether a worker was created. Future validation:
hold the worker at controlled barriers, trigger teardown and repeated start/stop
under sanitizers. Detaching alone would not resolve the shared-memory lifetime.

### R4 — Handshake waits have no complete deadline/cancellation path

Effective `goodix.c:1257–1259,1472–1487,596–597,513–525,1583,1609`;
`goodixtls.c:98–104,131`. Unbounded request/socket waits are inherited; the
community patch changes receive scheduling and retains retry-on-error behavior.

The callback-bearing TLS request uses timeout 0. Later TLS reads install no
command deadline; bulk-IN also uses timeout 0. Transport errors are retried while
the command remains waiting. Socketpair `read()`/`write()` are blocking, and reads
are called directly by the handshake state machine. The USB cancellation token
does not interrupt these local socket waits.

Silence or a persistent error can therefore leave an operation pending; a blocking
socket call can also prevent the event loop from delivering an ordinary timeout.
Correction direction: a bounded handshake deadline and cancellation/error exits,
with socket handling that permits the event loop to make progress. Future
validation: silent fake peer, repeated transport errors and cancellation at each
wait; verify bounded completion and continued event-loop activity.

### R5 — Partial TLS initialization is not safely unwound

Effective `goodixtls.c:162–188`; `goodix.c:1687–1702,1715–1719`. Inherited from
base `goodixtls.c:165–193`, `goodix.c:1551–1565`.

The server is allocated with uninitialized members. If socketpair creation fails,
SSL and descriptor fields have not been initialized; the caller logs and retains
that partial server. Later teardown uses those fields. Context configuration also
precedes its null check; SSL allocation/descriptor association and `pthread_create`
results are unchecked. A failed thread creation can still report init success.

Correction direction: initialize members, check before use, unwind only acquired
resources, and complete the caller with one error. Future validation: injected
failure at context, socketpair, SSL, descriptor association and thread creation;
assert no invalid free/close, leaks or success callback. These failures were not
injected during this source-only delivery.

### R6 — USB claim/release errors become successful open/close

Effective `goodix55x4.c:1282–1320`; `goodix.c:1392–1414,1442–1462`.
The reversed success branch is inherited from base `goodix55x4.c:788–812`;
the community patch adds the LED calls around it.

GUsb's claim and release functions return TRUE on success, confirmed in
[GUsb 0.4.9 source](https://github.com/hughsie/libgusb/blob/0.4.9/gusb/gusb-device.c#L1588-L1672).
`dev_init()` returns early on TRUE, reporting the null error as successful open.
On FALSE, it instead attempts the LED command and reports successful open with
`NULL`, discarding the real claim failure. Close similarly discards release errors.

This also corrects the earlier assumption that successful open always sends
LED-off: the successful-claim branch returns **before** that added call. The close
path attempts LED-off before releasing the interface.

Correction direction: handle FALSE as failure before issuing further commands.
Future validation: fake successful/failed claim and release; verify error reaches
completion, no LED command after failed claim, and intended LED behavior on success.

### R7 — Key-check logs/errors disclose returned hash bytes

Effective `goodix55x4.c:261–299`; inherited from base `goodix55x4.c:145–183`.
The query returns key-state/hash data, not evidence of extracting a raw secret key.
The driver hex-formats those bytes, prints them in debug, and includes them in
length/mismatch errors. `activate_complete()` logs the error message.

The owner's expected mismatch is precisely a path that includes the returned
hash in an error. Disabling debug alone does not remove that disclosure. This is
contrary to our probe's result-only approach and makes raw logs unsuitable for
sharing. No returned hash is included in this report.

Correction direction: return a generic mismatch/invalid-length error and omit
payload bytes from debug and downstream messages. Future validation: synthetic
distinctive hash bytes on match, mismatch and malformed replies; assert that no
output/error message contains the sentinel bytes.

## Limits, checks and next delivery

Checks performed: exact base/patch/combined-diff verification, numbered source
inspection, comparison with original base files, and primary dependency API
references. Documentation/link checks passed. No new runtime tests were run;
the preceding 41-test suite and successful isolated load do not exercise these
activation/handshake branches. This is a partial audit, not an upstream comparison,
complete parser/capture/matcher review or sensor compatibility certification.

Transport follow-up remains: initial ClientHello forwarding ignores the write
return; later writes check only negative results, and socket reads accept EOF as
data. Stream fragmentation/short writes need explicit validation. There is no
`SSL_get_error()` call or explicit BIO-based retry pump in these files. Do not
describe a nonexistent wrong argument to that API as a finding. Its
[documented result classification](https://docs.openssl.org/3.6/man3/SSL_get_error/)
is relevant to a future transport correction, with the current blocking sockets
accounted for.

Recommended next bounded implementation: correct R1 and R2's completion/error
flow with a focused offline harness that exercises the actual relevant functions,
including failure and repeated-restart cases. Preserve baseline inputs and build
pins separately. R3–R7 still need their own corrections and checks before any
community-driver USB trial. None of these host fixes provisions the sensor; the
reported key-state mismatch and persistent-write decision remain separate.
