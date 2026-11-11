#!/usr/bin/env python3
"""A/B 계측기 결함 주입 러너 (S14) — 원천 입력 칸을 하나씩 지우거나 깨뜨려도 계측기가 다른 측정을 조용히 유효로 내지 않는지 잰다.

두 단계 — collect(run 원천) · gpt(런처 첫 패스 원천 · collect-gpt).
collect 단계: mini-ledger fixture 의 B1(유효 기준선)을 B2 와 함께 수집해 통합 테스트와 같은 judge(원천 재판독 포함)로 판정한다.
B1 collect 가 실제로 연 원천(open 기록 — 손으로 고른 목록이 아니다)마다 파일 · 줄 · 키 경로를 걸으며 연산을 하나씩 건다:
  delete-file · empty-file · drop-line · break-line · insert-broken(JSONL) · del-key · flip(형 뒤집기)
  ⛔ 형식이 없는 자유 텍스트(산출물 본문 · 작업 출력 로그)는 지우기 · 비우기만 건다 — 자른 본문은 형식 위반이 아니라 다른 내용이다
  ⛔ 단 계측기가 줄로 읽는 텍스트(TEXT_PARSED — GPT 스트림 로그 배너)는 줄 빼기 · 줄 자르기(cut-line)도 건다 — 행이 바뀌면 실패다
  통째 JSON 은 반쪽 자르기(break-file)도 건다
변이 뒤 B1 만 다시 collect 해 judge 하고 결과를 가른다:
  excluded       B1 이 유효 목록에서 빠졌다(미완주 · 무효 · collect 거부) — 정상
  valid-same     B1 이 유효이고 행이 깨끗한 행과 같다 — 그 칸은 측정에 닿지 않는다
  valid-same-corrupt  못 읽게 만든 줄(break-line · insert-broken)인데 B1 이 유효하다 — 못 읽은 줄에 무엇이 있었는지 모른다(행이 같아도 실패)
  valid-changed  B1 이 유효인데 행이 다르다 — 빠지거나 깨진 칸을 기본값으로 메운 다른 측정(fail-open)
  crash-*        예외 — collect · judge 가 판정 없이 죽었다
gpt 단계: 런처 한 호출분(출력 · 감사 · rollout · 입력 diff)과 검증 트리 → collect-gpt 와 같은 행 → judge_gpt(SC-1 · AC-2, isolated).
깨끗한 plan 셀 행은 고정하고 review 셀 원천을 변이시킨다 — review 셀이 PASS 로 남으면 위와 같이 가른다.
  limit          실제 정상 로그에도 있는 꼴이라 계측기가 가를 수 없는 변이(아래 표 · 근거 수치) — 실패로 세지 않고 따로 인쇄한다
⛔ 통과 = valid-changed 0 · valid-same-corrupt 0 · crash 0. 깨끗한 B1 이 유효가 아니면 측정 불가(exit 2).
한계(limit)는 둘뿐이다 — ① 줄째 삭제: 지운 줄에 uuid 가 없거나(백그라운드 세션 워커 로그 · queue-operation 등) 그 uuid 를 부모로 잇는
뒤 줄이 없다(사슬 끝) — 판정은 지운 줄을 보고 기계로 한다 ② LIMIT_KEYS 의 키 삭제 셋 — 실측 근거를 표에 적는다.

usage: faults.py --out TSV [--kinds REGEX] [--stages collect,gpt]
출력 TSV: 1행 `# instrument_sha=<지문>` · 2행 머리 kind · path · op · result · count — 원천 본문은 쓰지 않는다.
exit: 0 = 실패 칸 0 · 1 = 남음 · 2 = 측정 불가
"""
import argparse
import builtins
import calendar
import collections
import contextlib
import copy
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(os.path.dirname(HERE))
FIX = os.path.join(PLUGIN, "tests", "fixtures", "ab", "mini-ledger")
BUILD = os.path.join(PLUGIN, "tests", "fixtures", "quality", "_lib", "build_repo.sh")
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))
GIT_ENV = {"GIT_AUTHOR_NAME": "fixture", "GIT_COMMITTER_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
           "GIT_COMMITTER_EMAIL": "fixture@example.invalid", "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
           "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"}
