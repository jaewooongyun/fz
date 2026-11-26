#!/bin/bash
# A/B 수집기 재생 — 번들 합성 셀 5종 (F-361 · F-335 ⑨⑩⑪). health-check 글롭(tests/fixtures/*/*/run.sh)에서 인자 없이 돈다.
#
# 셀마다 실측 결함의 모양을 그대로 본뜬 합성 transcript · 산출물 · GPT 로그를 임시 폴더에 만들고, 대상 트리의
# scripts/ab_ledger.py 로 parse_transcript(import) 또는 collect · recollect(CLI)를 돌린다. 입력은 이 파일 안에만 있다.
#   fstring-argv    2-run 묶음 run 1 ① — `python3 $W/render_plan.py $W final` 이 `open(f'{W}/plan-{ver}.md','w')` 로 썼다
#                   → 끝점 = 그 호출 · 다른 argv 값의 산출물(plan-v3.md)은 그 호출이 쓴 것이 아니다
#   moved-gpt-log   2-run 묶음 run 1 ② — 1라운드 뒤 `mv $W/$f.json.stream.log $W/$f.r1.json.stream.log` → 배너 4/4 · 미연결 0
#   lost-script     18-run 묶음 C2 plan-feature — 같은 명령의 heredoc 으로 만들고 부른 스크립트가 재수집 전에 사라졌다
#                   → recollect 가 끝점을 지키고(changed=0 · exit 0), 끝점 heredoc 을 지운 악화 주입에는 차이 · 이유 + exit 1
#   heredoc-versions 같은 경로 heredoc 두 벌 — 사이 호출은 첫 본문, 뒤 호출은 둘째 본문 · 디스크에 있으면 디스크 본문
#   multi-gpt-call  한 명령의 GPT 호출 둘(⑪) → calls 2 · 배너 2/2 + 행 모양: lead.tool_errors 만(⑩ retries 별칭 없음) ·
#                   sources.plugin_roots(⑨ 플러그인 사본)
#   archive-no-secret F-423 — 격리 GPT 홈에 auth.json · 토큰 설정 · 비밀 이름 세션 파일이 있어도 증거 폴더 어디에도 그 이름 · 가짜
#                   비밀값이 없다 · 양성 대조: 허용 목록(sessions/**/*.jsonl)의 rollout 은 사본이 있고 행 gpt.sessions = 1
#   archive-replay  F-423 — 실측 run 폴더 모양(input.json · start.json · end.json · gpt-home · tasks · plugin 사본)으로 collect 한 뒤
#                   원래 plugin · gpt-home · tasks · start.json · end.json · pristine 을 지우고 보관본만으로 재구성(dry) · recollect 한다
#                   → 판정 필드(VERIFY_FIELDS · complete.why · gpt.sessions · invisible · plugin 변경 표지)가 저장 행 = 원래 자리 재구성 =
#                   보관본 단독 재구성 = 원래 경로를 가리키는 옛 행 보기의 재구성 · recollect exit 0 · changed=0 · dry(옛 행 보기는
#                   빈 증거 폴더를 만들지 않는다)와 원천 없는 recollect 는 증거 폴더를 바꾸지 않는다 · 원천 범위(source_scope)에
#                   사라진 원천 0 · 보관 종류 여섯 · 플러그인 루트는 원래 자리로 세지 않는다.
#                   지운 원천마다 판정 필드가 움직인다(state.* · complete.why · gpt.ok · failed · models · versions · plugin.roots)
#   archive-remeasure F-423 — 같은 run_id 재측정 사이 rollout 을 바꾸고 작업 출력을 지우면, 사본이 원천과 같아져(앞 측정 파일이 남지
#                   않는다) gpt.sessions = 1 · 앞 측정 model 없음 · gpt.ok = 0 · 행 = 사본 재구성
# 보관 증거(두 묶음 18 · 2 run) 재생은 같은 폴더 external.sh 다 — 외부 원천이 필요해 게이트에서만 부른다.
# 출력: 셀마다 `PASS|FAIL <셀>: …` · 요약 줄 `COLLECTOR-REPLAY-OK 8/8` 또는 `COLLECTOR-REPLAY-FAIL <통과>/8 — <셀>` ·
#   끝 줄 `CELLS n=<수> ran=<…>`. ⛔ 셀 집합 대조(F-408): 돈 셀 이름이 `EXPECTED_CELLS`(위 8종 · 순서까지)와 다르면 FAIL(exit 1)
# exit: 0 8/8 · 1 셀 단언 실패 · 2 UNRUN(python3 · 대상 계측기 부재) · 3 준비 실패(인자 · 임시 폴더 · git · 셀 안 예외)
#   ⛔ 셀 안 예외를 1 로 내면 '기준 트리 exit 1' 게이트가 결함 재현 없이 통과한다 — 그래서 3 이다
# usage: run.sh [--tree <플러그인 루트>]   (기본: 이 파일이 든 트리)
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
command -v python3 >/dev/null 2>&1 || { echo "UNRUN: python3 없음"; exit 2; }
[ -f "$R/scripts/ab_ledger.py" ] || { echo "UNRUN: 대상 계측기 없음 $R/scripts/ab_ledger.py"; exit 2; }
# ⛔ mktemp 결과를 따로 받는다 — 치환을 바로 cd 에 넘기면 실패해도 `cd ""` 가 성공한다(F-355)
T0="$(mktemp -d "${TMPDIR:-/tmp}/fz-collector-replay.XXXXXX")" || { echo "SETUP mktemp 실패"; exit 3; }
trap 'rm -rf "${T0:?}"' EXIT
TD="$(cd "$T0" && pwd -P)" || { echo "SETUP 임시 폴더 정규화 실패: $T0"; exit 3; }

