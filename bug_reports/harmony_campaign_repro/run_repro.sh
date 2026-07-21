#!/usr/bin/env bash
# Reproduce lab Kea2 HarmonyOS campaign (T0 property runs) end-to-end.
#
# Usage:
#   bash run_repro.sh                  # all installed apps from apps.tsv
#   bash run_repro.sh maoyan wps        # subset by name
#   bash run_repro.sh --list
#   bash run_repro.sh --tongxin-blank   # also run blank cold-start probe
#
# Env:
#   PBT_KEA_DEVICE / DEVICE   hdc serial (auto if one device)
#   KEA2_HOME                 default: repo root (../.. from this dir) or ~/github/Kea2
#   EVENTS                    default 15
#   OUT_ROOT                  default: ./out_<timestamp>
#   SKIP_MISSING=1            skip apps not installed (default)
set -euo pipefail
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:${PATH}"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
KEA2_HOME="${KEA2_HOME:-${PBT_KEA_HOME:-$REPO}}"
[[ -d "$KEA2_HOME" ]] || KEA2_HOME="${HOME}/github/Kea2"
EVENTS="${EVENTS:-15}"
THROTTLE_MS="${THROTTLE_MS:-700}"
RUNNING_MINS="${RUNNING_MINS:-$(( EVENTS / 8 + 2 ))}"
SKIP_MISSING="${SKIP_MISSING:-1}"
OUT_ROOT="${OUT_ROOT:-$HERE/out_$(date +%Y%m%d_%H%M%S)}"
APPS_TSV="${APPS_TSV:-$HERE/apps.tsv}"
PROPS_DIR="$HERE/properties"

DEVICE="${PBT_KEA_DEVICE:-${DEVICE:-}}"
if [[ -z "$DEVICE" ]]; then
  DEVICE="$(hdc list targets 2>/dev/null | awk 'NF && $1 !~ /[Ee]mpty/ {print $1; exit}')"
fi

die() { echo "FAIL: $*" >&2; exit 1; }
info() { echo "$*"; }

KEA2_BIN=""
for c in "$KEA2_HOME/.venv/bin/kea2" "$KEA2_HOME/venv/bin/kea2" "$(command -v kea2 || true)"; do
  [[ -n "$c" && -x "$c" ]] && KEA2_BIN="$c" && break
done
[[ -n "$KEA2_BIN" ]] || die "kea2 binary not found under $KEA2_HOME (pip install -e . in venv)"

# ---- args ----
LIST_ONLY=0
DO_TONGXIN=0
NAMES=()
for a in "$@"; do
  case "$a" in
    --list) LIST_ONLY=1 ;;
    --tongxin-blank) DO_TONGXIN=1 ;;
    -h|--help)
      sed -n '2,20p' "$0"
      exit 0
      ;;
    *) NAMES+=("$a") ;;
  esac
done

pkg_installed() {
  local pkg="$1"
  hdc -t "$DEVICE" shell "bm dump -n $pkg" 2>/dev/null | grep -q "\"name\": \"$pkg\"" \
    || hdc -t "$DEVICE" shell "bm dump -a" 2>/dev/null | grep -q "$pkg"
}

ensure_screen() {
  hdc -t "$DEVICE" shell power-shell wakeup >/dev/null 2>&1 || true
  hdc -t "$DEVICE" shell "power-shell setmode 602" >/dev/null 2>&1 || true
  for _ in 1 2 3; do
    hdc -t "$DEVICE" shell "uitest uiInput swipe 640 2500 640 400 250" >/dev/null 2>&1 || true
    sleep 0.3
  done
}

start_app() {
  local pkg="$1"
  local ab="EntryAbility"
  local dump
  dump="$(hdc -t "$DEVICE" shell "bm dump -n $pkg" 2>/dev/null || true)"
  if printf '%s' "$dump" | grep -q '"mainAbility"'; then
    ab="$(printf '%s' "$dump" | python3 -c 'import sys,re; m=re.findall(r"\"mainAbility\"\s*:\s*\"([^\"]+)\"",sys.stdin.read()); print(m[0].split(".")[-1] if m else "EntryAbility")' 2>/dev/null || echo EntryAbility)"
  fi
  hdc -t "$DEVICE" shell "aa force-stop $pkg" >/dev/null 2>&1 || true
  sleep 0.4
  hdc -t "$DEVICE" shell "aa start -a $ab -b $pkg" >/dev/null 2>&1 || true
  sleep 2.5
  # privacy dismiss best-effort (common labels)
  python3 - "$DEVICE" <<'PY' || true
