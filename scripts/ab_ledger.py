#!/usr/bin/env python3
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 형제 모듈 import(fz_wf_metrics·freeze_baseline)와
#   계측기 해시에 이 파일의 디렉토리만 쓴다. 원장·transcript·fixture 경로는 전부 호출자가 넘긴다.
# diff-parse: not-a-diff — `startswith("-")` 는 셸 명령 토큰의 플래그 판별이다(sed -i · --out-dir · --out= · 스크립트 argv).
#   `startswith("--------")` 는 GPT 스트림 로그 배너의 구분선이다. diff 줄 접두를 판정하는 곳은 없다.
"""ab_ledger.py — A/B 원장: 수집(collect)·채점(score)·판정(judge) (S05).

왜: 속도 개선을 주장하려면 **같은 입력·같은 모델/effort·완주한 run** 끼리만 비교해야 한다. 손으로 옮긴
   수치는 이 조건을 검사하지 않고, 잘린 run 은 오류 없이 그럴듯한 wall 을 낸다(F-203). 이 도구는 값을
   원천(Lead transcript · Workflow 폴더 · 상태 스냅샷)에서 읽고, judge 는 `--verify-sources` 로 **다시** 읽는다.

원장 = JSONL, append-only. 같은 run_id 는 **마지막 행**이 이긴다(recollect·재채점은 새 행을 쓴다).
  {"type":"run",   run_id, workflow, arm, run, order, phase, release, fixture,
                   lead{model, models, effort, efforts, cli_versions, out_tok, messages, tool_errors,
                        bash_arg_chars, heredoc_targets, inline_python, followup_prompts, advisor},
                   plugin{root, roots, sha, dirty, tree_hash}, injected{User, Project, AutoMem}, instrument_sha,
                   input{hash, fixture, commits, prompt_sha},
                   wall{total_s, start, end, mtime_delta_s, workflows[{run_id, wf_s, lead_s, delta_pct}], gpt_s},
                   wf{runs[…], agents, out_tok, turns, advisor, models, efforts, stages, stage2_ran,
                      stages_completed, rejections},
                   gpt{calls, models, efforts, versions}, state{start_hash, pristine_hash, end_hash, leak, writes},
                   complete{ok, why}, sources{…}, collect_args{…}}
  {"type":"score", run_id, kind(review|plan), by_severity, by_axis, …, fixture_sha}

측정 규약 (⛔ 전부 실측으로 정했다 — 2026-09-26)
  · Lead·워커 transcript 는 응답 1건을 content block 마다 한 줄로 쓰고 **같은 id 에 같은 usage 를 반복**한다.
    usage 는 message id 별로 한 번만 센다(줄 합산은 1.35~1.6배 과대).
  · effort 는 assistant 이벤트 최상위 `effort`, model 은 `message.model` 이다(`<synthetic>` 제외).
  · 완료 시각은 task-notification 의 가장 이른 기록이다(queue-operation enqueue ≤ user 메시지).
  · wall_total = 첫 사람 발화 → 최종 산출물 기록 이벤트(Write·Edit·Bash 리다이렉트)의 결과 시각.
    파일 mtime 은 **교차 검사에만** 쓴다(mtime 자는 -36% 편향 — 판정에 쓰지 않는다).
  · wall_workflow 는 두 자 — 에이전트 timestamp(fz_wf_metrics) 와 Lead 의 Workflow 기동→완료 알림 — 끼리만
    교차하고 5% 를 넘으면 그 run 은 무효다. 두 값과 차이를 함께 인쇄한다.
  · 입력 해시 = sha256(fixture 이름 · fixture 저장소 main/feature 커밋 · 첫 사람 발화). build-repo.sh 가 커밋
    신원·시각을 고정하므로 같은 fixture 는 같은 SHA 를 낸다. 플러그인 트리 해시는 freeze_baseline 헬퍼로 따로 잰다.

exit: 0=PASS · 1=FAIL · 2=UNRUN(측정 불가·미구현 기준 — ⛔ 통과로 읽지 않는다)

Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import collections
import glob
import hashlib
import json
import math
import os
import pathlib
import re
import shlex
import shutil
import statistics
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import freeze_baseline as fb  # noqa: E402 — 형제 모듈(트리 파일 목록·해시)
import fz_wf_metrics as wfm   # noqa: E402 — 형제 모듈(Workflow 폴더 집계)

# 실행 코드는 형제 모듈(ab_ledger_*.py)에 있다. 이 파일은 CLI 진입점이고, 모듈 속성으로 읽는 소비자(tests · 외부 재생 러너)를 위해 하위 모듈의 이름을 그대로 다시 내보낸다.
from ab_ledger_base import (AXES6, AXES_ALLOWED, DEFAULT_EFFORT, DEFAULT_MODEL, FAIL, GATED, GPT_PASS_CRIT, INSTRUMENTS,
    LINE_TOL, MTIME_TOL_S, PASS, PHASES, SCHEMA, SEVERITIES, SOURCE_KINDS, STATE_SCHEMA, UNRUN, WALL_XCHECK_PCT, instrument_sha,
    iso, iter_jsonl, norm_model, read_json, secs, sha_obj, sha_text)
from ab_ledger_transcript import (ARGV_BIND_RE, ARGV_DIRECT_RE, ASSIGN_RE, BASE_DIR_RE, CD_RE, CPMV_RE, FOR_RE, FSTR_WRITE_RE,
    GPT_CALL_RE, GPT_OUT_RE, HEREDOC_RE, INLINE_PY_RE, LAUNCHER_RE, NOTIF_RE, PHASE2_RE, PY_ARGV_RE, PY_EXE_RE, PY_SCRIPT_RE,
    REAL_HOME_SKILL_RE, REDIRECT_RE, RENDER_OUTPUTS, SH_HEREDOC_RE, VAR_RE, WRITE_HINT_RE, WRITE_TOOLS, _argv_writes,
    _argv_written, _bash_writes, _call_segment, _cd_bases, _cmd_views, _exec_of, _expand_vars, _follow_moves,
    _fstring_argv_targets, _heredoc_scripts, _launcher_calls, _launcher_ok, _load_return, _merge_summaries, _mv_pairs,
    _plan_phase2, _redirect_targets, _render_outputs, _resolve_vars, _resolved_output, _same_path, _script_argv_writes,
    _sed_inplace_files, _segments, _shell_heredoc_bodies, _shell_part, _strings, _tag, _var_written, _writes_path,
    gpt_home_sessions, parse_transcript, queued_followups)
from ab_ledger_collect import (ALLOWED_PLUGIN_WRITES, ANSI_RE, CANON_PATTERN, CANON_WATCH, COLLECT_SPEC, COLLECT_SPEC_VERSION,
    REQUIRED_STAGES, REQUIRED_WATCH, SKILL_SCRIPTS, STAGES_BY_SCRIPT, _clock_time, _endpoint_clock_evidence, _evidence_dir,
    _ledger_lock, _state_key, append, append_collect, append_many, apply_endpoint_clock, build_row, collect_spec_args,
    expected_stages_completed, input_commits, input_hash, load, parse_gpt_log, plugin_info, read_endpoint_clock, required_stages,
    row_origin, snapshot, state_diff, state_hash, state_info, tree_digest, wf_summary)
from ab_ledger_judge import (BLIND_INSTRUCTIONS, BLOCK_START_RE, CITE_RE, CRITERIA, CTX_CAP, IMPLEMENTED, PATH_SCRUB_RE,
    SC7_FIELDS, VERIFY_FIELDS, _artifact_shas, _blocks, _crit_invalid, _dig, _exact, _fixture_source, _items, _js, _key_fields,
    _mean, _one_row_table, _ordered_json, _read_texts, _same_file, _sep_row, _sev, _unchecked_note, blind_pack, blind_unpack,
    cand_id, cite_spans, crit_blind_labels, crit_critical_path, crit_crossover, crit_gpt_wf_wall, crit_sc3, crit_sc4, crit_sc5,
    crit_sc6, crit_sc7, fixture_files, group_invalid, judge_rows, near_labels, plan_items, recollect_diff, resolve_cited,
    row_invalid, rule_files, score_plan, score_review, select, verify_sources)
from ab_ledger_gpt import (EVIDENCE_KINDS, GPT_BAD_INPUT_RE, GPT_CMD_STR_RE, GPT_MARKER_RE, GPT_SKILL_REF_RE, GPT_WORKDIR_RE,
    IOS_VOCAB_RE, LABEL_TO_RULE_AXIS, RULE_FIXTURES, SEV_RANK, _body_matches, _fixture_docs, _index_sections, _js_unquote,
    _rule_src, _sha_file, _src_in_section, build_gpt_row, classify_skill_refs, gpt_sc1_problems, gpt_sc2_problems, judge_gpt,
    load_gpt, rules_compare, scan_gpt_rollouts, summarize_gpt_output, tree_hash, verify_gpt_row)


# ── CLI ────────────────────────────────────────────────────────────────
def cmd_snapshot(a):
    if not a.watch:
        print("UNRUN: --watch 가 없다 — 감시 대상 없는 스냅샷은 AC-7 을 판정하지 못한다")
        return UNRUN
    watch = {}
    for w in a.watch:
        if "=" not in w:
            print(f"UNRUN: --watch 는 이름=경로 형식 — {w}")
            return UNRUN
        k, v = w.split("=", 1)
        watch[k] = v
    snap = snapshot(watch)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"snapshot {a.out}: " + " · ".join(f"{k}={len(v['files'])}" for k, v in snap["watch"].items())
          + f" · hash {snap['hash'][:12]}")
    return PASS


def cmd_input(a):
    """run **전**에 입력 신원을 남긴다 — 커밋 · 깨끗한 작업 트리 · 트리 내용 해시 · 저장소 경로."""
    commits = input_commits(a.root)
    if not commits:
        print(f"UNRUN: 커밋을 읽지 못했다 — {a.root}")
        return UNRUN
    st = fb.git(pathlib.Path(a.root), "status", "--porcelain", "--untracked-files=all")
    rec = {"fixture": a.fixture, "commits": commits, "root": os.path.realpath(a.root),
           "clean": st is not None and not st.strip(), "tree_hash": tree_digest(a.root)}
    if not rec["tree_hash"]:
        print(f"UNRUN: 입력 트리 해시를 잴 수 없다(git 목록·읽기 실패) — {a.root}")
        return UNRUN
    if a.plugin_root:
        # ⛔ run 이 플러그인 사본에 experiment-log 를 쓴다 — 신원은 run **전**에 잰다(collect 시점엔 dirty)
        rec["plugin"] = dict(plugin_info(os.path.realpath(a.plugin_root)), at="start")
        if a.plugin_source:
            # 사본이 선언된 원본의 충실한 복제인가(B = 기준 트리 · C = 작업 트리)
            rec["plugin"]["source"] = os.path.realpath(a.plugin_source)
            rec["plugin"]["source_tree_hash"] = tree_digest(a.plugin_source)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    print(f"input {a.fixture}: " + " · ".join(f"{k}={v[:10]}" for k, v in commits.items())
          + f" · clean={rec['clean']} · tree {str(rec['tree_hash'])[:12]}")
    return PASS if rec["clean"] else FAIL


def cmd_collect(a):
    if a.phase not in PHASES:
        print(f"UNRUN: --phase 는 {PHASES} 중 하나")
        return UNRUN
    if not os.path.isfile(a.transcript):
        print(f"UNRUN: transcript 없음 — {a.transcript}")
        return UNRUN
    row = append_collect(a.ledger, build_row(collect_spec_args(a)))
    c = row["complete"]
    print(f"collect {row['run_id']}: complete={c['ok']} wall_total={row['wall']['total_s']}s "
          f"lead_out={row['lead']['out_tok']} wf_agents={row['wf']['agents']} input={str(row['input']['hash'])[:12]}")
    for w in c["why"]:
        print(f"  ⚠️ {w}")
    if row["measure_seq"] > 1:
        print(f"  ⚠️ 같은 run_id 의 {row['measure_seq']}번째 측정이다 — judge 는 마지막 행을 쓴다(이력: show --history {row['run_id']})")
    return PASS


def cmd_recollect(a):
    try:
        runs, _ = load(a.ledger)
    except (OSError, ValueError) as e:
        print(f"UNRUN: 원장을 읽지 못했다 — {e}")
        return UNRUN
    if a.run_id and a.run_id not in runs:
        print(f"UNRUN: 원장에 run {a.run_id} 이 없다")
        return UNRUN
    targets = [runs[a.run_id]] if a.run_id else list(runs.values())
    if not targets:
        print("UNRUN: 다시 수집할 run 이 없다")
        return UNRUN
    # ⛔ 전부 다시 만든 뒤 한 번에 덧붙인다 — 중간 실패로 계측기 버전이 섞인 원장이 남지 않게(v4.40.0 리뷰)
    news = []
    for row in targets:
        try:
            new = build_row(collect_spec_args(row["collect_args"]))   # 옛 형식 행도 CollectSpec 필드로 읽는다
        except Exception as e:   # noqa: BLE001 — 원천 부재·옛 인자 모양 모두 판정 불가다
            print(f"UNRUN: {row.get('run_id')} 재구성 실패 {type(e).__name__}: {e} — 원장에 아무것도 덧붙이지 않았다")
            return UNRUN
        # 재수집은 재측정이 아니다 — 같은 측정 순번을 잇는다(옛 행은 순번이 없다)
        new.update(recollected_from=row.get("instrument_sha"), origin="recollect", measure_seq=row.get("measure_seq"))
        news.append((row, new))
    try:
        append_many(a.ledger, [new for _, new in news])
    except (OSError, TypeError, ValueError) as e:
        print(f"UNRUN: 원장에 쓰지 못했다 — {type(e).__name__}: {e} (원장은 그대로다)")
        return UNRUN
    n_changed = worse = 0
    for row, new in news:
        print(f"recollect {new['run_id']}: complete={new['complete']['ok']} instrument {row.get('instrument_sha')}→{new['instrument_sha']}")
        changed, added, bad = recollect_diff(row, new)
        n_changed += bool(changed or added)
        worse += bad
        for f in changed:
            print(f"  차이 {f}: {_js(_dig(row, f))[:120]} → {_js(_dig(new, f))[:120]}")
        if bad:
            print(f"  RECOLLECT-WORSE {new['run_id']}: " + " · ".join(added or ["완주 True→False"]))
    print(f"recollect: runs={len(news)} changed={n_changed} worse={worse}"
          + (" — ⛔ 악화 행도 덧붙였다(판정이 바뀐다). 원천·계측기를 확인하라" if worse else ""))
    return FAIL if worse else PASS


def cmd_score(a):
    """채점 — 가린 검증자 판정(`blind-unpack` 출력)이 있으면 그것으로 센다. 없으면 **미검증** 점수만 남는다
    (SC-3·SC-4 는 미검증 점수를 판정하지 않는다)."""
    runs, _ = load(a.ledger)
    targets = [runs[a.run_id]] if a.run_id else list(runs.values())
    vdoc = read_json(a.verdicts) if a.verdicts else {}
    if vdoc and not vdoc.get("blinded"):
        print("UNRUN: --verdicts 는 blind-unpack 출력이어야 한다(blinded=true) — arm 을 아는 판정은 받지 않는다")
        return UNRUN
    verdicts, varts = vdoc.get("runs") or {}, vdoc.get("artifacts") or {}
    rc = PASS
    for row in targets:
        fx = os.path.join(a.fixtures_root, row["fixture"] or "")
        texts = _read_texts(row)
        cur = _artifact_shas(row)
        v = verdicts.get(row["run_id"]) if vdoc else None
        if v is not None and varts.get(row["run_id"]) != cur:
            # ⛔ 판정은 꾸러미를 만들 때의 산출물 버전에 대한 것이다 — 산출물이 바뀌었으면 옛 판정을 쓰지 않는다
            print(f"  ⚠️ {row['run_id']}: 판정의 산출물 해시 ≠ 현재 산출물 — 미검증으로 채점한다(blind-pack 을 다시)")
            v = None
        if os.path.isfile(os.path.join(fx, "labels.json")):
            lp = os.path.join(fx, "labels.json")
            s = score_review(read_json(lp), texts, v, fixture_files(fx), rule_files(fx))
        elif os.path.isfile(os.path.join(fx, "rubric.json")):
            lp = os.path.join(fx, "rubric.json")
            s = score_plan(read_json(lp), "\n".join(texts), v)
        else:
            print(f"UNRUN {row['run_id']}: 채점표 없음 — {fx}")
            rc = UNRUN
            continue
        s.update({"type": "score", "run_id": row["run_id"], "fixture_sha": fb.hash_file(pathlib.Path(lp)),
                  "blind_pack_sha": vdoc.get("pack_sha") if v is not None else None, "artifacts_sha": cur,
                  "instrument_sha": instrument_sha()})
        append(a.ledger, s)
        sev = s["by_severity"] or {}
        print(f"score {row['run_id']}: verified={s['verified']} " + " ".join(f"{k}={v}" for k, v in sev.items())
              + (f" ratio={s.get('verified_ratio')}" if s["kind"] == "review" else f" covered={len(s['covered'])}/{s['items_total']}")
              + (f" · 미판정 {s['unverified']}" if s.get("unverified") else ""))
    return rc


def cmd_blind_pack(a):
    runs, _ = load(a.ledger)
    ids = a.run_id or [r["run_id"] for r in runs.values() if (r.get("complete") or {}).get("ok")]
    rows = [runs[i] for i in ids if i in runs]
    if not rows:
        print("UNRUN: 꾸러미에 넣을 run 이 없다(완주 run 0)")
        return UNRUN
    salt = a.salt or os.urandom(8).hex()
    try:
        pack, key = blind_pack(rows, a.fixtures_root, salt)
    except (OSError, ValueError) as e:
        print(f"UNRUN: {e}")
        return UNRUN
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "pack.json"), "w", encoding="utf-8") as fh:
        json.dump(pack, fh, ensure_ascii=False, indent=1, sort_keys=True)
    with open(os.path.join(a.out, "key.json"), "w", encoding="utf-8") as fh:
        json.dump({"key": key, "pack_sha": fb.hash_file(pathlib.Path(a.out, "pack.json"))}, fh, ensure_ascii=False, indent=1)
    n = sum(len(it.get("candidates", [])) for it in pack["items"])
    print(f"blind-pack {a.out}: 항목 {len(pack['items'])} · 리뷰 후보 {n} — ⛔ 검증자에게는 pack.json 만 준다(key.json 금지)")
    return PASS


def cmd_blind_unpack(a):
    try:
        pack = read_json(os.path.join(a.pack, "pack.json"))
        kd = read_json(os.path.join(a.pack, "key.json"))
        va = read_json(a.verdicts)
    except (OSError, ValueError) as e:
        print(f"UNRUN: {e}")
        return UNRUN
    sha = fb.hash_file(pathlib.Path(a.pack, "pack.json"))
    if sha != kd.get("pack_sha"):
        print("UNRUN: pack.json 이 꾸러미 생성 뒤 바뀌었다 — 판정 대상이 다르다")
        return UNRUN
    runs, arts, missing = blind_unpack(pack, kd["key"], va)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"schema": "ab-verdicts/1", "blinded": True, "pack_sha": sha, "runs": runs, "artifacts": arts,
                   "missing": missing},
                  fh, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"blind-unpack → {a.out}: run {len(runs)} · 빠진 판정 {len(missing)}" + (f" {missing[:4]}" if missing else ""))
    return PASS if not missing else FAIL


def cmd_judge(a):
    if a.min_runs < 1 or a.runs < 1:
        print(f"UNRUN: --min-runs·--runs 는 1 이상이어야 한다(받은 값 {a.min_runs}·{a.runs}) — 0 이면 유효 run 0건으로 통과한다")
        return UNRUN
    try:
        runs, scores = load(a.ledger)
    except (OSError, ValueError) as e:
        print(f"UNRUN: 원장을 읽지 못했다 — {e}")
        return UNRUN
    kinds = [k for k in (a.verify_sources or "").split(",") if k]
    bad = [k for k in kinds if k not in SOURCE_KINDS]
    if bad:
        print(f"UNRUN: 모르는 --verify-sources {bad} (허용 {SOURCE_KINDS})")
        return UNRUN
    wfs = [w for w in ((a.workflows or "") + "," + (a.workflow or "")).split(",") if w]
    req = [x for x in (a.require or "").split(",") if x]
    if a.phase == "baseline":
        req = req or ["baseline-runs"]
    elif not req:
        print("UNRUN: --require 없음 — 무엇을 판정할지 정하지 않았다")
        return UNRUN
    if a.formal:
        # 정식 비교(F-335 ⑧) — 원천을 다시 읽지 않았거나 기준선 트리 신원을 대조하지 않은 판정은 정식 비교가 아니다.
        #   ⛔ 이 플래그 없는 호출은 그대로다(기존 argv 의 출력 · exit 바이트 불변). 있으면 판정 · exit 는 같고 머리 줄 하나를 더한다
        if not kinds:
            print("UNRUN: FORMAL-SOURCES-MISSING — --formal 은 --verify-sources(원천 종류 1개 이상)가 필요하다")
            return UNRUN
        if not a.plugin_sha and any(r.get("arm") == "B" for r in runs.values()):
            print("UNRUN: FORMAL-PLUGIN-SHA-MISSING — 원장에 기준선(B) 행이 있는데 --plugin-sha 가 없다")
            return UNRUN
        print(f"formal: verify-sources={','.join(kinds)} · plugin-sha={a.plugin_sha or '-'}")
    s27 = [x for x in req if x in GPT_PASS_CRIT]
    if s27:
        if len(s27) != len(req):
            print(f"UNRUN: S27 기준 {s27} 은 run 기준과 섞지 않는다 — 따로 부른다")
            return UNRUN
        try:
            gpts = load_gpt(a.ledger)
        except (OSError, ValueError) as e:
            print(f"UNRUN: 원장을 읽지 못했다 — {e}")
            return UNRUN
        envs = [e for e in (a.envs or "").split(",") if e]
        rc, lines = judge_gpt(gpts, req, envs, a.fixtures_root)
        for x in lines:
            print(x)
        print(f"judge: {('PASS', 'FAIL', 'UNRUN')[rc]} (gpt-pass · require={','.join(req)} · envs={','.join(envs) or '-'})")
        return rc
    opts = {"model": a.model, "effort": a.effort, "phase": a.phase, "arm": a.arm, "release": a.release,
            "workflows": wfs, "min_runs": a.min_runs, "runs": a.runs, "plugin_sha": a.plugin_sha,
            "require": req, "envs": a.envs, "options_on": a.options_on, "require_passed": a.require_passed}
    rc, lines = judge_rows(runs, scores, opts, (lambda r: verify_sources(r, kinds)) if kinds else None)
    for x in lines:
        print(x)
    print(f"judge: {('PASS', 'FAIL', 'UNRUN')[rc]} (phase={a.phase or 'change'} · require={','.join(req)}"
          + (f" · verify-sources={','.join(kinds)}" if kinds else "") + ")")
    return rc


def show_history(ledger, run_id):
    """run_id 의 행 이력(원장 순서) — 재측정(collect#n)과 재수집(recollect)을 가른다(F-335 ⑦). judge · load() 는 마지막 행을 쓴다."""
    try:
        evs, bad = iter_jsonl(ledger)
    except OSError as e:
        print(f"UNRUN: 원장을 읽지 못했다 — {e}")
        return UNRUN
    rows = [r for r in evs if r.get("type") == "run" and r.get("run_id") == run_id]
    if not rows:
        print(f"UNRUN: 원장에 run {run_id} 이 없다")
        return UNRUN
    print(f"history {run_id}: 행 {len(rows)}개 (원장 순서 — judge 는 마지막 행)" + (f" · 원장 파싱 불가 줄 {bad}" if bad else ""))
    for i, r in enumerate(rows, 1):
        o, seq = row_origin(r), r.get("measure_seq")
        kind = {"collect": f"collect#{seq}", "recollect": f"recollect←collect#{seq}" if seq else "recollect"}.get(o, o)
        print(f"  {i} {kind} instrument={r.get('instrument_sha')} complete={(r.get('complete') or {}).get('ok')} "
              f"wall={(r.get('wall') or {}).get('total_s')}" + (" ← judge" if i == len(rows) else ""))
    return PASS


def cmd_show(a):
    if a.history:
        return show_history(a.ledger, a.history)
    runs, scores = load(a.ledger)
    for r in sorted(runs.values(), key=lambda r: (r["workflow"], r.get("order") or 0)):
        s = scores.get(r["run_id"]) or {}
        sev = s.get("by_severity") or {}
        d = [w["delta_pct"] for w in r["wall"]["workflows"] if w.get("delta_pct") is not None]
        g = r.get("gpt") or {}
        print(f"{r['run_id']:34} order={r.get('order')} complete={r['complete']['ok']} "
              f"wall={r['wall']['total_s']} Δmt={r['wall'].get('mtime_delta_s')} lead_out={r['lead']['out_tok']} msgs={r['lead']['messages']} "
              f"wf_out={r['wf']['out_tok']} turns={r['wf']['turns']} crit={sev.get('critical')} major={sev.get('major')} "
              f"gpt={g.get('calls')}({'/'.join(g.get('models') or [])}:{'/'.join(g.get('efforts') or [])}) "
              f"Δwf={max(d) if d else None}%")
    return PASS


def cmd_collect_gpt(a):
    inputs = {}
    for x in a.input or []:
        if "=" not in x:
            print(f"UNRUN: --input 은 이름=경로 — 받은 값 {x}")
            return UNRUN
        n, pth = x.split("=", 1)
        inputs[n] = os.path.abspath(pth)
    args = {"out": os.path.abspath(a.out), "run_id": a.run_id, "env": a.env, "mode": a.mode, "fixture": a.fixture,
            "plugin_root": os.path.abspath(a.plugin_root), "inputs": inputs,
            "lead_rules": os.path.abspath(a.lead_rules) if a.lead_rules else None, "gpt_agents": bool(a.gpt_agents)}
    try:
        row = build_gpt_row(args)
    except (OSError, ValueError) as e:
        print(f"UNRUN: 원천을 읽지 못했다 — {e}")
        return UNRUN
    append(a.ledger, row)
    pr = gpt_sc1_problems(row)
    print(f"collect-gpt {row['run_id']}: env={row['env']} mode={row['mode']} fixture={row['fixture']} · 감사 exit {row['audit']['exit']} · "
          f"마커 {len(row['scan']['markers'])} · 스킬 참조 {len(row['scan']['refs'])}(밖 {len(row['scan']['bad_refs'])}) · "
          f"host 스킬 {row['scan']['host_skills']} · SC-1 문제 {len(pr)}")
    return PASS


def cmd_verify_evidence(a):
    """S27 CHECK 두 번째 자 — 매트릭스 · 규칙 fixture 범위 확인 + 행마다 원천 재판독."""
    try:
        gpts = load_gpt(a.ledger)
    except (OSError, ValueError) as e:
        print(f"UNRUN: 원장을 읽지 못했다 — {e}")
        return UNRUN
    kinds = [k for k in (a.require or "").split(",") if k]
    unknown = [k for k in kinds if k not in EVIDENCE_KINDS]
    if not kinds or unknown:
        print(f"UNRUN: --require 는 {EVIDENCE_KINDS} 중에서 — 받은 값 {kinds}")
        return UNRUN
    envs = [e for e in (a.envs or "").split(",") if e]
    cells = []
    if a.matrix:
        m = re.fullmatch(r"([a-z,]+):x:([a-z,]+)", a.matrix)
        if not m:
            print(f"UNRUN: --matrix 형식은 env1,env2:x:mode1,mode2 — 받은 값 {a.matrix}")
            return UNRUN
        cells = [(e, md) for e in m.group(1).split(",") for md in m.group(2).split(",")]
    if envs and cells and sorted({e for e, _ in cells}) != sorted(envs):
        print(f"UNRUN: --envs {envs} 와 --matrix 환경이 다르다")
        return UNRUN
    rfx = [x for x in (a.rule_fixtures or "").split(",") if x]
    miss = [x for x in rfx if x not in RULE_FIXTURES]
    if miss:
        print(f"UNRUN: 모르는 --rule-fixtures {miss} (허용 {sorted(RULE_FIXTURES)})")
        return UNRUN
    rc, rows = PASS, sorted(gpts.values(), key=lambda g: g["run_id"])
    scope = []
    for e, md in cells:
        cell = [g for g in rows if g.get("env") == e and g.get("mode") == md and g.get("fixture") not in RULE_FIXTURES.values()]
        if not cell:
            print(f"UNRUN 매트릭스 [{e}×{md}]: gpt-pass 행 없음")
            rc = max(rc, UNRUN)
        scope += cell
    for x in rfx:
        cell = [g for g in rows if g.get("fixture") == RULE_FIXTURES[x] and g.get("mode") == "review"]
        if not cell:
            print(f"UNRUN 규칙 fixture [{x}]: gpt-pass 행 없음")
            rc = max(rc, UNRUN)
        scope += cell
    if not scope:
        print("UNRUN: 대상 행 0 — 측정 실패를 먼저 의심한다")
        return UNRUN
    for g in scope:
        bad = verify_gpt_row(g, kinds)
        rc = max(rc, FAIL if bad else PASS)
        print(f"{'FAIL' if bad else 'PASS'} verify-evidence {g['run_id']}: " + ("; ".join(bad) if bad else f"{','.join(kinds)} 재판독 일치"))
    print(f"verify-evidence: {('PASS', 'FAIL', 'UNRUN')[rc]} (행 {len(scope)} · require={','.join(kinds)})")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(description="A/B 원장 — 수집·채점·판정 (exit 0 PASS · 1 FAIL · 2 UNRUN)")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--case", help="self-test 사례 하나만")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("snapshot", help="메모리·세션 상태 스냅샷 (arm×run 시작·종료, 기준 1회)")
    p.add_argument("--out", required=True)
    p.add_argument("--watch", action="append", default=[], help="이름=경로 (반복)")
    p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("input", help="run 시작 전 fixture 저장소 커밋 기록")
    p.add_argument("--root", required=True)
    p.add_argument("--fixture", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--plugin-root", required=True, help="이 run 이 --plugin-dir 로 쓸 플러그인 사본 — 시작 신원을 남긴다")
    p.add_argument("--plugin-source", required=True, help="사본의 원본 트리(B=FZ_BASE_TREE · C=FZ_TREE) — 사본 충실도를 대조한다")
    p.set_defaults(func=cmd_input)

    p = sub.add_parser("collect", help="run 1건을 원천에서 읽어 원장에 한 행 추가")
    p.add_argument("--ledger", required=True)
    p.add_argument("--workflow", required=True, choices=("fz-plan", "fz-review", "fz-peer-review"))
    p.add_argument("--arm", required=True)
    p.add_argument("--run", type=int, required=True)
    p.add_argument("--order", type=int, required=True, help="전역 실행 순서 — 교차 순서 판정 입력")
    p.add_argument("--phase", required=True)
    p.add_argument("--release")
    p.add_argument("--run-id")
    p.add_argument("--fixture", required=True)
    p.add_argument("--transcript", required=True, help="Lead transcript (.jsonl)")
    p.add_argument("--artifact", action="append", help="최종 산출물 (반복) — wall 끝점")
    p.add_argument("--input-root", help="fixture 저장소 (run 뒤 커밋을 읽는다)")
    p.add_argument("--input-json", required=True, help="`input` 이 run 전에 쓴 입력 신원(필수 — 없으면 입력을 증명 못 한다)")
    p.add_argument("--state-pristine", required=True)
    p.add_argument("--state-start", required=True)
    p.add_argument("--state-end", required=True)
    p.add_argument("--gpt-log", action="append", help="GPT 스트림 로그 (자동 탐지 외 추가)")
    p.add_argument("--gpt-log-dir", action="append", help="run 구간에 쓰인 *.stream.log 를 찾을 폴더 (반복)")
    p.add_argument("--evidence-dir", help="하네스 반환 사본 폴더 (기본: 원장 옆 evidence/)")
    p.add_argument("--tasks-dir", action="append", help="run 직후 복사한 하네스 tasks/*.output 폴더 (반복)")
    p.add_argument("--endpoint-clock", help="러너 끝점 시계 JSONL(docs/ab-endpoint-clock.md) — 있으면 끝점 = 러너 관측 시각 · mtime 은 교차 대조만")
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("recollect", help="기록된 원천에서 다시 수집 (계측기 버전이 바뀐 뒤) — 판정 필드 전후 차이 인쇄 · 악화면 exit 1")
    p.add_argument("--ledger", required=True)
    p.add_argument("--run-id")
    p.set_defaults(func=cmd_recollect)

    p = sub.add_parser("score", help="산출물을 라벨·채점표로 채점")
    p.add_argument("--ledger", required=True)
    p.add_argument("--fixtures-root", default=os.path.join(os.path.dirname(SCRIPT_DIR), "tests", "fixtures", "quality"))
    p.add_argument("--run-id")
    p.add_argument("--verdicts", help="blind-unpack 출력 (blinded=true)")
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("blind-pack", help="가린 검증자 꾸러미 — run_id·arm·경로를 지운 후보·계획 본문")
    p.add_argument("--ledger", required=True)
    p.add_argument("--fixtures-root", default=os.path.join(os.path.dirname(SCRIPT_DIR), "tests", "fixtures", "quality"))
    p.add_argument("--out", required=True)
    p.add_argument("--run-id", action="append")
    p.add_argument("--salt", help="anon id 소금(기본 무작위 — 재현 테스트에만 고정)")
    p.set_defaults(func=cmd_blind_pack)

    p = sub.add_parser("blind-unpack", help="검증자 판정(anon) → run_id 기준 판정 파일")
    p.add_argument("--pack", required=True)
    p.add_argument("--verdicts", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_blind_unpack)

    p = sub.add_parser("judge", help="판정")
    p.add_argument("--ledger", required=True)
    p.add_argument("--phase", choices=PHASES)
    p.add_argument("--workflows")
    p.add_argument("--workflow")
    p.add_argument("--arm", default="C")
    p.add_argument("--release")
    p.add_argument("--min-runs", type=int, default=2)
    p.add_argument("--runs", type=int, default=1, help="release-smoke 의 C run 수")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--effort", default=DEFAULT_EFFORT)
    p.add_argument("--require-complete", action="store_true", help="(항상 적용 — 명시용. 미완주 run 은 언제나 무효)")
    p.add_argument("--plugin-sha")
    p.add_argument("--verify-sources", help=",".join(SOURCE_KINDS))
    p.add_argument("--require", help=",".join(IMPLEMENTED))
    p.add_argument("--envs", help="S27 gpt-pass 매트릭스 환경(isolated,installed) — SC-1 · AC-2")
    p.add_argument("--fixtures-root", default=os.path.join(os.path.dirname(SCRIPT_DIR), "tests", "fixtures", "quality"))
    p.add_argument("--options-on", action="store_true", help="(미구현 — S28b)")
    p.add_argument("--require-passed", help="(미구현 — S28c)")
    p.add_argument("--formal", action="store_true",
                   help="정식 비교 — --verify-sources 필수 · 원장에 B 행이 있으면 --plugin-sha 필수(없으면 UNRUN exit 2)")
    p.set_defaults(func=cmd_judge)

    p = sub.add_parser("show", help="원장 요약")
    p.add_argument("--ledger", required=True)
    p.add_argument("--history", metavar="RUN_ID", help="그 run 의 행 이력 — 재측정(collect#n) · 재수집(recollect) · 옛 행(legacy)")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("collect-gpt", help="GPT 첫 패스(런처 한 호출분) → gpt-pass 행 (S27)")
    p.add_argument("--ledger", required=True)
    p.add_argument("--out", required=True, help="런처 출력 <stem>.json (옆에 .audit.json · .rollouts/)")
    p.add_argument("--run-id", required=True)
    p.add_argument("--env", required=True, choices=("isolated", "installed"))
    p.add_argument("--mode", required=True, choices=("plan", "review"))
    p.add_argument("--fixture", required=True)
    p.add_argument("--plugin-root", required=True, help="런처를 부른 플러그인 루트")
    p.add_argument("--input", action="append", help="이름=경로 — 감사 inputs 해시와 대조할 원본(반복)")
    p.add_argument("--lead-rules", help="Lead 규칙 레코드(rules.json — check_project_rules 통과본) — rules-compare")
    p.add_argument("--gpt-agents", action="store_true", help="런처를 --gpt-agents 로 불렀다(하위 에이전트 허용)")
    p.set_defaults(func=cmd_collect_gpt)

    p = sub.add_parser("verify-evidence", help="S27 두 번째 자 — gpt-pass 행의 원천 재판독 · 매트릭스 · 규칙 fixture 범위")
    p.add_argument("--ledger", required=True)
    p.add_argument("--envs")
    p.add_argument("--require", help=",".join(EVIDENCE_KINDS))
    p.add_argument("--matrix", help="env1,env2:x:mode1,mode2")
    p.add_argument("--rule-fixtures", help=",".join(sorted(RULE_FIXTURES)))
    p.set_defaults(func=cmd_verify_evidence)

    a, extra = ap.parse_known_args()
    if extra:
        ap.error(f"모르는 인자 {extra}")
    if a.self_test:
        import ab_ledger_selftest   # ⛔ self-test 일 때만 싣는다 — 실행 경로에 들이면 지문 밖 코드가 판정에 섞인다
        return ab_ledger_selftest.self_test(a.case)
    if not getattr(a, "func", None):
        ap.print_help()
        return UNRUN
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
