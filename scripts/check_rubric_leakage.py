#!/usr/bin/env python3
# lint:no-root-anchor — 플러그인 루트를 직접 풀지 않는다. 검사 루트는 --root 인자로 받는다(lint #N6 면제 형태 c).
"""채점표 유출 검사 (R-D S33b) — fz-plan 프롬프트 자산에 plan fixture 채점표의 기준 문장이 들어가지 않았는가.

fz-plan 의 필수 항목 누락(F-352)을 렌즈 질문으로 보강할 때, 같은 fixture 로 고치고 재므로 채점표 문장을 프롬프트에 옮기면
'시험 문제를 가르치는' 수정이 된다. 이 검사는 문장 복사만 막는다 — 요약 · 바꿔 쓰기는 못 잡는다(그것은 사람의 판단이다).

채점표   tests/fixtures/quality/plan-*/rubric.json 의 모든 `criterion` 문자열(중첩 어디든)
대상     agents/plan-*.md · workflows/plan-*.js · skills/fz-plan/SKILL.md · modules/plan-*.md
비교     공백을 한 칸으로 접은 뒤 부분 문자열 — 줄바꿈 · 공백 수를 바꿔도 같은 문장으로 본다.
         MIN_LEN 미만의 짧은 기준(일반어와 겹친다)은 비교하지 않고 그 수를 보고한다
usage: check_rubric_leakage.py --root DIR | --self-test
exit: 0=유출 0 · 1=유출(VIOLATION 줄) · 2=미판정(채점표 0 · 대상 자산 0 · 사용법)
"""
import glob
import json
import os
import re
import shutil
import sys
import tempfile

MIN_LEN = 12
TARGETS = ("agents/plan-*.md", "workflows/plan-*.js", "skills/fz-plan/SKILL.md", "modules/plan-*.md")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def criteria(root):
    """[(fixture, id, 기준 문장)] — rubric.json 어디에 있든 criterion 을 모은다."""
    out = []
    for f in sorted(glob.glob(os.path.join(root, "tests", "fixtures", "quality", "plan-*", "rubric.json"))):
        fx = os.path.basename(os.path.dirname(f))
        try:
            d = json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise SystemExit(f"UNRUN: 채점표를 읽지 못했다 — {f}: {e}")

        def walk(x):
            if isinstance(x, dict):
                if isinstance(x.get("criterion"), str):
                    out.append((fx, str(x.get("id", "?")), x["criterion"]))
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
        walk(d)
    return out


def assets(root):
    files = []
    for pat in TARGETS:
        files += sorted(glob.glob(os.path.join(root, pat)))
    return files


def scan(root):
    """(code, lines)"""
    crit = criteria(root)
    if not crit:
        return 2, ["UNRUN: 채점표 기준 문장 0 — tests/fixtures/quality/plan-*/rubric.json 이 없거나 비었다(⛔ 통과 아님)"]
    files = assets(root)
    if not files:
        return 2, ["UNRUN: 대상 자산 0 — agents/plan-*.md 등이 없다(⛔ 통과 아님)"]
    long_crit = [(fx, i, norm(c)) for fx, i, c in crit if len(norm(c)) >= MIN_LEN]
    texts = {f: norm(open(f, encoding="utf-8", errors="replace").read()) for f in files}
    lines = []
    for f, t in texts.items():
        for fx, i, c in long_crit:
            if c in t:
                lines.append(f"VIOLATION {os.path.relpath(f, root)}: {fx}:{i} 채점표 문장 — '{c[:40]}…'")
    if lines:
        return 1, lines
    return 0, [f"OK: 채점표 문장 {len(long_crit)}개(짧은 기준 {len(crit) - len(long_crit)}개 제외) · 대상 자산 {len(files)}개 · 유출 0"]


def self_test():
    cases, bad = [], 0
    tmp = tempfile.mkdtemp(prefix="rubric-leak-")
    try:
        def tree(name, rubric, files):
            r = os.path.join(tmp, name)
            if rubric is not None:
                os.makedirs(os.path.join(r, "tests", "fixtures", "quality", "plan-x"))
                json.dump(rubric, open(os.path.join(r, "tests", "fixtures", "quality", "plan-x", "rubric.json"), "w", encoding="utf-8"),
                          ensure_ascii=False)
            for rel, body in files.items():
                os.makedirs(os.path.dirname(os.path.join(r, rel)), exist_ok=True)
                open(os.path.join(r, rel), "w", encoding="utf-8").write(body)
            os.makedirs(r, exist_ok=True)
            return r
        rub = {"sections": [{"id": "Q1a", "criterion": "합성 기준 문장 하나 — 렌즈가 이 문장을 그대로 옮기면 안 된다"},
                            {"id": "Q2a", "criterion": "짧은 기준"}]}
        cases.append(("clean", tree("clean", rub, {"agents/plan-a.md": "일반 축 — 인증 상태별 진입\n"}), 0))
        cases.append(("leak-whitespace", tree("leak", rub, {"agents/plan-a.md": "앞\n합성  기준 문장\n하나 — 렌즈가 이 문장을   그대로 옮기면 안 된다\n"}), 1))
        cases.append(("short-not-flagged", tree("short", rub, {"skills/fz-plan/SKILL.md": "짧은 기준 이라는 말은 흔하다\n"}), 0))
        cases.append(("no-rubric", tree("norub", None, {"agents/plan-a.md": "x\n"}), 2))
        cases.append(("no-assets", tree("noasset", rub, {}), 2))
        for name, root, want in cases:
            got, out = scan(root)
            ok = got == want and (want != 1 or any(l.startswith("VIOLATION") for l in out))
            bad += not ok
            print(f"{'PASS' if ok else 'FAIL'}  {name} — exit {got} (기대 {want})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"self-test {len(cases) - bad}/{len(cases)} passed")
    return 1 if bad else 0


def main():
    a = sys.argv[1:]
    if a == ["--self-test"]:
        return self_test()
    if len(a) == 2 and a[0] == "--root":
        code, lines = scan(a[1])
        print("\n".join(lines))
        return code
    print(__doc__.strip().splitlines()[-2])
    return 2


if __name__ == "__main__":
    sys.exit(main())
