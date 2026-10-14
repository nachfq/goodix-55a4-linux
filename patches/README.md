# Local driver corrections

Apply `0001-goodixtls-safe-errors.patch` after the previously reviewed Hydrogell
community patch, on libfprint commit
`d1ca62a801aa565e67d1a2a47aaa7a33232b7990`. The correction changes only
`err_from_ssl()` in `libfprint/drivers/goodixtls/goodixtls.c`. GLib constructs
the error with a valid libfprint domain and general error code, a copied message,
and a fallback when OpenSSL has no registered reason. The original OpenSSL code
remains in the message rather than being truncated into `GError.code`.

Fix SHA-256: `d3187cbc8c86a3a6881411428e781be9b4a90de68f7a3ae822e1e183bb5594b7`.
Combined canonical diff SHA-256:
`aaa19320440568ba9d7a9622f1c50a47c2262f2e484e1e74e6745445a3acfb16`.

This patch modifies LGPL-2.1-or-later code by Alexander Meiler and Matthieu
CHARETTE (2021). Their source notices remain intact; the license is preserved
in [LICENSES/libfprint-LGPL-2.1.txt](../LICENSES/libfprint-LGPL-2.1.txt).
Upstream file: [pinned goodixtls.c](https://github.com/TheWeirdDev/libfprint/blob/d1ca62a801aa565e67d1a2a47aaa7a33232b7990/libfprint/drivers/goodixtls/goodixtls.c).
No driver source or compiled library is vendored in this repository.

See [the correction trial](../docs/tls-error-fix.md) for assembly, tests,
build instructions, and remaining limits. Do not apply this on top of an
already fixed tree, silently replace source changes, or reuse the baseline build.

## Second correction: image budget and TLS completion

`0002-goodix-tls-flow.patch` applies after `0001` and preserves that source/build.
It separates the image recovery count from per-command reset, propagates phase
and confirmation errors, and gates success on the worker's published outcome.
Minimal absent-resource guards support completion of reported init failures.
Concurrent teardown, deadlines and full init robustness remain pending.

Second-patch SHA-256: `23a4dd473eb2b377938b5201a115943da67744473c1dd3c276ce5b36165344aa`.
Combined canonical diff: `a632e29b42495053b1bd4320c6d29b25cf4c7135f325e19f66d4dc897be02134`.

This modifies LGPL-2.1-or-later code in the pinned `goodix.c`, `goodix55x4.c`,
`goodixtls.c` and `goodixtls.h`, retaining the notices of Alexander Meiler,
Matthieu CHARETTE and Alireza S.N., and the community patch's attribution.
No whole driver source/library is vendored. See [the flow trial](../docs/tls-flow-fix.md)
for provenance, test extraction, exact scope and preserved paths.
