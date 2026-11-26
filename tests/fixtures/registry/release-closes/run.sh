#!/bin/bash
# 릴리스 대조 · 처분 fixture (F-550 · F-142 · F-180 · F-401) — check_release_closes.py 와 eject_findings.py 의
# 새 CLI(--list-applied · --dispose · --with-lock · Closes 의 partial 거부)를 하위 프로세스로 돌려 exit 와 레지스트리를 단언한다.
#
# 셀:
#   closes-cli-violation-exit1   applied: full 인데 Closes 에 없다 → exit 1 · '(a) F-001'
#   closes-cli-ok-exit0          Closes 에 full 전부 → exit 0 · RELEASE_CLOSES_OK
#   closes-cli-note-missing-2    노트 부재 → exit 2 (판정 불가 ≠ 통과)
#   list-applied-lines           --list-applied → 'F-NNN 값 ref slug' 줄
#   eject-partial-refused-cli    Closes 에 applied: partial → eject exit 1 · entries · APPLIED 불변
#   dispose-cli-moves            --dispose rejected → .archive 이동 · APPLIED 넷째 칸 'rejected' · INDEX 행 제거
#   with-lock-cli-nested         --with-lock ROOT -- eject --dispose … → 자식이 같은 잠금을 이어 써서 exit 0
#   closes-dup-id-unrun          같은 ID 의 live 엔트리 둘 → exit 2(slug 를 ID 로 접으면 형제가 숨는다)
#   closes-unknown-applied-violation  applied: "full"(따옴표) → exit 1 · '(g) F-007'
#   closes-four-digit-id-flagged F-1000-slug 를 Closes 에 넣어도 통과하지 않는다 → exit 1 · '(g) F-1000-big.md'(배출기도 거부하는 입력)
#   closes-odd-name-violation    slug 없는 F-551.md → exit 1 · '(g) F-551.md'(조용히 건너뛰지 않는다)
#   eject-unknown-applied-refused-cli  Closes 엔트리의 applied: "partial"(따옴표) → eject exit 1 · 레지스트리 불변
#   closes-pre-rewrite-absent-skipped  applied_ref_era: pre-rewrite 이고 이 저장소에 없는 SHA → exit 0 · 'NOTE F-011'(건너뜀을 드러낸다)
#   closes-pre-rewrite-present-checked 표시가 있어도 객체가 있으면 그대로 본다 — 브랜치 밖 커밋 → exit 1 · 'HEAD 의 조상이 아니다'
#   closes-pre-rewrite-unknown-era     모르는 표시 값 → exit 1 · '(g) F-013' · 없는 SHA 도 건너뛰지 않는다('커밋이 없다')
#   hygiene-pre-rewrite-key-neutral    위생 검사의 exit · 출력이 표시 줄을 더하기 전후로 같다 — 판정 불가 · traceback 이 아니고
#                                      정상 경로 줄 '분모: entries' 가 있어야 한다(검사기가 두 번 같게 죽은 것을 '같다' 로 읽지 않는다)
#   eject-pre-rewrite-key-accepted     표시를 단 full 엔트리를 Closes 로 배출 → exit 0 · archive 로 이동
#   outer-git-dir-ignored              바깥 GIT_DIR(미끼 저장소)을 물려준 자식 실행 → exit 0 · 미끼 저장소 불변(자식은 이 셀을 돌지 않는다)
# 구판 트리(이 CLI 들이 없다)에서는 exit 1 이다. 표시 처리가 없는 트리는 closes-pre-rewrite-absent-skipped 가 FAIL 이다.
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패(인자 · 트리 · git · 단언기 고장)
# ⛔ 임시 레지스트리 · 임시 git 저장소만 쓴다 — 실제 레지스트리 경로는 받지 않는다. 트리에 바이트코드를 남기지 않는다.
#    임시 저장소는 전역 · 시스템 git 설정을 읽지 않고 합성 신원으로 만든다. 시험의 커밋 해시는 실행 때 만든다.
# usage: run.sh [--tree <플러그인 루트>]   (기본: 이 fixture 가 든 트리)
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 3; }
command -v git >/dev/null 2>&1 || { echo "SETUP git 부재"; exit 3; }
[ -f "$R/scripts/eject_findings.py" ] || { echo "SETUP eject_findings.py 없음: $R"; exit 3; }

PYTHONDONTWRITEBYTECODE=1 python3 -B - "$R" "${BASH_SOURCE[0]}" <<'PY'
import os, pathlib, subprocess, sys, tempfile, traceback


def _crash(*exc):
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(3)


