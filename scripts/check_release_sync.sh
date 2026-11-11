#!/bin/bash
# scripts/check_release_sync.sh — 릴리즈 산출물이 서로를 가리키는지 본다 (plan-final S10).
#
# ⛔ 왜 신설인가: `health-check.sh` 는 계약·문법·회귀를 보지만 **이번 변경의 문서 동기와 버전
#    갱신은 증명하지 않는다**(verify-gates S10 revise 지적). 버전이 세 곳에 흩어져 있어
#    한 곳만 올리는 실패가 실제로 있었다(v4.33.0 CHANGELOG "적용은 했는데 커밋하지 않았다").
#
# 검사: ① plugin.json == marketplace.json ② CHANGELOG 최상단 == plugin.json
#       ①-b 하위 플러그인(marketplace 두 번째 항목부터 · 리포 안 폴더) 버전 동기와 바뀐 뒤 버전 올림
#       ③ 가이드가 sweep 기록 위치(§5.8 ⑥)를 가리키는가 ④ health-check exit 0
#       ②-b README · CHANGELOG 의 노트 절 참조(§N · § 이름 · '이름' 절)가 그 노트 제목에 있다(F-421)
#       ②-c 직전 태그(v*) 대비 파일 모드 변경 0 — 허용 목록 tests/fixtures/release-mode-allow.txt(F-427)
# exit: 0=전부 충족(DOCS_SYNC_OK) / 1=불일치 / 2=대상 부재(측정 실패)
# diff-parse: hunk-state — neutralize_axis 는 `diff --git` 헤더 구간과 `@@` hunk 를 구분해 hunk 안 `+` 줄만 추가 줄로 센다
#
# 모드:
#   (없음)      ①~④ — 수동·CI 용. health-check 포함이라 **약 7분 20초** 걸린다(2026-11-08 실측 439s · 14코어)
#   --release   ①~④ + ⑤ **커밋 축** + ⑥ **findings 축**(노트가 닫은 finding 을 밝혔는가). 릴리즈 직전 게이트
#   --staged    ⑤만, staged 내용 기준. ⛔ pre-commit 용 — health-check 를 뺀다
#   --neutralize-diff <ref> [--rules <파일>]
#               ⑦만 — <ref> 대비 추가 줄(미추적 파일 포함) × 중립화 규칙 적중 0 (F-420). `--release` 는 직전 태그 대비로 ⑦ 을 함께 돈다
#               내장 규칙은 프로젝트를 드러내지 않는 모양만 본다(개인 홈 경로 · 허용 밖 메일 도메인 · 티켓 키 꼴).
#               회사 · 앱 이름 같은 사내 규칙은 공개 트리에 두지 않는다 — `--rules`(또는 FZ_NEUTRALIZE_RULES) 파일에 한 줄 한 정규식
#   --self-test 임시 git 리포로 ⑤의 실패/통과 쌍을 확인
#
# ⛔ **커밋 축을 기본 모드에 넣지 않는 이유**: pre-commit 은 *커밋하려는 중* 이라
#    깨끗한 워킹트리를 요구할 수 없다. 그래서 축을 `--release` 로 분리한다.
# ⛔ **워킹트리 전체의 청결을 보지 않는 이유**: 릴리즈 후 쌓인 다음 버전 작업이
#    정상 상태이므로 오탐이 된다. 보는 것은 **선언된 버전 자신의 산출물이 HEAD 에 있는가** 다 —
#    이것이 원래 실패 모드(v4.33.0 "적용은 했는데 커밋하지 않았다")의 정확한 오라클이다.
set -uo pipefail

MODE="" NREF="" NRULES="${FZ_NEUTRALIZE_RULES:-}"
case "${1:-}" in
  --release)   MODE="release" ;;
  --staged)    MODE="staged" ;;
  --self-test) MODE="self-test" ;;
  --neutralize-diff)
    MODE="neutralize"; NREF="${2:-}"
    [ -n "$NREF" ] || { echo "❌ --neutralize-diff 에 기준 ref 가 없다"; exit 2; }
    if [ "${3:-}" = "--rules" ]; then
      NRULES="${4:-}"; [ -f "$NRULES" ] || { echo "❌ --rules 파일이 없다: '${NRULES}'"; exit 2; }
    elif [ -n "${3:-}" ]; then echo "❌ 알 수 없는 인자: $3"; exit 2; fi ;;
  "")          MODE="default" ;;
  *) echo "❌ 알 수 없는 인자: $1 (사용: [--release|--staged|--self-test|--neutralize-diff <ref> [--rules <파일>]])"; exit 2 ;;
esac
#   루트는 **자기 위치**에서 해석한다 (`BASH_SOURCE[0]` — `$0` 는 source 시 호출자를 가리킨다)
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SELF_DIR/.." && pwd)"
cd "$ROOT_DIR" || { echo "❌ 플러그인 루트로 이동 실패: $ROOT_DIR"; exit 2; }

fail=0
note() { echo "  ❌ $1"; fail=$((fail + 1)); }

json_version() {   # $1=파일경로 · stdout=version (실패 시 빈 문자열)
  python3 -c '
import json,sys
try: d=json.load(open(sys.argv[1]))
except Exception: sys.exit(0)
p=d["plugins"][0] if isinstance(d.get("plugins"),list) and d["plugins"] else d
print(p.get("version",""))' "$1" 2>/dev/null
}

git_show_version() {   # $1=리포 · $2=ref:path · stdout=version (소비처: --staged 전용)
  git -C "$1" show "$2" 2>/dev/null | python3 -c '
import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit(0)
p=d["plugins"][0] if isinstance(d.get("plugins"),list) and d["plugins"] else d
print(p.get("version",""))' 2>/dev/null
}

