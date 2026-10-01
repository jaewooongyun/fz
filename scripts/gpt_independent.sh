#!/bin/bash
# GPT 독립 첫 패스 런처 (S13) — plan | review. 허용 입력만 격리 폴더에 복사하고, 강제 격리 아래에서 GPT 역할 스킬로 첫 패스를 돌린다.
#
# ⛔ 왜: Claude 워크플로가 병렬로 도는 동안 런타임이 ~/.claude/projects 에 로그를 쓰고, 작업 폴더에는 Claude 산출물이 쌓인다.
#    시간 격리는 성립하지 않는다. 읽기 로그로 "안 읽었다"를 증명할 수도 없다(S11 ⑥ 반례 — `sh show.sh` 는 읽는 대상이 명령에 없다).
#    그래서 읽기 자체를 OS 수준에서 막는다(S11 ⑦ · ⑨ · ⑩):
#      격리 CODEX_HOME(인증 링크 · gpt-skills **사본** · 권한 프로필 · memories 끔) + 가짜 HOME(사용자 전역 스킬 폴더 차단)
#      + 래퍼 --config-permissions(sandbox_mode 가 프로필을 덮지 않게 · F-348)
#    rollout 감사는 격리가 실제로 걸렸는지와 시도를 보는 보조 확인이다.
#
# usage:
#   gpt_independent.sh plan   --requirement F [--sprint-contract F] [--rules-index F] [--snapshot D]... [--repo D] [--deny D]...
#                             --arm A --run-id ID --out-dir D [--timeout S] [--effort E] [--keep-iso]
#   gpt_independent.sh review --diff F [--pr-meta F] [--requirement F] [--rules-index F] [--base D] [--head D] [--snapshot D]...
#                             [--repo D] [--deny D]... [--gpt-agents] --arm A --run-id ID --out-dir D [--timeout S] [--effort E] [--keep-iso]
#   gpt_independent.sh cleanup --iso D   --keep-iso 로 남긴 격리 폴더를 지운다(resume 교차 뒤). 이름 fz-gpt-iso.XXXXXX · gpt-home/ 가 맞을 때만
#   --gpt-agents review 전용 — 역할 파일(gpt-agents/*.toml)을 격리 홈 agents/ 에 넣고 두 렌즈 역할(fz-review-arch · fz-review-quality)만
#             spawn 하게 한다(S14 · opt-in). 없으면 하위 에이전트 금지. 하위 에이전트는 부모 이력을 물려받는다 — 격리된 부모 안이라 독립이 유지된다
#   --repo    대상 저장소 — 복사하지 않고 권한 프로필 read 로 연다. 그 안의 .claude · .fz-work 는 막는다
#   --deny    더 막을 폴더(작업 폴더 WORK_DIR 등) — --repo 와 무관하게 권한 프로필 deny 로 넣는다. 권한 프로필은 디스크 전체 읽기에서
#             HOME · 임시 폴더만 막으므로, HOME 밖 작업 폴더의 Claude 산출은 --deny 가 없으면 읽힌다
#   --rules-index 지침 원문 색인(extract_project_rules.py 출력 — files · sections). ⛔ 규칙 레코드(rules · axes — Claude 가 해석한
#             check_project_rules 통과본)를 넘기면 독립이 깨진다 — 모양으로 판별해 exit 11
#   --snapshot 소비자 · 공유 모듈 본문 폴더 — 격리 폴더의 snapshot/<이름>/ 으로 복사한다(리뷰 범위를 줄이지 않는다)
#
# 산출(out-dir): <arm>-<run-id>.json (스키마 출력) · .md (사람용) · .audit.json · .rollouts/ (세션 로그 사본) · .contaminated (오염 시) · .json.session(세션 ID — 감사 sessionFile · --keep-iso 면 감사 iso · resume 입력)
#   ⛔ 시작할 때 같은 stem 의 옛 산출을 지우고 감사를 'running'(exit null)으로 먼저 쓴다 — 중간에 멈춘 run 의 산출은 병합 · 차이표가 거부한다
# exit: 0=성공 · 10=사용법 · 같은 --out 동시 실행 · 11=사전조건 · 12~14=래퍼 측정 실패 그대로(14 는 6축 후검사도)
#       15=오염 — 금지 입력 · 격리 미적용 · rollout 감사 적중 · 16=시간 초과(프로세스 그룹째 종료) · 17=planner 가 status=rejected
#   ⛔ 10~17 은 전부 첫 패스 결과가 아니다 — 0건으로 읽지 않는다.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# diff-parse: hunk-state — review 감사의 head 결손 표시는 diff_anchors.py 로 경로를 풀고 `diff --git` 블록마다 `@@` 전 헤더 구간만 본다
# fz 고유 산출물 이름(경로 성분 전체 일치) — 입력 가드 · base/head 미러 · 스냅샷 · rollout 감사가 이 표 하나를 쓴다(두 목록이 어긋나던 결함).
#   ⛔ 범용 이름(payload.json · *-result.json)은 여기 넣지 않는다 — 저장소 파일에 흔하다. 직접 입력에만 따로 댄다(GUARD)
FZ_ART_NAMES='code-context\.md|plan-v[0-9][^/]*\.md|plan-final[^/]*\.md|workflow-result[^/]*\.json|review-report\.md|pr-comments\.md|self-review\.md|triage\.md|render-preview\.json'