import re, subprocess, sys, time, json
D=sys.argv[1]
labs=("同意并继续","同意","使用基本服务","跳过","Deny","关闭","我知道了","下次再说","取消","我再想想")
def sh(c,t=25):
    r=subprocess.run(c,shell=True,capture_output=True,text=True,timeout=t)
    return (r.stdout or "")+(r.stderr or "")
for _ in range(4):
    sh(f'hdc -t {D} shell "uitest dumpLayout -p /data/local/tmp/repro_d.json"')
    sh(f'hdc -t {D} file recv /data/local/tmp/repro_d.json /tmp/repro_d.json')
    try: data=json.load(open("/tmp/repro_d.json",encoding="utf-8",errors="replace"))
    except Exception: break
    hits=[]
    def walk(n):
        if isinstance(n,dict):
            a=n.get("attributes") or {}
            t=(a.get("text") or "").strip(); b=a.get("bounds")
            if t: hits.append((t,b))
            for c in n.get("children") or []: walk(c)
        elif isinstance(n,list):
            for c in n: walk(c)
    walk(data)
    clicked=False
    for lab in labs:
        for t,b in hits:
            if t==lab and b:
                m=re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", b)
                if not m: continue
                x=(int(m.group(1))+int(m.group(3)))//2; y=(int(m.group(2))+int(m.group(4)))//2
                sh(f'hdc -t {D} shell "uitest uiInput click {x} {y}"')
                time.sleep(0.7); clicked=True; break
        if clicked: break
    if not clicked: break
PY
}

parse_last() {
  local out="$1"
  python3 - "$out" <<'PY'
import json, sys
from pathlib import Path
out = Path(sys.argv[1])
cands = list(out.rglob("LAST_RUN.json"))
if not cands:
    # fallback: result_*.json
    cands = list(out.rglob("result_*.json"))
if not cands:
    print(json.dumps({"status":"no_result","executed_total":0,"fail_total":0,"error_total":0,"properties":[]}))
    sys.exit(0)
def load(p):
    d=json.loads(p.read_text())
    if "executed_total" in d: return d
    # raw kea2 result shape
    props=[]
    ex=fa=er=0
    for k,v in (d if isinstance(d,dict) else {}).items():
        if not isinstance(v, dict): continue
        if "fail" not in v and "error" not in v and "executed" not in str(v).lower():
            continue
    # try property summary in log sibling
    return d
best=None
for p in cands:
    try:
        d=json.loads(p.read_text())
    except Exception:
        continue
    if "executed_total" in d:
        if best is None or d.get("executed_total",0) >= best.get("executed_total",0):
            best=d
if best is None:
    best={"status":"unknown","executed_total":0,"fail_total":0,"error_total":0,"properties":[],"raw":str(cands[0])}
print(json.dumps(best, ensure_ascii=False))
PY
}

# ---- preflight ----
[[ -n "$DEVICE" ]] || die "no hdc device (connect USB, enable debugging)"
info "device=$DEVICE"
info "kea2=$KEA2_BIN"
info "kea2_home=$KEA2_HOME"
info "events=$EVENTS out=$OUT_ROOT"
hdc list targets | head -5
ensure_screen

# load apps
declare -a APP_LINES=()
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" || "$line" =~ ^# ]] && continue
  APP_LINES+=("$line")
done < "$APPS_TSV"

if [[ "$LIST_ONLY" == "1" ]]; then
  printf '%s\t%s\t%s\n' "name" "package" "installed?"
  for line in "${APP_LINES[@]}"; do
    IFS=$'\t' read -r name pkg prop min_exec lab notes <<<"$line"
    inst=no
    pkg_installed "$pkg" && inst=yes
    printf '%s\t%s\t%s\n' "$name" "$pkg" "$inst"
  done
  exit 0
fi

mkdir -p "$OUT_ROOT"
SUMMARY="$OUT_ROOT/SUMMARY.md"
RESULTS_JSON="$OUT_ROOT/RESULTS.json"
echo "[]" > "$RESULTS_JSON"

