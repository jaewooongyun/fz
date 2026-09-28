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
#   gpt_independent.sh plan   --requirement F [--sprint-contract F] [--rules-index F] [--snapshot D]... [--repo D [--deny D]...]
#                             --arm A --run-id ID --out-dir D [--timeout S] [--effort E] [--keep-iso]
#   gpt_independent.sh review --diff F [--pr-meta F] [--requirement F] [--rules-index F] [--base D] [--head D] [--snapshot D]...
#                             [--repo D [--deny D]...] [--gpt-agents] --arm A --run-id ID --out-dir D [--timeout S] [--effort E] [--keep-iso]
#   --gpt-agents review 전용 — 역할 파일(gpt-agents/*.toml)을 격리 홈 agents/ 에 넣고 두 렌즈 역할(fz-review-arch · fz-review-quality)만
#             spawn 하게 한다(S14 · opt-in). 없으면 하위 에이전트 금지. 하위 에이전트는 부모 이력을 물려받는다 — 격리된 부모 안이라 독립이 유지된다
#   --repo    대상 저장소 — 복사하지 않고 권한 프로필 read 로 연다. 그 안의 .claude · .fz-work 와 --deny 는 막는다
#   --snapshot 소비자 · 공유 모듈 본문 폴더 — 격리 폴더의 snapshot/<이름>/ 으로 복사한다(리뷰 범위를 줄이지 않는다)
#
# 산출(out-dir): <arm>-<run-id>.json (스키마 출력) · .md (사람용) · .audit.json · .rollouts/ (세션 로그 사본) · .contaminated (오염 시)
# exit: 0=성공 · 10=사용법 · 같은 --out 동시 실행 · 11=사전조건 · 12~14=래퍼 측정 실패 그대로(14 는 6축 후검사도)
#       15=오염 — 금지 입력 · 격리 미적용 · rollout 감사 적중 · 16=시간 초과(프로세스 그룹째 종료) · 17=planner 가 status=rejected
#   ⛔ 10~17 은 전부 첫 패스 결과가 아니다 — 0건으로 읽지 않는다.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

die() { echo "INDEPENDENT-FAIL($1): $2" >&2; exit "$1"; }
need() { [ "$1" -ge 2 ] || die 10 "$2 는 값이 필요하다"; }

MODE="${1:-}"; shift || true
case "$MODE" in
  plan) ROLE=planner ;;
  review) ROLE=reviewer ;;
  *) die 10 "mode 는 plan|review — 받은 값: '${MODE}'" ;;
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
[ "${#DENIES[@]}" -eq 0 ] || [ -n "$REPO" ] || die 10 "--deny 는 --repo 안에서 더 막을 경로다 — --repo 없이 줄 수 없다"
[ -z "$GPT_AGENTS" ] || [ "$MODE" = "review" ] || die 10 "--gpt-agents 는 review 전용이다(역할 파일은 리뷰 렌즈다)"

# ── 사전 게이트: 입력 실재 · 금지 입력(⛔ exit 15 — Claude 산출물이 첫 패스에 들어가면 독립이 아니다)
REAL_HOME="$(cd "${HOME:?HOME 미설정}" && pwd -P)"
REAL_GPT_HOME="$(cd "${CODEX_HOME:-$REAL_HOME/.codex}" 2>/dev/null && pwd -P)" || die 11 "실제 GPT CLI 홈이 없다: ${CODEX_HOME:-$REAL_HOME/.codex}"
[ -f "$REAL_GPT_HOME/auth.json" ] || die 11 "인증 파일이 없다: $REAL_GPT_HOME/auth.json (로그인 필요)"
for f in "$REQ" "$SC" "$RULES" "$DIFF" "$META"; do [ -z "$f" ] || [ -s "$f" ] || die 11 "입력 파일 없음/빈 파일: $f"; done
for d in "$BASE_DIR" "$HEAD_DIR" "$REPO" "${SNAPS[@]+"${SNAPS[@]}"}" "${DENIES[@]+"${DENIES[@]}"}"; do [ -z "$d" ] || [ -d "$d" ] || die 11 "입력 폴더 없음: $d"; done
GUARD="$(python3 - "$REAL_HOME" "$REQ" "$SC" "$RULES" "$DIFF" "$META" -- "$BASE_DIR" "$HEAD_DIR" "${SNAPS[@]+"${SNAPS[@]}"}" -- "$REPO" <<'PY'
import os, re, sys
home, argv = sys.argv[1], sys.argv[2:]
a = argv.index("--"); b = argv.index("--", a + 1)
files, dirs, repo = [x for x in argv[:a] if x], [x for x in argv[a + 1:b] if x], [x for x in argv[b + 1:] if x]
BAD = re.compile(r"^(code-context.*|plan-v\d.*|plan-final.*|.*workflow-result.*|.*-result\.json|review-report\.md|pr-comments\.md"
                 r"|payload\.json|render-preview\.json|self-review\.md|triage\.md)$")
claude = os.path.join(home, ".claude")
hits = []
def check(p, name_check=True):
    rp = os.path.realpath(p)
    if rp == claude or rp.startswith(claude + os.sep):
        hits.append(f"{p} — ~/.claude 아래(에이전트 로그 · journal)")
    elif name_check and BAD.match(os.path.basename(rp)):
        hits.append(f"{p} — Claude 산출물 이름")
for f in files:
    check(f)
for d in dirs:
    check(d, name_check=False)
    for root, _, names in os.walk(d):
        for n in names:
            check(os.path.join(root, n))
