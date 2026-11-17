#!/bin/bash
# diff-parse: not-a-diff — `^---` 정규식은 SKILL.md frontmatter 의 경계 줄을 찾는다. diff 를 다루지 않는다.
# 증거 profile 회귀 판정 (F-534 · F-009 · 승격 원장 D-1) — check_evidence_slots.py --profile 을 실제 CLI 로 돌린다.
#
# D-1: 에러 전파 경로를 중간 층을 읽지 않은 채 '확정' 으로 적었고, 그 층의 catch 가 nil 을 돌려 결론이 뒤집혔다(F-009).
#      주장의 층마다 코드 인용 · catch 층은 본문까지 인용해야 통과한다. 채점은 따로 — 양성(TP)은 잡고 음성(FP)은 통과시킨다.
# 셀:
#   r3-f009-d1-middle-catch-uncited-fails  TP ① 중간 catch 층 인용 없음 → exit 1 ② catch 머리만 인용 → exit 1
#                                          ③' do 블록만 인용(`do { try x() } catch let e`) → exit 1
#                                          FP ③ catch 부수효과(nil 반환)가 결론을 뒤집는 체인을 층마다 인용 → exit 0
#                                             ④ 실제 전파(catch 가 다시 던짐) 체인을 층마다 인용 → exit 0
#   f534-skill-wiring                      fz-plan · fz-discover · fz-fix SKILL.md 가 첫 단계에서 profile 검사를 부른다
#   toolstate-tail-cli                     tools.md 첫 줄의 선택 도구 꼬리 — 꼬리 붙은 줄 → exit 0 · 꼬리 없는 줄 · 둘째 줄의 꼬리 → exit 1
#   toolstate-skill-notice                 frontmatter allowed-tools 에 선택 도구(Serena · context7 · sequential-thinking)가 있는
#                                          스킬마다 `선택 도구 상태` 줄이 형식 모듈 경로를 같이 적고, 꼬리 문법은 그 모듈 한 곳에만 있다
#                                          (다른 modules · SKILL.md 에 사본이 있으면 FAIL)
# exit: 0 통과 · 1 단언 실패 · 3 준비 실패
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HERE/../../../.."
CHK="$ROOT/scripts/check_evidence_slots.py"
[ -f "$CHK" ] || { echo "SETUP check_evidence_slots.py 를 찾을 수 없다: $CHK"; exit 3; }
T="$(mktemp -d "${TMPDIR:-/tmp}/fz-evidence-profiles.XXXXXX")" || exit 3
trap 'rm -rf "$T"' EXIT

mk() {   # $1 이름 · $2 error-paths.md 본문
  mkdir -p "$T/$1/evidence" || exit 3
  printf '[Serena 미사용 — 비 git 작업 폴더] · context7 목록✓ · sc 목록✓\n' > "$T/$1/evidence/tools.md"
  printf '%s\n' "$2" > "$T/$1/evidence/error-paths.md"
}
L1='- 층 1 NetworkClient.request: Sources/Net/Client.swift:42 `throw NetworkError.timeout`'
L3='- 층 3 OrderViewModel.start: Sources/UI/OrderViewModel.swift:30 `catch let e as OrderError { show(e) }`'
mk tp-uncited "$(printf '## 주장: 타임아웃은 화면까지 OrderError 로 전파된다\n%s\n- 층 2 OrderManager.fetch: 미독 — catch 로 잡힌다고 봤다\n%s' "$L1" "$L3")"
mk tp-head "$(printf '## 주장: 타임아웃은 화면까지 OrderError 로 전파된다\n%s\n- 층 2 OrderManager.fetch: Sources/Core/OrderManager.swift:88 `catch let e as NetworkError`\n%s' "$L1" "$L3")"
mk tp-do "$(printf '## 주장: 타임아웃은 화면까지 OrderError 로 전파된다\n%s\n- 층 2 OrderManager.fetch: Sources/Core/OrderManager.swift:86 `do { try lower() } catch let e as NetworkError`\n%s' "$L1" "$L3")"
mk fp-flip "$(printf '## 주장: 타임아웃은 중간 층에서 nil 로 흡수돼 화면까지 오지 않는다\n%s\n- 층 2 OrderManager.fetch: Sources/Core/OrderManager.swift:88 `catch { return nil }`\n- 층 3 OrderViewModel.start: Sources/UI/OrderViewModel.swift:31 `guard let item = await manager.fetch() else { throw OrderError.empty }`' "$L1")"
mk fp-prop "$(printf '## 주장: 타임아웃은 화면까지 OrderError 로 전파된다\n%s\n- 층 2 OrderManager.fetch: Sources/Core/OrderManager.swift:88 `catch let e as NetworkError { throw OrderError.network(e) }`\n%s' "$L1" "$L3")"

