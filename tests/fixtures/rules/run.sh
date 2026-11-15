#!/bin/bash
# 오케스트레이션 규칙 정본 하나로 (F-480 · F-483 · F-486 · F-488).
#
# 셀:
#   zero-match          0건 폴백 정본 = intent-registry Zero 행(resolver-only → total-miss AskUserQuestion, 다른 추천기 재매핑 없음)
#                       · fz SKILL Phase 1 이 트리거 소스를 스킬 YAML 로 지시하지 않는다 · 3.1 total-miss 가 AskUserQuestion
#   duplicate-trigger   registry 트리거 표에서 두 스킬에 같은 패턴이 있으면 동점 규칙이 있어야 한다 — 동점 처리 줄은 정확히 1개
#   autonomous          autonomy_decide: 자율 + 범위 안 + 가역 → PROCEED · 비가역 → ASK · 대화형 → ASK · 미지 모드 → ASK
#   commit-push-matrix  autonomy_decide: {interactive, autonomous} × {commit, push} → 넷 다 BLOCK (범위 안 · 가역이어도)
#   team-skill          fz-commit · fz-pr 이 `## Git Workflow` 제목에 묶이지 않고 governance § 팀 스킬 위임을 가리킨다
#                       · fz-commit 에 무조건 `/sc:sc-git` 커밋 경로가 없다 · governance 에 그 절이 있다
#   single-source       자율 예외 규범 문장은 skills · modules 중 governance 에만 있다 · 소비처는 governance § 자율 모드를 가리킨다
# 출력: 셀마다 `<셀>: PASS|FAIL <이유>` · 끝에 `rules: PASS|FAIL`
# exit: 0 전건 통과 · 1 단언 실패 · 2 준비 실패
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." 2>/dev/null && pwd)"
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 2; }
for f in modules/intent-registry.md modules/governance.md modules/lead-action-default.md skills/fz/SKILL.md \
         skills/fz-commit/SKILL.md skills/fz-pr/SKILL.md scripts/autonomy_decide.py; do
  [ -f "$ROOT/$f" ] || { echo "SETUP $f 없음: $ROOT"; exit 2; }
done

PYTHONDONTWRITEBYTECODE=1 python3 -B - "$ROOT" <<'PY'
import glob, os, re, subprocess, sys
ROOT = sys.argv[1]
fails = []


def rd(rel):
    return open(os.path.join(ROOT, rel), encoding="utf-8", errors="replace").read()


def case(name, problems):
    print(f"{name}: {'PASS' if not problems else 'FAIL'}" + ("" if not problems else " " + "; ".join(problems)))
    if problems:
        fails.append(name)


reg, skill, gov = rd("modules/intent-registry.md"), rd("skills/fz/SKILL.md"), rd("modules/governance.md")

# zero-match
p = []
zero = [l for l in reg.splitlines() if l.startswith("| Zero |")]
if len(zero) != 1:
    p.append(f"intent-registry Zero rows {len(zero)} != 1")
elif not ("resolver-only" in zero[0] and "AskUserQuestion" in zero[0]) or "sc-recommend" in zero[0]:
    p.append("Zero row is not 'resolver-only → AskUserQuestion' (or still remaps via sc-recommend)")
if re.search(r"각 스킬 YAML의 `intent-triggers` 정규식과 대조", skill):
    p.append("fz SKILL Phase 1 still matches skill YAML intent-triggers")
if not re.search(r"total-miss[^\n]*AskUserQuestion", skill):
    p.append("fz SKILL 3.1 total-miss → AskUserQuestion line missing")
case("zero-match", p)

# duplicate-trigger
p, owners = [], {}
for l in reg.splitlines():
    cells = [c.strip() for c in l.strip().strip("|").split("|")]
    if len(cells) >= 3 and re.fullmatch(r"`?/?fz[\w-]*`?", cells[0]):
        for pat in re.split(r"\s*[·,]\s*", cells[1] + " · " + cells[2]):
            pat = pat.strip("` ").lower()
            if len(pat) >= 2:
                owners.setdefault(pat, set()).add(cells[0])
dups = {k: v for k, v in owners.items() if len(v) > 1}
ties = [l for l in reg.splitlines() if l.startswith("**동점 처리**")]
if len(ties) != 1:
    p.append(f"tie rule lines {len(ties)} != 1")
if dups and not ties:
    p.append(f"{len(dups)} triggers shared by several skills and no tie rule")
case("duplicate-trigger", p)

# autonomous · commit-push-matrix
AD = os.path.join(ROOT, "scripts", "autonomy_decide.py")


def decide(*args):
    env = {k: v for k, v in os.environ.items() if k != "FZ_AUTONOMY"}
    return subprocess.run([sys.executable, AD, *args], capture_output=True, text=True, env=env).returncode


p = []
for args, want in [(("--action", "pipeline", "--mode", "autonomous", "--in-scope", "--reversible"), 0),
                   (("--action", "pipeline", "--mode", "autonomous", "--in-scope"), 1),
                   (("--action", "pipeline", "--mode", "interactive", "--in-scope", "--reversible"), 1),
                   (("--action", "pipeline", "--mode", "autonomus", "--in-scope", "--reversible"), 1)]:
    rc = decide(*args)
    if rc != want:
        p.append(f"{' '.join(args)} -> {rc} != {want}")
case("autonomous", p)
p = []
for mode in ("interactive", "autonomous"):
    for action in ("commit", "push"):
        rc = decide("--action", action, "--mode", mode, "--in-scope", "--reversible")
        if rc != 3:
            p.append(f"{mode} {action} -> {rc} != 3 (BLOCK)")
case("commit-push-matrix", p)

# team-skill
p = []
for rel in ("skills/fz-commit/SKILL.md", "skills/fz-pr/SKILL.md"):
    t = rd(rel)
    if "`## Git Workflow`" in t:
        p.append(f"{rel} still keys on the `## Git Workflow` heading")
    if "governance.md` § 팀 스킬 위임" not in t:
        p.append(f"{rel} does not point to governance § 팀 스킬 위임")
if re.search(r"^`/sc:sc-git` 스킬을 사용하여 커밋을 실행", rd("skills/fz-commit/SKILL.md"), re.M):
    p.append("fz-commit keeps an unconditional /sc:sc-git commit route")
if not re.search(r"^## 팀 스킬 위임", gov, re.M):
    p.append("governance has no § 팀 스킬 위임")
case("team-skill", p)

# single-source
p = []
NORM = re.compile(r"범위 내 \+ 가역|autonomous` 면 \*범위 내 가역\*")
holders = sorted(os.path.relpath(f, ROOT) for f in glob.glob(os.path.join(ROOT, "skills", "**", "*.md"), recursive=True)
                 + glob.glob(os.path.join(ROOT, "modules", "*.md"))
                 if NORM.search(open(f, encoding="utf-8", errors="replace").read()))
if holders != ["modules/governance.md"]:
    p.append(f"autonomy exception stated in {holders} (want only modules/governance.md)")
for rel in ("skills/fz/SKILL.md", "modules/lead-action-default.md"):
    if "governance.md` § 자율 모드" not in rd(rel):
        p.append(f"{rel} lacks the pointer to governance § 자율 모드")
case("single-source", p)

print(f"rules: {'PASS' if not fails else 'FAIL'}")
sys.exit(0 if not fails else 1)
PY
