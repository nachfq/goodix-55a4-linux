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
The outcome is a readable build walkthrough, followed by separately reviewed
compilation. The owner subsequently delegated execution to the assistant.
This does not choose a maintained fork or complete the audit.

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
- **S5 — Prepare contained dependencies.** The owner selected Nix rather than
  changing Arch packages or adapting the reviewed driver to OpenCV 5. Acceptance:
  a content-pinned environment supplies tools and OpenCV 4, imports no user
  Nixpkgs overlays/configuration, runs no experiment on entry, and explains
  acquisition, shared-store cleanup, and runtime dependency retention. Preparation
  checks must not acquire or realize packages. Activation is separately reviewed.
- **S6 — Correct TLS error construction before runtime trials.** The owner
  explicitly requested the fix after reviewing the build. Acceptance: a separate
  attributed patch uses a valid libfprint error domain/code, safely owns the
  message and handles missing OpenSSL descriptions; isolated regression tests
  demonstrate the original overflow and exercise the fix with sanitizers. A
  separately verified fixed worktree/build preserves the baseline. No additional
  downloads, installation, USB access, provisioning or service changes.

- **S7 — Load without hardware access.** The owner explicitly authorized preparing
  and executing an offline library-load trial. Acceptance: verify the exact
  corrected artifact, load only in a bubblewrap child with no host USB, D-Bus,
  network or home access, and check three basic GType names without constructing
  objects or enumerating devices. Fail closed on isolation/load errors; use only
  existing inputs, keep temporary copies ignored and remove them on exit. Report
  this as dependency resolution and type registration, not hardware compatibility.

- **S8 — Review retry and activation before hardware execution.** After D4 the
  owner authorized a focused static review using existing sources. Acceptance:
  record exact inputs, activation commands and stop conditions; verify retry,
  completion, lifetime and diagnostic-privacy findings with source locations and
  original provenance; separate confirmed control flow from conditional hardware
  consequences. Produce a reviewable report and proposed offline checks, without
  applying fixes, compiling/executing the driver, acquisition or USB access.

- **S9 — Correct the image retry budget and TLS completion flow offline.** The
  owner authorized the proposed R1/R2 delivery on 2026-10-13. Acceptance: preserve
  retry state across command completions, limit a logical image request to two
  recoveries, propagate phase/confirmation errors exactly once, and require both
  proxy progress and actual worker success before confirming TLS. Use a separate
  attributed patch/worktree and actual-function synthetic tests with sanitizers;
  syntax-check the changed complete C units using existing build metadata. No new
  downloads, full-library load, USB, provisioning, installation or service changes.
  Worker teardown, blocking-wait deadlines, complete init robustness, USB error
  handling and diagnostic redaction remain excluded. Necessary zero-initialized
  fields and null/resource guards for reported init failures are in scope; do not
  claim that they resolve all R5 failure paths.

- **S10 — Prepare the first explicit key-state hardware prerequisite.** The owner
  requested continuing toward a real trial on 2026-10-14 after discussing the
  known public key. Acceptance: prepare a separate default-plan script that uses
  existing query helpers, strict previously observed firmware/interface guards,
  skip-on-MATCH, exact typed confirmation, a fixed one-shot public blob write and
  private postcheck; synthetic wire/failure checks and a reviewable command/effects
  report. Preparation opens no device. The persistent hardware operation remains
  pending explicit agreement; ordinary discussion of the public key is not that
  authorization. No community installer/dump entry point or firmware operation.

- **S11 — Prepare one bounded private capture.** On 2026-10-14 the owner
  explicitly accepted the proposed host fixes, complete rebuild and acquisition
  script after reporting MATCH. Acceptance: preserve prior pins/artifacts in a
  separate variant; correct worker lifetime, deadlines/partial init, USB errors
  and key-state diagnostic privacy; exercise real host-side TLS and synthetic
  device failures offline; build only the complete library and standalone helper
  using cached dependencies. Prepare default-plan and verified-input modes that
  open no device, and an explicit typed-confirmation run for one private image
  with finite deadlines and cleanup. Do not execute that hardware mode in this
  preparation delivery. Explain chip enable, reset, MCU configuration, TLS,
  calibration/finger acquisition, LED and sleep operations before execution.
  No firmware/key writes, installer, PAM, service/sysfs changes or acquisition.