{
  echo "# Kea2 Harmony campaign repro"
  echo
  echo "- **When:** $(date -Iseconds 2>/dev/null || date)"
  echo "- **Device:** \`$DEVICE\`"
  echo "- **Kea2:** \`$KEA2_BIN\`"
  echo "- **Events:** $EVENTS"
  echo
  echo "| app | package | installed | status | exec | fail | err | lab |"
  echo "|---|---|---|---|---:|---:|---:|---|"
} > "$SUMMARY"

run_one() {
  local name="$1" pkg="$2" prop="$3" min_exec="$4" lab="$5"
  local prop_path="$PROPS_DIR/$prop"
  local out="$OUT_ROOT/$name"
  mkdir -p "$out"

  if ! pkg_installed "$pkg"; then
    info "SKIP $name ($pkg) — not installed"
    echo "| $name | \`$pkg\` | no | skipped | — | — | — | $lab |" >> "$SUMMARY"
    python3 - "$RESULTS_JSON" "$name" "$pkg" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1]); name,pkg=sys.argv[2],sys.argv[3]
rows=json.loads(p.read_text())
rows.append({"name":name,"package":pkg,"installed":False,"status":"skipped"})
p.write_text(json.dumps(rows,indent=2,ensure_ascii=False))
PY
    return 0
  fi

  [[ -f "$prop_path" ]] || die "missing property file $prop_path"

  info "=== RUN $name ($pkg) prop=$prop ==="
  ensure_screen
  start_app "$pkg"

  set +e
  (
    cd "$KEA2_HOME"
    # discover needs file in a path kea2 can import — run via absolute discover
    "$KEA2_BIN" run --platform harmony \
      -s "$DEVICE" \
      -p "$pkg" \
      --max-step "$EVENTS" \
      --running-minutes "$RUNNING_MINS" \
      --throttle "$THROTTLE_MS" \
      -o "$out" \
      propertytest discover -s "$PROPS_DIR" -p "$prop" \
      2>&1 | tee "$out/kea.log"
  )
  rc=${PIPESTATUS[0]}
  set -e

  # parse LAST_RUN or synthesize from log Property Execution Summary
  python3 - "$out" "$rc" "$min_exec" <<'PY' > "$out/LAST_RUN.json"
import json, re, sys
from pathlib import Path
out = Path(sys.argv[1]); rc=int(sys.argv[2]); min_exec=int(sys.argv[3])
# prefer engine LAST_RUN
cands=list(out.rglob("LAST_RUN.json"))
best=None
for p in cands:
    if p.resolve() == (out/"LAST_RUN.json").resolve():
        continue
    try:
        d=json.loads(p.read_text())
    except Exception:
        continue
    if "executed_total" in d:
        if best is None or d.get("executed_total",0) >= best.get("executed_total",0):
            best=d
if best is None:
    # parse kea.log summary
    log = out/"kea.log"
    text = log.read_text(errors="replace") if log.exists() else ""
    m = re.search(r"Property Execution Summary.*?Errors:(\d+),\s*Fails:(\d+)", text)
    # per-property from Load + FAIL lines is hard; count Check Property passes
    executed = len(re.findall(r"Check Property|ok$|PASS", text, re.I))
    # better: unittest-style " ... ok"
    oks = len(re.findall(r"\) \.\.\. ok\b", text))
    fails = len(re.findall(r"\nFAIL:", text))
    errors = len(re.findall(r"\nERROR:", text))
    if m:
        errors = int(m.group(1)); fails = int(m.group(2))
    # executed from result json if any
    for rj in out.rglob("result_*.json"):
        try:
            raw=json.loads(rj.read_text())
        except Exception:
            continue
        # Kea2 result: dict of prop -> stats
        if isinstance(raw, dict) and raw:
            props=[]
            ex=fa=er=0
            for name, st in raw.items():
                if not isinstance(st, dict): continue
                e=int(st.get("executed", st.get("exec", 0) or 0))
                f=int(st.get("fail", st.get("fails", 0) or 0))
                r=int(st.get("error", st.get("errors", 0) or 0))
                # alternate keys
                if e==0 and "total" in st: e=int(st.get("total") or 0)
                props.append({"name": name.split(".")[-1], "executed": e, "fail": f, "error": r,
                              "status": "FAIL" if f else ("ERROR" if r else ("pass" if e else "not_checked"))})
                ex+=e; fa+=f; er+=r
            if props:
                best={"status":"ran_ok" if fa==0 and er==0 and ex>0 else ("test_bug" if er else ("failing" if fa else "not_checked")),
                      "executed_total":ex,"fail_total":fa,"error_total":er,"properties":props,"result_json":str(rj)}
                break
    if best is None:
        ex = max(oks, 0)
        status = "ran_ok" if fails==0 and errors==0 and ex>0 else ("failing" if fails else ("test_bug" if errors else "not_checked"))
        best={"status":status,"executed_total":ex,"fail_total":fails,"error_total":errors,"properties":[],"exit_code":rc}