# ⑤ 커밋 축 — **선언된 버전 자신의 산출물이 HEAD 에 있는가.**
#    ⛔ 워킹트리 전체의 청결을 보지 않는다(다음 버전 작업이 쌓이는 것은 정상).
#    반환: 0=충족 · 1=불일치(사유를 stdout 에) · 2=측정 불가
commit_axis() {   # $1=리포 디렉토리 · $2=선언 버전
  local repo="$1" ver="$2" bad=0
  # ⛔ 가드는 **하나**다. 이전 판은 `--git-dir` 과 `--verify HEAD` 두 줄이 같은 2를 반환해
  #    어블레이션에서 서로를 가렸다(한쪽을 지워도 픽스처가 통과). `--verify HEAD` 가
  #    비-git 과 커밋 0개를 모두 잡으므로 이것만 둔다.
  git -C "$repo" rev-parse --verify HEAD >/dev/null 2>&1 \
    || { echo "  ⚠️ git 리포가 아니거나 커밋이 없다 — 커밋 축 미판정(⛔ 통과 아님)"; return 2; }

  # ⛔ **HEAD 버전과 디스크 버전을 대조하지 않는다 — 단독 발화가 불가능하다.**
  #    `$ver` 를 디스크 plugin.json 에서 읽으므로, HEAD 가 다르면 그 파일이 **반드시** dirty 다.
  #    즉 아래 dirty 검사와 중복이고, 어블레이션에서 제거해도 픽스처가 통과했다(죽은 로직).
  #    실패 모드(v4.33.0 "적용은 했는데 커밋하지 않았다")를 잡는 것은 dirty 검사 쪽이다.

  # 선언 버전의 릴리즈 문서가 **추적되는가** — 디스크 존재만으로는 릴리즈가 아니다
  local rel="docs/releases/v${ver}.md"
  if [ -f "$repo/$rel" ]; then
    git -C "$repo" ls-files --error-unmatch "$rel" >/dev/null 2>&1 \
      || { echo "  ❌ $rel 이 untracked — 릴리즈 문서가 커밋되지 않았다"; bad=1; }
  else
    echo "  ❌ $rel 이 없다 — 선언된 버전의 릴리즈 문서가 부재"; bad=1
  fi

  # 버전 3곳 중 커밋 안 된 수정이 남아 있으면 HEAD 와 디스크가 갈린 상태다
  local dirty
  dirty=$(git -C "$repo" status --porcelain -- .claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md 2>/dev/null)
  [ -z "$dirty" ] || { echo "  ❌ 버전 선언 파일에 미커밋 수정이 있다:"; echo "$dirty" | sed 's/^/      /'; bad=1; }

  return "$bad"
}

# ⑥ findings 축 — 선언 버전 노트가 **닫은 finding 을 밝혔는가**: `Closes:` 줄 또는 '닫은 finding 없음' 표지(v4.39.0:54 꼴).
#    ⛔ 레지스트리를 읽지 않는다 — 레지스트리 없는 머신에서도 같은 판정이다. applied ↔ Closes 대조는
#       check_release_closes.py 를 명시로 돌린다(CLAUDE.md 릴리스 절차).
#    반환: 0=선언 있음 · 1=선언 없음 · 2=노트 부재(미판정)
findings_axis() {   # $1=노트 경로
  local n="$1"
  [ -f "$n" ] || { echo "  ⚠️ $n 없음 — findings 축 미판정(⛔ 통과 아님)"; return 2; }
  # ⛔ 템플릿 원문이 두 술어를 이미 충족한다(_TEMPLATE.md 의 자리표시 Closes 줄 · 따옴표 안 표지 안내) — 둘 다 선언이 아니다
  if grep -E '^Closes:' "$n" | grep -Eq 'F-00[12]-(some|another)-slug'; then
    echo "  ❌ $n 의 Closes: 줄에 템플릿 자리표시 slug 가 남았다 — 닫은 엔트리로 바꾸거나 줄을 지운다"; return 1
  fi
  if grep -Eq '^Closes:' "$n" || grep -Eq "(^|[^'\"])닫은 finding (이 )?없" "$n"; then return 0; fi
  echo "  ❌ $n 에 Closes: 줄도 '닫은 finding 없음' 표지도 없다 — 닫은 것을 적거나 없음을 밝힌다"
  return 1
}

