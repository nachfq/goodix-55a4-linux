#!/usr/bin/env bash
# Lesson 2: verify the exact source inputs without building or running them.
set -euo pipefail

if [[ ${1:-} == --help ]]; then
    echo 'Usage: bash scripts/02-check-sources.sh'
    echo 'Interactively check local commits, clean trees, patch hash, and patch applicability.'
    echo 'Uses Git and sha256sum. No downloads, source execution, or USB access.'
    exit 0
fi
if (( $# != 0 )) || [[ ! -t 0 ]]; then
    echo 'Run without arguments in an interactive terminal, or use --help.' >&2
    exit 2
fi

# Resolve paths relative to this script, so the terminal working directory can vary.
repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd -- "$repo_dir"

check_source() {
    local directory=$1 expected=$2 actual changes
    printf '\nDirectory: %s\nExpected commit: %s\n' "$directory" "$expected"
    printf '$ git -C %q rev-parse HEAD\n' "$directory"
    printf '$ git --no-optional-locks -C %q status --porcelain\n' "$directory"
    read -r -p 'Enter to check; Ctrl+C to stop. ' || exit 130
    if [[ ! -d "$directory/.git" ]]; then
        echo "Missing source checkout: $directory. Nothing will be downloaded." >&2
        exit 1
    fi
    actual=$(git -C "$directory" rev-parse HEAD)
    printf 'Actual commit:   %s\n' "$actual"
    [[ "$actual" == "$expected" ]] || { echo 'STOP: unexpected commit.' >&2; exit 1; }
    changes=$(git --no-optional-locks -C "$directory" status --porcelain)
    if [[ -n "$changes" ]]; then
        printf 'STOP: source tree has local changes:\n%s\n' "$changes" >&2
        exit 1
    fi
    echo 'Commit matches; working tree is clean.'
}

check_source work/libfprint d1ca62a801aa565e67d1a2a47aaa7a33232b7990
check_source work/goodix-fp-dump cc43bb3b3154a0bccc0412ae024013c7e1923139

# This patch was copied locally from the already reviewed Hydrogell checkout.
patch_file=work/55a4-driver.patch
expected_hash=73720a4418ed7ceb640011f51d4f2bac206118bc480ab6f1784f6618b479ef15
printf '\n$ sha256sum %s\nExpected SHA-256: %s\n' "$patch_file" "$expected_hash"
read -r -p 'Enter to check the patch bytes; Ctrl+C to stop. ' || exit 130
digest=$(sha256sum "$patch_file")
echo "$digest"
[[ ${digest%% *} == "$expected_hash" ]] || { echo 'STOP: unexpected patch hash.' >&2; exit 1; }

# --check only checks applicability; it does not apply the patch or run its code.
printf '\n$ git -C work/libfprint apply --check ../../%s\n' "$patch_file"
read -r -p 'Enter to check applicability; Ctrl+C to stop. ' || exit 130
git -C work/libfprint apply --check "$repo_dir/$patch_file"
echo 'Patch applies to the pinned base. The source tree was not modified.'
echo 'Matching hashes and applicability establish the inputs, not driver correctness.'
