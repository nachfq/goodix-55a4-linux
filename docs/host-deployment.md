# Contained host fprintd deployment

The owner accepted preparing this delivery on 2026-10-14 after the contained
native experiment reported detection, enrollment, same-finger MATCH and
other-finger NO_MATCH ([Test013–016](private-fprintd.md)). This document describes
the reviewed deployment prepared in D14. On 2026-10-14 the owner then accepted
installation and normal-host detection ("hagamoslo"). The assistant installed it
and observed successful host detection; see Test017 below. Authentication
integration remains disabled.
No host installation, GC root, runtime mask, service reload/activation, USB trial,
package/source acquisition or PAM/login/sudo/lock change occurred during preparation.

## Installed files and effects

[21-prepare-host-deployment.py](../scripts/21-prepare-host-deployment.py) produced
ignored `work/host-deployment-bundle/` from the existing pinned native daemon,
experimental library, installed Polkit client library and controller source.
No native observer is installed. Installed Arch packages and CLI remain intact.

| Installed path | Ownership / purpose | Removal |
| --- | --- | --- |
| `/opt/thinkpad-fingerprint/` | root:root 0755; daemon, two libraries, controller, config, manifest, install record, LGPL text and attribution | Own exact frozen tree only |
| `/etc/systemd/system/fprintd.service.d/90-thinkpad-fingerprint.conf` | root:root 0644; redirects only fprintd | Own matching file only; never systemctl revert |
| `/nix/var/nix/gcroots/thinkpad-fingerprint/` | root-owned directory with 13 exact links to cached runtime roots | Own matching links only; no global GC |
| `/var/lib/thinkpad-fingerprint/fprint/` | root:root 0700; new native host templates, files 0600 | Preserved by default; explicit purge available |
| `/var/lib/thinkpad-fingerprint/.owner` | root:root 0600; identifies this private state namespace | With explicit state purge |
| `/run/systemd/system/fprintd.service` | Temporary own symlink to `/dev/null` during install/remove | Removed on ordinary exit, followed by daemon-reload |

The payload contains `fprintd` (0755), `lib/libfprint-2.so.2.0.0`,
`lib/libpolkit-gobject-1.so.0`, `manage.py`, `fprintd.conf`,
`fprintd-dropin.conf`, `manifest.json`, `installation.json`, `NOTICE` and
`COPYING` (other files 0644), plus 0755 `lib/` and `empty/` directories.
The package is for local use; this preparation does not publish binaries.

The generated drop-in resets ExecStart and invokes the cached Nix loader with
an explicit library path and the experimental library preloaded for the frozen
fprintd copy only. It resets StateDirectory before assigning the private host
path; the installed daemon honors systemd's `STATE_DIRECTORY` variable. A private
file-storage config is mounted read-only over `/etc/fprintd.conf` inside the
service, without replacing the host file. The generated state variable is retained.

Existing unit protections remain. Writable sysfs paths and inherited non-USB
device allowances are cleared; only the USB device allowance remains. The driver
already skips wakeup/persist sysfs writes. Only `goodixtls55x4` is selected.
Single-thread BLAS settings are explicit; debug/private-bus/preload variables are
removed, native stdout/stderr are discarded and the core limit is zero. The
supervised experimental observer is omitted because it requires its private FD.
Systemd can still log service lifecycle/failure metadata.

