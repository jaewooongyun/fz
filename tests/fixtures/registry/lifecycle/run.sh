#!/bin/bash
# findings · 승격 원장 수명주기 (F-477 · F-493 — B9).
#
# 셀:
#   expiry-boundary  합성 원장(now 2026-09-22): 정확히 3개월 되는 날 → 재평가필요 · 하루 모자람 → 유지 · 날짜 없음 → 판정불가
#                    · DEFERRED 는 6개월이라 유지 · '카운트 보류' 관측은 시계를 갱신하지 않는다
#   dup-merge        같은 OBS 세션을 나중 날짜로 다시 적어도 관측 1회 · 첫 날짜 유지(재기록이 시계를 되돌리지 않는다)
#   numeric-regen    check_report_regen: 재생성 명령이 있는 수치 표 → 0 · 칸 없음 → 1
#   consumer-call    fz-memory gc 가 적은 명령 그대로 실제 원장을 판정하고 요약 줄을 낸다
#   no-delete        판정 뒤 실제 원장 · 합성 원장의 바이트가 그대로다
# 출력: 셀마다 `<셀>: PASS|FAIL <이유>` · 끝에 `registry-lifecycle: PASS|FAIL`
# exit: 0 전건 통과 · 1 단언 실패 · 2 준비 실패
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." 2>/dev/null && pwd)"
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 2; }
for f in scripts/candidate_expiry.py modules/promotion-ledger.md skills/fz-memory/SKILL.md; do
  [ -f "$ROOT/$f" ] || { echo "SETUP $f 없음: $ROOT"; exit 2; }
done

PYTHONDONTWRITEBYTECODE=1 python3 -B - "$ROOT" <<'PY'
import hashlib, os, re, subprocess, sys, tempfile
ROOT = sys.argv[1]
CE = os.path.join(ROOT, "scripts", "candidate_expiry.py")
RG = os.path.join(ROOT, "scripts", "check_report_regen.py")
fails = []


def case(name, problems):
    print(f"{name}: {'PASS' if not problems else 'FAIL'}" + ("" if not problems else " " + "; ".join(problems)))
    if problems:
        fails.append(name)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


LEDGER = """# 합성 승격 원장
### L-1: 정확히 3개월
- 관측 #1: OBS-01 | Date: 2026-06-22 | finding-source: internal
### L-2: 하루 모자람
- 관측 #1: OBS-02 | Date: 2026-06-23
### L-3: 날짜 없음
- 관측 #1: OBS-03 (날짜 미기록)
### L-4: 보류 중 DEFERRED
- 관측 #1: OBS-04 | Date: 2026-06-22
- 상태: DEFERRED
### L-5: 보류 관측은 시계를 안 바꾼다
- 관측 #1: OBS-05 | Date: 2026-06-01
- 관측 #2: OBS-06 | Date: 2026-09-01 (⚠️ 카운트 보류)
### L-6: 같은 세션 재기록
- 관측 #1: OBS-11 | Date: 2026-06-22
- 관측 #2: OBS-11 | Date: 2026-09-10 (같은 세션 다시 적음)
### REJECTED
- ~~무시되는 절~~
"""
d = tempfile.mkdtemp(prefix="lifecycle-")
led = os.path.join(d, "ledger.md")
open(led, "w", encoding="utf-8").write(LEDGER)
before_fixture, real = sha(led), os.path.join(ROOT, "modules", "promotion-ledger.md")
before_real = sha(real)

r = subprocess.run([sys.executable, CE, "--ledger", led, "--now", "2026-09-22"], capture_output=True, text=True)
rows = {m.group(1): m.group(2) for m in re.finditer(r"^(L-\d+)\t.*→ (\S+)", r.stdout, re.M)}
want = {"L-1": "재평가필요", "L-2": "유지", "L-3": "판정불가", "L-4": "유지", "L-5": "재평가필요"}
p = [f"{k}: {rows.get(k)} != {v}" for k, v in want.items() if rows.get(k) != v]
if r.returncode != 2:
    p.append(f"exit {r.returncode} != 2 (판정불가가 있으면 통과가 아니다)")
case("expiry-boundary", p)

p = []
l6 = re.search(r"^L-6\t.*$", r.stdout, re.M)
if not l6 or "obs=1(" not in l6.group(0) or "last=2026-06-22" not in l6.group(0) or rows.get("L-6") != "재평가필요":
    p.append(f"same-session re-record changed the clock or count: {l6.group(0) if l6 else 'no L-6 row'}")
case("dup-merge", p)

p = []
good = os.path.join(d, "good.md"); bad = os.path.join(d, "bad.md")
open(good, "w").write("| 항목 | 수치 | 재생성 |\n|---|---|---|\n| 파일 | 3 | `ls \\| wc -l` |\n")
open(bad, "w").write("| 항목 | 수치 |\n|---|---|\n| 파일 | 3 |\n")
for path, rc_want in ((good, 0), (bad, 1)):
    rc = subprocess.run([sys.executable, RG, path], capture_output=True, text=True).returncode if os.path.isfile(RG) else -1
    if rc != rc_want:
        p.append(f"{os.path.basename(path)}: exit {rc} != {rc_want}")
case("numeric-regen", p)

p = []
skill = open(os.path.join(ROOT, "skills", "fz-memory", "SKILL.md"), encoding="utf-8").read()
m = re.search(r'`python3 "\$\{FZ_PLUGIN_ROOT\}/scripts/candidate_expiry\.py" --ledger "\$\{FZ_PLUGIN_ROOT\}/modules/promotion-ledger\.md"`', skill)
if not m:
    p.append("fz-memory gc does not carry the ledger invocation")
else:
    cmd = m.group(0).strip("`").replace("${FZ_PLUGIN_ROOT}", ROOT)
    r2 = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
    if r2.returncode not in (0, 1, 2) or not re.search(r"^ledger: \d+ entries", r2.stdout, re.M):
        p.append(f"consumer command did not produce a ledger summary: rc={r2.returncode} {r2.stdout[-120:]}{r2.stderr[-120:]}")
case("consumer-call", p)

p = []
if sha(led) != before_fixture:
    p.append("fixture ledger changed")
if sha(real) != before_real:
    p.append("modules/promotion-ledger.md changed")
case("no-delete", p)

print(f"registry-lifecycle: {'PASS' if not fails else 'FAIL'}")
sys.exit(0 if not fails else 1)
PY
