# Temporary fprintd on a private bus

## Scope and status

The owner accepted this preparation on 2026-10-14 after reporting satisfactory
standalone recognition trials. This delivery uses the installed **fprintd 1.94.5-2**
and its actual command-line tools with our pinned local library. It prepares an
owner-run experiment. The first owner-run detection attempt failed in the parent
output relay; a second attempt reported `DBUS` before readiness. The latest owner
output reaches readiness but reports `DEVICE`. These results are inconclusive.
The relay, directory permissions and USB inventory view were corrected, then
the owner reported **successful hardware detection and private teardown**
(Test013). The owner subsequently reported completing native enrollment, with
private persisted-state checks passing (Test014). The owner reported one MATCH
after the declared-same native verification command (Test015), followed by one
NO_MATCH in the declared-other trial (Test016). The first contained native
recognition experiment is complete; repeated native testing and host integration
remain separate stages.
No host authentication integration is enabled.

The offline trial starts real D-Bus, Polkit and fprintd inside private namespaces,
checks authorization against the installed fprint policy, calls GetDevices and
runs the real fprintd-list with no USB. It passed. This establishes loading,
private service registration and a basic empty-device API exchange, not hardware
support. Source/ABI inspection alone would not have established those behaviors.

## What is contained

[17-fprintd-session.py](../scripts/17-fprintd-session.py) is a launcher for the
installed native daemon and CLI, not another recognition implementation.

- Installed binaries and policy plus the experimental library/observer are checked
  against recorded hashes and copied to a disposable read-only mount. The Nix
  loader uses cached dependencies, disables its host loader cache and rejects
  host library paths in the offline loading check. No package/source acquisition.
- A private system-type D-Bus and a real private Polkit provide authorization.
  Neither connects to the host buses or reads its Polkit rules. Existing services,
  PAM, sudo, login, screen locking and `/var/lib/fprint` are untouched.
- Private proc, dev, run, tmp, network and PID/mount namespaces hide home, host
  sysfs and service sockets. In a hardware mode, only **one selected 27c6:55a4
  character node** is bound. Cached standard descriptors must match interface 0,
  alternate 0 and bulk 0x01/0x82; a kernel driver causes refusal, never detach.
  The open O_PATH descriptor fixes which node gets mounted during selection.
- Hardware modes provide a read-only **synthetic** `/sys`, generated from the
  selected device's already validated cached descriptor bytes and bus/address.
  It contains one canonical `reader` entry, its derived uevent/dev attributes,
  configuration 1 and two internal links. No host sysfs mount, serial string,
  physical topology, speed, other device metadata or udev database is supplied.
  The child checks exact entries, bytes, links, modes and the read-only non-sysfs
  mount with no nested mounts before enabling `SYSTEMD_DEVICE_VERIFY_SYSFS=0`
  solely in its fresh native environment. This lets libudev read the controlled
  snapshot. Default/offline smoke still has no `/sys` or USB nodes.
- Hardware root mode preserves real UIDs so Polkit can become uid/gid 102.
  Its supervisor retains SETUID/SETGID for that drop and KILL to stop the
  different-UID process inside the private PID namespace. Native fprintd/CLI
  drop capabilities; Polkit drops to its unprivileged account. The ordinary-user
  offline smoke instead uses synthetic namespace uid-0 accounts with no
  capabilities; it does **not** test the real root privilege-drop/cleanup path.
- All daemons are owned by the session and stopped on exit. No persistent unit,
  drop-in, udev rule, library installation or host policy edit is created.

The daemon still runs reviewed community code with local fixes. This is a focused
compatibility experiment, not a complete audit or security certification.
Runtime sensor commands remain those explained in [the recognition report](private-verification.md):
chip enable/reset, firmware/key queries, TLS, runtime configuration, calibration,
frame acquisition, finger detection, LEDs and sleep. No key or firmware write.
Detection calls device inventory/listing only; enrollment and verification may
activate acquisition. Firmware support and key state are checked on driver open.

## Completion observation and errors

The installed daemon can translate cancellation and missing-data errors to
`verify-no-match`. Native CLI exit status alone therefore cannot identify a valid
biometric rejection. This is observed in the matching installed binary's
`src/device.c:623–624`, using already acquired debug metadata; it is not a complete
source review. CLI retries also cause fprintd to repeat verification internally.

