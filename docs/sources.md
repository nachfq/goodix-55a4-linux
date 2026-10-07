# Sources and revisions

Inventory date: 2026-10-07. Hydrogell's existing local copy and the two pinned
dependencies have been inspected within the scope of the
[source review](source-review.md). Downloads are stored under ignored `work/`.

| Project | Revision | Status |
| --- | --- | --- |
| [Hydrogell/goodix-27c6-55a4-fingerprint-linux](https://github.com/Hydrogell/goodix-27c6-55a4-fingerprint-linux) | `fe27b4812d60b4709d3dfb2b72f1e1f2704ede18` | Local copy inspected; clean Git working tree |
| [TheWeirdDev/libfprint](https://github.com/TheWeirdDev/libfprint/tree/55b4-experimental) | `d1ca62a801aa565e67d1a2a47aaa7a33232b7990` | Downloaded and HEAD verified; activation/TLS paths reviewed; patch application checked |
| [goodix-fp-linux-dev/goodix-fp-dump](https://github.com/goodix-fp-linux-dev/goodix-fp-dump) | `cc43bb3b3154a0bccc0412ae024013c7e1923139` | Downloaded and HEAD verified; initialization, PSK, and firmware entry points reviewed; firmware submodule not downloaded |
| [GuNanOvO/goodix-55x4-linux](https://github.com/GuNanOvO/goodix-55x4-linux) | Pending | Reported alternative; not audited |
| [Official libfprint](https://gitlab.freedesktop.org/libfprint/libfprint) | Pending | A current comparison baseline has not been selected |

The local `patches/55a4-driver.patch` contains 1290 lines and has this SHA-256:

```text
73720a4418ed7ceb640011f51d4f2bac206118bc480ab6f1784f6618b479ef15
```

The hash identifies the reviewed content; it does not establish authorship or
safety. Stars, activity, and published results do not replace code review or
independent tests. Their current values have not been checked.

The `LICENSE` file in Hydrogell's copy and `COPYING` in the libfprint base contain
LGPL 2.1. The reviewed libfprint 55x4 driver header specifies LGPL 2.1 or later.
The dump repository's root license is MIT. This does not complete the licensing
review of individual files, dependencies, or future derived components.