- **S12 — Prepare private enrollment and controlled verification.** The owner
  accepted continuing on 2026-10-14 after reporting a real image and discussing
  integration. Acceptance: preserve the captured-image stack; review and correct
  concrete matching/serialization/error defects in a separate source variant
  without tuning thresholds; prepare one private host enrollment and one bounded
  verification per command with declared same/other category. A final decision
  requires successful verification and close; errors/retries/timeouts are
  inconclusive. Freeze the template during a series and stop progression toward
  authentication on any reported false accept. No saved images or public templates.
  Compile/test using cached dependencies, including full synthetic serialization
  and decision smoke in an offline sandbox; independently review the delivery.
  No hardware mode, new key/firmware write, packages, installation, PAM or service
  changes in preparation. Explain the existing sensor runtime commands and local
  template persistence before the owner's hardware execution.

Firmware changes, additional key provisioning, fprintd service overrides, PAM,
authentication integration and enrollment/verification are excluded. The completed
one-shot key trial remains explicitly authorized evidence, not future write scope.
Windows compatibility is not required by the owner; recovery of the original
sensor key remains unproven and is outside this initiative.

- **S13 — Contained fprintd compatibility experiment.** On 2026-10-14 the owner
  accepted temporary fprintd preparation after reporting the native pilot worked.
  Prepare installed daemon/CLI with the pinned experimental library, a private
  D-Bus and real installed Polkit, private state, observed real verification/close API completions, explicit owner-run hardware
  modes and bounded cleanup. Test complete loading and private service/API
  registration offline without USB; standard CLI detection/enrollment/verification
  remain owner-run. No host service/PAM/authentication configuration changes,
  system-bus connection, new package/source downloads, key/firmware writes or
  threshold tuning. Reuse cached Nix/runtime dependencies. Root mode preserves
  real UID mapping inside the sandbox so Polkit can drop privileges; its supervisor
  has CAP_KILL only for stopping that different-UID process within its private PID
  namespace, while native fprintd/CLI have no capabilities. Offline
  smoke uses synthetic namespace accounts and tests that limitation explicitly.

## Technical approach

D14 prepares, but does not install, a contained host deployment after the owner
accepted the proposal on 2026-10-14 ("do it"). **S14**: freeze the already tested
daemon/library and cached Nix runtime in an ignored local bundle; generate one
fprintd service drop-in, separate private host state and project-specific GC-root
links. Prepare explicit install/remove/purge commands that refuse foreign paths,
symlinks, modified payloads and active sessions. Native host tools and Polkit
remain installed/unmodified. Preserve the experimental templates; do not migrate
biometrics. Reset inherited StateDirectory, writable sysfs paths and non-USB
device allowances. Protect native diagnostics/core dumps. Verify payload loading,
unit syntax, closure retention and filesystem/rollback failure cases offline.
This delivery performs no privileged host writes, host-bus activation, hardware
execution, downloads, PAM/login/lock/sudo changes or Git publication. A later
installation needs review of the exact prepared files and effects. Host service
access to real sysfs/udev/USB and loss of the private observer gates are explicit
differences, not claims of equivalent isolation or authentication certification.

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
The assistant rechecked the inventory after execution was delegated: Meson,
`glib-mkenums`, and doctest are missing. OpenCV 5.0.0 is installed and exposes
`opencv5`, not `opencv4`. The existing SIGFM source passed a syntax-only C++17
check against those headers, without producing or executing a library. Linking
and recognition are untested. Using OpenCV 5 requires an explicit build adaptation
and corresponding source-validation changes; neither is implemented or selected
yet. The owner selected Nix instead; that earlier Arch package proposal is not
the current approach. On 2026-10-09 the owner separately authorized the estimated
Nix dependency acquisition and library-only compilation.

Use [nix/shell.nix](../../../nix/shell.nix) with the existing build script. It pins
the expected unpacked Nixpkgs content and an archive revision inferred from local
cache metadata; its independently computed Git tree subsequently matched upstream
commit metadata, and default expression evaluation reused the content in store.
Offline checks use the
already cached tree and an in-memory store. Normal activation may fetch the archive,
substitute missing binaries, or download/build dependencies. Preserve the original
patch and use Nixpkgs's default OpenCV 4 package to favor existing binary-cache
artifacts over a custom dependency build. Read [Nix boundaries](../../../docs/nix-build.md)
before any activation. This shell is an environment, not a USB/network sandbox.

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

