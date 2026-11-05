#!/usr/bin/env python3
"""check_symptom_anchor.py — severity minor 이상 발견에 **증상 관측 지점**이 있는가 (Gate 4.7-S).

왜 [F-285]: `major`·`regression` 6건이 배선을 끝까지 추적하고도 전부 철회됐다. 배선 4단계가
모두 사실이었는데 **그 값을 그리는 뷰가 그 시점에 계층에 없었다.** 방어 규칙은 있었지만
술어가 "코드로 확정할 수 없는 주장" 이라 *배선이 추적되는* 주장은 통째로 게이트 밖이었다.

⛔ **문서만 고치면 또 안 잡힌다.** F-285 가 정확히 그 사례다 — 규칙은 있었고 발화하지 않았다.
   그래서 기계 검사를 둔다.

판정: `severity_final`(없으면 `severity`)이 **minor 이상**(critical · major · minor)인 이슈는
`symptom_screen` 과 `symptom_reach` 둘 다 비어 있지 않아야 한다 — 계약은 `modules/peer-review-gates.md` 의 "`minor` 이상" 이다.
⛔ 열거가 아니라 하한이다 [F-533]: 예전 `BLOCKING = (major, minor)` 는 critical 을 빼먹어 가장 심각한 이슈가 검사 없이 통과했다.
알 수 없는 severity(오타 등)는 통과가 아니라 판정 불가다. `excluded`(Lead 가 제외한 이슈)는 비차단 값으로 인정한다.

exit code:
  0  PASS — 위반 0건
  1  VIOLATION — 관측 지점이 빈 minor+ 이슈가 있다 (suggestion 으로 강등하거나 채운다)
  2  UNRUN — 파일 부재·파싱 실패·issues 0건 등 판정 불가. ⛔ 통과로 읽지 않는다

Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

OK, VIOLATION, UNRUN = 0, 1, 2
# ⛔ N6 루트 앵커 — lint_contracts ANCHOR_LINES 허용 형태와 정확히 일치
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from check_synthesized import normalize, zero_evidence  # noqa: E402 — 두 생산자 모양 · 0건 완결 증거를 같은 규칙으로 읽는다(F-530)
BLOCKING = ("critical", "major", "minor")          # 계약 "minor 이상" — 새 등급이 생기면 여기와 KNOWN 을 같이 고친다
KNOWN = BLOCKING + ("suggestion", "excluded")       # 그 밖의 값은 판정 불가(UNRUN) — 오타가 조용히 면제되지 않게


def log(*a):
    print(*a, file=sys.stderr)


def check(path: pathlib.Path):
    if not path.is_file():
        log(f"UNRUN: 파일 없음 — {path}")
        return UNRUN
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        log(f"UNRUN: 읽기/파싱 실패 — {type(e).__name__}: {e}")
        return UNRUN

    # 두 생산자 모양(Lead issues[] · 병합 candidates[])을 check_synthesized.normalize 로 같은 칸에 모은다 — severity 판정 값 = 최종 우선
    shape, issues, problems = normalize(data)
    if shape is None:
        log(f"UNRUN: issues[] · candidates[] 를 찾을 수 없다 — {path}")
        return UNRUN
    if problems:   # ⛔ 깨진 항목(객체 아님 · 별칭 충돌 · 모르는 severity)을 버리고 남은 것만 보면 통과로 읽힌다
        log(f"UNRUN: 판정할 수 없는 항목 {len(problems)}건 — {problems[0]} (⛔ 통과 아님)")
        return UNRUN
    if not issues:
        why = zero_evidence(data)
        if why:
            log(f"UNRUN: 0건 — 측정 실패를 먼저 의심한다({why})")
            return UNRUN
        print("OK: 0건 — 완결 증거 있음(GPT 완료 · 입력 0 · 근거 대조 · 후보 0→0)")
        return OK

    bad, unrated, unknown, blocking = [], [], [], 0
    for i, it in enumerate(issues):
        if not isinstance(it, dict):
            unrated.append(f"[{i}] 객체가 아니다")
            continue
        iid = it.get("id") or f"[{i}]"
        sev = it["severity"]
        if sev is None:
            # ⛔ severity 가 없으면 **통과가 아니라 판정 불가**다. 조용히 넘기면
            #    필드를 지우는 것만으로 게이트를 우회할 수 있다.
            unrated.append(iid)
            continue
        if sev not in KNOWN:
            unknown.append(f"{iid}={sev}")
            continue
        if sev not in BLOCKING:
            continue
        blocking += 1
        screen = (it.get("symptom_screen") or "").strip()
        reach = (it.get("symptom_reach") or "").strip()
        miss = [n for n, v in (("symptom_screen", screen), ("symptom_reach", reach)) if not v]
        if miss:
            bad.append((iid, sev, miss))

    print(f"분모: 이슈 {len(issues)}건 · 그중 minor 이상 {blocking}건")
    print(f"  증상 관측 지점 누락            : {len(bad)}")
    for iid, sev, miss in bad:
        print(f"      {iid} ({sev}) — 빈 칸: {', '.join(miss)}")
    print(f"  severity 미표기(판정 불가)      : {len(unrated)}")
    print(f"  알 수 없는 severity(판정 불가)  : {len(unknown)}")
    for u in unknown[:5]:
        print(f"      {u}")
    for u in unrated[:5]:
        print(f"      {u}")

    if unrated or unknown:
        log(f"UNRUN: severity 가 없거나({len(unrated)}) 알 수 없는 값({len(unknown)})인 이슈 — 판정 불가 (⛔ 통과 아님)")
        return UNRUN
    if bad:
        log(f"VIOLATION: minor 이상 {len(bad)}건에 증상 관측 지점이 없다 — "
            "`suggestion` 으로 강등하거나 `symptom_screen`·`symptom_reach` 를 채워라 (Gate 4.7-S)")
        return VIOLATION
    print("OK: minor 이상 전건에 증상 관측 지점이 있다")
    return OK


def self_test():
    """fixture — 통과 · 화면누락 · 도달누락 · 둘다 · suggestion면제 · severity_final우선
    · severity부재UNRUN · 빈배열UNRUN · 파일부재UNRUN · 파싱실패UNRUN · 공백만은빈칸.
    """
    import tempfile
    passed, failed, cases = [], [], 0

    def case(name, fn):
        nonlocal cases
        cases += 1
        with tempfile.TemporaryDirectory() as tmp:
            try:
                fn(pathlib.Path(tmp)); passed.append(name)
            except AssertionError as e:
                failed.append(f"{name}: {e}")
            except Exception as e:
                failed.append(f"{name}: ⛔ 예외 {type(e).__name__}: {e}")

    def write(tmp, issues):
        f = tmp / "synthesized-issues.json"
        f.write_text(json.dumps({"issues": issues}, ensure_ascii=False), encoding="utf-8")
        return f

    FULL = {"id": "M1", "severity": "major", "symptom_screen": "PlayerVC", "symptom_reach": "상세 진입"}

    def c_pass(tmp):
        assert check(write(tmp, [FULL])) == OK, "채워졌는데 통과 못 했다"

    def c_missing_screen(tmp):
        it = dict(FULL); it["symptom_screen"] = ""
        assert check(write(tmp, [it])) == VIOLATION, "⛔ 화면 누락을 못 잡았다"

    def c_missing_reach(tmp):
        it = dict(FULL); it.pop("symptom_reach")
        assert check(write(tmp, [it])) == VIOLATION, "⛔ 도달 누락(키 부재)을 못 잡았다"

    def c_whitespace_is_empty(tmp):
        it = dict(FULL); it["symptom_screen"] = "   "
        assert check(write(tmp, [it])) == VIOLATION, "⛔ 공백만 채운 것을 통과시켰다"

    def c_suggestion_exempt(tmp):
        it = {"id": "S1", "severity": "suggestion"}
        assert check(write(tmp, [it])) == OK, "suggestion 은 면제인데 걸렸다"

    def c_severity_final_wins(tmp):
        """⛔ 강등한 이슈는 `severity_final` 로 내려간다 — 그 값을 봐야 한다."""
        it = {"id": "X1", "severity": "major", "severity_final": "suggestion"}
        assert check(write(tmp, [it])) == OK, "⛔ severity_final 강등을 무시하고 원래 값을 봤다"
        it2 = {"id": "X2", "severity": "suggestion", "severity_final": "major"}
        assert check(write(tmp, [it2])) == VIOLATION, "⛔ severity_final 승격을 무시했다"

    def c_critical_blocks(tmp):
        """⛔ 회귀 F-533: critical 은 minor 이상이다 — 증상 칸이 비면 위반."""
        assert check(write(tmp, [{"id": "C1", "severity": "critical"}])) == VIOLATION, "⛔ critical 이 검사 없이 통과했다"

    def c_unknown_severity_unrun(tmp):
        """⛔ 회귀 F-533: 오타 severity 는 면제가 아니라 판정 불가."""
        assert check(write(tmp, [{"id": "T1", "severity": "majoor"}])) == UNRUN, "⛔ 오타 severity 가 조용히 통과했다"

    def c_excluded_exempt(tmp):
        it = {"id": "E1", "severity": "major", "severity_final": "excluded"}
        assert check(write(tmp, [it])) == OK, "excluded 는 비차단인데 걸렸다"

    def c_no_severity_unrun(tmp):
        """⛔ severity 를 지우는 것만으로 게이트를 우회할 수 없어야 한다."""
        rc = check(write(tmp, [{"id": "N1", "description": "x"}]))
        assert rc == UNRUN, f"⛔ severity 부재인데 rc={rc} — 필드 삭제로 우회된다"

    def c_empty_unrun(tmp):
        assert check(write(tmp, [])) == UNRUN, "⛔ 빈 배열이 통과했다 — 0건은 측정 실패를 먼저 의심"

    def c_zero_with_merge_evidence(tmp):
        """0건은 병합본의 완결 증거가 있을 때만 통과다 — 같은 수치라도 GPT 가 못 돌았으면 UNRUN."""
        z = {"inputs": {"claude": 0, "gpt": 0, "gptUnavailable": None, "evidenceChecked": True},
             "candidates": [], "summary": {"candidatesIn": 0, "candidatesOut": 0}}
        p = tmp / "zero.json"
        p.write_text(json.dumps(z), encoding="utf-8")
        assert check(p) == OK, "증거 있는 0건이 통과하지 못했다"
        z["inputs"]["gptUnavailable"] = "exit 16"
        p.write_text(json.dumps(z), encoding="utf-8")
        assert check(p) == UNRUN, "⛔ GPT 시간 초과 병합본의 0건이 통과했다"

    def c_malformed_entry_unrun(tmp):
        """⛔ 회귀(S21 GPT): 객체가 아닌 항목을 정규화가 걸러도 나머지만으로 통과하지 않는다."""
        p = tmp / "mixed.json"
        p.write_text(json.dumps({"issues": [{"id": "S1", "severity": "suggestion"}, None]}), encoding="utf-8")
        assert check(p) == UNRUN, "⛔ 깨진 항목을 버리고 통과했다"

    def c_merge_shape_effective(tmp):
        """병합본 후보는 effectiveSeverity(최종)로 판정한다 — pre-existing 강등(suggestion)은 면제."""
        m = {"candidates": [{"id": "claude:P1", "severity": "major", "effectiveSeverity": "suggestion", "origin": "pre-existing"}]}
        p = tmp / "merged.json"
        p.write_text(json.dumps(m), encoding="utf-8")
        assert check(p) == OK, "pre-existing 강등 후보가 증상 칸을 요구받았다"

    def c_missing_file_unrun(tmp):
        assert check(tmp / "nope.json") == UNRUN, "파일 부재가 UNRUN 이 아니다"

    def c_bad_json_unrun(tmp):
        import contextlib, io
        f = tmp / "synthesized-issues.json"
        f.write_text("{ 이건 JSON 이 아니다", encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            rc = check(f)
        err = buf.getvalue()
        assert rc == UNRUN, f"파싱 실패가 UNRUN 이 아니다 (rc={rc})"
        # ⛔ **원인 보고로 축을 격리한다** — 빈 결과로 삼키면 "issues 0건" 가드가 대신 걸려
        #    같은 UNRUN 이 나므로 rc 만 보면 이 축이 검사되지 않는다(실측 헛돌이)
        assert "파싱 실패" in err, f"⛔ '0건' 으로 보고됐다 — 못 읽은 것과 읽었는데 빈 것은 다르다: {err!r}"

    def c_evidence_trace_is_not_enough(tmp):
        """⛔ 회귀: 배선 추적(`evidence_trace`)이 충실해도 통과 근거가 아니다 [F-285 6건 전부].""" 
        it = {"id": "S6", "severity": "major",
              "evidence_trace": "currentSeekableRange→seekableDuration→SeekingBar.trackFill 4단계 전수 확인",
              "symptom_screen": "", "symptom_reach": ""}
        assert check(write(tmp, [it])) == VIOLATION, \
            "⛔ evidence_trace 가 있다고 통과시켰다 — 6건 모두 trace 는 충실했다"

    for n, f in [("pass-when-filled", c_pass),
                 ("missing-screen", c_missing_screen),
                 ("missing-reach", c_missing_reach),
                 ("whitespace-is-empty", c_whitespace_is_empty),
                 ("suggestion-exempt", c_suggestion_exempt),
                 ("severity-final-wins", c_severity_final_wins),
                 ("critical-blocks", c_critical_blocks),
                 ("unknown-severity-unrun", c_unknown_severity_unrun),
                 ("excluded-exempt", c_excluded_exempt),
                 ("no-severity-unrun", c_no_severity_unrun),
                 ("empty-issues-unrun", c_empty_unrun),
                 ("zero-with-merge-evidence", c_zero_with_merge_evidence),
                 ("merge-shape-effective", c_merge_shape_effective),
                 ("malformed-entry-unrun", c_malformed_entry_unrun),
                 ("missing-file-unrun", c_missing_file_unrun),
                 ("bad-json-unrun", c_bad_json_unrun),
                 ("evidence-trace-not-enough", c_evidence_trace_is_not_enough)]:
        case(n, f)

    print(f"self-test {len(passed)}/{cases} 통과")
    for x in passed:
        print(f"  ok   {x}")
    for x in failed:
        print(f"  FAIL {x}")
    return OK if not failed else VIOLATION


def main():
    ap = argparse.ArgumentParser(description="증상 관측 지점 게이트 (4.7-S · F-285)")
    ap.add_argument("path", nargs="?", type=pathlib.Path, help="synthesized-issues.json 경로")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.path:
        ap.error("경로 또는 --self-test 가 필요하다")
    return check(a.path)


if __name__ == "__main__":
    sys.exit(main())
