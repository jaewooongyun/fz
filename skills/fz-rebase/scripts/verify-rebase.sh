#!/usr/bin/env bash
#
# verify-rebase.sh — 롱텀 브랜치 리베이스의 결정적 안전 게이트 (3층)
#
# 방어 대상: 리베이스/force-push에서 **양방향으로 조용히** 사라지는 변경.
#
#   ① 내 변경이 사라짐
#      - 커밋 드롭: `--empty=drop`이 기본이고, upstream과 동일 패치는 선제 드롭된다
#        (git-rebase(1): "commits which are clean cherry-picks ... are detected and dropped
#         as a preliminary step"). 경고는 나오지만 리베이스 로그에 묻힌다.
#      - 머지 커밋의 수동 해결 미재적용: "Any resolved merge conflicts or manual amendments
#        in these merge commits will have to be resolved/re-applied manually" (git-rebase(1)).
#        머지 **개수는 그대로**라 개수 기반 검증을 전부 통과한다.
#      - 팀원이 파일을 옮기거나 지워 내 hunk가 새 위치에 착지하지 못함.
#      - 내 삭제가 되살아남(충돌을 "양쪽 유지"로 해소).
#
#   ② 팀원 변경이 사라짐
#      - 충돌 해결 방향 역전: 리베이스에서 ours = base 측, theirs = 내 커밋
#        (git-rebase(1): "the sides are swapped").
#      - 무충돌 clean 적용: 전체 재작성/생성물 커밋이 base 최신을 되돌린다.
#      - 팀원의 삭제를 내가 되살림.
#      - force-push 파괴: ff-pull **이후** 팀원 push + 그 사이 fetch로 tracking 갱신 →
#        `--force-with-lease`는 통과하면서 팀원 커밋만 사라진다.
#
# 게이트 3층 — 개수 보존은 내용 보존을 뜻하지 않는다:
#   snapshot (리베이스 직전) → check (형태) → audit (내용) → prepush (원격)
#
# audit의 완전성 근거 — **경로 단위 배타 분할**:
#   ① MINE-only  (내가 변경 & base 미변경) → POST가 PRE와 바이트 동일해야 한다(mode 포함)
#   ② not MINE   (내가 미변경)             → POST가 BASE와 바이트 동일해야 한다
#   ③ OVERLAP    (양쪽 변경)               → 라인 4방향 검사(텍스트) / 검토 WARN(바이너리)
#   세 버킷이 세 트리(PRE·BASE·POST) 경로 합집합을 배타 분할하므로, 텍스트·바이너리·
#   mode·symlink·gitlink·추가·삭제·이동이 열거 없이 전부 판정 범위에 들어온다.
#   ⛔ 비대상(명시): 커밋 메타데이터(author/message/trailer) · 워킹트리 dirty/stash 유실.
#
# 사용법:
#   verify-rebase.sh snapshot <base-ref> <branch-ref>
#       ff-pull 이후·리베이스 **직전**. 상태를 $(git rev-parse --git-dir)/fz-rebase-state에
#       기록하고 롤백 앵커 ref를 만든 뒤 위험 브리핑을 출력한다. COMMITS=/MERGES=도 출력.
#
#   verify-rebase.sh capture <base-ref> <branch-ref>            # 개수만 (기존 호환)
#   verify-rebase.sh check <base-ref> <branch-ref> <expected-commits> <expected-merges> [key-path ...]
#   verify-rebase.sh audit <base-ref> <branch-ref>              # 내용 게이트 (리베이스 후)
#   verify-rebase.sh prepush <branch-ref> [<remote> <remote-branch>]   # force-push 직전
#
# 환경변수:
#   FZ_REBASE_SKIP_REMERGE=1  수동해결 머지 스캔 생략 (머지가 매우 많은 브랜치의 시간 절약)
#   FZ_REBASE_SKIP_LSREMOTE=1 prepush의 원격 실측 생략 (오프라인 — 보호가 약해진다)
#   FZ_REBASE_RELOCATE_SHOW=N  삭제 파일의 대체 후보를 몇 개까지 나열할지 (기본 5).
#                              ⛔ 표시량만 자른다 — 후보 특정 가능성을 판정하는 값이 아니다.

set -euo pipefail
export LC_ALL=C   # sort/comm 집합 연산의 collation 일치

# 표시 상한: 양의 정수가 아니면 기본값으로 되돌린다 (foo·0·-1 방어)
RELOCATE_SHOW="${FZ_REBASE_RELOCATE_SHOW:-5}"
[ "$RELOCATE_SHOW" -gt 0 ] 2>/dev/null || RELOCATE_SHOW=5

STATE_DIR="$(git rev-parse --git-dir)/fz-rebase-state"   # 워크트리에서 .git은 파일 → 리터럴 금지
HALT_COUNT=0

die()  { echo "HALT: $*" >&2; exit 1; }
halt() { echo "HALT: $*"; HALT_COUNT=$((HALT_COUNT + 1)); }
warn() { echo "WARN: $*"; }
info() { echo "INFO: $*"; }

# 경로<TAB>"mode blob" 맵. mode를 포함해야 실행권한 변경·symlink·gitlink까지 검사된다.
tree_map() {
  git -c core.quotePath=false ls-tree -r --format='%(path)%x09%(objectmode) %(objectname)' "$1" | sort
}

# 순(net) 변경 경로. --no-renames: 파티션은 경로 단위이므로 이동을 삭제+추가로 본다
# (base 측 이동은 renames.tsv로 별도 매핑한다).
changed_paths() {
  git -c core.quotePath=false diff --no-renames --name-only "$1" "$2" | sort -u
}

# 라인 정규화: 앞뒤 공백 제거 + 잡음 제외(3자 이하·순수 구두점).
# 이유: 중괄호·공백 라인은 유실 근거가 되지 못하면서 경보를 폭증시킨다.
norm_stream() {
  awk '{ gsub(/^[ \t]+/, ""); gsub(/[ \t]+$/, "");
         if (length($0) > 3 && $0 !~ /^[[:punct:]]+$/) print }'
}