### D2 — Prepare dependencies and learn from compilation

- **T4** — Prepare and inspect the selected Nix dependency environment without
  activating it. Specs: S5. Dependencies: T1, T2 and D1 human review. State: done.
  Verification: offline Nix parsing and strict evaluation of the environment's
  actual input lists using the existing cached source and `dummy://`; document
  effective versions, pin validation and cleanup limitations.
  Evidence: parsing and strict evaluation passed on 2026-10-09. Inputs include
  OpenCV 4.13.0, GLib 2.88.3, GUsb 0.4.9, OpenSSL 3.6.3, doctest 2.5.2,
  Meson 1.10.2 and Ninja 1.13.2; shell hook is empty. NAR content hash was
  independently computed and matches the local store's read-only database entry.
  Preparation acquired no packages. The subsequent T3 trial confirmed the cached
  tree's upstream revision and evaluated the default expression successfully;
  a fresh archive download remains untested.

- **T3** — Review the owner's dependency-check output, agree any necessary package
  setup separately, and then interpret their local build result. Specs: S2–S4.
  Dependencies: T1, T2, T4 and human review; prerequisites must be resolved before
  compilation. State: done.
  Verification: delegated configuration/build status and reviewed static
  artifact metadata, or a concrete failure report. Keep later work coarse until
  these outputs exist; do not proceed to USB access as part of D2.
  Evidence: assistant-run preflight exited 1; source pins and patch/diff hashes
  matched. Meson, GLib enum tool and doctest were missing. Read-only package queries
  confirmed OpenCV 5 is present; syntax-only SIGFM/OpenCV 5 check exited 0. No
  configuration, linking, package acquisition or installation was performed during
  that initial preflight. On 2026-10-09 permission changes restored daemon access;
  after an approved dry run (133 paths, 149.1 MiB download, 500.7 MiB unpacked),
  Nix dependency activation and preflight exited 0. The existing interactive script
  completed configuration, 64 Ninja actions and static readelf inspection with
  final status 0. Sources still match the exact reviewed patch. See
  [build evidence](../../../docs/build-test.md) for artifact metadata and warnings.
  No driver installation, loading, USB access or biometric test was performed.

### D3 — Correct and rebuild TLS error construction

D3 was explicitly authorized on 2026-10-09 when the owner requested fixing the defect and continuing. This
accepts D2's compilation evidence and authorizes a narrow patch, isolated tests
and a separate local rebuild. Collaboration mode: autonomous within this scope.

- **T5** — Separate attributed patch and isolated constructor tests. Specs: S6.
  Dependencies: T3 and D2 review. State: done. Evidence: original constructor
  reproduced an ASan heap-buffer-overflow; seven fixed cases passed with
  ASan/UBSan, including a real OpenSSL error, missing descriptions, empty/short/
  long messages and repeated free/copy. No USB code was linked.
- **T6** — Explicit selected build with separate pins/source/output and regression
  checks, then real rebuild and static inspection. Specs: S3, S4, S6.
  Dependencies: T5. State: done. Evidence: 32 integrated offline tests passed
  (22 build-script and 10 protocol checks); real variant preflight passed.
  Corrected preflight and full build exited 0; static ELF metadata matches the
  expected architecture, SONAME and dependencies. The baseline artifact hash and
  both source diff pins are unchanged. See [correction trial](../../../docs/tls-error-fix.md).

### D4 — Isolated complete-library load

D4 was explicitly authorized on 2026-10-09 by "do it" after the assistant proposed
this exact offline sandbox experiment. This accepts D3's correction/build evidence.
Collaboration mode: autonomous within this delivery; no additional acquisitions.

- **T7** — Readable default-plan/input-check/run script and internal sandbox helper.
  Specs: S7. Dependencies: T6 and D3 review. State: done. Evidence: exact artifact
  pin, frozen temporary copy, namespace/mount guards and explicit API whitelist.
  Nine new mock-based refusal/cleanup checks passed; 41 integrated offline tests
  passed. The nine new tests also pass without an existing checkout `work/`.
  No community library is loaded by those unit tests.
