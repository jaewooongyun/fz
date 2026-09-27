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
# usage: plugin_validate.sh [PLUGIN_ROOT] | --self-test
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

ROOT="${1:-$(cd "$SELF_DIR/.." && pwd)}"
command -v claude >/dev/null 2>&1 || { echo "UNRUN: claude CLI 부재"; exit 2; }
[ -f "$ROOT/.claude-plugin/plugin.json" ] || { echo "UNRUN: 매니페스트 없음 — $ROOT/.claude-plugin/plugin.json"; exit 2; }
OUT="$(cd "$ROOT" && claude plugin validate --json .claude-plugin/plugin.json 2>/dev/null)"; CODE=$?
judge "$CODE" "$OUT" "$ROOT"
