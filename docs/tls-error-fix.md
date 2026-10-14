# TLS error correction: isolated tests and separate build

The owner authorized correcting the defect exposed by the
[first build](build-test.md) and continuing offline verification on 2026-10-09.
This delivery uses existing sources and Nix dependencies. It changes one error
constructor; the driver has not been loaded or installed.
The separately authorized [subsequent load trial](library-load-test.md) loaded the
corrected library in an offline sandbox without executing sensor operations.

## Correction

Read [the separate patch](../patches/0001-goodixtls-safe-errors.patch). It removes
manual allocation of `GError` and its message. `g_error_new()` supplies a valid
`FP_DEVICE_ERROR` domain and `FP_DEVICE_ERROR_GENERAL` code, formats and owns the
message, and includes the original OpenSSL code in that message. A missing reason
has a stable fallback. OpenSSL still consumes one queued error, as before.
Official references: [GLib's constructor](https://docs.gtk.org/glib/ctor.Error.new.html)
and [OpenSSL's reason lookup](https://docs.openssl.org/3.6/man3/ERR_error_string/).
Attribution and the LGPL license are preserved in [the patch inventory](../patches/README.md).

The baseline `work/libfprint-patched` and `work/libfprint-build` are preserved.
The corrected source is a separate detached worktree, assembled with these
operations after checking the already downloaded inputs:

```sh
git -C work/libfprint worktree add --detach ../libfprint-tls-fixed d1ca62a801aa565e67d1a2a47aaa7a33232b7990
git -C work/libfprint-tls-fixed apply --check ../55a4-driver.patch
git -C work/libfprint-tls-fixed apply ../55a4-driver.patch
git -C work/libfprint-tls-fixed apply --check ../../patches/0001-goodixtls-safe-errors.patch
git -C work/libfprint-tls-fixed apply ../../patches/0001-goodixtls-safe-errors.patch
```

These commands have already been performed for this trial. Worktree creation
refuses an existing path. The build script validates the base, community patch,
fix patch and entire combined source diff against separate fixed hashes.
It does not download, assemble or repair the source itself.

## Isolated regression experiment

Inspect [scripts/05-test-tls-errors.py](../scripts/05-test-tls-errors.py) and
[the C harness](../tests/tls-errors-harness.c). Without arguments the script prints
the plan. Explicit `--run`, inside the existing Nix environment, compiles only
the actual baseline/fixed constructor extracted from the two worktrees, plus
the real device-error enumeration. GLib/OpenSSL are linked; the complete
libfprint library and USB code are not linked. The error-domain registration
has a small stand-in; reason/queue wrappers inject edge cases and also delegate
to real OpenSSL for the normal error and empty queue.

```sh
python3 scripts/05-test-tls-errors.py
# Inside the agreed Nix environment:
python3 scripts/05-test-tls-errors.py --run
```

Observed result: the baseline reproduced an AddressSanitizer heap-buffer-overflow.
All seven fixed cases passed with AddressSanitizer and UndefinedBehaviorSanitizer:
real OpenSSL error; empty error queue; unregistered reason; empty message;
one-character message; 8 KiB message containing literal format characters;
and 1,000 repeated create/copy/free cycles. Cases check the domain/code,
message, one queue read and error ownership. Temporary generated sources and
executables stay under ignored `work/` and are removed after testing.

An initial baseline trial stopped in the toolchain's fortify check before ASan
reported the write. The runner disables competing fortify checks only for
the isolated test compilation. Production driver compilation keeps normal Nix
hardening. Another initial test required explicitly loading OpenSSL's error
strings to exercise its registered reason. The final corrected harness passed.

## Separate full build

The optional second argument to the existing walkthrough selects the fixed
inputs and a fresh `work/libfprint-tls-fixed-build` output:

```sh
bash scripts/04-build-local.sh --plan --tls-error-fix
# Inside the agreed Nix environment:
bash scripts/04-build-local.sh --check-dependencies --tls-error-fix
bash scripts/04-build-local.sh --run --tls-error-fix
```

The default variant retains its baseline paths/pins. Both variants refuse an
existing output directory; preserved output must be discussed before retrying.
Offline fixture tests use fake tools and cover selector handling, patch/diff
tampering and preservation of both output directories. The integrated suite
passed 32 checks (22 build-walkthrough tests and 10 protocol tests).

The real fixed preflight and full library build both exited 0 on 2026-10-09.
Ninja completed 64 actions using the existing Nix dependencies; no further
packages were fetched. Static `readelf` inspection confirmed ELF64 x86-64,
SONAME `libfprint-2.so.2`, and the same direct dependency names as the baseline.
The original `goodixtls.c` overflow warning is absent from the corrected build.
Other driver/compiler warnings remain.

Corrected artifact: `work/libfprint-tls-fixed-build/libfprint/libfprint-2.so.2.0.0`.
Size: 2,183,504 bytes. Local artifact SHA-256:
`3fa1a8120f9105a413c002f8718d69b52ae3ba56255223fd685fb78e4416efee`.
The original baseline artifact still has its recorded SHA-256. The patched
baseline source still matches the community diff, and the fixed source matches
the separately pinned combined diff. Build logs remain ignored under `work/nix/`.
At the end of this build trial the corrected library had not been loaded or installed; these results establish
the narrow fix and compilation, not complete driver compatibility or safety.

## Scope and risk

This correction modifies local source/build files and runs offline processes.
It does not modify authentication, services, udev, firmware or sensor keys.
Nix provides dependencies; it is not an execution sandbox. Partial source
review and passing tests do not establish that the complete driver is safe.

Later hardware execution may reset or configure the sensor. Persistent key or
firmware writes can leave the fingerprint reader unusable; restoration has not
been demonstrated. Those operations are separately scoped and remain unperformed.
The earlier TLS retry defect and other compiler warnings remain unresolved.
