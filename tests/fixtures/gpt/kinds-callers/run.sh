#!/bin/bash
# GPT kind 호출자 대조 · challenger 두 칸 왕복 (F-467 · F-466).
#
# ⛔ 실제 `scripts/gpt_kinds.py` · `scripts/gpt-kinds.json` · `schemas/gpt_peer_review_schema.json` ·
#    `scripts/validate-gpt-output.py` 로 돈다. 심은 결함은 임시 사본에만 넣는다.
# 셀:
#   table-equals-grep     ① 이 트리에서 `gpt_kinds.py callers` 가 OK(선언 호출자 = 실제 배선)
#                         ② 사본에 배선 없는 선언(final ← '/fz-pr 전')을 심으면 FAIL — unwired claim
#                         ③ 사본의 fz-commit 에 선언 없는 실제 호출(gpt-call.sh peer-da)을 심으면 FAIL
#                         ④ '명시 호출' 줄은 배선으로 세지 않는다(같은 호출을 그 표시와 함께 심으면 OK)
#   challenger-roundtrip  두 칸(compiler_verifiable · ruleSource)을 issues · challenges 에 담은 응답이 통과하고
#                         값이 그대로 남는다 · null 도 통과 · ruleSource 'bogus' 는 거부(exit 1)
# 출력: 셀마다 `<셀>: PASS|FAIL <이유>` · 끝에 `kinds-callers: PASS|FAIL`
# exit: 0 전건 통과 · 1 단언 실패 · 2 준비 실패(python3 · 파일 부재)
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." 2>/dev/null && pwd)"
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 2; }
for f in scripts/gpt_kinds.py scripts/gpt-kinds.json schemas/gpt_peer_review_schema.json scripts/validate-gpt-output.py; do
  [ -f "$ROOT/$f" ] || { echo "SETUP $f 없음: $ROOT"; exit 2; }
done

PYTHONDONTWRITEBYTECODE=1 python3 -B - "$ROOT" <<'PY'
import copy, json, os, shutil, subprocess, sys, tempfile
ROOT = sys.argv[1]
fails = []


def case(name, ok, why=""):
    print(f"{name}: {'PASS' if ok else 'FAIL'}" + ("" if ok else f" {why}"))
    if not ok:
        fails.append(name)


def callers(root):
    r = subprocess.run([sys.executable, os.path.join(root, "scripts", "gpt_kinds.py"), "callers", "--root", root],
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def sandbox():
    d = tempfile.mkdtemp(prefix="kinds-callers-")
    for sub in ("scripts", "skills", "modules"):
        shutil.copytree(os.path.join(ROOT, sub), os.path.join(d, sub))
    return d


# ── table-equals-grep ───────────────────────────────────────────────
problems = []
rc, out = callers(ROOT)
if rc != 0 or "GPT-KINDS-CALLERS OK" not in out:
    problems.append(f"tree: rc={rc} {out.strip().splitlines()[-1] if out.strip() else ''}")
d = sandbox()
try:
    reg_p = os.path.join(d, "scripts", "gpt-kinds.json")
    reg = json.load(open(reg_p, encoding="utf-8"))
    if "final" not in reg.get("kinds", {}):
        problems.append("registry has no kind 'final' (seed target missing)")
    else:
        reg["kinds"]["final"]["callers"] = ["/fz-pr 전"]
        json.dump(reg, open(reg_p, "w", encoding="utf-8"), ensure_ascii=False)
        rc, out = callers(d)
        if rc == 0 or "unwired claim" not in out:
            problems.append(f"seeded unwired declaration not caught: rc={rc}")
finally:
    shutil.rmtree(d, ignore_errors=True)
d = sandbox()
try:
    skill = os.path.join(d, "skills", "fz-commit", "SKILL.md")
    base = open(skill, encoding="utf-8").read()
    open(skill, "w", encoding="utf-8").write(base + '\n"${FZ_PLUGIN_ROOT}/scripts/gpt-call.sh" peer-da --cd x --out y --prompt-file z\n')
    rc, out = callers(d)
    if rc == 0 or "skills/fz-commit calls it" not in out:
        problems.append(f"seeded undeclared call not caught: rc={rc}")
    open(skill, "w", encoding="utf-8").write(base + '\n수동 점검은 명시 호출: "${FZ_PLUGIN_ROOT}/scripts/gpt-call.sh" peer-da\n')
    rc, out = callers(d)
    if rc != 0:
        problems.append(f"'명시 호출' line was counted as wiring: rc={rc}")
finally:
    shutil.rmtree(d, ignore_errors=True)
case("table-equals-grep", not problems, "; ".join(problems))

# ── challenger-roundtrip ────────────────────────────────────────────
VAL = os.path.join(ROOT, "scripts", "validate-gpt-output.py")
PEER = os.path.join(ROOT, "schemas", "gpt_peer_review_schema.json")
ISSUE = {
    "id": "ARCH-001", "perspective": "architecture", "file": "Feature.swift", "line_range": "10-20",
    "severity": "suggestion", "confidence": 70, "origin": "regression",
    "description": "fixture 이슈", "impact": "fixture 영향", "suggestion": "fixture 제안",
    "alternatives": [{"label": "A", "description": "그대로", "pros": ["변경 없음"], "cons": ["유지"]}],
    "recommended": "A", "evidence_trace": "Feature.swift:10", "scope_disposition": "scope-in",
    "symptom_screen": None, "symptom_reach": None,
    "compiler_verifiable": True, "ruleSource": "plugin-default",
}
CH = {"target_issue_id": "ARCH-001", "action": "reverse", "reason": "컴파일러가 판정한다",
      "compiler_verifiable": True, "ruleSource": "project"}
BASE = {"schemaVersion": "1.1", "agent": "gpt-challenger", "agent_status": "ok", "status_reason": "정상",
        "issues": [ISSUE], "challenges": [CH], "strengths": ["fixture"], "overall_assessment": "good"}


def validate(doc):
    fd, p = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    r = subprocess.run([sys.executable, VAL, p, PEER], capture_output=True, text=True)
    back = json.load(open(p, encoding="utf-8"))
    os.unlink(p)
    return r.returncode, back, (r.stdout + r.stderr).strip()


problems = []
rc, back, msg = validate(BASE)
if rc != 0:
    problems.append(f"full response rejected rc={rc}: {msg[-160:]}")
elif (back["issues"][0].get("compiler_verifiable") is not True or back["issues"][0].get("ruleSource") != "plugin-default"
      or back["challenges"][0].get("compiler_verifiable") is not True or back["challenges"][0].get("ruleSource") != "project"):
    problems.append("field values not preserved")
nulls = copy.deepcopy(BASE)
for item in nulls["issues"] + nulls["challenges"]:
    item["compiler_verifiable"], item["ruleSource"] = None, None
rc, _, msg = validate(nulls)
if rc != 0:
    problems.append(f"null fields rejected rc={rc}: {msg[-160:]}")
bad = copy.deepcopy(BASE)
bad["issues"][0]["ruleSource"] = "bogus"
rc, _, msg = validate(bad)
if rc != 1:
    problems.append(f"ruleSource 'bogus' not rejected as a contract violation (rc={rc})")
case("challenger-roundtrip", not problems, "; ".join(problems))

print(f"kinds-callers: {'PASS' if not fails else 'FAIL'}")
sys.exit(0 if not fails else 1)
PY