die() { echo "INDEPENDENT-FAIL($1): $2" >&2; exit "$1"; }
need() { [ "$1" -ge 2 ] || die 10 "$2 는 값이 필요하다"; }

MODE="${1:-}"; shift || true
# 격리 폴더 정리 — --keep-iso 로 남긴 폴더를 resume 교차가 끝난 뒤 지운다(modules/fz-gpt-subcommands-core.md § resume 교차).
#   ⛔ Lead 명령줄의 `rm -rf "$ISO"` 는 자동 모드 안전 검사가 거부한다(R-C 측정 실측) — 지우기는 런처가 맡고 대상을 확인한다:
#      이름이 이 런처의 mktemp 형식(fz-gpt-iso.XXXXXX)이고 격리 홈(gpt-home/)이 있어야 한다. 아니면 아무것도 지우지 않는다.
if [ "$MODE" = "cleanup" ]; then
  [ "${1:-}" = "--iso" ] && [ -n "${2:-}" ] || die 10 "cleanup 은 --iso D 가 필요하다"
  D="$(cd "$2" 2>/dev/null && pwd -P)" || die 11 "격리 폴더가 없다: $2"
  case "${D##*/}" in fz-gpt-iso.??????) ;; *) die 10 "이 런처가 만든 격리 폴더가 아니다: $D" ;; esac
  [ -d "$D/gpt-home" ] || die 10 "격리 홈(gpt-home/)이 없다 — 격리 폴더가 아니다: $D"
  rm -rf "$D" || die 11 "격리 폴더 삭제 실패: $D"
  echo "INDEPENDENT-CLEANUP: $D"
  exit 0
fi
case "$MODE" in
  plan) ROLE=planner ;;
  review) ROLE=reviewer ;;
  *) die 10 "mode 는 plan|review|cleanup — 받은 값: '${MODE}'" ;;
esac

ARM="" RUN_ID="" OUT_DIR="" TIMEOUT=1800 EFFORT="" REQ="" SC="" RULES="" DIFF="" META="" BASE_DIR="" HEAD_DIR="" REPO="" KEEP_ISO="" GPT_AGENTS=""
SNAPS=() DENIES=()
while [ $# -gt 0 ]; do
  case "$1" in
    --arm)             need $# "--arm";             ARM="$2"; shift 2 ;;
    --run-id)          need $# "--run-id";          RUN_ID="$2"; shift 2 ;;
    --out-dir)         need $# "--out-dir";         OUT_DIR="$2"; shift 2 ;;
    --timeout)         need $# "--timeout";         TIMEOUT="$2"; shift 2 ;;
    --effort)          need $# "--effort";          EFFORT="$2"; shift 2 ;;
    --requirement)     need $# "--requirement";     REQ="$2"; shift 2 ;;
    --sprint-contract) need $# "--sprint-contract"; SC="$2"; shift 2 ;;
    --rules-index)     need $# "--rules-index";     RULES="$2"; shift 2 ;;
    --diff)            need $# "--diff";            DIFF="$2"; shift 2 ;;
    --pr-meta)         need $# "--pr-meta";         META="$2"; shift 2 ;;
    --base)            need $# "--base";            BASE_DIR="$2"; shift 2 ;;
    --head)            need $# "--head";            HEAD_DIR="$2"; shift 2 ;;
    --snapshot)        need $# "--snapshot";        SNAPS+=("$2"); shift 2 ;;
    --repo)            need $# "--repo";            REPO="$2"; shift 2 ;;
    --deny)            need $# "--deny";            DENIES+=("$2"); shift 2 ;;
    --keep-iso)        KEEP_ISO=1; shift ;;
    --gpt-agents)      GPT_AGENTS=1; shift ;;
    *) die 10 "알 수 없는 인자: $1" ;;
  esac
done

# ── 사전 게이트: 사용법
printf '%s' "$ARM" | grep -qE '^[A-Za-z0-9._-]+$' || die 10 "--arm 은 [A-Za-z0-9._-]+ — 받은 값: '$ARM'"
printf '%s' "$RUN_ID" | grep -qE '^[A-Za-z0-9._-]+$' || die 10 "--run-id 는 [A-Za-z0-9._-]+ — 받은 값: '$RUN_ID'"
[ -n "$OUT_DIR" ] || die 10 "--out-dir 필수"
printf '%s' "$TIMEOUT" | grep -qE '^[1-9][0-9]*$' || die 10 "--timeout 은 양의 정수(초) — 받은 값: '$TIMEOUT'"
if [ "$MODE" = "plan" ]; then
  [ -n "$REQ" ] || die 10 "plan 은 --requirement 필수"
  [ -z "$DIFF$META$BASE_DIR$HEAD_DIR" ] || die 10 "plan 은 --diff · --pr-meta · --base · --head 를 받지 않는다"
  EFFORT="${EFFORT:-xhigh}"
else
  [ -n "$DIFF" ] || die 10 "review 는 --diff 필수"
  [ -z "$SC" ] || die 10 "review 는 --sprint-contract 를 받지 않는다"
  EFFORT="${EFFORT:-high}"
fi
[ -z "$GPT_AGENTS" ] || [ "$MODE" = "review" ] || die 10 "--gpt-agents 는 review 전용이다(역할 파일은 리뷰 렌즈다)"