- **T8** — Execute with existing inputs and record the result and limits.
  Specs: S4, S7. Dependencies: T7. State: done. Evidence: preflight exited 0;
  first trial stopped in OpenBLAS allocation under the 1 GiB limit. After constraining
  dependency threading to one, actual sandbox trial exited 0 with immediate
  dependency resolution and FpDevice/FpPrint/FpContext GType checks. No object
  construction or sensor access. See [load trial](../../../docs/library-load-test.md).

### D5 — Focused TLS retry and activation source review

The owner explicitly authorized this review on 2026-10-09 ("oka do it") after
accepting the isolated load report. Autonomous within this source-only scope.

- **T9** — Verify effective sources and trace activation/recovery/failure paths.
  Specs: S8. Dependencies: T8 and D4 review. State: done. Evidence: base and patch
  pins plus full effective diff matched; source inspection reconfirmed the broken
  recovery budget and identified lost TLS errors, absent worker synchronization,
  unbounded waits, partial initialization, USB claim/release error loss and returned
  hash disclosure. Hardware-dependent crashes/hangs remain unobserved.
- **T10** — Record findings, their origins and bounded future offline validation;
  reconcile current documentation. Specs: S1, S8. Dependencies: T9. State: done.
  Evidence: [review report](../../../docs/tls-activation-review.md) records seven
  open findings and the actual activation stop at a persistent key mismatch.
  Corrected the earlier always-LED-off-on-open assumption. Documentation links
  and whitespace checks passed. No new runtime checks or driver fixes performed.

### D6 — Image retry budget and TLS completion correction

The owner accepted proceeding from the audit and authorized the proposed offline
R1/R2 correction on 2026-10-13 ("do it"). Autonomous within this bounded delivery.

- **T11** — Attributed second patch and separate fixed source. Specs: S9.
  Dependencies: T10 and D5 review. State: done. Verification: exact inputs,
  preserved prior sources/artifacts, diff/patch applicability and changed-unit
  syntax. Evidence: separate patch/worktree pins validated, applicability passed,
  three complete changed C units passed syntax checks. No update to previous
  build/load pins or hardware experiment.
- **T12** — Actual-function offline failure/retry harness, runner and documented
  results/limits. Specs: S9. Dependencies: T11. State: done. Verification:
  repeated restarts, intervening completions, phase/confirmation errors, worker
  outcome gating, callback reentry and cleanup under sanitizers. Test transport,
  socket/TLS results and SSM are stand-ins; do not claim a real handshake.
  Evidence: 24 C cases passed ASan/UBSan, two original-function negative controls
  failed their expected assertions, and 46 Python offline tests passed. See
  [flow trial](../../../docs/tls-flow-fix.md) for scope, pins and remaining risks.

### D7 — Prepare the first key provisioning experiment for review

The owner wants to try the hardware and asked to continue on 2026-10-14. This
accepts D6's host-side result. Preparation is autonomous; persistent execution is
not authorized until the owner agrees to the concrete command and effects.

- **T13** — Separate script and exact operation report. Specs: S10. Dependencies:
  T12 and D6 review. State: done. Evidence: `08-provision-key.py` default plan and
  dependency check passed; existing PyUSB/libusb are available. Pinned blob and
  serialized-payload hashes match static reference inspection. No USB opened.
- **T14** — Synthetic failure/wire checks and preparation review. Specs: S10.
  Dependencies: T13. State: done. Evidence: thirteen new synthetic checks and 59
  integrated Python checks passed. Hardware behavior is untested. The command,
  persistence/recovery limits and finite capture route are documented in
  [the first-capture plan](../../../docs/first-capture-plan.md).

### D8 — Owner-run one-shot key prerequisite

The owner explicitly authorized and personally executed the reviewed persistent
operation on 2026-10-14. This was the separately agreed hardware follow-up to D7.

- **T15** — One-shot known-key write and immediate private state check. Specs: S10
  plus explicit execution authorization. Dependencies: T14 and D7 review. State:
  done. Evidence: owner-supplied firmware 10062, pre-write MISMATCH, exact typed
  confirmation, post-write MATCH and USB resource release. Shell exit status was
  not supplied. No repeated write, real TLS, capture or persistence test observed.
  See [Test 003](../../../docs/key-provisioning-test.md).

### D9 — Prepare the first standalone private capture

The owner accepted the concrete proposed fixes/build/capture preparation on
2026-10-14 ("go for it"). Autonomous within this delivery; no hardware capture run.

