#!/usr/bin/env python3
# diff-parse: not-a-diff — diff 본문의 줄 접두사를 읽지 않는다. `git apply --numstat` 출력과 numstat 파일(추가·삭제·경로 탭 3열)만 센다
"""모드 게이트 — Workflow 를 띄우기 전에 작업 크기를 재서 light / full 추천과 근거를 낸다.

⛔ 왜 스크립트인가: 크기 조건이 산문에만 있으면 집행되지 않는다(fz-review light 의 '5파일·100LOC' 는 재는 코드가 없었다).
   추천 임계는 **이 파일이 정본**이다 — modules/mode-gate.md 는 언제 묻고 무엇을 보이는지(계약)를, 이 파일은 숫자를 가진다.
⛔ 추천은 라벨이다 — 사용자가 매번 고른다(질문 생략 경로는 modules/mode-gate.md). 그래서 임계는 초기값이고 실사용으로 고친다.
⛔ 측정 실패를 "작다 → light" 로 읽지 않는다 — git 실패 · 빈 diff 는 exit 2 UNRUN 이고 recommend 는 null 이다.

사용:
  mode_gate.py review   (--diff PATCH | --numstat FILE)               [--estimate WF]
  mode_gate.py peer     (--numstat FILE | --lines N --files N | --unmeasured) [--risk-json FILE] [--estimate WF]
  mode_gate.py plan     --read-scope LIST [--new-arch yes|no]           [--estimate WF]
  mode_gate.py code     (--steps STEPS_JSON | --plan-doc MD | --no-plan) [--estimate WF]
  mode_gate.py fix      --files N                                       [--estimate WF]
  mode_gate.py discover --complexity N                                  [--estimate WF]
  mode_gate.py lead-effort
  mode_gate.py --self-test

출력(stdout JSON 한 덩이): {skill, metrics, recommend: light|full|null, reasons[], effort, estimate}
  effort   = {value, source: transcript|env|none, note?, override?} — Workflow args.effort 로 넘길 값(value 가 null 이면 넘기지 않는다)
  estimate = {workflow, wall_median_min, n, approx} | null — full 이 더하는 Workflow 구간(이 환경의 최근 기록 · 근사)
exit: 0 성공 · 2 UNRUN 측정 불가(recommend null) · 10 입력 오류(인자 · 파일 없음)
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent

# ── 추천 임계 (정본) ──────────────────────────────────────────────────────────
# 리뷰 계열 — Workflow 시간은 입력 크기에 약하게만 반응한다. 그래서 임계는 시간이 아니라 "여러 렌즈가 볼 가치" 기준이다
REVIEW_LINES_FULL = 500     # 유효 줄(생성 파일 제외) — peer-review 의 비용 경고 경계와 같은 값
REVIEW_FILES_FULL = 20
PEER_RISK_FULL = 2          # risk_scan.py 의 위험 카테고리 수 — 승격 대입이 아니라 추천 근거
PLAN_FILES_FULL = 15        # readScope 파일 수
PLAN_MODULES_FULL = 3       # readScope 의 서로 다른 모듈(경로 앞 두 마디) 수
CODE_COMPLEXITY_FULL = 4    # Step complexity(1-5) 최댓값
CODE_STEPS_FULL = 10        # complexity 가 없을 때만 — Step 수만 보면 문서 위주 작업도 full 이 된다
FIX_FILES_FULL = 3
DISCOVER_COMPLEXITY_FULL = 4   # /fz 5차원 복잡도(modules/complexity.md) — 기존 TEAM 경계와 같은 값

GENERATED = re.compile(r"(package-lock|Package\.resolved|\.pbxproj|\.lock)")   # peer-review-tiers.md 의 생성 파일 정의와 같다
EFFORTS = ("low", "medium", "high", "xhigh", "max")
OK, UNRUN, BAD_INPUT = 0, 2, 10
ESTIMATE_SEC_DEFAULT = 20.0


class Unrun(Exception):
    pass


class BadInput(Exception):
    pass


# ── 크기 측정 ────────────────────────────────────────────────────────────────
def numstat_rows(text: str):
    rows = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        a, d, p = parts[0], parts[1], parts[2]
        rows.append((int(a) if a.isdigit() else 0, int(d) if d.isdigit() else 0, p))   # 바이너리는 '-' — 0 줄
    return rows


def size_of(rows) -> dict:
    files, lines, generated = set(), 0, 0
    for a, d, p in rows:
        files.add(p)
        if GENERATED.search(p):
            generated += a + d
        else:
            lines += a + d
    return {"files": len(files), "lines": lines, "generated_lines": generated}


def read_file(path: str) -> str:
    p = Path(path)
    if not p.exists() or p.is_dir():   # /dev/fd/N(프로세스 치환)도 받는다
        raise BadInput(f"파일이 없다: {path}")
    return p.read_text(encoding="utf-8", errors="replace")


def diff_size(patch: str) -> dict:
    read_file(patch)   # 없으면 입력 오류
    try:
        r = subprocess.run(["git", "apply", "--numstat", patch], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Unrun(f"git apply --numstat 실행 실패: {type(e).__name__}")
    if r.returncode != 0:
        raise Unrun(f"git apply --numstat exit {r.returncode}: {r.stderr.strip()[:200]}")
    rows = numstat_rows(r.stdout)
    if not rows:
        raise Unrun("빈 diff — 변경 0 이 아니라 확인 대상이다")
    return size_of(rows)


def numstat_size(path: str) -> dict:
    rows = numstat_rows(read_file(path))
    if not rows:
        raise Unrun("numstat 이 비었다 — 변경 0 이 아니라 확인 대상이다")
    return size_of(rows)


def module_of(p: str) -> str:
    parts = PurePosixPath(p.strip().lstrip("./")).parts
    return "/".join(parts[:2]) if len(parts) > 2 else (parts[0] if parts else "")


# ── 추천 ─────────────────────────────────────────────────────────────────────
def rec_review(m: dict, risk: int | None = None) -> tuple[str, list]:
    why = []
    if m["lines"] >= REVIEW_LINES_FULL:
        why.append(f"유효 {m['lines']}줄 ≥ {REVIEW_LINES_FULL}")
    if m["files"] >= REVIEW_FILES_FULL:
        why.append(f"파일 {m['files']} ≥ {REVIEW_FILES_FULL}")
    if risk is not None and risk >= PEER_RISK_FULL:
        why.append(f"위험 카테고리 {risk} ≥ {PEER_RISK_FULL}")
    if why:
        return "full", why
    tail = f" · 위험 카테고리 {risk}" if risk is not None else ""
    return "light", [f"유효 {m['lines']}줄 · 파일 {m['files']}{tail} — 임계 미만"]


def rec_plan(files: list, new_arch: bool) -> tuple[dict, str, list]:
    uniq = sorted({f.strip() for f in files if f.strip()})
    mods = sorted({module_of(f) for f in uniq if module_of(f)})
    m = {"files": len(uniq), "modules": len(mods), "new_architecture": new_arch}
    why = []
    if m["files"] >= PLAN_FILES_FULL:
        why.append(f"readScope 파일 {m['files']} ≥ {PLAN_FILES_FULL}")
    if m["modules"] >= PLAN_MODULES_FULL:
        why.append(f"모듈 {m['modules']} ≥ {PLAN_MODULES_FULL}")
    if new_arch:
        why.append("새 아키텍처 결정")
    if why:
        return m, "full", why
    return m, "light", [f"readScope 파일 {m['files']} · 모듈 {m['modules']} — 임계 미만"]


def rec_code(steps: list | None) -> tuple[dict, str, list]:
    if steps is None:
        return {"steps": 0, "max_complexity": None}, "light", ["승인 plan 없음 — 계획 없는 구현"]
    cx = [s.get("complexity") for s in steps if isinstance(s, dict) and isinstance(s.get("complexity"), (int, float))]
    m = {"steps": len(steps), "max_complexity": max(cx) if cx else None}
    if cx and max(cx) >= CODE_COMPLEXITY_FULL:
        return m, "full", [f"Step complexity 최댓값 {max(cx)} ≥ {CODE_COMPLEXITY_FULL}"]
    if not cx and len(steps) >= CODE_STEPS_FULL:
        return m, "full", [f"complexity 없음 · Step {len(steps)} ≥ {CODE_STEPS_FULL}"]
    basis = f"complexity 최댓값 {max(cx)}" if cx else "complexity 없음"
    return m, "light", [f"Step {len(steps)} · {basis} — 임계 미만"]


def load_steps(args) -> list | None:
    if args.no_plan:
        return None
    if args.steps:
        try:
            d = json.loads(read_file(args.steps))
        except json.JSONDecodeError as e:
            raise BadInput(f"steps JSON 을 읽지 못했다: {e}")
        steps = d.get("steps") if isinstance(d, dict) else d
        if not isinstance(steps, list):
            raise BadInput("steps JSON 에 steps 배열이 없다")
        return steps
    # 옛 plan-light.md 등 문서만 있을 때 — Step 머리 줄을 센다(complexity 는 없다)
    text = read_file(args.plan_doc)
    heads = re.findall(r"^#{2,4}\s*(?:S\d+[a-z]?\b|Step\s*\d+)", text, re.M)
    return [{} for _ in heads]


# ── Lead effort ──────────────────────────────────────────────────────────────
def last_transcript_effort(path: Path, tail_bytes: int = 4_000_000) -> str | None:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - tail_bytes))
            chunk = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    for line in reversed(chunk.splitlines()):
        if '"effort"' not in line or '"assistant"' not in line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "assistant" and ev.get("effort"):
            return ev["effort"]
    return None


def lead_effort(env=None, projects: Path | None = None) -> dict:
    """Workflow 워커에 넘길 Lead 세션 effort. 순서 = 세션 id 에 묶인 transcript 최신 assistant effort → env CLAUDE_EFFORT.

    ⛔ effort 를 생략하면 워커는 세션 값이 아니라 모델 기본(Opus 5.5 = medium)으로 돈다 — 그래서 값을 명시로 넘긴다.
    ⛔ CLAUDE_CODE_EFFORT_LEVEL 이 설정돼 있으면 그것이 콜 명시값보다 우선한다 — 워커 실효값이 그것임을 override 로 알린다.
    """
    env = os.environ if env is None else env
    sid = env.get("CLAUDE_CODE_SESSION_ID", "")
    t_val = None
    if re.fullmatch(r"[0-9A-Za-z-]{8,}", sid):
        root = projects or Path(env.get("HOME", str(Path.home()))) / ".claude" / "projects"
        for f in sorted(root.glob(f"*/{sid}.jsonl")):
            t_val = last_transcript_effort(f)
            if t_val:
                break
    e_raw = env.get("CLAUDE_EFFORT")
    e_val = e_raw if e_raw in EFFORTS else None
    if t_val in EFFORTS:
        out = {"value": t_val, "source": "transcript"}
        if e_val and e_val != t_val:
            out["note"] = f"transcript {t_val} ≠ env {e_val} — transcript 채택(그 턴의 실제 값)"
    elif e_val:
        out = {"value": e_val, "source": "env", "note": "transcript 판독 실패 — env 사용(세션 중 /effort 변경 반영 여부 미확인)"}
    else:
        out = {"value": None, "source": "none", "note": "출처 없음 — args.effort 를 넘기지 않는다(워크플로 미지정 = 'xhigh')"}
        if t_val or e_raw:
            out["note"] += f" · 알 수 없는 값 transcript={t_val!r} env={e_raw!r}"
    if env.get("CLAUDE_CODE_EFFORT_LEVEL"):
        out["override"] = env["CLAUDE_CODE_EFFORT_LEVEL"]
    return out


# ── 추정 (사용자 자신의 기록 · 근사) ───────────────────────────────────────────
def estimate(workflow: str, env=None) -> dict | None:
    env = os.environ if env is None else env
    reporter = env.get("FZ_MODE_GATE_REPORTER") or str(ROOT / "scripts" / "fz_telemetry_report.py")
    try:
        cap = float(env.get("FZ_MODE_GATE_ESTIMATE_SEC", ESTIMATE_SEC_DEFAULT))
    except ValueError:
        cap = ESTIMATE_SEC_DEFAULT
    with tempfile.TemporaryDirectory(prefix="fz-mode-gate-") as td:
        out = Path(td) / "report.json"
        try:
            subprocess.run([sys.executable, reporter, "--json", "--out", str(out)], capture_output=True,
                           timeout=cap, check=True)
            rows = json.loads(out.read_text(encoding="utf-8")).get("workflows") or []
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError, ValueError, AttributeError):
            return None   # 추정 실패는 진행을 막지 않는다 — 질문에 "실측 없음"
    approx = "full 이 더하는 Workflow 구간 · 에이전트 파일 mtime 차분 근사 · 이 환경 최근 30일"
    for r in rows:
        if isinstance(r, dict) and r.get("workflow") == workflow:
            return {"workflow": workflow, "wall_median_min": r.get("wall_median_min"), "n": r.get("wall_n") or 0, "approx": approx}
    return {"workflow": workflow, "wall_median_min": None, "n": 0, "approx": approx}


# ── 실행 ─────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="모드 게이트 — light / full 추천")
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="skill")
    for name in ("review", "peer", "plan", "code", "fix", "discover", "lead-effort"):
        s = sub.add_parser(name)
        if name != "lead-effort":
            s.add_argument("--estimate", metavar="WORKFLOW")
        if name == "review":
            g = s.add_mutually_exclusive_group(required=True)
            g.add_argument("--diff")
            g.add_argument("--numstat")
        elif name == "peer":
            # 측정은 호출자(peer-review-tiers.md 의 Gather 5.5 bash — PR 스냅샷 · gh · 브랜치 diff)가 하고 값만 넘길 수 있다
            g = s.add_mutually_exclusive_group(required=True)
            g.add_argument("--numstat")
            g.add_argument("--lines", type=int)
            g.add_argument("--unmeasured", action="store_true", help="호출자가 측정에 실패했다(BASE 부재 · diff 실패) — exit 2")
            s.add_argument("--files", type=int)
            s.add_argument("--risk-json")
        elif name == "plan":
            s.add_argument("--read-scope", required=True)
            s.add_argument("--new-arch", choices=("yes", "no"), default="no")
        elif name == "code":
            g = s.add_mutually_exclusive_group(required=True)
            g.add_argument("--steps")
            g.add_argument("--plan-doc")
            g.add_argument("--no-plan", action="store_true")
        elif name == "fix":
            s.add_argument("--files", type=int, required=True)
        elif name == "discover":
            s.add_argument("--complexity", type=int, required=True)
    return ap


def evaluate(argv: list, env=None) -> tuple[int, dict]:
    env = os.environ if env is None else env
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            args = build_parser().parse_args(argv)
    except SystemExit:
        msg = (err.getvalue().strip().splitlines() or ['mode_gate.py -h'])[-1]
        return BAD_INPUT, {"recommend": None, "reasons": [f"인자 오류 — {msg}"]}
    if not args.skill:
        return BAD_INPUT, {"recommend": None, "reasons": ["하위 명령이 없다 — mode_gate.py -h"]}
    eff = lead_effort(env)
    if args.skill == "lead-effort":
        return OK, {"skill": "lead-effort", "effort": eff}
    out = {"skill": args.skill, "metrics": {}, "recommend": None, "reasons": [], "effort": eff, "estimate": None}
    code = OK
    try:
        if args.skill == "review":
            m = diff_size(args.diff) if args.diff else numstat_size(args.numstat)
            out["metrics"], (out["recommend"], out["reasons"]) = m, rec_review(m)
        elif args.skill == "peer":
            if args.unmeasured:
                raise Unrun("호출자 측정 실패(BASE 부재 · diff 실패) — 변경량 0 으로 읽지 않는다")
            if args.lines is not None:
                if args.files is None or args.lines < 0 or args.files < 0:
                    raise BadInput("--lines 에는 0 이상의 --files 가 함께 필요하다")
                m = {"files": args.files, "lines": args.lines, "generated_lines": None}
            else:
                m = numstat_size(args.numstat)
            risk = None
            if args.risk_json:
                try:
                    risk = int(json.loads(read_file(args.risk_json)).get("risk"))
                except (ValueError, TypeError, AttributeError):
                    raise BadInput("risk JSON 에 정수 risk 가 없다")
            m["risk_categories"] = risk
            out["metrics"], (out["recommend"], out["reasons"]) = m, rec_review(m, risk)
        elif args.skill == "plan":
            files = read_file(args.read_scope).splitlines()
            out["metrics"], out["recommend"], out["reasons"] = rec_plan(files, args.new_arch == "yes")
        elif args.skill == "code":
            out["metrics"], out["recommend"], out["reasons"] = rec_code(load_steps(args))
        elif args.skill == "fix":
            out["metrics"] = {"files": args.files}
            full = args.files >= FIX_FILES_FULL
            out["recommend"] = "full" if full else "light"
            out["reasons"] = [f"수정 파일 {args.files} {'≥' if full else '<'} {FIX_FILES_FULL}"]
        elif args.skill == "discover":
            out["metrics"] = {"complexity": args.complexity}
            full = args.complexity >= DISCOVER_COMPLEXITY_FULL
            out["recommend"] = "full" if full else "light"
            out["reasons"] = [f"복잡도 {args.complexity} {'≥' if full else '<'} {DISCOVER_COMPLEXITY_FULL}"]
    except Unrun as e:
        code, out["recommend"], out["reasons"] = UNRUN, None, [f"UNRUN 측정 불가 — {e}"]
    except BadInput as e:
        code, out["recommend"], out["reasons"] = BAD_INPUT, None, [f"입력 오류 — {e}"]
    if code == OK and args.estimate:
        out["estimate"] = estimate(args.estimate, env)
    return code, out


def self_test() -> int:
    passed, total = 0, 0

    def check(name, cond, got=""):
        nonlocal passed, total
        total += 1
        if cond:
            passed += 1
        else:
            print(f"FAIL  {name} — {got}")

    with tempfile.TemporaryDirectory(prefix="fz-mode-gate-st-") as td:
        t = Path(td)
        base_env = {"HOME": str(t), "CLAUDE_CODE_SESSION_ID": "", "CLAUDE_EFFORT": ""}

        def w(name, text):
            (t / name).write_text(text, encoding="utf-8")
            return str(t / name)

        small = w("small.txt", "10\t2\ta.swift\n3\t0\tb.swift\n")
        big = w("big.txt", "400\t200\ta.swift\n")
        many = w("many.txt", "".join(f"1\t0\tf{i}.swift\n" for i in range(20)))
        gen = w("gen.txt", "600\t0\tPackage.resolved\n5\t1\ta.swift\n")
        risk2 = w("risk.json", json.dumps({"risk": 2, "tier_delta": 2}))
        empty = w("empty.patch", "")
        junk = w("junk.patch", "이것은 diff 가 아니다\n")
        c, o = evaluate(["review", "--numstat", small], base_env)
        check("작은 numstat → light", c == OK and o["recommend"] == "light", o)
        c, o = evaluate(["review", "--numstat", big], base_env)
        check("유효 600줄 → full", c == OK and o["recommend"] == "full", o)
        c, o = evaluate(["review", "--numstat", many], base_env)
        check("파일 20 → full", o["recommend"] == "full", o)
        c, o = evaluate(["review", "--numstat", gen], base_env)
        check("생성 파일 줄은 빼고 센다 → light", o["recommend"] == "light" and o["metrics"]["generated_lines"] == 600, o)
        c, o = evaluate(["peer", "--numstat", small, "--risk-json", risk2], base_env)
        check("peer 위험 카테고리 2 → full", o["recommend"] == "full", o)
        c, o = evaluate(["peer", "--lines", "120", "--files", "4"], base_env)
        check("peer 측정값 120줄 4파일 → light", c == OK and o["recommend"] == "light", o)
        c, o = evaluate(["peer", "--lines", "800", "--files", "4"], base_env)
        check("peer 측정값 800줄 → full", o["recommend"] == "full", o)
        c, o = evaluate(["peer", "--unmeasured"], base_env)
        check("peer 측정 불가 → exit 2 · recommend null", c == UNRUN and o["recommend"] is None, (c, o))
        c, o = evaluate(["peer", "--lines", "10"], base_env)
        check("peer --lines 에 --files 없음 → exit 10", c == BAD_INPUT, (c, o))
        c, o = evaluate(["review", "--diff", empty], base_env)
        check("빈 diff → exit 2 · recommend null", c == UNRUN and o["recommend"] is None, (c, o))
        c, o = evaluate(["review", "--diff", junk], base_env)
        check("diff 아님(git 실패) → exit 2", c == UNRUN and o["recommend"] is None, (c, o))
        c, o = evaluate(["review", "--numstat", str(t / "none.txt")], base_env)
        check("입력 파일 없음 → exit 10", c == BAD_INPUT and o["recommend"] is None, (c, o))
        c, o = evaluate(["nope"], base_env)
        check("모르는 하위 명령 → exit 10", c == BAD_INPUT, c)

        rs = w("rs.txt", "\n".join(f"skills/x/f{i}.md" for i in range(16)))
        rs3 = w("rs3.txt", "skills/a/SKILL.md\nmodules/b.md\nscripts/c.py\nworkflows/d.js\n")
        rs_small = w("rs_small.txt", "skills/a/SKILL.md\nskills/a/x.md\n")
        check("readScope 16 파일 → full", evaluate(["plan", "--read-scope", rs], base_env)[1]["recommend"] == "full")
        check("readScope 모듈 3+ → full", evaluate(["plan", "--read-scope", rs3], base_env)[1]["recommend"] == "full")
        check("새 아키텍처 → full", evaluate(["plan", "--read-scope", rs_small, "--new-arch", "yes"], base_env)[1]["recommend"] == "full")
        check("작은 readScope → light", evaluate(["plan", "--read-scope", rs_small], base_env)[1]["recommend"] == "light")

        st_cx = w("cx.json", json.dumps({"steps": [{"id": "S1", "complexity": 2}, {"id": "S2", "complexity": 4}]}))
        st_many = w("many.json", json.dumps({"steps": [{"id": f"S{i}"} for i in range(12)]}))
        st_few = w("few.json", json.dumps([{"id": f"S{i}"} for i in range(6)]))
        doc = w("plan-light.md", "## S1 a\n## S2 b\n### Step 3 c\n")
        check("complexity 4 → full", evaluate(["code", "--steps", st_cx], base_env)[1]["recommend"] == "full")
        check("complexity 없음 · Step 12 → full", evaluate(["code", "--steps", st_many], base_env)[1]["recommend"] == "full")
        check("complexity 없음 · Step 6 → light", evaluate(["code", "--steps", st_few], base_env)[1]["recommend"] == "light")
        c, o = evaluate(["code", "--plan-doc", doc], base_env)
        check("옛 plan 문서 Step 머리 3개", o["metrics"]["steps"] == 3 and o["recommend"] == "light", o)
        check("plan 없음 → light", evaluate(["code", "--no-plan"], base_env)[1]["recommend"] == "light")
        check("fix 파일 3 → full", evaluate(["fix", "--files", "3"], base_env)[1]["recommend"] == "full")
        check("discover 복잡도 4 → full · 3 → light",
              evaluate(["discover", "--complexity", "4"], base_env)[1]["recommend"] == "full"
              and evaluate(["discover", "--complexity", "3"], base_env)[1]["recommend"] == "light")

        proj = t / ".claude" / "projects" / "-x"
        proj.mkdir(parents=True)
        sid = "abcd1234-0000"
        (proj / f"{sid}.jsonl").write_text(
            json.dumps({"type": "assistant", "effort": "xhigh"}) + "\n" + json.dumps({"type": "user"}) + "\n"
            + json.dumps({"type": "assistant", "effort": "high"}) + "\n", encoding="utf-8")
        e = lead_effort({"HOME": str(t), "CLAUDE_CODE_SESSION_ID": sid, "CLAUDE_EFFORT": "xhigh"})
        check("transcript 최신 effort 1순위 + 불일치 기록", e["value"] == "high" and e["source"] == "transcript" and "note" in e, e)
        e = lead_effort({"HOME": str(t), "CLAUDE_CODE_SESSION_ID": "nosuch-session", "CLAUDE_EFFORT": "medium"})
        check("transcript 없음 → env", e["value"] == "medium" and e["source"] == "env", e)
        e = lead_effort({"HOME": str(t), "CLAUDE_CODE_SESSION_ID": "", "CLAUDE_EFFORT": "turbo"})
        check("출처 없음·불량 → value null", e["value"] is None and e["source"] == "none", e)
        e = lead_effort({"HOME": str(t), "CLAUDE_CODE_SESSION_ID": "", "CLAUDE_EFFORT": "high", "CLAUDE_CODE_EFFORT_LEVEL": "low"})
        check("CLAUDE_CODE_EFFORT_LEVEL → override 표시", e.get("override") == "low", e)

        fake = w("fake_reporter.py", "import json,sys\no=sys.argv[sys.argv.index('--out')+1]\n"
                 "json.dump({'workflows':[{'workflow':'review-live','wall_median_min':19.5,'wall_n':22}]},open(o,'w'))\n")
        slow = w("slow_reporter.py", "import time\ntime.sleep(5)\n")
        est = estimate("review-live", {"FZ_MODE_GATE_REPORTER": fake})
        check("추정 — 보고서에서 중앙값 · N", est and est["wall_median_min"] == 19.5 and est["n"] == 22, est)
        est = estimate("plan-lean2", {"FZ_MODE_GATE_REPORTER": fake})
        check("추정 — 기록 없는 워크플로는 N 0", est and est["n"] == 0 and est["wall_median_min"] is None, est)
        est = estimate("review-live", {"FZ_MODE_GATE_REPORTER": slow, "FZ_MODE_GATE_ESTIMATE_SEC": "1"})
        check("추정 — 상한 초과면 null", est is None, est)
    if passed != total:
        print(f"self-test {passed}/{total} passed")
        return 1
    print(f"self-test {passed}/{total} passed")
    return 0


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return self_test()
    code, out = evaluate(sys.argv[1:])
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if code != OK:
        print(out["reasons"][0] if out.get("reasons") else "실패", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