PYTHONDONTWRITEBYTECODE=1 python3 -I - "$R" "$TD" <<'PY'
import datetime
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import traceback

sys.dont_write_bytecode = True   # ⛔ 대상 트리(기준 clone 포함)의 scripts/ 에 __pycache__ 를 쓰지 않는다
TREE, TD = sys.argv[1], sys.argv[2]
AB = os.path.join(TREE, "scripts", "ab_ledger.py")
T0 = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)


class Setup(Exception):
    pass


def at(i, s=0):
    return T0 + datetime.timedelta(minutes=i, seconds=s)


def z(t):
    return t.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def epoch(v):
    return datetime.datetime.fromisoformat(v).timestamp() if isinstance(v, str) else None


def put(path, text, when=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    if when is not None:
        os.utime(path, (when.timestamp(), when.timestamp()))
    return path


def transcript(path, cwd, steps, extra=()):
    """첫 사람 발화(0분) + Bash 호출 i(i분 0초) · 결과(i분 5초). steps = [(명령, 결과 본문)]."""
    evs = [{"type": "user", "timestamp": z(at(0)), "cwd": cwd, "message": {"role": "user", "content": "/fz:fz-plan ABT-1"}}]
    evs += list(extra)
    for i, (cmd, text) in enumerate(steps, 1):
        evs.append({"type": "assistant", "timestamp": z(at(i)), "cwd": cwd, "effort": "xhigh",
                    "message": {"id": f"m{i}", "model": "claude-opus-5-5", "stop_reason": "tool_use", "usage": {"output_tokens": 10},
                                "content": [{"type": "tool_use", "id": f"t{i}", "name": "Bash", "input": {"command": cmd}}]}})
        evs.append({"type": "user", "timestamp": z(at(i, 5)), "cwd": cwd,
                    "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"t{i}", "content": text}]}})
    put(path, "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in evs))
    return path


def banner(session):
    return ("OpenAI GPT-CLI v0.157.0\n--------\nworkdir: /w\nmodel: gpt-6-sol\nprovider: openai\n"
            f"reasoning effort: xhigh\nsession id: {session}\n--------\nuser\n(합성)\n")


def load():
    sp = importlib.util.spec_from_file_location("abl_target", AB)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def collect(d, tp, artifacts=(), gpt_log_dir=None):
    led = os.path.join(d, "ledger.jsonl")
    cmd = ["python3", "-B", AB, "collect", "--ledger", led, "--workflow", "fz-plan", "--arm", "C", "--run", "1", "--order", "1",
           "--phase", "change", "--run-id", "replay", "--fixture", "plan-feature", "--transcript", tp,
           "--input-json", os.path.join(d, "input.json"), "--state-pristine", os.path.join(d, "pristine.json"),
           "--state-start", os.path.join(d, "start.json"), "--state-end", os.path.join(d, "end.json")]
    for a in artifacts:
        cmd += ["--artifact", a]
    if gpt_log_dir:
        cmd += ["--gpt-log-dir", gpt_log_dir]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise Setup(f"collect exit {r.returncode}: {(r.stdout + r.stderr)[-300:]}")
    return led, last_row(led)


def last_row(led):
    rows = [json.loads(x) for x in open(led, encoding="utf-8") if x.strip()]
    return [r for r in rows if r.get("type") == "run"][-1]


def recollect(led):
    r = subprocess.run(["python3", "-B", AB, "recollect", "--ledger", led], capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout + r.stderr


def gp(row, *ks):
    o = row
    for k in ks:
        o = o.get(k) if isinstance(o, dict) else None
    return o


def cell_fstring_argv(m):
    d = os.path.join(TD, "fstring-argv")
    W = os.path.join(d, "plan")
    body = "import sys\nW, ver = sys.argv[1], sys.argv[2]\nopen(f'{W}/plan-{ver}.md', 'w').write('# plan\\n')\n"
    put(os.path.join(W, "render_plan.py"), body)   # 실측(2-run 묶음)과 같이 스크립트는 디스크에 있다
    tp = transcript(os.path.join(d, "t.jsonl"), d, [
        (f"W={W}; cat > $W/render_plan.py <<'PYEOF'\n{body}PYEOF", ""),
        (f"W={W}; python3 $W/render_plan.py $W final && wc -l $W/plan-final.md", f"1 {W}/plan-final.md")])
    final = put(os.path.join(W, "plan-final.md"), "# plan\n", at(2, 5))
    other = put(os.path.join(W, "plan-v3.md"), "# v3\n", at(2, 5))
    got = [epoch(x.get("write")) for x in m.parse_transcript(tp, [final, other])["artifacts"]]
    ok = got == [at(2, 5).timestamp(), None]
    return ok, f"끝점 plan-final={got[0]} (기대 {at(2, 5).timestamp()}) · plan-v3={got[1]} (기대 None — 다른 argv 값)"


def cell_moved_gpt_log(m):
    d = os.path.join(TD, "moved-gpt-log")
    W = os.path.join(d, "plan")
    g = lambda n: f"/fz/scripts/gpt-exec.sh exec --cd {d} --out {W}/{n}.json --prompt-file {W}/p.md"
    steps = [(g("gpt-verify"), "GATE-PASS"), (g("gpt-verify-gates"), "GATE-PASS"),
             (f"W={W}; for f in gpt-verify gpt-verify-gates; do mv $W/$f.json.stream.log $W/$f.r1.json.stream.log; done", ""),
             (g("gpt-verify"), "GATE-PASS"), (g("gpt-verify-gates"), "GATE-PASS")]
    tp = transcript(os.path.join(d, "t.jsonl"), d, steps)
    for n, i in (("gpt-verify.r1", 1), ("gpt-verify-gates.r1", 2), ("gpt-verify", 4), ("gpt-verify-gates", 5)):
        put(os.path.join(W, f"{n}.json.stream.log"), banner(f"0199a000-0000-7000-8000-00000000000{i}"), at(i, 3))
    for n in ("gpt-verify", "gpt-verify-gates"):
        put(os.path.join(W, f"{n}.json"), '{"verdict": "pass"}\n', at(5, 4))
    _, row = collect(d, tp, gpt_log_dir=W)
    g_ = row.get("gpt") or {}
    ok = (g_.get("calls"), g_.get("ok"), g_.get("banners"), g_.get("unlinked")) == (4, 4, 4, 0)
    return ok, f"gpt calls={g_.get('calls')} ok={g_.get('ok')} banners={g_.get('banners')} unlinked={g_.get('unlinked')} (기대 4·4·4·0)"


def cell_lost_script(m):
    d = os.path.join(TD, "lost-script")
    W = os.path.join(d, "plan")
    fix = os.path.join(d, "tmpbin", "abt_fix_final2.py")   # /tmp 자리 — 재수집 전에 사라진다
    body = (f'W = "{d}"\ns = open(f"{{W}}/plan/plan-v3.md", encoding="utf-8").read()\n'
            'f = f"{W}/plan/plan-final.md"\nopen(f, "w", encoding="utf-8").write(s)\n')
    put(os.path.join(W, "plan-v3.md"), "# v3\n", at(0, 30))
    end_cmd = f"cat > {fix} <<'EOF'\n{body}EOF\npython3 {fix}\necho done"
    steps = [(f"cp {W}/plan-v3.md {W}/plan-final.md && echo copied", "copied"),   # 앞선 쓰기 — 끝점을 놓치면 이것이 끝점이 된다
             (end_cmd, "done")]
    tpath = os.path.join(d, "t.jsonl")
    tp = transcript(tpath, d, steps)
    final = put(os.path.join(W, "plan-final.md"), "# v3\n", at(2, 5))
    put(fix, body)                                          # 첫 collect 때는 디스크에 있었다(18-run 묶음 원 수집과 같다)
    led, row = collect(d, tp, [final])
    first = epoch(gp(row, "wall", "end"))
    os.remove(fix)
    rc1, out1 = recollect(led)
    kept = epoch(gp(last_row(led), "wall", "end"))
    # 악화 주입 — 끝점 명령의 heredoc 을 transcript 에서 지운다(원천 소실). 앞선 cp 가 끝점이 되고 mtime 교차가 깨진다
    transcript(tpath, d, [steps[0], (f"python3 {fix}\necho done", "done")])
    rc2, out2 = recollect(led)
    ok = (first == at(2, 5).timestamp() and rc1 == 0 and "changed=0 worse=0" in out1 and kept == first
          and rc2 == 1 and "RECOLLECT-WORSE" in out2 and "차이 wall.end" in out2)
    return ok, (f"collect 끝점={first} · 스크립트 소실 뒤 recollect exit={rc1} 끝점={kept} 무변화={'changed=0 worse=0' in out1} · "
                f"악화 주입 recollect exit={rc2} 이유={'RECOLLECT-WORSE' in out2} 차이={'차이 wall.end' in out2}")


def cell_heredoc_versions(m):
    d = os.path.join(TD, "heredoc-versions")
    ver, disk = os.path.join(d, "bin", "v.py"), os.path.join(d, "bin", "disk.py")
    mk = lambda p, out: f"cat > {p} <<'EOF'\nW = '{d}'\nf = f\"{{W}}/{out}\"\nopen(f, 'w').write('x')\nEOF"
    put(disk, "print('no write')\n")   # 디스크에 있다 — heredoc 본문(c.md 쓰기)이 아니라 이 본문이 정본이다
    tp = transcript(os.path.join(d, "t.jsonl"), d, [
        (mk(ver, "a.md"), ""), (f"python3 {ver} && echo ok", "ok"), (mk(ver, "b.md"), ""), (f"python3 {ver} && echo ok", "ok"),
        (mk(disk, "c.md"), ""), (f"python3 {disk} && echo ok", "ok")])
    # mtime 을 일부러 '틀린' 호출 쪽에 둔다 — 본문을 시각과 무관하게 합치면 최근접 선택이 틀린 호출을 고른다
    arts = [put(os.path.join(d, n), "x", at(i, 5)) for n, i in (("a.md", 4), ("b.md", 2), ("c.md", 6))]
    got = [epoch(x.get("write")) for x in m.parse_transcript(tp, arts)["artifacts"]]
    want = [at(2, 5).timestamp(), at(4, 5).timestamp(), None]
    return got == want, f"a.md={got[0]} b.md={got[1]} c.md={got[2]} (기대 {want})"


def cell_multi_gpt_call(m):
    d = os.path.join(TD, "multi-gpt-call")
    W = os.path.join(d, "plan")
    os.makedirs(os.path.join(d, "plugin", "skills", "fz-plan"))
    cmd = (f"( /fz/scripts/gpt-exec.sh exec --cd {d} --out {W}/gpt-verify.json --prompt-file {W}/p.md ) > {W}/v.log 2>&1 &\n"
           f"( /fz/scripts/gpt-exec.sh exec --cd {d} --out {W}/gpt-verify-gates.json --prompt-file {W}/q.md ) > {W}/g.log 2>&1 &\n"
           f"wait; cat {W}/v.log {W}/g.log")
    skill = {"type": "user", "timestamp": z(at(0, 10)), "cwd": d, "isMeta": True,
             "message": {"role": "user", "content": f"Base directory for this skill: {d}/plugin/skills/fz-plan\n\n# fz-plan"}}
    tp = transcript(os.path.join(d, "t.jsonl"), d, [(cmd, "GATE-PASS\nGATE-PASS")], extra=[skill])
    for n, s in (("gpt-verify", 2), ("gpt-verify-gates", 3)):
        put(os.path.join(W, f"{n}.json.stream.log"), banner(f"0199a000-0000-7000-8000-0000000000a{s}"), at(1, s))
        put(os.path.join(W, f"{n}.json"), '{"verdict": "pass"}\n', at(1, 4))
    _, row = collect(d, tp, gpt_log_dir=W)
    g_, lead, src = row.get("gpt") or {}, row.get("lead") or {}, row.get("sources") or {}
    calls = (g_.get("calls"), g_.get("ok"), g_.get("banners"), g_.get("unlinked")) == (2, 2, 2, 0)
    shape = "tool_errors" in lead and "retries" not in lead and src.get("plugin_roots") == [os.path.join(d, "plugin")]
    return calls and shape, (f"gpt calls={g_.get('calls')} ok={g_.get('ok')} banners={g_.get('banners')} unlinked={g_.get('unlinked')} "
                             f"(기대 2·2·2·0) · lead tool_errors={'tool_errors' in lead} retries={'retries' in lead} · "
                             f"sources.plugin_roots={src.get('plugin_roots')}")


# ── F-423 보관 증거 자족성 ─────────────────────────────────────────────────
SECRET = "FZ-F423-FAKE-SECRET-5c1e"   # 가짜 비밀값 — 증거 폴더 어디에도 나오면 안 된다
DENY_RE = re.compile(r"auth|token|credential|key", re.I)
ARCH = {}


def js(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)


def dig(o, dotted):
    for k in dotted.split("."):
        o = o.get(k) if isinstance(o, dict) else None
    return o


def tree_sha(d):
    out = []
    for root, _, files in os.walk(d):
        for f in files:
            p = os.path.join(root, f)
            with open(p, "rb") as fh:
                out.append(os.path.relpath(p, d) + " " + hashlib.sha256(fh.read()).hexdigest())
    return hashlib.sha256("\n".join(sorted(out)).encode()).hexdigest()


def git_commit(d):
    env = dict(os.environ, GIT_AUTHOR_NAME="fixture", GIT_COMMITTER_NAME="fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
               GIT_COMMITTER_EMAIL="fixture@example.invalid", GIT_AUTHOR_DATE="2026-01-01T00:00:00Z",
               GIT_COMMITTER_DATE="2026-01-01T00:00:00Z")
    for cmd in (["init", "-q"], ["add", "-A"], ["-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "fx"]):
        r = subprocess.run(["git", "-C", d] + cmd, capture_output=True, text=True, timeout=60, env=env)
        if r.returncode != 0:
            raise Setup(f"git {cmd[-1]} 실패 {d}: {r.stderr.strip()[:200]}")


def snap_json(m, repo_mem):
    """상태 스냅샷(snapshot() 모양) — 감시 경로는 정본(실 HOME 아래 이름)이고 파일은 읽지 않는다(존재 없음 · 파일 0)."""
    home = os.path.expanduser("~")
    w = {"user_agent_memory": {"path": os.path.join(home, ".claude", "agent-memory"), "pattern": None, "exists": False, "files": {}},
         "repo_agent_memory": {"path": repo_mem, "pattern": None, "exists": False, "files": {}},
         "user_sessions": {"path": os.path.join(home, ".claude", "sessions"), "pattern": "SESSION-*_issues.json", "exists": False,
                           "files": {}}}
    return json.dumps({"schema": m.STATE_SCHEMA, "watch": w, "hash": m.state_hash(w)}, ensure_ascii=False)


def archive_run(m, name="archive"):
    """F-423 합성 run 하나(이름마다 collect 1회 · archive 는 두 셀이 나눠 쓴다). 실측 run 폴더(~/.fz/ab/<묶음>/<run>/) 모양을 본뜬다:
    run/{input.json, start.json, end.json, gpt-home/(sessions rollout + auth.json · config.toml · 비밀 이름 세션), tasks/<id>.output,
    plugin/(git 사본 · skills/fz-plan), repo/(git · GPT 출력 · 스트림 로그)} · ab/{ledger.jsonl, evidence/, state/pristine.json}.
    원천 하나하나가 판정 필드에 닿게 만든다 — tasks: 백그라운드 GPT 호출의 작업 출력(GATE-PASS)이 tasks 사본에만 있다(하네스 /tmp 원본은
    처음부터 없다) · gpt-home: 배너와 연결되지 않은 세션(다른 model · CLI 판 → gpt.models · versions) · plugin: transcript 의 스킬 루트."""
    if name in ARCH:
        return ARCH[name]
    d = os.path.join(TD, name)
    run, ab = os.path.join(d, "run"), os.path.join(d, "ab")
    repo, plugin, home, tasks = (os.path.join(run, x) for x in ("repo", "plugin", "gpt-home", "tasks"))
    put(os.path.join(repo, "README.md"), "# fixture\n")
    git_commit(repo)
    put(os.path.join(plugin, "skills", "fz-plan", "SKILL.md"), "# fz-plan\n")
    git_commit(plugin)
    ij = os.path.join(run, "input.json")
    r = subprocess.run(["python3", "-B", AB, "input", "--root", repo, "--fixture", "plan-feature", "--plugin-root", plugin,
                        "--plugin-source", plugin, "--out", ij], capture_output=True, text=True, timeout=120)
    if not os.path.isfile(ij):
        raise Setup(f"input 기록 실패 exit {r.returncode}: {(r.stdout + r.stderr)[-200:]}")
    W, gone, tid = os.path.join(repo, "X-1", "plan"), os.path.join(d, "gone-tmp", "tasks"), "b0f423task"
    cmd = f"/fz/scripts/gpt-exec.sh exec --cd {repo} --out {W}/gpt-verify.json --prompt-file {W}/p.md"
    notif = (f"<task-notification>\n<task-id>{tid}</task-id>\n<tool-use-id>t1</tool-use-id>\n<output-file>{gone}/{tid}.output"
             "</output-file>\n<status>completed</status>\n<summary>Background command \"gpt verify\" completed (exit code 0)</summary>\n"
             "</task-notification>")
    evs = [{"type": "user", "timestamp": z(at(0)), "cwd": repo, "message": {"role": "user", "content": "/fz:fz-plan ABT-1"}},
           {"type": "user", "timestamp": z(at(0, 10)), "cwd": repo, "isMeta": True,
            "message": {"role": "user", "content": f"Base directory for this skill: {plugin}/skills/fz-plan\n\n# fz-plan"}},
           {"type": "assistant", "timestamp": z(at(1)), "cwd": repo, "effort": "xhigh",
            "message": {"id": "m1", "model": "claude-opus-5-5", "stop_reason": "tool_use", "usage": {"output_tokens": 10},
                        "content": [{"type": "tool_use", "id": "t1", "name": "Bash",
                                     "input": {"command": cmd, "run_in_background": True}}]}},
           {"type": "user", "timestamp": z(at(1, 1)), "cwd": repo, "message": {"role": "user", "content": [
               {"type": "tool_result", "tool_use_id": "t1",
                "content": f"Command running in background with ID: {tid}. Output is being written to: {gone}/{tid}.output"}]}},
           {"type": "user", "timestamp": z(at(3)), "cwd": repo, "message": {"role": "user", "content": notif}}]
    tp = put(os.path.join(d, "session.jsonl"), "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in evs))
    put(os.path.join(W, "p.md"), "prompt\n")
    put(os.path.join(W, "gpt-verify.json"), '{"verdict": "pass"}\n', at(2, 50))
    put(os.path.join(W, "gpt-verify.json.stream.log"), banner("00000000-0000-7000-8000-000000000001"), at(1, 3))
    put(os.path.join(tasks, f"{tid}.output"), "GATE-PASS\n", at(3))
    day = os.path.join(home, "sessions", "2026", "01", "01")
    put(os.path.join(day, "rollout-2026-01-01T00-01-00-00000000-0000-7000-8000-000000000002.jsonl"),
        json.dumps({"type": "session_meta", "payload": {"id": "00000000-0000-7000-8000-000000000002", "cli_version": "0.999.0"}}) + "\n"
        + json.dumps({"type": "turn_context", "payload": {"model": "gpt-6-home", "effort": "high"}}) + "\n")
    put(os.path.join(day, "auth-token.jsonl"), json.dumps({"type": "session_meta", "payload": {"token": SECRET}}) + "\n")
    put(os.path.join(home, "auth.json"), json.dumps({"OPENAI_API_KEY": SECRET}) + "\n")
    put(os.path.join(home, "config.toml"), f'[auth]\ntoken = "{SECRET}"\n')
    pristine = put(os.path.join(ab, "state", "pristine.json"), snap_json(m, "/nonexistent"))
    start = put(os.path.join(run, "start.json"), snap_json(m, os.path.join(repo, ".claude", "agent-memory")))
    end = put(os.path.join(run, "end.json"), snap_json(m, os.path.join(repo, ".claude", "agent-memory")))
    led = os.path.join(ab, "ledger.jsonl")
    cmd = ["python3", "-B", AB, "collect", "--ledger", led, "--workflow", "fz-plan", "--arm", "C", "--run", "1", "--order", "1",
           "--phase", "change", "--run-id", "fz-plan:C1:plan-feature", "--fixture", "plan-feature", "--transcript", tp,
           "--input-json", ij, "--state-pristine", pristine, "--state-start", start, "--state-end", end, "--tasks-dir", tasks]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise Setup(f"collect exit {r.returncode}: {(r.stdout + r.stderr)[-300:]}")
    ARCH[name] = dict(row=last_row(led), led=led, ev=os.path.join(ab, "evidence"), home=home, cmd=cmd, day=day, tid=tid,
                      originals={"plugin": plugin, "gpt-home": home, "tasks": tasks, "start.json": start, "end.json": end,
                                 "pristine": pristine})
    return ARCH[name]


def cell_archive_no_secret(m):
    st = archive_run(m)
    ev, row = st["ev"], st["row"]
    names, leaks, rollouts = [], [], []
    for root, _, files in os.walk(ev):
        for f in files:
            p = os.path.join(root, f)
            rel = os.path.relpath(p, ev)
            names.append(rel)
            with open(p, "rb") as fh:
                if SECRET.encode() in fh.read():
                    leaks.append(rel)
            if f.startswith("rollout-") and f.endswith(".jsonl"):
                rollouts.append(rel)
    with open(st["led"], encoding="utf-8") as fh:
        led_leak = SECRET in fh.read()
    planted = all(os.path.isfile(os.path.join(st["home"], x)) for x in ("auth.json", "config.toml"))
    denied = [x for x in names if DENY_RE.search(os.path.basename(x)) or os.path.basename(x) == "config.toml"]
    ok = planted and not leaks and not denied and not led_leak and len(rollouts) == 1 and dig(row, "gpt.sessions") == 1
    return ok, (f"심은 비밀 파일 실재={planted} · 증거 폴더 비밀값 {leaks} · 비밀 이름 파일 {denied} · 원장 비밀값={led_leak} · "
                f"양성 대조: rollout 사본 {len(rollouts)}개(기대 1) · gpt.sessions={dig(row, 'gpt.sessions')}(기대 1)")


def cell_archive_replay(m):
    st = archive_run(m)
    row, led, ev = st["row"], st["led"], st["ev"]
    fields = sorted({f for fs in m.VERIFY_FIELDS.values() for f in fs}
                    | {"complete.why", "gpt.sessions", "gpt.invisible", "plugin.changed_during_run", "plugin.code_changed_during_run"})
    ev0 = tree_sha(ev) if os.path.isdir(ev) else None
    f0 = m.build_row(m.collect_spec_args(row["collect_args"]), dry=True)          # 원래 자리가 있을 때
    # 옛 행 보기(원래 경로를 가리키는 collect_args · 빈 증거 폴더) dry 재구성 — 사본을 쓰지 않고(폴더가 생기지 않는다) 같은 판정
    o = st["originals"]
    old = dict(row["collect_args"], evidence_dir=os.path.join(TD, "archive", "dry-ev"), state_pristine=o["pristine"],
               state_start=o["start.json"], state_end=o["end.json"], tasks_dir=[o["tasks"]])
    f_old = m.build_row(m.collect_spec_args(old), dry=True)
    dry_clean = (tree_sha(ev) if os.path.isdir(ev) else None) == ev0 and not os.path.exists(old["evidence_dir"])
    d_old = [f for f in fields if js(dig(f_old, f)) != js(dig(f0, f))]
    for p in st["originals"].values():                                             # 원래 자리 제거
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    left = [k for k, p in st["originals"].items() if os.path.exists(p)]
    f1 = m.build_row(m.collect_spec_args(row["collect_args"]), dry=True)          # 보관본 단독
    # 원천 범위(source_scope) — 지운 뒤 사라진 원천 0 · 보관 종류 여섯 · 플러그인 루트는 원래 자리로 세지 않는다(기록이 대신한다)
    sc = sys.modules["ab_ledger_collect"].source_scope(row)
    sc_gone = sorted({n for n, _, ok_ in sc["archived"] + sc["original"] if not ok_})
    sc_arch, sc_orig = sorted({n for n, _, _ in sc["archived"]}), sorted({n for n, _, _ in sc["original"]})
    want_arch = ["gpt_home", "plugin_record", "state_end", "state_pristine", "state_start", "tasks_dirs"]
    scope_ok = not sc_gone and sc_arch == want_arch and "plugin_roots" not in sc_orig
    rc, out = recollect(led)
    ev_kept = (tree_sha(ev) if os.path.isdir(ev) else None) == ev0
    d_row = [f for f in fields if js(dig(row, f)) != js(dig(f0, f))]
    d_arch = [f for f in fields if js(dig(f0, f)) != js(dig(f1, f))]
    moved = " · ".join(f"{f} {js(dig(f0, f))[:40]}→{js(dig(f1, f))[:40]}" for f in d_arch[:6])
    ok = (not left and not d_row and not d_old and not d_arch and dry_clean and rc == 0 and "changed=0 worse=0" in out and ev_kept
          and scope_ok)
    return ok, (f"원래 자리 제거 {sorted(st['originals'])} 남음 {left} · 판정 필드 {len(fields)}개 — 저장 행↔원래 자리 재구성 차이 {d_row} · "
                f"원래 경로 행 보기↔사본 경로 차이 {d_old} · "
                f"원래 자리↔보관본 단독 차이 {d_arch} {moved} · recollect exit={rc} 무변화={'changed=0 worse=0' in out} · "
                f"dry 쓰기 0={dry_clean} · 원천 없는 recollect 뒤 증거 폴더 불변={ev_kept} · "
                f"원천 범위: 사라짐 {sc_gone} · 보관 {sc_arch} · 원래 자리 {sc_orig}")


def cell_archive_remeasure(m):
    st = archive_run(m, "remeasure")
    for f in os.listdir(st["day"]):                    # 재측정 사이 원천이 바뀌었다 — rollout 교체 · 작업 출력 삭제
        if f.startswith("rollout-"):
            os.remove(os.path.join(st["day"], f))
    put(os.path.join(st["day"], "rollout-2026-01-01T00-02-00-00000000-0000-7000-8000-000000000003.jsonl"),
        json.dumps({"type": "session_meta", "payload": {"id": "00000000-0000-7000-8000-000000000003", "cli_version": "0.998.0"}}) + "\n"
        + json.dumps({"type": "turn_context", "payload": {"model": "gpt-6-other", "effort": "high"}}) + "\n")
    os.remove(os.path.join(st["originals"]["tasks"], f"{st['tid']}.output"))
    r = subprocess.run(st["cmd"], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise Setup(f"재측정 collect exit {r.returncode}: {(r.stdout + r.stderr)[-300:]}")
    row = last_row(st["led"])
    fields = sorted({f for fs in m.VERIFY_FIELDS.values() for f in fs} | {"complete.why", "gpt.sessions", "gpt.invisible"})
    f1 = m.build_row(m.collect_spec_args(row["collect_args"]), dry=True)
    d = [f for f in fields if js(dig(row, f)) != js(dig(f1, f))]
    g = row.get("gpt") or {}
    ok = (row.get("measure_seq") == 2 and g.get("sessions") == 1 and "gpt-6-other" in (g.get("models") or [])
          and "gpt-6-home" not in (g.get("models") or []) and g.get("ok") == 0 and not d)
    return ok, (f"재측정 measure_seq={row.get('measure_seq')} · gpt.sessions={g.get('sessions')}(기대 1) · models={g.get('models')} "
                f"(앞 측정 gpt-6-home 없음) · gpt.ok={g.get('ok')}(작업 출력 삭제 — 기대 0) · 행↔사본 재구성 차이 {d}")


EXPECTED_CELLS = ("fstring-argv", "moved-gpt-log", "lost-script", "heredoc-versions", "multi-gpt-call", "archive-no-secret",
                  "archive-replay", "archive-remeasure")   # 셀 이름 고정(F-408)
CELLS = (("fstring-argv", cell_fstring_argv), ("moved-gpt-log", cell_moved_gpt_log), ("lost-script", cell_lost_script),
         ("heredoc-versions", cell_heredoc_versions), ("multi-gpt-call", cell_multi_gpt_call),
         ("archive-no-secret", cell_archive_no_secret), ("archive-replay", cell_archive_replay),
         ("archive-remeasure", cell_archive_remeasure))
try:
    mod = load()
except Exception as e:   # noqa: BLE001 — 대상 계측기가 싣히지 않는 것은 트리 결함이다(셀 FAIL 과 같은 1)
    print(f"FAIL 계측기 적재 {AB}: {type(e).__name__}: {e}")
    print(f"COLLECTOR-REPLAY-FAIL 0/{len(CELLS)} — 적재")
    sys.exit(1)
passed, failed, setup, ran = 0, [], [], []
for name, fn in CELLS:
    ran.append(name)
    try:
        ok, detail = fn(mod)
    except Exception as e:   # noqa: BLE001 — 셀 안 예외는 준비 실패(3)다. 결함 재현(1)으로 세지 않는다
        setup.append(name)
        print(f"SETUP {name}: {type(e).__name__}: {e}")
        traceback.print_exc(limit=2)
        continue
    print(f"{'PASS' if ok else 'FAIL'} {name}: {detail}")
    if ok:
        passed += 1
    else:
        failed.append(name)
cells_line = f"CELLS n={len(ran)} ran={','.join(ran)}"
if setup:
    print(f"COLLECTOR-REPLAY-SETUP {passed}/{len(CELLS)} — 준비 실패 {','.join(setup)}")
    print(cells_line)
    sys.exit(3)
if tuple(ran) != EXPECTED_CELLS:
    failed.append("cell-set")
    print(f"FAIL cell-set: 돈 셀 = EXPECTED_CELLS 가 아니다 — 없음={sorted(set(EXPECTED_CELLS) - set(ran))} · "
          f"뜻밖={sorted(set(ran) - set(EXPECTED_CELLS))} · 순서={list(ran)}")
if failed:
    print(f"COLLECTOR-REPLAY-FAIL {passed}/{len(CELLS)} — {','.join(failed)}")
    print(cells_line)
    sys.exit(1)
print(f"COLLECTOR-REPLAY-OK {passed}/{len(CELLS)}")
print(cells_line)
PY