- **T16** — Separate safety variant, actual-function offline tests and complete
  local library rebuild. Specs: S11. Dependencies: T15. State: done.
  Evidence: strict source/patch pins and applicability, 50 native ASan/UBSan
  cases, device-function harness/negative controls, full library build and
  targeted NOP integration rebuild passed. Cached inputs only, no USB.
  Verification: lifetime/fault/deadline/fragmentation and USB/privacy regressions,
  strict input checks, full linking and static inspection with cached inputs.
- **T17** — One-image helper, private bounded launcher and operation report.
  Specs: S11. Dependencies: T16. State: done. Evidence: 78 Python offline
  tests, helper compilation, final pinned-input checks and complete sealed
  runtime/synthetic PGM smoke in a no-host-USB sandbox passed. Hardware not run.
  Verification: default mode no USB,
  exact frozen inputs, confirmation, deadline/error refusal, private output and
  offline isolated runtime smoke test; independent review before handoff.

### D10 — Correct USB descriptor validation after the owner's trial

The owner supplied the failed experiment output on 2026-10-14. A focused fix is
within the existing one-image preparation/debugging scope, with no hardware run.

- **T18** — Record selection-only failure and fix descriptor/transfer-type
  confusion; rebuild helper and improve safe error categories. Dependencies: T17.
  State: done. Evidence: unchanged driver library; helper compile -Werror and
  static ELF checks passed, twenty focused Python checks passed, isolated complete
  runtime passed actual synthetic descriptor/finger-lift/PGM checks. Exact current
  pins and limits are in [Test 004](../../../docs/capture-selection-test.md).
  No new packages, USB/vendor commands, installations or independent review.

### D11 — Owner-run first sensor image

The owner ran the corrected, already explained capture command and supplied its
successful output on 2026-10-14.

- **T19** — Record the bounded hardware result without publishing biometrics.
  Dependencies: T18. State: done. Evidence: owner-reported construction/open,
  activation/calibration, finger lift, successful close and one 108 x 88 image.
  Private path omitted; shell exit status unobserved. No assistant hardware run
  or image inspection. See [Test 005](../../../docs/first-capture-test.md).

### D12 — Prepare private enrollment and controlled verification

The owner explicitly accepted continuing on 2026-10-14 ("perfecto sigamos").
Autonomous within this preparation delivery, not authentication integration.

- **T20** — Review/fix essential verification, template serialization and errors
  in a separate variant with meaningful offline regressions. Specs: S12.
  Dependencies: T19. State: done. Evidence: core ownership/parser/matcher patch;
  real SIGFM/OpenCV/GLib sanitizer regressions plus two original-function failure
  controls passed. Thresholds and capture variant unchanged.
- **T21** — Prepare bounded private enrollment/verify helper and owner-run scripts,
  fixed input/template provenance and explicit decision/error classes. Specs: S12.
  Dependencies: T20. State: done. Evidence: helper/launcher prepared; 37 focused
  private-series/protocol/decision Python checks passed, no hardware executed.
- **T22** — Complete new local build, isolated synthetic runtime, integration
  checks and independent delivery review. Specs: S12. Dependencies: T20, T21.
  State: done. Evidence: full fresh build and final targeted rebuild/static ELF
  inspection and pins passed; 116 integrated Python tests and sealed complete
  runtime public FpPrint synthetic round-trip/prompt/deadline smoke passed.
  Independent read-only D12 review found no actionable defects; reviewer checked
  pins and inspected test logs without rerunning native tests or accessing USB.

### D13 — Prepare temporary contained fprintd

The owner accepted the concrete proposed temporary fprintd compatibility trial
on 2026-10-14 ("go for it"). Autonomous preparation and offline checks only.

- **T23** — Resolve installed daemon/CLI loader, D-Bus/Polkit/storage behavior and
  freeze inputs. Specs: S13. Dependencies: T22 and owner recognition report.
  State: done. Evidence: installed symbol/version coverage, storage/auth/callback
  behavior and private Polkit requirement verified; all runtime inputs pinned.
- **T24** — Prepare private sandbox/session launcher, standard CLI modes and
  local state/cleanup without host integration. Specs: S13. Dependencies: T23.
  State: done. Evidence: bounded parent/child, private state and completion
  observer prepared; native compiler checks and six versioned synthetic cases passed.
