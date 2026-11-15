#!/bin/bash
# A/B 수집기 보관 증거 재생 (F-361) — 보관한 두 실험 묶음(18 run · 2 run)의 원장 행을 대상 트리 계측기로 다시 만든다.
#
# ⛔ health-check 글롭(tests/fixtures/*/*/run.sh) 밖 러너다 — 플러그인 밖 보관 증거가 필요해 인자 없이 도는 휴대 회귀 셀이
#    될 수 없다. 게이트만 `bash external.sh --tree <플러그인 루트> --evidence <보관 증거 루트>` 로 부른다.
#    번들 합성 셀은 같은 폴더 run.sh 다.
#
# 보관 증거(--evidence E) = E/<릴리스>/<run>/ 사본 + E/../evidence.sources.jsonl(행 원문 · 사본 목록 · sha256 · 원래 경로)
#   대체: transcript · end.json 은 사본으로 돌린다. transcript 사본 안의 Workflow 폴더 경로(sources.wf_dirs)는 사본
#     E/<run>/wf/<이름> 으로 바꾼 파생본을 쓴다 — 원래 폴더(~/.claude/projects 아래)는 약 30일 뒤 사라진다
#   ⛔ 나머지 원천은 **원래 자리에 있어야 돈다**(F-423): 계측기가 transcript 의 절대 경로로 찾고 경로 문자열 자체를 비교한다
#     (산출물 쓰기 대상 `_same_path` · GPT 로그 직접 경로 · 플러그인 경로 실재 · gpt-home 은 input.json 옆). 그래서 산출물 ·
#     GPT 로그 · 감사 · input.json 은 원래 자리 해시 == 목록 해시, run 폴더 repo/ 는 repo.sha256 전건, 스냅샷 · tasks ·
#     gpt_log_dir · evidence_dir · 플러그인 사본 · gpt-home 은 실재를 먼저 센다. 하나라도 어긋나면 UNRUN 이다(PASS 아님)
#   쓰기: 이 러너의 임시 폴더뿐 — 원장 사본 · evidence_dir 사본(싱크) · 파생 transcript. 끝에 원본 원장 · 원래 evidence_dir ·
#     보관 사본 해시를 앞뒤로 대조한다. HOME 은 바꾸지 않는다(state_info 가 감시 경로를 ~ 정본과 비교한다 — 격리하면 인공물)
# 판정
#   2-run 묶음 run 1   재구성 complete=True · GPT ok = 배너 = 4 · 미연결 0
#   18-run 묶음 C2     plan-feature 끝점 비퇴화 — wall.total_s · wall.end 가 저장 행과 같고 |mtime Δ| ≤ MTIME_TOL_S · 무효 사유 불변
#   20 행 전부  대상 트리 VERIFY_FIELDS + complete.why 가 저장 행과 같다. 예외 둘 —
#               ⑪ 한 명령 여러 GPT 호출: gpt.calls · ok · banners 만, 셋 다 transcript 의 추가 호출 수만큼 늘었으면 INTENDED
#               시도 · advisor 계측 키(wall.workflows · wf.advisor — F-387 · F-382 가 설계상 바꾸는 키): complete.ok · 무효
#               사유가 그대로면 NOTE(최종 판정은 계측기 지문을 확정하는 재채점 단계). 그 밖의 차이는 FAIL
#   recollect   원장 사본 둘(두 묶음) 재수집 exit 0 · 악화 0 / 악화 주입(C2 끝점 명령의 heredoc 을 지운 transcript)은
#               exit 1 + `RECOLLECT-WORSE fz-plan:C2:plan-feature` + `차이 wall.end`
# 출력: 판정마다 `PASS|FAIL|INTENDED|NOTE …` · 끝줄 `COLLECTOR-EXTERNAL-OK` 또는 `COLLECTOR-EXTERNAL-FAIL <건수>`
# exit: 0 PASS · 1 판정 실패 · 2 UNRUN(증거 루트 · 목록 · 사본 해시 · 원래 자리 원천 부재 · python3 · 계측기 부재) ·
#       3 준비 실패(인자 · 임시 폴더 · 예외 · 원본이 바뀜)
#   ⛔ 예외를 1 로 내면 '기준 트리 exit 1' 게이트가 결함 재현 없이 통과한다 — 그래서 3 이다
# usage: external.sh --evidence <보관 증거 루트> [--tree <플러그인 루트>]   (기본 트리: 이 파일이 든 트리)
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
E=""
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    --evidence) [ $# -ge 2 ] || { echo "SETUP --evidence 에 경로가 없다"; exit 3; }
            E="$2"; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
[ -n "$E" ] || { echo "SETUP --evidence 가 없다"; exit 3; }
[ -d "$E" ] || { echo "UNRUN: evidence unavailable $E"; exit 2; }
E="$(cd "$E" && pwd)"
command -v python3 >/dev/null 2>&1 || { echo "UNRUN: python3 없음"; exit 2; }
[ -f "$R/scripts/ab_ledger.py" ] || { echo "UNRUN: 대상 계측기 없음 $R/scripts/ab_ledger.py"; exit 2; }
T0="$(mktemp -d "${TMPDIR:-/tmp}/fz-collector-external.XXXXXX")" || { echo "SETUP mktemp 실패"; exit 3; }
trap 'rm -rf "${T0:?}"' EXIT
TD="$(cd "$T0" && pwd -P)" || { echo "SETUP 임시 폴더 정규화 실패: $T0"; exit 3; }

# ⛔ GIT_OPTIONAL_LOCKS=0 — plugin_info 의 `git status` 가 원래 자리 플러그인 사본의 index 를 고쳐 쓰지 않게
GIT_OPTIONAL_LOCKS=0 PYTHONDONTWRITEBYTECODE=1 python3 -I - "$R" "$E" "$TD" <<'PY'
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import traceback

sys.dont_write_bytecode = True   # ⛔ 대상 트리(기준 clone 포함)의 scripts/ 에 __pycache__ 를 쓰지 않는다
TREE, EV, TD = sys.argv[1:4]
AB = os.path.join(TREE, "scripts", "ab_ledger.py")
MAN = os.path.join(os.path.dirname(EV), "evidence.sources.jsonl")
# 보관 목록(evidence.sources.jsonl)의 (release, run_id) 값 — 데이터 키라 목록과 같은 글자로 둔다(2-run 묶음 run 1 · 18-run 묶음 C2)
RD1, C2 = ("R-D", "fz-plan:C1:plan-feature"), ("R-C", "fz-plan:C2:plan-feature")
GPT11 = ("gpt.banners", "gpt.calls", "gpt.ok")
OTHER_STEP = ("wall.workflows", "wf.advisor")
# 악화 주입 표지 — 18-run 묶음 C2 plan-feature 끝점 명령(보관 transcript 878줄 · /tmp 에 만들고 바로 부른 heredoc 스크립트 — F-361)
C2_HEREDOC = "cat > /tmp/abt2001_fix_final2.py <<'EOF'\n"


def unrun(msg):
    print(f"UNRUN: {msg}")
    print("COLLECTOR-EXTERNAL-UNRUN")
    sys.exit(2)


def setup(msg):
    print(f"SETUP {msg}")
    sys.exit(3)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def js(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)


def dig(o, dotted):
    for k in dotted.split("."):
        o = o.get(k) if isinstance(o, dict) else None
    return o


def tree_sha(d):
    out = []
    for root, _, files in os.walk(d):
        for f in sorted(files):
            p = os.path.join(root, f)
            out.append(os.path.relpath(p, d) + " " + sha(p))
    return hashlib.sha256("\n".join(sorted(out)).encode()).hexdigest()


def manifest():
    if not os.path.isfile(MAN):
        unrun(f"evidence manifest unavailable {MAN}")
    out = []
    for ln in open(MAN, encoding="utf-8"):
        r = json.loads(ln)
        if hashlib.sha256(r["row"].encode("utf-8")).hexdigest() != r["row_sha256"]:
            unrun(f"목록 행 원문 해시 불일치 {r['release']} {r['run_id']}")
        r["obj"] = json.loads(r["row"])
        out.append(r)
    if len(out) != 20 or not {(r["release"], r["run_id"]) for r in out} >= {RD1, C2}:
        unrun(f"목록이 보관 두 묶음(18 · 2 run)이 아니다 ({len(out)}행)")
    return out


def copy_of(r, kind):
    hit = [os.path.join(EV, r["ev"], rel) for rel, k, _, _ in r["copies"] if k == kind]
    return hit[0] if len(hit) == 1 else None


def integrity(man):
    bad = []
    for r in man:
        for rel, kind, want, _ in r["copies"]:
            cp = os.path.join(EV, r["ev"], rel)
            if not os.path.isfile(cp) or sha(cp) != want:
                bad.append(f"{r['ev']}/{rel}")
        for d in r["obj"]["sources"]["wf_dirs"]:
            if not os.path.isdir(os.path.join(EV, r["ev"], "wf", os.path.basename(d))):
                bad.append(f"{r['ev']}/wf/{os.path.basename(d)}")
        if not copy_of(r, "transcript") or not copy_of(r, "state_end") or not copy_of(r, "input_json"):
            bad.append(f"{r['ev']} transcript · end.json · input.json 사본")
    return bad


def census(r):
    """원래 자리에서 읽히는 원천(F-423) — 부재 · 변경 목록."""
    row, ca, miss = r["obj"], r["obj"]["collect_args"], []
    inp = [(rel, orig) for rel, k, _, orig in r["copies"] if k == "input_json"][0]
    run_dir = inp[1][:-len(inp[0])].rstrip("/")
    for rel, kind, want, orig in r["copies"]:
        if kind in ("transcript", "state_end", "wf"):
            continue
        if not os.path.isfile(orig):
            miss.append(f"부재 {orig}")
        elif sha(orig) != want:
            miss.append(f"변경 {orig}")
    lst = os.path.join(EV, r["ev"], "repo.sha256")
    if not os.path.isfile(lst):
        miss.append(f"목록 없음 {lst}")
    else:
        for ln in open(lst, encoding="utf-8"):
            want, rel = ln.rstrip("\n").split("  ", 1)
            p = os.path.join(run_dir, "repo", rel)
            if not os.path.isfile(p):
                miss.append(f"부재 {p}")
            elif sha(p) != want:
                miss.append(f"변경 {p}")
    for p in (ca.get("state_pristine"), ca.get("state_start")):
        if not p or not os.path.isfile(p):
            miss.append(f"부재 {p}")
    dirs = list(ca.get("tasks_dir") or []) + list(ca.get("gpt_log_dir") or []) + [ca.get("evidence_dir")]
    dirs += list((row.get("plugin") or {}).get("roots") or [])
    if (row.get("gpt") or {}).get("sessions") is not None:
        dirs.append(os.path.join(run_dir, "gpt-home"))
    miss += [f"부재 {d}" for d in dirs if not d or not os.path.isdir(d)]
    return miss


def derived_transcript(r, dst, drop_heredoc=False):
    """transcript 사본 → Workflow 폴더 경로를 보관 사본으로 바꾼 파생본(drop_heredoc: C2 끝점 명령의 heredoc 을 지운 악화본)."""
    txt = open(copy_of(r, "transcript"), encoding="utf-8").read()
    for d in r["obj"]["sources"]["wf_dirs"]:
        txt = txt.replace(d, os.path.join(EV, r["ev"], "wf", os.path.basename(d)))
    if drop_heredoc:
        out, hit = [], 0
        for ln in txt.splitlines():
            ev = json.loads(ln)
            for b in ((ev.get("message") or {}).get("content") or []) if ev.get("type") == "assistant" else []:
                c = (b.get("input") or {}).get("command") if isinstance(b, dict) and b.get("type") == "tool_use" else None
                if isinstance(c, str) and C2_HEREDOC in c:
                    b["input"]["command"] = c.split(C2_HEREDOC, 1)[1].split("\nEOF\n", 1)[1]
                    hit += 1
            out.append(json.dumps(ev, ensure_ascii=False))
        if hit != 1:
            setup(f"악화 주입 표지를 {hit}번 찾았다(1번이어야 한다) — {C2_HEREDOC!r}")
        txt = "\n".join(out) + "\n"
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(txt)
    return dst


SINKS = {}


def sink_for(orig):
    """원래 evidence_dir(하네스 반환 사본)를 임시 폴더로 복사(mtime 보존)해 쓴다 — recollect 의 쓰기는 사본에만."""
    if orig not in SINKS:
        dst = os.path.join(TD, "sink", f"{len(SINKS)}-{os.path.basename(os.path.dirname(os.path.dirname(orig)))}")
        shutil.copytree(orig, dst, copy_function=shutil.copy2)
        SINKS[orig] = dst
    return SINKS[orig]


def args_for(r, tag="replay", drop_heredoc=False):
    a = dict(r["obj"]["collect_args"])
    a["transcript"] = derived_transcript(r, os.path.join(TD, tag, r["ev"], "transcript.jsonl"), drop_heredoc)
    a["state_end"] = copy_of(r, "state_end")
    a["evidence_dir"] = sink_for(a["evidence_dir"])
    return a


def extra_calls(m, path):
    """transcript 의 Bash 명령마다 (GPT 호출 수 − 1) 합 — 대상 트리의 호출 판정(_cmd_views · GPT_CALL_RE)으로 센다."""
    n = 0
    evs, _ = m.iter_jsonl(path)
    for ev in evs:
        for b in ((ev.get("message") or {}).get("content") or []) if ev.get("type") == "assistant" else []:
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Bash":
                for v in m._cmd_views(str((b.get("input") or {}).get("command") or "")):
                    k = len(m.GPT_CALL_RE.findall(m._shell_part(v)))
                    if k:
                        n += k - 1
                        break
    return n


def originals(man):
    led = sorted({r["ledger"] for r in man})
    evd = sorted({r["obj"]["collect_args"]["evidence_dir"] for r in man})
    return [sha(x) for x in led] + [tree_sha(x) for x in evd] + [str(integrity(man))]


def main():
    sp = importlib.util.spec_from_file_location("abl_target", AB)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    man = manifest()
    bad = integrity(man)
    if bad:
        unrun(f"보관 증거 사본 해시 불일치 · 부재 {len(bad)}건 — {bad[:3]}")
    miss = [f"{r['release']} {r['run_id']}: {x}" for r in man for x in census(r)]
    if miss:
        unrun(f"원래 자리 원천 부재 · 변경 {len(miss)}건 (F-423 — 보관 증거는 transcript · end.json · wf 만 대체한다) — {miss[:5]}")
    for lg in sorted({r["ledger"] for r in man}):
        if sha(lg) not in {r["ledger_sha256"] for r in man if r["ledger"] == lg}:
            unrun(f"원장이 목록 시점과 다르다 {lg}")
    before = originals(man)
    opts = {"model": m.DEFAULT_MODEL, "effort": m.DEFAULT_EFFORT}
    fields = sorted({f for fs in m.VERIFY_FIELDS.values() for f in fs} | {"complete.why"})
    fails = []

    def check(ok, label, detail):
        print(f"{'PASS' if ok else 'FAIL'} {label}: {detail}")
        if not ok:
            fails.append(label)

    # ① 20 행 재구성(dry)
    for r in man:
        key, old = (r["release"], r["run_id"]), r["obj"]
        a = args_for(r)
        new = m.build_row(argparse.Namespace(**a), dry=True)
        diff = [f for f in fields if js(dig(old, f)) != js(dig(new, f))]
        inv0, inv1 = m.row_invalid(old, None, opts), m.row_invalid(new, None, opts)
        tag = f"{r['release']} {r['run_id']}"
        other = [f for f in diff if f in OTHER_STEP]
        rest = [f for f in diff if f not in OTHER_STEP]
        if other:
            same = inv0 == inv1 and dig(old, "complete.ok") == dig(new, "complete.ok")
            print(f"NOTE {tag}: 계측 키 {other} 변화 · 완주 · 무효 사유 {'그대로' if same else '바뀜'} — 최종 판정은 재채점 단계")
            if not same:
                fails.append(f"{tag} 계측 키 변화가 판정을 바꿨다")
        if rest and set(rest) <= set(GPT11):
            k = extra_calls(m, a["transcript"])
            grown = all((dig(new, f) or 0) - (dig(old, f) or 0) == k for f in GPT11)
            ok11 = k > 0 and grown and inv0 == inv1
            print(f"{'INTENDED' if ok11 else 'FAIL'} {tag}: ⑪ 한 명령 여러 GPT 호출 +{k} — "
                  + " · ".join(f"{f} {dig(old, f)}→{dig(new, f)}" for f in GPT11) + f" · 무효 사유 {'그대로' if inv0 == inv1 else inv1}")
            if not ok11:
                fails.append(f"{tag} ⑪")
            rest = []
        if rest:
            check(False, f"{tag} 판정 필드", " · ".join(f"{f} {js(dig(old, f))[:60]}→{js(dig(new, f))[:60]}" for f in rest[:6])
                  + f" · 무효 사유 {inv0}→{inv1}")
        elif not other and not diff:
            print(f"PASS {tag}: 판정 필드 {len(fields)}개 동일")
        if key == RD1:
            g = new.get("gpt") or {}
            check(dig(new, "complete.ok") is True and g.get("ok") == g.get("banners") == 4 and g.get("unlinked") == 0,
                  "2-run 묶음 run 1", f"complete={dig(new, 'complete.ok')} why={dig(new, 'complete.why')} gpt ok={g.get('ok')} "
                  f"banners={g.get('banners')} unlinked={g.get('unlinked')} (기대 True · 4 · 4 · 0)")
        if key == C2:
            md = dig(new, "wall.mtime_delta_s")
            check(dig(new, "wall.total_s") == dig(old, "wall.total_s") and dig(new, "wall.end") == dig(old, "wall.end")
                  and md is not None and abs(md) <= m.MTIME_TOL_S and inv1 == inv0,
                  "18-run 묶음 C2 끝점", f"wall {dig(old, 'wall.total_s')}→{dig(new, 'wall.total_s')} · end {dig(new, 'wall.end')} · "
                  f"mtimeΔ {md} · 무효 사유 {inv1}")

    # ② recollect — 원장 사본(목록 행만 원천을 사본으로 · 모든 run 행의 evidence_dir 는 싱크)
    by_line = {(r["ledger"], r["line"]): r for r in man}

    def prep(lg, dst, worse=False):
        out = []
        for i, ln in enumerate(open(lg, encoding="utf-8"), 1):
            row = json.loads(ln)
            if row.get("type") == "run" and isinstance(row.get("collect_args"), dict):
                r = by_line.get((lg, i))
                if r is not None:
                    row["collect_args"] = args_for(r, "recollect-worse" if worse else "recollect",
                                                   drop_heredoc=worse and (r["release"], r["run_id"]) == C2)
                else:
                    row["collect_args"]["evidence_dir"] = sink_for(row["collect_args"]["evidence_dir"])
            out.append(json.dumps(row, ensure_ascii=False))
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")
        return dst

    def recollect(led, *extra):
        p = subprocess.run(["python3", "-B", AB, "recollect", "--ledger", led, *extra], capture_output=True, text=True, timeout=600)
        return p.returncode, p.stdout + p.stderr

    for n, lg in enumerate(sorted({r["ledger"] for r in man})):
        rc, out = recollect(prep(lg, os.path.join(TD, f"ledger-{n}.jsonl")))
        lines = [x for x in out.splitlines() if x.startswith("recollect")]
        check(rc == 0 and "RECOLLECT-WORSE" not in out, f"recollect {os.path.basename(os.path.dirname(os.path.dirname(lg)))}",
              f"exit={rc} · {lines[-1] if lines else '(요약 없음)'}")
    rc_lg = [r["ledger"] for r in man if (r["release"], r["run_id"]) == C2][0]
    rc, out = recollect(prep(rc_lg, os.path.join(TD, "ledger-worse.jsonl"), worse=True), "--run-id", C2[1])
    check(rc == 1 and f"RECOLLECT-WORSE {C2[1]}" in out and "차이 wall.end" in out, "recollect 악화 주입",
          f"exit={rc} (기대 1) · 이유={f'RECOLLECT-WORSE {C2[1]}' in out} · 차이={'차이 wall.end' in out} · "
          + " | ".join(x.strip() for x in out.splitlines() if "RECOLLECT-WORSE" in x or x.startswith("recollect:"))[:300])

    if originals(man) != before:
        setup("원본 원장 · evidence_dir · 보관 사본이 실행 중에 바뀌었다 — 측정 무효")
    print("originals unchanged — 원장 2 · evidence_dir 2 · 보관 사본 해시")
    if fails:
        print(f"COLLECTOR-EXTERNAL-FAIL {len(fails)} — {', '.join(fails)}")
        sys.exit(1)
    print("COLLECTOR-EXTERNAL-OK")


try:
    main()
except SystemExit:
    raise
except Exception as e:   # noqa: BLE001 — 예외는 준비 실패(3)다. 결함 재현(1)으로 세지 않는다
    traceback.print_exc(limit=3)
    setup(f"예외 {type(e).__name__}: {e}")
PY