# stamp
best["exit_code"]=rc
best["min_exec_expected"]=min_exec
print(json.dumps(best, indent=2, ensure_ascii=False))
PY

  local st execn failn errn
  st="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("status","?"))' "$out/LAST_RUN.json")"
  execn="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("executed_total",0))' "$out/LAST_RUN.json")"
  failn="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("fail_total",0))' "$out/LAST_RUN.json")"
  errn="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("error_total",0))' "$out/LAST_RUN.json")"
  info "RESULT $name: status=$st e=$execn f=$failn err=$errn (lab=$lab min_exec=$min_exec)"
  echo "| $name | \`$pkg\` | yes | **$st** | $execn | $failn | $errn | $lab |" >> "$SUMMARY"

  python3 - "$RESULTS_JSON" "$name" "$pkg" "$out/LAST_RUN.json" <<'PY'
import json,sys
from pathlib import Path
rp, name, pkg, lastp = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4])
rows=json.loads(rp.read_text())
d=json.loads(lastp.read_text())
d.update({"name":name,"package":pkg,"installed":True})
rows.append(d)
rp.write_text(json.dumps(rows,indent=2,ensure_ascii=False))
PY

  hdc -t "$DEVICE" shell "aa force-stop $pkg" >/dev/null 2>&1 || true
}

# ---- select apps ----
for line in "${APP_LINES[@]}"; do
  IFS=$'\t' read -r name pkg prop min_exec lab notes <<<"$line"
  if [[ ${#NAMES[@]} -gt 0 ]]; then
    want=0
    for n in "${NAMES[@]}"; do [[ "$n" == "$name" ]] && want=1; done
    [[ $want -eq 1 ]] || continue
  fi
  run_one "$name" "$pkg" "$prop" "$min_exec" "$lab"
done

# ---- optional tongxin blank ----
if [[ "$DO_TONGXIN" == "1" ]]; then
  TDIR="$HERE/../com.csai.tongxin_blank_cold_start"
  if [[ -x "$TDIR/repro_blank_cold_start.sh" ]]; then
    info "=== tongxin blank cold-start probe ==="
    bash "$TDIR/repro_blank_cold_start.sh" 10 10 "$DEVICE" "$OUT_ROOT/tongxin_blank" \
      | tee "$OUT_ROOT/tongxin_blank.log" || true
    echo >> "$SUMMARY"
    echo "## Tongxin blank cold-start" >> "$SUMMARY"
    echo '```' >> "$SUMMARY"
    tail -5 "$OUT_ROOT/tongxin_blank.log" >> "$SUMMARY" || true
    echo '```' >> "$SUMMARY"
  else
    info "tongxin repro script missing at $TDIR"
  fi
fi

{
  echo
  echo "## How to read"
  echo
  echo "- **ran_ok** + exec ≥ lab min → matches clean T0 campaign"
  echo "- **failing** → assertion fail (possible SUT or flaky settle)"
  echo "- **test_bug** → ElementNotFound / selector error (test issue)"
  echo "- **not_checked** / exec=0 → precond never met (login wall / wrong UI)"
  echo "- Per-app logs: \`$OUT_ROOT/<name>/kea.log\`"
  echo "- Machine summary: \`$RESULTS_JSON\`"
  echo
  echo "## Lab baseline (original campaign)"
  echo
  echo "See [README.md](../harmony_campaign_repro/README.md#lab-baseline)."
} >> "$SUMMARY"

info ""
info "DONE → $SUMMARY"
cat "$SUMMARY"
