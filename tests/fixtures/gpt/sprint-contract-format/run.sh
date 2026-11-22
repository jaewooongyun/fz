#!/bin/bash
# modes: --fixture caller=manual last-pass=7b89bd4 result=9 PASS · 기본 DIR quality/plan-feature(2026-11-05 배선 감사)
# modes: --live caller=manual last-pass=none result=실제 GPT CLI 호출(네트워크) · 독립 런처 격리(gpt_independent.sh iso) — 사람 호출 전용
# Sprint Contract 형식 러너 (S12) — fz-architect 로 Sprint Contract 를 만들 때(modules/sprint-contract.md 절차 2) SC 산출 형식이 유지되는가.
#
# 기본 모드(게이트) — GPT 를 부르지 않는다. 결정론이다.
#   ① 조립: --live 와 같은 함수로 과제 프롬프트를 만들고 래퍼(--inject-skill) + 가짜 CLI(../_shim/codex)로 캡처한다
#      → architect 본문 1회 · SC 스키마 키 전부 · 요구 원문
#   ② 우선: fz-architect 본문에 '과제 형식이 이긴다' 규칙과 SC 키 이름이 있다 — 없으면 본문의 검증 형식이 SC 형식을 덮는다
#   ③ 기록: recorded/sc-output.yaml 이 SC 스키마 키를 갖고, recorded/provenance.json 의 architect 본문·과제 프롬프트 해시가 지금과 같다
#      ⛔ 기록이 없거나 해시가 다르면 FAIL 이다 — 옛 기록으로 통과시키지 않는다. `--live` 로 다시 기록한다
#   ④ 격리: --live 재녹화 호출이 독립 런처와 같은 격리(gpt_independent.sh iso)로 도는가 — 모델에게 묻지 않고 실행으로 본다.
#      가짜 CLI 앞에 호출마다 한 줄 남기는 래퍼를 두고 --live 를 돌려 첫 호출(재녹화)의 HOME · CODEX_HOME · 권한 프로필 deny ·
#      sandbox_mode 부재 · 플러그인 트리 deny · 저장소 read 를 보고, 기록의 격리 증거와 격리 폴더 정리를 본다
#   ⑤ iso 사전 게이트: gpt_independent.sh iso 가 메인 경로와 같은 두 게이트 — 격리 폴더 자리(TMPDIR 이 ~/.claude 아래 → exit 11) ·
#      금지 입력(--repo 가 ~/.claude 아래 → exit 15 · ~/.claude 가 링크면 링크 경로 · 링크 대상 경로 둘 다) — 를 격리 폴더를 만들기 전에 거는가(빈 stdout · 폴더 0개). 대조: 같은 가짜 HOME 에서
#      ~/.claude 밖 자리 · 저장소면 exit 0 과 격리 폴더 경로 한 줄. 가짜 HOME · 러너 임시 폴더 안 TMPDIR 만 쓴다(실제 ~/.claude · 임시 루트를 가리키지 않는다)
#      인증 파일 없음(CLI 홈에 auth.json 이 없다 — API 키 env 가 있어도)은 두 게이트보다 먼저 exit 18 · 'GPT-OFF: 인증 파일 없음(격리 첫 패스)'(메인 경로와 같은 GPT 미사용)
#      GPT 미사용 사유는 메인 경로와 같은 순서다 — CLI 없음 · 사용자 선택 · 로그인 필요 · 인증 파일 없음(셀 iso-cli-missing-off · iso-user-choice-off ·
#      iso-not-signed-in-login-needed · iso-signed-in-no-auth-file · iso-key-only-no-auth-file — 가짜 CLI 의 login status 로 로그인 상태를 정한다)
# --live — 실제 GPT CLI 1회(effort high · read-only 권한 프로필)로 기록을 새로 만든 뒤 기본 모드를 돈다. 사람이 부른다(게이트는 부르지 않는다)
#   호출은 독립 런처와 같은 격리 아래서 돈다 — gpt_independent.sh iso 가 만든 격리 폴더(가짜 HOME · 격리 CODEX_HOME · 권한 프로필:
#   HOME · 임시 루트 · 플러그인 트리 deny · 저장소 사본 read)와 래퍼 --config-permissions. 기록(provenance.json)에 격리 config 의 deny 경로 수를 남긴다
#
# ⛔ 필수 키는 여기 적지 않는다 — modules/sprint-contract.md 의 스키마 블록에서 읽는다(형식 정본이 한 곳이다)
# ⛔ exit 셋을 섞지 않는다(F-396): 모듈 파일이 없다 = 측정 실패(2) · 파일은 있는데 스키마 블록이 없다 = 내용 위반(1).
#    FZ_SC_MODULE 은 자기 시험 전용 덮어쓰기다 — 블록 없는 사본으로 자신을 다시 불러 exit 1 을 확인한다.
#    FZ_SC_RECORD_DIR 도 자기 시험 전용이다 — ④ 가 --live 를 가짜 CLI 로 돌릴 때 트리의 recorded/ 대신 임시 폴더에 쓴다.
# usage: run.sh [--fixture DIR] [--live]
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURE="$R/tests/fixtures/quality/plan-feature" LIVE=0   # 기본 = plan-feature — health-check 4.6 은 러너를 인자 없이 부른다
while [ $# -gt 0 ]; do
  case "$1" in
    --fixture) FIXTURE="${2:-}"; shift 2 ;;
    --live) LIVE=1; shift ;;
    *) echo "UNRUN: 알 수 없는 인자 $1"; exit 2 ;;
  esac
