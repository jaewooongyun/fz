#!/usr/bin/env python3
"""run_metrics.py — 스킬 실행 1회(시도 1회)를 한 줄로 남기는 기록기.

무엇을 남기나: 그 실행이 고른 모드 · 추천 · 실효 model · effort · 시작과 끝 · 완료 여부.
  light 경로는 Workflow journal 을 남기지 않아 `mode_gate.py --estimate` 가 그 시간을 보지 못했다 — 이 행이 그 빈칸을 채운다.
⛔ 프롬프트 · 트랜스크립트 본문 · 파일 본문 · 토큰 수는 담지 않는다. 행 키는 ROW_KEYS 밖으로 나가지 않는다.
⛔ 기록기는 스킬 실행을 깨지 않는다 — 기록 실패는 stderr `RUN_METRICS_UNAVAILABLE <사유>` + exit 0(`--strict` 면 1 · 테스트용).

저장 — ${FZ_RUN_STATE:-~/.fz/runs}/<pipeline_id>/
  runs.jsonl                    끝난 시도 1회 = 1행(append 전용 · 한 줄을 write 1회 + fsync · flock 안에서)
  open/<run_id>.<attempt>.json  시작했고 아직 끝나지 않은 시도의 표지
  .lock                         읽기-수정-쓰기 전부를 감싸는 flock
  pipeline_id = sha1(realpath(WORK_DIR))[:12] · WORK_DIR 이 없으면 sess-<세션 id 앞 12자> · 그것도 없으면 adhoc-<sha1(cwd)[:12]>
  run_id      = sha1(pipeline_id + skill)[:12] — 같은 WORK_DIR 의 같은 스킬은 다시 돌려도 같다(재개는 attempt 로 가른다)
읽는 쪽은 `fz_telemetry_report.py` 다(--runs-root · --runs-json · 리포트 「실행 기록」 절). 기본 경로 · schema · 상태 · 오래 열린 시도의
  기준은 두 파일에 같은 이름(DEFAULT_RUN_STATE · RUN_SCHEMA · RUN_STATUSES · RUN_OPEN_STALE_HOURS)으로 둔다 — 한쪽 이름을 grep 하면 다른 쪽이 보인다.

사용:
  run_metrics.py start --skill S --mode light|full --recommended light|full|none
                       [--source arg|fz|signal|autonomous|gate] [--work-dir W] [--reason TEXT]
  run_metrics.py end   --skill S [--work-dir W] --status completed|interrupted|failed [--workflow-run-id wf_x]
  run_metrics.py sweep [--older-than-hours N]
  공통 옵션: --projects-root DIR(기본 ~/.claude/projects — model · effort 판독) · --strict
  run_metrics.py --self-test

start  end 없이 남은 앞 시도의 표지를 status interrupted 1행으로 먼저 닫고 다음 attempt 의 표지를 연다.
       attempt = 1 + 그 run_id 의 끝난 행 수(번호가 비어 있으면 최대 attempt + 1). stdout `RUN <run_id> attempt <n>`.
end    열린 표지를 1행으로 닫는다. model = 세션 트랜스크립트의 마지막 assistant message.model ·
       effort = mode_gate.lead_effort 의 override(있으면) 또는 value. 트랜스크립트를 못 읽으면 둘 다 unknown(추측하지 않는다).
       같은 시도에 두 번 부르면 두 번째는 `RUN <run_id> already ended` 이고 행을 더 쓰지 않는다.
sweep  RUN_OPEN_STALE_HOURS(24) 시간보다 오래 열린 표지를 interrupted 로 닫는다. 아무도 닫지 않은 표지는 리포터가 「열린 채 남은 시도」로 센다.
자동으로 닫은 interrupted 행의 ended_at 은 null 이다 — 멈춘 시각을 모르므로 닫은 시각을 끝으로 쓰지 않는다.
--source · --reason 은 행 키가 아니라 reason(200자 이하) 한 칸에 `source=…` 로 들어간다.

exit: 0 기록 · no-op · 기록 불가(기본) / 1 기록 불가(--strict) · self-test 실패 / 2 인자 오류
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import functools
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent

RUN_SCHEMA = 1                          # fz_telemetry_report.py 와 같은 이름 · 같은 값 — 읽는 쪽은 이 schema 의 행만 센다
DEFAULT_RUN_STATE = "~/.fz/runs"        # 사용자 중립 기본값 — 개인 경로는 env FZ_RUN_STATE 로 (fz_telemetry_report.py 와 같은 이름 · 같은 값)
RUN_OPEN_STALE_HOURS = 24.0             # sweep 기본값 · 리포터의 '오래 열린 시도' 기준 — fz_telemetry_report.py 와 같은 이름 · 같은 값
RUN_STATUSES = ("completed", "interrupted", "failed")   # fz_telemetry_report.py 와 같은 이름 · 같은 값
DEFAULT_PROJECTS = "~/.claude/projects"
RUNS_FILE = "runs.jsonl"
OPEN_DIR = "open"
LOCK_FILE = ".lock"
LOCK_WAIT_SEC = 10.0                    # 넘으면 기록 불가로 물러난다 — 스킬을 기다리게 하지 않는다
TAIL_BYTES = 4_000_000                  # mode_gate.last_transcript_effort 와 같은 꼬리 크기
REASON_MAX = 200
UNKNOWN = "unknown"
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

MODES = ("light", "full")
RECOMMENDS = ("light", "full", "none")
SOURCES = ("arg", "fz", "signal", "autonomous", "gate")
# 행 키 허용 집합 — 이 밖의 키는 쓰지 않는다(원장 게이트가 그 밖의 키를 거부한다)
ROW_KEYS = ("schema", "run_id", "attempt", "pipeline_id", "skill", "mode", "recommended", "reason", "started_at",
            "ended_at", "status", "model", "effort", "session_id", "work_dir", "workflow_run_id", "plugin_root",
            "plugin_version", "plugin_sha")
MODEL_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:@/[]-")

SKILL_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
SID_RE = re.compile(r"[0-9A-Za-z][0-9A-Za-z-]{0,127}")
WF_RE = re.compile(r"wf_[0-9A-Za-z_-]{1,64}")
MARKER_RE = re.compile(r"([0-9a-f]{12})[.]([0-9]+)[.]json")
SHA_RE = re.compile(r"[0-9a-f]{40}")


class Unavailable(Exception):
    """기록할 수 없다 — main 이 stderr 한 줄 + exit 0 으로 바꾼다(스킬 실행은 계속된다)."""


# ── 식별자 ──────────────────────────────────────────────────────────────────
def now_iso() -> str:
    return datetime.now(timezone.utc).strftime(TS_FORMAT)


def state_root(env) -> Path:
    return Path(os.path.expanduser(env.get("FZ_RUN_STATE") or DEFAULT_RUN_STATE))


def session_of(env) -> str:
    sid = env.get("CLAUDE_CODE_SESSION_ID") or ""
    return sid if SID_RE.fullmatch(sid) else ""


def real_work_dir(work_dir):
    return os.path.realpath(os.path.expanduser(work_dir)) if work_dir else None


def pipeline_id(work_dir, env) -> str:
    wd = real_work_dir(work_dir)
    if wd:
        return hashlib.sha1(wd.encode("utf-8")).hexdigest()[:12]
    sid = session_of(env)
    if sid:
        return "sess-" + sid[:12]
    return "adhoc-" + hashlib.sha1(os.getcwd().encode("utf-8")).hexdigest()[:12]


def run_id_of(pid: str, skill: str) -> str:
    return hashlib.sha1((pid + skill).encode("utf-8")).hexdigest()[:12]


def is_model_id(value) -> bool:
    """합성 엔트리(`<synthetic>` · `<fallback>`)는 모델이 아니다 — 꺾쇠가 MODEL_CHARS 밖이라 걸러진다."""
    return isinstance(value, str) and 0 < len(value) <= 100 and value[0].isalnum() and set(value) <= MODEL_CHARS


# ── 저장 ────────────────────────────────────────────────────────────────────
@contextlib.contextmanager
def locked(pdir: Path):
    """pipeline 폴더의 .lock 에 배타 flock. LOCK_WAIT_SEC 안에 못 잡으면 Unavailable."""
    pdir.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(pdir / LOCK_FILE), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        deadline = time.monotonic() + LOCK_WAIT_SEC
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise Unavailable(f"lock busy over {LOCK_WAIT_SEC:.0f}s: {pdir / LOCK_FILE}")
                time.sleep(0.02)
        yield
    finally:
        os.close(fd)   # 닫으면 flock 도 풀린다


def read_rows(pdir: Path, run_id: str) -> list:
    """그 run_id 의 끝난 행. 깨진 줄은 건너뛴다(집계기가 센다). 파일 없음은 0행 · 그 밖의 읽기 실패는 올린다."""
    try:
        text = (pdir / RUNS_FILE).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return []
    rows = []
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("run_id") == run_id:
            rows.append(row)
    return rows


def attempts_of(rows) -> list:
    return [r["attempt"] for r in rows if type(r.get("attempt")) is int]


def append_row(pdir: Path, row: dict) -> None:
    """한 줄을 O_APPEND write 1회 + fsync 로 붙인다 — 동시 실행에서 줄이 섞이지 않는다(호출자가 lock 을 쥔다)."""
    data = (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    fd = os.open(str(pdir / RUNS_FILE), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        written = os.write(fd, data)
        if written != len(data):
            raise OSError(f"short write {written}/{len(data)}")
        os.fsync(fd)
    finally:
        os.close(fd)


def open_markers(pdir: Path, run_id=None) -> list:
    """[(attempt, run_id, path)] — attempt 오름차순. run_id 를 주면 그 run 의 표지만."""
    folder = pdir / OPEN_DIR
    if not folder.is_dir():
        return []
    found = []
    for path in folder.iterdir():
        m = MARKER_RE.fullmatch(path.name)
        if m and (run_id is None or m.group(1) == run_id):
            found.append((int(m.group(2)), m.group(1), path))
    return sorted(found, key=lambda t: (t[0], t[1]))


def write_marker(pdir: Path, marker: dict) -> None:
    folder = pdir / OPEN_DIR
    folder.mkdir(parents=True, exist_ok=True)
    final = folder / f"{marker['run_id']}.{marker['attempt']}.json"
    tmp = folder / f".{final.name}.tmp"
    tmp.write_text(json.dumps(marker, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(str(tmp), str(final))


def read_marker(path: Path) -> dict:
    """표지 → dict. 깨졌으면 빈 dict 에 파일 mtime 을 started_at 으로 — 그래도 행은 남긴다."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    if not isinstance(data, dict):
        data = {}
    if not isinstance(data.get("started_at"), str):
        with contextlib.suppress(OSError):
            data["started_at"] = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime(TS_FORMAT)
    return data


