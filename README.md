# Goodix 55a4 on Linux

Step-by-step research and development to use the **Goodix USB `27c6:55a4`**
fingerprint reader in a **Lenovo ThinkPad E14 Gen 2** on Linux.

We will first audit the community implementation, understand the protocol, and
measure its behavior. That evidence will guide whether to maintain a libfprint
patch or develop the missing components.

**Committed stage 6:** Private enrollment and comparison are available, with owner-reported same/other outcomes; this does not establish accuracy.

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

## Implemented follow-up stages

- [build(nix): pin dependencies and record the first local build](docs/nix-build.md)
- [fix(tls): harden error construction and isolate library loading](docs/tls-error-fix.md)
- [fix(tls): bound image retries and propagate completion errors](docs/tls-flow-fix.md)
- [feat(provision): guard one-shot sensor key provisioning](docs/key-provisioning-test.md)
- [feat(capture): bound private acquisition and record the first image](docs/private-capture.md)
- [feat(verify): add private enrollment and controlled comparison](docs/private-verification.md)