sys.excepthook = _crash
TREE = pathlib.Path(sys.argv[1])
CLOSES, EJECT, HYG = TREE / "scripts" / "check_release_closes.py", TREE / "scripts" / "eject_findings.py", TREE / "scripts" / "check_findings_hygiene.py"
FAIL, CELLS = [], []
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", FZ_REGISTRY_LOCK_WAIT="2")
# 바깥 git 환경(훅이 건 GIT_DIR 등)을 끊는다 — 남으면 `git -C <임시 저장소>` 도 바깥 저장소에 쓰고, 검사기도 바깥 저장소를 읽는다
for _k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR",
           "GIT_NAMESPACE", "GIT_PREFIX", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT"):   # 뒤 둘 = 부모 git 의 설정 주입 두 길
    ENV.pop(_k, None)


def check(cell, ok, what):
    CELLS.append(cell)
    print(("PASS  " if ok else "FAIL  ") + f"{cell}: {what}")
    if not ok:
        FAIL.append(cell)


def run(*args):
    p = subprocess.run([sys.executable, "-B", *map(str, args)], capture_output=True, text=True, env=ENV, timeout=120)
    return p.returncode, p.stdout + p.stderr


with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    repo = tmp / "repo"
    (repo / "modules").mkdir(parents=True)
    genv = dict(ENV, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
                GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    for cmd in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-qm", "a", "--allow-empty"]):
        if subprocess.run(["git", "-C", str(repo), *cmd], capture_output=True, env=genv).returncode != 0:
            print(f"SETUP git {cmd[0]} 실패")
            sys.exit(3)
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, env=genv).stdout.strip()
    # 실행 때 만드는 SHA 둘 — 브랜치 밖 커밋(객체는 있고 HEAD 의 조상이 아니다) · 이 저장소에 없는 SHA(HEAD 앞 12자리의 비트를 뒤집는다)
    p = subprocess.run(["git", "-C", str(repo), "commit-tree", "HEAD^{tree}", "-m", "off"], capture_output=True, text=True, env=genv)
    off, gone = p.stdout.strip(), format(int(sha[:12], 16) ^ 0xFFFFFFFFFFFF, "012x")
    if p.returncode != 0 or not off or subprocess.run(["git", "-C", str(repo), "cat-file", "-e", gone], capture_output=True, env=genv).returncode == 0:
        print("SETUP 브랜치 밖 커밋 · 없는 SHA 준비 실패")
        sys.exit(3)
    (repo / "modules" / "promotion-ledger.md").write_text("# 원장\n\n### 배출 기록\n\n- x\n", encoding="utf-8")

    def registry(name, rows):
        root = tmp / name
        (root / "entries").mkdir(parents=True)
        for slug, extra in rows:
            (root / "entries" / f"{slug}.md").write_text(f"---\nid: {slug[:5]}\nstatus: proposed\n{extra}---\n\n# {slug[:5]}\n", encoding="utf-8")
        (root / "APPLIED.md").write_text("# APPLIED\n\n| 날짜 | ID | 한 줄 | 처리 |\n|---|---|---|---|\n", encoding="utf-8")
        (root / "INDEX.md").write_text("# INDEX\n\n## 대기열\n\n| ID | x | 문서 |\n|---|---|---|\n"
                                       + "".join(f"| {s[:5]} | x | [{s[:5]}](entries/{s}.md) |\n" for s, _ in rows), encoding="utf-8")
        return root

    full = f"applied: full\napplied_ref: {sha[:7]}\n"
    root = registry("a", [("F-001-alpha", full), ("F-002-beta", "")])
    note = tmp / "v9.md"
    note.write_text("# v9\n\nCloses: F-002\n", encoding="utf-8")
    rc, out = run(CLOSES, "--findings-root", root, "--note", note, "--repo", repo)
    check("closes-cli-violation-exit1", rc == 1 and "(a) F-001" in out, f"rc={rc} · {out.strip()[-160:]!r}")
    note.write_text("# v9\n\nCloses: F-001\n", encoding="utf-8")
    rc, out = run(CLOSES, "--findings-root", root, "--note", note, "--repo", repo)
    check("closes-cli-ok-exit0", rc == 0 and "RELEASE_CLOSES_OK" in out, f"rc={rc} · {out.strip()[-160:]!r}")
    # F-606 — 코드 울타리 안 예시 Closes(full 아닌 F-002)는 선언이 아니다 — 밖의 F-001 만 대조한다
    note.write_text("# v9\n\nCloses: F-001\n\n```\nCloses: F-002\n```\n", encoding="utf-8")
    rc, out = run(CLOSES, "--findings-root", root, "--note", note, "--repo", repo)
    check("closes-cli-fenced-example-ignored", rc == 0 and "Closes 1 ·" in out and "F-002" not in out, f"rc={rc} · {out.strip()[-160:]!r}")
    rc, out = run(CLOSES, "--findings-root", root, "--note", tmp / "absent.md", "--repo", repo)
    check("closes-cli-note-missing-2", rc == 2 and "RELEASE_CLOSES_OK" not in out, f"rc={rc}")
    rc, out = run(CLOSES, "--findings-root", root, "--list-applied")
    check("list-applied-lines", rc == 0 and f"F-001 full {sha[:7]} F-001-alpha" in out.splitlines(), f"rc={rc} · {out.strip()!r}")

    root = registry("b", [("F-003-gamma", "applied: partial\napplied_ref: pending\n")])
    before = {p.name: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    note.write_text("Closes: F-003\n", encoding="utf-8")
    rc, out = run(EJECT, "--root", root, "--note", note, "--version", "v9")
    after = {p.name: p.read_bytes() for p in root.rglob("*") if p.is_file() and p.name != ".fz-registry.lock"}
    check("eject-partial-refused-cli", rc == 1 and after == before, f"rc={rc} · 레지스트리 불변={after == before}")

    root = registry("c", [("F-004-delta", ""), ("F-005-eps", "")])
    rc, out = run(EJECT, "--dispose", "rejected", "--id", "F-004", "--reason", "stub 조건 그대로", "--root", root)
    ap = (root / "APPLIED.md").read_text(encoding="utf-8")
    row = next((ln for ln in ap.splitlines() if "| F-004-delta |" in ln), "")
    idx = (root / "INDEX.md").read_text(encoding="utf-8")
    check("dispose-cli-moves", rc == 0 and (root / ".archive" / "F-004-delta.md").is_file() and not (root / "entries" / "F-004-delta.md").exists()
          and row.split("|")[4].strip().startswith("rejected") and "entries/F-004-delta.md" not in idx and "entries/F-005-eps.md" in idx,
          f"rc={rc} · 행={row!r}")

    rc, out = run(EJECT, "--with-lock", root, "--", sys.executable, "-B", EJECT, "--dispose", "works", "--id", "F-005",
                  "--reason", "nested", "--root", root)
    check("with-lock-cli-nested", rc == 0 and (root / ".archive" / "F-005-eps.md").is_file(), f"rc={rc} · {out.strip()[-160:]!r}")

    def closes(root, text):
        note.write_text(f"# v9\n\n{text}\n", encoding="utf-8")
        return run(CLOSES, "--findings-root", root, "--note", note, "--repo", repo)

    rc, out = closes(registry("d", [("F-006-one", full), ("F-006-two", full)]), "Closes: F-006-one")
    check("closes-dup-id-unrun", rc == 2 and "같은 ID" in out and "RELEASE_CLOSES_OK" not in out, f"rc={rc} · {out.strip()[-160:]!r}")
    rc, out = closes(registry("e", [("F-007-quoted", f'applied: "full"\napplied_ref: {sha[:7]}\n')]), "Closes: F-007")
    check("closes-unknown-applied-violation", rc == 1 and "(g) F-007" in out, f"rc={rc} · {out.strip()[-160:]!r}")
    rc, out = closes(registry("f", [("F-1000-big", full), ("F-010-small", "")]), "Closes: F-1000-big")
    check("closes-four-digit-id-flagged", rc == 1 and "(g) F-1000-big.md" in out and "RELEASE_CLOSES_OK" not in out,
          f"rc={rc} · {out.strip()[-160:]!r}")
    root = registry("g", [("F-008-ok", "")])
    (root / "entries" / "F-551.md").write_text("---\nid: F-551\napplied: full\n---\n", encoding="utf-8")
    rc, out = closes(root, "Closes: F-008")
    check("closes-odd-name-violation", rc == 1 and "(g) F-551.md" in out, f"rc={rc} · {out.strip()[-160:]!r}")

    root = registry("h", [("F-009-quoted", 'applied: "partial"\napplied_ref: pending\n')])
    before = {p.name: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    note.write_text("Closes: F-009\n", encoding="utf-8")
    rc, out = run(EJECT, "--root", root, "--note", note, "--version", "v9")
    after = {p.name: p.read_bytes() for p in root.rglob("*") if p.is_file() and p.name != ".fz-registry.lock"}
    check("eject-unknown-applied-refused-cli", rc == 1 and after == before and "모른다" in out, f"rc={rc} · 레지스트리 불변={after == before}")

    # 재작성 전 표시(applied_ref_era) — 객체가 없을 때만 건너뛰고 · 있으면 그대로 보고 · 모르는 값은 위반이다.
    # 같은 표시를 단 엔트리를 위생 검사 · 배출기가 거부하거나 다르게 읽지 않는다
    era = "applied_ref_era: pre-rewrite\n"
    rc, out = closes(registry("i", [("F-011-old", f"applied: full\napplied_ref: {gone}\n{era}")]), "Closes: F-011")
    check("closes-pre-rewrite-absent-skipped", rc == 0 and "RELEASE_CLOSES_OK" in out and "NOTE F-011" in out,
          f"rc={rc} · {out.strip()[-160:]!r}")
    rc, out = closes(registry("j", [("F-012-off", f"applied: full\napplied_ref: {off[:9]}\n{era}")]), "Closes: F-012")
    check("closes-pre-rewrite-present-checked", rc == 1 and "(c) F-012" in out and "HEAD 의 조상이 아니다" in out,
          f"rc={rc} · {out.strip()[-160:]!r}")
    rc, out = closes(registry("k", [("F-013-typo", f"applied: full\napplied_ref: {gone}\napplied_ref_era: rewritten\n")]), "Closes: F-013")
    check("closes-pre-rewrite-unknown-era", rc == 1 and "(g) F-013" in out and "커밋이 없다" in out,
          f"rc={rc} · {out.strip()[-160:]!r}")

    # 위생 검사 — 검사기가 두 번 같은 traceback 으로 죽어도 (rc, 출력) 은 같다. 그래서 정상 경로 줄(분모)과 traceback 부재를 함께 본다
    root = registry("m", [("F-014-old", f"applied: full\napplied_ref: {gone}\n")])
    ent = root / "entries" / "F-014-old.md"
    rc0, out0 = run(HYG, "--root", root)
    ent.write_text(ent.read_text(encoding="utf-8").replace("\n---\n", f"\n{era}---\n", 1), encoding="utf-8")
    rc1, out1 = run(HYG, "--root", root)
    check("hygiene-pre-rewrite-key-neutral", era in ent.read_text(encoding="utf-8") and rc0 != 2 and "분모: entries" in out0
          and "Traceback (most recent call last)" not in out0 and (rc0, out0) == (rc1, out1),
          f"rc={rc0}→{rc1} · 출력 같음={out0 == out1} · {out0.strip()[-160:]!r}")
    note.write_text("Closes: F-014\n", encoding="utf-8")
    rc, out = run(EJECT, "--root", root, "--note", note, "--version", "v9")
    check("eject-pre-rewrite-key-accepted", rc == 0 and (root / ".archive" / "F-014-old.md").is_file() and not ent.exists(),
          f"rc={rc} · {out.strip()[-160:]!r}")

    # 바깥 git 환경 — GIT_DIR 이 미끼 저장소를 가리키는 채로 이 러너를 다시 돈다. 끊지 않으면 임시 저장소 준비(init · 커밋)가 미끼에 쓴다
    if not os.environ.get("FZ_RELCLOSES_CHILD"):
        decoy = tmp / "decoy"
        decoy.mkdir()
        dg = lambda *a: subprocess.run(["git", "-C", str(decoy), *a], capture_output=True, text=True, env=genv)
        made = all(dg(*c).returncode == 0 for c in (["init", "-q", "-b", "main"], ["commit", "-qm", "decoy", "--allow-empty"]))
        head0 = dg("rev-parse", "HEAD").stdout.strip()
        if not made or not head0:
            print("SETUP 미끼 저장소 준비 실패")
            sys.exit(3)
        c = subprocess.run(["bash", sys.argv[2], "--tree", str(TREE)], capture_output=True, text=True, timeout=600,
                           # 부모 git 의 설정 주입(서명 강제 + 실패하는 서명 프로그램 — 두 길)도 함께 준다 — 끊지 않으면 임시 저장소 준비가 실패한다
                           env=dict(os.environ, FZ_RELCLOSES_CHILD="1", GIT_DIR=str(decoy / ".git"),
                                    GIT_CONFIG_PARAMETERS="'commit.gpgsign=true' 'gpg.program=false'", GIT_CONFIG_COUNT="2",
                                    GIT_CONFIG_KEY_0="commit.gpgsign", GIT_CONFIG_VALUE_0="true",
                                    GIT_CONFIG_KEY_1="gpg.program", GIT_CONFIG_VALUE_1="false"))
        head1, count = dg("rev-parse", "HEAD").stdout.strip(), dg("rev-list", "--count", "--all").stdout.strip()
        check("outer-git-dir-ignored", c.returncode == 0 and head1 == head0 and count == "1",
              f"자식 rc={c.returncode} · 미끼 HEAD 불변={head1 == head0} · 미끼 커밋 수={count} · {c.stdout.strip()[-120:]!r}")

n = len(set(CELLS))
print(f"{'OK' if not FAIL else 'FAIL'}: {n - len(set(FAIL))}/{n}")
sys.exit(1 if FAIL else 0)
PY
