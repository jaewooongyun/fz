#!/bin/bash
# gpt-exec.sh --config-permissions 계약 러너 (F-348) — 가짜 CLI(../_shim/codex)로 래퍼가 CLI 에 넘기는 인자만 본다.
#
# ⛔ 왜: 래퍼가 늘 붙이는 `-c sandbox_mode="read-only"` 가 config 권한 프로필(default_permissions)의 경로 deny 를 덮는다(실측 09-28).
#    격리 경로는 sandbox_mode 를 빼고 프로필에 쓰기 금지를 맡긴다 — 그래서 프로필이 read-only 를 확장하는지 호출 전에 본다.
# ⛔ 옵션을 안 주면 argv 가 분리 전과 같아야 한다 — 기본 경로의 인자 모양을 황금값으로 고정한다.
# ⛔ FZ_GPT_EXEC_UNDER_TEST 로 다른 판(기준 트리)의 래퍼를 같은 러너로 돌린다 — 판별력 대조용.
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
WRAP="${FZ_GPT_EXEC_UNDER_TEST:-$R/scripts/gpt-exec.sh}"
export PATH="$R/tests/fixtures/gpt/_shim:$PATH"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

fail=0
ok() { echo "PASS  $1"; }
no() { echo "FAIL  $1"; fail=1; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else no "$1 — 기대 '$3' · 실제 '$2'"; fi; }

mkdir -p "$T/repo"; printf '과제 본문 CP-TASK-7\n' > "$T/task.txt"
home() {   # $1=이름 · stdin=config.toml
  mkdir -p "$T/h-$1"; cat > "$T/h-$1/config.toml"
}
home good <<'EOF'
default_permissions = "iso"
model = "m"

[permissions.iso]
extends = ":read-only"

[permissions.iso.filesystem]
"/nowhere" = "deny"
EOF
home late <<'EOF'
model = "m"

[projects."/x"]
trust_level = "trusted"
default_permissions = "iso"

[permissions.iso]
extends = ":read-only"
EOF
home write <<'EOF'
default_permissions = "iso"

[permissions.iso]
extends = ":workspace-write"
EOF
home noprof <<'EOF'
default_permissions = "iso"
model = "m"
EOF

cell() {   # $1=셀 · $2=CODEX_HOME(빈 값이면 unset) · 나머지=래퍼 인자
  local name="$1" ch="$2"; shift 2
  local d="$T/c-$name"; mkdir -p "$d"
  if [ -n "$ch" ]; then
    env CODEX_HOME="$ch" FZ_SHIM_CAPTURE="$d/argv.json" FZ_TELEMETRY_DIR="$d/tel" bash "$WRAP" "$@" --cd "$T/repo" --out "$d/out.txt" > "$d/stdout" 2> "$d/stderr"
  else
    env -u CODEX_HOME FZ_SHIM_CAPTURE="$d/argv.json" FZ_TELEMETRY_DIR="$d/tel" bash "$WRAP" "$@" --cd "$T/repo" --out "$d/out.txt" > "$d/stdout" 2> "$d/stderr"
  fi
  echo $? > "$d/rc"
}
rc() { cat "$T/c-$1/rc" 2>/dev/null || echo "?"; }
has() {    # argv 에 문자열이 몇 번 (캡처 없으면 0)
  [ -s "$T/c-$1/argv.json" ] || { echo 0; return; }
  python3 -c 'import json,sys; print(" ".join(json.load(open(sys.argv[1], encoding="utf-8"))).count(sys.argv[2]))' "$T/c-$1/argv.json" "$2"
}
shape() {  # 경로·프롬프트를 지운 argv 모양 — 기본 경로 황금값 대조
  [ -s "$T/c-$1/argv.json" ] || { echo "-"; return; }
  python3 - "$T/c-$1/argv.json" "$T" <<'PY'
import json, sys
a, T = json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2]
print(" ".join("<prompt>" if "CP-TASK-7" in x else x.replace(T, "$T") for x in a))
PY
}

# ① 좋은 프로필 + --config-permissions → sandbox_mode · sandbox_permissions 를 넘기지 않는다 · effort 는 넘긴다
cell good "$T/h-good" exec --prompt-file "$T/task.txt" --config-permissions
check "좋은 프로필: exit 0" "$(rc good)" 0
check "좋은 프로필: sandbox_mode 안 넘김" "$(has good 'sandbox_mode')" 0
check "좋은 프로필: sandbox_permissions 안 넘김" "$(has good 'sandbox_permissions')" 0
check "좋은 프로필: effort 는 넘김" "$(has good 'model_reasoning_effort=high')" 1

# ② default_permissions 가 table 뒤 → 앞 table 의 키가 된다(S11 ⑦ R11) → 호출 전 exit 11
cell late "$T/h-late" exec --prompt-file "$T/task.txt" --config-permissions
check "table 뒤 default_permissions: exit 11" "$(rc late)" 11
check "table 뒤 default_permissions: CLI 미호출" "$(has late 'CP-TASK-7')" 0

# ③ 프로필이 read-only 를 확장하지 않는다 → 쓰기 금지가 사라진다 → exit 11
cell write "$T/h-write" exec --prompt-file "$T/task.txt" --config-permissions
check "쓰기 가능 프로필: exit 11" "$(rc write)" 11

# ④ default_permissions 가 가리키는 [permissions.X] 표가 없다 → exit 11
cell noprof "$T/h-noprof" exec --prompt-file "$T/task.txt" --config-permissions
check "프로필 표 없음: exit 11" "$(rc noprof)" 11

# ⑤ CODEX_HOME 없음 → 어느 config 를 믿을지 모른다 → exit 11
cell nohome "" exec --prompt-file "$T/task.txt" --config-permissions
check "CODEX_HOME 없음: exit 11" "$(rc nohome)" 11

# ⑥ 옵션 없음 → 분리 전과 같은 인자 모양(황금값 — 2026-09-28 bc7779a 래퍼와 바이트 대조 뒤 고정)
cell plain "$T/h-good" exec --prompt-file "$T/task.txt"
check "옵션 없음: exit 0" "$(rc plain)" 0
check "옵션 없음: 인자 모양 불변" "$(shape plain)" \
  'exec -C $T/repo -c sandbox_mode="read-only" -c sandbox_permissions=["disk-full-read-access"] -c model_reasoning_effort=high --skip-git-repo-check -o $T/c-plain/out.txt -- <prompt>'

echo
[ "$fail" -eq 0 ] && echo "config-permissions: 전건 통과" || echo "config-permissions: 실패 있음"
exit "$fail"
