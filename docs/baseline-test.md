# Test 001: installed-stack device detection

Date: 2026-10-07. Hardware: ThinkPad E14 Gen 2, Goodix USB `27c6:55a4`.

## Purpose and scope

Check whether USB enumerates the sensor and whether the currently installed
fprintd stack exposes it. This is a detection baseline, not a community-driver
capture, enrollment, or matching test.

No downloads, package installations, community scripts, key provisioning,
enrollment, PAM edits, or service configuration changes were performed.
`fprintd-list` can activate the installed service through D-Bus; the service
was observed running after the query. No manual restart was performed.

## Commands and results

Commands were run as the regular user, without sudo:

```sh
pacman -Q libfprint-git fprintd
lsusb -d 27c6:55a4
systemctl cat fprintd.service
systemctl show fprintd.service -p FragmentPath -p DropInPaths -p Environment -p ExecStart
timeout 20s fprintd-list "$USER"
```

| Check | Observed result |
| --- | --- |
| libfprint package | `libfprint-git 1:1.94.100.r10.g6f9479c-1` |
| fprintd package | `fprintd 1.94.5-2` |
| USB enumeration | `27c6:55a4`, Goodix FingerPrint Device |
| fprintd query | `No devices available` |
| Query exit status | `1`; not timeout status `124` |
| Service unit | `/usr/lib/systemd/system/fprintd.service` |
| Executable | `/usr/lib/fprintd` |
| Drop-in paths | Empty |
| Service environment property | Empty |
| Service state after query | `active`, `running` |

The installed unit declares `StateDirectory=fprint` and
`StateDirectoryMode=0700`, with a comment identifying `/var/lib/fprint`.
This corroborates the configured storage location and requested directory mode.
Actual directory permissions, template contents, and encryption were not inspected.

An attempt to inspect the running process's library mappings was denied by
permissions. No elevated access was requested. The service configuration contains
no library override, but the actual loaded library path was not directly verified.

## Interpretation

USB sees the sensor, but the installed fprintd stack does not expose a usable
reader. This reproduces the previously reported failure. It does not establish
its full cause or test the community patch. No finger placement is needed for
this query, and it yields no biometric acceptance or rejection result.

## Build preparation observations

Read-only tool checks found `ninja`, `gcc`, and `pkg-config` on PATH, but no
`meson` executable. `pkg-config` could not find `opencv4`. This is a partial
inventory, not a complete dependency assessment; an absent pkg-config entry does
not by itself prove every corresponding library file is absent.

The next prerequisite for a community-driver test is reviewing the pinned source
dependencies, followed by a separately scoped build. See the [staged plan](plan.md).
