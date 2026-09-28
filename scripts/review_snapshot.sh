#!/bin/bash
# lint:no-root-anchor — 플러그인 루트를 쓰지 않는다(입력은 --repo · --out 인자 · SELF 는 self-test 가 자기를 다시 부르는 경로다).
# fz-review 사전 수집 스냅샷 (S22b) — 리뷰 대상 변경의 diff · 변경 파일 base/head 본문 · 규칙 레코드를 한 폴더에 결정론으로 모은다.
#
# 사용: review_snapshot.sh --repo R --out DIR [--base REF] [--rules F]
#       review_snapshot.sh --self-test
#   --base 기본 HEAD — 작업 트리(스테이지 + 미스테이지) 대 REF. 추적되지 않은 새 파일도 added 로 넣는다(fz-review 는 미커밋 변경을 본다)
# 산출(DIR): diff.patch · manifest.tsv(status · old · new · binary 탭 구분) · base/<old> · head/<new> · project-rules.json(--rules 시)
#   base/ · head/ 는 저장소 경로 그대로 미러링한다 — skills/fz-peer-review/scripts/gather.sh 와 같은 배치 · 같은 경로 가드(safe).
#   목록은 diff 텍스트가 아니라 `git diff --name-status -M -z` 로 만든다 — NUL 구분이라 공백 · 따옴표 경로에서 흔들리지 않는다.
#   바이너리(앞 8000 바이트에 NUL — git 과 같은 판별)는 본문을 싣지 않고 manifest 에 표시한다.
# ⛔ Lead 가 손으로 고르지 않는다 — 워커와 GPT 독립 첫 패스가 같은 입력을 보게 하는 것이 목적이다(base/ · head/ 를 런처 --base · --head 에 그대로 준다).
# ⛔ --out 이 이미 있고 비어 있지 않으면 거부한다 — 지난 실행의 파일이 섞이면 스냅샷이 결정론이 아니다.
# exit: 0 성공 · 10 사용법 · 11 사전조건(git 저장소 아님 · REF 해석 실패 · --rules 없음) · 12 쓰기 실패
set -u
SELF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
if [ "${1:-}" = "--self-test" ]; then
  exec python3 - "$SELF" <<'PY'
import os, pathlib, subprocess, sys, tempfile
me = sys.argv[1]
res = []
def case(name, ok, got=""):
    res.append(ok); print(f"{'PASS' if ok else 'FAIL'}  {name}{'' if ok else f' — {got}'}")
def git(repo, *a):
    subprocess.run(["git", "-C", repo, *a], check=True, capture_output=True)
