---
{
  "id": "local-driver-build",
  "title": "Prepare an owner-run local build of the reviewed driver",
  "status": "active",
  "depends_on": []
}
---

# Prepare an owner-run local build of the reviewed driver

## Specs

The owner chose local build preparation after reporting firmware `10062` and
expected key state `MISMATCH`; see [project context](../../context.md).
The outcome is a readable build walkthrough, followed by a separately reviewed
owner-run compilation. This does not choose a maintained fork or complete the audit.

- **S1 — Record existing evidence accurately.** Document the owner-reported probe
  result and reconcile statements that this query has not been run. Distinguish
  a key-state mismatch from an absent key, failed sensor, or biometric rejection.
  Acceptance: current documentation identifies completed queries and unperformed
  capture/enrollment/verification, with no returned hash or unreviewed logs.
- **S2 — Explain and inspect prerequisites.** A new interactive script defaults to
  a plan; an explicit dependency-check mode inspects local tools, discovery
  metadata, pinned inputs, and the fresh output path. Acceptance: it lists required inputs and missing prerequisites, opens
  no USB device, and neither downloads nor installs anything. Missing pkg-config
  entries are reported as discovery failures, not proof that every library is absent.
- **S3 — Prepare a bounded local build.** An explicit owner-run mode displays each
  command and waits for Enter. It verifies the pinned base, patch hash, and intended
  patched source before configuring a fresh ignored build directory. Acceptance:
  no root execution, automatic source repair, directory deletion, dependency
  acquisition, installation, test/example execution, sensor access, or system
  configuration changes. Failures stop the sequence and remain visible.
- **S4 — Report compilation as compilation.** A later owner-run build may establish
  that the shared library links; static ELF inspection can describe its SONAME and
  dependencies. Acceptance: neither this nor the firmware-string check is presented
  as fprintd runtime compatibility, capture support, or authentication readiness.

Provisioning, firmware changes, retry-defect fixes, expanded driver audits,
fprintd service overrides, PAM, and authentication integration are excluded.
Windows compatibility is not required by the owner; recovery of the original
sensor key remains unproven and is outside this initiative.

## Technical approach

The current probe sends a few USB queries; it does not load the community driver.
Compilation is a different experiment: Meson reads build descriptions and locates
dependencies, then Ninja compiles and links C/C++ into a shared library. Producing
that file does not make the installed fprintd service use it.

Reuse the clean base and separate patched worktree recorded in the
[source review](../../../docs/source-review.md), without modifying either.
The proposed flow is:

```text
show plan -> inspect dependencies -> review missing requirements together
          -> owner explicitly runs configure -> build only shared library
          -> inspect file metadata -> discuss result
```

Prepare one small script, provisionally `scripts/04-build-local.sh`, with default
plan, `--check-dependencies`, and interactive `--run` modes. Reuse the teaching
style of the [walkthrough](../../../docs/walkthrough.md). Build products and
Meson's generated logs belong under ignored `work/`; upload no raw logs.
Refuse an existing build directory rather than cleaning or silently reusing it.
Stop on source discrepancies rather than resetting the owner's changes.

Select only `goodixtls55x4`. Configure with introspection, documentation, GTK
examples, installed tests, udev rules, and udev hwdb disabled, plus
`--wrap-mode=nofallback`. Build only shared-library target `fprint-2`, confirming
its name/output from generated metadata first. Do not invoke the default all
target, `test`, `install`, or `sync-udev-hwdb`; the latter copies into the source tree.

The pinned manifests require C/C++ tools, Meson >=0.56, Ninja, Python3,
pkg-config, GLib/GIO/GObject >=2.56, GUsb >=0.2, OpenSSL, threads,
`glib-mkenums`, OpenCV4, and doctest >=2,<3. In
[`sigfm/meson.build`](https://github.com/TheWeirdDev/libfprint/blob/d1ca62a801aa565e67d1a2a47aaa7a33232b7990/libfprint/sigfm/meson.build),
OpenCV and doctest are unconditional even for the library target. Disabling
`installed-tests` does not remove tests from configuration. CMake may help
dependency discovery but is not an unconditional requirement in these manifests.
The old dependency inventory must be rechecked by the owner; no installation
command or package transaction is authorized by this plan.

Read-only planning inspection found compiler/dependency probes, an inline Python
environment formatter, enum generation, and generated registration code in this
configuration. Configuration executes build tooling; the reviewed library graph
has no intended device access. No downloader or subproject fallback was found in
the inspected manifests. `nofallback` prevents Meson fallback acquisition; it is
not a network sandbox. Tool-version compatibility remains untested.

## Tasks

### D1 — Prepare the walkthrough for human review

- **T1** — Record the reported probe and reconcile current status in the walkthrough,
  README, staged plan, and stale AGENTS stage statement as needed. Historical audit
  reports retain their original scope. Specs: S1. Dependencies: none. State: done.
  Verification: compare with the owner's supplied output; check links and ensure
  unperformed tests remain unperformed.
  Evidence: added `docs/probe-test.md` from owner-supplied output and reconciled
  current status; repository-local documentation links resolve and whitespace
  checks pass. Reported shell exit status remains explicitly unobserved.
- **T2** — Prepare the plan/dependency/build modes and concise reading instructions.
  Include source validation, fresh ignored output, target selection, cleanup of
  temporary validation resources, and failure handling without deleting user data.
  Specs: S2, S3, S4. Dependencies: T1. State: done.
  Verification: shell syntax and proportionate offline checks, including missing
  prerequisites, changed inputs, existing output, interruption, and command failure.
  Use temporary fixtures or fake tools for build-path checks; do not compile the
  community library or access hardware while preparing this delivery.
  Evidence: shell syntax and default plan pass; integrated suite passes 26 offline
  tests (16 build-walkthrough checks, 10 protocol checks). Canonical diff still
  matches the reviewed patch hash. Documentation links resolve. No real dependency
  preflight, configuration, compilation, installation, or USB access was run.

### D2 — Learn from the owner's compilation

- **T3** — Review the owner's dependency-check output, agree any necessary package
  setup separately, and then interpret their local build result. Specs: S2–S4.
  Dependencies: T1, T2 and D1 human review; prerequisites must be resolved before
  compilation. State: active.
  Verification: owner-supplied configuration/build status and reviewed static
  artifact metadata, or a concrete failure report. Keep later work coarse until
  these outputs exist; do not proceed to USB access as part of D2.

## Next delivery

Current committed milestone: Guarded one-shot key provisioning is available. The owner reported immediate MISMATCH-to-MATCH; original-key recovery is unproven.
See [the stage report](../../../docs/key-provisioning-test.md).
No further hardware/installation/auth changes are authorized by this Git staging
checkpoint. The complete chronological plan is published with the final integration.
