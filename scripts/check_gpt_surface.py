#!/usr/bin/env python3
# lint:no-root-anchor — 루트를 `--root` 로 받는다(기본값은 이 파일 기준 부모 상수).
"""fz 표면에 `codex` 호칭이 **보존 규칙 밖에서** 다시 나타나지 않는지 검사한다 (Track C).

⛔ 왜 필요한가: v4.32.1 에서 codex→GPT 개명을 마쳤는데도 새 문서·계획·인용에 codex 호칭이
   다시 들어왔다(2026-09-25, 사용자: "codex 전부 fz 에서 지워달라고 하고 작업도 몇번했는데").
   정리는 한 번 하면 끝나지만 **재유입은 매번 일어난다** — 막는 것은 절차가 아니라 검사다.

모델·판정·검증자 호칭은 **GPT**, 실행 파일은 래퍼(`scripts/gpt-exec.sh`)가 격리한다.
보존 근거는 두 가지뿐이다: ①바꾸면 도구가 깨진다 ②바꾸면 사실이 거짓이 된다.

허용 판정은 두 층이다
  (a) 범주 토큰 — 경로·패키지·플러그인 명령·과거 산출물 파일명·권한 패턴·URL·트리거 쿼리·개명 이력
  (b) 보존 행 — `tests/fixtures/gpt-surface-keep.tsv` 의 (파일, 정규화 텍스트) 와 같은 줄 (범주로 설명되지 않는 도구 코드)
  래퍼 경계 파일(`scripts/gpt-exec.sh`·`scripts/check-gpt-flags.sh`)은 전체 허용 — 실행 파일명 격리 지점이다.

⛔ 이행(Track C) 전용 모드(원장 대조·keep identity·원장 구조 검사)는 이 검사기에 두지 않는다 — 입력(원장)이 레포 밖이라
   플러그인 사용자는 쓸 수 없다. 이행 작업 폴더의 도구가 맡는다 (fz-review 2026-09-25 S1).

exit: 0=충족 · 1=위반 · 2=측정 실패(⛔ 통과 아님 — 스캔 대상 0개는 "위반 0건" 이 아니다)
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

OK, VIOLATION, UNRUN = 0, 1, 2
DEFAULT_ROOT = pathlib.Path(__file__).resolve().parent.parent
BOUNDARY = {"scripts/gpt-exec.sh", "scripts/check-gpt-flags.sh",   # 래퍼 — 실행 파일명 격리 지점
            "scripts/check_gpt_surface.py",                          # 이 탐지기(패턴에 토큰을 담는다)
            "schemas/tool-inventory.json"}                           # 외부 실행 파일 목록 — 키가 실행 파일명이다
# 이력 파일 — 과거 실행·결정의 기록이다. 호칭을 바꾸면 당시 기록이 달라진다(CHANGELOG·릴리즈 노트·실험 로그)
EXCLUDE_PREFIX = ("docs/releases/", "tests/fixtures/", ".git/", "CHANGELOG.md", "experiment-log.md")
SUFFIXES = (".md", ".js", ".py", ".sh", ".json", ".yaml", ".toml")   # yaml·toml — GPT 스킬 메타(agents/openai.yaml) · 역할 파일
TOKEN = re.compile(r"codex", re.I)

# (a) 범주 토큰 — 원장의 keep 범주에서 나온 **형태**다(행 목록이 아니다). 새 범주는 원장 검수 후에만 추가한다.
ALLOW = [
    r"(~|\$HOME|\$\{HOME\}|\$\{CODEX_HOME:-\$HOME)?/?\.codex(/[\w./*${}-]*)?",   # 경로 (~/.codex/…)
    r"\bCODEX_HOME\b",
    r"@openai/codex\b", r"github\.com/openai/codex[\w./-]*",                   # 패키지·저장소
    r"developers\.openai\.com/codex[\w./-]*", r"learn\.chatgpt\.com/docs/codex[\w./-]*",  # URL
    r"/?codex:(?:\*|[a-z][\w-]*)", r"\bopenai-codex\b", r"\bcodex-companion\b",       # 플러그인 네임스페이스
    r"\bcodex[-_](?:review|verify|verdict|bug|workspace|utilization|residue)[\w*.-]*",  # 과거 산출물 파일명
    r"Bash\(codex \*\)",                                                       # allowed-tools 권한 패턴
    r"예:\s*codex", r"codex로 [^\"|]{0,30}해줘", r"codex exec로 직접 검증 돌려줘",   # 인텐트 트리거 쿼리
    r"codex\s*(?:→|->)\s*gpt", r"\bget_codex_skill\b",                          # 개명 이력
    r"\bcodex mcp list\b",                                                     # 과거 CLI 버그 기록(실제 명령)
]
ALLOW_RE = re.compile("|".join(f"(?:{p})" for p in ALLOW), re.I)
def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def residual(line: str) -> bool:
    """허용 범주 토큰을 지운 뒤에도 codex 가 남는가."""
    return bool(TOKEN.search(ALLOW_RE.sub("", line)))


class Unreadable(Exception):
    """열거 실패 — 0건과 다른 축이다(F-271)."""


def list_files(root: pathlib.Path):
    """검사 대상 파일. git 저장소면 git 이 무시하지 않는 파일만 — 무시된 로컬 작업 폴더(`.fz-work/` 등)는
    배포물이 아니다(F-339: 같은 커밋이 그 폴더가 있는 트리에서만 health-check 를 실패시켰다).
    `.git` 은 디렉터리(일반 저장소)이거나 파일(worktree)이다. git 이 없는 설치본은 rglob 그대로.
    """
    if not (root / ".git").exists():
        return sorted(p for p in root.rglob("*") if p.is_file())
    try:
        proc = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                              capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        raise Unreadable(f"git ls-files 실행 실패: {type(e).__name__}: {e}") from e
    if proc.returncode != 0:
        raise Unreadable(f"git ls-files exit {proc.returncode}: {proc.stderr.decode('utf-8', 'replace').strip()[:200]}")
    names = [n for n in proc.stdout.decode("utf-8", "surrogateescape").split("\0") if n]
    return sorted(p for p in (root / n for n in names) if p.is_file())   # 추적 중 삭제된 파일은 뺀다


def scan(root: pathlib.Path):
    files = [p for p in list_files(root) if p.suffix in SUFFIXES]
    rel = [(p, p.relative_to(root).as_posix()) for p in files]
    rel = [(p, r) for p, r in rel if not r.startswith(EXCLUDE_PREFIX) and r not in BOUNDARY]
    hits = []
    for p, r in rel:
        try:
            lines = p.read_text(encoding="utf-8").split("\n")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(lines, 1):
            if TOKEN.search(line) and residual(line):
                hits.append((r, i, norm(line)))
    return rel, hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    return self_test() if a.self_test else run(a.root)


def run(root: pathlib.Path) -> int:
    try:
        files, hits = scan(root)
    except Unreadable as e:
        print(f"UNRUN: 검사 대상 열거 실패 — {e}")
        return UNRUN
    if not files:
        print(f"UNRUN: 스캔 대상 0개 — {root} (경로 확인)")
        return UNRUN
    keep = {}
    kf = root / "tests" / "fixtures" / "gpt-surface-keep.tsv"
    if kf.exists():
        for line in kf.read_text(encoding="utf-8").split("\n"):
            if "\t" in line:
                f, t = line.split("\t", 1)
                keep.setdefault(f, set()).add(norm(t))
    residue = [(f, i, t) for f, i, t in hits if t not in keep.get(f, set())]
    for f, i, t in residue:
        print(f"VIOLATION {f}:{i}: 보존 규칙 밖 codex — {t[:120]}")
    print(f"gpt-surface: files={len(files)} residue={len(residue)} violations={len(residue)}")
    return VIOLATION if residue else OK


def self_test() -> int:
    import shutil
    import tempfile
    passed, fails = 0, []

    def expect(name, got, want):
        nonlocal passed
        if got == want:
            passed += 1
        else:
            fails.append(f"{name}: want {want} got {got}")

    # 허용 범주 — 걸려선 안 되는 것
    for line in ("설정은 `~/.codex/config.toml`", "`$HOME/.codex/skills/fz-x/SKILL.md`", "CODEX_HOME",
                 "`npm i -g @openai/codex`", "`/codex:review --base`", "`codex-review*.md` 인용", "Bash(codex *)",
                 "예: codex, 교차검증", '"codex로 리뷰해줘"', "2026-09-06 codex→gpt 개명", "`get_codex_skill()`",
                 "`codex mcp list` 는 plugin 이 아니다", "https://developers.openai.com/codex/changelog"):
        expect(f"허용 '{line[:24]}'", residual(line), False)
    # 위반 — 걸려야 하는 것
    for line in ("Codex CLI 로 교차 검증", "`codex exec review -o`", "[외부: codex]", "Codex 리뷰(2026-09-06)",
                 "raw codex exec 는 제안하지 말고", "codex는 검증 전용"):
        expect(f"위반 '{line[:24]}'", residual(line), True)

    d = pathlib.Path(tempfile.mkdtemp(prefix="fz-gs-"))
    try:
        (d / "guides").mkdir()
        (d / "scripts").mkdir()
        (d / "tests" / "fixtures").mkdir(parents=True)
        (d / "guides" / "a.md").write_text("경로 `~/.codex/config.toml`\nCodex CLI 로 검증\n", encoding="utf-8")
        (d / "scripts" / "gpt-exec.sh").write_text("codex exec -- x\n", encoding="utf-8")
        _, hits = scan(d)
        expect("스캔 — 래퍼 경계 제외 · 경로 허용 → 잔존 1", len(hits), 1)
        expect("보존 규칙 밖 잔존 → 위반", run(d), VIOLATION)
        (d / "tests" / "fixtures" / "gpt-surface-keep.tsv").write_text("guides/a.md\tCodex CLI 로 검증\n", encoding="utf-8")
        expect("keep 파일 행은 통과", run(d), OK)
        (d / "guides" / "a.md").write_text("경로 `~/.codex/config.toml`\nCodex CLI 로 검증 — 뒤에 덧붙임\n", encoding="utf-8")
        expect("keep 행과 달라진 줄 → 위반 (완전 일치만 보존)", run(d), VIOLATION)
        (d / "guides" / "meta.yaml").write_text("description: Codex 로 검증\n", encoding="utf-8")
        _, hits = scan(d)
        expect("yaml 도 스캔한다(GPT 스킬 메타 agents/openai.yaml)", any(r == "guides/meta.yaml" for r, _, _ in hits), True)
        empty = pathlib.Path(tempfile.mkdtemp(prefix="fz-gs-empty-"))
        expect("스캔 대상 0개 → 측정 실패", run(empty), UNRUN)
        shutil.rmtree(empty)
    finally:
        shutil.rmtree(d)

    # git 인식 (F-339) — 무시된 로컬 폴더는 배포물이 아니다
    g = pathlib.Path(tempfile.mkdtemp(prefix="fz-gs-git-"))
    git = lambda *a, cwd=g: subprocess.run(["git", "-C", str(cwd), *a], capture_output=True, check=True)
    try:
        git("init", "-q")
        git("-c", "user.email=t@t", "-c", "user.name=t", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
            "commit", "-q", "--allow-empty", "-m", "init")   # 사용자 전역 훅 · 서명 설정과 끊는다(review_snapshot.sh 와 같다)
        (g / ".gitignore").write_text(".fz-work/\n", encoding="utf-8")
        (g / "README.md").write_text("neutral\n", encoding="utf-8")
        (g / ".fz-work").mkdir()
        (g / ".fz-work" / "index.md").write_text("- Codex challenger: 1\n", encoding="utf-8")
        expect("git 무시 폴더의 낱말 → 위반 아님", run(g), OK)
        (g / "README.md").write_text("Codex CLI 로 검증\n", encoding="utf-8")
        expect("미추적이지만 무시되지 않은 파일의 낱말 → 위반", run(g), VIOLATION)
        (g / "README.md").write_text("neutral\n", encoding="utf-8")
        wt = pathlib.Path(tempfile.mkdtemp(prefix="fz-gs-wt-")) / "wt"
        git("worktree", "add", "-q", "--detach", str(wt))
        (wt / ".gitignore").write_text(".fz-work/\n", encoding="utf-8")
        (wt / "README.md").write_text("neutral\n", encoding="utf-8")
        (wt / ".fz-work").mkdir()
        (wt / ".fz-work" / "x.md").write_text("Codex CLI 로 검증\n", encoding="utf-8")
        expect("worktree(.git 파일) 도 git 경로 — 무시 폴더 제외", ((wt / ".git").is_file(), run(wt)), (True, OK))
        shutil.rmtree(wt.parent)
        bad = pathlib.Path(tempfile.mkdtemp(prefix="fz-gs-bad-"))
        (bad / ".git").write_text("gitdir: /nonexistent/path\n", encoding="utf-8")
        (bad / "a.md").write_text("neutral\n", encoding="utf-8")
        expect("깨진 .git → 측정 실패(0건으로 읽지 않는다)", run(bad), UNRUN)
        shutil.rmtree(bad)
    finally:
        shutil.rmtree(g)

    for f in fails:
        print(f"  FAIL {f}")
    total = passed + len(fails)
    print(f"self-test {passed}/{total} passed")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