done
[ -n "$FIXTURE" ] && [ -s "$FIXTURE/requirement.md" ] || { echo "UNRUN: --fixture 에 requirement.md 가 없다: '$FIXTURE'"; exit 2; }
ARCH="$R/gpt-skills/fz-architect/SKILL.md"
MOD="${FZ_SC_MODULE:-$R/modules/sprint-contract.md}"
REC="${FZ_SC_RECORD_DIR:-$HERE/recorded}"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

fail=0
ok() { echo "PASS  $1"; }
no() { echo "FAIL  $1"; fail=1; }

# 자기 시험(F-396) — 블록 없는 모듈 = exit 1 · 없는 모듈 = exit 2. 덮어쓰기로 불린 안쪽 실행은 다시 들어가지 않는다
if [ -z "${FZ_SC_MODULE:-}" ]; then
  printf '# Sprint Contract\n\n## Sprint Contract Schema\n\n본문만 있고 yaml 펜스가 없다\n' > "$T/no-block.md"
  o="$(FZ_SC_MODULE="$T/no-block.md" bash "${BASH_SOURCE[0]}" 2>&1)"; rc=$?
  if [ "$rc" -eq 1 ] && printf '%s\n' "$o" | grep -q '^FAIL  스키마 블록'; then ok "f396-schema-block-missing-violation"
  else no "f396-schema-block-missing-violation — exit $rc · $(printf '%s' "$o" | tail -1)"; fi
  o="$(FZ_SC_MODULE="$T/absent.md" bash "${BASH_SOURCE[0]}" 2>&1)"; rc=$?
  if [ "$rc" -eq 2 ] && printf '%s\n' "$o" | grep -q '^UNRUN: 모듈 파일이 없다'; then ok "f396-schema-module-missing-unrun"
  else no "f396-schema-module-missing-unrun — exit $rc · $(printf '%s' "$o" | tail -1)"; fi
fi

# 스키마 블록(## Sprint Contract Schema 아래 첫 ```yaml 펜스)을 파일로 뽑는다 — 과제 프롬프트와 키 목록의 단일 출처
[ -f "$MOD" ] || { echo "UNRUN: 모듈 파일이 없다: $MOD"; exit 2; }
python3 - "$MOD" "$T/schema.yaml" <<'PY'
import re, sys
s = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"^## Sprint Contract Schema\s*\n+```yaml\n(.*?)\n```", s, re.S | re.M)
if not m:
    sys.exit(3)
open(sys.argv[2], "w", encoding="utf-8").write(m.group(1) + "\n")
PY
rc=$?
case "$rc" in
  0) ;;
  3) echo "FAIL  스키마 블록: $MOD 에 '## Sprint Contract Schema' 아래 yaml 펜스가 없다"; exit 1 ;;
  *) echo "UNRUN: 스키마 블록 추출기 exit $rc"; exit 2 ;;
esac

task() {   # 과제 프롬프트 — --live 와 조립 검사가 같은 함수를 쓴다
  cat <<EOF
Sprint Contract 작성 — 구현을 시작하기 **전에** 이 요구사항의 성공 기준을 쓴다(modules/sprint-contract.md 절차 2).
저장소는 작업 디렉터리에 있다. 필요한 만큼 읽되 수정하지 않는다.

출력: 아래 스키마의 YAML 문서 하나만 낸다. 앞뒤 설명·코드 펜스 없이.
- success_criteria 는 각각 빌드·grep·테스트로 참/거짓이 갈리는 단일 명제다(measurable: true)
- anti_criteria 는 반드시 일어나면 안 되는 패턴과 그 탐지 방법이다

## 스키마
$(cat "$T/schema.yaml")

## 요구사항
$(cat "$FIXTURE/requirement.md")
EOF
}
task > "$T/task.txt"

