#!/bin/bash
# Sprint Contract 형식 러너 (S12) — fz-architect 로 Sprint Contract 를 만들 때(modules/sprint-contract.md 절차 2) SC 산출 형식이 유지되는가.
#
# 기본 모드(게이트) — GPT 를 부르지 않는다. 결정론이다.
#   ① 조립: --live 와 같은 함수로 과제 프롬프트를 만들고 래퍼(--inject-skill) + 가짜 CLI(../_shim/codex)로 캡처한다
#      → architect 본문 1회 · SC 스키마 키 전부 · 요구 원문
#   ② 우선: fz-architect 본문에 '과제 형식이 이긴다' 규칙과 SC 키 이름이 있다 — 없으면 본문의 검증 형식이 SC 형식을 덮는다
#   ③ 기록: recorded/sc-output.yaml 이 SC 스키마 키를 갖고, recorded/provenance.json 의 architect 본문·과제 프롬프트 해시가 지금과 같다
#      ⛔ 기록이 없거나 해시가 다르면 FAIL 이다 — 옛 기록으로 통과시키지 않는다. `--live` 로 다시 기록한다
# --live — 실제 GPT CLI 1회(effort high · read-only)로 기록을 새로 만든 뒤 기본 모드를 돈다. 사람이 부른다(게이트는 부르지 않는다)
#
# ⛔ 필수 키는 여기 적지 않는다 — modules/sprint-contract.md 의 스키마 블록에서 읽는다(형식 정본이 한 곳이다)
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
MOD="$R/modules/sprint-contract.md"
REC="$HERE/recorded"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

fail=0
ok() { echo "PASS  $1"; }
no() { echo "FAIL  $1"; fail=1; }

# 스키마 블록(## Sprint Contract Schema 아래 첫 ```yaml 펜스)을 파일로 뽑는다 — 과제 프롬프트와 키 목록의 단일 출처
python3 - "$MOD" "$T/schema.yaml" <<'PY' || { echo "UNRUN: sprint-contract.md 에서 스키마 블록을 찾지 못했다"; exit 2; }
import re, sys
s = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"^## Sprint Contract Schema\s*\n+```yaml\n(.*?)\n```", s, re.S | re.M)
if not m:
    sys.exit(1)
open(sys.argv[2], "w", encoding="utf-8").write(m.group(1) + "\n")
PY

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
  env FZ_TELEMETRY_DIR="$T/tel" bash "$R/scripts/gpt-exec.sh" exec --cd "$T/repo" --out "$T/live.yaml" --prompt-file "$T/task.txt" \
    --effort high --gpt-skill architect --inject-skill "$ARCH" || { echo "FAIL  --live: 래퍼 exit $? (기록하지 않는다)"; exit 1; }
  check_format "$T/live.yaml" >/dev/null || { echo "FAIL  --live: 산출물이 SC 형식이 아니다 — $(check_format "$T/live.yaml")"; cp "$T/live.yaml" "$REC/sc-output.rejected.yaml"; exit 1; }
  cp "$T/live.yaml" "$REC/sc-output.yaml"
  python3 - "$REC/provenance.json" "$(sha "$ARCH")" "$(sha "$T/task.txt")" "$(codex --version 2>/dev/null | head -1)" <<'PY'
import datetime, json, os, sys
json.dump({"architect_sha256_16": sys.argv[2], "task_sha256_16": sys.argv[3], "cli_version": sys.argv[4], "effort": "high",
           "codex_home": "isolated" if os.environ.get("CODEX_HOME") else "default",
           "recorded": datetime.date.today().isoformat(), "note": "run.sh --live 가 쓴다 — 손으로 고치지 않는다"},
          open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
PY
  echo "기록: $REC/sc-output.yaml · provenance.json"
fi

# ① 조립 — 래퍼 + 가짜 CLI
env PATH="$R/tests/fixtures/gpt/_shim:$PATH" FZ_SHIM_CAPTURE="$T/argv.json" FZ_SHIM_OUTPUT="sprint_id: x" FZ_TELEMETRY_DIR="$T/tel-shim" \
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

echo
[ "$fail" -eq 0 ] && echo "sprint-contract-format: 전건 통과" || echo "sprint-contract-format: 실패 있음"
exit "$fail"