# ── 실효 model · effort ─────────────────────────────────────────────────────
def last_model(path: Path):
    """트랜스크립트 꼬리에서 마지막 assistant message.model. 없으면 None. 읽기 실패(OSError)는 올린다."""
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(0, size - TAIL_BYTES))
        chunk = fh.read().decode("utf-8", errors="replace")
    for line in reversed(chunk.splitlines()):
        if '"assistant"' not in line or '"model"' not in line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict) or event.get("type") != "assistant" or not isinstance(event.get("message"), dict):
            continue
        model = event["message"].get("model")
        if is_model_id(model):
            return model
    return None


def lead_effort_of(env, sid: str, projects: Path) -> str:
    """effort 판정의 정본은 형제 mode_gate.lead_effort 다 — 복제하지 않고 import 한다."""
    try:
        sys.dont_write_bytecode = True        # 플러그인 트리에 __pycache__ 를 남기지 않는다
        if str(SCRIPT_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPT_DIR))
        import mode_gate
        effort = mode_gate.lead_effort(dict(env, CLAUDE_CODE_SESSION_ID=sid), projects=projects)
    except Exception:  # noqa: BLE001 — effort 판독 실패는 unknown 이지 기록 실패가 아니다
        return UNKNOWN
    value = (effort.get("override") or effort.get("value")) if isinstance(effort, dict) else None
    return value if isinstance(value, str) and value else UNKNOWN


