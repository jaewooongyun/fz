# lint:no-root-anchor — 플러그인 루트를 해석하지 않는다. 합성 기록은 호출자가 넘긴 임시 폴더에만 쓰고 형제 모듈만 import 한다 · 낱말-표 짝 칸만 형제 모듈 한 단계 위의 modules/symbol-tools-audit.md 를 읽는다.
"""fz_wf_metrics_selftest.py — fz_wf_metrics 의 self-test 와 합성 기록(probe). `fz_wf_metrics.py --self-test` 와
`fz_wf_metrics._write_probe` 가 부를 때만 이 모듈을 싣는다.

⛔ 계측기 지문(ab_ledger_base.INSTRUMENTS) 밖이다 — 측정 경로(collect · recollect · judge · show)는 이 모듈을 import 하지 않는다.
   사례 · 합성 기록만 고친 변경은 instrument_sha 를 바꾸지 않아 채점 행이 낡지 않는다. 판정 코드를 여기에 두지 않는다(지문 밖
   코드가 판정에 섞인다). fz_wf_metrics.py 가 모듈 머리에서 이 모듈을 실으면 tests/fixtures/ab/structure-d 의 fingerprint-coverage
   셀이 실패한다. 나눈 까닭: 계측기 파일 하나가 1500줄 상한(같은 fixture 의 split-size 셀)을 넘었다.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

import fz_wf_metrics as wfm   # 형제 모듈(판정 코드) — 이 모듈은 그 함수를 부르기만 한다. ⛔ 모듈 머리에서 wfm 의 이름을 읽지 않는다(순환 import)


def _write_probe(root: str, kind: str) -> None:
    """self-test · 단언 fixture — kind 별 합성 기록(정상 · 고장 · advisor 스톨 · 시도 · `--mcp-audit` 판정마다의 꼴)."""
    folder = os.path.join(root, "proj", "sess-probe", "subagents", "workflows", "wf_probe")
    os.makedirs(folder, exist_ok=True)
    if kind == "empty":
        return
    p = os.path.join(folder, "agent-a1.jsonl")
    if kind == "corrupt":
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("{not json at all\n")
        return
    if kind == "no-turns":
        # 완결 턴 0 — stop_reason 없음 + output_tokens 플레이스홀더. 반환은 journal 에만 있다.
        rows = [
            {"type": "user", "timestamp": "2026-09-11T00:00:00Z",
             "message": {"content": "[역할] 경계 케이스 발굴자 — CC 교차"}},
            {"type": "assistant", "timestamp": "2026-09-11T00:07:00Z",
             "message": {"content": [{"type": "tool_use", "id": "t1", "name": "StructuredOutput", "input": {}}],
                         "usage": {"output_tokens": 2}}},
        ]
        with open(p, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        with open(os.path.join(folder, "agent-a1.meta.json"), "w", encoding="utf-8") as fh:
            json.dump({"agentType": "fz:plan-edge-case", "model": "opus"}, fh)
        with open(os.path.join(folder, "journal.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "result", "agentId": "a1", "result": {"links": [{"sourceId": "E:E1", "finding": "x" * 500}], "additions": []}}, ensure_ascii=False) + "\n")
        return
    if kind == "sweep-effort":
        rows = [
            {"type": "user", "timestamp": "2026-09-11T00:00:00Z",
             "message": {"content": "[역할] 구조 설계자"}},
            {"type": "assistant", "timestamp": "2026-09-11T00:02:00Z",
             "message": {"stop_reason": "tool_use", "effort": "xhigh",
                         "content": [{"type": "tool_use", "id": "t1", "name": "StructuredOutput", "input": {}}],
                         "usage": {"output_tokens": 70, "output_tokens_details": {"thinking_tokens": 20}}}},
        ]
        with open(p, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        with open(os.path.join(folder, "agent-a1.meta.json"), "w", encoding="utf-8") as fh:
            json.dump({"agentType": "fz:plan-structure", "model": "opus"}, fh)
        with open(os.path.join(folder, "journal.jsonl"), "w", encoding="utf-8") as fh:
            fh.write('{"type": "result", "agentId": "a1", "result": "x"}\n')
        return
    if kind in ("stall", "resume", "no-resume"):
        # stall: advisor 호출 2(srvtoolu_A1 결과 2줄 중복 · srvtoolu_A2 결과 없음) — 실 블록 꼴(server_tool_use + 별도 줄 결과)
        # resume · no-resume: 같은 key 의 실패 시도(0~6000s) 뒤 재개 시도(50000~50600s) / 재개 없이 실패로 끝남
        def agent(name, rows, meta="fz:plan-structure"):
            with open(os.path.join(folder, f"agent-{name}.jsonl"), "w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            with open(os.path.join(folder, f"agent-{name}.meta.json"), "w", encoding="utf-8") as fh:
                json.dump({"agentType": meta, "model": "opus"}, fh)
        t = lambda sec: (datetime.datetime(2026, 10, 1) + datetime.timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%SZ")
        role = {"type": "user", "timestamp": t(0), "message": {"content": "[역할] 설계자 — 이 과제의 계획"}}
        if kind == "stall":
            call = lambda i: {"type": "server_tool_use", "id": f"srvtoolu_{i}", "name": "advisor", "input": {}}
            res = {"type": "advisor_tool_result", "tool_use_id": "srvtoolu_A1", "content": {"type": "advisor_result"}}
            agent("a1", [role] + [{"type": "assistant", "timestamp": t(sec), "message": {"id": "m1", "content": [b]}}
                                  for sec, b in ((10, call("A1")), (60, res), (60, res), (90, call("A2")))])
            journal = [{"type": "started", "key": "k1", "agentId": "a1"}]
        else:
            done = {"type": "assistant", "timestamp": t(50600),
                    "message": {"id": "m2", "stop_reason": "end_turn", "usage": {"output_tokens": 9}, "content": []}}
            agent("a1", [role, {"type": "assistant", "timestamp": t(6000), "message": {"id": "m1", "content": []}}])
            journal = [{"type": "started", "key": "k1", "agentId": "a1"}, {"type": "failed", "key": "k1", "agentId": "a1"}]
            if kind == "resume":
                agent("a2", [dict(role, timestamp=t(50000)), done])
                journal += [{"type": "started", "key": "k1", "agentId": "a2"},
                            {"type": "result", "key": "k1", "agentId": "a2", "result": "x"}]
        with open(os.path.join(folder, "journal.jsonl"), "w", encoding="utf-8") as fh:
            for ev in journal:
                fh.write(json.dumps(ev) + "\n")
        return
    if kind in ("mcp-arm", "mcp-arm-err", "mcp-nolabel", "mcp-othertree", "mcp-allerr", "mcp-uncovered", "mcp-nopath",
                "mcp-nonsymbol", "mcp-upper-ext", "mcp-folder", "mcp-extless", "mcp-noresult", "mcp-unanswered",
                "mcp-na-kind", "mcp-na-mixed", "mcp-direct", "mcp-sweep", "mcp-sweep-nostate", "mcp-sweep-latestate",
                "mcp-mixed-err", "mcp-impl-only", "mcp-decl-only", "mcp-info-othertree", "mcp-unrun-othertree", "mcp-dotted"):
        # 심볼 도구 결과 · 단계 라벨 · 다른 트리 표지 · 직접 호출 · 세션 훑기. 호출 = (도구, 지목한 파일 | None, 결과 | None) · 결과 = (is_error, 글)
        # · 결과가 None 이면 그 호출의 결과 줄을 쓰지 않는다(기록이 중간에 끊긴 꼴) · 글 자리에 블록 목록을 두면 그 목록이 결과 본문이다.
        # 결과 글은 Serena 의 실제 꼴이다 — 찾기는 JSON 목록(없으면 `[]`) · 오류는 is_error 없는 `Error…` 글.
        S = "mcp__plugin_fz_serena__"
        found = (False, '[{"name_path": "main", "relative_path": "scripts/run.sh", "body_location": {"start_line": 3}}]')
        no_project = (False, "Error: No active project. Ask the user to provide the project path or to select a project "
                             "from this list of known projects: []")
        no_tool = (True, "<tool_use_error>Error: No such tool available: mcp__plugin_fz_serena__find_symbol</tool_use_error>")
        ignored = lambda f: (False, f"Error executing tool: ValueError - The explicitly passed file {f} is ignored, not returning overview.")
        grep = ("Grep", None, (False, "scripts/run.sh:3:main() {"))
        read = ("Read", "scripts/run.sh", (False, "     3\tmain() {"))
        stamp = lambda m: f"2026-09-11T00:{m:02d}:00Z"

        def worker(dst, aid, meta, calls, minute=0, label=None, final="so", note=""):
            uses, results = [], []
            for i, (tool, target, res) in enumerate(calls, 1):
                tid = f"{aid}-t{i}"
                inp = ({"relative_path": target} if target else {"name_path_pattern": "main"}) if tool.startswith(S) else (
                    {"file_path": target} if tool == "Read" else {"skill": target} if tool == "Skill" else
                    {"libraryId": target, "query": "main"} if "context7" in tool else {"pattern": "main"})
                uses.append({"type": "tool_use", "id": tid, "name": tool, "input": inp})
                if res is None:
                    continue
                err, text = res
                results.append(dict({"type": "tool_result", "tool_use_id": tid,
                                     "content": text if err or not isinstance(text, str) else [{"type": "text", "text": text}]},
                                    **({"is_error": True} if err else {})))
            done = ({"type": "tool_use", "id": f"{aid}-so", "name": "StructuredOutput", "input": {"findings": [], "note": note}}
                    if final == "so" else {"type": "text", "text": f"검토를 마쳤다. {note}".strip()})
            rows = [{"type": "user", "timestamp": stamp(minute), "message": {"content": "[역할] 심볼 탐색자"}}]
            if uses:
                rows += [{"type": "assistant", "timestamp": stamp(minute), "message": {
                             "id": f"m-{aid}-1", "stop_reason": "tool_use", "content": uses, "usage": {"output_tokens": 40}}},
                         {"type": "user", "timestamp": stamp(minute + 1), "message": {"content": results}}]
            rows.append({"type": "assistant", "timestamp": stamp(minute + 1), "message": {
                "id": f"m-{aid}-2", "stop_reason": "tool_use" if final == "so" else "end_turn", "content": [done],
                "usage": {"output_tokens": 30}}})
            with open(os.path.join(dst, f"agent-{aid}.jsonl"), "w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            with open(os.path.join(dst, f"agent-{aid}.meta.json"), "w", encoding="utf-8") as fh:
                json.dump({"agentType": meta, "model": "sonnet"}, fh)
            return [dict({"type": "started", "key": f"k-{aid}", "agentId": aid}, **({"label": label} if label else {})),
                    {"type": "result", "key": f"k-{aid}", "agentId": aid, "result": {"findings": [], "note": note}}]

        if kind == "mcp-direct":
            # 같은 종류의 직접 호출 둘(앞 = 호출 있음 · 뒤 = 0회) + 다른 종류 둘(호출 있음 · 켜진 언어 파일에 전부 오류) —
            # 합쳐 세면 통과로 읽히는 꼴이다. 직접 호출은 journal 이 없고 세션의 subagents/ 에 바로 쌓인다
            direct = os.path.join(root, "proj", "sess-probe", "subagents")
            worker(direct, "d1", "fz:review-correctness", [(S + "find_symbol", "scripts/run.sh", found), read], 0, final="text")
            worker(direct, "d3", "general-purpose", [(S + "find_symbol", "scripts/run.sh", found)], 5, final="text")
            worker(direct, "d4", "fz:review-quality", [(S + "find_symbol", "scripts/run.sh", no_project),
                                                       (S + "find_referencing_symbols", "scripts/run.sh", no_project), read],
                   8, final="text")
            worker(direct, "d2", "fz:review-correctness", [read, grep], 10, final="text")
            return
        if kind.startswith("mcp-sweep"):
            # 세션 하나(root = 세션 기록 폴더)의 끝난 실행 넷 — 성공 1(워크플로) · 0회(워크플로) · 해당 없음(심볼 도구가 없는 종류의
            # 직접 호출 — fz 밖 스킬 호출 하나와 fz 스킬 호출 하나를 담는다) · 켜진 언어 파일에 전부 오류(직접 호출 — 일반 · 직접 호출 모드의
            # `mcp-allerr` 와 같은 입력). 상태 기록 `state/tools.md` 는 실행보다 먼저(mcp-sweep) · 없음(-nostate) · 실행 뒤에 고침(-latestate)
            sub = os.path.join(root, "subagents")
            c7 = ("mcp__context7__query-docs", "/example/lib", (False, "Example docs: main() starts the run."))
            for n, (wid, meta, calls) in enumerate((("wf_sw1", "fz:plan-structure", [(S + "find_symbol", "scripts/run.sh", found), c7, read]),
                                                  ("wf_sw2", "fz:plan-impact", [read, grep]))):
                dst = os.path.join(sub, "workflows", wid)
                os.makedirs(dst, exist_ok=True)
                with open(os.path.join(dst, "journal.jsonl"), "w", encoding="utf-8") as fh:
                    for ev in [{"type": "launched"}] + worker(dst, "a1", meta, calls, n * 4, "impact"):
                        fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
            skill = lambda name: ("Skill", name, (False, f"Launching skill: {name}"))
            worker(sub, "d1", "general-purpose", [read, skill("example-stack:example-skill"), skill("fz:fz-plan")], 8, final="text")
            worker(sub, "d2", "fz:review-quality", [(S + "find_symbol", "scripts/run.sh", no_project),
                                                    (S + "find_referencing_symbols", "scripts/run.sh", no_project), read], 12, final="text")
            if kind != "mcp-sweep-nostate":
                state = os.path.join(root, "state", "tools.md")
                os.makedirs(os.path.dirname(state), exist_ok=True)
                with open(state, "w", encoding="utf-8") as fh:
                    fh.write("Serena: active /tmp/x @abc1234 (languages: bash) · context7 목록✓ · sc 목록✓ · seq 목록✓ · pr-review 목록✓"
                             " · 스택 스킬 example-stack:example-skill\n")
                hour = 6 if kind == "mcp-sweep-latestate" else -24   # 실행(2026-09-11 00:00~)보다 뒤 · 앞
                t = (datetime.datetime(2026, 9, 11, tzinfo=datetime.timezone.utc) + datetime.timedelta(hours=hour)).timestamp()
                os.utime(state, (t, t))
            return
        sym_err =[(S + "find_symbol", "scripts/run.sh", no_tool), (S + "get_symbols_overview", "scripts/run.sh", no_project), grep]
        plan = {
            # 첫 탐색 = 글자 검색뿐(0회) · 교차 단계 = 결과가 돌아온 호출 — 같은 에이전트 종류라 라벨로만 갈린다
            "mcp-arm": [("a1", "fz:search-symbolic", [grep, read], "stage1-symbolic", ""),
                        ("a2", "fz:search-pattern", [grep], "stage1-pattern", ""),
                        ("a3", "fz:search-symbolic", [(S + "find_referencing_symbols", "scripts/run.sh", found)],
                         "stage2-sym-on-pat", "")],
            # 불렀으나 전부 오류 — 도구 오류(is_error) 하나 · Serena 오류 글 하나
            "mcp-arm-err": [("a1", "fz:search-symbolic", sym_err, "stage1-symbolic", ""),
                            ("a2", "fz:search-pattern", [grep], "stage1-pattern", "")],
            "mcp-nolabel": [("a1", "fz:search-symbolic", [grep], "stage1-symbolic", ""),
                            ("a2", "fz:search-symbolic", [grep], None, "")],
            # 첫 탐색 워커가 호출 둘에 성공하고 결과에 다른 트리 표지를 남겼다
            "mcp-othertree": [("a1", "fz:search-symbolic", [(S + "find_symbol", "scripts/run.sh", found),
                                                            (S + "find_referencing_symbols", "scripts/run.sh", found), read],
                               "stage1-symbolic", wfm.OTHER_TREE_MARK),
                              ("a2", "fz:search-pattern", [grep], "stage1-pattern", "")],
            # 다른 트리 표지를 산출에 남긴 워커 — 심볼 읽기가 아닌 Serena 호출(안내) 하나 뒤 · 호출 없이(-unrun-). 둘 다 도구 작업은 0 이다
            "mcp-info-othertree": [("a1", "fz:plan-impact", [(S + "initial_instructions", None, (False, "You are a professional coding agent."))],
                                    "impact", wfm.OTHER_TREE_MARK)],
            "mcp-unrun-othertree": [("a1", "fz:plan-impact", [], "impact", wfm.OTHER_TREE_MARK)],
            # 켜진 언어(bash)의 파일을 물었는데 전부 오류 — 프로젝트가 활성화되지 않았을 때의 꼴
            "mcp-allerr": [("a1", "fz:plan-impact", [(S + "find_symbol", "scripts/run.sh", no_project),
                                                     (S + "find_referencing_symbols", "scripts/run.sh", no_project), read],
                            "impact", "")],
            # 켜진 언어 밖의 파일만 물었고 전부 오류 — 언어 미지원 폴백
            "mcp-uncovered": [("a1", "fz:plan-impact", [(S + "get_symbols_overview", "scripts/report.py", ignored("scripts/report.py")),
                                                        (S + "get_symbols_overview", "workflows/pipeline.js",
                                                         ignored("workflows/pipeline.js")), read], "impact", "")],
            # 파일을 지정하지 않은 찾기 하나가 `[]` 를 돌려줬다 — 결과도 아니고 켜진 언어 파일의 오류도 아니다
            "mcp-nopath": [("a1", "fz:plan-impact", [(S + "find_symbol", None, (False, "[]")), grep], "impact", "")],
            # 심볼 읽기가 아닌 Serena 호출(안내) 하나는 성공 · 켜진 언어 파일을 물은 찾기 둘은 전부 오류
            "mcp-nonsymbol": [("a1", "fz:plan-impact", [(S + "initial_instructions", None, (False, "You are a professional coding agent.")),
                                                        (S + "find_symbol", "scripts/run.sh", no_project),
                                                        (S + "find_referencing_symbols", "scripts/run.sh", no_project), read],
                               "impact", "")],
            # 대문자 확장자의 켜진 언어 파일을 물었는데 오류
            "mcp-upper-ext": [("a1", "fz:plan-impact", [(S + "find_symbol", "scripts/RUN.SH", no_project), read], "impact", "")],
            # 폴더 · 확장자 없는 경로를 물었고 빈 결과 — 불명 대상
            "mcp-folder": [("a1", "fz:plan-impact", [(S + "find_symbol", "src/", (False, "[]")), read], "impact", "")],
            "mcp-extless": [("a1", "fz:plan-impact", [(S + "find_symbol", "scripts", (False, "[]")), read], "impact", "")],
            # 마지막 마디에 점이 든 폴더 이름(확장자 표 밖)을 물었고 오류 — 켜진 언어 밖 파일이 아니라 불명 대상
            "mcp-dotted": [("a1", "fz:plan-impact", [(S + "find_symbol", "vendor/gopkg.in/yaml.v3", ignored("vendor/gopkg.in/yaml.v3")), read],
                            "impact", "")],
            # 켜진 언어 파일을 물은 호출 하나가 결과 줄 없이 남았다(기록이 끊겼다) · 그 앞에 켜진 언어 밖 파일의 오류 하나(-unanswered)
            "mcp-noresult": [("a1", "fz:plan-impact", [(S + "find_symbol", "scripts/run.sh", None), read], "impact", "")],
            "mcp-unanswered": [("a1", "fz:plan-impact", [(S + "get_symbols_overview", "scripts/report.py", ignored("scripts/report.py")),
                                                         (S + "find_symbol", "scripts/run.sh", None), read], "impact", "")],
            # 심볼 도구가 없는 종류(글자 탐색 팔)의 워커뿐 · 그 워커와 정의 폴더에 없는 종류의 워커(-mixed)
            "mcp-na-kind": [("a1", "fz:search-pattern", [read, grep], "stage1-pattern", "")],
            "mcp-na-mixed": [("a1", "fz:search-pattern", [read, grep], "stage1-pattern", ""),
                             ("a2", "general-purpose", [grep], "impact", "")],
            # 켜진 언어 파일을 물은 찾기의 결과가 글이 아닌 블록(리소스) 하나 + Serena 오류 글 블록 하나다 — 오류 블록이 결과를 오류로 만든다
            "mcp-mixed-err": [("a1", "fz:plan-impact", [(S + "find_symbol", "scripts/run.sh", (False, [
                {"type": "resource", "resource": {"uri": "file:///tmp/x/scripts/run.sh", "mimeType": "text/x-sh", "text": "main() {"}},
                {"type": "text", "text": no_project[1]}])), read], "impact", "")],
            # 구현 찾기만 · 선언 찾기만 선언한 종류의 워커가 파일만 읽었다(정의 폴더는 셀이 따로 쓴다)
            "mcp-impl-only": [("a1", "fz:impl-correctness", [read, grep], "impact", "")],
            "mcp-decl-only": [("a1", "fz:review-correctness", [read, grep], "impact", "")],
        }[kind]
        journal = []
        for n, (aid, meta, calls, label, note) in enumerate(plan):
            journal += worker(folder, aid, meta, calls, n * 2, label, note=note)
        with open(os.path.join(folder, "journal.jsonl"), "w", encoding="utf-8") as fh:
            for ev in journal:
                fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
        return
    if kind in ("mcp-ok", "mcp-dead", "mcp-unrun", "mcp-nocontrol", "mcp-info", "mcp-info-read"):
        # ⛔ 여섯 픽스처는 **도구 호출 조합만** 다르다 — 판정이 그 조합에서만 갈리는지 보기 위해서다(mcp-ok 만 심볼 도구 결과 한 줄을 더 갖는다).
        calls = {"mcp-ok": [("mcp__plugin_fz_serena__find_symbol", "s1"), ("Read", "r1")],
                 "mcp-dead": [("Read", "r1"), ("Grep", "g1")],
                 "mcp-unrun": [],
                 # ⛔ 작업은 했지만 **대조 심볼이 없다** — 부재를 주장할 근거가 없는 경로
                 "mcp-nocontrol": [("Grep", "g1")],
                 # 심볼 읽기가 아닌 Serena 호출(안내) 하나뿐 · 그 호출과 파일 읽기 — 안내 호출은 도구 작업이 아니다
                 "mcp-info": [("mcp__plugin_fz_serena__initial_instructions", "i1")],
                 "mcp-info-read": [("Read", "r1"), ("mcp__plugin_fz_serena__initial_instructions", "i1")]}[kind]
        blocks = [{"type": "tool_use", "id": i, "name": nm, "input": {}} for nm, i in calls]
        blocks.append({"type": "tool_use", "id": "so1", "name": "StructuredOutput", "input": {}})
        rows = [
            {"type": "user", "timestamp": "2026-09-11T00:00:00Z",
             "message": {"content": "[역할] 심볼 탐색자"}},
            {"type": "assistant", "timestamp": "2026-09-11T00:01:00Z",
             "message": {"stop_reason": "tool_use", "content": blocks,
                         "usage": {"output_tokens": 50}}},
        ]
        if kind == "mcp-ok":   # 심볼 도구 호출에 결과(찾은 심볼)가 돌아왔다 — 판정은 결과를 돌려준 호출 수로 낸다
            rows.append({"type": "user", "timestamp": "2026-09-11T00:01:00Z", "message": {"content": [
                {"type": "tool_result", "tool_use_id": "s1",
                 "content": [{"type": "text", "text": '[{"name_path": "main", "relative_path": "scripts/run.sh"}]'}]}]}})
        with open(p, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        with open(os.path.join(folder, "agent-a1.meta.json"), "w", encoding="utf-8") as fh:
            json.dump({"agentType": "fz:search-symbolic", "model": "opus"}, fh)
        with open(os.path.join(folder, "journal.jsonl"), "w", encoding="utf-8") as fh:
            fh.write('{"type": "result", "agentId": "a1", "result": "x"}\n')
        return
    rows = [
        {"type": "user", "timestamp": "2026-09-11T00:00:00Z",
         "message": {"content": "[역할] 방향성 도전자(review-direction 렌즈)"}},
        {"type": "assistant", "timestamp": "2026-09-11T00:01:00Z",
         "message": {"stop_reason": "tool_use", "content": [
             {"type": "advisor_tool_result", "tool_use_id": "adv1"},
             {"type": "tool_use", "id": "t1", "name": "StructuredOutput", "input": {}}],
             "usage": {"output_tokens": 100, "output_tokens_details": {"thinking_tokens": 40},
                       "cache_read_input_tokens": 10, "cache_creation_input_tokens": 5}}},
        {"type": "assistant", "timestamp": "2026-09-11T00:01:30Z",
         "message": {"content": [{"type": "advisor_tool_result", "tool_use_id": "adv1"}]}},
    ]
    with open(p, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(folder, "agent-a1.meta.json"), "w", encoding="utf-8") as fh:
        json.dump({"agentType": "fz:review-direction", "model": "fable"}, fh)
    with open(os.path.join(folder, "journal.jsonl"), "w", encoding="utf-8") as fh:
        fh.write('{"type": "started", "agentId": "a1"}\n{"type": "result", "agentId": "a1", "result": "x"}\n')


def self_test() -> int:
    me = os.path.abspath(wfm.__file__)
    passed, fails = 0, []

    def run(kind, spec_runs, want_exit, want_text=None):
        nonlocal passed
        root = tempfile.mkdtemp(prefix="fzwf-")
        try:
            _write_probe(root, kind)
            fx = os.path.join(root, "expected.json")
            with open(fx, "w", encoding="utf-8") as fh:
                json.dump({"tolerance_seconds": 1.0, "runs": spec_runs}, fh)
            proc = subprocess.run([sys.executable, me, "--expect", fx, "--root", root],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
            out = (proc.stdout or b"").decode("utf-8", "replace")
            why = []
            if proc.returncode != want_exit:
                why.append(f"exit {proc.returncode} (기대 {want_exit})")
            if want_text and want_text not in out:
                why.append(f"출력에 {want_text!r} 없음: {out.strip()[:120]}")
            if why:
                fails.append(f"{kind}/{want_exit}: {'; '.join(why)}")
            else:
                passed += 1
        finally:
            shutil.rmtree(root, ignore_errors=True)

    good = [{"id": "probe", "session_glob": "sess-probe", "wf": "wf_probe",
             "wall_s": 90.0, "agents": 1, "advisor": 1}]
    # ① 정상: 값 일치 → METRICS_OK (advisor 는 중복 id 를 1로 센다 — 블록 2개, 고유 1개)
    run("good", good, 0, "METRICS_OK")
    # ② 값 불일치 → 실패 (조용한 통과 금지)
    run("good", [dict(good[0], wall_s=1.0)], 1, "wall")
    run("good", [dict(good[0], advisor=7)], 1, "advisor")
    # ③ 기록 없음 → unavailable + exit 1 (측정 실패를 0 으로 쓰지 않는다)
    run("good", [{"id": "missing", "session_glob": "nope*", "wf": "wf_none",
                  "wall_s": 1.0, "agents": 1, "advisor": 0}], 1, "unavailable")
    # ④ 빈 폴더 → agent 0건 → wall unavailable + exit 1
    run("empty", good, 1, "unavailable")
    # ⑤ 손상 jsonl → 파싱 불가 → exit 1
    run("corrupt", good, 1, None)
    # ⑥ runs 빈 배열 → 0/0 통과 금지
    run("good", [], 1, "runs 가 없다")
    # ⑦ ⛔ 완결 턴 없는 agent — 반환은 있는데 usage 가 플레이스홀더뿐이면 0 이 아니라 unavailable
    #    (실측 wf_00000000-006 S3-edge: 6,342자 반환 · out_tok 0 으로 인쇄됐다)
    root = tempfile.mkdtemp(prefix="fzwf-nt-")
    try:
        _write_probe(root, "no-turns")
        folder = os.path.join(root, "proj", "sess-probe", "subagents", "workflows", "wf_probe")
        wf = wfm.read_wf(folder)
        a = wf["agents"][0]
        if a["out_tok"] is None and a["result_chars"] and wf["tokens_partial"]:
            passed += 1
        else:
            fails.append(f"no-turns: out_tok={a['out_tok']} (기대 None) · result_chars={a.get('result_chars')} · partial={wf['tokens_partial']}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    # F-660 — 하네스가 전달한 사용자 요청을 워커마다 `--wf` 상세에 찍는다(전달이 없는 워커는 조용하다)
    root = tempfile.mkdtemp(prefix="fzwf-fw-")
    try:
        folder = os.path.join(root, "proj", "sess-probe", "subagents", "workflows", "wf_probe")
        os.makedirs(folder)
        req = {"type": "user", "timestamp": "2026-09-11T00:00:00Z",
               "message": {"content": "[Workflow harness — user request] The harness relays, verbatim and indented below, "
                                      "the user request that triggered this workflow run:\n  smoke 측정 해줘\n  둘째 줄"}}
        task = {"type": "user", "timestamp": "2026-09-11T00:00:01Z",
                "message": {"content": "[Workflow harness — computed task] script output\n[역할] 구조 설계자"}}
        stop = {"type": "assistant", "timestamp": "2026-09-11T00:01:00Z",
                "message": {"id": "m1", "stop_reason": "end_turn", "content": [], "usage": {"output_tokens": 5}}}
        for name, rows in (("agent-f1.jsonl", (req, task, stop)), ("agent-f2.jsonl", (task, stop))):
            with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
                fh.write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        a = wfm.read_agent(os.path.join(folder, "agent-f1.jsonl"))
        b = wfm.read_agent(os.path.join(folder, "agent-f2.jsonl"))
        proc = subprocess.run([sys.executable, me, "--wf", "wf_probe", "--root", root],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        out = (proc.stdout or b"").decode("utf-8", "replace")
        if (a["forwarded"] == "smoke 측정 해줘 둘째 줄" and a["role"].startswith("구조 설계자") and b["forwarded"] is None
                and out.count("전달 요청: 'smoke 측정 해줘 둘째 줄'") == 1):
            passed += 1
        else:
            fails.append(f"전달 요청: f1={a['forwarded']!r} role={a['role']!r} f2={b['forwarded']!r} 출력 {out.count('전달 요청')}줄")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    # ⑧~⑩ --mcp-audit 판정 — 도구 조합 · 결과 · 상태 기록 · 라벨 · 직접 호출만 바꿔 판정을 각각 확인한다(셀 이름 = mcp-audit/<이름>)
    tail = " · context7 목록✓ · sc 목록✓ · seq 목록✓ · pr-review 목록✓ · 스택 스킬 없음"
    states = {"active": "Serena: active /tmp/x @abc1234 (languages: bash)" + tail,
              "unused": "[Serena 미사용 — 미설치]" + tail,
              "old-tail": "[Serena 미사용 — 미설치] · context7 목록✓ · sc 목록✓",   # 옛 꼬리 — Serena 부분만 읽는다
              "unknown-lang": "Serena: active /tmp/x @abc1234 (languages: example-lang)" + tail,
              "bad": "not a state line"}

    def audit(name, kind, want_exit, want_text, extra=(), state=None, direct=False, prep=None):
        nonlocal passed
        r2 = tempfile.mkdtemp(prefix="fzwf-mcp-")
        try:
            _write_probe(r2, kind)
            try:
                if prep:
                    prep(r2)
            except OSError as exc:
                fails.append(f"mcp-audit/{name}: 준비 실패 {type(exc).__name__}")
                return
            argv =[sys.executable, me, "--mcp-audit", "--root", r2, "--session", "*"]
            argv += ["--direct"] if direct else ["--wf", "wf_probe"]
            argv += list(extra)
            if state:
                with open(os.path.join(r2, "tools.md"), "w", encoding="utf-8") as fh:
                    fh.write(states[state] + "\n")
                argv += ["--tools-md", os.path.join(r2, "tools.md")]
            proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, cwd=r2)
            out = (proc.stdout or b"").decode("utf-8", "replace")
            why = []
            if proc.returncode != want_exit:
                why.append(f"exit {proc.returncode} (기대 {want_exit})")
            if want_text not in out:
                why.append(f"출력에 {want_text!r} 없음: {out.strip()[:140]}")
            if why:
                fails.append(f"mcp-audit/{name}: " + " · ".join(why))
            else:
                passed += 1
        finally:
            shutil.rmtree(r2, ignore_errors=True)

    audit("mcp-ok", "mcp-ok", 0, "MCP_AUDIT_OK")
    # 상태 기록 없이 0회 · Read 있음 — 심볼 서버가 없는 머신과 배선 끊김을 가를 수 없어 미판정이다(의심은 활성 기록이 있을 때만 · tools-md-active)
    audit("mcp-dead", "mcp-dead", 2, "UNRUN: serena 0건 · Read 1건인데 상태 기록이 없다")
    audit("mcp-unrun", "mcp-unrun", 2, "도구 작업이 0건")
    audit("mcp-nocontrol", "mcp-nocontrol", 2, "대조 심볼")
    audit("result-kinds", "mcp-ok", 0, "serena 결과: 성공 1 · 오류 0 · 빈 결과 0")
    # 상태 기록(--tools-md) — 상태를 인자로 받지 않고 세션 시작 기록의 첫 줄에서 읽는다
    audit("tools-md-active", "mcp-dead", 1, "MCP_WIRING_SUSPECT", state="active")
    audit("tools-md-unused", "mcp-dead", 0, "MCP_FALLBACK (사유: 미설치)", state="unused")
    audit("tools-md-mismatch", "mcp-ok", 1, "MCP_STATE_MISMATCH", state="unused")
    audit("tools-md-bad", "mcp-dead", 2, "UNRUN: 상태 기록", state="bad")
    audit("tools-md-unrun", "mcp-unrun", 2, "도구 작업이 0건", state="unused")
    audit("tools-md-old-tail", "mcp-dead", 0, "MCP_FALLBACK (사유: 미설치)", state="old-tail")
    # 심볼 읽기가 아닌 Serena 호출(안내)은 도구 작업이 아니다 — 상태(기록 없음 · 미사용 · 활성)마다 산출 제출뿐인 워커(mcp-unrun)와 안내 호출
    # 하나를 더한 워커(mcp-info)가 같은 낱말 · 종료 코드다. 파일 읽기가 있으면 안내 호출을 더해도 판정이 그대로다(mcp-dead 의 tools-md-active)
    audit("tools-md-active-unrun", "mcp-unrun", 2, "UNRUN: 도구 작업이 0건", state="active")
    audit("info-only", "mcp-info", 2, "UNRUN: 도구 작업이 0건")
    audit("info-only-unused", "mcp-info", 2, "UNRUN: 도구 작업이 0건", state="unused")
    audit("info-only-active", "mcp-info", 2, "UNRUN: 도구 작업이 0건", state="active")
    audit("info-read-active", "mcp-info-read", 1, "MCP_WIRING_SUSPECT", state="active")
    # 다른 트리 표지를 낸 워커가 Serena 를 불렀으면(안내 호출뿐이어도) 표지가 서버 관찰에서 나올 수 있다 — 도구 작업 0 보다 다른 트리가 먼저다.
    # 호출이 아예 없는 워커의 표지는 인용일 가능성이 커 미판정 그대로다
    audit("info-only-othertree", "mcp-info-othertree", 1, "MCP_OTHER_TREE")
    audit("unrun-othertree", "mcp-unrun-othertree", 2, "UNRUN: 도구 작업이 0건")
    # 탐색 팔(--only-label) — 보고 모드라 판정은 exit 0 · 라벨을 못 읽거나 그 라벨의 워커가 없으면 2
    audit("mcp-arm-text-only", "mcp-arm", 0, "ARM_TEXT_ONLY", ("--only-label", "stage1-symbolic"))
    audit("mcp-arm-used", "mcp-arm", 0, "ARM_SYMBOL_USED", ("--only-label", "stage2-sym"))
    audit("mcp-arm-err", "mcp-arm-err", 0, "ARM_CALLED_NO_RESULT", ("--only-label", "stage1-symbolic"))
    audit("mcp-arm-nolabel", "mcp-nolabel", 2, "UNRUN: 라벨", ("--only-label", "stage1-symbolic"))
    audit("mcp-arm-no-worker", "mcp-arm", 2, "UNRUN: 라벨", ("--only-label", "no-such-stage"))
    audit("mcp-arm-othertree", "mcp-othertree", 0, "ARM_OTHER_TREE", ("--only-label", "stage1-symbolic"))
    audit("mcp-othertree", "mcp-othertree", 1, "MCP_OTHER_TREE")
    # 직접 호출(--direct) — 그 종류의 가장 최근 호출 하나를 판정한다(앞 호출의 사용이 뒤 호출의 0회를 가리지 않게)
    audit("mcp-direct-latest", "mcp-direct", 2, "UNRUN: serena 0건 · Read 1건인데 상태 기록이 없다", ("--only-agent", "fz:review-correctness"),
          direct=True)
    audit("mcp-direct-latest-active", "mcp-direct", 1, "MCP_WIRING_SUSPECT", ("--only-agent", "fz:review-correctness"),
          state="active", direct=True)
    audit("mcp-direct-other-kind", "mcp-direct", 0, "MCP_AUDIT_OK", ("--only-agent", "general-purpose"), direct=True)
    audit("mcp-direct-no-agent", "mcp-direct", 2, "--only-agent", direct=True)
    audit("only-agent-unreadable", "mcp-direct", 2, "UNRUN: 에이전트 종류", ("--only-agent", "general-purpose"), direct=True,
          prep=lambda r: os.remove(os.path.join(r, "proj", "sess-probe", "subagents", "agent-d4.meta.json")))
    # 성공 수 판정 — 같은 "전부 오류" 가 지목한 파일에 따라 다른 판정을 받는다 · 일반과 직접 호출이 같은 판정 함수를 쓴다
    audit("mcp-allerr", "mcp-allerr", 1, "MCP_CALLED_NO_RESULT", state="active")
    audit("mcp-allerr-direct", "mcp-direct", 1, "MCP_CALLED_NO_RESULT", ("--only-agent", "fz:review-quality"),
          state="active", direct=True)
    audit("mcp-allerr-nostate", "mcp-allerr", 2, "UNRUN: 성공 0")
    # 결과에 글이 아닌 블록이 섞여도 오류 글 블록이 있으면 오류다 — 켜진 언어 파일을 물은 유일한 호출이 그 결과면 통과가 아니다
    audit("mixed-block-error", "mcp-mixed-err", 1, "MCP_CALLED_NO_RESULT", state="active")
    audit("mcp-uncovered", "mcp-uncovered", 0, "MCP_FALLBACK_UNCOVERED", state="active")
    audit("mcp-nopath", "mcp-nopath", 2, "MCP_UNDECIDED", state="active")
    audit("lang-table-miss", "mcp-allerr", 2, "UNRUN: 상태 기록의 언어", state="unknown-lang")
    # 심볼 읽기 도구만 심볼 호출이다 — 성공한 안내 호출이 전부 오류인 찾기를 가리지 않고, 정보 줄에만 찍힌다
    audit("nonsymbol-serena", "mcp-nonsymbol", 1, "MCP_CALLED_NO_RESULT", state="active")
    audit("nonsymbol-serena-info", "mcp-nonsymbol", 1, "판정에 세지 않는다): mcp__plugin_fz_serena__initial_instructions=1", state="active")
    # 확장자는 대소문자를 가리지 않는다 · 폴더와 확장자 없는 경로의 빈 결과 · 확장자 표 밖 대상(점이 든 폴더 이름)의 오류는 불명 대상이다
    audit("upper-ext", "mcp-upper-ext", 1, "MCP_CALLED_NO_RESULT", state="active")
    audit("folder-target", "mcp-folder", 2, "MCP_UNDECIDED", state="active")
    audit("extless-target", "mcp-extless", 2, "MCP_UNDECIDED", state="active")
    audit("dotted-folder-target", "mcp-dotted", 2, "MCP_UNDECIDED", state="active")
    # 결과 줄이 없는 호출 — 전부 결과가 없으면 그 사실을 적고, 켜진 언어 파일을 물은 호출이 결과 없이 남았으면 켜진 언어 밖 폴백이 아니다
    audit("no-result-yet", "mcp-noresult", 2, "MCP_UNDECIDED: 성공 0 · 오류 0 · 빈 결과 0 — 심볼 호출 1건이 전부 아직 결과가 없다", state="active")
    audit("uncovered-unanswered", "mcp-unanswered", 2, "MCP_UNDECIDED", state="active")
    # 심볼 도구 결과 판독 — 빈 JSON · 빈 글 = 빈 결과 · 오류 표지 = 오류. 외부 MCP 판독기의 뜻(`[]` 도 본문)은 그대로다
    got = [wfm.symbol_result_kind(False, "[]"), wfm.symbol_result_kind(False, [{"type": "text", "text": "{}"}]),
           wfm.symbol_result_kind(False, " "), wfm.symbol_result_kind(True, "x"),
           wfm.symbol_result_kind(False, "Error executing tool: ValueError - x"),
           wfm.symbol_result_kind(False, "RuntimeError while processing the request: the language server is not running"),
           wfm.symbol_result_kind(False, '[{"name_path": "main"}]'), wfm.mcp_result_kind(False, "[]")]
    want = ["empty", "empty", "empty", "error", "error", "error", "ok", "content"]
    if got == want:
        passed += 1
    else:
        fails.append(f"symbol-result-kind: {got} (기대 {want})")
    # 글 블록이 여럿이면 블록마다 따로 판정해 합친다 — 오류 블록이 하나라도 있으면 오류 · 전부 빈 결과면 빈 결과 · 그 밖은 성공
    blocks = lambda *xs: [{"type": "text", "text": x} for x in xs]
    got = [wfm.symbol_result_kind(False, blocks("[]", "{}")), wfm.symbol_result_kind(False, blocks("[]", "Error: No active project.")),
           wfm.symbol_result_kind(False, blocks('[{"name_path": "main"}]', "[]")), wfm.symbol_result_kind(True, blocks("[]", "{}"))]
    want = ["empty", "error", "ok", "error"]
    if got == want:
        passed += 1
    else:
        fails.append(f"symbol-result-blocks: {got} (기대 {want})")
    # 글이 아닌 블록(리소스)은 본문이라 빈 결과가 아니지만 곁의 오류 글 블록을 가리지 않는다 — 오류 표지 · 오류 글 블록이 먼저다
    res = {"type": "resource", "resource": {"uri": "file:///tmp/x/scripts/run.sh", "mimeType": "text/x-sh", "text": "main() {"}}
    got = [wfm.symbol_result_kind(False, [res] + blocks("Error: No active project.")), wfm.symbol_result_kind(False, [res] + blocks(" ")),
           wfm.symbol_result_kind(False, [res]), wfm.symbol_result_kind(True, [res])]
    want = ["error", "ok", "ok", "error"]
    if got == want:
        passed += 1
    else:
        fails.append(f"symbol-result-nontext: {got} (기대 {want})")

    # 세션 훑기(--mcp-audit --sweep) — 심볼 도구를 가진 종류의 워커만 센다 · 같은 '전부 오류' 입력(넷째 실행)이 일반 · 직접 호출과 같은 판정 ·
    # 상태 기록이 하나가 아니거나 실행 뒤에 고쳐졌으면 0회 · 성공 0 은 미판정 · 이미 본 실행(열쇠 = 실행 id + 워커 기록 수)은 다시 세지 않는다
    sym = "mcp__plugin_fz_serena__find_symbol, mcp__plugin_fz_serena__find_referencing_symbols"
    agent_defs = (("plan-structure", f"Read, Grep, Glob, {sym}, mcp__context7__query-docs"), ("plan-impact", f"Read, Grep, Glob, {sym}"),
                  ("review-quality", f"Read, Grep, Glob, {sym}"), ("search-pattern", "Read, Grep, Glob"),
                  ("memory-curator", "Read, Grep, Glob, mcp__plugin_fz_serena__read_memory, mcp__plugin_fz_serena__find_symbol"),
                  ("plan-merge", None))   # 머리에 도구 선언이 없다 — 본문의 `tools:` 줄은 선언이 아니다

    def write_agents(d, defs=agent_defs):
        os.makedirs(d)
        for nm, tools in defs:
            with open(os.path.join(d, nm + ".md"), "w", encoding="utf-8") as fh:
                fh.write(f"---\nname: {nm}\ndescription: 합성 에이전트 정의\nmodel: sonnet\n" + (f"tools: {tools}\n" if tools else "")
                         + "---\n\n본문 예시 — tools: mcp__plugin_fz_serena__find_symbol\ntools: mcp__plugin_fz_serena__find_symbol\n")

    def sweep_cell(name, kind, steps, plugin_time=None):
        """steps = [(추가 인자, 준비 | None, 출력에 있어야 할 글(하나 · 튜플) | None, 검사(기록 줄들, 열쇠) → 사유 | None[, 출력에 없어야 할 글 튜플])]
        — 같은 세션을 차례로 훑는다. plugin_time 이 있으면 이 스크립트를 임시 플러그인 루트(`scripts/` · 수정 시각을 그 값으로 둔
        `.claude-plugin/plugin.json`)에 복사해 그 사본으로 훑는다."""
        nonlocal passed
        r = tempfile.mkdtemp(prefix="fzwf-swp-")
        try:
            sess, rec = os.path.join(r, "sess"), os.path.join(r, "runs", "mcp-sweep.jsonl")
            write_agents(os.path.join(r, "agents"))
            if kind:
                _write_probe(sess, kind)
            os.makedirs(sess, exist_ok=True)
            script = me
            if plugin_time is not None:
                os.makedirs(os.path.join(r, "plug", "scripts"))
                os.makedirs(os.path.join(r, "plug", ".claude-plugin"))
                script = shutil.copy(me, os.path.join(r, "plug", "scripts"))
                shutil.copy(os.path.join(os.path.dirname(me), "fz_wf_view.py"), os.path.join(r, "plug", "scripts"))   # 형제 모듈(출력)
                manifest = os.path.join(r, "plug", ".claude-plugin", "plugin.json")
                with open(manifest, "w", encoding="utf-8") as fh:
                    fh.write('{"name": "example-plugin", "version": "0.0.1"}\n')
                os.utime(manifest, (plugin_time, plugin_time))
            for i, (extra, prep, want_text, check, *absent) in enumerate(steps, 1):
                if prep:
                    prep(sess)
                extra = [x.replace("{sess}", sess) for x in extra]
                proc = subprocess.run([sys.executable, script, "--mcp-audit", "--sweep", sess, "--record", rec,
                                       "--agents-dir", os.path.join(r, "agents")] + extra,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
                out = (proc.stdout or b"").decode("utf-8", "replace")
                lines, keys = [], None
                if os.path.isfile(rec):
                    with open(rec, "r", encoding="utf-8") as fh:
                        lines = [json.loads(x) for x in fh if x.strip()]
                if os.path.isfile(os.path.join(r, "runs", "mcp-sweep.keys.json")):
                    with open(os.path.join(r, "runs", "mcp-sweep.keys.json"), "r", encoding="utf-8") as fh:
                        keys = json.load(fh)
                why = [] if proc.returncode == 0 else [f"exit {proc.returncode} (기대 0)"]
                for want in (want_text if isinstance(want_text, tuple) else (want_text,)):
                    if want and want not in out:
                        why.append(f"출력에 {want!r} 없음: {out.strip()[:160]}")
                for gone in (absent[0] if absent else ()):
                    if gone in out:
                        why.append(f"출력에 {gone!r} 가 있다: {out.strip()[:160]}")
                bad = check(lines, keys) if check and not why else None
                if bad:
                    why.append(bad)
                if why:
                    fails.append(f"mcp-sweep/{name} {i}회째: " + " · ".join(why))
                    return
            passed += 1
        finally:
            shutil.rmtree(r, ignore_errors=True)

    def runs_of(line):
        return {x["run"]: x for x in line["runs"]}

    def first_line(lines, keys):
        if len(lines) != 1:
            return f"기록 줄 {len(lines)} (기대 1)"
        ln, text = lines[0], json.dumps(lines[0], ensure_ascii=False)
        rs = runs_of(ln)
        if '"fz:' in text:
            return "기록에 `fz:` 로 시작하는 값이 있다"
        if ln.get("skills") != {"example-stack:example-skill": 1} or ln.get("stack_skills") != ["example-stack:example-skill"]:
            return f"스킬 칸: skills={ln.get('skills')} stack_skills={ln.get('stack_skills')}"
        if (rs.get("agent-d2") or {}).get("word") != "MCP_CALLED_NO_RESULT" or (rs.get("agent-d2") or {}).get("error") != 2:
            return f"넷째 실행(켜진 언어 파일에 전부 오류) 판정: {rs.get('agent-d2')}"
        if (rs.get("wf_sw1") or {}).get("context7") != {"content": 1} or (rs.get("wf_sw1") or {}).get("ok") != 1:
            return f"첫 실행 결과 수: {rs.get('wf_sw1')}"
        if sorted(keys or {}) != ["sess/agent-d1", "sess/agent-d2", "sess/wf_sw1", "sess/wf_sw2"]:
            return f"열쇠: {keys}"
        return None

    state = ["--state", "{sess}/state/tools.md"]
    same = ([], None, "MCP_SWEEP runs=0 ", lambda lines, keys: None if len(lines) == 1 else f"다시 훑었는데 기록 줄 {len(lines)} (기대 1)")
    sweep_cell("active", "mcp-sweep", [(state, None, "used=1 suspect=2 fallback=0 undecided=0 n/a=1", first_line), same])
    sweep_cell("nostate", "mcp-sweep-nostate", [([], None, "used=1 suspect=0 fallback=0 undecided=2 n/a=1", None)])
    sweep_cell("latestate", "mcp-sweep-latestate", [(state, None, "used=1 suspect=0 fallback=0 undecided=2 n/a=1", None)])
    sweep_cell("two-states", "mcp-sweep", [(state + state, None, "used=1 suspect=0 fallback=0 undecided=2 n/a=1", None)])
    # 상태를 모르는 0회 실행의 기록 줄 — 미판정에는 미판정 낱말(UNRUN)이 붙는다(내린 의심 낱말이 남지 않는다)
    sweep_cell("nostate-recorded-word", "mcp-sweep-nostate", [([], None, "undecided=2", lambda lines, keys: None if lines and (
        runs_of(lines[0]).get("wf_sw2") or {}).get("verdict") == "undecided" and runs_of(lines[0])["wf_sw2"].get("word") == "UNRUN"
        else f"0회 실행의 기록: {runs_of(lines[0]).get('wf_sw2') if lines else '기록 없음'}")])

    def unfinish(sess):   # 끝나지 않은 실행 둘 — 0회 워크플로의 워커가 결과를 아직 내지 않았고 · 전부 오류인 직접 호출이 아직 돈다(끝 응답 전)
        for p, gone in ((os.path.join(sess, "subagents", "workflows", "wf_sw2", "journal.jsonl"), '"type": "result"'),
                        (os.path.join(sess, "subagents", "agent-d2.jsonl"), '"stop_reason": "end_turn"')):
            with open(p, "r", encoding="utf-8") as fh:
                full = fh.read()
            with open(p + ".full", "w", encoding="utf-8") as fh:
                fh.write(full)
            with open(p, "w", encoding="utf-8") as fh:
                fh.writelines(x for x in full.splitlines(True) if gone not in x)

    def finish(sess):
        for p in (os.path.join(sess, "subagents", "workflows", "wf_sw2", "journal.jsonl"), os.path.join(sess, "subagents", "agent-d2.jsonl")):
            os.replace(p + ".full", p)

    def resume(sess):     # 같은 실행의 다음 시도 — 워커 기록이 하나 늘었다(앞 워커를 복사해 새 id 로 둔다)
        d = os.path.join(sess, "subagents", "workflows", "wf_sw1")
        for ext in (".jsonl", ".meta.json"):
            shutil.copy(os.path.join(d, "agent-a1" + ext), os.path.join(d, "agent-a2" + ext))
        with open(os.path.join(d, "journal.jsonl"), "a", encoding="utf-8") as fh:
            fh.write('{"type": "started", "key": "k-a2", "agentId": "a2"}\n{"type": "result", "key": "k-a2", "agentId": "a2", "result": {}}\n')

    sweep_cell("pending", "mcp-sweep", [
        (state, unfinish, "used=1 suspect=0 fallback=0 undecided=0 n/a=1",
         lambda lines, keys: None if sorted(keys or {}) == ["sess/agent-d1", "sess/wf_sw1"] else f"끝나지 않은 실행의 열쇠: {keys}"),
        (state, finish, "MCP_SWEEP runs=2 used=0 suspect=2 ", None)])

    def main_log(sess):   # 본 대화 기록(세션 폴더와 같은 이름의 형제 파일)의 Skill 호출 — fz 밖 하나 · fz 하나
        call = lambda i, name: {"type": "tool_use", "id": f"m{i}", "name": "Skill", "input": {"skill": name}}
        with open(sess + ".jsonl", "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "assistant", "timestamp": "2026-09-11T00:00:00Z", "message": {
                "id": "m-main", "content": [call(1, "example-stack:example-skill"), call(2, "fz:fz-code")]}}, ensure_ascii=False) + "\n")

    sweep_cell("main-log", "mcp-sweep", [(state, main_log, "MCP_SWEEP runs=4 ",
                                          lambda lines, keys: None if lines and lines[0].get("skills") == {"example-stack:example-skill": 2}
                                          else f"스킬 칸: {lines[0].get('skills') if lines else '기록 없음'}")])
    sweep_cell("resumed", "mcp-sweep", [(state, None, "MCP_SWEEP runs=4 ", None),
                                        (state, resume, "MCP_SWEEP runs=1 used=1 ",
                                         lambda lines, keys: None if (keys or {}).get("sess/wf_sw1") == 2 else f"열쇠: {keys}")])
    sweep_cell("budget", "mcp-sweep", [
        (state + ["--budget", "0"], None, "MCP_SWEEP runs=1 ",
         lambda lines, keys: None if len(lines) == 1 and list(keys or {}) == ["sess/wf_sw1"] else f"본 데까지: 줄 {len(lines)} · 열쇠 {keys}"),
        (state, None, "MCP_SWEEP runs=3 ", lambda lines, keys: None if len(lines) == 2 and len(keys or {}) == 4 else f"줄 {len(lines)} · 열쇠 {keys}")])
    # 실행 기록이 없는 세션 — 기록 · 열쇠 파일을 만들지 않는다
    sweep_cell("idle", None, [([], None, "MCP_SWEEP runs=0 ",
                               lambda lines, keys: None if not lines and keys is None else "실행 없는 세션에서 파일을 만들었다")])

    def only_na(sess):    # 해당 없음 실행(심볼 도구가 없는 종류의 직접 호출) 하나만 남긴다
        shutil.rmtree(os.path.join(sess, "subagents", "workflows"))
        for ext in (".jsonl", ".meta.json"):
            os.remove(os.path.join(sess, "subagents", "agent-d2" + ext))

    # 새로 판정한 실행이 전부 해당 없음 — 열쇠만 쓰고 기록 줄은 쓰지 않는다(아무도 보지 않는 머신에서 기록이 자라지 않게)
    sweep_cell("all-na", "mcp-sweep", [(state, only_na, "MCP_SWEEP runs=1 used=0 suspect=0 fallback=0 undecided=0 n/a=1",
                                        lambda lines, keys: None if not lines and keys == {"sess/agent-d1": 1}
                                        else f"전부 해당 없음인데 기록 줄 {len(lines)} · 열쇠 {keys}")])
    big = {}

    def big_record(sess):  # 돌림 크기에 이른 기록(유효한 JSON 줄) + 앞서 돌린 옛 파일 하나
        big["old"] = os.path.join(os.path.dirname(sess), "runs", "mcp-sweep.jsonl.1")
        os.makedirs(os.path.dirname(big["old"]), exist_ok=True)
        row = json.dumps({"at": "2026-09-10T00:00:00Z", "session": "sess-old", "summary": {}, "runs": []}) + "\n"
        with open(big["old"][:-len(".1")], "w", encoding="utf-8") as fh:
            fh.write(row * (getattr(wfm, "SWEEP_RECORD_MAX", 1_000_000) // len(row) + 1))
        with open(big["old"], "w", encoding="utf-8") as fh:
            fh.write(row)

    def rotated(lines, keys):
        size = os.path.getsize(big["old"]) if os.path.isfile(big["old"]) else 0
        if len(lines) == 1 and size >= getattr(wfm, "SWEEP_RECORD_MAX", 1_000_000) and not os.path.exists(big["old"][:-1] + "2"):
            return None
        return f"돌림: 기록 줄 {len(lines)} (기대 1 — 새 줄만) · 옛 파일 {size}바이트 (기대 돌린 기록 하나)"

    # 기록이 돌림 크기에 이르면 덧붙이기 전에 한 번 돌린다 — 옛 파일은 하나만 남는다(앞서 돌린 것을 덮는다)
    sweep_cell("rotate", "mcp-sweep", [(state, big_record, "MCP_SWEEP runs=4 ", rotated)])

    def block_record(sess):   # 기록 폴더 자리에 보통 파일 — 기록 · 열쇠를 쓰지 못한다
        with open(os.path.join(os.path.dirname(sess), "runs"), "w", encoding="utf-8") as fh:
            fh.write("x\n")

    # 기록하지 못한 판정은 알리지 않는다 — 기록 · 열쇠 쓰기가 실패하면 UNRUN 줄 하나뿐(요약 · 의심 줄 없음) · 쓸 수 있으면 둘 다 찍는다
    sweep_cell("record-unwritable", "mcp-sweep", [(state, block_record, "MCP_SWEEP_UNRUN", None, ("MCP_SWEEP runs=", "의심:"))])
    sweep_cell("record-writable", "mcp-sweep", [(state, None, ("MCP_SWEEP runs=4 ", "  의심: wf_sw2 MCP_WIRING_SUSPECT"), None)])
    now = time.time()

    def age_run(sess):    # 0회 워크플로 실행(wf_sw2)의 기록 파일이 두 시간 전에 끝났다
        d = os.path.join(sess, "subagents", "workflows", "wf_sw2")
        for n in os.listdir(d):
            os.utime(os.path.join(d, n), (now - 7200, now - 7200))

    def predated(lines, keys):
        got = runs_of(lines[0]).get("wf_sw2") if lines else None
        ok = got and got.get("verdict") == "n/a" and "설치된 플러그인보다 먼저" in str(got.get("reason")) and len(keys or {}) == 4
        return None if ok else f"설치 전 실행의 기록: {got} · 열쇠 {keys}"

    # 플러그인 설치(루트의 .claude-plugin/plugin.json 수정 시각)보다 먼저 끝난 실행은 판정하지 않는다 — 해당 없음 · 사유 · 알림 없음 · 열쇠는 적는다.
    # 설치 시각이 미래면 경계가 없다(둘 다 판정)
    sweep_cell("predates-plugin", "mcp-sweep", [
        (state, age_run, ("MCP_SWEEP runs=4 used=1 suspect=1 fallback=0 undecided=0 n/a=2", "  의심: agent-d2 "), predated, ("의심: wf_sw2",)),
        same], plugin_time=now - 3600)
    sweep_cell("plugin-time-future", "mcp-sweep", [(state, age_run, "MCP_SWEEP runs=4 used=1 suspect=2 fallback=0 undecided=0 n/a=1", None)],
               plugin_time=now + 86400)

    def stall(sess):      # 끝나지 않은 두 실행(unfinish)의 기록 파일이 이틀 전에 멈췄다
        unfinish(sess)
        d = os.path.join(sess, "subagents", "workflows", "wf_sw2")
        for p in [os.path.join(d, x) for x in os.listdir(d)] + [os.path.join(sess, "subagents", "agent-d2.jsonl")]:
            os.utime(p, (now - 2 * 86400, now - 2 * 86400))

    def stalled_rows(lines, keys):   # 멈춘 두 실행 — 미판정 · 사유 · 열쇠 = [워커 기록 수, 기록 크기]
        rs, keys = (runs_of(lines[0]) if len(lines) == 1 else {}), keys or {}
        bad = [r for r in ("wf_sw2", "agent-d2") if not (rs.get(r) and rs[r]["verdict"] == "undecided" and rs[r]["word"] == "UNRUN"
               and "24시간 넘게 멈춘" in str(rs[r].get("reason")) and keys.get(f"sess/{r}") == [1, rs[r].get("bytes")])]
        return f"멈춘 실행: 줄 {len(lines)} · 열쇠 {keys} · 어긋난 실행 {[(r, rs.get(r)) for r in bad]}" if bad or len(keys) != 4 else None

    def retry(sess):      # 멈춘 워크플로 실행의 다음 시도 — 새 워커 기록 하나(앞 워커를 복사해 새 id 로 둔다 · 기존 기록 파일은 그대로)
        d = os.path.join(sess, "subagents", "workflows", "wf_sw2")
        for ext in (".jsonl", ".meta.json"):
            shutil.copy(os.path.join(d, "agent-a1" + ext), os.path.join(d, "agent-a2" + ext))

    def retry_done(sess):  # 그 시도가 끝났다 — 앞 시도는 실패 · 새 시도는 결과
        with open(os.path.join(sess, "subagents", "workflows", "wf_sw2", "journal.jsonl"), "a", encoding="utf-8") as fh:
            fh.write('{"type": "failed", "key": "k-a1", "agentId": "a1"}\n{"type": "started", "key": "k-a1", "agentId": "a2"}\n'
                     '{"type": "result", "key": "k-a1", "agentId": "a2", "result": {}}\n')

    unchanged = ([], None, "MCP_SWEEP runs=0 ", lambda lines, keys: None if len(lines) == 1 else f"멈춘 실행을 다시 읽었다 — 기록 줄 {len(lines)}",
                 ("멈춘 실행", "끝나지 않은 실행"))
    # 끝나지 않은 채 기록이 24시간 넘게 멈춘 실행은 미판정으로 적고 열쇠(워커 기록 수 + 기록 크기)를 적는다 — 그대로면 다시 읽지 않고, 재개가
    # 기존 워커 기록에 덧붙이면(워커 수 그대로 · stale-pending) · 새 워커 기록을 더하면(stale-retry) 다시 본다. 설치 전이면 해당 없음이 먼저다
    sweep_cell("stale-pending", "mcp-sweep", [
        (state, stall, ("MCP_SWEEP runs=4 used=1 suspect=0 fallback=0 undecided=2 n/a=1", "  멈춘 실행 2"), stalled_rows), unchanged,
        (state, finish, "MCP_SWEEP runs=2 used=0 suspect=2 ", lambda lines, keys: None if len(lines) == 2 and (keys or {}).get("sess/wf_sw2") == 1
         and keys.get("sess/agent-d2") == 1 else f"기존 기록에 덧붙인 재개 뒤: 줄 {len(lines)} · 열쇠 {keys}")], plugin_time=now - 30 * 86400)
    sweep_cell("stale-retry", "mcp-sweep", [
        (state, stall, "undecided=2 ", stalled_rows),
        (state, retry, ("MCP_SWEEP runs=0 ", "  끝나지 않은 실행 1"), None, ("멈춘 실행",)),
        (state, retry_done, "MCP_SWEEP runs=1 used=0 suspect=1 ", lambda lines, keys: None if len(lines) == 2 and (keys or {}).get("sess/wf_sw2") == 2
         else f"새 워커 기록을 더한 재개 뒤: 줄 {len(lines)} · 열쇠 {keys}")], plugin_time=now - 30 * 86400)
    sweep_cell("stale-predates", "mcp-sweep", [
        (state, stall, ("MCP_SWEEP runs=4 used=1 suspect=0 fallback=0 undecided=0 n/a=3", "  설치 전 실행 2"),
         lambda lines, keys: None if lines and "설치된 플러그인보다 먼저" in str((runs_of(lines[0]).get("wf_sw2") or {}).get("reason"))
         and isinstance((keys or {}).get("sess/wf_sw2"), list) else f"설치 전에 멈춘 실행: {lines[-1] if lines else '기록 없음'} · 열쇠 {keys}",
         ("멈춘 실행",)), unchanged], plugin_time=now - 3600)

    def block_keys(sess):     # 열쇠 파일 자리에 폴더 — 기록 줄은 쓰고 열쇠는 읽지도 쓰지도 못한다
        os.makedirs(os.path.join(os.path.dirname(sess), "runs", "mcp-sweep.keys.json"))

    one_line = lambda lines, keys: None if len(lines) == 1 else f"기록 줄 {len(lines)} (기대 1 — 같은 실행을 다시 판정했다)"
    # 기록 줄을 쓰고 열쇠를 쓰지 못한 종료 뒤 — 다음 훑기는 기록 줄에서 열쇠를 되살려 다시 판정하지 않고, 쓸 수 있게 되면 열쇠 파일을 다시 쓴다.
    # 멈춘 실행의 열쇠는 기록 크기까지 되살아나 기존 기록에 덧붙인 재개를 다시 본다
    sweep_cell("keys-recover", "mcp-sweep", [
        (state, lambda s: (stall(s), block_keys(s)), "MCP_SWEEP_UNRUN", one_line), (state, None, "MCP_SWEEP_UNRUN", one_line),
        (state, lambda s: os.rmdir(os.path.join(os.path.dirname(s), "runs", "mcp-sweep.keys.json")), "MCP_SWEEP runs=0 ",
         lambda lines, keys: None if len(lines) == 1 and len(keys or {}) == 4 and isinstance(keys.get("sess/agent-d2"), list)
         else f"되살린 열쇠: 줄 {len(lines)} · 열쇠 {keys}"),
        (state, finish, "MCP_SWEEP runs=2 used=0 suspect=2 ", None)], plugin_time=now - 30 * 86400)

    def one_suspect(sess):    # 의심 실행을 하나(0회 워크플로 wf_sw2)만 남긴다 — 켜진 언어 파일에 전부 오류인 직접 호출(agent-d2)을 뺀다
        for ext in (".jsonl", ".meta.json"):
            os.remove(os.path.join(sess, "subagents", "agent-d2" + ext))

    # 기록 줄을 쓰고 열쇠를 쓰지 못한 종료는 그 의심을 알리지 못했다 — 열쇠를 되살린 훑기가 그 의심 줄을 앞선 훑기의 판정으로 한 번 찍고
    # 기록 줄은 새로 쓰지 않는다(요약 줄은 이번에 판정한 실행만 센다) · 다음 훑기는 조용하다 · 되살린 성공 · 해당 없음 실행은 아무것도 찍지 않는다
    sweep_cell("keys-recover-notice", "mcp-sweep", [
        (state, lambda s: (one_suspect(s), block_keys(s)), "MCP_SWEEP_UNRUN", one_line, ("의심:",)),
        (state, lambda s: os.rmdir(os.path.join(os.path.dirname(s), "runs", "mcp-sweep.keys.json")),
         ("MCP_SWEEP runs=0 used=0 suspect=0 ", "  의심: wf_sw2 MCP_WIRING_SUSPECT", "앞선 훑기의 판정"),
         lambda lines, keys: None if len(lines) == 1 and sorted(keys or {}) == ["sess/agent-d1", "sess/wf_sw1", "sess/wf_sw2"]
         else f"되살린 훑기: 기록 줄 {len(lines)} (기대 1) · 열쇠 {keys}", ("의심: wf_sw1", "의심: agent-d1")),
        (state, None, "MCP_SWEEP runs=0 ", one_line, ("의심:",))])
    r8 = tempfile.mkdtemp(prefix="fzwf-hold-")
    try:
        write_agents(os.path.join(r8, "agents"))
        got = wfm.symbol_holders(os.path.join(r8, "agents")) if hasattr(wfm, "symbol_holders") else "symbol_holders 없음"
        if got =={"fz:plan-structure", "fz:plan-impact", "fz:review-quality"}:
            passed += 1
        else:
            fails.append(f"mcp-sweep/holders: {got} (기대 심볼 도구 선언이 있는 세 종류 — 본문 줄 · 큐레이터 제외)")
    finally:
        shutil.rmtree(r8, ignore_errors=True)
    # 일반 모드(--wf · --only-agent 없음)는 정의 폴더에 정의돼 있고 심볼 도구가 없는 종류의 워커를 세지 않는다 — 남는 워커가 없으면 해당 없음.
    # 정의에 없는 종류 · --only-agent 로 고른 워커 · 정의 폴더를 못 읽었을 때는 그대로 센다. 정의 폴더 기본값은 이 스크립트 플러그인의 agents/ 다
    r9 = tempfile.mkdtemp(prefix="fzwf-defs-")
    try:
        defs = os.path.join(r9, "agents")
        write_agents(defs)
        audit("na-kind-only", "mcp-na-kind", 0, "MCP_NOT_APPLICABLE: 심볼 도구를 가진 종류의 워커가 없다(뺀 종류: fz:search-pattern 1)",
              ("--agents-dir", defs), state="active")
        audit("na-kind-mixed", "mcp-na-mixed", 2, "대조 심볼", ("--agents-dir", defs), state="active")
        audit("na-kind-only-agent", "mcp-na-kind", 1, "MCP_WIRING_SUSPECT", ("--agents-dir", defs, "--only-agent", "fz:search-pattern"),
              state="active")
        audit("na-kind-no-defs", "mcp-na-kind", 1, "MCP_WIRING_SUSPECT", ("--agents-dir", os.path.join(r9, "missing")), state="active")
    finally:
        shutil.rmtree(r9, ignore_errors=True)
    audit("na-kind-default-dir", "mcp-na-kind", 0, "MCP_NOT_APPLICABLE", state="active")
    # 심볼 도구를 가진 종류는 심볼 읽기 도구 다섯으로 가른다 — 구현 찾기만 · 선언 찾기만 선언한 종류의 워커도 세고(파일만 읽었으면 의심),
    # 다섯 중 어느 것도 없는 종류(심볼 읽기가 아닌 Serena 도구만 있어도)는 여전히 뺀다
    r10 = tempfile.mkdtemp(prefix="fzwf-defs5-")
    try:
        defs5 = os.path.join(r10, "agents")
        write_agents(defs5, (("impl-correctness", "Read, Grep, Glob, mcp__plugin_fz_serena__find_implementations"),
                             ("review-correctness", "Read, Grep, Glob, mcp__plugin_fz_serena__find_declaration"),
                             ("search-pattern", "Read, Grep, Glob, mcp__plugin_fz_serena__read_memory")))
        audit("holder-impl-only", "mcp-impl-only", 1, "MCP_WIRING_SUSPECT", ("--agents-dir", defs5), state="active")
        audit("holder-decl-only", "mcp-decl-only", 1, "MCP_WIRING_SUSPECT", ("--agents-dir", defs5), state="active")
        audit("holder-none-left-out", "mcp-na-kind", 0, "MCP_NOT_APPLICABLE", ("--agents-dir", defs5), state="active")
    finally:
        shutil.rmtree(r10, ignore_errors=True)

    # ⑪~⑬ --sweep-row — 측정값과 사람 판정 칸이 섞이지 않는지, 부재를 0 으로 쓰지 않는지
    def sweep(kind, want_exit, want_text):
        nonlocal passed
        r3 = tempfile.mkdtemp(prefix="fzwf-sw-")
        try:
            _write_probe(r3, kind)
            proc = subprocess.run([sys.executable, me, "--sweep-row", "--root", r3,
                                   "--wf", "wf_probe", "--session", "*"],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
            out = (proc.stdout or b"").decode("utf-8", "replace")
            why = []
            if proc.returncode != want_exit:
                why.append(f"exit {proc.returncode} (기대 {want_exit})")
            if want_text not in out:
                why.append(f"출력에 {want_text!r} 없음: {out.strip()[:140]}")
            if why:
                fails.append(f"sweep-row/{kind}: " + " · ".join(why))
            else:
                passed += 1
        finally:
            shutil.rmtree(r3, ignore_errors=True)

    sweep("sweep-effort", 0, "`xhigh`×1")     # 실측된 effort 가 행에 들어간다
    sweep("mcp-ok", 0, "unavailable (raw")    # ⛔ 부재를 0 으로 쓰지 않는다
    sweep("empty", 2, "UNRUN")                # agent 0건은 통과가 아니다

    # ⑭ stage 규칙 — 현행 워크플로의 실제 [역할] 문구(앞 60자 이내)가 기대 라벨로 가는가.
    #    ⛔ 첫 일치 규칙이라 순서가 틀리면 조용히 다른 라벨이 붙는다(교차 콜이 Stage 1 로 읽힌다).
    stage_cases = (
        ("설계자 — 이 과제의 계획을 **혼자** 끝낸다. 방향 판정·영향 범위·", "L1-full"),
        ("경계 케이스 적대자 — 이 접근이 **어디서 깨지는가**만 판다.", "L1-edge"),
        ("영향 범위 + 아키텍처 검증자 — **이 변경이 어디까지 퍼지는가**와", "L1-impact"),
        ("통합자 — 적대 렌즈와 영향·아키 렌즈의 발견을 기존 계획에", "L2-merge"),
        ("아키텍처 리뷰어(review-arch 렌즈) — 설계 결정·레이어 위반·확장성", "R1-arch"),
        ("품질 리뷰어(review-quality 렌즈) — 코드 품질·dead code·성능", "R1-quality"),
        ("정확성 리뷰어(review-correctness 렌즈) — 요구사항 충족·로직", "R1-correct"),
        ("아키텍처 리뷰어 — 교차 조정", "R2-arch"),
        ("품질 리뷰어 — 교차 보충", "R2-quality"),
        ("반론자(review-counter 렌즈) — Devil's Advocate", "R3-counter"),
        ("아키텍처 검증자(review-arch 렌즈)", "S2-arch"),          # 옛 배선 — 라벨 불변
        ("설계자(plan-structure 렌즈) — 방향 반박", "S0-reb"),
        ("구조 설계자", "?"),                                        # sweep probe — 새 규칙에 걸리면 안 된다
    )
    bad_stage = [f"{r[:18]}…→{wfm._stage_of(r)}(기대 {want})" for r, want in stage_cases if wfm._stage_of(r) != want]
    if bad_stage:
        fails.append("stage 규칙: " + " · ".join(bad_stage))
    else:
        passed += 1

    # ⑮ ⛔ usage 중복 — 같은 id 의 content block 줄 3개가 usage 를 반복해도 응답 1건으로 센다.
    #    같은 fixture 로 하네스 래퍼 뒤의 [역할] 도 본다(첫 메시지만 보면 stage 가 '?').
    root = tempfile.mkdtemp(prefix="fzwf-dup-")
    try:
        p = os.path.join(root, "agent-d1.jsonl")
        u = {"output_tokens": 100, "output_tokens_details": {"thinking_tokens": 40}}
        rows = [{"type": "user", "timestamp": "2026-09-26T00:00:00Z",
                 "message": {"content": "[Workflow harness — user request] relayed"}},
                {"type": "user", "timestamp": "2026-09-26T00:00:00Z",
                 "message": {"content": "[Workflow harness — computed task]\n[역할] 통합자 — x"}}]
        rows += [{"type": "assistant", "timestamp": f"2026-09-26T00:00:0{i}Z",
                  "message": {"id": "msg_1", "stop_reason": "tool_use", "usage": u,
                              "content": [{"type": kind}]}} for i, kind in enumerate(("thinking", "text", "tool_use"), 1)]
        rows.append({"type": "assistant", "timestamp": "2026-09-26T00:00:09Z",
                     "message": {"id": "msg_2", "stop_reason": "end_turn", "usage": {"output_tokens": 7}, "content": []}})
        with open(p, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        a = wfm.read_agent(p)
        if (a["turns"], a["out_tok"], a["thinking"], a["stage"]) == (2, 107, 40, "L2-merge"):
            passed += 1
        else:
            fails.append(f"usage 중복: turns={a['turns']} out_tok={a['out_tok']} thinking={a['thinking']} "
                         f"stage={a['stage']} (기대 2·107·40·L2-merge)")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # ⑯ advisor 스톨 (F-382) — 호출 2 · 결과 1(2줄 중복) → advisor 1(결과 기반 불변) · calls 2 · stalled 1.
    #    결과만 있고 호출 블록이 없는 ① probe 는 스톨 수를 0 이 아니라 unavailable(None)로 둔다.
    #    --expect 가 적힌 advisor_stalled 를 비교하는가(틀린 값 0 → exit 1)
    def wf_of(kind):
        r = tempfile.mkdtemp(prefix="fzwf-at-")
        _write_probe(r, kind)
        return r, wfm.read_wf(os.path.join(r, "proj", "sess-probe", "subagents", "workflows", "wf_probe"))

    r4, wf = wf_of("stall")
    try:
        got = (wf["advisor"], wf["advisor_calls"], wf["advisor_stalled"])
        r5, wg = wf_of("good")
        shutil.rmtree(r5, ignore_errors=True)
        if got == (1, 2, 1) and wg["advisor_stalled"] is None and wg["advisor"] == 1:
            passed += 1
        else:
            fails.append(f"advisor 스톨: (advisor, calls, stalled)={got} (기대 1·2·1) · 호출 블록 없는 probe stalled={wg['advisor_stalled']} (기대 None)")
    finally:
        shutil.rmtree(r4, ignore_errors=True)
    st_run = {"id": "probe", "session_glob": "sess-probe", "wf": "wf_probe", "wall_s": 90.0, "agents": 1,
              "advisor": 1, "advisor_calls": 2, "advisor_stalled": 1}
    run("stall", [st_run], 0, "METRICS_OK")
    run("stall", [dict(st_run, advisor_stalled=0)], 1, "advisor_stalled 1 ≠ 0")

    # ⑰ 시도 구분 (F-387) — 실패 시도 + 재개: wall · critical_path 는 마지막 시도(600s) · failed_attempts 1 ·
    #    재개 없이 실패로 끝난 run 은 경계를 정할 수 없어 wall · critical_path UNRUN(None) — 0 도 전 agent 값도 아니다
    r6, wr = wf_of("resume")
    r7, wn = wf_of("no-resume")
    try:
        got = (wr["wall"], wr["critical_path"], wr["failed_attempts"], wr["attempt_ambiguous"],
               wn["wall"], wn["critical_path"], bool(wn["attempt_ambiguous"]))
        if got == (600.0, 600.0, 1, None, None, None, True):
            passed += 1
        else:
            fails.append(f"시도 구분: (wall, crit, failed_attempts, ambiguous | 무재개 wall, crit, ambiguous)={got} "
                         f"(기대 600·600·1·None | None·None·True)")
    finally:
        shutil.rmtree(r6, ignore_errors=True)
        shutil.rmtree(r7, ignore_errors=True)

    # ⑱ 낱말-표 짝 — `--mcp-audit` 가 내는 판정 낱말(MCP_* · ARM_* · UNRUN — 원문의 `return "<낱말>", n` · `print("<낱말>:` · `print(f"<낱말>:` 꼴 ·
    #    훑기 요약 줄의 MCP_SWEEP* 는 뺀다)과 modules/symbol-tools-audit.md § 출력 낱말 표의 첫 칸이 같은 집합이고 낱말마다 행이 하나다.
    #    표 사본 변이(낱말마다 행 삭제 · 행 중복 · 이름 바꿈 + 모르는 낱말 행 추가)는 하나하나 어긋나야 한다 — 그대로만 통과한다
    def pair_gaps(words, md):
        sec = md.split("\n## 출력 낱말", 1)[-1].split("\n## ", 1)[0] if "\n## 출력 낱말" in md else ""
        rows = re.findall(r"(?m)^\| `([A-Z_]+)` \|", sec)
        return [f"표에 없음 {w}" for w in sorted(words - set(rows))] + [f"원문에 없음 {w}" for w in sorted(set(rows) - words)] + \
               [f"행 {rows.count(w)}개 {w}" for w in sorted(set(rows)) if rows.count(w) > 1]

    audit_md = os.path.join(os.path.dirname(os.path.dirname(me)), "modules", "symbol-tools-audit.md")
    try:
        with open(me, encoding="utf-8") as fh:
            src = fh.read()
        with open(audit_md, encoding="utf-8") as fh:
            md = fh.read()
    except OSError as exc:
        fails.append(f"낱말-표 짝: 원문 · 표를 못 읽었다 ({type(exc).__name__}: {audit_md})")
    else:
        pat = r"(?:MCP|ARM)_[A-Z_]+|UNRUN"
        words = {w for w in re.findall(rf'return "({pat})", \d', src) + re.findall(rf'print\(f?"({pat}):', src)
                 if not w.startswith("MCP_SWEEP")}
        lines = md.split("\n")
        variants = {"모르는 낱말 행 추가": md.replace("|---|---|---|---|\n", "|---|---|---|---|\n| `MCP_PROBE_UNKNOWN` | 0 | 합성 | 합성 |\n", 1)}
        for w in sorted(words):
            head = f"| `{w}` |"
            variants[f"{w} 행 삭제"] = "\n".join(x for x in lines if not x.startswith(head))
            variants[f"{w} 행 중복"] = "\n".join(y for x in lines for y in ((x, x) if x.startswith(head) else (x,)))
            variants[f"{w} 이름 바꿈"] = md.replace(head, f"| `{w}_RENAMED` |")
        gaps = pair_gaps(words, md)
        missed = sorted(k for k, v in variants.items() if not pair_gaps(words, v))
        if words and not gaps and not missed:
            passed += 1
        else:
            fails.append(f"낱말-표 짝: 원문 낱말 {len(words)}개 · 어긋남 {gaps or '없음'} · 못 잡은 표 변이 {missed or '없음'}")

    # 요약 줄의 묶음 수는 손으로 적는다 — 묶음 합이 총수와 다르면 셀을 더하고 묶음 수를 고치지 않은 것이다(요약이 셀 수를 속이지 않게)
    groups = (("양성", 1), ("음성", 7), ("mcp-audit", 53), ("심볼 결과 판독", 3), ("mcp-sweep", 22), ("sweep-row", 3),
              ("stage 규칙", 1), ("usage 중복", 1), ("advisor 스톨", 3), ("시도 구분", 1), ("낱말-표 짝", 1),
              ("전달 요청", 1))
    total = passed + len(fails)
    if sum(n for _, n in groups) != total:
        fails.append(f"요약 묶음 합 {sum(n for _, n in groups)} ≠ 총수 {total}")
    for f in fails:
        print(f"  FAIL {f}")
    if fails:
        print(f"fz_wf_metrics self-test {passed}/{passed + len(fails)} passed")
        return 1
    print(f"SELFTEST_OK (fz_wf_metrics self-test {passed}/{total} — " + " · ".join(f"{k} {n}" for k, n in groups) + ")")
    return 0
