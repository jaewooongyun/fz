#!/usr/bin/env python3
# lint:no-root-anchor — 입력 · 출력 파일을 인자로 받는 변환기라 플러그인 루트를 해석하지 않는다
"""review-live counter 대 GPT DA 측정 arm 어댑터 (B11 · M2).

review-live 를 `counter: 'off'` 로 돌리면 Stage 3(opus counter)을 빼고 `counterSkipped: 'arm'` 을 돌려준다.
그 run 의 DA 는 GPT 가 맡는다 — 이 스크립트가 양쪽 모양을 잇는다.

  1. prepare  Workflow 반환(workflow-result.json)에서 counter 가 보던 입력(Stage 1·2 findings · okAreas)을 고정 파일로 남기고
              GPT DA 프롬프트를 만든다. findings 는 병합 표지(finalSeverity · crossVerdict · crossNote · counterVerdict ·
              counterNote)를 걷어 counter 가 받던 모양 그대로 둔다
  2. (Lead)   정문으로 기존 DA kind 를 부른다:
              gpt-call.sh peer-da --cd {WORK_DIR} --out {WORK_DIR}/gpt-da-result.json --prompt-file {prompt}
  3. convert  GPT 응답(gpt_peer_review_schema)을 review-live CounterSchema(challenges[target · verdict · note] ·
              missedFindings)로 옮긴다. action 대응: agree · supplement → uphold / challenge · reverse → refute
              (원래 action 은 challenge 의 gptAction 에 남긴다 — 병합에는 쓰지 않는다)
  4. merge    review-live.js 병합과 같은 규칙으로 counter 판정을 findings 에 반영한다 — 두 arm 의 병합 규칙이 같아야
              비교가 된다(tests/workflows/review-live-counter-arm.js 가 같은 counter 입력에서 두 경로의 결과를 대조한다)

⛔ GPT 실패는 arm 무효다 — 통신 실패 · GPT 미사용(exit 18) · 결과 파일 없음 · JSON 아님 · 스키마 위반 · agent_status failed 는
   '반론 0건' 이 아니다. convert 가 armValid:false 로 적고 exit 1 · merge 는 무효 counter 를 거부한다. 그 run 은 측정에서 뺀다.

usage:
  counter_adapter.py prepare --result R.json --out-dir DIR        → DIR/counter-input.json · DIR/counter-prompt.md
  counter_adapter.py convert --gpt-result G.json --gpt-exit N --out C.json
  counter_adapter.py merge --result R.json --counter C.json --out M.json
  counter_adapter.py --self-test
exit: 0 정상 · 1 arm 무효(GPT 실패 · 무효 counter) · 2 입력 · 사용 오류
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

ANNOTATIONS = ("finalSeverity", "crossVerdict", "crossNote", "counterVerdict", "counterNote")
VERDICT = {"agree": "uphold", "supplement": "uphold", "challenge": "refute", "reverse": "refute"}
SEVERITIES = ("critical", "major", "minor", "suggestion")
GPT_OFF = 18   # scripts/gpt-call.sh — GPT 미사용은 실패가 아니지만 이 arm 에는 DA 가 없었다

PROMPT = """[역할] 반론자 — Devil's Advocate (fz-review counter 대 GPT DA 측정 arm)
[입력] findings 와 okAreas 는 아래 JSON 이다(고정 파일 {input_path} 와 같다). finding 의 id 를 그대로 target_issue_id 로 쓴다.
[findings] {findings}
[okAreas(정상 판정)] {ok_areas}
[목표] (1) 각 finding을 실측 재검증 — 과장/오독이면 challenge(뒤집히면 reverse) + 인용, 맞으면 agree(보탤 것이 있으면 supplement). (2) okAreas에 "정말 OK인가?" 반례 탐색 — 반례 발견 시 issues 로. 라인 인용 오류를 특히 의심.
"""


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def dump(obj, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def counter_input(result):
    """Workflow 반환 → counter 가 받던 입력 — Stage 1·2 findings(병합 표지 제거) · okAreas."""
    if not isinstance(result, dict) or result.get("mode") != "workflow" or not isinstance(result.get("findings"), list):
        raise ValueError("workflow-result 가 mode:'workflow' 반환이 아니다")
    if result.get("counterSkipped") != "arm":
        raise ValueError("counter 를 돌린 run 이다 — counterSkipped:'arm' 인 반환만 받는다")
    findings = [{k: v for k, v in f.items() if k not in ANNOTATIONS} for f in result["findings"]]
    return {"findings": findings, "okAreas": list(result.get("okAreas") or [])}


def render_prompt(inp, input_path):
    compact = lambda x: json.dumps(x, ensure_ascii=False, separators=(",", ":"))
    return PROMPT.format(input_path=input_path, findings=compact(inp["findings"]), ok_areas=compact(inp["okAreas"]))


def invalid(reason):
    return {"armValid": False, "reason": reason, "counter": None}


def convert(gpt, gpt_exit):
    """GPT DA 응답 → {armValid, reason, counter: CounterSchema | None}. 무효 사유는 하나만 적는다."""
    if gpt_exit == GPT_OFF:
        return invalid("gpt-off — GPT 미사용(exit 18): 이 run 에는 DA 가 없었다")
    if gpt_exit != 0:
        return invalid(f"gpt-call-failed — 정문 exit {gpt_exit}")
    if not isinstance(gpt, dict):
        return invalid("gpt-result-not-object")
    if gpt.get("schemaVersion") != "1.1":
        return invalid(f"schema — schemaVersion {gpt.get('schemaVersion')!r} != '1.1'")
    if gpt.get("agent_status") == "failed":
        return invalid(f"agent-failed — {gpt.get('status_reason') or '사유 없음'}")
    chs, issues = gpt.get("challenges"), gpt.get("issues")
    if not isinstance(chs, list) or not isinstance(issues, list):
        return invalid("schema — challenges · issues 배열이 없다")
    challenges = []
    for c in chs:
        if not isinstance(c, dict) or not c.get("target_issue_id") or c.get("action") not in VERDICT:
            return invalid(f"schema — challenge 모양 위반: {json.dumps(c, ensure_ascii=False)[:80]}")
        challenges.append({"target": c["target_issue_id"], "verdict": VERDICT[c["action"]],
                           "note": str(c.get("reason") or ""), "gptAction": c["action"]})
    missed = []
    for i in issues:
        if not isinstance(i, dict) or not i.get("id") or i.get("severity") not in SEVERITIES or not i.get("description"):
            return invalid(f"schema — issue 모양 위반: {json.dumps(i, ensure_ascii=False)[:80]}")
        desc, impact = str(i["description"]), i.get("impact")
        missed.append({
            "id": i["id"], "severity": i["severity"], "category": i.get("perspective") or "gpt-da",
            "title": desc[:80], "detail": desc + (f" — {impact}" if impact else ""),
            "file": i.get("file") or "", "line_range": i.get("line_range") or "",
            "evidence": i.get("evidence_trace") or f"{i.get('file') or '?'}:{i.get('line_range') or '?'}",
        })
    return {"armValid": True, "reason": None, "counter": {"challenges": challenges, "missedFindings": missed}}


def merge(result, conv):
    """review-live.js 병합 규칙 — counter 판정 반영 · C: missedFindings 추가 · okArea 도전 · distribution 재계산."""
    if not isinstance(conv, dict) or conv.get("armValid") is not True or not isinstance(conv.get("counter"), dict):
        raise PermissionError(f"arm 무효 counter — 병합하지 않는다: {conv.get('reason') if isinstance(conv, dict) else conv!r}")
    counter = conv["counter"]
    by_target = {c["target"]: c for c in counter["challenges"]}
    findings = []
    for f in result["findings"]:
        g = {k: v for k, v in f.items() if k not in ("counterVerdict", "counterNote")}
        ctr = by_target.get(f["id"])
        g["counterVerdict"] = ctr["verdict"] if ctr else "unchallenged"
        if ctr:
            g["counterNote"] = ctr["note"]
        findings.append(g)
    findings += [dict(m, id=f"C:{m['id']}", finalSeverity=m["severity"], crossVerdict="counter_found", counterVerdict="uphold")
                 for m in counter["missedFindings"]]
    ids = {f["id"] for f in findings}
    out = dict(result, findings=findings,
               okAreaChallenges=[{k: c[k] for k in ("target", "verdict", "note")} for c in counter["challenges"] if c["target"] not in ids])
    dist = dict(result.get("distribution") or {})
    for s in SEVERITIES:
        dist[s] = sum(1 for f in findings if f.get("finalSeverity") == s)
    dist["fpFlagged"] = sum(1 for f in findings if f.get("crossVerdict") == "false_positive" or f.get("counterVerdict") == "refute")
    out["distribution"] = dist
    out["counterSource"] = "gpt-da"
    return out


def arg(argv, name):
    if name in argv and argv.index(name) + 1 < len(argv):
        return argv[argv.index(name) + 1]
    return None


def main(argv):
    if argv[:1] == ["--self-test"]:
        return self_test()
    cmd = argv[0] if argv else None
    try:
        if cmd == "prepare" and arg(argv, "--result") and arg(argv, "--out-dir"):
            d = arg(argv, "--out-dir")
            os.makedirs(d, exist_ok=True)
            inp = counter_input(load(arg(argv, "--result")))
            ip = os.path.join(d, "counter-input.json")
            dump(inp, ip)
            with open(os.path.join(d, "counter-prompt.md"), "w", encoding="utf-8") as fh:
                fh.write(render_prompt(inp, ip))
            print(f"counter_adapter prepare: findings={len(inp['findings'])} okAreas={len(inp['okAreas'])} → {d}")
            return 0
        if cmd == "convert" and arg(argv, "--out") and arg(argv, "--gpt-exit") is not None:
            code, path = int(arg(argv, "--gpt-exit")), arg(argv, "--gpt-result")
            try:
                gpt = load(path) if path and os.path.isfile(path) and os.path.getsize(path) else None
                conv = convert(gpt, code) if (gpt is not None or code != 0) else invalid("gpt-result-missing — 결과 파일 없음 · 빈 파일")
            except json.JSONDecodeError as e:
                conv = invalid(f"gpt-result-not-json — {e.msg}")
            dump(conv, arg(argv, "--out"))
            print(f"counter_adapter convert: armValid={conv['armValid']}" + ("" if conv["armValid"] else f" reason={conv['reason']}"))
            return 0 if conv["armValid"] else 1
        if cmd == "merge" and arg(argv, "--result") and arg(argv, "--counter") and arg(argv, "--out"):
            try:
                merged = merge(load(arg(argv, "--result")), load(arg(argv, "--counter")))
            except PermissionError as e:
                print(f"counter_adapter merge: {e} — 이 run 은 측정에서 뺀다")
                return 1
            dump(merged, arg(argv, "--out"))
            print(f"counter_adapter merge: findings={len(merged['findings'])} okAreaChallenges={len(merged['okAreaChallenges'])}")
            return 0
    except (OSError, ValueError, KeyError) as e:
        print(f"counter_adapter: 입력 오류 — {e}", file=sys.stderr)
        return 2
    print(__doc__.strip().split("usage:")[1].split("exit:")[0].rstrip(), file=sys.stderr)
    return 2


def self_test():
    fails, ran = [], []

    def case(name, cond, got=""):
        ran.append(name)
        print(f"{name}: {'PASS' if cond else 'FAIL'}" + ("" if cond else f" {got}"))
        if not cond:
            fails.append(name)

    off_result = {
        "mode": "workflow", "counterSkipped": "arm", "okAreas": ["캐시 무효화 OK"],
        "findings": [
            {"id": "A:A1", "severity": "major", "category": "c", "title": "t", "detail": "d", "evidence": "e",
             "finalSeverity": "major", "crossVerdict": "agree", "counterVerdict": "unchallenged"},
            {"id": "Q:Q1", "severity": "minor", "category": "c", "title": "t", "detail": "d", "evidence": "e",
             "finalSeverity": "minor", "crossVerdict": "unreviewed", "counterVerdict": "unchallenged"},
        ],
        "distribution": {"critical": 0, "major": 1, "minor": 1, "suggestion": 0, "fpFlagged": 0, "structuralAxes": False},
        "metrics": {"agentCalls": 4, "nullCount": 0, "fallbackCount": 0, "stagesCompleted": 2, "stagesExpected": 2},
    }
    inp = counter_input(off_result)
    case("prepare-strips-annotations", [f["id"] for f in inp["findings"]] == ["A:A1", "Q:Q1"]
         and not any(k in f for f in inp["findings"] for k in ANNOTATIONS) and inp["okAreas"] == ["캐시 무효화 OK"], json.dumps(inp)[:120])
    prompt = render_prompt(inp, "/x/counter-input.json")
    case("prompt-carries-ids", all(i in prompt for i in ("A:A1", "Q:Q1", "캐시 무효화 OK", "target_issue_id")), prompt[:80])
    try:
        counter_input(dict(off_result, counterSkipped=None))
        case("prepare-rejects-counter-run", False, "counter 를 돌린 run 을 받았다")
    except ValueError:
        case("prepare-rejects-counter-run", True)

    gpt = {"schemaVersion": "1.1", "agent": "gpt-challenger", "agent_status": "ok", "status_reason": "정상",
           "challenges": [{"target_issue_id": "A:A1", "action": "reverse", "reason": "라인 오독", "compiler_verifiable": None, "ruleSource": None},
                          {"target_issue_id": "Q:Q1", "action": "supplement", "reason": "근거 보강", "compiler_verifiable": None, "ruleSource": None},
                          {"target_issue_id": "캐시 무효화 OK", "action": "challenge", "reason": "반례 있음", "compiler_verifiable": None, "ruleSource": None}],
           "issues": [{"id": "GPT-001", "severity": "major", "perspective": "concurrency_safety", "file": "F.swift", "line_range": "10-12",
                       "description": "경합", "impact": "크래시", "evidence_trace": "F.swift:10"}],
           "strengths": [], "overall_assessment": "o"}
    conv = convert(gpt, 0)
    verdicts = [(c["target"], c["verdict"], c["gptAction"]) for c in (conv["counter"] or {}).get("challenges", [])] if conv["armValid"] else []
    case("action-to-verdict", verdicts == [("A:A1", "refute", "reverse"), ("Q:Q1", "uphold", "supplement"), ("캐시 무효화 OK", "refute", "challenge")], str(verdicts))
    m = conv["counter"]["missedFindings"][0] if conv["armValid"] else {}
    case("issue-to-missed", m.get("id") == "GPT-001" and m.get("severity") == "major" and m.get("category") == "concurrency_safety"
         and m.get("evidence") == "F.swift:10" and "크래시" in m.get("detail", ""), json.dumps(m, ensure_ascii=False))

    merged = merge(off_result, conv)
    byid = {f["id"]: f for f in merged["findings"]}
    case("round-trip-ids", list(byid) == ["A:A1", "Q:Q1", "C:GPT-001"]
         and byid["A:A1"]["counterVerdict"] == "refute" and byid["A:A1"]["counterNote"] == "라인 오독"
         and byid["Q:Q1"]["counterVerdict"] == "uphold" and byid["C:GPT-001"]["crossVerdict"] == "counter_found", json.dumps(list(byid)))
    case("okarea-challenge", merged["okAreaChallenges"] == [{"target": "캐시 무효화 OK", "verdict": "refute", "note": "반례 있음"}], json.dumps(merged["okAreaChallenges"], ensure_ascii=False))
    d = merged["distribution"]
    case("distribution-recount", (d["major"], d["minor"], d["fpFlagged"], d["structuralAxes"]) == (2, 1, 1, False), json.dumps(d))

    bad = {
        "gpt-off-18": (gpt, 18), "call-failed": (gpt, 1), "not-object": ([], 0),
        "schema-version": (dict(gpt, schemaVersion="1.0"), 0), "agent-failed": (dict(gpt, agent_status="failed"), 0),
        "no-challenges": ({k: v for k, v in gpt.items() if k != "challenges"}, 0),
        "bad-action": (dict(gpt, challenges=[{"target_issue_id": "A:A1", "action": "maybe", "reason": "r"}]), 0),
        "bad-issue": (dict(gpt, issues=[{"id": "X", "severity": "huge", "description": "d"}]), 0),
    }
    leaked = [k for k, (g, code) in bad.items() if convert(g, code)["armValid"] is not False]
    case("gpt-failure-invalidates-arm", not leaked, f"armValid true for {leaked}")
    try:
        merge(off_result, convert(gpt, 18))
        case("merge-refuses-invalid", False, "무효 counter 를 병합했다")
    except PermissionError:
        case("merge-refuses-invalid", True)

    with tempfile.TemporaryDirectory() as t:   # CLI 왕복 — 빈 결과 파일 · 비 JSON 은 exit 1 + armValid false 파일
        empty, junk, out = os.path.join(t, "e.json"), os.path.join(t, "j.json"), os.path.join(t, "c.json")
        open(empty, "w").close()
        with open(junk, "w") as fh:
            fh.write("not json")
        rc = [main(["convert", "--gpt-result", p, "--gpt-exit", "0", "--out", out]) for p in (empty, junk, os.path.join(t, "none.json"))]
        case("cli-missing-or-junk", rc == [1, 1, 1] and load(out)["armValid"] is False, str(rc))

    print(f"self-test {len(ran) - len(fails)}/{len(ran)} passed")
    print(f"counter_adapter self-test: {'PASS' if not fails else 'FAIL'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