# unified=0 diff(stdin) → 정규화 라인. side=add(추가) / del(삭제)
# 헤더는 `diff --git` ~ 첫 `@@` 구간에서만 인식한다. 이유: 내용 라인 "-- foo"가
# 삭제되면 diff에서 "--- foo"로 보여 헤더로 오인될 수 있다.
diff_lines() {
  awk -v side="$1" '
    /^diff --git / { inhdr = 1; next }
    inhdr && /^--- /    { next }
    inhdr && /^\+\+\+ / { next }
    /^@@/ { inhdr = 0; next }
    inhdr { next }
    {
      c = substr($0, 1, 1)
      if (side == "add" && c == "+")      { l = substr($0, 2) }
      else if (side == "del" && c == "-") { l = substr($0, 2) }
      else next
      gsub(/^[ \t]+/, "", l); gsub(/[ \t]+$/, "", l)
      if (length(l) <= 3) next
      if (l ~ /^[[:punct:]]+$/) next
      print l
    }
  '
}

# 사라진 라인이 트리 다른 경로에 같은 문자열로 존재할 때 후보를 보고한다.
# ⛔ "착지"가 아니라 "위치 후보"다 — 문자열 일치는 이동의 증거가 아니다.
# 목적지 파일로 집계해 쌍당 한 줄만 낸다(라인마다 내면 50줄 이동이 WARN 50건이 된다).
report_moved() {   # $1=출발 경로  $2=사라진 라인 파일  $3=주체 라벨
  local src="$1" f="$2" who="$3" lines dests
  [ -s "$f" ] || return 0
  join -t"$(printf '\t')" -1 1 -2 1 "$f" "$W/tree-index" \
    | cut -f2 | sort | uniq -c | sort -rn > "$W/.moved-agg"
  [ -s "$W/.moved-agg" ] || return 0
  # ⛔ 두 수를 구분한다 — 사라진 라인 수와 그 문자열이 나타나는 목적지 파일 수는 다르다.
  #    (라인 1줄이 파일 250곳에 있으면 "250건"이 아니라 "1줄 · 250곳"이다)
  lines="$(wc -l < "$f" | tr -d ' ')"
  dests="$(wc -l < "$W/.moved-agg" | tr -d ' ')"
  warn "동일 라인 위치 후보: ${src}에서 ${who} 라인 ${lines}줄이 사라졌고, 같은 문자열이 다른 경로 ${dests}곳에 있다 — 이동/리팩토링에 따른 것인지 사람이 확인할 것"
  # ⛔ 임시 파일 경로를 안내하지 않는다. $W는 audit마다 rm -rf되고 .moved-agg는 고정
  #    이름이라 같은 실행 안에서도 다음 호출이 덮어쓴다 — 사용자가 열면 없거나 남의 결과다.
  head -10 "$W/.moved-agg" | awk '{ print "    " $2 "  (" $1 "줄)" }'
  [ "$dests" -le 10 ] || echo "    … 외 $((dests - 10))곳 (같은 문자열이 그만큼 흔하다는 뜻이므로 이동 판정에 쓰기 어렵다)"
}

# 삭제된 경로의 대체 후보를 그 삭제 커밋의 동시 추가에서 찾는다.
# ⛔ 대체 관계의 증거가 아니라 **같은 커밋이라는 provenance**만 준다.
#    squash·revert·기능제거와 신규추가 동시 착지에서는 틀린다. 문구도 확정으로 쓰지 않는다.
relocate_hint() {   # $1=삭제 경로  $2=old_mb  $3=base
  local p="$1" mb="$2" base="$3" dels ndel c added n
  # ⛔ `-1`을 쓰지 않는다. 경로 제한 log는 history simplification을 적용해 반환 커밋이
  #    인과적으로 유일한 삭제라는 보장이 없다 [실측: 병렬 삭제·재추가에서 2건 반환].
  #    범위를 분기점 이후로 좁히고 --full-history로 전 edge를 본 뒤,
  #    non-merge 삭제가 정확히 하나일 때만 후보를 낸다.
  dels="$(git log --full-history --no-merges --diff-filter=D --format=%H "${mb}..${base}" -- "$p" 2>/dev/null || true)"
  ndel="$(printf '%s\n' "$dels" | grep -c . || true)"
  if [ "${ndel:-0}" -ne 1 ]; then
    [ "${ndel:-0}" -le 1 ] || echo "      └ 삭제 커밋이 ${ndel}개라 후보를 특정하지 않는다 (삭제·재추가 반복 또는 머지 해결)"
    return 0
  fi
  c="$(printf '%s\n' "$dels" | head -1)"
  # ⛔ --no-renames: diff.renames 기본이 true라 D/A 쌍이 R로 재분류될 수 있다.
  #    literal 추가 목록이 필요하므로 rename 감지를 끈다. -z로 경로 인코딩도 지킨다.
  added="$(git show --no-renames --name-status --diff-filter=A --format='' -z "$c" 2>/dev/null \
           | tr '\0' '\n' | awk 'NR%2==0' | grep . || true)"
  n="$(printf '%s\n' "$added" | grep -c . || true)"
  [ "${n:-0}" -gt 0 ] || return 0
  echo "      └ 같은 커밋에서 추가된 파일 ${n}개 — 대체 후보일 수 있으나 확정 아님 ($(git log -1 --format='%h %s' "$c"))"
  printf '%s\n' "$added" | head -"$RELOCATE_SHOW" | sed 's|^|         |'
  [ "$n" -le "$RELOCATE_SHOW" ] || echo "         … 외 $((n - RELOCATE_SHOW))개 (전체는 위 커밋에서 확인)"
}

# 수동 해결(evil merge)을 품은 머지 목록 → "subject<TAB>remerge라인수"
# 리베이스가 머지를 재생성하면 해시가 바뀌므로 대조 키는 subject다.
scan_manual_merges() {
  if [ "${FZ_REBASE_SKIP_REMERGE:-0}" = "1" ]; then return 0; fi
  local m n s
  for m in $(git rev-list --merges "$1"); do
    n="$(git log -1 --remerge-diff --format='' -p "$m" 2>/dev/null | wc -l | tr -d ' ')"
    [ "${n:-0}" -gt 0 ] || continue
    s="$(git log -1 --format=%s "$m")"
    printf '%s\t%s\n' "$s" "$n"
  done
}

cmd="${1:-}"

