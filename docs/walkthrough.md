# Run the experiments yourself

Read one script, run it, and discuss its output before moving to the next one.
Each script displays its commands and waits for Enter before the next step.
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

## How we work from here

The owner runs the experiments. The assistant prepares small scripts, explains
their commands, and checks syntax; it waits for the owner's output before drawing
new hardware conclusions. Hardware execution is delegated to the assistant only
when explicitly requested. Scripts save no logs automatically and upload nothing.
Share only the relevant output after reviewing it.

A direct firmware/key-state query is a future script. Its USB initialization and
command list will be reviewed together before its first run. These two walkthroughs
do not execute any community driver code or query its key state.
