#!/usr/bin/env bash
# Minimal cold-start repro for 携程 CTImage Stack overflow jscrash.
# Usage: bash repro.sh [serial]
set -u
SERIAL="${1:-${SERIAL:-5SM0125606000291}}"
PKG="com.ctrip.harmonynext"
ABILITY="CTEntryAbility"
MODULE="Phone"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/repro_last"
mkdir -p "$OUT"

if ! command -v hdc >/dev/null 2>&1; then
  echo "FAIL: hdc not in PATH"
  exit 2
fi

echo "[repro] serial=$SERIAL pkg=$PKG"
hdc -t "$SERIAL" list targets 2>/dev/null | head -5

before="$OUT/faults_before.txt"
after="$OUT/faults_after.txt"
hdc -t "$SERIAL" shell "ls /data/log/faultlog/faultlogger 2>/dev/null" >"$before" 2>/dev/null || true

echo "[repro] force-stop"
hdc -t "$SERIAL" shell aa force-stop "$PKG" || true
sleep 2

echo "[repro] cold start $ABILITY ($MODULE)"
hdc -t "$SERIAL" shell "aa start -a $ABILITY -b $PKG -m $MODULE"
echo "[repro] waiting 15s for home image bind / possible jscrash..."
sleep 15

hdc -t "$SERIAL" shell "ls /data/log/faultlog/faultlogger 2>/dev/null" >"$after" 2>/dev/null || true

# new jscrash files for this pkg
new_list="$OUT/new_jscrash.txt"
: >"$new_list"
while read -r f; do
  [[ -z "$f" ]] && continue
  grep -qxF "$f" "$before" 2>/dev/null && continue
  case "$f" in
    jscrash-com.ctrip.harmonynext-*.log) echo "$f" >>"$new_list" ;;
  esac
done <"$after"

echo "[repro] new ctrip jscrash files:"
if [[ ! -s "$new_list" ]]; then
  echo "  (none)"
  echo "RESULT: NO_NEW_JSCRASH (may still be intermittent — retry 3–5×)"
  # still show newest ctrip log if any
  newest=$(grep 'jscrash-com.ctrip.harmonynext' "$after" | tail -1 || true)
  if [[ -n "${newest:-}" ]]; then
    echo "[repro] newest existing: $newest"
  fi
  exit 1
fi

cat "$new_list"
newest=$(tail -1 "$new_list")
local_log="$OUT/$newest"
echo "[repro] pulling $newest"
hdc -t "$SERIAL" file recv "/data/log/faultlog/faultlogger/$newest" "$local_log" || true

echo "[repro] excerpt:"
if [[ -f "$local_log" ]]; then
  # show key lines
  grep -E 'Timestamp|Version|Process life|Reason|Error name|Error message|CTImage|transUrl|onImageOption|originImageAlt|configCommon|configBefore' "$local_log" | head -40
  if grep -q 'Stack overflow' "$local_log" && grep -q 'ctimage\|CTImage\|transUrl\|onImageOptionChange' "$local_log"; then
    echo "RESULT: FAIL — CTImage Stack overflow jscrash reproduced"
    exit 0
  fi
  if grep -q 'Stack overflow' "$local_log"; then
    echo "RESULT: FAIL — Stack overflow jscrash (check stack manually)"
    exit 0
  fi
fi
echo "RESULT: NEW_JSCRASH but signature unclear — inspect $local_log"
exit 0
