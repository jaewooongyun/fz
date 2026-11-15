#!/usr/bin/env python3
# lint:no-root-anchor — 트랜스크립트 경로를 인자로 받는 계측기라 플러그인 루트를 해석하지 않는다
"""세션 하나가 실제로 읽어 들인 하네스 분량을 층별로 잰다 — 정적 floor 가 못 보는 실측.

`measure_constraint_load.py` 는 참조 지시를 정적으로 세서 "부르면 드는 비용"의 상·하한을 추정한다(SKILL 본문은 빼고 · 조건 휴리스틱).
이 도구는 트랜스크립트 하나에서 **실제로 들어온 것**을 센다.

층 (단위: 문자/4 근사 토큰 — measure_constraint_load 와 같은 단위)
  body        스킬 본문 — "Base directory for this skill:" 로 시작하는 user 텍스트
  references  Read 결과 중 플러그인 참조 문서(skills/*/references · modules · guides · agents · templates) 첫 읽기
  injection   워커 · 하위 에이전트에 실어 보낸 프롬프트 — Agent · Task · Workflow 도구 입력
  read        Read 결과 전부의 첫 읽기(파일마다 1회)
  reread      같은 파일을 다시 Read 한 결과
⛔ `api-request-blob` 줄은 같은 내용의 중복이라 세지 않는다 — user · assistant 줄만 본다.

usage: measure_runtime_load.py --transcript T.jsonl [--out OUT.json]   →  표 + `layers: 5/5`
       measure_runtime_load.py --self-test
exit: 0 측정 · 2 입력 오류
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile

LAYERS = ("body", "references", "injection", "read", "reread")
PLUGIN_DOC = re.compile(r"/(skills/[^/]+/references|modules|guides|agents|templates)/[^/]+\.md$")
INJECT_TOOLS = {"Agent", "Task", "Workflow"}


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
    return ""


def measure(path):
    chars = dict.fromkeys(LAYERS, 0)
    pending, seen, counts = {}, set(), dict.fromkeys(("skills", "reads", "rereads", "injections"), 0)
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") not in ("user", "assistant"):
            continue
        content = (e.get("message") or {}).get("content")
        items = content if isinstance(content, list) else [{"type": "text", "text": content}] if isinstance(content, str) else []
        for x in items:
            if not isinstance(x, dict):
                continue
            if e["type"] == "user" and x.get("type") == "text" and str(x.get("text", "")).startswith("Base directory for this skill:"):
                chars["body"] += len(x["text"])
                counts["skills"] += 1
            elif x.get("type") == "tool_use" and x.get("name") == "Read":
                pending[x.get("id")] = (x.get("input") or {}).get("file_path", "")
            elif x.get("type") == "tool_use" and x.get("name") in INJECT_TOOLS:
                chars["injection"] += len(json.dumps(x.get("input") or {}, ensure_ascii=False))
                counts["injections"] += 1
            elif x.get("type") == "tool_result" and x.get("tool_use_id") in pending:
                fp, n = pending.pop(x["tool_use_id"]), len(_text(x.get("content")))
                if fp in seen:
                    chars["reread"] += n
                    counts["rereads"] += 1
                else:
                    seen.add(fp)
                    chars["read"] += n
                    counts["reads"] += 1
                    if PLUGIN_DOC.search(fp):
                        chars["references"] += n
    layers = {k: round(v / 4) for k, v in chars.items()}
    return {"transcript": os.path.abspath(path), "transcript_sha256": hashlib.sha256(open(path, "rb").read()).hexdigest(),
            "unit": "chars/4", "layers": layers, "counts": counts}


def self_test():
    cases, fails = [], []

    def case(name, ok, why=""):
        cases.append(f"{name}: {'PASS' if ok else 'FAIL'}" + ("" if ok else f" {why}"))
        if not ok:
            fails.append(name)

    lines = [
        {"type": "user", "message": {"content": [{"type": "text", "text": "Base directory for this skill: /p/skills/x\n" + "b" * 39}]}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "r1", "name": "Read", "input": {"file_path": "/p/modules/m.md"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "r1", "content": "m" * 40}]}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "r2", "name": "Read", "input": {"file_path": "/p/modules/m.md"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "r2", "content": [{"type": "text", "text": "m" * 40}]}]}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "r3", "name": "Read", "input": {"file_path": "/repo/a.py"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "r3", "content": "a" * 80}]}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "w1", "name": "Workflow", "input": {"x": "y" * 30}}]}},
        {"type": "api-request-blob", "message": {"content": [{"type": "tool_result", "tool_use_id": "r3", "content": "z" * 400}]}},
    ]
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.jsonl")
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(json.dumps(x) for x in lines))
        m = measure(p)
    L, c = m["layers"], m["counts"]
    case("body", L["body"] == 20 and c["skills"] == 1, f"{L['body']} {c}")
    case("read-first-only", L["read"] == 30 and c["reads"] == 2, f"{L['read']} {c}")
    case("reread", L["reread"] == 10 and c["rereads"] == 1, f"{L['reread']} {c}")
    case("references", L["references"] == 10, f"{L['references']}")
    case("injection", c["injections"] == 1 and L["injection"] > 0, f"{L['injection']} {c}")
    case("blob-ignored", L["read"] == 30, "api-request-blob line was counted")
    print("\n".join(cases))
    print(f"measure_runtime_load self-test: {'PASS' if not fails else 'FAIL'} ({len(cases) - len(fails)}/{len(cases)})")
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="세션이 실제로 읽어 들인 하네스 분량을 층별로")
    ap.add_argument("--transcript")
    ap.add_argument("--out")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if not a.transcript or not os.path.isfile(a.transcript):
        print("measure: --transcript 파일이 없다", file=sys.stderr)
        return 2
    m = measure(a.transcript)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        json.dump(m, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("layer        tokens(chars/4)")
    for k in LAYERS:
        print(f"{k:12} {m['layers'][k]:>8}")
    print("counts", json.dumps(m["counts"], ensure_ascii=False))
    print(f"layers: {sum(1 for k in LAYERS if k in m['layers'])}/{len(LAYERS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