# ①-b 하위 플러그인 — marketplace 두 번째 항목부터, source 가 이 리포 안 폴더(`./…`)인 것마다 둘을 본다.
#    · 그 폴더 `.claude-plugin/plugin.json` 의 버전 == marketplace 항목의 버전
#    · 직전 릴리스 태그(`v*`)에 그 폴더가 있었고 그 뒤 내용이 바뀌었으면(미커밋 · untracked 포함) 버전도 바뀌었다 —
#      같은 버전이면 `plugin update` 가 바뀐 내용을 건너뛴다. 태그가 없거나 태그에 없던 폴더(새 플러그인)는 넘어간다.
#    반환: 0=충족 · 1=불일치(사유를 stdout 에) · 2=marketplace 의 plugins 를 읽지 못함
subplugin_axis() {   # $1=리포 디렉토리
  python3 - "$1" <<'PY'
import json, subprocess, sys
repo = sys.argv[1]
def git(*args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
def version_of(text):
    try:
        value = json.loads(text)
    except Exception:
        return ""
    return value.get("version", "") if isinstance(value, dict) else ""
try:
    with open(f"{repo}/.claude-plugin/marketplace.json", encoding="utf-8") as f:
        plugins = json.load(f)["plugins"]
    assert isinstance(plugins, list)
except Exception:
    print("  ⚠️ marketplace.json 의 plugins 를 읽지 못했다 — 하위 플러그인 미판정(⛔ 통과 아님)")
    sys.exit(2)
found = git("describe", "--tags", "--abbrev=0", "--match", "v*")
tag = found.stdout.strip() if found.returncode == 0 else ""
bad = 0
for entry in plugins[1:]:
    source = entry.get("source") if isinstance(entry, dict) else None
    if not isinstance(source, str) or not source.startswith("./"):
        continue
    path = source[2:].rstrip("/")
    name, listed = entry.get("name", path), entry.get("version", "")
    try:
        with open(f"{repo}/{path}/.claude-plugin/plugin.json", encoding="utf-8") as f:
            own = version_of(f.read())
    except OSError:
        own = ""
    if own == "" or own != listed:
        print(f"  ❌ {name}: {path}/.claude-plugin/plugin.json({own or '읽지 못함'}) ≠ marketplace({listed})")
        bad = 1
        continue
    if tag == "":
        continue
    before = git("show", f"{tag}:{path}/.claude-plugin/plugin.json")
    if before.returncode != 0:
        continue
    changed = git("diff", "--quiet", tag, "--", path).returncode != 0 \
        or git("ls-files", "--others", "--exclude-standard", "--", path).stdout.strip() != ""
    if changed and version_of(before.stdout) == own:
        print(f"  ❌ {name}: {tag} 뒤 {path} 가 바뀌었는데 버전이 {own} 그대로다 — plugin update 가 건너뛴다")
        bad = 1
sys.exit(bad)
PY
}

# ②-b 노트 절 참조 — README · CHANGELOG 가 노트의 절을 번호(§2) · 이름(§ 남은 것) · 따옴표('X' 절)로 가리키면 그 절이 노트에 있어야 한다.
#    노트는 줄 안의 `docs/releases/vX.md` 가 있으면 그것, 없으면 CHANGELOG 는 가장 가까운 위 `### vX` 절 · README 는 최상단 버전.
#    이름 대조: 노트 제목에서 괄호 · ` — ` 뒤를 뗀 앞부분으로 참조 문장이 시작하면 해소(`§ 남은 것에 적었다` → `## 남은 것 (가이드 갱신)`).
#    ⛔ 노트 제목을 고친 뒤 옛 제목을 가리키는 요약이 남던 실패(F-421 — README:154 · CHANGELOG 두 곳)를 잡는다
#    반환: 0=충족 · 1=끊긴 참조(사유를 stdout 에) · 2=CHANGELOG 부재
note_ref_axis() {   # $1=리포 디렉토리
  python3 - "$1" <<'PY'
import os, re, sys
repo = sys.argv[1]
SEC_RE = re.compile(r"(?:릴리[즈스]\s*노트|docs/releases/v(\d+\.\d+\.\d+)\.md`?)\s*§\s*(\S.*)")
QUO_RE = re.compile(r"(?:노트(?:의)?|docs/releases/v(\d+\.\d+\.\d+)\.md`?)\s*'([^'\n]+)'\s*절")
VER_RE = re.compile(r"^###\s+v(\d+\.\d+\.\d+)")
FENCE_RE = re.compile(r"^\s*(```|~~~)")

def norm(s):
    return re.sub(r"[`*]", "", s).strip()

def core(h):
    return re.split(r"\s+—\s+|\s*\(", norm(h), maxsplit=1)[0].strip()

cache = {}
def heads(ver):
    if ver not in cache:
        p = os.path.join(repo, "docs", "releases", f"v{ver}.md")
        if not os.path.isfile(p):
            cache[ver] = None
        else:
            out, fence = [], False
            for ln in open(p, encoding="utf-8"):
                if FENCE_RE.match(ln):
                    fence = not fence
                    continue
                m = re.match(r"^#{1,6}\s+(.*)", ln)
                if m and not fence:
                    out.append(norm(m.group(1)))
            cache[ver] = out
    return cache[ver]

def sec_ok(hs, rest):
    rest = norm(rest)
    m = re.match(r"(\d+)(?!\d)", rest)
    if m:
        return any(re.match(rf"(?:§\s*)?{m.group(1)}(?:[.)]|\s|$)", h) for h in hs)
    return any(core(h) and rest.startswith(core(h)) for h in hs)

def quote_ok(hs, name):
    name = norm(name)
    return any(name == core(h) or name in h for h in hs)

cl = os.path.join(repo, "CHANGELOG.md")
if not os.path.isfile(cl):
    print("  ⚠️ CHANGELOG.md 없음 — 노트 절 참조 미판정(⛔ 통과 아님)")
    sys.exit(2)
lines = open(cl, encoding="utf-8").read().split("\n")
top = next((m.group(1) for m in map(VER_RE.match, lines) if m), None)
bad = 0
for rel in ("README.md", "CHANGELOG.md"):
    p = os.path.join(repo, rel)
    if not os.path.isfile(p):
        continue
    cur, fence = (top if rel == "README.md" else None), False
    for i, ln in enumerate(open(p, encoding="utf-8").read().split("\n"), 1):
        if FENCE_RE.match(ln):
            fence = not fence
            continue
        if fence:
            continue
        vm = VER_RE.match(ln)
        if vm and rel == "CHANGELOG.md":
            cur = vm.group(1)
            continue
        for rx, ok in ((SEC_RE, sec_ok), (QUO_RE, quote_ok)):
            for m in rx.finditer(ln):
                ver = m.group(1) or cur
                if ver is None:
                    continue
                hs = heads(ver)
                if hs is None:
                    print(f"  ❌ {rel}:{i}: 노트 v{ver} 가 없다 — 절 참조 '{m.group(2)[:40]}' 를 확인할 곳이 없다")
                    bad = 1
                elif not ok(hs, m.group(2)):
                    print(f"  ❌ {rel}:{i}: 노트 v{ver} 에 '{norm(m.group(2))[:40]}' 절이 없다 — 노트 제목을 고친 뒤 옛 이름이 남았다")
                    bad = 1
sys.exit(bad)
PY
}

# ②-c 파일 모드 — 직전 태그(v*) 대비 `mode change` 가 허용 목록 밖에 있으면 불일치(F-427: 원자 교체가 0755 를 0644 로 바꿨는데
#    검증 경로는 모두 `bash <파일>` 이라 실행 비트 없이도 돌았다). 태그가 없으면 건너뛴다(subplugin_axis 와 같은 규칙).
#    허용 목록 = tests/fixtures/release-mode-allow.txt(한 줄 한 경로 · `#` 주석) — 없으면 빈 목록.
#    반환: 0=충족 · 1=허용 밖 모드 변경 · 2=git 리포 아님
mode_axis() {   # $1=리포 디렉토리
  local repo="$1" tag allow="$1/tests/fixtures/release-mode-allow.txt" hits bad=0 path
  git -C "$repo" rev-parse --verify HEAD >/dev/null 2>&1 \
    || { echo "  ⚠️ git 리포가 아니거나 커밋이 없다 — 모드 축 미판정(⛔ 통과 아님)"; return 2; }
  tag="$(git -C "$repo" describe --tags --abbrev=0 --match 'v*' 2>/dev/null)" || { echo "  ⚠️ v* 태그 없음 — 모드 축 건너뜀"; return 0; }
  hits="$(git -C "$repo" -c core.quotepath=off diff --summary "$tag" -- . 2>/dev/null | sed -n 's/^ mode change [0-7]* => [0-7]* //p')"
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    if [ -f "$allow" ] && grep -vE '^[[:space:]]*(#|$)' "$allow" | grep -qxF -- "$path"; then continue; fi
    echo "  ❌ $tag 뒤 파일 모드가 바뀌었다: $path — 의도한 변경이면 tests/fixtures/release-mode-allow.txt 에 적는다"; bad=1
  done <<< "$hits"
  return "$bad"
}

# ⑦ 중립화 — <ref> 대비 추가 줄(미추적 파일 포함)에 공개 저장소에 두면 안 되는 식별자가 있는가(F-420).
#    내장 규칙은 모양만 본다 — 개인 홈 경로 · 허용 밖 메일 도메인 · 티켓 키 꼴(대문자 2~6 + 숫자 3~6, 허용 접두 제외).
#    사내 이름 규칙은 $3 파일(한 줄 한 정규식 · `#` 주석)로만 받는다 — 규칙 자체가 프로젝트를 드러내므로 트리에 두지 않는다.
#    반환: 0=적중 0 · 1=적중(파일:줄: 규칙 — 토큰) · 2=ref 를 풀지 못함 · 규칙 파일 오류
neutralize_axis() {   # $1=리포 · $2=기준 ref · $3=사내 규칙 파일(빈 값 가능)
  python3 - "$1" "$2" "${3:-}" <<'PY'
import os, re, subprocess, sys
repo, ref, rules_path = sys.argv[1], sys.argv[2], sys.argv[3]

def git(*a):
    return subprocess.run(["git", "-C", repo, "-c", "core.quotepath=off", *a], capture_output=True, text=True, errors="replace")

if git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode != 0:
    print(f"  ⚠️ 기준 ref 를 풀지 못했다: {ref} — 중립화 축 미판정(⛔ 통과 아님)")
    sys.exit(2)
HOME_RE = re.compile(r"/(?:Users|home)/(?!example/|you/|user/|me/|\{user\}/|<user>/|USER/|\$USER/)[A-Za-z0-9._-]+/")
MAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})")
MAIL_OK = ("example.com", "example.org", "example.net", "users.noreply.github.com", "anthropic.com")
KEY_RE = re.compile(r"(?<![A-Za-z0-9_-])([A-Z]{2,6})-\d{3,6}(?![A-Za-z0-9_])")
# ISSUE 는 fz 스키마(gpt_verification · issue_tracker 의 `^ISSUE-[0-9]{3,}$`)가 정한 지적 id 이름공간이다 — 사내 티켓 키가 아니다
KEY_OK = {"TKT", "TICKET", "ISO", "CVE", "RFC", "UTF", "SHA", "PEP", "GHSA", "ISSUE"}
rules = []
if rules_path:
    try:
        for n, ln in enumerate(open(rules_path, encoding="utf-8"), 1):
            ln = ln.rstrip("\n")
            if ln.strip() and not ln.lstrip().startswith("#"):
                rules.append((f"사내 규칙 {n}", re.compile(ln)))
    except (OSError, re.error) as e:
        print(f"  ⚠️ 사내 규칙 파일을 읽지 못했다: {rules_path} — {e} (⛔ 통과 아님)")
        sys.exit(2)

