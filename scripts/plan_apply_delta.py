#!/usr/bin/env python3
# lint:no-root-anchor — 반영할 lean2 반환 JSON 을 인자로 받는다(플러그인 루트의 파일을 읽지 않는다).
"""plan-lean2 델타 반영 (S21) — 병합 콜의 delta 를 plan 에 Step id 로 붙인다. 본문은 다시 쓰지 않는다.

lean2 병합 콜은 델타 전용 스키마(MergeSchema)라 계획 본문을 쓸 수 없다. 그 델타를 계획에 옮기는 기계 작업 —
id 검증 · Step 별 귀속 · 출처 표시 · unresolved 보존 — 만 여기서 한다. ⛔ stepAmendments.change 는 400자 자유 텍스트라
Step 본문을 결정론으로 고칠 수 없다. 본문을 어떻게 고칠지는 Lead 가 이 표를 보고 정한다.

  stepAmendments   stepId 로 그 Step 의 amendments[] 에 붙인다(field · change · reason · source) — 모르는 id 는 거부(새 Step 금지)
  addedEdgeCases   affectedStep 으로 그 Step 의 edgeCases[] 에 붙인다 — 모르는 id 는 거부
  addedImpact      readScope 에 없던 파일만 더하고 출처를 plan.addedImpact[] 에 남긴다. ⛔ writeScope 로 옮기지 않는다
                   (읽기 범위를 쓰기 범위로 자동 번역하지 않는다 — lean2 PlanSchema §Y)
  unresolved       plan.unresolved[] 로 보존한다 — 사용자 보고 대상이라 버리지 않는다
  멱등             같은 델타를 두 번 적용해도 결과가 같다(항목 키로 중복을 막는다)

모드
  --result FILE [--out FILE] [--table FILE]   lean2 반환(plan + delta) → 반영한 반환 JSON(--out) · Step 별 귀속 표(--table, 없으면 stdout)
  --self-test

exit: 0=반영(delta 가 null 이면 그대로) · 1=거부(모르는 Step id · field enum 밖) · 2=입력 불가(⛔ 통과 아님 — plan.steps 없음 · JSON 아님)
실패하면 어떤 파일도 쓰지 않는다.
"""
from __future__ import annotations

import argparse
import copy
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

OK, REJECT, UNRUN = 0, 1, 2
FIELDS = ("title", "files", "verify", "approach")   # lean2 MergeSchema stepAmendments.field enum
SOURCE = "lean2-merge"


class InputError(Exception):
    """입력 불가 — exit 2."""


class Reject(Exception):
    """델타가 계획 밖을 가리킨다 — exit 1."""


def step_ids(result) -> list:
    if not isinstance(result, dict):
        raise InputError("입력이 JSON 객체가 아니다")
    plan = result.get("plan")
    if not isinstance(plan, dict) or not isinstance(plan.get("steps"), list) or not plan["steps"]:
        raise InputError("plan.steps 가 없다 — lean2 반환(workflow-result.json)을 준다")
    ids = [s.get("id") if isinstance(s, dict) else None for s in plan["steps"]]
    if not all(isinstance(i, str) and i for i in ids):
        raise InputError("Step 마다 id 가 있어야 한다")
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise InputError(f"Step id 중복 — {dup}")
    return ids


def validate(delta: dict, ids: list) -> None:
    unknown, bad = [], []
    for k in ("stepAmendments", "addedEdgeCases", "addedImpact", "unresolved"):
        v = delta.get(k)
        if v is not None and (not isinstance(v, list) or (k != "unresolved" and not all(isinstance(x, dict) for x in v))):
            raise InputError(f"delta.{k} 형식이 다르다 — 배열{'' if k == 'unresolved' else '(객체)'}이어야 한다")
    for a in delta.get("stepAmendments") or []:
        if a.get("stepId") not in ids:
            unknown.append(f"stepAmendments → {a.get('stepId')!r}")
        if a.get("field") not in FIELDS:
            bad.append(f"{a.get('stepId')}: {a.get('field')!r}")
    for e in delta.get("addedEdgeCases") or []:
        if e.get("affectedStep") not in ids:
            unknown.append(f"addedEdgeCases {e.get('id')} → {e.get('affectedStep')!r}")
    for im in delta.get("addedImpact") or []:
        if not isinstance(im.get("file"), str) or not im["file"].strip():
            bad.append(f"addedImpact 에 file 이 없다: {im}")
    if unknown:
        raise Reject("모르는 Step id — 델타는 새 Step 을 만들 수 없다: " + " · ".join(unknown))
    if bad:
        raise Reject(f"델타 형식 밖 — field 는 {' · '.join(FIELDS)} 중 하나다: " + " · ".join(bad))


