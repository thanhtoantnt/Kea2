#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
SERIAL="${SERIAL:-5SM0125606000291}"
MINS=4; MAXSTEP=50; THROTTLE=350
STAMP_RUN=$(date +%Y%m%d_%H%M%S)
LOG="$ROOT/modeA_runs/multi_decomp_v3b_${STAMP_RUN}.log"
SUMMARY="$ROOT/modeA_runs/props_out/MULTI_DECOMP_V3B_${STAMP_RUN}.tsv"
echo -e "pkg\tout\tsteps\tprops\tfired\tfire_pct\texecs\tdecomp_execs\tfails\terrors\tcrash\twidgets" > "$SUMMARY"
echo "RUN_V3B recover thin apps $STAMP_RUN" | tee "$LOG"
packs_for() {
  case "$1" in
    com.huawei.hmos.calculator) echo "properties.modeA_props.calculator_decompiled properties.modeA_props.decompiled properties.modeA_props.bug_find";;
    com.ctrip.harmonynext) echo "properties.modeA_props.ctrip_ctimage properties.modeA_props.decompiled properties.modeA_props.bug_find properties.modeA_props.flow";;
    *) echo "properties.modeA_props.decompiled properties.modeA_props.bug_find properties.modeA_props.flow";;
  esac
}
# apps that collapsed or failed in V3
QUEUE=(com.phoenix.read.next com.youku.next com.xunmeng.pinduoduo.hos com.kuaishou.hmapp com.ss.hm.ugc.aweme com.huawei.hmos.calculator com.ctrip.harmonynext com.taobao.idlefish4ohos)
for pkg in "${QUEUE[@]}"; do
  stamp=$(date +%Y%m%d_%H%M%S)
  out="$ROOT/modeA_runs/props_out/${pkg}_multiv3b_${stamp}"
  mkdir -p "$out"
  packs=$(packs_for "$pkg")
  echo "[$(date -Iseconds)] START $pkg" | tee -a "$LOG"
  # hdc agent recover before each app
  hdc -t "$SERIAL" shell "rm -f /data/local/tmp/agent.so" >/dev/null 2>&1 || true
  hdc -t "$SERIAL" shell aa force-stop "$pkg" >/dev/null 2>&1 || true
  sleep 2
  set +e
  # shellcheck disable=SC2086
  KEA2_TARGET_PKG="$pkg" PYTHONPATH="$ROOT" \
    "$ROOT/.venv/bin/kea2" run --platform harmony -s "$SERIAL" -p "$pkg" \
    --running-minutes "$MINS" --max-step "$MAXSTEP" --throttle "$THROTTLE" \
    --take-screenshots -o "$out" --log-stamp "$stamp" \
    propertytest $packs >"$out/console.log" 2>&1
  ec=$?
  # one retry on hdc agent failure
  if [[ $ec -ne 0 ]] && rg -q "HdcError|operation not permitted" "$out/console.log"; then
    echo "RETRY $pkg after HdcError" | tee -a "$LOG"
    hdc -t "$SERIAL" shell "rm -f /data/local/tmp/agent.so" >/dev/null 2>&1 || true
    sleep 3
    stamp2=$(date +%Y%m%d_%H%M%S)
    out="$ROOT/modeA_runs/props_out/${pkg}_multiv3b_${stamp2}"
    mkdir -p "$out"
    KEA2_TARGET_PKG="$pkg" PYTHONPATH="$ROOT" \
      "$ROOT/.venv/bin/kea2" run --platform harmony -s "$SERIAL" -p "$pkg" \
      --running-minutes "$MINS" --max-step "$MAXSTEP" --throttle "$THROTTLE" \
      --take-screenshots -o "$out" --log-stamp "$stamp2" \
      propertytest $packs >"$out/console.log" 2>&1
    ec=$?
  fi
  set -e
  PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" - "$pkg" "$out" "$SUMMARY" <<'PY'
import json,re,sys
from pathlib import Path
pkg,out,summary=sys.argv[1:4]; out=Path(out)
res=next(out.glob("res_*/result_*.json"), None)
log=(out/"console.log").read_text(errors="replace") if (out/"console.log").exists() else ""
steps=re.findall(r"step=(\d+)", log); widgets=re.findall(r"unique widgets triggered: (\d+)", log)
crash="has_crash_or_anr=True" in log
r={}; 
if res:
  try: r=json.loads(res.read_text())
  except: pass
n=fired=te=tf=terr=de=0
for name,v in r.items():
  if not isinstance(v,dict) or v.get("kind")!="property": continue
  n+=1; e=int(v.get("executed") or 0); f=int(v.get("fail") or 0); er=int(v.get("error") or 0)
  te+=e; tf+=f; terr+=er
  if e: fired+=1
  if any(x in name for x in (".decompiled.",".ctrip_ctimage.",".calculator_decompiled.")): de+=e
fire=round(100*fired/n,1) if n else 0
st=steps[-1] if steps else "0"; wg=widgets[-1] if widgets else "0"
Path(summary).open("a").write(f"{pkg}\t{out}\t{st}\t{n}\t{fired}\t{fire}\t{te}\t{de}\t{tf}\t{terr}\t{int(crash)}\t{wg}\n")
print(f"{pkg} steps={st} fire={fired}/{n}={fire}% ex={te} de={de} fail={tf}")
PY
  echo "[$(date -Iseconds)] END $pkg ec=$ec" | tee -a "$LOG"
done
echo BATCH_DONE | tee -a "$LOG"
cat "$SUMMARY" | tee -a "$LOG"
