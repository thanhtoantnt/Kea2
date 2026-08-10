#!/bin/bash
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QUEUE="$ROOT/modeA_runs/queue_improve.txt"
LOG="$ROOT/modeA_runs/improve.log"
DONE="$ROOT/modeA_runs/done_ok.txt"
MINS="${1:-5}"
SERIAL=5SM0125606000291
touch "$DONE" "$LOG"
echo "[$(date -Iseconds)] IMPROVE_CAMPAIGN start mins=$MINS" | tee -a "$LOG"
while read -r PKG; do
  [[ -z "$PKG" || "$PKG" =~ ^# ]] && continue
  if rg -qx "$PKG" "$DONE" 2>/dev/null && [[ "$PKG" != com.xs.fm.next && "$PKG" != com.ss.hm.ugc.aweme ]]; then
    echo "[$(date -Iseconds)] SKIP $PKG" | tee -a "$LOG"
    continue
  fi
  bash "$ROOT/modeA_runs/run_one.sh" "$PKG" "$MINS" || true
  OUTDIR=$(ls -dt "$ROOT"/modeA_runs/${PKG}_* 2>/dev/null | head -1 || true)
  STEPS=0; CRASH=none
  if [ -n "$OUTDIR" ]; then
    for f in "$OUTDIR"/res_*/output_*/steps.log; do
      [ -f "$f" ] && STEPS=$(wc -l < "$f" | tr -d ' ')
    done
    if [ -f "$OUTDIR"/res_*/output_*/crash-dump.log ]; then
      CRASH=HAS_DUMP
      echo "[$(date -Iseconds)] CRASH_DUMP $PKG" | tee -a "$LOG"
      head -40 "$OUTDIR"/res_*/output_*/crash-dump.log | tee -a "$LOG" || true
    fi
    rg -n 'HarmonyLogWatcher|Harmony.*CRASH|Harmony.*ANR|No crash was found|Device not found|HarmonyOS mode' "$OUTDIR/console.log" 2>/dev/null | tail -20 | tee -a "$LOG" || true
  fi
  if [ "${STEPS:-0}" -gt 5 ]; then
    echo "$PKG" >> "$DONE"
    sort -u "$DONE" -o "$DONE"
    echo "[$(date -Iseconds)] MARK_OK $PKG steps=$STEPS crash=$CRASH" | tee -a "$LOG"
  else
    echo "[$(date -Iseconds)] WEAK $PKG steps=$STEPS crash=$CRASH" | tee -a "$LOG"
  fi
  hdc -t "$SERIAL" shell "uitest uiInput keyEvent Home" >/dev/null 2>&1 || true
  sleep 3
done < "$QUEUE"
echo "[$(date -Iseconds)] IMPROVE_CAMPAIGN complete" | tee -a "$LOG"
