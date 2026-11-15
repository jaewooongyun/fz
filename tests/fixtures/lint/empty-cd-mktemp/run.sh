#!/bin/bash
# 빈 mktemp 치환 cd lint fixture (F-355) — lint_contracts.py #N14 가 위험 꼴을 실행 코드에서 잡고, 문서 · 주석 · heredoc 의
# BAD 예시와 안전 꼴은 놓아두는지 동작으로 본다.
#   self-tree    이 트리: `lint_contracts.py --only N14` exit 0 · `OK #N14` · 후보 수 ≥ MIN_HITS (현 트리 오탐 0)
#   repro-4      v4.42.0 이 고친 4곳의 고치기 전 줄(db7c411^ · 4fba0db^ 원문)을 원래 줄 번호에 둔 셀 → 그 4 위치에서만 위반
#   repro-plant  이 트리 사본의 independent-arm 러너 안전 꼴 바로 뒤에 위험 꼴 1줄을 심고 lint 전체 → exit 1 · 위반은 그 줄 #N14 하나
#   variants     pushd · mktemp -d -t · 따옴표 없음 · 백틱 · 옵션 · 환경 접두 · 서브셸 · 닫힌 heredoc 뒤 · .py/.js 셸 문자열 → 전부 위반
#   docs         모듈 BAD 예시 · 레지스트리 INDEX 행 사본 · CHANGELOG · 릴리스 노트(.md) → 위반 0
#   comments     고친 자리의 설명 주석 4곳 원문 · .py/.js 주석 → 위반 0
#   heredoc      따옴표 구분자 heredoc 본문에 쓴 BAD 예시(`<<'EOF'` · `<<"EOF"` · `<<\EOF`) → 위반 0 ·
#                따옴표 없는 `<<EOF` · `<<-EOF` 본문(생성 셸이 `$(…)` 를 실행) → 위반
#   safe         현 트리의 안전 꼴 원문(결과를 따로 받고 실패면 멈춘다) · `${d:?}` · 루트 앵커 cd → 위반 0
# 음성 셀마다 무해한 cd 대조 줄을 함께 둬 '후보 0 = 순회가 셀을 못 봤다' 와 '위반 0' 을 구별한다.
# 기준 트리(#N14 없음)는 판정기가 없어 셀이 놓치고, `--only N14` 를 모르는 id 로 거부하고, 심은 사본을 '위반 0건' 으로 통과시킨다 → exit 1.
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패(인자 · 트리 · 임시 폴더 · lint traceback · 단언기 고장)
#   ⛔ 준비 실패를 1 로 내면 '기준 트리 exit 1' 이 기능 부재 재현 없이 통과한다 — 그래서 3 이다(미처리 예외도 3).
# ⛔ 셀 데이터(위험 꼴)는 아래 heredoc 안에만 둔다 — 이 파일도 #N14 의 대상이다. 임시 폴더만 쓰고 레지스트리는 읽지 않는다.
# usage: run.sh [--tree <플러그인 루트>]   (기본: 이 fixture 가 든 트리)
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 3; }
[ -f "$R/scripts/lint_contracts.py" ] || { echo "SETUP lint_contracts.py 없음: $R"; exit 3; }

PYTHONDONTWRITEBYTECODE=1 python3 -B - "$R" <<'PY'
import importlib.util, os, pathlib, re, shutil, subprocess, sys, tempfile, traceback


def _crash(*exc):   # 단언기 고장은 3 — 미처리 예외의 기본 exit 1 은 '단언 실패' 와 구별되지 않는다
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(3)


sys.excepthook = _crash
sys.dont_write_bytecode = True

TREE = pathlib.Path(sys.argv[1])
LINT_REL = "scripts/lint_contracts.py"
PY = sys.executable
FAIL = []


class Setup(Exception):
    """fixture 자신의 준비 실패 — exit 3."""


def check(cell, ok, what, detail=""):
    detail = " ⏎ ".join(x.strip() for x in str(detail).splitlines() if x.strip())[-400:]     # 한 단언 = 한 줄
    print(("PASS  " if ok else "FAIL  ") + f"{cell}: {what}" + ("" if ok or not detail else f" · {detail}"))
    if not ok:
        FAIL.append(f"{cell}: {what}")
    return ok


def load(lint):
    """대상 트리의 lint 를 모듈로 적재한다(판정기 함수를 셀 트리에 직접 건다)."""
    spec = importlib.util.spec_from_file_location("lint_contracts_under_test", lint)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except SystemExit as e:
        raise Setup(f"lint_contracts 적재 중 종료(exit {e.code})")
    except Exception as e:                                                   # noqa: BLE001
        raise Setup(f"lint_contracts 적재 실패 {type(e).__name__}: {e}")
    return mod