# ── 사전 게이트: 입력 실재 · 금지 입력(⛔ exit 15 — Claude 산출물이 첫 패스에 들어가면 독립이 아니다)
REAL_HOME="$(cd "${HOME:?HOME 미설정}" && pwd -P)"
REAL_GPT_HOME="$(cd "${CODEX_HOME:-$REAL_HOME/.codex}" 2>/dev/null && pwd -P)" || die 11 "실제 GPT CLI 홈이 없다: ${CODEX_HOME:-$REAL_HOME/.codex}"
[ -f "$REAL_GPT_HOME/auth.json" ] || die 11 "인증 파일이 없다: $REAL_GPT_HOME/auth.json (로그인 필요)"
for f in "$REQ" "$SC" "$RULES" "$DIFF" "$META"; do [ -z "$f" ] || [ -s "$f" ] || die 11 "입력 파일 없음/빈 파일: $f"; done
for d in "$BASE_DIR" "$HEAD_DIR" "$REPO" "${SNAPS[@]+"${SNAPS[@]}"}" "${DENIES[@]+"${DENIES[@]}"}"; do [ -z "$d" ] || [ -d "$d" ] || die 11 "입력 폴더 없음: $d"; done
GUARD="$(FZ_ART_NAMES="$FZ_ART_NAMES" python3 - "$REAL_HOME" "$REQ" "$SC" "$RULES" "$DIFF" "$META" -- "$BASE_DIR" "$HEAD_DIR" "${SNAPS[@]+"${SNAPS[@]}"}" -- "$REPO" <<'PY'
import os, re, sys
home, argv = sys.argv[1], sys.argv[2:]
a = argv.index("--"); b = argv.index("--", a + 1)
files, dirs, repo = [x for x in argv[:a] if x], [x for x in argv[a + 1:b] if x], [x for x in argv[b + 1:] if x]
FZ = re.compile(os.environ["FZ_ART_NAMES"])                 # fz 고유 이름 — 어디서든 금지
GENERIC = re.compile(r"payload\.json|.+-result\.json")      # 범용 이름 — 직접 입력에만(base/head 미러 · 스냅샷은 저장소 파일이다)
claude = os.path.join(home, ".claude")
hits = []
def check(p, names):
    rp = os.path.realpath(p)
    if rp == claude or rp.startswith(claude + os.sep):
        hits.append(f"{p} — ~/.claude 아래(에이전트 로그 · journal)")
    elif any(r.fullmatch(os.path.basename(rp)) for r in names):
        hits.append(f"{p} — Claude 산출물 이름")
for f in files:
    check(f, (FZ, GENERIC))
for d in dirs:
    check(d, ())
    for root, _, names in os.walk(d):
        for n in names:
            check(os.path.join(root, n), (FZ,))
for r in repo:
    check(r, ())
print("\n".join(hits))
PY
)" || die 11 "입력 판정 실패"
[ -z "$GUARD" ] || die 15 "허용 목록 밖 입력 — 독립 첫 패스가 아니다:
$GUARD"
# ⛔ --rules-index 는 원문 색인이다 — 규칙 레코드(Claude 의 해석)를 넘기면 GPT 가 그 해석을 원문으로 알고 받아쓴다(독립 붕괴 · 리뷰 C:C-1)
if [ -n "$RULES" ] && python3 -c 'import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
sys.exit(0 if isinstance(d, dict) and "rules" in d and "sections" not in d else 1)' "$RULES" 2>/dev/null; then
  die 11 "--rules-index 에 규칙 레코드(rules · axes — Claude 가 해석한 통과본)를 넘겼다. 지침 원문 색인(extract_project_rules.py 의 files · sections)을 넘긴다"
fi

# ── 같은 --out 동시 실행 거부 (mkdir 는 원자적이다)
mkdir -p "$OUT_DIR" || die 11 "--out-dir 생성 실패: $OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd -P)"
BASE_NAME="${ARM}-${RUN_ID}"
OUT="$OUT_DIR/$BASE_NAME.json"
mkdir "$OUT.lock" 2>/dev/null || die 10 "같은 --out 이 이미 실행 중이다(또는 전 실행의 잠금이 남았다): $OUT.lock"
ISO=""
# ⛔ 지우기 전에 이름을 확인한다 — 격리 폴더 경로가 잘못 풀리면(빈 mktemp 결과 · bash 3.2 의 `cd ""` 는 성공한다) 현재 폴더를 지운다
cleanup() { rm -rf "$OUT.lock"; [ -n "$ISO" ] && [ -z "$KEEP_ISO" ] && case "${ISO##*/}" in fz-gpt-iso.??????) rm -rf "$ISO" ;; esac; }
trap cleanup EXIT

# ── 같은 stem 의 옛 산출 정리 + 감사 선기록 — 다시 돌린 run 이 옛 `.contaminated` 로 거부되거나, 옛 성공 감사가 새 미감사 출력을 보증하지 않게.
#    ⛔ 지울 파일은 명시 목록이다(글롭 금지). 감사는 'running'(exit null)으로 먼저 쓰고 끝에 덮는다 — 중간에 멈춘 run 은 병합 · 차이표가 거부한다
rm -f "$OUT" "$OUT.session" "$OUT.stream.log" "$OUT_DIR/$BASE_NAME.md" "$OUT_DIR/$BASE_NAME.audit.json" \
  "$OUT_DIR/$BASE_NAME.contaminated" "$OUT_DIR/$BASE_NAME.wrapper.log"
