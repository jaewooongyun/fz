#!/bin/bash
# verify-gates 판정 축 러너 (round 2 S12) — 판 끝 절차 뒤 시점 축(post_procedure · F-390)이 스키마 · 프롬프트 · 사후 대조에 배선됐는가.
#
# ⛔ 셀:
#   f390-post-procedure-axis   스키마 required · enum(holds|breaks|unknown|n/a) 에 post_procedure · verify-gates 프롬프트 블록이 그 축과
#                              [판 끝 절차] 줄을 적는다 · gate_check --verdict-check — 원장 머리 RELEASE_PROCEDURE 가 있으면 n/a · 누락 거부,
#                              holds 통과, breaks + accept 거부 · 머리가 없으면 축 없는 옛 응답도 통과(호환)
# ⛔ 모델을 부르지 않는다 — 판정 파일을 손으로 만들어 사후 대조기만 돌린다.
# usage: run.sh [--tree <플러그인 트리>]   (기본: 이 fixture 가 든 트리 — health-check 는 인자 없이 부른다)
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TREE="$(cd "$HERE/../../../.." && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "PREP  --tree 에 경로가 없다"; exit 3; }
            TREE="$(cd "$2" 2>/dev/null && pwd)" || { echo "PREP  --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "PREP  알 수 없는 인자: $1"; exit 3 ;;
  esac
done
for f in schemas/gpt_gate_verdict_schema.json modules/fz-gpt-subcommands-core.md scripts/gate_check.py; do
  [ -f "$TREE/$f" ] || { echo "PREP  없음: $TREE/$f"; exit 3; }
done
command -v python3 >/dev/null 2>&1 || { echo "PREP  python3 필요"; exit 3; }
T="$(mktemp -d "${TMPDIR:-/tmp}/vg-axes.XXXXXX")" || { echo "PREP  mktemp 실패"; exit 3; }
trap 'rm -rf "$T"' EXIT

python3 - "$TREE" "$T" <<'PY'
import json, os, subprocess, sys
tree, t = sys.argv[1], sys.argv[2]
sch = json.load(open(os.path.join(tree, "schemas/gpt_gate_verdict_schema.json"), encoding="utf-8"))
item = sch["properties"]["gates"]["items"]
pp = item["properties"].get("post_procedure") or {}
s_ok = "post_procedure" in item["required"] and sorted(pp.get("enum") or []) == ["breaks", "holds", "n/a", "unknown"]
core = open(os.path.join(tree, "modules/fz-gpt-subcommands-core.md"), encoding="utf-8").read()
blk = core[core.index("[원장 경로] {LEDGER 절대경로}"):]
blk = blk[:blk.index("```")]
p_ok = "post_procedure" in blk and "[판 끝 절차]" in blk and "RELEASE_PROCEDURE" in blk


def ledger(name, header):
    p = os.path.join(t, name + ".md")
    open(p, "w", encoding="utf-8").write(f"# Gates: t\nROOT: {t}\nSTATE: active\n{header}\n- [ ] G1: 제목 하나\n  CHECK: true\n  EXPECT: ok\n")
    return p


def verdict(name, **extra):
    g = {"id": "G1", "title": "제목 하나", "kind": "command", "measurement_fit": "fit", "noninteractive": True, "rerunnable": True,
         "determinism": "deterministic", "side_effects": "none", "verdict": "accept", "reason": "r", "suggestion": None}
    g.update(extra)
    p = os.path.join(t, name + ".json")
    json.dump({"schemaVersion": "1.0", "ledger": "l.md", "gates": [g],
               "summary": {"total": 1, "accept": int(g["verdict"] == "accept"), "revise": int(g["verdict"] == "revise"), "demote_to_manual": 0}},
              open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return p


def vc(v, l):
    r = subprocess.run([sys.executable, os.path.join(tree, "scripts/gate_check.py"), "--verdict-check", v, l], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


rel = ledger("rel", "RELEASE_PROCEDURE: eject_findings 로 entries 를 .archive 로 옮기고 버전을 올린 뒤 --reverify\n")
old = ledger("old", "")
got = {"rel-missing": vc(verdict("a"), rel), "rel-na": vc(verdict("b", post_procedure="n/a"), rel),
       "rel-holds": vc(verdict("c", post_procedure="holds"), rel),
       "rel-breaks-accept": vc(verdict("d", post_procedure="breaks"), rel),
       "rel-breaks-revise": vc(verdict("e", post_procedure="breaks", verdict="revise", suggestion="x"), rel),
       "old-missing": vc(verdict("f"), old)}
want = {"rel-missing": 1, "rel-na": 1, "rel-holds": 0, "rel-breaks-accept": 1, "rel-breaks-revise": 0, "old-missing": 0}
rc = {k: (0 if v[0] == 0 else 1) for k, v in got.items()}
c_ok = rc == want and "post_procedure" in got["rel-missing"][1] and "accept" in got["rel-breaks-accept"][1]
ok = s_ok and p_ok and c_ok
print(("PASS  " if ok else "FAIL  ") + "f390-post-procedure-axis — " + ("스키마 · 프롬프트 · 사후 대조 6조합" if ok else
      f"스키마 {s_ok} · 프롬프트 {p_ok} · 대조 {rc} (기대 {want})"))
sys.exit(0 if ok else 1)
PY
rc=$?
echo "VERIFY-GATES-AXES cells=1 FAIL=$rc"
exit "$rc"
