#!/bin/bash
# diff-parse: not-a-diff — 이 러너는 render_review.py 산출물과 diff_anchors.py 의 JSON 출력만 대조한다. diff 파싱은 diff_anchors.py 소관.
# 리뷰 산출물 단일 출처 (S20b) — review.json 하나에서 세 산출물을 만들고, 서로와 diff_anchors CLI 에 대조한다.
#   인자 없음  render_review.py --self-test → fixture 렌더 대조. health-check 가 이 모드로 돈다(git 이력 불필요)
#   ⛔ 옛 `--default-path-unchanged`(두 SKILL 보호 구간을 기준 SHA 와 대조)는 4.51.0 에서 지웠다 — 호출처 0 으로 수 주 FAIL 이었고(F-354)
#      보호 구간이 W4(Curate) SKILL 변경과 설계상 충돌한다. 다른 인자는 UNRUN(exit 2)
# modes: default caller=health
# exit: 0 전건 통과 / 1 불일치 / 2 실행 불가
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HERE/../../../.."
RR="$ROOT/scripts/render_review.py"
DA="$ROOT/skills/fz-peer-review/scripts/diff_anchors.py"
FX="$ROOT/skills/fz-peer-review/references/fixtures/synthetic-sample.patch"
[ -f "$RR" ] && [ -f "$DA" ] && [ -f "$FX" ] || { echo "render_review.py · diff_anchors.py · 합성 patch 중 없는 것이 있다" >&2; exit 2; }
python3 - "$ROOT" "$HERE" "${1:-}" <<'PY'
import json, os, re, shutil, subprocess, sys, tempfile
root, here, mode = sys.argv[1:4]
RR = os.path.join(root, "scripts/render_review.py")
DA = os.path.join(root, "skills/fz-peer-review/scripts/diff_anchors.py")
FX = os.path.join(root, "skills/fz-peer-review/references/fixtures/synthetic-sample.patch")
REVIEW = os.path.join(here, "review.json")
MARK = re.compile(r"<!-- fz-review:([A-Za-z0-9:_.\-]+) -->")
fails = 0

def check(name, ok, detail=""):
    global fails
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else f" — {detail}"))
    fails += 0 if ok else 1

def run(args):
    return subprocess.run([sys.executable, RR, *args], capture_output=True, text=True)

def render(review_path, out):
    r = run(["--review", review_path, "--diff", FX, "--out-dir", out])
    return r.returncode, r.stderr

