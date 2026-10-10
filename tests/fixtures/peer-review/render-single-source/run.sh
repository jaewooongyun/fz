#!/bin/bash
# diff-parse: not-a-diff — 이 러너는 render_review.py 산출물과 diff_anchors.py 의 JSON 출력만 대조한다. diff 파싱은 diff_anchors.py 소관.
# 리뷰 산출물 단일 출처 (S20b) — review.json 하나에서 세 산출물을 만들고, 서로와 diff_anchors CLI 에 대조한다.
#   인자 없음                 render_review.py --self-test → fixture 렌더 대조. health-check 가 이 모드로 돈다(git 이력 불필요)
#   --default-path-unchanged  옵션 미지정 절차가 기준과 같은가 — 두 SKILL 의 보호 구간에서 기준 줄이 순서대로 전부 남고,
#                             더한 줄은 모두 렌더 줄이며, 렌더러 경로가 실제로 들어갔다(양성 대조).
#                             렌더 줄 = fz-review(렌더 opt-in)는 --render 조건부 줄 · fz-peer-review(v4.42.0 렌더 기본)는 렌더를 말하는 줄
#                             기준 = FZ_REGRESSION_BASE_TREE 또는 git ${FZ_REGRESSION_BASE_SHA:-13755a6} — 둘 다 없으면 exit 2
#                             범용 FZ_BASE_TREE · FZ_BASE_SHA 는 읽지 않는다(A/B 가 다른 뜻으로 쓴다 — F-363). 새 이름 없이 옛 이름만 있으면
#                             WARN 줄을 내고 기본값으로 돈다. 검사 이름의 `기준(…)` 이 출처다
#                             의도된 변경(INTENDED)은 기준 줄을 정확 치환한 뒤 대조한다 — fz-peer-review Deliver 흐름 줄 1건(착지 검증 →
#                             verify_landing.py 판정 규칙 · F-150). 기준 SHA 는 그대로 · 보호 구간도 그대로이고, 같은 기준 · 구간에서
#                             음성 대조 3건(다른 보호 줄 변경 · 의도 줄 변형 · 옛 줄 없는 기준)이 FAIL 로 나와야 통과다.
#                             의도 변환 대상 파일이 보호 구간 목록(guard)에 없거나, 변환 적용 수 ≠ 의도 수, 음성 대조 실행 수 ≠ 3 이면 FAIL
#                             (guard 항목을 빼거나 음성 대조 블록을 지우면 둘 다 돌지 않은 채 통과한다 — F-408). 끝 줄에 음성 대조 실행 수를 적는다
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

