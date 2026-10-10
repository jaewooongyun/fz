#!/usr/bin/env python3
# lint:no-root-anchor — 루트를 `--root` 로 받는다(기본값은 이 파일 기준 부모 상수).
# diff-parse: hunk-state — `git diff -U0` 의 `@@` 헤더로 hunk 범위를 추적하고, hunk 안에서는
#   남은 줄 수를 세어 `+++`·`---` 로 시작하는 소스 행을 파일 헤더로 오인하지 않는다.
"""합성 품질 fixture(`tests/fixtures/quality/`) 계약 검사 (S04).

⛔ 왜 필요한가: 리뷰·계획 품질을 A/B 로 재려면 **고정 입력의 정답**이 틀리지 않아야 한다.
   정답 라벨이 diff 밖 줄을 가리키거나(리뷰어가 볼 수 없는 결함) 축 이름이 오타이거나
   지침 파일이 원래 이름으로 들어가 있으면(이 폴더에서 작업하는 세션이 자동 로드) 채점 자체가
   틀린다. 라벨은 생성기가 만들었더라도 **검사는 따로** 돈다.

판정 (fixture 단위)
  review: labels.json 스키마 · 축·심각도 enum · 라벨 줄이 실제 diff hunk(RIGHT) 안 · 그 줄에 anchor 존재 ·
          rule_ref 가 복원된 지침 파일의 heading 을 가리킴 · axes_required 전부 등장
          지침 없음(guidelines=[]) → *.fixture 지침 0 · rule_ref 전부 null · 금지 인용 목록 존재
          상충(conflicts) → 출처 2개 이상 · 출처 heading 실재 · 대상 파일 실재
          비 iOS → 지침에 RIBs 없음 · architecture 라벨은 자기 지침을 인용
  plan:   rubric.json 6절(Contracts·Roles·Stage·Adapters·State·Failure) · Q1~Q8 · load_10x ·
          dependency_failure · rollback 비어 있지 않음 · residues·consumers 심볼이 base 에 실재
  공통:   build-repo.sh 실행 성공 · 평문 지침 파일(CLAUDE.md·AGENTS.md·GEMINI.md) 0 · 홈 절대경로·이메일 0
판정 (세트 단위)
  6축+critical·major ≥2 인 iOS review · 비 iOS review · 지침 없음 · 상충 · plan · 잔재가 있는 plan 이 각 1개 이상

exit: 0=충족 · 1=위반 · 2=측정 실패(git 없음·fixture 폴더 없음 — ⛔ 통과 아님)
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

OK, VIOLATION, UNRUN = 0, 1, 2
DEFAULT_ROOT = pathlib.Path(__file__).resolve().parent.parent
REL_FIXTURES = pathlib.Path("tests/fixtures/quality")

AXES6 = ["idiom", "naming", "architecture", "ui_structure", "placement", "design_alternative"]
AXES_ALLOWED = set(AXES6) | {"correctness"}
SEVERITIES = {"critical", "major", "minor", "suggestion"}
PLAIN_GUIDES = {"CLAUDE.md", "AGENTS.md", "GEMINI.md"}
PLAN_SECTIONS = ["Contracts", "Roles", "Stage", "Adapters", "State", "Failure"]
PLAN_EXTRAS = ["load_10x", "dependency_failure", "rollback"]
HOME_RE = re.compile(r"(/Users/[A-Za-z0-9]|/home/[A-Za-z0-9])")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")


class Unrun(Exception):
    """측정 실패 — 위반 0건으로 읽히면 안 된다."""


def read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


# ── diff 파싱 (hunk-state) ───────────────────────────────────────────────
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_right_hunks(diff_text: str) -> dict[str, list[tuple[int, int]]]:
    """파일 경로 → RIGHT(새 쪽) hunk 범위 목록. 삭제만 있는 hunk(d=0)는 범위가 없다."""
    files: dict[str, list[tuple[int, int]]] = {}
    cur = None
    rem_old = rem_new = 0
    for line in diff_text.split("\n"):
        if rem_old > 0 or rem_new > 0:
            # hunk 안 — 접두사는 내용이다. `+++ x` 는 '++ x' 를 추가한 소스 행이다.
            tag = line[:1]
            if tag == "-":
                rem_old -= 1
            elif tag == "+":
                rem_new -= 1
            elif tag == " ":
                rem_old -= 1
                rem_new -= 1
            # '\ No newline at end of file' 는 카운트하지 않는다
            continue
        if line.startswith("diff --git "):
            cur = None
            continue
        if line.startswith("+++ "):
            path = line[4:]
            cur = None if path == "/dev/null" else (path[2:] if path.startswith("b/") else path)
            if cur is not None:
                files.setdefault(cur, [])
            continue
        m = HUNK_RE.match(line)
        if m and cur is not None:
            b = int(m.group(2)) if m.group(2) is not None else 1
            c = int(m.group(3))
            d = int(m.group(4)) if m.group(4) is not None else 1
            rem_old, rem_new = b, d
            if d > 0:
                files[cur].append((c, c + d - 1))
    return files


# ── 저장소 복원 ─────────────────────────────────────────────────────────
def build(fx: pathlib.Path, dest: pathlib.Path) -> None:
    script = fx / "build-repo.sh"
    if not script.is_file():
        raise ValueError("build-repo.sh 없음")
    r = subprocess.run(["bash", str(script), str(dest)], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise ValueError(f"build-repo.sh 실패 rc={r.returncode}: {r.stderr.strip()[:200]}")


def git(repo: pathlib.Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise ValueError(f"git {' '.join(args)} 실패: {r.stderr.strip()[:200]}")
    return r.stdout


def headings(text: str) -> set[str]:
    return {m.group(1).strip() for m in re.finditer(r"^#{1,6}\s+(.+?)\s*$", text, re.M)}


# ── fixture 단위 검사 ────────────────────────────────────────────────────
def scan_common(fx: pathlib.Path) -> list[str]:
    v = []
    for p in fx.rglob("*"):
        if p.is_file() and p.name in PLAIN_GUIDES:
            v.append(f"{p.relative_to(fx)}: 평문 지침 파일 — *.fixture 로만 둔다")
    targets = [p for sub in ("base", "head") if (fx / sub).is_dir() for p in (fx / sub).rglob("*") if p.is_file()]
    targets += [p for p in fx.iterdir() if p.is_file() and p.suffix in (".json", ".md")]
    for p in targets:
        t = read(p)
        if HOME_RE.search(t):
            v.append(f"{p.relative_to(fx)}: 홈 절대경로")
        for m in EMAIL_RE.finditer(t):
            v.append(f"{p.relative_to(fx)}: 이메일 {m.group(0)}")
            break
    return v


def check_rule_ref(ref, guidelines: list[str], repo: pathlib.Path, where: str) -> list[str]:
    if ref is None:
        return []
    if not isinstance(ref, str) or "#" not in ref:
        return [f"{where}: rule_ref 형식은 FILE#Heading — {ref!r}"]
    f, h = ref.split("#", 1)
    if f not in guidelines:
        return [f"{where}: rule_ref 파일 {f} 가 guidelines 목록 밖"]
    gp = repo / f
    if not gp.is_file():
        return [f"{where}: 지침 {f} 가 복원 저장소에 없다"]
    if h not in headings(read(gp)):
        return [f"{where}: 지침 {f} 에 heading '{h}' 없음"]
    return []


def check_review(fx: pathlib.Path, work: pathlib.Path) -> tuple[list[str], dict]:
    v: list[str] = []
    lab = json.loads(read(fx / "labels.json"))
    need = ["fixture", "kind", "platform", "base_branch", "head_branch", "guidelines", "axes_required",
            "not_applicable_axes", "issues", "conflicts", "forbidden_rule_citations"]
    miss = [k for k in need if k not in lab]
    if miss:
        return [f"labels.json 필수 키 없음: {miss}"], {}
    repo = work / fx.name
    build(fx, repo)
    diff = git(repo, "diff", "-U0", "--no-color", lab["base_branch"], lab["head_branch"], "--")
    hunks = parse_right_hunks(diff)
    if not hunks:
        v.append("diff 가 비었다 — head/ 변경 없음")
    git(repo, "checkout", "-q", lab["head_branch"])
    ids = [i.get("id") for i in lab["issues"]]
    if len(ids) != len(set(ids)):
        v.append("라벨 id 중복")
    for i in lab["issues"]:
        w = f"{i.get('id')}"
        for k in ("id", "axis", "severity", "file", "line_start", "line_end", "anchor", "summary"):
            if k not in i:
                v.append(f"{w}: 필드 {k} 없음")
        if i.get("axis") not in AXES_ALLOWED:
            v.append(f"{w}: 축 {i.get('axis')!r} 은 허용 목록 밖")
        if i.get("severity") not in SEVERITIES:
            v.append(f"{w}: severity {i.get('severity')!r}")
        f = i.get("file")
        s, e = i.get("line_start", 0), i.get("line_end", 0)
        # ⛔ 줄 범위는 정수(bool 제외)이고 line_start ≤ line_end 여야 한다 — 역순 범위(6-4)는 아래 hunk 포함 검사(a ≤ s · e ≤ b)를
        #    그대로 통과했고, 문자열 줄 번호("5")는 비교에서 TypeError 로 감사 전체를 죽였다(traceback). 파일 끝을 넘는 줄은
        #    RIGHT hunk 가 파일 길이를 넘지 못하므로 hunk 검사가 잡는다
        rng = type(s) is int and type(e) is int and s <= e
        if not rng:
            v.append(f"{w}: 줄 범위 {s!r}-{e!r} 가 잘못됐다 — 정수이고 line_start ≤ line_end 여야 한다")
        if f not in hunks:
            v.append(f"{w}: {f} 는 diff 에 없다")
        elif rng and not any(a <= s and e <= b for a, b in hunks[f]):
            v.append(f"{w}: {f}:{s}-{e} 가 diff hunk 밖 — 리뷰어가 볼 수 없는 줄")
        fp = repo / f if f else None
        if fp and fp.is_file() and type(s) is int:
            lines = read(fp).split("\n")
            if not (1 <= s <= len(lines)) or i.get("anchor", "\0") not in lines[s - 1]:
                v.append(f"{w}: {f}:{s} 에 anchor {i.get('anchor')!r} 없음(줄 드리프트)")
        v += check_rule_ref(i.get("rule_ref"), lab["guidelines"], repo, w)
    present = {i.get("axis") for i in lab["issues"]}
    for ax in lab["axes_required"]:
        if ax not in present:
            v.append(f"필수 축 {ax} 라벨 0건")
    fixture_guides = [p for p in (fx / "base").rglob("*.fixture")] + (
        [p for p in (fx / "head").rglob("*.fixture")] if (fx / "head").is_dir() else [])
    if not lab["guidelines"]:
        if fixture_guides:
            v.append("guidelines=[] 인데 *.fixture 지침이 있다")
        if any(i.get("rule_ref") for i in lab["issues"]):
            v.append("지침 없음 fixture 의 라벨이 rule_ref 를 가진다 — 규칙 출처가 없다")
        if not lab["forbidden_rule_citations"]:
            v.append("지침 없음 fixture 에 금지 인용 목록이 비었다(AC-3 판정 입력)")
    else:
        for g in lab["guidelines"]:
            if not (repo / g).is_file():
                v.append(f"지침 {g} 가 복원 저장소에 없다(*.fixture 누락)")
    for c in lab["conflicts"]:
        w = f"{c.get('id')}"
        if len(c.get("sources", [])) < 2:
            v.append(f"{w}: 상충 출처가 2개 미만")
        for src in c.get("sources", []):
            v += check_rule_ref(src, lab["guidelines"], repo, w)
        if not c.get("claim_a") or not c.get("claim_b"):
            v.append(f"{w}: claim_a/claim_b 비었다")
        if c.get("target") and not (repo / c["target"]).is_file():
            v.append(f"{w}: 대상 {c['target']} 없음")
    if lab["platform"] != "ios":
        for g in lab["guidelines"]:
            if (repo / g).is_file() and "RIBs" in read(repo / g):
                v.append(f"비 iOS 지침 {g} 에 RIBs — 다른 아키텍처 규칙이어야 한다")
        for i in lab["issues"]:
            if i.get("axis") == "architecture" and not i.get("rule_ref"):
                v.append(f"{i.get('id')}: 비 iOS architecture 라벨은 자기 지침을 인용해야 한다")
    crit_major = sum(1 for i in lab["issues"] if i.get("severity") in ("critical", "major"))
    info = {"kind": "review", "platform": lab["platform"], "axes": present, "crit_major": crit_major,
            "guidelines": lab["guidelines"], "conflicts": len(lab["conflicts"]),
            "six": all(a in present for a in AXES6)}
    return v, info


def check_plan(fx: pathlib.Path, work: pathlib.Path) -> tuple[list[str], dict]:
    v: list[str] = []
    rub = json.loads(read(fx / "rubric.json"))
    if not (fx / rub.get("requirement", "requirement.md")).is_file():
        v.append("requirement 파일 없음")
    for s in PLAN_SECTIONS:
        items = rub.get("sections", {}).get(s)
        if not items:
            v.append(f"채점표 절 {s} 비었다")
            continue
        for it in items:
            if not it.get("id") or not it.get("criterion") or not it.get("keywords"):
                v.append(f"{s}: 항목에 id·criterion·keywords 필요")
    for q in (f"Q{n}" for n in range(1, 9)):
        if not rub.get("questions", {}).get(q):
            v.append(f"질문 {q} 비었다")
    for k in PLAN_EXTRAS:
        if not rub.get(k):
            v.append(f"{k} 비었다")
    repo = work / fx.name
    build(fx, repo)
    for kind in ("residues", "consumers"):
        for it in rub.get(kind, []):
            p = repo / it.get("file", "")
            if not p.is_file():
                v.append(f"{it.get('id')}: {it.get('file')} 없음")
            elif it.get("symbol", "\0") not in read(p):
                v.append(f"{it.get('id')}: {it.get('file')} 에 {it.get('symbol')!r} 없음")
    return v, {"kind": "plan", "residues": len(rub.get("residues", []))}


def audit(root: pathlib.Path) -> dict:
    qdir = root / REL_FIXTURES
    if not qdir.is_dir():
        raise Unrun(f"{REL_FIXTURES} 없음")
    if shutil.which("git") is None:
        raise Unrun("git 없음")
    fixtures = sorted(p for p in qdir.iterdir() if p.is_dir() and not p.name.startswith("_"))
    if not fixtures:
        raise Unrun("fixture 0개 — 경로 오류 의심(⛔ PASS 아님)")
    violations: list[str] = []
    infos: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as td:
        work = pathlib.Path(td)
        for fx in fixtures:
            vv = scan_common(fx)
            try:
                if (fx / "labels.json").is_file():
                    more, info = check_review(fx, work)
                elif (fx / "rubric.json").is_file():
                    more, info = check_plan(fx, work)
                else:
                    more, info = ["labels.json·rubric.json 둘 다 없다"], {}
            except (ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
                more, info = [f"검사 중 오류: {e}"], {}
            vv += more
            violations += [f"{fx.name}: {x}" for x in vv]
            infos[fx.name] = info
    reviews = [i for i in infos.values() if i.get("kind") == "review"]
    plans = [i for i in infos.values() if i.get("kind") == "plan"]
    need = {
        "6축 + critical·major ≥2 인 iOS review": any(i["platform"] == "ios" and i["six"] and i["crit_major"] >= 2 for i in reviews),
        "비 iOS review": any(i["platform"] != "ios" for i in reviews),
        "지침 없음 review": any(not i["guidelines"] for i in reviews),
        "상충 review": any(i["conflicts"] > 0 for i in reviews),
        "plan": bool(plans),
        "잔재가 있는 plan": any(i["residues"] > 0 for i in plans),
    }
    violations += [f"세트: {k} 가 없다" for k, ok in need.items() if not ok]
    return {"fixtures": len(fixtures), "violations": violations}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test(pathlib.Path(a.root))
    try:
        r = audit(pathlib.Path(a.root))
    except Unrun as e:
        print(f"UNRUN: {e}")
        return UNRUN
    for x in r["violations"]:
        print(f"  VIOLATION {x}")
    print(f"quality-fixtures: fixtures={r['fixtures']} violations={len(r['violations'])}")
    return VIOLATION if r["violations"] else OK


# ── self-test ──────────────────────────────────────────────────────────
def self_test(root: pathlib.Path) -> int:
    lib = root / REL_FIXTURES / "_lib" / "build_repo.sh"
    if not lib.is_file() or shutil.which("git") is None:
        print("UNRUN: self-test 전제(_lib/build_repo.sh·git) 없음")
        return UNRUN
    wrapper = ('#!/bin/bash\nexec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../_lib/build_repo.sh" '
               '"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" "$@"\n')
    guide = "# G\n\n## Rules\n\n- 규칙 하나\n"
    base_src = "line1\nline2\nline3\n"
    head_src = "line1\nline2\nline3\nnew-a\nnew-b\nnew-c\nnew-d\nnew-e\nnew-f\nnew-g\n"

    def mk_review(td: pathlib.Path, *, issues=None, guides=True, plain=False, extra_head=None, conflicts=None,
                  forbidden=None, platform="ios", axes_required=None) -> pathlib.Path:
        q = td / REL_FIXTURES
        (q / "_lib").mkdir(parents=True, exist_ok=True)
        shutil.copy(lib, q / "_lib" / "build_repo.sh")
        fx = q / "r"
        (fx / "base").mkdir(parents=True)
        (fx / "head").mkdir()
        (fx / "build-repo.sh").write_text(wrapper)
        (fx / "base" / "a.txt").write_text(base_src)
        (fx / "head" / "a.txt").write_text(head_src + (extra_head or ""))
        if guides:
            (fx / "base" / ("CLAUDE.md" if plain else "CLAUDE.md.fixture")).write_text(guide)
        if issues is None:
            issues = [{"id": f"X{n}", "axis": ax, "severity": "major" if n < 2 else "minor", "file": "a.txt",
                       "line_start": 4 + n, "line_end": 4 + n, "anchor": f"new-{'abcdefg'[n]}",
                       "rule_ref": "CLAUDE.md#Rules" if guides else None, "summary": "s"}
                      for n, ax in enumerate(AXES6)]
        (fx / "labels.json").write_text(json.dumps({
            "fixture": "r", "kind": "review", "platform": platform, "base_branch": "main", "head_branch": "feature",
            "guidelines": ["CLAUDE.md"] if guides else [],
            "axes_required": AXES6 if axes_required is None else axes_required, "not_applicable_axes": [],
            "issues": issues, "conflicts": conflicts or [], "forbidden_rule_citations": forbidden or []}))
        return fx

    def mk_plan(td: pathlib.Path, *, drop=None, residue_symbol="present") -> pathlib.Path:
        q = td / REL_FIXTURES
        (q / "_lib").mkdir(parents=True, exist_ok=True)
        shutil.copy(lib, q / "_lib" / "build_repo.sh")
        fx = q / "p"
        (fx / "base").mkdir(parents=True)
        (fx / "build-repo.sh").write_text(wrapper)
        (fx / "base" / "code.txt").write_text("present symbol\n")
        (fx / "requirement.md").write_text("# 요구\n")
        item = [{"id": "x", "criterion": "c", "keywords": ["k"]}]
        rub = {"requirement": "requirement.md", "sections": {s: item for s in PLAN_SECTIONS if s != drop},
               "questions": {f"Q{n}": item for n in range(1, 9)}, "load_10x": item, "dependency_failure": item,
               "rollback": item, "residues": [{"id": "r1", "symbol": residue_symbol, "file": "code.txt"}], "consumers": []}
        (fx / "rubric.json").write_text(json.dumps(rub))
        return fx

    def review_violations(fx: pathlib.Path) -> list[str]:
        with tempfile.TemporaryDirectory() as w:
            return scan_common(fx) + check_review(fx, pathlib.Path(w))[0]

    def plan_violations(fx: pathlib.Path) -> list[str]:
        with tempfile.TemporaryDirectory() as w:
            return scan_common(fx) + check_plan(fx, pathlib.Path(w))[0]

    passed, fails = 0, []

    def case(name, make, checker, want_violation: bool, needle: str | None = None):
        nonlocal passed
        td = pathlib.Path(tempfile.mkdtemp())
        try:
            got = checker(make(td))
            if want_violation != bool(got):
                fails.append(f"{name}: violations={got[:2]} (기대 {'위반' if want_violation else '통과'})")
            elif needle and not any(needle in x for x in got):
                fails.append(f"{name}: 사유에 {needle!r} 없음 — {got[:2]}")
            else:
                passed += 1
        except Exception as e:  # noqa: BLE001 — self-test 는 예외도 실패로 센다
            fails.append(f"{name}: 예외 {e}")
        finally:
            shutil.rmtree(td, ignore_errors=True)

    rv, pv = review_violations, plan_violations
    # ① 양성 — 6축·major 2 · 지침 heading 실재
    case("valid-review", lambda td: mk_review(td), rv, False)
    # ② 축 오타
    case("bad-axis", lambda td: mk_review(td, issues=[{"id": "b", "axis": "style", "severity": "minor", "file": "a.txt",
         "line_start": 4, "line_end": 4, "anchor": "new-a", "rule_ref": None, "summary": "s"}], axes_required=[]), rv, True, "허용 목록 밖")
    # ③ ⛔ hunk 밖 줄 — 리뷰어가 볼 수 없는 결함
    case("outside-hunk", lambda td: mk_review(td, issues=[{"id": "o", "axis": "idiom", "severity": "minor", "file": "a.txt",
         "line_start": 2, "line_end": 2, "anchor": "line2", "rule_ref": None, "summary": "s"}], axes_required=[]), rv, True, "hunk 밖")
    # ④ anchor 드리프트
    case("anchor-drift", lambda td: mk_review(td, issues=[{"id": "d", "axis": "idiom", "severity": "minor", "file": "a.txt",
         "line_start": 4, "line_end": 4, "anchor": "new-z", "rule_ref": None, "summary": "s"}], axes_required=[]), rv, True, "anchor")
    # ⑤ 필수 축 누락
    case("missing-axis", lambda td: mk_review(td, issues=[{"id": "m", "axis": "idiom", "severity": "major", "file": "a.txt",
         "line_start": 4, "line_end": 4, "anchor": "new-a", "rule_ref": None, "summary": "s"}]), rv, True, "필수 축")
    # ⑥ ⛔ 평문 CLAUDE.md — 세션 자동 로드
    case("plain-guide", lambda td: mk_review(td, plain=True), rv, True, "평문 지침")
    # ⑦ 홈 절대경로
    case("home-path", lambda td: mk_review(td, extra_head="/Users/someone/x\n"), rv, True, "홈 절대경로")
    # ⑧ ⛔ 지침 없음인데 rule_ref
    case("absent-with-rule", lambda td: mk_review(td, guides=False, axes_required=[], forbidden=[{"topic": "t", "why": "w"}],
         issues=[{"id": "a", "axis": "idiom", "severity": "minor", "file": "a.txt", "line_start": 4, "line_end": 4,
                  "anchor": "new-a", "rule_ref": "CLAUDE.md#Rules", "summary": "s"}]), rv, True, "rule_ref")
    # ⑨ 상충 출처 1개
    case("conflict-one-source", lambda td: mk_review(td, conflicts=[{"id": "k", "axis": "naming", "sources": ["CLAUDE.md#Rules"],
         "claim_a": "a", "claim_b": "b"}]), rv, True, "2개 미만")
    # ⑩ rule_ref heading 부재
    case("rule-heading-missing", lambda td: mk_review(td, issues=[{"id": "h", "axis": "idiom", "severity": "minor", "file": "a.txt",
         "line_start": 4, "line_end": 4, "anchor": "new-a", "rule_ref": "CLAUDE.md#NoSuch", "summary": "s"}], axes_required=[]), rv, True, "heading")
    # ⑪ 계획 채점표 절 누락
    case("plan-missing-section", lambda td: mk_plan(td, drop="Failure"), pv, True, "Failure")
    # ⑫ ⛔ 잔재 심볼이 base 에 없다(채점 대상이 허구)
    case("plan-residue-absent", lambda td: mk_plan(td, residue_symbol="ghost"), pv, True, "ghost")
    # ⑬ 계획 양성
    case("valid-plan", lambda td: mk_plan(td), pv, False)
    # ⑭ hunk 파서 — hunk 안의 '+++' 소스 행을 헤더로 오인하지 않는다
    d = ("diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1,0 +2,2 @@\n+++ not-a-header\n+second\n"
         "diff --git a/y b/y\n--- a/y\n+++ b/y\n@@ -3 +3 @@\n-old\n+new\n")
    got = parse_right_hunks(d)
    if got == {"x": [(2, 3)], "y": [(3, 3)]}:
        passed += 1
    else:
        fails.append(f"hunk-parser: {got}")

    for f in fails:
        print(f"  FAIL {f}")
    total = passed + len(fails)
    print(f"self-test {passed}/{total} passed")
    return OK if not fails else VIOLATION


if __name__ == "__main__":
    sys.exit(main())
