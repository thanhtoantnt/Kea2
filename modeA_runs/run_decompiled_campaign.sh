#!/usr/bin/env bash
# Mode A campaign using decompile/mine-seeded property packs.
# Offline prep: ${HARMONY_DECOMPILE_HOME}/offline_check.py
# Phone only needed here.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export HARMONY_DECOMPILE_HOME="${HARMONY_DECOMPILE_HOME:-${KEA2_DECOMPILE_HOME:-$ROOT/../harmony-decompile}}"
export KEA2_DECOMPILE_HOME="$HARMONY_DECOMPILE_HOME"
cd "$ROOT"
SERIAL="${SERIAL:-5SM0125606000291}"
MINS="${MINS:-4}"
THROTTLE="${THROTTLE:-400}"
MAXSTEP="${MAXSTEP:-50}"
LOG="$ROOT/modeA_runs/decompiled_campaign.log"
DONE="$ROOT/modeA_runs/decompiled_done.txt"
FAIL="$ROOT/modeA_runs/decompiled_fail.txt"
QUEUE="${QUEUE_FILE:-$ROOT/modeA_runs/decompiled_queue.txt}"
mkdir -p "$ROOT/modeA_runs/props_out"
touch "$DONE" "$FAIL" "$LOG"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

# offline gate first
if ! PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" "${HARMONY_DECOMPILE_HOME:-${KEA2_DECOMPILE_HOME:-$ROOT/../harmony-decompile}}/offline_check.py" >>"$LOG" 2>&1; then
  log "OFFLINE_CHECK failed — abort (fix signals/imports before phone run)"
  exit 2
fi
log "OFFLINE_CHECK ok"

if [[ ! -f "$QUEUE" ]]; then
  cat >"$QUEUE" <<'Q'
# pkg|property modules (comma)
com.huawei.hmos.calculator|properties.modeA_props.calculator_decompiled,properties.modeA_props.decompiled
com.ctrip.harmonynext|properties.modeA_props.ctrip_ctimage,properties.modeA_props.decompiled,properties.modeA_props.bug_find
com.amap.hmapp|properties.modeA_props.decompiled,properties.modeA_props.flow,properties.modeA_props.bug_find
com.sankuai.dianping|properties.modeA_props.decompiled,properties.modeA_props.semantic,properties.modeA_props.bug_find
com.sankuai.hmeituan|properties.modeA_props.decompiled,properties.modeA_props.flow,properties.modeA_props.bug_find
com.sina.weibo.stage|properties.modeA_props.decompiled,properties.modeA_props.semantic,properties.modeA_props.bug_find
com.taobao.idlefish4ohos|properties.modeA_props.decompiled,properties.modeA_props.deep_hunt,properties.modeA_props.bug_find
com.zhihu.hmos|properties.modeA_props.decompiled,properties.modeA_props.semantic,properties.modeA_props.bug_find
com.ss.hm.ugc.aweme|properties.modeA_props.decompiled,properties.modeA_props.video_feed,properties.modeA_props.bug_find
com.kuaishou.hmapp|properties.modeA_props.decompiled,properties.modeA_props.video_feed,properties.modeA_props.bug_find
com.phoenix.read.next|properties.modeA_props.decompiled,properties.modeA_props.content_apps,properties.modeA_props.bug_find
com.youku.next|properties.modeA_props.decompiled,properties.modeA_props.video_feed,properties.modeA_props.bug_find
com.xunmeng.pinduoduo.hos|properties.modeA_props.decompiled,properties.modeA_props.flow,properties.modeA_props.bug_find
Q
fi

log "DECOMPILED CAMPAIGN start mins=$MINS maxstep=$MAXSTEP serial=$SERIAL"

# device present? (hdc prints "[Empty]" offline — do not match letters in that word)
devs=$(hdc list targets 2>/dev/null | tr -d '\r' | rg -v '^\s*$|Empty|\[|\]' || true)
if [[ -z "${devs// /}" ]]; then
  log "NO_DEVICE — queue ready at $QUEUE. Re-run when phone connected."
  log "offline_check already green; nothing else to do until hdc sees a serial."
  exit 0
fi

while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" || "$line" =~ ^# ]] && continue
  pkg="${line%%|*}"
  mods="${line#*|}"
  [[ "$mods" == "$pkg" ]] && mods="properties.modeA_props.decompiled"
  if rg -qx "$pkg" "$DONE" 2>/dev/null; then
    log "SKIP done $pkg"
    continue
  fi
  if ! hdc -t "$SERIAL" shell bm dump -a 2>/dev/null | tr -d '\t\r' | sed 's/^ *//' | rg -qx "$pkg"; then
    log "SKIP missing $pkg"
    continue
  fi
  # signals must exist
  if [[ ! -f "${HARMONY_DECOMPILE_HOME:-${KEA2_DECOMPILE_HOME:-$ROOT/../harmony-decompile}}/mined_all/$pkg/signals.json" ]]; then
    log "SKIP no signals $pkg"
    continue
  fi

  stamp=$(date +%Y%m%d_%H%M%S)
  out="$ROOT/modeA_runs/props_out/${pkg}_decompiled_${stamp}"
  mkdir -p "$out"
  log "START $pkg mods=$mods out=$out"

  IFS=',' read -ra MODARR <<<"$mods"
  prop_args=()
  for m in "${MODARR[@]}"; do
    prop_args+=("$m")
  done

  set +e
  KEA2_TARGET_PKG="$pkg" \
  PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" \
    "$ROOT/.venv/bin/kea2" run \
      --platform harmony \
      -s "$SERIAL" \
      -p "$pkg" \
      --running-minutes "$MINS" \
      --max-step "$MAXSTEP" \
      --throttle "$THROTTLE" \
      --take-screenshots \
      -o "$out" \
      --log-stamp "$stamp" \
      propertytest "${prop_args[@]}" \
      >>"$out/console.log" 2>&1
  rc=$?
  set -e

  fails=$(rg -c "FAIL:|AssertionError" "$out/console.log" 2>/dev/null || echo 0)
  crash=$(rg -c "has_crash_or_anr=True|Harmony\] CRASH|Harmony\] ANR|RangeError|Stack overflow" "$out/console.log" 2>/dev/null || echo 0)
  steps=0
  for f in "$out"/res_*/output_*/steps.log; do
    [[ -f "$f" ]] && steps=$(wc -l <"$f" | tr -d ' ')
  done
  log "END $pkg rc=$rc steps=$steps fails~$fails crash=$crash"
  echo "$pkg" >>"$DONE"
  if [[ "$rc" -ne 0 || "$crash" -ne 0 ]]; then
    echo "$pkg rc=$rc fails=$fails crash=$crash" >>"$FAIL"
    log "MARK_FAIL $pkg"
  else
    log "MARK_OK $pkg"
  fi
done <"$QUEUE"

log "DECOMPILED CAMPAIGN complete"
