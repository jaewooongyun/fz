#!/usr/bin/env python3
"""fz 완료 게이트 판정기 — 완료를 선언이 아니라 프로세스 결과로 증명한다.

⛔ 본 스크립트가 **실행 문법·exit·한계값의 SSOT**다. `modules/gates.md`는 수명주기·배선을
   담고 문법은 요약만 둔다 (권위는 여기). 이유: 같은 사실을 두 곳에 쓰면 드리프트한다
   (플러그인 자체 감사 F-025 — 정적 계약이 존재만 검사해 모순을 통과시킨 사례).

판정 계약 (⛔ 둘 다여야 통과):
  1. 프로세스가 exit 0 으로 끝난다
  2. EXPECT: 가 stdout+stderr 결합 출력에 **부분 문자열로** 포함된다
  exit 0 만 보면 "실행됐다"만 증명하고, EXPECT 만 보면 실패한 프로세스가 에러 텍스트에
  성공 토큰을 담았을 때 통과한다.

exit code 4분 (⛔ 판정의 fail-open 금지 / 인프라 부재의 fail-open 허용):
  0 = satisfied         전 게이트 충족
  1 = unmet             판정 결과. timeout·출력초과·EXPECT불일치·exit≠0 포함
  3 = invalid-ledger    fz 가 만든 원장의 계약 위반. 평가 불가는 통과가 아니다 → 차단
  2 = infrastructure    사용법 오류·파일 부재. 세션 감금이 게이트 누락보다 나쁘다 → 통과

⛔ 2 와 3 의 구분: 원장 *내용*의 위반은 3, 원장에 도달하지 못한 환경 문제는 2.
   `lint_contracts.py` 의 "2 = configuration/parse error" 3분 구조를 확장한 것.

정규식 미지원 — Python `re` 에 타임아웃이 없어 파멸적 백트래킹을 막을 수 없다. 원장을 fz 가
생성하므로 정규식이 필요 없고, 지원하지 않으면 그 실패 유형이 통째로 사라진다.

Python 3.9+ (macOS 시스템 python3 기준). 표준 라이브러리 전용.
루트는 자기 위치에서 해석한다(CWD 비의존).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # scripts/ → 플러그인 루트

# ── 한계값 (⛔ single source — 문서가 아니라 여기가 정답) ────────────────────
DEFAULT_TIMEOUT_S = 120        # 게이트 1개 기본 상한
MIN_PER_CHECK_S = 2            # 총예산 배분 시 하한
MAX_OUTPUT_BYTES = 1024 * 1024  # 결합 출력 상한. 초과는 경성 실패
DRAIN_GRACE_S = 1.0            # killpg 후 파이프 강제 종료까지의 유예
HASH_LEN = 12                  # sha256 앞 N자

STATES = ("active", "ready_for_review", "closed")

EXIT_OK, EXIT_UNMET, EXIT_INFRA, EXIT_INVALID = 0, 1, 2, 3


class LedgerError(Exception):
    """원장 계약 위반 → exit 3."""


class InfraError(Exception):
    """원장에 도달하지 못한 환경 문제 → exit 2."""


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:HASH_LEN]


# ── 파서 ────────────────────────────────────────────────────────────────
GATE_RE = re.compile(r"^- \[( |x)\] ([A-Za-z0-9_.-]+): (.+)$")
ATTR_RE = re.compile(r"^  ([A-Z_]+): ?(.*)$")
HEADER_RE = re.compile(r"^([A-Z][A-Za-z_]*): ?(.*)$")
ABANDON_RE = re.compile(r"^ABANDON: ([A-Za-z0-9_.-]+)[ \t]*(.*)$")

RUNNABLE_ATTRS = {"CHECK", "EXPECT"}
KNOWN_ATTRS = {
    "CHECK", "EXPECT", "CWD", "TIMEOUT", "MANUAL", "CRITERION",
    "CRITERION_HASH", "CONFIRMED", "APPROVED_ORACLE_HASH", "EVIDENCE",
}


class Gate:
    def __init__(self, gid: str, title: str, checked: bool, line: int):
        self.id = gid
        self.title = title
        self.checked = checked
        self.line = line
        self.attrs = {}
        self.abandoned_reason = None
        # ⛔ 이 게이트가 차지하는 원장 라인 번호(1-기반). **파서가 SSOT다.**
        #    별도 스캐너를 쓰면 파서와 문법이 갈린다 — 펜스 안의 예시가
        #    `- [ ] G1:` 모양이면 파서는 무시하는데 스캐너는 게이트로 읽어
        #    문서 예시가 `- [x]` 로 고쳐지고 증거까지 박혔다 (2026-08-25 실측).
        self.span = [line]
        self.attr_lines = {}          # 속성명 → 라인 번호

    @property
    def is_runnable(self) -> bool:
        return "CHECK" in self.attrs

    @property
    def is_manual(self) -> bool:
        return "MANUAL" in self.attrs

    def validate(self) -> None:
        has_check = "CHECK" in self.attrs
        has_expect = "EXPECT" in self.attrs
        if has_check != has_expect:
            missing = "EXPECT" if has_check else "CHECK"
            raise LedgerError(f"{self.id}: 실행 게이트에 {missing} 누락 — 둘 다 있어야 한다")
        if not has_check and not self.is_manual:
            raise LedgerError(f"{self.id}: CHECK/EXPECT 도 MANUAL 도 없다")
        if has_check and self.is_manual:
            raise LedgerError(f"{self.id}: CHECK 와 MANUAL 을 함께 쓸 수 없다")
        for key in ("CHECK", "EXPECT", "MANUAL"):
            if key in self.attrs and not self.attrs[key].strip():
                raise LedgerError(f"{self.id}: {key} 값이 비었다")
        expect = self.attrs.get("EXPECT", "")
        # EXPECT 는 부분 문자열 매칭이다 (Python re 에 타임아웃이 없어 백트래킹을 막을 수 없다).
        # 저자가 정규식으로 착각하면 게이트가 영영 매칭되지 않으므로 알려야 한다.
        # ⛔ 단 `startswith("/")` 로 판정하면 `/tmp/result` 같은 **경로 리터럴**까지 거부한다.
        #    두 실패의 방향이 다르다 — 정규식을 리터럴로 취급하면 게이트가 빨갛게 실패해
        #    저자가 알아채지만, 경로를 정규식으로 오인해 거부하면 정당한 게이트가 원장
        #    검증 단계에서 통째로 막힌다. 애매하면 **드러나는 실패** 쪽으로 기운다.
        if expect.startswith("/") and len(expect) > 1:
            body, sep, tail = expect[1:].rpartition("/")
            if sep and body:
                # ⛔ 알려진 오거부: `/tmp/i` 처럼 마지막 구성요소가 플래그 문자만인
                #    **정당한 경로**는 거부된다. 해결책은 CWD 를 쓰거나 EXPECT 를 더
                #    긴 문맥으로 잡는 것이다. 완전한 경로/정규식 판별자는 존재하지 않는다.
                if tail and all(c in "imsxaLu" for c in tail):
                    # `/…/i` — 플래그 문자만 뒤따르는 형태. 정규식 의도가 분명하다.
                    raise LedgerError(
                        f"{self.id}: EXPECT 가 정규식 문법({expect!r}) — 부분 문자열만 지원한다."
                        " 경로 리터럴이면 뒤의 플래그 문자를 지우거나 CWD 를 쓴다")
                if not tail:
                    # `/var/log/` — 디렉토리 경로와 무플래그 정규식이 같은 모양이다.
                    #  판정 근거가 없으므로 리터럴로 두고 경고만 남긴다.
                    print(f"⚠️  {self.id}: EXPECT {expect!r} 는 정규식으로도 읽히는 모양이다."
                          " 부분 문자열로 취급한다", file=sys.stderr)
                elif any(c in body for c in "^$*+?[]()|\\"):
                    # `/foo/g`(JS 플래그)·`/^ok$/` 처럼 Python 플래그가 아닌 꼬리를
                    # 달았거나 본문에 메타문자가 있으면 정규식 의도가 강하다.
                    # ⛔ 거부하지 않는다 — `/tmp/[cache]` 같은 경로도 이 모양이다.
                    print(f"⚠️  {self.id}: EXPECT {expect!r} 에 정규식 메타문자가 있다."
                          " 부분 문자열로 취급한다 — 정규식은 지원하지 않는다", file=sys.stderr)
        cwd = self.attrs.get("CWD")
        if cwd is not None:
            if not cwd.startswith("/"):
                raise LedgerError(f"{self.id}: CWD 는 절대경로만 허용 — {cwd!r}")
            if ".." in Path(cwd).parts:
                raise LedgerError(f"{self.id}: CWD 에 traversal(..) 금지 — {cwd!r}")
        if "TIMEOUT" in self.attrs:
            try:
                v = int(self.attrs["TIMEOUT"])
            except ValueError:
                raise LedgerError(f"{self.id}: TIMEOUT 이 정수가 아니다")
            if not (1 <= v <= 86400):
                raise LedgerError(f"{self.id}: TIMEOUT 범위 1..86400 — {v}")


class Ledger:
    def __init__(self, path: Path, text: str):
        self.path = path
        self.text = text
        self.newline = "\r\n" if "\r\n" in text else "\n"
        self.headers = {}
        self.root = None          # _validate 가 정규화해 채운다
        self.gates = []
        self._parse()
        self._validate()

    def _parse(self) -> None:
        lines = self.text.replace("\r\n", "\n").split("\n")
        current = None
        in_fence = False
        for i, raw in enumerate(lines, start=1):
            if raw.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue

            m = GATE_RE.match(raw)
            if m:
                gate = Gate(m.group(2), m.group(3), m.group(1) == "x", i)
                if any(g.id == gate.id for g in self.gates):
                    raise LedgerError(f"중복 게이트 id: {gate.id} (line {i})")
                self.gates.append(gate)
                current = gate
                continue

            m = ATTR_RE.match(raw)
            if m is not None and current is None:
                # ⛔ 어느 게이트에도 속하지 않는 들여쓰기 속성은 **조용히 무시하지 않는다.**
                #    오타로 게이트 줄이 빠지면 그 게이트의 CHECK 가 통째로 사라지는데
                #    파서는 아무 말도 하지 않았다 (fail-closed 위반).
                raise LedgerError(
                    f"게이트에 속하지 않은 속성 {m.group(1)} (line {i}) — "
                    "게이트 줄이 빠졌거나 빈 줄로 블록이 끊겼다")
            if m and current is not None:
                key, val = m.group(1), m.group(2)
                if key not in KNOWN_ATTRS:
                    raise LedgerError(f"{current.id}: 미지 속성 {key} (line {i})")
                if key in current.attrs:
                    raise LedgerError(f"{current.id}: 속성 {key} 중복 (line {i})")
                current.attrs[key] = val
                current.span.append(i)
                current.attr_lines[key] = i
                continue

            m = ABANDON_RE.match(raw)
            if m:
                gid, reason = m.group(1), m.group(2).strip()
                if not reason:
                    raise LedgerError(f"ABANDON: {gid} 에 이유가 없다 (line {i})")
                target = next((g for g in self.gates if g.id == gid), None)
                if target is None:
                    raise LedgerError(f"ABANDON 대상 {gid} 이 원장에 없다 (line {i})")
                target.abandoned_reason = reason
                target.span.append(i)
                current = None
                continue

            m = HEADER_RE.match(raw)
            if m and not self.gates:
                key = m.group(1)
                # ⛔ 중복 선언 거부. 마지막이 이기는 규칙이면 `STATE: closed` 를 한 줄
                #    append 해서 원장 전체를 no-op 으로 만들 수 있다 — `ABANDON:` 처럼
                #    흔적이 남는 이탈로가 아니라 **조용한 무력화**다. ROOT 중복도 같은 축으로
                #    실행 디렉토리를 바꾼다 (2026-08-25 실측: 둘 다 통과했다).
                if key in self.headers:
                    raise LedgerError(
                        f"헤더 {key} 중복 선언 (line {i}) — 마지막이 이기면 한 줄 append 로 "
                        "원장을 무력화할 수 있다")
                self.headers[key] = m.group(2).strip()
                continue

            if raw.strip() == "":
                current = None

    def _validate(self) -> None:
        if not self.gates:
            raise LedgerError("게이트가 0개 — ALL MET 이 아니라 오류다")
        root = self.headers.get("ROOT", "").strip()
        if not root:
            raise LedgerError("ROOT 헤더 부재 또는 빈 값 — 이 원장이 어느 WORK_DIR 것인지 확인 불가")
        # ⛔ modules/gates.md 가 "realpath 절대경로"를 선언하는데 코드가 존재만 봤다.
        #    상대경로·심볼릭·비정규 경로가 통과하면 ROOT 불일치 no-op 규칙이 성립하지 않는다.
        if not os.path.isabs(root):
            raise LedgerError(f"ROOT 는 절대경로여야 한다 — {root!r}")
        # ⛔ realpath **일치**를 요구하지 않는다. macOS 의 /var → /private/var 처럼
        #    정상 경로도 심볼릭을 거친다 (2026-08-24 실측: fixture 21건이 이것으로 깨졌다).
        #    필요한 것은 정규형 강요가 아니라 **소유 판정**이므로 양쪽을 realpath 로 정규화해 비교한다.
        real = os.path.realpath(root)
        if ".." in Path(root).parts:
            raise LedgerError(f"ROOT 에 traversal(..) 금지 — {root!r}")
        if not Path(real).is_dir():
            raise LedgerError(f"ROOT 디렉토리가 존재하지 않는다 — {root!r}")
        # 원장 파일이 그 ROOT 하위여야 한다 (소유 일치)
        ledger_real = os.path.realpath(str(self.path))
        if os.path.commonpath([real, ledger_real]) != real:
            raise LedgerError(
                f"원장이 ROOT 하위에 없다 — ROOT={real} / 원장={ledger_real}")
        # ⛔ 검증한 **정규** 경로를 저장하고 이후 전부 이것을 쓴다.
        #    검증은 realpath 로 하고 실행은 헤더 원문으로 하면 그 사이에 심볼릭을
        #    다른 디렉토리로 돌려 CHECK 를 딴 곳에서 돌릴 수 있다(TOCTOU). 증거 서명은
        #    바뀌지 않은 *표기*에만 묶이므로 나중 --status 는 met 으로 읽는다.
        self.root = real
        # ⛔ 확정본이면 실행 게이트 **전부** 도장이 있어야 한다. 일부만 찍히면
        #    안 찍힌 게이트는 CHECK 를 바꿔도 통과하므로, 부분 도장은 무도장보다 위험하다
        #    (도장이 있으니 보호받는다고 읽힌다).
        if self.headers.get("APPROVED", "").strip().lower() == "yes":
            naked = [g.id for g in self.gates
                     if g.is_runnable and "APPROVED_ORACLE_HASH" not in g.attrs]
            if naked:
                raise LedgerError(
                    f"확정 원장인데 승인 도장 없는 실행 게이트: {naked} — `--finalize` 를 다시 돌린다")
        state = self.headers.get("STATE")
        if state not in STATES:
            raise LedgerError(f"STATE 는 {'/'.join(STATES)} 중 하나 — 받은 값 {state!r}")
        for g in self.gates:
            g.validate()

    @property
    def state(self) -> str:
        return self.headers["STATE"]


def load(path: Path) -> Ledger:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise InfraError(f"원장 파일 없음: {path}")
    except OSError as e:
        raise InfraError(f"원장 읽기 실패: {e}")
    return Ledger(path, text)


# ── 원장 발견 (Stop hook · health-check 공용) ─────────────────────────────
# ⛔ 깊이를 하나로 고정하지 않는다. `*/gates/plan.md`(깊이 2)만 보면
#    `{CWD}/gates/plan.md`(깊이 1)·`{CWD}/a/b/gates/plan.md`(깊이 3)를 놓치고
#    **조용히 통과**한다 (2026-08-25 실측: 4종 중 1종만 발견). 명시적 깊이 목록으로
#    상한을 분명히 둔다 — `rglob` 은 큰 트리에서 hook 을 늘어지게 만든다.
LEDGER_GLOBS = ("gates/plan.md", "*/gates/plan.md",
                "*/*/gates/plan.md", "*/*/*/gates/plan.md")
GATES_DIR_GLOBS = ("gates", "*/gates", "*/*/gates", "*/*/*/gates")
# ⛔ `tests` 를 넣는 이유 — fixture 원장은 **테스트 자산**이고 작업 원장이 아니다.
#    플러그인 루트에서 `--discover` 를 돌리면 `tests/fixtures/gates/` 가 "확정 원장 없는
#    gates 디렉토리"로 잡혀 진단이 매번 뜬다(2026-08-25 실측 — 위반은 아니지만 노이즈).
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".build", "tests"}
# ⛔ cwd **밖** 원장용 탈출로. hook 은 `cwd` 만 받으므로 워크트리에서 작업하고
#    원장이 리포 루트에 있으면 어떤 glob 으로도 못 찾는다 — 설계 한계다.
LEDGER_ENV = "FZ_GATES_LEDGER"
MAX_DISCOVERED = 8              # 상한 — 큰 트리에서 탐색이 늘어지지 않게


def _skipped(path: Path, base: Path) -> bool:
    try:
        parts = path.relative_to(base).parts
    except ValueError:
        return False
    return any(seg in SKIP_DIRS for seg in parts)


def find_ledgers(cwd, env_raw: str = "") -> tuple:
    """확정 원장 목록과 진단.

    ⛔ `plan.draft.md` 는 제외 — 확정 전이라 대상이 아니다.

    반환 `(원장들, 진단)`. 진단이 필요한 이유 — **게이트 미사용 세션과 "찾지 못함"이
    구분되지 않으면** 놓친 원장이 조용한 통과로 보인다. `gates/` 디렉토리가 아예 없으면
    게이트를 안 쓰는 세션이므로 조용히 통과하고, `gates/` 는 있는데 `plan.md` 가 없거나
    깊이 밖이면 그 사실을 남긴다.
    """
    cwd = Path(cwd)
    env_raw = (env_raw or "").strip()
    if env_raw:
        picked, missing = [], []
        for chunk in env_raw.split(os.pathsep):
            chunk = chunk.strip()
            if not chunk:
                continue
            cand = Path(chunk)
            if cand.is_file():
                picked.append(cand)
            else:
                missing.append(chunk)
        note = f"{LEDGER_ENV} 의 경로 {missing} 를 찾을 수 없다" if missing else ""
        return picked[:MAX_DISCOVERED], note

    found = []
    for pattern in LEDGER_GLOBS:
        try:
            found += [p for p in cwd.glob(pattern)
                      if p.is_file() and not _skipped(p, cwd)]
        except OSError:
            continue
    uniq = sorted({p.resolve() for p in found})
    if uniq:
        return uniq[:MAX_DISCOVERED], ""

    # 원장은 없다 — `gates/` 자체가 없으면 게이트 미사용 세션이다(조용히 통과).
    for pattern in GATES_DIR_GLOBS:
        try:
            for g in cwd.glob(pattern):
                if g.is_dir() and not _skipped(g, cwd):
                    return [], (f"`{g}` 가 있는데 확정 원장(plan.md)이 없다 — "
                                f"draft 단계이거나 확정(`--finalize`)이 빠졌다")
        except OSError:
            continue
    return [], ""



# ── oracle 무결성 ────────────────────────────────────────────────────────
def path_fingerprint() -> str:
    entries = os.environ.get("PATH", "").split(os.pathsep)
    return f"{sha(os.pathsep.join(entries))}/{len(entries)} entries"


def tail(text: str, limit: int = 240) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[:limit] + "…"


# ── --confirm (MANUAL 사용자 확인) ──────────────────────────────────────


def env_fingerprint() -> str:
    """실행 환경 지문 — 증거의 provenance 축.

    ⛔ 승인 도장(`oracle_hash`)과 **분리한다.** 두 해시의 목적이 다르다.

    | 해시 | 무엇을 묶나 | 환경 |
    |------|------------|:----:|
    | 승인 도장 | 사람·Codex 가 승인한 oracle | ⛔ 제외 |
    | 증거 서명 | 이 결과가 **어느 환경에서** 나왔나 | ✅ 포함 |
    """
    return sha(f"{os.environ.get('SHELL', '/bin/sh')}|{path_fingerprint()}")[:HASH_LEN]


def oracle_hash(gate: Gate, cwd: str) -> str:
    payload = json.dumps({
        "schema": 1,
        "check": gate.attrs.get("CHECK", ""),
        "expect": gate.attrs.get("EXPECT", ""),
        "manual": gate.attrs.get("MANUAL", ""),
        # ⛔ criterion(사람이 읽는 합격 조건)을 해시에 넣는다. VerifySpec 이 요구하는
        #    필드인데 원장에 남기지 않으면, 승인받은 "무엇을 재는가"가 사라지고
        #    CHECK 만 남는다 — 그러면 CHECK 를 쉬운 것으로 바꿔도 대조 대상이 없다.
        "criterion": gate.attrs.get("CRITERION", ""),
        "title": gate.title,
        "cwd": cwd,
        "timeout": gate.attrs.get("TIMEOUT", str(DEFAULT_TIMEOUT_S)),
        # ⛔ **환경(SHELL·PATH)은 넣지 않는다.** 이 해시는 승인 도장의 비교 대상이고,
        #    승인 대상은 "무엇을 어떻게 재는가"다 — PATH 는 사람이 승인한 것이 아니다.
        #    넣으면 cross-session 에서 정상 파이프라인이 멈춘다: fz-plan 이 세션 A 에서
        #    도장을 찍고 fz-code 가 세션 B 에서 실행하면 PATH 가 달라 exit 3(차단) 이 되고,
        #    메시지는 "승인 후 oracle 이 바뀌었다"라며 원인을 잘못 지목한다.
        #    실측(2026-08-25): PATH 만 바꿔도, SHELL 만 바꿔도 각각 exit 3.
        #    fz-plan → fz-code 가 별 세션인 것은 예외가 아니라 설계된 흐름이다
        #    (compact · 다음 날 · 다른 터미널 · direnv/nvm shim).
        #    환경은 **증거 서명**이 묶는다 — 그쪽이 provenance 축이다.
    }, sort_keys=True, ensure_ascii=False)
    return sha(payload)


def ev_enc(s: str) -> str:
    """증거 레코드에 넣을 값 인코딩 — `;` 와 `%` 를 escape 한다.

    ⛔ 증거는 `sig=…; exit=…; cwd=…; output=…` 형태이고 `parse_evidence` 는 `;` 로
       쪼갠다. 정상 출력에 `;` 가 들어 있으면(예: `echo "done; cleanup=ok"`) 파싱이
       잘려 재계산 서명이 어긋나고, 통과한 게이트가 나중에 unmet 으로 읽힌다
       (2026-08-25 실측 — fail-red). `ev_dec` 와 정확한 역함수 쌍이다.
    """
    return s.replace("%", "%25").replace(";", "%3B")


def ev_dec(s: str) -> str:
    """`ev_enc` 의 역함수 — 순서가 중요하다(`;` 먼저, `%` 나중)."""
    return s.replace("%3B", ";").replace("%25", "%")


def evidence_signature(gate: Gate, cwd: str, exit_code, output: str, env: str) -> str:
    """증거를 자기 oracle 에 묶는 서명.

    ⛔ **암호학적 위조 방지가 아니다.** 원장은 평문이고 이 알고리즘은 공개돼 있어,
       작정하면 재계산할 수 있다. 이것이 막는 것은 *우연한* false-green 이다 —
       모델이 CHECK 를 실행하지 않고 "통과했다"는 텍스트만 쓰는 경로.
       위조하려면 oracle 을 정확히 재계산해야 하고, 그건 게이트를 의도적으로
       무력화하는 행위이지 실수로 되지 않는다.
    ⛔ 이 서명이 없으면 `gate_state()` 가 EVIDENCE 문자열의 *존재*만 보고 met 을 준다
       (2026-08-24 실측: `CHECK: false` + `EVIDENCE: forged` → ALL MET + 전진 성공).
    """
    # ⛔ `env` 는 **기록된** 지문이다(현재 환경이 아니다). 재계산이 증거의 `env=` 필드를
    #    쓰므로 cross-session 에서도 일치한다 — 현재 환경을 쓰면 통과한 게이트가 다른
    #    세션에서 unmet 으로 읽힌다 (2026-08-25 실측: PATH 만 바꿔 `--status` 가 UNMET).
    #    부수 이득 — 이제 `env=` 필드가 서명에 묶여 위조 불가다. 이전엔 기록만 되고
    #    서명 밖이라 provenance 가 실제로 보호되지 않았다.
    return sha(f"{oracle_hash(gate, cwd)}|{env}|{exit_code}|{ev_enc(tail(output, 240))}")


# ── 실행기 ──────────────────────────────────────────────────────────────
class Result:
    def __init__(self, ok, exit_code, output, error=None, killed=False):
        self.ok = ok
        self.exit_code = exit_code
        self.output = output
        self.error = error
        # ⛔ 손자를 강제 종료했는지. 판정을 뒤집지는 않지만(CHECK 계약은 exit+EXPECT 다)
        #    증거에 남겨야 한다 — 프로세스를 새는 CHECK 를 저자가 알아챌 수 있어야 한다.
        self.killed = killed


def _drain(stream, sink: bytearray, lock: threading.Lock, state: dict) -> None:
    """실행 중 streaming capture — 앞부분을 보존하고 상한 초과 시 플래그.

    ⛔ `read(n)` 이 아니라 `read1(n)` 이다. `BufferedReader.read(8192)` 는 **8192바이트가
       모이거나 EOF 가 될 때까지 블록**한다. 그래서 `read` 를 쓰면 "실행 중 capture"가
       사실이 아니었다 — 짧은 출력은 프로세스가 끝날 때 한꺼번에 도착했고,
       EXPECT 조기 매칭도 출력 상한 감지도 실행 중에는 발화하지 못했다
       (2026-08-25 음성 대조에서 드러남: 경계 fixture 가 주입 전후 3.1초로 동일했다).
       `read1` 은 지금 있는 만큼만 돌려준다.
    """
    try:
        while True:
            chunk = stream.read1(8192)
            if not chunk:
                break
            with lock:
                room = MAX_OUTPUT_BYTES - state["bytes"]
                if room > 0:
                    sink.extend(chunk[:room])
                state["bytes"] += len(chunk)
                if state["bytes"] > MAX_OUTPUT_BYTES:
                    state["overflow"] = True
    except (OSError, ValueError):
        pass


def run_check(gate: Gate, cwd: str, budget_s: float) -> Result:
    timeout = min(float(gate.attrs.get("TIMEOUT", DEFAULT_TIMEOUT_S)), budget_s)
    out, err = bytearray(), bytearray()
    lock = threading.Lock()
    state = {"bytes": 0, "overflow": False}

    try:
        proc = subprocess.Popen(
            gate.attrs["CHECK"], shell=True, cwd=cwd,
            # ⛔ stdin 을 명시적으로 닫는다. 미지정이면 터미널·상위 파이프를 **상속**해
            #    CHECK 가 입력을 기다리면 게이트당 기본 120초(총 예산 최대 960초)를 잡아먹는다.
            #    unlazy 는 `stdio:['ignore', ...]` 로 같은 것을 한다.
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,  # 프로세스 그룹 분리 — 손자까지 죽이기 위함
        )
    except OSError as e:
        return Result(False, None, "", f"실행 실패: {e}")

    try:
        pgid = os.getpgid(proc.pid)   # 살아 있을 때 확보 — 종료 후엔 조회 불가
    except OSError:
        pgid = None

    threads = [
        threading.Thread(target=_drain, args=(proc.stdout, out, lock, state), daemon=True),
        threading.Thread(target=_drain, args=(proc.stderr, err, lock, state), daemon=True),
    ]
    for t in threads:
        t.start()

    timed_out = False
    deadline = time.monotonic() + timeout
    while True:
        if proc.poll() is not None:
            break
        if state["overflow"] or time.monotonic() >= deadline:
            timed_out = not state["overflow"]
            _kill_group(proc, pgid)
            proc.wait()
            break
        time.sleep(0.02)

    # ⛔ 셸이 exit 해도 손자가 상속받은 파이프를 붙잡으면 read 가 안 끝난다.
    #    (`(cmd &)` 로 떠난 손자도 같은 pgid 라 killpg 가 닿는다 — 실측 확인)
    #
    #    얼마나 기다릴지가 문제였다. 고정 grace(1초)로 자르면 **정상적인 지연 출력**을
    #    잃고, 무한정 기다리면 orphan daemon 에 걸려 TIMEOUT 만큼 매달린다.
    #    두 경우는 밖에서 구분되지 않는다 — 손자가 곧 쓸 것인지, 영영 안 쓸 것인지.
    #
    #    구분 기준은 하나다: **더 기다려서 판정이 바뀔 수 있는가.**
    #    EXPECT 가 이미 매칭됐으면 기다릴 이유가 없고, 아직 아니면 저자가 선언한
    #    TIMEOUT 까지는 기다려 주는 것이 맞다 (그것이 저자가 준 예산이다).
    needle_b = gate.attrs["EXPECT"].encode("utf-8")

    def _matched() -> bool:
        """⛔ 두 스트림을 **이어 붙이지 않는다.**

        `EXPECT:` 는 원장 한 줄이라 개행을 담을 수 없다(`ATTR_RE` 가 줄 단위로 매칭하고
        `render_ledger` 가 개행을 거부한다). 최종 판정은 `stdout + "\n" + stderr` 에서
        찾으므로, 개행 없는 needle 은 **한 스트림 안에서만** 매칭된다. 따라서
        스트림별로 보는 것이 최종 판정과 정확히 같은 의미다.

        개행 없이 이어 붙이면 경계에서 needle 을 **합성**한다 — stdout=`he`,
        stderr=`llo` 가 EXPECT=`hello` 에 걸려 조기 kill 을 유발하고, 최종 매칭은
        실패해 불필요한 FAIL 이 된다 (2026-08-25 실측).

        ⛔ decode 하지 않는다. 1MiB 스냅샷을 50ms 마다 디코딩하면 120초 대기에서
        누적 2.4GiB 를 디코딩하고, 그 동안 drain lock 을 잡는다. UTF-8 은 자기
        동기화하므로 bytes 부분 문자열 검색이 문자 경계를 깨지 않는다.
        `bytearray.find` 는 복사 없이 찾는다.
        """
        with lock:
            return out.find(needle_b) >= 0 or err.find(needle_b) >= 0

    forced_kill = False
    for t in threads:
        t.join(timeout=0.05)
    seen_bytes = -1
    while any(t.is_alive() for t in threads):
        if time.monotonic() >= deadline or state["overflow"]:
            break
        with lock:
            now_bytes = state["bytes"]
        # 새 바이트가 없으면 매칭 결과도 같다 — 재검색을 건너뛴다
        if now_bytes != seen_bytes:
            seen_bytes = now_bytes
            if _matched():
                break
        time.sleep(0.05)
        for t in threads:
            t.join(timeout=0)
    if any(t.is_alive() for t in threads):
        forced_kill = True
        _kill_group(proc, pgid)
        for t in threads:
            t.join(timeout=DRAIN_GRACE_S)
    if any(t.is_alive() for t in threads):
        for stream in (proc.stdout, proc.stderr):
            try:
                stream.close()
            except OSError:
                pass
        for t in threads:
            t.join(timeout=DRAIN_GRACE_S)

    stdout = out.decode("utf-8", "replace")
    stderr = err.decode("utf-8", "replace")
    combined = stdout + ("\n" if stdout and stderr else "") + stderr

    if state["overflow"]:
        return Result(False, proc.returncode, combined,
                      f"출력이 {MAX_OUTPUT_BYTES} 바이트를 초과", killed=forced_kill)
    if timed_out:
        return Result(False, proc.returncode, combined,
                      f"{timeout:.0f}초 timeout", killed=forced_kill)

    # EXPECT 는 원장 한 줄이라 개행을 담을 수 없다(ATTR_RE 가 줄 단위로 매칭하고
    # render_ledger 가 개행을 거부한다). 그래서 stdout+stderr 를 이어 붙일 때
    # 경계에서 EXPECT 가 합성되거나 잘릴 수 없다 — 사이에 개행이 들어가고
    # 한 줄 needle 은 한 스트림 안에서만 매칭된다.
    matched = gate.attrs["EXPECT"] in combined
    ok = proc.returncode == 0 and matched
    error = None
    if not ok:
        error = ("EXPECT 불일치" if proc.returncode == 0
                 else f"exit={proc.returncode}" + ("" if matched else " + EXPECT 불일치"))
    return Result(ok, proc.returncode, combined, error, killed=forced_kill)


def _kill_group(proc, pgid=None) -> None:
    """⛔ pgid 는 **스폰 직후에 확보**해 둔 값을 넘긴다.

    셸이 먼저 종료하면 `os.getpgid(proc.pid)` 가 ProcessLookupError 를 던져
    그룹을 못 죽이고, 상속된 파이프를 붙잡은 손자를 그대로 남긴다.
    (`(cmd &) ; echo` 형태에서 실측 — 손자 sleep 30 을 30초 그대로 기다렸다)
    """
    if pgid is None:
        try:
            pgid = os.getpgid(proc.pid)
        except OSError:
            pgid = None
    if pgid is not None:
        try:
            os.killpg(pgid, signal.SIGKILL)
            return
        except OSError:
            pass
    try:
        proc.kill()
    except OSError:
        pass


# ── writeback (CAS + atomic) ────────────────────────────────────────────
def write_atomic(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".gate-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def ledger_lines(ledger) -> list:
    """원장을 파서와 **같은 방식**으로 줄 분해한다 (CRLF 정규화 포함)."""
    return ledger.text.replace("\r\n", "\n").split("\n")


def gate_block_hash(ledger, gate_id: str) -> str:
    """대상 게이트 블록의 해시 — writeback CAS 의 비교 범위.

    ⛔ **전체 파일 해시를 쓰지 않는다.** CHECK 는 최대 `TIMEOUT` 초(기본 120) 도는데,
    그 사이 사용자가 **무관한 형제 게이트**를 편집하면 전체 파일 해시가 바뀌어
    writeback 이 exit 3 으로 죽었다. 실행 결과를 잃는 것은 게이트가 만들려던 것과
    반대다 — 판정을 지키려고 판정을 버린다.

    ⛔ **범위는 파서가 정한다.** 이전 구현은 자체 스캐너로 블록을 다시 찾았고,
    그래서 파서와 문법이 갈렸다 — 파서는 펜스(```)를 건너뛰지만 스캐너는 몰랐다.

    범위에 넣는 것과 이유:

    | 포함 | 이유 |
    |------|------|
    | `- [ ] id: 제목` 줄 | ⛔ 제목이 바뀌면 **같은 증거가 다른 주장에 붙는다**. `oracle_hash` 에는 제목이 없지만 게이트 판정의 `measurement_fit` 은 CHECK 를 제목 대비 평가한다 |
    | 그 게이트의 속성 줄 전부 | CHECK·EXPECT·CWD·TIMEOUT·MANUAL — oracle 자체 |
    | 그 게이트를 지목한 `ABANDON:` | 도는 중에 포기됐으면 met/unmet 기록이 포기와 모순된다 |

    범위에서 빼는 것 — 다른 게이트 블록, 헤더(`ROOT`/`STATE`), 빈 줄, 산문, 펜스 내부.
    헤더 변경은 `evaluate()` 진입부 가드가 본다(실행 **전** 판정이므로 여기서 중복 확인하지 않는다).

    ⛔ 이 좁히기는 교환이다 — **단일 writer 를 가정한다.** 상세는 `modules/gates.md`.
    """
    gate = next((g for g in ledger.gates if g.id == gate_id), None)
    if gate is None:
        raise LedgerError(f"{gate_id}: 게이트가 원장에 없다 — CAS 기준을 세울 수 없다")
    lines = ledger_lines(ledger)
    return sha("\n".join(lines[n - 1] for n in sorted(set(gate.span))))


def apply_result(path: Path, baseline_hash: str, gate_id: str,
                 checked: bool, evidence: str) -> None:
    """대상 게이트의 체크박스와 EVIDENCE 만 고친다.

    ⛔ 편집 위치를 **파서 스팬**으로 잡는다. 자체 스캐너로 라인을 다시 찾으면
       파서가 무시하는 펜스 내부의 `- [ ] id:` 예시까지 고쳐 문서를 오염시킨다
       (2026-08-25 실측 — 예시가 `- [x]` 가 되고 증거까지 박혔다).
    """
    fresh = load(path)                     # 파서 재실행 — 스팬의 SSOT
    if gate_block_hash(fresh, gate_id) != baseline_hash:
        raise LedgerError(
            f"{gate_id}: 실행 중 이 게이트가 변경됨 — stale 덮어쓰기를 거부한다 (CAS 충돌)")
    gate = next((g for g in fresh.gates if g.id == gate_id), None)
    if gate is None:
        raise LedgerError(f"{gate_id}: writeback 대상을 찾지 못했다")

    lines = ledger_lines(fresh)
    box = lines[gate.line - 1]
    m = GATE_RE.match(box)
    if m is None:
        raise LedgerError(f"{gate_id}: 스팬이 게이트 줄을 가리키지 않는다 (line {gate.line})")
    lines[gate.line - 1] = f"- [{'x' if checked else ' '}] {gate_id}: {m.group(3)}"

    ev_line = gate.attr_lines.get("EVIDENCE")
    if ev_line is not None:
        lines[ev_line - 1] = f"  EVIDENCE: {evidence}"
    else:
        # EVIDENCE 부재 시 마지막 속성 뒤에 만든다.
        # ⛔ 없으면 체크박스만 [x] 가 되고 gate_state 는 "증거 없음"으로 unmet 을 반환한다 —
        #    PASS 를 출력하고도 --status 가 UNMET 이 되어 전진이 영구 차단된다 (2026-08-24 실측).
        attr_nums = [n for k, n in gate.attr_lines.items()]
        if not attr_nums:
            raise LedgerError(f"{gate_id}: EVIDENCE 를 기록할 위치를 찾지 못했다")
        lines.insert(max(attr_nums), f"  EVIDENCE: {evidence}")
    write_atomic(path, "\n".join(lines))


def confirm_token(gate_id: str, criterion_hash: str, stamp: str) -> str:
    """MANUAL 확인 토큰 — `--confirm` 이 발급하고 `gate_state` 가 재계산해 대조한다."""
    return sha(f"{gate_id}|{criterion_hash}|{stamp}")[:8]


def parse_evidence(evidence: str) -> dict:
    """`sig=…; exit=…; cwd=…` 형태를 키-값으로 푼다."""
    out = {}
    for part in evidence.split(";"):
        if "=" in part:
            k, _, v = part.partition("=")
            out[k.strip()] = v.strip()
    return out


def gate_state(gate: Gate, ledger=None) -> str:
    """met / unmet / abandoned — 체크박스가 아니라 **인증된** 증거가 판정한다.

    ⛔ `ledger` 없이 호출하면 서명 검증을 건너뛴다. 호출부는 반드시 넘긴다 —
       인자를 optional 로 둔 것은 기존 호출부 호환이 아니라 **순환 참조 회피**용이고,
       실제 판정 경로(evaluate·set_state)는 모두 전달한다.
    """
    if gate.abandoned_reason:
        return "abandoned"
    if not gate.checked:
        return "unmet"
    evidence = gate.attrs.get("EVIDENCE", "").strip()
    if not evidence or evidence == "pending":
        return "unmet"

    if gate.is_runnable:
        # ⛔ 증거가 자기 oracle 에 묶여 있는지 본다. 손으로 쓴 텍스트는 여기서 떨어진다.
        if ledger is None:
            return "unmet"
        fields = parse_evidence(evidence)
        declared_sig = fields.get("sig", "")
        if not declared_sig:
            return "unmet"
        cwd = resolve_cwd(gate, ledger)
        try:
            exit_code = int(fields.get("exit", ""))
        except ValueError:
            return "unmet"
        output = ev_dec(fields.get("output", ""))
        recorded_env = fields.get("env", "")
        if declared_sig != evidence_signature(gate, cwd, exit_code, output, recorded_env):
            return "unmet"
        if exit_code != 0:
            return "unmet"   # 증거가 진짜여도 실패한 실행이면 미충족
        # 승인된 oracle 이 선언돼 있으면 현재 oracle 과 일치해야 한다
        approved = gate.attrs.get("APPROVED_ORACLE_HASH")
        if approved and approved != oracle_hash(gate, cwd):
            return "unmet"

    if gate.is_manual:
        # ⛔ CRITERION_HASH 가 MANUAL 문구에서 실제로 유도되는지 먼저 본다.
        #    이 검사가 없으면 조건 문구만 바꾸고 hash 를 그대로 둬서 통과시킬 수 있다.
        if gate.attrs.get("CRITERION_HASH", "") != sha(gate.attrs.get("MANUAL", "")):
            return "unmet"
        confirmed = gate.attrs.get("CONFIRMED", "").split()
        if len(confirmed) < 3:
            return "unmet"
        stamp, chash, token = confirmed[0], confirmed[1], confirmed[2]
        if chash != gate.attrs.get("CRITERION_HASH", ""):
            return "unmet"  # 확인 조건이 바뀌면 이전 확인은 무효
        # ⛔ 토큰을 재계산해 대조한다. 이 검사가 없으면 `CONFIRMED: fake <공개hash> fake`
        #    로 met 을 만들 수 있다 (2026-08-24 실측 — hash 는 원장에 적혀 있어 공개값이다).
        if token != confirm_token(gate.id, chash, stamp):
            return "unmet"
    return "met"


def resolve_cwd(gate: Gate, ledger: Ledger) -> str:
    return gate.attrs.get("CWD") or ledger.root      # 검증된 정규 경로 (헤더 원문 아님)


def evaluate(ledger: Ledger, mode: str, budget_s: float, only=None) -> int:
    """mode: status(미실행) | run(미충족만) | reverify(전부 재실행).

    ⛔ 수명주기 가드가 **여기** 있어야 한다. 문서(modules/gates.md)가 선언한
       `STATE: closed` no-op · `FZ_GATES_OFF` kill-switch · `ROOT` 불일치 no-op 를
       실행체가 전혀 보지 않던 결함이 있었다 (2026-08-24 실측: closed 원장이 실행되고
       `FZ_GATES_OFF=1` 이 무시됐다 — 문서가 유일한 세션 kill-switch 라 부른 것).
    """
    if ledger.headers.get("APPROVED", "").strip().lower() != "yes":
        runnable = [g for g in ledger.gates if g.is_runnable]
        if runnable and not any("APPROVED_ORACLE_HASH" in g.attrs for g in runnable):
            print(f"⚠️  {ledger.path.name}: 미확정 원장 (draft) — 승인 도장이 없어 "
                  "CHECK 교체를 막지 못한다. 확정은 `--finalize`", file=sys.stderr)
    if os.environ.get("FZ_GATES_OFF") == "1":
        print("FZ_GATES_OFF=1 — 게이트 판정을 건너뛴다 (원장 STATE 는 불변)")
        return EXIT_OK
    if ledger.state == "closed":
        print(f"{ledger.path.name}: STATE closed — no-op")
        return EXIT_OK

    unmet, met, abandoned, ran = [], [], [], 0
    started = time.monotonic()

    # ⛔ fz-code 는 "해당 Step 게이트"만 돌려야 한다. 선택자가 없으면 미래 Step 게이트가
    #    함께 실행돼 실패하고, 첫 Step 에서 영구 정지한다 (2026-08-24 리뷰 지적).
    targets = ledger.gates
    if only:
        wanted = {s.strip() for s in only.split(",") if s.strip()}
        missing = wanted - {g.id for g in ledger.gates}
        if missing:
            raise InfraError(f"--only 에 없는 게이트 id: {', '.join(sorted(missing))}")
        targets = [g for g in ledger.gates if g.id in wanted]

    for gate in targets:
        state = gate_state(gate, ledger)
        if state == "abandoned":
            abandoned.append(gate)
            print(f"  ABANDON {gate.id}: {gate.abandoned_reason}")
            continue

        if mode == "status" or not gate.is_runnable:
            (met if state == "met" else unmet).append(gate)
            if state != "met":
                print(f"  UNMET {gate.id}: {gate.title}")
            continue

        if mode == "run" and state == "met":
            met.append(gate)
            continue

        cwd = resolve_cwd(gate, ledger)
        declared = gate.attrs.get("APPROVED_ORACLE_HASH")
        if declared is not None:
            actual = oracle_hash(gate, cwd)
            if declared != actual:
                raise LedgerError(
                    f"{gate.id}: APPROVED_ORACLE_HASH 불일치 (선언 {declared} / 실측 {actual})"
                    " — 승인 후 oracle 이 바뀌었다. 재승인이 필요하다")

        if not Path(cwd).is_dir():
            raise LedgerError(f"{gate.id}: CWD 가 디렉토리가 아니다 — {cwd}")

        remaining = budget_s - (time.monotonic() - started)
        if remaining <= MIN_PER_CHECK_S:
            unmet.append(gate)
            print(f"  BUDGET {gate.id}: 예산 소진 — 미판정은 통과가 아니다")
            continue

        baseline = gate_block_hash(load(ledger.path), gate.id)
        result = run_check(gate, cwd, remaining)
        ran += 1

        env_digest = env_fingerprint()
        signature = evidence_signature(gate, cwd, result.exit_code, result.output, env_digest)
        killed_field = "; killed=descendant" if result.killed else ""
        evidence = (f"sig={signature}; exit={result.exit_code}; cwd={ev_enc(cwd)}; "
                    f"env={env_digest}{killed_field}; "
                    f"output={ev_enc(tail(result.output))}")
        if result.killed:
            # 판정은 안 뒤집지만 흔적을 남긴다 — CHECK 가 프로세스를 새고 있다.
            print(f"  KILL  {gate.id}: 잔존 손자를 강제 종료했다 — CHECK 가 프로세스를 남긴다")
        if result.ok:
            apply_result(ledger.path, baseline, gate.id, True, evidence)
            # ⛔ 쓴 것을 디스크에서 다시 읽어 판정한다. writeback 이 잘못 써도
            #    메모리 상태로 met 을 세면 `ALL MET` 을 출력하고 `--status` 는
            #    UNMET 이 되는 불일치가 생긴다 (EVIDENCE 미삽입 결함의 재발 경로).
            recheck = load(ledger.path)
            rg = next((g for g in recheck.gates if g.id == gate.id), None)
            if rg is None or gate_state(rg, recheck) != "met":
                print(f"  FAIL  {gate.id}: 통과했으나 원장에 met 으로 기록되지 않았다")
                unmet.append(gate)
                continue
            print(f"  PASS  {gate.id}: {gate.title}")
            met.append(gate)
        else:
            print(f"  FAIL  {gate.id}: {gate.title}")
            print(f"        {result.error}; output={tail(result.output)}")
            apply_result(ledger.path, baseline, gate.id, False, "pending")
            unmet.append(gate)

    total = len(targets)
    suffix = f", reran: {ran}" if ran else ""
    if unmet:
        print(f"{ledger.path.name}: {total} gates")
        print(f"UNMET: {len(unmet)} (met: {len(met)}, abandoned: {len(abandoned)}{suffix})")
        for g in unmet:
            print(f"  {g.id}")
        return EXIT_UNMET
    print(f"{ledger.path.name}: {total} gates")
    print(f"ALL MET ({len(met)} met, abandoned: {len(abandoned)}{suffix})")
    return EXIT_OK


def confirm(ledger: Ledger, gate_id: str) -> int:
    gate = next((g for g in ledger.gates if g.id == gate_id), None)
    if gate is None:
        raise InfraError(f"게이트 {gate_id} 이 원장에 없다")
    if not gate.is_manual:
        raise InfraError(f"{gate_id} 은 MANUAL 게이트가 아니다")

    criterion = gate.attrs.get("MANUAL", "")
    expected_hash = sha(criterion)
    declared = gate.attrs.get("CRITERION_HASH", "")
    print(f"확인 조건: {criterion}")
    if declared and declared != expected_hash:
        print(f"⛔ CRITERION_HASH 가 조건과 어긋난다 (선언 {declared} / 실측 {expected_hash})")

    if not sys.stdin.isatty():
        # ⛔ 모델·hook·워커는 비대화형이라 여기서 멈춘다. 이것이 MANUAL 의 무결성이다.
        print("⛔ 비대화형 환경 — 사용자가 직접 터미널에서 실행해야 한다", file=sys.stderr)
        return EXIT_INFRA

    answer = input("이 조건을 직접 확인했습니까? (y/N) ").strip().lower()
    if answer != "y":
        print("확인 취소 — 게이트는 미충족으로 남는다")
        return EXIT_UNMET

    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    token = confirm_token(gate_id, expected_hash, stamp)
    text = ledger.path.read_text(encoding="utf-8")
    baseline = sha(text)
    lines, out, target = text.split("\n"), [], None
    for raw in lines:
        m = GATE_RE.match(raw)
        if m and m.group(2) == gate_id:
            target = gate_id
            out.append(f"- [x] {gate_id}: {m.group(3)}")
            continue
        if target == gate_id:
            m2 = ATTR_RE.match(raw)
            if m2 and m2.group(1) == "CRITERION_HASH":
                out.append(f"  CRITERION_HASH: {expected_hash}")
                out.append(f"  CONFIRMED: {stamp} {expected_hash} {token}")
                continue
            if m2 and m2.group(1) == "CONFIRMED":
                continue  # 기존 확인 라인은 새 것으로 대체
            if m2 and m2.group(1) == "EVIDENCE":
                out.append("  EVIDENCE: 사용자 직접 확인")
                target = None
                continue
        out.append(raw)
    if sha(ledger.path.read_text(encoding="utf-8")) != baseline:
        raise LedgerError(f"{gate_id}: 확인 중 원장이 변경됨 (CAS 충돌)")
    write_atomic(ledger.path, "\n".join(out))
    print(f"확인 기록됨 — token {token}")
    return EXIT_OK


# ── self-test (매니페스트 기반) ─────────────────────────────────────────
FIXTURES = ROOT / "tests" / "fixtures" / "gates"


def self_test() -> int:
    """⛔ 케이스 목록은 manifest.json 이 SSOT — 여기에 하드코딩하지 않는다.

    fixture 를 임시 디렉토리로 복사해 돌린다. 원장은 실행 중 mutate 되므로
    원본을 그대로 쓰면 self-test 가 자기 입력을 오염시킨다.
    """
    manifest_path = FIXTURES / "manifest.json"
    if not manifest_path.exists():
        print(f"⛔ 매니페스트 없음: {manifest_path}", file=sys.stderr)
        return EXIT_INFRA
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = manifest["cases"]

    passed, failed = 0, []
    for case in cases:
        with tempfile.TemporaryDirectory(prefix="fz-gate-selftest-") as tmp:
            sandbox = Path(tmp) / "gates"
            shutil.copytree(FIXTURES, sandbox)
            # fixture 원장의 ROOT/CWD 는 절대 경로이므로 sandbox 로 재작성한다.
            #
            # ⛔ `replace(str(FIXTURES), …)` 만으로는 부족하다. fixture 파일에 박힌
            #    경로는 **커밋한 사람의 클론 위치**이고, 플러그인 캐시나 다른 클론에서
            #    돌리면 `FIXTURES` 와 달라 매칭이 0건이 된다. 그러면 ROOT 가 남의
            #    경로를 가리켜 소유 검사에서 전부 exit 3 이 된다
            #    (2026-08-25 실측: 캐시에서 self-test 19/66).
            #
            #    그래서 **경로 모양**으로 재작성한다 — `…/tests/fixtures/gates` 로
            #    끝나는 절대 경로를 sandbox 로 바꾼다. 어느 클론에서 커밋했든 동작한다.
            marker = "/tests/fixtures/gates"
            pat = re.compile(r"(/[^\s:]*" + re.escape(marker) + r")")
            for md in sandbox.rglob("*.md"):
                body = md.read_text(encoding="utf-8")
                body = pat.sub(str(sandbox), body)
                body = body.replace(str(FIXTURES), str(sandbox))
                md.write_text(body, encoding="utf-8")

            ledger_path = sandbox / case["ledger"]
            before = ledger_path.read_text(encoding="utf-8") if ledger_path.exists() else None

            if case.get("mode") == "from-plan":
                # 변환 케이스 — 입력은 plan JSON 이고 산출물은 새 원장이다.
                out = sandbox / "fromplan" / "generated.md"
                argv = ["--from-plan", str(ledger_path), "--root", str(sandbox), "--out", str(out)]
            elif case.get("mode") == "finalize":
                # 확정 경로 — 입력 원장이 그대로 산출물이다(제자리 도장).
                argv = ["--finalize"]
            elif case.get("mode") == "oracle-fields":
                argv = ["--oracle-fields"]
            elif case.get("mode") == "cross-session":
                argv = ["--cross-session"]
            elif case.get("mode") == "discover":
                argv = None          # 디렉토리를 받는다 — 아래 실행부가 분기
            else:
                argv = list(case.get("args", ["--reverify"]))
            started = time.monotonic()
            captured, captured_err = io.StringIO(), io.StringIO()
            saved_out, saved_err = sys.stdout, sys.stderr
            sys.stdout, sys.stderr = captured, captured_err
            try:
                if argv is None:
                    code = _dispatch(["--discover", str(sandbox / "discover")],
                                     quiet=False)
                else:
                    code = _dispatch(argv + [str(ledger_path)], quiet=False)
            finally:
                sys.stdout, sys.stderr = saved_out, saved_err
            elapsed = time.monotonic() - started
            stdout_text = captured.getvalue()
            stderr_text = captured_err.getvalue()

            if case.get("mode") == "from-plan":
                generated = sandbox / "fromplan" / "generated.md"
                mutated = generated.exists()
                if mutated:
                    load(generated)  # ⛔ 산출물이 자기 계약을 만족하는지 파서가 판정한다
            else:
                after = ledger_path.read_text(encoding="utf-8") if ledger_path.exists() else None
                mutated = (before != after)

            want = case["expect"]
            reasons = []
            if code != want["exit"]:
                reasons.append(f"exit {code} (기대 {want['exit']})")
            if mutated != want["mutates"]:
                reasons.append(f"mutates {mutated} (기대 {want['mutates']})")
            # ⛔ 시간 예산 — exit code 만 보면 hang 을 놓친다. 실측으로 확인된 결함:
            #    `(cmd &)` 손자가 파이프를 붙잡아 30초 대기했는데 exit 는 1로 정상이었다.
            budget = want.get("max_seconds")
            if budget is not None and elapsed > budget:
                reasons.append(f"{elapsed:.1f}초 (한도 {budget}초)")
            # ⛔ 산출물 **내용** 축 — exit/mutates 만으로는 "썼는데 잘못 썼다"를 못 본다.
            #    실측 근거: EVIDENCE 라인 미삽입 결함이 exit 1 + mutates True 를 그대로 만족했다.
            for needle in (want.get("expect_stdout") or []):
                if needle not in stdout_text:
                    reasons.append(f"stdout 에 {needle!r} 없음")
            # ⛔ stderr 축 — 거부 **사유**는 stderr 로 나간다. exit 3 을 내는 파서 검사가
            #    여럿이라 exit 만으로는 어느 방어선이 발화했는지 구분되지 않는다.
            #    실측(2026-08-25): 절대경로 검사를 제거해도 뒤의 is_dir 검사가 같은 exit 3 을
            #    내서 fixture 가 통과했다 — 회귀가 관측되지 않았다.
            for needle in (want.get("expect_stderr") or []):
                if needle not in stderr_text:
                    reasons.append(f"stderr 에 {needle!r} 없음")
            for needle, count in (want.get("expect_contains") or {}).items():
                target = (sandbox / "fromplan" / "generated.md") if case.get("mode") == "from-plan" else ledger_path
                got = target.read_text(encoding="utf-8").count(needle) if target.exists() else 0
                if got != count:
                    reasons.append(f"{needle!r} {got}회 (기대 {count}회)")
            # ⛔ finalize 는 **도장이 자기 게이트 블록 안에** 박혔는지가 판별 축이다.
            #    개수만 세면 밀린 도장도 통과한다 — 삽입 한 줄마다 뒤쪽 스팬이 밀리는
            #    결함은 블록이 그 폭을 흡수하는 동안 exit·건수 어느 축에도 나타나지
            #    않았고, 폭을 넘어선 뒤에야 exit 3 으로 드러났다 (2026-09-02 실측).
            #    재파싱한 확정본에서 각 도장이 **자기 oracle 값**인지 대조한다.
            # ⛔ **성공을 기대하는 케이스에만** 건다 — from-plan 이 산출물 존재로 가드하는
            #    것과 같은 축이다. 무조건 재파싱하면 거부(exit 3)를 기대하는 케이스는
            #    확정본이 없는 것이 정상인데도 사유가 붙어 통과할 수 없다.
            if case.get("mode") == "finalize" and want["exit"] == EXIT_OK:
                try:
                    final_ledger = load(ledger_path)
                except (LedgerError, InfraError) as e:
                    reasons.append(f"확정본 재파싱 실패 — {e}")
                else:
                    for g in final_ledger.gates:
                        got_stamp = g.attrs.get("APPROVED_ORACLE_HASH")
                        if not g.is_runnable:
                            # ⛔ 미관측 방어선 — manifest `_notes.finalize-manual-stamp-unobserved`
                            if got_stamp is not None:
                                reasons.append(f"{g.id}: manual 인데 도장이 박혔다")
                            continue
                        want_stamp = oracle_hash(g, resolve_cwd(g, final_ledger))
                        if got_stamp is None:
                            reasons.append(f"{g.id}: 자기 블록에 도장이 없다")
                        elif got_stamp != want_stamp:
                            reasons.append(
                                f"{g.id}: 도장이 자기 oracle 과 다르다 ({got_stamp} != {want_stamp})")
            if not reasons:
                passed += 1
            else:
                failed.append(f"{case['id']}: " + ", ".join(reasons))

    for line in failed:
        print(f"  FAIL {line}")
    print(f"self-test {passed}/{len(cases)} passed")
    return EXIT_OK if not failed else EXIT_UNMET


# ── --from-plan (plan steps → 원장 생성) ────────────────────────────────
def render_ledger(steps, root: str, scope: str, title: str) -> str:
    """plan 의 steps[] 를 원장 Markdown 으로 변환한다.

    ⛔ 산문 절차가 아니라 스크립트인 이유: 변환이 결정론적이고, 산문으로 두면
       형식이 스킬마다 드리프트한다 (`guides/skill-authoring.md` §11).
    ⛔ 문자열 verify(구 계약)는 **manual 로 강등**한다. 자연어에서 명령을 지어내면
       제목과 무관한 oracle 이 생긴다 — 이 도구가 막으려는 실패 그 자체다.
    """
    lines = [f"# Gates: {title}", f"ROOT: {root}", "STATE: active"]
    if scope:
        lines.append(f"Scope: {scope}")
    lines.append("")

    demoted = []
    for step in steps:
        gid = str(step.get("id", "")).strip()
        if not gid:
            raise InfraError("step 에 id 가 없다")
        stitle = str(step.get("title", "")).strip() or gid
        verify = step.get("verify")

        if isinstance(verify, str):
            demoted.append(gid)
            verify = {"kind": "manual", "criterion": verify}
        if not isinstance(verify, dict):
            raise InfraError(f"{gid}: verify 가 VerifySpec 도 문자열도 아니다")

        criterion = str(verify.get("criterion", "")).strip()
        if not criterion:
            raise InfraError(f"{gid}: verify.criterion 이 비었다")

        # ⛔ 개행 인젝션 차단 — plan 은 모델이 쓴다. command 에 `\n  EXPECT: never\nABANDON: G1 …`
        #    을 넣으면 원장이 "포기된 게이트"로 파싱돼 ALL MET 이 된다 (2026-08-24 실측).
        for field in ("criterion", "command", "expect", "cwd"):
            val = verify.get(field)
            if isinstance(val, str) and ("\n" in val or "\r" in val):
                raise InfraError(f"{gid}: verify.{field} 에 개행 금지 — 원장 구조를 깨뜨린다")
        if "\n" in gid or "\r" in gid or "\n" in stitle or "\r" in stitle:
            raise InfraError(f"{gid}: id/title 에 개행 금지")
        kind = verify.get("kind")
        if kind not in ("command", "manual"):
            raise InfraError(f"{gid}: verify.kind 는 command|manual — 받은 값 {kind!r}")

        lines.append(f"- [ ] {gid}: {stitle}")
        if kind == "command":
            command = str(verify.get("command", "")).strip()
            expect = str(verify.get("expect", "")).strip()
            if not command or not expect:
                raise InfraError(f"{gid}: kind=command 인데 command/expect 가 비었다")
            # ⛔ criterion 을 버리지 않는다. VerifySpec 이 요구하는 필드인데
            #    원장에 안 남기면 승인받은 "무엇을 재는가"가 사라지고 CHECK 만 남는다.
            #    그러면 CHECK 를 쉬운 것으로 바꿔도 대조할 원본이 없다 (2026-08-25 실측:
            #    lint 실행 → `echo 위반 0건` 으로 교체해도 PASS 였다).
            lines.append(f"  CRITERION: {criterion}")
            lines.append(f"  CHECK: {command}")
            lines.append(f"  EXPECT: {expect}")
            cwd = str(verify.get("cwd", "")).strip()
            if cwd:
                lines.append(f"  CWD: {cwd}")
        else:
            lines.append(f"  MANUAL: {criterion}")
            lines.append(f"  CRITERION_HASH: {sha(criterion)}")
        lines.append("  EVIDENCE: pending")
        lines.append("")

    if demoted:
        print(f"⚠️ 문자열 verify {len(demoted)}건을 manual 로 강등: {', '.join(demoted)}",
              file=sys.stderr)
    return "\n".join(lines)


def from_plan(plan_path: Path, root: str, out: Path) -> int:
    try:
        data = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise InfraError(f"plan 읽기/파싱 실패: {e}")
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        raise InfraError("plan.steps 가 비었다 — 게이트 0개 원장은 만들지 않는다")

    root_real = os.path.realpath(root)
    if not Path(root_real).is_dir():
        raise InfraError(f"--root 가 디렉토리가 아니다: {root_real}")

    text = render_ledger(steps, root_real,
                         str(data.get("scope", "")).strip(),
                         str(data.get("title", "")).strip() or out.stem)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(out, text)

    # ⛔ 생성 직후 자기 산출물을 파싱한다 — 원장이 자기 계약을 만족하는지는
    #    "만들었다"가 아니라 파서가 판정한다.
    load(out)
    print(f"원장 생성: {out} (게이트 {len(steps)}개)")
    return EXIT_OK


def finalize(ledger: Ledger) -> int:
    """draft 를 확정 원장으로 만든다 — 실행 게이트마다 `APPROVED_ORACLE_HASH` 를 찍는다.

    ⛔ **이것이 없으면 승인 계약이 존재하지 않았다.** `gate_state` 와 `evaluate` 는
       `APPROVED_ORACLE_HASH` 가 **있을 때만** 대조한다. 발급하는 곳이 없었으므로
       검사 코드는 3곳에 있는데 한 번도 발화하지 않았다 — 011 과 같은 부류다.
       실측(2026-08-25): 승인된 CHECK 를 `echo <기대문자열>` 로 바꿔도 PASS 였다.

    ⛔ 도장은 `verify-gates` 판정을 **반영한 뒤** 찍는다. 찍고 나면 CHECK·EXPECT·CWD·
       TIMEOUT·CRITERION·제목 중 하나라도 바뀌면 실행이 거부된다(재승인 필요).

    ⛔ 삽입 위치는 **매 반복 재로드본에서 다시 찾는다.** 도장 한 줄이 들어갈 때마다
       뒤쪽 게이트의 스팬이 1씩 밀리는데, 루프가 시작 시점의 `Gate` 객체를 계속 내면
       n번째 도장이 (n−1)줄 앞에 박힌다. 벗어나는 조건은 **n > 그 게이트의 속성 수 + 1**
       이고, 그 전까지는 자기 블록 안에 떨어져 조용히 통과한다 — 넘어서는 순간 도장이
       게이트 줄 앞으로 나가 확정본이 자기 파서에 거부된다 (2026-09-02 실측: 실행
       게이트 10개 원장에서 `게이트에 속하지 않은 속성 APPROVED_ORACLE_HASH (line 69)`
       — exit 3).

    헤더 `APPROVED:` 는 "이 원장은 확정본"이라는 표식이다. 없으면 draft 로 보고
    경고만 낸다 — draft 단계에서 도장을 요구하면 순서가 뒤집힌다(Phase 2 평가자가
    볼 CHECK 가 도장보다 먼저 있어야 한다).
    """
    lines = ledger_lines(ledger)
    gate_ids = [g.id for g in ledger.gates]
    stamped, skipped = 0, 0
    for gid in gate_ids:
        # ⛔ 재로드본에서 id 로 다시 찾는다 — 옛 `Gate` 객체의 `attr_lines` 는 앞선
        #    삽입만큼 낡아 있어 도장이 남의 줄에 박힌다.
        gate = next((g for g in ledger.gates if g.id == gid), None)
        if gate is None:
            raise LedgerError(f"{gid}: 확정 중 게이트가 사라졌다 — 도장 위치를 정할 수 없다")
        if not gate.is_runnable:
            skipped += 1
            continue
        cwd = resolve_cwd(gate, ledger)
        h = oracle_hash(gate, cwd)
        existing = gate.attr_lines.get("APPROVED_ORACLE_HASH")
        if existing is not None:
            lines[existing - 1] = f"  APPROVED_ORACLE_HASH: {h}"
        else:
            # ⛔ CAS — 다른 쓰기 경로는 전부 블록 해시를 대조하는데 여기만 밖에 있었다.
            #    단일 writer 가정으로 덮이지만 "가정으로 보호된다"와 "규율 밖에 있다"는 다르다.
            baseline = gate_block_hash(ledger, gate.id)
            anchor = max(gate.attr_lines.values())
            lines.insert(anchor, f"  APPROVED_ORACLE_HASH: {h}")
            # 삽입으로 뒤쪽 게이트의 스팬이 밀리므로 매 게이트마다 재파싱한다.
            fresh = load(ledger.path)
            if gate_block_hash(fresh, gate.id) != baseline:
                raise LedgerError(
                    f"{gate.id}: 확정 중 이 게이트가 변경됨 — stale 도장을 거부한다 (CAS 충돌)")
            write_atomic(ledger.path, "\n".join(lines))
            ledger = load(ledger.path)
            lines = ledger_lines(ledger)
        stamped += 1

    text = "\n".join(lines)
    if "\nAPPROVED:" not in text and not text.startswith("APPROVED:"):
        out, done = [], False
        for raw in text.split("\n"):
            out.append(raw)
            if not done and raw.startswith("STATE:"):
                out.append("APPROVED: yes")
                done = True
        if not done:
            raise LedgerError("STATE 헤더를 찾지 못해 APPROVED 를 넣을 수 없다")
        text = "\n".join(out)
    write_atomic(ledger.path, text)
    load(ledger.path)          # 확정본이 자기 계약을 만족하는지 파서가 판정한다
    print(f"확정: 실행 게이트 {stamped}개에 승인 도장, manual {skipped}개 제외")
    return EXIT_OK


# ── --set-state (STATE 전이) ────────────────────────────────────────────
def set_state(ledger: Ledger, target: str) -> int:
    """STATE 를 전이한다.

    ⛔ **전진은 조건부, 역행은 자유.** 전진(active → ready_for_review → closed)은
       "이만큼 끝났다"는 주장이므로 증명이 필요하고, 역행은 "다시 열겠다"라 증명이 없어도 된다.
       역행을 막으면 재작업이 막힌다.

    ⛔ 전진 판정은 **기록된 증거**로 한다(CHECK 미실행). 전이마다 전체 재실행은 비싸고,
       fz-code 가 Step 마다 게이트를 돌렸으므로 증거가 최신이다. 증거가 낡았다고 의심되면
       `--reverify` 를 먼저 돌리는 것이 호출자 책임이다.
    """
    if target not in STATES:
        raise InfraError(f"STATE 는 {'/'.join(STATES)} 중 하나 — 받은 값 {target!r}")

    # ⛔ 판정은 **디스크 최신본**으로 한다. 인자로 받은 ledger 는 호출 전 파스라
    #    그 사이 편집된 내용을 반영하지 못한다 (2026-08-24 실측: 파스 후 게이트를 unmet 으로
    #    바꿔도 set_state 가 0 을 반환하고 ready_for_review 를 썼다).
    fresh = load(ledger.path)
    current = fresh.state
    if current == target:
        print(f"STATE 이미 {target}")
        return EXIT_OK

    forward = STATES.index(target) > STATES.index(current)
    if forward:
        # ⛔ 인접 단계만 전진한다. active → closed 직행은 fz-review 재검증을 통째로 건너뛴다.
        if STATES.index(target) - STATES.index(current) != 1:
            reason = (f"⛔ {current} → {target} 거부: 인접 단계만 전진 가능 "
                      f"(다음 단계는 {STATES[STATES.index(current) + 1]})")
            print(reason, file=sys.stderr)
            print("REJECT: non-adjacent-transition")   # self-test 관측용 — 축 구분
            return EXIT_UNMET
        unmet = [g.id for g in fresh.gates if gate_state(g, fresh) == "unmet"]
        if unmet:
            print(f"⛔ {current} → {target} 거부: 미충족 게이트 {len(unmet)}개 — {', '.join(unmet)}",
                  file=sys.stderr)
            print("REJECT: unmet-gates")               # self-test 관측용 — 축 구분
            print("   (증거가 낡았으면 --reverify 후 재시도)", file=sys.stderr)
            return EXIT_UNMET

    text = fresh.path.read_text(encoding="utf-8")
    baseline = sha(text)
    lines, out, done = text.split("\n"), [], False
    for raw in lines:
        if not done and raw.startswith("STATE:"):
            out.append(f"STATE: {target}")
            done = True
            continue
        out.append(raw)
    if not done:
        raise LedgerError("STATE 헤더를 찾지 못했다")
    if sha(ledger.path.read_text(encoding="utf-8")) != baseline:
        raise LedgerError("전이 중 원장이 변경됨 (CAS 충돌)")
    write_atomic(ledger.path, "\n".join(out))
    arrow = "→" if forward else "←"
    print(f"STATE: {current} {arrow} {target}")
    return EXIT_OK


# ── CLI ─────────────────────────────────────────────────────────────────
def _dispatch(argv, quiet: bool = False) -> int:
    parser = argparse.ArgumentParser(
        prog="gate_check.py",
        description="fz 완료 게이트 판정기 (exit 0=충족 1=미충족 2=인프라 3=원장오류)")
    parser.add_argument("ledger", nargs="?", help="원장 경로")
    parser.add_argument("--status", action="store_true", help="파싱만 — CHECK 미실행")
    parser.add_argument("--reverify", action="store_true",
                        help="이미 충족된 게이트까지 재실행 (강등 가능)")
    parser.add_argument("--confirm", metavar="GATE_ID", help="MANUAL 게이트 사용자 확인")
    parser.add_argument("--set-state", metavar="STATE",
                        help="STATE 전이 (active|ready_for_review|closed). 전진은 전 게이트 충족 시만")
    parser.add_argument("--self-test", action="store_true", help="매니페스트 fixture 실행")
    parser.add_argument("--from-plan", metavar="PLAN_JSON",
                        help="plan steps[] 를 원장으로 변환 (--root, --out 필수)")
    parser.add_argument("--root", metavar="DIR", help="--from-plan 의 WORK_DIR (realpath 로 정규화)")
    parser.add_argument("--out", metavar="FILE", help="--from-plan 의 출력 원장 경로")
    parser.add_argument("--discover", metavar="DIR",
                        help="DIR 하위 확정 원장을 찾아 상태 요약 (health-check 용). 미충족은 exit 0 + 건수 · 계약 위반만 exit 3)")
    parser.add_argument("--cross-session", action="store_true",
                        help="승인 도장·증거 서명의 환경 안정성 검사 (self-test 용)")
    parser.add_argument("--oracle-fields", action="store_true",
                        help="oracle_hash 가 승인 계약 필드 전부에 민감한지 검사 (self-test 용)")
    parser.add_argument("--finalize", action="store_true",
                        help="draft 확정 — 실행 게이트마다 APPROVED_ORACLE_HASH 도장 + APPROVED 헤더")
    parser.add_argument("--verdict-check", metavar="RESPONSE_JSON",
                        help="verify-gates 응답이 원장을 전수 판정했는지 대조 (게이트 수·id 집합·summary 합계)")
    parser.add_argument("--only", metavar="IDS",
                        help="쉼표로 구분한 게이트 id 만 판정 (fz-code 의 Step 단위 실행)")
    parser.add_argument("--budget", type=float, default=None,
                        help="총 실행 예산(초). 미지정 시 게이트별 TIMEOUT 합")

    try:
        opt = parser.parse_args(argv)
    except SystemExit as e:
        # ⛔ argparse 는 --help 에서도 SystemExit 를 던진다(코드 0). 이걸 INFRA 로 뭉개면
        #    `--help` 가 exit 2 가 되어 문서가 가리키는 "문법 SSOT" 진입로가 실패로 보인다.
        return EXIT_OK if e.code == 0 else EXIT_INFRA

    if opt.self_test:
        return self_test()
    # ⛔ ledger 위치 인자 요구보다 **먼저** — discover 는 디렉토리를 받는다
    if opt.discover:
        return discover(opt.discover)
    if opt.from_plan:
        if not opt.root or not opt.out:
            print("⛔ --from-plan 은 --root 와 --out 이 필요하다", file=sys.stderr)
            return EXIT_INFRA
        saved = sys.stdout
        if quiet:
            sys.stdout = open(os.devnull, "w")
        try:
            return from_plan(Path(opt.from_plan), opt.root, Path(opt.out))
        except LedgerError as e:
            print(f"INVALID LEDGER: {e}", file=sys.stderr)
            return EXIT_INVALID
        except InfraError as e:
            print(f"INFRA: {e}", file=sys.stderr)
            return EXIT_INFRA
        except OSError as e:
            print(f"INFRA: 파일시스템 오류 — {e}", file=sys.stderr)
            return EXIT_INFRA
        finally:
            if quiet:
                sys.stdout.close()
                sys.stdout = saved
    if opt.status and opt.reverify:
        print("⛔ --status 와 --reverify 는 함께 쓸 수 없다", file=sys.stderr)
        return EXIT_INFRA
    if not opt.ledger:
        print("⛔ 원장 경로가 필요하다", file=sys.stderr)
        return EXIT_INFRA

    stdout = sys.stdout
    if quiet:
        sys.stdout = open(os.devnull, "w")
    try:
        ledger = load(Path(opt.ledger).resolve())
        if opt.cross_session:
            return cross_session(ledger)
        if opt.oracle_fields:
            return oracle_fields(ledger)
        if opt.finalize:
            return finalize(ledger)
        if opt.verdict_check:
            return verdict_check(ledger, opt.verdict_check)
        if opt.confirm:
            return confirm(ledger, opt.confirm)
        if opt.set_state:
            return set_state(ledger, opt.set_state)
        mode = "status" if opt.status else ("reverify" if opt.reverify else "run")
        budget = opt.budget if opt.budget is not None else float(DEFAULT_TIMEOUT_S * 8)
        return evaluate(ledger, mode, budget, opt.only)
    except LedgerError as e:
        print(f"INVALID LEDGER: {e}", file=sys.stderr)
        return EXIT_INVALID
    except InfraError as e:
        print(f"INFRA: {e}", file=sys.stderr)
        return EXIT_INFRA
    except OSError as e:
        # ⛔ mkstemp·fsync·replace·재읽기의 OSError 가 traceback 으로 새면 exit 1 이 되어
        #    "미충족(차단)"으로 오독된다. 읽기전용·디스크풀은 판정 실패가 아니라 인프라다.
        print(f"INFRA: 파일시스템 오류 — {e}", file=sys.stderr)
        return EXIT_INFRA
    finally:
        if quiet:
            sys.stdout.close()
            sys.stdout = stdout


VERDICT_VALUES = ("accept", "revise", "demote_to_manual")
VERDICT_FIELDS = ("id", "title", "kind", "measurement_fit", "noninteractive",
                  "rerunnable", "determinism", "side_effects", "verdict", "reason")


ORACLE_FIELD_PROBES = (
    ("CHECK", "echo tampered"),
    ("EXPECT", "tampered"),
    ("CRITERION", "완전히 다른 합격 조건"),
    ("TIMEOUT", "999"),
)


def cross_session(ledger: Ledger) -> int:
    """승인 도장과 증거 서명이 **환경 변화에 안정한지** 검사한다.

    ⛔ 이 축은 원장 fixture 로 볼 수 없다 — 한 프로세스 안에서 환경을 바꿔야 한다.

    ⛔ **왜 필요한가.** `oracle_hash` 에 `SHELL`·`PATH` 가 들어 있으면 fz-plan 이 세션 A 에서
       도장을 찍고 fz-code 가 세션 B 에서 실행할 때 exit 3(차단)이 된다. 메시지는
       "승인 후 oracle 이 바뀌었다"라며 원인을 잘못 지목한다. 별 세션인 것은 예외가 아니라
       설계된 흐름이다(compact · 다음 날 · 다른 터미널 · direnv/nvm shim).
       증거 서명도 같은 병을 앓아 통과한 게이트가 unmet 으로 읽혔다.
    """
    gate = ledger.gates[0]
    cwd = resolve_cwd(gate, ledger)
    saved = {k: os.environ.get(k) for k in ("PATH", "SHELL")}
    try:
        base_oracle = oracle_hash(gate, cwd)
        base_env = env_fingerprint()
        os.environ["PATH"] = "/usr/bin:/bin"
        os.environ["SHELL"] = "/bin/bash"
        moved_oracle = oracle_hash(gate, cwd)
        moved_env = env_fingerprint()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    bad = []
    if base_oracle != moved_oracle:
        bad.append("oracle_hash 가 환경에 흔들린다 — 승인 도장이 cross-session 에서 깨진다")
    if base_env == moved_env:
        bad.append("env_fingerprint 가 환경을 반영하지 않는다 — provenance 축이 죽었다")
    print("CROSS_SESSION:" + ("OK" if not bad else ";".join(bad)))
    return EXIT_UNMET if bad else EXIT_OK


def oracle_fields(ledger: Ledger) -> int:
    """`oracle_hash` 가 승인 계약에 필요한 필드 전부에 민감한지 검사한다.

    ⛔ **fixture 로는 이 축을 관측할 수 없다.** `oracle_hash` 는 `path_fingerprint()` 와
       `SHELL` 을 포함하므로 머신마다 값이 달라, 정적 원장에 유효한
       `APPROVED_ORACLE_HASH` 를 넣어 둘 수 없다. 그래서 순수 함수 대조로 본다.

    한 필드라도 무감각하면 그 필드는 승인 후 자유롭게 바꿀 수 있다 —
    `CRITERION` 이 빠져 있었다면 "무엇을 재는가"를 바꿔도 도장이 유효하다.
    """
    gate = ledger.gates[0]
    cwd = resolve_cwd(gate, ledger)
    base = oracle_hash(gate, cwd)
    numb = []
    for field, newval in ORACLE_FIELD_PROBES:
        saved = gate.attrs.get(field)
        gate.attrs[field] = newval
        if oracle_hash(gate, cwd) == base:
            numb.append(field)
        if saved is None:
            gate.attrs.pop(field, None)
        else:
            gate.attrs[field] = saved
    saved_title = gate.title
    gate.title = "완전히 다른 제목"
    if oracle_hash(gate, cwd) == base:
        numb.append("title")
    gate.title = saved_title

    print("ORACLE_INSENSITIVE:" + (",".join(numb) if numb else "none"))
    return EXIT_UNMET if numb else EXIT_OK


def discover(root_dir: str) -> int:
    """`root_dir` 하위 확정 원장을 찾아 상태를 요약한다 — health-check 용.

    ⛔ **미충족은 실패가 아니다.** 작업 중 원장이 미충족인 것은 정상 상태이고,
       exit 에 반영하면 원장 있는 모든 세션에서 `/fz-manage check` 가 빨개져 사람이
       health-check 를 안 돌리게 된다. `lint_doc_freshness` 선례와 같다 —
       findings 가 있어도 exit 0 이고 **건수만** 보고한다.

    ⛔ **원장 계약 위반(exit 3)은 실패다.** fz 가 만든 원장이 자기 계약을 어긴 것은
       plugin 자산 결함이고, 그것이 health-check 의 관심사다.

    이것이 hook 미설치 머신의 유일한 노출 경로다 — 배선 1~3 은 SKILL.md 산문이라
    건너뛰어도 신호가 없고, `FZ_GATES_TRACE` 는 환경변수 opt-in 이다.
    """
    ledgers, note = find_ledgers(root_dir, os.environ.get(LEDGER_ENV, ""))
    if not ledgers:
        print(note or "원장 0건 (게이트 미사용)")
        return EXIT_OK

    met_n, unmet_n, invalid = 0, 0, []
    for path in ledgers:
        try:
            led = load(path)
        except LedgerError as e:
            invalid.append(f"{path}: {e}")
            continue
        except InfraError as e:
            print(f"⚠️  {path}: {e}", file=sys.stderr)
            continue
        if led.state == "closed":
            met_n += 1
            continue
        bad = [g.id for g in led.gates if gate_state(g, led) == "unmet"]
        if bad:
            unmet_n += 1
            print(f"  미충족 {path} — {bad}")
        else:
            met_n += 1

    for line in invalid:
        print(f"⛔ 계약 위반 {line}", file=sys.stderr)
    summary = f"원장 {len(ledgers)}건 (충족·closed {met_n} · 미충족 {unmet_n} · 계약위반 {len(invalid)})"
    if note:
        summary += f" · {note}"
    print(summary)
    return EXIT_INVALID if invalid else EXIT_OK


def verdict_check(ledger: Ledger, response_path: str) -> int:
    """`verify-gates` 응답이 **현재** 원장을 전수 판정했는지 대조한다.

    ⛔ **스키마만으로는 보장되지 않는다.** `codex_gate_verdict_schema` 는
    `gates: []`(빈 배열)·중복 id·원장에 없는 id·거짓 `summary` 합계를 전부 통과시킨다.
    누락은 미판정이며 통과가 아니므로 호출자가 대조해야 한다.

    ⛔ 이 대조를 산문 지시로 두지 않는 이유 — 이 계층이 없애려는 것이 바로
    "문서에 적힌 대조"다. 눈으로 하는 확인은 건너뛰어도 신호가 없다.

    ⛔ **id 집합만 보면 stale 응답이 통과한다.** 원장의 제목·kind 가 바뀌어도 id 는
    그대로이므로, 옛 oracle 을 보고 낸 판정이 새 oracle 에 붙는다. `(id, title, kind)`
    삼중으로 묶는다 — 응답이 그 두 필드를 required 로 담으므로 추가 비용이 없다.

    ⛔ **summary 는 배열에서 재계산해 비교한다.** 응답이 스스로 신고한 수치를 믿으면
    보고가 거짓이 될 수 있고, 음수끼리 상쇄해 합계만 맞추는 것도 가능하다.
    """
    try:
        data = json.loads(Path(response_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise InfraError(f"응답을 읽을 수 없다: {e}")
    if not isinstance(data, dict):
        print("REJECT: 응답이 객체가 아니다")
        return EXIT_UNMET

    gates = data.get("gates")
    if not isinstance(gates, list):
        print("REJECT: gates 가 배열이 아니다 — 미판정")
        return EXIT_UNMET

    reasons = []
    if not str(data.get("schemaVersion") or "").strip():
        reasons.append("schemaVersion 부재")

    # 각 항목의 필수 필드·enum
    for n, g in enumerate(gates):
        if not isinstance(g, dict):
            reasons.append(f"gates[{n}] 이 객체가 아니다")
            continue
        missing = [f for f in VERDICT_FIELDS if not str(g.get(f) or "").strip()
                   and not isinstance(g.get(f), bool)]
        if missing:
            reasons.append(f"gates[{n}]({g.get('id')}) 필드 누락 {missing}")
        if g.get("verdict") not in VERDICT_VALUES:
            reasons.append(f"gates[{n}]({g.get('id')}) verdict 값 이상: {g.get('verdict')!r}")

    ledger_map = {g.id: (g.title, "manual" if g.is_manual else "command")
                  for g in ledger.gates}
    ids = [g.get("id") for g in gates if isinstance(g, dict)]
    if len(gates) != len(ledger_map):
        reasons.append(f"게이트 수 {len(gates)} != 원장 {len(ledger_map)}")
    if len(set(ids)) != len(ids):
        reasons.append(f"중복 id {sorted({i for i in ids if ids.count(i) > 1})}")
    missing = sorted(set(ledger_map) - set(ids))
    extra = sorted(set(ids) - set(ledger_map))
    if missing:
        reasons.append(f"미판정 {missing}")
    if extra:
        reasons.append(f"원장에 없는 id {extra}")

    # stale 응답 차단 — 제목·kind 가 현재 원장과 일치해야 한다
    for g in gates:
        if not isinstance(g, dict) or g.get("id") not in ledger_map:
            continue
        want_title, want_kind = ledger_map[g["id"]]
        if str(g.get("title", "")).strip() != want_title:
            reasons.append(f"{g['id']}: 제목이 원장과 다르다 — stale 응답 (응답 {g.get('title')!r})")
        if str(g.get("kind", "")).strip() != want_kind:
            reasons.append(f"{g['id']}: kind 가 원장과 다르다 (응답 {g.get('kind')!r} / 원장 {want_kind})")

    # summary 는 신고값을 믿지 않고 배열에서 재계산한다
    summary = data.get("summary") or {}
    if not isinstance(summary, dict):
        reasons.append("summary 가 객체가 아니다")
    else:
        derived = {k: sum(1 for g in gates
                          if isinstance(g, dict) and g.get("verdict") == k)
                   for k in VERDICT_VALUES}
        for k, want in derived.items():
            got = summary.get(k)
            if not isinstance(got, int) or isinstance(got, bool):
                reasons.append(f"summary.{k} 가 정수가 아니다: {got!r}")
            elif got < 0:
                reasons.append(f"summary.{k} 가 음수: {got}")
            elif got != want:
                reasons.append(f"summary.{k} {got} != 실측 {want}")
        total = summary.get("total")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            reasons.append(f"summary.total 이 음이 아닌 정수가 아니다: {total!r}")
        elif total != len(gates):
            reasons.append(f"summary.total {total} != 판정 수 {len(gates)}")

    if reasons:
        for r in reasons:
            print(f"REJECT: {r}")
        return EXIT_UNMET
    print(f"VERDICT OK ({len(gates)}/{len(ledger_map)} 판정, 제목·kind 일치)")
    return EXIT_OK


def _trace(argv, code: int) -> None:
    """호출 사실을 append-only 로 남긴다 — `FZ_GATES_TRACE` 가 가리키는 파일에.

    ⛔ **왜 플래그가 아니라 환경변수인가.** 이 기록의 목적은 "스킬이 이 판정기를
    실제로 부르는가"를 관측하는 것이다. 플래그로 만들면 SKILL.md 의 호출 줄을
    고쳐야 하고, 그러면 관측이 관측 대상(배선)에 의존해 순환한다. 환경변수는
    호출부를 한 글자도 건드리지 않는다.

    ⛔ 실패해도 판정에 영향을 주지 않는다. 관측 장치가 판정을 바꾸면 안 된다.
    """
    path = os.environ.get("FZ_GATES_TRACE")
    if not path:
        return
    try:
        record = {"argv": list(argv), "cwd": os.getcwd(), "exit": code,
                  "stamp": time.strftime("%Y-%m-%dT%H:%M:%S")}
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def main() -> int:
    argv = sys.argv[1:]
    code = _dispatch(argv)
    _trace(argv, code)
    return code


if __name__ == "__main__":
    sys.exit(main())
