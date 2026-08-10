#!/bin/bash
set -euo pipefail
PKG="${1:?pkg}"
MINS="${2:-5}"
SERIAL=5SM0125606000291
STAMP=$(date +%Y%m%d_%H%M%S)
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/modeA_runs/${PKG}_${STAMP}"
mkdir -p "$OUT"
echo "[$(date -Iseconds)] START $PKG mins=$MINS out=$OUT" | tee -a "$ROOT/modeA_runs/campaign.log"

wait_dev() {
  local i
  for i in $(seq 1 60); do
    if hdc list targets 2>/dev/null | rg -q "$SERIAL"; then
      if hdc -t "$SERIAL" shell "echo ping" 2>/dev/null | rg -q ping; then
        return 0
      fi
    fi
    echo "[$(date -Iseconds)] wait device try=$i" | tee -a "$ROOT/modeA_runs/campaign.log"
    sleep 3
  done
  return 1
}

wait_dev || { echo "[$(date -Iseconds)] END $PKG rc=99 device_lost" | tee -a "$ROOT/modeA_runs/campaign.log"; exit 99; }

if ! hdc -t "$SERIAL" shell bm dump -a 2>/dev/null | tr -d '\t\r' | sed 's/^ *//' | rg -qx "$PKG"; then
  echo "[$(date -Iseconds)] END $PKG rc=98 not_installed" | tee -a "$ROOT/modeA_runs/campaign.log"
  echo "not_installed" > "$OUT/hits.txt"
  exit 98
fi

hdc -t "$SERIAL" shell "power-shell setmode 602" >/dev/null 2>&1 || true
hdc -t "$SERIAL" shell "uitest uiInput keyEvent Home" >/dev/null 2>&1 || true
sleep 1
hdc -t "$SERIAL" shell "aa force-stop $PKG" >/dev/null 2>&1 || true
sleep 1
# resolve main ability
AB=$(hdc -t "$SERIAL" shell bm dump -n "$PKG" 2>/dev/null | python3 -c "
import sys,re
t=sys.stdin.read()
m=re.search(r'\"mainAbility\"\s*:\s*\"([^\"]+)\"', t)
if m:
    n=m.group(1); print(n.split('.')[-1]); raise SystemExit
for pat in [r'EntryAbility', r'MainAbility', r'IndexAbility']:
    m=re.search(r'\"name\"\s*:\s*\"([^\"]*%s[^\"]*)\"'%pat, t)
    if m:
        print(m.group(1).split('.')[-1]); raise SystemExit
print('EntryAbility')
" 2>/dev/null || echo EntryAbility)
echo "[$(date -Iseconds)] ability=$AB" | tee -a "$ROOT/modeA_runs/campaign.log"
hdc -t "$SERIAL" shell "aa start -a $AB -b $PKG" >/dev/null 2>&1 || \
  hdc -t "$SERIAL" shell "aa start -a EntryAbility -b $PKG" >/dev/null 2>&1 || true
sleep 3
python3 "$ROOT/modeA_runs/pre_consent.py" "$SERIAL" "$PKG" >"$OUT/pre_consent.log" 2>"$OUT/pre_consent.err" || true
cat "$OUT/pre_consent.log" 2>/dev/null | tee -a "$ROOT/modeA_runs/campaign.log" || true

cd "$ROOT"
set +e
.venv/bin/kea2 run \
  --platform harmony \
  -s "$SERIAL" \
  -p "$PKG" \
  -o "$OUT" \
  --running-minutes "$MINS" \
  --throttle 800 \
  --take-screenshots \
  --log-stamp "$STAMP" \
  > "$OUT/console.log" 2>&1
RC=$?
set -e

echo "[$(date -Iseconds)] END $PKG rc=$RC" | tee -a "$ROOT/modeA_runs/campaign.log"
SUM=$(python3 "$ROOT/modeA_runs/summarize_hits.py" "$OUT" 2>&1 || echo summarize_fail)
echo "[$(date -Iseconds)] SUMMARY $PKG $SUM" | tee -a "$ROOT/modeA_runs/campaign.log"
rg -n "No crash was found|crash was found|Triggered Crash|ANR|Device not found" "$OUT/console.log" 2>/dev/null | tail -8 | tee -a "$ROOT/modeA_runs/campaign.log" || true
exit $RC
