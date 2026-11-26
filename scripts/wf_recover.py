#!/usr/bin/env python3
# lint:no-root-anchor — 읽는 폴더는 인자로 받는다(플러그인 루트를 참조하지 않는다)
"""wf_recover.py — 죽은 Workflow 워커의 산출물을 트랜스크립트에서 회수한다 (F-732).

왜: 한도 · 스톨로 끝난 워커는 journal 에 반환이 없다. 워커가 마지막에 낸 StructuredOutput 호출 입력은 그 워커의
`agent-*.jsonl` 에 남아 있어 손으로 회수했다. 실패 복구 사다리(`guides/skill-authoring.md` §12) L3 의 처방 보강이다 —
새 사다리 단계가 아니다.

⛔ 회수분은 반환이 아니다. 출력마다 `needs_lead_reverify: true` 를 단다 — Lead 가 스키마 · 근거를 다시 대조한 뒤에만 쓴다.

사용: python3 scripts/wf_recover.py <wf_* 폴더 절대 경로> [--out FILE]
exit: 0 = 1건 이상 회수 · 1 = 회수 0(StructuredOutput 호출 없음) · 2 = 폴더 · 파일을 읽지 못함(⛔ 통과 아님)
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import tempfile

OK, NONE, UNRUN = 0, 1, 2


def last_structured_output(path: str):
    """한 트랜스크립트의 마지막 StructuredOutput 호출 입력 — 없으면 None. 깨진 줄은 건너뛴다(셈은 돌려준다)."""
    found, bad = None, 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                ev = json.loads(line)
            except ValueError:
                bad += 1
                continue
            content = ((ev.get("message") or {}).get("content") or []) if isinstance(ev, dict) else []
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "StructuredOutput":
                    found = block.get("input")
    return found, bad


def recover(folder: str) -> tuple:
    if not os.path.isdir(folder):
        return UNRUN, [], f"폴더가 아니다 — {folder}"
    files = sorted(glob.glob(os.path.join(folder, "agent-*.jsonl")))
    if not files:
        return UNRUN, [], f"agent-*.jsonl 이 없다 — {folder}"
    out = []
    for path in files:
        try:
            got, bad = last_structured_output(path)
        except (OSError, UnicodeDecodeError) as e:
            return UNRUN, [], f"읽지 못했다 — {path} ({type(e).__name__})"
        meta = path[: -len(".jsonl")] + ".meta.json"
        agent_type = None
        if os.path.isfile(meta):
            try:
                agent_type = json.load(open(meta, encoding="utf-8")).get("agentType")
            except (OSError, ValueError):
                agent_type = None
        if got is not None:
            out.append({"agent": os.path.basename(path), "agentType": agent_type, "skipped_lines": bad,
                        "recovered": got, "needs_lead_reverify": True})
    return (OK if out else NONE), out, f"트랜스크립트 {len(files)} · 회수 {len(out)}"


def self_test() -> int:
    fails = []
    with tempfile.TemporaryDirectory() as d:
        so = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "StructuredOutput",
                                                             "input": {"findings": [1]}}]}}
        late = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t2", "name": "StructuredOutput",
                                                               "input": {"findings": [2]}}]}}
        other = {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "t3", "name": "Read", "input": {}}]}}
        with open(os.path.join(d, "agent-a.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(so) + "\n{깨진 줄\n" + json.dumps(late) + "\n")
        with open(os.path.join(d, "agent-a.meta.json"), "w", encoding="utf-8") as fh:
            json.dump({"agentType": "fz:review-arch"}, fh)
        with open(os.path.join(d, "agent-b.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(other) + "\n")
        rc, out, _ = recover(d)
        if not (rc == OK and len(out) == 1 and out[0]["recovered"] == {"findings": [2]} and out[0]["agentType"] == "fz:review-arch"
                and out[0]["skipped_lines"] == 1 and out[0]["needs_lead_reverify"] is True):
            fails.append(f"recover-last-structured-output: {rc} {out}")
        os.remove(os.path.join(d, "agent-a.jsonl"))
        rc, out, _ = recover(d)
        if rc != NONE:
            fails.append(f"no-structured-output-exit1: {rc}")
        rc, _, _ = recover(os.path.join(d, "absent"))
        if rc != UNRUN:
            fails.append(f"missing-folder-exit2: {rc}")
        os.remove(os.path.join(d, "agent-b.jsonl"))
        rc, _, _ = recover(d)
        if rc != UNRUN:
            fails.append(f"no-transcripts-exit2: {rc}")
    print(f"wf_recover self-test {4 - len(fails)}/4 passed")
    for f in fails:
        print(f"  FAIL {f}")
    return OK if not fails else NONE


def main() -> int:
    ap = argparse.ArgumentParser(description="죽은 Workflow 워커의 StructuredOutput 입력 회수 (F-732)")
    ap.add_argument("folder", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.folder:
        ap.error("wf_* 폴더가 필요하다 (또는 --self-test)")
    rc, out, note = recover(a.folder)
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    else:
        print(text)
    print(("UNRUN: " if rc == UNRUN else "") + note + (" — 회수분은 Lead 재검증 대상이다" if out else ""), file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