for r in repo:
    check(r, name_check=False)
print("\n".join(hits))
PY
)" || die 11 "입력 판정 실패"
[ -z "$GUARD" ] || die 15 "허용 목록 밖 입력 — 독립 첫 패스가 아니다:
$GUARD"

# ── 같은 --out 동시 실행 거부 (mkdir 는 원자적이다)
mkdir -p "$OUT_DIR" || die 11 "--out-dir 생성 실패: $OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd -P)"
BASE_NAME="${ARM}-${RUN_ID}"
OUT="$OUT_DIR/$BASE_NAME.json"
mkdir "$OUT.lock" 2>/dev/null || die 10 "같은 --out 이 이미 실행 중이다(또는 전 실행의 잠금이 남았다): $OUT.lock"
ISO=""
cleanup() { rm -rf "$OUT.lock"; [ -n "$ISO" ] && [ -z "$KEEP_ISO" ] && rm -rf "$ISO"; }
trap cleanup EXIT

# ── 격리 폴더 — ⛔ 경로는 전부 realpath(`/tmp`→`/private/tmp` · `/var/folders`→`/private/var/folders`). deny·read 표기가 어긋나면 중첩 규칙이 안 맞는다
ISO="$(cd "$(mktemp -d "${TMPDIR:-/tmp}/fz-gpt-iso.XXXXXX")" && pwd -P)" || die 11 "격리 폴더 생성 실패"
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
    for d in denies:
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
( sleep "$TIMEOUT"; touch "$ISO/.timed-out"; kill -TERM -- "-$WPID" 2>/dev/null; sleep 3; kill -KILL -- "-$WPID" 2>/dev/null ) >/dev/null 2>&1 &
TPID=$!
wait "$WPID"; RC=$?
kill "$TPID" 2>/dev/null; wait "$TPID" 2>/dev/null
TIMED_OUT=0; [ -f "$ISO/.timed-out" ] && TIMED_OUT=1

# ── 감사 · 후검사 · 렌더 — rollout 은 세션 폴더의 jsonl **전부**(spawn 을 못 끈다 — S11 ⑤)
rm -rf "$OUT_DIR/$BASE_NAME.rollouts"; mkdir -p "$OUT_DIR/$BASE_NAME.rollouts"
find "$ISO/gpt-home/sessions" -name '*.jsonl' -exec cp {} "$OUT_DIR/$BASE_NAME.rollouts/" \; 2>/dev/null
python3 - "$MODE" "$OUT" "$OUT_DIR/$BASE_NAME" "$REAL_HOME" "$REPO_REAL" "$ISO" "$RC" "$TIMED_OUT" "$SCHEMA" <<'PY'
import glob, hashlib, json, os, re, sys
mode, out, stem, home, repo, iso, rc, timed_out, schema_p = sys.argv[1:10]
# ⛔ 입력 해시는 격리 사본에서 잰다 — GPT 가 실제로 본 내용이다(읽기 전용 프로필이라 실행 중에 바뀌지 않는다). 병합이 stale 을 가린다
inputs = {n: hashlib.sha256(open(os.path.join(iso, "input", n), "rb").read()).hexdigest()
          for n in ("diff.patch", "requirement.md", "sprint-contract.md", "rules-index.json", "pr-meta.json")
          if os.path.isfile(os.path.join(iso, "input", n))}
rc, timed_out = int(rc), timed_out == "1"
rolls = sorted(glob.glob(os.path.join(stem + ".rollouts", "*.jsonl")))
FORBID = re.compile(r"\.claude/|plan-v\d|workflow-result|-result\.json|code-context|review-report\.md|pr-comments\.md")
ROOTS = r"(~|\$HOME|/Users(/[^\s'\"]*)?|/)(?=[\s'\";|&)]|$)"
RECURSE = [re.compile(rf"\bfind\s+{ROOTS}"), re.compile(rf"\b(rg|fd|ag)\b[^|;&\n]*\s{ROOTS}"),
           re.compile(rf"\bgrep\s+-[a-zA-Z]*[rR][a-zA-Z]*\b[^|;&\n]*\s{ROOTS}"), re.compile(rf"\bls\s+-[a-zA-Z]*R[a-zA-Z]*\b[^|;&\n]*\s{ROOTS}")]
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
        p = r.get("payload") or {}
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
        why = ("금지 산출물 참조" if FORBID.search(cmd) else
               "홈 · 루트 재귀 검색" if any(x.search(cmd) for x in RECURSE) else
               ("격리 밖 홈 경로 " + home_ref(cmd)) if home_ref(cmd) else None)
        if why:
            hits.append({"rollout": os.path.basename(f), "rule": why, "cmd": cmd[:300]})
if tcs == 0:
    iso_ok = False
audit = {"mode": mode, "rollouts": len(rolls), "turnContexts": tcs, "isolationApplied": iso_ok, "spawnAgent": spawn, "spawnedRoles": roles,
         "toolCalls": calls, "hits": hits, "wrapperExit": rc, "timedOut": timed_out, "inputs": inputs}
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
audit.update({"exit": code, "note": note})
json.dump(audit, open(stem + ".audit.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"INDEPENDENT {'OK' if code == 0 else 'FAIL(' + str(code) + ')'} mode={mode} rollouts={len(rolls)} spawn={spawn} calls={calls} hits={len(hits)} isolation={iso_ok} — {note}")
sys.exit(code)
PY
