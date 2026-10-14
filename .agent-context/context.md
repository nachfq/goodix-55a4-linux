# Project context

## Purpose and ownership

The owner is investigating Goodix USB `27c6:55a4` on a ThinkPad E14 Gen 2.
This is a hands-on learning project with a practical goal: establish device
access, fingerprint acquisition, enrollment, and verification, including explicit
rejection of other fingers, before authentication integration.

The owner wants to understand each experiment. They initially chose to run the
scripts personally, then explicitly delegated execution of the current build
delivery to the assistant on 2026-10-08 ("do not ask me to execute things").
That delegation does not remove the separately agreed installation and persistent
sensor-change review points. Small scripts are part of the learning experience,
rather than merely automation. The initial
conversation chose to audit community work before deciding between maintaining a
libfprint-based implementation and developing missing components. Neither choice
has been made. The audit remains partial.

The public repository is [nachfq/goodix-55a4-linux](https://github.com/nachfq/goodix-55a4-linux).
On 2026-10-08, the owner explicitly chose versioned project context suitable for
that public repository.

## Orientation

- [README](../README.md): project scope and starting hardware/software facts.
- [Walkthrough](../docs/walkthrough.md): interactive scripts and documented
  offline test command. Tests of synthetic packets do not establish hardware support.
- [Sources](../docs/sources.md): pinned revisions and licensing inventory.
- [Source review](../docs/source-review.md): reviewed initialization, provisioning,
  firmware paths, and an unresolved TLS retry defect.
- [Probe trial](../docs/probe-test.md): the owner's completed bounded query and
  its evidentiary limits.
- [Staged plan](../docs/plan.md): existing progression, with later stages still
  subject to separate agreement.
- [Local build initiative](plans/local-driver-build/plan.md): the agreed next
  preparation delivery and its boundaries.
- [Nix dependencies](../docs/nix-build.md): prepared environment, content pin,
  acquisition and cleanup boundaries, and execution limits.
- [First local build](../docs/build-test.md): assistant-observed compilation,
  static ELF metadata, and TLS error-path defects to review before loading.
- [TLS error fix](../docs/tls-error-fix.md): separately attributed local patch,
  isolated sanitizer regression tests, and corrected rebuild.
- [Key provisioning trial](../docs/key-provisioning-test.md): owner-reported
  MISMATCH-to-MATCH result after one write; no capture/power-cycle evidence.
- [First capture route](../docs/first-capture-plan.md): completed one-shot key
  experiment and remaining work for a real image.
- [Private capture preparation](../docs/private-capture.md): the newly authorized
  complete safety variant, build, private acquisition helper and offline smoke.
- [TLS flow correction](../docs/tls-flow-fix.md): separate second patch, actual-function
  sanitizer cases, original-function negative controls and changed-unit syntax.
- [TLS/activation review](../docs/tls-activation-review.md): verified retry and
  failure/lifetime findings, actual command sequence and proposed offline corrections.
- [Isolated load](../docs/library-load-test.md): complete library dependency
  resolution and basic GTypes in an offline sandbox, without sensor access.

Downloaded community sources and the assembled patch live under ignored `work/`;
they are not supplied by a fresh clone of this repository. The repository's own
probe implements a bounded query path instead of importing community utilities.

## Evidence that changes the next decision

The installed stack sees the USB device but exposes no usable reader through
fprintd; see the [baseline](../docs/baseline-test.md).

On 2026-10-08, the owner supplied output from personally running
[`03-probe-sensor.py`](../scripts/03-probe-sensor.py). Regular-user access failed
with USB permission error 13. A subsequent run through one-shot sudo reported
firmware `GF3268_RTSEC_APP_10062` and expected key state `MISMATCH`, followed
by USB resource cleanup.

This is owner-reported execution evidence, not an assistant-run hardware test.
`MISMATCH` means the returned state differed from the probe's public expected
hash; it does not prove the key is absent or the sensor is broken. No capture,
enrollment, or biometric verification has been demonstrated.

Static inspection of the assembled driver shows its firmware-string check accepts
this reported family, but its activation requires the expected key state. That is
a prerequisite check, not evidence of complete firmware compatibility. In contrast,
the pinned full dump entry point targets firmware `10041` and can erase another
valid-family version. It must not be substituted for this query probe. See the
[source review](../docs/source-review.md) and its pinned source links.

The completed bounded query is distinct from community-driver hardware execution;
the latter and the biometric tests remain unperformed.

## Consequential decisions and unresolved questions

In the conversation preceding discovery, the owner agreed to preparation of an
unprivileged local build. That bounded agreement does not authorize additional
package installations, persistent provisioning, or running the community driver
on hardware.

Recovery of the original sensor key and Windows coexistence have not been
demonstrated. Separate key selectors and third-party success reports do not settle
those questions. On 2026-10-08, the owner stated that they do not use Windows and
do not require Windows compatibility. This removes it as a project requirement;
it is not authorization to write a key or evidence of recoverability.

The matching behavior, remaining capture paths, memory handling, upstream
divergence, and complete dependency/license review remain open. A successful build
will establish compilation only. Maintaining a fork or reimplementing components
remains a later evidence-based decision.

The build preflight performed by the assistant on 2026-10-08 found missing Meson,
GLib development tools, and doctest. Installed OpenCV is version 5, whereas the
pinned build description requests `opencv4`. A syntax-only check of existing SIGFM
against OpenCV 5 headers passed; full linking and recognition remain untested.
This invalidates treating the failure as simply an absent OpenCV package. Resolve
the build-dependency choice before modifying pinned inputs or acquiring packages.

The owner subsequently chose Nix for contained dependencies and on 2026-10-09
authorized continuing preparation with more discretion. After changing session
permissions, the owner explicitly authorized the predicted Nix downloads and
library-only compilation. `nix/shell.nix` preserves the reviewed driver inputs
and supplies OpenCV 4.13.0 from content-pinned Nixpkgs. The cached source's Git
tree matches upstream commit metadata; default expression evaluation passed.
Dependencies were acquired from cache.nixos.org after a dry run estimated
149.1 MiB download and 500.7 MiB unpacked. Preflight and the interactive build
exited 0, producing `work/libfprint-build/libfprint/libfprint-2.so.2.0.0`.
Static ELF inspection passed; the library has not been loaded or installed.
Nix dependencies have no project-specific permanent GC root yet.

Compilation exposed a confirmed one-byte allocation overflow in the pinned
`goodixtls.c` error constructor, which also leaves `GError.domain` unset and
does not check for a null OpenSSL reason. No runtime crash was observed. The
recommended next delivery is a separate reviewed TLS error-path correction
with offline checks before driver execution. Other compiler warnings and the
previous retry defect remain unresolved; see the build report. Source pins and
canonical patch diff were reconfirmed unchanged after compilation. Further
USB access, provisioning and service integration remain separately scoped.

The owner accepted that build evidence and explicitly requested the constructor
fix and continuation on 2026-10-09. The separate tracked patch changes only
`err_from_ssl()`; baseline source and build are preserved. The original isolated
constructor reproduced an ASan heap overflow; all seven fixed cases passed with
ASan/UBSan. The integrated suite passed 32 offline tests. Full corrected preflight
and compilation exited 0, with static ELF inspection and no further downloads.
Fixed source/build paths are `work/libfprint-tls-fixed` and
`work/libfprint-tls-fixed-build`; see the trial for hashes. No driver installation,
loading or hardware execution followed. The TLS retry defect and other warnings
remain; recommend reviewing those before a separately agreed runtime experiment.
The owner asked about damaging the laptop: distinguish low-impact local
build/tests from persistent sensor operations, which can leave the reader unusable
and have no demonstrated recovery. Do not claim zero risk or complete audit.

On 2026-10-09 the owner accepted continuing after the correction and explicitly
authorized preparing and executing a sandboxed offline load ("do it"). The
assistant used existing bubblewrap and Nix inputs, with no further acquisition.
The exact corrected artifact passed isolated immediate dependency resolution and
the `FpDevice`, `FpPrint`, `FpContext` GType-name checks. A first attempt stopped
in OpenBLAS allocation under the 1 GiB process limit; adding one-thread settings
allowed the final trial to exit 0. The suite passed 41 offline tests. Temporary
copies were removed. No objects were constructed, USB devices accessed, service
configuration changed or biometric data captured. This does not validate fprintd
compatibility or hardware support. Outstanding TLS retry/activation review is the
proposed next delivery; key provisioning and hardware trials remain separately scoped.

The owner accepted that report and authorized the proposed focused TLS retry and
activation review on 2026-10-09. The assistant inspected the unchanged pinned sources
and documented seven open findings: recovery budget reset; lost/false-success TLS
completion; unsynchronized worker teardown; unbounded waits; unsafe partial TLS
initialization; USB claim/release failures reported as success; and returned
key-state hash disclosure in debug/errors. This is static evidence, not observed
hardware hangs/crashes. It also corrects the earlier open-path interpretation:
a successful USB claim returns before the community-added LED-off call.
No fixes, compilation, driver execution, downloads or USB access were performed
in that delivery. Next proposed implementation is a bounded retry/completion fix
with actual-function offline failure tests. Other findings still need correction,
and MISMATCH/provisioning remain separate from host-side fixes.

On 2026-10-13 the owner requested a status recap, then authorized the proposed
retry-counter/TLS-error correction ("do it"). A second separate patch/worktree
`work/libfprint-flow-fixed` preserves earlier inputs/artifacts. Its image budget
survives command completion and stops after two recoveries. TLS completion clears
callback state before invocation, propagates reported phase/confirmation errors
and waits for a worker-published atomic result before success. Main-context polling
reports worker failure during asynchronous waits; it is not a deadline and cannot
make blocking socket reads cancellable. Zero initialization and absent-resource
guards support reported init-error completion without resolving complete R5.
Three complete changed C units passed syntax using pinned prior generated flags;
24 extracted-function synthetic cases passed ASan/UBSan, two controls restoring
original functions failed the expected regression assertions, and 46 Python tests
passed. No complete new library was rebuilt/loaded or real TLS handshake performed.
R3–R7 remain open; worker teardown/concurrency is the proposed next delivery.
The key mismatch and any provisioning remain separately scoped. Changes are still
uncommitted; this correction request did not authorize Git publication.

On 2026-10-14 the owner clarified that the Linux method uses a publicly known
shared key, not a personally generated asymmetric key, and asked to continue
because they want a real trial. A separate `08-provision-key.py` is prepared to
check firmware/key and, only with exact typed confirmation, send one fixed
persistent write and perform a private postcheck. Default/dependency modes open
no device; thirteen synthetic checks and 59 integrated Python tests passed. The
existing PyUSB/libusb environment remains available without downloads.
**At preparation handoff no provisioning or capture had run; concrete write
authorization was still pending.** The user's general desire to try the reader does not bypass
their explicit scope-agreement instruction. The first-capture report gives the
exact payload, invocation and limits. The key experiment avoids the C driver;
actual capture still needs remaining driver fixes, a new complete build and a
bounded standalone acquisition program. Reprovisioning and original-state
recovery are not demonstrated; Windows compatibility is still not required.

The owner then explicitly authorized one provisioning attempt ("try it", no
Windows requirement). The assistant checked existing dependencies and tried the
prepared script unprivileged in a PTY; it exited 1 at get_active_configuration
with USB error 13 before NOP, firmware/key queries, confirmation or key writing.
USB resources were disposed. Non-interactive sudo required an OS password, so no
privileged provisioning invocation was started. The owner asked for the commands
and subsequently ran the already authorized one-shot sudo invocation themselves.
Their reported result follows; no further write is authorized by the earlier agreement. No key write has
occurred in the assistant's attempt. No automatic retries are authorized.

On 2026-10-14 the owner supplied the privileged script output: exact firmware
`GF3268_RTSEC_APP_10062`, pre-write MISMATCH, typed WRITE 27c6:55a4 KEY confirmation,
post-write MATCH, and USB resources released. Record as owner-reported execution,
not an assistant-observed USB trial. Shell exit status was not supplied. The
expected state was met immediately after one known-key provisioning operation;
persistence across reboot/power loss and restoration are still unproven. No
TLS handshake, image capture, enrollment or verification occurred. Avoid repeating
the key write unnecessarily; if state needs reconfirmation use the bounded query.
Remaining host driver fixes/build/private capture preparation are proposed next,
with hardware operations separately explained and agreed. The original mismatch
is historical and must not be presented as the latest observation.

The owner's eventual interests include local authentication, web logins, and
authorizing signing-key use. These are distinct integrations: fprintd alone does
not enable passkeys, and commit signing still requires SSH or GPG keys. They are
outside the initial recognition milestone.

## Related projects

Consult the [source inventory](../docs/sources.md) for exact revisions and URLs:
Hydrogell supplies the community patch and wrappers; TheWeirdDev supplies its
libfprint base; goodix-fp-dump supplies protocol and provisioning references.
GuNanOvO is an unaudited alternative, and official libfprint is the future upstream
comparison target. These sources inform this project; none is established as a
trusted installation path by this partial review.

On 2026-10-14, after receiving the MATCH result, the owner accepted preparing the
remaining driver safety fixes, full rebuild and standalone private acquisition
("go for it"). This accepts the immediate key-state evidence, not biometric
support. D9 of the local build initiative covers this whole preparation as one
bounded delivery; no hardware acquisition is run in this delivery. The new
source variant is `work/libfprint-capture-fixed`, with separate local patch0003
and fresh build/helper paths. Earlier source/artifact pins remain preserved.

D9 preparation checks passed using existing dependencies: 50 native sanitizer
cases, actual-device-function harness/negative controls, 78 Python checks, full
library/helper compilation (plus focused NOP integration rebuild), static ELF
inspection and sealed executable/library smoke in a no-host-USB sandbox. The
runtime smoke writes and deletes a synthetic 2x2 PGM, not sensor data. New native
pins and command effects are in the private-capture report. Acquisition hardware
mode has not run. Independent review reported no confirmed actionable code
defects; stale handoff documentation was corrected (D9-R1). The focused
documentation follow-up confirmed the finding resolved; owner acceptance
remains pending. No
commit/push requested. MATCH must still not be equated with fingerprint support.

On 2026-10-14 the owner ran capture mode with its typed confirmation and supplied
USB_SELECTION failure before INIT/OPEN/CAPTURE. No Goodix activation, realTLS or
image operation was reached; the latest key MATCH is still the earlier trial.
A confirmed host validation defect was found: GUsb get_kind reads descriptor type5,
not bmAttributes bulk type2. The helper now checks raw active libusb descriptors
bound to the selected USB identity/current configuration, and emits distinct safe
selection error tags. Driver library/patch pins are unchanged; only the helper
was rebuilt using cached libusb development inputs. Twenty focused Python checks
and the complete isolated runtime/synthetic-descriptor/PGM smoke passed. Earlier
independent review covers D9, not this focused helper correction; direct checks
are recorded in docs/capture-selection-test.md. No corrected hardware run or Git
publication performed. Return the same owner-run command for a new finite trial;
no further key provisioning is needed or authorized.

On 2026-10-14 the owner supplied the corrected capture output: selected-device
construction/open, activation/calibration, lift prompt, successful close, one
108 x 88 image and a private PGM path. Record as owner-reported hardware evidence;
no image/private trial identifier is stored in shared context or documentation,
and the assistant did not open the image or repeat USB access. Shell exit status
was not supplied. Successful capture follows the prepared driver's firmware/key,
TLS/decryption/calibration route; individual commands are inferred from code,
not independently observed in a USB trace. Test005 docs/first-capture-test.md
records the evidence and current native artifact pins. This supersedes the
selection failure as the latest physical result, while preserving that earlier
failure as history. Capture passed once; image quality, repeated trials,
enrollment/verification and power-cycle persistence remain untested. Next propose
private local enrollment and controlled registered/other-finger verification as
one bounded delivery; wait for agreement before preparing/executing that stage.
No new provisioning, installation, PAM/service integration or Git publication is
authorized by this result.

The owner subsequently reported inspecting the private image and recognizing a
fingerprint-like appearance. Record this as owner visual feedback, not an
assistant pixel inspection or objective quality/matching evaluation. They asked
about driver ownership and integration: explain the patched community libfprint
userspace driver, own diagnostic/acquisition helpers, planned fprintd/PAM route,
and separate cryptographic-key authorization. This question does not authorize
installation, authentication configuration or implementing later integrations.

On 2026-10-14 the owner accepted continuing with private enrollment and controlled
verification preparation ("perfecto sigamos"). D12/S12 defines this bounded
host-only delivery, preserving the current capture stack and thresholds. Review
matcher/template/error paths, prepare one private template and explicit same/other
verification, compile/test offline with existing dependencies and independently
review before handoff. No hardware mode or authentication integration is run in
preparation; exact sensor commands and local template storage must be explained.

The D12 host-only implementation adds a separate verification-safety variant,
private right-index enrollment and declared-category one-trial comparison.
Concrete SIGFM ownership, parsing, serialization and match error guards were
corrected without changing threshold 72/minimum 5/16 stages. Full fresh build
and final targeted rebuild, actual-function sanitizer suite with two original
failure controls, 116 Python tests and sealed full-runtime public FpPrint
round-trip/prompt/deadline smoke in a no-host-USB sandbox passed. Independent
review found no actionable defects; pins were independently checked and existing
test logs inspected. Native smoke covers serialization/prompts/deadline, while
parent decision gates use synthetic reports. No physical enrollment/verification
has run. See
[the operation/report](../docs/private-verification.md).

The owner then reported completing script14 enrollment on 2026-10-14. No terminal
transcript or exit status was supplied. Assistant host-only checks confirmed the
private template/manifest's existence, required ownership/permissions, format
header and frozen artifact/template integrity, with no content/digest published,
no biometric feature parsing, native load or USB access. Enrollment is now
owner-reported with persisted-series evidence (Test006 in private-verification).
Recognition remains untested. Return the already prepared one-trial declared-same
verification command for the owner, then wait for their result before the
declared-other trial. No re-enrollment/threshold tuning/integration is authorized.

On 2026-10-14, after receiving the declared-same verification command, the owner
reported one NO_MATCH and one MATCH. No full transcript, exit status or placement
details were supplied; enrolled-finger identity follows the requested procedure
and remains an operator declaration. Record one false-reject observation and one
consistent match, not an accuracy estimate or reliable authentication (Test007 in
private-verification.md). The assistant did not execute USB or inspect biometrics.
Next return one prepared declared-other trial with an unenrolled finger, retaining
template/thresholds; wait for output. A false accept stops authentication progress.

The owner next reported NO_MATCH following the prepared declared-other command
on 2026-10-14 (Test008). No full transcript/exit status or other-finger identity
was supplied; category follows the requested procedure. Reported totals: same
finger 1 MATCH/1 NO_MATCH; other finger 0 MATCH/1 NO_MATCH. One observed correct
rejection and no reported false accept in that one trial do not validate accuracy.
No assistant hardware run or biometric inspection occurred. Proposed next bounded
step: five additional same and five with the same other finger, recording decisions
and errors separately; await agreement before preparing a new series workflow.
Preserve template/thresholds; no integration, reinstall or new provisioning.

The owner accepted five-same/five-other manual pilot instructions, then reported
"anda perfecto" on 2026-10-14 (Test009). This is qualitative satisfaction, not
supplied per-attempt counts/errors or a validated accuracy rate. Keep earlier
NO_MATCH history. No assistant hardware runs or biometrics inspection. Proposed
next direction, not yet chosen/implemented: contained fprintd compatibility and
owner-run enrollment/verification, keeping the library separate before PAM/login
integration. Read-only installedservice inspection and ELFsymbolcoverage passed:
all 47 requested fp_* names are present; ABI/dependency/runtime behavior remain
unverified. No daemon activation, service change, installation or acquisition.

The owner accepted preparing temporary contained fprintd on 2026-10-14
("go for it"). D13/S13 is autonomous within preparation/offline checks, with
owner-run detection first. The private bus requires a real private Polkit daemon,
not a bypass; reuse installed components and cached Nix dependencies, keep state
separate, and do not connect to the host system bus or change auth/services.
During read-only binutils research it unexpectedly fetched 842904 bytes of
debuginfo into its user cache; reported to the owner, automatic symbol acquisition
disabled with DEBUGINFOD_URLS empty. No packages/sources/repos acquired or sensor
executed. Do not repeat acquisitions. Full trial details belong in fprintd docs.

D13 preparation now has installed native daemon/CLI, private bus and real private
Polkit, isolated cached Nix loading and caller-owned private state/cleanup.
Root runtime preserves UID102 dropping; its private-PID supervisor retains
CAP_KILL to stop Polkit, with no native fprintd/CLI capabilities. Offline smoke
uses synthetic UID0 namespace accounts and does not test real privilege dropping.
The complete no-USB private service/authorization/GetDevices/native-list smoke
passed. Because fprintd maps some errors to no-match, a separately built original
observer records real public verify/close finish results; matching/error/close
interposition preserved outcomes across six versioned synthetic native cases.
No driver/library changes or hardware runs. fp_print_equal staticcallroutes are
behind STORAGE_LIST notannouncedbythisdriver; Release waitsactualclosefinish.
See [contained fprintd](../docs/private-fprintd.md). Final checks/review pending;
owner's first next hardware step is script17 --run --detect, no finger required.

D13 preparation completed: final complete private no-USB fprintd/Polkit/CLI
startup/authentication/basic API smoke passed with the observer loaded; six
versioned synthetic observer completion cases and 188 integrated Python tests
passed. Independent read-only review found no actionable defects and checked
pins/AST/whitespace/API call sites, inspecting existing logs without rerunning
native tests. Root UID102 drop/cleanup and hardware remain untested; next owner
command is script17 --run --detect with typed FPRINTD27c6 confirmation and no
finger placement. No host service/PAM/auth changes, install or hardware run.
The three accidentally acquired public debug files were relocated into ignored
work/elf-debug/ (842904 bytes,0600); no unrelated cache entries touched.
No Git publication. Delivery awaiting human review/physical detection output.

The first owner-run script17 detection attempt on 2026-10-14 raised
AttributeError in the parent relay: selector key.fd is already an integer, so
key.fd.fileno() was invalid. Child startup preceded the read; detection and the
reached hardware stage are unknown. Test010 in private-fprintd.md records this
inconclusive result. The one-line correction uses os.read(key.fd, 1024).
Five new real-subprocess-pipe regression methods reproduced the exception before
the fix; 22 focused parent and 193 integrated Python tests passed after it, along
with pinned runtime inputs and whitespace checks. No experimental sandbox
processes remained in read-only inventory; this does not establish sensor sleep.
No assistant USB/native run, rebuild or acquisition. Earlier D13 independent
review predates this correction. Next: owner repeats the existing --run --detect
command, no finger; wait for output before proceeding to enrollment.

The next owner detection attempt on 2026-10-14 reported FAIL DBUS before READY
(Test011). A no-USB multi-UID reproduction using existing unshare/subordinate ID
maps and a test-only child copy reproduced PolicyKit action-not-registered:
implicit sandbox /etc,/usr and policy parents were0700, unreadable after Polkit
dropped to UID102. Script17 now chmods an exact set of synthetic runtime dirs to
0755; never mounted host inputs, /experiment, /state or USB. Private state stays
0700/0600. The identical distinct-UID no-USB private bus/auth/fprintd/list/teardown
trial, ordinary smoke and 194 Python tests passed after correction; guard regression failed before
and focused independent read-only review found no defects. Production child and
native pins unchanged. Host-root runtime and sensor route still await owner retry.
No assistant sensor run, host bus/service change, acquisition, rebuild or Git
publication. Return the same --run --detect command and wait before enrollment.

Latest owner output reaches READY then FAIL DEVICE; it was later pasted again
(Test012). Do not infer separate trial counts or biometric failure. A concrete
isolation defect was established: cached libusb/GUsb udev inventory needs sysfs
metadata, but17 hid /sys and bound only the USBnode. Script17 now builds an exact
readonly synthetic /sys from alreadyvalidateddescriptors and bus/node, noextra
hostsysfsreads or livehostsysfsmounts. OriginalMIT usb-metadata.py validates
entries/links/bytes/modes; child verifies readonlynonsysfs/nochildmounts and
frozenartifacthashes before private SYSTEMD_DEVICE_VERIFY_SYSFS=0. Parent validates
endpointlayout; child validates frozenbytes/tree. No speed, serial or realtopology.
Three script20 actualFpContext noUSBnode fixtures gave0/0/1goodixtls55x4; ignored
distinctUID102 realprivatefprintd/Polkit/GetDevicesone/nativeCLIlist/teardown smoke
also passed withtest-onlypositivesmokeconfig. Productionguards retained. Ordinary
emptyinventorysmoke/inputs passed; focusedindependentreview nofindings. No native
rebuild,acquisition,hostauth/service change,sensor execution orbiometricinspection.
New EMPTY/MULTIPLE/PROTOCOL tags disambiguateinventoryerrors. Real owner detection
retry remainsnext; waitforoutput before enrollment. No Gitpublication authorized.
Final integrated Python suite:204 tests passed, with frozeninputs/whitespacechecks
passing. Source/helper pins are in17/20; original driverlibrary andobserver unchanged.

Owner's next corrected script17 --run --detect output on2026-10-14 succeeded:
typed confirmation, privatefprintd/Polkit READY, selectedreader exposed, private
teardown completed, final DETECTED (Test013). Shell exitstatus notsupplied. This
is owner-reported hardware evidence, not anassistant USBtrial. The native stack
nowexposes the reader; acquisition/TLS onopen, nativeenrollment/verification and
hostauthentication remainunverified. Priorstandalone evidence stays separate.
Return only prepared --run --enroll forRIGHT INDEX,16stages/newprivatefprintd
template,offduringcalibration/touchonLED/liftonprompts. Waitfor finalowneroutput
beforeverification. No newprovisioning,install/integration orGitpublication.

Owner replied "done" to the prepared native enrollment command on2026-10-14
(Test014). No terminal transcript/stagecounts/exitstatus supplied; completion is
owner-reported. Assistant read-onlyhost checks confirmed exactlyoneprint+frozen
manifest, callerownership and0700/0600permissions, currentruntimepins/statehash
integrity; no contents/digests/privateidentifiers published, featureinterpretation,
nativecode load,bus orUSB. Next return exactlyone prepared declared-same native
verification command with enrolledRIGHT INDEX, template/thresholds fixed; wait
for decision/close output beforeotherfinger. Hostauthentication stilloutofscope.

Owner replied "match" after the native declared-same command on2026-10-14
(Test015). Record one operator-declared enrolledfinger MATCH; no transcript or
exitstatus supplied, observer/close notindependentlyobserved. No accuracyrate or
authenticationvalidation. Assistant noUSB/biometricinspection. Next oneprepared
--run --verify --expected other withunenrolledfinger, samefixedtemplate/thresholds;
waitforoutput. OtherfingerMATCH stopsintegration; errors/timeouts inconclusive.

Owner replied "no match ok" after native declared-other command on2026-10-14
(Test016). Record one operator-declared unenrolledfinger NO_MATCH, no transcript
or exitstatus supplied; observer/close notindependentlyobserved. Native initial
milestone nowcomplete throughownerreports: detect,enroll,sameMATCH,otherNO_MATCH.
No nativeaccuracy/repeatability/authreliability claim; retainolder standalone
sameNO_MATCHhistory. Assistant noUSB/biometricinspection. Returncontrol; propose
a bounded nextdelivery preparing contained,reversiblehostservicedeployment with
exactchanges/removal forreview. Notauthorizedyet: install,hostbus/PAM/service
config/login/sudo/lock/signing integration. Preserveprivate series/thresholds.

On 2026-10-14 the owner accepted the proposed contained host-deployment preparation
("do it"). D14/S14/T26–T28 is autonomous within preparation/offline checks only.
Reuse installed daemon/Polkit client, exact experimental library and cached Nix;
no acquisition, actual install, fingerprint API call on the host bus, sensor run,
PAM/login/sudo/lock change or Git publication. Read-only unit/activator/policy
inspection established existing systemd activation and STATE_DIRECTORY support.

Prepared work/host-deployment-bundle contains frozen daemon/library/client,
controller/config/drop-in, attribution/LGPL text and manifest. Proposed installed
ownership is /opt/thinkpad-fingerprint, one service drop-in, 13 own Nix GC roots
(176 cached store paths transitively), and /var/lib/thinkpad-fingerprint private
host state. No experimental template migration or /var/lib/fprint change.
Controller refuses active/foreign service state, destinations, drop-in entries,
masks, modified payloads/roots/state and symlink/hardlink boundaries. Ordinary
install errors roll back own new files, preserving existing owned state. Own
temporary runtime mask blocks activation during changes; abrupt termination and
reload failures require partial-state review. Remove preserves host templates;
explicit purge deletes only own host state. No global Nix GC or key restoration.

Unlike script17, future host service uses real system bus/Polkit/USB inventory,
read-only sysfs and a frozen /opt payload; no synthetic metadata override or
experimental observer/close gates. Host native no-match may be an error. Debug
streams/core limit are suppressed; package updates do not auto-update the copy.
Installation would enable automatic host D-Bus activation and requires separate
agreement, not merely consent to copy files. See docs/host-deployment.md.

Offline relocated loader/library maps and actual daemon help passed with no host
bus, sysfs, USB or /usr fallback. Generated service passed isolated systemd-analyze
verification (man/unit/environment generators disabled). All33 deployment checks,
including19 actual disposable-root transactions with fake service/Nix calls,
passed; general suite237 checks passed with19 omitted there and covered separately.
No actual host GC root, mask, reload, installation or hardware test. Independent
D14 review found D14-R1: ActiveState alone did not prove its runtime mask was
effective after reload. Require LoadState=masked and FragmentPath of the own mask
before transactions. The synthetic regression failed before and passed after,
covering install and remove. Corrected source pins/bundle and offline checks were
renewed; one focused independent follow-up verified snapshot d58218b2, pins,
AST and simulated guard behavior, with D14-R1 resolved and no remaining actionable
findings. Reviewer inspected logs without repeating native/transaction runs.
After review, only outcome/task-status documentation changed. D14 is complete
and awaiting owner review; actual host integration remains untested. No further
delivery or Git publication.


On 2026-10-14 the owner accepted applying the reviewed deployment and checking
normal fprintd detection ("hagamoslo"). This authorizes only that bounded host
installation/detection delivery. Preflight pins, dependencies and stock inactive
unit passed; own paths did not exist. sudo -n required a password, so one-shot
pkexec with the normal Polkit authentication flow launched the unchanged reviewed
controller in a terminal. Authorization succeeded, typed INSTALL THINKPAD
FINGERPRINT was supplied and installation exited0. No policy/sudo rule changed.
Post-install exact root-owned payload/drop-in/13 roots, root0700 state parent and
removed temporary mask passed read-only checks. Normal-user fprintd-list exited0
and exposed one Goodix TLS55X4, no host prints yet; real service active/running,
Result=success, effective own loader/StateDirectory verified. See Test017 in
host-deployment.md. Native host enrollment/verification are still untested.
No template migration/inspection, new key/firmware write, acquisition, PAM/login/
sudo/lock integration or Git publication. Earlier private series remains intact.
Installation/detection delivery complete; return control before a new host
right-index enrollment, then separately review same/other verification.


On 2026-10-14 the owner accepted continuing with the proposed normal-host
right-index enrollment ("oka sigamos"). The assistant launched normal-user CLI;
the owner placed the finger. Preflight list had no host prints. First command's
right-index was invalid; corrected identifier is right-index-finger. First
corrected attempt produced enroll-unknown-error, zero stage-passed, exit1;
service still healthy, list still empty. Owner suspected being late to touch;
that cause is unproven. After that steering, one retry produced16stage-passed,
enroll-completed and exit0; following list exited0 with one right-index-finger.
Outer750s timeout did not fire. Test018 in host-deployment.md records the result.
No assistant image/template inspection, raw logs, key/firmware write, acquisition,
service-policy or PAM/login/sudo/lock change, or Git publication. No independent
library-close observer in host mode. Host enrollment is complete; return control
before one declared-same verification, then review before declared-other.


On2026-10-14 the owner accepted one normal-host declared-same verification
("go for it"). Assistant ran fprintd-verify -f right-index-finger as the normal
user, with120s outer deadline. First attempt listed the enrolled finger and
started, then verify-unknown-error(done)/exit1; no decision. Owner said "me
colgue" (delayed attention/placement). Record inconclusive, no proven particular
sensor timeout. One retry after that steering produced verify-match(done)/exit0.
Outer deadlines did not fire. Test019 records one observed positive comparison
with operator-declared enrolled right index; no independent close observer or
accuracy claim. No re-enroll/deletion, image/template inspection, debug logs,
key/firmware write, acquisition, service-policy/PAM/login/sudo/lock change or
Git publication. Return control before a declared-other host comparison. Normal
CLI NO_MATCH can be an error; do not equate it with independently observed
library rejection. Authentication integration remains pending.


On2026-10-14 the owner accepted the proposed normal-host declared-other trial
("go for it"). Assistant ran the same fprintd-verify right-index-finger reference;
owner instructed to touch an unenrolled finger, e.g. left index. Actual physical
identity remains operator-controlled. CLI listed right index, started, then
verify-no-match(done)/exit1 with no retry/error statuses before it. Outer120s
limit did not fire. Test020 records one normal-CLI NO_MATCH in the requested
other category, consistent with intended rejection but not independently proven
library rejection: host CLI maps some internal errors to NO_MATCH, no observer.
No re-enroll/deletion, template/image inspection, raw logs, key/firmware write,
acquisition, service-policy/PAM/login/sudo/lock changes or Git publication.
Initial host exposure/enroll/sameMATCH/otherCLI-NO_MATCH sequence complete, retaining
unknown-error trials. No reliability/accuracy claim. Return control; propose
bounded repeatability/error-classification work before authentication integration.


On2026-10-14 the owner explicitly declined further verification repetitions:
"no man dale, ya suficientes prubas, funciona". Accept the initial host trials
as sufficient for the owner's practical decision and stop proposing additional
biometric test rounds. Preserve the existing evidence limits without imposing
more trials. Next discuss/apply a concrete everyday integration; the assistant
asked which target first (screen unlock, sudo, or session login) and inspected
installed Omarchy integration read-only. No authentication config changed yet.
Installed Omarchy uses its Quickshell lock, not Hyprlock, with independent
omarchy-lock-password and optional omarchy-lock-fingerprint PAM contexts. The
stock all-in-one setup would also touch sudo/Polkit and re-enroll, so do not run
it for a single-target change. Existing enrollment should be reused.


The owner selected "Desbloquear la pantalla (recomendado)". The assistant
explained the exact fingerprint-specific PAM file and implemented that bounded
integration through normal one-shot Polkit. Created only
/etc/pam.d/omarchy-lock-fingerprint root:root0644, using installed Omarchy's
3-line recipe (versioned config/pam/omarchy-lock-fingerprint). Exclusive creation,
no existing leaf overwrite. Installed Omarchy4.0.4-1/Quickshell0.3.1-1 uses separate
password/fingerprint PAM contexts and refreshes availability at beginLock; no
restart/reboot needed. Verified exact contents/ownership/mode and byte-identical
password-lock/sudo/login/Polkit/SDDM configurations against ignored local hashes.
No lock or extra biometric trial launched, respecting the owner's preference.
Actual screen unlock via PAM remains unobserved, configuration is enabled.
See docs/lock-screen-integration.md for use and reversal. Before driver removal,
remove the matching separate lock PAM file; existing driver controller does not
own it. No extra packages, key/firmware write, template/image inspection, rawlogs,
or Git publication. Return control; future sudo/login/Polkit work needs scope.


On2026-10-14 the owner reported screen unlock worked with fingerprint and
password ("anduvo joya con huella y con password") and requested sudo/login.
Assistant inspected installed SDDM and found autologin configured. Owner said
startup always asks password but could not identify which screen. Correct
read-only lsblk tree ancestry confirms root beneath an encrypted volume; an
initial flat-column lsblk check was inadequate and superseded, no identifiers
published. No autologin/disk/initramfs/bootloader/TPM changes are authorized.
Assistant explained that sudo and graphical SDDM login would get fingerprint
first with original password rules, leaving startup disk decryption separate.
Normal Polkit elevation applied the bounded sudo/SDDM PAM changes: afterheader
stock Omarchy closed-lid skip, sufficient pam_fprintd max-tries=1 timeout=10,
markers. Original rest/mode retained; private root0700 /etc/thinkpad-fingerprint-auth
holds root0600 originalsudo/sddm, before/afterhash manifest and standalone restore.py
(versioned scripts/25-restore-pam-auth.py). Source recipe config/pam/fingerprint-auth-prefix.conf.
Exact target hashes/ownership/modes and unchanged lockpassword/lockfingerprint/
consolelogin/Polkit/autologin baselines passed. Restorehelper AST/defaultplan pass.
No live sudo/login auth, session restart, extra biometric rounds, packages,
key/firmware writes, template/image inspection or Git publication. Installed
SDDM Main.qml accepts Enter with blankpassword; actual login not observed.
Docs/sudo-login-integration.md describes use, limits and one-command reversal.
Before driver removal, restore sudo/SDDM and remove separate lock PAM; old driver
controller does not own these integrations/backups. Return control for ordinary
use; do not alter disk encryption or disable autologin without explicit scope.


On2026-10-14 the owner explicitly requested committing all accumulated work in
reasonable incremental commits reflecting its evolution, rather than a single
squash. This authorizes grouped commits and the git-commit workflow's reviewed
push to the existing feature/sensor-probe branch on their public GitHub repo.
Preserve biometric/runtime data and machine-specific backups outside Git.
Commit dates remain current; group the existing corrected implementations by
functional stage without recreating earlier failing versions or rewriting history.
No PR creation, merge, further hardware trials or authentication changes requested.
