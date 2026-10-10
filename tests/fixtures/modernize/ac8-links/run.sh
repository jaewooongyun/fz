#!/bin/bash
# AC8 링크 수집 fixture (F-224 · SC-16) — 실제 skills/fz-modernize/scripts/ac8-link-check.sh 를 git 이력에 고정된
# 가이드 스냅샷(be8c871 의 guides/*.md)에 돌린다. ⛔ 네트워크를 쓰지 않는다 — curl 은 shim 이 받아 200 을 낸다.
#   PATH = 허용 목록 폴더 하나(/usr/bin:/bin 의 POSIX 도구 링크 + curl shim). rg 는 그 폴더에 없다 —
#   호스트에 rg 가 있어도 'rg 부재' 조건은 같다. BASH_ENV · ENV 는 지운다(셸 함수 rg 가 끼어들지 않게).
#   bash         일반 셸(환경 상속 · PATH 만 격리) — exit 0 · urls-to-check.txt = 기대 49건 집합(중복 0) ·
#                curl shim 호출 = 같은 49건 · link-check-results.txt = '200 <url>' 49줄 · 기존 산출물 교체 · 임시 파일 0
#   env-i-sh     env -i PATH=<격리> /bin/sh <스크립트> — 같은 단언(빈 환경 · C 로캘 · POSIX sh)
#   zero-url     URL 없는 가이드 — exit 2 · 'UNRUN' 줄 · 기존 산출물 바이트 보존 · curl 0회 · 임시 파일 0
#   missing-dir  없는 가이드 폴더 — exit 3(입력 오류) · 기존 산출물 보존 · curl 0회 · 임시 파일 0
#   read-error   URL 있는 a.md + 끊긴 심볼릭 b.md(grep exit 2) — exit 3 · 기존 산출물 보존 · curl 0회 · 임시 파일 0
#   validate-dies  추출은 성공하고 검증 단계가 죽는다(xargs 자리에 exit 125 stub) — exit 비0 · urls-to-check.txt 는
#                새 집합으로 교체 · link-check-results.txt 는 바이트 보존 · 임시 파일 0 (단계별 원자 쓰기)
# 기대 집합 = 같은 스냅샷에 원 파이프라인(rg -o … | cut -d: -f2- | sed … | sort -u — 도구 셸의 rg)을 돌린 49건.
#   원 정규식을 grep -hoE 에 그대로 넣으면 0건(UNRUN)이고, 대괄호를 POSIX 순서로만 고친 [] 안 \s 판은 24건 · cut 을 남기면
#   스킴이 잘린다 — 집합 일치가 두 회귀를 따로 잡는다(cut 만 남기면 49줄 전부 '//…', \s 만 남기면 URL 이 첫 's' 에서 끊겨 24건).
# 기준 트리는 PATH 에 rg 가 없어 exit 127 · 0바이트 urls-to-check.txt → bash · env-i-sh 등이 FAIL → exit 1.
#   ⛔ macOS /bin/sh 는 POSIX 모드 bash 라 env-i-sh 셀이 bashism([[ ]] 등)까지 막지는 않는다 — dash 호스트에서만 막는다.
# exit: 0 전건 통과 · 1 단언 실패 · 2 UNRUN(고정 스냅샷 없음 — .git 없는 설치본 · 얕은 clone, 줄 맨 앞 `UNRUN:`) ·
#       3 준비 실패(인자 · 트리 · 스크립트 · 허용 도구 부재 ·
#       실행 불가 · 시간 초과 · 단언기 고장)
#   ⛔ 준비 실패를 1 로 내면 '기준 트리 exit 1' 게이트가 결함 재현 없이 통과한다 — 그래서 3 이다.
#      python 의 미처리 예외(기본 exit 1)는 excepthook 으로, python 이 0/1/3 밖으로 끝나면 바깥 셸이 3 으로 바꾼다.
# ⛔ 셀 입력·출력은 python 임시 폴더에만 쓴다. 트리에 바이트코드를 남기지 않는다.
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
[ -f "$R/skills/fz-modernize/scripts/ac8-link-check.sh" ] || { echo "SETUP ac8-link-check.sh 없음: $R"; exit 3; }

PYTHONDONTWRITEBYTECODE=1 python3 -B - "$R" <<'PY'
import os, pathlib, shlex, shutil, subprocess, sys, tempfile, traceback


def _crash(*exc):   # 단언기 고장은 3 — 미처리 예외의 기본 exit 1 은 '단언 실패' 와 구별되지 않는다
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(3)


sys.excepthook = _crash
sys.dont_write_bytecode = True

