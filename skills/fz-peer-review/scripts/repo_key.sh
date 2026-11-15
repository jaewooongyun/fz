# shellcheck shell=bash
# repo_key — 원격 URL · PR url 앞부분을 `owner/repo`(소문자)로 정규화한다. gather.sh · fetch_pr_refs.sh 가 source 한다.
# ⛔ 한 곳에만 둔다 — 두 스크립트가 서로 다른 규칙으로 원격을 고르면 Step 0.5 와 Step 1 이 다른 원격을 본다(F-414 ②).
# https · ssh · scp 꼴(`git@host:o/r`) · 로컬 경로 모두 마지막 두 경로 조각을 쓴다. 경로 조각이 둘 미만이면 실패(1).
repo_key() {
  local u="${1%/}" o r
  u="${u%.git}"
  u="${u//:/\/}"
  case "$u" in */*) ;; *) return 1 ;; esac
  r="${u##*/}" o="${u%/*}"
  o="${o##*/}"
  [ -n "$o" ] && [ -n "$r" ] || return 1
  printf '%s/%s\n' "$o" "$r" | tr '[:upper:]' '[:lower:]'
}

# PR url(`…/owner/repo/pull/N`)과 URL 이 맞는 원격 이름 — upstream · origin 을 먼저, 그다음 나머지. 없으면 실패(1).
remote_for_pr_url() {
  local want rem rem_url
  case "$1" in */pull/[0-9]*) want=$(repo_key "${1%/pull/*}") || return 1 ;; *) return 1 ;; esac
  for rem in upstream origin $(git remote 2>/dev/null); do
    rem_url=$(git remote get-url "$rem" 2>/dev/null) || continue
    [ "$(repo_key "$rem_url")" = "$want" ] && { printf '%s\n' "$rem"; return 0; }
  done
  return 1
}