def model_and_effort(env, sid: str, projects_root: str):
    """(model, effort). 세션 id 가 없거나 트랜스크립트를 못 찾거나 못 읽으면 둘 다 unknown — 추측하지 않는다."""
    if not sid:
        return UNKNOWN, UNKNOWN
    projects = Path(os.path.expanduser(projects_root))
    for path in sorted(projects.glob(f"*/{sid}.jsonl")):
        try:
            model = last_model(path)
        except OSError:
            continue
        return model or UNKNOWN, lead_effort_of(env, sid, projects)
    return UNKNOWN, UNKNOWN


@functools.lru_cache(maxsize=1)
def plugin_info() -> tuple:
    """(plugin_root, plugin_version, plugin_sha|None).

    sha 는 plugin_root 가 git 작업 트리의 꼭대기일 때만 낸다 — 플러그인을 품은 상위 레포의 HEAD 를 빌리지 않는다.
    """
    version = None
    with contextlib.suppress(OSError, ValueError, AttributeError):
        value = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")).get("version")
        version = value if isinstance(value, str) else None
    sha = None
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        proc = subprocess.run(["git", "-C", str(PLUGIN_ROOT), "rev-parse", "--show-toplevel", "HEAD"],
                              capture_output=True, text=True, timeout=5)
        lines = proc.stdout.splitlines()
        if (proc.returncode == 0 and len(lines) == 2 and SHA_RE.fullmatch(lines[1])
                and os.path.realpath(lines[0]) == os.path.realpath(str(PLUGIN_ROOT))):
            sha = lines[1]
    return str(PLUGIN_ROOT), version, sha


