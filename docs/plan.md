# Staged plan

Each stage ends with reviewable evidence and an explanation of the next step.
Do not use the community installer as a shortcut to combine stages.

## 0. Starting point — completed

- Record hardware and versions, distinguishing reported and verified facts.
- Identify the local revision and patch hash.
- Publish the preliminary review and open questions.
- Run the [baseline detection test](baseline-test.md) using installed software.

## 1. Complete the source audit — in progress

The owner authorized downloading the two required repositories under ignored
`work/`. Both exact commits have now been fetched and checked:

- TheWeirdDev/libfprint: `d1ca62a801aa565e67d1a2a47aaa7a33232b7990`.
- goodix-fp-linux-dev/goodix-fp-dump: `cc43bb3b3154a0bccc0412ae024013c7e1923139`.

The download only stored sources. No setup, pip, Meson, project Python code, or
USB operation was executed. The patch applies to the pinned base and is assembled
in a separate ignored worktree. The [focused source review](source-review.md)
documents initialization, key provisioning, firmware entry points, and a TLS
retry defect. A narrow firmware/key-state diagnostic is now prepared in
`scripts/03-probe-sensor.py`, with offline tests. Its plan and dependencies are
described in the [walkthrough](walkthrough.md).
The owner subsequently ran that diagnostic and reported firmware
`GF3268_RTSEC_APP_10062` and expected key state `MISMATCH`; see the
[recorded trial](probe-test.md). This completes the bounded query,
not capture, enrollment, or verification.

Continue the audit:

- Extend the completed `init_device → check_psk → write_psk` trace to the remaining
  capture paths; assess firmware-side effects and recovery limits.
- Review framing, lengths, checksums, timeouts, cancellation, and C/C++ memory handling.
- Review the PSK, TLS negotiation, image acquisition, and SIGFM matching.
- Review build/runtime dependencies, licenses, and divergence from upstream.
- Compare GuNanOvO's alternative through a separately proposed source review.

Deliver a map of operations and concrete risks, reproducible dependencies, and an
informed decision on components to retain. Do not choose a fork or reimplementation
before this analysis.

## 2. Local build

The following records the build/review progression. Later owner-run acquisition
evidence is recorded in stage 3 below; early “untested” statements describe their
individual preparation checkpoints.

The selected next delivery is specified in the
[local build initiative](../.agent-context/plans/local-driver-build/plan.md).
It prepares an owner-run walkthrough; compilation and any prerequisite
installation remain separate review points.

On 2026-10-09, after the owner delegated execution and authorized Nix dependency
acquisition, the first library compilation completed successfully. See the
[build trial](build-test.md) for exact inputs, warnings and static inspection.
The TLS error-construction defect found during compilation should be addressed
before loading the driver. Hardware and fprintd runtime compatibility remain
untested.

The owner subsequently authorized the narrow constructor correction. Its
[separate patch and trial](tls-error-fix.md) passed sanitizer checks and a full
rebuild. The TLS retry defect and remaining warnings still need review before
community-driver hardware execution.

The separately authorized [isolated load trial](library-load-test.md) passed
dependency resolution and three GType checks, with no USB access or object
construction. This supplies bounded library-runtime evidence; sensor execution
and fprintd compatibility remain untested.

The owner subsequently authorized [focused TLS/activation review](tls-activation-review.md).
It reconfirmed the broken retry budget and documented six additional failure,
lifetime and diagnostic findings. No fixes were applied. The proposed next
implementation corrects retry/completion with offline failure checks; other
findings must also be addressed before community-driver USB execution. The
reported key mismatch is a separate prerequisite, without automatic provisioning.

On 2026-10-13 the owner authorized the [retry/completion correction](tls-flow-fix.md).
Its separate source passed 24 actual-function sanitizer cases, two original-function
negative controls, complete-C-unit syntax checks and 46 Python offline tests. No
complete new library was rebuilt or loaded; worker teardown and remaining findings
still need correction before community-driver USB execution.

Prepare an unprivileged build without system installation. Identify missing
dependencies and explain any proposed installation first. Check patch application,
build success, and fprintd compatibility. A successful build does not establish
that hardware operations are safe.

The owner subsequently performed the separately authorized known-key write with
our standalone script and reported an immediate `MATCH` postcheck; see
[Test 003](key-provisioning-test.md). At that checkpoint no driver TLS handshake
or image capture had run. The later acquisition result is recorded below;
power-cycle persistence and original-state recovery remain untested.

## 3. First community-driver access to the sensor — one successful owner trial

After separate host corrections/build and a helper descriptor fix, the owner
reported one 108 x 88 image and successful close; see
[Test 005](first-capture-test.md). This completes the first acquisition milestone,
not image-quality/repeatability assessment, enrollment or verification. The
assistant did not run that hardware trial or inspect its private image.

Explain the exact sequence and its effects first. Review initialization too:
a program described as a reader may send configuration commands. If persistent
provisioning is required, stop beforehand to present the slot, payload,
preconditions, recovery limits, and available evidence. Do not promise
reversibility without demonstrating it.

The goal is driver enumeration and controlled acquisition. Images remain in
private local storage outside Git.

## 4. Enrollment and verification without PAM integration

The owner accepted [private experiment preparation](private-verification.md)
after the first image. A separate corrected source/build preserves the capture
variant. The owner subsequently completed standalone and private native
enrollment/verification; normal-host CLI trials and screen unlock followed.
See the linked reports for outcomes and their evidentiary limits.


Define a trial matrix with a fixed target template before starting:

| Case | Expected result |
| --- | --- |
| Enrolled finger, different placements | Explicit match |
| Other, unenrolled fingers against that template | Explicit non-match |
| No finger | Wait or timeout; never acceptance |
| Cancellation or communication failure | Distinguishable error; inconclusive trial |
| Session/device restart, within already authorized operations | Repeatable behavior |

The original exploratory proposal below is preserved as a possible future
measurement protocol. The owner accepted the practical initial results and
explicitly declined further test rounds; it is not a current requirement.

For an initial exploration, the proposal was 20 valid attempts with the enrolled finger
and 20 with each of at least two different fingers. Record conditions, valid
attempts, acceptances, rejections, retries, and failures separately. Freeze
parameters during a series; start a new series if they change.

A false accept stops progress toward authentication integration. Zero false
accepts in a small sample does not certify a low error rate or spoof resistance.
Publish aggregate results with denominators, without images, templates, or USB
captures. Review full logs before sharing them.

## 5. Later integrations

The separately reviewed [contained installation](host-deployment.md) is complete.
The owner reported [screen unlock](lock-screen-integration.md) worked with both
methods; [sudo/SDDM](sudo-login-integration.md) are configured with password
fallback and private originals. Live sudo/login outcomes remain unreported.
Investigate passkeys and SSH/GPG key authorization as separate integrations.
