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
