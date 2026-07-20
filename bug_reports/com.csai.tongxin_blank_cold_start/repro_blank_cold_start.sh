#!/usr/bin/env bash
# Repro: com.csai.tongxin intermittent blank white cold start
# Usage: bash repro_blank_cold_start.sh [N_TRIALS] [WAIT_SEC] [DEVICE]
set -euo pipefail
N="${1:-10}"
WAIT="${2:-10}"
D="${3:-${PBT_KEA_DEVICE:-$(hdc list targets | head -1 | awk '{print $1}')}}"
PKG=com.csai.tongxin
OUT="${4:-./repro_out_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$OUT"
echo "device=$D package=$PKG trials=$N wait=${WAIT}s out=$OUT"

blank=0
for i in $(seq 0 $((N-1))); do
  hdc -t "$D" shell power-shell wakeup >/dev/null 2>&1 || true
  hdc -t "$D" shell "uitest uiInput swipe 640 2400 640 400 300" >/dev/null 2>&1 || true
  hdc -t "$D" shell "aa force-stop $PKG" >/dev/null 2>&1 || true
  sleep 1
  hdc -t "$D" shell "aa start -a EntryAbility -b $PKG" >/dev/null 2>&1 || true
  sleep "$WAIT"
  hdc -t "$D" shell "uitest screenCap -p /data/local/tmp/tx_repro.png" >/dev/null 2>&1
  hdc -t "$D" file recv /data/local/tmp/tx_repro.png "$OUT/trial_$(printf '%02d' $i).png" >/dev/null 2>&1
  # classify blank: very high mean pixel (~white)
  verdict=$(python3 - "$OUT/trial_$(printf '%02d' $i).png" <<'PY'
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
echo "Screenshots in $OUT — open BLANK trials; compare to ok (should show home/splash UI)."