def default_path():
    # 넷째 = 렌더가 그 스킬의 기본인가(v4.42.0 — fz-peer-review 만). 기본이면 더한 줄이 `--render` 를 안 써도 렌더를 말하면 된다
    guard = [("skills/fz-peer-review/SKILL.md", "## Step: Synthesize", "## 4-Tier Graceful Degradation", True),
             ("skills/fz-review/SKILL.md", "## Phase 7: Completion", "## ", False)]
    env = os.environ
    tree, sha = env.get("FZ_REGRESSION_BASE_TREE"), env.get("FZ_REGRESSION_BASE_SHA") or "13755a6"
    src = "FZ_REGRESSION_BASE_TREE" if tree else f"git {sha}({'FZ_REGRESSION_BASE_SHA' if env.get('FZ_REGRESSION_BASE_SHA') else '기본값'})"
    # 옛 이름은 있는지만 본다 — 그 값은 기준에 쓰지 않는다(조용한 기본값 복귀만 알린다)
    if not tree and not env.get("FZ_REGRESSION_BASE_SHA") and (env.get("FZ_BASE_SHA") or env.get("FZ_BASE_TREE")):
        print("WARN: FZ_BASE_* 는 무시된다 — FZ_REGRESSION_BASE_*")

    def base_text(rel):
        if tree:
            p = os.path.join(tree, rel)
            return open(p, encoding="utf-8").read() if os.path.isfile(p) else None
        r = subprocess.run(["git", "-C", root, "show", f"{sha}:{rel}"], capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else None

    def section(text, start, stop):
        ls = text.split("\n")
        i = next((k for k, l in enumerate(ls) if l.startswith(start)), None)
        if i is None:
            return None
        j = next((k for k in range(i + 1, len(ls)) if ls[k].startswith(stop)), len(ls))
        return [l.rstrip() for l in ls[i:j] if l.strip()]

    # ⛔ 의도된 기본 경로 변경 — 기준 구간을 이 변환으로 옮긴 뒤 비교한다(default-off-regression.js INTENDED 선례). 그 밖의 차이는 여전히 회귀다.
    #    정확한 치환이다 — 기준 구간에 옛 줄이 정확히 1번 · 새 줄이 0번이 아니면 FAIL(변환이 헛돌면 회귀를 가린다).
    #    기준 SHA 를 올리거나 보호 구간을 줄여 통과시키지 않는다 — 음성 대조가 같은 기준 · 같은 구간에서 다른 변경의 FAIL 을 잰다.
    #    F-150(E1-20): Deliver 흐름 줄의 '착지 검증' 에 verify_landing.py 판정 규칙을 붙인다.
    landing_old = "`앵커 계산(scripts/diff_anchors.py) → 구간 선택(Lead) → non_anchorable은 본문 인용 → payload(top-level body = **review-report.md 전문**) → ⛔확인 게이트 → gh api …/pulls/{N}/reviews → 착지 검증`"
    landing_new = landing_old[:-1] + "(scripts/verify_landing.py — 판정만. ⛔UNVERIFIED 는 삭제·재게시 금지 · MISMATCH 삭제·재게시는 사용자 확인 뒤)`"
    intended = {"skills/fz-peer-review/SKILL.md": [(landing_old, landing_new)]}

    def transform(rel, b):
        out = list(b)
        for old, new in intended.get(rel, []):
            if out.count(old) != 1 or new in out:
                return None, f"기준이 변환 전제와 다르다 — 옛 줄 {out.count(old)}번 · 새 줄 {out.count(new)}번(기대 1 · 0) — 기준이 E1-20 이전인지 본다"
            out[out.index(old)] = new
        return out, ""

    def compare(b, w, is_render):
        k, extra = 0, []
        for line in w:
            if k < len(b) and line == b[k]:
                k += 1
            else:
                extra.append(line)
        return k, extra, [line for line in extra if not is_render(line)]

    # 의도 변환 · 음성 대조는 guard 를 도는 루프 안에서만 돈다 — 대상이 guard 에 없으면 둘 다 조용히 빠진다. 먼저 막고, 끝에서 실행 수를 센다
    gkeys = {g[0] for g in guard}
    check(f"의도 변환 대상 {sorted(intended)} 이 모두 보호 구간 목록에 있다", set(intended) <= gkeys, f"없는 것 {sorted(set(intended) - gkeys)}")
    applied, neg = 0, [0]

    def negative(name, ok, detail):   # 음성 대조 한 건 = 판정 한 줄 + 실행 수 1 — 판정 줄을 지우면 실행 수도 준다
        neg[0] += 1
        check(name, ok, detail)

    for rel, start, stop, render_default in guard:
        bt = base_text(rel)
        if bt is None:
            print(f"UNRUN  기준 {rel} 를 얻지 못했다 — FZ_REGRESSION_BASE_TREE 또는 git 이력({sha})이 필요하다 (⛔ 통과 아님)")
            sys.exit(2)
        b0 = section(bt, start, stop)
        w = section(open(os.path.join(root, rel), encoding="utf-8").read(), start, stop)
        if not b0 or not w:
            check(f"{rel}: 보호 구간 '{start}' 이 기준·현재 둘 다에 있다", False, f"기준 {bool(b0)} · 현재 {bool(w)}")
            continue
        b, why = transform(rel, b0)
        if rel in intended:
            check(f"{rel} '{start}': 기준({src}) 의도 변환 {len(intended[rel])}건이 정확히 적용됐다", b is not None, why)
            if b is None:
                continue
            applied += 1
        is_render = (lambda l: any(t in l for t in ("--render", "렌더", "render_review.py"))) if render_default else (lambda l: "--render" in l)
        k, extra, bare = compare(b, w, is_render)
        check(f"{rel} '{start}': 기준({src}) {len(b)}줄이 순서대로 전부 남았다", k == len(b), f"기준 {k + 1}번째 줄부터 어긋남 — {b[k][:80] if k < len(b) else ''}")
        kind = "렌더 줄(렌더 기본)" if render_default else "--render 조건부 줄"
        check(f"{rel} '{start}': 더한 {len(extra)}줄은 모두 {kind}이다", not bare, " | ".join(line[:80] for line in bare))
        check(f"{rel} '{start}': 렌더러 경로가 이 구간에 있다(--render 와 render_review.py 가 한 줄에)",
              any("--render" in line and "render_review.py" in line for line in extra), "없다 — 옵션이 절차에 배선되지 않았다")
        if rel not in intended:
            continue
        # 음성 대조 — 같은 기준 · 같은 구간. 비교기가 아래 셋을 통과시키면 의도 변환이 다른 변경까지 가린다는 뜻이다
        held = lambda bb, ww: (lambda kk, _e, bb_: kk == len(bb) and not bb_)(*compare(bb, ww, is_render))
        news = {new for _o, new in intended[rel]}
        pick = next((i for i, line in enumerate(w) if i > 0 and line in b and line not in news and w.count(line) == 1 and not is_render(line)), None)
        if pick is None:
            check(f"{rel} '{start}': 음성 대조 — 바꿀 다른 보호 줄을 골랐다", False, "후보 0 — 음성 대조를 잴 수 없다")
        else:
            w1 = list(w)
            w1[pick] = w1[pick] + " (음성 대조 변경)"
            negative(f"{rel} '{start}': 음성 대조 — 보호 구간 다른 줄 1개 변경(기준 · 구간 그대로)은 FAIL 이다", not held(b, w1), f"{pick + 1}번째 줄 변경이 통과했다")
        w2 = [line.replace("사용자 확인 뒤", "확인 없이") if line in news else line for line in w]
        negative(f"{rel} '{start}': 음성 대조 — 의도 줄을 새 줄과 다르게 바꾸면 FAIL 이다(정확 변환)", w2 != w and not held(b, w2), "변형이 통과했다" if w2 != w else "의도 줄이 현재 구간에 없다")
        b3 = [line for line in b0 if line not in {old for old, _n in intended[rel]}]
        negative(f"{rel} '{start}': 음성 대조 — 옛 줄이 없는 기준에는 변환이 거부된다", transform(rel, b3)[0] is None, "옛 줄 없는 기준에서 변환이 통과했다")
    check(f"의도 변환 적용 {applied}건 = 의도 {len(intended)}건", applied == len(intended), "변환이 돌지 않은 의도 대상이 있다")
    check(f"음성 대조 실행 {neg[0]}건 = 3건", neg[0] == 3, "음성 대조가 돌지 않았거나 빠졌다")
    return neg[0]

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

neg_runs = None
if mode == "--default-path-unchanged":
    neg_runs = default_path()
elif mode:
    print(f"UNRUN  모르는 인자 {mode}")
    sys.exit(2)
else:
    fixture()
print(f"\n렌더 단일 출처 {'전건 통과' if not fails else f'실패 {fails}건'}" + (f" · 음성 대조 실행 {neg_runs}건" if neg_runs is not None else ""))
sys.exit(1 if fails else 0)
PY
