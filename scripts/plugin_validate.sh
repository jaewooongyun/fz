#!/bin/bash
# scripts/plugin_validate.sh — 플러그인 검증 단일 지점 (A5-02). health-check 는 이 스크립트만 부른다.
#
# ⛔ 대상은 `.claude-plugin/plugin.json` 이다. 루트 디렉터리를 주면 CLI 가 **marketplace 매니페스트만**
#    검증해 스킬·에이전트 frontmatter 가 깨져도 통과한다(실측 2026-09-26).
# ⛔ plugin.json 대상은 YAML 파싱 실패를 오류(exit 1)로 잡지만, frontmatter 결손은 **경고**만 내고 exit 0 이다
#    (실측: 파일 전체를 `---` / `name: [broken` / `---` 로 바꾸면 스킬·에이전트 모두 "No description in frontmatter" 경고).
#    그래서 JSON 보고서를 읽어 오류 또는 **허용 목록 밖 경고**가 있으면 실패로 본다. 허용 목록은 루트 CLAUDE.md 경고 1종뿐이다(개발용 문서라 의도된 경고).
#    CLI 의 엄격 모드는 이 경고까지 실패로 만들어 쓰지 않는다.
# ⛔ 새 경고가 생기면 실패한다(fail-closed) — 고치거나, 의도된 것이면 ALLOWED 에 근거와 함께 더한다.
#
# usage: plugin_validate.sh [PLUGIN_ROOT] | --self-test | --self-test-cli(실 CLI 음성 대조 — 게이트 전용, 아래)
# exit: 0=통과 · 1=오류 또는 허용 밖 경고 · 2=미실행(claude CLI 부재·매니페스트 없음·보고서 해석 불가)
set -u
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# $1=CLI exit · $2=JSON 보고서 · $3=경로 표시에서 벗길 루트
judge() {
  VAL_JSON="$2" python3 - "$1" "$3" <<'PY'
import json, os, sys
code = sys.argv[1]
# CLI 는 실제 경로를 보고한다(macOS 임시 폴더 /var → /private/var) — 두 형태를 접두사로 벗긴다
roots = sorted({sys.argv[2].rstrip("/") + "/", os.path.realpath(sys.argv[2]).rstrip("/") + "/"}, key=len, reverse=True)
# ⛔ 허용은 (파일 · path · 문장 접두) 셋이 모두 맞을 때만 — 파일을 안 보면 다른 파일의 같은 경고가 섞여 통과한다(GPT R-A 검토 006)
ALLOWED = [("CLAUDE.md", "root", "CLAUDE.md at the plugin root is not loaded as project context")]
rel = lambda f: next((str(f)[len(r):] for r in roots if str(f).startswith(r)), str(f))
try:
    d = json.loads(os.environ.get("VAL_JSON", ""))
    man = d["manifest"]
    contents = d["contents"]
except (ValueError, KeyError, TypeError) as e:
    print(f"UNRUN: 검증 보고서를 해석하지 못했다 (CLI exit {code}) — {type(e).__name__}")
    sys.exit(2)
# ⛔ 대상이 요청한 plugin 매니페스트인지 확인한다 — 다른 매니페스트를 검증하고 contents 가 비어도 통과하던 경로(검토 007)
if rel(man.get("file", "")) != ".claude-plugin/plugin.json" or man.get("type") != "plugin" or not isinstance(contents, list):
    print(f"UNRUN: 보고서가 plugin.json 검증이 아니다 (manifest={rel(man.get('file', ''))} · type={man.get('type')} · contents={type(contents).__name__})")
    sys.exit(2)
bad, canary = [], False
for e in [man] + contents:
    f = rel(e.get("file", "?"))
    for x in e.get("errors") or []:
        bad.append(f"오류 {f} :: {x.get('path')} :: {x.get('message')}")
    for x in e.get("warnings") or []:
        if any(f == af and x.get("path") == p and str(x.get("message", "")).startswith(m) for af, p, m in ALLOWED):
            canary = True
            continue
        bad.append(f"경고 {f} :: {x.get('path')} :: {x.get('message')}")
if code not in ("0", "1"):
    print(f"UNRUN: CLI exit {code}")
    sys.exit(2)
# ⛔ 알려진 경고(루트 CLAUDE.md)는 **카나리아**다 — 없으면 CLI 가 내용을 검사하지 않은 보고서일 수 있다(2라운드 006)
if not bad and not canary:
    print("UNRUN: 알려진 경고(루트 CLAUDE.md)가 보고서에 없다 — CLI 가 내용을 검사하지 않았을 수 있다")
    sys.exit(2)
if code == "1" and not bad:
    print("UNRUN: CLI 는 exit 1 인데 보고서에 오류·허용 밖 경고가 없다 — 해석 불일치")
    sys.exit(2)
for b in bad:
    print(f"  FAIL {b}")
print(f"plugin_validate: {'실패 ' + str(len(bad)) + '건' if bad else '통과'} (대상 plugin.json · 허용 경고 {len(ALLOWED)}종)")
sys.exit(1 if bad else 0)
PY
}

