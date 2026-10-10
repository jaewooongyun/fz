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
# 보관 증거(두 묶음 18 · 2 run) 재생은 같은 폴더 external.sh 다 — 외부 원천이 필요해 게이트에서만 부른다.
# 출력: 셀마다 `PASS|FAIL <셀>: …` · 요약 줄 `COLLECTOR-REPLAY-OK 5/5` 또는 `COLLECTOR-REPLAY-FAIL <통과>/5 — <셀>` ·
#   끝 줄 `CELLS n=<수> ran=<…>`. ⛔ 셀 집합 대조(F-408): 돈 셀 이름이 `EXPECTED_CELLS`(위 5종 · 순서까지)와 다르면 FAIL(exit 1)
# exit: 0 5/5 · 1 셀 단언 실패 · 2 UNRUN(python3 · 대상 계측기 부재) · 3 준비 실패(인자 · 임시 폴더 · 셀 안 예외)
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
import importlib.util
import json
import os
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


EXPECTED_CELLS = ("fstring-argv", "moved-gpt-log", "lost-script", "heredoc-versions", "multi-gpt-call")   # 셀 이름 고정(F-408)
CELLS = (("fstring-argv", cell_fstring_argv), ("moved-gpt-log", cell_moved_gpt_log), ("lost-script", cell_lost_script),
         ("heredoc-versions", cell_heredoc_versions), ("multi-gpt-call", cell_multi_gpt_call))
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
