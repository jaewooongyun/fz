#!/bin/sh
# Runs hooks/guard.sh over fixed PreCompact stdin cases and checks each exit code, that stdout stays empty,
# and that a block (exit 2) gives its reason on stderr. It also checks that the register.ts lines guard.sh
# copies its marker shapes from still read the same, so a marker change there fails here instead of leaving
# guard.sh behind with every stdin case still passing. Prints one line, guard: <passed>/<total> (with a FAIL
# line before it for each failed case), and exits 0 only when every case passes.
dir=$(cd "$(dirname "$0")" && pwd)
guard="$dir/../hooks/guard.sh"
register="$dir/../hooks/register.ts"
tmp=$(mktemp -d "${TMPDIR:-/tmp}/fz-compact-guard.XXXXXX") || { printf '%s\n' 'guard: 0/0 (could not make a temporary folder)'; exit 1; }
trap 'rm -rf "$tmp"' EXIT
passed=0
total=0

# check <expected exit> <name> <stdin>
check() {
  total=$((total + 1))
  printf '%s' "$3" | sh "$guard" >"$tmp/out" 2>"$tmp/err"
  code=$?
  why=''
  [ "$code" -eq "$1" ] || why="exit $code, expected $1"
  if [ -s "$tmp/out" ]; then why="${why:+$why; }stdout is not empty"; fi
  if [ "$1" -eq 2 ] && [ ! -s "$tmp/err" ]; then why="${why:+$why; }no reason on stderr"; fi
  if [ -z "$why" ]; then
    passed=$((passed + 1))
  else
    printf 'FAIL %s: %s\n' "$2" "$why"
  fi
}

# same_line <name> <line>: register.ts must hold <line> exactly, as a whole line.
same_line() {
  total=$((total + 1))
  if grep -Fqx -- "$2" "$register" 2>/dev/null; then
    passed=$((passed + 1))
  else
    printf 'FAIL %s: register.ts has no line reading exactly: %s\n' "$1" "$2"
  fi
}

check 2 'idle marker in a full PreCompact input' '{"hook_event_name":"PreCompact","trigger":"manual","custom_instructions":"fz-compact:idle:3"}'
check 2 'resume marker with a space after the colon' '{"custom_instructions": "fz-compact:resume"}'
check 2 'resume marker with spaces around the colon' '{"custom_instructions" : "fz-compact:resume"}'
check 2 'idle marker of generation 0' '{"custom_instructions":"fz-compact:idle:0"}'
check 0 'guidance text' '{"custom_instructions":"fz-compact guidance (appended after any user focus, which takes priority):"}'
check 0 'resume marker with more after it' '{"custom_instructions":"fz-compact:resumeX"}'
check 0 'idle marker with no digits' '{"custom_instructions":"fz-compact:idle:"}'
check 0 'idle marker with more after it' '{"custom_instructions":"fz-compact:idle:3 and more"}'
check 0 'null instructions' '{"custom_instructions":null}'
check 0 'user text' '{"custom_instructions":"keep it short"}'
check 0 'a marker quoted inside user text' '{"custom_instructions":"say \"custom_instructions\":\"fz-compact:resume\""}'
check 0 'empty stdin' ''

# marker <expected exit> <expected marker name, or - for none> <name> <stdin> [home is a file]: guard.sh under a fresh
# HOME; a block with a safe session_id leaves exactly that passed-over marker, anything else leaves none.
marker() {
  total=$((total + 1))
  home="$tmp/home-$total"
  if [ -n "${5:-}" ]; then : >"$home"; else mkdir -p "$home"; fi
  printf '%s' "$4" | HOME="$home" sh "$guard" >/dev/null 2>&1
  code=$?
  why=''
  [ "$code" -eq "$1" ] || why="exit $code, expected $1"
  found=$(ls "$home/.claude/fz-compact/passed-over" 2>/dev/null | tr '\n' ' ' | sed 's/ $//')
  [ "${found:--}" = "$2" ] || why="${why:+$why; }markers '${found:--}', expected '$2'"
  if [ -z "$why" ]; then
    passed=$((passed + 1))
  else
    printf 'FAIL %s: %s\n' "$3" "$why"
  fi
}

marker 2 abc-123_X 'passed-over marker: a block with a session_id leaves it' '{"session_id":"abc-123_X","hook_event_name":"PreCompact","custom_instructions":"fz-compact:idle:3"}'
marker 2 - 'passed-over marker: a block with no session_id leaves none' '{"custom_instructions":"fz-compact:resume"}'
marker 0 - 'passed-over marker: an input it passes leaves none' '{"session_id":"abc","custom_instructions":"keep it short"}'
marker 2 - 'passed-over marker: an unsafe session_id leaves none' '{"session_id":"../up","custom_instructions":"fz-compact:resume"}'
marker 2 - 'passed-over marker: an unwritable HOME keeps the block' '{"session_id":"abc","custom_instructions":"fz-compact:resume"}' file

# A marker file that cannot be opened for writing (read-only): the write fails, the block still exits 2.
total=$((total + 1))
home="$tmp/home-ro"
mkdir -p "$home/.claude/fz-compact/passed-over" && : >"$home/.claude/fz-compact/passed-over/abc" && chmod 444 "$home/.claude/fz-compact/passed-over/abc"
printf '%s' '{"session_id":"abc","custom_instructions":"fz-compact:resume"}' | HOME="$home" sh "$guard" >/dev/null 2>&1
code=$?
chmod 644 "$home/.claude/fz-compact/passed-over/abc"
if [ "$code" -eq 2 ]; then passed=$((passed + 1)); else printf 'FAIL %s: exit %s, expected 2\n' 'passed-over marker: a read-only marker keeps the block' "$code"; fi

same_line 'register.ts marker prefix' "const MARKER = 'fz-compact:'"
same_line 'register.ts idle marker' 'const IDLE_MARKER = `${MARKER}idle:`'
same_line 'register.ts resume marker' 'const RESUME_MARKER = `${MARKER}resume`'
same_line 'register.ts idle generation digits' '  if (!/^[0-9]+$/.test(digits)) return null'
same_line 'register.ts passed-over path' "  return /^[A-Za-z0-9_-]+\$/.test(sessionId) ? \`\${home.replace(/\\/+\$/, '')}/.claude/fz-compact/passed-over/\${sessionId}\` : null"

printf 'guard: %s/%s\n' "$passed" "$total"
if [ "$passed" -eq "$total" ]; then exit 0; fi
exit 1
