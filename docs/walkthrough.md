# Run the experiments yourself

Read one script, run it, and discuss its output before moving to the next one.
Each hardware walkthrough displays its operations and waits for Enter before the next step.
Ctrl+C stops the walkthrough. Use your regular terminal without sudo.

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
dependency setup together before using it. The local Python currently lacks
PyUSB; libusb was found. No dependency has been installed for this delivery.
The script does not install packages or download anything.

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
modules are imported. Query behavior on this laptop remains untested; no captures,
key writes, firmware updates, TLS handshake, or enrollment are implemented here.

Offline checks use synthetic packets and a fake USB transport:

```sh
python3 -m unittest discover -s tests -v
```

These tests verify protocol handling and command restrictions, not real sensor support.

## How we work from here

The owner runs the experiments. The assistant prepares small scripts, explains
their commands, and checks syntax; it waits for the owner's output before drawing
new hardware conclusions. Hardware execution is delegated to the assistant only
when explicitly requested. Scripts save no logs automatically and upload nothing.
Share only the relevant output after reviewing it.

The direct firmware/key-state query is prepared for review and has not been run
against the hardware by the assistant. Review its plan and dependencies first.
