#!/bin/sh
# Host test of libhmk's matrix.c with detachable.patch (no hardware or ARM toolchain needed).
#   LIBHMK=/path/to/libhmk ./run.sh
# The patch is applied to a scratch copy unless the checkout already has it.
set -e
here=$(cd "$(dirname "$0")" && pwd)
patch="$here/../detachable.patch"
: "${LIBHMK:?set LIBHMK to a libhmk checkout}"
out=$(mktemp -d)
trap 'rm -rf "$out"' EXIT
mkdir -p "$out/src"
cp -r "$LIBHMK/include" "$out/"
cp "$LIBHMK/src/matrix.c" "$out/src/"
if git -C "$LIBHMK" apply --check "$patch" 2>/dev/null; then
    (cd "$out" && git apply --include='include/*' --include='src/matrix.c' "$patch")
fi
cc -std=gnu11 -Wall -Wextra -Wno-unused-function -O1 -I"$here" -I"$out/include" \
    "$here/test_detachable.c" "$out/src/matrix.c" -o "$out/test_detachable"
"$out/test_detachable"