The Nix roots protect **13 direct runtime inputs and their 176 cached store-path
closure**, as observed during preparation. Roots follow Nix's
[documented collector rules](https://nix.dev/manual/nix/2.35/package-management/garbage-collector-roots).
No dependency is acquired by preparation or the controller. Removal releases
only these references; already cached store objects remain shared and may become
eligible for a separately chosen Nix garbage collection. A project rollback
never runs global GC or removes another application's roots.

## Difference from the private experiment

This deployment is more exposed than script17. The daemon connects to the **real
host system bus and host Polkit**, sees real host USB inventory/udev/read-only
sysfs and has the standard root service identity. There is no synthetic `/sys`
or private-bus permission override. Host Polkit/session authorization may prompt
or deny differently from the root-authorized private trial; no rule is bypassed
or added. No D-Bus activator/policy changes are needed: the installed activator
already selects `fprintd.service`.

Standard `fprintd-list`, `fprintd-enroll` and `fprintd-verify` use normal D-Bus
commands. They do not have script17's verification/close observer or declared
same/other gates. In particular, native CLI NO_MATCH can represent an error;
count errors/retries/cancellations/timeouts as inconclusive. One match/rejection
report in the private trial is not a reliability estimate or authentication
certification. Host native enrollment/verification are still untested.

Private experiment state under `work/private-fprintd/` and
`work/private-verification/`, plus original `/var/lib/fprint`, are never imported,
overwritten or deleted. A separately reviewed host enrollment creates new state.
PAM, sudo, lock screen, login and SSH/GPG key authorization remain unchanged.
Removing this deployment cannot restore the earlier persistent sensor key.

## Preparation and offline checks

These commands run as the regular user and do not install:

```sh
python3 -B scripts/21-prepare-host-deployment.py --check-inputs
python3 -B scripts/21-prepare-host-deployment.py --prepare
python3 -B scripts/22-manage-host-deployment.py
python3 -B scripts/23-test-host-deployment.py --run
python3 -B scripts/24-test-host-transactions.py --run
```

The bundle is already prepared in this checkout. `--prepare` refuses an existing
output rather than updating/deleting it. Frozen manager/daemon/library/config
pins, exact entries and Nix root content hashes are stored and rechecked. A new
version needs review and a fresh bundle; no automatic update or dependency repair.
Copies under `/opt` would remain frozen when Arch packages update, so keeping
this experimental service maintained is a separate obligation.

The offline relocated loader/library maps and real daemon `--help` passed in a
namespace without host `/usr`, `/etc`, sysfs, USB, buses or home. The generated
unit passed actual `systemd-analyze verify` in a separate no-bus/no-USB namespace;
manual-page checks and unit/environment generators were disabled for this syntax
check. Initial verifier attempts lacked temporary directories and tried missing
man/environment helpers; the final explicit offline verifier passed.

All **33 deployment checks**, including **19 filesystem transaction cases**, passed
inside a disposable user namespace with fake systemd/Nix calls. They cover
install/remove/preserve/reinstall/purge, active/pre-existing service/mask refusal,
modified binaries/config/state/roots, foreign siblings/paths, symlinks/hardlinks,
permissions and partial-write rollback. The mask guard requires both
`LoadState=masked` and the effective `FragmentPath` of its own runtime mask before
any payload transaction; a stale cached vendor unit followed by a higher-priority
foreign unit is refused. The new synthetic case failed before that correction
and passed afterward, for installation and removal. Real host integration and systemd runtime
confinement are not simulated by these filesystem cases; service syntax and
loader checks are separate. No actual privileged deployment was tested in D14;
the subsequent installation/detection observation is recorded in Test017.

Independent D14 source review used HEAD `621dde00` and base `ceb73bf1`,
with explicit dirty-file snapshots (initial `425bdc39`, follow-up `d58218b2`).
It found D14-R1, the ineffective runtime-mask guard described above. The
correction and its regression were checked in one focused follow-up, with no
remaining actionable findings. The reviewer verified source/bundle pins and
syntax, inspected logs and reproduced the guard using simulated calls; it did
not repeat native tests or run services/hardware. Only documentation of the
review outcome and task completion changed after the reviewed snapshot.

## Installation procedure — already completed in this checkout

Review the generated bundle/drop-in and this exact effect list first. Finish
all private experiments and any fprintd operation; the controller refuses an
active host service and performs a best-effort private-session check. Do not
launch private trials while installing/removing: it cannot lock unrelated clients.
If fprintd is active, explicitly stopping it is a separately chosen operation;
the controller never silently kills or stops it.

For a fresh, separately reviewed installation, the prepared command is below.
Do not repeat it here: the owned destinations already exist and overwrite is
refused. The actual assistant run used one-shot Polkit authorization (`pkexec`)
because noninteractive sudo required a password; no policy or sudo rule changed.

```sh
sudo -- /usr/bin/python3 "$PWD/scripts/22-manage-host-deployment.py" \
  --install "$PWD/work/host-deployment-bundle"
```

Confirmation: `INSTALL THINKPAD FINGERPRINT`.

It checks the frozen bundle, Nix inputs and inspected host integration pins;
refuses an existing payload/drop-in/root directory, foreign private state,
symlink ancestors and foreign overrides; temporarily masks the inactive service;
copies root-owned files, creates only project GC links and new/previously owned
private state, adds its drop-in and removes its mask. Ordinary installation
errors roll back newly created paths and preserve previously owned state.

**Finishing installation enables host D-Bus activation.** The tool does not call
fprintd or start a biometric trial, but another host client can activate it once
the mask is removed. Agree on that sensor/service exposure as part of installation,
not merely file copying. No host trial is authorized by preparation alone.

The first normal-user check, `fprintd-list`, may activate the service and was
completed successfully in Test017. Review that result before a new host
enrollment. Do not proceed automatically to enrollment, verification or PAM.

## Test017 — Installed host service and native detection

On 2026-10-14 at approximately 19:48 UTC, after the owner's explicit acceptance:

- Exact source/bundle hashes, cached Nix input hashes, inactive stock service,
  absence of foreign overrides/destinations and the private-session guard passed.
- Noninteractive sudo required a password. The reviewed controller was launched
  through `pkexec --disable-internal-agent` in a terminal; Polkit authorization
  succeeded, then the assistant supplied `INSTALL THINKPAD FINGERPRINT`.
  The controller exited 0 after installing its own payload, drop-in, state and
  13 GC-root links, and removing its temporary runtime mask.
- A post-install read-only check verified the exact root-owned payload, generated
  drop-in, all 13 root links, root-owned 0700 state parent and absence of the mask.
  No template contents were read.
- `timeout --kill-after=2s 20s fprintd-list <current user>` ran as the normal user
  and exited 0. It activated the real host daemon and reported one device,
  `/net/reactivated/Fprint/Device/0`, named `Goodix TLS Fingerprint Sensor 55X4`,
  with no enrolled fingers for that user in the separate host state.
- The service reported active/running and Result=success; systemd's effective
  ExecStart selects the frozen `/opt` daemon/library and cached Nix loader,
  with StateDirectory=thinkpad-fingerprint/fprint and mode0700/UMask0077.

This establishes normal-host daemon startup and device exposure, not host
capture, enrollment, verification or reliable authentication. The standard
service can remain active until its normal idle exit and is available for
subsequent D-Bus activation. No sensor key/firmware change, template migration,
package/source acquisition, PAM/login/sudo/lock integration or Git publication
occurred. The owner must place a finger in the next separately agreed host
registration trial; preserve all earlier private experiment state.

## Test018 — Normal-host right-index enrollment

On 2026-10-14 the owner accepted the next host registration trial ("oka sigamos").
The assistant ran the normal-user CLI; the owner supplied the physical finger.
A preflight `fprintd-list` confirmed no host fingers enrolled, avoiding overwrite.

The initial command used `right-index`, which this CLI rejected as an invalid
name (exit1) before enrollment. The correct identifier is `right-index-finger`.
The first correctly named enrollment reported `enroll-unknown-error`, no
successful stages, and exited1. The service remained running with Result=success,
and a subsequent list still showed no enrolled fingers. This attempt is
inconclusive, not biometric rejection. The owner suspected delayed finger
placement; the unknown-error status alone does not prove a timeout or its cause.
No debug streams or raw logs were enabled to investigate it.

After the owner's feedback, one retry used:

```sh
fprintd-enroll -f right-index-finger <current user>
```

The assistant supervised it with a 750-second outer deadline; the deadline did
not fire. The CLI reported **16 `enroll-stage-passed` statuses**, then
**`enroll-completed`**, and exited0. A following normal-user `fprintd-list` exited0
and listed exactly one enrolled `right-index-finger` on Goodix TLS55X4.
The service reported active/running and Result=success. The standard CLI has no
private experiment completion observer, so a distinct library-close result was
not independently captured.

This is successful host enrollment and exposed persisted enrollment metadata,
not proof of verification accuracy or authentication integration. No image or
template bytes were inspected by the assistant or published. Earlier private
series remains separate; no key/firmware write, package/source download,
service-policy change, PAM/login/sudo/lock integration or Git publication.
Next propose one declared-same verification, then review before a declared-other
verification. Do not automatically proceed to authentication integration.

## Test019 — Normal-host declared-same verification MATCH

On 2026-10-14 the owner accepted one host verification with the enrolled right
index ("go for it"). The assistant launched the normal-user command, supervised
with a 120-second outer deadline:

```sh
fprintd-verify -f right-index-finger <current user>
```

The first attempt listed the enrolled right index, started verification, then
reported `verify-unknown-error (done)` and exited1. It produced no comparison
decision. The owner subsequently said they had been distracted and delayed
finger placement ("me colgue"). Record this as an inconclusive error with that
operator feedback; the error alone does not prove a particular device timeout.
The outer deadline did not fire.

One retry after that feedback again selected the enrolled right index and
reported **`verify-match (done)`**, exiting0. The owner had been instructed to
use the same registered right index; physical identity remains operator-declared.
This is one observed positive host comparison, not a reliability estimate.
The standard CLI has no independent library-close observer. Other-finger host
verification and authentication integration remain untested.

No enrollment/deletion command, template/image inspection, raw debug logging,
key/firmware write, download, service-policy/PAM/login/sudo/lock change or Git
publication occurred. Return control before a separately agreed declared-other
comparison with the same enrolled reference. A NO_MATCH from the normal CLI
alone can represent an error; retain the error-classification limit described
above rather than claiming independently observed library rejection.

## Test020 — Normal-host declared-other CLI NO_MATCH

On 2026-10-14 the owner accepted the proposed declared-other host comparison
("go for it"). The assistant ran the same normal-user verification command
against the enrolled `right-index-finger`; the owner was instructed to touch an
unenrolled finger, for example the left index. Physical identity remains under
operator control, not independently observed by the assistant.

The CLI listed the enrolled right index, started verification and reported
**`verify-no-match (done)`**, exiting1. No retry/error status preceded that result;
the supervising120-second outer deadline did not fire. The reference finger
selection was unchanged; no registration or deletion was performed.

This is one observed normal-CLI NO_MATCH in the requested other-finger category,
consistent with the intended rejection. It is **not independently confirmed
library rejection**: this fprintd version can map some internal verification
errors to NO_MATCH, and the host daemon does not include script17's separate
completion observer. A nonzero CLI exit alone does not distinguish rejection
from an error. Preserve that distinction in later repeatability/integration work.

The initial normal-host sequence now has observed device exposure, enrollment,
one declared-same CLI MATCH and one declared-other CLI NO_MATCH, plus the earlier
inconclusive unknown-error attempts. No accuracy/reliability rate or dependable
local authentication is established. No image/template inspection, raw logs,
key/firmware write, acquisition, service-policy/PAM/login/sudo/lock change or Git
publication occurred. Return control; propose a bounded repeated verification
series with appropriate error classification before authentication integration.

## Future removal and cleanup

Screen unlock was subsequently enabled with a separate PAM file; see
lock-screen integration (covered in a later commit: `lock-screen-integration.md`). Disable that integration
before removing the driver. Also restore the subsequently enabled
sudo/SDDM integration (covered in a later commit: `sudo-login-integration.md`). This controller does not
own/remove these PAM files or their separate backup namespace.

Finish the active operation and explicitly stop fprintd first if necessary. The
installed root-owned controller is self-contained, so removal does not require
keeping this repository mounted:

```sh
sudo -- /usr/bin/python3 /opt/thinkpad-fingerprint/manage.py --remove
```

Confirmation: `REMOVE THINKPAD FINGERPRINT`. It temporarily masks the inactive
service, validates the installed files/drop-in/roots/state, removes only its
matching configuration/payload/roots and reloads. It does not use `systemctl
revert`, restore a saved vendor unit, restart a daemon or erase private prints.
The currently installed stock fprintd unit can activate again through D-Bus.

To remove its own private **host** prints in the same operation, choose:

```sh
sudo -- /usr/bin/python3 /opt/thinkpad-fingerprint/manage.py --remove --purge-state
```

Confirmation: `REMOVE THINKPAD FINGERPRINT AND HOST PRINTS`. This deletes only the
validated project-owned state namespace, including templates. Choose this option
at removal time; after preserving/removing the payload, the removed controller
cannot purge state without a separately reviewed cleanup/reinstallation. Experimental
work state and `/var/lib/fprint` remain untouched in both modes.

A power loss, SIGKILL, filesystem failure or service-manager reload failure can
leave a partial deployment or an own runtime mask. `/run` masks vanish on reboot,
but a partial persistent drop-in/payload may remain. Stop and inspect the listed
owned paths; do not blindly rerun or remove foreign masks/overrides. Removal
errors restore stock activation when ordinary mask cleanup/reload succeeds, but
are not a power-loss-safe atomic cleanup guarantee. A modified installed payload
is refused rather than automatically deleting unreviewed data.
