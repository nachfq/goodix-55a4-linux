# Image retry budget and TLS completion correction — 2026-10-13

The owner authorized correcting the retry counter and TLS error flow after the
[activation review](tls-activation-review.md). This delivery applies a separate
patch and executes offline tests using existing sources/tooling. It does not
access the reader, provision its key, install anything or execute a TLS handshake.

## Read the change

Start with [0002-goodix-tls-flow.patch](../patches/0002-goodix-tls-flow.patch).
It applies after the community patch and our first error-construction correction.

The image recovery count now belongs to a logical image request. Normal command
resets preserve it, including the commands exchanged while reconnecting TLS.
A new image request starts with zero; terminal image completion or failed recovery
ends that budget. Two reconnect attempts are permitted; a third restart reply
produces one terminal error. Internal retries bypass the new-request entry point.

TLS completion uses one helper which takes and clears the pending callback and
poll source before calling the owner. It propagates reported initialization,
request, proxy and confirmation errors. It rejects incomplete ClientHello
forwarding, short proxy writes and EOF. The activation callback now forwards
errors to libfprint instead of logging and returning without completion.

The worker publishes its error followed by an atomic result; it never calls a
device completion or changes the state machine. The main-context poll observes
the result. An extra final state waits for worker success as well as successful
proxy progress before sending the TLS confirmation. For worker failure during
an asynchronous USB wait, error delivery first clears the registered command
callback, preventing it from later targeting an already-freed state machine.
Official references for the publication barrier:
[GLib atomic set](https://docs.gtk.org/glib/func.atomic_int_set.html) and
[atomic get](https://docs.gtk.org/glib/func.atomic_int_get.html).

The server is zero-initialized with invalid descriptor sentinels, and cleanup
guards absent resources. These guards are necessary when a reported init failure
now completes the caller and can lead to close. They do not fix every unchecked
allocation/thread-creation path in R5 or the concurrent teardown in R3.

## Preserved inputs and separate source

Base commit: `d1ca62a801aa565e67d1a2a47aaa7a33232b7990`.
Community and first-fix pins are unchanged; see the [patch inventory](../patches/README.md).
The new worktree is `work/libfprint-flow-fixed`.

Second-patch SHA-256:
`23a4dd473eb2b377938b5201a115943da67744473c1dd3c276ce5b36165344aa`.
Combined canonical diff against the base:
`a632e29b42495053b1bd4320c6d29b25cf4c7135f325e19f66d4dc897be02134`.

The assistant created the separate detached worktree from the existing clean
base, applied the existing community and first patches, then developed the second
patch there. Applicability to `work/libfprint-tls-fixed` is checked read-only.
Baseline and first-fixed sources/builds remain preserved. Their existing build
and sandbox-load scripts still target their original inputs; neither has silently
switched to this variant.

No complete shared library was rebuilt or loaded for this delivery. Syntax checks
reuse the prior build's generated headers and flags, substituting the separate
flow-fixed source. The runner pins local `compile_commands.json` and `config.h`:

- Compilation metadata: `806c48cb0e9a610c0b0b8633417c186e8df91a4d99bd8937526aed6065831c8a`.
- Configuration header: `da687355004242049fbd1f92f7a575b30a79e3de0e3a0aa15b473cc714e55a5d`.

These are local generated-input pins, not a cross-machine reproducibility claim.
A fresh clone has no downloaded worktrees or generated headers. The runner
refuses missing/changed inputs rather than acquiring or repairing them.

## Offline experiment and observed results

Read [scripts/07-test-tls-flow.py](../scripts/07-test-tls-flow.py) and
[the harness](../tests/tls-flow-harness.c). Default mode prints the plan;
`--check-inputs` checks source pins and applicability without compilation.
`--run` requires existing Nix Python, regular-user execution and prior metadata.

The runner extracts actual functions/private structures from the pinned effective
files, preserving their notices in ignored generated units. Real GLib errors and
atomics are linked. Device completion, USB framing/transport, local socket results,
server initialization and state-machine scheduling are synthetic stand-ins.
The fake SSM models synchronous transitions/completion; this is not a test of
libfprint's real event loop, worker thread, OpenSSL negotiation or sensor firmware.

Observed final result, exit 0:

- Syntax checks passed for complete `goodix.c`, `goodix55x4.c` and `goodixtls.c`
  translation units with the prior generated configuration; no object files or
  dependency files were produced. Existing compiler warnings remain.
- **24 isolated C cases passed with ASan/UBSan**, including two successful
  reconnects followed by a third restart, preserved budget across intermediate
  commands, new/terminal request reset, phase/confirmation failures, short writes,
  EOF, pending/failed/successful worker results, activation errors, callback reentry
  and duplicate finalization. The worker result is injected, not a real handshake.
- Two negative controls restored one original function at a time within the
  otherwise fixed test unit. Original `goodix_reset_state()` failed the retry-budget
  assertion; original `on_tls_successfully_established()` failed the confirmation-error
  assertion. This checks that the regressions detect those defects; it is not
  execution of the entire original driver.
- **46 Python offline tests passed**, including five new runner refusal checks.
  These do not compile or load the community library.

Temporary generated sources/executables are removed. The assistant saved a local
review log under ignored `work/nix/tls-flow-tests.log`; the runner saves no logs
itself. No biometric data or raw device output was produced.

To inspect the plan from a normal terminal:

```sh
python3 scripts/07-test-tls-flow.py --plan
```

The actual trial used the existing verified cached Nix input with substitution
disabled, as in [the preceding load trial](library-load-test.md#read-or-repeat),
with `--run 'python3 -B scripts/07-test-tls-flow.py --run'`. No additional
packages were acquired. Nix activation is outside an execution sandbox; this
experiment runs an isolated-function harness, not the full driver.

## Remaining limits and next step

R1 and the tested R2 completion/worker-result flow are corrected in this separate
source variant. R3–R7 remain open. In particular, the 10 ms poll is a result
notification mechanism, not a deadline. Blocking socket calls can still prevent
it from running (R4). Cancellation/teardown while the worker is active remains
unsafe (R3), and no full initialization-fault injection was performed (R5).
Remaining stream fragmentation, cancellation and concurrency cases need work.

The previous library-load success belongs to the previous artifact, not this new
patch. These results establish offline flow behavior and C syntax, not full
linking, fprintd compatibility, capture, registration or matching.

Next proposed delivery: correct worker lifetime/teardown with controlled offline
concurrency tests before any new full-library runtime or community-driver USB
trial. The reported `MISMATCH` remains separate; no host fix changes the sensor key.