- **T25** — Offline loader/service/API smoke, meaningful isolation/failure tests,
  documentation and independent review. Specs: S13. Dependencies: T24.
  State: done. Evidence: complete private no-USB real daemon/Polkit/API smoke,
  188 Python tests, final pin checks and independent read-only review passed.
  Root UID102 privilege drop/cleanup and sensor/CLI hardware routes remain untested.

### D14 — Prepare contained host installation and removal

- **T26** — Inspect service/loader/storage requirements; freeze a local payload,
  exact path manifest and cached Nix closure. Specs: S14. Dependencies: T25 and
  owner native recognition results (Test013–016). State: done. Evidence: frozen
  local payload, 13 runtime roots/176 cached store paths, relocated loader/help
  and isolated generated unit verification passed. No acquisition/installation.
- **T27** — Prepare guarded installation/removal/purge with no default mutation.
  Specs: S14. Dependencies: T26. State: done. Evidence: all33 deployment checks,
  including19 real disposable-root transactions, passed with fake service/Nix
  calls; foreign paths, state, artifacts, siblings and partial writes covered.
  No installation or mutating service command on the host.
- **T28** — Complete offline checks, exact effect/rollback report and independent
  delivery review. Specs: S14. Dependencies: T26,T27. State: done. Evidence:
  237 Python checks (19 separately covered in the disposable transaction run),
  relocated native loader/help and isolated unit verification passed. Independent
  review found D14-R1, corrected with before/after regression; one focused
  follow-up on snapshot d58218b2 confirmed resolution, no remaining findings.
  Installation and real host-service behavior remain unperformed.

### D15 — Apply reviewed deployment and check host detection

The owner explicitly accepted the proposed installation/detection on2026-10-14
("hagamoslo"). Reuse the exact D14 source/bundle; no code change or acquisition.

- **T29** — Check preconditions and apply contained installation through normal
  OS authorization. Dependencies: T28 and owner acceptance. State: done.
  Evidence: pins/dependencies/inactive stock unit/absent destinations passed;
  unchanged controller completed through one-shot Polkit, exit0. Post-install
  exact payload/drop-in/13 roots/private state parent/mask cleanup passed.
- **T30** — Check normal-host device exposure and document actual outcome.
  Dependencies: T29. State: done. Evidence: normal-user fprintd-list exited0,
  one Goodix TLS55X4 exposed and no host fingers enrolled; service startup and
  effective installed configuration verified. Test017 records limits. No host
  enrollment/verification, PAM/auth changes or Git publication.

### D16 — One normal-host right-index enrollment

The owner accepted the proposed host enrollment on2026-10-14 ("oka sigamos").
The assistant supervises the normal CLI, and the owner supplies the finger.

- **T31** — Register the right index without overwriting earlier experiment
  state; observe CLI completion and list the new host enrollment.
  Dependencies: T30 and owner acceptance. State: done. Evidence: preflight list
  empty; invalid finger argument corrected before enrollment. One real attempt
  ended unknown-error/exit1 without stages or registration, inconclusive. One
  retry after owner timing feedback completed16stages/enroll-completed/exit0;
  normal list confirmed one right-index-finger (Test018). No timeout fired.
  Host verification/accuracy, independent close and authentication unproven.

### D17 — One normal-host declared-same verification

The owner accepted the proposed verification on2026-10-14 ("go for it").

- **T32** — Compare the operator-declared registered right index through normal
  fprintd and record decision/error separately. Dependencies: T31 and owner
  acceptance. State: done. Evidence: first attempt unknown-error/exit1,
  inconclusive; owner reported delayed attention/placement. One retry after
  that feedback gave verify-match(done)/exit0 (Test019), no outer timeout.
  Standard CLI has no independent close observer or accuracy guarantee.

### D18 — One normal-host declared-other verification

The owner accepted the proposed other-finger trial on2026-10-14 ("go for it").

- **T33** — Keep right-index enrollment as reference, instruct an unenrolled
  finger and record normal CLI status with error-classification limits.
  Dependencies: T32 and owner acceptance. State: done. Evidence: CLI selected
  right index, reported verify-no-match(done)/exit1 (Test020), no preceding
  retries/errors or outer timeout. Physical identity is operator-controlled.
  Host CLI may map internal errors to NO_MATCH; no independent observer-backed
  library rejection or close proof. No template or configuration changes.

### D19 — Enable Omarchy screen unlock