run() { python3 -B "$CHK" --profile fix "$T/$1" > "$T/out.$1" 2>&1; echo $?; }
fail=""
r=$(run tp-uncited); { [ "$r" = 1 ] && grep -q '층 2 OrderManager.fetch 인용 없음' "$T/out.tp-uncited"; } || fail="$fail ①exit=$r"
r=$(run tp-head);    { [ "$r" = 1 ] && grep -q 'catch 본문 미인용' "$T/out.tp-head"; } || fail="$fail ②exit=$r"
r=$(run tp-do);      { [ "$r" = 1 ] && grep -q 'catch 본문 미인용' "$T/out.tp-do"; } || fail="$fail ②'exit=$r"
r=$(run fp-flip);    [ "$r" = 0 ] || fail="$fail ③exit=$r($(tr '\n' ' ' < "$T/out.fp-flip" | cut -c1-120))"
r=$(run fp-prop);    [ "$r" = 0 ] || fail="$fail ④exit=$r($(tr '\n' ' ' < "$T/out.fp-prop" | cut -c1-120))"
rc=0
if [ -z "$fail" ]; then echo "PASS  r3-f009-d1-middle-catch-uncited-fails  (TP 3/3 · FP 0/2)"; else echo "FAIL  r3-f009-d1-middle-catch-uncited-fails  —$fail"; rc=1; fi

miss=""
for s in fz-plan fz-discover fz-fix; do
  p="${s#fz-}"
  grep -q "check_evidence_slots.py\" --profile $p" "$ROOT/skills/$s/SKILL.md" || miss="$miss $s"
done
if [ -z "$miss" ]; then echo "PASS  f534-skill-wiring"; else echo "FAIL  f534-skill-wiring  — profile 검사 호출이 없다:$miss"; rc=1; fi

U='[Serena 미사용 — 비 git 작업 폴더]'
tl() {   # $1 이름 · $2 tools.md 본문(printf %b) → exit
  mkdir -p "$T/$1/evidence" || exit 3
  printf '%b\n' "$2" > "$T/$1/evidence/tools.md"
  python3 -B "$CHK" --profile discover "$T/$1" > "$T/out.$1" 2>&1; echo $?
}
fail=""
r=$(tl tail-ext "$U · context7 목록✗ · sc 목록✓ — 빠지는 단계: 라이브러리 문서 조회"); [ "$r" = 0 ] || fail="$fail ext=$r($(tr '\n' ' ' < "$T/out.tail-ext" | cut -c1-120))"
r=$(tl tail-none "$U");  { [ "$r" = 1 ] && grep -q '선택 도구 상태' "$T/out.tail-none"; } || fail="$fail nostate=$r"
r=$(tl tail-second "$U\\ncontext7 목록✗ · sc 목록✓ — 빠지는 단계: 문서 조회"); [ "$r" = 1 ] || fail="$fail second=$r"
if [ -z "$fail" ]; then echo "PASS  toolstate-tail-cli"; else echo "FAIL  toolstate-tail-cli  —$fail"; rc=1; fi

FMT="modules/tool-status.md"
miss="" n=0
for f in "$ROOT"/skills/*/SKILL.md; do
  awk 'NR==1 && /^---/ {f=1; next} f && /^---/ {exit} f' "$f" | grep -qE 'mcp__[A-Za-z0-9_]*(serena|context7|sequential)' || continue
  n=$((n + 1))
  grep -F '선택 도구 상태' "$f" | grep -qF "$FMT" || miss="$miss $(basename "$(dirname "$f")")"
done
grep -qF 'context7 목록✓|목록✗ · sc 목록✓|목록✗' "$ROOT/$FMT" || miss="$miss $FMT(꼬리 문법 없음)"
for f in "$ROOT"/modules/*.md "$ROOT"/skills/*/SKILL.md; do
  [ "$f" = "$ROOT/$FMT" ] && continue
  grep -qF 'context7 목록✓|목록✗ · sc 목록✓|목록✗' "$f" && miss="$miss 형식사본:${f#"$ROOT"/}"
done
if [ "$n" -gt 0 ] && [ -z "$miss" ]; then echo "PASS  toolstate-skill-notice  (스킬 $n)"
else echo "FAIL  toolstate-skill-notice  — 선택 도구 스킬 $n · 고지 줄(형식 $FMT)이 없다:$miss"; rc=1; fi
[ "$rc" = 0 ] && echo "EVIDENCE_PROFILES_OK"
exit "$rc"