# 기록 형식 판정 — 스키마의 최상위 키 · success_criteria/anti_criteria 항목 키가 산출물에 있는가
check_format() {   # $1=산출물
  python3 - "$T/schema.yaml" "$1" <<'PY'
import re, sys
schema, out = (open(p, encoding="utf-8").read() for p in sys.argv[1:3])
out = re.sub(r"^\s*```[a-z]*\s*\n|\n\s*```\s*$", "", out.strip()) + "\n"

def top_keys(t):
    return [m.group(1) for m in re.finditer(r"^([a-z_]+):", t, re.M)]

def items(t, key):
    """key: 아래 목록 항목(- 로 시작)마다 그 항목 블록의 키 집합."""
    m = re.search(rf"^{key}:\s*\n((?:[ \t-].*\n|\s*\n)*)", t, re.M)
    if not m:
        return []
    blocks, cur = [], None
    for line in m.group(1).split("\n"):
        k = re.match(r"^\s*-\s+([a-z_]+):", line)
        if k:
            cur = {k.group(1)}; blocks.append(cur)
        elif cur is not None:
            k2 = re.match(r"^\s+([a-z_]+):", line)
            if k2:
                cur.add(k2.group(1))
    return blocks

bad = []
miss = [k for k in top_keys(schema) if k not in top_keys(out)]
if miss:
    bad.append(f"최상위 키 결손 {miss}")
for key in ("success_criteria", "anti_criteria"):
    want = set().union(*items(schema, key)) if items(schema, key) else set()
    got = items(out, key)
    if not got:
        bad.append(f"{key} 항목 0개")
    for i, b in enumerate(got, 1):
        if want - b:
            bad.append(f"{key}[{i}] 키 결손 {sorted(want - b)}")
if re.search(r"/Users/|/private/|/var/folders/", out):
    bad.append("산출물에 로컬 절대경로")
print("; ".join(bad) if bad else f"OK top={len(top_keys(out))} sc={len(items(out, 'success_criteria'))} ac={len(items(out, 'anti_criteria'))}")
sys.exit(1 if bad else 0)
PY
}
sha() { python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest()[:16])' "$1"; }

if [ "$LIVE" -eq 1 ]; then
  bash "$FIXTURE/build-repo.sh" "$T/repo" >/dev/null 2>&1 || { echo "UNRUN: fixture 저장소 복원 실패"; exit 2; }
  mkdir -p "$REC"
  # 격리 — 독립 런처와 같은 한 벌(gpt_independent.sh iso): 가짜 HOME · 격리 CODEX_HOME(인증 링크 · gpt-skills 사본 · 권한 프로필) ·
  #   저장소 사본 read · 플러그인 트리 deny(옛 기록 recorded/ 가 새 기록으로 새지 않게). 래퍼는 --config-permissions 로 sandbox_mode 를 넘기지 않는다.
  #   ⛔ 가짜 HOME 이면 래퍼의 선택 폴더가 격리 홈 아래로 바뀐다 — 런처처럼 실제 홈 기준 선택 폴더를 명시로 넘긴다
  REPO_DIR="$(cd "$T/repo" && pwd -P)"
  ISO="$(bash "$R/scripts/gpt_independent.sh" iso --repo "$REPO_DIR" --deny "$R")" && [ -d "$ISO/gpt-home" ] || { echo "UNRUN: 격리 폴더 생성 실패(gpt_independent.sh iso)"; exit 2; }
  trap 'bash "$R/scripts/gpt_independent.sh" cleanup --iso "$ISO" >/dev/null 2>&1; rm -rf "$T"' EXIT
  env HOME="$ISO/home" CODEX_HOME="$ISO/gpt-home" FZ_TELEMETRY_DIR="$T/tel" FZ_GPT_CHOICE_DIR="${FZ_GPT_CHOICE_DIR:-$HOME/.fz/gpt-choice}" \
    bash "$R/scripts/gpt-exec.sh" exec --cd "$REPO_DIR" --out "$T/live.yaml" --prompt-file "$T/task.txt" --effort high --gpt-skill architect \
    --inject-skill "$ISO/gpt-home/skills/fz-architect/SKILL.md" --config-permissions || { echo "FAIL  --live: 래퍼 exit $? (기록하지 않는다)"; exit 1; }
  check_format "$T/live.yaml" >/dev/null || { echo "FAIL  --live: 산출물이 SC 형식이 아니다 — $(check_format "$T/live.yaml")"; cp "$T/live.yaml" "$REC/sc-output.rejected.yaml"; exit 1; }
  cp "$T/live.yaml" "$REC/sc-output.yaml"
  python3 - "$REC/provenance.json" "$(sha "$ARCH")" "$(sha "$T/task.txt")" "$(codex --version 2>/dev/null | head -1)" "$ISO/gpt-home/config.toml" <<'PY'