def add_once(items: list, item, key) -> None:
    if all(key(x) != key(item) for x in items):
        items.append(item)


def apply(result) -> dict:
    """반영한 반환 사본. 입력은 바꾸지 않는다."""
    ids = step_ids(result)
    delta = result.get("delta")
    out = copy.deepcopy(result)
    if delta is None:
        return out
    if not isinstance(delta, dict):
        raise InputError("delta 가 객체가 아니다")
    validate(delta, ids)
    plan = out["plan"]
    steps = {s["id"]: s for s in plan["steps"]}
    for a in delta.get("stepAmendments") or []:
        add_once(steps[a["stepId"]].setdefault("amendments", []),
                 {"field": a["field"], "change": a.get("change", ""), "reason": a.get("reason", ""), "source": SOURCE},
                 lambda x: (x.get("field"), x.get("change"), x.get("reason")))
    for e in delta.get("addedEdgeCases") or []:
        add_once(steps[e["affectedStep"]].setdefault("edgeCases", []),
                 {"id": e.get("id"), "case": e.get("case", ""), "source": SOURCE},
                 lambda x: (x.get("id"), x.get("case")))
    read = plan.setdefault("readScope", [])
    for im in delta.get("addedImpact") or []:
        f = im["file"].strip()
        already = f in read
        if not already:
            read.append(f)
        add_once(plan.setdefault("addedImpact", []),
                 {"file": f, "why": im.get("why", ""), "source": SOURCE, "alreadyInScope": already}, lambda x: x.get("file"))
    for u in delta.get("unresolved") or []:
        add_once(plan.setdefault("unresolved", []), u, lambda x: x)
    return out


def cell(text) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def table(applied: dict) -> str:
    plan = applied["plan"]
    lines = ["# 델타 반영 — Step 별 귀속", ""]
    if applied.get("delta") is None:
        lines += ["델타 없음 — 병합 콜 결과가 null 이다(계획은 그대로다).", ""]
    lines += ["| Step | 제목 | 수정 지시 | 경계 사례 |", "|---|---|---|---|"]
    for s in plan["steps"]:
        am = [a for a in s.get("amendments", []) if a.get("source") == SOURCE]
        ec = [e for e in s.get("edgeCases", []) if e.get("source") == SOURCE]
        lines.append(f"| {s['id']} | {cell(s.get('title', ''))} | {' · '.join(a['field'] for a in am) or '—'} | "
                     f"{' · '.join(str(e.get('id')) for e in ec) or '—'} |")
    amended = [(s["id"], a) for s in plan["steps"] for a in s.get("amendments", []) if a.get("source") == SOURCE]
    if amended:
        lines += ["", "## 수정 지시 — 본문 반영은 Lead 가 한다", ""]
        lines += [f"- {sid} · {a['field']} — {cell(a['change'])} (근거: {cell(a['reason'])})" for sid, a in amended]
    edges = [(s["id"], e) for s in plan["steps"] for e in s.get("edgeCases", []) if e.get("source") == SOURCE]
    if edges:
        lines += ["", "## 경계 사례", ""] + [f"- {sid} · {e.get('id')} — {cell(e.get('case', ''))}" for sid, e in edges]
    impact = [i for i in plan.get("addedImpact", []) if i.get("source") == SOURCE]
    if impact:
        lines += ["", f"## 더한 영향 범위 — readScope 에 편입(출처 {SOURCE} · writeScope 는 그대로)", ""]
        lines += [f"- `{i['file']}` — {cell(i['why'])}" + (" (이미 readScope 에 있었다)" if i.get("alreadyInScope") else "") for i in impact]
    if plan.get("unresolved"):
        lines += ["", "## 사용자 판단 필요 (unresolved)", ""] + [f"- {cell(u)}" for u in plan["unresolved"]]
    return "\n".join(lines).rstrip() + "\n"


