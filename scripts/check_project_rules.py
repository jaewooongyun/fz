#!/usr/bin/env python3
# lint:no-root-anchor — 검사 대상(규칙·색인·저장소·fixture 폴더)을 인자로 받는다(플러그인 루트의 파일을 읽지 않는다).
"""프로젝트 규칙 레코드 검증기 (S15 · 정본 `modules/project-rules.md`).

모드
  --compare EXTRACTED GOLDEN      추출기 출력과 golden 을 **구조로** 비교한다(바이트 아님)
  --check RULES --index INDEX [--project DIR]
                                  모델이 만든 규칙 레코드를 원문 색인에 대조한다
  --project-arch RULES            fz-plan `archConstraints` 호환 투영(4축 + 그 축의 conflicts)을 stdout 에
  --fixtures QUALITY_DIR          품질 fixture 마다 저장소를 복원해 추출 → golden 대조 (health-check 용)
  --self-test

--check 가 거부하는 것 (⛔ 전부 결정론 — 레코드를 만든 모델의 판단을 믿지 않는다)
  V1 지어낸 인용 — quote 가 인용한 파일에 없거나, 있어도 인용한 줄을 덮지 않는다(맞는 문장 · 틀린 위치)
  V2 상충 축에 값 — conflicts 에 오른 축은 axes 에서 null 이어야 한다
  V3 지침 부재인데 규칙 — 색인이 absent 인데 지침·예시 레코드가 있다 · 지침·예시가 지침 파일 밖을 인용한다
  V4 출처 없는 규칙 — source 의 file·line·quote 중 하나라도 비었다
  V5 예시를 지침으로 오인 — 인용이 전부 예시 구간 안인데 authority 가 지침
  V6 appliesTo 밖 적용 — appliedTo 경로가 appliesTo.paths(glob) 나 languages(확장자) 밖이다
  S  스키마 — authority·axis 목록 밖 · 근거 레코드 없는 축 값 · gaps·conflicts 어디에도 없는 미확인 축

exit: 0=충족 · 1=위반 · 2=측정 실패(⛔ 통과 아님 — 관례 레코드인데 --project 가 없을 때 포함)
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import pathlib
import re
import subprocess
import sys
import tempfile

OK, VIOLATION, UNRUN = 0, 1, 2
EXTRACTOR = pathlib.Path(__file__).resolve().parent / "extract_project_rules.py"

AXES = ["architecturePattern", "uiStack", "dependencyDirection", "naming", "placement", "conventions"]
ARCH_AXES = AXES[:4]                       # plan 워크플로가 읽는 archConstraints 4축
AUTHORITIES = {"지침", "관례", "예시"}
LANG_EXT = {".swift": "swift", ".m": "objc", ".mm": "objc", ".kt": "kotlin", ".java": "java", ".ts": "typescript",
            ".tsx": "typescript", ".js": "javascript", ".jsx": "javascript", ".py": "python", ".go": "go",
            ".rs": "rust", ".rb": "ruby", ".cs": "csharp", ".dart": "dart", ".c": "c", ".h": "c", ".cpp": "cpp"}

# 예시 구간 표지 — ⛔ modules/project-rules.md §5 와 같은 정의다(Claude·GPT 가 같은 표지로 판별한다)
EX_HEADING = re.compile(r"예시|\b[Ee]xamples?\b")
EX_PAREN = re.compile(r"\((?:예|예시|e\.g\.|eg\.|Example|For example)\s*[:,)]?[^()]*\)")
EX_LINE = re.compile(r"^[ \t]*(?:[-*+][ \t]+|\d+[.)][ \t]+)?((?:예|예시)[:)]|e\.g\.|Example:|For example).*$", re.M)
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


class Unrun(Exception):
    pass


def load_json(path: str):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Unrun(f"JSON 을 읽을 수 없다 — {path}: {e}")


# ── 인용 위치 대조 ─────────────────────────────────────────────────
def occurrences(text: str, quote: str, first_line: int) -> list:
    """quote 가 text 안에서 차지하는 (시작 줄, 끝 줄, 시작 오프셋, 끝 오프셋) 목록."""
    out, at = [], text.find(quote)
    while quote and at >= 0:
        start = first_line + text.count("\n", 0, at)
        out.append((start, start + quote.count("\n"), at, at + len(quote)))
        at = text.find(quote, at + 1)
    return out


def example_spans(section: dict) -> list:
    """절 본문(quote) 안의 예시 구간 (시작, 끝) 오프셋 — 병합 전."""
    body = section["quote"]
    if section.get("heading") and EX_HEADING.search(section["heading"]):
        return [(0, len(body))]
    spans, fence_at, pos = [], None, 0
    for ln in body.split("\n"):
        if FENCE.match(ln):
            if fence_at is None:
                fence_at = pos
            else:
                spans.append((fence_at, pos + len(ln)))
                fence_at = None
        pos += len(ln) + 1
    if fence_at is not None:
        spans.append((fence_at, len(body)))
    spans += [m.span() for m in EX_PAREN.finditer(body)]
    spans += [m.span(1)[:1] + (m.end(),) for m in EX_LINE.finditer(body)]
    return spans


def inside(spans: list, a: int, b: int) -> bool:
    """[a, b) 가 병합한 예시 구간 하나에 통째로 들어가는가."""
    merged = []
    for s, e in sorted(spans):
        if merged and s <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return any(s <= a and b <= e for s, e in merged)


def locate_in_index(index: dict, src: dict):
    """지침 인용을 색인에서 찾는다 → (절, 발생 위치) 또는 (None, 사유)."""
    f, line, quote = src.get("file"), src.get("line"), src.get("quote")
    secs = [s for s in index["sections"] if s["file"] == f]
    here = [s for s in secs if s["line"] <= line <= s["endLine"]]
    for s in here:
        if s.get("heading") and quote in s["heading"] and line == s["line"]:
            return s, None                                   # heading 문구 자체를 인용
        if s["bodyLine"] is not None:
            for occ in occurrences(s["quote"], quote, s["bodyLine"]):
                if occ[0] <= line <= occ[1]:
                    return s, occ
    elsewhere = [s for s in secs if quote in s["quote"] or (s.get("heading") and quote in s["heading"])]
    return None, (f"인용문은 {f} 의 다른 줄에 있다(인용 줄 {line})" if elsewhere else f"인용문이 {f} 에 없다")


def locate_in_project(project: pathlib.Path, src: dict):
    p = project / src["file"]
    if not p.is_file():
        return f"관례 인용 파일이 저장소에 없다 — {src['file']}"
    occ = occurrences(p.read_text(encoding="utf-8", errors="replace"), src["quote"], 1)
    if not occ:
        return f"인용문이 {src['file']} 에 없다"
    if not any(o[0] <= src["line"] <= o[1] for o in occ):
        return f"인용문은 {src['file']} 의 다른 줄에 있다(인용 줄 {src['line']})"
    return None


def source_missing(src) -> bool:
    return not isinstance(src, dict) or not src.get("file") or not isinstance(src.get("line"), int) or not src.get("quote")


# ── --check ────────────────────────────────────────────────────────
def check(rules: dict, index: dict, project) -> list:
    v = []
    guide_files = set(index.get("files", []))
    axes = rules.get("axes") or {}
    conflicts = rules.get("conflicts") or []
    gaps = set(rules.get("gaps") or [])
    conflict_axes = {c.get("axis") for c in conflicts}
    rule_axes = set()

    for r in rules.get("rules") or []:
        rid, src, auth = r.get("id", "?"), r.get("source"), r.get("authority")
        if auth not in AUTHORITIES:
            v.append(f"S  {rid}: authority {auth!r} 는 {sorted(AUTHORITIES)} 밖이다")
            continue
        if r.get("axis") not in AXES:
            v.append(f"S  {rid}: axis {r.get('axis')!r} 는 {AXES} 밖이다")
        rule_axes.add(r.get("axis"))
        if source_missing(src):
            v.append(f"V4 {rid}: 출처 없는 규칙 — source 의 file·line·quote 가 모두 있어야 한다")
            continue
        if auth == "관례":
            if project is None:
                raise Unrun(f"{rid}: 관례 레코드는 코드 인용이라 --project 없이 확인할 수 없다")
            why = locate_in_project(project, src)
            if why:
                v.append(f"V1 {rid}: 지어낸 인용 — {why}")
        else:
            if index.get("absent"):
                v.append(f"V3 {rid}: 지침 부재인데 {auth} 레코드 — 색인에 지침 파일이 없다")
                continue
            if src["file"] not in guide_files:
                v.append(f"V3 {rid}: {auth} 레코드가 지침 파일 밖({src['file']})을 인용한다")
                continue
            sec, occ = locate_in_index(index, src)
            if sec is None:
                v.append(f"V1 {rid}: 지어낸 인용 — {occ}")
                continue
            if auth == "지침" and occ is not None and inside(example_spans(sec), occ[2], occ[3]):
                v.append(f"V5 {rid}: 예시를 지침으로 오인 — 인용이 전부 예시 구간 안이다(authority 는 예시여야 한다)")
        langs = set((r.get("appliesTo") or {}).get("languages") or [])
        globs = (r.get("appliesTo") or {}).get("paths") or []
        for path in r.get("appliedTo") or []:
            if globs and not any(fnmatch.fnmatchcase(path, g) for g in globs):
                v.append(f"V6 {rid}: appliesTo.paths {globs} 밖 경로에 적용 — {path}")
            if langs and LANG_EXT.get(pathlib.PurePosixPath(path).suffix) not in langs:
                v.append(f"V6 {rid}: appliesTo.languages {sorted(langs)} 밖 언어에 적용 — {path}")

    for c in conflicts:
        ax = c.get("axis")
        if axes.get(ax) is not None:
            v.append(f"V2 상충 축 {ax} 에 값 {axes.get(ax)!r} — 자동 승자를 고르지 않는다(null 이어야 한다)")
        srcs = c.get("sources") or []
        if len(srcs) < 2:
            v.append(f"S  상충 {ax}: 출처가 둘 이상이어야 한다")
        for s in srcs:
            if source_missing(s) or s["file"] not in guide_files:
                v.append(f"V4 상충 {ax}: 출처가 비었거나 지침 파일 밖이다 — {s}")
                continue
            sec, why = locate_in_index(index, s)
            if sec is None:
                v.append(f"V1 상충 {ax}: 지어낸 인용 — {why}")

    for ax in AXES:
        if axes.get(ax) is None:
            if ax not in gaps and ax not in conflict_axes:
                v.append(f"S  미확인 축 {ax} 가 gaps 에 없다(Probe Coverage Gap 으로 남긴다)")
        elif ax not in rule_axes:
            v.append(f"S  축 {ax} 의 값 {axes.get(ax)!r} 에 근거 레코드가 없다")
    return v


# ── --project-arch · --compare · --fixtures ────────────────────────
def project_arch(rules: dict) -> dict:
    axes = rules.get("axes") or {}
    out = {ax: axes.get(ax) for ax in ARCH_AXES}
    out["conflicts"] = [c for c in rules.get("conflicts") or [] if c.get("axis") in ARCH_AXES]
    return out


def compare(a: dict, b: dict) -> str | None:
    if a == b:
        return None
    for k in ("schemaVersion", "absent", "files"):
        if a.get(k) != b.get(k):
            return f"{k}: {a.get(k)!r} ≠ {b.get(k)!r}"
    sa, sb = a.get("sections", []), b.get("sections", [])
    for i, (x, y) in enumerate(zip(sa, sb)):
        if x != y:
            key = next(k for k in sorted(set(x) | set(y)) if x.get(k) != y.get(k))
            return f"sections[{i}] ({x.get('file')} L{x.get('line')}) {key}: {x.get(key)!r} ≠ {y.get(key)!r}"
    return f"절 수 {len(sa)} ≠ {len(sb)}"


def extract_to(project: pathlib.Path) -> dict:
    r = subprocess.run([sys.executable, str(EXTRACTOR), "--project", str(project)], capture_output=True, text=True)
    if r.returncode != 0:
        raise Unrun(f"추출기 exit {r.returncode} — {r.stderr.strip()[-200:]}")
    return json.loads(r.stdout)


def fixtures(qdir: pathlib.Path) -> int:
    goldens = sorted(qdir.glob("*/expected-index.json"))
    if not goldens:
        print(f"UNRUN: golden 이 0개다 — {qdir} (측정 대상 0 은 통과가 아니다)")
        return UNRUN
    bad = 0
    with tempfile.TemporaryDirectory(prefix="fz-rules-fixtures-") as tmp:
        for g in goldens:
            fx = g.parent
            dest = pathlib.Path(tmp) / fx.name
            b = subprocess.run(["bash", str(fx / "build-repo.sh"), str(dest)], capture_output=True, text=True)
            if b.returncode != 0:
                print(f"UNRUN: {fx.name} 저장소 복원 실패 — {b.stderr.strip()[-160:]}")
                return UNRUN
            diff = compare(extract_to(dest), load_json(str(g)))
            print(f"{'FIXTURE OK  ' if diff is None else 'FIXTURE FAIL'} {fx.name}{'' if diff is None else ' — ' + diff}")
            bad += diff is not None
    print(f"fixtures {len(goldens) - bad}/{len(goldens)} OK")
    return OK if bad == 0 else VIOLATION


# ── self-test ──────────────────────────────────────────────────────
MINI_CLAUDE = ("# Mini — 지침\n\n## Naming\n\n- 서버 응답을 파싱하는 타입은 `…DTO` 접미사를 쓴다\n"
               "- 공용 유틸을 다시 만들지 않는다(예: `Debouncer`)\n\n## 예시\n\n- `WatchlistItemDTO` 처럼 쓴다\n")
MINI_AGENTS = "# Mini — 에이전트 지침\n\n## Naming\n\n- 서버 응답 타입은 `…Response` 접미사로 통일한다\n"


def positive_rules() -> dict:
    rule = lambda rid, axis, auth, f, line, q, **kw: dict(  # noqa: E731
        {"id": rid, "axis": axis, "authority": auth, "condition": "c", "expectedResult": "e",
         "appliesTo": {"languages": ["swift"], "paths": ["Sources/**"]},
         "source": {"file": f, "line": line, "quote": q}, "appliedTo": ["Sources/Feature/FooService.swift"]}, **kw)
    return {
        "schemaVersion": 1,
        "axes": {"architecturePattern": None, "uiStack": None, "dependencyDirection": None, "naming": None,
                 "placement": None, "conventions": "공용 유틸을 다시 만들지 않는다"},
        "rules": [
            rule("R1", "naming", "지침", "CLAUDE.md", 5, "서버 응답을 파싱하는 타입은 `…DTO` 접미사를 쓴다"),
            rule("R2", "naming", "지침", "AGENTS.md", 5, "서버 응답 타입은 `…Response` 접미사로 통일한다"),
            rule("R3", "conventions", "지침", "CLAUDE.md", 6, "공용 유틸을 다시 만들지 않는다(예: `Debouncer`)"),
            rule("R4", "conventions", "예시", "CLAUDE.md", 6, "(예: `Debouncer`)"),
            rule("R5", "conventions", "관례", "Sources/Feature/FooService.swift", 1, "final class FooService"),
        ],
        "conflicts": [{"axis": "naming", "claim_a": "…DTO", "claim_b": "…Response",
                       "sources": [{"file": "CLAUDE.md", "line": 5, "quote": "`…DTO` 접미사"},
                                   {"file": "AGENTS.md", "line": 5, "quote": "`…Response` 접미사"}]}],
        "gaps": ["architecturePattern", "uiStack", "dependencyDirection", "placement"],
    }


def self_test() -> int:
    results = []

    def case(name, ok, got=""):
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name}{'' if ok else f' — {got}'}")

    with tempfile.TemporaryDirectory(prefix="fz-rules-check-") as tmp:
        t = pathlib.Path(tmp)
        proj = t / "proj"
        (proj / "Sources" / "Feature").mkdir(parents=True)
        (proj / "CLAUDE.md").write_text(MINI_CLAUDE, encoding="utf-8")
        (proj / "AGENTS.md").write_text(MINI_AGENTS, encoding="utf-8")
        (proj / "Sources" / "Feature" / "FooService.swift").write_text("final class FooService {}\n", encoding="utf-8")
        index = extract_to(proj)
        empty = t / "empty"
        empty.mkdir()
        absent = extract_to(empty)

        def run(rules, idx=index, project=proj):
            try:
                return OK if not check(rules, idx, project) else VIOLATION, check(rules, idx, project)
            except Unrun as e:
                return UNRUN, [str(e)]

        code, v = run(positive_rules())
        case("⛔ 양성 대조 — 여섯 거부를 모두 통과하는 레코드는 exit 0", code == OK, v)

        def mutated(fn):
            r = positive_rules()
            fn(r)
            return r

        negatives = [
            ("V1 지어낸 인용", "V1", lambda r: r["rules"][0]["source"].update(quote="서버 응답은 무조건 DTO 로 한다")),
            ("V1 맞는 문장 · 틀린 줄", "V1", lambda r: r["rules"][0]["source"].update(line=6)),
            ("V1 관례 인용이 코드에 없다", "V1", lambda r: r["rules"][4]["source"].update(quote="class BarService")),
            ("V2 상충 축에 값", "V2", lambda r: r["axes"].update(naming="…DTO")),
            ("V4 출처 없는 규칙", "V4", lambda r: r["rules"][0].pop("source")),
            ("V5 예시(괄호)를 지침으로", "V5", lambda r: r["rules"][3].update(authority="지침")),
            ("V5 예시 절을 지침으로", "V5", lambda r: r["rules"].append(dict(r["rules"][0], id="R6", source={
                "file": "CLAUDE.md", "line": 10, "quote": "`WatchlistItemDTO` 처럼 쓴다"}))),
            ("V6 appliesTo.paths 밖", "V6", lambda r: r["rules"][0].update(appliedTo=["Tests/FooServiceTests.swift"])),
            ("V6 appliesTo.languages 밖", "V6", lambda r: r["rules"][0].update(appliedTo=["Sources/web/app.ts"])),
            ("S 근거 없는 축 값", "S ", lambda r: r["axes"].update(placement="Domain/{Feature}/")),
            ("S 미확인 축이 gaps 에 없다", "S ", lambda r: r["gaps"].remove("placement")),
        ]
        for name, key, fn in negatives:
            code, v = run(mutated(fn))
            case(f"거부: {name}", code == VIOLATION and any(x.startswith(key) for x in v), f"exit {code} {v}")

        code, v = run({"schemaVersion": 1, "axes": {}, "gaps": AXES, "conflicts": [],
                       "rules": [positive_rules()["rules"][0]]}, idx=absent)
        case("거부: V3 지침 부재인데 지침 레코드", code == VIOLATION and any(x.startswith("V3") for x in v), f"exit {code} {v}")
        code, v = run(mutated(lambda r: r["rules"][0]["source"].update(file="Sources/Feature/FooService.swift")))
        case("거부: V3 지침이 지침 파일 밖을 인용", code == VIOLATION and any(x.startswith("V3") for x in v), f"exit {code} {v}")
        code, v = run(positive_rules(), project=None)
        case("⛔ 관례 레코드인데 --project 없음 → UNRUN(통과 아님)", code == UNRUN, f"exit {code} {v}")

        arch = project_arch(mutated(lambda r: r["conflicts"].append(
            {"axis": "placement", "claim_a": "a", "claim_b": "b", "sources": []})))
        case("투영 — 키는 4축 + conflicts, conflicts 는 4축 것만",
             list(arch) == ARCH_AXES + ["conflicts"] and [c["axis"] for c in arch["conflicts"]] == ["naming"], json.dumps(arch, ensure_ascii=False))

        me = pathlib.Path(__file__).resolve()
        (t / "a.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        (t / "b.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")   # 공백만 다르다
        changed = json.loads(json.dumps(index))
        changed["sections"][1]["line"] += 1
        (t / "c.json").write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
        r_same = subprocess.run([sys.executable, str(me), "--compare", str(t / "a.json"), str(t / "b.json")], capture_output=True, text=True)
        r_diff = subprocess.run([sys.executable, str(me), "--compare", str(t / "a.json"), str(t / "c.json")], capture_output=True, text=True)
        case("--compare 는 구조 비교 — 공백만 다르면 OK · 줄이 다르면 exit 1",
             r_same.returncode == OK and r_diff.returncode == VIOLATION and "line" in r_diff.stdout, f"{r_same.returncode} {r_diff.returncode} {r_diff.stdout[-120:]}")

    print(f"self-test {sum(results)}/{len(results)} passed")
    return OK if all(results) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--compare", nargs=2, metavar=("EXTRACTED", "GOLDEN"))
    ap.add_argument("--check", metavar="RULES")
    ap.add_argument("--index")
    ap.add_argument("--project")
    ap.add_argument("--project-arch", metavar="RULES")
    ap.add_argument("--fixtures", metavar="QUALITY_DIR")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    try:
        if a.self_test:
            return self_test()
        if a.compare:
            diff = compare(load_json(a.compare[0]), load_json(a.compare[1]))
            print("COMPARE OK" if diff is None else f"COMPARE FAIL — {diff}")
            return OK if diff is None else VIOLATION
        if a.check:
            if not a.index:
                raise Unrun("--check 에는 --index 가 필요하다")
            project = pathlib.Path(a.project).expanduser().resolve() if a.project else None
            rules = load_json(a.check)
            v = check(rules, load_json(a.index), project)
            for x in v:
                print(f"  ⛔ {x}")
            print(f"VIOLATION {len(v)}건" if v else f"CHECK OK (rules {len(rules.get('rules') or [])} · conflicts {len(rules.get('conflicts') or [])})")
            return VIOLATION if v else OK
        if a.project_arch:
            print(json.dumps(project_arch(load_json(a.project_arch)), ensure_ascii=False))
            return OK
        if a.fixtures:
            return fixtures(pathlib.Path(a.fixtures).expanduser())
    except Unrun as e:
        print(f"UNRUN: {e}")
        return UNRUN
    ap.print_help(sys.stderr)
    return UNRUN


if __name__ == "__main__":
    sys.exit(main())
