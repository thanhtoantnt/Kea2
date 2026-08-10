#!/usr/bin/env bash
# Continuous Mode A: kea2-only per app. Improve props in repo between rounds.
# Stop: kill $(cat modeA_runs/modeA_loop.pid)
set +e
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
export HARMONY_DECOMPILE_HOME="${HARMONY_DECOMPILE_HOME:-${KEA2_DECOMPILE_HOME:-$ROOT/../harmony-decompile}}"
export KEA2_DECOMPILE_HOME="$HARMONY_DECOMPILE_HOME"
SERIAL="${SERIAL:-5SM0125606000291}"
MINS="${MINS:-6}"
MAXSTEP="${MAXSTEP:-70}"
THROTTLE="${THROTTLE:-200}"
# optional unlock password (file preferred; never commit)
if [[ -z "${KEA2_UNLOCK_PASSWORD:-}" && -f "$ROOT/modeA_runs/.device_unlock" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/modeA_runs/.device_unlock"
fi
export KEA2_UNLOCK_PASSWORD="${KEA2_UNLOCK_PASSWORD:-}"
STAMP=$(date +%Y%m%d_%H%M%S)
LOG="$ROOT/modeA_runs/modeA_loop_${STAMP}.log"
SUMMARY="$ROOT/modeA_runs/props_out/MODEA_LOOP_${STAMP}.tsv"
PIDFILE="$ROOT/modeA_runs/modeA_loop.pid"
echo $$ >"$PIDFILE"
echo -e "round\tpkg\tout\tsteps\texecs\tdecomp\tbug20\tfails\tcrash\twidgets" >"$SUMMARY"
echo "LOOP_START $STAMP mins=$MINS pid=$$" | tee -a "$LOG"

QUEUE=(
  # core guest store (decomp signals)
  com.amap.hmapp
  com.sankuai.dianping
  com.zhihu.hmos
  com.sina.weibo.stage
  com.sankuai.hmeituan
  com.youku.next
  com.xunmeng.pinduoduo.hos
  com.kuaishou.hmapp
  com.ss.hm.ugc.aweme
  com.ctrip.harmonynext
  com.fliggy.hmos
  com.anjuke.home
  com.ss.hm.article.video
  com.meituan.takeaway
  cn.damai.hongmeng
  cn.mucang.hm.jiakao
  # baicizhan dropped: login/empty dump tarpit (3 steps/6min)
)

packs_for() {
  case "$1" in
    com.ctrip.harmonynext)
      echo "properties.modeA_props.ctrip_ctimage properties.modeA_props.decompiled properties.modeA_props.bug_classes properties.modeA_props.bug_find properties.modeA_props.flow";;
    *)
      echo "properties.modeA_props.decompiled properties.modeA_props.bug_classes properties.modeA_props.bug_find properties.modeA_props.flow";;
  esac
}

refresh_inst() {
  # retry bm dump — empty dump caused R1 skip-all
  local i out=""
  for i in 1 2 3 4 5; do
    out=$(hdc -t "$SERIAL" shell "bm dump -a" 2>/dev/null | tr -d '\t\r' | sed 's/^ *//' | grep -E '^[a-zA-Z0-9_.]+$')
    if [[ -n "$out" ]]; then
      echo "$out"
      return 0
    fi
    sleep 2
  done
  echo ""
  return 1
}

is_installed() {
  local pkg="$1" inst="$2"
  # substring line match; avoid -x flake on BOM/spaces
  echo "$inst" | grep -F "$pkg" >/dev/null 2>&1
}

wake() {
  # python unlock path (swipe + optional password)
  ROOT="$ROOT" SERIAL="$SERIAL" KEA2_UNLOCK_PASSWORD="${KEA2_UNLOCK_PASSWORD:-}" \
    "$ROOT/.venv/bin/python" - <<'PY' 2>/dev/null || true
import os, sys
sys.path.insert(0, os.environ["ROOT"])
from kea2.hdcUtils import HDCDevice
HDCDevice.setDevice(os.environ.get("SERIAL"))
HDCDevice().unlock()
PY
  hdc -t "$SERIAL" shell "rm -f /data/local/tmp/agent.so" >/dev/null 2>&1 || true
  # clear stale fports that break hmdriver2
  hdc -t "$SERIAL" fport ls 2>/dev/null | awk '/tcp:/{print $2}' | while read -r p; do
    hdc -t "$SERIAL" fport rm "$p" >/dev/null 2>&1 || true
  done
}