import datetime, json, re, sys
# 격리 증거 — 래퍼가 받은 격리 config 의 권한 프로필 deny 경로 수(호출자 env 의 자기 보고가 아니다)
deny = len(re.findall(r'(?m)^".+" = "deny"$', open(sys.argv[5], encoding="utf-8").read()))
json.dump({"architect_sha256_16": sys.argv[2], "task_sha256_16": sys.argv[3], "cli_version": sys.argv[4], "effort": "high",
           "codex_home": "isolated" if deny else "default", "iso_deny_paths": deny,
           "recorded": datetime.date.today().isoformat(), "note": "run.sh --live 가 쓴다 — 손으로 고치지 않는다"},
          open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
PY
  echo "기록: $REC/sc-output.yaml · provenance.json"
fi

# ① 조립 — 래퍼 + 가짜 CLI
env PATH="$R/tests/fixtures/gpt/_shim:$PATH" FZ_GPT_CHOICE_DIR="$T/no-choice" FZ_SHIM_CAPTURE="$T/argv.json" FZ_SHIM_OUTPUT="sprint_id: x" FZ_TELEMETRY_DIR="$T/tel-shim" \
  bash "$R/scripts/gpt-exec.sh" exec --cd "$T" --out "$T/shim.out" --prompt-file "$T/task.txt" --effort high --gpt-skill architect --inject-skill "$ARCH" \
  > "$T/shim.stdout" 2>&1
[ -s "$T/argv.json" ] && ok "조립: 래퍼가 CLI 를 불렀다" || no "조립: 래퍼가 CLI 를 부르지 않았다 — $(tail -1 "$T/shim.stdout")"
if [ -s "$T/argv.json" ]; then
  A="$(python3 - "$T/argv.json" "$T/schema.yaml" "$ARCH" "$FIXTURE/requirement.md" <<'PY'
import json, re, sys
argv = " ".join(json.load(open(sys.argv[1], encoding="utf-8")))
schema, arch, req = (open(p, encoding="utf-8").read() for p in sys.argv[2:5])
head = next(l for l in arch.split("\n") if l.startswith("# "))
keys = re.findall(r"^([a-z_]+):", schema, re.M)
res = [("architect 본문 1회", argv.count(head) == 1), ("주입 마커 1회", argv.count("[fz-gpt-skill-injected] fz-architect") == 1),
       ("요구 원문", req.strip().split("\n")[0] in argv), (f"스키마 최상위 키 {len(keys)}개", all(f"{k}:" in argv for k in keys))]
for name, good in res:
    print(("PASS  조립: " if good else "FAIL  조립: ") + name)
PY
)"
  printf '%s\n' "$A"
  printf '%s\n' "$A" | grep -q '^FAIL' && fail=1
fi

# ② 우선 — architect 본문이 과제 형식을 앞세우고 SC 키를 이름으로 댄다
if grep -q "The task's format wins" "$ARCH" && python3 - "$ARCH" <<'PY'
import sys
t = open(sys.argv[1], encoding="utf-8").read()
line = next((l for l in t.split("\n") if "The task's format wins" in l), "")
sys.exit(0 if all(k in line for k in ("sprint_id", "success_criteria", "anti_criteria", "review_pass_threshold", "scope_boundary")) else 1)
PY
then ok "우선: architect 본문에 과제 형식 우선 규칙 + SC 키"; else no "우선: architect 본문에 '과제 형식이 이긴다' 규칙(또는 SC 키 이름)이 없다"; fi

# ③ 기록 — 형식과 해시
if [ ! -s "$REC/sc-output.yaml" ] || [ ! -s "$REC/provenance.json" ]; then
  no "기록: recorded/sc-output.yaml · provenance.json 이 없다 — run.sh --fixture … --live 로 기록한다"
else
  F="$(check_format "$REC/sc-output.yaml")" && ok "기록 형식: $F" || no "기록 형식: $F"
  P="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("architect_sha256_16",""), d.get("task_sha256_16",""))' "$REC/provenance.json")"
  [ "${P%% *}" = "$(sha "$ARCH")" ] && ok "기록 해시: architect 본문이 기록 때와 같다" \
    || no "기록 해시: architect 본문이 기록 뒤 바뀌었다 — --live 로 다시 기록한다"
  [ "${P##* }" = "$(sha "$T/task.txt")" ] && ok "기록 해시: 과제 프롬프트(스키마·요구)가 기록 때와 같다" \
    || no "기록 해시: 과제 프롬프트가 기록 뒤 바뀌었다 — --live 로 다시 기록한다"
fi