def lint_cli(root, *args):
    """root 의 lint 를 프로세스로 → (rc, 출력). ⛔ traceback 은 탐지가 아니라 검사기 고장이다 → Setup."""
    e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHON_COLORS="0")
    r = subprocess.run([PY, "-B", str(root / LINT_REL), *args], capture_output=True, text=True, env=e, cwd=str(root))
    out = r.stdout + r.stderr
    if "Traceback (most recent call last)" in out:
        raise Setup(f"lint traceback: {out[-300:]}")
    return r.returncode, out


def violations(out):
    """lint 출력의 위반 절 → [(항목, 'rel:line')]."""
    got, item, on = [], None, False
    for line in out.split("\n"):
        if line.startswith("── 위반 "):
            on = True
            continue
        if not on:
            continue
        m = re.match(r"^  #(\S+)\s*$", line)
        if m:
            item = m.group(1)
            continue
        m = re.match(r"^     (\S+?:\d+): ", line)
        if m:
            got.append((item, m.group(1)))
    return got


def write(root, files):
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")


def judge(cell, files, want):
    """셀 트리에 #N14 판정기를 건다 — 위반 위치 집합이 정확히 want 이고 후보가 1 이상."""
    if CHK is None:
        check(cell, False, "#N14 판정기 없음 — 이 트리의 lint 는 위험 꼴을 볼 검사가 없다")
        return
    try:
        td = tempfile.TemporaryDirectory(prefix="fz-n14-")
    except OSError as e:
        raise Setup(f"임시 폴더 생성 실패: {e}")
    with td as d:
        try:
            write(pathlib.Path(d), files)
        except OSError as e:
            raise Setup(f"셀 트리 기록 실패: {e}")
        v, hits = CHK(root=pathlib.Path(d))
    got = sorted(x.split(": ", 1)[0] for x in v)
    check(cell, got == sorted(want), f"위반 위치 = {sorted(want) or '0건'}", f"실제 {got}")
    check(cell, hits >= 1, "후보(cd/pushd 줄) 1 이상 — 판정기가 셀 파일을 봤다", f"hits={hits}")


def pad(n):
    """n 줄짜리 머리(셸본 줄 + 무해한 줄) — 다음 줄이 n+1 번째가 된다."""
    return "#!/bin/bash\n" + ":\n" * (n - 1)


CTL = {"tests/control.sh": 'cd "$(dirname "$0")" || exit 1\n'}     # 음성 셀의 대조 — 무해한 cd 1줄

if not (TREE / LINT_REL).is_file():
    raise Setup(f"lint 없음: {TREE / LINT_REL}")
