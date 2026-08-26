# `git diff --numstat` 대체 — patch 파일에서 파일별 추가·삭제 행을 센다.
#
# diff-parse: hunk-state — `h` 플래그로 hunk 안팎을 가른다.
#
# 왜 파일로 빼는가: PR 경로는 로컬 ref 가 없어 `git diff --numstat` 이 **항상 실패**한다 →
# 이 폴백이 매번 돈다. 인라인 awk 는 테스트가 불가능했고, 실제로 두 가지를 잃고 있었다.
#
# ⛔ hunk 상태(h)를 추적한다. `+++`·`+`·`-` 는 hunk **안팎**에서 뜻이 다르다.
#    상태 없이 접두사만 보면 파일 헤더를 추가 행으로 세고 귀속도 엉킨다.
# ⛔ `/^\+[^+]/` 같은 "둘째 글자" 조건을 쓰지 않는다. 두 가지를 통째로 잃는다:
#      · 빈 추가 행 (`+` 단독) — 둘째 글자가 없어 매칭 실패
#      · `++ actor` 를 추가한 행 (`++…`) — diff 를 담은 diff 에서 나온다
#    변경 규모는 auto-tier 입력이므로, 과소계상은 **낮은 Tier 로 기울게** 만든다.
# ⛔ addition·deletion 키의 **합집합**을 순회한다. `for(k in a)` 만 돌면 삭제만 있는 파일이 빠진다.
#
# 출력: 추가<TAB>삭제<TAB>경로  (git --numstat 형식)
/^diff --git /  { h = 0; next }
!h && /^\+\+\+ /{ f = $2; next }
/^@@/           { h = 1; next }
h && /^\+/      { a[f]++ }
h && /^-/       { d[f]++ }
END {
  for (k in a) seen[k]
  for (k in d) seen[k]
  for (k in seen) print (a[k] + 0) "\t" (d[k] + 0) "\t" k
}