def hits(text):
    out = [("개인 홈 경로", m.group(0)) for m in HOME_RE.finditer(text)]
    out += [("메일 주소", m.group(0)) for m in MAIL_RE.finditer(text)
            if not any(m.group(1).lower() == d or m.group(1).lower().endswith("." + d) for d in MAIL_OK)]
    out += [("티켓 키 꼴", m.group(0)) for m in KEY_RE.finditer(text) if m.group(1) not in KEY_OK]
    out += [(name, m.group(0)) for name, rx in rules for m in rx.finditer(text)]
    return out

added = []   # (경로, 줄 번호, 내용)
d = git("diff", "-U0", "--no-color", "--no-ext-diff", "--text", ref, "--", ".")
if d.returncode != 0:
    print(f"  ⚠️ git diff 실패: {d.stderr.strip()[:120]} — 중립화 축 미판정(⛔ 통과 아님)")
    sys.exit(2)
path, in_hunk, new_no = None, False, 0
for ln in d.stdout.split("\n"):
    if ln.startswith("diff --git "):
        path, in_hunk = None, False
        continue
    if not in_hunk:
        if ln.startswith("+++ "):
            tgt = ln[4:]
            path = None if tgt == "/dev/null" else (tgt[2:] if tgt.startswith("b/") else tgt)
        elif ln.startswith("@@"):
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", ln)
            in_hunk, new_no = True, int(m.group(1)) if m else 0
        continue
    if ln.startswith("@@"):
        m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", ln)
        new_no = int(m.group(1)) if m else 0
    elif ln.startswith("+"):
        if path:
            added.append((path, new_no, ln[1:]))
        new_no += 1
    elif ln.startswith(" "):
        new_no += 1
    elif ln.startswith("diff --git "):
        in_hunk = False
untracked = git("ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0")
for rel in filter(None, untracked):
    try:
        with open(os.path.join(repo, rel), encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                added.append((rel, n, line.rstrip("\n")))
    except (OSError, UnicodeDecodeError):
        continue   # 바이너리 · 읽기 불가 — 텍스트 식별자 규칙의 대상이 아니다
bad = 0
for rel, n, text in added:
    for name, tok in hits(text):
        print(f"  ❌ {rel}:{n}: {name} — {tok}")
        bad = 1
print(f"  중립화: {ref} 대비 추가 줄 {len(added)} · 사내 규칙 {len(rules)}개{'' if rules else '(미지정 — 내장 모양 규칙만)'}")
sys.exit(bad)
PY
}