TREE = pathlib.Path(sys.argv[1])
SCRIPT = TREE / "skills" / "fz-modernize" / "scripts" / "ac8-link-check.sh"
SNAP = "be8c87197ed386f46d8153c872bb1a1a519e3e2a"   # v4.43.0 — guides/*.md 9파일
SYS_PATH = "/usr/bin:/bin"
TOOLS = ("sh", "bash", "env", "cat", "cut", "grep", "sed", "sort", "tr", "wc", "xargs", "mv", "rm", "mktemp",
         "dirname", "basename", "head", "tail", "tee")
TIMEOUT = 120
URLS, RESULTS = "urls-to-check.txt", "link-check-results.txt"
OLD_URLS, OLD_RESULTS = b"OLD urls sentinel\n", b"OLD results sentinel\n"
EXPECTED = """
https://arxiv.org/abs/
https://arxiv.org/abs/2507.19457
https://arxiv.org/abs/2603.28052
https://arxiv.org/abs/2604.08224
https://arxiv.org/abs/2604.20801
https://arxiv.org/abs/2604.20938
https://arxiv.org/abs/2604.21003
https://arxiv.org/abs/2604.25850
https://arxiv.org/abs/2605.00663
https://arxiv.org/abs/2605.13357
https://arxiv.org/abs/2607.17641
https://arxiv.org/abs/2607.25152
https://arxiv.org/html/2603.05344v1
https://arxiv.org/html/2603.25723v1
https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
https://claude.com/blog/claude-model-and-effort-level-in-claude-code
https://code.claude.com/docs/en/advisor
https://code.claude.com/docs/en/changelog
https://code.claude.com/docs/en/how-claude-code-works
https://code.claude.com/docs/en/model-config
https://code.claude.com/docs/en/workflows
https://cookbook.openai.com/examples/gpt-5/gpt-5_prompting_guide
https://developers.openai.com/codex/cli
https://dspy.ai/
https://github.com/Chachamaru127/claude-code-harness
https://learn.chatgpt.com/docs/changelog
https://openai.com/index/gpt-5-5-system-card/
https://openai.com/index/introducing-gpt-5-5/
https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools
https://platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5
https://platform.claude.com/docs/en/about-claude/models/whats-new-opus-5
https://platform.claude.com/docs/en/about-claude/pricing
https://platform.claude.com/docs/en/build-with-claude/effort
https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5
https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1
https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5
https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5
https://platform.claude.com/docs/en/models/fable-5-1/whats-new-fable-5-1
https://platform.claude.com/docs/en/models/opus-5-5/whats-new-opus-5-5
https://revfactory.github.io/harness-paper
https://www.anthropic.com/claude-opus-5-5
https://www.anthropic.com/engineering/claude-code-best-practices
https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
https://www.anthropic.com/engineering/harness-design-long-running-apps
https://www.anthropic.com/engineering/managed-agents
https://www.anthropic.com/news/claude-opus-4-8
https://www.anthropic.com/news/claude-opus-5
https://www.anthropic.com/research/building-effective-agents
""".split()
FAIL, N, RAN = [], [0], []


class Setup(Exception):
    """fixture 자신의 준비 실패 — exit 3."""


class Unrun(Exception):
    """고정 스냅샷이 없어 판정할 수 없다 — exit 2 · 줄 맨 앞 `UNRUN:`(health-check 3분 판정이 미실행으로 센다)."""


def check(cell, ok, what, detail=""):
    N[0] += 1
    if cell not in RAN:
        RAN.append(cell)
    detail = " ⏎ ".join(x.strip() for x in str(detail).splitlines() if x.strip())[-300:]     # 한 단언 = 한 줄
    print(("PASS  " if ok else "FAIL  ") + f"{cell}: {what}" + ("" if ok or not detail else f" · {detail}"))
    if not ok:
        FAIL.append(f"{cell}: {what}")
    return ok