if [ "${1:-}" = "--self-test" ]; then
  ok=0 n=0
  t() { n=$((n + 1)); judge "$2" "$3" "/r" >/dev/null 2>&1; [ $? -eq "$4" ] && ok=$((ok + 1)) || echo "  FAIL self-test: $1"; }
  M='"manifest":{"file":"/r/.claude-plugin/plugin.json","type":"plugin","errors":[],"warnings":[]}'
  MM='"manifest":{"file":"/r/.claude-plugin/marketplace.json","type":"marketplace","errors":[],"warnings":[]}'
  OW='{"file":"/r/skills/a/CLAUDE.md","errors":[],"warnings":[{"path":"root","message":"CLAUDE.md at the plugin root is not loaded as project context. x"}]}'
  CW='{"file":"/r/CLAUDE.md","errors":[],"warnings":[{"path":"root","message":"CLAUDE.md at the plugin root is not loaded as project context. x"}]}'
  SW='{"file":"/r/skills/a/SKILL.md","errors":[],"warnings":[{"path":"description","message":"No description in frontmatter."}]}'
  SE='{"file":"/r/agents/b.md","errors":[{"path":"name","message":"bad"}],"warnings":[]}'
  t "허용 경고만 → 통과" 0 "{$M,\"contents\":[$CW]}" 0
  t "허용 밖 경고(깨진 frontmatter) → 실패" 0 "{$M,\"contents\":[$CW,$SW]}" 1
  t "오류 → 실패" 1 "{$M,\"contents\":[$SE]}" 1
  t "보고서 해석 불가 → 미실행" 0 "not json" 2
  t "exit 1 인데 오류 0 → 미실행" 1 "{$M,\"contents\":[$CW]}" 2
  t "다른 파일의 같은 경고 → 실패" 0 "{$M,\"contents\":[$CW,$OW]}" 1
  t "대상이 marketplace 매니페스트 → 미실행" 0 "{$MM,\"contents\":[]}" 2
  t "contents 없음 → 미실행" 0 "{$M}" 2
  t "contents 비었고 오류 없음(카나리아 없음) → 미실행" 0 "{$M,\"contents\":[]}" 2
  echo "plugin_validate self-test $ok/$n passed"
  [ "$ok" -eq "$n" ] && exit 0 || exit 1
fi

