#!/usr/bin/env bash
# Mode A + properties campaign (agent + Kea2).
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SERIAL="${SERIAL:-5SM0125606000291}"
MINS="${MINS:-4}"
THROTTLE="${THROTTLE:-750}"
MAXSTEP="${MAXSTEP:-40}"
LOG="$ROOT/modeA_runs/props_campaign.log"
DONE="$ROOT/modeA_runs/props_done.txt"
FAIL="$ROOT/modeA_runs/props_fail.txt"
mkdir -p "$ROOT/modeA_runs/props_out"
touch "$DONE" "$FAIL" "$LOG"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

# pkg|extra_property_modules (comma), empty = generic only
QUEUE_FILE="$ROOT/modeA_runs/props_queue.txt"
if [[ ! -f "$QUEUE_FILE" ]]; then
  cat >"$QUEUE_FILE" <<'Q'
com.amap.hmapp|properties.modeA_props.amap,properties.modeA_props.generic_ui
com.sankuai.hmeituan|properties.modeA_props.meituan,properties.modeA_props.generic_ui
com.sankuai.dianping|properties.modeA_props.content_apps,properties.modeA_props.generic_ui
com.quark.ohosbrowser|properties.modeA_props.quark,properties.modeA_props.generic_ui
com.qiyi.video.hmy|properties.modeA_props.video_feed,properties.modeA_props.generic_ui
yylx.danmaku.bili|properties.modeA_props.video_feed,properties.modeA_props.generic_ui
com.kugou.hmmusic|properties.modeA_props.video_feed,properties.modeA_props.generic_ui
com.ximalaya.ting.xmharmony|properties.modeA_props.video_feed,properties.modeA_props.generic_ui
com.youku.next|properties.modeA_props.video_feed,properties.modeA_props.generic_ui
com.mgtv.phone|properties.modeA_props.video_feed,properties.modeA_props.generic_ui
com.ss.hm.ugc.aweme.jingxuan|properties.modeA_props.video_feed,properties.modeA_props.generic_ui
com.qimao.novel|properties.modeA_props.content_apps,properties.modeA_props.generic_ui
com.lemon.hm.lv|properties.modeA_props.content_apps,properties.modeA_props.generic_ui
cn.mucang.hm.jiakao|properties.modeA_props.content_apps,properties.modeA_props.generic_ui
com.ctrip.harmonynext|properties.modeA_props.content_apps,properties.modeA_props.generic_ui
com.zhihu.hmos|properties.modeA_props.content_apps,properties.modeA_props.generic_ui
com.meitu.meitupic|properties.modeA_props.content_apps,properties.modeA_props.generic_ui
com.taobao.idlefish4ohos|properties.modeA_props.content_apps,properties.modeA_props.generic_ui
com.baidu.baidulite|properties.modeA_props.generic_ui
com.uc.mobile|properties.modeA_props.generic_ui
com.ss.dcar.auto|properties.modeA_props.generic_ui
com.beike.hongmeng|properties.modeA_props.generic_ui
com.anjuke.home|properties.modeA_props.generic_ui
com.tongcheng.hmos|properties.modeA_props.generic_ui
com.xunmeng.pinduoduo.hos|properties.modeA_props.generic_ui
com.zhuanzhuan.hmoszz|properties.modeA_props.generic_ui
com.tencent.videohm|properties.modeA_props.video_feed,properties.modeA_props.generic_ui
com.tencent.hm.qqmusic|properties.modeA_props.video_feed,properties.modeA_props.generic_ui
com.phoenix.read.next|properties.modeA_props.content_apps,properties.modeA_props.generic_ui
com.hm.cat.readall|properties.modeA_props.content_apps,properties.modeA_props.generic_ui
Q
fi

log "PROPS CAMPAIGN start mins=$MINS maxstep=$MAXSTEP"

while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" || "$line" =~ ^# ]] && continue
  pkg="${line%%|*}"
  mods="${line#*|}"
  [[ "$mods" == "$pkg" ]] && mods="properties.modeA_props.generic_ui"
  if rg -qx "$pkg" "$DONE" 2>/dev/null; then
    log "SKIP done $pkg"
    continue
  fi
  # installed?
  if ! hdc -t "$SERIAL" shell bm dump -a 2>/dev/null | tr -d '\t\r' | sed 's/^ *//' | rg -qx "$pkg"; then
    log "SKIP missing $pkg"
    continue
  fi
  stamp=$(date +%Y%m%d_%H%M%S)
  out="$ROOT/modeA_runs/props_out/${pkg}_${stamp}"
  mkdir -p "$out"
  log "START $pkg mods=$mods out=$out"

  # build propertytest args: multiple modules space-separated
  IFS=',' read -ra MODARR <<<"$mods"
  prop_args=()
  for m in "${MODARR[@]}"; do
    prop_args+=("$m")
  done

  set +e
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

  # summarize
  fails=$(rg -c "FAIL:|AssertionError|ERROR:" "$out/console.log" 2>/dev/null || echo 0)
  props_run=$(rg -c "Executing property|run property|Property" "$out/console.log" 2>/dev/null || echo 0)
  crash=$(rg -c "has_crash_or_anr=True|Harmony\] CRASH|Harmony\] ANR" "$out/console.log" 2>/dev/null || echo 0)
  steps=0
  for f in "$out"/res_*/output_*/steps.log; do
    [[ -f "$f" ]] && steps=$(wc -l <"$f" | tr -d ' ')
  done
  log "END $pkg rc=$rc steps=$steps fails~$fails props~$props_run crash=$crash"

  if [[ "$rc" -eq 0 && "$crash" -eq 0 ]]; then
    echo "$pkg" >>"$DONE"
    log "MARK_OK $pkg"
  else
    echo "$pkg rc=$rc fails=$fails crash=$crash" >>"$FAIL"
    log "MARK_FAIL $pkg rc=$rc"
    # still mark done to progress; failures recorded
    echo "$pkg" >>"$DONE"
  fi
done <"$QUEUE_FILE"

log "PROPS CAMPAIGN complete"
