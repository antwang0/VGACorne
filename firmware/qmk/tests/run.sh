#!/bin/sh
# Host test of the hall-effect matrix logic (no hardware or ARM toolchain needed).
set -e
here=$(cd "$(dirname "$0")" && pwd)
kb="$here/../keyboards/vgacorne"
out=$(mktemp -d)
cc -std=gnu11 -Wall -Wextra -O1 -I"$here/stubs" -I"$kb" \
    "$here/test_he_matrix.c" "$kb/he_matrix.c" -o "$out/test_he_matrix" -lm
"$out/test_he_matrix"
# The other sensor polarity (DRV5055A3 <-> MT9102ET in circuits.py): readings mirrored, pulls swapped.
echo "--- with the sensor polarity flipped"
mkdir "$out/kb" && cp "$kb"/*.c "$kb"/*.h "$out/kb/"  # a quoted include looks beside the .c first
sed -i -e 's/^#define HE_INVERT_ADC 1/#define HE_INVERT_ADC X/' -e 's/^#define HE_INVERT_ADC 0/#define HE_INVERT_ADC 1/' \
    -e 's/^#define HE_INVERT_ADC X/#define HE_INVERT_ADC 0/' "$out/kb/he_wiring.h"
cc -std=gnu11 -Wall -Wextra -O1 -I"$here/stubs" -I"$out/kb" \
    "$here/test_he_matrix.c" "$out/kb/he_matrix.c" -o "$out/test_he_matrix" -lm
"$out/test_he_matrix" > "$out/log" || { cat "$out/log"; exit 1; }
tail -1 "$out/log"
rm -rf "$out"
