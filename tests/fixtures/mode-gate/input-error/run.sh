#!/bin/bash
# 입력 파일 없음 · 모르는 하위 명령 · 깨진 steps JSON → exit 10 · recommend null
. "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"
printf '{not json' > "$T/bad.json"
gate review --numstat "$T/none.txt" > "$T/a.json" 2>/dev/null; a=$?
gate nope > "$T/b.json" 2>/dev/null; b=$?
gate code --steps "$T/bad.json" > "$T/c.json" 2>/dev/null; c=$?
[ "$a" -eq 10 ] && [ "$b" -eq 10 ] && [ "$c" -eq 10 ] && [ "$(field "$T/c.json" "d['recommend']")" = None ] \
  && { echo "MODE_GATE_INPUT_ERROR_OK"; exit 0; }
echo "FAIL  input-error a=$a b=$b c=$c"; exit 1