with tempfile.TemporaryDirectory(prefix="fz-snapshot-") as t:
    t = pathlib.Path(t); repo = t / "repo"; repo.mkdir()
    git(str(repo), "init", "-q"); git(str(repo), "config", "user.email", "t@example.invalid"); git(str(repo), "config", "user.name", "t")
    (repo / "keep.txt").write_text("keep\n"); (repo / "mod.txt").write_text("a\n"); (repo / "del.txt").write_text("gone\n")
    (repo / "ren_old.txt").write_text("renamed body line 1\nrenamed body line 2\nrenamed body line 3\n")
    (repo / "bin.dat").write_bytes(b"\x00\x01\x02binary")
    git(str(repo), "add", "-A"); git(str(repo), "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", "commit", "-qm", "base")   # 사용자 전역 훅 · 서명 설정과 끊는다
    (repo / "mod.txt").write_text("b\n"); (repo / "del.txt").unlink()
    (repo / "dir").mkdir(); git(str(repo), "mv", "ren_old.txt", "dir/ren_new.txt")
    (repo / "bin.dat").write_bytes(b"\x00\x09\x09binary2")
    (repo / "new file.txt").write_text("untracked\n")
    out = t / "snap"
    r = subprocess.run(["bash", me, "--repo", str(repo), "--out", str(out)], capture_output=True, text=True)
    case("정상 실행 exit 0", r.returncode == 0, f"exit {r.returncode} · {r.stderr.strip()[-200:]}")
    rows = [l.split("\t") for l in (out / "manifest.tsv").read_text().splitlines()] if (out / "manifest.tsv").exists() else []
    got = {(s, o, n, b) for s, o, n, b in rows}
    want = {("modified", "mod.txt", "mod.txt", "0"), ("deleted", "del.txt", "", "0"), ("renamed", "ren_old.txt", "dir/ren_new.txt", "0"),
            ("modified", "bin.dat", "bin.dat", "1"), ("added", "", "new file.txt", "0")}
    case("manifest — 수정 · 삭제 · rename · 바이너리 · 공백 든 미추적 새 파일", got == want, sorted(got))
    b, h = out / "base", out / "head"
    case("base/ — 옛 본문(수정 · 삭제 · rename 옛 경로)", (b / "mod.txt").read_text() == "a\n" and (b / "del.txt").exists() and (b / "ren_old.txt").exists())
    case("head/ — 새 본문(수정 · rename 새 경로 · 미추적) · 삭제 파일 없음",
         (h / "mod.txt").read_text() == "b\n" and (h / "dir" / "ren_new.txt").exists() and (h / "new file.txt").exists() and not (h / "del.txt").exists())
    case("바이너리 — 본문을 싣지 않는다(manifest 에 표시)", not (b / "bin.dat").exists() and not (h / "bin.dat").exists())
    d = (out / "diff.patch").read_text(errors="replace") if (out / "diff.patch").exists() else ""
    case("diff.patch — 추적 변경 + 미추적 새 파일", "mod.txt" in d and "new file.txt" in d and "rename to dir/ren_new.txt" in d, d[:120])
    r2 = subprocess.run(["bash", me, "--repo", str(repo), "--out", str(out)], capture_output=True, text=True)
    case("--out 이 비어 있지 않으면 exit 10(지난 파일과 섞지 않는다)", r2.returncode == 10, f"exit {r2.returncode}")
    rules = t / "rules.json"; rules.write_text('{"rules": []}\n')
    r3 = subprocess.run(["bash", me, "--repo", str(repo), "--out", str(t / "snap2"), "--rules", str(rules)], capture_output=True, text=True)
    case("--rules — project-rules.json 사본", r3.returncode == 0 and (t / "snap2" / "project-rules.json").read_text() == '{"rules": []}\n', f"exit {r3.returncode}")
    codes = [subprocess.run(["bash", me, *a], capture_output=True, text=True).returncode for a in (
        ["--repo", str(repo)], ["--repo", str(t), "--out", str(t / "s3")], ["--repo", str(repo), "--out", str(t / "s4"), "--base", "no-such-ref"],
        ["--repo", str(repo), "--out", str(t / "s5"), "--rules", str(t / "none.json")])]
    case("사용법 10 · git 저장소 아님 11 · REF 해석 실패 11 · --rules 없음 11", codes == [10, 11, 11, 11], codes)
print(f"self-test {sum(res)}/{len(res)} passed")
sys.exit(0 if all(res) else 1)
PY
fi

REPO="" OUT="" BASE="HEAD" RULES=""
die() { echo "review_snapshot: $2" >&2; exit "$1"; }
while [ $# -gt 0 ]; do
  case "$1" in
    --repo)  [ $# -ge 2 ] || die 10 "--repo 값 없음"; REPO="$2"; shift 2 ;;
    --out)   [ $# -ge 2 ] || die 10 "--out 값 없음"; OUT="$2"; shift 2 ;;
    --base)  [ $# -ge 2 ] || die 10 "--base 값 없음"; BASE="$2"; shift 2 ;;
    --rules) [ $# -ge 2 ] || die 10 "--rules 값 없음"; RULES="$2"; shift 2 ;;
    *) die 10 "모르는 인자: $1" ;;
  esac
done
[ -n "$REPO" ] && [ -n "$OUT" ] || die 10 "사용: review_snapshot.sh --repo R --out DIR [--base REF] [--rules F] | --self-test"
git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1 || die 11 "git 저장소가 아니다: $REPO"
git -C "$REPO" rev-parse --verify --quiet "${BASE}^{commit}" >/dev/null || die 11 "REF 를 해석하지 못했다: $BASE"
[ -z "$RULES" ] || [ -f "$RULES" ] || die 11 "--rules 파일 없음: $RULES"
if [ -e "$OUT" ] && [ -n "$(/bin/ls -A "$OUT" 2>/dev/null)" ]; then die 10 "--out 이 비어 있지 않다: $OUT"; fi
mkdir -p "$OUT/base" "$OUT/head" || die 12 "출력 폴더를 만들지 못했다: $OUT"