The owner declined additional biometric trials, accepted D18, and selected
screen unlock as the first everyday integration on2026-10-14. Exact scope: create
only fingerprint-specific lock PAM config; preserve password and other auth.

- **T34** — Enable the installed Omarchy fingerprint lock context using existing
  host enrollment, and document use/reversal. Dependencies: T33 and owner scope
  selection. State: done. Evidence: normal Polkit-authorized exclusive creation
  of stock 3-line PAM recipe, root:root0644. Exact content/metadata and unchanged
  password-lock/sudo/login/Polkit/SDDM PAM baselines verified. No lock/test round,
  restart, packages, biometric inspection or Git publication. Actual screen
  unlocking not yet observed. Separate PAM file reversal documented.

### D20 — Enable sudo and graphical login

The owner reported both screen-unlock methods worked, then requested sudo/login
on2026-10-14. Preserve password fallback, current autologin and disk encryption.

- **T35** — Inspect actual login manager and configure sudo/SDDM PAM with private
  originals and reversible changes. Dependencies: T34 and explicit owner request.
  State: done. Evidence: stock closed-lid skip plus sufficient fingerprint with
  max-tries1/timeout10 inserted after header in only sudo/sddm. Normal Polkit
  authorization succeeded; exact target hashes/ownership/modes and unchanged
  password-lock/fingerprint-lock/consolelogin/Polkit/autologin baselines passed.
  Private originals/hashmanifest/rootrestorehelper created; helper syntax and
  default plan checked. No extra auth trial or session restart. Live sudo/SDDM
  results unobserved; confirmed encrypted root and preexisting autologin mean
  startup disk password is a separate flow, not replaced by this delivery.

## Next delivery

D19 is accepted through the owner's fingerprint/password unlock reports. D20
sudo/SDDM configuration is complete, awaiting ordinary use/owner review. Do not
impose additional biometric rounds, reboot/logout, disable autologin or modify
LUKS/initramfs/bootloader/TPM. Those boot-security choices require explicit scope.
Polkit fingerprint setup and Git publication also remain separately scoped.

### Completed prerequisite evidence

Focused D13 correction after the owner's first detection attempt (2026-10-14):
parent relay called fileno() on the selector's integer descriptor. Use key.fd
directly; five regression methods exercise real subprocess pipes without USB.
The exact exception was reproduced before the fix; 22 focused parent and 193
integrated Python tests plus runtime input checks passed afterward. Hardware
detection remains inconclusive; repeat only owner-run detection next (Test010).

Second focused D13 correction (Test011): the next owner trial reported DBUS before
READY. A no-USB distinct-UID namespace reproduction confirmed implicit runtime
directories were0700 and prevented UID102 policy discovery. Script17 explicitly
chmods only synthetic NSS/policy/runtime parent directories0755; binds and private
state unchanged. Before/after native reproduction demonstrated the exact failure
and corrected authorization/daemon/list/teardown. Ordinary smoke, 194 Python tests, input checks
and focused read-only review passed. Owner host-root detection retry remains next.

Third focused D13 correction (Test012): READY then DEVICE output exposed missing
udev/sysfs inventory. Add a readonly synthetic selected-device metadata view,
exact child verification and a private libudev filesystem-verification override.
No host sysfs mount or extra host device reads. Three actual FpContext fixtures
give0/0/1selecteddriver withnoUSBnodes; positive privatefprintd/UID102Polkit/native
list/teardown and ordinary smoke passed. Focused independent review nofindings.
Native pins and sensor state unchanged; owner real detection remains next.
Final verification:204 integrated Python tests, frozeninputs andwhitespace passed.

D12 is accepted through owner enrollment/verification feedback. D13/T23–T25 is
complete; the owner reported successful hardware detection/private teardown
(Test013), then completing enrollment (Test014; no transcript/status supplied).
Private persisted print/manifest metadata and integrity checks passed.
The owner then reported one declared-same native MATCH (Test015, no transcript
or status supplied), then one declared-other native NO_MATCH (Test016, no
transcript/status supplied). The initial contained native recognition experiment
is complete through owner reports. Return control; propose a bounded contained,
reversible host-service preparation delivery, without installing or changing
authentication before agreement. Private runtime
Polkit is required; no changes to host rules, services, PAM or login. No hardware
execution, install/acquisition or Git publication by the assistant.