# ④ 격리 — 가짜 CLI 앞 기록 래퍼가 호출마다 한 줄(HOME · CODEX_HOME · 그 config 의 deny 줄 수 · 인자의 sandbox_mode 유무)을 남긴다.
#    둘째 줄은 러너가 기록(provenance.json)에 CLI 버전을 적으려고 래퍼(gpt-exec.sh) 밖에서 부르는 버전 조회(`--version`)다(러너의 바깥
#    env 그대로 — 격리가 아니다). 조립용 호출(①)은 PATH 맨 앞에 _shim 을 두어 기록 래퍼를 거치지 않는다. 그래서 첫 줄(재녹화 호출)을 본다.
#    첫 호출의 config 는 사본으로 남긴다.
#    ⛔ 트리의 recorded/ 를 덮지 않는다(FZ_SC_RECORD_DIR) · 실제 GPT 홈 대신 임시 인증 파일(CODEX_HOME) · 안쪽 실행(--live · 자기 시험)은 다시 들어가지 않는다
if [ "$LIVE" -eq 0 ] && [ -z "${FZ_SC_MODULE:-}" ]; then
  mkdir -p "$T/lw" "$T/lgh" "$T/lrec"; echo '{"fake":"auth"}' > "$T/lgh/auth.json"
  cat > "$T/lw/codex" <<'WRAP'
#!/bin/bash
case "${1:-} ${2:-}" in "login status") exec "$FZ_SC_SHIM/codex" "$@" ;; esac   # iso 의 인증 판정(auth-check)은 재녹화 호출이 아니다 — 줄을 남기지 않는다
d=$(grep -c '= "deny"' "${CODEX_HOME:-/nonexistent}/config.toml" 2>/dev/null)
case " $* " in *sandbox_mode*) s=1 ;; *) s=0 ;; esac
printf 'CALL HOME=%s CODEX_HOME=%s DENY=%s SBX=%s\n' "${HOME:-}" "${CODEX_HOME:-}" "${d:-0}" "$s" >> "$FZ_SC_CALLS"
[ -e "$FZ_SC_CALLS.toml" ] || cp "${CODEX_HOME:-/nonexistent}/config.toml" "$FZ_SC_CALLS.toml" 2>/dev/null
[ -e "$FZ_SC_CALLS.cwd" ] || { p=""; for a in "$@"; do [ "$p" = "-C" ] && printf '%s\n' "$a" > "$FZ_SC_CALLS.cwd"; p="$a"; done; }
exec "$FZ_SC_SHIM/codex" "$@"
WRAP
  chmod +x "$T/lw/codex"
  env PATH="$T/lw:$PATH" CODEX_HOME="$T/lgh" FZ_GPT_CHOICE_DIR="$T/no-choice" FZ_SC_CALLS="$T/calls.txt" FZ_SC_SHIM="$R/tests/fixtures/gpt/_shim" \
    FZ_SC_RECORD_DIR="$T/lrec" FZ_SHIM_OUTPUT="$(cat "$REC/sc-output.yaml" 2>/dev/null)" bash "${BASH_SOURCE[0]}" --fixture "$FIXTURE" --live > "$T/live.out" 2>&1
  L1="$(head -1 "$T/calls.txt" 2>/dev/null)"
  LC="$(printf '%s\n' "$L1" | sed -n 's/^CALL HOME=[^ ]* CODEX_HOME=\([^ ]*\) DENY=.*/\1/p')"; LI="${LC%/gpt-home}"
  LISO=0; case "${LI##*/}" in fz-gpt-iso.??????) [ "$LC" = "$LI/gpt-home" ] && LISO=1 ;; esac
  LCFG="$T/calls.txt.toml"
  case "$LISO:$L1" in "1:CALL HOME=$LI/home CODEX_HOME=$LC DENY="*) ok "live-iso-env — 재녹화 호출이 격리 폴더(gpt_independent.sh iso)의 HOME · CODEX_HOME 으로 돈다" ;;
    *) no "live-iso-env — 첫 호출 '${L1:-없음}' · $(tail -1 "$T/live.out" 2>/dev/null)" ;; esac
  case "$L1" in ""|*" DENY=0 SBX="*) no "live-iso-deny — 첫 호출의 config 에 권한 프로필 deny 줄이 없다: '${L1:-없음}'" ;;
    *) ok "live-iso-deny — 첫 호출의 config 에 권한 프로필 deny 줄이 있다" ;; esac
  case "$L1" in *" SBX=0") ok "live-iso-no-sandbox-mode — 재녹화 호출 인자에 sandbox_mode 가 없다(--config-permissions — 프로필 deny 를 덮지 않는다)" ;;
    *) no "live-iso-no-sandbox-mode — 첫 호출 '${L1:-없음}'" ;; esac
  LCWD="$(cat "$T/calls.txt.cwd" 2>/dev/null)"
  [ -n "$LCWD" ] && grep -qxF "\"$(cd "$R" && pwd -P)\" = \"deny\"" "$LCFG" 2>/dev/null && grep -qxF "\"$LCWD\" = \"read\"" "$LCFG" && grep -qxF "[projects.\"$LCWD\"]" "$LCFG" \
    && ok "live-iso-paths — 플러그인 트리(옛 기록 recorded/ 포함) deny · 재녹화 cwd(저장소 사본 실경로) read · 신뢰" \
    || no "live-iso-paths — 첫 호출의 config 에 플러그인 트리 deny · cwd '${LCWD:-없음}' read · 신뢰 중 빠진 것이 있다"
  LP="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1], encoding="utf-8")); print(d.get("codex_home"), d.get("iso_deny_paths"))' "$T/lrec/provenance.json" 2>/dev/null)"
  case "$LP" in "isolated "[1-9]*) ok "live-iso-provenance — 기록에 격리 증거(격리 config 의 deny 경로 $(printf '%s' "$LP" | cut -d' ' -f2)개)" ;;
    *) no "live-iso-provenance — 기록의 격리 표기 '${LP:-없음}'(자기 보고가 아니라 격리 config 의 deny 수여야 한다)" ;; esac
  [ "$LISO" = 1 ] && [ ! -e "$LI" ] && ok "live-iso-cleanup — 재녹화 뒤 격리 폴더가 남지 않는다" || no "live-iso-cleanup — 격리 폴더 '${LI:-없음}' 가 남았거나 격리가 아니다"