# ── 행 ──────────────────────────────────────────────────────────────────────
def reason_text(source, reason):
    parts = []
    if source:
        parts.append(f"source={source}")
    if reason:
        parts.append(" ".join(str(reason).split()))
    text = " · ".join(parts)
    return text[:REASON_MAX] or None


def close_marker(pdir: Path, path: Path, run_id: str, attempt: int, status: str, ended_at, env, projects_root,
                 workflow_run_id=None, sid=None, skill=None):
    """열린 표지 1개 → 행 1개 append → 표지 삭제. 같은 (run_id, attempt) 행이 이미 있으면 표지만 지우고 None.

    호출자가 lock 을 쥔다. append 뒤 삭제 전에 죽으면 다음 호출이 이미 있는 행을 보고 표지만 지운다(중복 행 없음).
    """
    if attempt in attempts_of(read_rows(pdir, run_id)):
        path.unlink(missing_ok=True)
        return None
    marker = read_marker(path)
    sid = sid or (marker.get("session_id") if isinstance(marker.get("session_id"), str) else "")
    sid = sid if SID_RE.fullmatch(sid or "") else ""
    model, effort = model_and_effort(env, sid, projects_root)
    root, version, sha = plugin_info()
    row = {
        "schema": RUN_SCHEMA,
        "run_id": run_id,
        "attempt": attempt,
        "pipeline_id": pdir.name,
        "skill": marker.get("skill") or skill or UNKNOWN,
        "mode": marker.get("mode") or UNKNOWN,
        "recommended": marker.get("recommended") or UNKNOWN,
        "reason": reason_text(marker.get("source"), marker.get("reason")),
        "started_at": marker.get("started_at"),
        "ended_at": ended_at,
        "status": status,
        "model": model,
        "effort": effort,
        "session_id": sid or None,
        "work_dir": marker.get("work_dir"),
        "workflow_run_id": workflow_run_id,
        "plugin_root": root,
        "plugin_version": version,
        "plugin_sha": sha,
    }
    for optional in ("reason", "workflow_run_id", "plugin_sha"):
        if row[optional] is None:
            del row[optional]
    row = {k: row[k] for k in ROW_KEYS if k in row}
    append_row(pdir, row)
    path.unlink(missing_ok=True)
    return row