# --self-test-cli — 실 claude CLI 음성 대조(F-335 ⑭). --self-test 는 judge 에 보고서 문자열만 넣는다 — CLI 가 보고서 형식 · exit 를
#   바꾸면 그쪽은 그대로 통과한다. 여기서는 합성 플러그인 4종을 아래 본 경로와 **같은** 실 CLI 호출 → judge 로 돌려 기대 exit 와 대조한다.
#   cli-clean 0 · cli-broken-frontmatter 1(그 파일이 FAIL 줄에) · cli-broken-manifest 1(name 이 숫자 — 스키마 오류) · cli-no-canary 2
#   (CLI 2.1.292 관찰). ⛔ 외부 실증이라 health-check 는 부르지 않는다 — tests/fixtures/plugin/validate-cli/external.sh(게이트 전용)가 부른다.
#   ⛔ 설정은 임시 CLAUDE_CONFIG_DIR 에서 쓴다(호출자가 주지 않으면 임시 폴더 안에 만든다) — 사용자 설정을 건드리지 않는다.
#   출력: 첫 줄 `SELF-TEST-CLI claude=<버전>` · 셀마다 `CELL <이름> exit=<판정 exit> want=<기대> PASS|FAIL` · 끝 줄 요약.
#   exit: 0 전건 일치 · 1 불일치 · 2 claude CLI 부재(UNRUN)
if [ "${1:-}" = "--self-test-cli" ]; then
  command -v claude >/dev/null 2>&1 || { echo "UNRUN: claude CLI 부재"; exit 2; }
  # ⛔ mktemp 결과를 따로 받는다 — 치환을 바로 cd 에 넘기면 실패해도 `cd ""` 가 성공한다(F-355)
  W="$(mktemp -d "${TMPDIR:-/tmp}/fz-plugin-validate-cli.XXXXXX")" || { echo "UNRUN: 임시 폴더를 만들지 못했다"; exit 2; }
  trap 'rm -rf "${W:?}"' EXIT
  if [ -z "${CLAUDE_CONFIG_DIR:-}" ]; then mkdir -p "$W/config" && export CLAUDE_CONFIG_DIR="$W/config"; fi
  VER="$(claude --version 2>/dev/null | sed -n '1s/^\([0-9][0-9.]*\).*/\1/p')"
  echo "SELF-TEST-CLI claude=${VER:-unknown}"
  GOOD='{"name":"probe","version":"0.0.1","description":"probe plugin","author":{"name":"probe"}}'
  SKILL='---
name: a
description: probe skill
---

# a
'
  mk() {   # $1 이름 · $2 plugin.json · $3 루트 CLAUDE.md(1|0) · $4 SKILL.md 본문
    mkdir -p "$W/$1/.claude-plugin" "$W/$1/skills/a" || return 1
    printf '%s\n' "$2" > "$W/$1/.claude-plugin/plugin.json"
    [ "$3" = 1 ] && printf '# probe\n' > "$W/$1/CLAUDE.md"
    printf '%s' "$4" > "$W/$1/skills/a/SKILL.md"
  }
  mk cli-clean "$GOOD" 1 "$SKILL" && mk cli-broken-frontmatter "$GOOD" 1 '---
name: [broken
---
' && mk cli-broken-manifest '{"name":123,"version":"0.0.1","description":"probe plugin","author":{"name":"probe"}}' 1 "$SKILL" \
    && mk cli-no-canary "$GOOD" 0 "$SKILL" || { echo "UNRUN: 합성 플러그인을 만들지 못했다"; exit 2; }
  ok=0 n=0
  for c in cli-clean:0 cli-broken-frontmatter:1 cli-broken-manifest:1 cli-no-canary:2; do
    name="${c%%:*}" want="${c##*:}" n=$((n + 1))
    OUT="$(cd "$W/$name" && claude plugin validate --json .claude-plugin/plugin.json 2>/dev/null)"; CODE=$?
    J="$(judge "$CODE" "$OUT" "$W/$name" 2>&1)"; got=$?
    pass=1
    [ "$got" = "$want" ] || pass=0
    if [ "$name" = cli-broken-frontmatter ]; then printf '%s\n' "$J" | grep -q 'FAIL .*skills/a/SKILL.md' || pass=0; fi
    if [ "$pass" = 1 ]; then ok=$((ok + 1)); echo "CELL $name exit=$got want=$want PASS"; else
      echo "CELL $name exit=$got want=$want FAIL (cli exit $CODE · $(printf '%s' "$J" | tail -1 | cut -c1-160))"; fi
  done
  echo "plugin_validate self-test-cli $ok/$n passed (claude ${VER:-unknown})"
  [ "$ok" -eq "$n" ] && exit 0 || exit 1
fi

ROOT="${1:-$(cd "$SELF_DIR/.." && pwd)}"
command -v claude >/dev/null 2>&1 || { echo "UNRUN: claude CLI 부재"; exit 2; }
[ -f "$ROOT/.claude-plugin/plugin.json" ] || { echo "UNRUN: 매니페스트 없음 — $ROOT/.claude-plugin/plugin.json"; exit 2; }
OUT="$(cd "$ROOT" && claude plugin validate --json .claude-plugin/plugin.json 2>/dev/null)"; CODE=$?
judge "$CODE" "$OUT" "$ROOT"
