#!/bin/bash
# fallback 이웃 셀 변이 러너 — F-573. fallback(기본값 · '미검증' · '판정 불가 → 통과' 류)을 지나는 기존 셀이 자기 방어를 지운 사본에서
# 여전히 실패하는가를 health-check 마다 다시 잰다. fallback 의미를 바꾼 수정이 들어와 그 셀이 공허 통과로 바뀌면 SURVIVOR 로 실패한다.
#   (F-573: 저장소가 없으면 미검증으로 바꾼 수정 뒤, 저장소 없이 돌던 기존 셀이 키워드 처리를 되돌려도 통과했다 —
#    수정별 되돌림 측정은 그 수정이 더한 새 셀만 쟀다)
#
# 표(NEIGHBORS) — 판정기의 fallback 지점 하나와 그 fallback 을 지나는 기존 셀 · 셀을 통과시키는 방어(지울 조각)
#   check_comment_worthy repo_has — 저장소 · sha 를 못 쓰면 None(미검증 · 위반 아님)
#     f063-literals-keywords-not-symbols   Java · Kotlin 수식어 키워드 줄(CODE_WORDS)
#     f063-unchanged-file-helper-ok        대상 sha 트리에서 찾은 이름을 담는 줄
# 자기 점검 r3-f573-neighbor-vacuous-caught — fallback 을 넓힌 변이(repo_has 가 늘 None)를 함께 건 사본에서
#   f063-unchanged-file-helper-ok 가 방어 없이도 통과한다. 이 러너가 그것을 SURVIVOR 로 판정하는가(공허 통과를 실제로 잡는가)를 본다.
# ⛔ diff 로 함수 확장을 추정하지 않는다(F-458 근사기 꼬리) — 이웃 셀은 이 표에 사람이 적는다. fallback 을 바꾸면 그 이웃을 여기 더한다.
# ⛔ 사본은 scripts/ 만 — 판정기는 같은 폴더 모듈만 읽고 self-test 는 자기 임시 git 저장소를 만든다.
# exit: 0 이웃 전부 caught · 1 SURVIVOR 또는 자기 점검 실패 · 3 준비 실패(SETUP — 조각이 정확히 한 번이 아님 · 기준 사본에서 셀 미통과 ·
#   판정기 self-test 가 셀 줄을 못 냄). 판정기를 고쳐 조각이 사라지면 3 으로 드러난다 — 표를 함께 고친다
# usage: run.sh [--tree <플러그인 루트>]
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)" || { echo "SETUP 트리 루트를 풀지 못했다"; exit 3; }
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
[ -f "$R/scripts/check_comment_worthy.py" ] || { echo "SETUP 판정기 없음: $R/scripts/check_comment_worthy.py"; exit 3; }
command -v git >/dev/null 2>&1 || { echo "SETUP git 부재 — 판정기 self-test 가 임시 저장소를 만든다"; exit 3; }

python3 - "$R" <<'PY'
import os
import shutil
import subprocess
import sys
import tempfile

R = sys.argv[1]
CCW = "check_comment_worthy.py"
DOC = '    """스냅샷에 없는 식별자를 대상 sha 의 전체 트리에서 찾는다 — 찾은 이름 집합. 저장소 · sha 를 못 쓰면 None(미검증)."""\n'
WIDEN = (DOC, DOC + "    return None\n")   # fallback 을 넓힌다 — 저장소가 있어도 미검증
NEIGHBORS = [
    ("f063-literals-keywords-not-symbols", "Java · Kotlin 수식어 키워드 줄(CODE_WORDS)",
     ('    "protected abstract synchronized volatile transient native strictfp assert byte short float double goto "\n', "")),
    ("f063-unchanged-file-helper-ok", "대상 sha 트리에서 찾은 이름을 담는 줄(repo_has)",
     ("            found.add(n)\n", "            pass\n")),
]
SELF = "f063-unchanged-file-helper-ok"


class Setup(Exception):
    pass


def probe(edits, cells):
    """scripts/ 사본에 edits 를 걸고 판정기 self-test 를 돈다 — 셀마다 통과 줄이 있는가."""
    t = tempfile.mkdtemp(prefix="fz-mutn-")
    try:
        s = os.path.join(t, "scripts")
        shutil.copytree(os.path.join(R, "scripts"), s, ignore=shutil.ignore_patterns("__pycache__"))
        p = os.path.join(s, CCW)
        text = open(p, encoding="utf-8").read()
        for old, new in edits:
            if text.count(old) != 1:
                raise Setup(f"{CCW} 에 조각이 {text.count(old)}번 — {old.strip()[:60]!r}")
            text = text.replace(old, new)
        open(p, "w", encoding="utf-8").write(text)
        out = subprocess.run([sys.executable, CCW, "--self-test"], cwd=s, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             env=dict(os.environ, FZ_SELFTEST_LIST="1")).stdout.decode("utf-8", "replace").splitlines()
        seen = {c: [ln for ln in out if ln == c or ln.startswith(c + " ") or ln.startswith(c + ":")] for c in cells}
        if not all(seen.values()):
            raise Setup(f"판정기 self-test 가 셀 줄을 내지 않았다 — {[c for c, v in seen.items() if not v]} · 끝 줄 {out[-1:]}")
        return {c: any(ln.endswith(": PASS") for ln in v) for c, v in seen.items()}
    finally:
        shutil.rmtree(t, ignore_errors=True)


def verdicts(extra):
    """이웃마다 caught(방어를 지우면 실패) · survivor(방어 없이도 통과 = 공허 통과)."""
    return {c: ("survivor" if probe(extra + [d], [c])[c] else "caught") for c, _w, d in NEIGHBORS}


try:
    base = probe([], [c for c, _w, _d in NEIGHBORS])
    if not all(base.values()):
        raise Setup(f"무변경 사본에서 통과하지 않는 이웃 셀 — {[c for c, ok in base.items() if not ok]}")
    now = verdicts([])
    widened = verdicts([WIDEN])
except Setup as e:
    print(f"SETUP {e}")
    sys.exit(3)
fail = 0
for c, why, _d in NEIGHBORS:
    if now[c] == "caught":
        print(f"  ok {c} — {why} 를 지우면 실패한다")
    else:
        print(f"SURVIVOR {c} — {why} 를 지워도 통과한다 · fallback 을 지나 공허 통과(F-573) — 셀을 fallback 밖 형태로 옮기거나 음성 대조를 단다")
        fail = 1
print(f"  info fallback 을 넓힌 변이에서 — {widened}")
ok = now[SELF] == "caught" and widened[SELF] == "survivor"
print(("PASS  " if ok else "FAIL  ") + "r3-f573-neighbor-vacuous-caught — fallback 을 넓힌 변이에서 방어 없이 통과하는 이웃 셀을 SURVIVOR 로 잡는다"
      + ("" if ok else f" · 실제 현재 {now[SELF]} · 변이 {widened[SELF]}"))
fail |= not ok
print("mutation-neighbors: " + ("전건 통과" if not fail else "실패 있음"))
sys.exit(1 if fail else 0)
PY