The small [observer](../scripts/helpers/fprintd-observer.c) interposes only public
`fp_device_verify_finish` and `fp_device_close_finish`, forwarding their arguments
and return/error values to the original library. It records only fixed success,
match and error tags through a private nonblocking Unix seqpacket channel. No
image, template, score, device ID or error string enters that channel.

The launcher requires agreement between CLI status and the real library's
successful verification, followed by successful close. Missing, conflicting,
duplicate or error records, retries, timeouts, cancellation, Release errors or
forced shutdown are **inconclusive**. A pending result is withheld until private
teardown completes and its observer records are rechecked. Native no-match caused
by an error cannot become a correct rejection in this wrapper.

The installed CLI waits for Release, whose reply follows close_finish; a failed
close produces a CLI error. Expected daemon SIGTERM termination is process
cleanup, not independent evidence of sensor sleep. The completion observer is
necessary for the actual close gate. Forced exit cannot prove LED-off or sleep.

`fp_print_equal` still does not support SIGFM. Static inspection found its two
installed-daemon call sites behind STORAGE_LIST, absent in this selected image
driver; the bounded host-template workflows avoid them. This finding is limited
to the pinned build and reviewed routes, not a guarantee for every API.

## First owner-run experiment: detection

Run from the repository root:

```sh
python3 scripts/17-fprintd-session.py --plan
python3 scripts/17-fprintd-session.py --check-inputs
sudo -- /usr/bin/python3 "$PWD/scripts/17-fprintd-session.py" --run --detect
```

Type `FPRINTD 27c6:55a4 DETECT` at the confirmation. **No finger placement is
needed.** The launcher inventories the cached descriptors, starts the private
services with the bounded synthetic inventory view, calls the real installed
`fprintd-list` on that bus and tears down.
It does not activate the host fprintd through D-Bus.

Expected result: `Completed fprintd trial: DETECTED`. Discuss that safe terminal
output before the next hardware experiment. An error is inconclusive; do not
run the installed service or installer to bypass the guard.

## Later owner-run enrollment and comparison

Only after reviewing detection, use the prepared enrollment mode:

```sh
sudo -- /usr/bin/python3 "$PWD/scripts/17-fprintd-session.py" --run --enroll
```

Confirmation: `FPRINTD 27c6:55a4 ENROLL`. It runs the real `fprintd-enroll -f
right-index-finger` for the caller's account in the sandbox. fprintd needs its own
new private enrollment; the standalone `work/private-verification/` template is
preserved and never imported/overwritten. Keep off for calibration, touch on the
physical LED, lift on the prompt, and wait for subsequent touch prompts. Initial
finger-needed is not a calibration-ready signal; prompts use public device
properties and native progress. Successful completion needs 16 stages and close.
Actual device properties/native hardware output remain untested at preparation.

After reviewing enrollment, compare one declared category per command:

```sh
sudo -- /usr/bin/python3 "$PWD/scripts/17-fprintd-session.py" --run --verify --expected same
sudo -- /usr/bin/python3 "$PWD/scripts/17-fprintd-session.py" --run --verify --expected other
```

Confirm `FPRINTD 27c6:55a4 VERIFY SAME` or `FPRINTD 27c6:55a4 VERIFY OTHER`.
The actual tool is `fprintd-verify -f right-index-finger`; explicit selection uses
verification rather than identification. `same`/`other` remain operator
categories, not independently measured finger identity. A declared-other MATCH
stops authentication progress. Keep the template and parameters fixed.

| Result | Exit status |
| --- | --- |
| Detection/enrollment completed, or comparison consistent with category | 0 |
| Error, retry, invalid state, observation or close/teardown failure | 1 |
| Other + verified MATCH: false-accept observation, stop | 3 |
| Same + verified NO_MATCH: false-reject observation | 4 |
| Parent timeout / interruption | 124 / 130 |

Native boot is bounded to 15 seconds, listing to 15, enrollment to 600,
verification to 60 and teardown to 10. Parent hard limits are 750 seconds for
enrollment, 120 for detection/verification. No automatic enrollment overwrite or
parameter adjustment is performed.

## Private state and cleanup

Only enrollment/verification create ignored `work/private-fprintd/`: one native
state tree plus a private `series.json` freezing its contents and runtime pins.
After exit, directories are 0700 and files 0600, owned by the caller. During the
root trial, state ownership temporarily becomes root so capability-free native
processes can access it; it is restored afterward. Verification mounts the state
read-only and checks integrity again before reporting. Enrollment refuses an
existing series. Concurrent sessions are refused by a directory lock.

