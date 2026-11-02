#!/usr/bin/env python3
"""gpt_rounds.py — GPT 재검증 라운드 원장 판정기. 정본: modules/cross-validation.md § 재검증 라운드 상한.

정문 scripts/gpt-call.sh 가 호출자가 산출물 계열(env FZ_GPT_ARTIFACT)을 밝힌 호출마다 어댑터 직전에 `reserve`, EXIT 에서 `finish` 를
부른다. binary 규칙(상한 · 같은 입력 · 소비 여부 · 거부 때 옛 출력 보존)은 이 파일 한 곳에 있다 — 스킬 · 모듈은 횟수를 다시 적지 않는다.

키        산출물 계열(ARTIFACTS) × kind 계열(KIND_SLOTS) — 계열마다 상한은 FAMILY_CAP 한 곳에 있다
            verify 계열 — verify · verify-cross · modernize-verify · validate(본 슬롯) + verify-gates(게이트 슬롯)
            independent 계열 — independent-plan / contract 계열 — sprint-contract(작성 · modify 재확인)
단위      호출이 아니라 라운드다. 예약은 가장 최근 라운드에 그 슬롯이 비어 있으면 거기 들고(verify ∥ verify-gates 가 한 라운드),
          차 있으면 다음 라운드를 연다. 살아 있는 라운드 수가 상한에 닿았으면 거부한다(budget-exhausted — 미해결 · 통과 아님).
          상한은 라운드 번호가 아니라 개수로 잰다 — 실패로 빈 번호는 예산을 먹지 않는다
소비      정문 exit 0(유효 판정)만. 실패(10~17 · 그 밖) · 신호(128+N) · exit 18(GPT 미사용 — 실패 아님)은 슬롯을 비운다
같은 입력 같은 슬롯의 직전 유효 판정과 manifest 가 같고, 그 판정 파일(--out · --out-dir)이 끝맺을 때 남긴 해시 그대로이고,
          그 뒤 새 근거(evidence)가 없으면 거부한다(same-input — stderr · ROUND-PRIOR-OUT 에 그 파일). 이번 출력 경로가 그
          파일이면 ROUND-KEEP-OUT=1 — 정문은 옛 출력을 지우지 않는다(그 판정이 답이다). 판정 파일이 사라졌거나 바뀌었으면
          거부하지 않는다(다시 읽을 판정이 없다).
          manifest = kind · 산출물 버전(env FZ_GPT_ARTIFACT_VERSION) · 입력 파일 내용(FILE_INPUTS) · 검토 대상 코드(REPO_INPUTS 의
          git HEAD + 작업 트리 diff + 추적 안 된 파일 — 출력 경로 · 원장 제외). 코드만 바뀌어도 새 입력이다.
          일부를 못 읽거나 분류(FILE_INPUTS · REPO_INPUTS · SKIP_INPUTS) 밖 입력이 있으면 manifest 는 unknown 이고 같은 입력
          판정만 건너뛴다(상한은 그대로 센다)
재호출    env FZ_GPT_RECALL=post-check — verify-gates 사후 대조(gate_check.py --verdict-check) 실패 뒤 1회. 직전 게이트 판정의
          라운드를 잇고 라운드를 쓰지 않는다(라운드당 1회 — 넘으면 recall-used)

저장      WORK_DIR(--work-dir 또는 env FZ_WORK_DIR)이 있으면 {WORK_DIR}/gpt-rounds.json, 없으면
          ${FZ_RUN_STATE:-~/.fz/runs}/<pipeline_id>/gpt-rounds.json — 루트와 pipeline_id 는 run_metrics.state_root · pipeline_id 를
          그대로 쓴다. 발견 색인 ${FZ_RUN_STATE:-~/.fz/runs}/gpt-rounds-index.jsonl — 원장을 처음 만들 때 한 줄(status --all).
동시성    <원장>.lock flock 아래서 검사와 예약(끝맺음 · 근거 기록)만 원자적으로 한다. manifest 계산 · 끝맺음의 판정 파일 해시 ·
          어댑터 실행은 잠금 밖이다. 상태 reserved → completed | failed | aborted. 주인 프로세스가 죽었거나(같은 호스트)
          ORPHAN_STALE_HOURS 를 넘긴 예약은 다음 예약이 aborted(orphan)로 회수한다 — 정문이 KILL 로 죽어 EXIT 가 돌지 못한 경우다.
레지스트리 KIND_SLOTS 의 kind 와 그 입력 분류는 scripts/gpt-kinds.json 과 맞아야 한다 — self-test 가 case 앞에서 본다.

사용
  gpt_rounds.py reserve [--owner-pid PID] [--call-id ID] [--work-dir W] -- KIND [정문 입력...]
        stdout ROUND-LEDGER=<원장> · ROUND-SLOT=<id> · ROUND=<n> key=… — 세지 않는 kind 는 ROUND-UNTRACKED=<kind> 한 줄
        거부(19) stdout ROUND-REFUSED=<사유> [ROUND-PRIOR-OUT=<직전 판정 파일>] [ROUND-KEEP-OUT=1] — 정문이 읽는다
  gpt_rounds.py finish --ledger L --slot ID --rc N
  gpt_rounds.py evidence --new-evidence FILE --kind KIND [--artifact A] [--work-dir W]
  gpt_rounds.py status [--artifact A] [--work-dir W] [--all]
  gpt_rounds.py --self-test

exit: 0 예약 · 세지 않음 · 기록 / 10 사용법(산출물 계열 없음 · 모르는 값 · WORK_DIR 없음 · 재호출 대상 없음 · 슬롯 없음) /
      11 원장 판정 불가(손상 · 잠금 시간 초과 · 쓰기 실패 — 측정 실패 · 0건 아님) /
      19 거부 — stderr 'GPT-ROUNDS: <budget-exhausted|same-input|recall-used> — …'
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True                        # 형제 모듈 import 가 플러그인 트리에 __pycache__ 를 남기지 않는다
HERE = os.path.dirname(os.path.abspath(__file__))     # ⛔ abspath(realpath 아님) — 프록시 루트의 레지스트리 사본을 읽는다(gpt_kinds.py 와 같다)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import gpt_kinds    # noqa: E402 — 값 없는 정문 입력 · 레지스트리 읽기의 단일 출처: FLAG_INPUTS · load · Broken
import run_metrics  # noqa: E402 — 상태 루트 · pipeline_id · 시각의 단일 출처(같은 루트 · 같은 규칙을 다시 만들지 않는다)

LEDGER_SCHEMA = 1
LEDGER_FILE = "gpt-rounds.json"
INDEX_FILE = "gpt-rounds-index.jsonl"
LOCK_WAIT_SEC = 30.0            # 넘으면 11 — 원장을 판정하지 못한 채 GPT 를 부르지 않는다
ORPHAN_STALE_HOURS = 24.0       # 다른 호스트의 예약 · 주인 pid 를 확인할 수 없는 예약은 이 시간을 넘기면 고아다
GIT_TIMEOUT_SEC = 60
UNTRACKED_HASH_MAX = 4_000_000  # 추적 안 된 파일 하나를 내용으로 해시하는 상한 — 넘으면 크기 · mtime 으로 대신한다
DIFF_FLAGS = ("--binary", "--no-color", "--no-ext-diff", "--no-textconv")   # 사용자 diff 설정(외부 diff · textconv · 색)이 해시를 흔들지 않게
NUL = bytes(1)
ARTIFACTS = ("plan", "guide-plan", "code")
KIND_SLOTS = {   # kind → (계열, 슬롯). 여기 없는 kind 는 세지 않는다(ROUND-UNTRACKED) — 레지스트리와의 정렬은 self-test 가 본다
    "verify": ("verify", "main"), "verify-cross": ("verify", "main"), "modernize-verify": ("verify", "main"),
    "validate": ("verify", "main"), "verify-gates": ("verify", "gates"),
    "independent-plan": ("independent", "main"), "sprint-contract": ("contract", "main"),
}
FAMILY_CAP = {"verify": 3, "independent": 1, "contract": 2}   # 계열마다 누적 라운드 상한 — 정본 절 표와 같은 값
RECALL_ENV, RECALL_VALUE, RECALL_SLOT = "FZ_GPT_RECALL", "post-check", "gates"
LIVE = ("reserved", "completed")    # 라운드를 차지하는 상태 — failed · aborted 는 슬롯을 비운다
GPT_OFF = 18                        # 정문 exit 18 — GPT 미사용(실패 아님)
REFUSED = 19                        # 정문 exit 19 — 라운드 거부
# 정문 입력 분류 — 내용으로 드는 것 · 코드 스냅숏으로 드는 것 · 빼는 것. 세는 kind 의 입력은 셋 중 하나여야 한다(밖이면 manifest unknown)
FILE_INPUTS = {"prompt-file", "audit", "requirement", "sprint-contract", "rules-index", "diff", "pr-meta", "snapshot"}
REPO_INPUTS = {"cd", "repo"}
OUTPUT_INPUTS = {"out", "out-dir", "prompt-out"}
SKIP_INPUTS = OUTPUT_INPUTS | {"run-id", "arm", "deny", "keep-iso", "gpt-agents", "model", "effort", "timeout", "experimental"}
VERDICT_INPUTS = ("out", "out-dir")   # 판정이 놓이는 곳 — 래퍼 kind 는 --out · 독립 kind 는 --out-dir(앞이 우선)
SPEC_FIELDS = ("required", "optional", "repeatable", "flags", "experimental_only")   # 레지스트리 kinds.<K>.inputs 의 이름 목록들


class Usage(Exception):
    """호출 오류 — exit 10."""


class Broken(Exception):
    """원장을 판정할 수 없다 — exit 11(측정 실패 · 0건 아님)."""


class Unreadable(Exception):
    """manifest 의 일부를 읽지 못했거나 분류 밖 입력이다 — manifest 는 unknown 이고 같은 입력 판정만 건너뛴다."""


class Parser(argparse.ArgumentParser):
    """인자 오류도 10 이다 — 정문은 0 · 10 · 19 밖의 exit 를 11(원장 판정 실패)로 읽는다."""

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"GPT-ROUNDS-FAIL(10): {message}", file=sys.stderr)
        sys.exit(10)


# ── 정문 입력 · manifest ────────────────────────────────────────────────────
def flag_inputs() -> set:
    """값 없는 정문 입력 — resolver 와 같은 출처(gpt_kinds.FLAG_INPUTS · 레지스트리 inputs.flags)에서 읽는다."""
    try:
        reg = gpt_kinds.load()
    except gpt_kinds.Broken as exc:
        raise Broken(str(exc))
    flags = set(gpt_kinds.FLAG_INPUTS) | {"experimental"}
    for k in reg["kinds"].values():
        if isinstance(k, dict):
            flags |= set((k.get("inputs") or {}).get("flags") or [])
    return flags


def parse_call(tokens, flags) -> list:
    """정문 입력 → [(키, 값 | None)]. resolver 를 통과한 뒤에만 불리므로 형태만 본다."""
    pairs, i = [], 0
    while i < len(tokens):
        tok = tokens[i]
        if not tok.startswith("--") or "=" in tok:
            raise Usage(f"정문 입력 형태가 아니다: {tok!r}")
        key = tok[2:]
        if key in flags:
            pairs.append((key, None))
            i += 1
            continue
        if i + 1 >= len(tokens):
            raise Usage(f"--{key} 에 값이 없다")
        pairs.append((key, tokens[i + 1]))
        i += 2
    return pairs


def verdict_path(pairs):
    """판정이 놓이는 곳의 실경로 — VERDICT_INPUTS 순서로 첫 값. 없으면 None."""
    for want in VERDICT_INPUTS:
        for key, value in pairs:
            if key == want and value:
                return os.path.realpath(value)
    return None


def file_digest(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def path_digest(path: str) -> str:
    """파일은 내용 · 폴더는 (상대 경로, 내용) 목록의 해시. 없으면 Unreadable."""
    real = os.path.realpath(path)
    if os.path.isfile(real):
        return "file:" + file_digest(real)
    if os.path.isdir(real):
        h = hashlib.sha256()
        for top, dirs, files in os.walk(real):
            dirs.sort()
            for name in sorted(files):
                full = os.path.join(top, name)
                h.update(os.path.relpath(full, real).encode("utf-8", "surrogateescape") + NUL)
                h.update((file_digest(full) if os.path.isfile(full) else "special").encode("ascii") + NUL)
        return "dir:" + h.hexdigest()
    raise Unreadable(f"입력 경로가 없다: {path}")


def verdict_digest(path):
    """판정 파일(또는 --out-dir 폴더)의 해시 — 없거나 못 읽으면 None."""
    if not path:
        return None
    try:
        return path_digest(path)
    except (Unreadable, OSError):
        return None


def _git(top: str, *args: str) -> bytes:
    proc = subprocess.run(["git", "-C", top, *args], capture_output=True, timeout=GIT_TIMEOUT_SEC)
    if proc.returncode != 0:
        raise Unreadable(f"git {args[0]} exit {proc.returncode}: {proc.stderr.decode('utf-8', 'replace').strip()[:120]}")
    return proc.stdout


def excluded(real: str, exclude) -> bool:
    """exclude = [(경로, 묶음)] — 'stem' 은 그 경로로 시작하는 이름 전부(OUT · OUT.session · OUT.lock …) · 'tree' 는 그 폴더 아래."""
    for path, how in exclude:
        if real == path or real.startswith(path if how == "stem" else path + os.sep):
            return True
    return False


def excluded_spec(top: str, exclude) -> list:
    """diff 에도 같은 제외 — 추적 중인 출력 · 작업 폴더의 변경이 새 입력으로 읽히지 않게. literal 경로(폴더면 그 아래 전부)라
    'stem' 묶음은 그 파일 자체만 뺀다(OUT.session 같은 형제가 추적되는 경우는 다루지 않는다)."""
    specs = [f":(exclude,top,literal){rel}" for rel in (os.path.relpath(p, top) for p, _ in exclude)
             if rel != os.curdir and rel != os.pardir and not rel.startswith(os.pardir + os.sep)]
    return ["--", "."] + specs if specs else []


def code_digest(path: str, exclude) -> str:
    """검토 대상 코드 스냅숏 — HEAD · 작업 트리 diff(스테이징 포함) · 추적 안 된 파일(무시 규칙 밖 · 출력과 원장 제외)."""
    real = os.path.realpath(path)
    if not os.path.isdir(real):
        raise Unreadable(f"코드 폴더가 없다: {path}")
    probe = subprocess.run(["git", "-C", real, "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                           timeout=GIT_TIMEOUT_SEC)
    if probe.returncode != 0:
        return "nogit"      # git 작업 트리가 아니다 — 검토할 코드가 없는 호출(작업 폴더를 --cd 로 준 kind)
    top = os.path.realpath(probe.stdout.strip())
    h, spec = hashlib.sha256(), excluded_spec(top, exclude)
    head = subprocess.run(["git", "-C", top, "rev-parse", "--verify", "-q", "HEAD"], capture_output=True,
                          timeout=GIT_TIMEOUT_SEC)
    if head.returncode == 0:
        h.update(b"head " + head.stdout.strip() + NUL)
        h.update(_git(top, "diff", *DIFF_FLAGS, "HEAD", *spec))
    else:               # 커밋 없는 저장소 — 스테이징 + 작업 트리
        h.update(b"head none" + NUL)
        h.update(_git(top, "diff", *DIFF_FLAGS, "--cached", *spec))
        h.update(_git(top, "diff", *DIFF_FLAGS, *spec))
    for rel in sorted(x for x in _git(top, "ls-files", "-z", "--others", "--exclude-standard").split(NUL) if x):
        full = os.path.realpath(os.path.join(top, os.fsdecode(rel)))
        if excluded(full, exclude):
            continue
        h.update(b"untracked " + rel + NUL)
        try:
            st = os.stat(full)
            mark = file_digest(full) if st.st_size <= UNTRACKED_HASH_MAX else f"size {st.st_size} mtime {int(st.st_mtime)}"
        except OSError:
            mark = "unreadable"
        h.update(mark.encode("utf-8") + NUL)
    return "git:" + h.hexdigest()


def prior_outputs(ledger: Path):
    """원장의 모든 슬롯이 적은 판정 경로 — 저장소 안 --out 이 다음 라운드의 새 입력이 되지 않게. 잠금 밖에서 읽는다(원장은 rename 으로만
    바뀐다) — 아직 원장에 오르지 않은 병렬 호출의 --out 은 보지 못한다(그때는 새 입력으로 읽혀 거부 쪽이 아니라 새 라운드 쪽이다)."""
    data = read_ledger(ledger) or {}
    outs = {s.get("out") for k in (data.get("keys") or {}).values() for s in k.get("slots") or [] if s.get("out")}
    return [(os.path.realpath(o), "tree" if os.path.isdir(o) else "stem") for o in sorted(outs)]


def manifest_of(kind: str, pairs, env, ledger: Path):
    """→ (sha256 | None, 사유). 출력 경로 · 원장은 코드 스냅숏에서 뺀다 — 호출마다 바뀌는 파일이 새 입력으로 읽히지 않게.
    분류 밖 입력은 None(unknown)이다 — 경로 문자열만 해시하면 내용이 바뀐 정당한 재검증을 같은 입력으로 거부한다."""
    exclude = [(os.path.realpath(str(ledger)), "stem"), (os.path.realpath(str(ledger.parent / ("." + ledger.name))), "stem")]
    for key, value in pairs:
        if key in OUTPUT_INPUTS and value:
            exclude.append((os.path.realpath(value), "tree" if key == "out-dir" else "stem"))
        elif key == "deny" and value:      # 작업 폴더가 저장소 안이면 그 산출물(plan-v* 등)이 새 입력으로 읽히지 않게
            exclude.append((os.path.realpath(value), "tree" if os.path.isdir(value) else "stem"))
    exclude += prior_outputs(ledger)
    parts = []
    try:
        for key, value in pairs:
            if key in SKIP_INPUTS:
                continue
            if value is None or key not in (FILE_INPUTS | REPO_INPUTS):
                raise Unreadable(f"분류 밖 입력 --{key} — FILE_INPUTS · REPO_INPUTS · SKIP_INPUTS 중 하나에 넣는다")
            parts.append([key, path_digest(value) if key in FILE_INPUTS else code_digest(value, exclude)])
    except (Unreadable, OSError, subprocess.SubprocessError) as exc:
        return None, " ".join(f"{type(exc).__name__}: {exc}".split())
    body = {"kind": kind, "version": env.get("FZ_GPT_ARTIFACT_VERSION") or "", "inputs": sorted(parts)}
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(), ""


def registry_drift(reg) -> list:
    """세는 kind · 입력 분류가 레지스트리와 맞는가 → 어긋남 목록(빈 목록 = 맞다).
    KIND_SLOTS ⊆ 레지스트리 kind(이름이 바뀌면 조용히 ROUND-UNTRACKED 가 된다) ·
    세는 kind 의 입력 ⊆ FILE_INPUTS ∪ REPO_INPUTS ∪ SKIP_INPUTS(분류 밖 입력은 manifest 를 unknown 으로 만든다)."""
    kinds = reg.get("kinds") if isinstance(reg, dict) else None
    if not isinstance(kinds, dict):
        return ["레지스트리에 kinds 가 없다"]
    known = FILE_INPUTS | REPO_INPUTS | SKIP_INPUTS
    drift = []
    for name in sorted(KIND_SLOTS):
        k = kinds.get(name)
        if not isinstance(k, dict):
            drift.append(f"KIND_SLOTS 의 {name} 이 레지스트리에 없다")
            continue
        spec = k.get("inputs") if isinstance(k.get("inputs"), dict) else {}
        names = set()
        for field in SPEC_FIELDS:
            value = spec.get(field) or []
            names |= set(value) if isinstance(value, list) else {f"<{field} 형식 오류>"}
        drift += [f"{name} 의 입력 --{key} 가 분류 밖이다" for key in sorted(names - known)]
    return drift


# ── 원장 ────────────────────────────────────────────────────────────────────
def ledger_location(work_dir, env):
    """→ (원장 경로, pipeline_id, WORK_DIR 실경로 | None). WORK_DIR 이 없으면 run_metrics 와 같은 루트 · 같은 pipeline_id."""
    wd = work_dir or env.get("FZ_WORK_DIR") or ""
    if wd:
        real = run_metrics.real_work_dir(wd)
        if not os.path.isdir(real):
            raise Usage(f"WORK_DIR 가 폴더가 아니다: {wd}")
        return Path(real) / LEDGER_FILE, run_metrics.pipeline_id(real, env), real
    pid = run_metrics.pipeline_id(None, env)
    return Path(os.path.abspath(str(run_metrics.state_root(env) / pid / LEDGER_FILE))), pid, None


@contextlib.contextmanager
def locked(ledger: Path):
    """원장 단위 배타 flock — 검사 + 예약(또는 끝맺음 · 근거 기록)만 이 안에서 한다. 어댑터 실행은 밖이다.
    run_metrics.locked 와 같은 꼴이다 — 잠금 파일(<원장>.lock) · 대기(LOCK_WAIT_SEC) · 예외(Broken → 11)만 다르다."""
    ledger.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(ledger) + ".lock", os.O_RDWR | os.O_CREAT, 0o644)
    try:
        deadline = time.monotonic() + LOCK_WAIT_SEC
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise Broken(f"원장 잠금을 {LOCK_WAIT_SEC:.0f}초 안에 잡지 못했다: {ledger}.lock")
                time.sleep(0.02)
        yield
    finally:
        os.close(fd)   # 닫으면 flock 도 풀린다


def read_ledger(ledger: Path):
    """원장 dict · 없으면 None. 깨졌으면 Broken — 고쳐 쓰지 않는다(센 기록을 잃는다)."""
    try:
        text = ledger.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise Broken(f"원장이 JSON 이 아니다: {ledger}: {exc}")
    if not isinstance(data, dict) or data.get("schema") != LEDGER_SCHEMA or not isinstance(data.get("keys"), dict):
        raise Broken(f"원장 형식이 아니다(schema {LEDGER_SCHEMA}): {ledger}")
    return data


def load_or_new(ledger: Path):
    data = read_ledger(ledger)
    if data is None:
        return {"schema": LEDGER_SCHEMA, "seq": 0, "created_at": run_metrics.now_iso(), "keys": {}}, True
    return data, False


def write_ledger(ledger: Path, data: dict) -> None:
    """같은 폴더 임시 파일 + fsync + rename — 잠금 밖 읽기(status · finish 의 해시 준비)도 반쯤 쓴 원장을 보지 않는다."""
    tmp = ledger.parent / f".{ledger.name}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(str(tmp), str(ledger))


def index_add(env, ledger: Path, pid: str, work_dir) -> None:
    """발견 색인에 한 줄 — WORK_DIR 없는 실행의 원장도 status --all 로 찾는다.
    run_metrics.append_row 와 같은 꼴(한 줄을 O_APPEND write 1회 + 짧은 쓰기 확인 + fsync)이다 — 파일 이름만 다르다.
    색인은 원장마다 다른 잠금 아래서 여러 원장이 붙이므로 write 1회가 줄 섞임을 막는다. 색인 실패는 예약을 막지 않는다(경고)."""
    root = run_metrics.state_root(env)
    row = {"schema": LEDGER_SCHEMA, "pipeline_id": pid, "ledger": str(ledger), "work_dir": work_dir,
           "created_at": run_metrics.now_iso()}
    data = (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    try:
        root.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(root / INDEX_FILE), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            written = os.write(fd, data)
            if written != len(data):
                raise OSError(f"short write {written}/{len(data)}")
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as exc:
        print(f"GPT-ROUNDS-WARN: 발견 색인 기록 실패({type(exc).__name__}: {exc}) — 원장은 {ledger}", file=sys.stderr)


def next_seq(data: dict) -> int:
    data["seq"] = int(data.get("seq") or 0) + 1
    return data["seq"]


def key_of(data: dict, artifact: str, family: str):
    name = f"{artifact}/{family}"
    k = data["keys"].setdefault(name, {"artifact": artifact, "family": family, "cap": FAMILY_CAP[family]})
    for field in ("slots", "evidence", "refusals"):
        if not isinstance(k.get(field), list):
            k[field] = []
    return name, k


def find_slot(data, sid):
    return next((s for k in (data.get("keys") or {}).values() for s in k.get("slots") or [] if s.get("id") == sid), None)


def artifact_of(explicit, env) -> str:
    value = explicit or env.get("FZ_GPT_ARTIFACT") or ""
    if value not in ARTIFACTS:
        raise Usage(f"산출물 계열 {value!r} — {' · '.join(ARTIFACTS)} 중 하나다(env FZ_GPT_ARTIFACT 또는 --artifact)")
    return value


def pid_alive(pid) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:     # 권한 없음 등 — 살아 있다고 본다(남의 예약을 회수하지 않는 쪽)
        return True
    return True


def recover_orphans(data: dict) -> int:
    """주인 프로세스가 죽은(같은 호스트) 또는 ORPHAN_STALE_HOURS 를 넘긴 reserved 를 aborted 로 — 슬롯을 비운다."""
    host, now, n = socket.gethostname(), time.time(), 0
    for k in data["keys"].values():
        for s in k.get("slots") or []:
            if s.get("state") != "reserved":
                continue
            dead = s.get("host") == host and not pid_alive(s.get("owner_pid"))
            stale = now - float(s.get("reserved_epoch") or 0) > ORPHAN_STALE_HOURS * 3600
            if dead or stale:
                s.update(state="aborted", reason="orphan" if dead else "orphan-stale", ended_at=run_metrics.now_iso(),
                         ended_seq=next_seq(data))
                n += 1
    return n


def verdict_intact(slot) -> bool:
    """끝맺을 때 남긴 판정 파일 해시와 지금이 같은가 — 같아야 '그 판정이 그대로다'가 참이다."""
    recorded = slot.get("out_digest")
    return bool(recorded) and verdict_digest(slot.get("out")) == recorded


def plan_reservation(k: dict, slot: str, manifest, recall: bool, out_real):
    """→ (라운드, None) 또는 (None, 거부 dict{reason, detail[, prior_out, keep_out]}). 원장 잠금 안에서만 부른다."""
    live = [s for s in k["slots"] if s.get("state") in LIVE]
    done = [s for s in k["slots"] if s.get("slot") == slot and s.get("state") == "completed"]
    if recall:
        firsts = [s for s in done if not s.get("recall")]
        if not firsts:
            raise Usage(f"{RECALL_ENV}={RECALL_VALUE}: 이 키에 끝난 {slot} 판정이 없다 — 다시 부를 대상이 없다")
        rnd = max(firsts, key=lambda s: s.get("ended_seq") or 0)["round"]
        if any(s.get("recall") and s.get("round") == rnd and s.get("slot") == slot for s in live):
            return None, {"reason": "recall-used", "detail": f"라운드 {rnd} 의 사후 대조 재호출은 이미 했다(라운드당 1회)"}
        return rnd, None
    last = max(done, key=lambda s: s.get("ended_seq") or 0) if done else None
    if manifest and last and last.get("manifest") == manifest and verdict_intact(last):
        if not any((e.get("seq") or 0) > (last.get("ended_seq") or 0) for e in k["evidence"]):
            prior = last.get("out")
            return None, {"reason": "same-input", "prior_out": prior, "keep_out": bool(out_real) and out_real == prior,
                          "detail": f"라운드 {last.get('round')} 의 {last.get('kind')} 판정과 입력이 같고 그 뒤 새 근거가 없다 — 그 판정({prior})이 그대로다"}
    rounds = sorted({s["round"] for s in live})
    latest = rounds[-1] if rounds else 0
    if latest and not any(s["round"] == latest and s.get("slot") == slot and not s.get("recall") for s in live):
        return latest, None
    cap = FAMILY_CAP[k["family"]]
    if len(rounds) >= cap:      # 번호가 아니라 개수 — 실패로 빈 번호는 예산을 먹지 않는다(status rounds_used 와 같은 기준)
        prior = last.get("out") if last else None      # 마지막 판정 = 미해결 보고의 근거 — 같은 --out 이면 정문이 지우지 않는다
        return None, {"reason": "budget-exhausted", "prior_out": prior, "keep_out": bool(out_real) and out_real == prior,
                      "detail": f"누적 {cap} 라운드를 다 썼다 — 미해결로 보고한다(통과 아님) · 마지막 판정 {prior or '없음'}"}
    return latest + 1, None


def outcome(rc: int):
    """정문 exit → (상태, 사유). 0 만 라운드를 쓴다."""
    if rc == 0:
        return "completed", None
    if rc == GPT_OFF:
        return "aborted", "gpt-off"
    if rc >= 128:
        return "aborted", f"signal-{rc - 128}"
    return "failed", f"exit-{rc}"


def summarize(data: dict, artifact=None) -> dict:
    out = {}
    for name, k in sorted((data.get("keys") or {}).items()):
        if artifact and not name.startswith(artifact + "/"):
            continue
        slots, refusals = k.get("slots") or [], k.get("refusals") or []
        rounds = {}
        for s in slots:
            rounds.setdefault(str(s.get("round")), []).append(f"{s.get('kind')}:{s.get('state')}" + (":recall" if s.get("recall") else ""))
        out[name] = {"cap": FAMILY_CAP.get(k.get("family")),
                     "rounds_used": len({s.get("round") for s in slots if s.get("state") in LIVE}),
                     "rounds": rounds, "evidence": len(k.get("evidence") or []),
                     "refusals": [f"{r.get('reason')}:{r.get('kind')}" for r in refusals],
                     "unresolved": any(r.get("reason") == "budget-exhausted" for r in refusals)}
    return out


# ── 명령 ────────────────────────────────────────────────────────────────────
def cmd_reserve(args, call, env) -> int:
    if not call:
        raise Usage("reserve 뒤에 `-- KIND [정문 입력...]` 이 없다")
    kind, tokens = call[0], call[1:]
    artifact = artifact_of(None, env)
    if kind not in KIND_SLOTS:
        print(f"ROUND-UNTRACKED={kind}")
        return 0
    family, slot = KIND_SLOTS[kind]
    recall_raw = env.get(RECALL_ENV) or ""
    if recall_raw and (recall_raw != RECALL_VALUE or slot != RECALL_SLOT):
        raise Usage(f"{RECALL_ENV}={recall_raw!r} — kind verify-gates 의 '{RECALL_VALUE}' 만 받는다")
    recall = bool(recall_raw)
    pairs = parse_call(tokens, flag_inputs())
    out_real = verdict_path(pairs)
    ledger, pid, wd = ledger_location(args.work_dir, env)
    manifest, note = manifest_of(kind, pairs, env, ledger)      # 잠금 밖 — git 명령이 원장 잠금을 쥐지 않게
    owner = args.owner_pid if args.owner_pid is not None else os.getppid()
    sid = ""
    with locked(ledger):
        data, created = load_or_new(ledger)
        recover_orphans(data)
        name, k = key_of(data, artifact, family)
        rnd, refusal = plan_reservation(k, slot, manifest, recall, out_real)
        if refusal:
            k["refusals"].append({"seq": next_seq(data), "kind": kind, "reason": refusal["reason"], "manifest": manifest,
                                  "at": run_metrics.now_iso()})
        else:
            sid = secrets.token_hex(6)
            k["slots"].append({"id": sid, "kind": kind, "slot": slot, "round": rnd, "recall": recall, "state": "reserved",
                               "manifest": manifest, "manifest_note": note or None, "out": out_real,
                               "artifact_version": env.get("FZ_GPT_ARTIFACT_VERSION") or None,
                               "owner_pid": owner, "host": socket.gethostname(), "call_id": args.call_id,
                               "reserved_at": run_metrics.now_iso(), "reserved_epoch": time.time(),
                               "reserved_seq": next_seq(data)})
        write_ledger(ledger, data)
        if created:
            index_add(env, ledger, pid, wd)
    if refusal:
        print(f"ROUND-REFUSED={refusal['reason']}")
        if refusal.get("prior_out"):
            print(f"ROUND-PRIOR-OUT={refusal['prior_out']}")
        if refusal.get("keep_out"):
            print("ROUND-KEEP-OUT=1")
        print(f"GPT-ROUNDS: {refusal['reason']} — {name} {kind}: {refusal['detail']} · 원장 {ledger} · "
              "정본 modules/cross-validation.md § 재검증 라운드 상한", file=sys.stderr)
        return REFUSED
    print(f"ROUND-LEDGER={ledger}")
    print(f"ROUND-SLOT={sid}")
    print(f"ROUND={rnd} key={name} slot={slot} cap={FAMILY_CAP[family]}" + (" recall" if recall else "")
          + ("" if manifest else f" manifest=unknown({note})"))
    return 0


def cmd_finish(args, env) -> int:
    ledger = Path(os.path.abspath(args.ledger))
    digest = None
    if args.rc == 0:    # 판정 파일 해시는 잠금 밖에서 — 원장은 rename 으로만 바뀌므로 잠금 밖 읽기도 온전한 판을 본다
        pre = read_ledger(ledger)
        found = find_slot(pre, args.slot) if pre else None
        digest = verdict_digest(found.get("out")) if found else None
    with locked(ledger):
        data = read_ledger(ledger)
        if data is None:
            raise Usage(f"원장이 없다: {ledger}")
        slot = find_slot(data, args.slot)
        if slot is None:
            raise Usage(f"원장에 슬롯 {args.slot} 이 없다: {ledger}")
        late = slot.get("state") != "reserved"
        if late:            # 고아로 회수된 뒤 늦게 끝났다 — 상태는 바꾸지 않고 rc 만 남긴다
            slot["late_rc"] = args.rc
        else:
            state, reason = outcome(args.rc)
            slot.update(state=state, rc=args.rc, reason=reason, out_digest=digest if state == "completed" else None,
                        ended_at=run_metrics.now_iso(), ended_seq=next_seq(data))
        write_ledger(ledger, data)
    if late:
        print(f"GPT-ROUNDS-WARN: 슬롯 {args.slot} 은 이미 {slot.get('state')}({slot.get('reason')}) — 늦은 끝맺음 rc {args.rc} 는 기록만 한다",
              file=sys.stderr)
    print(f"ROUND-FINISH={slot.get('state')}" + (f" ({slot.get('reason')})" if slot.get("reason") else "") + (" late" if late else ""))
    return 0


def cmd_evidence(args, env) -> int:
    artifact = artifact_of(args.artifact, env)
    if args.kind not in KIND_SLOTS:
        raise Usage(f"--kind {args.kind!r} 는 세는 kind 가 아니다({', '.join(sorted(KIND_SLOTS))})")
    path = os.path.realpath(args.new_evidence)
    if not os.path.isfile(path):
        raise Usage(f"--new-evidence 파일이 없다: {args.new_evidence}")
    digest = file_digest(path)
    ledger, pid, wd = ledger_location(args.work_dir, env)
    seq = 0
    with locked(ledger):
        data, created = load_or_new(ledger)
        name, k = key_of(data, artifact, KIND_SLOTS[args.kind][0])
        dup = next((e for e in k["evidence"] if e.get("sha256") == digest), None)
        if dup is None:
            seq = next_seq(data)
            k["evidence"].append({"seq": seq, "file": path, "sha256": digest, "kind": args.kind, "at": run_metrics.now_iso()})
            write_ledger(ledger, data)
            if created:
                index_add(env, ledger, pid, wd)
    if dup is not None:
        print(f"ROUND-EVIDENCE={dup.get('seq')} key={name} duplicate — 같은 내용의 근거는 재라운드를 다시 열지 않는다")
        return 0
    print(f"ROUND-EVIDENCE={seq} key={name} sha256={digest[:12]}")
    return 0


def cmd_status(args, env) -> int:
    if args.all:
        index = run_metrics.state_root(env) / INDEX_FILE
        try:
            lines = index.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            lines = []
        rows, seen = [], set()
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            path = row.get("ledger") if isinstance(row, dict) else None
            if not isinstance(path, str) or path in seen:
                continue
            seen.add(path)
            try:
                data = read_ledger(Path(path))
                rows.append({"ledger": path, "pipeline_id": row.get("pipeline_id"),
                             "keys": summarize(data, args.artifact) if data else {}})
            except (Broken, OSError) as exc:
                rows.append({"ledger": path, "pipeline_id": row.get("pipeline_id"), "error": str(exc)})
        print(json.dumps({"index": str(index), "ledgers": rows}, ensure_ascii=False, indent=1, sort_keys=True))
        return 0
    ledger, _, _ = ledger_location(args.work_dir, env)
    data = read_ledger(ledger)
    print(json.dumps({"ledger": str(ledger), "keys": summarize(data, args.artifact) if data else {}},
                     ensure_ascii=False, indent=1, sort_keys=True))
    return 0


COMMANDS = {"finish": cmd_finish, "evidence": cmd_evidence, "status": cmd_status}


def build_parser() -> argparse.ArgumentParser:
    ap = Parser(prog="gpt_rounds.py", description="GPT 재검증 라운드 원장 — 정본 modules/cross-validation.md § 재검증 라운드 상한")
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("reserve", help="어댑터 직전 — 검사 + 슬롯 예약(정문이 부른다) · 정문 입력은 `--` 뒤")
    r.add_argument("--owner-pid", type=int, help="예약 주인 pid(기본 부모 프로세스 — 정문)")
    r.add_argument("--call-id", help="정문 호출 id(gpt-calls.tsv 와 잇는다)")
    r.add_argument("--work-dir", help="WORK_DIR(기본 env FZ_WORK_DIR)")
    f = sub.add_parser("finish", help="어댑터 뒤 — 끝맺음(정문 EXIT 가 부른다)")
    f.add_argument("--ledger", required=True)
    f.add_argument("--slot", required=True)
    f.add_argument("--rc", required=True, type=int)
    e = sub.add_parser("evidence", help="Lead 가 새 근거를 남긴다 — 같은 입력의 재라운드를 연다(상한은 열지 않는다)")
    e.add_argument("--new-evidence", required=True, metavar="FILE")
    e.add_argument("--kind", required=True)
    e.add_argument("--artifact", choices=ARTIFACTS)
    e.add_argument("--work-dir")
    s = sub.add_parser("status", help="원장 요약 JSON — 키마다 rounds_used · unresolved")
    s.add_argument("--artifact", choices=ARTIFACTS)
    s.add_argument("--work-dir")
    s.add_argument("--all", action="store_true", help="발견 색인의 원장 전부")
    return ap


# ── self-test ───────────────────────────────────────────────────────────────
SELFTEST_STRIP = ("FZ_GPT_ARTIFACT", "FZ_GPT_ARTIFACT_VERSION", "FZ_WORK_DIR", RECALL_ENV, "FZ_RUN_STATE", "CLAUDE_CODE_SESSION_ID")


def self_test() -> int:
    """레지스트리 정렬을 먼저 본다(어긋날 때만 `registry-alignment: FAIL …` 한 줄). case 마다 `<case>: PASS|FAIL <why>` 한 줄,
    이어서 `self-test N/M passed` 와 `gpt_rounds self-test: PASS|FAIL`. case 마다 임시 WORK_DIR · FZ_RUN_STATE."""
    try:
        drift = registry_drift(gpt_kinds.load())
    except gpt_kinds.Broken as exc:
        drift = [f"레지스트리를 읽지 못했다: {exc}"]
    if drift:
        print(f"registry-alignment: FAIL {' · '.join(drift)[:400]}")
    me = os.path.abspath(__file__)
    results = []
    with tempfile.TemporaryDirectory(prefix="fz-gpt-rounds-st-") as td:
        base = Path(os.path.realpath(td))

        def world(case):
            root = base / case
            for sub in ("wd", "code", "in", "out"):
                (root / sub).mkdir(parents=True, exist_ok=True)
            env = {k: v for k, v in os.environ.items() if k not in SELFTEST_STRIP}
            env.update({"FZ_RUN_STATE": str(root / "runs"), "FZ_WORK_DIR": str(root / "wd"), "FZ_GPT_ARTIFACT": "plan",
                        "PYTHONDONTWRITEBYTECODE": "1"})
            return root, env

        def write(root, name, text):
            path = root / "in" / name
            path.write_text(text, encoding="utf-8")
            return str(path)

        def argv(*args):
            return [sys.executable, "-B", me, *args]

        def cli(env, *args):
            proc = subprocess.run(argv(*args), env=env, cwd=str(base), capture_output=True, text=True, timeout=120,
                                  stdin=subprocess.DEVNULL)
            return proc.returncode, proc.stdout, proc.stderr

        def lines_of(out):
            got = {}
            for line in out.splitlines():
                key, sep, value = line.partition("=")
                if sep and key not in got:
                    got[key] = value
            return got

        def round_of(got):
            return (got.get("ROUND", "").split() or [""])[0]

        def reserve(env, call, owner=None):
            """→ (rc, stdout KEY=VALUE, stderr)"""
            head = ["reserve"] + (["--owner-pid", str(owner)] if owner is not None else [])
            rc, out, err = cli(env, *head, "--", *call)
            return rc, lines_of(out), err

        def stub_verdict(call):
            """어댑터 대신 판정 파일을 쓴다 — 끝맺음이 그 해시를 남긴다(같은 입력 거부의 전제)."""
            for flag in VERDICT_INPUTS:
                if ("--" + flag) in call:
                    path = Path(call[call.index("--" + flag) + 1])
                    if flag == "out-dir":
                        path.mkdir(parents=True, exist_ok=True)
                        path = path / "result.json"
                    path.write_text(json.dumps({"stub": secrets.token_hex(4)}), encoding="utf-8")
                    return

        def run(env, call, rc_after=0):
            """예약 → (rc_after 0 이면 판정 파일) → 끝맺음 → (예약 rc, 라운드, stdout KEY=VALUE, stderr)"""
            rc, got, err = reserve(env, call)
            if rc == 0 and got.get("ROUND-SLOT"):
                if rc_after == 0:
                    stub_verdict(call)
                cli(env, "finish", "--ledger", got.get("ROUND-LEDGER", ""), "--slot", got["ROUND-SLOT"], "--rc", str(rc_after))
            return rc, round_of(got), got, err

        def vcall(root, kind, prompt, tag, code=None):
            return [kind, "--cd", str(code or root / "code"), "--out", str(root / "out" / f"{tag}.json"), "--prompt-file", prompt]

        def slots_of(root, key):
            return json.loads((root / "wd" / LEDGER_FILE).read_text(encoding="utf-8"))["keys"][key]["slots"]

        def c_cap3():
            root, env = world("cap")
            got, failed = [], []
            for n in (1, 2, 3):
                p, g = write(root, f"p{n}.md", f"계획 판 {n}"), write(root, f"g{n}.md", f"원장 판 {n}")
                if n == 2:   # 스키마 위반(14) · GPT 미사용(18)은 라운드를 쓰지 않는다 — 같은 라운드 번호를 다시 받는다
                    for bad in (14, GPT_OFF):
                        rc, rnd, _, _ = run(env, vcall(root, "verify", p, f"bad{bad}"), rc_after=bad)
                        failed.append(f"{rc}:{rnd}")
                v = run(env, vcall(root, "verify", p, f"v{n}"))
                gt = run(env, vcall(root, "verify-gates", g, f"g{n}"))
                got.append((v[0], v[1], gt[0], gt[1]))
            fourth = run(env, vcall(root, "verify", write(root, "p4.md", "계획 판 4"), "v4"))
            ok = (got == [(0, "1", 0, "1"), (0, "2", 0, "2"), (0, "3", 0, "3")] and failed == ["0:2", "0:2"]
                  and fourth[0] == REFUSED and fourth[2].get("ROUND-REFUSED") == "budget-exhausted" and "budget-exhausted" in fourth[3])
            return ok, f"rounds={got} failed-calls={failed} fourth=rc{fourth[0]} {fourth[3].strip()[:160]}"

        def c_same_input():
            root, env = world("same")
            repo = root / "repo"
            repo.mkdir()
            (repo / "src.txt").write_text("v1", encoding="utf-8")
            for cmd in (["git", "init", "-q"], ["git", "add", "-f", "src.txt"]):
                proc = subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True, timeout=60)
                if proc.returncode != 0:
                    return False, f"{' '.join(cmd[:2])} 실패(측정 불가): {proc.stderr.strip()[:120]}"
            p = write(root, "p.md", "같은 계획")
            a = run(env, vcall(root, "verify", p, "a", code=repo))
            b = run(env, vcall(root, "verify", p, "b", code=repo))     # 같은 프롬프트 · 같은 코드 · 판정 파일 그대로 · 새 근거 없음 → 거부(다른 --out)
            (repo / "src.txt").write_text("v2", encoding="utf-8")       # 코드만 바뀌었다 → 새 입력
            c = run(env, vcall(root, "verify", p, "c", code=repo))
            d = run(env, vcall(root, "verify", p, "c", code=repo))     # 같은 --out 으로 다시 → 거부 + 옛 판정 보존 신호
            e_rc, e_out, _ = cli(env, "evidence", "--new-evidence", write(root, "evidence.md", "Lead 의 새 근거"), "--kind", "verify")
            e = run(env, vcall(root, "verify", p, "e", code=repo))     # 새 근거 뒤 → 같은 입력이어도 연다
            env_code = dict(env, FZ_GPT_ARTIFACT="code")                # 판정 파일이 사라지면 같은 입력이어도 연다(다른 키)
            f1 = run(env_code, vcall(root, "verify", p, "f1", code=repo))
            os.remove(str(root / "out" / "f1.json"))
            f2 = run(env_code, vcall(root, "verify", p, "f2", code=repo))
            env_g = dict(env, FZ_GPT_ARTIFACT="guide-plan")             # --out 이 저장소 안 — 직전 판정 파일이 새 입력이 되면 안 된다
            g1 = run(env_g, ["verify", "--cd", str(repo), "--out", str(repo / "verdict-g1.json"), "--prompt-file", p])
            g2 = run(env_g, ["verify", "--cd", str(repo), "--out", str(repo / "verdict-g2.json"), "--prompt-file", p])
            wdin = repo / "wdin"                                        # 작업 폴더(--deny)가 저장소 안 — 그 산출물은 입력이 아니다
            wdin.mkdir()
            (wdin / "plan-v1.md").write_text("Lead 의 첫 판", encoding="utf-8")
            proc = subprocess.run(["git", "add", "-f", "wdin/plan-v1.md"], cwd=str(repo), capture_output=True, text=True, timeout=60)
            if proc.returncode != 0:
                return False, f"git add 실패(측정 불가): {proc.stderr.strip()[:120]}"

            def ind(run_id):
                return ["independent-plan", "--requirement", p, "--repo", str(repo), "--deny", str(wdin), "--arm", "gpt",
                        "--run-id", run_id, "--out-dir", str(root / "out" / run_id)]
            q1 = run(env_g, ind("q1"))
            (wdin / "plan-v2.md").write_text("Lead 가 쓴 다음 판", encoding="utf-8")      # 미추적 산출물
            (wdin / "plan-v1.md").write_text("Lead 가 고친 첫 판", encoding="utf-8")      # 추적 중인 산출물의 변경(diff 쪽)
            q2 = run(env_g, ind("q2"))
            a_out = str(root / "out" / "a.json")
            ok = (a[:2] == (0, "1")
                  and b[0] == REFUSED and b[2].get("ROUND-REFUSED") == "same-input" and b[2].get("ROUND-PRIOR-OUT") == a_out
                  and "ROUND-KEEP-OUT" not in b[2]
                  and c[:2] == (0, "2")
                  and d[0] == REFUSED and d[2].get("ROUND-REFUSED") == "same-input" and d[2].get("ROUND-KEEP-OUT") == "1"
                  and e_rc == 0 and "ROUND-EVIDENCE=" in e_out and e[:2] == (0, "3")
                  and f1[:2] == (0, "1") and f2[:2] == (0, "2")
                  and g1[:2] == (0, "1") and g2[0] == REFUSED and g2[2].get("ROUND-REFUSED") == "same-input"
                  and q1[:2] == (0, "1") and q2[0] == REFUSED and q2[2].get("ROUND-REFUSED") == "same-input")
            return ok, (f"a={a[:2]} b=rc{b[0]}/{b[2].get('ROUND-KEEP-OUT')} c={c[:2]} d=rc{d[0]}/{d[2].get('ROUND-KEEP-OUT')} "
                        f"evidence=rc{e_rc} e={e[:2]} f1={f1[:2]} f2={f2[:2]} g1={g1[:2]} g2=rc{g2[0]}/{g2[2].get('ROUND-REFUSED')} "
                        f"q1={q1[:2]} q2=rc{q2[0]}/{q2[2].get('ROUND-REFUSED')} {(b[3] + d[3]).strip()[:160]}")

        def c_budget():
            root, env = world("budget")
            r1, r2 = write(root, "req1.md", "요구 1"), write(root, "req2.md", "요구 2")

            def ind(req, run_id):
                return ["independent-plan", "--requirement", req, "--arm", "gpt", "--run-id", run_id,
                        "--out-dir", str(root / "out" / run_id)]

            first = run(env, ind(r1, "a"), rc_after=12)   # 통신 실패 — 라운드를 쓰지 않는다
            second = run(env, ind(r1, "b"))
            third = run(env, ind(r2, "c"))                # 입력이 달라도 independent 계열 상한을 넘는다 — 미해결로 남는다
            s_rc, s_out, _ = cli(env, "status")
            try:
                key = json.loads(s_out)["keys"]["plan/independent"]
            except (ValueError, KeyError, TypeError):
                key = {}
            ok = (first[:2] == (0, "1") and second[:2] == (0, "1") and third[0] == REFUSED
                  and third[2].get("ROUND-REFUSED") == "budget-exhausted" and "budget-exhausted" in third[3]
                  and s_rc == 0 and key.get("unresolved") is True and key.get("rounds_used") == 1)
            return ok, f"first={first[:2]} second={second[:2]} third=rc{third[0]} status=rc{s_rc} key={key}"

        def c_lock_reserve():
            root, env = world("lock")
            for n in (1, 2):
                run(env, vcall(root, "verify", write(root, f"p{n}.md", f"계획 {n}"), f"v{n}"))
            racers = [argv("reserve", "--", *vcall(root, "verify", write(root, f"race{i}.md", f"경합 {i}"), f"r{i}"))
                      for i in range(6)]
            procs = [subprocess.Popen(a, env=env, cwd=str(base), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, stdin=subprocess.DEVNULL) for a in racers]
            raced = []
            for proc in procs:
                out, err = proc.communicate(timeout=120)
                got = lines_of(out)
                raced.append((proc.returncode, round_of(got), got, err))
            winners = [r[:2] for r in raced if r[0] == 0]
            losers = [r for r in raced if r[0] == REFUSED and r[2].get("ROUND-REFUSED") == "budget-exhausted"]
            # 이긴 슬롯은 아직 reserved(끝맺지 않음) — 잠금을 쥐지 않으므로 같은 라운드의 게이트 슬롯이 곧바로 든다
            g_rc, g_got, g_err = reserve(env, vcall(root, "verify-gates", write(root, "g.md", "원장"), "g"))
            rounds = sorted({s["round"] for s in slots_of(root, "plan/verify") if s.get("state") in LIVE})
            ok = (winners == [(0, "3")] and len(losers) == len(racers) - 1 and (g_rc, round_of(g_got)) == (0, "3")
                  and rounds == [1, 2, 3])
            return ok, (f"winners={winners} losers={len(losers)}/{len(racers) - 1} gates=({g_rc},{round_of(g_got)}) "
                        f"rounds={rounds} {g_err.strip()[:120]}")

        def c_orphan():
            root, env = world("orphan")
            dead = subprocess.Popen([sys.executable, "-c", "pass"])
            dead.wait()
            first = reserve(env, vcall(root, "verify", write(root, "p1.md", "계획 1"), "o1"), owner=dead.pid)
            second = reserve(env, vcall(root, "verify", write(root, "p2.md", "계획 2"), "o2"), owner=os.getpid())
            third = reserve(env, vcall(root, "verify", write(root, "p3.md", "계획 3"), "o3"), owner=os.getpid())
            orphan = next((s for s in slots_of(root, "plan/verify") if s.get("id") == first[1].get("ROUND-SLOT")), {})
            ok = ((first[0], round_of(first[1])) == (0, "1") and orphan.get("state") == "aborted"
                  and orphan.get("reason") == "orphan" and (second[0], round_of(second[1])) == (0, "1")
                  and (third[0], round_of(third[1])) == (0, "2"))
            return ok, (f"first=({first[0]},{round_of(first[1])}) orphan={orphan.get('state')}/{orphan.get('reason')} "
                        f"second=({second[0]},{round_of(second[1])}) third=({third[0]},{round_of(third[1])})")

        for name, fn in (("cap-3", c_cap3), ("same-input-stop", c_same_input), ("budget-exhausted", c_budget),
                         ("lock-reserve", c_lock_reserve), ("orphan-recovery", c_orphan)):
            try:
                ok, why = fn()
            except Exception as exc:  # noqa: BLE001 — case 하나의 고장은 그 case 의 FAIL 이다
                ok, why = False, f"{type(exc).__name__}: {exc}"
            print(f"{name}: PASS" if ok else f"{name}: FAIL {why}")
            results.append(ok)
    print(f"self-test {sum(results)}/{len(results)} passed")
    if results and all(results) and not drift:
        print("gpt_rounds self-test: PASS")
        return 0
    print(f"gpt_rounds self-test: FAIL ({sum(results)}/{len(results)}" + (" · 레지스트리 어긋남" if drift else "") + ")")
    return 1


# ── 실행 ────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    call = []
    if "--" in argv:
        cut = argv.index("--")
        argv, call = argv[:cut], argv[cut + 1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.cmd:
        parser.print_usage(sys.stderr)
        return 10
    if call and args.cmd != "reserve":
        print("GPT-ROUNDS-FAIL(10): `--` 뒤 정문 입력은 reserve 만 받는다", file=sys.stderr)
        return 10
    try:
        if args.cmd == "reserve":
            return cmd_reserve(args, call, os.environ)
        return COMMANDS[args.cmd](args, os.environ)
    except Usage as exc:
        print(f"GPT-ROUNDS-FAIL(10): {exc}", file=sys.stderr)
        return 10
    except Broken as exc:
        why = str(exc)
    except Exception as exc:  # noqa: BLE001 — 원장을 판정하지 못한 것은 측정 실패(11)다 — 통과로 넘기지 않는다
        why = f"{type(exc).__name__}: {exc}"
    print(f"GPT-ROUNDS-FAIL(11): {why}", file=sys.stderr)
    return 11


if __name__ == "__main__":
    sys.exit(main())
