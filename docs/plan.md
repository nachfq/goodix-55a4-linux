# Staged plan

Each stage ends with reviewable evidence and an explanation of the next step.
Do not use the community installer as a shortcut to combine stages.

## 0. Starting point — completed

- Record hardware and versions, distinguishing reported and verified facts.
- Identify the local revision and patch hash.
- Publish the preliminary review and open questions.
- Run the [baseline detection test](baseline-test.md) using installed software.

## 1. Complete the source audit — proposed, not yet executed

First review the remaining local patch. Then propose downloading its two required
repositories under `work/` at these exact commits:

- TheWeirdDev/libfprint: `d1ca62a801aa565e67d1a2a47aaa7a33232b7990`.
- goodix-fp-linux-dev/goodix-fp-dump: `cc43bb3b3154a0bccc0412ae024013c7e1923139`.

The proposed download would only store source files. It would not execute setup,
pip, Meson, project Python code, or USB operations. Explain the commands and agree
on this scope with the owner before downloading.

With the sources available:

- Trace `init_device → check_psk → write_psk` down to USB messages; inventory key,
  firmware, configuration, and any other persistent-state writes.
- Review framing, lengths, checksums, timeouts, cancellation, and C/C++ memory handling.
- Review the PSK, TLS negotiation, image acquisition, and SIGFM matching.
- Review build/runtime dependencies, licenses, and divergence from upstream.
- Compare GuNanOvO's alternative through a separately proposed source review.

Deliver a map of operations and concrete risks, reproducible dependencies, and an
informed decision on components to retain. Do not choose a fork or reimplementation
before this analysis.

## 2. Local build

Prepare an unprivileged build without system installation. Identify missing
dependencies and explain any proposed installation first. Check patch application,
build success, and fprintd compatibility. A successful build does not establish
that hardware operations are safe.

## 3. First community-driver access to the sensor

Explain the exact sequence and its effects first. Review initialization too:
a program described as a reader may send configuration commands. If persistent
provisioning is required, stop beforehand to present the slot, payload,
preconditions, recovery limits, and available evidence. Do not promise
reversibility without demonstrating it.

The goal is driver enumeration and controlled acquisition. Images remain in
private local storage outside Git.

## 4. Enrollment and verification without PAM integration

Define a trial matrix with a fixed target template before starting:

| Case | Expected result |
| --- | --- |
| Enrolled finger, different placements | Explicit match |
| Other, unenrolled fingers against that template | Explicit non-match |
| No finger | Wait or timeout; never acceptance |
| Cancellation or communication failure | Distinguishable error; inconclusive trial |
| Session/device restart, within already authorized operations | Repeatable behavior |

For an initial exploration, propose 20 valid attempts with the enrolled finger
and 20 with each of at least two different fingers. Record conditions, valid
attempts, acceptances, rejections, retries, and failures separately. Freeze
parameters during a series; start a new series if they change.

A false accept stops progress toward authentication integration. Zero false
accepts in a small sample does not certify a low error rate or spoof resistance.
Publish aggregate results with denominators, without images, templates, or USB
captures. Review full logs before sharing them.

## 5. Later integrations

Only after evaluating results should we propose a maintainable installation and
unlocking or sudo integration, with documented changes and recovery.
Investigate passkeys and SSH/GPG key authorization as separate integrations.
