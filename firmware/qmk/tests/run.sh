#!/bin/sh
# Host test of the hall-effect matrix logic (no hardware or ARM toolchain needed).
set -e
here=$(cd "$(dirname "$0")" && pwd)
kb="$here/../keyboards/vgacorne"
out=$(mktemp -d)
cc -std=gnu11 -Wall -Wextra -O1 -I"$here/stubs" -I"$kb" \
    "$here/test_he_matrix.c" "$kb/he_matrix.c" -o "$out/test_he_matrix" -lm
"$out/test_he_matrix"
rm -rf "$out"
