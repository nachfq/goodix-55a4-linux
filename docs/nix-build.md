# Contained build dependencies with Nix

This dependency environment supported the [first successful local build](build-test.md).
It uses
the existing Nix installation and keeps Arch packages unchanged. Entering it may
download or build missing dependencies in `/nix/store`; that activation is a
separate step from reviewing the definition. The owner authorized acquisition and
compilation on 2026-10-09; that trial is complete, without installing the driver.

Read [nix/shell.nix](../nix/shell.nix). It supplies build tools and libraries to
the existing [local build script](../scripts/04-build-local.sh), including OpenCV
4 instead of the host's OpenCV 5. The original reviewed driver inputs remain
unchanged. There is no automatic build command in `shellHook`.

## Pins and preparation evidence

The proposed Nixpkgs archive revision is
`a5cc6f2c37bf518436dc8d1c288ccd0c43c2f4c4`. It was inferred from the fingerprint
of cached Nixpkgs file records; its corresponding
[upstream commit](https://github.com/NixOS/nixpkgs/commit/a5cc6f2c37bf518436dc8d1c288ccd0c43c2f4c4)
exists. The cached source's independently computed NAR SHA-256 is
`sha256-r2f1oUwixlgq9zOdYLqJLfS/lWBT60/IITjhTKI59JU=`. This is an unpacked-tree
hash, not the compressed archive's SHA-256. On 2026-10-09 the cached source's
independently computed Git tree hash `6619d0f30bc3fcfd06447218fec0b1deee021df8`
matched GitHub's commit metadata, verifying the revision association without a
new archive download. Evaluation of the default expression also passed, reusing
the content already in the store. A fresh archive download remains untested.
The default expression enforces the content
hash: a different tree must fail rather than silently substitute another input.

Offline evaluation against that cached tree, using Nix's in-memory `dummy://`
store, checks the expression without downloading or realizing packages. The
definitions provide:

| Dependency | Version in the cached definition |
| --- | --- |
| OpenCV 4 | 4.13.0 |
| GLib | 2.88.3 |
| GUsb | 0.4.9 |
| OpenSSL | 3.6.3 |
| doctest | 2.5.2 |
| Meson | 1.10.2 |
| Ninja | 1.13.2 |

These recipe versions were subsequently confirmed by the real preflight, which
exited 0. OpenCV supplies `opencv4.pc`, GLib's `dev` output supplies `glib-mkenums`,
and `doctest.pc` was found. Compilation then completed; see the build report for
its limits and compiler warnings.

## Activation and compilation are separate operations

The next operation, after agreeing its download scope, is:

```sh
nix-shell --pure nix/shell.nix --run 'bash scripts/04-build-local.sh --check-dependencies'
```

It fetches the pinned Nixpkgs archive if necessary, obtains missing tools and
libraries plus their transitive dependencies, sets the shell environment, and
runs only the preflight. Existing configured Nix substituters supply binaries
when available; cache misses can cause source downloads and dependency builds.
OpenCV's default package includes additional image/video dependencies. The approved
trial's dry run predicted 133 missing store paths, 149.1 MiB download and 500.7 MiB
unpacked; this is a machine-specific pre-acquisition estimate. Binaries were
substituted from `https://cache.nixos.org`. A future dry run may differ as the
local store changes. Do not interpret the short direct-input list as the complete
dependency closure.

On machines without a `nixpkgs` channel, `nix-shell` may print a lookup error and
fall back to the host Bash when choosing its initial shell. For the recorded trial,
the assistant explicitly set `-I nixpkgs=<verified cached source>` and used that
same source for `--arg nixpkgsSource`; this selected the pinned Nix Bash too.
No channel or global Nix configuration was added.

Only after a successful preflight is the separate compilation command applicable:

```sh
nix-shell --pure nix/shell.nix --run 'bash scripts/04-build-local.sh --run'
```

The build script remains interactive and checks its exact source inputs. It
produces a library under ignored `work/libfprint-build`, without installing or
loading it. The assistant can operate those prompts when execution is delegated.
Nix does not supply USB permissions, and `--pure` clears most inherited variables;
it is not a filesystem, network, or hardware sandbox. See the official
[shell tutorial](https://nix.dev/tutorials/first-steps/declarative-shell.html) and
[`nix-shell` manual](https://nix.dev/manual/nix/2.35/command-ref/nix-shell.html).

## Lifetime and cleanup

Leaving the shell removes its environment from the current process. It does not
delete downloaded packages. Build output and generated logs stay under ignored
`work/`; preserve failed output until it has been reviewed. This definition adds
no user profile, service override, PAM setting, udev rule, or automatic GC root.

Nix linker wrappers can embed `/nix/store` dependency paths into the resulting
library. A library outside the store is not itself a GC root. Before later runtime
testing, explicitly choose how to retain its dependencies; otherwise subsequent
garbage collection may break it. Do not run global garbage collection as a
project rollback: it affects unreferenced paths from other projects too. Nix's
[garbage-collection manual](https://nix.dev/manual/nix/2.35/command-ref/nix-store/gc)
explains reachability and roots. No cleanup operation is automated here.

## Execution history

On 2026-10-09 the assistant's restricted session could read the cached source and
evaluate definitions in memory, but connecting to the Nix daemon socket failed
with `Operation not permitted`. Direct local-store access also failed on its
database lock permissions. The owner changed session permissions later that day.
Daemon access, dry-run estimation, authorized activation, Meson configuration,
compilation and static ELF inspection then succeeded. Hardware execution remains
unperformed; the build report identifies issues to resolve before loading it.