RID, PEER = "B1", "B2"
CORRUPT = ("break-line", "insert-broken", "break-file")
TEXT_PARSED = re.compile(r"\.stream\.log$")   # parse_gpt_log 가 줄마다 배너를 읽는다
BAD = ("valid-changed", "valid-same-corrupt", "crash")
# 실제 정상 로그에도 그 칸이 없는 꼴이 있다 — 빠진 것과 원래 없는 것을 가를 수 없다(실측: ~/.claude 워커 3,151파일 · Lead 80개)
LIMIT_KEYS = {
    ("del-key", "L:assistant.message.stop_reason"): "stop-less: stop 없는 응답이 실제로 있다(워커 107파일 · 2,797건)",
    ("del-key", "L:queue-operation.content"): "enqueue-no-content: content 없는 enqueue 가 실제로 있다(825건 중 119건)",
    ("del-key", "L:attachment.attachment.files.[]"): "instructions-files: 주입 파일 수가 run 마다 다르다(166건 · 1·2·3개 = 22·21·123)",
}
_open = builtins.open


def sh(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, timeout=300, **kw)


def epoch(iso):
    return calendar.timegm(time.strptime(iso.split(".")[0].replace("Z", ""), "%Y-%m-%dT%H:%M:%S"))


def paths(o, pre=()):
    if isinstance(o, dict):
        for k, v in o.items():
            yield pre + (k,)
            yield from paths(v, pre + (k,))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield pre + (i,)
            yield from paths(v, pre + (i,))


def flip(v):
    """같은 자리에 다른 형의 값 — 문자열은 수, 수 · 참거짓은 문자열, 목록은 dict, dict 는 문자열."""
    if isinstance(v, str):
        return 7
    if isinstance(v, list):
        return {"x": 1}
    if isinstance(v, (bool, int, float, dict)):
        return "x"
    return {"x": 1}


def generic(p):
    return ".".join("[]" if isinstance(x, int) else str(x) for x in p)


