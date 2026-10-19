#!/bin/bash
# diff 가 아닌 파일 · 빈 파일 → exit 2 UNRUN · recommend null (측정 실패를 light 로 읽지 않는다)
. "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"
printf '이것은 diff 가 아니다\n' > "$T/junk.patch"; : > "$T/empty.patch"
gate review --diff "$T/junk.patch" > "$T/a.json"; a=$?
gate review --diff "$T/empty.patch" > "$T/b.json"; b=$?
[ "$a" -eq 2 ] && [ "$b" -eq 2 ] && [ "$(field "$T/a.json" "d['recommend']")" = None ] && [ "$(field "$T/b.json" "d['recommend']")" = None ] \
  && { echo "MODE_GATE_UNRUN_OK"; exit 0; }
echo "FAIL  git-fail a=$a b=$b"; exit 1