No raw logs are saved; daemon diagnostics are suppressed and hardware reports
contain allowlisted tags. Offline synthetic diagnostic files under ignored work
contain no device/biometric data. Never upload state or its private hashes.

Remove only this experimental series, including an interrupted root-owned one:

```sh
sudo -- /usr/bin/python3 "$PWD/scripts/17-fprintd-session.py" --cleanup
```

Cleanup does not open USB or touch the standalone template, source/build folders,
Nix dependencies or sensor key. It refuses unexpected contents/links. Detection
and offline smoke use disposable empty state and require no series cleanup.
A machine power loss or forcibly killed parent may leave state root-owned and
partial; use the scoped cleanup above before choosing a new enrollment.

## Inputs, checks and limits

All runtime binary/policy pins are in script 17; source/map pins and the complete
underlying source pin are checked by [18-build-fprintd-observer.py](../scripts/18-build-fprintd-observer.py).
The library remains `161c4a9fa432963b30d7303e1f6d8152269254f52850d14a77aae3e53399c2cd`.
The observer build is separate and uses the already cached Nix shell; it does not
rebuild/replace libfprint or execute hardware. Installed program changes fail
input checks instead of silently accepting another version.

The initial static candidate covered 35 ELF, all 47 requested fingerprint API
symbols and their symbol versions. The complete offline smoke goes further:
actual loader maps/help, private real daemon startup, real Polkit authorization
for enroll/verify/setusername, GetDevices returning no devices and the native
list command's expected no-device response. An intermediate loading check failed
because fprintd-list treats `--help` as a username; its real private-bus call now
checks that executable. The final smoke passed with the observer loaded.

[19-test-fprintd-observer.py](../scripts/19-test-fprintd-observer.py) passed six
native synthetic cases inside the no-USB sandbox: match, non-match and error,
each with successful/failed close. Versioned interposition and preservation of
return values/GError were tested against a synthetic API fixture, not hardware.
Unit tests also exercise isolation, state tampering/links/permissions, observer
error/duplicate/missing-record gates, prompts, deadlines and teardown failures.
Root UID mapping/privilege drop, real sensor enumeration and real status/property
signals remain owner-run checks.

Offline commands, as the regular user:

```sh
python3 -B scripts/17-fprintd-session.py --smoke
python3 -B scripts/19-test-fprintd-observer.py --run
python3 -B scripts/20-test-usb-inventory.py --run
python3 -B -m unittest discover -s tests -v
```

No new packages or source repositories were acquired. During initial ELF research,
binutils unexpectedly downloaded 842904 bytes of debuginfo to its user cache;
this was reported to the owner and DEBUGINFOD_URLS was disabled for subsequent
inspection/native environments. The three newly acquired public debug files were then moved into ignored
`work/elf-debug/` (0600) after inspection; unrelated cache entries were preserved.
No repeated debug acquisition followed.

Final integrated Python suite: **188 tests passed**, including 55 focused child
and 17 focused parent checks. Full private runtime and six native observer fixture
cases passed after integration. Source/artifact input checks and diff whitespace
checks passed. Independent read-only D13 review found no actionable defects.
It checked the frozen target, input pins, Python syntax and whitespace, inspected
existing test logs and confirmed the installed API/Release call sites statically.
It did not repeat native executions or test hardware/root privilege dropping.

## Test 010 — Owner detection attempt and relay correction

On 2026-10-14 the owner confirmed the detection command and reported an
`AttributeError` at `os.read(key.fd.fileno(), 1024)`. A selector key's `fd` is
already an integer. The parent had launched its child before reading output, so
the traceback establishes neither successful detection nor the child's reached
stage. It is an inconclusive trial, not evidence against sensor support.

The correction reads `key.fd` directly. Five new regression methods use real
subprocess pipes and the same selector path without USB, covering fragmented
success reports, comparison/close gates, failures, suppressed unknown output and
deadlines. They reproduced the reported exception before the correction; all
22 focused parent tests and **193 integrated Python tests** passed afterward.
Pinned runtime input checks and whitespace checks passed. The earlier offline
smoke uses `communicate()` rather than this relay and had missed the defect.

