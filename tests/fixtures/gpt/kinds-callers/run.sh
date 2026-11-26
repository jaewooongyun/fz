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
#   pipeline-chain-declared  /fz 파이프라인 체인(modules/pipelines.md `| 체인 | fz-gpt <kind> |`)도 배선이다. 사본에 심으면 FAIL:
#                         ① §16 체인을 비격리 plan 으로 되돌림 — plan 의 callers 가 §16 을 들지 않는다
#                         ② independent-plan callers 에서 §16 표지를 뺌 ③ plan callers 에 §16 표지를 다시 넣음 — 그 절 체인은 plan 을 부르지 않는다
#   challenger-roundtrip  두 칸(compiler_verifiable · ruleSource)을 issues · challenges 에 담은 응답이 통과하고
#                         값이 그대로 남는다 · null 도 통과 · ruleSource 'bogus' 는 거부(exit 1)
#   peer-independent-gate fz-peer-review Tier 경로의 정문 kind peer-independent-review(F-646) — 실제 정문 · 런처를 가짜 CLI(../_shim)로 돌린다.
#                         Tier 0 ~ 3 마다 유효 폴더 → exit 0 · CLI 1회 / 슬롯 부재 → 10 · CLI 0회. Tier 1 에서 결속 불일치(다른 리뷰의 diff ·
#                         이전 Tier 폴더 · tier.txt 없음) · 검사기 실패(tools.md 없음 → 10 · 표를 못 읽는 사본 → 11) · 폴더 없음 → CLI 0회.
#                         유효 run 은 근거 폴더를 런처 --deny 로 받는다(격리 config 의 deny 줄) · 통과 표식 파일을 남기지 않는다
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

# ── pipeline-chain-declared ─────────────────────────────────────────
PLAN_PARALLEL = "/fz plan-parallel (modules/pipelines.md §16)"
CHAIN_ISO, CHAIN_PLAIN = "| 체인 | fz-gpt independent-plan |", "| 체인 | fz-gpt plan |"


