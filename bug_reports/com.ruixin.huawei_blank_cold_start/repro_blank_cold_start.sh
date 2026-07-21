#!/usr/bin/env bash
# Repro: com.ruixin.huawei intermittent blank white cold start
# Usage: bash repro_blank_cold_start.sh [N_TRIALS] [WAIT_SEC] [DEVICE]
set -euo pipefail
export PATH="${HOME}/.local/bin:${PATH}"
N="${1:-10}"
WAIT="${2:-10}"
D="${3:-${PBT_KEA_DEVICE:-$(hdc list targets 2>/dev/null | awk 'NF && $1 !~ /[Ee]mpty/ {print $1; exit}')}}"
PKG=com.ruixin.huawei
ABILITY=EntryAbility
OUT="${4:-./repro_out_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$OUT"
echo "device=$D package=$PKG ability=$ABILITY trials=$N wait=${WAIT}s out=$OUT"
blank=0
for i in $(seq 0 $((N-1))); do
  hdc -t "$D" shell power-shell wakeup >/dev/null 2>&1 || true
  hdc -t "$D" shell "uitest uiInput swipe 640 2500 640 400 250" >/dev/null 2>&1 || true
  hdc -t "$D" shell "aa force-stop $PKG" >/dev/null 2>&1 || true
  sleep 0.8
  hdc -t "$D" shell "aa start -a $ABILITY -b $PKG" >/dev/null 2>&1 || true
  sleep "$WAIT"
  shot="$OUT/trial_$(printf '%02d' $i).png"
  hdc -t "$D" shell "uitest screenCap -p /data/local/tmp/rx_repro.png" >/dev/null 2>&1
  hdc -t "$D" file recv /data/local/tmp/rx_repro.png "$shot" >/dev/null 2>&1
  verdict=$(python3 - "$shot" <<'PY'
import sys
from PIL import Image
import numpy as np
a=np.asarray(Image.open(sys.argv[1]).convert("RGB").resize((64,128)),dtype=np.float32)
w=float(np.mean(a>248))
print("BLANK" if w>=0.92 else "ok", f"{w:.3f}")
PY
)
  echo "trial $(printf '%02d' $i): $verdict"
  echo "$verdict" | grep -q BLANK && blank=$((blank+1)) || true
done
echo "RESULT blank=$blank / $N"
echo "Screenshots in $OUT"