fi

# ⑤ iso 사전 게이트 — 가짜 HOME(.claude 만) · 실제 GPT 홈 대신 임시 인증 파일(CODEX_HOME) · 이 러너의 임시 폴더($T) 안 TMPDIR 로
#    iso 를 부른다(모델 호출 없음). 인증이 있어도 두 게이트가 먼저 멈추는지 본다.
#    ⛔ iso 의 로그인 판정(래퍼 auth-check)은 CLI 의 login status 를 묻는다 — 실제 CLI 를 부르지 않게 셀마다 PATH 앞에 가짜 CLI(../_shim) 를 두고
#       API 키 env · FZ_SHIM_LOGIN · 세션 선택 폴더를 셀이 정한다(사용자 env 가 셀에 새지 않게)
#    ⛔ 지우는 격리 폴더는 iso 가 stdout 으로 돌려준 경로 하나뿐이다(cleanup --iso) — 나머지는 $T 와 함께 지워진다
if [ "$LIVE" -eq 0 ] && [ -z "${FZ_SC_MODULE:-}" ]; then
  IH="$T/ih"
  mkdir -p "$IH/.claude/tmp" "$IH/.claude/projects/p" "$T/igh" "$T/it-repo" "$T/it-ok" "$T/irepo"; echo '{"fake":"auth"}' > "$T/igh/auth.json"
  SHIMP="$R/tests/fixtures/gpt/_shim:$PATH"
  isoenv() { env -u OPENAI_API_KEY -u CODEX_API_KEY -u FZ_SHIM_LOGIN -u FZ_AUTONOMY PATH="$SHIMP" FZ_GPT_CHOICE_DIR="$T/iso-sel" CLAUDE_CODE_SESSION_ID=iso-sid "$@"; }
  iso_run() {   # $1 = TMPDIR · 나머지 = iso 인자 → $T/iso.out(stdout) · $T/iso.err · 종료값 · IHOME = 가짜 HOME(기본 $IH)
    local tmp="$1"; shift
    isoenv HOME="${IHOME:-$IH}" CODEX_HOME="$T/igh" TMPDIR="$tmp" bash "$R/scripts/gpt_independent.sh" iso "$@" > "$T/iso.out" 2> "$T/iso.err"
  }
  isos() { find "$1" -maxdepth 1 -name 'fz-gpt-iso.*' 2>/dev/null | wc -l | tr -d ' '; }
  iso_run "$IH/.claude/tmp"; IRC=$?
  [ "$IRC" = 11 ] && [ ! -s "$T/iso.out" ] && grep -qF '격리 폴더가 ~/.claude 아래에 생긴다' "$T/iso.err" && [ "$(isos "$IH/.claude/tmp")" = 0 ] \
    && ok "iso-claude-tmpdir-refused — TMPDIR 이 ~/.claude 아래면 iso 도 메인 경로처럼 exit 11 · 빈 stdout · 격리 폴더를 만들지 않는다" \
    || no "iso-claude-tmpdir-refused — exit $IRC · stdout '$(cat "$T/iso.out")' · 격리 폴더 $(isos "$IH/.claude/tmp")개 · $(tail -1 "$T/iso.err")"
  iso_run "$T/it-repo" --repo "$IH/.claude/projects/p"; IRC=$?
  [ "$IRC" = 15 ] && [ ! -s "$T/iso.out" ] && grep -qF '허용 목록 밖 입력 — 독립 첫 패스가 아니다' "$T/iso.err" && [ "$(isos "$T/it-repo")" = 0 ] \
    && ok "iso-claude-repo-refused — --repo 가 ~/.claude 아래면 iso 도 메인 경로처럼 exit 15 · 빈 stdout · 격리 폴더를 만들지 않는다" \
    || no "iso-claude-repo-refused — exit $IRC · stdout '$(cat "$T/iso.out")' · 격리 폴더 $(isos "$T/it-repo")개 · $(tail -1 "$T/iso.err")"
  # ~/.claude 가 링크인 가짜 HOME(대상은 같은 HOME 아래 claude-data) — 링크 경로로 적든 대상 경로로 적든 같은 금지 입력이다.
  #   ⛔ 막지 못해 만들어진 격리 폴더는 iso 가 stdout 으로 돌려준 경로로만 지운다(cleanup --iso)
  IL="$T/il"; mkdir -p "$IL/claude-data/projects/p" "$IL/dev/repo"; ln -s "$IL/claude-data" "$IL/.claude"
  iso_link_refused() {   # $1 = 셀 이름 · $2 = 경로 설명 · $3 = --repo 값
    local lt="$T/it-$1"; mkdir -p "$lt"
    IHOME="$IL" iso_run "$lt" --repo "$3"; IRC=$?
    [ "$IRC" = 15 ] && [ ! -s "$T/iso.out" ] && grep -qF '~/.claude 아래(에이전트 로그 · journal)' "$T/iso.err" && [ "$(isos "$lt")" = 0 ] \
      && ok "$1 — ~/.claude 가 링크면 --repo 를 $2로 적어도 exit 15 · 빈 stdout · 격리 폴더를 만들지 않는다" \
      || no "$1 — exit $IRC · stdout '$(cat "$T/iso.out")' · 격리 폴더 $(isos "$lt")개 · $(tail -1 "$T/iso.err")"
    IP="$(cat "$T/iso.out")"
    case "$IP" in "$(cd "$lt" && pwd -P)/fz-gpt-iso."??????) bash "$R/scripts/gpt_independent.sh" cleanup --iso "$IP" >/dev/null 2>&1 ;; esac
  }
  iso_link_refused iso-claude-link-repo-refused "링크 경로(~/.claude/…)" "$IL/.claude/projects/p"
  iso_link_refused iso-claude-link-target-repo-refused "링크 대상 경로" "$IL/claude-data/projects/p"
  mkdir -p "$T/it-lok"; IHOME="$IL" iso_run "$T/it-lok" --repo "$IL/dev/repo"; IRC=$?
  IP="$(cat "$T/iso.out")"
  case "$IRC:$(grep -c . "$T/iso.out"):$IP" in "0:1:$(cd "$T/it-lok" && pwd -P)/fz-gpt-iso."??????) [ -d "$IP/gpt-home" ] && IOK=1 || IOK=0 ;; *) IOK=0 ;; esac
  case "$IP" in "$(cd "$T/it-lok" && pwd -P)/fz-gpt-iso."??????) bash "$R/scripts/gpt_independent.sh" cleanup --iso "$IP" >/dev/null 2>&1 ;; esac
  [ "$IOK" = 1 ] && ok "iso-claude-link-control — ~/.claude 가 링크인 HOME 에서도 ~/.claude 밖 저장소면 exit 0 · 격리 폴더 경로 한 줄" \
    || no "iso-claude-link-control — exit $IRC · stdout '$IP' · $(tail -1 "$T/iso.err")"
  iso_run "$T/it-ok" --repo "$T/irepo"; IRC=$?
  IP="$(cat "$T/iso.out")"
  case "$IRC:$(grep -c . "$T/iso.out"):$IP" in "0:1:$(cd "$T/it-ok" && pwd -P)/fz-gpt-iso."??????) [ -d "$IP/gpt-home" ] && IOK=1 || IOK=0 ;; *) IOK=0 ;; esac
  case "$IP" in "$(cd "$T/it-ok" && pwd -P)/fz-gpt-iso."??????) bash "$R/scripts/gpt_independent.sh" cleanup --iso "$IP" >/dev/null 2>&1 ;; esac
  [ "$IOK" = 1 ] && ok "iso-gates-control — 같은 가짜 HOME 에서 ~/.claude 밖 자리 · 저장소면 exit 0 · 격리 폴더 경로 한 줄" \
    || no "iso-gates-control — exit $IRC · stdout '$IP' · $(tail -1 "$T/iso.err")"
  # 인증 파일 없음 — 격리 홈은 실제 CLI 홈의 auth.json 을 링크해서 돈다. 없으면 메인 경로처럼 GPT 미사용(18 · GPT-OFF)이고 자리 게이트(11)보다 먼저다
  #   (TMPDIR 이 ~/.claude 아래여도 18) · API 키 env 가 있어도 같다 · 빈 stdout · 격리 폴더 0개
  mkdir -p "$T/igh-none" "$T/it-na"
  isoenv HOME="$IH" CODEX_HOME="$T/igh-none" TMPDIR="$IH/.claude/tmp" OPENAI_API_KEY=sk-test-synthetic bash "$R/scripts/gpt_independent.sh" iso --repo "$T/irepo" > "$T/iso.out" 2> "$T/iso.err"; IRC=$?
  isoenv HOME="$IH" CODEX_HOME="$T/igh-none" TMPDIR="$T/it-na" bash "$R/scripts/gpt_independent.sh" iso --repo "$T/irepo" > "$T/iso2.out" 2> "$T/iso2.err"; IRC2=$?
  [ "$IRC:$IRC2" = "18:18" ] && [ ! -s "$T/iso.out" ] && [ ! -s "$T/iso2.out" ] && grep -q '^GPT-OFF: 인증 파일 없음(격리 첫 패스) — ' "$T/iso.err" \
    && [ "$(isos "$IH/.claude/tmp"):$(isos "$T/it-na")" = "0:0" ] \
    && ok "iso-no-auth-file-off — 인증 파일이 없으면 iso 도 메인 경로처럼 exit 18 · 'GPT-OFF: 인증 파일 없음(격리 첫 패스)' · 자리 게이트(11)보다 먼저 · 빈 stdout · 격리 폴더 0" \
    || no "iso-no-auth-file-off — exit $IRC · $IRC2 · stdout '$(cat "$T/iso.out" "$T/iso2.out")' · 격리 폴더 $(isos "$IH/.claude/tmp") · $(isos "$T/it-na")개 · $(tail -1 "$T/iso.err")"
  # GPT 미사용 순서 — 메인 경로와 같다: CLI 없음 · 사용자 선택 · 로그인 필요 · 인증 파일 없음(앞 사유가 이긴다). 셀마다 인증 파일이 없는
  #   CLI 홈 · 가짜 CLI(login status = FZ_SHIM_LOGIN) · 러너 임시 TMPDIR — 어느 사유든 18 · 빈 stdout · 격리 폴더 0
  iso_off() {   # $1 = 셀 · 나머지 = env 'NAME=값'(PATH 도 덮을 수 있다) → '종료값|GPT-OFF 사유|stdout 바이트|격리 폴더 수'
    local c="$1" t="$T/it-off-$1"; shift; mkdir -p "$t"
    isoenv HOME="$IH" CODEX_HOME="$T/igh-none" TMPDIR="$t" "$@" bash "$R/scripts/gpt_independent.sh" iso --repo "$T/irepo" > "$T/iso-$c.out" 2> "$T/iso-$c.err"
    printf '%s|%s|%s|%s' "$?" "$(grep -m1 '^GPT-OFF: ' "$T/iso-$c.err" | sed 's/ — .*//')" "$(wc -c < "$T/iso-$c.out" | tr -d ' ')" "$(isos "$t")"
  }
  NOCLIP=""; for d in $(printf '%s' "$PATH" | tr ':' ' '); do [ -x "$d/codex" ] || NOCLIP="${NOCLIP:+$NOCLIP:}$d"; done   # CLI 가 든 폴더를 뺀 PATH
  mkdir -p "$T/iso-sel"; printf 'model=off\neffort=off\n' > "$T/iso-sel/iso-off"
  for row in "iso-not-signed-in-login-needed|FZ_SHIM_LOGIN=1|GPT-OFF: 로그인 필요|login status 1 · 인증 파일 · 키 없음" \
             "iso-signed-in-no-auth-file|FZ_SHIM_LOGIN=0|GPT-OFF: 인증 파일 없음(격리 첫 패스)|login status 0 · 인증 파일 없음" \
             "iso-key-only-no-auth-file|FZ_SHIM_LOGIN=1 OPENAI_API_KEY=sk-test-synthetic|GPT-OFF: 인증 파일 없음(격리 첫 패스)|API 키만(login status 1) · 인증 파일 없음" \
             "iso-cli-missing-off|PATH=$NOCLIP|GPT-OFF: CLI 없음|CLI 없음 · 인증 파일 · 키 없음" \
             "iso-user-choice-off|FZ_SHIM_LOGIN=1 CLAUDE_CODE_SESSION_ID=iso-off|GPT-OFF: 사용자 선택|세션 선택 off · login status 1 · 인증 파일 없음"; do
    IFS='|' read -r cn ce cw cd_ <<< "$row"
    got="$(iso_off "$cn" $ce)"   # ce = 셀이 정한 'NAME=값' 낱말들(공백으로 나눈다)
    [ "$got" = "18|$cw|0|0" ] && ok "$cn — $cd_ → exit 18 · '$cw' · 빈 stdout · 격리 폴더 0" || no "$cn — $cd_ → 기대 '18|$cw|0|0' · 실제 '$got'"
  done
fi

echo
[ "$fail" -eq 0 ] && echo "sprint-contract-format: 전건 통과" || echo "sprint-contract-format: 실패 있음"
exit "$fail"