# ── --self-test — 임시 git 리포로 ⑤의 실패/통과 쌍을 확인한다 ────────────────
if [ "$MODE" = "self-test" ]; then
  pass=0; failed=0
  # ⛔ git 단계의 exit code 를 버리지 않는다 — 실패를 삼키면 **위조 픽스처**가 만들어지고
  #    자기시험이 아무것도 증명하지 않는다 (`lint_contracts` #N5 가 이것을 잡는다).
  #    ⛔ `mk` 밖에 정의한다 — `mk` 는 `$( )` 서브셸에서 돌아, 그 안에서 정의하면 호출부(③ · ⑧)에 없다.
  gq() { "$@" >/dev/null 2>&1 || { echo "⛔ 픽스처 준비 실패: $*" >&2; exit 2; }; }
  mk() {   # $1=버전 · stdout=리포 경로 (v$1 을 전부 커밋한 상태)
    local d ver="$1"
    d=$(mktemp -d "${TMPDIR:-/tmp}/fz-relsync.XXXXXX")
    mkdir -p "$d/.claude-plugin" "$d/docs/releases"
    printf '{"version": "%s"}\n' "$ver" > "$d/.claude-plugin/plugin.json"
    printf '{"plugins": [{"version": "%s"}]}\n' "$ver" > "$d/.claude-plugin/marketplace.json"
    printf '# Changelog\n\n### v%s (2026-01-01) — x\n' "$ver" > "$d/CHANGELOG.md"
    printf '# v%s\n' "$ver" > "$d/docs/releases/v${ver}.md"
    gq git -C "$d" init -q
    gq git -C "$d" -c user.email=t@t -c user.name=t add -A
    gq git -C "$d" -c user.email=t@t -c user.name=t commit -qm "v$ver"
    echo "$d"
  }
  # ⛔ `R=$(mk …)` 는 **명령 치환 서브셸**이라 mk 안의 `exit 2` 가 런을 멈추지 못한다 —
  #    실측: 서브셸만 죽고 `$R` 이 비어 `/CHANGELOG.md` 에 쓰려 했고 자기시험은 4/5 로 계속됐다.
  #    그래서 호출부에서 종료코드와 산출물을 **둘 다** 검산한다.
  #    ⛔⛔ **`exit` 는 `$( )` 를 벗어나지 못한다.** 그래서 이 함수는 경로를 stdout 이 아니라
  #        전역 `REPO` 에 담고, 호출부는 치환 **없이** `mkr 1.0.0` 로 부른다. 치환으로 부르면
  #        여기의 `exit 2` 가 다시 서브셸에 갇힌다(실측: 두 층 모두에서 갇혔다).
  REPO=""
  mkr() {
    REPO=$(mk "$1") || { echo "⛔ 픽스처 준비 실패 (mk 종료코드)" >&2; exit 2; }
    [ -n "$REPO" ] && [ -d "$REPO/.git" ] \
      || { echo "⛔ 픽스처 리포가 만들어지지 않았다: '${REPO}'" >&2; exit 2; }
  }

  ok_() { pass=$((pass+1)); [ -n "${FZ_SELFTEST_LIST:-}" ] && echo "PASS $1"; return 0; }   # 통과 줄 — 게이트가 셀 이름으로 센다
  case_() {   # $1=이름 · $2=기대 반환 · $3=리포 · $4=선언버전
    local out rc
    out=$(commit_axis "$3" "$4"); rc=$?
    if [ "$rc" = "$2" ]; then ok_ "$1"
    else failed=$((failed+1)); echo "  FAIL $1: 반환 $rc (기대 $2)"; echo "$out" | sed 's/^/        /'; fi
  }

  # ① 정상 — 전부 커밋됨
  mkr 1.0.0; R="$REPO"; case_ "all-committed" 0 "$R" "1.0.0"; rm -rf "$R"

  # ② 결함 — 버전만 디스크에서 올리고 커밋하지 않았다 (v4.33.0 실패 모드)
  mkr 1.0.0; R="$REPO"
  printf '{"version": "1.1.0"}\n' > "$R/.claude-plugin/plugin.json"
  case_ "bump-without-release-doc" 1 "$R" "1.1.0"; rm -rf "$R"
  #    ⚠️ 이 픽스처는 **격리형이 아니다** — dirty 와 릴리즈 문서 부재가 함께 발화한다.
  #       현실적 상태(버전 올리고 문서를 빠뜨림)라서 남기고, 각 검사의 격리는 아래 두 건이 한다.

  # ③ 결함 — 릴리즈 문서가 untracked
  mkr 1.0.0; R="$REPO"
  printf '{"version": "1.1.0"}\n' > "$R/.claude-plugin/plugin.json"
  printf '{"plugins": [{"version": "1.1.0"}]}\n' > "$R/.claude-plugin/marketplace.json"
  printf '# Changelog\n\n### v1.1.0 (2026-01-02) — y\n' > "$R/CHANGELOG.md"
  printf '# v1.1.0\n' > "$R/docs/releases/v1.1.0.md"
  gq git -C "$R" -c user.email=t@t -c user.name=t add .claude-plugin CHANGELOG.md
  gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm "v1.1.0 (릴리즈 문서 빠뜨림)"
  case_ "release-doc-untracked" 1 "$R" "1.1.0"; rm -rf "$R"

  # ④ 결함 — 릴리즈 문서는 추적된 채로 **버전 선언 파일만** 더럽다.
  #    ⛔ 이 픽스처가 dirty 검사를 **격리**한다. 릴리즈 문서를 빼면 다른 검사가 발화해
  #       dirty 를 지워도 통과했다(실측 — 헛돌이였다).
  mkr 1.0.0; R="$REPO"
  printf '# Changelog\n\n### v1.0.0 (2026-01-01) — x\n\n추가 한 줄\n' > "$R/CHANGELOG.md"
  case_ "version-file-dirty-only" 1 "$R" "1.0.0"; rm -rf "$R"

  # ⑤ 측정 불가 — git 리포가 아니다. ⛔ 미판정은 통과가 아니다
  R=$(mktemp -d "${TMPDIR:-/tmp}/fz-relsync.XXXXXX"); case_ "not-a-repo" 2 "$R" "1.0.0"; rm -rf "$R"

  # ①-b 하위 플러그인 — v1.0.0 태그 리포에 `mods/sub` 를 둔다. $1=태그 때 둘지(yes/no) · $2=하위 버전
  sub_files() {   # $1=리포 · $2=하위 plugin.json 버전 · $3=marketplace 하위 버전
    mkdir -p "$1/mods/sub/.claude-plugin"
    printf '{"version": "%s"}\n' "$2" > "$1/mods/sub/.claude-plugin/plugin.json"
    printf '{"plugins": [{"version": "1.0.0"}, {"name": "sub", "source": "./mods/sub", "version": "%s"}]}\n' "$3" > "$1/.claude-plugin/marketplace.json"
  }
  case_sub() {   # $1=이름 · $2=기대 반환 · $3=리포
    local out rc
    out=$(subplugin_axis "$3"); rc=$?
    if [ "$rc" = "$2" ]; then ok_ "$1"
    else failed=$((failed+1)); echo "  FAIL $1: 반환 $rc (기대 $2)"; echo "$out" | sed 's/^/        /'; fi
  }
  # ⑥ 정상 — 태그 뒤 새로 생긴 하위 플러그인(태그에 없던 폴더)은 버전 올림 검사를 건너뛴다
  mkr 1.0.0; R="$REPO"; gq git -C "$R" tag v1.0.0
  sub_files "$R" 0.1.0 0.1.0; case_sub "sub-new-after-tag" 0 "$R"; rm -rf "$R"
  # ⑦ 결함 — 하위 plugin.json 과 marketplace 항목의 버전이 다르다
  mkr 1.0.0; R="$REPO"; gq git -C "$R" tag v1.0.0
  sub_files "$R" 0.1.0 0.2.0; case_sub "sub-version-mismatch" 1 "$R"; rm -rf "$R"
  # ⑧ 결함 — 태그에 있던 하위 플러그인 내용이 바뀌었는데 버전은 그대로다(untracked 파일 추가)
  mkr 1.0.0; R="$REPO"; sub_files "$R" 0.1.0 0.1.0
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A
  gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm "sub 0.1.0"; gq git -C "$R" tag v1.0.0
  printf 'x\n' > "$R/mods/sub/new.ts"; case_sub "sub-changed-no-bump" 1 "$R"
  # ⑨ 정상 — 같은 변경에 두 곳 버전을 함께 올렸다(⑧ 의 대조)
  sub_files "$R" 0.1.1 0.1.1; case_sub "sub-changed-bumped" 0 "$R"; rm -rf "$R"

  # ⑥ findings 축 — 노트 선언만 본다(레지스트리 무관)
  case_fx() {   # $1=이름 · $2=기대 반환 · $3=노트 본문(빈 문자열이면 노트 없음)
    local d out rc
    d=$(mktemp -d "${TMPDIR:-/tmp}/fz-relsync.XXXXXX")
    [ -n "$3" ] && printf '%s\n' "$3" > "$d/v9.9.9.md"
    out=$(findings_axis "$d/v9.9.9.md"); rc=$?
    rm -rf "$d"
    if [ "$rc" = "$2" ]; then ok_ "$1"
    else failed=$((failed+1)); echo "  FAIL $1: 반환 $rc (기대 $2)"; echo "$out" | sed 's/^/        /'; fi
  }
  case_fx "findings-axis-closes-ok" 0 $'# v9.9.9\n\nCloses: F-001'
  case_fx "findings-axis-no-finding-marker-ok" 0 $'# v9.9.9\n\n이 릴리즈는 닫은 finding 이 없어 `Closes:` 줄을 쓰지 않는다.'
  case_fx "findings-axis-missing-fails" 1 $'# v9.9.9\n\n<!-- Closes: 줄 없음 -->\n본문만 있다'
  # 템플릿 원문 그대로인 노트는 아무것도 선언하지 않았다 — 자리표시 Closes · 따옴표 안 표지 안내가 술어를 채우면 안 된다
  case_fx "findings-axis-template-verbatim-fails" 1 "$(cat "$ROOT_DIR/docs/releases/_TEMPLATE.md")"
  case_fx "findings-axis-quoted-marker-fails" 1 $'# v9.9.9\n\n- 닫은 것이 없으면 본문에 \'닫은 finding 이 없어 …\' 표지를 둔다'
  # 기본 모드는 ⑥ 을 부르지 않고 FZ_FINDINGS_ROOT 도 읽지 않는다 — 실행 확인은 기본 모드 전체 실행(health-check 포함)이 맡는다
  calls=$(grep -n 'findings_axis "\$' "${BASH_SOURCE[0]}" | grep -v 'case_fx\|out=\$(findings_axis' | cut -d: -f1)
  dm_ok=1
  for ln in $calls; do sed -n "$((ln - 1)),${ln}p" "${BASH_SOURCE[0]}" | grep -q 'MODE" = "release"' || dm_ok=0; done
  [ -n "$calls" ] || dm_ok=0
  sed -n '/^findings_axis()/,/^}/p' "${BASH_SOURCE[0]}" | grep -q 'FZ_FINDINGS_ROOT' && dm_ok=0
  if [ "$dm_ok" = 1 ]; then ok_ "default-mode-no-registry-ok"; else failed=$((failed+1)); echo "  FAIL default-mode-no-registry-ok: ⑥ 호출이 release 가드 밖이거나 레지스트리를 읽는다"; fi

  # 축 판정 공용 — $1=이름 · $2=기대 반환 · 나머지=부를 함수와 인자
  case_ax() {
    local name="$1" want="$2" out rc; shift 2
    out=$("$@"); rc=$?
    if [ "$rc" = "$want" ]; then ok_ "$name"
    else failed=$((failed+1)); echo "  FAIL $name: 반환 $rc (기대 $want)"; echo "$out" | sed 's/^/        /'; fi
  }

  # ②-b 노트 절 참조(F-421) — 노트 제목 둘(무엇이 바뀌었나 · 2. 검증)과 CHANGELOG 한 줄
  nr() {   # $1=CHANGELOG 본문 줄 · stdout 없음 · 전역 R 에 리포
    R=$(mktemp -d "${TMPDIR:-/tmp}/fz-relsync.XXXXXX"); mkdir -p "$R/docs/releases"
    printf '# v1.0.0 — x\n\n## 무엇이 바뀌었나\n\n## 2. 검증\n\n## 남은 것 (가이드 갱신)\n' > "$R/docs/releases/v1.0.0.md"
    printf '# Changelog\n\n### v1.0.0 (2026-01-01) — x\n\n%s\n' "$1" > "$R/CHANGELOG.md"
  }
  nr "자세한 표는 릴리즈 노트 § 무엇을 고쳤나 에 있다"; case_ax "f421-note-section-ref-missing" 1 note_ref_axis "$R"; rm -rf "$R"
  nr "자세한 표는 릴리즈 노트 § 무엇이 바뀌었나 에 있다"; case_ax "f421-note-section-ref-ok" 0 note_ref_axis "$R"; rm -rf "$R"
  nr "남은 일은 릴리즈 노트 § 남은 것에 적었다"; case_ax "f421-note-section-prefix-ok" 0 note_ref_axis "$R"; rm -rf "$R"
  nr "결과는 릴리즈 노트 §3 표"; case_ax "f421-note-section-number-missing" 1 note_ref_axis "$R"; rm -rf "$R"
  nr "결과는 릴리즈 노트 §2 표"; case_ax "f421-note-section-number-ok" 0 note_ref_axis "$R"; rm -rf "$R"
  nr "근거: docs/releases/v1.0.0.md 'Closes 줄 규약' 절"; case_ax "f421-quoted-section-missing" 1 note_ref_axis "$R"; rm -rf "$R"
  nr "근거: docs/releases/v2.0.0.md '무엇이 바뀌었나' 절"; case_ax "f421-note-file-missing" 1 note_ref_axis "$R"; rm -rf "$R"
  # 실제 트리 — 지금 README · CHANGELOG 의 참조가 모두 풀린다(이 검사가 막을 회귀의 출발점)
  case_ax "f421-real-tree-refs-ok" 0 note_ref_axis "$ROOT_DIR"

  # ②-c 모드 변경(F-427) — 태그 v1.0.0 의 0755 스크립트를 0644 로
  mkr 1.0.0; R="$REPO"; printf '#!/bin/bash\n' > "$R/run.sh"; chmod 755 "$R/run.sh"
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A; gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm s
  gq git -C "$R" tag v1.0.0; chmod 644 "$R/run.sh"
  case_ax "f427-mode-change-flagged" 1 mode_axis "$R"
  mkdir -p "$R/tests/fixtures"; printf '# 의도한 변경\nrun.sh\n' > "$R/tests/fixtures/release-mode-allow.txt"
  case_ax "f427-mode-change-allowlisted" 0 mode_axis "$R"
  chmod 755 "$R/run.sh"; rm -rf "$R/tests"; case_ax "f427-no-mode-change-ok" 0 mode_axis "$R"; rm -rf "$R"

  # ⑦ 중립화(F-420) — ⛔ 시험 문자열은 쪼개 쓴다. 이 파일도 추가 줄로 검사되므로 원문 그대로면 자기 자신이 걸린다
  HOMEP="/Us""ers/alice/work"; MAILP="bob@""corp-mail.io"; KEYP="AB""C-1234"
  mkr 1.0.0; R="$REPO"; printf 'base %s\n' "$HOMEP" > "$R/old.txt"
  gq git -C "$R" -c user.email=t@t -c user.name=t add -A; gq git -C "$R" -c user.email=t@t -c user.name=t commit -qm base
  case_ax "f420-base-line-not-counted" 0 neutralize_axis "$R" HEAD ""
  printf '경로 %s\n' "$HOMEP" >> "$R/CHANGELOG.md"; case_ax "f420-added-line-neutralize-hit" 1 neutralize_axis "$R" HEAD ""
  gq git -C "$R" checkout -q -- CHANGELOG.md
  printf '문의 %s\n' "$MAILP" > "$R/new.md"; case_ax "f420-untracked-file-scanned" 1 neutralize_axis "$R" HEAD ""
  printf '티켓 %s · 중립 TKT-5743 · 예시 /Us''ers/example/x\n' "$KEYP" > "$R/new.md"; case_ax "f420-ticket-key-shape-hit" 1 neutralize_axis "$R" HEAD ""
  printf '중립 TKT-5743 · 예시 /Us''ers/example/x · noreply@''example.com\n' > "$R/new.md"; case_ax "f420-neutral-tokens-ok" 0 neutralize_axis "$R" HEAD ""
  printf '지적 ISSUE-001 · ISSUE-202616\n' > "$R/new.md"; case_ax "r3-issue-id-namespace-ok" 0 neutralize_axis "$R" HEAD ""
  printf '지적 ISSUE-001 · 티켓 %s\n' "$KEYP" > "$R/new.md"; case_ax "r3-issue-allow-keeps-other-keys" 1 neutralize_axis "$R" HEAD ""
  printf '(?i)acme\n' > "$R/../fz-relsync-rules.$$"; printf 'Acme 앱\n' > "$R/new.md"
  case_ax "f420-private-rules-file" 1 neutralize_axis "$R" HEAD "$R/../fz-relsync-rules.$$"; rm -f "$R/../fz-relsync-rules.$$"
  case_ax "f420-bad-ref-unrun" 2 neutralize_axis "$R" no-such-ref ""
  rm -rf "$R"

  echo "self-test $pass/$((pass+failed)) passed"
  [ "$failed" = 0 ] || exit 1
  exit 0