# ── 명령 ────────────────────────────────────────────────────────────────────
def cmd_start(args, env) -> int:
    pid = pipeline_id(args.work_dir, env)
    rid = run_id_of(pid, args.skill)
    pdir = state_root(env) / pid
    with locked(pdir):
        for attempt, _, path in open_markers(pdir, rid):   # end 없이 끝난 앞 시도 — 이번 start 는 재개다
            if close_marker(pdir, path, rid, attempt, "interrupted", None, env, args.projects_root, skill=args.skill):
                print(f"RUN {rid} attempt {attempt} interrupted")
        rows = read_rows(pdir, rid)
        attempt = 1 + max([len(rows)] + attempts_of(rows))
        marker = {"run_id": rid, "attempt": attempt, "skill": args.skill, "mode": args.mode,
                  "recommended": args.recommended, "source": args.source, "started_at": now_iso(),
                  "session_id": session_of(env) or None, "work_dir": real_work_dir(args.work_dir)}
        if args.reason:
            marker["reason"] = " ".join(args.reason.split())[:REASON_MAX]
        write_marker(pdir, marker)
    print(f"RUN {rid} attempt {attempt}")
    return 0


def cmd_end(args, env) -> int:
    pid = pipeline_id(args.work_dir, env)
    rid = run_id_of(pid, args.skill)
    pdir = state_root(env) / pid
    with locked(pdir):
        markers = open_markers(pdir, rid)
        if not markers:
            done = attempts_of(read_rows(pdir, rid))
            if not done:
                raise Unavailable(f"no open run for --skill {args.skill} (run {rid}) — start was not recorded")
            print(f"RUN {rid} already ended (attempt {max(done)})")
            return 0
        for attempt, _, path in markers[:-1]:   # start 가 앞 표지를 닫으므로 보통 없다
            close_marker(pdir, path, rid, attempt, "interrupted", None, env, args.projects_root, skill=args.skill)
        attempt, _, path = markers[-1]
        row = close_marker(pdir, path, rid, attempt, args.status, now_iso(), env, args.projects_root,
                           args.workflow_run_id, session_of(env), skill=args.skill)
    print(f"RUN {rid} attempt {attempt} {args.status}" if row else f"RUN {rid} already ended (attempt {attempt})")
    return 0


def marker_epoch(path: Path, marker: dict) -> float:
    with contextlib.suppress(TypeError, ValueError):
        return datetime.strptime(marker.get("started_at"), TS_FORMAT).replace(tzinfo=timezone.utc).timestamp()
    return path.stat().st_mtime


def cmd_sweep(args, env) -> int:
    root = state_root(env)
    cutoff = time.time() - args.older_than_hours * 3600.0
    closed = 0
    pdirs = sorted(p for p in root.iterdir() if (p / OPEN_DIR).is_dir()) if root.is_dir() else []
    for pdir in pdirs:
        with locked(pdir):
            for attempt, rid, path in open_markers(pdir):
                if marker_epoch(path, read_marker(path)) > cutoff:
                    continue
                if close_marker(pdir, path, rid, attempt, "interrupted", None, env, args.projects_root):
                    closed += 1
    print(f"SWEEP closed {closed}")
    return 0


COMMANDS = {"start": cmd_start, "end": cmd_end, "sweep": cmd_sweep}


# ── 인자 ────────────────────────────────────────────────────────────────────
def _matching(pattern, what: str):
    def check(value: str) -> str:
        if not pattern.fullmatch(value):
            raise argparse.ArgumentTypeError(f"{what} 형식이 아니다: {value!r}")
        return value
    return check