python3 - "$REPO" "$OUT" "$BASE" "$RULES" <<'PY' || exit $?
import os, shutil, subprocess, sys
repo, out, base, rules = sys.argv[1:5]

def git(*a, ok=(0,)):
    r = subprocess.run(["git", "-C", repo, *a], capture_output=True)
    if r.returncode not in ok:
        print(f"review_snapshot: git {' '.join(a[:3])} 실패 — {r.stderr.decode(errors='replace').strip()[-200:]}", file=sys.stderr)
        sys.exit(12)
    return r.stdout

def safe(p):
    """base/ · head/ 밖으로 쓰지 못하게 막는다 — gather.sh 와 같은 규칙(절대 경로 · 빈 조각 · .. 거부)."""
    if not p or p.startswith("/"):
        return None
    return None if any(seg in ("..", "") for seg in p.split("/")) else p

def is_binary(data):
    return b"\0" in data[:8000]

STATUS = {"A": "added", "M": "modified", "T": "modified", "D": "deleted", "R": "renamed", "C": "copied"}
entries = []
toks = git("diff", "--name-status", "-M", "-z", base, "--").split(b"\0")
i = 0
while i < len(toks) and toks[i]:
    code = toks[i].decode()[0]
    if code in "RC":
        entries.append((STATUS[code], toks[i + 1].decode("utf-8", "surrogateescape"), toks[i + 2].decode("utf-8", "surrogateescape"))); i += 3
    elif code in STATUS:
        p = toks[i + 1].decode("utf-8", "surrogateescape")
        entries.append((STATUS[code], "" if code == "A" else p, "" if code == "D" else p)); i += 2
    else:   # U(병합 충돌) 등 — 스냅샷에 싣지 않고 알린다
        print(f"review_snapshot: 상태 {code} 는 싣지 않는다 — {toks[i + 1].decode(errors='replace')}", file=sys.stderr); i += 2
untracked = [p.decode("utf-8", "surrogateescape") for p in git("ls-files", "--others", "--exclude-standard", "-z").split(b"\0") if p]
entries += [("added", "", p) for p in untracked]

patch = git("diff", "-M", base, "--")
for p in untracked:   # --no-index 는 차이가 있으면 exit 1 이다
    patch += subprocess.run(["git", "-C", repo, "diff", "--no-index", "--", "/dev/null", p], capture_output=True).stdout
try:
    open(os.path.join(out, "diff.patch"), "wb").write(patch)
    rows = []
    for status, old, new in entries:
        binary = False
        o, n = safe(old), safe(new)
        if (old and not o) or (new and not n):
            print(f"review_snapshot: 경로 가드 — 싣지 않는다: {old or new}", file=sys.stderr); continue
        if o:
            data = git("show", f"{base}:{o}")
            binary |= is_binary(data)
            if not is_binary(data):
                os.makedirs(os.path.dirname(os.path.join(out, "base", o)) or out, exist_ok=True)
                open(os.path.join(out, "base", o), "wb").write(data)
        if n:
            src = os.path.join(repo, n)
            if os.path.isfile(src) and not os.path.islink(src):
                data = open(src, "rb").read()
                binary |= is_binary(data)
                if not is_binary(data):
                    os.makedirs(os.path.dirname(os.path.join(out, "head", n)) or out, exist_ok=True)
                    open(os.path.join(out, "head", n), "wb").write(data)
        rows.append(f"{status}\t{o or ''}\t{n or ''}\t{int(binary)}")
    open(os.path.join(out, "manifest.tsv"), "w", encoding="utf-8").write("\n".join(rows) + ("\n" if rows else ""))
    if rules:
        shutil.copyfile(rules, os.path.join(out, "project-rules.json"))
except OSError as e:
    print(f"review_snapshot: 쓰기 실패 — {e}", file=sys.stderr); sys.exit(12)
nb = sum(1 for r in rows if r.endswith("\t1"))
print(f"SNAPSHOT OK files={len(rows)} binary={nb} base={base} → {out}")
PY
