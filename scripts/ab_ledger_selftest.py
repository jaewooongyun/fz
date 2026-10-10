# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 형제 모듈 import 와 계측기 해시에 이 파일의 디렉토리만 쓴다.
"""ab_ledger_selftest.py — A/B 원장 판정기 self-test(`ab_ledger.py --self-test` 가 이 모듈을 싣는다).

⛔ 계측기 지문(INSTRUMENTS) 밖이다 — 실행 경로(collect · judge …)는 이 모듈을 import 하지 않는다. 사례만 고친 변경은
   instrument_sha 를 바꾸지 않아 채점 행이 낡지 않는다. 판정 코드를 여기에 두지 않는다(지문 밖 코드가 판정에 섞인다).
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import tempfile

import fz_wf_metrics as wfm   # noqa: E402 — 형제 모듈(Workflow 폴더 집계)
from ab_ledger_base import (AXES6, DEFAULT_EFFORT, DEFAULT_MODEL, FAIL, PASS, STATE_SCHEMA, UNRUN, instrument_sha, iso)
from ab_ledger_transcript import (CPMV_RE, GPT_CALL_RE, PHASE2_RE, REAL_HOME_SKILL_RE, _bash_writes, _call_segment, _cd_bases,
    _cmd_views, _exec_of, _follow_moves, _launcher_calls, _launcher_ok, _merge_summaries, _mv_pairs, _plan_phase2,
    _redirect_targets, _resolve_vars, _segments, _shell_part, _writes_path, gpt_home_sessions, parse_transcript, queued_followups)
from ab_ledger_collect import (CANON_PATTERN, CANON_WATCH, append, append_many, expected_stages_completed, required_stages,
    state_hash, state_info, wf_summary)
from ab_ledger_judge import (SC7_FIELDS, VERIFY_FIELDS, blind_pack, blind_unpack, cite_spans, judge_rows, near_labels,
    recollect_diff, score_plan, score_review)
from ab_ledger_gpt import (_sha_file, build_gpt_row, classify_skill_refs, gpt_sc1_problems, gpt_sc2_problems, judge_gpt,
    scan_gpt_rollouts, verify_gpt_row)


# ── self-test ──────────────────────────────────────────────────────────
INSTR_NOW = instrument_sha()


def _mk(run_id, arm, order, crit=1, major=2, wall=1000.0, **kw):
    """판정기용 최소 유효 run + score."""
    row = {"type": "run", "run_id": run_id, "workflow": kw.get("workflow", "fz-review"), "arm": arm,
           "run": kw.get("run", 1), "order": order, "phase": kw.get("phase", "baseline" if arm == "B" else "change"),
           "release": kw.get("release"), "fixture": kw.get("fixture", "fx"),
           "lead": {"model": kw.get("model", DEFAULT_MODEL), "effort": kw.get("effort", DEFAULT_EFFORT),
                    "cli_versions": ["2.1.282"], "out_tok": kw.get("out_tok", 5000), "messages": 40, "tool_errors": 1,
                    "followup_prompts": 0},
           "wf": {"models": {kw.get("wmodel", DEFAULT_MODEL): 10}, "efforts": {kw.get("weffort", DEFAULT_EFFORT): 10},
                  "advisor": 0, "stages": kw.get("stages", ["R1-arch", "R1-quality", "R3-counter"]),
                  "out_tok": 9000, "turns": 30, "so_retries": 0},
           "gpt": {"calls": kw.get("gpt_calls", 1), "ok": kw.get("gpt_ok", 1), "failed": kw.get("gpt_failed", 0),
                   "launcher_ok": kw.get("gpt_launcher_ok", 0),
                   "banners": kw.get("banners", 1), "unlinked": kw.get("unlinked", 0),
                   "models": ["gpt-6-sol"], "efforts": ["xhigh"], "versions": ["0.157.0"]},
           "plugin": {"sha": "10197a0aaaa", "dirty": False, "tree_hash": kw.get("tree", "tB" if arm == "B" else "tC"),
                      "source": kw.get("psource", f"/src/{arm}"),
                      "source_tree_hash": kw.get("psource_tree", kw.get("tree", "tB" if arm == "B" else "tC"))},
           "artifacts": [{"path": f"/runs/{run_id}/a.md", "sha256": f"a-{run_id}"}],
           "injected": {"User": "u", "Project": "p", "AutoMem": None}, "instrument_sha": "i1",
           "input": {"hash": kw.get("input", "h1"), "root": kw.get("root", f"/runs/{run_id}/repo"), "tree_hash": "it1"},
           "wall": {"total_s": wall, "mtime_delta_s": 0.4, "workflows": [{"run_id": "w", "wf_s": 600, "lead_s": 610,
                                                                          "delta_pct": 1.64}]},
           "state": {"start_hash": "s", "pristine_hash": "s", "end_hash": "e", "leak": kw.get("leak", []),
                     "problems": kw.get("problems", [])},
           "complete": {"ok": kw.get("complete", True), "why": [] if kw.get("complete", True) else ["완료 알림 없음"]}}
    axes = kw.get("axes", {a: 1 for a in AXES6})
    score = {"type": "score", "run_id": run_id, "kind": "review", "fixture_sha": "L",
             "by_severity": {"critical": crit, "major": major, "minor": 0, "suggestion": 0},
             "by_axis": axes, "verified_ratio": kw.get("ratio", 0.8), "empty": False,
             "verified": kw.get("verified", True), "artifacts_sha": kw.get("score_arts", [f"a-{run_id}"]),
             "instrument_sha": kw.get("score_instr", INSTR_NOW), "blind_pack_sha": kw.get("pack", "P1")}
    return row, score


def _judge(rows_scores, **opt):
    runs = {r["run_id"]: r for r, _ in rows_scores}
    scores = {s["run_id"]: s for _, s in rows_scores}
    opts = {"model": DEFAULT_MODEL, "effort": DEFAULT_EFFORT, "phase": opt.get("phase"), "arm": opt.get("arm", "C"),
            "release": opt.get("release"), "workflows": ["fz-review"], "min_runs": opt.get("min_runs", 2),
            "runs": opt.get("runs", 1), "plugin_sha": opt.get("plugin_sha"), "require": opt.get("require", []),
            "envs": opt.get("envs"), "options_on": False, "require_passed": None}
    return judge_rows(runs, scores, opts)


def _write_lines(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def self_test(case=None):
    cases = {}

    def reg(fn):
        cases[fn.__name__.replace("_", "-")] = fn
        return fn

    base = lambda **kw: [_mk("B1", "B", 1, major=3, **kw.get("b1", {})), _mk("B2", "B", 3, major=2, **kw.get("b2", {}))]

    @reg
    def sc3_pass():
        rc, out = _judge(base() + [_mk("C1", "C", 2, major=2), _mk("C2", "C", 4, major=3)], require=["SC-3"])
        return rc == PASS, out

    @reg
    def sc3_fail():
        rc, out = _judge(base() + [_mk("C1", "C", 2, major=1), _mk("C2", "C", 4, major=1)], require=["SC-3"])
        return rc == FAIL and any("major" in x and "> N" in x for x in out), out

    @reg
    def sc3_smoke():
        ok_rc, a = _judge(base() + [_mk("S1", "C", 5, major=2, phase="release-smoke", release="R-A")],
                          phase="release-smoke", release="R-A", require=["SC-3-smoke"], runs=1)
        bad_rc, b = _judge(base() + [_mk("S1", "C", 5, major=1, phase="release-smoke", release="R-A")],
                           phase="release-smoke", release="R-A", require=["SC-3-smoke"], runs=1)
        two_rc, c = _judge(base() + [_mk("S1", "C", 5, phase="release-smoke", release="R-A"),
                                     _mk("S2", "C", 6, phase="release-smoke", release="R-A")],
                           phase="release-smoke", release="R-A", require=["SC-3-smoke"], runs=1)
        return (ok_rc, bad_rc, two_rc) == (PASS, FAIL, FAIL), a + b + c

    @reg
    def sc6_pass_fail():
        good_rc, a = _judge([_mk("B1", "B", 1, wall=1000), _mk("B2", "B", 3, wall=1100),
                             _mk("C1", "C", 2, wall=700), _mk("C2", "C", 4, wall=760)], require=["SC-6"])
        bad_rc, b = _judge([_mk("B1", "B", 1, wall=1000), _mk("B2", "B", 3, wall=1100),
                            _mk("C1", "C", 2, wall=1000), _mk("C2", "C", 4, wall=1020)], require=["SC-6"])
        return (good_rc, bad_rc) == (PASS, FAIL), a + b

    @reg
    def crossover_violation():
        bad_rc, a = _judge([_mk("B1", "B", 1), _mk("B2", "B", 2), _mk("C1", "C", 3), _mk("C2", "C", 4)],
                           require=["crossover-order"])
        good_rc, b = _judge([_mk("B1", "B", 1), _mk("C1", "C", 2), _mk("B2", "B", 3), _mk("C2", "C", 4)],
                            require=["crossover-order"])
        return (bad_rc, good_rc) == (FAIL, PASS), a + b

    @reg
    def sc5_negative():
        # 계획 채점표 항목을 전부 덮으면 PASS · 잔재 1건 누락이면 FAIL · feature fixture 만 있으면 UNRUN(제거 조항 미판정)
        FEAT, REM = ["RC1", "Q1a", "L1"], ["RC1", "Q1a", "L1", "RZ1", "CU1"]

        def plan(run_id, arm, order, fx, items, covered):
            row, score = _mk(run_id, arm, order, workflow="fz-plan", fixture=fx)
            crit = sum(1 for i in items if i.startswith(("RZ", "CU")))
            score = dict(score, kind="plan", items=items, covered=covered, items_total=len(items),
                         items_by_severity={"critical": crit, "major": len(items) - crit, "minor": 0, "suggestion": 0})
            return row, score

        def grp(fx, items, c2_cov):
            return [plan(f"{fx}-B1", "B", 1, fx, items, items), plan(f"{fx}-B2", "B", 3, fx, items, items),
                    plan(f"{fx}-C1", "C", 2, fx, items, items), plan(f"{fx}-C2", "C", 4, fx, items, c2_cov)]

        def j(rs):
            return judge_rows({r["run_id"]: r for r, _ in rs}, {s["run_id"]: s for _, s in rs},
                              dict(model=DEFAULT_MODEL, effort=DEFAULT_EFFORT, phase=None, arm="C", release=None,
                                   workflows=["fz-plan"], min_runs=2, runs=1, plugin_sha=None, require=["SC-5"],
                                   envs=None, options_on=False, require_passed=None))
        ok_rc, a = j(grp("feat", FEAT, FEAT) + grp("rem", REM, REM))
        miss_rc, b = j(grp("feat", FEAT, FEAT) + grp("rem", REM, ["RC1", "Q1a", "L1", "CU1"]))
        only_rc, c = j(grp("feat", FEAT, FEAT))
        return ((ok_rc, miss_rc, only_rc) == (PASS, FAIL, UNRUN) and any("⛔누락 ['RZ1']" in x for x in b)), a + b + c

    @reg
    def cp_dest_stops_at_operator():
        # 실측 명령 모양 — heredoc 뒤 `&& cp A B && … head -1`. 대상은 B 여야 하고 `-1` 이 아니다
        cmd = ("python3 - <<'EOF'\nx = 1\nEOF\npython3 gen.py 3 && cp P/plan-v3.md P/plan-final.md && R=/r; W=$PWD/P; "
               "python3 $R/g.py --out $W/g.md && cp $W/g.md $W/plan.md; echo \"E=$?\"; grep -c H $W/x | head -1")
        dests = [m.group(2) for m in CPMV_RE.finditer(_shell_part(cmd))]
        hit = _bash_writes(cmd, "/repo/P/plan-final.md", "/repo")
        miss = _bash_writes("cp P/a.md P/b.md && echo done", "/repo/P/plan-final.md", "/repo")
        return (dests[:1] == ["P/plan-final.md"] and "-1" not in dests and hit and not miss), [str(dests), hit, miss]

    @reg
    def writes_sed_inplace_and_renderer():
        # 실측(C1 마지막 명령) — 렌더러 --out-dir 가 review-report.md 를, sed -i '' 가 self-review.md 를 고쳤다
        cmd = ("WD=/r/ABT-1001; PR=/r/plugin\npython3 - \"$WD/review/review.json\" <<'PY'\nx=1\nPY\n"
               "rm -f $WD/review/review-report.md $WD/review/pr-comments.md\n"
               "python3 $PR/scripts/render_review.py --review $WD/review/review.json --diff $WD/review/diff.patch --out-dir $WD/review | head -2; echo x\n"
               "sed -i '' 's/suggestion 3/suggestion 4/' $WD/review/self-review.md $WD/index.md\n"
               "grep -n 's|a|b|' $WD/review/self-review.md | head")
        rep = _bash_writes(cmd, "/r/ABT-1001/review/review-report.md", "/r/plugin")
        sr = _bash_writes(cmd, "/r/ABT-1001/review/self-review.md", "/r/plugin")
        idx = _bash_writes(cmd, "/r/ABT-1001/index.md", "/r/plugin")
        # 음성 대조 — 읽기만(grep · cat · sed 출력) · rm · 렌더러 self-test · sed -n 은 쓰기가 아니다
        neg = [_bash_writes(x, "/r/ABT-1001/review/self-review.md", "/r")
               for x in ("grep -n x /r/ABT-1001/review/self-review.md", "sed -n 1,5p /r/ABT-1001/review/self-review.md",
                         "sed 's/a/b/' /r/ABT-1001/review/self-review.md > /tmp/o", "rm -f /r/ABT-1001/review/self-review.md",
                         "python3 /r/plugin/scripts/render_review.py --self-test")]
        gnu = _bash_writes("sed -i -e 's/a/b/' /r/f.md", "/r/f.md", "/r")
        return (rep and sr and idx and gnu and not any(neg)), [rep, sr, idx, gnu, neg]

    @reg
    def lead_cwd_is_session_start():
        # Lead 가 플러그인 폴더에 오래 머물러도(최빈 cwd = plugin) 작업 폴더는 세션 시작 cwd(repo)다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            evs = [{"type": "user", "timestamp": "2026-01-01T00:00:00Z", "cwd": "/runs/x/repo", "message": {"content": "/fz:fz-review"}}]
            evs += [{"type": "assistant", "timestamp": f"2026-01-01T00:00:0{i}Z", "cwd": "/runs/x/plugin", "version": "2.1.282",
                     "message": {"id": f"m{i}", "model": "claude-opus-5-5", "stop_reason": "end_turn", "usage": {"output_tokens": 1},
                                 "content": [{"type": "text", "text": "t"}]}} for i in range(1, 6)]
            p = os.path.join(td, "t.jsonl")
            _write_lines(p, evs)
            tp = parse_transcript(p)
            return (tp["cwd"] == "/runs/x/repo" and tp["cwds"].get("/runs/x/plugin") == 5), [tp["cwd"], tp["cwds"]]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def gpt_out_var_resolved():
        # 실측(plan B1) — `W=$PWD/ABT-2001; …; "$R/scripts/gpt-exec.sh" exec --cd "$PWD" --out "$W/plan/gpt-verify.json"`
        cmd = 'W=$PWD/ABT-2001; R=/r/plugin; export FZ_PLUGIN_ROOT=$R; "$R/scripts/gpt-exec.sh" exec --cd "$PWD" --out "$W/plan/g.json"'
        a_ = _resolve_vars("$W/plan/g.json", cmd, "/runs/x/repo")
        b_ = _resolve_vars("$Q/plan/g.json", cmd, "/runs/x/repo")
        # 실측(review B2) — cwd=plugin 에서 `cd /runs/x/repo && R="$PWD" && …gpt-exec.sh review --out "$R/…"`
        c_ = _resolve_vars("$R/ABT-1001/review/gpt-review.md", 'cd /runs/x/repo && R="$PWD" && /p/gpt-exec.sh review --out "$R/o"', "/runs/x/plugin")
        d_ = _resolve_vars("$PWD/$W/o", "cd sub && W=a/b; x", "/runs/x")
        return (a_ == "/runs/x/repo/ABT-2001/plan/g.json" and b_ == "$Q/plan/g.json"
                and c_ == "/runs/x/repo/ABT-1001/review/gpt-review.md" and d_ == "/runs/x/sub/a/b/o"), [a_, b_, c_, d_]

    @reg
    def merge_summary_and_ac4():
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            f = os.path.join(td, "merged.json")
            with open(f, "w", encoding="utf-8") as fh:
                json.dump({"summary": {"candidatesIn": 5, "candidatesOut": 5}}, fh)
            uses = [{"name": "Bash", "id": "1", "cwd": td, "input": {"command": f"WD={td}; python3 /p/scripts/review_merge.py --claude a --gpt b --diff d --out $WD/merged.json"}},
                    {"name": "Bash", "id": "2", "cwd": td, "input": {"command": "python3 scripts/review_merge.py --claude a --gpt-unavailable x --diff d"}},
                    {"name": "Bash", "id": "3", "cwd": td, "input": {"command": "wc -l scripts/review_merge.py; sed -n 1,5p scripts/review_merge.py"}},
                    {"name": "Bash", "id": "4", "cwd": td, "input": {"command": "python3 scripts/review_merge.py --self-test"}}]
            res = {"2": {"text": '{"summary": {"candidatesIn": 7, "candidatesOut": 7}}'}}
            m_ = _merge_summaries(uses, res)
            ok_sum = [(x["in"], x["out"]) for x in m_["summaries"]] == [(5, 5), (7, 7)] and m_["violations"] == 0
            rej = _merge_summaries([{"name": "Bash", "id": "5", "cwd": td, "input": {"command": "python3 scripts/review_merge.py --claude a --gpt b --diff d"}}],
                                   {"5": {"is_error": True, "text": "REJECT 후보 보존 위반 — 입력 3 ≠ 출력 2(AC-4)"}})
            rows = base() + [_mk("C1", "C", 2), _mk("C2", "C", 4)]
            for r_, _ in rows[2:]:
                r_["merge"] = {"summaries": [{"in": 5, "out": 5}], "violations": 0}
            good_rc, a_ = _judge(rows, require=["AC-4"])
            rows[3][0]["merge"] = {"summaries": [{"in": 5, "out": 4}], "violations": 0}
            bad_rc, b_ = _judge(rows, require=["AC-4"])
            rows[3][0]["merge"] = None
            none_rc, c_ = _judge(rows, require=["AC-4"])
            return (ok_sum and rej["violations"] == 1 and (good_rc, bad_rc, none_rc) == (PASS, FAIL, FAIL)), [m_, rej, a_, b_, c_]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def plan_phase2_evidence():
        mk = lambda c, err=False: ([{"name": "Bash", "id": "1", "cwd": "/r", "input": {"command": c}}], {"1": {"is_error": err}})
        v = _plan_phase2(*mk('"$R/scripts/gpt-exec.sh" exec --out "$W/plan/gpt-verify.json" --schema "$R/schemas/gpt_review_schema.json"'))
        r_ = _plan_phase2(*mk('"$R/scripts/gpt-exec.sh" resume --session-file "$S" --out o.json'))
        sprint = _plan_phase2(*mk('nohup "$R/scripts/gpt-exec.sh" exec --out "$W/plan/sprint-contract-gpt.md" --prompt-file p &'))
        doc = _plan_phase2(*mk("python3 - <<'EOF'\nx = 'gpt-exec.sh exec --schema gpt_review_schema'\nEOF"))
        fail = _plan_phase2(*mk('"$R/scripts/gpt-exec.sh" resume --session-file s', err=True))
        return (v and r_ and not sprint and not doc and not fail), [v, r_, sprint, doc, fail]

    @reg
    def gpt_home_sessions_count():
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            d = os.path.join(td, "sessions", "2026", "09", "29")
            os.makedirs(d)
            _write_lines(os.path.join(d, "a.jsonl"), [{"type": "session_meta", "payload": {"id": "s1", "cli_version": "0.157.0"}},
                                                      {"type": "turn_context", "payload": {"model": "gpt-6-sol", "effort": "high"}}])
            _write_lines(os.path.join(d, "b.jsonl"), [{"type": "session_meta", "payload": {"id": "s2"}}])
            # review 모드 자식 — id 는 다르고 session_id 가 부모를 가리킨다
            _write_lines(os.path.join(d, "c.jsonl"), [{"type": "session_meta", "payload": {"id": "c1", "session_id": "s2", "cli_version": "0.157.0"}},
                                                      {"type": "turn_context", "payload": {"model": "gpt-6-sol", "effort": "high"}}])
            got = gpt_home_sessions(td)
            empty = tempfile.mkdtemp(prefix="abl-")
            try:
                none_sessions = gpt_home_sessions(empty)
            finally:
                shutil.rmtree(empty, ignore_errors=True)
            return (sorted(x["session"] for x in got) == ["s1", "s2"] and len(got) == 2
                    and gpt_home_sessions(os.path.join(td, "none")) is None and none_sessions == []), [got, none_sessions]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def segments_multiline_quote():
        # 실측(peer C1) — 병합 뒤 같은 줄에서 여는 여러 줄 `python3 -c "…"` 가 병합 명령까지 버리게 했다
        cmd = 'W=/w; P=/p; python3 $P/scripts/review_merge.py --claude a --gpt b --diff d --out $W/m.json; echo "e=$?"; python3 -c "\nimport json\nprint(1)\n"'
        segs = _segments(_shell_part(cmd))
        merged = [x for x in segs if _exec_of(x, "review_merge.py")]
        bad = _segments("echo 'unclosed\necho ok")    # 따옴표가 끝내 안 맞으면 줄마다로 물러선다
        return (len(merged) == 1 and merged[0][-2:] == ["--out", "$W/m.json"] and ["echo", "ok"] in bad), [segs, bad]

    @reg
    def gate_pass_in_redirect_target():
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            with open(os.path.join(td, "da.log"), "w") as fh:
                fh.write("…\nGATE-PASS contract_ok issues=0\n")
            seg = f'bash /p/scripts/gpt-exec.sh exec --cd /r --out "$W/r.json" --prompt-file p > $W/da.log 2>&1'
            tg = _redirect_targets(seg)
            f = _resolve_vars(tg[0], f"W={td}; " + seg, td) if tg else None
            real = bool(REAL_HOME_SKILL_RE.search('SK=$HOME/.codex/skills/fz-challenger/SKILL.md; gpt-exec.sh exec --gpt-skill-path "$SK"'))
            iso_ = bool(REAL_HOME_SKILL_RE.search('SK=${CODEX_HOME:-$HOME/.codex}/skills/fz-challenger/SKILL.md'))
            return (f == os.path.join(td, "da.log") and real and not iso_), [tg, f, real, iso_]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def queued_followup_detected():
        first = "/fz:fz-plan ABT-2001 …"
        mk = lambda pr: {"type": "attachment", "attachment": {"type": "queued_command", "prompt": pr}}
        evs = [mk(first), {"type": "user", "message": {"content": "x"}}, mk("Gate 2 승인·확정 — 추가 질문 없이 plan-final.md 를 기록해줘"),
               mk("<task-notification>\n<task-id>b1</task-id>…"), {"type": "attachment", "attachment": {"type": "hook_success"}},
               {"type": "attachment", "attachment": {"type": "queued_command", "prompt": "<agent-message from=\"a1\">…", "isMeta": True, "origin": "x"}}]
        return (queued_followups(evs, first) == 1 and queued_followups(evs[:2], first) == 0), [queued_followups(evs, first)]

    @reg
    def script_file_argv_write():
        scripts = {"/r/W/plan/mk.py": "import sys\nsrc = open(sys.argv[1]).read()\nopen(sys.argv[2], 'w', encoding='utf-8').write(src)\n"}
        cmd = "W=/r/W/plan; python3 $W/mk.py $W/plan-v3.md $W/plan-final.md && echo ok"
        final = _bash_writes(cmd, "/r/W/plan/plan-final.md", "/r", scripts)
        src = _bash_writes(cmd, "/r/W/plan/plan-v3.md", "/r", scripts)          # argv[1] 은 읽기
        unknown = _bash_writes(cmd, "/r/W/plan/plan-final.md", "/r", {})        # 본문을 모르면 쓰기로 치지 않는다
        here = _bash_writes("python3 - /r/a.md /r/f.md <<'EOF'\nimport sys\nopen(sys.argv[2], 'w').write('x')\nEOF", "/r/f.md", "/r")
        here_read = _bash_writes("python3 - /r/a.md /r/f.md <<'EOF'\nimport sys\nopen(sys.argv[2], 'w').write('x')\nEOF", "/r/a.md", "/r")
        return (final and not src and not unknown and here and not here_read), [final, src, unknown, here, here_read]

    @reg
    def gpt_call_via_variable_and_continuation():
        c1 = 'R=/r; X="/p/scripts/gpt-exec.sh"; ( "$X" exec --cd "$R" --out $R/v.json --prompt-file p --schema /p/schemas/gpt_review_schema.json ) > l 2>&1'
        c2 = '( "/p/scripts/gpt-exec.sh" exec --cd "$R" --out "$W/v.json" --prompt-file p \\\n    --effort high --schema /p/schemas/gpt_review_schema.json )'
        found1 = any(GPT_CALL_RE.search(_shell_part(v)) for v in _cmd_views(c1))
        ph1 = any(PHASE2_RE.search(_shell_part(v)) for v in _cmd_views(c1))
        ph2 = any(PHASE2_RE.search(_shell_part(v)) for v in _cmd_views(c2))
        neg = any(GPT_CALL_RE.search(_shell_part(v)) for v in _cmd_views('X="/p/scripts/gpt-exec.sh"; sed -n 1,5p "$X"'))
        return (found1 and ph1 and ph2 and not neg), [found1, ph1, ph2, neg]

    @reg
    def script_internal_output_path():
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            sp = os.path.join(td, "render_plan.py")
            with open(sp, "w") as fh:
                fh.write('import sys\nW="/r/W"\nOUT = f"{W}/plan/plan-final.md" if sys.argv[1] == "final" else "x"\nopen(OUT, "w").write("x")\n')
            hit = _bash_writes(f"python3 {sp} final a.md b.json", "/r/W/plan/plan-final.md", "/r")
            other = _bash_writes(f"python3 {sp} final a.md b.json", "/r/W/plan/other.md", "/r")
            return (hit and not other), [hit, other]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def script_fstring_argv_output():
        # ⛔ R-D S36 run 1 — `render_plan.py $W final` 이 `open(f'{W}/plan-{ver}.md','w')` 로 썼다(산출물 이름 글자 없음)
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            sp = os.path.join(td, "render_plan.py")
            with open(sp, "w") as fh:
                fh.write("import sys\nW, ver = sys.argv[1], sys.argv[2]\nopen(f'{W}/plan-{ver}.md', 'w').write('x')\n"
                         "open(f'{X}/other-{ver}.md', 'w').write('y')\n")
            cmd = f"W=/r/W/plan; python3 {sp} $W final && wc -l $W/plan-final.md"
            hit = _bash_writes(cmd, "/r/W/plan/plan-final.md", "/r")
            other_ver = _bash_writes(cmd, "/r/W/plan/plan-v3.md", "/r")       # argv 값이 다르면 아니다
            unbound = _bash_writes(cmd, "/r/W/plan/other-final.md", "/r")    # 자리 하나라도 argv 밖이면 풀지 않는다
            inline = _bash_writes("python3 - /r/W/plan final <<'EOF'\nimport sys\nW, ver = sys.argv[1], sys.argv[2]\n"
                                  "open(f'{W}/plan-{ver}.md','w').write('x')\nEOF", "/r/W/plan/plan-final.md", "/r")
            return (hit and not other_ver and not unbound and inline), [hit, other_ver, unbound, inline]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def gpt_log_follows_mv():
        # ⛔ R-D S36 run 1 — 2라운드 전 `for f in …; do mv $W/$f.json.stream.log $W/$f.r1.json.stream.log; done`
        pairs = _mv_pairs("W=/r/p; for f in gpt-verify gpt-verify-gates; do mv $W/$f.json.stream.log $W/$f.r1.json.stream.log; done", "/r")
        moves = [(50.0, s, d) for s, d in pairs]
        after = _follow_moves("/r/p/gpt-verify.json.stream.log", 40.0, moves)     # 40 에 끝나고 50 에 옮겼다 → 따라간다
        during = _follow_moves("/r/p/gpt-verify.json.stream.log", 60.0, moves)    # 끝나기 전에 옮긴 것은 따라가지 않는다
        guard = _mv_pairs("[ -f /r/a ] && mv -f /r/a /r/b; mv /r/x /r/y /r/dir/", "/r")   # 피연산자 셋은 쌍이 아니다
        return (("/r/p/gpt-verify-gates.json.stream.log", "/r/p/gpt-verify-gates.r1.json.stream.log") in pairs
                and after == "/r/p/gpt-verify.r1.json.stream.log" and during == "/r/p/gpt-verify.json.stream.log"
                and guard == [("/r/a", "/r/b")]), [pairs, after, during, guard]

    def bash_events(cwd, cmds, result="ok"):
        """첫 사람 발화 + Bash 호출 i(i 분 0초) · 결과(i 분 5초) — 합성 transcript 이벤트."""
        evs = [{"type": "user", "timestamp": "2026-01-01T00:00:00Z", "message": {"content": "/fz:fz-plan"}}]
        for i, c in enumerate(cmds, 1):
            evs.append({"type": "assistant", "timestamp": f"2026-01-01T00:{i:02d}:00Z", "cwd": cwd,
                        "message": {"id": f"m{i}", "content": [{"type": "tool_use", "id": f"t{i}", "name": "Bash", "input": {"command": c}}]}})
            evs.append({"type": "user", "timestamp": f"2026-01-01T00:{i:02d}:05Z", "cwd": cwd,
                        "message": {"content": [{"type": "tool_result", "tool_use_id": f"t{i}", "content": result}]}})
        return evs

    @reg
    def heredoc_script_fallback_by_call_time():
        # ⛔ R-C C2 plan-feature — `cat > /tmp/x.py <<'EOF' … EOF` 로 만들고 바로 부른 스크립트가 재수집 전에 디스크에서 사라졌다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            gone, ver, disk = (os.path.join(td, n) for n in ("gone.py", "v.py", "disk.py"))
            mk = lambda p, out: f"cat > {p} <<'EOF'\nW = '{td}'\nf = f\"{{W}}/{out}\"\nopen(f, 'w').write('x')\nEOF"
            cmds = [mk(gone, "g.md") + f"\npython3 {gone}\n",                       # 같은 명령에서 만들고 부른다 · 디스크에 없다
                    mk(ver, "a.md"), f"python3 {ver} && echo ok", mk(ver, "b.md"), f"python3 {ver} && echo ok",   # 같은 경로 두 벌
                    mk(disk, "c.md"), f"python3 {disk} && echo ok"]                   # 디스크에 있으면 디스크 본문이 정본
            with open(disk, "w") as fh:
                fh.write("print('no write')\n")
            p = os.path.join(td, "t.jsonl")
            _write_lines(p, bash_events(td, cmds))
            at = lambda i: wfm._ts(f"2026-01-01T00:{i:02d}:05Z")
            arts = {n: os.path.join(td, n) for n in ("g.md", "a.md", "b.md", "c.md")}
            # mtime 을 일부러 '틀린' 호출 쪽에 둔다 — 본문을 시각과 무관하게 합치면 최근접 선택이 틀린 호출을 고른다
            for n, i in (("g.md", 1), ("a.md", 5), ("b.md", 3), ("c.md", 7)):
                with open(arts[n], "w") as fh:
                    fh.write("x")
                os.utime(arts[n], (at(i).timestamp(), at(i).timestamp()))
            got = {os.path.basename(x["path"]): x["write"] for x in parse_transcript(p, list(arts.values()))["artifacts"]}
            want = {"g.md": iso(at(1)), "a.md": iso(at(3)), "b.md": iso(at(5)), "c.md": None}
            return got == want, [got, want]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def gpt_calls_all_in_one_command():
        # ⛔ F-335 ⑪ — `( A ) & ( B ) & wait` 의 두 번째 호출이 계수 · 배너 대조에서 빠졌다(R-C plan B1-feature · B2-removal 실측)
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            for n in ("a.json", "b.json"):
                with open(os.path.join(td, n), "w") as fh:
                    fh.write("{}")
            cmd = (f"( /p/scripts/gpt-exec.sh exec --out {td}/a.json --prompt-file p ) > {td}/a.log 2>&1 &\n"
                   f"( /p/scripts/gpt-exec.sh exec --out {td}/b.json --effort high --prompt-file q ) > {td}/b.log 2>&1 &\nwait")
            p = os.path.join(td, "t.jsonl")
            _write_lines(p, bash_events(td, [cmd], result="GATE-PASS"))
            g = parse_transcript(p)["gpt"]
            return ([os.path.basename(x["out"] or "") for x in g] == ["a.json", "b.json"] and all(x["ok"] for x in g)
                    and [x["explicit_effort"] for x in g] == [False, True]), [g]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def lead_tool_errors_without_retries_alias():
        # ⛔ F-335 ⑩ — `retries` 는 tool_errors 의 별칭이었다(같은 값) · SC-7 · 원천 대조는 tool_errors 를 본다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            p = os.path.join(td, "t.jsonl")
            evs = bash_events(td, ["false"])
            evs[-1]["message"]["content"][0]["is_error"] = True
            _write_lines(p, evs)
            lead = parse_transcript(p)["lead"]
            return (lead["tool_errors"] == 1 and "retries" not in lead and ("lead", "tool_errors") in SC7_FIELDS
                    and "lead.tool_errors" in VERIFY_FIELDS["transcript"]), [lead]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def recollect_diff_reports_worse():
        old, _ = _mk("C1", "C", 2)
        cp = lambda: json.loads(json.dumps(old))
        moved, lost, drift = cp(), cp(), cp()
        moved["wall"]["total_s"] = 999.0                                      # 바뀌었지만 여전히 유효 — 차이만 인쇄
        lost["complete"] = {"ok": False, "why": ["최종 산출물 기록 이벤트 없음"]}   # 완주 → 미완주
        drift["wall"]["mtime_delta_s"] = 184.0                                # 완주 그대로 · mtime 교차 실패(R-C C2 꼴)
        r = [recollect_diff(old, x) for x in (cp(), moved, lost, drift)]
        return (r[0] == ([], [], False) and r[1][0] == ["wall.total_s"] and not r[1][2] and r[2][2] and "complete.ok" in r[2][0]
                and r[3][2] and bool(r[3][1]) and "wall.mtime_delta_s" in r[3][0]), [r]

    @reg
    def merge_summary_cd_relative_and_text():
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            os.makedirs(os.path.join(td, "review"))
            with open(os.path.join(td, "review", "m.json"), "w") as fh:
                json.dump({"summary": {"candidatesIn": 56, "candidatesOut": 56}}, fh)
            u1 = {"name": "Bash", "id": "1", "cwd": td, "input": {"command": f"cd {td}/review && P=/p && python3 \"$P/scripts/review_merge.py\" --claude c.json --gpt g.json --diff d --out m.json"}}
            u2 = {"name": "Bash", "id": "2", "cwd": td, "input": {"command": "python3 /p/scripts/review_merge.py --claude c --gpt g --diff d"}}
            got = _merge_summaries([u1, u2], {"2": {"text": "MERGE OK — 후보 12→12 · 그룹 9"}})
            return ([(x["in"], x["out"]) for x in got["summaries"]] == [(56, 56), (12, 12)]), [got]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def shell_heredoc_body_is_command():
        scripts = {"/r/W/plan/mk.py": "import sys\nsrc, dst = sys.argv[1], sys.argv[2]\nopen(dst, 'w').write(open(src).read())\n"}
        cmd = "bash <<'BASH'\nset -u\nW=/r/W\npython3 $W/plan/mk.py $W/plan/v3.md $W/plan/plan-final.md || exit 1\nBASH"
        w = _bash_writes(cmd, "/r/W/plan/plan-final.md", "/r", scripts)
        r = _bash_writes(cmd, "/r/W/plan/v3.md", "/r", scripts)
        data = _bash_writes("cat > /r/n.txt <<'EOF'\npython3 /r/W/plan/mk.py a /r/W/plan/plan-final.md\nEOF", "/r/W/plan/plan-final.md", "/r", scripts)
        g = any(GPT_CALL_RE.search(_shell_part(v)) for v in _cmd_views("bash <<'X'\n/p/scripts/gpt-exec.sh exec --out o --prompt-file p\nX"))
        return (w and not r and not data and g), [w, r, data, g]

    @reg
    def critical_path_recorded():
        rows = base() + [_mk("C1", "C", 2), _mk("C2", "C", 4)]
        rows[2][0]["critical"] = {"gpt_plan_s": 900.0, "wf_s": 1200.0, "path": "workflow"}
        rows[3][0]["critical"] = {"gpt_plan_s": 1500.0, "wf_s": 1200.0, "path": "gpt"}
        ok_w, a = _judge(rows, require=["gpt-wf-wall"])
        ok_p, b = _judge(rows, require=["critical-path"])
        switched = any("전환" in x for x in b)
        rows[3][0]["critical"] = {"gpt_plan_s": None, "wf_s": 1200.0, "path": None}
        miss_w, c = _judge(rows, require=["gpt-wf-wall"])
        miss_p, d = _judge(rows, require=["critical-path"])
        calls = _launcher_calls([{"id": "1", "ts": None, "input": {"command": 'bash "$P/scripts/gpt_independent.sh" plan --requirement r'}},
                                 {"id": "2", "ts": None, "input": {"command": "sed -n 1,80p $P/scripts/gpt_independent.sh"}}], {}, {})
        return ((ok_w, ok_p, miss_w, miss_p) == (PASS, PASS, FAIL, FAIL) and switched
                and [x["mode"] for x in calls] == ["plan"]), a + b + c + d + [str(calls)]

    @reg
    def blind_labels_one_pack():
        # 한 꾸러미 → PASS · arm 별 꾸러미 → FAIL · 판정 전(미검증) → UNRUN · 검증됐다는데 꾸러미가 없음 → FAIL
        one_rc, a = _judge(base() + [_mk("C1", "C", 2), _mk("C2", "C", 4)], require=["blind-labels"])
        split_rc, b = _judge(base() + [_mk("C1", "C", 2, pack="P2"), _mk("C2", "C", 4, pack="P2")], require=["blind-labels"])
        unv_rc, c = _judge(base() + [_mk("C1", "C", 2, verified=False), _mk("C2", "C", 4)], require=["blind-labels"])
        nopack_rc, d = _judge(base() + [_mk("C1", "C", 2, pack=None), _mk("C2", "C", 4)], require=["blind-labels"])
        return (one_rc, split_rc, unv_rc, nopack_rc) == (PASS, FAIL, UNRUN, FAIL), a + b + c + d

    @reg
    def ac1_mismatch_invalid():
        rc, out = _judge(base() + [_mk("C1", "C", 2, effort="high"), _mk("C2", "C", 4, wmodel="claude-sonnet-5"),
                                   _mk("C3", "C", 6), _mk("C4", "C", 8)], require=["SC-3"])
        inval = [x for x in out if x.startswith("  INVALID")]
        return (any("C1" in x and "AC-1 Lead effort" in x for x in inval) and
                any("C2" in x and "AC-1 워커 model" in x for x in inval) and rc == PASS), out

    @reg
    def ac5_incomplete_not_zero():
        # 미완주 C 2개는 0건이 아니라 무효 → 유효 run 부족 FAIL (0건으로 세면 'loss' 계산이 돌았을 것이다)
        rc, out = _judge(base() + [_mk("C1", "C", 2, complete=False, major=0), _mk("C2", "C", 4, complete=False, major=0)],
                         require=["SC-3"])
        return rc == FAIL and any("정확히" in x for x in out) and not any("loss=" in x for x in out), out

    @reg
    def ac7_memory_diff_invalid():
        rc, out = _judge(base(b2={"leak": ["user_agent_memory"]}), phase="baseline", min_runs=2)
        return rc == FAIL and any("B2" in x and "AC-7" in x for x in out), out

    @reg
    def sc4_axis_and_ratio():
        # B 비율 0.8·0.76 → 잡음 0.04 · 하한 0.74. (B 가 같은 값이면 잡음 0 이라 어떤 감소도 미달이다)
        nb = lambda: base(b1={"ratio": 0.8}, b2={"ratio": 0.76})
        miss_rc, a = _judge(nb() + [_mk("C1", "C", 2, axes={x: 1 for x in AXES6 if x != "placement"}),
                                    _mk("C2", "C", 4)], require=["SC-4"])
        low_rc, b = _judge(nb() + [_mk("C1", "C", 2, ratio=0.5), _mk("C2", "C", 4, ratio=0.5)], require=["SC-4"])
        ok_rc, c = _judge(nb() + [_mk("C1", "C", 2, ratio=0.8), _mk("C2", "C", 4, ratio=0.78)], require=["SC-4"])
        return (miss_rc, low_rc, ok_rc) == (FAIL, FAIL, PASS) and any("placement" in x for x in a), a + b + c

    @reg
    def sc7_fields_required():
        rows = base() + [_mk("C1", "C", 2), _mk("C2", "C", 4)]
        rows[2][0]["lead"]["out_tok"] = None
        bad_rc, a = _judge(rows, require=["SC-7"])
        ok_rc, b = _judge(base() + [_mk("C1", "C", 2), _mk("C2", "C", 4)], require=["SC-7"])
        return (bad_rc, ok_rc) == (FAIL, PASS) and any("out_tok" in x for x in a), a + b

    @reg
    def sc7_launcher_counts():
        # 실측 review C: 직접 호출 0 · 런처 1(감사 exit 0) — 런처를 세지 않으면 GPT 리뷰를 옮긴 후보가 '검증 누락' 으로 떨어졌다
        lrow = lambda n, o, lo: _mk(n, "C", o, gpt_calls=0, gpt_ok=0, gpt_launcher_ok=lo)
        ok_rc, a = _judge(base() + [lrow("C1", 2, 1), lrow("C2", 4, 1)], require=["SC-7"])
        bad_rc, b = _judge(base() + [lrow("C1", 2, 0), lrow("C2", 4, 1)], require=["SC-7"])
        return ((ok_rc, bad_rc) == (PASS, FAIL) and any("직접 0 + 런처 1" in x for x in a)
                and any("C1" in x and "직접 0 + 런처 0" in x for x in b)), a + b

    @reg
    def launcher_audit_ok():
        # ⛔ 성공은 감사 exit 0 뿐 — 실패 코드 · 깨진 JSON · 객체가 아닌 JSON · 없는 파일은 성공이 아니다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            got = []
            for name, body in [("a", '{"exit": 0, "note": "ok"}'), ("b", '{"exit": 15, "note": "격리 미적용"}'),
                               ("c", '{"exit": 0'), ("d", "[0]")]:
                pth = os.path.join(td, name + ".audit.json")
                with open(pth, "w", encoding="utf-8") as fh:
                    fh.write(body)
                got.append(_launcher_ok(pth))
            got.append(_launcher_ok(os.path.join(td, "none.audit.json")))
            return got == [True, False, False, False, False], got
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def input_hash_mismatch_invalid():
        rc, out = _judge(base() + [_mk("B3", "B", 5, input="h2")], phase="baseline", min_runs=2)
        return rc == PASS and any("B3" in x and "input-hash" in x for x in out), out

    @reg
    def two_fixture_groups():
        # fz-plan 은 feature·removal 두 fixture 에서 기준선을 잰다 — 입력 해시가 달라도 서로를 무효로 만들면 안 된다
        rows = [_mk("F1", "B", 1, fixture="plan-feature", input="hf"), _mk("F2", "B", 3, fixture="plan-feature", input="hf"),
                _mk("R1", "B", 5, fixture="plan-removal", input="hr"), _mk("R2", "B", 7, fixture="plan-removal", input="hr")]
        rc, out = _judge(rows, phase="baseline", min_runs=2)
        return (rc == PASS and not any("INVALID" in x for x in out)
                and any("[plan-feature]" in x for x in out) and any("[plan-removal]" in x for x in out)), out

    @reg
    def unimplemented_is_unrun():
        # ⛔ 아직 구현하지 않은 기준으로 잰다 — 구현된 기준은 입력 부족으로도 UNRUN 이 나와 이 사례를 헛되이 통과시킨다
        a_rc, a = _judge(base(), require=["SC-8"])
        b_rc, b = _judge(base(), require=["SC-3"], envs="isolated,installed")
        c_rc, c = _judge(base(), require=["SC-1"])
        return ((a_rc, b_rc, c_rc) == (UNRUN, UNRUN, UNRUN) and any("미구현 기준 ['SC-8']" in x for x in a)
                and any("gpt-pass" in x for x in c)), a + b + c

    @reg
    def plugin_sha_baseline():
        rc, out = _judge(base(b1={}) + [_mk("B3", "B", 5)], phase="baseline", min_runs=3, plugin_sha="10197a0")
        rows = base()
        rows[1][0]["plugin"]["sha"] = "757afe2bbbb"
        rc2, out2 = _judge(rows, phase="baseline", min_runs=2, plugin_sha="10197a0")
        return (rc, rc2) == (PASS, FAIL), out + out2

    @reg
    def transcript_usage_dedupe():
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            u = {"output_tokens": 100}
            evs = [{"type": "user", "timestamp": "2026-01-01T00:00:00Z", "message": {"content": "/fz:fz-review"}}]
            evs += [{"type": "assistant", "timestamp": f"2026-01-01T00:00:0{i}Z", "effort": "xhigh", "version": "2.1.282",
                     "message": {"id": "m1", "model": "claude-opus-5-5", "stop_reason": "tool_use", "usage": u,
                                 "content": [{"type": k}]}} for i, k in enumerate(("thinking", "text"), 1)]
            p = os.path.join(td, "t.jsonl")
            _write_lines(p, evs)
            lead = parse_transcript(p)["lead"]
            return (lead["out_tok"], lead["messages"], lead["effort"]) == (100, 1, "xhigh"), [str(lead)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    labels2 = {"issues": [{"id": "I1", "axis": "naming", "severity": "major", "file": "App/A.swift",
                           "line_start": 10, "line_end": 12},
                          {"id": "I2", "axis": "idiom", "severity": "critical", "file": "App/B.swift",
                           "line_start": 40, "line_end": 40}]}

    @reg
    def cite_and_score():
        texts = ["- `A.swift:13` 이름이 반환 의미를 말하지 않는다\n- `App/B.swift:L55` 무관\n- `C.swift:1-3` 위치가 틀렸다"]
        v = {"A.swift:13": {"real": True, "label_ids": ["I1"]}, "App/B.swift:55": {"real": False},
             "C.swift:1-3": {"real": True, "label_ids": [], "severity": "minor", "axis": "placement"}}
        s = score_review(labels2, texts, v)
        ok = (s["verified"] and s["labels_found"] == ["I1"] and s["by_severity"]["major"] == 1
              and s["by_severity"]["critical"] == 0 and s["by_axis"]["placement"] == 1 and s["verified_ratio"] == round(2 / 3, 4))
        part = score_review(labels2, texts, {"A.swift:13": {"real": True, "label_ids": ["I1"]}})
        ok &= part["verified"] is False and part["unverified"] == 2 and part["verified_ratio"] is None
        rub = {"sections": {"Contracts": [{"id": "PC1", "criterion": "c", "keywords": ["DTO"]}]}, "questions": {},
               "residues": [{"id": "RZ1", "symbol": "LegacyX", "file": "a.swift"}]}
        p = score_plan(rub, "DTO 를 정의하지 않는다 · LegacyX 제거", {"PC1": {"covered": False}, "RZ1": {"covered": True}})
        ok &= p["verified"] and p["covered"] == ["RZ1"] and p["by_severity"]["critical"] == 1 and p["by_severity"]["major"] == 0
        ok &= score_plan(rub, "DTO", None)["verified"] is False
        return ok, [str(s), str(part), str(p)]

    @reg
    def ok_mention_not_counted():
        # ⛔ GPT ISSUE-001 — 라벨 위치를 '정상' 이라고 인용해도 발견이 아니다. 판정 없으면 SC-3 은 UNRUN
        texts = ["- `App/A.swift:11` 정상 — 문제 없음"]
        s = score_review(labels2, texts, {"App/A.swift:11": {"real": False}})
        rows = base() + [_mk("C1", "C", 2), _mk("C2", "C", 4, verified=False)]
        rc, out = _judge(rows, require=["SC-3"])
        return (s["by_severity"]["major"] == 0 and s["labels_found"] == [] and rc == UNRUN
                and any("가린 검증자" in x for x in out)), out + [str(s)]

    @reg
    def c_same_tree_invalid():
        rc, out = _judge(base() + [_mk("C1", "C", 2, tree="tB"), _mk("C2", "C", 4, tree="tB")], require=["SC-3"])
        return rc == FAIL and any("같은 플러그인 트리" in x for x in out), out

    @reg
    def input_root_reuse_invalid():
        rc, out = _judge([_mk("B1", "B", 1, root="/r/x"), _mk("B2", "B", 3, root="/r/x")], phase="baseline", min_runs=2)
        return rc == FAIL and any("B2" in x and "재사용" in x for x in out), out

    @reg
    def extra_valid_run_fails():
        rc, out = _judge(base() + [_mk("C1", "C", 2), _mk("C2", "C", 4), _mk("C3", "C", 6)], require=["SC-6"])
        return rc == FAIL and any("정확히" in x for x in out), out

    @reg
    def baseline_rejects_other_require():
        rc, out = _judge(base(), phase="baseline", require=["SC-3"])
        return rc == UNRUN and any("baseline-runs 만" in x for x in out), out

    @reg
    def state_problems_invalid():
        rc, out = _judge(base(b2={"problems": ["start 에 감시 이름 repo_agent_memory 없음"]}), phase="baseline", min_runs=2)
        return rc == FAIL and any("B2" in x and "AC-7 감시 불완전" in x for x in out), out

    @reg
    def gpt_banner_missing_invalid():
        rc, out = _judge(base(b2={"gpt_ok": 2, "banners": 1}), phase="baseline", min_runs=2)
        return rc == FAIL and any("B2" in x and "GPT 배너" in x for x in out), out

    @reg
    def bool_verdict_rejected():
        # ⛔ GPT ISSUE-025 — "false" 문자열은 참으로 읽히면 안 된다(미검증)
        s = score_review(labels2, ["- `A.swift:13` 이름"], {"A.swift:13": {"real": "false", "label_ids": ["I1"]}})
        pl = score_plan({"sections": {"C": [{"id": "PC1", "criterion": "c"}]}, "questions": {}}, "x", {"PC1": {"covered": "false"}})
        return (s["verified"] is False and s["unverified"] == 1 and pl["verified"] is False and pl["covered"] == []), [str(s), str(pl)]

    @reg
    def stale_score_unrun():
        # ⛔ GPT ISSUE-024 — 점수의 산출물 해시가 현재 행과 다르면 낡은 판정이다
        rows = base() + [_mk("C1", "C", 2, score_arts=["old"]), _mk("C2", "C", 4)]
        rc, out = _judge(rows, require=["SC-3"])
        return rc == UNRUN and any("C1" in x and "낡음" in x for x in out), out

    @reg
    def plugin_tree_and_source_invalid():
        # ⛔ GPT ISSUE-003 — 트리 해시 없음 · 선언 원본과 다른 사본은 무효
        rc, out = _judge(base(b2={"tree": None}), phase="baseline", min_runs=2)
        rc2, out2 = _judge(base(b2={"psource": "/src/B", "psource_tree": "other"}), phase="baseline", min_runs=2)
        return (rc, rc2) == (FAIL, FAIL) and any("트리 해시 없음" in x for x in out) and any("원본" in x for x in out2), out + out2

    @reg
    def gpt_failed_or_unlinked_invalid():
        # ⛔ GPT ISSUE-013·014 — 실패한 GPT 호출 · 배너가 연결되지 않은 성공 호출
        rc, out = _judge(base(b2={"gpt_failed": 1}), phase="baseline", min_runs=2)
        rc2, out2 = _judge(base(b2={"unlinked": 1}), phase="baseline", min_runs=2)
        return (rc, rc2) == (FAIL, FAIL) and any("GPT 호출 실패" in x for x in out) and any("미연결" in x for x in out2), out + out2

    @reg
    def root_reuse_across_workflows():
        # ⛔ GPT ISSUE-007 잔여 — 다른 워크플로가 같은 저장소 경로를 써도 재사용이다
        rows = [_mk("B1", "B", 1, root="/r/shared"), _mk("B2", "B", 3),
                _mk("P1", "B", 5, workflow="fz-plan", root="/r/shared"), _mk("P2", "B", 7, workflow="fz-plan")]
        runs = {r["run_id"]: r for r, _ in rows}
        scores = {s["run_id"]: s for _, s in rows}
        opts = {"model": DEFAULT_MODEL, "effort": DEFAULT_EFFORT, "phase": "baseline", "arm": "C", "release": None,
                "workflows": ["fz-review", "fz-plan"], "min_runs": 2, "runs": 1, "plugin_sha": None,
                "require": [], "envs": None, "options_on": False, "require_passed": None}
        rc, out = judge_rows(runs, scores, opts)
        return rc == FAIL and any("P1" in x and "재사용" in x for x in out), out

    @reg
    def stage_expectations():
        # 열쇠는 워크플로 스크립트 이름이다(F-335 ⑥) — 스킬 이름으로 찾으면 표가 없다
        ok = (required_stages("peer-review", True, 3) == ["R1-arch", "R1-quality", "R1-correct", "R2-arch", "R2-quality",
                                                          "R3-counter"]
              and required_stages("peer-review", False, 2) == ["R1-arch", "R1-quality", "R1-correct"]
              and expected_stages_completed("peer-review", True, 3) == 3
              and expected_stages_completed("peer-review", False, 2) == 1
              and expected_stages_completed("review-live", None, None) == 3
              and expected_stages_completed("plan-lean2", None, None) == 2
              and required_stages("fz-review", None, None) == [] and expected_stages_completed("fz-plan", None, None) is None)
        blk = cite_spans(["- `A.swift:3` 이름이 틀렸다\n  근거: 반환값이 있는데 동사형\n- `B.swift:9` 다른 지적"])
        ok &= len(blk) == 2 and "근거" in blk[0][3] and "다른 지적" not in blk[0][3]
        return ok, [str(blk)]

    @reg
    def real_without_mapping_unverified():
        # ⛔ GPT ISSUE-027 — real=true 인데 라벨·severity·axis 가 없거나, 다른 파일의 라벨로 매핑하면 미검증
        a = score_review(labels2, ["- `A.swift:13` 이름"], {"A.swift:13": {"real": True, "label_ids": []}})
        b = score_review(labels2, ["- `A.swift:13` 이름"], {"A.swift:13": {"real": True, "label_ids": ["I2"]}})
        return (a["verified"] is False and b["verified"] is False and a["unverified"] == 1 and b["unverified"] == 1), [str(a), str(b)]

    @reg
    def cited_abbrev_resolves():
        # ⛔ 실측 peer C2 · review B1 — Lead 보고서의 약칭 인용(`Interactor.swift`)을 fixture 파일로 풀어 같은-파일 대조를 한다
        labs = {"issues": [{"id": "I1", "axis": "idiom", "severity": "major", "file": "App/W/WatchlistInteractor.swift",
                            "line_start": 10, "line_end": 12},
                           {"id": "I2", "axis": "naming", "severity": "minor", "file": "App/W/WatchlistRouter.swift",
                            "line_start": 5, "line_end": 5}]}
        files = ["App/W/WatchlistInteractor.swift", "App/W/WatchlistRouter.swift"]
        t = ["- `Interactor.swift:11` 결함"]
        a = score_review(labs, t, {"Interactor.swift:11": {"real": True, "label_ids": ["I1"]}}, files)
        b = score_review(labs, t, {"Interactor.swift:11": {"real": True, "label_ids": ["I2"]}}, files)   # 풀린 파일과 다른 파일의 라벨
        return (a["verified"] and a["labels_found"] == ["I1"] and a["mapping_unchecked"] == 0
                and b["verified"] is False and b["unverified"] == 1), [str(a), str(b)]

    @reg
    def cited_unresolved_mapping_counted():
        # ⛔ 못 푸는 인용(`VC.swift` — 접미 일치 0 · `Interactor.swift` — 접미 일치 2)은 검증자 매핑을 받고 수를 남긴다 · 없는 라벨은 미검증
        labs = {"issues": [{"id": "I7", "axis": "ui_structure", "severity": "major", "file": "App/W/WatchlistViewController.swift",
                            "line_start": 34, "line_end": 40}]}
        files = ["App/W/WatchlistViewController.swift", "App/W/WatchlistInteractor.swift", "App/H/HomeInteractor.swift"]
        a = score_review(labs, ["- `VC.swift:34-40` 구조"], {"VC.swift:34-40": {"real": True, "label_ids": ["I7"]}}, files)
        b = score_review(labs, ["- `Interactor.swift:3` 결함"], {"Interactor.swift:3": {"real": True, "label_ids": ["I7"]}}, files)
        c = score_review(labs, ["- `VC.swift:34-40` 구조"], {"VC.swift:34-40": {"real": True, "label_ids": ["NOPE"]}}, files)
        return (a["verified"] and a["labels_found"] == ["I7"] and a["mapping_unchecked"] == 1
                and b["verified"] and b["mapping_unchecked"] == 1
                and c["verified"] is False and c["unverified"] == 1), [str(a), str(b), str(c)]

    @reg
    def near_labels_resolve_abbrev():
        # 다음 꾸러미부터 — 약칭 인용에도 위치 힌트가 붙는다(파일 목록이 없으면 옛 규칙 그대로 빈 힌트)
        labs = {"issues": [{"id": "I1", "axis": "idiom", "severity": "major", "file": "App/W/WatchlistInteractor.swift",
                            "line_start": 10, "line_end": 12}]}
        sp = ("Interactor.swift", 11, 11, "")
        got = (near_labels(sp, labs, ["App/W/WatchlistInteractor.swift"]), near_labels(sp, labs))
        return got == (["I1"], []), [str(got)]

    @reg
    def context_one_row_table_section():
        # ⛔ 실측 review C1 — 렌더러 보고서의 지적 절(1행 위치 표 → What → Suggestion → 마커)을 그대로 옮겼다
        t = ("### [minor] m1\n\n| File:line | Origin | Confidence | Found-by |\n|---|---|---|---|\n"
             "| `App/Watchlist/WatchlistInteractor.swift:53` | regression | 90 | claude · gpt |\n\n"
             "**What** — `weak var listener`를 `guard let`으로 풀었다(CLAUDE.md:12, R5 위반)." + "가" * 900 + "\n\n"
             "**Suggestion** — guard를 지운다.\n\n<!-- fz-review:m2 -->\n### [minor] m2\n\n다음 지적")
        sp = [x for x in cite_spans([t]) if x[0].endswith("WatchlistInteractor.swift")]
        ctx = sp[0][3] if sp else ""
        return ("**What**" in ctx and "**Suggestion**" in ctx and "다음 지적" not in ctx and "fz-review:m2" not in ctx), [ctx]

    @reg
    def context_multirow_table_unchanged():
        # Lead 보고서의 여러 행 표는 행마다 주장을 적는다 — 뒤 문단을 붙이지 않는다
        t = ("| 위치 | 등급 | 내용 |\n|---|---|---|\n| `A.swift:3` | major | 이름이 틀렸다 |\n"
             "| `B.swift:9` | minor | 색 하드코딩 |\n\n표 뒤 요약 문단")
        got = {x[0]: x[3] for x in cite_spans([t])}
        return (got.get("A.swift", "").endswith("이름이 틀렸다 |") and "요약 문단" not in got.get("B.swift", "x요약 문단")
                and "요약 문단" not in got.get("A.swift", "x요약 문단")), [str(got)]

    @reg
    def rule_citation_excluded():
        # ⛔ 규칙 문서 인용(`CLAUDE.md:12`)은 참조다 — 선언된 규칙 출처면 후보에서 뺀다 · 선언이 없으면 옛 동작
        t = ["- `App/X.swift:3` guard let 으로 풀었다(`CLAUDE.md:12` 위반)"]
        with_rules = [x[0] for x in cite_spans(t, ["CLAUDE.md"])]
        without = [x[0] for x in cite_spans(t)]
        return with_rules == ["App/X.swift"] and sorted(without) == ["App/X.swift", "CLAUDE.md"], [str(with_rules), str(without)]

    @reg
    def cited_same_finding_other_file():
        # ⛔ 실측 review C — 렌더러의 1행 위치 표가 결함 위치(Interactor:54)와 근거 위치(Repo:15-19)를 한 지적에 적는다.
        #    근거 위치 후보에 붙은 같은 지적의 라벨을 받는다 · 라벨은 한 번만 센다
        labs = {"issues": [{"id": "I1", "axis": "architecture", "severity": "major", "file": "App/W/WatchlistInteractor.swift",
                            "line_start": 54, "line_end": 54}]}
        files = ["App/W/WatchlistInteractor.swift", "Data/W/Repo.swift"]
        t = ["### [major] M1\n\n| File:line | Origin |\n|---|---|\n"
             "| `App/W/WatchlistInteractor.swift:54` · `Data/W/Repo.swift:15-19` | regression |\n\n"
             "**What** — Interactor 가 APIClient 를 직접 부른다.\n\n<!-- fz-review:M2 -->"]
        v = {"App/W/WatchlistInteractor.swift:54": {"real": True, "label_ids": ["I1"]},
             "Data/W/Repo.swift:15-19": {"real": True, "label_ids": ["I1"]}}
        s_ = score_review(labs, t, v, files)
        return (s_["verified"] and s_["labels_found"] == ["I1"] and s_["by_severity"]["major"] == 1
                and s_["mapping_context"] == 1), [str(s_)]

    @reg
    def cross_file_mapping_without_citation_unverified():
        # 보존: 문단이 인용하지 않은 파일의 라벨로 매핑하면 여전히 미검증(ISSUE-027)
        labs = {"issues": [{"id": "I1", "axis": "architecture", "severity": "major", "file": "App/W/WatchlistInteractor.swift",
                            "line_start": 54, "line_end": 54}]}
        files = ["App/W/WatchlistInteractor.swift", "Data/W/Repo.swift"]
        s_ = score_review(labs, ["- `Data/W/Repo.swift:15-19` 저장소가 이미 있다"],
                          {"Data/W/Repo.swift:15-19": {"real": True, "label_ids": ["I1"]}}, files)
        return s_["verified"] is False and s_["unverified"] == 1, [str(s_)]

    @reg
    def section_what_citation_maps_row_file():
        # ⛔ 실측 C′1 — What 문단 안 근거 인용(Repo:15)이 같은 절 위치 표의 라벨 파일(Interactor)을 본다
        labs = {"issues": [{"id": "I1", "axis": "architecture", "severity": "major", "file": "App/W/WatchlistInteractor.swift",
                            "line_start": 54, "line_end": 54}]}
        files = ["App/W/WatchlistInteractor.swift", "Data/W/Repo.swift"]
        t = ["### [major] M1\n\n| File:line | Origin |\n|---|---|\n| `App/W/WatchlistInteractor.swift:54` | regression |\n\n"
             "**What** — Interactor 가 APIClient 를 직접 부른다. 같은 요청을 감싼 `Data/W/Repo.swift:15` 가 이미 있다.\n\n"
             "<!-- fz-review:M2 -->\n### [minor] M2\n\n| File:line | Origin |\n|---|---|\n| `Data/W/Repo.swift:30` | new |\n\n**What** — 다른 지적"]
        v = {"App/W/WatchlistInteractor.swift:54": {"real": True, "label_ids": ["I1"]},
             "Data/W/Repo.swift:15": {"real": True, "label_ids": ["I1"]},
             "Data/W/Repo.swift:30": {"real": False, "label_ids": []}}
        s_ = score_review(labs, t, v, files)
        ctx = {x[0] + ":" + str(x[1]): x[3] for x in cite_spans(t)}
        return (s_["verified"] and s_["labels_found"] == ["I1"] and s_["mapping_context"] == 1
                and "WatchlistInteractor.swift:54" in ctx.get("Data/W/Repo.swift:15", "")
                and "WatchlistInteractor" not in ctx.get("Data/W/Repo.swift:30", "x WatchlistInteractor")), [str(s_), str(ctx)]

    @reg
    def section_cross_file_without_label_file_unverified():
        # 보존(절 형태): 절 어디에도 라벨 파일 인용이 없으면 What 안 교차 파일 매핑은 여전히 미검증
        labs = {"issues": [{"id": "I1", "axis": "architecture", "severity": "major", "file": "App/W/WatchlistInteractor.swift",
                            "line_start": 54, "line_end": 54}]}
        files = ["App/W/WatchlistInteractor.swift", "Data/W/Repo.swift", "App/W/Other.swift"]
        t = ["### [major] M1\n\n| File:line | Origin |\n|---|---|\n| `App/W/Other.swift:3` | regression |\n\n"
             "**What** — 같은 요청을 감싼 `Data/W/Repo.swift:15` 가 이미 있다.\n\n<!-- fz-review:M2 -->"]
        v = {"App/W/Other.swift:3": {"real": False, "label_ids": []},
             "Data/W/Repo.swift:15": {"real": True, "label_ids": ["I1"]}}
        s_ = score_review(labs, t, v, files)
        return s_["verified"] is False and s_["unverified"] == 1, [str(s_)]

    def _gpt_fixture(td, bad=False):
        """가짜 검증 트리 + 런처 한 호출분(출력 · 감사 · rollout) → (collect 인자, 트리 루트)."""
        tree = os.path.join(td, "tree")
        os.makedirs(os.path.join(tree, "gpt-skills", "fz-reviewer"))
        os.makedirs(os.path.join(tree, "skills", "fz-review"))
        with open(os.path.join(tree, "gpt-skills", "fz-reviewer", "SKILL.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nname: fz-reviewer\n---\nBODY-OF-REVIEWER\n")
        run = os.path.join(td, "run")
        os.makedirs(os.path.join(run, "g.rollouts"))
        with open(os.path.join(run, "diff.patch"), "w", encoding="utf-8") as fh:
            fh.write("diff\n")
        iso = "/private/tmp/fz-gpt-iso.T/gpt-home/skills"
        with open(os.path.join(run, "g.audit.json"), "w", encoding="utf-8") as fh:
            json.dump({"mode": "review", "exit": 0, "note": "ok", "timedOut": False, "isolationApplied": True, "spawnAgent": 0,
                       "hits": [], "inputs": {"diff.patch": _sha_file(os.path.join(run, "diff.patch"))}}, fh)
        with open(os.path.join(run, "g.json"), "w", encoding="utf-8") as fh:
            json.dump({"verdict": "approved", "issues": [], "craft": [], "axis_coverage": [],
                       "projectRules": {"rules": [], "conflicts": [], "gaps": []}}, fh)
        skills = "fz-reviewer" + (", fz-review" if bad else "")
        host = "\n## Skills\n### Skill roots\n- `r0` = `" + iso + "`\n### Available\n" + "".join(
            f"- {n}: d (r0/{n}/SKILL.md)\n" for n in skills.split(", "))
        cmds = [f'tools.exec_command({{cmd:"cat {iso}/fz-reviewer/references/domain-ios.md"}})']
        if bad:
            cmds.append('tools.exec_command({cmd:"cat ~/.codex/skills/fz-reviewer/SKILL.md"})')
        _write_lines(os.path.join(run, "g.rollouts", "r.jsonl"), [
            {"type": "session_meta", "payload": {"id": "s1", "creator_account_id": "ACCT-SECRET", "creator_user_id": "USER-SECRET"}},
            {"type": "world_state", "payload": {"state": {"host_skills": {"body": host}}}},
            {"type": "turn_context", "payload": {"model": "gpt-6-sol"}},
            {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": f"[fz-gpt-skill-injected] fz-reviewer ({iso}/fz-reviewer) — 본문\n"
                                               "---\nname: fz-reviewer\n---\nBODY-OF-REVIEWER\n"}]}},
            *[{"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec", "input": c}} for c in cmds]])
        args = {"out": os.path.join(run, "g.json"), "run_id": "t:isolated:review", "env": "isolated", "mode": "review",
                "fixture": "review-ios-ribs", "plugin_root": tree, "inputs": {"diff.patch": os.path.join(run, "diff.patch")},
                "lead_rules": None, "gpt_agents": False}
        return args, tree

    @reg
    def gpt_pass_scan_and_sc1():
        # ⛔ S27 — 격리 홈 사본만 읽고 주입 본문 = 검증 트리면 SC-1 문제 0 · 실제 GPT 홈 경로 · Claude 스킬 노출은 잡는다 · 계정 식별자는 싣지 않는다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            args, tree = _gpt_fixture(os.path.join(td, "ok"))
            row = build_gpt_row(args, tree)
            ok_p = gpt_sc1_problems(row)
            args2, tree2 = _gpt_fixture(os.path.join(td, "bad"), bad=True)
            row2 = build_gpt_row(args2, tree2)
            bad_p = gpt_sc1_problems(row2)
            blob = json.dumps([row, row2], ensure_ascii=False)
            return (ok_p == [] and any(c == "SC-1" and "실제 GPT 홈 경로" in t for c, t in bad_p)
                    and any(c == "AC-2" and "fz-review" in t for c, t in bad_p)
                    and "ACCT-SECRET" not in blob and "USER-SECRET" not in blob), [str(ok_p), str(bad_p)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def gpt_relative_skill_ref_uses_workdir():
        # ⛔ 실측 S27 plan — `cat gpt-home/skills/fz-planner/references/domain-ios.md` · workdir = 격리 폴더 → 사본 읽기(문제 0).
        #    같은 상대 경로라도 workdir 가 다른 곳이면 여전히 격리 홈 밖이다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            iso = "/private/tmp/fz-gpt-iso.T"
            os.makedirs(os.path.join(td, "skills", "fz-review"))
            os.makedirs(os.path.join(td, "gpt-skills", "fz-planner"))
            os.makedirs(os.path.join(td, "r"))
            rel = "cat gpt-home/skills/fz-planner/references/domain-ios.md"
            _write_lines(os.path.join(td, "r", "x.jsonl"), [
                {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [
                    {"type": "input_text", "text": f"[fz-gpt-skill-injected] fz-planner ({iso}/gpt-home/skills/fz-planner) — b\nB"}]}},
                {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec", "input":
                    f'tools.exec_command({{cmd:"{rel}",workdir:"{iso}",max_output_tokens:10}})'}},
                {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec", "input":
                    f'tools.exec_command({{cmd:"{rel}",workdir:"/private/tmp/other"}})'}}])
            sc = scan_gpt_rollouts(os.path.join(td, "r"))
            ok = classify_skill_refs(dict(sc, cmds=sc["cmds"][:1], workdirs=sc["workdirs"][:1]), td)
            bad = classify_skill_refs(dict(sc, cmds=sc["cmds"][1:], workdirs=sc["workdirs"][1:]), td)
            return (sc["workdirs"] == [iso, "/private/tmp/other"] and ok["bad"] == [] and len(bad["bad"]) == 1), \
                [str(sc["workdirs"]), str(ok["bad"]), str(bad["bad"])]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def gpt_matrix_cell_missing_unrun():
        # 매트릭스 한 칸이라도 비면 UNRUN — 한 환경만 보고 통과하지 않는다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            args, tree = _gpt_fixture(td)
            rows = {}
            for mode in ("plan", "review"):
                r = build_gpt_row(dict(args, mode=mode, run_id=f"t:isolated:{mode}"), tree)
                rows[r["run_id"]] = r
            rc, out = judge_gpt(rows, ["SC-1", "AC-2"], ["isolated", "installed"], td)
            rc_one, out_one = judge_gpt(rows, ["SC-1", "AC-2"], ["isolated"], td)
            return (rc == UNRUN and any("installed×plan" in x for x in out) and rc_one == PASS), out + out_one
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def gpt_rule_fixtures_sc2_ac3():
        # 규칙 fixture 3개 — 없는 규칙 추정 적용 · 상충 임의 선택 · 비-iOS 에 iOS 어휘는 잡고 깨끗한 출력은 통과
        labs = {"rules-conflict": {"conflicts": [{"id": "K1", "axis": "naming", "sources": ["CLAUDE.md#Naming", "AGENTS.md#Naming"],
                                                   "target": "Sources/P/ProfileResponse.swift"},
                                                  {"id": "K2", "axis": "ui_structure", "sources": ["CLAUDE.md#UI", "AGENTS.md#UI"],
                                                   "target": "Sources/P/ProfileCardView.swift"}]},
                "review-nonios": {"guidelines": ["AGENTS.md"], "not_applicable_axes": ["ui_structure"]}, "rules-absent": {}}
        it = lambda **kw: dict({"kind": "craft", "id": "X1", "ruleSource": "plugin-default", "ruleRef": None, "severity": "suggestion",
                                "craftAxis": "naming", "file": "a.ts", "text": "t"}, **kw)
        row = lambda fx, items, conflicts=(), rules=(): {"run_id": fx, "fixture": fx, "mode": "review", "output": {
            "items": list(items), "conflicts": list(conflicts), "rules": list(rules), "axis_coverage": {}}}
        cases = [
            (row("rules-absent", [it()]), []),
            (row("rules-absent", [it(ruleSource="project", ruleRef="CLAUDE.md:3")]), ["SC-2"]),
            (row("rules-conflict", [it()], [{"axis": "naming"}, {"axis": "uiStack"}]), []),
            (row("rules-conflict", [it(ruleSource="project", ruleRef="CLAUDE.md#Naming")], [{"axis": "naming"}, {"axis": "uiStack"}]), ["SC-2"]),
            (row("rules-conflict", [it()], [{"axis": "naming"}]), ["SC-2"]),
            (row("review-nonios", [it(text="SwiftUI 로 바꾸라")]), ["AC-3"]),
            (row("review-nonios", [it(ruleSource="project", ruleRef="AGENTS.md:4")]), []),
            (row("review-nonios", [it(severity="major")]), ["AC-3"]),
        ]
        got = [sorted({c for c, _ in gpt_sc2_problems(g, labs[g["fixture"]], {})[0]}) for g, _ in cases]
        want = [w for _, w in cases]
        return got == want, [str(got)]

    @reg
    def gpt_rule_ref_resolves_ids():
        # ⛔ 실측 S27 nonios — GPT 는 ruleRef 에 자기 projectRules id 를 적는다. id → 출처로 풀어 판정한다(거짓 FAIL · 거짓 PASS 방지)
        it = lambda **kw: dict({"kind": "craft", "id": "X1", "ruleSource": "project", "ruleRef": "R1", "severity": "minor",
                                "craftAxis": "naming", "file": "a.ts", "text": "t"}, **kw)
        non = {"guidelines": ["AGENTS.md"], "not_applicable_axes": []}
        con = {"conflicts": [{"axis": "naming", "sources": ["CLAUDE.md#Naming", "AGENTS.md#Naming"], "target": "P.swift"}]}
        idx = {"sections": [{"file": "CLAUDE.md", "heading": "Naming", "line": 3, "endLine": 6},
                            {"file": "AGENTS.md", "heading": "Naming", "line": 3, "endLine": 6}]}
        row = lambda fx, items, rules, conflicts=(): {"run_id": fx, "fixture": fx, "mode": "review", "output": {
            "items": list(items), "rules": list(rules), "conflicts": list(conflicts), "axis_coverage": {}}}
        a = gpt_sc2_problems(row("review-nonios", [it()], [{"id": "R1", "file": "AGENTS.md", "line": 5}]), non, {})[0]
        b = gpt_sc2_problems(row("review-nonios", [it(ruleRef="R9")], [{"id": "R1", "file": "AGENTS.md", "line": 5}]), non, {})[0]
        c = gpt_sc2_problems(row("rules-conflict", [it(ruleRef="R2", file="P.swift")], [{"id": "R2", "file": "CLAUDE.md", "line": 5}],
                                 [{"axis": "naming"}]), con, idx)[0]
        return (a == [] and any(k == "SC-2" and "풀 수 없는" in t for k, t in b)
                and any(k == "SC-2" and "임의 선택" in t for k, t in c)), [str(a), str(b), str(c)]

    @reg
    def gpt_verify_evidence_rereads():
        # 두 번째 자 — 원천이 그대로면 일치 · rollout 을 바꾸면 session-log · gpt-skills-only 가 잡는다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            args, tree = _gpt_fixture(td)
            row = build_gpt_row(args, tree)
            kinds = ["session-log", "input-hash", "gpt-skills-only", "marker", "no-claude-artifacts"]
            same = verify_gpt_row(row, kinds, tree)
            with open(os.path.join(td, "run", "g.rollouts", "r.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec",
                                     "input": 'tools.exec_command({cmd:"cat ~/.codex/skills/fz-x/SKILL.md"})'}}) + "\n")
            moved = verify_gpt_row(row, kinds, tree)
            return (same == [] and any(x.startswith("session-log") for x in moved)
                    and any(x.startswith("gpt-skills-only") for x in moved)), [str(same), str(moved)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def stale_scorer_unrun():
        # ⛔ GPT ISSUE-024 — 채점기(계측기) 버전이 바뀐 뒤의 옛 점수는 쓰지 않는다
        rc, out = _judge(base() + [_mk("C1", "C", 2, score_instr="old"), _mk("C2", "C", 4)], require=["SC-3"])
        return rc == UNRUN and any("C1" in x and "낡음" in x for x in out), out

    @reg
    def string_json_error_result():
        # ⛔ GPT ISSUE-005 — journal 결과가 JSON 문자열로 된 오류여도 실패로 센다
        td = tempfile.mkdtemp(prefix="abl-wf-")
        try:
            _write_lines(os.path.join(td, "agent-x1.jsonl"), [
                {"type": "user", "timestamp": "2026-01-01T00:00:00Z", "message": {"content": "[역할] 통합자 — x"}},
                {"type": "assistant", "timestamp": "2026-01-01T00:00:05Z",
                 "message": {"id": "m", "model": "claude-opus-5-5", "stop_reason": "end_turn", "usage": {"output_tokens": 1},
                             "content": []}}])
            _write_lines(os.path.join(td, "journal.jsonl"), [{"type": "started", "agentId": "x1"},
                                                             {"type": "result", "agentId": "x1",
                                                              "result": "{\"ok\": false, \"error\": \"worker failed\"}"}])
            s = wf_summary(td)
            return s["journal_empty_results"] == 1, [str(s["journal_empty_results"])]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def write_target_must_be_artifact():
        # ⛔ GPT ISSUE-011 — 같은 명령의 무관한 쓰기 동사는 산출물 쓰기가 아니다
        unrelated = "cat report.md; python3 -c \"from pathlib import Path; Path('other.md').write_text('x')\""
        real = "python3 -c \"from pathlib import Path; Path('out/report.md').write_text('x')\""
        return (not _writes_path(unrelated, "report.md") and _writes_path(real, "report.md")), []

    @reg
    def variable_path_and_cd_writes():
        # 실측 2026-09-26 — review B1 끝점이 +472s 로 잡혔다(실제 마지막 쓰기 +1433s)
        var_w = "python3 - <<'EOF'\np='ABT/review/self-review.md'\ns=open(p).read()\nopen(p,'w').write(s)\nEOF"
        var_r = "python3 - <<'EOF'\np='ABT/review/self-review.md'\nprint(open(p).read())\nq='x.md'\nopen(q,'w').write('')\nEOF"
        other = "python3 - <<'EOF'\np='other.md'\nopen(p,'w').write('')\nEOF"
        bases = _cd_bases("cd /r/repo && cat >> ABT/review/self-review.md <<'EOF'\nx\nEOF", "/x")
        ok = _writes_path(var_w, "self-review.md") and not _writes_path(var_r, "self-review.md") \
            and not _writes_path(other, "self-review.md") and bases == ["/x", "/r/repo"]
        return ok, [str(bases)]

    @reg
    def append_many_is_all_or_nothing():
        # v4.40.0 validate — recollect 가 행마다 덧붙이다 중간에 실패하면 일부만 남았다
        td = tempfile.mkdtemp(prefix="abl-app-")
        try:
            p = os.path.join(td, "l.jsonl")
            append(p, {"type": "run", "run_id": "a"})
            append_many(p, [{"type": "run", "run_id": "b"}, {"type": "run", "run_id": "c"}])
            ok1 = [json.loads(l)["run_id"] for l in open(p, encoding="utf-8")] == ["a", "b", "c"]
            try:
                append_many(p, [{"type": "run", "run_id": "d"}, {"bad": object()}])   # 직렬화 실패 → 아무것도 안 바뀐다
            except TypeError:
                pass
            ok2 = [json.loads(l)["run_id"] for l in open(p, encoding="utf-8")] == ["a", "b", "c"] and not glob.glob(os.path.join(td, ".ledger-*"))
            return ok1 and ok2, [str(ok1), str(ok2)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def end_snapshot_repo_path_checked():
        # v4.40.0 리뷰 — 종료 스냅샷이 다른(빈) repo_agent_memory 를 보면 AC-7 판정 불가다
        td = tempfile.mkdtemp(prefix="abl-state-")
        try:
            def snap(repo_mem):
                w = {"user_agent_memory": {"path": os.path.expanduser(CANON_WATCH["user_agent_memory"]), "pattern": None, "exists": True, "files": {}},
                     "repo_agent_memory": {"path": repo_mem, "pattern": None, "exists": False, "files": {}},
                     "user_sessions": {"path": os.path.expanduser(CANON_WATCH["user_sessions"]), "pattern": CANON_PATTERN["user_sessions"],
                                       "exists": True, "files": {}}}
                return {"schema": STATE_SCHEMA, "watch": w, "hash": state_hash(w)}
            paths = {}
            for k, repo_mem in (("p", "/nonexistent"), ("s", "/r/repo/.claude/agent-memory"), ("e_ok", "/r/repo/.claude/agent-memory"),
                                ("e_bad", "/other/.claude/agent-memory")):
                paths[k] = os.path.join(td, k + ".json")
                json.dump(snap(repo_mem), open(paths[k], "w", encoding="utf-8"))
            ok = state_info(paths["p"], paths["s"], paths["e_ok"], "/r/repo")["problems"]
            bad = state_info(paths["p"], paths["s"], paths["e_bad"], "/r/repo")["problems"]
            return (not any("end 의 repo_agent_memory" in x for x in ok) and any("end 의 repo_agent_memory" in x for x in bad)), ok + bad
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def cite_formats_from_real_artifacts():
        # v4.40.0 리뷰 — 실제 C1 산출물은 `path` L52–65 형식을 쓴다(후보에서 빠진 채 verified=True)
        t = ("- `App/Watchlist/WatchlistInteractor.swift` L52–65 삭제 경로\n- App/Foo.swift#L10-L20 참고\n"
             "- Bar.swift L3-6 · Baz.swift:7\n- 버전 4.40.0 L2 는 인용이 아니다")
        got = [(f, s, e) for f, s, e, _ in cite_spans([t])]
        want = sorted([("App/Foo.swift", 10, 20), ("App/Watchlist/WatchlistInteractor.swift", 52, 65), ("Bar.swift", 3, 6), ("Baz.swift", 7, 7)])
        return got == want, [str(got)]

    @reg
    def gpt_call_heads_and_segment():
        # v4.40.0 리뷰 — 템플릿의 들여쓴·then 뒤·접두 호출을 못 잡았고, 뒤 호출의 --effort 가 앞 호출을 '명시' 로 바꿨다
        pos = ["if true; then\n  \"$P/scripts/gpt-exec.sh\" exec --cd . --out o.md --prompt-file p.md\nfi",
               "then \"$P/scripts/gpt-exec.sh\" review --cd . --out r.md --uncommitted",
               "FZ_PLUGIN_ROOT=$P bash \"$P/scripts/gpt-exec.sh\" exec --cd . --out o.md --prompt-file p",
               "timeout 600 $P/scripts/gpt-exec.sh exec --cd . --out o.md --prompt-file p"]
        neg = ["sed -n 1,60p $P/scripts/gpt-exec.sh | grep usage", "rg 'gpt-exec.sh exec' modules"]
        heads = [bool(GPT_CALL_RE.search(_shell_part(c))) for c in pos + neg]
        two = ("\"$P/scripts/gpt-exec.sh\" exec --cd . --out a.md --prompt-file p\n"
               "\"$P/scripts/gpt-exec.sh\" exec --cd . --out b.md --prompt-file q --effort high")
        seg = _call_segment(two, GPT_CALL_RE.search(two))
        tight = "$P/scripts/gpt-exec.sh exec --cd . --out a.md; echo --effort high"
        seg2 = _call_segment(tight, GPT_CALL_RE.search(tight))
        quoted = '$P/scripts/gpt-exec.sh exec --cd "a;b && c" --out o.md > "$W/l;og" 2>&1 --effort high; echo x'
        seg3 = _call_segment(quoted, GPT_CALL_RE.search(quoted))
        cont = "$P/scripts/gpt-exec.sh exec --cd . \\\n  --out c.md --effort xhigh\necho --effort low"
        seg4 = _call_segment(cont, GPT_CALL_RE.search(cont))
        ok = heads == [True] * len(pos) + [False] * len(neg) and "--effort" not in seg and "a.md" in seg and "b.md" not in seg \
            and "--effort" not in seg2 and "a.md" in seg2 and "--effort high" in seg3 and "echo" not in seg3 \
            and "--effort xhigh" in seg4 and "low" not in seg4
        return ok, [str(heads), seg, seg2, seg3, seg4]

    @reg
    def verify_fields_cover_judged_gpt_and_plugin():
        # hunter M1 — 판정이 읽는 필드가 원천 대조 밖이면 행을 고쳐 무효 사유를 지울 수 있다(실측 FAIL→PASS)
        need = {"gpt.failed", "gpt.unlinked", "plugin.dirty", "plugin.source", "plugin.source_tree_hash"}
        return need <= set(VERIFY_FIELDS["transcript"]), [str(sorted(need - set(VERIFY_FIELDS["transcript"])))]

    @reg
    def argv_and_shell_var_writes():
        # 실측 2026-09-27(F-331) — B 4/6 run 의 마지막 쓰기(셸 변수 리다이렉트 · argv 로 넘긴 경로 · for 값)를 놓쳤다
        art = "/r/ABT/review/self-review.md"
        pos = ["F=/r/ABT/review/self-review.md; python3 - \"$F\" <<'EOF'\nimport sys\np=sys.argv[1]; t=open(p).read()\n"
               "open(p,'w').write(t); print(\"ok\")\nEOF",
               "W=/r/ABT/review; cp /tmp/x.txt $W/integrity-check.txt; cat >> $W/self-review.md <<'EOF'\n- x\nEOF",
               "W=/r/ABT; for f in self-review.md other.md; do python3 - \"$W/review/$f\" <<'EOF'\nimport sys\n"
               "p=sys.argv[1]; s=open(p,encoding='utf-8').read()\nopen(p,\"w\",encoding='utf-8').write(s)\nEOF\ndone",
               "P=/r/log.md; W=/r/ABT/review; python3 - \"$P\" \"$W/self-review.md\" <<'PY'\nimport sys\n"
               "p,sr=sys.argv[1],sys.argv[2]\nopen(sr,'w').write('x')\nPY"]
        neg = ["F=/r/ABT/review/self-review.md; python3 - \"$F\" <<'EOF'\nimport sys\np=sys.argv[1]\nprint(open(p).read())\nEOF",
               "A=/r/log.md; F=/r/ABT/review/self-review.md; python3 - \"$A\" \"$F\" <<'EOF'\nimport sys\n"
               "p,sr=sys.argv[1],sys.argv[2]\nt=open(sr).read()\nopen(p,'w').write(t)\nEOF",
               "W=/r/ABT/review; cat $W/self-review.md 2>&1 | head"]
        got = [_bash_writes(c, art, "/x") for c in pos + neg]
        return got == [True] * len(pos) + [False] * len(neg), [str(got)]

    def _effort_rows(e1, e2, d1, d2):
        rs = base()
        for (r, _), e, d in zip(rs, (e1, e2), (d1, d2)):
            r["gpt"]["efforts"], r["gpt"]["efforts_default"] = e, d
        return rs

    @reg
    def gpt_explicit_effort_not_compared():
        # F-333 — Lead 가 `--effort` 를 명시한 호출은 run 마다 달라도 무효가 아니다(측정 대상의 행동)
        rc, out = _judge(_effort_rows(["xhigh"], ["high"], [], []), phase="baseline", min_runs=2)
        return rc == PASS and not any("불일치" in x for x in out), out

    @reg
    def gpt_default_effort_still_compared():
        # F-333 — 기본값으로 간 호출의 effort 가 다르면 환경 차이다 — 여전히 무효
        rc, out = _judge(_effort_rows(["xhigh"], ["high"], ["xhigh"], ["high"]), phase="baseline", min_runs=2)
        return rc == FAIL and any("gpt-effort 불일치" in x for x in out), out

    @reg
    def blind_source_accumulates():
        # ⛔ GPT ISSUE-023 — 꾸러미 source 는 fixture 의 모든 run 이 인용한 파일을 담는다
        td = tempfile.mkdtemp(prefix="abl-src-")
        try:
            fxr = os.path.join(td, "fx")
            for sub, body in (("base", "x\n"), ("head", "y\n")):
                for f in ("App/A.swift", "App/B.swift"):
                    os.makedirs(os.path.dirname(os.path.join(fxr, "r", sub, f)), exist_ok=True)
                    open(os.path.join(fxr, "r", sub, f), "w").write(body if f.endswith("A.swift") else "same\n")
            json.dump(labels2, open(os.path.join(fxr, "r", "labels.json"), "w"))
            rows = []
            for rid, cite in (("RA", "App/A.swift:1"), ("RB", "App/B.swift:1")):
                ap_ = os.path.join(td, f"{rid}.md")
                open(ap_, "w").write(f"- `{cite}` 지적\n")
                rows.append({"run_id": rid, "fixture": "r", "sources": {"artifacts": [ap_]}, "artifacts": []})
            pack, _ = blind_pack(rows, fxr, "s")
            files = sorted(pack["fixtures"]["r"]["source"]["files"])
            return files == ["App/A.swift", "App/B.swift"], [str(files)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def blind_roundtrip():
        td = tempfile.mkdtemp(prefix="abl-blind-")
        try:
            fxr = os.path.join(td, "fx")
            os.makedirs(os.path.join(fxr, "r"))
            with open(os.path.join(fxr, "r", "labels.json"), "w", encoding="utf-8") as fh:
                json.dump(labels2, fh)
            rows = []
            for rid in ("RUNID-ALPHA", "RUNID-BETA"):
                ap_ = os.path.join(td, f"{rid}.md")
                with open(ap_, "w", encoding="utf-8") as fh:
                    fh.write(f"- `App/A.swift:11` 이름 문제 (/Users/someone/{rid}/x)\n")
                rows.append({"run_id": rid, "arm": "B", "fixture": "r", "sources": {"artifacts": [ap_]}})
            pack, key = blind_pack(rows, fxr, "salt")
            blob = json.dumps(pack, ensure_ascii=False)
            leak = [s for s in ("RUNID-ALPHA", "RUNID-BETA", "/Users/", '"arm"') if s in blob]
            va = {it["anon"]: {c["cid"]: {"real": True, "label_ids": ["I1"]} for c in it["candidates"]} for it in pack["items"]}
            got, _arts, missing = blind_unpack(pack, key, va)
            va2 = dict(va)
            va2.pop(pack["items"][0]["anon"])
            _, _, missing2 = blind_unpack(pack, key, va2)
            ok = not leak and sorted(got) == ["RUNID-ALPHA", "RUNID-BETA"] and not missing and len(missing2) == 1
            return ok, [f"leak={leak} got={sorted(got)} missing={missing} missing2={missing2}"]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    names = [case] if case else sorted(cases)
    if case and case not in cases:
        print(f"UNRUN: 모르는 case {case} (있는 것: {', '.join(sorted(cases))})")
        return UNRUN
    passed, fails = 0, []
    for n in names:
        try:
            ok, out = cases[n]()
        except Exception as e:  # noqa: BLE001 — self-test 는 예외도 실패로 센다
            ok, out = False, [f"예외 {type(e).__name__}: {e}"]
        if ok:
            passed += 1
        else:
            fails.append(n)
            print(f"  FAIL {n}")
            for x in out[:6]:
                print(f"       {x[:220]}")
    print(f"self-test {passed}/{len(names)} passed")
    return PASS if not fails else FAIL
