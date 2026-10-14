# Isolated library-load trial

On 2026-10-09 the owner authorized preparing and executing this bounded offline
trial after the [TLS correction and rebuild](tls-error-fix.md). The assistant
executed it using only existing Nix dependencies and existing bubblewrap 0.12.0.
No packages were downloaded or installed for this delivery.

## What the experiment does

Read [scripts/06-load-library.py](../scripts/06-load-library.py), then its small
[internal helper](../scripts/helpers/load-library-child.py). The default mode
describes the plan. `--check-dependencies` checks inputs without loading anything;
`--run` executes the sandbox. Run without sudo. Only Nix Python is accepted,
to keep the interpreter and library on the same dependency environment.

The parent reads and verifies the exact corrected build, then copies those
verified bytes and the helper into a temporary ignored directory under `work/`.
The library mounted in the child is that copy, so a later change to the original
build file cannot replace the bytes tested. Both copies are removed on success,
failure, timeout or interruption.

Bubblewrap starts with a fresh root and separate namespaces. The command mounts
only the whole Nix store, the copied library and the helper read-only, plus
private `/proc`, a minimal `/dev`, and a temporary `/tmp`. It mounts no host
USB nodes, `/sys`, `/run` (including D-Bus), home directory or Nix daemon socket.
The new network namespace has no host network interfaces. It clears inherited
environment variables, closes other file descriptors, supplies no terminal input,
and uses a new session with dropped capabilities.

Before loading, the child compares mount/network/PID namespace identities with
the parent's, checks the absent access paths and read-only mounts, and rechecks
the copied library hash. There is no unsandboxed fallback. The child has a
1 GiB virtual-address-space limit, a 10-second CPU limit, and disabled core dumps;
the parent imposes a 20-second timeout. These limits affect only this trial.
`OPENBLAS_NUM_THREADS=1` and `OMP_NUM_THREADS=1` constrain dependency threading.

`ctypes.CDLL` uses `RTLD_NOW | RTLD_LOCAL`, so dynamic symbol dependencies are
resolved immediately. Native library/dependency constructors execute inside
the sandbox. The only explicit libfprint API calls are:

| Symbol | Expected registered type name |
| --- | --- |
| `fp_device_get_type()` | `FpDevice` |
| `fp_print_get_type()` | `FpPrint` |
| `fp_context_get_type()` | `FpContext` |

`g_type_name()` checks each returned identifier. Registering these GTypes does
not construct their instances. In the pinned base,
[`fp-context.c`](https://github.com/TheWeirdDev/libfprint/blob/d1ca62a801aa565e67d1a2a47aaa7a33232b7990/libfprint/fp-context.c)
separates its type registration from `fp_context_init()`, which creates the USB
context. This experiment never calls `fp_context_new()`, device enumeration,
device open, capture or verification.

Reference behavior: [bubblewrap's sandbox policy](https://github.com/containers/bubblewrap/blob/main/README.md),
[Python ctypes](https://docs.python.org/3.13/library/ctypes.html),
[GObject type names](https://docs.gtk.org/gobject/func.type_name.html), and
[OpenBLAS thread settings](https://www.openmathlib.org/OpenBLAS/docs/runtime_variables/).
This policy is a bounded local precaution, not a complete security audit.
The whole Nix store is readable; do not assume it contains only these packages
or that files placed in the store are confidential. The sandbox uses the host
kernel and is not a virtual machine.

## Observed result

Artifact: `work/libfprint-tls-fixed-build/libfprint/libfprint-2.so.2.0.0`.
Size: 2,183,504 bytes. Local SHA-256:
`3fa1a8120f9105a413c002f8718d69b52ae3ba56255223fd685fb78e4416efee`.
This is the exact locally observed artifact pin, not a reproducibility claim.
A different build must be reviewed before changing the script's pin; the script
does not automatically accept a new hash or build the missing library.

Dependency preflight exited 0. The first load attempt exited 1 during OpenBLAS
initialization, with a memory-allocation error under the 1 GiB limit. It did not
complete the API checks and is an inconclusive load trial. After adding the
single-thread settings, the final load trial exited 0:

```text
PASS: isolation checks; immediate dependency resolution; FpDevice, FpPrint, FpContext
Child exited; temporary files removed. No reader was opened or enumerated.
```

This establishes loading of this corrected artifact and basic GType registration
in this environment. It does not establish fprintd ABI compatibility, a working
TLS handshake, sensor initialization, capture, enrollment, matching accuracy,
spoof resistance or authentication readiness. No system service, PAM, udev,
firmware or sensor key was changed. No biometric data was acquired.

## Read or repeat

To read the plan from a normal terminal:

```sh
python3 scripts/06-load-library.py --plan
```

The assistant used this existing, previously verified cached source with
substitution disabled. These commands do not authorize acquiring missing inputs:
if the existing environment is unavailable, stop and review prerequisites.

```sh
XDG_CACHE_HOME="$PWD/work/nix/cache" \
XDG_STATE_HOME="$PWD/work/nix/state" \
XDG_DATA_HOME="$PWD/work/nix/data" \
nix-shell --pure --option substitute false \
  -I nixpkgs=/nix/store/nqkh6j5xlyvlw4hlrw4ybpq1cis79szf-source \
  --arg nixpkgsSource /nix/store/nqkh6j5xlyvlw4hlrw4ybpq1cis79szf-source \
  nix/shell.nix --run 'python3 -B scripts/06-load-library.py --check-dependencies && python3 -B scripts/06-load-library.py --run'
```

The source path is machine-specific; see [the Nix report](nix-build.md) for its
content pin and acquisition/cleanup boundaries. Nix activation itself is outside
the bubblewrap sandbox. Disabling substitution is not a general network sandbox
for a missing dependency's build; this trial used already available inputs.
The script saves no logs and does not create permanent Nix GC roots.

The integrated offline suite passed 41 tests: 22 build-walkthrough, 10 probe, and
9 load-trial refusal/cleanup checks. The new tests exercise changed inputs,
host-Python refusal, isolation failures, timeout cleanup and unexpected type names
using mocks; they do not load the community library. The actual successful
sandbox trial supplies separate execution evidence.
The nine new tests also passed with a synthetic checkout root lacking `work/`;
their fixtures do not require the downloaded sources or previous build output.

Next: agree a focused review of the outstanding TLS retry and activation path
before any community-driver USB trial. The observed key-state mismatch still
blocks the normal activation path; persistent provisioning needs its own proposal.
