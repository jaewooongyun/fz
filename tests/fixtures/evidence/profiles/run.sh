#!/bin/bash
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
  printf '[Serena 미사용 — 비 git 작업 폴더]\n' > "$T/$1/evidence/tools.md"
  printf '%s\n' "$2" > "$T/$1/evidence/error-paths.md"
}
L1='- 층 1 NetworkClient.request: Sources/Net/Client.swift:42 `throw NetworkError.timeout`'
L3='- 층 3 DownloadViewModel.start: Sources/UI/DownloadViewModel.swift:30 `catch let e as DownloadError { show(e) }`'
mk tp-uncited "$(printf '## 주장: 타임아웃은 화면까지 DownloadError 로 전파된다\n%s\n- 층 2 DownloadManager.fetch: 미독 — catch 로 잡힌다고 봤다\n%s' "$L1" "$L3")"
mk tp-head "$(printf '## 주장: 타임아웃은 화면까지 DownloadError 로 전파된다\n%s\n- 층 2 DownloadManager.fetch: Sources/Core/DownloadManager.swift:88 `catch let e as NetworkError`\n%s' "$L1" "$L3")"
mk tp-do "$(printf '## 주장: 타임아웃은 화면까지 DownloadError 로 전파된다\n%s\n- 층 2 DownloadManager.fetch: Sources/Core/DownloadManager.swift:86 `do { try lower() } catch let e as NetworkError`\n%s' "$L1" "$L3")"
mk fp-flip "$(printf '## 주장: 타임아웃은 중간 층에서 nil 로 흡수돼 화면까지 오지 않는다\n%s\n- 층 2 DownloadManager.fetch: Sources/Core/DownloadManager.swift:88 `catch { return nil }`\n- 층 3 DownloadViewModel.start: Sources/UI/DownloadViewModel.swift:31 `guard let item = await manager.fetch() else { throw DownloadError.empty }`' "$L1")"
mk fp-prop "$(printf '## 주장: 타임아웃은 화면까지 DownloadError 로 전파된다\n%s\n- 층 2 DownloadManager.fetch: Sources/Core/DownloadManager.swift:88 `catch let e as NetworkError { throw DownloadError.network(e) }`\n%s' "$L1" "$L3")"

run() { python3 -B "$CHK" --profile fix "$T/$1" > "$T/out.$1" 2>&1; echo $?; }
fail=""
r=$(run tp-uncited); { [ "$r" = 1 ] && grep -q '층 2 DownloadManager.fetch 인용 없음' "$T/out.tp-uncited"; } || fail="$fail ①exit=$r"
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
[ "$rc" = 0 ] && echo "EVIDENCE_PROFILES_OK"
exit "$rc"