fi

# ── --staged — pre-commit 용. 버전 선언 파일이 staged 일 때만, 값싸게 ──────────
if [ "$MODE" = "staged" ]; then
  VFILES=".claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md"
  # shellcheck disable=SC2086
  touched=$(git diff --cached --name-only -- $VFILES 2>/dev/null)
  [ -n "$touched" ] || { echo "STAGED_SKIP (버전 선언 파일 변경 없음)"; exit 0; }
  ipv=$(git_show_version "$ROOT_DIR" ":.claude-plugin/plugin.json")
  imv=$(git_show_version "$ROOT_DIR" ":.claude-plugin/marketplace.json")
  icv=$(git show ":CHANGELOG.md" 2>/dev/null | grep -m1 -oE '^### v[0-9]+\.[0-9]+\.[0-9]+' | sed 's/^### v//')
  [ -n "$ipv" ] || { echo "❌ staged plugin.json 에서 version 을 읽지 못했다 (측정 실패)"; exit 2; }
  echo "staged 버전: plugin=$ipv · marketplace=$imv · CHANGELOG=$icv"
  [ "$ipv" = "$imv" ] || note "staged plugin.json($ipv) ≠ marketplace.json($imv)"
  [ "$ipv" = "$icv" ] || note "staged plugin.json($ipv) ≠ CHANGELOG 최상단($icv)"
  if [ "$fail" -gt 0 ]; then
    echo "⛔ 버전 선언 ${fail}건 불일치 — 세 곳을 함께 올린다"
    echo "   우회(정당 사유 시): git commit --no-verify"
    exit 1
  fi
  echo "STAGED_OK (버전 3곳 일치)"
  exit 0