Read-only process inventory found no experimental sandbox processes remaining.
This does not prove sensor sleep. No assistant hardware execution, native rebuild,
installation or acquisition occurred. The prior independent D13 review predates
this focused correction. Repeat only the existing owner-run `--run --detect`
command before choosing enrollment.

## Test 011 — Private policy discovery and directory permissions

The owner repeated detection on 2026-10-14 and reported `INCONCLUSIVE: DBUS`
without `READY`. No native diagnostic or sensor result was supplied. Static
control flow points to the private authorization check before fprintd startup;
the original generic tag alone does not prove the reached stage.

A no-USB reproduction used installed `unshare`, `newuidmap` and `newgidmap` with
the existing subordinate-ID allocation to map the regular user to namespace UID0
and give Polkit a distinct UID102. It reused the pinned runtime assets and
root-style sandbox without any USB bind. A temporary test-only child copy allowed
UID102 in smoke mode and exposed bounded native errors into ignored local logs;
the production child configuration guards remain unchanged. This reproduced
`org.freedesktop.PolicyKit1.Error.Failed`: the enrollment action was not registered.
Polkit successfully dropped privileges, but could not read NSS or policy paths.

Inspection established that bubblewrap's implicit parent directories were 0700
in this mode, including `/etc`, `/usr` and the policy directory. The all-UID0
smoke had hidden this error. Script17 now sets 0755 on an exact list of disposable
runtime directories only. No chmod targets a host bind, USB node, `/experiment`
or `/state`; private data and its 0700/0600 permissions are preserved.

The identical multi-UID reproduction then passed real private bus/Polkit policy
checks, fprintd startup, empty GetDevices, native list and orderly teardown.
The ordinary no-USB smoke also passed. All **194 integrated Python tests** passed.
A regression checks the exact chmod paths,
modes and disjointness from host binds; it failed before the correction. Runtime
input and whitespace checks passed. A focused independent read-only review found
no actionable defects. No sensor, host bus, installation, source/package
acquisition or native rebuild was involved.

This tests distinct-UID privilege dropping and cleanup in a subordinate user
namespace, not host-root execution or sensor detection. Missing logind/sleep
inhibitor messages are expected in the private sandbox; no host service is added.
Repeat the existing owner-run detection command before enrollment.

## Test 012 — Missing USB inventory metadata

On 2026-10-14 the owner supplied `READY`, then `INCONCLUSIVE: DEVICE`, and later
repeated that output. The generic tag did not distinguish an empty list from a
parser failure; do not count repeated pasted output as independent trials. There
was no enrollment, finger comparison or demonstrated hardware detection.

