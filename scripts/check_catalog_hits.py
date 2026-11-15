#!/usr/bin/env python3
"""check_catalog_hits.py — 점검 카탈로그 판정 기록이 제 모양으로 남았는가(round 3 S3 · PROMPT 15 — F-005 외).

산출물 종류마다 본다.
  · light Lead 산출물(.md) — `## 점검 카탈로그 판정` 절 아래 표(| id | target | verdict |)가 있다. id 는 카탈로그(--catalog)에 있는 것 ·
    verdict 는 hit · clear · unchecked 중 하나 · target 은 비지 않는다. 해당 없는 항목은 건너뛰므로 행 수는 세지 않는다(머리만 있어도 된다).
  · 워크플로 반환 · GPT 출력(.json) — `catalogHits` 키가 있다. 배열이면 항목마다 위 세 조건이고, null 은 "카탈로그 블록을 못 받은 경로"다
    (통과 — catalog_hits_report.py 가 경로별 unchecked 로 센다). 키가 없으면 기록 스위치가 꺼진 산출물이라 거부한다(켜고 낸 산출물만 넣는다).
사용: check_catalog_hits.py ARTIFACT --catalog TEMPLATE     (exit 0 통과 · 1 거부 · 2 사용법 · 읽기 실패 — ⛔ 2 는 통과 아님)
      check_catalog_hits.py --self-test
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
VERDICTS = ("hit", "clear", "unchecked")
HEADING = re.compile(r"^#{2,4}\s*점검 카탈로그 판정\s*$", re.M)
CATALOG_ROW = re.compile(r"^\| (F-\d{3}[a-z]?) \|", re.M)
GPT_SCHEMAS = ("schemas/gpt_review_schema.json", "schemas/gpt_independent_plan_schema.json", "schemas/gpt_independent_review_schema.json")


def catalog_ids(template_text: str) -> set:
    return set(CATALOG_ROW.findall(template_text))


def md_table(text: str):
    """`## 점검 카탈로그 판정` 아래 첫 표 → [{id, target, verdict}] · 절이나 표 머리가 없으면 None."""
    m = HEADING.search(text)
    if not m:
        return None
    lines = text[m.end():].lstrip("\n").split("\n")
    if len(lines) < 2 or not lines[0].startswith("|") or not re.match(r"^\|[\s:|-]+\|$", lines[1].strip()):
        return None
    head = [c.strip().lower() for c in lines[0].strip().strip("|").split("|")]
    if head[:3] != ["id", "target", "verdict"]:
        return None
    rows = []
    for ln in lines[2:]:
        if not ln.startswith("|"):
            break
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        rows.append(dict(zip(("id", "target", "verdict"), (cells + ["", "", ""])[:3])))
    return rows


def bad_items(items, ids) -> list:
    out = []
    for k, it in enumerate(items):
        if not isinstance(it, dict):
            out.append(f"[{k}] 객체가 아니다")
            continue
        cid, tgt, ver = it.get("catalogId", it.get("id")), it.get("target"), it.get("verdict")
        if cid not in ids:
            out.append(f"[{k}] {cid!r} 는 카탈로그에 없는 id")
        if ver not in VERDICTS:
            out.append(f"[{k}] verdict {ver!r} — hit · clear · unchecked 중 하나")
        if not (isinstance(tgt, str) and tgt.strip()):
            out.append(f"[{k}] target 이 비었다")
    return out


def judge(path: str, ids: set) -> list:
    """거부 사유 목록 — 비면 통과. 읽기 실패는 OSError · ValueError 로 올린다."""
    text = open(path, encoding="utf-8").read()
    if path.endswith(".json"):
        doc = json.loads(text)
        if not isinstance(doc, dict) or "catalogHits" not in doc:
            return ["catalogHits 키가 없다 — 기록 스위치를 켜고 낸 산출물이 아니다"]
        hits = doc["catalogHits"]
        if hits is None:
            return []                                  # 카탈로그 블록을 못 받은 경로 — 집계기가 unchecked 로 센다
        if not isinstance(hits, list):
            return [f"catalogHits 가 배열 · null 이 아니다({type(hits).__name__})"]
        return bad_items(hits, ids)
    rows = md_table(text)
    if rows is None:
        return ["`## 점검 카탈로그 판정` 절 아래 | id | target | verdict | 표가 없다"]
    return bad_items(rows, ids)


def schema_nullable(path: str) -> list:
    """GPT 스키마의 catalogHits — 필수 칸 · 배열 또는 null · 항목 세 칸(strict 출력은 선택 칸을 null 합집합으로 흉내 낸다)."""
    s = json.load(open(path, encoding="utf-8"))
    p = (s.get("properties") or {}).get("catalogHits")
    out = [] if "catalogHits" in (s.get("required") or []) else ["required 에 catalogHits 가 없다"]
    if not isinstance(p, dict):
        return out + ["properties.catalogHits 가 없다"]
    if sorted(p.get("type") or []) != ["array", "null"]:
        out.append(f"type {p.get('type')!r} — [\"array\", \"null\"] 이어야 한다")
    it = p.get("items") or {}
    if sorted(it.get("required") or []) != ["catalogId", "target", "verdict"] or it.get("additionalProperties") is not False:
        out.append("items 가 catalogId · target · verdict 필수 + additionalProperties false 가 아니다")
    if ((it.get("properties") or {}).get("verdict") or {}).get("enum") != list(VERDICTS):
        out.append("verdict enum 이 hit · clear · unchecked 가 아니다")
    return out


def self_test() -> int:
    results = []

    def case(name, ok, got=""):
        results.append(bool(ok))
        print(f"PASS {name}" if ok else f"FAIL {name} — {got}")

    ids = {"F-005", "F-027"}
    with tempfile.TemporaryDirectory() as t:
        def put(name, body):
            p = os.path.join(t, name)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body if isinstance(body, str) else json.dumps(body))
            return p
        good = put("good.md", "# 플랜\n\n## 점검 카탈로그 판정\n\n| id | target | verdict |\n|---|---|---|\n| F-005 | a.py:3 | hit |\n| F-027 | 세션 키 | clear |\n")
        empty = put("empty.md", "## 점검 카탈로그 판정\n\n| id | target | verdict |\n|---|---|---|\n\n본문\n")
        bad = {"no-table": put("a.md", "# 플랜\n본문\n"), "unknown-id": put("b.md", "## 점검 카탈로그 판정\n| id | target | verdict |\n|---|---|---|\n| F-999 | x | hit |\n"),
               "bad-verdict": put("c.md", "## 점검 카탈로그 판정\n| id | target | verdict |\n|---|---|---|\n| F-005 | x | maybe |\n"),
               "empty-target": put("d.md", "## 점검 카탈로그 판정\n| id | target | verdict |\n|---|---|---|\n| F-005 |  | clear |\n")}
        got = {k: judge(v, ids) for k, v in bad.items()}
        case("r3-catalog-artifact-table-checked — light 산출물 판정 표가 없거나 · 모르는 id · verdict 밖 · 빈 target 이면 거부 · 머리만 있는 표는 통과",
             judge(good, ids) == [] and judge(empty, ids) == [] and all(got.values()), {k: bool(v) for k, v in got.items()})
        j = {"null": put("n.json", {"catalogHits": None}), "arr": put("y.json", {"catalogHits": [{"catalogId": "F-005", "target": "a.py:3", "verdict": "clear"}]}),
             "missing": put("m.json", {"verdict": "approved"}), "bad": put("x.json", {"catalogHits": [{"catalogId": "F-005", "target": "t", "verdict": "yes"}]})}
        jg = {k: judge(v, ids) for k, v in j.items()}
        case("r3-catalog-json-key-required — catalogHits 키가 없으면 거부 · null 은 통과(미수신 경로) · 항목은 같은 세 조건",
             jg["null"] == [] and jg["arr"] == [] and jg["missing"] and jg["bad"], {k: bool(v) for k, v in jg.items()})
    probs = {}
    for rel in GPT_SCHEMAS:
        try:
            probs[rel] = schema_nullable(os.path.join(ROOT, rel))
        except (OSError, ValueError) as e:
            probs[rel] = [f"읽지 못했다 {type(e).__name__}"]
    case("r3-catalog-gpt-schema-required-nullable — GPT 스키마 셋의 catalogHits 가 필수 칸이고 값은 배열 또는 null",
         not any(probs.values()), {k: v for k, v in probs.items() if v})
    print(f"self-test {sum(results)}/{len(results)} passed (check_catalog_hits)")
    return 0 if all(results) else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("artifact", nargs="?")
    ap.add_argument("--catalog")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if not (a.artifact and a.catalog):
        ap.error("ARTIFACT 와 --catalog 가 필요하다")
    try:
        ids = catalog_ids(open(a.catalog, encoding="utf-8").read())
        probs = judge(a.artifact, ids)
    except (OSError, ValueError) as e:
        print(f"UNRUN: 읽지 못했다 — {type(e).__name__}: {e} (⛔ 통과 아님)")
        return 2
    if not ids:
        print(f"UNRUN: 카탈로그 {a.catalog} 에서 id 를 하나도 못 읽었다 (⛔ 통과 아님)")
        return 2
    for p in probs:
        print(f"REJECT {p}")
    if not probs:
        print(f"OK 점검 카탈로그 판정 기록 — {os.path.basename(a.artifact)}")
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
