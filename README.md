# Goodix 55a4 on Linux

Step-by-step research and development to use the **Goodix USB `27c6:55a4`**
fingerprint reader in a **Lenovo ThinkPad E14 Gen 2** on Linux.

We will first audit the community implementation, understand the protocol, and
measure its behavior. That evidence will guide whether to maintain a libfprint
patch or develop the missing components.

**Status: the owner reported the first successful sensor image, 108 x 88 pixels,
with successful driver close.** See [Test 005](docs/first-capture-test.md).
The earlier known-key write reported MATCH with firmware `GF3268_RTSEC_APP_10062`.
The stack remains a local experimental build with Nix dependencies and attributed
host-side corrections. Its first selection failure was fixed before this result.
[Private enrollment and comparison](docs/private-verification.md) now have
owner-reported results: enrollment, then one NO_MATCH and one MATCH during the
requested same-finger trials, followed by one NO_MATCH with an unenrolled
finger. The private template/manifest passed host-only
integrity checks. The owner later reported that the proposed repeatability pilot
works well; per-attempt counts and errors were not supplied. The earlier
same-finger rejection remains recorded. No accuracy or reliable authentication
claim is established. A [contained fprintd experiment](docs/private-fprintd.md)
now has **owner-reported successful hardware detection** and private session
teardown (Test013). Relay, policy-directory permissions and missing USB inventory
metadata were corrected before this result. The owner then reported completing
native enrollment; its private template/manifest passed host-only integrity and
permission checks (Test014). The owner reported one MATCH in the requested
same-finger native verification (Test015), then one NO_MATCH in the requested
other-finger trial (Test016). This completes the initial contained native
recognition experiment; repeatability and authentication reliability are not
established by those private trials. Subsequent host integration is described below.
A [contained host deployment](docs/host-deployment.md) is now installed after
separate owner agreement (Test017). The assistant observed normal-host
`fprintd-list` exposing one Goodix TLS 55X4 reader. A subsequent normal-host
right-index enrollment completed with 16 accepted stages; listing confirmed the
registered finger (Test018). An earlier enrollment failed with unknown-error and
is inconclusive. Guarded removal and a frozen Nix-backed payload remain
available. One normal-host declared-same verification reported `verify-match`
and exited0 after an earlier inconclusive unknown-error attempt (Test019).
A subsequent requested other-finger trial reported `verify-no-match`/exit1
(Test020). Host CLI NO_MATCH can mask internal errors and lacks the private
completion observer; this is initial CLI behavior, not a reliability claim.
The owner accepted these trials and declined further repetitions.
[Omarchy screen unlock](docs/lock-screen-integration.md) is now configured with
its separate fingerprint PAM service, keeping password unlock available. The owner
reported successful screen unlock with both fingerprint and password.
[Sudo and graphical SDDM login](docs/sudo-login-integration.md) are now configured
with fingerprint-first authentication and password fallback; everyday results
are not yet reported. Autologin and disk encryption remain unchanged. Polkit
fingerprint integration remains pending; earlier private templates are preserved.
This is a partial audit of community code. Sources/build products and experimental
data stay under ignored `work/`; the repository contains documentation,
small scripts, regression harnesses and attributed local patches.

## Hands-on walkthrough

Start with [the walkthrough](docs/walkthrough.md). Read `scripts/01-detect.sh`,
then run it yourself:

```sh
bash scripts/01-detect.sh
```

It displays each command and waits for Enter. We will interpret your results
together before the next experiment.

## Starting point

| Component | Status as of 2026-10-07 | Evidence |
| --- | --- | --- |
| Laptop | ThinkPad E14 Gen 2, model `20TBS10100` | Reported by the owner |
| System | Omarchy, based on Arch Linux | Reported by the owner |
| USB sensor | `27c6:55a4` | Reconfirmed with `lsusb -d 27c6:55a4` |
| libfprint | `libfprint-git 1:1.94.100.r10.g6f9479c-1` | Reconfirmed with `pacman -Q` |
| fprintd | `1.94.5-2` | Reconfirmed with `pacman -Q` |
| fprintd detection | `No devices available` | Reproduced in the [baseline test](docs/baseline-test.md) |
| Official support | Not listed when previously checked | Current upstream support remains to be checked |

USB enumeration does not demonstrate that libfprint can initialize the device.
The first milestone is detection, image acquisition, enrollment, and verification,
including rejection of fingers other than the enrolled one.

## Reading guide

1. [Preliminary community-code audit](docs/initial-audit.md): evidence, findings,
   and open questions.
2. [Sources and revisions](docs/sources.md): available code and pending reviews.
3. [Staged plan](docs/plan.md): next steps and test criteria.
4. [Baseline detection test](docs/baseline-test.md): the first local test and its limits.
5. [Pinned source review](docs/source-review.md): downloaded dependencies,
   provisioning/firmware paths, and a TLS retry finding.
6. [Owner-run firmware/key-state trial](docs/probe-test.md): observed query
   results and their limits.
7. [Contained Nix build environment](docs/nix-build.md): dependency pins,
   acquisition boundaries, cleanup, and execution evidence.
8. [First local build](docs/build-test.md): successful compilation, static ELF
   inspection, warnings and the recommended next review.
9. [TLS error correction](docs/tls-error-fix.md): local patch, isolated sanitizer
   regression tests and separately verified rebuild.
10. [Isolated library load](docs/library-load-test.md): dependency resolution and
    three basic API types without USB access or object construction.
11. [TLS and activation review](docs/tls-activation-review.md): failure paths,
    recovery limits, runtime effects and proposed offline checks.
12. [TLS flow correction](docs/tls-flow-fix.md): second patch, 24 sanitizer cases,
    negative controls and complete-unit syntax verification.
13. [First capture route](docs/first-capture-plan.md): prepared key provisioning
    experiment and the remaining capture work.
14. [Owner-run key provisioning](docs/key-provisioning-test.md): reported
    MISMATCH-to-MATCH result, cleanup and untested persistence/biometric limits.
15. [First owner-run sensor image](docs/first-capture-test.md): reported 108 x 88
    capture and close, evidence limits and proposed enrollment/verification.

Before downloading more source code, installing dependencies, or writing to the
sensor, explain the exact operation, its purpose, and its effects to the owner.
Authorization for one stage does not automatically authorize later stages.

PAM, screen unlocking, and sudo integration come after recognition testing.
Passkeys and signing-key authorization require additional integrations. fprintd
does not enable them by itself; commit signing would still use SSH or GPG keys,
with any future biometric integration authorizing their use.

## Test data

This repository is public. Publish reviewed code, methodology, and aggregate
results. Keep fingerprint images, templates, USB captures, and sensor dumps out
of Git history. `.gitignore` helps prevent accidental additions but does not
replace reviewing everything before publishing.

## Attribution

The starting point is the work by
[Hydrogell](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux),
based on [TheWeirdDev/libfprint](https://github.com/TheWeirdDev/libfprint/tree/55b4-experimental)
and [goodix-fp-dump](https://github.com/goodix-fp-linux-dev/goodix-fp-dump).
We will also evaluate [GuNanOvO/goodix-55x4-linux](https://github.com/GuNanOvO/goodix-55x4-linux).
The official project is [libfprint](https://gitlab.freedesktop.org/libfprint/libfprint).

The diagnostic probe adapts protocol framing and query definitions from the
pinned MIT-licensed dump source. Its attribution and license notice are preserved
in the script and `LICENSES/`. No community driver library is vendored here.
Review each component's license and preserve attribution before incorporating more code.

First image preparation: [operation, limits and evidence](docs/private-capture.md).