def seeded(edit_pipe=False, edit_reg=None):
    """사본 하나에 결함 하나를 심고 `callers` 를 돌린다 → (rc, 출력) · 심을 자리가 없으면 (None, 사유)."""
    d = sandbox()
    try:
        pipe = os.path.join(d, "modules", "pipelines.md")
        reg_p = os.path.join(d, "scripts", "gpt-kinds.json")
        if edit_pipe:
            text = open(pipe, encoding="utf-8").read()
            if text.count(CHAIN_ISO) != 1:
                return None, f"modules/pipelines.md has {text.count(CHAIN_ISO)} '{CHAIN_ISO}' rows (seed target missing)"
            open(pipe, "w", encoding="utf-8").write(text.replace(CHAIN_ISO, CHAIN_PLAIN))
        if edit_reg:
            reg = json.load(open(reg_p, encoding="utf-8"))
            why = edit_reg(reg["kinds"])
            if why:
                return None, why
            json.dump(reg, open(reg_p, "w", encoding="utf-8"), ensure_ascii=False)
        return callers(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def drop_ip_label(kinds):
    c = kinds.get("independent-plan", {}).get("callers") or []
    if PLAN_PARALLEL not in c:
        return f"independent-plan callers have no '{PLAN_PARALLEL}' (seed target missing)"
    kinds["independent-plan"]["callers"] = [x for x in c if x != PLAN_PARALLEL]


def add_plan_label(kinds):
    if "plan" not in kinds or PLAN_PARALLEL in (kinds["plan"].get("callers") or []):
        return f"registry has no kind 'plan', or its callers already carry '{PLAN_PARALLEL}' (seed target missing)"
    kinds["plan"]["callers"] = list(kinds["plan"].get("callers") or []) + [PLAN_PARALLEL]


problems = []
for name, kw, want in (("chain back to plan", {"edit_pipe": True}, "kind plan: modules/pipelines.md §16 chains it"),
                       ("independent-plan label dropped", {"edit_reg": drop_ip_label}, "kind independent-plan: modules/pipelines.md §16 chains it"),
                       ("plan label put back", {"edit_reg": add_plan_label}, f"kind plan: declared caller '{PLAN_PARALLEL}' cites modules/pipelines.md §16")):
    rc, out = seeded(**kw)
    if rc is None:
        problems.append(f"{name}: {out}")
    elif rc == 0 or want not in out:
        problems.append(f"{name}: not caught (rc={rc})")
case("pipeline-chain-declared", not problems, "; ".join(problems))

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

# ── peer-independent-gate (F-646) ──────────────────────────────────
SHIM = os.path.join(ROOT, "tests", "fixtures", "gpt", "_shim")
SAMPLE = os.path.join(ROOT, "tests", "fixtures", "gpt", "independent-arm", "sample-review-ok.json")
TIER_SLOTS = {0: ["requirements", "old-new-pairs", "base-behavior"], 1: ["requirements", "old-new-pairs", "base-behavior", "base-patterns"]}
TIER_SLOTS[2] = TIER_SLOTS[1] + ["producer-consumer", "convention-samples", "open-observations"]   # F-105
TIER_SLOTS[3] = TIER_SLOTS[2] + ["caller-analysis", "semantic-mapping", "deletion-verification"]
TOOLS = "[Serena 미사용 — fixture] · context7 목록✓ · sc 목록✓ · seq 목록✓ · pr-review 목록✓ · 스택 스킬 없음\n"
DA = "diff --git a/src/a.ts b/src/a.ts\n--- a/src/a.ts\n+++ b/src/a.ts\n@@ -1 +1 @@\n-a\n+b\n"
DB = "diff --git a/src/z.ts b/src/z.ts\n--- a/src/z.ts\n+++ b/src/z.ts\n@@ -1 +1 @@\n-y\n+z\n"
T = os.path.realpath(tempfile.mkdtemp(prefix="kinds-callers-pir-"))
H = os.path.join(T, "home")
os.makedirs(os.path.join(H, ".codex"))
open(os.path.join(H, ".codex", "auth.json"), "w").write('{"fake":"auth"}\n')


def evdir(name, tier, slots, diff=DA, tier_txt=True, tools=True):
    d = os.path.join(T, name)
    os.makedirs(os.path.join(d, "evidence"))
    if tier_txt:
        open(os.path.join(d, "tier.txt"), "w").write(f"{tier}\nrationale: fixture\n")   # 실제 기록 꼴(peer-review-tiers.md — 첫 줄 숫자)
    for sl in slots:
        body = "## 호출\n- fixture\n\n## 구현\n해당 없음 — fixture\n" if sl == "caller-analysis" else f"# {sl}\nfixture\n"
        open(os.path.join(d, "requirements.md" if sl == "requirements" else os.path.join("evidence", sl + ".md")), "w").write(body)
    if tools:
        open(os.path.join(d, "evidence", "tools.md"), "w").write(TOOLS)
    json.dump({"kind": "pr", "ref": "pr-1", "sha": "abc1234def5678"}, open(os.path.join(d, "target.json"), "w"))
    open(os.path.join(d, "diff.patch"), "w").write(diff)
    return d


roll = os.path.join(T, "roll.jsonl")
rows = [{"type": "session_meta", "payload": {"id": "x"}},
        {"type": "turn_context", "payload": {"permission_profile": {"type": "managed", "file_system": {"type": "restricted", "entries": [
            {"path": {"type": "path", "path": H}, "access": "deny"}, {"path": {"type": "special", "value": {"kind": "root"}}, "access": "read"}]}}}},
        {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec", "input": "tools.exec_command({cmd:\"cat diff.patch\"})"}}]
open(roll, "w").write("\n".join(json.dumps(r) for r in rows) + "\n")
open(os.path.join(T, "current.patch"), "w").write(DA)


def gate(cell, root, tier, diff, tree=ROOT, stem_of=None):
    """정문 peer-independent-review 한 번 → (exit, CLI 호출 수, stderr, 격리 config 사본 · 없으면 ''). stem_of = 다른 셀의 --out-dir · --run-id 를 다시 쓴다."""
    out = os.path.join(T, "out-" + (stem_of or cell))
    os.makedirs(out, exist_ok=True)
    cap, cfg_copy = os.path.join(T, f"argv-{cell}.json"), os.path.join(T, f"cfg-{cell}.toml")
    wrap = os.path.join(T, f"bin-{cell}")
    os.makedirs(wrap)
    with open(os.path.join(wrap, "codex"), "w") as f:   # 호출 시점의 격리 config 를 사본으로 남기고 shim 으로 넘긴다
        f.write('#!/bin/bash\ncase "${1:-} ${2:-}" in "login status"*|"--version "*) exec "$PIR_SHIM/codex" "$@" ;; esac\n'
                '[ -n "${CODEX_HOME:-}" ] && cp "$CODEX_HOME/config.toml" "$PIR_CFG" 2>/dev/null\nexec "$PIR_SHIM/codex" "$@"\n')
    os.chmod(os.path.join(wrap, "codex"), 0o755)
    env = {k: v for k, v in os.environ.items() if k not in ("CODEX_HOME", "FZ_GPT_CHOICE_DIR", "FZ_GPT_ARTIFACT", "FZ_WORK_DIR", "FZ_CLAUDE_REALS",
                                                            "OPENAI_API_KEY", "CODEX_API_KEY")}
    env.update(PATH=wrap + ":" + SHIM + ":" + os.environ.get("PATH", ""), HOME=H, TMPDIR=os.path.join(T, "tmp"), CLAUDE_CODE_SESSION_ID="kc-pir-no-choice",
               FZ_RUN_STATE=os.path.join(T, "runs"), FZ_TELEMETRY_DIR=os.path.join(T, "tel"), FZ_SHIM_CAPTURE=cap, FZ_SHIM_OUTPUT=open(SAMPLE).read(),
               FZ_SHIM_ROLLOUT=roll, PIR_SHIM=SHIM, PIR_CFG=cfg_copy, PYTHONDONTWRITEBYTECODE="1")
    os.makedirs(env["TMPDIR"], exist_ok=True)
    r = subprocess.run(["bash", os.path.join(tree, "scripts", "gpt-call.sh"), "peer-independent-review", "--evidence-root", root, "--tier", str(tier),
                        "--diff", diff, "--arm", "A", "--run-id", stem_of or cell, "--out-dir", out], env=env, capture_output=True, text=True, timeout=300)
    n = 1 if os.path.isfile(cap) and os.path.getsize(cap) else 0
    return r.returncode, n, r.stderr, (open(cfg_copy, encoding="utf-8").read() if os.path.isfile(cfg_copy) else "")


def proxy_tree():
    """표를 못 읽는 사본 — modules/peer-review-tiers.md 만 § Tier-Adaptive Evidence 머리를 지운 사본, 나머지는 링크(검사기가 UNRUN 2 로 끝난다)."""
    px = os.path.join(T, "proxy")
    os.makedirs(px)
    for name in os.listdir(ROOT):
        if name not in ("scripts", "modules", ".git"):
            os.symlink(os.path.join(ROOT, name), os.path.join(px, name))
    for sub in ("scripts", "modules"):
        os.makedirs(os.path.join(px, sub))
        for name in os.listdir(os.path.join(ROOT, sub)):
            src = os.path.join(ROOT, sub, name)
            if sub == "modules" and name == "peer-review-tiers.md":
                open(os.path.join(px, sub, name), "w", encoding="utf-8").write(open(src, encoding="utf-8").read().replace("## Tier-Adaptive Evidence", "## (fixture)"))
            else:
                os.symlink(src, os.path.join(px, sub, name))
    return px


problems = []
try:
    for tier in (0, 1, 2, 3):
        v = evdir(f"t{tier}-valid", tier, TIER_SLOTS[tier])
        rc, n, err, cfg = gate(f"t{tier}-valid", v, tier, os.path.join(v, "diff.patch"))
        if (rc, n) != (0, 1):
            problems.append(f"Tier {tier} valid: rc={rc} cli={n} {err.strip().splitlines()[-1:] if err.strip() else ''}")
        elif f'"{v}" = "deny"' not in cfg:
            problems.append(f"Tier {tier} valid: evidence folder is not a launcher deny in the isolation config")
        m = evdir(f"t{tier}-slot", tier, TIER_SLOTS[tier][:-1])
        rc, n, err, _ = gate(f"t{tier}-slot", m, tier, os.path.join(m, "diff.patch"))
        if rc != 10 or n != 0 or "evidence slots" not in err:
            problems.append(f"Tier {tier} slot missing: rc={rc} cli={n}")
    # 같은 stem 을 거부되는 사전 검사로 다시 부르면 옛 성공 감사가 실패 감사로 덮인다 — 병합기가 옛 결과를 받지 않게(GPT check 8.5 P2)
    a1 = os.path.join(T, "out-t1-valid", "A-t1-valid.audit.json")
    before = json.load(open(a1)).get("exit") if os.path.isfile(a1) else None
    m1 = evdir("t1-reslot", 1, TIER_SLOTS[1][:-1])
    rc, n, _, _ = gate("t1-reslot", m1, 1, os.path.join(m1, "diff.patch"), stem_of="t1-valid")
    after = json.load(open(a1)).get("exit") if os.path.isfile(a1) else None
    if (before, rc, n, after) != (0, 10, 0, 10):
        problems.append(f"refused re-run of a valid stem: audit exit {before} -> {after} · rc={rc} cli={n} (want 0 -> 10 · 10 · 0)")
    o = evdir("other-review", 1, TIER_SLOTS[1], diff=DB)
    p2 = evdir("prior-tier", 2, TIER_SLOTS[2])
    nt = evdir("no-tier-file", 1, TIER_SLOTS[1], tier_txt=False)
    tm = evdir("tools-missing", 1, TIER_SLOTS[1], tools=False)
    for cell, root, tier, diff, want_rc, want_msg in (
            ("other-review", o, 1, os.path.join(T, "current.patch"), 10, "belongs to another review"),
            ("prior-tier", p2, 1, os.path.join(p2, "diff.patch"), 10, "another Tier"),
            ("no-tier-file", nt, 1, os.path.join(nt, "diff.patch"), 10, "no readable Tier"),
            ("tools-missing", tm, 1, os.path.join(tm, "diff.patch"), 10, "evidence slots"),
            ("no-dir", os.path.join(T, "no-such-dir"), 1, os.path.join(T, "current.patch"), 10, "not a folder"),
            ("checker-unrun", evdir("checker-unrun", 1, TIER_SLOTS[1]), 1, None, 11, "could not judge")):
        diff = diff or os.path.join(T, "checker-unrun", "diff.patch")
        rc, n, err, _ = gate(cell, root, tier, diff, tree=proxy_tree() if cell == "checker-unrun" else ROOT)
        if rc != want_rc or n != 0 or want_msg not in err:
            problems.append(f"{cell}: rc={rc}(want {want_rc}) cli={n} msg={'yes' if want_msg in err else 'no'}")
    marks = [os.path.join(dp, f) for dp, _, fs in os.walk(T) for f in fs if "slots-ok" in f]
    if marks:
        problems.append(f"a pass marker file was written: {marks[:2]}")
finally:
    shutil.rmtree(T, ignore_errors=True)
case("peer-independent-gate", not problems, "; ".join(problems))

print(f"kinds-callers: {'PASS' if not fails else 'FAIL'}")
sys.exit(0 if not fails else 1)
PY