score() {
  local round="$1" pkg="$2" out="$3"
  PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" - "$round" "$pkg" "$out" "$SUMMARY" <<'PY'
import json,re,sys
from pathlib import Path
round,pkg,out,summary=sys.argv[1:5]
out=Path(out)
log=(out/"console.log").read_text(errors="replace") if (out/"console.log").exists() else ""
steps=re.findall(r"step=(\d+)", log)
widgets=re.findall(r"unique widgets triggered: (\d+)", log)
crash=int("has_crash_or_anr=True" in log)
res=next(out.glob("res_*/result_*.json"), None)
te=tf=de=bc=0
if res:
  try:
    r=json.loads(res.read_text())
  except Exception:
    r={}
  for name,v in r.items():
    if not isinstance(v,dict) or v.get("kind")!="property": continue
    e=int(v.get("executed") or 0); f=int(v.get("fail") or 0)
    te+=e; tf+=f
    if ".decompiled." in name or ".ctrip_ctimage." in name or ".calculator_decompiled." in name:
      de+=e
    if ".bug_classes." in name:
      bc+=e
st=steps[-1] if steps else "0"
wg=widgets[-1] if widgets else "0"
Path(summary).open("a").write(f"{round}\t{pkg}\t{out}\t{st}\t{te}\t{de}\t{bc}\t{tf}\t{crash}\t{wg}\n")
print(f"R{round} {pkg} steps={st} ex={te} de={de} bc={bc} fail={tf} crash={crash}", flush=True)
if tf or crash:
  Path(out/"_NEEDS_TRIAGE").write_text(f"fails={tf} crash={crash}\n")
# mark transport flake
if re.search(r"DeviceNotFoundError|ConnectionResetError|No devices found|Unexpected Error", log):
  Path(out/"_TRANSPORT_FLAKE").write_text("1\n")
PY
}

run_kea() {
  # prints ONLY exit code on stdout (caller: ec=$(run_kea ...))
  local pkg="$1" out="$2" packs="$3" stamp="$4" try ec=1
  for try in 1 2 3; do
    wake
    sleep 1
    # shellcheck disable=SC2086
    KEA2_TARGET_PKG="$pkg" PYTHONPATH="$ROOT" \
      "$ROOT/.venv/bin/kea2" run --platform harmony -s "$SERIAL" -p "$pkg" \
      --running-minutes "$MINS" --max-step "$MAXSTEP" --throttle "$THROTTLE" \
      -o "$out" --log-stamp "r${round}_${stamp}_t${try}" \
      propertytest $packs >"$out/console.log" 2>&1
    ec=$?
    if [[ $ec -eq 0 ]]; then
      printf '%s' "$ec"
      return 0
    fi
    if rg -q "DeviceNotFoundError|ConnectionResetError|No devices found|Unexpected Error in KeaTestRunner" "$out/console.log" 2>/dev/null; then
      # log only — never stdout (pollutes ec= capture)
      echo "RETRY $pkg try=$try ec=$ec" >>"$LOG"
      echo "RETRY $pkg try=$try ec=$ec" >&2
      hdc list targets >/dev/null 2>&1 || sleep 3
      sleep 4
      continue
    fi
    printf '%s' "$ec"
    return 0
  done
  printf '%s' "$ec"
}

round=0
while true; do
  round=$((round+1))
  echo "[$(date +%F\ %T)] ROUND $round" | tee -a "$LOG"
  wake
  INST=$(refresh_inst)
  ninst=$(echo "$INST" | grep -c . || true)
  echo "[$(date +%F\ %T)] installed_lines=$ninst" | tee -a "$LOG"
  if [[ "$ninst" -lt 5 ]]; then
    echo "WARN bm dump thin — retry round after sleep" | tee -a "$LOG"
    sleep 10
    INST=$(refresh_inst)
    ninst=$(echo "$INST" | grep -c . || true)
    echo "installed_lines_retry=$ninst" | tee -a "$LOG"
  fi
  for pkg in "${QUEUE[@]}"; do
    if [[ "$ninst" -ge 5 ]] && ! is_installed "$pkg" "$INST"; then
      echo "SKIP not installed $pkg" | tee -a "$LOG"
      continue
    fi
    # hard gate: installed app + offline decompile signals required
    sig="${HARMONY_DECOMPILE_HOME:-${KEA2_DECOMPILE_HOME:-$ROOT/../harmony-decompile}}/mined_all/$pkg/signals.json"
    if [[ ! -f "$sig" ]]; then
      echo "ABORT no decompile signals $pkg — expected $sig (prep HAP/ABC→mine before Mode A)" | tee -a "$LOG"
      mkdir -p "$ROOT/modeA_runs/props_out"
      echo "missing $sig" >"$ROOT/modeA_runs/props_out/${pkg}_NO_DECOMPILE.abort"
      continue
    fi
    if ! PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" -m properties.modeA_props.decompile_gate "$pkg" >/dev/null 2>>"$LOG"; then
      echo "ABORT decompile gate failed $pkg" | tee -a "$LOG"
      continue
    fi
    # if dump failed, still try queue (better than skip-all)
    stamp=$(date +%Y%m%d_%H%M%S)
    out="$ROOT/modeA_runs/props_out/${pkg}_loop_r${round}_${stamp}"
    mkdir -p "$out"
    packs=$(packs_for "$pkg")
    echo "[$(date +%F\ %T)] START $pkg" | tee -a "$LOG"
    ec=$(run_kea "$pkg" "$out" "$packs" "$stamp")
    echo "[$(date +%F\ %T)] END $pkg ec=$ec" | tee -a "$LOG"
    score "$round" "$pkg" "$out" | tee -a "$LOG"
  done
  echo "[$(date +%F\ %T)] ROUND $round DONE — sleep 15s then continue" | tee -a "$LOG"
  sleep 15
done