Static inspection found a concrete isolation defect. The exact cached GUsb
0.4.9/libusb 1.0.29 chain discovers devices through udev/sysfs, not by scanning
the single bound USB character node. The launcher hid all `/sys`, so that node
alone could not supply inventory entries. The reviewed libusb source is
[the v1.0.29 udev enumeration backend](https://github.com/libusb/libusb/blob/v1.0.29/libusb/os/linux_udev.c#L247).
This explains missing enumeration; the old terminal tag alone did not establish
the daemon's actual returned list.

The correction adds [usb-metadata.py](../scripts/helpers/usb-metadata.py), an
original MIT helper, using the same descriptor read already performed during
selection. No additional host device queries are required. Descriptor layout is
validated in the parent, then bytes are frozen in the artifact manifest and
checked against the synthetic view in the child. The node binding, native
library/observer, sensor key, private state and host authentication are unchanged.
New fixed failure tags distinguish `DEVICE_EMPTY`, `DEVICE_MULTIPLE` and
`DEVICE_PROTOCOL` without printing raw D-Bus/native output.

[20-test-usb-inventory.py](../scripts/20-test-usb-inventory.py) ran three fixtures
with the real pinned libfprint `FpContext` and no USB nodes: missing `/sys` gives
zero devices; synthetic metadata with default filesystem verification gives zero;
the verified snapshot plus the private override gives exactly one
`goodixtls55x4`. No device-open/capture API is called. Native context construction
may attempt wakeup/persist configuration against the read-only synthetic view;
it cannot write host sysfs or access real hardware.

A separate ignored test-only smoke copy then exercised real private fprintd,
distinct UID102 Polkit, authorization, GetDevices returning the synthetic reader,
the actual native fprintd-list positive result and orderly teardown. Its config
adjustments allow a positive inventory in otherwise USB-free smoke mode; those
adjustments do not weaken production mode/node guards. Ordinary empty-device
smoke and frozen-input checks also passed. No driver/native rebuild, download,
package install, service change, assistant USB run or biometric inspection.

Metadata guard regressions cover extra devices, mutation, missing entries,
escaping links, hardlinks, permissions, and live/writable/nested sysfs mounts.
All **204 integrated Python tests** passed after the correction; frozen runtime
input and whitespace checks passed.
A focused independent read-only review found no actionable defects, inspected
the recorded fixture outcomes and did not rerun native code or hardware.
Real selected-reader detection remains owner-run and unverified. Repeat only
the same `--run --detect` command and review its output before enrollment.

## Test 013 — Owner-run native fprintd detection succeeded

On 2026-10-14 the owner supplied the corrected detection output: typed
`FPRINTD 27c6:55a4 DETECT`, private fprintd/Polkit ready, selected reader exposed,
private session teardown completed and `Completed fprintd trial: DETECTED`.
Record this as owner-reported hardware evidence; shell exit status was not
supplied. The assistant did not repeat detection or access the sensor.

The script's detection route requires one device from GetDevices and a successful
real fprintd-list call on the private bus before its final result. This confirms
the contained native stack exposes the reader. It does not establish native
enrollment, acquisition/TLS during an open session, verification accuracy,
sensor sleep or host login support. Earlier standalone recognition evidence
remains separate, and the failed detection attempts remain history.

Next return only the already prepared `--run --enroll` command. It registers the
right index through native fprintd-enroll, with up to 16 stages and a new private
template under ignored `work/private-fprintd/`. Keep off during calibration,
touch on the physical LED and lift on prompts. Wait for the owner's final output
before verification. No re-provisioning, installation, host integration or Git
publication follows from this detection result.

## Test 014 — Owner-reported native enrollment and persisted state

On 2026-10-14 the owner replied "done" after receiving the prepared right-index
enrollment command. No enrollment transcript, stage counts or exit status was
supplied. Record completion as owner-reported, not a directly observed native
capture/close result.

Assistant read-only host checks found exactly one private print plus the frozen
series manifest. Caller ownership, directory 0700/file 0600 permissions, frozen
state integrity and current runtime pins matched. No private path identifiers,
content or digests are published. The checks did not interpret biometric features,
load native code, connect to a bus or access USB. The standalone template was
not imported or replaced.

Next return one prepared `--run --verify --expected same` command using the
enrolled right index. Keep off for calibration and touch only on the physical
LED, then lift on prompts. Wait for the final decision/close report before a
declared-other trial. Native recognition and host authentication remain pending.

## Test 015 — Owner-reported native same-finger MATCH

On 2026-10-14 the owner replied "match" after receiving the prepared native
`--verify --expected same` command. Record one reported MATCH in the requested
enrolled-right-index category; finger identity is an operator declaration.
No terminal transcript or exit status was supplied, so observer/close records
were not independently observed. This is one positive recognition report, not
an accuracy estimate or authentication certification.

The assistant did not repeat USB access or inspect biometrics. Next return only
one prepared `--verify --expected other` trial with an unenrolled finger. Keep the
template and thresholds fixed; wait for its output. MATCH in that category stops
authentication progress. Errors/retries/timeouts remain inconclusive.

## Test 016 — Owner-reported native other-finger NO_MATCH

On 2026-10-14 the owner replied "no match ok" after receiving the native
`--verify --expected other` command. Record one reported NO_MATCH in the requested
unenrolled-finger category; identity remains an operator declaration. No full
terminal transcript or exit status was supplied, so observer/close records were
not independently observed. The assistant did not run hardware or inspect data.

The initial contained experiment now has owner-reported detection, enrollment,
one declared-same MATCH and one declared-other NO_MATCH. One consistent result
in each category does not establish accuracy, repeatability or reliable
authentication. Earlier standalone same-finger NO_MATCH history is retained.
No host fprintd activation/configuration, PAM, sudo, login, screen locking or
signing-key authorization was enabled by these trials.

Return control to the owner. A proposed next delivery is to prepare a contained,
reversible host-service deployment with exact changes/removal steps for review;
installation, host bus access and authentication changes need their own scope
agreement. Preserve the private native series and current thresholds meanwhile.
