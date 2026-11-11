#!/bin/bash
# 구현 단계 기각 위험 → PR 초안 이송 회귀 판정 (F-523) — check_pr_template.py --risks 를 실제 CLI 로 돌린다.
#
# 구현 중 Lead 가 "드문 경우"로 기각한 위험(기제 · 근거 · 재현 경로)이 Step 산출물 · PR 어디에도 남지 않아, 리뷰어가 다른
# 진입으로 같은 기제를 다시 찾아야 했다. fz-code 는 Step 산출물에 `## 기각한 위험` 절을 쓰고(없으면 `없음`), fz-pr 은 행마다
# ID 와 기제 이름을 PR 본문에 옮긴다. 이 검사가 그 이송을 잰다.
# 셀:
#   r3-f523-code-rejected-risk-reaches-pr  ① 위험 1 · PR 에 없음 → exit 1 · RISK-MISSING ② 옮긴 PR → exit 0
#                                          ③ 위험 없음(`없음`) → exit 0 ④ 위험 2 · 하나만 옮김 → exit 1 · 빠진 것만 보고
#                                          ⑤ 전용 절 없는 템플릿 · 다른 절에 옮김 → exit 0 ⑥ 절 없는 원천 → exit 2(대조 불가)
# exit: 0 통과 · 1 단언 실패 · 3 준비 실패
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHK="$HERE/../../../../scripts/check_pr_template.py"
[ -f "$CHK" ] || { echo "SETUP check_pr_template.py 를 찾을 수 없다: $CHK"; exit 3; }
T="$(mktemp -d "${TMPDIR:-/tmp}/fz-dismissed-risk.XXXXXX")" || exit 3
trap 'rm -rf "$T"' EXIT

RISK1='- `R-1` — 남은 후보(staleCandidate)가 전환 없는 크기 변경에 쓰인다 · 근거: 같은 크기 클래스 회전 뒤에만 남는다(드문 경우) · 재현: 회전 → 화면 밖 크기 변경 → 복귀'
RISK2='- `R-2` — 접힘 중 갱신이 버려진다 · 근거: 접힘 애니메이션 중에는 갱신이 오지 않는다 · 재현: 접기 시작 직후 목록 갱신'
printf '# Step S5\n\n## 바꾼 파일\n- a.swift\n\n## 기각한 위험\n%s\n' "$RISK1" > "$T/step-one.md"
printf '# Step S5\n\n## 기각한 위험\n%s\n%s\n' "$RISK1" "$RISK2" > "$T/step-two.md"
printf '# Step S5\n\n## 기각한 위험\n없음\n' > "$T/step-none.md"
printf '# Step S5\n\n## 바꾼 파일\n- a.swift\n' > "$T/step-nosec.md"
printf '## 요약\n- \n\n## 변경 사항\n- \n\n## 확인하지 못한 항목\n- \n' > "$T/tpl.md"
printf '## 요약\n- \n\n## 변경 사항\n- \n' > "$T/tpl-plain.md"
printf '## 요약\n- 크기 변경 복원\n\n## 변경 사항\n- 후보 정리 순서\n\n## 확인하지 못한 항목\n- 홈이 화면 밖일 때 접기\n' > "$T/pr-without.md"
printf '## 요약\n- 크기 변경 복원\n\n## 변경 사항\n- 후보 정리 순서\n\n## 확인하지 못한 항목\n- `R-1` 남은 후보(staleCandidate)가 전환 없는 크기 변경에 쓰인다 — 드문 경우로 기각 · 재현: 회전 → 화면 밖 크기 변경 → 복귀\n' > "$T/pr-with.md"
printf '## 요약\n- 크기 변경 복원\n\n## 변경 사항\n- 후보 정리 순서 · 기각한 위험 `R-1` 남은 후보(staleCandidate)가 전환 없는 크기 변경에 쓰인다(드문 경우)\n' > "$T/pr-plain.md"

run() { python3 -B "$CHK" --template "$1" --body "$2" --risks "$3" > "$T/out" 2>&1; echo $?; }
fail=""
r=$(run "$T/tpl.md" "$T/pr-without.md" "$T/step-one.md"); grep -q 'RISK-MISSING R-1' "$T/out" && [ "$r" = 1 ] || fail="$fail ①exit=$r"
r=$(run "$T/tpl.md" "$T/pr-with.md" "$T/step-one.md"); [ "$r" = 0 ] || fail="$fail ②exit=$r"
r=$(run "$T/tpl.md" "$T/pr-without.md" "$T/step-none.md"); [ "$r" = 0 ] || fail="$fail ③exit=$r"
r=$(run "$T/tpl.md" "$T/pr-with.md" "$T/step-two.md"); { [ "$r" = 1 ] && grep -q 'RISK-MISSING R-2' "$T/out" && ! grep -q 'RISK-MISSING R-1' "$T/out"; } || fail="$fail ④exit=$r"
r=$(run "$T/tpl-plain.md" "$T/pr-plain.md" "$T/step-one.md"); [ "$r" = 0 ] || fail="$fail ⑤exit=$r"
r=$(run "$T/tpl.md" "$T/pr-with.md" "$T/step-nosec.md"); { [ "$r" = 2 ] && grep -q '^UNRUN' "$T/out"; } || fail="$fail ⑥exit=$r"
if [ -z "$fail" ]; then
  echo "PASS  r3-f523-code-rejected-risk-reaches-pr"
  echo "DISMISSED_CODE_RISK_OK"
  exit 0
fi
echo "FAIL  r3-f523-code-rejected-risk-reaches-pr  —$fail · 마지막 출력: $(tr '\n' ' ' < "$T/out" | cut -c1-200)"
exit 1