case "$cmd" in
  capture)
    base="${2:?capture requires <base-ref>}"
    branch="${3:?capture requires <branch-ref>}"
    echo "COMMITS=$(git rev-list --count "${base}..${branch}") MERGES=$(git rev-list --merges --count "${base}..${branch}")"
    ;;

  snapshot)
    base="${2:?snapshot requires <base-ref>}"
    branch="${3:?snapshot requires <branch-ref>}"

    # ⛔ 진입 즉시 이전 상태를 버린다. 아래 해석이 실패하면 스크립트가 종료되는데,
    #    그때 이전 실행의 meta.env가 남아 있으면 다음 audit이 그것을 정상 snapshot으로
    #    읽는다(기준선이 어긋난 채 판정). 성공 경로에서만 다시 만든다.
    rm -rf "$STATE_DIR"

    # `set -e` 하에서 rev-parse/merge-base가 실패하면 die 없이 무음 종료한다 —
    # 사용자는 아무 메시지도 못 받고, 내용 게이트가 통째로 비활성화된다.
    base_hash="$(git rev-parse -q --verify "$base" 2>/dev/null || true)"
    [ -n "$base_hash" ] || die "base ref를 해석할 수 없다: ${base}. fetch 여부와 철자를 확인할 것."
    pre="$(git rev-parse -q --verify "$branch" 2>/dev/null || true)"
    [ -n "$pre" ] || die "branch ref를 해석할 수 없다: ${branch}."
    old_mb="$(git merge-base "$base" "$branch" 2>/dev/null || true)"
    [ -n "$old_mb" ] || die "${base}와 ${branch}에 공통 조상이 없다. 히스토리가 재작성됐거나 base 지정이 잘못됐다 — 리베이스하면 전체 히스토리가 대상이 되므로 진행하지 않는다. base를 재확인할 것."
    commits="$(git rev-list --count "${base}..${branch}")"
    merges="$(git rev-list --merges --count "${base}..${branch}")"

    # 롤백 앵커: 이름에 해시를 넣어 snapshot 재실행이 이전 앵커를 덮어쓰지 못하게 한다.
    # ref이므로 GC 대상에서도 벗어나 audit이 PRE 트리를 계속 읽을 수 있다.
    anchor="refs/fz-rebase/pre/${branch}-$(echo "$pre" | cut -c1-8)"
    git update-ref "$anchor" "$pre"

    mkdir -p "$STATE_DIR"
    {
      echo "FZ_BASE_REF=$base"
      echo "FZ_BASE_HASH=$base_hash"
      echo "FZ_BRANCH_REF=$branch"
      echo "FZ_PRE=$pre"
      echo "FZ_OLD_MB=$old_mb"
      echo "FZ_COMMITS=$commits"
      echo "FZ_MERGES=$merges"
      echo "FZ_ANCHOR=$anchor"
    } > "$STATE_DIR/meta.env"

    # base 측 이동/삭제 — 내 hunk의 착지 지점 판정(audit 파티션의 rename 매핑)에 사용
    git -c core.quotePath=false diff -M --diff-filter=R --name-status "$old_mb" "$base" \
      | awk -F'\t' '{print $2 "\t" $3}' | sort -u > "$STATE_DIR/renames.tsv"

    # 기본 임계(50%)에서 놓친 이동을 낮은 임계로 한 번 더 본다.
    # ⛔ 판정에 쓰지 않는다 — 브리핑 전용이다. 낮은 임계는 오매핑을 만들 수 있어
    #    audit의 경로 분할에 섞으면 버킷 판정이 흔들린다. 파일을 물리적으로 분리한다.
    git -c core.quotePath=false diff -M30% --diff-filter=R --name-status "$old_mb" "$base" \
      | awk -F'\t' '{print $2 "\t" $3}' | sort -u > "$STATE_DIR/.rn-low"
    comm -13 "$STATE_DIR/renames.tsv" "$STATE_DIR/.rn-low" > "$STATE_DIR/rename-candidates.tsv" || : > "$STATE_DIR/rename-candidates.tsv"
    rm -f "$STATE_DIR/.rn-low"

    git -c core.quotePath=false diff --diff-filter=D --name-only "$old_mb" "$base" | sort -u > "$STATE_DIR/base-deleted.txt"
    # relocate 조회 전용 — NUL 구분. 위 표시용 목록은 큰따옴표·역슬래시를 C quoting하므로
    # 그 문자열을 pathspec으로 넘기면 조회가 실패한다 (기존 판정 파일은 그대로 둔다).
    git -c core.quotePath=false diff --diff-filter=D --name-only -z "$old_mb" "$base" > "$STATE_DIR/base-deleted-z"

    changed_paths "$old_mb" "$pre"  > "$STATE_DIR/mine-files.txt"
    changed_paths "$old_mb" "$base" > "$STATE_DIR/incoming-files.txt"
    comm -12 "$STATE_DIR/mine-files.txt" "$STATE_DIR/incoming-files.txt" > "$STATE_DIR/overlap.txt"

    scan_manual_merges "${old_mb}..${pre}" > "$STATE_DIR/manual-merges.tsv" || true

    echo "COMMITS=${commits} MERGES=${merges}"
    info "snapshot 기록 → ${STATE_DIR} (분기점 ${old_mb}, 리베이스 전 HEAD ${pre})"
    info "롤백 앵커 → ${anchor}  (복구: git reset --hard ${anchor})"
    info "내 변경 파일 $(wc -l < "$STATE_DIR/mine-files.txt" | tr -d ' ')개 / 팀원 변경 $(wc -l < "$STATE_DIR/incoming-files.txt" | tr -d ' ')개 / 겹침 $(wc -l < "$STATE_DIR/overlap.txt" | tr -d ' ')개 — 겹침만이 사람 판정이 필요한 집합이다."

    awk -F'\t' 'FILENAME==ARGV[1]{mine[$0]=1; next} ($1 in mine){print "  이동: " $1 " → " $2}' \
      "$STATE_DIR/mine-files.txt" "$STATE_DIR/renames.tsv" > "$STATE_DIR/.risk" || true
    awk -F'\t' 'FILENAME==ARGV[1]{mine[$0]=1; next} ($1 in mine){print "  이동 후보(유사도 낮아 확정 아님): " $1 " → " $2}' \
      "$STATE_DIR/mine-files.txt" "$STATE_DIR/rename-candidates.tsv" >> "$STATE_DIR/.risk" || true
    # ⛔ NUL 구분 목록을 읽는다. 표시용 base-deleted.txt는 큰따옴표·역슬래시를
    #    C quoting하므로 그 문자열로는 git 조회가 실패한다.
    while IFS= read -r -d '' dp; do
      grep -qxF "$dp" "$STATE_DIR/mine-files.txt" 2>/dev/null || continue
      echo "  삭제: $dp" >> "$STATE_DIR/.risk"
      relocate_hint "$dp" "$old_mb" "$base" >> "$STATE_DIR/.risk"
    done < "$STATE_DIR/base-deleted-z"

    # ⛔ 헤더 건수는 표시 줄 수가 아니라 **unique 원본 경로 수**로 센다.
    #    한 파일이 이동 후보와 삭제 양쪽에 걸리면 줄은 둘이지만 위험 파일은 하나다.
    {
      awk -F'\t' 'FILENAME==ARGV[1]{m[$0]=1; next} ($1 in m){print $1}' "$STATE_DIR/mine-files.txt" "$STATE_DIR/renames.tsv"
      awk -F'\t' 'FILENAME==ARGV[1]{m[$0]=1; next} ($1 in m){print $1}' "$STATE_DIR/mine-files.txt" "$STATE_DIR/rename-candidates.tsv"
      awk 'FILENAME==ARGV[1]{m[$0]=1; next} ($0 in m){print $0}' "$STATE_DIR/mine-files.txt" "$STATE_DIR/base-deleted.txt"
    } 2>/dev/null | sort -u > "$STATE_DIR/.risk-paths" || : > "$STATE_DIR/.risk-paths"
    if [ -s "$STATE_DIR/.risk" ]; then
      warn "팀원이 이동/삭제한 파일 중 내가 만진 것 $(wc -l < "$STATE_DIR/.risk-paths" | tr -d ' ')건 — 충돌로 표면화되지 않으면 내 변경이 옛 경로에 잔존할 수 있다:"
      cat "$STATE_DIR/.risk"
    else
      info "팀원 이동/삭제 ∩ 내 변경: 없음"
    fi

    if [ -s "$STATE_DIR/manual-merges.tsv" ]; then
      warn "수동 해결을 품은 머지 $(wc -l < "$STATE_DIR/manual-merges.tsv" | tr -d ' ')건 — --rebase-merges는 이 해결을 재적용하지 않는다(git 원문). 리베이스 후 audit이 대조한다:"
      awk -F'\t' '{print "  " $1 "  (remerge " $2 "줄)"}' "$STATE_DIR/manual-merges.tsv"
    else
      info "수동 해결을 품은 머지: 없음${FZ_REBASE_SKIP_REMERGE:+ (스캔 생략됨)}"
    fi
    ;;

  check)
    base="${2:?check requires <base-ref>}"
    branch="${3:?check requires <branch-ref>}"
    expected_commits="${4:?check requires <expected-commits>}"
    expected_merges="${5:?check requires <expected-merges>}"
    shift 5 || true
    key_paths=("$@")

    now_commits="$(git rev-list --count "${base}..${branch}")"
    now_merges="$(git rev-list --merges --count "${base}..${branch}")"

    # 1) 커밋 수 감소 — 정당한 드롭(base 흡수·빈 커밋)일 수 있다. audit이 판정한다.
    if [ "${now_commits}" -lt "${expected_commits}" ]; then
      die "커밋 수 감소 ${expected_commits} → ${now_commits}. audit으로 내용 유실 여부를 판정할 것 (라인이 모두 POST 트리에 있으면 흡수, 없으면 유실)."
    fi

    # 2) 머지 수 감소 = --rebase-merges 누락 의심
    if [ "${now_merges}" -lt "${expected_merges}" ]; then
      die "머지 커밋 수 감소 ${expected_merges} → ${now_merges}. --rebase-merges 누락 의심 — 리베이스 롤백."
    fi

    # 3) branch가 base tip을 포함해야 리베이스 완료
    if ! git merge-base --is-ancestor "${base}" "${branch}"; then
      die "${branch}가 ${base}를 조상으로 포함하지 않음. 리베이스 미완료 또는 대상 base 오류."
    fi

    # 4) 워킹 트리 clean (미해결 충돌/잔여 churn)
    if [ -n "$(git status --porcelain)" ]; then
      die "워킹 트리 dirty. 미해결 충돌 또는 잔여 변경 존재 — force-push 금지."
    fi

    # 5) coarse smoke test — 팀원이 정당하게 옮긴 경우에도 걸린다(착지 판정은 audit 소관)
    # bash 3.2는 nounset 하에서 빈 배열 참조를 unbound로 취급하므로 확장 방어가 필요하다.
    for p in ${key_paths[@]+"${key_paths[@]}"}; do
      if [ -z "$(git ls-tree -r --name-only "${branch}" -- "${p}")" ]; then
        die "핵심 경로 부재: ${p}. 유실 또는 팀원의 경로 이동 — audit으로 착지 지점을 확인할 것."
      fi
    done

    echo "OK: commits ${expected_commits}→${now_commits} merges ${expected_merges}→${now_merges}, ${branch} contains ${base}, tree clean${key_paths+, key paths present}."
    ;;

  audit)
    base="${2:?audit requires <base-ref>}"
    branch="${3:?audit requires <branch-ref>}"
    [ -f "$STATE_DIR/meta.env" ] || die "snapshot 상태 없음 (${STATE_DIR}). 리베이스 전 snapshot을 실행해야 내용 검증이 가능하다 — 지금은 형태 게이트(check)만 유효."

    # ⛔ `. meta.env`로 source하지 않는다. 저장되는 값에 **ref 이름이 들어가고**,
    #    git은 ref 이름에 `$(...)`·백틱·`|`·`&`를 허용한다(`;`만 거부) — 실측 확인.
    #    source하면 조작된 브랜치 이름이 audit 시점에 명령으로 실행된다.
    #    값만 뽑는 파서를 쓴다 (셸 해석 없음).
    meta_get() { sed -n "s/^$1=//p" "$STATE_DIR/meta.env" | head -1; }
    FZ_BASE_REF="$(meta_get FZ_BASE_REF)"
    FZ_BASE_HASH="$(meta_get FZ_BASE_HASH)"
    FZ_BRANCH_REF="$(meta_get FZ_BRANCH_REF)"
    FZ_PRE="$(meta_get FZ_PRE)"
    FZ_OLD_MB="$(meta_get FZ_OLD_MB)"
    FZ_COMMITS="$(meta_get FZ_COMMITS)"
    FZ_MERGES="$(meta_get FZ_MERGES)"
    FZ_ANCHOR="$(meta_get FZ_ANCHOR)"
    [ -n "$FZ_PRE" ] && [ -n "$FZ_OLD_MB" ] || die "meta.env 파싱 실패 — snapshot 상태가 손상됐다. 재-snapshot 필요."

    # snapshot이 기록한 대상과 지금 판정하려는 대상이 같아야 한다. 다르면 renames·
    # manual-merges(옛 대상 기준)와 base.map(현 대상)이 섞여 판정이 무의미해진다.
    [ "$FZ_BASE_REF" = "$base" ] || die "snapshot은 base=${FZ_BASE_REF}로 기록됐는데 audit은 ${base}로 호출됐다 — 같은 대상으로 재-snapshot 후 리베이스할 것."
    [ "$FZ_BRANCH_REF" = "$branch" ] || die "snapshot은 branch=${FZ_BRANCH_REF}로 기록됐는데 audit은 ${branch}로 호출됐다."

    post="$(git rev-parse "$branch")"

    # ⛔ WARN이 아니라 die다. renames.tsv·manual-merges.tsv는 snapshot 시점 base 기준인데
    #    base.map·base-changed는 지금 base를 읽는다. base가 움직이면 한 판정 안에 기준선이
    #    둘이 되어 통과든 실패든 신뢰할 수 없다 — 거짓 통과를 남기느니 멈춘다.
    if [ "$(git rev-parse "$base")" != "$FZ_BASE_HASH" ]; then
      die "base가 snapshot 이후 이동했다 (${FZ_BASE_HASH} → $(git rev-parse "$base")). renames·manual-merges는 옛 base 기준이고 base.map은 현재 base라 판정이 두 기준선에 걸친다.
  ⛔ 지금 상태에서 재-snapshot하지 말 것 — 이미 유실됐을 수 있는 POST가 새 PRE가 되어 원래 기준선을 잃는다.
  복구: 리베이스 진행 중이면 'git rebase --abort'. 완료 후면 'git reset --hard ${FZ_ANCHOR:-$FZ_PRE}'로 되돌린 뒤 새 base에서 snapshot → rebase를 다시 시작한다."
    fi

    # 전제: 리베이스가 완료돼 base가 POST의 조상이어야 한다. 미완료 상태에서 판정하면
    # base의 신규 라인이 "내가 지운 것"으로 보여 방향②가 통째로 오판한다.
    if ! git merge-base --is-ancestor "$base" "$post"; then
      die "${branch}가 ${base}를 조상으로 포함하지 않음 — 리베이스 미완료. audit은 리베이스 **후**에 실행한다 (지금 판정하면 base 신규 라인을 유실로 오판)."
    fi

    W="$STATE_DIR/.work"; rm -rf "$W"; mkdir -p "$W"

    tree_map "$FZ_PRE" > "$W/pre.map"
    tree_map "$base"   > "$W/base.map"
    tree_map "$post"   > "$W/post.map"

    # ─── 경로 분할 ─────────────────────────────────────────────────────
    # 내 변경 경로는 base 측 이동(A→B)을 먼저 반영한다. 매핑하지 않으면 팀원의
    # 정당한 rename에서 내 hunk가 새 경로에 착지한 것을 위반으로 오판한다.
    changed_paths "$FZ_OLD_MB" "$FZ_PRE" > "$W/mine-raw"
    changed_paths "$FZ_OLD_MB" "$base"   > "$W/base-changed"
    # ⛔ NR==FNR로 파일을 구분하지 않는다 — 첫 파일이 비면 두 번째 파일 전체에서도 참이 되어
    # 모든 라인이 첫 파일 것으로 소비되고 출력이 통째로 사라진다(rename 없는 리베이스 = 대다수).
    awk -F'\t' 'FILENAME == ARGV[1] { R[$1] = $2; next } { print ($0 in R) ? R[$0] : $0 }' \
      "$STATE_DIR/renames.tsv" "$W/mine-raw" | sort -u > "$W/mine"
    # 역매핑(분할 키 → 내 diff 경로): OVERLAP 라인 검사에서 내 diff를 찾는 데 쓴다
    awk -F'\t' 'FILENAME == ARGV[1] { R[$1] = $2; next } { print (($0 in R) ? R[$0] : $0) "\t" $0 }' \
      "$STATE_DIR/renames.tsv" "$W/mine-raw" | sort -u > "$W/mine-srcmap"

    comm -12 "$W/mine" "$W/base-changed" > "$W/overlap"
    comm -23 "$W/mine" "$W/base-changed" > "$W/mine-only"

    info "분할: MINE-only $(wc -l < "$W/mine-only" | tr -d ' ')개 / OVERLAP $(wc -l < "$W/overlap" | tr -d ' ')개 / 나머지(=not MINE)는 BASE와 동일해야 한다."

    # ─── 버킷 ① MINE-only: POST가 PRE와 바이트 동일해야 한다 ──────────
    # base가 손대지 않은 파일이므로 리베이스는 내 내용을 그대로 재현해야 한다.
    # "부재"도 값으로 비교하므로 내 삭제가 되살아나는 경우까지 잡힌다.
    awk -F'\t' '
      FILENAME == ARGV[1] { M[$0] = 1; next }
      FILENAME == ARGV[2] { R[$1] = $2; next }
      FILENAME == ARGV[3] { P[$1] = $2; next }
      END { for (p in M) {
              r = (p in R) ? R[p] : "<부재>"
              q = (p in P) ? P[p] : "<부재>"
              if (r != q) print p "\t" r "\t" q
            } }
    ' "$W/mine-only" "$W/pre.map" "$W/post.map" | sort > "$W/v1"
    if [ -s "$W/v1" ]; then
      halt "MINE-only 파일 $(wc -l < "$W/v1" | tr -d ' ')개가 리베이스 전과 다르다 (base가 손대지 않았으므로 그대로 재현돼야 한다) — 내 변경 유실/변형:"
      awk -F'\t' '{print "  " $1 "\n      리베이스 전: " $2 "\n      리베이스 후: " $3}' "$W/v1" | head -30
    else
      info "버킷① MINE-only 전부 리베이스 전과 바이트 동일 (mode 포함)."
    fi

    # ─── 버킷 ② not MINE: POST가 BASE와 바이트 동일해야 한다 ──────────
    # 내가 손대지 않은 파일은 base 최신 그대로여야 한다. 다르면 내 브랜치가
    # 팀원 변경(추가·수정·삭제)을 덮어썼거나 무관 파일이 오염된 것이다.
    awk -F'\t' '
      FILENAME == ARGV[1] { M[$0] = 1; next }
      FILENAME == ARGV[2] { B[$1] = $2; seen[$1] = 1; next }
      FILENAME == ARGV[3] { P[$1] = $2; seen[$1] = 1; next }
      END { for (p in seen) {
              if (p in M) continue
              b = (p in B) ? B[p] : "<부재>"
              q = (p in P) ? P[p] : "<부재>"
              if (b != q) print p "\t" b "\t" q
            } }
    ' "$W/mine" "$W/base.map" "$W/post.map" | sort > "$W/v2"
    if [ -s "$W/v2" ]; then
      halt "내가 손대지 않은 파일 $(wc -l < "$W/v2" | tr -d ' ')개가 base와 다르다 — 팀원 변경 덮어쓰기:"
      awk -F'\t' '{print "  " $1 "\n      base: " $2 "\n      내 브랜치: " $3}' "$W/v2" | head -30
      cut -f1 "$W/v2" | head -10 | while IFS= read -r f; do
        git log --oneline -2 "${FZ_OLD_MB}..${base}" -- "$f" | sed "s|^|      귀속(${f}): |"
      done
    else
      info "버킷② 내가 손대지 않은 파일 전부 base와 바이트 동일."
    fi

    # ─── 버킷 ③ OVERLAP: 양쪽이 만진 파일만 라인 4방향 ────────────────
    ov_text=0; ov_bin=0
    : > "$W/ov-bin"
    if [ -s "$W/overlap" ]; then
      # 트리 전역 라인 집합 1패스 — 코드가 다른 파일로 이동한 경우를 유실로 오판하지 않기 위해
      # ⛔ `-h`를 쓰지 않는다. 같은 1회 스캔에서 경로를 함께 보존하면 "내 라인이 어디로
      #    갔는가"를 추가 비용 없이 답할 수 있다. tree-all은 여기서 파생한다(소비부 무변경).
      #    통짜 `sort -u` — `-k1,1`을 붙이면 `-u`가 첫 필드 기준으로 중복을 지워
      #    같은 라인이 여러 경로에 있을 때 두 번째 경로가 사라진다. TAB 구분에서 1열이
      #    같으면 2열로 tie-break되므로 join이 요구하는 1열 정렬은 이미 만족한다.
      # ⛔ 경로에 `:`가 있으면 아래 `-F:` 분리가 경로 일부를 내용으로 오인한다.
      #    그 오인이 tree-index에 가짜 라인을 넣으면 **원래 HALT였을 유실이 WARN으로
      #    낮아진다** — 검출 완화는 이 변경의 금지 사항이므로 해당 경로를 아예 제외한다.
      #    (제외는 tree-all을 줄이므로 판정이 엄격해지는 방향이다.)
      git grep -I -a -e '' "$post" -- 2>/dev/null \
        | sed "s|^${post}:||" \
        | awk -F: -v OFS='\t' '{ pth = $1; ln = substr($0, length(pth) + 2)
            gsub(/^[ \t]+/, "", ln); gsub(/[ \t]+$/, "", ln)
            if (length(ln) > 3 && ln !~ /^[[:punct:]]+$/) print ln, pth }' \
        | sort -u > "$W/tree-index" || true
      # 콜론 포함 경로 실재 여부를 별도로 확인해 알린다 (인덱스 신뢰 구간 명시)
      if git ls-tree -r --name-only "$post" | grep -q ':'; then
        warn "경로에 ':'가 든 파일이 있다 — 위치 후보 인덱스는 그 경로들을 신뢰할 수 없어 제외했다. 해당 파일의 라인은 위치 후보 대신 HALT로 판정된다(엄격 방향)."
        git ls-tree -r --name-only "$post" | grep ':' | sed 's/^/    /' | head -5
        awk -F'\t' 'index($2, ":") == 0' "$W/tree-index" > "$W/.ti2" && mv "$W/.ti2" "$W/tree-index"
      fi
      cut -f1 "$W/tree-index" | uniq > "$W/tree-all" || true
      : > "$W/l1"; : > "$W/l2"; : > "$W/l3"; : > "$W/l4"
      while IFS= read -r q; do
        [ -n "$q" ] || continue
        src="$(awk -F'\t' -v k="$q" '$1 == k { print $2; exit }' "$W/mine-srcmap")"
        [ -n "$src" ] || src="$q"
        if [ "$(git diff --numstat "$FZ_OLD_MB" "$post" -- "$q" | awk '{print $1}')" = "-" ]; then
          ov_bin=$((ov_bin + 1)); printf '%s\n' "$q" >> "$W/ov-bin"; continue
        fi
        ov_text=$((ov_text + 1))
        git diff --unified=0 --no-color --no-ext-diff "$FZ_OLD_MB" "$FZ_PRE" -- "$src" | diff_lines add | sort -u > "$W/.myadd"
        git diff --unified=0 --no-color --no-ext-diff "$FZ_OLD_MB" "$FZ_PRE" -- "$src" | diff_lines del | sort -u > "$W/.mydel"
        git diff --unified=0 --no-color --no-ext-diff "$FZ_OLD_MB" "$base" -- "$q"   | diff_lines add | sort -u > "$W/.baseadd"
        git diff --unified=0 --no-color --no-ext-diff "$FZ_OLD_MB" "$base" -- "$q"   | diff_lines del | sort -u > "$W/.basedel"
        git show "${post}:${q}" 2>/dev/null | norm_stream | sort -u > "$W/.postfile" || : > "$W/.postfile"

        # 경로 접두는 awk로 붙인다 — BSD sed는 치환부 `\t`를 탭으로 해석하지 않고,
        # 경로에 구분자 문자가 있으면 sed 표현식이 깨진다.
        # ①내 추가가 트리에 없음 = 내 변경 유실
        # 트리 전역에만 없으면 유실(HALT). 이 파일에는 없는데 트리엔 있으면 위치 후보(WARN).
        comm -23 "$W/.myadd" "$W/.postfile" > "$W/.gone1"
        comm -23 "$W/.gone1" "$W/tree-all" | awk -v p="$q" '{print p "\t" $0}' >> "$W/l1"
        comm -12 "$W/.gone1" "$W/tree-all" > "$W/.moved1"
        report_moved "$q" "$W/.moved1" "내"
        # ②내 삭제가 이 파일에 되살아남 (base가 다시 추가한 것은 제외 — base의 결정)
        comm -23 "$W/.mydel" "$W/.baseadd" | sort -u > "$W/.mydel2"
        comm -12 "$W/.mydel2" "$W/.postfile" | awk -v p="$q" '{print p "\t" $0}' >> "$W/l2"
        # ③팀원 추가가 트리에 없음 = 팀원 변경 덮어쓰기
        comm -23 "$W/.baseadd" "$W/.postfile" > "$W/.gone3"
        comm -23 "$W/.gone3" "$W/tree-all" | awk -v p="$q" '{print p "\t" $0}' >> "$W/l3"
        comm -12 "$W/.gone3" "$W/tree-all" > "$W/.moved3"
        report_moved "$q" "$W/.moved3" "팀원"
        # ④팀원 삭제가 되살아남 (내가 다시 추가한 것은 제외 — 내 의도)
        comm -23 "$W/.basedel" "$W/.myadd" | sort -u > "$W/.basedel2"
        comm -12 "$W/.basedel2" "$W/.postfile" | awk -v p="$q" '{print p "\t" $0}' >> "$W/l4"
      done < "$W/overlap"

      for pair in "l1:내 추가 라인이 트리에서 사라짐(내 변경 유실)" \
                  "l2:내가 지운 라인이 되살아남(내 변경 미반영)" \
                  "l3:팀원 추가 라인이 트리에서 사라짐(팀원 변경 덮어쓰기)" \
                  "l4:팀원이 지운 라인이 되살아남(팀원 변경 덮어쓰기)"; do
        f="${pair%%:*}"; msg="${pair#*:}"
        if [ -s "$W/$f" ]; then
          halt "OVERLAP — ${msg}: $(wc -l < "$W/$f" | tr -d ' ')건"
          cut -f1 "$W/$f" | sort | uniq -c | sort -rn | awk '{print "  " $2 "  (" $1 "줄)"}' | head -10
          head -2 "$W/$f" | awk -F'\t' '{print "      예: " $2}'
        fi
      done
      [ "$ov_bin" -eq 0 ] || {
        warn "OVERLAP 바이너리 ${ov_bin}개 — 라인 판정 불가, 사람이 확인해야 한다:"
        sed 's|^|  |' "$W/ov-bin"
      }
      info "버킷③ OVERLAP 텍스트 ${ov_text}개 · 바이너리 ${ov_bin}개 검사 완료."
    else
      info "버킷③ OVERLAP 없음 — 경로별 내용 보존 관점의 유실 여지는 없다 (⛔ 팀원이 같은 로직을 다른 경로에 새로 만든 경우는 이 판정 밖)."
    fi

    # ─── 머지 커밋의 수동 해결이 재적용됐는가 ──────────────────────────
    if [ -s "$STATE_DIR/manual-merges.tsv" ]; then
      scan_manual_merges "${base}..${post}" > "$W/post-manual.tsv" || true

      # ⛔ subject 하나만 대조하면 같은 subject의 머지가 하나라도 남을 때 나머지 유실이
      #    통째로 가려진다. 롱텀 브랜치는 "Merge branch 'develop' into ..." 같은 자동
      #    subject가 반복되므로 이 마스킹이 예외가 아니라 기본이다.
      #    subject별 **건수 감소**를 유실로 본다. remerge 줄 수 변동은 리베이스가 머지를
      #    재생성하며 정상적으로 생길 수 있으므로 HALT가 아니라 WARN이다.
      #    ⛔ `FILENAME == ARGV[1]`로 파일을 구분한다 — `NR==FNR`은 첫 파일이 비면
      #    무너지고, 수동 해결 머지가 0건인 경우가 대다수다(같은 함정이 위 파티션에도 있다).
      awk -F'\t' '
        FILENAME == ARGV[1] { pre[$1]++;  pre_lines[$1]  += $2; next }
                            { post[$1]++; post_lines[$1] += $2 }
        END {
          for (subj in pre) {
            pc = (subj in post) ? post[subj] : 0
            if (pre[subj] > pc)
              printf "LOST\t%s\t(PRE %d건 → POST %d건)\n", subj, pre[subj], pc
            else if ((subj in post) && post_lines[subj] < pre_lines[subj])
              printf "SHRUNK\t%s\t(remerge %d줄 → %d줄)\n", subj, pre_lines[subj], post_lines[subj]
          }
        }
      ' "$STATE_DIR/manual-merges.tsv" "$W/post-manual.tsv" | sort > "$W/merge-delta"

      grep '^LOST' "$W/merge-delta" > "$W/merge-lost" || : > "$W/merge-lost"
      grep '^SHRUNK' "$W/merge-delta" > "$W/merge-shrunk" || : > "$W/merge-shrunk"

      if [ -s "$W/merge-lost" ]; then
        halt "수동 해결을 품었던 머지 $(wc -l < "$W/merge-lost" | tr -d ' ')종이 리베이스 후 건수가 줄었다 — --rebase-merges는 해결을 재적용하지 않는다:"
        awk -F'\t' '{print "  " $2 "  " $3}' "$W/merge-lost"
        info "복구: git log -1 --remerge-diff <원래 머지 해시>로 해결 내용을 확인해 수동 재적용."
      fi
      if [ -s "$W/merge-shrunk" ]; then
        warn "머지 건수는 유지됐으나 해결 내용이 줄어든 subject $(wc -l < "$W/merge-shrunk" | tr -d ' ')종 — 재생성에 따른 정상 변동일 수 있으니 사람이 확인할 것:"
        awk -F'\t' '{print "  " $2 "  " $3}' "$W/merge-shrunk"
      fi
      if [ ! -s "$W/merge-lost" ] && [ ! -s "$W/merge-shrunk" ]; then
        info "수동 해결 머지 $(wc -l < "$STATE_DIR/manual-merges.tsv" | tr -d ' ')건 모두 리베이스 후에도 내용 보유."
      fi
    fi

    if [ "$HALT_COUNT" -gt 0 ]; then
      echo "HALT 총 ${HALT_COUNT}건 — force-push 금지. 롤백: git reset --hard ${FZ_ANCHOR:-$FZ_PRE}"
      exit 1
    fi
    echo "OK: 내용 게이트 통과 — 경로 전량 분할 검사 (MINE-only $(wc -l < "$W/mine-only" | tr -d ' ') · OVERLAP $(wc -l < "$W/overlap" | tr -d ' ') · 나머지 base 동일)."
    ;;

  prepush)
    # force-push가 팀원 커밋을 파괴하지 않는지 검사한다. 되돌릴 수 없는 단계라 가장 강한 게이트.
    branch="${2:?prepush requires <branch-ref>}"
    remote="${3:-$(git config --get "branch.${branch}.remote" || true)}"
    rbranch="${4:-$(git config --get "branch.${branch}.merge" | sed 's#^refs/heads/##' || true)}"
    [ -n "$remote" ] || die "push 원격을 알 수 없다. prepush <branch> <remote> <remote-branch> 형태로 지정할 것."
    [ -n "$rbranch" ] || rbranch="$branch"
    track="refs/remotes/${remote}/${rbranch}"
    local_track="$(git rev-parse --verify -q "$track" || true)"
    [ -n "$local_track" ] || die "tracking ref 없음: ${track}. fetch 후 재실행."

    if [ "${FZ_REBASE_SKIP_LSREMOTE:-0}" = "1" ]; then
      warn "원격 실측 생략(FZ_REBASE_SKIP_LSREMOTE=1) — tracking ref가 stale이면 팀원 커밋 파괴를 놓친다."
    else
      remote_actual="$(git ls-remote "$remote" "refs/heads/${rbranch}" 2>/dev/null | awk '{print $1}')"
      [ -n "$remote_actual" ] || die "원격 상태 확인 불가 (${remote} ${rbranch}). force-push는 원격 실측 없이 진행하지 않는다 — 네트워크 확인 후 재시도."
      if [ "$remote_actual" != "$local_track" ]; then
        die "tracking ref가 stale: ${track}=${local_track} vs 원격=${remote_actual}. 내 마지막 fetch 이후 누군가 push했다 — fetch 후 prepush 재실행(그 커밋들을 먼저 반영해야 한다)."
      fi
    fi

    # (a) non-merge 커밋: 패치 등가 판정. 리베이스로 해시가 바뀌어도 오탐하지 않는다.
    cherry_out="$(git cherry -v "$branch" "$track" || true)"
    doomed="$(printf '%s\n' "$cherry_out" | grep -c '^+' || true)"
    if [ "${doomed:-0}" -gt 0 ]; then
      halt "force-push가 파괴할 커밋 ${doomed}건 — 원격에 있고 내 브랜치엔 등가 패치가 없다:"
      printf '%s\n' "$cherry_out" | grep '^+' | awk '{print $2}' | while IFS= read -r sha; do
        git log -1 --format='    %h  %an  %s' "$sha"
      done
      info "해소: 이 커밋들을 먼저 내 브랜치에 반영(ff-merge 또는 리베이스 재실행) 후 prepush 재검사."
    else
      info "원격 non-merge 커밋 전부 내 브랜치에 등가 패치로 존재."
    fi

    # (b) 머지 커밋: git cherry는 머지를 아예 보고하지 않는다 [실측: 3커밋(머지 1) → + 2건].
    #     수동 해결을 품은 머지(evil)는 그 내용이 어느 부모에도 없으므로 파괴 = 내용 유실 → HALT.
    #     내용 없는 평범한 PR 머지는 부모가 (a)에서 판정되므로 구조만 사라진다 → WARN.
    rm_merges=0
    for m in $(git rev-list --merges "${branch}..${track}"); do
      rm_merges=$((rm_merges + 1))
      n="$(git log -1 --remerge-diff --format='' -p "$m" 2>/dev/null | wc -l | tr -d ' ')"
      if [ "${n:-0}" -gt 0 ]; then
        halt "force-push가 파괴할 **수동 해결 머지**: $(git log -1 --format='%h %an %s' "$m") (remerge ${n}줄) — 이 내용은 부모 어디에도 없다."
      else
        warn "원격 머지 커밋 소실 예정(내용은 부모에 보존, 히스토리 구조만 사라짐): $(git log -1 --format='%h %an %s' "$m")"
      fi
    done
    [ "$rm_merges" -eq 0 ] || info "원격 머지 ${rm_merges}건 검사 완료 (수동해결=HALT / 평범=WARN)."

    if [ "$HALT_COUNT" -gt 0 ]; then
      echo "HALT 총 ${HALT_COUNT}건 — force-push 금지."
      exit 1
    fi
    info "lease pin 권장: git push ${remote} ${branch} --force-with-lease=${rbranch}:${local_track}"
    echo "OK: prepush 게이트 통과 (원격 ${local_track} → 로컬 $(git rev-parse "$branch"))."
    ;;

  *)
    echo "usage: verify-rebase.sh snapshot <base-ref> <branch-ref>            # 리베이스 직전" >&2
    echo "       verify-rebase.sh capture  <base-ref> <branch-ref>            # 개수만 (호환)" >&2
    echo "       verify-rebase.sh check    <base-ref> <branch-ref> <expected-commits> <expected-merges> [key-path ...]" >&2
    echo "       verify-rebase.sh audit    <base-ref> <branch-ref>            # 리베이스 후 내용 게이트" >&2
    echo "       verify-rebase.sh prepush  <branch-ref> [<remote> <remote-branch>]  # force-push 전 파괴 검사" >&2
    exit 2
    ;;
esac
