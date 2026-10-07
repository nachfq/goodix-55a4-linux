# Goodix 55a4 on Linux

Step-by-step research and development to use the **Goodix USB `27c6:55a4`**
fingerprint reader in a **Lenovo ThinkPad E14 Gen 2** on Linux.

We will first audit the community implementation, understand the protocol, and
measure its behavior. That evidence will guide whether to maintain a libfprint
patch or develop the missing components.

**Status: source audit in progress; baseline detection test completed. There is no custom driver
or tested community installation on this laptop yet.** This repository currently
contains original documentation, without vendored drivers or installers.

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

No third-party code has been incorporated yet. Review each component's license
and preserve attribution before doing so.
