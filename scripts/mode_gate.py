#!/usr/bin/env python3
# diff-parse: not-a-diff — diff 본문의 줄 접두사를 읽지 않는다. `git apply --numstat` 출력과 numstat 파일(추가·삭제·경로 탭 3열)만 센다
"""모드 게이트 — Workflow 를 띄우기 전에 작업 크기를 재서 light / full 추천과 근거를 낸다.

⛔ 왜 스크립트인가: 크기 조건이 산문에만 있으면 집행되지 않는다(fz-review light 의 '5파일·100LOC' 는 재는 코드가 없었다).
   추천 임계는 **이 파일이 정본**이다 — modules/mode-gate.md 는 언제 묻고 무엇을 보이는지(계약)를, 이 파일은 숫자를 가진다.
⛔ full 은 "큼 AND 복잡" 일 때만 추천한다 — 한 절만 채우면 light. 추천이 full 일 때만 묻고 light · 측정 불가는 묻지 않는다
   (언제 묻나 정본 modules/mode-gate.md). 임계는 초기값이고 실사용으로 고친다.
⛔ 측정 실패를 "작다 → light" 로 읽지 않는다 — git 실패 · 빈 diff 는 exit 2 UNRUN 이고 recommend 는 null 이다
   (호출자는 light 로 진행하되 '측정 불가' 를 통보한다 — 추천이 있었던 것처럼 적지 않는다).

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
# ⛔ review · peer · plan · code 는 full = 큼 AND 복잡(and_rule). 한 절만 크면 light — full 은 몇 배 느린데 품질 차이가
#    작았다(사용자 결정 2026-11-12 · OR 결합에서 peer 48건 중 15건이 full 추천 → AND 에서 1건)
REVIEW_LINES_FULL = 1000    # 큼 — 유효 줄(생성 파일 제외)
REVIEW_FILES_FULL = 20      # 복잡 — 넓게 퍼진 변경
PEER_RISK_FULL = 2          # 복잡 — risk_scan.py 의 위험 카테고리 수 · 승격 대입이 아니라 추천 근거
PLAN_FILES_FULL = 30        # 큼 — readScope 파일 수
PLAN_MODULES_FULL = 5       # 복잡 — readScope 의 서로 다른 모듈(경로 앞 두 마디) 수 · 새 아키텍처 결정도 복잡
CODE_COMPLEXITY_FULL = 4    # 복잡 — Step complexity(1-5) 최댓값
CODE_STEPS_FULL = 10        # 큼 — Step 수. complexity 가 없으면 복잡을 잴 수 없어 light(Step 수만 보면 문서 위주 작업도 full 이 된다)
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


def repo_relative(p: str) -> tuple[str, str] | None:
    """readScope 한 줄을 (저장소 루트, 루트 기준 상대경로)로 — 같은 파일을 절대 · 상대로 적어도 같은 모듈이 된다(F-586).

    절대경로는 가장 가까운 `.git`(폴더 · 파일 — 워크트리) 조상이 루트다. 못 찾으면 None(루트 불명). 상대경로의 루트는 "".
    ⛔ 입력 경로들의 공통 조상을 루트로 쓰지 않는다 — 그러면 같은 파일도 함께 적힌 경로에 따라 모듈 수가 달라진다.
    - Important: 입력 규약 — 상대경로 줄은 한 저장소 기준이고 다른 저장소는 절대경로로 적는다. 절대 루트가 하나면 상대경로를
      그 저장소로 읽는다. 절대 루트가 여럿인데 상대경로가 섞이면 어느 저장소인지 몰라 모듈 수를 미상으로 둔다(rec_plan).
      ⛔ cwd 로 풀지 않는다 — 같은 read-scope 가 실행 위치에 따라 다른 값을 낸다.
    """
    p = p.strip()
    if not p.startswith("/"):
        return "", p
    path = Path(p)
    for parent in path.parents:
        if (parent / ".git").exists():
            return str(parent), path.relative_to(parent).as_posix()
    return None


# ── 추천 ─────────────────────────────────────────────────────────────────────
def and_rule(big: tuple[bool, str], cx: tuple[bool, str]) -> tuple[str, list]:
    """full = 큼 AND 복잡. 두 절의 충족 여부를 모두 근거로 남긴다 — light 면 어느 절이 빠졌는지 보인다."""
    rec = "full" if big[0] and cx[0] else "light"
    return rec, [f"큼 {'충족' if big[0] else '미충족'} — {big[1]}", f"복잡 {'충족' if cx[0] else '미충족'} — {cx[1]}"]


def cmp(v, limit) -> str:
    return f"{v} {'≥' if v >= limit else '<'} {limit}"


def rec_review(m: dict, risk: int | None = None) -> tuple[str, list]:
    files_hit = m["files"] >= REVIEW_FILES_FULL
    risk_hit = risk is not None and risk >= PEER_RISK_FULL
    cx = [f"파일 {cmp(m['files'], REVIEW_FILES_FULL)}"] + ([f"위험 카테고리 {cmp(risk, PEER_RISK_FULL)}"] if risk is not None else [])
    return and_rule((m["lines"] >= REVIEW_LINES_FULL, f"유효 {m['lines']}줄 {'≥' if m['lines'] >= REVIEW_LINES_FULL else '<'} {REVIEW_LINES_FULL}"),
                    (files_hit or risk_hit, " · ".join(cx)))


def rec_plan(files: list, new_arch: bool) -> tuple[dict, str, list]:
    raw = [f.strip() for f in files if f.strip()]
    pairs = [repo_relative(f) for f in raw]
    # 루트가 하나면 절대 · 상대 표기를 하나로 합친다. 여럿이면 루트를 붙여 센다 — 다른 저장소의 같은 상대경로는 다른 파일이다
    multi = len({pr[0] for pr in pairs if pr and pr[0]}) > 1
    # 절대 루트가 여럿이면 상대경로는 귀속 불가(입력 규약 밖) — 절대경로의 같은 상대경로와 겹치면 별칭으로 보고 한 번만 센다
    abs_rels = {pr[1] for pr in pairs if pr and pr[0]}
    loose = multi and any(pr and not pr[0] for pr in pairs)
    uniq = {(pr if multi else pr[1]) if pr else f for f, pr in zip(raw, pairs) if not (multi and pr and not pr[0] and pr[1] in abs_rels)}
    mods = None if None in pairs or loose else len({(pr[0] if multi else "", module_of(pr[1])) for pr in pairs if module_of(pr[1])})
    m = {"files": len(uniq), "modules": mods, "new_architecture": new_arch}
    mod_hit = mods is not None and mods >= PLAN_MODULES_FULL
    why_none = ".git 없는 절대경로" if None in pairs else "절대 루트 여럿 + 상대경로 — 상대경로의 저장소"
    mod_txt = f"모듈 수 미상({why_none} — 루트 불명)" if mods is None else f"모듈 {cmp(mods, PLAN_MODULES_FULL)}"
    rec, why = and_rule((m["files"] >= PLAN_FILES_FULL, f"readScope 파일 {cmp(m['files'], PLAN_FILES_FULL)}"),
                        (mod_hit or new_arch, f"{mod_txt} · {'새 아키텍처 결정' if new_arch else '새 아키텍처 아님'}"))
    return m, rec, why


def rec_code(steps: list | None) -> tuple[dict, str, list]:
    if steps is None:
        return {"steps": 0, "max_complexity": None}, "light", ["승인 plan 없음 — 계획 없는 구현"]
    cx = [s.get("complexity") for s in steps if isinstance(s, dict) and isinstance(s.get("complexity"), (int, float))]
    m = {"steps": len(steps), "max_complexity": max(cx) if cx else None}
    if not cx:
        return m, "light", [f"Step {len(steps)} · complexity 없음 — 복잡을 잴 수 없어 light(Step complexity 는 fz-plan 이 싣는다)"]
    rec, why = and_rule((len(steps) >= CODE_STEPS_FULL, f"Step {cmp(len(steps), CODE_STEPS_FULL)}"),
                        (max(cx) >= CODE_COMPLEXITY_FULL, f"complexity 최댓값 {cmp(max(cx), CODE_COMPLEXITY_FULL)}"))
    return m, rec, why


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
        long1 = w("long1.txt", "800\t400\ta.swift\n")
        many = w("many.txt", "".join(f"1\t0\tf{i}.swift\n" for i in range(20)))
        wide = w("wide.txt", "".join(f"50\t0\tf{i}.swift\n" for i in range(20)))
        gen = w("gen.txt", "1200\t0\tPackage.resolved\n5\t1\ta.swift\n")
        risk2 = w("risk.json", json.dumps({"risk": 2, "tier_delta": 2}))
        empty = w("empty.patch", "")
        junk = w("junk.patch", "이것은 diff 가 아니다\n")
        c, o = evaluate(["review", "--numstat", small], base_env)
        check("작은 numstat → light", c == OK and o["recommend"] == "light", o)
        c, o = evaluate(["review", "--numstat", long1], base_env)
        check("유효 1200줄 · 1파일 → light(큼만)", c == OK and o["recommend"] == "light" and "복잡 미충족" in o["reasons"][1], o)
        c, o = evaluate(["review", "--numstat", many], base_env)
        check("파일 20 · 20줄 → light(복잡만)", o["recommend"] == "light" and "큼 미충족" in o["reasons"][0], o)
        c, o = evaluate(["review", "--numstat", wide], base_env)
        check("유효 1000줄 · 파일 20 → full", o["recommend"] == "full" and o["reasons"][0].startswith("큼 충족"), o)
        c, o = evaluate(["review", "--numstat", gen], base_env)
        check("생성 파일 줄은 빼고 센다 → light", o["recommend"] == "light" and o["metrics"]["generated_lines"] == 1200, o)
        c, o = evaluate(["peer", "--numstat", small, "--risk-json", risk2], base_env)
        check("peer 위험 2 · 작은 변경 → light", o["recommend"] == "light", o)
        c, o = evaluate(["peer", "--lines", "1000", "--files", "4", "--risk-json", risk2], base_env)
        check("peer 1000줄 · 위험 2 → full", o["recommend"] == "full", o)
        c, o = evaluate(["peer", "--lines", "120", "--files", "4"], base_env)
        check("peer 측정값 120줄 4파일 → light", c == OK and o["recommend"] == "light", o)
        c, o = evaluate(["peer", "--lines", "999", "--files", "25"], base_env)
        check("peer 999줄 · 25파일 → light(경계 직전)", o["recommend"] == "light", o)
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

        def plan(paths, arch="no"):
            return evaluate(["plan", "--read-scope", w(f"rs{len(paths)}-{arch}.txt", "\n".join(paths)), "--new-arch", arch], base_env)[1]

        one_mod = [f"skills/x/f{i}.md" for i in range(30)]
        five_mod = [f"pkg/m{i % 5}/f{i}.md" for i in range(30)]
        check("readScope 30 · 1모듈 → light(큼만)", plan(one_mod)["recommend"] == "light")
        check("readScope 30 · 5모듈 → full", plan(five_mod)["recommend"] == "full")
        check("readScope 30 · 새 아키텍처 → full", plan(one_mod, "yes")["recommend"] == "full")
        check("readScope 16 · 5모듈 · 새 아키텍처 → light(복잡만)", plan(five_mod[:16], "yes")["recommend"] == "light")
        repo = t / "repo"
        (repo / ".git").mkdir(parents=True)
        rel3 = ["skills/a/SKILL.md", "modules/b.md", "scripts/c.py"]
        o_abs = plan([str(repo / p) for p in rel3] + rel3)
        check("절대(.git 있음) · 상대 같은 파일 → 모듈 3 · 파일 3", o_abs["metrics"]["modules"] == 3 and o_abs["metrics"]["files"] == 3, o_abs)
        repo2 = t / "repo2"
        (repo2 / ".git").mkdir(parents=True)
        o_two = plan([str(repo / p) for p in rel3] + [str(repo2 / p) for p in rel3])
        check("두 저장소 같은 상대경로 → 파일 6 · 모듈 6", o_two["metrics"]["files"] == 6 and o_two["metrics"]["modules"] == 6, o_two)
        o_loose = plan([str(repo / p) for p in rel3] + [str(repo2 / p) for p in rel3] + rel3)
        check("절대 루트 둘 + 상대 별칭 → 파일 6 · 모듈 null(루트 불명)",
              o_loose["metrics"]["files"] == 6 and o_loose["metrics"]["modules"] is None and "루트 불명" in o_loose["reasons"][1], o_loose)
        o_nogit = plan([str(t / "norepo" / f"pkg/m{i % 5}/f{i}.md") for i in range(30)])
        check(".git 없는 절대경로 → 모듈 null · 새 아키텍처 아니면 light",
              o_nogit["metrics"]["modules"] is None and o_nogit["recommend"] == "light" and "루트 불명" in o_nogit["reasons"][1], o_nogit)
        check(".git 없는 절대경로 · 30 · 새 아키텍처 → full",
              plan([str(t / "norepo" / f"x/f{i}.md") for i in range(30)], "yes")["recommend"] == "full")

        def steps_file(n, cx=None, name="s"):
            return w(f"{name}.json", json.dumps({"steps": [dict({"id": f"S{i}"}, **({"complexity": cx} if cx else {})) for i in range(n)]}))

        doc = w("plan-light.md", "## S1 a\n## S2 b\n### Step 3 c\n")
        check("complexity 4 · Step 10 → full", evaluate(["code", "--steps", steps_file(10, 4, "c1")], base_env)[1]["recommend"] == "full")
        check("complexity 4 · Step 2 → light(복잡만)", evaluate(["code", "--steps", steps_file(2, 4, "c2")], base_env)[1]["recommend"] == "light")
        check("complexity 3 · Step 12 → light(큼만)", evaluate(["code", "--steps", steps_file(12, 3, "c3")], base_env)[1]["recommend"] == "light")
        check("complexity 없음 · Step 12 → light", evaluate(["code", "--steps", steps_file(12, None, "c4")], base_env)[1]["recommend"] == "light")
        check("배열 steps · Step 6 → light", evaluate(["code", "--steps", w("few.json", json.dumps([{"id": f"S{i}"} for i in range(6)]))], base_env)[1]["recommend"] == "light")
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
