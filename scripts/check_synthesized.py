#!/usr/bin/env python3
"""check_synthesized.py — peer-review Synthesize 산출물(synthesized-issues.json)의 계약 검사 + 공용 정규화 (F-530 · 결정 2).

왜: 저장된 synthesized-issues.json 36개 · 이슈 149건에 키 조합이 82가지였다 — 생산자가 둘(Lead 가 쓰는 `issues[]` ·
결정론 병합 `review_merge.py` 의 `candidates[]`)이고 같은 뜻을 다른 이름으로 적었다(`found_by` · `source` · `rawSeverity` …).
소비자(check_symptom_anchor · Curate 검사기)마다 따로 읽으면 한쪽 이름을 놓친다 — 이 모듈의 `normalize()` 를 같이 쓴다.

정규화(생산자별 변환표):
  Lead `issues[]`             id · foundBy(found_by) · severity 원본 · 최종 · file · line_range(line) · evidence · origin · symptom_*
  병합 `candidates[]`          foundBy = 있으면 그대로 · 없으면 [source] + lens · evidence 문자열 → [문자열]
  severity 는 **두 칸**이다     원본 `severity_raw`(별칭 severity · rawSeverity) · 최종 `severity_final`(별칭 finalSeverity · effectiveSeverity)
                              충돌은 **같은 칸의 별칭끼리만** 본다 — 원본 ≠ 최종은 정상(병합기의 pre-existing 강등이 일부러 만든다)
                              단 원본 칸(severity_raw · rawSeverity)을 따로 적고 최종 칸이 없으면 `severity` 는 최종이다(저장본 실측 — 5211 · 5235)
                              판정 값 = 최종이 있으면 최종 · 없으면 원본(check_symptom_anchor 의 기존 규칙과 같다)
0건 완결 증거(그때만 0건이 통과다): 병합본 `inputs.claude == inputs.gpt == 0` · `inputs.gptUnavailable == null`(GPT 가 돌아 끝났다) ·
  `inputs.evidenceChecked == true` · `summary.candidatesIn == summary.candidatesOut == 0`. GPT 실패 · 시간 초과 · 끔 · Tier 0 은
  수치가 같아도 0건 완결이 아니다(UNRUN). 양수 후보를 전부 뺀 경우는 0건이 아니라 후보별 처분(Curate excluded) 대상이다.

사용: check_synthesized.py FILE [--normalize OUT]   (원본은 고치지 않는다 — OUT 에 정규형을 쓴다)
exit: 0 PASS · 1 VIOLATION(별칭 충돌 · id 없음 · 모르는 severity) · 2 UNRUN(파일 · 모양 · 증거 없는 0건 — ⛔ 통과 아님)
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import tempfile

OK, VIOLATION, UNRUN = 0, 1, 2
# ⛔ N6 루트 앵커 — lint_contracts ANCHOR_LINES 허용 형태와 정확히 일치
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW = ("severity_raw", "severity", "rawSeverity")
FINAL = ("severity_final", "finalSeverity", "effectiveSeverity")
SEVERITIES = ("critical", "major", "minor", "suggestion", "excluded")


def _one(item: dict, keys):
    """같은 칸 별칭에서 값 하나 — (값 | None, 충돌 설명 | None)."""
    vals = {k: str(item[k]).strip().lower() for k in keys if isinstance(item.get(k), str) and item[k].strip()}
    if len(set(vals.values())) > 1:
        return None, " ≠ ".join(f"{k}={v}" for k, v in vals.items())
    return (next(iter(vals.values())) if vals else None), None


def normalize(data):
    """두 생산자 모양 → (shape, items, problems). shape 를 모르면 (None, None, [사유]).

    items 의 키: id · foundBy · severity_raw · severity_final · severity(판정 값) · file · line_range · evidence · origin ·
    symptom_screen · symptom_reach · title. problems 는 항목별 위반 문자열(별칭 충돌 · id 없음 · 모르는 severity).
    """
    if isinstance(data, dict) and isinstance(data.get("issues"), list):
        shape, raw_items = "lead", data["issues"]
    elif isinstance(data, dict) and isinstance(data.get("candidates"), list):
        shape, raw_items = "merge", data["candidates"]
    elif isinstance(data, list):
        shape, raw_items = "lead", data
    else:
        return None, None, ["issues[] · candidates[] 둘 다 없다"]
    items, problems = [], []
    for i, it in enumerate(raw_items):
        if not isinstance(it, dict):
            problems.append(f"[{i}] 객체가 아니다")
            continue
        iid = it.get("id")
        if iid in (None, ""):
            problems.append(f"[{i}] id 가 없다")
            iid = f"[{i}]"
        # `severity` 는 두 뜻으로 쓰였다(2026-11-05 저장본 37 실측): 원본 칸(rawSeverity · severity_raw)을 따로 적은 Lead 산출물에서는
        # 조정 뒤 **최종값**이었다(5211 · 5235). 그래서 원본 칸이 명시돼 있고 최종 칸이 없으면 `severity` 를 최종 별칭으로 읽는다
        as_final = any(k in it for k in RAW[0::2]) and not any(k in it for k in FINAL)
        raw, c1 = _one(it, tuple(k for k in RAW if not (as_final and k == "severity")))
        final, c2 = _one(it, FINAL + (("severity",) if as_final else ()))
        for c in (c1, c2):
            if c:
                problems.append(f"{iid} — 같은 칸 별칭 충돌: {c}")
        sev = final or raw
        if sev is not None and sev not in SEVERITIES:
            problems.append(f"{iid} — 모르는 severity {sev!r}")
        fb = it.get("foundBy", it.get("found_by"))
        if fb is None and shape == "merge":
            fb = [x for x in (it.get("source"), it.get("lens")) if x]
        if isinstance(fb, str):
            fb = [fb]
        ev = it.get("evidence")
        if isinstance(ev, str):
            ev = [ev]
        items.append({
            "id": iid, "foundBy": fb or [], "severity_raw": raw, "severity_final": final, "severity": sev,
            "file": it.get("file"), "line_range": it.get("line_range", it.get("line")), "evidence": ev or [],
            "origin": it.get("origin"), "symptom_screen": it.get("symptom_screen"), "symptom_reach": it.get("symptom_reach"),
            "title": it.get("title") or it.get("description"),
        })
    return shape, items, problems


def zero_evidence(data) -> str | None:
    """0건 완결 증거가 있으면 None, 없으면 무엇이 빠졌는지 한 줄."""
    if not isinstance(data, dict):
        return "병합본 inputs · summary 가 없다"
    inp, summ = data.get("inputs"), data.get("summary")
    if not isinstance(inp, dict) or not isinstance(summ, dict):
        return "병합본 inputs · summary 가 없다(Lead 0건만으로는 '찾지 못함' 과 '안 돌림' 을 가를 수 없다)"
    if "gptUnavailable" not in inp or inp.get("gptUnavailable") is not None:
        return f"GPT 패스가 완료되지 않았다(gptUnavailable={inp.get('gptUnavailable', '키 없음')!r}) — 0건이 '찾지 못함' 인지 모른다"
    if inp.get("claude") != 0 or inp.get("gpt") != 0:
        return f"입력 후보가 0 이 아니다(claude={inp.get('claude')!r} · gpt={inp.get('gpt')!r}) — 후보를 뺐다면 Curate excluded 로 처분한다"
    if inp.get("evidenceChecked") is not True:
        return "evidenceChecked 가 true 가 아니다(diff 대조 없이 병합했다)"
    if summ.get("candidatesIn") != 0 or summ.get("candidatesOut") != 0:
        return f"summary 후보 수가 0 이 아니다(in={summ.get('candidatesIn')!r} · out={summ.get('candidatesOut')!r})"
    return None


def check(path: pathlib.Path, out=None):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        print(f"UNRUN: 읽기/파싱 실패 — {type(e).__name__}: {e}", file=sys.stderr)
        return UNRUN
    shape, items, problems = normalize(data)
    if shape is None:
        print(f"UNRUN: 모양을 모른다 — {problems[0]}", file=sys.stderr)
        return UNRUN
    if out:
        pathlib.Path(out).write_text(json.dumps({"schema": "fz-synthesized/1", "shape": shape, "items": items,
                                                 "inputs": data.get("inputs") if isinstance(data, dict) else None},
                                                ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"synthesized 계약 — 모양 {shape} · 항목 {len(items)} · 위반 {len(problems)}")
    for p in problems[:10]:
        print(f"  ✗ {p}")
    if problems:
        return VIOLATION
    if not items:
        why = zero_evidence(data)
        if why:
            print(f"UNRUN: 0건인데 완결 증거가 없다 — {why}", file=sys.stderr)
            return UNRUN
        print("  0건 — 완결 증거 있음(GPT 완료 · 입력 0 · 근거 대조 · 후보 0→0)")
    return OK


def self_test() -> int:
    passed = total = 0

    def case(name, ok, detail=""):
        nonlocal passed, total
        total += 1
        passed += bool(ok)
        print(f"{name}: {'PASS' if ok else 'FAIL'}" + ("" if ok else f" — {detail}"))

    ZERO = {"schemaVersion": 1, "inputs": {"claude": 0, "gpt": 0, "gptVerdicts": 0, "gptUnavailable": None, "evidenceChecked": True},
            "candidates": [], "groups": [], "summary": {"candidatesIn": 0, "candidatesOut": 0}}
    # 실제 병합기 출력 모양(review_merge.candidate + 등급 단계) — pre-existing 은 effectiveSeverity 가 suggestion 이다
    MERGED = {"inputs": {"claude": 1, "gpt": 1, "gptVerdicts": 0, "gptUnavailable": None, "evidenceChecked": True},
              "candidates": [
                  {"id": "claude:C1", "source": "claude", "lens": "arch", "file": "src/a.swift", "line_range": "10-12", "severity": "major",
                   "origin": "pre-existing", "evidence": "src/a.swift:10 guard 없음", "effectiveSeverity": "suggestion", "foundBy": ["claude"]},
                  {"id": "gpt:G1", "source": "gpt", "lens": None, "file": "src/b.swift", "line_range": "3", "severity": "minor",
                   "origin": "regression", "evidence": ["src/b.swift:3"], "effectiveSeverity": "minor"}],
              "summary": {"candidatesIn": 2, "candidatesOut": 2}}
    LEAD = {"issues": [{"id": "L1", "found_by": "gpt", "rawSeverity": "major", "severity_final": "minor", "line": "7",
                        "file": "src/c.swift", "symptom_screen": "목록", "symptom_reach": "탭 → 목록", "evidence": "src/c.swift:7"}]}
    with tempfile.TemporaryDirectory() as t:
        T = pathlib.Path(t)

        def run(name, obj, out=None):
            p = T / f"{name}.json"
            p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
            o, e = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = open(os.devnull, "w")
            try:
                return check(p, out)
            finally:
                sys.stdout.close()
                sys.stdout, sys.stderr = o, e

        rc = run("lead", LEAD, T / "lead.norm.json")
        n = json.loads((T / "lead.norm.json").read_text(encoding="utf-8"))["items"][0]
        orig_kept = json.loads((T / "lead.json").read_text(encoding="utf-8")) == LEAD
        case("lead-shape-roundtrip", rc == OK and n["foundBy"] == ["gpt"] and n["severity_raw"] == "major" and n["severity_final"] == "minor"
             and n["severity"] == "minor" and n["line_range"] == "7" and n["evidence"] == ["src/c.swift:7"] and orig_kept, (rc, n))
        rc = run("merged", MERGED, T / "merged.norm.json")
        items = {x["id"]: x for x in json.loads((T / "merged.norm.json").read_text(encoding="utf-8"))["items"]}
        g1 = items.get("gpt:G1", {})
        case("merge-shape-roundtrip", rc == OK and g1.get("foundBy") == ["gpt"] and g1.get("evidence") == ["src/b.swift:3"], (rc, g1))
        c1 = items.get("claude:C1", {})
        case("merge-preexisting-cap", c1.get("severity_raw") == "major" and c1.get("severity_final") == "suggestion"
             and c1.get("severity") == "suggestion" and c1.get("evidence") == ["src/a.swift:10 guard 없음"], c1)
        case("raw-alias-conflict", run("c1", {"issues": [{"id": "X", "severity_raw": "major", "rawSeverity": "minor"}]}) == VIOLATION)
        case("final-alias-conflict", run("c2", {"issues": [{"id": "X", "finalSeverity": "minor", "effectiveSeverity": "suggestion"}]}) == VIOLATION)
        r = run("c6", {"issues": [{"id": "I1", "severity": "suggestion", "rawSeverity": "minor"}]}, T / "c6.norm.json")
        x = json.loads((T / "c6.norm.json").read_text(encoding="utf-8"))["items"][0]
        case("severity-is-final-when-raw-explicit", r == OK and x["severity_raw"] == "minor" and x["severity_final"] == "suggestion" and x["severity"] == "suggestion", (r, x))
        case("raw-vs-final-not-conflict", run("c3", {"issues": [{"id": "X", "severity": "major", "severity_final": "suggestion"}]}) == OK)
        case("unknown-severity", run("c4", {"issues": [{"id": "X", "severity": "majoor"}]}) == VIOLATION)
        case("missing-id", run("c5", {"issues": [{"severity": "minor"}]}) == VIOLATION)
        case("zero-with-evidence", run("z1", ZERO) == OK)
        to = json.loads(json.dumps(ZERO)); to["inputs"]["gptUnavailable"] = "exit 16 — GPT 시간 초과"
        case("zero-gpt-timeout-unrun", run("z2", to) == UNRUN)
        ni = {k: v for k, v in ZERO.items() if k != "inputs"}
        case("zero-no-inputs-unrun", run("z3", ni) == UNRUN)
        case("zero-bare-lead-unrun", run("z4", {"issues": []}) == UNRUN)
        nk = json.loads(json.dumps(ZERO)); del nk["inputs"]["gptUnavailable"]
        case("zero-missing-gpt-key-unrun", run("z5", nk) == UNRUN)
        ev = json.loads(json.dumps(ZERO)); ev["inputs"]["evidenceChecked"] = False
        case("zero-unchecked-evidence-unrun", run("z6", ev) == UNRUN)
        case("unknown-shape-unrun", run("u1", {"findings_x": []}) == UNRUN)
    print(f"self-test {passed}/{total} passed")
    return OK if passed == total else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--normalize", metavar="OUT")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.file:
        print("UNRUN: FILE 이 필요하다", file=sys.stderr)
        return UNRUN
    return check(pathlib.Path(a.file), a.normalize)


if __name__ == "__main__":
    sys.exit(main())
