# Run the experiments yourself

Read one script, run it, and discuss its output before moving to the next one.
Each hardware walkthrough displays its operations and waits for Enter before the next step.
Ctrl+C stops the walkthrough. Start in your regular terminal. The completed
probe required one-shot sudo for USB access; local compilation must run without sudo.

## 1. Detection: two different layers

Open [scripts/01-detect.sh](../scripts/01-detect.sh) in your editor, then run
from the repository root:

```sh
bash scripts/01-detect.sh
```

The four steps inspect installed packages, USB enumeration, fprintd's service
configuration, and its list of usable readers. The final query may activate
fprintd through D-Bus and lists enrolled finger names if a supported reader
already exists. It does not enroll, verify, provision keys, or change configuration.
There is no need to touch the sensor.

Look at the `step()` function first: it prints a command, waits for you, runs it,
and reports its exit status. Commands are passed as arguments, without `eval`.
The calls below it are the actual experiment.

The previous baseline was a USB listing containing `27c6:55a4`, followed by
`No devices available` from fprintd. Your results are a new observation, not
assumed to match. A failed command remains visible and the walkthrough continues;
the script exits 1 if any step failed, including the expected unsupported-device
result. A timeout or other error is not a biometric rejection.

## 2. Source inputs: what are we reviewing?

After discussing the first result, open
[scripts/02-check-sources.sh](../scripts/02-check-sources.sh), then run:

```sh
bash scripts/02-check-sources.sh
```

This checks the two local commit IDs and clean source trees, then the patch's
SHA-256 and whether Git can apply it to the base. `git apply --check` does not
modify source files. The script stops on a mismatch and makes no repairs.

It uses the previously downloaded sources under `work/` and
`work/55a4-driver.patch`, copied from the previously reviewed Hydrogell checkout.
These files are ignored. A fresh clone of our public repository will not contain
them; the script reports missing files rather than downloading anything.
It checks the clean base, not the intentionally modified `libfprint-patched` tree.

## 3. Firmware and expected key state: inspect before running

Open [scripts/03-probe-sensor.py](../scripts/03-probe-sensor.py), then start with:

```sh
python3 scripts/03-probe-sensor.py --plan
python3 scripts/03-probe-sensor.py --check-dependencies
```

Both modes work without opening a USB device. Running the script without arguments
also shows the plan. Start reading at `QUERIES`: it contains only NOP (`0x00`),
firmware version (`0xa8`), and key-state query (`0xe4`). `encode_frame()` shows how
the command is wrapped and padded; `run_probe()` puts the steps in order.

For hardware execution, the explicit mode is `--run`. Review the plan and local
dependency setup together before using it. The initial check lacked PyUSB; the
owner subsequently prepared ignored `work/probe-venv` with PyUSB `1.3.1` and ran
the probe. A fresh clone does not contain that environment. The script itself
does not install packages or download anything.

`--run` reads the current USB configuration and claims its existing data/vendor
interface at alternate setting zero. It refuses an attached kernel driver and
stops if the claim fails. It does not detach drivers, change configuration, reset
the sensor, or stop fprintd. The interface and USB handle are released on exit.
Initialization drains at most four pending input transfers and sends NOP;
each query then expects an acknowledgement and a matching reply.
Writes have a 1-second timeout. Each receive uses at most eight USB reads with
a 1-second timeout each (100 ms for the NOP response). Packet lengths are bounded.

The firmware identifier is printed. Returned key-state data is compared privately
with the public expected hash; only `MATCH` or `MISMATCH` is printed. `MISMATCH`
means the expected state was not observed; it does not establish an absent key.
An unsuccessful or malformed response is an error. There is no automatic repair.

| Exit status | Meaning |
| --- | --- |
| `0` | Plan completed, dependencies found, or hardware queries completed with expected key state, depending on selected mode |
| `1` | Hardware/protocol error; inconclusive probe |
| `2` | Dependencies missing or invalid CLI arguments |
| `3` | Hardware queries completed; expected key state did not match |
| `130` | Operator stopped the hardware walkthrough |

The protocol framing and query definitions are adapted from the reviewed MIT
source. Attribution is in the script and the original notice is preserved in
[LICENSES/goodix-fp-dump-MIT.txt](../LICENSES/goodix-fp-dump-MIT.txt). No community
modules are imported. The owner reported successful queries with firmware
`GF3268_RTSEC_APP_10062` and expected key state `MISMATCH`; see the
[recorded trial](probe-test.md). No captures, key writes, firmware updates, TLS
handshake, or enrollment are implemented here.

Offline checks use synthetic packets and a fake USB transport:

```sh
python3 -m unittest discover -s tests -v
```

These tests verify protocol handling and command restrictions, not real sensor support.

## 4. Local build: inspect prerequisites first

Read [scripts/04-build-local.sh](../scripts/04-build-local.sh), then start with:

```sh
bash scripts/04-build-local.sh --plan
bash scripts/04-build-local.sh --check-dependencies
```

The default mode only explains the plan. The dependency check inspects installed
tools, library-discovery metadata, pinned source inputs, and the fresh output path;
it does not configure, compile, download, install, or access USB. Share its output
before starting the build. A missing
dependency is a prerequisite to resolve together, not permission to install it.

Start reading at `plan()` for the operations, then `preflight()` and
`check_inputs()` for the checks. The final calls to `step()` are the experiment;
each prints its arguments and waits for Enter, without `eval`.

Meson prepares compilation instructions; Ninja compiles and links the selected
shared library. OpenCV supplies image-processing support for SIGFM matching.
Doctest remains a configuration dependency in this source even though this
walkthrough does not compile or execute its tests. CMake is a possible discovery
backend, not an unconditional project requirement. A missing pkg-config entry
does not prove that every corresponding library file is absent.

After discussing prerequisites, the owner can use the explicit interactive mode:

```sh
bash scripts/04-build-local.sh --run
```

Run without sudo. It validates the local source revision and patch, configures a
fresh ignored `work/libfprint-build` directory, checks the generated library target,
and builds only that target. It stops on failure and preserves existing directories. It
does not load the resulting library into fprintd, run examples or upstream tests,
provision a key, or change system configuration. The installed reader support
therefore does not change just because the build finishes.

If `work/libfprint-build` already exists, including after a failed trial, the script
stops. It never removes or reuses that directory automatically. Review the output
together before deciding where to preserve it and how to retry. Static `readelf`
inspection describes the library's SONAME and dependencies without loading it.

Meson writes generated build files and logs under ignored `work/`. Review any
output before sharing; a successful compilation establishes that a library was
built, not that it captures or recognizes fingerprints.

## How we work from here

The owner runs the experiments. The assistant prepares small scripts, explains
their commands, and checks syntax; it waits for the owner's output before drawing
new hardware conclusions. Hardware execution is delegated to the assistant only
when explicitly requested. Scripts upload nothing. The query probe saves no logs;
Meson generates local build logs under ignored `work/`. Share only relevant output
after reviewing it.

The direct query has been run by the owner and its output discussed. The next
experiment prepares a local build; it does not provision the mismatched key or
activate the community driver.