def _hours(value: str) -> float:
    try:
        hours = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"시간 수가 아니다: {value!r}")
    if hours < 0:
        raise argparse.ArgumentTypeError(f"0 이상이어야 한다: {value!r}")
    return hours


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="스킬 실행 기록기 — 시도 1회 = runs.jsonl 1행")
    ap.add_argument("--self-test", action="store_true")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--projects-root", default=DEFAULT_PROJECTS, help="세션 트랜스크립트 루트(model · effort 판독)")
    common.add_argument("--strict", action="store_true", help="기록 불가를 exit 1 로 낸다(테스트용)")
    sub = ap.add_subparsers(dest="cmd")
    skill = _matching(SKILL_RE, "스킬 이름")
    s = sub.add_parser("start", parents=[common], help="모드가 정해진 직후")
    s.add_argument("--skill", required=True, type=skill)
    s.add_argument("--mode", required=True, choices=MODES)
    s.add_argument("--recommended", required=True, choices=RECOMMENDS)
    s.add_argument("--source", choices=SOURCES)
    s.add_argument("--work-dir")
    s.add_argument("--reason")
    e = sub.add_parser("end", parents=[common], help="완료 보고 직전")
    e.add_argument("--skill", required=True, type=skill)
    e.add_argument("--work-dir")
    e.add_argument("--status", required=True, choices=RUN_STATUSES)
    e.add_argument("--workflow-run-id", type=_matching(WF_RE, "workflow runId(wf_…)"))
    w = sub.add_parser("sweep", parents=[common], help="오래 열린 표지를 interrupted 로 닫는다")
    w.add_argument("--older-than-hours", type=_hours, default=RUN_OPEN_STALE_HOURS)
    return ap


# ── self-test ───────────────────────────────────────────────────────────────
CANARY = "CANARY-7f3a-본문"   # 가짜 트랜스크립트의 프롬프트 · 본문에만 둔다 — 행에 나타나면 본문 복제다
STRIP_ENV = ("CLAUDE_CODE_EFFORT_LEVEL", "CLAUDE_EFFORT", "FZ_RUN_STATE", "CLAUDE_CODE_SESSION_ID")