fi

# ── --neutralize-diff — ⑦만 ─────────────────────────────────────────────────
if [ "$MODE" = "neutralize" ]; then
  neutralize_axis "$ROOT_DIR" "$NREF" "$NRULES"; rc=$?
  case "$rc" in
    0) echo "NEUTRALIZE_OK ($NREF 대비 추가 줄 적중 0)" ;;
    1) echo "⛔ 중립화 규칙 적중 — 공개 저장소에 두기 전에 중립 표기로 바꾼다" ;;
  esac
  exit "$rc"
fi

for f in .claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md \
         guides/skill-authoring.md guides/model-guide.md scripts/health-check.sh; do
  [ -f "$f" ] || { echo "❌ 대상 부재: $f (측정 실패)"; exit 2; }
done

PV=$(python3 -c 'import json;print(json.load(open(".claude-plugin/plugin.json"))["version"])' 2>/dev/null)
MV=$(python3 -c 'import json,sys;d=json.load(open(".claude-plugin/marketplace.json"));p=d["plugins"][0] if isinstance(d.get("plugins"),list) and d["plugins"] else d;print(p.get("version",""))' 2>/dev/null)
CV=$(grep -m1 -oE '^### v[0-9]+\.[0-9]+\.[0-9]+' CHANGELOG.md | sed 's/^### v//')
[ -n "$PV" ] || { echo "❌ plugin.json version 을 읽지 못했다 (측정 실패)"; exit 2; }
[ -n "$CV" ] || { echo "❌ CHANGELOG 최상단 버전 헤딩을 찾지 못했다 (측정 실패)"; exit 2; }

