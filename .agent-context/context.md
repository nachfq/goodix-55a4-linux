# Project context

## Purpose and ownership

The owner is investigating Goodix USB `27c6:55a4` on a ThinkPad E14 Gen 2.
This is a hands-on learning project with a practical goal: establish device
access, fingerprint acquisition, enrollment, and verification, including explicit
rejection of other fingers, before authentication integration.

The owner wants to understand and personally run each experiment. Small scripts
are part of the learning experience, rather than merely automation. The initial
conversation chose to audit community work before deciding between maintaining a
libfprint-based implementation and developing missing components. Neither choice
has been made. The audit remains partial.

The public repository is [nachfq/goodix-55a4-linux](https://github.com/nachfq/goodix-55a4-linux).
On 2026-10-08, the owner explicitly chose versioned project context suitable for
that public repository.

## Orientation

- [README](../README.md): project scope and starting hardware/software facts.
- [Walkthrough](../docs/walkthrough.md): interactive scripts and documented
  offline test command. Tests of synthetic packets do not establish hardware support.
- [Sources](../docs/sources.md): pinned revisions and licensing inventory.
- [Source review](../docs/source-review.md): reviewed initialization, provisioning,
  firmware paths, and an unresolved TLS retry defect.
- [Probe trial](../docs/probe-test.md): the owner's completed bounded query and
  its evidentiary limits.
- [Staged plan](../docs/plan.md): existing progression, with later stages still
  subject to separate agreement.
- [Local build initiative](plans/local-driver-build/plan.md): the agreed next
  preparation delivery and its boundaries.

Downloaded community sources and the assembled patch live under ignored `work/`;
they are not supplied by a fresh clone of this repository. The repository's own
probe implements a bounded query path instead of importing community utilities.

## Evidence that changes the next decision

The installed stack sees the USB device but exposes no usable reader through
fprintd; see the [baseline](../docs/baseline-test.md).

On 2026-10-08, the owner supplied output from personally running
[`03-probe-sensor.py`](../scripts/03-probe-sensor.py). Regular-user access failed
with USB permission error 13. A subsequent run through one-shot sudo reported
firmware `GF3268_RTSEC_APP_10062` and expected key state `MISMATCH`, followed
by USB resource cleanup.

This is owner-reported execution evidence, not an assistant-run hardware test.
`MISMATCH` means the returned state differed from the probe's public expected
hash; it does not prove the key is absent or the sensor is broken. No capture,
enrollment, or biometric verification has been demonstrated.

Static inspection of the assembled driver shows its firmware-string check accepts
this reported family, but its activation requires the expected key state. That is
a prerequisite check, not evidence of complete firmware compatibility. In contrast,
the pinned full dump entry point targets firmware `10041` and can erase another
valid-family version. It must not be substituted for this query probe. See the
[source review](../docs/source-review.md) and its pinned source links.

The completed bounded query is distinct from community-driver hardware execution;
the latter and the biometric tests remain unperformed.

## Consequential decisions and unresolved questions

In the conversation preceding discovery, the owner agreed to preparation of an
unprivileged local build. That bounded agreement does not authorize additional
package installations, persistent provisioning, or running the community driver
on hardware.

Recovery of the original sensor key and Windows coexistence have not been
demonstrated. Separate key selectors and third-party success reports do not settle
those questions. On 2026-10-08, the owner stated that they do not use Windows and
do not require Windows compatibility. This removes it as a project requirement;
it is not authorization to write a key or evidence of recoverability.

The matching behavior, remaining capture paths, memory handling, upstream
divergence, and complete dependency/license review remain open. A successful build
will establish compilation only. Maintaining a fork or reimplementing components
remains a later evidence-based decision.

The owner's eventual interests include local authentication, web logins, and
authorizing signing-key use. These are distinct integrations: fprintd alone does
not enable passkeys, and commit signing still requires SSH or GPG keys. They are
outside the initial recognition milestone.

## Related projects

Consult the [source inventory](../docs/sources.md) for exact revisions and URLs:
Hydrogell supplies the community patch and wrappers; TheWeirdDev supplies its
libfprint base; goodix-fp-dump supplies protocol and provisioning references.
GuNanOvO is an unaudited alternative, and official libfprint is the future upstream
comparison target. These sources inform this project; none is established as a
trusted installation path by this partial review.

## Committed follow-up progress

- The pinned Nix dependency environment and first local compilation are documented. This is build evidence, not reader support. See [stage report](../docs/nix-build.md).

This commit series groups completed work by functional stage using corrected
implementations; it does not recreate earlier failing code or authorize new trials.