def mutations(raw, text_lines=False):
    """원천 한 파일의 변이 (path, op, 새 바이트 | None=파일 삭제, 한계 사유 | None). JSONL 은 줄 연산 + 줄마다 키 경로, JSON 은 키 경로 +
    반쪽 자르기, 줄로 읽는 텍스트(text_lines)는 줄 빼기 · 줄 자르기."""
    yield "", "delete-file", None, None
    yield "", "empty-file", b"", None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return
    lines = text.split("\n")
    objs = []
    for ln in lines:
        try:
            objs.append(json.loads(ln) if ln.strip() else None)
        except ValueError:
            objs.append(False)
    if not any(isinstance(o, (dict, list)) for o in objs):
        try:
            whole = json.loads(text)
        except ValueError:
            whole = None
        if not isinstance(whole, (dict, list)):
            for i in range(len(lines)) if text_lines else ():   # 줄로 읽는 텍스트 — 읽지 않는 줄이면 같은 행이 맞다
                yield "T:line", "drop-line", "\n".join(lines[:i] + lines[i + 1:]).encode(), None
                yield "T:line", "cut-line", "\n".join(lines[:i] + [lines[i][: len(lines[i]) // 2]] + lines[i + 1:]).encode(), None
            return                                   # 자유 텍스트 — 형식이 없다
        yield "", "break-file", raw[: len(raw) // 2], None
        for p in list(paths(whole)):
            for op in ("del-key", "flip"):
                o = copy.deepcopy(whole)
                par = o
                for x in p[:-1]:
                    par = par[x]
                if op == "del-key":
                    par.pop(p[-1])
                else:
                    par[p[-1]] = flip(par[p[-1]])
                yield generic(p), op, json.dumps(o, ensure_ascii=False).encode(), None
        return
    linked = {x.get("parentUuid") for x in objs if isinstance(x, dict)}
    for i, o in enumerate(objs):
        if not isinstance(o, (dict, list)):
            continue
        tag = "L:" + (str(o.get("type")) if isinstance(o, dict) else "list")
        uid = o.get("uuid") if isinstance(o, dict) else None
        drop_limit = ("no-uuid: 지운 줄에 uuid 가 없다 — 사슬로 빠짐을 볼 수 없다" if not uid
                      else None if uid in linked else "chain-tail: 지운 줄을 잇는 뒤 줄이 없다(사슬 끝)")
        for op in ("drop-line", "break-line", "insert-broken"):
            ls = list(lines)
            if op == "drop-line":
                ls.pop(i)
            elif op == "break-line":
                ls[i] = ls[i][: max(1, len(ls[i]) // 2)]
            else:
                ls.insert(i + 1, ls[i][: max(1, len(ls[i]) // 2)])
            yield tag, op, "\n".join(ls).encode(), (drop_limit if op == "drop-line" else None)
        for p in list(paths(o)):
            for op in ("del-key", "flip"):
                oo = copy.deepcopy(o)
                par = oo
                for x in p[:-1]:
                    par = par[x]
                if op == "del-key":
                    par.pop(p[-1])
                else:
                    par[p[-1]] = flip(par[p[-1]])
                ls = list(lines)
                ls[i] = json.dumps(oo, ensure_ascii=False)
                yield tag + "." + generic(p), op, "\n".join(ls).encode(), LIMIT_KEYS.get((op, tag + "." + generic(p)))


class CollectStage:
    """mini-ledger B2 + B1 → judge. B1 원천을 변이시키고 B1 만 다시 collect 한다."""

    def __init__(self, work):
        self.work = work
        fx = self.fx = os.path.join(work, "fx")
        shutil.copytree(FIX, fx)
        spec0 = json.load(_open(os.path.join(fx, "runs.json"), encoding="utf-8"))
        table = {}
        for r in spec0["runs"]:
            if r["run_id"] in (RID, PEER):
                d = os.path.join(work, "inputs", r["run_id"], "repo")
                os.makedirs(os.path.dirname(d))
                if sh(["bash", BUILD, os.path.join(fx, "input"), d]).returncode != 0:
                    raise RuntimeError("입력 저장소 복원 실패")
                table[r["input"]] = d
        env = dict(os.environ, **GIT_ENV)
        for stub in ("plugin", "plugin-c"):
            p = os.path.join(fx, stub)
            for c in (["git", "-C", p, "init", "-q"], ["git", "-C", p, "add", "-A"],
                      ["git", "-C", p, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "stub"]):
                if sh(c, env=env).returncode != 0:
                    raise RuntimeError("플러그인 스텁 git 실패")
        psha = sh(["git", "-C", os.path.join(fx, "plugin"), "rev-parse", "HEAD"]).stdout.strip()
        self.ledger = ledger = os.path.join(work, "ab", "ledger.jsonl")
        table.update({"@FIX@": fx, "@PLUGIN_C@": os.path.join(fx, "plugin-c"), "@PLUGIN@": os.path.join(fx, "plugin"),
                      "@WORK@": work, "@LEDGER@": ledger, "@PLUGIN_SHA@": psha})

        def subst(t):
            for k, v in table.items():
                t = t.replace(k, v)
            return t
        for root, _, files in os.walk(os.path.join(fx, "raw")):
            for f in files:
                p = os.path.join(root, f)
                t = subst(_open(p, encoding="utf-8").read())   # ⛔ 읽은 뒤 연다 — open(p, "w") 가 먼저 파일을 비운다
                with _open(p, "w", encoding="utf-8") as fh:
                    fh.write(t)
        spec = json.loads(subst(_open(os.path.join(fx, "runs.json"), encoding="utf-8").read()))
        for path, iso in spec["mtimes"].items():
            if os.path.exists(path):
                os.utime(path, (epoch(iso), epoch(iso)))
        os.makedirs(os.path.dirname(ledger), exist_ok=True)
        self.args = {}
        for run in spec["runs"]:
            if run["run_id"] not in (RID, PEER):
                continue
            ij = os.path.join(work, "inputs", run["run_id"], "input.json")
            rc, out = self.cli("input", "--root", run["input"], "--fixture", run["fixture"], "--plugin-root", run["plugin"],
                               "--plugin-source", run["plugin"], "--out", ij)
            if rc != 0:
                raise RuntimeError(f"input {run['run_id']} exit {rc}")
            a = ["collect", "--ledger", ledger, "--run-id", run["run_id"], "--input-json", ij]
            for k in ("workflow", "arm", "run", "order", "phase", "release", "fixture", "transcript", "state_pristine",
                      "state_start", "state_end", "evidence_dir"):
                if run.get(k) is not None:
                    a += ["--" + k.replace("_", "-"), str(run[k])]
            for x in run["artifact"]:
                a += ["--artifact", x]
            self.args[run["run_id"]] = a
        rc, out = self.cli(*self.args[PEER])
        if rc != 0:
            raise RuntimeError(f"collect {PEER} exit {rc}")
        self.evid = os.path.join(work, "evidence")
        self.snap = os.path.join(work, "snap")
        os.makedirs(self.snap)
        shutil.copyfile(ledger, os.path.join(self.snap, "ledger"))
        if os.path.isdir(self.evid):
            shutil.copytree(self.evid, os.path.join(self.snap, "evidence"))
        self.judge = ["judge", "--ledger", ledger, "--phase", "baseline", "--workflows", "fz-review", "--model", "claude-opus-5-5",
                      "--effort", "xhigh", "--require-complete", "--plugin-sha", psha,
                      "--verify-sources", "transcript,wf-metrics,start-state,input-hash,instrument-sha", "--min-runs", "2"]
        self.t_collect = self.t_judge = 0.0
        self.n = 0

    @staticmethod
    def cli(*argv):
        import ab_ledger
        buf, old = io.StringIO(), sys.argv
        sys.argv = ["ab_ledger.py", *argv]
        try:
            with contextlib.redirect_stdout(buf):
                rc = ab_ledger.main()
        finally:
            sys.argv = old
        return rc, buf.getvalue()

    def _reset(self):
        shutil.copyfile(os.path.join(self.snap, "ledger"), self.ledger)
        shutil.rmtree(self.evid, ignore_errors=True)
        if os.path.isdir(os.path.join(self.snap, "evidence")):
            shutil.copytree(os.path.join(self.snap, "evidence"), self.evid)

    def _row(self):
        rows = [json.loads(x) for x in _open(self.ledger, encoding="utf-8") if x.strip()]
        r = [x for x in rows if x.get("type") == "run" and x.get("run_id") == RID]
        return r[-1] if r else None

    def verdict(self, record=None):
        """(결과, 행 지문) — 결과 excluded · valid · crash-*. record 가 주어지면 B1 collect 가 연 원천 경로를 담는다."""
        self._reset()
        t0 = time.time()
        if record is not None:
            def rec_open(f, *a, **k):
                if isinstance(f, (str, bytes, os.PathLike)):
                    fp = os.path.abspath(os.fsdecode(f))
                    mode = a[0] if a else k.get("mode", "r")
                    if fp.startswith(self.work) and "r" in mode and "+" not in mode and fp not in record:
                        record.append(fp)
                return _open(f, *a, **k)
            builtins.open = rec_open
        try:
            rc, out = self.cli(*self.args[RID])
        except Exception as e:   # noqa: BLE001 — collect 가 죽으면 행이 없다
            return "crash-collect:" + type(e).__name__, None
        finally:
            builtins.open = _open
        self.t_collect += time.time() - t0
        row = self._row()
        if rc != 0 or row is None:
            return "excluded", None                  # collect 가 행을 거부했다
        t1 = time.time()
        try:
            rc, jout = self.cli(*self.judge)
        except Exception as e:   # noqa: BLE001
            return "crash-judge:" + type(e).__name__, None
        self.t_judge += time.time() - t1
        self.n += 1
        m = re.search(r"baseline-runs fz-review\[review-mini\]: 유효 \d+/\d+ \(필요 \d+\)(?: — (.*))?", jout)
        if m is None:
            return "crash-judge:no-line", None
        valid = [x.strip() for x in (m.group(1) or "").split(",") if x.strip()]
        if RID not in valid:
            return "excluded", None
        row = {k: v for k, v in row.items() if k not in ("collected_at",)}
        return "valid", json.dumps(row, sort_keys=True, ensure_ascii=False, default=str)

    def kind(self, fp):
        rel = os.path.relpath(fp, self.work).replace("fx/raw/", "").replace(f"inputs/{RID}/", "")
        rel = re.sub(r"agent-[^/]*?(\.meta)?\.json", lambda m: "agent-*" + (m.group(1) or "") + ".json", rel)
        return re.sub(r"(?<![A-Za-z])(?:b1|bb1|wb1|wf_b1)(?![A-Za-z0-9])", "*", rel)


class GptStage:
    """런처 한 호출분 → gpt-pass 행(build_gpt_row — collect-gpt 와 같은 함수 · 같은 예외 정책) → judge_gpt. review 원천만 변이시킨다."""

    def __init__(self, work):
        import hashlib
        self.work = work
        self.tree = os.path.join(work, "tree")
        os.makedirs(os.path.join(self.tree, "gpt-skills", "fz-reviewer"))
        with _open(os.path.join(self.tree, "gpt-skills", "fz-reviewer", "SKILL.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nname: fz-reviewer\n---\nBODY-OF-REVIEWER\n")
        self.args = {m: self._run(os.path.join(work, "run-" + m), m, hashlib) for m in ("plan", "review")}
        self.t_collect = self.t_judge = 0.0
        self.n = 0

    def _run(self, run, mode, hashlib):
        iso = "/private/tmp/fz-gpt-iso.T/gpt-home/skills"
        os.makedirs(os.path.join(run, "g.rollouts"))
        diff = os.path.join(run, "diff.patch")
        with _open(diff, "w", encoding="utf-8") as fh:
            fh.write("diff\n")
        with _open(os.path.join(run, "g.audit.json"), "w", encoding="utf-8") as fh:
            json.dump({"mode": mode, "exit": 0, "note": "ok", "timedOut": False, "isolationApplied": True, "spawnAgent": 0, "hits": [],
                       "inputs": {"diff.patch": hashlib.sha256(_open(diff, "rb").read()).hexdigest()},
                       "toolCalls": 1, "rollouts": 1, "turnContexts": 1, "wrapperExit": 0}, fh)
        with _open(os.path.join(run, "g.json"), "w", encoding="utf-8") as fh:
            json.dump({"verdict": "approved", "issues": [], "craft": [], "axis_coverage": [],
                       "projectRules": {"rules": [], "conflicts": [], "gaps": []}}, fh)
        host = "\n## Skills\n### Skill roots\n- `r0` = `" + iso + "`\n### Available\n- fz-reviewer: d (r0/fz-reviewer/SKILL.md)\n"
        evs = [{"type": "session_meta", "payload": {"id": "s1"}},
               {"type": "world_state", "payload": {"state": {"host_skills": {"body": host}}}},
               {"type": "turn_context", "payload": {"model": "gpt-6-sol"}},
               {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [
                   {"type": "input_text", "text": f"[fz-gpt-skill-injected] fz-reviewer ({iso}/fz-reviewer) — 본문\n"
                                                  "---\nname: fz-reviewer\n---\nBODY-OF-REVIEWER\n"}]}},
               {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec",
                                                     "input": f'tools.exec_command({{cmd:"cat {iso}/fz-reviewer/references/domain-ios.md"}})'}}]
        with _open(os.path.join(run, "g.rollouts", "r.jsonl"), "w", encoding="utf-8") as fh:
            fh.write("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in evs))
        return {"out": os.path.join(run, "g.json"), "run_id": f"t:isolated:{mode}", "env": "isolated", "mode": mode,
                "fixture": "review-ios-ribs", "plugin_root": self.tree, "inputs": {"diff.patch": diff}, "lead_rules": None,
                "gpt_agents": False}

    def _row(self, mode):
        from ab_ledger_gpt import build_gpt_row
        try:   # cmd_collect_gpt 와 같은 정책 — 예외 · 직렬화 실패는 행 없음(UNRUN)
            row = build_gpt_row(self.args[mode], self.tree)
            json.dumps(row, ensure_ascii=False, sort_keys=True)
            return row
        except Exception:   # noqa: BLE001
            return None

    def verdict(self, record=None):
        from ab_ledger_gpt import judge_gpt
        t0 = time.time()
        if record is not None:
            def rec_open(f, *a, **k):
                if isinstance(f, (str, bytes, os.PathLike)):
                    fp = os.path.abspath(os.fsdecode(f))
                    if fp.startswith(os.path.join(self.work, "run-review")) and fp not in record:
                        record.append(fp)
                return _open(f, *a, **k)
            builtins.open = rec_open
        try:
            row = self._row("review")
        finally:
            builtins.open = _open
        self.t_collect += time.time() - t0
        if row is None:
            return "excluded", None
        plan = self._row("plan")
        t1 = time.time()
        try:
            rc, out = judge_gpt({"p": plan, "r": row}, ["SC-1", "AC-2"], ["isolated"], self.work)
        except Exception as e:   # noqa: BLE001
            return "crash-judge:" + type(e).__name__, None
        self.t_judge += time.time() - t1
        self.n += 1
        ok = any(x.startswith("PASS SC-1 [isolated×review]") for x in out) and any(x.startswith("PASS AC-2") for x in out)
        if not ok:
            return "excluded", None
        return "valid", json.dumps(row, sort_keys=True, ensure_ascii=False, default=str)

    def kind(self, fp):
        return "gpt:" + os.path.relpath(fp, os.path.join(self.work, "run-review"))


def run_stage(stage, kinds_re, rows, limits):
    reads = []
    v0, p0 = stage.verdict(record=reads)
    v1, p1 = stage.verdict()
    if v0 != "valid" or p0 != p1:
        print(f"UNRUN: 깨끗한 {RID} 가 유효가 아니거나 재수집이 다르다 ({v0} · {v1} · same={p0 == p1})")
        return False
    reads = [r for r in reads if os.path.isfile(r) and r != getattr(stage, "ledger", None)]   # 원장은 collect 의 출력이다(순번을 읽는다) — 원천이 아니다
    print(f"원천 {len(reads)}개: " + " · ".join(sorted({stage.kind(r) for r in reads})))
    for fp in reads:
        kind = stage.kind(fp)
        if kinds_re and not re.search(kinds_re, kind):
            continue
        st = os.stat(fp)
        raw = _open(fp, "rb").read()

        def put(b):
            with _open(fp, "wb") as fh:
                fh.write(b)
            os.utime(fp, (st.st_atime, st.st_mtime))   # 내용만 바꾼다 — mtime 은 깨끗한 값
        try:
            for path, op, b, lim in mutations(raw, bool(TEXT_PARSED.search(fp))):
                if b is None:
                    os.remove(fp)
                else:
                    put(b)
                v, p = stage.verdict()
                put(raw)
                if v == "valid":
                    v = "valid-changed" if p != p0 else ("valid-same-corrupt" if op in CORRUPT else "valid-same")
                if lim and v.startswith(BAD[:2]):
                    v = "limit:" + lim.split(":")[0]
                    limits[v] = lim
                rows[(kind, path, op, v)] += 1
        finally:
            put(raw)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--kinds", help="이 정규식에 맞는 원천 종류만(재실행용) — 생략하면 전부")
    ap.add_argument("--stages", default="collect,gpt")
    a = ap.parse_args()
    if shutil.which("git") is None:
        print("UNRUN: git 없음")
        return 2
    from ab_ledger_base import instrument_sha
    sha = instrument_sha()
    work = tempfile.mkdtemp(prefix="ab-faults-")
    rows, limits = collections.Counter(), {}
    try:
        for name in [x for x in a.stages.split(",") if x]:
            sub = os.path.join(work, name)
            os.makedirs(sub)
            stage = {"collect": CollectStage, "gpt": GptStage}[name](sub)
            if not run_stage(stage, a.kinds, rows, limits):
                return 2
            if stage.n:
                print(f"[{name}] 변이당 collect {stage.t_collect / stage.n:.2f}s · judge {stage.t_judge / stage.n:.2f}s · {stage.n}건")
    finally:
        builtins.open = _open
        shutil.rmtree(work, ignore_errors=True)
    if instrument_sha() != sha:
        print("UNRUN: 측정 중 계측기가 바뀌었다")
        return 2
    agg = collections.Counter()
    for (kind, path, op, res), n in rows.items():
        agg[res.split(":")[0]] += n
    with _open(a.out, "w", encoding="utf-8") as fh:
        fh.write(f"# instrument_sha={sha}\n")
        fh.write("kind\tpath\top\tresult\tcount\n")
        for (kind, path, op, res), n in sorted(rows.items()):
            fh.write(f"{kind}\t{path}\t{op}\t{res}\t{n}\n")
    bad = sorted({(k, p, o, r) for (k, p, o, r) in rows if r.startswith(BAD)})
    print("합계 " + " · ".join(f"{k} {v}" for k, v in sorted(agg.items())))
    for k, why in sorted(limits.items()):
        print(f"  한계 {sum(n for (_k, _p, _o, r), n in rows.items() if r == k)}건 — {why}")
    for k, p, o, r in bad[:60]:
        print(f"  {r:16} {o:13} {k}  {p}")
    if len(bad) > 60:
        print(f"  …외 {len(bad) - 60}자리")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
