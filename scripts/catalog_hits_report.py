#!/usr/bin/env python3
"""catalog_hits_report.py — 점검 카탈로그 적중 집계(round 3 S3) — 경로마다 기록 상태 · 항목별 hit · clear · unchecked 수.

입력은 산출물 파일들이다 — .json(워크플로 반환 · GPT 출력의 catalogHits) · .md(light Lead 산출물의 `## 점검 카탈로그 판정` 표).
경로 이름은 파일 이름이다. 상태는 셋이다.
  recorded        배열 · 표가 있다(빈 배열 = 해당 항목 없음)
  null-unchecked  GPT 출력이 null — 카탈로그 블록을 못 받은 경로다. ⛔ 0건으로 세지 않고 경로 단위 unchecked 로 센다
  off             키 · 표가 없다 — 기록 스위치가 꺼진 산출물(집계 밖)
판정(효과가 있었나)은 이 표로 하지 않는다 — S10 측정 엔트리 하나로 모은다.
사용: catalog_hits_report.py FILE…   ·   --self-test      (exit 0 · 2 읽기 실패 — ⛔ 2 는 통과 아님)
Python 3.9 stdlib 전용.
"""
# lint:no-root-anchor — 입력 산출물은 인자로 받고 형제 모듈(check_catalog_hits)만 읽는다(플러그인 루트를 쓰지 않는다)
from __future__ import annotations

import json
import os
import sys
import tempfile
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_catalog_hits import VERDICTS, md_table  # noqa: E402 — 표 읽기 규칙을 검사기와 같이 쓴다


def path_hits(path: str):
    """(상태, 항목 목록) — 읽기 실패는 OSError · ValueError 로 올린다."""
    text = open(path, encoding="utf-8").read()
    if path.endswith(".json"):
        doc = json.loads(text)
        if not isinstance(doc, dict) or "catalogHits" not in doc:
            return "off", []
        hits = doc["catalogHits"]
        if hits is None:
            return "null-unchecked", []
        return "recorded", [h for h in hits if isinstance(h, dict)] if isinstance(hits, list) else []
    rows = md_table(text)
    return ("off", []) if rows is None else ("recorded", rows)


def report(files) -> tuple:
    """(경로 행 목록, 항목별 Counter, 상태 Counter)."""
    paths, per_id, states = [], {}, Counter()
    for f in files:
        state, items = path_hits(f)
        states[state] += 1
        c = Counter(str(it.get("verdict")) for it in items)
        paths.append((os.path.basename(f), state, c))
        for it in items:
            per_id.setdefault(str(it.get("catalogId", it.get("id"))), Counter())[str(it.get("verdict"))] += 1
    return paths, per_id, states


def render(paths, per_id, states) -> list:
    out = ["| 경로 | 상태 | " + " | ".join(VERDICTS) + " |", "|---|---|" + "---|" * len(VERDICTS)]
    out += [f"| {n} | {s} | " + " | ".join(str(c[v]) for v in VERDICTS) + " |" for n, s, c in paths]
    out += ["", "| id | " + " | ".join(VERDICTS) + " |", "|---|" + "---|" * len(VERDICTS)]
    out += [f"| {i} | " + " | ".join(str(c[v]) for v in VERDICTS) + " |" for i, c in sorted(per_id.items())]
    out.append(f"경로 {len(paths)} — recorded {states['recorded']} · null-unchecked {states['null-unchecked']}(카탈로그 블록 미수신 — 경로 단위 unchecked)"
               f" · off {states['off']}(기록 스위치 꺼짐 — 집계 밖)")
    return out


def self_test() -> int:
    results = []

    def case(name, ok, got=""):
        results.append(bool(ok))
        print(f"PASS {name}" if ok else f"FAIL {name} — {got}")

    with tempfile.TemporaryDirectory() as t:
        def put(name, doc):
            p = os.path.join(t, name)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(doc if isinstance(doc, str) else json.dumps(doc))
            return p
        hit = {"catalogId": "F-005", "target": "a.py:3", "verdict": "hit"}
        files = [put("gpt-null.json", {"verdict": "approved", "catalogHits": None}), put("live.json", {"catalogHits": [hit]}),
                 put("off.json", {"mode": "workflow"}), put("empty.json", {"catalogHits": []}),
                 put("light.md", "## 점검 카탈로그 판정\n\n| id | target | verdict |\n|---|---|---|\n| F-005 | b.py:9 | clear |\n")]
        paths, per_id, states = report(files)
        st = {n: s for n, s, _c in paths}
        text = "\n".join(render(paths, per_id, states))
        case("r3-catalog-report-null-is-unchecked — GPT 의 null 은 0건이 아니라 경로 단위 unchecked 다(빈 배열 · 꺼진 산출물과 갈린다)",
             st == {"gpt-null.json": "null-unchecked", "live.json": "recorded", "off.json": "off", "empty.json": "recorded", "light.md": "recorded"}
             and states["null-unchecked"] == 1 and "| gpt-null.json | null-unchecked |" in text, st)
        case("catalog-report-per-id — 항목별 판정 수를 경로를 가로질러 더한다",
             dict(per_id.get("F-005", {})) == {"hit": 1, "clear": 1}, {k: dict(v) for k, v in per_id.items()})
    print(f"self-test {sum(results)}/{len(results)} passed (catalog_hits_report)")
    return 0 if all(results) else 1


def main(argv) -> int:
    if argv[:1] == ["--self-test"]:
        return self_test()
    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    try:
        res = report(argv)
    except (OSError, ValueError) as e:
        print(f"UNRUN: 읽지 못했다 — {type(e).__name__}: {e} (⛔ 통과 아님)")
        return 2
    print("\n".join(render(*res)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