def run(a) -> int:
    try:
        result = json.loads(pathlib.Path(a.result).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"UNRUN: 입력을 읽지 못했다 — {e}", file=sys.stderr)
        return UNRUN
    try:
        applied = apply(result)
    except InputError as e:
        print(f"UNRUN: {e}", file=sys.stderr)
        return UNRUN
    except Reject as e:
        print(f"REJECT: {e}", file=sys.stderr)
        return REJECT
    text = table(applied)
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps(applied, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if a.table:
        pathlib.Path(a.table).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return OK


# ── self-test ──────────────────────────────────────────────────────────────
def sample():
    return {"mode": "workflow", "plan": {
        "steps": [{"id": "S1", "title": "모델 추가", "files": ["src/a.swift"], "verify": {"kind": "manual", "criterion": "c"}},
                  {"id": "S2", "title": "화면 연결", "files": ["src/b.swift"], "verify": {"kind": "manual", "criterion": "c"}}],
        "readScope": ["src/a.swift", "src/b.swift"], "writeScope": [{"file": "src/a.swift", "rationale": "r"}],
        "rtm": [{"reqId": "R1", "requirement": "r", "stepId": "S1", "verify": "v", "status": "pending"}]},
        "delta": {"stepAmendments": [{"stepId": "S2", "field": "files", "change": "src/c.swift 추가", "reason": "E1 이 요구"}],
                  "addedEdgeCases": [{"id": "E1", "case": "빈 목록", "affectedStep": "S2"}],
                  "addedImpact": [{"file": "src/c.swift", "why": "두 번째 소비자"}, {"file": "src/a.swift", "why": "중복"}],
                  "unresolved": ["캐시 정책은 사용자 결정"]}}


def self_test() -> int:
    passed = total = 0

    def case(name, ok, detail=""):
        nonlocal passed, total
        total += 1
        passed += bool(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f" — {detail}"))

    def raises(fn, exc):
        try:
            fn()
        except exc:
            return True
        return False

    def t_amend():
        out = apply(sample())
        s1, s2 = out["plan"]["steps"]
        case("amendments — stepAmendments 를 그 Step 에 붙이고 본문(title · files · verify)은 그대로 둔다",
             s2["amendments"] == [{"field": "files", "change": "src/c.swift 추가", "reason": "E1 이 요구", "source": SOURCE}]
             and s2["files"] == ["src/b.swift"] and s2["title"] == "화면 연결" and "amendments" not in s1, s2)

    def t_edge():
        s2 = apply(sample())["plan"]["steps"][1]
        case("edge-cases — addedEdgeCases 를 affectedStep 에 붙인다", s2["edgeCases"] == [{"id": "E1", "case": "빈 목록", "source": SOURCE}], s2)

    def t_unknown():
        a = sample()
        a["delta"]["stepAmendments"][0]["stepId"] = "S9"
        b = sample()
        b["delta"]["addedEdgeCases"][0]["affectedStep"] = "S7"
        case("unknown-step — 모르는 stepId · affectedStep 은 거부(새 Step 금지)", raises(lambda: apply(a), Reject) and raises(lambda: apply(b), Reject))

    def t_field():
        a = sample()
        a["delta"]["stepAmendments"][0]["field"] = "body"
        case("field-enum — title · files · verify · approach 밖의 field 는 거부", raises(lambda: apply(a), Reject))

    def t_impact():
        p = apply(sample())["plan"]
        case("impact — readScope 에 없던 파일만 더하고 출처를 남긴다 · writeScope 는 그대로",
             p["readScope"] == ["src/a.swift", "src/b.swift", "src/c.swift"] and p["writeScope"] == [{"file": "src/a.swift", "rationale": "r"}]
             and [(i["file"], i["source"], i["alreadyInScope"]) for i in p["addedImpact"]]
             == [("src/c.swift", SOURCE, False), ("src/a.swift", SOURCE, True)], p)

    def t_unresolved():
        case("unresolved — 사용자 판단 항목을 plan.unresolved 로 보존한다", apply(sample())["plan"]["unresolved"] == ["캐시 정책은 사용자 결정"])

    def t_idem():
        once = apply(sample())
        twice = apply(once)
        case("idempotent — 같은 델타를 두 번 적용해도 결과가 같다", json.dumps(once, sort_keys=True) == json.dumps(twice, sort_keys=True))

    def t_pure():
        src = sample()
        before = json.dumps(src, sort_keys=True)
        apply(src)
        case("pure — 입력 객체를 바꾸지 않는다", json.dumps(src, sort_keys=True) == before)

    def t_null():
        a = sample()
        a["delta"] = None
        out = apply(a)
        case("no-delta — delta 가 null 이면 계획은 그대로이고 표가 그 사실을 적는다",
             out["plan"] == sample()["plan"] and "델타 없음" in table(out))

    def t_input():
        bad = [{}, {"plan": {}}, {"plan": {"steps": []}}, {"plan": {"steps": [{"id": "S1"}, {"id": "S1"}]}}, [1]]
        case("input — plan.steps 없음 · 빈 steps · id 중복 · 객체 아님은 입력 불가", all(raises(lambda b=b: apply(b), InputError) for b in bad))

    def t_table():
        t = table(apply(sample()))
        case("table — Step 마다 한 행 · 수정 지시 · 경계 사례 · 더한 영향 · unresolved 가 표에 있다",
             "| S1 | 모델 추가 | — | — |" in t and "| S2 | 화면 연결 | files | E1 |" in t and "`src/c.swift`" in t
             and "캐시 정책은 사용자 결정" in t and "(이미 readScope 에 있었다)" in t, t)

    def t_cli():
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="plan-apply-delta-"))
        try:
            def cli(obj, raw=None):
                f = tmp / "in.json"
                f.write_text(raw if raw is not None else json.dumps(obj, ensure_ascii=False), encoding="utf-8")
                for p in ("out.json", "table.md"):
                    (tmp / p).unlink(missing_ok=True)
                r = subprocess.run([sys.executable, __file__, "--result", str(f), "--out", str(tmp / "out.json"), "--table", str(tmp / "table.md")],
                                   capture_output=True, text=True)
                return r.returncode, sorted(p.name for p in tmp.glob("*.*") if p.name != "in.json")
            ok = cli(sample())
            bad = sample()
            bad["delta"]["stepAmendments"][0]["stepId"] = "S9"
            rej = cli(bad)
            emp = cli(None, raw="")
            case("cli-exit — 반영 0 · 거부 1 · 빈 입력 2 · 실패하면 파일 0개",
                 ok == (0, ["out.json", "table.md"]) and rej == (1, []) and emp == (2, []), (ok, rej, emp))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    for t in (t_amend, t_edge, t_unknown, t_field, t_impact, t_unresolved, t_idem, t_pure, t_null, t_input, t_table, t_cli):
        try:
            t()
        except Exception as e:   # ⛔ 케이스 안의 예외는 FAIL 로 센다 — 크래시로 끝나면 몇 건이 안 돌았는지 모른다
            case(f"{t.__name__} — 예외", False, repr(e))
    print(f"self-test {passed}/{total} passed")
    return OK if passed == total else REJECT


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--result")
    ap.add_argument("--out")
    ap.add_argument("--table")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.result:
        print("UNRUN: --result 가 필요하다 (또는 --self-test)", file=sys.stderr)
        return UNRUN
    return run(a)


if __name__ == "__main__":
    sys.exit(main())
