#!/usr/bin/env python3
"""하네스 원장 모집단 대조 — 원장이 하네스 구성요소를 빠짐없이, 없는 것 없이 담는가.

원장(구성요소 · 로드 조건 · 비용 · 고유 발견 · 판정)은 사람이 쓰므로 처음부터 빠진 구성요소를 스스로 찾지 못한다
(자기 원장에서 범주 하나를 지워 보는 시험은 원래 없던 것을 못 잡는다 — F-493). 그래서 모집단은 원장이 아니라
**파일 탐색과 등록 정보**에서 유도하고 원장과 양방향으로 대조한다.

모집단 (id 형식)
  skill:<이름>          skills/*/SKILL.md            ref:<스킬>/<파일>   skills/*/references/*.md
  module:<이름>         modules/*.md                 guide:<이름>        guides/*.md
  agent:<이름>          agents/*.md                  workflow:<이름>     workflows/*.js
  gpt-skill:<이름>      gpt-skills/*/SKILL.md        template:<이름>     templates/*
  schema:<이름>         schemas/*.json               kind:<이름>         scripts/gpt-kinds.json 의 kinds

usage:
  harness_census.py [--root R] --list                 모집단 id 를 한 줄씩
  harness_census.py [--root R] --check-ledger L.json  missing(모집단 − 원장) · extra(원장 − 모집단)
  harness_census.py [--root R] --init-ledger L.json   모집단으로 원장 뼈대를 쓴다(이미 있으면 거부)
  harness_census.py --self-test
원장 형식: {"schema": 1, "components": [{"id", "load", "cost_tokens", "unique_findings", "verdict", "note"}]}
exit: 0 차이 0 · 1 차이 있음 · 2 입력 오류
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
LEDGER_SCHEMA = 1

GLOBS = [   # (id 접두, glob, 이름 뽑기)
    ("skill", "skills/*/SKILL.md", lambda p: os.path.basename(os.path.dirname(p))),
    ("ref", "skills/*/references/*.md", lambda p: f"{os.path.basename(os.path.dirname(os.path.dirname(p)))}/{os.path.basename(p)}"),
    ("module", "modules/*.md", lambda p: os.path.basename(p)[:-3]),
    ("guide", "guides/*.md", lambda p: os.path.basename(p)[:-3]),
    ("agent", "agents/*.md", lambda p: os.path.basename(p)[:-3]),
    ("workflow", "workflows/*.js", lambda p: os.path.basename(p)[:-3]),
    ("gpt-skill", "gpt-skills/*/SKILL.md", lambda p: os.path.basename(os.path.dirname(p))),
    ("template", "templates/*", lambda p: os.path.basename(p)),
    ("schema", "schemas/*.json", lambda p: os.path.basename(p)[:-5]),
]


def census(root):
    """-> {id: path or registry} — 파일 탐색 + 등록 정보."""
    out = {}
    for prefix, pattern, name in GLOBS:
        for p in sorted(glob.glob(os.path.join(root, pattern))):
            if os.path.isfile(p):
                out[f"{prefix}:{name(p)}"] = os.path.relpath(p, root)
    reg = os.path.join(root, "scripts", "gpt-kinds.json")
    if os.path.isfile(reg):
        for k in json.load(open(reg, encoding="utf-8")).get("kinds", {}):
            out[f"kind:{k}"] = "scripts/gpt-kinds.json"
    return out


def cost_tokens(root, rel):
    p = os.path.join(root, rel)
    if rel == "scripts/gpt-kinds.json" or not os.path.isfile(p):
        return None
    return round(len(open(p, encoding="utf-8", errors="replace").read()) / 4)   # 문자/4 근사 — measure_constraint_load 와 같은 단위


def load_ledger(path):
    d = json.load(open(path, encoding="utf-8"))
    if d.get("schema") != LEDGER_SCHEMA or not isinstance(d.get("components"), list):
        raise ValueError(f"ledger schema != {LEDGER_SCHEMA} or no components list")
    ids = [c.get("id") for c in d["components"]]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise ValueError(f"duplicate ids in ledger: {dup[:5]}")
    return set(ids)


def check(root, ledger_path):
    pop, led = set(census(root)), load_ledger(ledger_path)
    missing, extra = sorted(pop - led), sorted(led - pop)
    return missing, extra


def init_ledger(root, path):
    if os.path.exists(path):
        raise FileExistsError(path)
    pop = census(root)
    comps = [{"id": i, "load": "unmeasured", "cost_tokens": cost_tokens(root, rel), "unique_findings": "unmeasured",
              "verdict": "keep", "note": ""} for i, rel in sorted(pop.items())]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    json.dump({"schema": LEDGER_SCHEMA, "components": comps}, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return len(comps)


def self_test():
    cases, fails = [], []

    def case(name, ok, why=""):
        cases.append(f"{name}: {'PASS' if ok else 'FAIL'}" + ("" if ok else f" {why}"))
        if not ok:
            fails.append(name)

    with tempfile.TemporaryDirectory() as d:
        for rel in ("skills/a/SKILL.md", "skills/a/references/x.md", "modules/m.md", "agents/g.md", "workflows/w.js"):
            os.makedirs(os.path.join(d, os.path.dirname(rel)), exist_ok=True)
            open(os.path.join(d, rel), "w").write("x" * 40)
        os.makedirs(os.path.join(d, "scripts"))
        json.dump({"kinds": {"review": {}}}, open(os.path.join(d, "scripts", "gpt-kinds.json"), "w"))
        led = os.path.join(d, "ledger.json")
        n = init_ledger(d, led)
        m, e = check(d, led)
        case("clean", n == 6 and not m and not e, f"n={n} missing={m} extra={e}")
        open(os.path.join(d, "modules", "new.md"), "w").write("y")
        m, e = check(d, led)
        case("missing-component", m == ["module:new"] and not e, f"missing={m} extra={e}")
        os.remove(os.path.join(d, "modules", "new.md"))
        os.remove(os.path.join(d, "agents", "g.md"))
        m, e = check(d, led)
        case("extra-component", e == ["agent:g"] and not m, f"missing={m} extra={e}")
    print("\n".join(cases))
    print(f"harness_census self-test: {'PASS' if not fails else 'FAIL'} ({len(cases) - len(fails)}/{len(cases)})")
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="하네스 원장 모집단 대조")
    ap.add_argument("--root", default=ROOT)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--check-ledger", metavar="LEDGER")
    g.add_argument("--init-ledger", metavar="LEDGER")
    g.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if a.list:
        for i in sorted(census(a.root)):
            print(i)
        return 0
    try:
        if a.init_ledger:
            print(f"ledger written: {init_ledger(a.root, a.init_ledger)} components")
            return 0
        missing, extra = check(a.root, a.check_ledger)
    except (OSError, ValueError) as e:
        print(f"census: input error — {e}", file=sys.stderr)
        return 2
    for i in missing:
        print(f"MISSING {i}")
    for i in extra:
        print(f"EXTRA {i}")
    print(f"missing: {len(missing)} · extra: {len(extra)}")
    print(f"census diff: {len(missing) + len(extra)}")
    return 0 if not missing and not extra else 1


if __name__ == "__main__":
    sys.exit(main())
