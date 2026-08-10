#!/bin/bash
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QUEUE="$ROOT/modeA_runs/queue.txt"
LOG="$ROOT/modeA_runs/campaign.log"
DONE="$ROOT/modeA_runs/done_ok.txt"
MINS="${1:-5}"
SERIAL=5SM0125606000291
touch "$DONE"

echo "[$(date -Iseconds)] CAMPAIGN start mins=$MINS nologin_v3" | tee -a "$LOG"
while read -r PKG; do
  [[ -z "$PKG" || "$PKG" =~ ^# ]] && continue
  if rg -qx "$PKG" "$DONE" 2>/dev/null; then
    echo "[$(date -Iseconds)] SKIP ok-done $PKG" | tee -a "$LOG"
    continue
  fi
  bash "$ROOT/modeA_runs/run_one.sh" "$PKG" "$MINS" || true
  RC=$?
  OUTDIR=$(ls -dt "$ROOT"/modeA_runs/${PKG}_* 2>/dev/null | head -1 || true)
  STEPS=0
  if [ -n "$OUTDIR" ]; then
    for f in "$OUTDIR"/res_*/output_*/steps.log; do
      [ -f "$f" ] && STEPS=$(wc -l < "$f" | tr -d ' ')
    done
  fi
  if [ "${STEPS:-0}" -gt 5 ]; then
    echo "$PKG" >> "$DONE"
    echo "[$(date -Iseconds)] MARK_OK $PKG steps=$STEPS rc=$RC" | tee -a "$LOG"
  else
    echo "[$(date -Iseconds)] RETRYABLE $PKG steps=$STEPS rc=$RC" | tee -a "$LOG"
  fi
  hdc -t "$SERIAL" shell "uitest uiInput keyEvent Home" >/dev/null 2>&1 || true
  sleep 4
done < "$QUEUE"
echo "[$(date -Iseconds)] CAMPAIGN complete" | tee -a "$LOG"
echo "==== SUMMARY ====" | tee -a "$LOG"
rg 'MARK_OK|RETRYABLE|SUMMARY ' "$LOG" | tail -60 | tee -a "$LOG"