printf '{"exit": null, "note": "running — 감사가 끝나기 전에 런처가 멈췄다(중단 · 시그널 · 감사 실패). 결과가 아니다"}\n' > "$OUT_DIR/$BASE_NAME.audit.json"

# ── 격리 폴더 — ⛔ 경로는 전부 realpath(`/tmp`→`/private/tmp` · `/var/folders`→`/private/var/folders`). deny·read 표기가 어긋나면 중첩 규칙이 안 맞는다
#    ⛔ mktemp 결과를 따로 받는다 — `cd "$(mktemp …)"` 꼴은 mktemp 가 실패해도 `cd ""` 가 성공해 현재 폴더가 격리 폴더가 된다(bash 3.2 실측)
ISO_TMP="$(mktemp -d "${TMPDIR:-/tmp}/fz-gpt-iso.XXXXXX")" || die 11 "격리 폴더 생성 실패(mktemp)"
ISO="$(cd "$ISO_TMP" && pwd -P)" || die 11 "격리 폴더 경로 해석 실패: $ISO_TMP"
mkdir -p "$ISO/gpt-home/skills" "$ISO/home" "$ISO/input" || die 11 "격리 폴더 구성 실패"
ln -s "$REAL_GPT_HOME/auth.json" "$ISO/gpt-home/auth.json" || die 11 "인증 링크 실패"   # ⛔ 인증은 링크만 — 내용을 복사하지 않는다
for s in "$PLUGIN_ROOT"/gpt-skills/fz-*; do cp -R "$s" "$ISO/gpt-home/skills/" || die 11 "스킬 사본 실패: $s"; done
if [ -n "$GPT_AGENTS" ]; then
  mkdir -p "$ISO/gpt-home/agents" && cp "$PLUGIN_ROOT"/gpt-agents/*.toml "$ISO/gpt-home/agents/" || die 11 "역할 파일 사본 실패: $PLUGIN_ROOT/gpt-agents"
fi   # ⛔ 사본 — HOME 아래 링크 대상은 샌드박스에서 안 읽힌다
put() { [ -z "$1" ] || cp "$1" "$ISO/input/$2" || die 11 "입력 복사 실패: $1"; }
put_dir() { [ -z "$1" ] || { mkdir -p "$ISO/input/$2" && cp -R "$1"/. "$ISO/input/$2/"; } || die 11 "입력 폴더 복사 실패: $1"; }
put "$REQ" requirement.md; put "$SC" sprint-contract.md; put "$RULES" rules-index.json; put "$DIFF" diff.patch; put "$META" pr-meta.json
put_dir "$BASE_DIR" base; put_dir "$HEAD_DIR" head
for d in "${SNAPS[@]+"${SNAPS[@]}"}"; do put_dir "$d" "snapshot/$(basename "$d")"; done
REPO_REAL=""; [ -n "$REPO" ] && REPO_REAL="$(cd "$REPO" && pwd -P)"
CD="$ISO/input"; [ "$MODE" = "plan" ] && [ -n "$REPO_REAL" ] && CD="$REPO_REAL"

python3 - "$ISO" "$REAL_HOME" "$REAL_GPT_HOME/config.toml" "$REPO_REAL" "$CD" "${DENIES[@]+"${DENIES[@]}"}" <<'PY' || die 11 "격리 config 작성 실패"
import json, os, re, sys
iso, home, real_cfg, repo, cd, denies = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6:]
q = lambda p: json.dumps(p)          # TOML basic string — JSON 이스케이프와 호환
model = ""
try:
    head = re.split(r"(?m)^\s*\[", open(real_cfg, encoding="utf-8").read(), maxsplit=1)[0]
    m = re.search(r'(?m)^model\s*=\s*"[^"\n]*"\s*$', head)   # ⛔ model 한 줄만 — MCP env 등 다른 줄은 옮기지 않는다
    model = m.group(0) if m else ""
except OSError:
    pass
fs = [(home, "deny")]
for p in ("/private/tmp", "/private/var/folders"):
    if os.path.isdir(p):
        fs.append((os.path.realpath(p), "deny"))
fs.append((iso, "read"))
if repo:
    fs.append((repo, "read"))
    for sub in (".claude", ".fz-work"):
        if os.path.isdir(os.path.join(repo, sub)):
            fs.append((os.path.join(repo, sub), "deny"))
for d in denies:   # ⛔ --repo 와 무관 — 프로필은 디스크 전체 읽기에서 출발해 HOME 밖 작업 폴더는 이것이 없으면 읽힌다
    fs.append((os.path.realpath(d), "deny"))
lines = ['default_permissions = "fz-iso"']
if model:
    lines.append(model)
lines += ["", "[features]", "memories = false", "", "[permissions.fz-iso]", 'extends = ":read-only"', "", "[permissions.fz-iso.filesystem]"]
lines += [f"{q(p)} = {q(a)}" for p, a in fs]
lines += ["", f"[projects.{q(cd)}]", 'trust_level = "trusted"', ""]
open(os.path.join(iso, "gpt-home", "config.toml"), "w", encoding="utf-8").write("\n".join(lines))
PY

# ── 과제 프롬프트 — 역할 본문은 래퍼 --inject-skill 이 넣는다(격리 사본 경로 → 팩 경로가 풀린다)
{
  echo "[독립 첫 패스 — $MODE] 다른 모델과 독립으로 수행한다. 다른 모델의 계획 · 리뷰 · 중간 산출물을 찾거나 읽지 않는다."
  if [ -n "$GPT_AGENTS" ]; then
    echo "하위 에이전트는 역할 두 개만 만든다 — agent_type \`fz-review-arch\`(아키텍처 렌즈) · \`fz-review-quality\`(품질 렌즈). 각 렌즈에 diff 와 네가 만든 규칙 레코드를 넘기고, 두 결과를 합쳐 스키마 JSON 하나로 낸다. 다른 하위 에이전트는 만들지 않는다."
  else
    echo "하위 에이전트를 만들지 않는다."
  fi
  echo "읽기는 권한 프로필로 제한돼 있다 — 막힌 경로를 우회하려 하지 않는다."
  echo
  echo "## 입력 (격리 입력 폴더 $ISO/input)"
  [ -n "$REQ" ] && echo "- requirement.md — 요구사항 원문"
  [ -n "$SC" ] && echo "- sprint-contract.md — 합의된 Sprint Contract"
  [ -n "$RULES" ] && echo "- rules-index.json — 지침 파일 원문 색인(해석 없음). 규칙 레코드는 직접 만든다(Project Rules 절)"
  [ -n "$DIFF" ] && echo "- diff.patch — 리뷰 대상 diff"
  [ -n "$META" ] && echo "- pr-meta.json — PR 메타"
  [ -n "$BASE_DIR" ] && echo "- base/ — 변경 전 원본(저장소 상대 경로 그대로)"
  [ -n "$HEAD_DIR" ] && echo "- head/ — 변경 후 원본(저장소 상대 경로 그대로)"
  for d in "${SNAPS[@]+"${SNAPS[@]}"}"; do echo "- snapshot/$(basename "$d")/ — 소비자 · 공유 모듈 본문"; done
  if [ -n "$REPO_REAL" ]; then echo; echo "## 저장소"; echo "$REPO_REAL — 읽기 전용"; fi
  echo
  if [ "$MODE" = "plan" ]; then
    echo "## 출력"; echo "스키마의 JSON 한 객체(fz-planner 출력 형식)."
    echo; echo "## 요구사항"; cat "$REQ"
  else
    echo "## 출력"
    echo "스키마의 JSON 한 객체 — 결함은 issues, 솜씨 항목은 craft, 6축마다 axis_coverage 한 행. 파일 경로는 저장소 상대 경로로 쓴다(head/ 접두 없이)."
    echo "issues 와 craft 의 evidence 에는 diff 에 있는 코드 원문을 백틱으로 인용한다 — 병합이 그 인용을 diff 에서 다시 찾지 못하면 게시하지 않는다."
  fi
} > "$ISO/prompt.txt"

# ── 실행 — ⛔ 래퍼를 새 프로세스 그룹에서 띄운다. 시간 초과면 그룹째 죽인다(래퍼만 죽이면 그 아래 CLI 가 고아로 남아 세션을 계속 쓴다)
TEL="${FZ_TELEMETRY_DIR:-$REAL_HOME/.fz/telemetry}"   # ⛔ 가짜 HOME 이면 래퍼 기본값이 달라져 행이 조용히 사라진다 — 명시로 넘긴다
SCHEMA="$PLUGIN_ROOT/schemas/gpt_independent_${MODE}_schema.json"
perl -e 'setpgrp(0, 0); exec @ARGV' env HOME="$ISO/home" CODEX_HOME="$ISO/gpt-home" FZ_TELEMETRY_DIR="$TEL" \
  bash "$SCRIPT_DIR/gpt-exec.sh" exec --cd "$CD" --out "$OUT" --prompt-file "$ISO/prompt.txt" --schema "$SCHEMA" \
  --effort "$EFFORT" --gpt-skill "$ROLE" --inject-skill "$ISO/gpt-home/skills/fz-$ROLE/SKILL.md" --config-permissions \
  > "$OUT_DIR/$BASE_NAME.wrapper.log" 2>&1 &
WPID=$!
# 감시자 — ⛔ 자기 sleep 을 trap 으로 정리한다(서브셸만 죽이면 `sleep $TIMEOUT` 이 고아로 남는다 — 정상 run 마다 30분짜리 프로세스).
#    ⛔ 시간 초과면 본문이 감시자를 죽이지 않고 KILL 까지 기다린다 — TERM 을 무시한 자손이 격리 폴더를 지운 뒤에도 남지 않게
( trap 'kill "$SP" 2>/dev/null; exit 0' TERM; sleep "$TIMEOUT" & SP=$!; wait "$SP"
  touch "$ISO/.timed-out"; kill -TERM -- "-$WPID" 2>/dev/null; sleep 3; kill -KILL -- "-$WPID" 2>/dev/null ) >/dev/null 2>&1 &
TPID=$!
wait "$WPID"; RC=$?
if [ -f "$ISO/.timed-out" ]; then wait "$TPID" 2>/dev/null
else kill "$TPID" 2>/dev/null; wait "$TPID" 2>/dev/null; fi
TIMED_OUT=0; [ -f "$ISO/.timed-out" ] && TIMED_OUT=1

# ── 감사 · 후검사 · 렌더 — rollout 은 세션 폴더의 jsonl **전부**(spawn 을 못 끈다 — S11 ⑤)
rm -rf "$OUT_DIR/$BASE_NAME.rollouts"; mkdir -p "$OUT_DIR/$BASE_NAME.rollouts"
find "$ISO/gpt-home/sessions" -name '*.jsonl' -exec cp {} "$OUT_DIR/$BASE_NAME.rollouts/" \; 2>/dev/null
FZ_ART_NAMES="$FZ_ART_NAMES" python3 - "$MODE" "$OUT" "$OUT_DIR/$BASE_NAME" "$REAL_HOME" "$REPO_REAL" "$ISO" "$RC" "$TIMED_OUT" "$SCHEMA" "$KEEP_ISO" "$PLUGIN_ROOT" <<'PY'
import glob, hashlib, importlib.util, json, os, re, sys
mode, out, stem, home, repo, iso, rc, timed_out, schema_p = sys.argv[1:10]
keep = sys.argv[10:11] == ["1"]   # --keep-iso — 격리 홈이 남아야 resume 이 세션을 잇는다
plugin_root = sys.argv[11]
# ⛔ 입력 해시는 격리 사본에서 잰다 — GPT 가 실제로 본 내용이다(읽기 전용 프로필이라 실행 중에 바뀌지 않는다). 병합이 stale 을 가린다
inputs = {n: hashlib.sha256(open(os.path.join(iso, "input", n), "rb").read()).hexdigest()
          for n in ("diff.patch", "requirement.md", "sprint-contract.md", "rules-index.json", "pr-meta.json")
          if os.path.isfile(os.path.join(iso, "input", n))}
rc, timed_out = int(rc), timed_out == "1"
# head/ 결손 표시(fail-visible) — diff 의 변경 후 경로가 head/ 미러에 있는가. 삭제만 있는 PR 은 head/ 가 정당하게 빈다.
#   ⛔ 경로는 diff_anchors.py 로 푼다(git 따옴표 8진 · 탭 꼬리 · a/ b/ — 여기서 다시 짜지 않는다). `diff --git` 블록마다 `@@` 전 헤더만 본다 —
#      hunk 안의 `+++ x` 는 `++ x` 를 더한 소스 행이다. 순수 rename(`rename to`) · 바이너리(`Binary files … differ`)는 ---/+++ 가 없어 따로 잡는다.
#      풀지 못하면 감사를 죽이지 않고 head 에 error 를 적는다(결과 판정이 아니라 표시다)
head = None
hdir, dpath = os.path.join(iso, "input", "head"), os.path.join(iso, "input", "diff.patch")
if mode == "review" and os.path.isdir(hdir) and os.path.isfile(dpath):
    try:
        spec = importlib.util.spec_from_file_location("diff_anchors", os.path.join(plugin_root, "skills", "fz-peer-review", "scripts", "diff_anchors.py"))
        da = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(da)
        side = lambda raw: da.strip_prefix(da.unquote_path(raw))
        post, blk = set(), None
        def close(b):
            if b and not b["gone"]:
                p = b["post"] or b["same"]
                if p:
                    post.add(p)
        for line in open(dpath, encoding="utf-8", errors="replace").read().splitlines():
            if line.startswith("diff --git "):
                close(blk)
                rest = line[len("diff --git "):]
                n = (len(rest) - 5) // 2      # 따옴표 없는 같은 경로 쌍 `a/X b/X` — 모드만 바뀐 파일의 경로
                blk = {"post": None, "gone": False, "hdr": True,
                       "same": rest[2:2 + n] if n > 0 and rest == f"a/{rest[2:2 + n]} b/{rest[2:2 + n]}" else None}
                continue
            if not blk or not blk["hdr"]:
                continue
            if line.startswith("@@"):
                blk["hdr"] = False
            elif line.startswith("deleted file mode"):
                blk["gone"] = True
            elif line.startswith(("rename to ", "copy to ")):
                blk["post"] = da.unquote_path(line.split(" to ", 1)[1])
            elif line.startswith("+++ "):
                p = side(line[4:])
                blk["gone"], blk["post"] = (True, None) if p == "/dev/null" else (blk["gone"], p)
            elif line.startswith("Binary files ") and line.endswith(" differ"):
                m = re.match(r"Binary files (.+) and (.+) differ$", line)
                p = side(m.group(2)) if m else None
                blk["gone"], blk["post"] = (True, None) if p == "/dev/null" else (blk["gone"], p or blk["post"])
                blk["hdr"] = False
        close(blk)
        post = sorted(post)
        miss = [p for p in post if not os.path.isfile(os.path.join(hdir, p))]
        head = {"expected": len(post), "present": len(post) - len(miss), "missing": miss[:20]}
    except Exception as e:   # ⛔ 표시용 — 감사 판정을 막지 않는다
        head = {"expected": None, "error": f"{type(e).__name__}: {e}"}
rolls = sorted(glob.glob(os.path.join(stem + ".rollouts", "*.jsonl")))
ROOTS = r"(~|\$HOME|/Users(?:/[^\s'\"]*)?|/)(?=[\s'\";|&)]|$)"
FZ_ART = re.compile(os.environ["FZ_ART_NAMES"])
def forbid_hit(cmd):
    """Claude 산출물 참조 — `.claude/` 경로 또는 fz 고유 산출물 이름(경로 성분 전체 일치 · 입력 가드와 같은 표).
    ⛔ 부분 문자열로 보지 않는다 — `code-context-builder.swift` · `ci/test-result.json` · 검색 패턴 'workflow-result' 는 산출물이 아니다.
       범용 이름(payload.json · *-result.json)은 저장소 파일에 흔해 보지 않는다 — 작업 폴더는 --deny 가 OS 수준에서 막는다
    ⛔ 따옴표 · 이스케이프를 먼저 걷는다 — rollout 의 명령은 JSON 문자열 안에 있어 `"…"` 가 `\\"…\\"` 로 남고(이름 끝에 `\\` 가 붙는다),
       셸은 이어 붙은 따옴표 조각을 한 단어로 읽는다(`code-context".md"`). 걷은 뒤 경로 · JSON 구분자로 자른다(역검증 ISSUE-001)"""
    flat = re.sub(r"[\\'\"`]", "", cmd)
    return ".claude/" in flat or any(FZ_ART.fullmatch(t) for t in re.findall(r"[^\s/;|&()<>=,{}\[\]:]+", flat))
FIND_ROOT = re.compile(rf"\bfind\s+{ROOTS}")                      # find 는 첫 인자가 검색 뿌리다
MULTI_HEADS = [re.compile(r"\b(?:rg|fd|ag)\b"), re.compile(r"\bgrep\s+-[a-zA-Z]*[rR][a-zA-Z]*\b"),
               re.compile(r"\bls\s+-[a-zA-Z]*R[a-zA-Z]*\b")]
ROOT_ARG = re.compile(rf"\s{ROOTS}")
def under_allowed(p):
    """허용된 저장소(--repo) · 격리 폴더 하위 — home_ref 와 같은 기준."""
    p = os.path.normpath(p) if p.startswith("/") else p   # `<repo>/../..` 로 허용 범위를 벗어나지 못하게
    return bool((repo and (p == repo or p.startswith(repo + "/"))) or p == iso or p.startswith(iso + "/"))
def recurse_hit(cmd):
    """홈 · 루트 재귀 검색 — 뿌리가 허용된 저장소 · 격리 폴더 하위면 적중이 아니다.
    ⛔ macOS 저장소는 거의 전부 /Users 아래라 예외가 없으면 GPT 가 저장소를 절대 경로로 검색하기만 해도 첫 패스가 버려진다(S27 실측).
    ⛔ 조각(| ; & 줄바꿈 사이) 안의 뿌리 인자를 **전부** 본다 — 탐욕 접두는 마지막 뿌리만 잡아 `rg x <repo> ~` 를 놓친다."""
    if any(not under_allowed(m.group(1)) for m in FIND_ROOT.finditer(cmd)):
        return True
    for h in MULTI_HEADS:
        for m in h.finditer(cmd):
            seg = re.split(r"[|;&\n]", cmd[m.end():], maxsplit=1)[0]
            seg = re.sub(r"'[^']*\s[^']*'|\"[^\"]*\s[^\"]*\"", " ", seg)   # 공백 든 따옴표 구간은 검색 패턴이다('width / 2') — 뿌리로 읽지 않는다
            if any(not under_allowed(t.group(1)) for t in ROOT_ARG.finditer(seg)):
                return True
    return False
def home_ref(cmd):
    for m in re.finditer(re.escape(home) + r"[^\s'\"]*", cmd):
        p = m.group(0)
        if not ((repo and (p == repo or p.startswith(repo + "/"))) or p == iso or p.startswith(iso + "/")):
            return p
    return None
tcs, spawn, calls, hits, roles = 0, 0, 0, [], []
iso_ok = bool(rolls)
for f in rolls:
    for line in open(f, encoding="utf-8", errors="replace"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict):
            continue
        p = r.get("payload") or {}
        if not isinstance(p, dict):
            continue   # 모르는 모양은 건너뛴다 — 감사 블록이 예외로 죽지 않게(죽어도 감사는 running 으로 남아 거부된다)
        if r.get("type") == "turn_context":
            tcs += 1
            ents = ((p.get("permission_profile") or {}).get("file_system") or {}).get("entries") or []
            if not any((e.get("path") or {}).get("path") == home and e.get("access") == "deny" for e in ents):
                iso_ok = False
        t = p.get("type")
        if t == "function_call" and p.get("name") == "spawn_agent":
            spawn += 1
            try:
                roles.append(json.loads(p.get("arguments") or "{}").get("agent_type"))
            except (ValueError, AttributeError):
                roles.append(None)
        cmd = None
        if t == "custom_tool_call":
            cmd = p.get("input")
        elif t == "function_call" and p.get("name") in ("exec_command", "shell", "local_shell"):
            cmd = p.get("arguments")
        elif t == "local_shell_call":
            cmd = json.dumps(p.get("action"))
        if not isinstance(cmd, str):
            continue
        calls += 1
        why = ("금지 산출물 참조" if forbid_hit(cmd) else
               "홈 · 루트 재귀 검색" if recurse_hit(cmd) else
               ("격리 밖 홈 경로 " + home_ref(cmd)) if home_ref(cmd) else None)
        if why:
            hits.append({"rollout": os.path.basename(f), "rule": why, "cmd": cmd[:300]})
if tcs == 0:
    iso_ok = False
audit = {"mode": mode, "rollouts": len(rolls), "turnContexts": tcs, "isolationApplied": iso_ok, "spawnAgent": spawn, "spawnedRoles": roles,
         "toolCalls": calls, "hits": hits, "wrapperExit": rc, "timedOut": timed_out, "inputs": inputs, "head": head,
         # resume 입력(fz-plan Phase 2 resume 교차) — 격리 홈은 --keep-iso 일 때만 남는다. sessionFile 은 판정(exit) 뒤에 적는다(아래)
         "iso": iso if keep else None}
code, note = 0, "ok"
if hits or (not iso_ok and not timed_out and rc == 0):
    code, note = 15, ("rollout 감사 적중" if hits else "격리 미적용 — rollout 에 HOME deny 가 없다(또는 rollout 이 없다)")
    open(stem + ".contaminated", "w", encoding="utf-8").write(json.dumps({"reason": note, "hits": hits}, ensure_ascii=False, indent=1))
elif timed_out:
    code, note = 16, "시간 초과 — 프로세스 그룹째 종료"
elif rc != 0:
    code, note = rc, f"래퍼 exit {rc} — 측정 실패(결과 아님)"
else:
    try:
        doc = json.load(open(out, encoding="utf-8"))
    except (OSError, ValueError) as e:
        doc, code, note = None, 13, f"출력 읽기 실패: {e}"
    if doc is not None and mode == "plan" and doc.get("status") == "rejected":
        code, note = 17, f"planner 거부 — {doc.get('reason')}"
    if doc is not None and mode == "review":
        want = json.load(open(schema_p, encoding="utf-8"))["properties"]["axis_coverage"]["items"]["properties"]["axis"]["enum"]
        got = [a.get("axis") for a in doc.get("axis_coverage", [])]
        if sorted(got) != sorted(want):
            code, note = 14, f"6축 후검사 실패 — axis_coverage 축 집합 {got} ≠ {want}(중복 · 결손)"
    if doc is not None:
        md = [f"# GPT 독립 첫 패스 — {mode}", ""]
        if mode == "plan":
            md += [f"- status: `{doc.get('status')}`" + (f" · reason: {doc.get('reason')}" if doc.get('reason') else ""), f"- approach: {doc.get('approach')}", "",
                   "| 파일 | 동작 | 이유 |", "|---|---|---|"]
            md += [f"| {s.get('file') or ', '.join(s.get('files') or [])} | {s.get('action')} | {s.get('why')} |" for s in doc.get("steps", [])]
            md += ["", "## 위험"] + [f"- {x.get('risk')} → {x.get('mitigation')}" for x in doc.get("riskMatrix", [])]
            md += ["", "## 비교할 결정"] + [f"- {x}" for x in doc.get("divergencePoints", [])]
        else:
            md += [f"- verdict: `{doc.get('verdict')}`", f"- {doc.get('summary')}", "", "## 결함"]
            md += [f"- **{i.get('severity')}** `{i.get('file')}:{i.get('line_range')}` — {i.get('title')}" for i in doc.get("issues", [])] or ["- 없음"]
            md += ["", "## 솜씨(6축)"]
            md += [f"- `{c.get('craftAxis')}` [{c.get('ruleSource')}] `{c.get('file')}:{c.get('line_range')}` — {c.get('title')}" for c in doc.get("craft", [])] or ["- 없음"]
            md += ["", "| 축 | 상태 | 비고 |", "|---|---|---|"] + [f"| {a.get('axis')} | {a.get('status')} | {a.get('note')} |" for a in doc.get("axis_coverage", [])]
        open(stem + ".md", "w", encoding="utf-8").write("\n".join(md) + "\n")
# ⛔ 래퍼는 자기 게이트(exit · 파일 · 스키마) 통과 직후 세션 파일을 쓴다 — 그 뒤 여기서 걸린 run(오염 15 · 6축 14 · planner 거부 17)의
#    세션은 resume 교차가 잇지 못하게 지운다. 감사 sessionFile 은 exit 0 일 때만 남는다
sess = out + ".session"
if code != 0 and os.path.isfile(sess):
    os.remove(sess)
audit.update({"exit": code, "note": note, "sessionFile": sess if os.path.isfile(sess) else None})
json.dump(audit, open(stem + ".audit.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"INDEPENDENT {'OK' if code == 0 else 'FAIL(' + str(code) + ')'} mode={mode} rollouts={len(rolls)} spawn={spawn} calls={calls} hits={len(hits)} isolation={iso_ok} — {note}")
sys.exit(code)
PY
ARC=$?
# ⛔ 감사 블록이 예외로 죽으면(파이썬 exit 1) 감사는 'running' 그대로다 — 결과가 아니므로 사전조건 실패로 끝낸다(10~17 밖의 코드는 Lead 규칙이 못 본다)
if [ "$ARC" -ne 0 ] && grep -q '"exit": null' "$OUT_DIR/$BASE_NAME.audit.json" 2>/dev/null; then
  die 11 "감사 블록 실패(exit $ARC) — 감사는 running 으로 남는다(병합 · 차이표가 거부한다)"
fi
exit "$ARC"
