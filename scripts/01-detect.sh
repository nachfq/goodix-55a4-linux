#!/usr/bin/env bash
# Lesson 1: USB enumeration and libfprint support are separate things.
# Run each displayed command yourself by pressing Enter. Ctrl+C stops here.
set -u

if [[ ${1:-} == --help ]]; then
    echo 'Usage: bash scripts/01-detect.sh'
    echo 'Interactive detection walkthrough using installed tools, without sudo.'
    echo 'fprintd-list may activate fprintd through D-Bus. No enrollment or provisioning.'
    exit 0
fi
if (( $# != 0 )) || [[ ! -t 0 ]]; then
    echo 'Run without arguments in an interactive terminal, or use --help.' >&2
    exit 2
fi

# Keep failures visible while allowing the next independent observation.
failures=0
step() {
    local explanation=$1 status
    shift
    printf '\n%s\n$' "$explanation"
    printf ' %q' "$@"
    printf '\n'
    read -r -p 'Enter to run; Ctrl+C to stop. ' || exit 130
    if "$@"; then
        status=0
    else
        status=$?
        failures=$((failures + 1))
    fi
    printf 'Exit status: %s\n' "$status"
}

echo 'Lesson 1: can USB see the reader, and can fprintd use it?'
echo 'No finger placement needed. Output stays in this terminal; no log is saved.'
echo 'The last query may start the installed fprintd service through D-Bus.'

step '1/4 — Record the installed fingerprint packages.' \
    pacman -Q libfprint-git fprintd

# A USB ID identifies the device; it does not establish driver support.
step '2/4 — Look for Goodix vendor 27c6, product 55a4 on USB.' \
    lsusb -d 27c6:55a4

step '3/4 — Inspect service configuration for a custom library override.' \
    systemctl show fprintd.service -p FragmentPath -p DropInPaths -p Environment

# Bound the CLI wait. This does not stop or reconfigure the daemon.
step '4/4 — Ask fprintd for readers and enrolled finger names for this user.' \
    timeout --kill-after=2s 20s fprintd-list "$(id -un)"

printf '\nWalkthrough complete. Commands with nonzero status: %s\n' "$failures"
echo 'USB device + "No devices available" means USB sees it but fprintd exposes no reader.'
echo 'Status 124 on the last command means a timeout, not a fingerprint rejection.'
echo 'Read any other error as reported; this walkthrough does not diagnose every cause.'
echo 'Compare the USB and fprintd outputs together before the next experiment.'
(( failures == 0 ))