def git(*args):
    try:
        return subprocess.run(["git", "-C", str(TREE)] + list(args), capture_output=True, timeout=60,
                              stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as ex:
        raise Setup(f"git 실행 불가: {ex!r}")


def snapshot(dst):
    """고정 커밋의 guides/*.md 를 dst 에 쓴다 — 작업 트리의 가이드는 읽지 않는다(편집에 따라 기대 집합이 흔들린다)."""
    r = git("cat-file", "-t", SNAP)
    if r.returncode != 0 or r.stdout.strip() != b"commit":
        raise Unrun(f"고정 가이드 스냅샷 {SNAP[:7]} 이 {TREE} 의 git 이력에 없다 (.git 없음 · 얕은 clone — ⛔ 통과 아님)")
    r = git("ls-tree", "-z", "--name-only", SNAP, "--", "guides/")
    names = [x.decode("utf-8") for x in r.stdout.split(b"\0") if x.endswith(b".md")]
    if r.returncode != 0 or not names:
        raise Setup(f"스냅샷 {SNAP[:7]} 에서 guides/*.md 를 읽지 못했다 (exit {r.returncode})")
    dst.mkdir()
    for n in names:
        b = git("cat-file", "blob", f"{SNAP}:{n}")
        if b.returncode != 0:
            raise Setup(f"스냅샷 {SNAP[:7]}:{n} 읽기 실패")
        (dst / pathlib.PurePosixPath(n).name).write_bytes(b.stdout)
    return len(names)


def isolated_bin(tmp, name="bin", xargs_dies=False):
    """허용 목록 PATH — 도구가 없으면 준비 실패(3)다. 스크립트가 목록 밖 도구를 부르면 그 셀의 단언이 깨진다.
    xargs_dies: xargs 자리에 exit 125 stub — 검증 단계 사망을 신호·타이밍 없이 재현한다."""
    b = tmp / name
    b.mkdir()
    for t in TOOLS:
        p = shutil.which(t, path=SYS_PATH)
        if not p:
            raise Setup(f"허용 도구 부재: {t} ({SYS_PATH})")
        if t == "xargs" and xargs_dies:
            (b / t).write_text("#!/bin/sh\necho 'fixture xargs stub — 검증 단계 사망' >&2\nexit 125\n", encoding="utf-8")
            (b / t).chmod(0o755)
            continue
        (b / t).symlink_to(p)
    calls = tmp / "curl-calls"
    shim = b / "curl"
    shim.write_text("#!/bin/sh\n# fixture curl shim — 네트워크를 쓰지 않는다. 마지막 인자(URL)를 적고 HTTP 200 을 낸다\n"
                    'for a in "$@"; do u=$a; done\n'
                    f"printf '%s\\n' \"$u\" >> {shlex.quote(str(calls))}\n"
                    "printf 200\n", encoding="utf-8")
    shim.chmod(0o755)
    return b, calls


def seed(out):
    out.mkdir()
    (out / URLS).write_bytes(OLD_URLS)
    (out / RESULTS).write_bytes(OLD_RESULTS)


def run(cell, argv, env, calls, cwd):
    """스크립트 실행 → (exit, 출력, curl 호출 목록). ⛔ 실행 불가 · 시간 초과는 판정이 아니라 측정 불가 → Setup."""
    calls.write_bytes(b"")
    try:
        r = subprocess.run([str(x) for x in argv], env=env, cwd=str(cwd), capture_output=True, timeout=TIMEOUT,
                           stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        raise Setup(f"{cell}: {TIMEOUT}s 초과 — 판정 불가")
    except OSError as ex:
        raise Setup(f"{cell}: 실행 불가 {ex!r}")
    out = (r.stdout + r.stderr).decode("utf-8", "replace")
    return r.returncode, out, calls.read_text(encoding="utf-8").splitlines()


def lines(p):
    return p.read_text(encoding="utf-8", errors="replace").splitlines() if p.is_file() else []


def leftovers(out):
    return sorted(x.name for x in out.iterdir() if x.name not in (URLS, RESULTS))


def ok_cell(cell, rc, out, calls, odir):
    exp = sorted(EXPECTED)
    got = lines(odir / URLS)
    check(cell, rc == 0, f"exit 0 (exit {rc})", out)
    miss, extra = sorted(set(exp) - set(got)), sorted(set(got) - set(exp))
    check(cell, not miss and not extra and len(got) == len(set(got)),
          f"{URLS} = 기대 {len(exp)}건 집합 (실측 {len(got)}줄 · 고유 {len(set(got))} · 빠짐 {len(miss)} · 남음 {len(extra)})",
          f"빠짐 {miss[:3]} · 남음 {extra[:3]} · 크기 {(odir / URLS).stat().st_size if (odir / URLS).exists() else '없음'}B")
    check(cell, sorted(calls) == exp, f"curl shim 호출 = 기대 {len(exp)}건 각 1회 (호출 {len(calls)})")
    res = lines(odir / RESULTS)
    check(cell, sorted(res) == sorted("200 " + u for u in exp),
          f"{RESULTS} = '200 <url>' {len(exp)}줄 (실측 {len(res)}줄)", " | ".join(res[:3]))
    left = leftovers(odir)
    check(cell, not left, f"임시 파일 잔존 0 ({left[:3]})")


def kept_cell(cell, rc, want, out, calls, odir, unrun=False):
    check(cell, rc == want, f"exit {want} (exit {rc})", out)
    if unrun:
        check(cell, any(x.startswith("UNRUN") for x in out.splitlines()), "출력에 'UNRUN' 줄", out)
    u = (odir / URLS).read_bytes() if (odir / URLS).is_file() else None
    r = (odir / RESULTS).read_bytes() if (odir / RESULTS).is_file() else None
    check(cell, u == OLD_URLS and r == OLD_RESULTS,
          f"기존 산출물 바이트 보존 ({URLS} {'같음' if u == OLD_URLS else repr(u)[:40]} · {RESULTS} {'같음' if r == OLD_RESULTS else repr(r)[:40]})")
    check(cell, not calls, f"curl 호출 0 (호출 {len(calls)})")
    left = leftovers(odir)
    check(cell, not left, f"임시 파일 잔존 0 ({left[:3]})")


def main():
    if len(EXPECTED) != 49 or len(set(EXPECTED)) != 49:
        raise Setup(f"기대 집합 고장 — {len(EXPECTED)}줄 · 고유 {len(set(EXPECTED))} (49 여야 한다)")
    with tempfile.TemporaryDirectory(prefix="fz-ac8-links.") as td:
        tmp = pathlib.Path(td)
        guides = tmp / "guides"
        nmd = snapshot(guides)
        b, calls = isolated_bin(tmp)
        sh, envx = shutil.which("sh", path=SYS_PATH), shutil.which("env", path=SYS_PATH)
        normal = {k: v for k, v in os.environ.items() if k not in ("BASH_ENV", "ENV")}
        normal["PATH"] = str(b)

        o = tmp / "out-bash"
        seed(o)
        rc, out, cl = run("bash", [b / "bash", SCRIPT, guides, o], normal, calls, tmp)
        ok_cell("bash", rc, out, cl, o)

        o = tmp / "out-env-i-sh"
        seed(o)
        rc, out, cl = run("env-i-sh", [envx, "-i", f"PATH={b}", sh, SCRIPT, guides, o], None, calls, tmp)
        ok_cell("env-i-sh", rc, out, cl, o)

        g = tmp / "guides-zero"
        g.mkdir()
        (g / "a.md").write_text("# URL 없음\n\n주소 없는 본문 · http 라는 낱말만 있다\n", encoding="utf-8")
        o = tmp / "out-zero"
        seed(o)
        rc, out, cl = run("zero-url", [b / "bash", SCRIPT, g, o], normal, calls, tmp)
        kept_cell("zero-url", rc, 2, out, cl, o, unrun=True)

        o = tmp / "out-missing"
        seed(o)
        rc, out, cl = run("missing-dir", [b / "bash", SCRIPT, tmp / "no-such-guides", o], normal, calls, tmp)
        kept_cell("missing-dir", rc, 3, out, cl, o)

        g = tmp / "guides-broken"
        g.mkdir()
        (g / "a.md").write_text("see https://example.invalid/a\n", encoding="utf-8")
        (g / "b.md").symlink_to(tmp / "no-such-file.md")
        o = tmp / "out-read-error"
        seed(o)
        rc, out, cl = run("read-error", [b / "bash", SCRIPT, g, o], normal, calls, tmp)
        kept_cell("read-error", rc, 3, out, cl, o)

        g = tmp / "guides-one"
        g.mkdir()
        (g / "a.md").write_text("see https://example.invalid/one.\n", encoding="utf-8")
        bx, _ = isolated_bin(tmp, "bin-xargs-dies", xargs_dies=True)
        o = tmp / "out-validate-dies"
        seed(o)
        env = dict(normal, PATH=str(bx))
        rc, out, cl = run("validate-dies", [bx / "bash", SCRIPT, g, o], env, calls, tmp)
        check("validate-dies", rc != 0, f"exit 비0 (exit {rc})", out)
        got = lines(o / URLS)
        check("validate-dies", got == ["https://example.invalid/one"], f"{URLS} 교체 — 추출 단계는 성공 ({got[:2]})", out)
        r = (o / RESULTS).read_bytes() if (o / RESULTS).is_file() else None
        check("validate-dies", r == OLD_RESULTS, f"{RESULTS} 바이트 보존 ({'같음' if r == OLD_RESULTS else repr(r)[:40]})")
        left = leftovers(o)
        check("validate-dies", not left, f"임시 파일 잔존 0 ({left[:3]})")
    if FAIL:
        print(f"FAIL {len(FAIL)}/{N[0]} — " + " | ".join(FAIL))
        return 1
    print(f"AC8_LINKS_OK {N[0]}/{N[0]} (스냅샷 {SNAP[:7]} guides {nmd}파일 · URL {len(EXPECTED)} · 셀 {len(RAN)}: {' · '.join(RAN)})")
    return 0


try:
    sys.exit(main())
except Unrun as ex:
    print(f"UNRUN: {ex}")
    sys.exit(2)
except Setup as ex:
    print(f"SETUP {ex}")
    sys.exit(3)
PY
rc=$?
case "$rc" in
  0|1|2|3) exit "$rc" ;;
  *) echo "SETUP python 이 0/1/2/3 밖으로 끝났다 (exit $rc)"; exit 3 ;;
esac
