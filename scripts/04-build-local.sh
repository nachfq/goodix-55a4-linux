#!/usr/bin/env bash
# Lesson 4: inspect prerequisites, then build only the reviewed shared library.
set -Eeuo pipefail

mode=${1:---plan}
if (( $# > 1 )); then
    echo 'Usage: bash scripts/04-build-local.sh [--plan|--check-dependencies|--run]' >&2
    exit 2
fi
case "$mode" in
    --plan|--help|--check-dependencies|--run) ;;
    *) echo "Unknown mode: $mode" >&2; exit 2 ;;
esac

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
base="$repo_dir/work/libfprint"
source_dir="$repo_dir/work/libfprint-patched"
patch_file="$repo_dir/work/55a4-driver.patch"
build_dir="$repo_dir/work/libfprint-build"
expected_commit=d1ca62a801aa565e67d1a2a47aaa7a33232b7990
expected_hash=73720a4418ed7ceb640011f51d4f2bac206118bc480ab6f1784f6618b479ef15
# Read-only Git operations must not refresh the index or run fsmonitor hooks.
export GIT_OPTIONAL_LOCKS=0

git_read() {
    git -c core.fsmonitor=false -c core.fileMode=true "$@"
}

plan() {
    cat <<PLAN
Usage: bash scripts/04-build-local.sh [--plan|--check-dependencies|--run]
Default: show this plan only. --check-dependencies inspects tools, pkg-config
metadata, pinned local inputs, and the intended output path; it configures nothing.

Inputs (already downloaded; no acquisition or repair):
  Clean base: $base
  Patched worktree: $source_dir
  Base HEAD: $expected_commit
  Patch: $patch_file
  Patch and canonical assembled diff SHA-256: $expected_hash
Fresh ignored output: $build_dir (must not exist, even after a failed build).

Required tools: Git, sha256sum, cc, c++, Meson >=0.56.0, Ninja, Python3,
pkg-config, glib-mkenums, readelf (static inspection).
Required discovery metadata: glib-2.0, gio-unix-2.0, gobject-2.0 >=2.56;
gusb >=0.2; openssl; opencv4; doctest >=2,<3. Threads are checked by Meson.
CMake can assist discovery but is not an unconditional requirement.
Missing pkg-config metadata is a discovery failure, not proof of absent libraries.

--run requires your regular-user terminal. Each step waits for Enter:
  1. Inspect dependencies and verify exact source inputs and fresh ignored output.
  2. Create the output directory; configure Meson with Ninja and no fallbacks:
     -Ddrivers=goodixtls55x4 -Dintrospection=false -Ddoc=false
     -Dgtk-examples=false -Dinstalled-tests=false
     -Dudev_rules=disabled -Dudev_hwdb=disabled --wrap-mode=nofallback
  3. Read generated target metadata; require shared library fprint-2 and its output.
  4. Recheck inputs; Ninja builds only that shared-library output and its dependencies.
  5. Inspect ELF dynamic metadata with readelf, without loading the library.

Configuration executes build tooling, compiler/dependency probes, inline Python,
enum generation and driver registration. The reviewed library graph has no
intended sensor access. nofallback prevents fallback acquisition; it is not a
network sandbox. Tests and examples still exist in configuration but are not run
or selected for compilation. No install, test, default all, sync-udev-hwdb,
provisioning, USB query, source reset/deletion, or system configuration command.
Failures stop immediately; partial build output is preserved for local review.
Compilation establishes compilation only, not fprintd or biometric compatibility.
Review any local logs before sharing; this script uploads nothing.
PLAN
}

stop() { printf 'STOP: %s\n' "$*" >&2; exit 1; }
trap 'echo "Stopped; any build output is preserved." >&2; exit 130' INT
trap 'echo "Stopped; any build output is preserved." >&2; exit 143' TERM
trap 'status=$?; printf "Command failed with exit status %s; any build output is preserved.\n" "$status" >&2; exit "$status"' ERR

step() {
    printf '\n%s\n$' "$1"
    shift
    printf ' %q' "$@"
    printf '\n'
    read -r -p 'Enter to continue; Ctrl+C to stop. ' || { echo 'Stopped at prompt (EOF); output is preserved.' >&2; exit 130; }
    "$@"
}

check_dependencies() {
    local tool version package requirement missing=0
    for tool in git sha256sum cc c++ meson ninja python3 pkg-config glib-mkenums readelf; do
        if command -v "$tool" >/dev/null 2>&1; then
            printf 'Tool found: %s\n' "$tool"
        else
            printf 'Missing tool: %s\n' "$tool"
            missing=1
        fi
    done
    if command -v meson >/dev/null 2>&1; then
        version=$(meson --version) || return 1
        printf 'Meson version: %s (required >=0.56.0)\n' "$version"
        if command -v python3 >/dev/null 2>&1; then
            python3 -c 'import re, sys; v = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:[.+-].*)?", sys.argv[1]); sys.exit(0 if v and tuple(map(int, v.groups())) >= (0, 56, 0) else 1)' "$version" || missing=1
        fi
    fi
    if command -v pkg-config >/dev/null 2>&1; then
        for requirement in 'glib-2.0 >= 2.56' 'gio-unix-2.0 >= 2.56' \
                'gobject-2.0 >= 2.56' 'gusb >= 0.2' openssl opencv4 \
                'doctest >= 2.0' 'doctest < 3.0'; do
            package=${requirement%% *}
            if pkg-config --exists "$requirement"; then
                version=$(pkg-config --modversion "$package") || return 1
                printf 'Metadata found: %s (%s)\n' "$requirement" "$version"
            else
                printf 'Discovery failed: %s\n' "$requirement"
                missing=1
            fi
        done
    fi
    echo 'Threads and compiler/linker compatibility remain for Meson to check.'
    echo 'Missing pkg-config entries do not prove that every library file is absent.'
    (( missing == 0 ))
}