def fixture():
    r = run(["--self-test"])
    check("render_review.py --self-test", r.returncode == 0, (r.stdout + r.stderr).strip().split("\n")[-1])
    tmp = tempfile.mkdtemp(prefix="render-fixture-")
    try:
        review = json.load(open(REVIEW, encoding="utf-8"))
        out = os.path.join(tmp, "a")
        rc, err = render(REVIEW, out)
        if rc != 0:
            check("fixture 렌더 exit 0", False, err.strip())
            return
        rep = open(os.path.join(out, "review-report.md"), encoding="utf-8").read()
        com = open(os.path.join(out, "pr-comments.md"), encoding="utf-8").read()
        pay = json.load(open(os.path.join(out, "payload.json"), encoding="utf-8"))
        pre = json.load(open(os.path.join(out, "render-preview.json"), encoding="utf-8"))
        ids = {i["id"] for i in review["issues"]}
        s_rep, s_com = set(MARK.findall(rep)), set(MARK.findall(com))
        s_pay = {m for c in pay["comments"] for m in MARK.findall(c["body"])} | set(pre["reportOnly"])
        check("세 산출물의 이슈 id 집합이 같다(리포트 · 코멘트 · payload 인라인 ∪ reportOnly)", s_rep == s_com == s_pay == ids, (s_rep, s_com, s_pay))
        check("top-level body = review-report.md 전문", pay["body"] == rep)

        sites = {i["id"]: i["sites"] for i in review["issues"]}
        bad = []
        for row, c in zip(pre["inline"], pay["comments"]):
            s = sites[row["id"]][row["site"]]
            t = [{"path": s["path"], "start": s["start"], "end": s["end"], "side": s.get("side", "RIGHT")}]
            d = subprocess.run([sys.executable, DA, "--diff", FX, "--targets", json.dumps(t)], capture_output=True, text=True)
            a = json.loads(d.stdout)["anchorable"][s.get("pick", 0)]
            want = (a["path"], a["start_line"], a["line"], a["side"])
            got = (c["path"], c.get("start_line", c["line"]), c["line"], c["side"])
            if want != got or MARK.findall(c["body"]) != [row["id"]]:
                bad.append((row["id"], row["part"], got, want))
        check(f"인라인 {len(pay['comments'])}건의 앵커가 diff_anchors.py CLI 결과와 같다(pick 반영)",
              len(pre["inline"]) == len(pay["comments"]) == 7 and not bad, bad or f"인라인 {len(pay['comments'])}건")
        multi = [c for c in pay["comments"] if "start_line" in c]
        single = [c for c in pay["comments"] if "start_line" not in c]
        check("다중 라인은 start_side 가 side 와 짝 · 단일 줄은 start_* 가 없다",
              all(c.get("start_side") == c["side"] and c["start_line"] < c["line"] for c in multi)
              and all("start_side" not in c for c in single) and len(single) == 1, (len(multi), len(single)))

        def of(iid):
            return [c for c in pay["comments"] if MARK.findall(c["body"]) == [iid]]
        m1 = of("M1")
        heads = [c["body"].split("\n", 1)[1][:5] for c in m1]
        check("M1 — 지점 3개는 [1/3] · [2/3] · [3/3] 코멘트 셋이고 [2/3] 은 LEFT", heads == ["[1/3]", "[2/3]", "[3/3]"] and m1[1]["side"] == "LEFT", heads)
        a2 = of("A2")
        check("A2 — 지점 2개 중 diff 밖 지점은 한 코멘트 본문에 코드로 인용", len(a2) == 1 and "EngineContext.swift:122-140" in a2[0]["body"] and "cache[key]" in a2[0]["body"], a2)
        check("S1 — 인라인 자리가 없는 이슈는 리포트에만 남는다(reportOnly)", pre["reportOnly"] == ["S1"] and not of("S1") and "### [suggestion] S1" in rep, pre["reportOnly"])
        c1 = of("C1")
        check("C1 — 겹치는 hunk 두 후보 중 pick 1 = 431-439", len(c1) == 1 and (c1[0]["start_line"], c1[0]["line"]) == (431, 439), c1)
        rs = pre["reasons"]
        check("확인 게이트 — (b) 앵커 불가 · (c) 구간 선택 · (a) 없음(event COMMENT)",
              pre["confirmRequired"] and any(x.startswith("(b)") for x in rs) and any(x.startswith("(c)") for x in rs)
              and not any(x.startswith("(a)") for x in rs), rs)

        out2 = os.path.join(tmp, "b")
        render(REVIEW, out2)
        names = sorted(os.listdir(out))
        same = names == sorted(os.listdir(out2)) and all(open(os.path.join(out, f), "rb").read() == open(os.path.join(out2, f), "rb").read() for f in names)
        check("같은 입력을 두 번 렌더하면 산출물이 바이트 단위로 같다", same, names)

        def write(name, text):
            p = os.path.join(tmp, name)
            open(p, "w", encoding="utf-8").write(text)
            return p
        nopick = json.loads(json.dumps(review))
        next(i for i in nopick["issues"] if i["id"] == "C1")["sites"][0].pop("pick")
        for name, path, want in [("pick 없는 겹침", write("nopick.json", json.dumps(nopick, ensure_ascii=False)), 1),
                                 ("빈 JSON {}", write("empty.json", "{}"), 2), ("빈 파일", write("blank.json", ""), 2)]:
            o = os.path.join(tmp, "x-" + os.path.basename(path))
            rc, _ = render(path, o)
            check(f"{name} → exit {want} · 산출물을 남기지 않는다", rc == want and not os.path.exists(o), f"exit {rc} · 폴더 {os.path.exists(o)}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if mode:
    print(f"UNRUN  모르는 인자 {mode} — 인자를 받지 않는다(옛 --default-path-unchanged 는 4.51.0 에서 지웠다 · F-354)")
    sys.exit(2)
fixture()
print(f"\n렌더 단일 출처 {'전건 통과' if not fails else f'실패 {fails}건'}")
sys.exit(1 if fails else 0)
PY
