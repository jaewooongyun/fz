# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 형제 모듈 import 와 계측기 해시에 이 파일의 디렉토리만 쓴다.
"""ab_ledger_selftest_r3.py — ab_ledger_selftest.self_test 가 싣는 round 3 S14 사례(파일 1500줄 상한 때문에 나눴다).

⛔ 계측기 지문(INSTRUMENTS) 밖이다 — self_test 를 정의하지 않고 register(reg, base) 로 사례만 등록한다
   (self_test 정의 파일은 하나뿐이어야 한다 · structure-d selftest-outside-fingerprint).
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

import fz_wf_metrics as wfm
from ab_ledger_base import CORPUS_GUARD_EXTRA, DEFAULT_EFFORT, DEFAULT_MODEL, FAIL, INSTRUMENTS, PASS, UNRUN, instrument_sha
from ab_ledger_collect import external_mcp_merge, launcher_unmeasured, sleep_count, wf_summary
from ab_ledger_gpt import RULE_FIXTURES, agents_record, judge_gpt
from ab_ledger_judge import VERIFY_FIELDS, freeze_corpus, row_invalid
from ab_ledger_transcript import mcp_summary, parse_transcript
from ab_ledger_selftest import _judge, _mk


def register(reg, base):
    # ── round 3 S14 — 계측기 신원 · 코퍼스 동결 · 외부 MCP 워커 · 수면 증거 · 규칙 fixture 감사 ─────────────
    here = os.path.dirname(os.path.abspath(__file__))
    cli = lambda *a: subprocess.run([sys.executable, os.path.join(here, "ab_ledger.py"), *a], capture_output=True, text=True, timeout=120)

    @reg
    def r3_ab_instrument_hash_separates_baseline():
        # 계측기를 고치면 지문이 바뀌고(--instrument-hash = instrument_sha) · 지문이 다른 행은 묶음 다수와 갈려 비교에서 빠진다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            for n in INSTRUMENTS:
                shutil.copy(os.path.join(here, n), td)
            same = instrument_sha(td) == instrument_sha()
            with open(os.path.join(td, "ab_ledger_judge.py"), "a", encoding="utf-8") as fh:
                fh.write("\n# 계측기 수정\n")
            moved = instrument_sha(td) != instrument_sha()
            ih = cli("--instrument-hash").stdout.strip()
            rows = base() + [_mk("C1", "C", 2), _mk("C2", "C", 4), _mk("C3", "C", 6)]
            rows[4][0]["instrument_sha"] = "i2"     # C3 만 고친 계측기로 잰 행
            rc, out = _judge(rows, require=["AC-5"])
            ok = (same and moved and ih == instrument_sha()
                  and any(x.startswith("  INVALID C3") and "instrument 불일치" in x for x in out)
                  and not any(x.startswith(("  INVALID C1", "  INVALID B1")) for x in out))
            return ok, [f"same={same} moved={moved} cli={ih}"] + out
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_ab_list_instruments_equals_fingerprint():
        # --list-instruments 의 파일마다 고치면 지문이 바뀌고, 목록 밖 형제(self-test 모듈)를 고치면 그대로다 — 목록 == 지문 입력
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            listed = cli("--list-instruments").stdout.split()
            root = os.path.dirname(here)
            for n in INSTRUMENTS + ("ab_ledger_selftest.py",):
                shutil.copy(os.path.join(here, n), td)
            h0 = instrument_sha(td)
            moves = []
            for rel in listed:
                f = os.path.join(td, os.path.basename(rel))
                keep = open(f, encoding="utf-8").read()
                with open(f, "a", encoding="utf-8") as fh:
                    fh.write("\n# x\n")
                moves.append(instrument_sha(td) != h0)
                with open(f, "w", encoding="utf-8") as fh:
                    fh.write(keep)
            with open(os.path.join(td, "ab_ledger_selftest.py"), "a", encoding="utf-8") as fh:
                fh.write("\n# 사례만 고친 변경\n")
            outside_same = instrument_sha(td) == h0
            ok = (listed == ["scripts/" + n for n in INSTRUMENTS] and all(os.path.isfile(os.path.join(root, x)) for x in listed)
                  and moves and all(moves) and outside_same)
            return ok, [f"listed={listed} moves={moves} outside_same={outside_same}"]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    sm = {"sha256": "a" * 64, "audit_hits": 0}
    corpus = lambda *tasks: {"input_tree_sha": "b" * 40, "tasks": list(tasks)}
    task = lambda tid, paths, smoke=sm: dict({"id": tid, "diff_paths": paths}, **({"a0_smoke": smoke} if smoke is not None else {}))

    @reg
    def r3_f443_task_touching_instrument_excluded():
        # 과제 diff 가 지문 파일 · 측정 런처를 건드리면 동결을 거부하고 아무것도 쓰지 않는다 — 측정이 계측기를 리뷰하게 된다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            r1, b1 = freeze_corpus(corpus(task("T1", ["src/a.py"])))
            r2, b2 = freeze_corpus(corpus(task("T1", ["src/a.py"]), task("T2", ["./scripts/gpt_independent.sh", "README.md"])))
            r3, b3 = freeze_corpus(corpus(task("T3", ["scripts/ab_ledger_judge.py"])))
            spec, out = os.path.join(td, "tasks.json"), os.path.join(td, "freeze.json")
            with open(spec, "w", encoding="utf-8") as fh:
                json.dump(corpus(task("T2", ["scripts/gpt-exec.sh"])), fh)
            p = cli("freeze-corpus", "--tasks", spec, "--out", out)
            ok = (r1 is not None and not b1 and r2 is None and any(x.startswith("T2:") and "gpt_independent.sh" in x for x in b2)
                  and r3 is None and any("ab_ledger_judge.py" in x for x in b3) and p.returncode == FAIL and not os.path.exists(out))
            return ok, b2 + b3 + [p.stdout[-200:]]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_f443_a0_smoke_bound_to_freeze():
        # 과제마다 A0 스모크(감사 적중 0) 결과 해시가 동결 입력에 있어야 동결한다 — 기록은 그 해시와 계측기 지문 · 입력 트리를 담는다
        rn, bn = freeze_corpus(corpus(task("T1", ["src/a.py"], smoke=None)))
        rh, bh = freeze_corpus(corpus(task("T1", ["src/a.py"], smoke={"sha256": "a" * 64, "audit_hits": 1})))
        rs, bs = freeze_corpus(corpus(task("T1", ["src/a.py"], smoke={"sha256": "xyz", "audit_hits": 0})))
        rg, bg = freeze_corpus(corpus(task("T1", ["src/a.py"]), task("T2", ["docs/b.md"], smoke={"sha256": "c" * 64, "audit_hits": 0})))
        ok = (rn is None and any("A0 스모크 결과 해시" in x for x in bn) and rh is None and any("감사 적중 1" in x for x in bh)
              and rs is None and rg is not None and not bg
              and [t["a0_smoke_sha256"] for t in rg["tasks"]] == ["a" * 64, "c" * 64]
              and rg["instrument_sha"] == instrument_sha() and rg["input_tree_sha"] == "b" * 40)
        return ok, bn + bh + bs + [str(rg)[:200]]

    @reg
    def r3_f325_worker_mcp_counted():
        # 외부 MCP 를 Lead 와 Workflow 워커 transcript 에서 함께 센다(같은 세션 · 호출 id 한 번) · 워커 로그가 없는 Workflow 는 0 이 아니라
        # 미측정으로 적고(필드) judge 가 그 run 을 뺀다(판정) — 두 반쪽을 함께 본다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            wx, we = os.path.join(td, "wf_x"), os.path.join(td, "wf_empty")
            os.makedirs(wx)
            os.makedirs(we)
            ev = lambda **k: json.dumps(dict({"sessionId": "S1", "timestamp": "2026-01-01T00:00:00Z"}, **k))
            lines = [ev(type="assistant", message={"id": "m1", "content": [
                         {"type": "tool_use", "id": "w1", "name": "mcp__atlassian-jira__jira_get", "input": {}},
                         {"type": "tool_use", "id": "w2", "name": "mcp__plugin_fz_serena__find_symbol", "input": {}}]}),
                     ev(type="user", message={"content": [{"type": "tool_result", "tool_use_id": "w1", "content": "issue body"},
                                                          {"type": "tool_result", "tool_use_id": "w2", "content": "sym"}]})]
            with open(os.path.join(wx, "agent-a1.jsonl"), "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines + lines) + "\n")          # 같은 호출이 두 번 기록된 로그
            lead = [{"session": "L", "id": "t1", "name": "mcp__github__get_issue", "kind": "error"}]
            runs = [{"run_id": "wf_x", "summary": wf_summary(wx)}, {"run_id": "wf_empty", "summary": wf_summary(we)}]
            em, em_ok = external_mcp_merge(lead, runs), external_mcp_merge(lead, runs[:1])
            rows = base() + [_mk("C1", "C", 2), _mk("C2", "C", 4)]
            rows[2][0]["external_mcp"] = dict(em, returned=0)        # 유입은 없고 미측정만 — 미측정이 run 을 뺀다
            rows[3][0]["external_mcp"] = dict(em_ok, returned=0)
            rc, out = _judge(rows, require=["AC-5"])
            ok = ((em["calls"], em["returned"], em["errors"]) == (2, 1, 1) and em["unmeasured"] == ["wf_empty"]
                  and em["tools"] == ["mcp__atlassian-jira__jira_get", "mcp__github__get_issue"] and em_ok["unmeasured"] == []
                  and any(x.startswith("  INVALID C1") and "외부 MCP 미측정" in x for x in out)
                  and not any(x.startswith("  INVALID C2") for x in out))
            return ok, [str(em)] + out
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_f326_no_sleep_log_unmeasured():
        # 정식 비교에서 수면 기록이 없는 run 은 '수면 0' 이 아니라 미측정으로 뺀다 · 정식이 아닌 판정은 그대로다
        ev_ = {"count": 0, "source": "/runs/sleep.txt", "sha256": "s", "note": None}
        rows = base() + [_mk("C1", "C", 2), _mk("C2", "C", 4)]
        for r, _ in rows:
            r["sleep"] = dict(ev_)
        rows[2][0]["sleep"] = {"count": None, "source": None, "sha256": None, "note": "--sleep-log 없음 — 미측정"}
        rc_f, out_f = _judge(rows, require=["AC-5"], formal=True)
        rc_n, out_n = _judge(rows, require=["AC-5"])
        ok = (any(x.startswith("  INVALID C1") and "수면 증거 없음" in x for x in out_f)
              and not any(x.startswith(("  INVALID C2", "  INVALID B1")) for x in out_f)
              and not any(x.startswith("  INVALID C1") for x in out_n))
        return ok, out_f + out_n

    @reg
    def r3_f356_rule_fixture_audit_axes():
        # 규칙 fixture 행도 감사 exit · 격리 · 입력 이름 집합 · 재해시를 본다(빈 hash_ok 는 통과가 아니다) · 다렌즈 처치는 요청과 spawn 을 따로 남긴다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            os.makedirs(os.path.join(td, "rules-absent"))   # 오라클 문서 — 없으면 SC-2 가 판정 전에 UNRUN 이다(r1 ISSUE-005)
            for name, doc in (("labels.json", {"guidelines": []}), ("expected-index.json", {"sections": []})):
                with open(os.path.join(td, "rules-absent", name), "w", encoding="utf-8") as fh:
                    json.dump(doc, fh)
            it = {"kind": "craft", "id": "X1", "ruleSource": "plugin-default", "ruleRef": None, "severity": "suggestion",
                  "craftAxis": "naming", "file": "a.ts", "text": "t"}

            def row(rid, audit=None, inputs=None):
                return {"run_id": rid, "fixture": "rules-absent", "mode": "review", "instrument_sha": instrument_sha(),
                        "audit": dict({"mode": "review", "exit": 0, "isolationApplied": True, "timedOut": False}, **(audit or {})),
                        "inputs": dict({"names": ["diff"], "given": ["diff"], "claude_named": [], "hash_ok": {"diff": True}}, **(inputs or {})),
                        "output": {"items": [dict(it)], "conflicts": [], "rules": [], "axis_coverage": {}}}
            rows = [row("r-ok"), row("r-exit", audit={"exit": 15, "note": "오염"}), row("r-iso", audit={"isolationApplied": False}),
                    row("r-names", inputs={"names": ["diff", "plan"]}), row("r-hash", inputs={"hash_ok": {}})]
            lines = {}
            for g in rows:
                _, out = judge_gpt({g["run_id"]: g}, ["SC-2"], [], td)
                lines[g["run_id"]] = [x for x in out if f"SC-2 [rules-absent] {g['run_id']}" in x]
            want = {"r-exit": "감사 exit 15", "r-iso": "격리 미적용", "r-names": "입력 이름 집합 불일치", "r-hash": "재해시 기록 없음"}
            ok = (len(lines["r-ok"]) == 1 and lines["r-ok"][0].startswith("PASS")
                  and all(len(lines[k]) == 1 and lines[k][0].startswith("FAIL") and w in lines[k][0] for k, w in want.items())
                  and agents_record({"gpt_agents": True}, {"spawn": 0}, {}) == {"requested": True, "spawned": 0}
                  # spawned 는 rollout 재계수만 — 감사 값(2)으로 메우지 않는다(S14 r4 ISSUE-008 · 불일치는 gpt_source_problems 가 센다)
                  and agents_record({}, {"spawn": 0}, {"spawnAgent": 2}) == {"requested": False, "spawned": 0})
            return ok, [str(lines)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    # ── round 3 S14 적대 검토 r1(GPT) 반례 11건 — 셀마다 그 반례 입력 그대로 · 고친 뒤 통과 · 깨끗한 짝은 그대로 통과 ─────────
    def jl(path, evs):
        with open(path, "w", encoding="utf-8") as fh:
            for e in evs:
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")

    def ev_use(t, sid, tid, name, inp=None):
        return {"type": "assistant", "timestamp": f"2026-01-01T00:00:0{t}Z", "sessionId": sid,
                "message": {"id": f"m{t}", "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp or {}}]}}

    def ev_res(t, sid, tid, content, err=False):
        return {"type": "user", "timestamp": f"2026-01-01T00:00:0{t}Z", "sessionId": sid,
                "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": content, "is_error": err}]}}

    def opts(**kw):
        return dict({"model": DEFAULT_MODEL, "effort": DEFAULT_EFFORT}, **kw)

    @reg
    def r3_adv_verify_covers_invalidation_fields():
        # 001 — row_invalid 가 읽는 행 필드(잎)는 전부 원천 대조(VERIFY_FIELDS)에 든다 — 사본을 지우거나 바꿔도 대조가 잡는다.
        #       읽은 경로를 기록하는 dict 로 row_invalid 를 한 번 돌려 목록을 뽑는다(눈으로 고른 목록이 아니다)
        seen = set()

        class Rec(dict):
            def __init__(self, d, path):
                super().__init__(d)
                self.path = path

            def get(self, k, default=None):
                v = dict.get(self, k, default)
                pth = f"{self.path}.{k}" if self.path else k
                seen.add(pth)
                return Rec(v, pth) if isinstance(v, dict) else v

            def __getitem__(self, k):
                return self.get(k)
        row, score = _mk("C1", "C", 2)
        row.update(sleep={"source": "s", "count": 0, "note": None, "sha256": "x"},
                   external_mcp={"calls": 1, "returned": 0, "errors": 0, "empty": 1, "unresolved": 0, "tools": [], "unmeasured": []},
                   merge={"violations": 0, "summaries": [{"in": 1, "out": 1}]})
        row["gpt"].update(launcher_failed=0, launcher_unmeasured=0)
        row_invalid(Rec(row, ""), score, opts(require=["AC-4"], formal=True, plugin_sha="10197a0"))
        leaves = {x for x in seen if not any(y.startswith(x + ".") for y in seen)}
        fields = {f for fs in VERIFY_FIELDS.values() for f in fs}
        exempt = {"phase", "workflow",          # 판정 옵션과 맞춰 보는 행 정체(collect 인자) — 원천에서 만든 값이 아니다
                  "instrument_sha",             # instrument-sha 종류가 현재 지문과 따로 대조한다
                  "complete.why", "plugin.at",  # 사유 문구 — 판정은 complete.ok · plugin.dirty 가 정하고 둘은 대조된다
                  "sleep.source"}               # 증거 사본 경로 — 같은 사본인지는 sleep.sha256 이 대조한다
        gap = sorted(x for x in leaves - exempt if not any(x == f or x.startswith(f + ".") for f in fields))
        probe = {"sleep.count", "external_mcp.returned", "gpt.launcher_failed", "gpt.launcher_unmeasured", "merge.violations"}
        return not gap and probe <= seen, [f"대조 밖 판정 필드 {gap}", f"기록 못 한 탐침 {sorted(probe - seen)}"]

    @reg
    def r3_adv_launcher_without_audit_unmeasured():
        # 002 — 백그라운드 런처의 접수 응답만 있고 완료 알림 · 감사 파일이 없으면 미측정이다(실행 0 · 실패 0 이 아니다)
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            cmd = {"command": "bash /plugin/scripts/gpt-call.sh independent-review --out /runs/g.json", "run_in_background": True}
            evs = [ev_use(1, "L1", "b1", "Bash", cmd), ev_res(2, "L1", "b1", "Command running in background with ID: task1")]
            jl(os.path.join(td, "a.jsonl"), evs)
            open_calls = parse_transcript(os.path.join(td, "a.jsonl"))["launcher"]
            note = {"type": "user", "timestamp": "2026-01-01T00:00:09Z", "sessionId": "L1", "message": {"content":
                    "<task-notification><task-id>task1</task-id><tool-use-id>b1</tool-use-id><status>completed</status></task-notification>"}}
            jl(os.path.join(td, "b.jsonl"), evs + [note])
            done_calls = parse_transcript(os.path.join(td, "b.jsonl"))["launcher"]
            row, score = _mk("C1", "C", 2)
            row["gpt"]["launcher_unmeasured"] = launcher_unmeasured(open_calls, 0)
            why = row_invalid(row, score, opts())
            ok = (len(open_calls) == 1 and launcher_unmeasured(open_calls, 0) == 1 and launcher_unmeasured(open_calls, 1) == 1
                  and launcher_unmeasured(done_calls, 1) == 0 and launcher_unmeasured(done_calls, 0) == 1
                  and any("런처 미측정 1건" in w for w in why))
            return ok, [str(open_calls), str(done_calls), str(why)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def gpass(rid, mode, out=True, audit=None, inputs=None, fixture="fx"):
        return {"type": "gpt-pass", "run_id": rid, "env": "isolated", "mode": mode, "fixture": fixture, "instrument_sha": instrument_sha(),
                "audit": dict({"mode": mode, "exit": 0, "isolationApplied": True, "timedOut": False, "hits": 0}, **(audit or {})),
                "inputs": dict({"names": ["diff"], "given": ["diff"], "claude_named": [], "hash_ok": {"diff": True}}, **(inputs or {})),
                "scan": {"rollout_files": ["r"], "markers": [{"path": "/x/gpt-home/skills/a"}], "bad_refs": [], "claude_listed": []},
                "skills": {"body_matches_tree": {"a": True}, "tree_hash": "t", "plugin_hash": "t"},
                "output": {"items": [], "rules": [], "conflicts": []} if out else None, "collect_args": {}}

    @reg
    def r3_adv_matrix_row_without_output_unrun():
        # 003 — 매트릭스 셀 행의 첫 패스 출력이 없으면 SC-1 · AC-2 는 미판정이다(출력이 있는 짝은 PASS 그대로)
        rc, out = judge_gpt({"p": gpass("p", "plan", out=False), "r": gpass("r", "review", out=False)}, ["SC-1", "AC-2"], ["isolated"], "")
        rc_ok, out_ok = judge_gpt({"p": gpass("p", "plan"), "r": gpass("r", "review")}, ["SC-1", "AC-2"], ["isolated"], "")
        ok = (rc == UNRUN and any(x.startswith("UNRUN SC-1 [isolated×plan]: 출력 없음") for x in out)
              and any(x.startswith("UNRUN AC-2") for x in out) and not any(x.startswith("PASS") for x in out)
              and rc_ok == PASS and len([x for x in out_ok if x.startswith("PASS")]) == 3)
        return ok, out + out_ok

    @reg
    def r3_adv_ac2_only_keeps_audit_checks():
        # 004 — AC-2 만 물어도 감사 exit · 격리 · 재해시가 틀린 행은 AC-2 를 통과시키지 않는다
        bad = gpass("r", "review", audit={"exit": 15, "isolationApplied": False}, inputs={"hash_ok": {}})
        rc, out = judge_gpt({"p": gpass("p", "plan"), "r": bad}, ["AC-2"], ["isolated"], "")
        rc_ok, _ = judge_gpt({"p": gpass("p", "plan"), "r": gpass("r", "review")}, ["AC-2"], ["isolated"], "")
        line = next((x for x in out if "AC-2" in x), "")
        ok = (rc == FAIL and line.startswith("FAIL AC-2") and "감사 exit 15" in line and "격리 미적용" in line
              and "재해시 기록 없음" in line and rc_ok == PASS)
        return ok, out

    @reg
    def r3_adv_missing_fixture_oracle_unrun():
        # 005 — 규칙 fixture 오라클(labels · expected-index)이 없거나 비면 SC-2 · AC-3 은 미판정이다(빈 기대로 PASS 하지 않는다)
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            rows = {fx: gpass(fx, "review", fixture=fx) for fx in RULE_FIXTURES.values()}
            rc, out = judge_gpt(rows, ["SC-2", "AC-3"], [], os.path.join(td, "absent"))
            os.makedirs(os.path.join(td, "rules-absent"))
            for name in ("labels.json", "expected-index.json"):
                with open(os.path.join(td, "rules-absent", name), "w", encoding="utf-8") as fh:
                    fh.write("{}")
            rc2, out2 = judge_gpt({"rules-absent": rows["rules-absent"]}, ["SC-2"], [], td)
            ok = (rc == UNRUN and not any(x.startswith("PASS") for x in out)
                  and sum(1 for x in out if x.startswith("UNRUN SC-2") and "오라클 없음" in x) == 3
                  and rc2 == UNRUN and any("비었거나" in x for x in out2))
            return ok, out + out2
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def mcp_logs(td, evs):
        jl(os.path.join(td, "lead.jsonl"), evs)
        jl(os.path.join(td, "agent-w.jsonl"), evs)
        lead = mcp_summary(parse_transcript(os.path.join(td, "lead.jsonl"))["external_mcp_calls"])
        work = mcp_summary(wfm.read_agent(os.path.join(td, "agent-w.jsonl"))["mcp_external"])
        return lead, work

    @reg
    def r3_adv_mcp_image_content_counts_returned():
        # 006 — 텍스트가 아닌 결과(이미지)도 본문이다 — Lead · 워커 판독 모두 returned 1 · 빈 텍스트 결과는 empty 그대로
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            img = [{"type": "image", "source": {"type": "base64", "data": "AAAA"}}]
            lead, work = mcp_logs(td, [ev_use(1, "L1", "t1", "mcp__browser__take_screenshot"), ev_res(2, "L1", "t1", img)])
            e_lead, e_work = mcp_logs(td, [ev_use(1, "L1", "t1", "mcp__jira__get"), ev_res(2, "L1", "t1", [{"type": "text", "text": " "}])])
            row, score = _mk("C1", "C", 2)
            row["external_mcp"] = lead
            ok = (lead["returned"] == work["returned"] == 1 and lead["empty"] == work["empty"] == 0
                  and e_lead["empty"] == e_work["empty"] == 1 and e_lead["returned"] == e_work["returned"] == 0
                  and any("외부 MCP 내용 유입 1회" in w for w in row_invalid(row, score, opts())))
            return ok, [str(lead), str(work), str(e_lead), str(e_work)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_adv_mcp_unresolved_result_unmeasured():
        # 007 — 결과가 없는 외부 MCP 호출은 오류가 아니라 미확인이다 — Lead · 워커 모두 unresolved 1 · judge 가 run 을 뺀다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            lead, work = mcp_logs(td, [ev_use(1, "L1", "t1", "mcp__jira__get")])
            row, score = _mk("C1", "C", 2)
            row["external_mcp"] = lead
            why = row_invalid(row, score, opts())
            ok = (lead["unresolved"] == work["unresolved"] == 1 and lead["errors"] == work["errors"] == 0
                  and any("외부 MCP 결과 미확인 1회" in w for w in why))
            return ok, [str(lead), str(work), str(why)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_adv_mcp_result_keyed_by_session():
        # 008 — 같은 호출 id 가 두 세션에 있으면 결과도 (세션, id) 로 찾는다 — 둘째 세션의 오류가 첫 세션의 본문을 덮지 않는다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            lead, work = mcp_logs(td, [ev_use(1, "L1", "t1", "mcp__jira__get"), ev_res(2, "L1", "t1", "external issue body"),
                                       ev_use(3, "L2", "t1", "mcp__jira__get"), ev_res(4, "L2", "t1", "denied", err=True)])
            ok = all((x["calls"], x["returned"], x["errors"]) == (2, 1, 1) for x in (lead, work))
            return ok, [str(lead), str(work)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_adv_corpus_guard_launcher_closure():
        # 009 — 진입점 · 런처를 고친 과제는 동결하지 않는다. 런처 셋(과 그 .sh 가 부르는 .sh)의 주석 밖 참조 파일은 저장소 어디에 있든
        #   전부 가드에 든다(scripts/ 밖 diff_anchors.py · gpt-exec.sh 가 부르는 validate-gpt-output.py — 2차 ISSUE-009) · 008 절대 경로 거부
        def frz(*paths):
            return freeze_corpus({"input_tree_sha": "b" * 40, "tasks": [{"id": "T1", "diff_paths": list(paths),
                                                                        "a0_smoke": {"sha256": "a" * 64, "audit_hits": 0}}]})
        root = os.path.dirname(here)
        files = {}
        for dp, _dirs, fs in os.walk(root):
            if "/." in dp or "__pycache__" in dp or "/tests/" in dp + "/":
                continue
            for f in fs:
                files.setdefault(f, set()).add(os.path.relpath(os.path.join(dp, f), root))
        refs, todo, seen = set(), ["scripts/gpt-call.sh", "scripts/gpt_independent.sh", "scripts/gpt-exec.sh"], set()
        while todo:
            rel = todo.pop()
            if rel in seen:
                continue
            seen.add(rel)
            with open(os.path.join(root, rel), encoding="utf-8") as fh:   # 주석(줄 전체 · 공백 뒤 끝 주석)은 참조가 아니다
                code = "\n".join(re.sub(r"(^|\s)#.*$", "", ln) for ln in fh.read().splitlines())
            for m in re.findall(r"[A-Za-z0-9_.-]+\.(?:sh|py|json)\b", code):
                for hit in files.get(m, ()):
                    refs.add(hit)
                    if hit.endswith(".sh"):
                        todo.append(hit)
        guard = {"scripts/" + n for n in INSTRUMENTS} | set(CORPUS_GUARD_EXTRA)
        rejects = [frz(p)[0] is None for p in ("scripts/gpt-call.sh", "skills/fz-peer-review/scripts/diff_anchors.py",
                                               "scripts/validate-gpt-output.py", os.path.join(root, "scripts/ab_ledger_judge.py"),
                                               "../x/scripts/ab_ledger.py")]
        ok = all(rejects) and frz("skills/fz/SKILL.md")[0] is not None and refs and refs <= guard
        return ok, [str(rejects), f"가드 밖 런처 참조 {sorted(refs - guard)}"]

    @reg
    def r3_s14_unreadable_artifact_unscored():
        # 2차 ISSUE-001 — 산출물 하나라도 못 읽거나 collect 기록과 내용이 다르면 채점 · 꾸러미에 쓰지 않는다(남은 요약만으로 0 지적 채점 금지)
        from ab_ledger_judge import _read_texts
        import hashlib
        td = tempfile.mkdtemp(prefix="abl-art-")
        try:
            a, b = os.path.join(td, "report.md"), os.path.join(td, "summary.md")
            for pth, body in ((a, b"- x"), (b, b"summary only")):
                with open(pth, "wb") as fh:
                    fh.write(body)
            rec = [{"path": x, "sha256": hashlib.sha256(open(x, "rb").read()).hexdigest(), "bytes": 1} for x in (a, b)]
            row = {"sources": {"artifacts": [a, b]}, "artifacts": rec}
            ok_read = _read_texts(row) == ["- x", "summary only"]
            with open(a, "wb") as fh:
                fh.write(b"- changed")
            changed = _read_texts(row)
            os.remove(a)
            gone = _read_texts(row)
            return ok_read and changed is None and gone is None, [f"read={ok_read} changed={changed} gone={gone}"]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_s14_launcher_calls_all_counted():
        # 2차 ISSUE-002 — 한 Bash 안 런처 호출을 모두 센다 · 감사가 하나뿐이면 미측정 1
        from ab_ledger_transcript import _launcher_calls
        t0 = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
        cmd = ("bash /p/scripts/gpt-call.sh independent-review --diff /r/d.patch --out-dir /r/a; "
               "bash /p/scripts/gpt-call.sh independent-review --diff /missing.patch --out-dir /r/b || true")
        calls = _launcher_calls([{"id": "u1", "ts": t0, "input": {"command": cmd}}], {},
                                {"u1": {"ts": t0 + datetime.timedelta(seconds=9)}})
        # 실행되지 않은 언급(검색 인자 · 주석 · 다른 명령의 인자)은 호출이 아니다 — 세면 감사 없는 호출로 정상 run 이 무효가 된다(r3 8.5 2차)
        talk = ['rg -n "gpt-call.sh independent-plan" skills/fz-plan/SKILL.md', "# gpt-call.sh independent-review\nls",
                "echo bash gpt-call.sh independent-plan"]
        quiet = [len(_launcher_calls([{"id": "u2", "ts": t0, "input": {"command": c}}], {}, {})) for c in talk]
        return len(calls) == 2 and launcher_unmeasured(calls, 1) == 1 and quiet == [0, 0, 0], [str(calls), str(quiet)]

    @reg
    def r3_s14_journal_ids_one_to_one():
        # 2차 ISSUE-003 — 같은 agent 의 중복 result 가 다른 agent 의 누락을 메우지 못한다(건수가 아니라 agentId 대응)
        agents = [{"file": f"agent-a{i}.jsonl"} for i in (1, 2, 3)]
        st = [("started", None, f"a{i}") for i in (1, 2, 3)]
        dup = st + [("result", None, "a1")] * 3
        good = st + [("result", None, f"a{i}") for i in (1, 2, 3)]
        got = (wfm._journal_ids_match(dup, agents), wfm._journal_ids_match(good, agents), wfm._journal_ids_match(None, agents))
        return got == (False, True, False), [str(got)]

    @reg
    def r3_s14_orphan_result_unmeasured():
        # 2차 ISSUE-004 — 호출 줄이 빠진 결과는 고아로 센다(외부 MCP 미측정) · 이미 이은 결과의 중복 사본은 세지 않는다
        td = tempfile.mkdtemp(prefix="abl-orph-")
        try:
            p = os.path.join(td, "agent-a1.jsonl")
            lines = [{"type": "assistant", "sessionId": "L", "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Read", "input": {}}]}},
                     {"type": "user", "sessionId": "L", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}},
                     {"type": "user", "sessionId": "L", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}},
                     {"type": "user", "sessionId": "L", "message": {"content": [{"type": "tool_result", "tool_use_id": "external-call",
                                                                                  "content": "External Jira issue body"}]}}]
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("".join(json.dumps(x) + "\n" for x in lines))
            got = wfm.read_agent(p).get("orphan_results")
            return got == 1, [f"orphan_results={got}"]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_s14_sleep_log_bad_utf8_unmeasured():
        # 2차 ISSUE-005 — 깨진 UTF-8 수면 기록은 0 이 아니라 미측정이다
        td = tempfile.mkdtemp(prefix="abl-slp-")
        try:
            p = os.path.join(td, "pmset.log")
            with open(p, "wb") as fh:
                fh.write(b"2026-01-01 00:00:00 +0000 Wake\n"
                         b"2026-01-01 01:30:00 +0000 Sl\xffep               Entering Sleep state due to Clamshell Sleep\n"
                         b"2026-01-01 02:05:00 +0000 : Showing all currently held IOKit power assertions\n")
            utc = datetime.timezone.utc
            got = sleep_count(p, datetime.datetime(2026, 1, 1, 1, tzinfo=utc), datetime.datetime(2026, 1, 1, 2, tzinfo=utc))
            return got["count"] is None and bool(got["note"]), [str(got)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_s14_clock_mtime_nan_rejected():
        # 2차 ISSUE-006 — 끝점 시계의 mtime NaN · Infinity 는 형식 위반 · 행의 mtime Δ 가 NaN 이면 무효
        from ab_ledger_collect import read_endpoint_clock
        td = tempfile.mkdtemp(prefix="abl-clk-")
        try:
            p = os.path.join(td, "clock.jsonl")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write('{"t": "2026-01-01T00:00:11Z", "path": "/v/report.md", "size": 4, "mtime": NaN, "sha256": "%s"}\n' % ("a" * 64))
            rows, probs = read_endpoint_clock(p)
            r, _ = _mk("B1", "B", 1)[0], None
            r.setdefault("wall", {})["mtime_delta_s"] = float("nan")
            inv = row_invalid(r, None, {"model": DEFAULT_MODEL, "effort": DEFAULT_EFFORT})
            return not rows and bool(probs) and any("mtime" in x for x in inv), [str(probs), str(inv)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_s14_gpt_row_instrument_mismatch_excluded():
        # 2차 ISSUE-007 — 다른 계측기 지문(또는 없음)의 gpt-pass 행은 판정에서 뺀다 — 칸이 비면 UNRUN
        p_old = gpass("p", "plan")
        p_old["instrument_sha"] = "1" * 16
        rc, out = judge_gpt({"p": p_old, "r": gpass("r", "review")}, ["SC-1"], ["isolated"], "")
        return rc != PASS and any(x.strip().startswith("제외 1") for x in out), out

    @reg
    def r3_s14_dir_input_rehash():
        # 2차 ISSUE-010 — 폴더 입력(head/ 등)은 런처와 같은 tree hash 로 재잰다. 런처 파일의 정의를 꺼내 실행한 값과 대조한다(재구현 헛돌이 방지)
        from ab_ledger_gpt import _tree_hash, input_hash_ok
        with open(os.path.join(here, "gpt_independent.sh"), encoding="utf-8") as fh:
            src = fh.read()
        m = re.search(r"^def tree_hash\(d\):\n(?:[ \t]+.*\n)+", src, re.M)
        ns = {"os": os, "hashlib": __import__("hashlib")}
        if m:
            exec(m.group(0), ns)   # noqa: S102 — 저장소의 런처 정의(시험 대상) — 외부 입력이 아니다
        td = tempfile.mkdtemp(prefix="abl-tree-")
        try:
            d = os.path.join(td, "head")
            os.makedirs(os.path.join(d, "sub"))
            for rel, body in (("a.swift", b"x"), ("sub/b.swift", b"y"), (".hidden", b"z")):
                with open(os.path.join(d, rel), "wb") as fh:
                    fh.write(body)
            os.symlink("a.swift", os.path.join(d, "ln"))
            os.symlink("missing", os.path.join(d, "broken"))
            os.symlink("sub", os.path.join(d, "dirlink"))
            f = os.path.join(td, "d.patch")
            with open(f, "wb") as fh:
                fh.write(b"diff")
            rec = ns["tree_hash"](d) if "tree_hash" in ns else None
            same = rec is not None and _tree_hash(d) == rec
            ok_dir = input_hash_ok("head/", d, rec)
            ok_file = input_hash_ok("diff.patch", f, __import__("hashlib").sha256(b"diff").hexdigest())
            with open(os.path.join(d, "a.swift"), "wb") as fh:
                fh.write(b"changed")
            stale = input_hash_ok("head/", d, rec)
            ok = same and ok_dir and ok_file and not stale and not input_hash_ok("head/", d, None)
            return ok, [f"same={same} dir={ok_dir} file={ok_file} stale={stale}"]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_adv_missing_instrument_sha_invalid():
        # 010 — 계측기 지문이 없는 행은 지문 비교 전에 뺀다(네 행 모두 없으면 '같은 지문' 이 아니다) · 지문 있는 짝은 PASS
        rows = [_mk("B1", "B", 1, major=3), _mk("B2", "B", 3), _mk("C1", "C", 2), _mk("C2", "C", 4, major=3)]
        rc_ok, _ = _judge(rows, require=["AC-5"])
        for r, _ in rows:
            r.pop("instrument_sha", None)
        rc, out = _judge(rows, require=["AC-5"])
        ok = rc_ok == PASS and rc != PASS and sum(1 for x in out if x.startswith("  INVALID") and "계측기 지문 없음" in x) == 4
        return ok, out

    @reg
    def r3_adv_sleep_snapshot_before_end_unmeasured():
        # 011 — 수면 기록의 마지막 시각(캡처)이 run 끝보다 이르면 미측정 · 끝 뒤에 캡처한 기록은 수를 센다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            utc = datetime.timezone.utc
            s, e = datetime.datetime(2026, 1, 1, 1, tzinfo=utc), datetime.datetime(2026, 1, 1, 2, tzinfo=utc)
            early, late = os.path.join(td, "early.txt"), os.path.join(td, "late.txt")
            with open(early, "w", encoding="utf-8") as fh:
                fh.write("2026-01-01 00:00:00 +0000 Wake                \tWake from Normal Sleep\n")
            with open(late, "w", encoding="utf-8") as fh:
                fh.write("2026-01-01 00:00:00 +0000 Wake                \tWake from Normal Sleep\n"
                         "2026-01-01 01:30:00 +0000 Sleep               \tEntering Sleep state due to 'Clamshell Sleep'\n"
                         "2026-01-01 02:05:00 +0000 : Showing all currently held IOKit power assertions\n")
            a, b = sleep_count(early, s, e), sleep_count(late, s, e)
            ok = a["count"] is None and "끝을 덮지 않는다" in (a["note"] or "") and b["count"] == 1
            return ok, [str(a), str(b)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    # ── S14 구조 전환(r3 확인 라운드 지적 001~006 · 결함 주입 tests/ab/faults.py 가 찾은 읽는 곳 다섯) ─────────────────────
    #    셀마다 지적의 반례 입력 그대로 · 깨끗한 짝은 그대로 통과. 전수는 결함 주입 러너가 잰다(이 셀들은 읽는 곳마다 대표 한 꼴)
    t0 = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)

    @reg
    def r3_s14_r3_001_current_instrument_only():
        # 001 — 네 행이 모두 현재가 아닌 같은 지문(0000…)이면 묶음 대조로는 못 뺀다 — 모든 기준에서 현재 지문과 대조한다
        rows = [_mk("B1", "B", 1), _mk("B2", "B", 3), _mk("C1", "C", 2), _mk("C2", "C", 4)]
        rc_ok, _ = _judge(rows, require=["AC-5"])
        for r, _s in rows:
            r["instrument_sha"] = "0" * 16
        rc, out = _judge(rows, require=["AC-5"])
        ok = rc_ok == PASS and rc != PASS and sum(1 for x in out if x.startswith("  INVALID") and "instrument 불일치" in x) == 4
        return ok, out

    @reg
    def r3_s14_r3_002_lead_orphan_unmeasured():
        # 002 — 짝 tool_use 줄이 빠진 Lead 쪽 tool_result 는 형식 위반(고아)이다 — 깨끗한 입력으로 읽지 않는다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            p = os.path.join(td, "lead.jsonl")
            evs = [{"type": "user", "timestamp": "2026-01-01T00:00:00Z", "sessionId": "L", "message": {"role": "user", "content": "go"}},
                   ev_use(1, "L", "t1", "Read", {"file_path": "/x"}), ev_res(2, "L", "t1", "ok")]
            jl(p, evs)
            clean = parse_transcript(p)["format_problems"]
            jl(p, evs + [ev_res(3, "L", "lost-jira", "external Jira issue body")])
            lost = parse_transcript(p)["format_problems"]
            return clean == {} and lost.get("orphan_result") == 1, [str(clean), str(lost)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def stop_line(mid, uid=None, parent=None, sec=1, **msg):
        e = {"type": "assistant", "timestamp": f"2026-01-01T00:00:0{sec}Z", "sessionId": "S", "effort": "xhigh",
             "message": dict({"id": mid, "model": "claude-opus-5-5", "stop_reason": "end_turn", "usage": {"output_tokens": 120},
                              "content": [{"type": "text", "text": "done"}]}, **msg)}
        if uid:
            e.update(uuid=uid, parentUuid=parent)
        return e

    @reg
    def r3_s14_r3_003_usage_missing_unmeasured():
        # 003 — usage 가 빠진 완결 턴을 out_tok 0 으로 확정하지 않는다 — 형식 위반으로 Workflow 폴더 오류(미완주)가 된다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            p = os.path.join(td, "agent-a1.jsonl")
            jl(p, [stop_line("m1")])
            a_ok = wfm.read_agent(p)
            bad = stop_line("m1")
            bad["message"].pop("usage")
            jl(p, [bad])
            a_bad = wfm.read_agent(p)
            errs = wfm.read_wf(td)["errors"]
            ok = (a_ok["format_problems"] == {} and a_ok["out_tok"] == 120 and a_bad["format_problems"].get("assistant.usage") == 1
                  and any("형식 위반" in e for e in errs))
            return ok, [str(a_ok["format_problems"]), str(a_bad["format_problems"]), str(errs)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_s14_r3_004_journal_broken_line_unmeasured():
        # 004 — 파싱 불가 journal 줄(닫는 중괄호 없는 failed)을 버리고 완주를 확정하지 않는다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            jp = os.path.join(td, "journal.jsonl")
            jl(jp, [{"type": "started", "key": "a", "agentId": "a1"}, {"type": "result", "key": "a", "agentId": "a1", "result": {"ok": True}}])
            ok_j = wfm.read_journal(td)
            with open(jp, "a", encoding="utf-8") as fh:
                fh.write('{"type":"failed","key":"a","agentId":"a1"\n')
            bad_j = wfm.read_journal(td)
            errs = wfm.read_wf(td)["errors"]
            ok = ok_j["bad_lines"] == 0 and bad_j["bad_lines"] == 1 and any("journal" in e and "형식 위반" in e for e in errs)
            return ok, [str(ok_j["bad_lines"]), str(bad_j["bad_lines"]), str(errs)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_s14_r3_005_audit_mode_bound():
        # 005 — 감사의 실제 mode 와 수집 --mode 가 다르면 그 셀의 첫 패스가 아니다(review 감사를 plan 행으로 실은 꼴)
        rc_ok, _ = judge_gpt({"p": gpass("p", "plan"), "r": gpass("r", "review")}, ["SC-1", "AC-2"], ["isolated"], "")
        rc, out = judge_gpt({"p": gpass("p", "plan", audit={"mode": "review"}), "r": gpass("r", "review")}, ["SC-1", "AC-2"], ["isolated"], "")
        ok = rc_ok == PASS and rc != PASS and any("감사 mode review ≠ 수집 mode plan" in x for x in out)
        return ok, out

    def bash_uses(*cmds):
        return [{"id": f"u{i}", "name": "Bash", "ts": t0, "input": {"command": c}, "cwd": "", "session": ""} for i, c in enumerate(cmds)]

    @reg
    def r3_s14_r3_006_phase2_command_position():
        # 006 — 검색 인자 안 문구(`rg 'gpt-call.sh verify' docs`)는 Phase 2 실행이 아니다 · 실제 호출은 실행 · 함수 본문 안은 판정 불가(None)
        from ab_ledger_transcript import _plan_phase2
        cases = [bash_uses("rg 'gpt-call.sh verify' docs"), bash_uses('bash "$P/scripts/gpt-call.sh" verify --cd g --out o'),
                 bash_uses("f() { bash scripts/gpt-call.sh verify --out o; }; echo x")]
        got = tuple(_plan_phase2(u, {x["id"]: {"is_error": False} for x in u}) for u in cases)
        return got == (False, True, None), [str(got)]

    @reg
    def r3_s14_launcher_wrapped_forms():
        # 8.5 2차 뒤 발견 — 예약어 · 경로 래퍼 · 옵션 든 래퍼 뒤 런처 호출도 센다 · 묶음 옵션처럼 판정 못 한 꼴은 0 이 아니라 미측정
        from ab_ledger_transcript import _launcher_calls
        cmds = ["if bash scripts/gpt-call.sh independent-review --out x; then echo ok; fi",
                "/usr/bin/time -p bash scripts/gpt-call.sh independent-plan --out x",
                "caffeinate -i bash scripts/gpt-call.sh independent-review --out x",
                "caffeinate -dims bash scripts/gpt-call.sh independent-review --out x"]
        calls = [_launcher_calls([{"id": "u", "ts": t0, "input": {"command": c}}], {}, {"u": {"ts": t0}}) for c in cmds]
        got = [[(x["mode"], bool(x.get("unsure"))) for x in cs] for cs in calls]
        want = [[("review", False)], [("plan", False)], [("review", False)], [(None, True)]]
        return got == want and launcher_unmeasured(calls[3], 1) == 1, [str(got)]

    @reg
    def r3_s14_uuid_chain_gap():
        # 줄째 삭제 — uuid 사슬이 있는 형식에서 가운데 줄이 빠지면 부모 uuid 가 끊긴다(워커 · Lead 같은 함수 · 실측 끊김 0)
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            p = os.path.join(td, "agent-a1.jsonl")
            evs = [{"type": "user", "uuid": "u1", "parentUuid": None, "timestamp": "2026-01-01T00:00:00Z", "message": {"role": "user", "content": "go"}},
                   stop_line("m1", "u2", "u1", 1),
                   {"type": "user", "uuid": "u3", "parentUuid": "u2", "timestamp": "2026-01-01T00:00:02Z", "message": {"role": "user", "content": "more"}},
                   stop_line("m2", "u4", "u3", 3)]
            jl(p, evs)
            clean = wfm.read_agent(p)["format_problems"]
            jl(p, evs[:1] + evs[2:])
            gap, lead = wfm.read_agent(p)["format_problems"], parse_transcript(p)["format_problems"]
            return clean == {} and gap.get("parentUuid") == 1 and lead.get("parentUuid") == 1, [str(clean), str(gap), str(lead)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_s14_empty_assistant_content():
        # 블록 삭제 — 마지막 StructuredOutput 은 답(tool_result)이 없는 것이 정상이라 고아 규칙에 안 걸린다 · 블록이 빠져 빈 목록이 된 응답 줄을 잡는다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            p = os.path.join(td, "agent-a1.jsonl")
            so = {"type": "assistant", "timestamp": "2026-01-01T00:00:02Z",
                  "message": {"id": "m2", "content": [{"type": "tool_use", "id": "t9", "name": "StructuredOutput", "input": {"ok": True}}]}}
            jl(p, [stop_line("m1"), so])
            clean = wfm.read_agent(p)["format_problems"]
            so["message"]["content"] = []
            jl(p, [stop_line("m1"), so])
            cut, lead = wfm.read_agent(p)["format_problems"], parse_transcript(p)["format_problems"]
            ok = clean == {} and cut.get("assistant.content-empty") == 1 and lead.get("assistant.content-empty") == 1
            return ok, [str(clean), str(cut), str(lead)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_s14_gpt_banner_complete():
        # 스트림 로그 배너는 줄로 읽는다 — 버전 줄이 빠지거나 model 줄이 잘리거나 둘째 구분선이 없으면 빈 칸을 남긴 배너가 아니라 배너 없음이다
        from ab_ledger_collect import parse_gpt_log
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            head = ["OpenAI GPT-CLI v0.157.0", "--------", "model: gpt-6-sol", "reasoning effort: xhigh",
                    "session id: 01a0d8c9-7239-7ae1-9e9c-832f78b30c8b", "--------", "user", "model: not-a-banner"]
            def got(ls):
                p = os.path.join(td, "g.json.stream.log")
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write("\n".join(ls) + "\n")
                return parse_gpt_log(p)
            full = got(head)
            # 둘째 = 색 입힌 실제 줄 `\x1b[1mmodel:\x1b[0m gpt-6-sol` 의 앞 절반 — 값 자리에 색 조각만 남는다
            cases = [got(head[1:]), got(head[:2] + ["\x1b[1mmodel:\x1b["] + head[3:]), got(head[:5] + head[6:])]
            ok = full == {"model": "gpt-6-sol", "effort": "xhigh", "version": "0.157.0", "session": "01a0d8c9-7239-7ae1-9e9c-832f78b30c8b"} \
                and cases == [None, None, None]
            return ok, [str(full), str(cases)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    # ── S14 r4 처분(2026-11-11) — 지적마다 셀 하나 · 제거 probe 짝은 작업 폴더 removal-spec-S14.py ─────────────
    @reg
    def r3_s14_r4_001_tool_result_shape():
        # 001 — 결과의 content 를 지우거나 is_error 를 "false" 문자열로 바꾸면 빈 결과 · 오류로 읽지 않고 형식 위반이다(워커 · Lead 같은 함수)
        import collections

        def fmt(block):
            ev = {"type": "user", "timestamp": "2026-01-01T00:00:01Z", "message": {"role": "user", "content": [block]}}
            return wfm.event_format(ev, set(), [], collections.defaultdict(set))
        good = {"type": "tool_result", "tool_use_id": "x", "content": "external"}
        got = [fmt(good), fmt({"type": "tool_result", "tool_use_id": "x"}), fmt(dict(good, is_error="false"))]
        return got == [[], ["tool_result.content"], ["tool_result.content"]], [str(got)]

    @reg
    def r3_s14_r4_002_skip_flag_type():
        # 002 — 조건부 생략 표지가 정본 형(null · bool · {reason})이 아니면("false" 문자열) 생략으로 읽지 않고 형식 위반이다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            m = {"agentCalls": 3, "nullCount": 0, "fallbackCount": 0, "stagesCompleted": 2}

            def run(ms):
                p = os.path.join(td, "t.jsonl")
                ret = json.dumps({"mode": "workflow", "metrics": m, "mergeSkipped": ms})
                jl(p, [{"type": "user", "timestamp": "2026-01-01T00:00:00Z", "message": {"content": "/fz:fz-plan"}},
                       {"type": "assistant", "timestamp": "2026-01-01T00:01:00Z",
                        "message": {"id": "m1", "content": [{"type": "tool_use", "id": "w1", "name": "Workflow", "input": {}}]}},
                       {"type": "user", "timestamp": "2026-01-01T00:01:01Z",
                        "message": {"content": [{"type": "tool_result", "tool_use_id": "w1", "content": "started"}]},
                        "toolUseResult": {"runId": "wf_1", "transcriptDir": os.path.join(td, "wf1"), "workflowName": "plan-lean2"}},
                       {"type": "user", "timestamp": "2026-01-01T00:01:30Z",
                        "message": {"content": f"<task-notification>\n<tool-use-id>w1</tool-use-id>\n<status>completed</status>\n"
                                               f"<result>{ret}</result>\n</task-notification>"}}])
                return parse_transcript(p)["format_problems"].get("workflow.return.mergeSkipped", 0)
            got = [run({"reason": "빈 렌즈"}), run(None), run(False), run("false")]
            return got == [0, 0, 0, 1], [str(got)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_s14_r4_003_data_heredoc_not_shell():
        # 003 — 데이터 heredoc 본문 안의 `bash <<` 글자는 셸 명령이 아니다 · 명령 자리 셸에 먹인 heredoc 본문은 명령이다
        from ab_ledger_transcript import _plan_phase2
        data = "cat <<'DATA'\nbash <<'SH'\ngpt-call.sh 'verify'\nSH\nDATA"
        real = "bash <<'SH'\nbash scripts/gpt-call.sh verify --out o\nSH"
        got = tuple(_plan_phase2(bash_uses(c), {"u0": {"is_error": False}}) for c in (data, real))
        return got == (False, True), [str(got)]

    @reg
    def r3_s14_r4_004_quoted_launcher_mode():
        # 004 — 모드 인자를 따옴표로 감싼 런처 호출도 센다(원문 글자 거르기가 따옴표에서 끊기지 않는다)
        from ab_ledger_transcript import _launcher_calls
        calls = _launcher_calls([{"id": "u", "ts": t0, "input": {"command": "bash /p/gpt-call.sh 'independent-review' --out-dir /r"}}],
                                {}, {"u": {"ts": t0}})
        got = [(x["mode"], bool(x.get("unsure"))) for x in calls]
        return got == [("review", False)], [str(got)]

    @reg
    def r3_s14_r4_005_definite_plus_deferred():
        # 005 — 확정 호출과 함수 본문 호출이 한 명령에 있으면 확정 1건 + 미측정 1건이다(확정이 미측정을 지우지 않는다)
        from ab_ledger_transcript import _launcher_calls
        cmd = "gpt-call.sh independent-plan; f() { gpt-call.sh independent-review; }; f"
        calls = _launcher_calls([{"id": "u", "ts": t0, "input": {"command": cmd}}], {}, {"u": {"ts": t0}})
        got = [(x["mode"], bool(x.get("unsure"))) for x in calls]
        return got == [("plan", False), (None, True)] and launcher_unmeasured(calls, 1) == 1, [str(got)]

    def gpt_scan(td, calls, spawn_audit=0, doc=None):
        from ab_ledger_gpt import gpt_source_problems, scan_gpt_rollouts
        rd = os.path.join(td, "g.rollouts")
        os.makedirs(rd, exist_ok=True)
        host = "\n## Skills\n### Available\n- fz-reviewer: d (r0/fz-reviewer/SKILL.md)\n"
        jl(os.path.join(rd, "r.jsonl"), [{"type": "session_meta", "payload": {"id": "s1"}},
                                          {"type": "world_state", "payload": {"state": {"host_skills": {"body": host}}}},
                                          {"type": "turn_context", "payload": {"model": "gpt-6-sol"}}]
           + [{"type": "response_item", "payload": c} for c in calls])
        sc = scan_gpt_rollouts(rd)
        audit = {"mode": "review", "exit": 0, "note": "ok", "timedOut": False, "isolationApplied": True, "spawnAgent": spawn_audit,
                 "hits": [], "inputs": {}, "toolCalls": len(calls), "rollouts": 1, "turnContexts": 1, "wrapperExit": 0}
        base = {"verdict": "approved", "issues": [], "craft": [], "axis_coverage": [], "projectRules": {"rules": [], "conflicts": [], "gaps": []}}
        return sc, gpt_source_problems(audit, dict(base, **(doc or {})), sc)

    @reg
    def r3_s14_r4_006_function_call_arguments():
        # 006 — 인자를 잃은 function_call 을 명령 0 건으로 읽지 않는다(형식 위반)
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            fc = {"type": "function_call", "name": "exec_command", "arguments": json.dumps({"cmd": "cat x"})}
            _, ok_p = gpt_scan(os.path.join(td, "a"), [fc])
            _, bad_p = gpt_scan(os.path.join(td, "b"), [{k: v for k, v in fc.items() if k != "arguments"}])
            return ok_p.get("function_call.arguments") is None and bad_p.get("function_call.arguments") == 1, [str(ok_p), str(bad_p)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_s14_r4_007_output_item_fields():
        # 007 — 출력 항목에서 판정이 읽는 칸(ruleSource 등)이 빠지면 '규칙 근거 없음' 으로 읽지 않고 형식 위반이다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            item = {"id": "C1", "ruleSource": "plugin-default", "ruleRef": None, "severity": "major", "craftAxis": "naming",
                    "title": "t", "detail": "d"}
            _, ok_p = gpt_scan(os.path.join(td, "a"), [], doc={"craft": [item]})
            _, bad_p = gpt_scan(os.path.join(td, "b"), [], doc={"craft": [{k: v for k, v in item.items() if k != "ruleSource"}]})
            return "output.craft" not in ok_p and bad_p.get("output.craft") == 1, [str(ok_p), str(bad_p)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_s14_r4_008_spawn_recount():
        # 008 — 감사 spawnAgent 는 rollout 재계수와 같아야 하고 · 기록하는 spawned 는 재계수만이다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            sc, ok_p = gpt_scan(os.path.join(td, "a"), [], spawn_audit=0)
            _, bad_p = gpt_scan(os.path.join(td, "b"), [], spawn_audit=3)
            ok = ("audit.spawnAgent≠rollout" not in ok_p and bad_p.get("audit.spawnAgent≠rollout") == 1
                  and agents_record({"gpt_agents": True}, sc, {"spawnAgent": 3}) == {"requested": True, "spawned": 0})
            return ok, [str(ok_p), str(bad_p)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_s14_r4_009_gpt_home_bad_line():
        # 009 — arm GPT 홈 세션의 파싱 불가 줄을 건너뛰지 않는다. 함수 겹: gpt_home_sessions 가 그 파일을 bad_lines 로 낸다(언제나 돈다)
        # 끝까지 겹: collect → judge 를 지나 그 run 이 빠진다(온전한 세션은 유효 그대로) — tests/ 가 있는 저장소에서만 돌고 그때 faults 가 없으면 실패다
        # (scripts 만 복사한 사본에서는 함수 겹만 잰다 — structure-d selftest-outside-fingerprint)
        from ab_ledger_transcript import gpt_home_sessions
        meta = json.dumps({"type": "session_meta", "payload": {"id": "s1", "cli_version": "0.157.0"}})
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            d = os.path.join(td, "sessions")
            os.makedirs(d)
            with open(os.path.join(d, "good.jsonl"), "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"type": "session_meta", "payload": {"id": "s0"}}) + "\n"
                         + json.dumps({"type": "turn_context", "payload": {"model": "gpt-6-sol", "effort": "xhigh"}}) + "\n")
            with open(os.path.join(d, "bad.jsonl"), "w", encoding="utf-8") as fh:
                fh.write(meta + '\n{"type":"turn_context","payload":\n')
            got = gpt_home_sessions(td) or []
        finally:
            shutil.rmtree(td, ignore_errors=True)
        fn_ok = (sorted((x.get("file"), bool(x.get("bad_lines"))) for x in got if x.get("bad_lines")) == [("bad.jsonl", True)]
                 and [x.get("session") for x in got if not x.get("bad_lines")] == ["s0"])
        tests_dir = os.path.join(os.path.dirname(here), "tests")
        if not os.path.isdir(tests_dir):
            return fn_ok, [f"함수 겹만(tests/ 없음) {got}"]
        sys.path.insert(0, os.path.join(tests_dir, "ab"))
        try:
            import faults
        finally:
            sys.path.pop(0)
        work = tempfile.mkdtemp(prefix="abl-")
        try:
            st = faults.CollectStage(work)
            home = os.path.join(work, "inputs", "B1", "gpt-home", "sessions")
            os.makedirs(home)
            p = os.path.join(home, "r.jsonl")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(meta + "\n" + json.dumps({"type": "turn_context", "payload": {"model": "gpt-6-sol", "effort": "xhigh"}}) + "\n")
            v_ok, _ = st.verdict()
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(meta + '\n{"type":"turn_context","payload":\n')
            v_bad, _ = st.verdict()
            return fn_ok and (v_ok, v_bad) == ("valid", "excluded"), [f"함수 겹 {fn_ok} · {v_ok} · {v_bad}"]
        finally:
            shutil.rmtree(work, ignore_errors=True)

    @reg
    def r3_s14_gpt_audit_counters_bound():
        # 런처 감사의 계수(rollouts · turnContexts · toolCalls)는 rollout 사본을 다시 센 값과 같아야 한다 — 줄이 빠진 사본을 잡는다(실측 71/71)
        from ab_ledger_gpt import gpt_source_problems, scan_gpt_rollouts
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            rdir = os.path.join(td, "g.rollouts")
            os.makedirs(rdir)
            lines = [{"type": "session_meta", "payload": {"id": "s"}},
                     {"type": "world_state", "payload": {"state": {"host_skills": {"body": "- a: d"}}}},
                     {"type": "turn_context", "payload": {"model": "m"}},
                     {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec", "input": "x"}}]
            audit = {"mode": "review", "exit": 0, "note": "ok", "timedOut": False, "isolationApplied": True, "spawnAgent": 0, "hits": [],
                     "inputs": {}, "toolCalls": 1, "rollouts": 1, "turnContexts": 1, "wrapperExit": 0}
            doc = {"verdict": "approved", "projectRules": {"rules": [], "conflicts": [], "gaps": []}}
            jl(os.path.join(rdir, "r.jsonl"), lines)
            clean = gpt_source_problems(audit, doc, scan_gpt_rollouts(rdir))
            jl(os.path.join(rdir, "r.jsonl"), lines[:3])
            drop = gpt_source_problems(audit, doc, scan_gpt_rollouts(rdir))
            return clean == {} and drop.get("audit.toolCalls≠rollout") == 1, [str(clean), str(drop)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_s14_input_self_hash():
        # `input` 기록은 자기 해시를 싣는다 — 칸이 빠지거나 형이 바뀐 기록(커밋 하나 · clean 형)은 collect 가 입력 기록 없음으로 본다
        from ab_ledger_collect import input_record_ok
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            repo, out = os.path.join(td, "repo"), os.path.join(td, "input.json")
            os.makedirs(repo)
            with open(os.path.join(repo, "a.txt"), "w", encoding="utf-8") as fh:
                fh.write("a\n")
            g = ["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]
            for c in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "x"]):
                subprocess.run(g + c, capture_output=True, check=True)
            p = cli("input", "--root", repo, "--fixture", "fx", "--out", out, "--plugin-root", repo, "--plugin-source", repo)
            if not os.path.isfile(out):
                return False, [p.stdout[-300:], p.stderr[-300:]]
            rec = json.load(open(out, encoding="utf-8"))
            no_commit = dict(rec, commits={})
            flipped = dict(rec, clean="x")
            ok = (p.returncode == PASS and input_record_ok(rec) and not input_record_ok(no_commit) and not input_record_ok(flipped)
                  and not input_record_ok({k: v for k, v in rec.items() if k != "sha256"}))
            return ok, [p.stdout[-200:]]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_s14_snapshot_hash_bound():
        # 상태 스냅샷은 기록한 hash 를 다시 잰다 — 감시 파일 하나 · exists · 감시 이름이 빠지거나 형이 바뀐 스냅샷은 비교하지 않는다
        from ab_ledger_collect import snapshot, snapshot_ok
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            d = os.path.join(td, "mem")
            os.makedirs(d)
            with open(os.path.join(d, "MEMORY.md"), "w", encoding="utf-8") as fh:
                fh.write("m\n")
            snap = snapshot({"repo_agent_memory": d})
            lost = json.loads(json.dumps(snap))
            lost["watch"]["repo_agent_memory"]["files"] = {}
            flip = json.loads(json.dumps(snap))
            flip["watch"]["repo_agent_memory"]["exists"] = "x"
            ok = snapshot_ok(snap) and not snapshot_ok(lost) and not snapshot_ok(flip) and not snapshot_ok(dict(snap, watch="x"))
            return ok, [str(snap)[:160]]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def r3_s14_collect_unrun_on_malformed():
        # 원천 형식이 계측기 가정 밖이라 행을 만들 · 직렬화할 수 없으면 collect 는 UNRUN 이고 원장에 아무것도 쓰지 않는다(예외로 죽지 않는다)
        import argparse
        import contextlib
        import io
        import ab_ledger
        td = tempfile.mkdtemp(prefix="abl-")
        orig = ab_ledger.build_row
        try:
            tr, led = os.path.join(td, "t.jsonl"), os.path.join(td, "ledger.jsonl")
            open(tr, "w", encoding="utf-8").close()
            ab_ledger.build_row = lambda a, dry=False: {"run_id": "X", "x": {1: "a", "b": 2}}   # 정렬 불가 키(형이 뒤집힌 원천 값)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = ab_ledger.cmd_collect(argparse.Namespace(phase="baseline", transcript=tr, ledger=led, run_id="X", run=1))
            return rc == UNRUN and not os.path.exists(led) and "수집 실패" in buf.getvalue(), [buf.getvalue()[:200]]
        finally:
            ab_ledger.build_row = orig
            shutil.rmtree(td, ignore_errors=True)
