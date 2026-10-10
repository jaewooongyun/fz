# `git diff --numstat` 대체 — patch 파일에서 파일별 추가·삭제 행을 센다.
#
# diff-parse: hunk-state — `h` 플래그로 hunk 안팎을 가른다.
#
# 왜 파일로 빼는가: gather.sh 의 **유일한 numstat 출처**다(PR · 브랜치 모두 diff.patch 에서 센다 —
# `git diff --numstat <base>...<PR번호>` 는 PR 번호를 SHA 접두로 풀어 exit 0 으로 틀린다 · F-135 · F-350).
# 인라인 awk 는 테스트가 불가능했고, 실제로 두 가지를 잃고 있었다.
#
# ⛔ hunk 상태(h)를 추적한다. `+++`·`+`·`-` 는 hunk **안팎**에서 뜻이 다르다.
#    상태 없이 접두사만 보면 파일 헤더를 추가 행으로 세고 귀속도 엉킨다.
# ⛔ `/^\+[^+]/` 같은 "둘째 글자" 조건을 쓰지 않는다. 두 가지를 통째로 잃는다:
#      · 빈 추가 행 (`+` 단독) — 둘째 글자가 없어 매칭 실패
#      · `++ actor` 를 추가한 행 (`++…`) — diff 를 담은 diff 에서 나온다
#    변경 규모는 auto-tier 입력이므로, 과소계상은 **낮은 Tier 로 기울게** 만든다.
# ⛔ addition·deletion 키의 **합집합**을 순회한다. `for(k in a)` 만 돌면 삭제만 있는 파일이 빠진다.
# ⛔ 파일 키는 `diff --git a/X b/X` 헤더 기준이다(F-381 · risk_scan.py `_header_path` 와 같은 규칙).
#    삭제 파일은 `+++ /dev/null` 이라 `+++` 둘째 토큰으로 키잉하면 삭제 파일이 전부 '/dev/null' 한 키로 모인다.
#    헤더 가운데 공백으로 가르므로 공백이 든 경로도 풀린다(`+++` 의 `$2` 는 공백에서 잘린다 — 줄 끝 탭도 뗀다).
#    개명은 헤더 양쪽이 달라 `+++ b/새경로` 를 쓴다. 헤더를 못 풀면(대칭 아님) 예전처럼 '/dev/null' 로 모은다 — 행은 잃지 않는다.
#    소비처(gather.sh 요약 · F-350 대조)는 **합계만** 본다(IR7) — 키는 `b/…` 꼴 그대로다.
#
# 출력: 추가<TAB>삭제<TAB>경로  (git --numstat 열 순서 · 경로는 `b/…` 꼴)
function header_b(rest,   n, mid, a, b) {
  n = length(rest)
  if (n % 2 == 0) return ""
  mid = (n + 1) / 2
  if (substr(rest, mid, 1) != " ") return ""
  a = substr(rest, 1, mid - 1); b = substr(rest, mid + 1)
  if (a == b) return b
  if (substr(a, 1, 2) == "a/" && substr(b, 1, 2) == "b/" && substr(a, 3) == substr(b, 3)) return b
  if (substr(a, 1, 3) == "\"a/" && substr(b, 1, 3) == "\"b/" && substr(a, 4) == substr(b, 4)) return b
  return ""
}
/^diff --git /  { h = 0; hb = header_b(substr($0, 12)); next }
!h && /^\+\+\+ /{ f = substr($0, 5); sub(/\t$/, "", f); if (f == "/dev/null" && hb != "") f = hb; next }
/^@@/           { h = 1; next }
h && /^\+/      { a[f]++ }
h && /^-/       { d[f]++ }
END {
  for (k in a) seen[k]
  for (k in d) seen[k]
  for (k in seen) print (a[k] + 0) "\t" (d[k] + 0) "\t" k
}