echo "버전: plugin=$PV · marketplace=$MV · CHANGELOG=$CV"
[ "$PV" = "$MV" ] || note "plugin.json($PV) ≠ marketplace.json($MV)"
[ "$PV" = "$CV" ] || note "plugin.json($PV) ≠ CHANGELOG 최상단($CV) — 항목 없이 버전만 올리거나 그 반대"
subplugin_axis "$ROOT_DIR" || { rc=$?; [ "$rc" = 2 ] && note "하위 플러그인 미판정 — 통과가 아니다" || fail=$((fail + 1)); }
note_ref_axis "$ROOT_DIR" || { rc=$?; [ "$rc" = 2 ] && note "노트 절 참조 미판정 — 통과가 아니다" || fail=$((fail + 1)); }
mode_axis "$ROOT_DIR" || { rc=$?; [ "$rc" = 2 ] && note "모드 축 미판정 — 통과가 아니다" || fail=$((fail + 1)); }

# ③ sweep 결과가 어디로 가는지 가이드가 가리키는가 — 사전등록만 하고 참조가 없으면 표가 미아가 된다
grep -q '§5.8 ⑥' guides/skill-authoring.md || note "skill-authoring.md 가 sweep 기록 위치(§5.8 ⑥)를 가리키지 않는다"
grep -q '§5.8 ⑥' guides/model-guide.md || note "model-guide.md 가 sweep 기록 위치(§5.8 ⑥)를 가리키지 않는다"
grep -q '### ⑥ 세션 effort sweep' experiment-log.md || note "experiment-log.md 에 §5.8 ⑥ 표가 없다 (가이드가 없는 곳을 가리킨다)"
grep -q '## §5.9 구조 ablation' experiment-log.md || note "experiment-log.md 에 §5.9 표가 없다"

# ③-b 최상단 절의 finding 표 — 표가 있으면 모든 행의 판정·근거·검증 절차가 차 있어야 한다(없는 릴리즈는 통과)
python3 scripts/check_release_notes.py --table-complete --version "$CV" >/tmp/fz-release-notes.log 2>&1 \
  || note "CHANGELOG v$CV finding 표에 빈 칸이 있다 (로그: /tmp/fz-release-notes.log)"

# ④ health-check — 이번 변경이 기존 계약을 깨지 않았는가
if bash scripts/health-check.sh >/tmp/fz-release-hc.log 2>&1; then
  echo "  ✅ health-check exit 0"
else
  note "health-check 실패 (로그: /tmp/fz-release-hc.log)"
fi

# ⑤ 커밋 축 — `--release` 에서만. 미판정(2)은 통과로 세지 않는다
if [ "$MODE" = "release" ]; then
  commit_axis "$ROOT_DIR" "$PV" || { rc=$?; [ "$rc" = 2 ] && note "커밋 축 미판정 — 통과가 아니다" || fail=$((fail + 1)); }
fi
# ⑦ 중립화 축 — `--release` 에서만, 직전 태그 대비. 태그가 없으면 미판정이다(릴리스는 직전 출하와 대조한다)
if [ "$MODE" = "release" ]; then
  LTAG="$(git -C "$ROOT_DIR" describe --tags --abbrev=0 --match 'v*' 2>/dev/null)"
  if [ -z "$LTAG" ]; then note "중립화 축 미판정 — v* 태그가 없다(통과가 아니다)"
  else neutralize_axis "$ROOT_DIR" "$LTAG" "$NRULES" || { rc=$?; [ "$rc" = 2 ] && note "중립화 축 미판정 — 통과가 아니다" || fail=$((fail + 1)); }; fi
fi
# ⑥ findings 축 — `--release` 에서만. 미판정(2)은 통과로 세지 않는다
if [ "$MODE" = "release" ]; then
  findings_axis "$ROOT_DIR/docs/releases/v${PV}.md" || { rc=$?; [ "$rc" = 2 ] && note "findings 축 미판정 — 통과가 아니다" || fail=$((fail + 1)); }
fi

if [ "$fail" -gt 0 ]; then
  echo "릴리즈 동기 불일치 ${fail}건"
  exit 1
fi
if [ "$MODE" = "release" ]; then
  echo "RELEASE_SYNC_OK (버전 3곳 일치 · 가이드→표 참조 4건 · 노트 절 참조 · 모드 변경 0 · health-check exit 0 · 커밋 축 · 중립화 · findings 선언 있음 — applied ↔ Closes 대조는 check_release_closes.py)"
else
  echo "DOCS_SYNC_OK (버전 3곳 일치 · 가이드→표 참조 4건 · 노트 절 참조 · 모드 변경 0 · health-check exit 0)"
fi