check_inputs() {
    local directory actual changes digest entry
    for directory in "$base" "$source_dir"; do
        [[ -e "$directory/.git" ]] || stop "Missing checkout: $directory"
        actual=$(git_read -C "$directory" rev-parse --show-toplevel)
        [[ "$actual" == "$directory" ]] || stop "Unexpected checkout location: $actual"
        actual=$(git_read -C "$directory" rev-parse HEAD)
        [[ "$actual" == "$expected_commit" ]] || stop "Unexpected HEAD in $directory"
        # Reject index flags that could conceal changed tracked files from diff.
        changes=$(git_read -C "$directory" ls-files -v)
        while IFS= read -r entry; do
            [[ ${entry:0:1} =~ [a-zS] ]] && stop "Hidden index flags in $directory; inspect them manually."
        done <<< "$changes"
        # Include ignored files: extra build descriptions or headers are not reviewed inputs.
        changes=$(git_read -C "$directory" ls-files --others)
        [[ -z "$changes" ]] || stop "Untracked or ignored files in $directory; inspect them manually."
    done
    changes=$(git_read -C "$base" status --porcelain --untracked-files=all)
    [[ -z "$changes" ]] || stop 'The clean base has local changes; no repair attempted.'
    [[ -f "$patch_file" ]] || stop "Missing patch: $patch_file"
    digest=$(sha256sum "$patch_file")
    [[ ${digest%% *} == "$expected_hash" ]] || stop 'Patch SHA-256 differs from the reviewed input.'
    # This canonical diff covers staged AND unstaged tracked changes against HEAD.
    # pipefail prevents a failed Git command from looking like a valid empty diff.
    digest=$(git_read -C "$source_dir" -c diff.algorithm=myers \
        -c diff.indentHeuristic=true -c diff.suppressBlankEmpty=false \
        diff --no-ext-diff --no-textconv --no-renames --no-color \
        --src-prefix=a/ --dst-prefix=b/ --unified=3 --inter-hunk-context=0 \
        --abbrev=7 HEAD | sha256sum)
    [[ ${digest%% *} == "$expected_hash" ]] || stop 'Patched source differs from the exact reviewed patch.'
    echo 'Pinned base, patch bytes, and assembled tracked changes match; no source modified.'
}

check_output() {
    [[ -d "$repo_dir/work" && ! -L "$repo_dir/work" ]] || stop 'work/ must be an existing real directory.'
    [[ ! -e "$build_dir" && ! -L "$build_dir" ]] || stop "Output already exists: $build_dir; no deletion attempted."
    git_read -C "$repo_dir" check-ignore --no-index -q "$build_dir/meson-info/intro-targets.json" \
        || stop 'The output path must be ignored by this repository.'
}

preflight() {
    local failed=0
    check_dependencies || failed=1
    # Still inspect local inputs when tools permit, so missing tools remain visible.
    if command -v git >/dev/null 2>&1 && command -v sha256sum >/dev/null 2>&1; then
        check_inputs
        check_output
    else
        failed=1
    fi
    (( failed == 0 )) || stop 'Prerequisites or discovery metadata are missing; discuss setup before building.'
}

confirm_target() {
    # Read generated JSON directly; do not execute project programs or introspection hooks.
    python3 - "$build_dir" <<'PY'
import json
import pathlib
import sys

build = pathlib.Path(sys.argv[1])
targets = json.loads((build / 'meson-info/intro-targets.json').read_text())
matches = [target for target in targets if target.get('name') == 'fprint-2']
expected = build / 'libfprint/libfprint-2.so.2.0.0'
if len(matches) != 1 or matches[0].get('type') != 'shared library':
    sys.exit('STOP: expected exactly one shared-library target fprint-2.')
if matches[0].get('filename') != [str(expected)]:
    sys.exit('STOP: unexpected fprint-2 output; review generated metadata.')
print('Confirmed target: fprint-2; output: ' + str(expected))
PY
}

case "$mode" in
    --plan|--help) plan; exit 0 ;;
    --check-dependencies) preflight; exit 0 ;;
esac
(( EUID != 0 )) || stop '--run refuses root; use your regular-user terminal.'
[[ -t 0 ]] || stop '--run requires an interactive terminal.'
plan
step 'Inspect prerequisites and pinned local inputs (read-only).' preflight
step 'Reserve a fresh ignored output directory.' mkdir -- "$build_dir"
step 'Configure only; this executes build tooling, not the driver.' \
    meson setup "$build_dir" "$source_dir" --backend=ninja --wrap-mode=nofallback \
    -Ddrivers=goodixtls55x4 -Dintrospection=false -Ddoc=false \
    -Dgtk-examples=false -Dinstalled-tests=false -Dudev_rules=disabled -Dudev_hwdb=disabled
step 'Read generated metadata to confirm the shared-library target and output.' confirm_target
step 'Recheck source inputs before compilation (read-only).' check_inputs
step 'Compile only the confirmed shared library and its dependencies.' \
    ninja -C "$build_dir" libfprint/libfprint-2.so.2.0.0
step 'Inspect ELF SONAME and NEEDED entries without loading the library.' \
    readelf -d "$build_dir/libfprint/libfprint-2.so.2.0.0"
echo 'Local compilation completed; no installation or hardware test was performed.'