def self_test() -> int:
    """case 마다 `<case>: PASS|FAIL <why>` 한 줄, 끝에 `run_metrics self-test: PASS|FAIL (k/n)`. case 마다 임시 FZ_RUN_STATE."""
    with tempfile.TemporaryDirectory(prefix="fz-run-metrics-st-") as td:
        base = Path(td)
        sid = "selftest-session-0001"
        projects = base / "projects"
        (projects / "-selftest").mkdir(parents=True)
        (projects / "-selftest" / f"{sid}.jsonl").write_text(
            json.dumps({"type": "user", "message": {"role": "user", "content": CANARY}}, ensure_ascii=False) + "\n"
            + json.dumps({"type": "assistant", "effort": "high",
                          "message": {"id": "m1", "model": "claude-selftest-model",
                                      "content": [{"type": "text", "text": CANARY}],
                                      "usage": {"input_tokens": 11, "output_tokens": 13}}}, ensure_ascii=False) + "\n"
            + json.dumps({"type": "assistant", "message": {"id": "m2", "model": "<synthetic>", "content": []}}) + "\n",
            encoding="utf-8")
        me = str(Path(__file__).resolve())

        def env_for(state):
            env = {k: v for k, v in os.environ.items() if k not in STRIP_ENV}
            env.update({"FZ_RUN_STATE": str(state), "CLAUDE_CODE_SESSION_ID": sid, "PYTHONDONTWRITEBYTECODE": "1"})
            return env

        def argv(*args, strict=True):
            return [sys.executable, "-B", me, *args, "--projects-root", str(projects)] + (["--strict"] if strict else [])

        def cli(state, *args, strict=True):
            proc = subprocess.run(argv(*args, strict=strict), env=env_for(state), capture_output=True, text=True,
                                  timeout=120, stdin=subprocess.DEVNULL)
            return proc.returncode, proc.stdout, proc.stderr

        def start(state, skill, wd, *extra, strict=True):
            return cli(state, "start", "--skill", skill, "--mode", "light", "--recommended", "light", "--source", "gate",
                       "--work-dir", str(wd), *extra, strict=strict)

        def end(state, skill, wd, strict=True):
            return cli(state, "end", "--skill", skill, "--work-dir", str(wd), "--status", "completed", strict=strict)

        def rows_of(state):
            rows, bad = [], 0
            for path in sorted(Path(state).glob(f"*/{RUNS_FILE}")):
                for line in path.read_text(encoding="utf-8").splitlines():
                    try:
                        row = json.loads(line)
                    except ValueError:
                        bad += 1
                        continue
                    if isinstance(row, dict):
                        rows.append(row)
                    else:
                        bad += 1
            return rows, bad

        def c_concurrent():
            st, wd, n = base / "s-concurrent", base / "wd-concurrent", 8
            errors = []
            for phase, extra in (("start", ("--mode", "light", "--recommended", "light", "--source", "gate")),
                                 ("end", ("--status", "completed"))):
                procs = [subprocess.Popen(argv(phase, "--skill", f"st-skill-{i}", "--work-dir", str(wd), *extra),
                                          env=env_for(st), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          text=True, stdin=subprocess.DEVNULL) for i in range(n)]
                for proc in procs:
                    _, err = proc.communicate(timeout=120)
                    if proc.returncode != 0:
                        errors.append(f"{phase} rc={proc.returncode} {err.strip()[-120:]}")
            rows, bad = rows_of(st)
            left = list(st.glob(f"*/{OPEN_DIR}/*.json"))
            run_ids = {r.get("run_id") for r in rows}
            pipelines = {r.get("pipeline_id") for r in rows}
            ok = (not errors and bad == 0 and len(rows) == n and len(run_ids) == n and len(pipelines) == 1 and not left
                  and all(r.get("attempt") == 1 and r.get("status") == "completed" for r in rows))
            return ok, f"rows={len(rows)} bad_lines={bad} run_ids={len(run_ids)} open={len(left)} errors={errors[:2]}"

        def c_duplicate_end():
            st, wd = base / "s-dup", base / "wd-dup"
            first, second, third = start(st, "fz-x", wd), end(st, "fz-x", wd), end(st, "fz-x", wd)
            rows, bad = rows_of(st)
            ok = ((first[0], second[0], third[0]) == (0, 0, 0) and "already ended" in third[1] and bad == 0
                  and len(rows) == 1 and rows[0].get("status") == "completed")
            return ok, f"rc={first[0]},{second[0]},{third[0]} rows={len(rows)} third={third[1].strip()!r} {third[2].strip()[-120:]}"

        def c_interrupted():
            st, wd = base / "s-int", base / "wd-int"
            first, second = start(st, "fz-x", wd), start(st, "fz-x", wd)
            rows, _ = rows_of(st)
            row = rows[0] if len(rows) == 1 else {}
            reopened = list(st.glob(f"*/{OPEN_DIR}/*.2.json"))
            got = [(r.get("attempt"), r.get("status")) for r in rows]
            ok = ((first[0], second[0]) == (0, 0) and len(rows) == 1 and row.get("status") == "interrupted"
                  and row.get("attempt") == 1 and row.get("ended_at") is None and len(reopened) == 1
                  and re.search(r"^RUN [0-9a-f]{12} attempt 2$", second[1], re.M) is not None)
            return ok, f"rc={first[0]},{second[0]} rows={got} open2={len(reopened)} out={second[1].strip()!r}"

        def c_write_failure():
            notes, ok = [], True
            blocker = base / "blocker"
            blocker.write_text("x", encoding="utf-8")
            roots = [("not-a-dir", blocker / "runs")]
            ro = base / "ro-root"
            if os.geteuid() != 0:   # root 는 0o555 폴더에도 쓴다 — 그때는 not-a-dir · append 만 판정한다
                ro.mkdir()
                ro.chmod(0o555)
                roots.append(("read-only", ro))
            try:
                for label, state in roots:
                    soft = start(state, "fz-x", base / "wd-wf", strict=False)
                    hard = start(state, "fz-x", base / "wd-wf", strict=True)
                    ok = (ok and soft[0] == 0 and hard[0] == 1
                          and all("RUN_METRICS_UNAVAILABLE" in res[2] for res in (soft, hard)))
                    notes.append(f"{label}: rc={soft[0]} strict rc={hard[0]}")
                state, wd = base / "s-append", base / "wd-append"
                opened = start(state, "fz-x", wd)
                for folder in state.glob(f"*/{OPEN_DIR}"):
                    (folder.parent / RUNS_FILE).mkdir()   # runs.jsonl 자리에 폴더 — end 의 읽기 · append 가 실패한다
                soft = end(state, "fz-x", wd, strict=False)
                ok = ok and opened[0] == 0 and soft[0] == 0 and "RUN_METRICS_UNAVAILABLE" in soft[2]
                notes.append(f"append: start rc={opened[0]} end rc={soft[0]}")
            finally:
                if ro.exists():
                    ro.chmod(0o755)
            return ok, " · ".join(notes)

        def c_no_body_copy():
            st, wd = base / "s-body", base / "wd-body"
            first = start(st, "fz-x", wd, "--reason", "긴 사유 " * 80)
            second = end(st, "fz-x", wd)
            rows, _ = rows_of(st)
            row = rows[0] if len(rows) == 1 else {}
            extra = sorted(set(row) - set(ROW_KEYS))
            blob = json.dumps(row, ensure_ascii=False)
            reason = row.get("reason") or ""
            ok = ((first[0], second[0]) == (0, 0) and len(rows) == 1 and not extra and 0 < len(reason) <= REASON_MAX
                  and reason.startswith("source=gate") and CANARY not in blob
                  and row.get("model") == "claude-selftest-model" and row.get("effort") == "high")
            return ok, (f"rows={len(rows)} extra={extra} reason_len={len(reason)} model={row.get('model')!r} "
                        f"effort={row.get('effort')!r} canary_copied={CANARY in blob}")

        def c_resume_attempt():
            st, wd = base / "s-resume", base / "wd-resume"
            outs = [start(st, "fz-x", wd), end(st, "fz-x", wd), start(st, "fz-x", wd), end(st, "fz-x", wd)]
            rows, _ = rows_of(st)
            got = sorted((r.get("attempt"), r.get("status")) for r in rows if type(r.get("attempt")) is int)
            run_ids = {r.get("run_id") for r in rows}
            ok = (all(o[0] == 0 for o in outs) and len(rows) == 2 and len(run_ids) == 1
                  and got == [(1, "completed"), (2, "completed")]
                  and re.search(r"^RUN [0-9a-f]{12} attempt 2$", outs[2][1], re.M) is not None)
            return ok, f"rc={[o[0] for o in outs]} rows={got} run_ids={len(run_ids)}"

        cases = (("concurrent", c_concurrent), ("duplicate-end", c_duplicate_end), ("interrupted", c_interrupted),
                 ("write-failure", c_write_failure), ("no-body-copy", c_no_body_copy), ("resume-attempt", c_resume_attempt))
        passed = 0
        for name, fn in cases:
            try:
                ok, why = fn()
            except Exception as exc:  # noqa: BLE001 — case 하나의 고장은 그 case 의 FAIL 이다
                ok, why = False, f"{type(exc).__name__}: {exc}"
            print(f"{name}: PASS" if ok else f"{name}: FAIL {why}")
            passed += 1 if ok else 0
    verdict = "PASS" if passed == len(cases) else "FAIL"
    print(f"run_metrics self-test: {verdict} ({passed}/{len(cases)})")
    return 0 if verdict == "PASS" else 1


# ── 실행 ────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)   # 인자 오류는 argparse 가 exit 2
    if args.self_test:
        return self_test()
    if not args.cmd:
        parser.print_usage(sys.stderr)
        return 2
    try:
        return COMMANDS[args.cmd](args, os.environ)
    except Unavailable as exc:
        why = str(exc)
    except Exception as exc:  # noqa: BLE001 — 기록기는 스킬 실행을 깨지 않는다(권한 · 디스크 오류 · 예상 밖 결함 모두)
        why = f"{type(exc).__name__}: {exc}"
    print(f"RUN_METRICS_UNAVAILABLE {why}", file=sys.stderr)
    return 1 if getattr(args, "strict", False) else 0


if __name__ == "__main__":
    sys.exit(main())