try:
    MOD = load(TREE / LINT_REL)
    CHK = getattr(MOD, "CHECKS", {}).get("N14")
    FLOOR = getattr(MOD, "MIN_HITS", {}).get("N14")

    # ── self-tree — 현 트리 오탐 0 · 하한 이상 ───────────────────────────────
    rc, out = lint_cli(TREE, "--only", "N14")
    m = re.search(r"^OK\s+#N14\s.*\[검사 대상 (\d+)\]", out, re.M)
    check("self-tree", rc == 0 and bool(m) and "위반 0건" in out, "`--only N14` exit 0 · OK #N14 · 위반 0건",
          f"rc={rc} {out[-300:]}")
    check("self-tree", bool(m) and isinstance(FLOOR, int) and int(m.group(1)) >= FLOOR,
          "후보 수 ≥ MIN_HITS['N14']", f"후보 {m.group(1) if m else '?'} · 하한 {FLOOR!r}")

    # ── repro-4 — v4.42.0 이 고친 4곳의 고치기 전 줄(원래 줄 번호) ─────────────
    judge("repro-4", {
        "scripts/gpt_independent.sh": pad(140)
            + 'ISO="$(cd "$(mktemp -d "${TMPDIR:-/tmp}/fz-gpt-iso.XXXXXX")" && pwd -P)" || die 11 "격리 폴더 생성 실패"\n',
        "tests/fixtures/gpt/independent-arm/run.sh": pad(11)
            + 'T="$(cd "$(mktemp -d)" && pwd -P)"; trap \'rm -rf "$T"\' EXIT\n',
        "skills/fz-rebase/scripts/test-gates.sh": pad(18) + 'ROOT="$(cd "$(mktemp -d)" && pwd -P)"\n',
        "tests/fixtures/plan-wiring/parallel-arms/run.sh": pad(12)
            + 'T="$(cd "$(mktemp -d)" && pwd -P)"; trap \'rm -rf "$T"\' EXIT\n',
    }, ["scripts/gpt_independent.sh:141", "tests/fixtures/gpt/independent-arm/run.sh:12",
        "skills/fz-rebase/scripts/test-gates.sh:19", "tests/fixtures/plan-wiring/parallel-arms/run.sh:13"])

    # ── repro-plant — 이 트리 사본에 위험 꼴 1줄을 심고 lint 전체 ───────────────
    RUNNER = "tests/fixtures/gpt/independent-arm/run.sh"
    try:
        tdp = tempfile.TemporaryDirectory(prefix="fz-n14-plant-")
    except OSError as e:
        raise Setup(f"임시 폴더 생성 실패: {e}")
    with tdp as d:
        cp = pathlib.Path(d) / "tree"
        try:
            shutil.copytree(TREE, cp, symlinks=True,
                            ignore=shutil.ignore_patterns(".git", ".fz-work", "node_modules", "__pycache__", "worktrees"))
        except (OSError, shutil.Error) as e:
            raise Setup(f"트리 사본 실패: {e}")
        rp = cp / RUNNER
        if not rp.is_file():
            raise Setup(f"심을 러너 없음: {RUNNER}")
        lines = rp.read_text(encoding="utf-8").split("\n")
        at = next((i for i, l in enumerate(lines) if l.startswith('T0="$(mktemp -d)"')), None)
        if at is None:
            raise Setup(f"심을 자리(안전 꼴 T0= 줄) 없음: {RUNNER}")
        lines.insert(at + 1, 'cd "$(mktemp -d)" || exit 2   # F-355 probe: 위험 꼴 재유입')
        rp.write_text("\n".join(lines), encoding="utf-8")
        rc, out = lint_cli(cp)
    v = violations(out)
    want = [("N14", f"{RUNNER}:{at + 2}")]
    check("repro-plant", rc == 1, "lint 전체 exit 1(심은 줄을 위반으로 낸다)", f"rc={rc} {out[-300:]}")
    check("repro-plant", v == want, f"위반은 정확히 {want}", f"실제 {v}")

    # ── variants — 변형 양성 ─────────────────────────────────────────────────
    judge("variants", {
        "tests/v_pushd.sh": 'pushd "$(mktemp -d)" >/dev/null\n',
        "tests/v_dt.sh": 'cd "$(mktemp -d -t fz-x)"\n',
        "tests/v_unquoted.sh": 'cd $(mktemp -d)\n',
        "tests/v_backtick.sh": 'cd "`mktemp -d`"\n',
        "tests/v_opts.sh": 'cd -P -- "$(mktemp -d)"\n',
        "tests/v_env.sh": 'cd "$(TMPDIR=/x mktemp -d)"\n',
        "tests/v_subshell.sh": '( cd "$(mktemp -d)" && touch x )\n',
        "tests/v_after_heredoc.sh": "cat <<'EOF' > ok.txt\nx\nEOF\ncd \"$(mktemp -d)\"\n",
        "tests/v_shell.py": 'import subprocess\nsubprocess.run(\'cd "$(mktemp -d)" && make\', shell=True)\n',
        "tests/v_shell.js": 'require("child_process").execSync(\'cd "$(mktemp -d)" && make\');\n',
    }, ["tests/v_pushd.sh:1", "tests/v_dt.sh:1", "tests/v_unquoted.sh:1", "tests/v_backtick.sh:1",
        "tests/v_opts.sh:1", "tests/v_env.sh:1", "tests/v_subshell.sh:1", "tests/v_after_heredoc.sh:4",
        "tests/v_shell.py:2", "tests/v_shell.js:1"])

    # ── docs — .md 의 BAD 예시(모듈 · 레지스트리 INDEX 행 사본 · CHANGELOG · 릴리스 노트) ──
    judge("docs", dict(CTL, **{
        "modules/bash-hygiene.md": '```bash\n# BAD\nX="$(cd "$(mktemp -d)" && pwd -P)"\n```\n',
        "INDEX.md": '| F-355 | 2026-10-01 | `hole` | empty-cd-substitution-resolves-to-cwd | `X="$(cd "$(mktemp -d)" && pwd -P)"` '
                    '는 mktemp 실패 시 bash 3.2 `cd ""` 가 성공해 현재 폴더가 되고 trap 이 지운다 | review | open |\n',
        "CHANGELOG.md": '런처 · 러너가 `cd "$(mktemp -d)"` 꼴로 임시 폴더를 만들어 mktemp 가 실패하면 현재 폴더를 지웠다\n',
        "docs/releases/v4.42.0.md": '- **critical** — 런처와 러너 셋이 `cd "$(mktemp -d)"` 꼴로 임시 폴더를 만들었다\n',
    }), [])

    # ── comments — 고친 자리의 설명 주석(현 트리 원문) · .py/.js 주석 ─────────────
    judge("comments", dict(CTL, **{
        "scripts/gpt_independent.sh": '#    ⛔ mktemp 결과를 따로 받는다 — `cd "$(mktemp …)"` 꼴은 mktemp 가 실패해도 `cd ""` 가 성공해 '
                                      '현재 폴더가 격리 폴더가 된다(bash 3.2 실측)\n',
        "skills/fz-rebase/scripts/test-gates.sh": '# ⛔ mktemp 결과를 따로 받는다 — `cd "$(mktemp -d)"` 는 mktemp 가 실패해도 '
                                                  '`cd ""` 가 성공해(bash 3.2) 현재 폴더가 ROOT 가 되고 trap 이 지운다\n',
        "tests/fixtures/gpt/independent-arm/run.sh": '# ⛔ mktemp 결과를 따로 받는다 — `cd "$(mktemp -d)"` 는 mktemp 가 실패해도 '
                                                     '`cd ""` 가 성공해(bash 3.2) 현재 폴더를 지운다\n',
        "tests/fixtures/plan-wiring/parallel-arms/run.sh": '# ⛔ mktemp 결과를 따로 받는다 — `cd "$(mktemp -d)"` 는 mktemp 가 '
                                                           '실패해도 `cd ""` 가 성공해(bash 3.2) 현재 폴더를 지운다\n',
        "tests/c.py": '# cd "$(mktemp -d)" 는 쓰지 않는다\n',
        "tests/c.js": '// cd "$(mktemp -d)" 는 쓰지 않는다\n',
    }), [])

    # ── heredoc — 따옴표 구분자 본문의 BAD 예시는 데이터, 따옴표 없는 본문은 코드 ────────
    judge("heredoc", dict(CTL, **{
        "tests/h_quoted.sh": "cat > bad.sh <<'EOF'\ncd \"$(mktemp -d)\"\nEOF\n",
        "tests/h_dquoted.sh": 'cat > bad.sh <<"EOF"\ncd "$(mktemp -d)"\nEOF\n',
        "tests/h_bslash.sh": "cat > bad.sh <<\\EOF\ncd \"$(mktemp -d)\"\nEOF\n",
        "tests/h_plain.sh": 'cat > bad.sh <<EOF\nX="$(cd "$(mktemp -d)" && pwd -P)"\nEOF\n',
        "tests/h_tab.sh": "\tcat <<-EOF\n\tpushd \"$(mktemp -d)\"\n\tEOF\n",
    }), ["tests/h_plain.sh:2", "tests/h_tab.sh:2"])

    # ── safe — 현 트리의 안전 꼴 원문 · `${d:?}` · 루트 앵커 cd ─────────────────
    judge("safe", dict(CTL, **{
        "scripts/gpt_independent.sh": 'ISO_TMP="$(mktemp -d "${TMPDIR:-/tmp}/fz-gpt-iso.XXXXXX")" || die 11 "격리 폴더 생성 실패(mktemp)"\n'
                                      'ISO="$(cd "$ISO_TMP" && pwd -P)" || die 11 "격리 폴더 경로 해석 실패: $ISO_TMP"\n',
        "skills/fz-rebase/scripts/test-gates.sh": 'ROOT0="$(mktemp -d)" || { echo "mktemp 실패" >&2; exit 2; }; '
                                                  'ROOT="$(cd "$ROOT0" && pwd -P)"\n',
        "tests/fixtures/gpt/independent-arm/run.sh": 'T0="$(mktemp -d)" || { echo "mktemp 실패" >&2; exit 2; }; '
                                                     'T="$(cd "$T0" && pwd -P)"; trap \'rm -rf "$T"\' EXIT\n',
        "skills/fz-peer-review/scripts/gather.sh": 'STAGE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/fz-gather.XXXXXX")" || die 4 "임시 디렉터리 생성 실패"\n',
        "tests/s_guard.sh": 'd=$(mktemp -d) || exit 1\ncd "${d:?}" || exit 1\n',
        "tests/s_root.sh": 'R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"\ncd "$(git rev-parse --show-toplevel)"\n',
    }), [])
except Setup as e:
    print(f"SETUP {e}")
    sys.exit(3)

print()
print(f"SUMMARY fail={len(FAIL)}")
for f in FAIL:
    print(f"  FAIL {f}")
sys.exit(1 if FAIL else 0)
PY
