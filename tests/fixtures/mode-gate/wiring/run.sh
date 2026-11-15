#!/bin/bash
# modes: --expect-fail caller=manual last-pass=none result=음성 대조 — 옛 기준 트리에서만 판정한다(HEAD 는 전 셀 통과라 해당 없음)
# 모드 게이트 배선 — 스킬·모듈 문서의 **그 자리에** 모드 게이트 계약이 있는가(정적 단언). 셀 단위로 판정한다.
#   재는 것: 절 안의 토큰 · 순서 · 표 행 · frontmatter 권한. ⛔ 재지 못하는 것: 런타임에 실제로 물었는가 — 실행 스모크가 본다.
#   인자: [--tree DIR] [--cells a,b,…] [--expect-fail]
#     --tree        대상 트리(기본: 이 저장소)
#     --cells       셀 선택(기본: 등록된 전부 — health-check 는 인자 없이 돈다)
#     --expect-fail 선택한 셀이 **전부 FAIL** 이면 exit 0 — 기준 트리 음성 대조(이 fixture 가 옛 상태를 잡는다는 증명)
#   출력: 셀마다 `WIRING-OK <셀>` 또는 `WIRING-FAIL <셀>: 사유`. 읽기 실패는 FAIL 이다(부재로 읽지 않는다).
#   exit: 0 판정대로 · 1 아님 · 2 UNRUN(모르는 셀 · 인자 오류)
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
exec python3 - "$R" "$@" <<'PY'
import re, sys
from pathlib import Path

root, argv = Path(sys.argv[1]), sys.argv[2:]
tree, sel, expect_fail = root, None, False
i = 0
while i < len(argv):
    a = argv[i]
    if a == "--tree" and i + 1 < len(argv):
        tree = Path(argv[i + 1]); i += 2
    elif a == "--cells" and i + 1 < len(argv):
        sel = [c for c in argv[i + 1].split(",") if c]; i += 2
    elif a == "--expect-fail":
        expect_fail = True; i += 1
    else:
        print(f"UNRUN  인자 오류: {a}"); sys.exit(2)


class Fail(Exception):
    pass


def read(rel):
    p = tree / rel
    try:
        return p.read_text(encoding="utf-8")
    except OSError as e:
        raise Fail(f"읽기 실패 {rel}: {type(e).__name__}")


def headings(lines):
    """(줄 번호, 레벨, 제목) — ``` 코드 펜스 안의 `# …`(bash 주석)는 헤딩이 아니다."""
    fence = False
    for k, ln in enumerate(lines):
        if ln.lstrip().startswith("```"):
            fence = not fence
            continue
        m = None if fence else re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            yield k, len(m.group(1)), m.group(2)


def section(text, title, rel=""):
    """제목에 title 이 들어간 첫 헤딩부터 같은 레벨 이상의 다음 헤딩 직전까지."""
    lines = text.split("\n")
    hs = list(headings(lines))
    for idx, (k, lvl, name) in enumerate(hs):
        if title in name:
            end = next((k2 for k2, l2, _ in hs[idx + 1:] if l2 <= lvl), len(lines))
            return "\n".join(lines[k:end])
    raise Fail(f"절 없음 '{title}' {rel}")


def need(text, tokens, where):
    miss = [t for t in tokens if t not in text]
    if miss:
        raise Fail(f"{where} 에 없음: {', '.join(miss)}")


def table_row(text, token, where):
    if not any(ln.startswith("|") and token in ln for ln in text.split("\n")):
        raise Fail(f"{where} 표에 '{token}' 행 없음")


def order_in(rel, title, first, then):
    sec = section(read(rel), title, rel)
    a, b = sec.find(first), sec.find(then)
    if a < 0 or b < 0 or a > b:
        raise Fail(f"{rel} § {title}: '{first}' 가 '{then}' 앞에 없다(위치 {a} · {b})")


GPT_DROP = re.compile(r"GPT[^\n]*(생략|미호출)|(생략|미호출)[^\n]*GPT")
GPT_KEEP = re.compile(r"생략 금지|생략 불가")


def light_ok(rel, gpt_token, extra=()):
    sec = section(read(rel), "light 모드", rel)
    need(sec, ["생략 불가", "modules/mode-gate.md", gpt_token, *extra], f"{rel} § light 모드")
    bad = [ln for ln in sec.split("\n") if GPT_DROP.search(ln) and not GPT_KEEP.search(ln)]
    if bad:
        raise Fail(f"{rel} § light 모드 에 GPT 생략 지시: {bad[0][:80]}")


def absent(rel, phrases):
    t = read(rel)
    hit = [ph for ph in phrases if ph in t]
    if hit:
        raise Fail(f"{rel} 에 옛 문구: {', '.join(hit)}")


def absent_in(text, phrases, where):
    hit = [ph for ph in phrases if ph in text]
    if hit:
        raise Fail(f"{where} 에 옛 문구: {', '.join(hit)}")


# ── 셀 ────────────────────────────────────────────────────────────────────────
def cell_module():
    # 2026-11-12 — 추천 full 일 때만 묻는다 · light · 측정 불가는 통보하고 light · 질문 불가면 light + 추천 보존 · /fz 는 명시 선택만
    m = read("modules/mode-gate.md")
    for h in ("## 목차", "## 참조 스킬", "## 언제 묻나", "## 신호어", "## 측정", "## 기록", "## 질문 형식", "## 사용자 결정", "## 설계 원칙"):
        if not re.search(rf"^{re.escape(h)}\s*$", m, re.M):
            raise Fail(f"mode-gate.md 절 없음: {h}")
    when = section(m, "언제 묻나")
    need(when, ["명시 인자", "명시로 고른", "신호어", "질문 도구를 쓸 수 없는", "light 로 진행", "**묻는 것은 6 뿐이다.**",
                'autonomy_decide.py" --action mode_select --in-scope --reversible', "exit 0(PROCEED)만 자율",
                "추천 light · 측정 불가", "측정 불가는 추천이 아니다", "`--recommended full`"], "§ 언제 묻나")
    if not re.search(r"^4\. \*\*자율 모드 또는 질문 도구를 쓸 수 없는 실행\*\*", when, re.M):
        raise Fail("§ 언제 묻나 4 가 자율 · 질문 도구 없음이 아니다 — gpt-strategy.md · tests/fixtures/gpt/off 가 이 번호를 참조한다")
    absent_in(when, ["추천대로 진행", "자동 선택: 추천", "5. **그 밖**", "사용자가 고른 모드를 인자로 받는다"], "§ 언제 묻나")
    need(section(m, "신호어"), ["정본 목록", "그냥", "가볍게", "`--seq` 단독은 신호어가 아니다"], "§ 신호어")
    meas = section(m, "측정")
    need(meas, ["mode_gate.py", "| 추천 full |", "| 추천 light |", "| 2 |", "측정 불가", "| 10 |", "입력 오류", "`default`", "`gate`", "추천 full 보존"], "§ 측정")
    absent_in(meas, ["추천을 달고 묻는다", "추천 없이 \"측정 불가\" 를 보이고 묻는다", "추천대로 +"], "§ 측정")
    rec = section(m, "기록")
    need(rec, ["autonomous\\|default\\|gate", "5 추천 light · 측정 불가로 묻지 않음 `default`", "6 질문 `gate`", "`full` 로 적는다"], "§ 기록")
    absent_in(rec, ["질문(5)", "경로(1~4)", "5 질문 `gate`"], "§ 기록")
    ask = section(m, "질문 형식")
    need(ask, ["추천이 full 일 때만", "full (Recommended)", "gpt-strategy.md", "추천 light · 측정 불가는 묻지 않는다"], "§ 질문 형식")
    absent_in(ask, ["{추천 모드} (Recommended)", "측정 불가(exit 2)면 `(Recommended)` 를 달지 않는다"], "§ 질문 형식")
    need(section(m, "사용자 결정"), ["2026-10-19", "2026-11-12", "추천이 full 일 때만 묻는다", "큼 AND 복잡", "질문 불가면 추천 모드 그대로 진행", "명시로 고른"], "§ 사용자 결정")
    g = read("modules/governance.md")
    table_row(section(g, "적용 경로", "governance.md"), "mode-gate.md", "governance § 적용 경로")
    table_row(section(g, "Truth-of-Source", "governance.md"), "mode_gate.py", "governance § Truth-of-Source")
    for rel, key in (("skills/fz/SKILL.md", "`simplified_keywords`"), ("modules/lead-action-default.md", "40차 (Simplified Request)")):
        row = next((ln for ln in read(rel).split("\n") if ln.startswith("|") and key in ln), None)
        if row is None or "mode-gate.md" not in row:
            raise Fail(f"{rel} 의 신호어 행이 모듈을 가리키지 않는다")


# 소비 문서 — 게이트 줄이 2026-11-12 계약(full 만 질문 · 그 밖은 통보하고 light · /fz 명시 선택만)을 가리키고 임계 숫자를 복제하지 않는가
GATE_LINES = [("skills/fz-plan/SKILL.md", "1.2. **모드 게이트**"), ("skills/fz-review/SKILL.md", "1.5. **모드 게이트**"),
              ("skills/fz-code/SKILL.md", "0. **모드 게이트**"), ("skills/fz-fix/SKILL.md", "0. **모드 게이트**"),
              ("skills/fz-discover/SKILL.md", "1.5. **모드 게이트**")]
THRESH = re.compile(r"1,?000 ?줄|20 ?파일|파일 20|30 ?파일|5 ?모듈|모듈 5")


def no_thresh(text, where):
    m = THRESH.search(text)
    if m:
        raise Fail(f"{where} 에 임계 숫자 복제 '{m.group(0)}' — 정본 scripts/mode_gate.py")


def line_with(rel, key, starts=True):
    ln = next((x for x in read(rel).split("\n") if (x.startswith(key) if starts else key in x)), None)
    if ln is None:
        raise Fail(f"{rel} 에 '{key}' 줄 없음")
    return ln


def cell_consumers():
    for rel, key in GATE_LINES:
        ln = line_with(rel, key)
        need(ln, ["추천 full 일 때만 묻는다", "light + 통보", "명시로 고른 모드면 재지 않는다", "§ 언제 묻나 5 · 6"], f"{rel} 게이트 줄")
        absent_in(ln, ["추천을 달고 묻", "`/fz` 경유면 묻지 않는다"], f"{rel} 게이트 줄")
        no_thresh(ln, f"{rel} 게이트 줄")
    disc = section(read("skills/fz-discover/SKILL.md"), "발동 조건", "fz-discover")
    need(disc, ["추천 full 일 때만 묻고"], "fz-discover § 발동 조건")
    absent_in(disc, ["추천을 달고 묻"], "fz-discover § 발동 조건")
    peer = "skills/fz-peer-review/SKILL.md"
    ln = line_with(peer, "모드 게이트 + Tier", starts=False)
    need(ln, ["추천 full(큼 AND 복잡)일 때만 질문", "light + 통보"], f"{peer} 요약 줄")
    t55 = section(read(peer), "5.5. Tier Determination", peer)
    need(t55, ["추천 full 일 때만 질문", "light + 통보"], f"{peer} § 5.5")
    absent_in(t55, ["`/fz` 경유 · `--tier` 면 묻지 않는다"], f"{peer} § 5.5")
    no_thresh(ln + t55, peer)
    for rel in ("skills/fz-plan/SKILL.md", "skills/fz-review/SKILL.md", "skills/fz-code/SKILL.md"):
        no_thresh(section(read(rel), "light 모드", rel), f"{rel} § light 모드")
    plan_light = section(read("skills/fz-plan/SKILL.md"), "light 모드", "fz-plan")
    need(plan_light, ["크고 복잡할 때"], "fz-plan § light 모드")
    absent_in(plan_light, ["새 아키텍처 결정이면 1.2 가 full"], "fz-plan § light 모드")
    gov = line_with("modules/governance.md", "| 모드 게이트 (무거운 경로")
    need(gov, ["추천 full 일 때만 묻는다", "추천 full 을 기록에 보존", "2026-11-12"], "governance 모드 게이트 행")
    absent_in(gov, ["자율이면 추천대로"], "governance 모드 게이트 행")
    no_thresh(gov, "governance 모드 게이트 행")
    gd = line_with("guides/skill-authoring.md", "현행: 스킬이 Workflow", starts=False)
    need(gd, ["추천이 full(큼 AND 복잡)일 때만 묻고"], "guides/skill-authoring.md")
    absent_in(gd, ["light · full 을 묻고"], "guides/skill-authoring.md")
    no_thresh(gd, "guides/skill-authoring.md")


def cell_review_order():
    order_in("skills/fz-review/SKILL.md", "실행 절차 (Lead)", "mode_gate.py", "Workflow({ scriptPath")


def cell_review_light():
    light_ok("skills/fz-review/SKILL.md", "GPT 단계는 full 과 같다", ("Phase 5 Lead 3중 검증",))
    absent("skills/fz-review/SKILL.md", ["review-arch 단독", "full 모드 강제", "5 파일 미만", "100 LOC 미만"])


def cell_peer_tier():
    rel = "modules/peer-review-tiers.md"
    doc = read(rel)
    sec = section(doc, "자동 선택 실행 bash", rel)
    for pat in (r"TIER=\$\(\(\s*TIER\s*\+", r"SIGNIFICANT_LINES -lt (100|200|500)\b.*TIER=", r"TIER_DELTA"):
        if re.search(pat, sec):
            raise Fail(f"{rel} § 자동 선택 실행 bash 에 자동 Tier 판정이 남았다: /{pat}/")
    need(sec, ["mode_gate.py", "TIER=1", "TIER=2", "AskUserQuestion", "TIER_OPT", "--unmeasured"], f"{rel} § 자동 선택 실행 bash")
    need(section(doc, "수집 축소의 검증 계약", rel), ["2026-10-19", "modules/mode-gate.md"], f"{rel} § ablation")
    need(section(doc, "모드 선택 (측정 · 추천 · 질문)", rel), ["scripts/mode_gate.py", "modules/mode-gate.md", "light = Tier 1"], f"{rel} § 모드 선택")
    skill = read("skills/fz-peer-review/SKILL.md")
    row = next((ln for ln in skill.split("\n") if "모드 게이트 + Tier" in ln), "")
    if "modules/mode-gate.md" not in row:
        raise Fail("fz-peer-review SKILL.md 의 모드 게이트 요약 줄이 모듈을 가리키지 않는다")


def cell_plan_order():
    order_in("skills/fz-plan/SKILL.md", "실행 절차 (Lead)", "mode_gate.py", "cp {플러그인 루트}/workflows/plan-lean2.js")


def cell_plan_light():
    rel = "skills/fz-plan/SKILL.md"
    light_ok(rel, "GPT 단계도 같다", ("Phase 2", "원장", "plan-final.md"))
    absent(rel, ["full 모드 강제", "GPT verify 미호출"])
    l31 = next((ln for ln in read(rel).split("\n") if "draft 원장 생성" in ln), "")
    if not l31 or "full 모드" in l31:
        raise Fail(f"{rel} 3.1 이 full 모드에만 원장을 만든다: {l31[:80]}")
    absent("modules/gates.md", ["light 모드는 원장을 만들지 않는다"])


def cell_code_order():
    order_in("skills/fz-code/SKILL.md", "실행 절차 (Lead — Step 루프 소유)", "mode_gate.py", "Workflow({ scriptPath")


def cell_code_light():
    rel = "skills/fz-code/SKILL.md"
    light_ok(rel, "GPT 교차 검증(8.5)은 full 과 같다", ("모든** Step",))
    absent(rel, ["Step 1 (incremental", "GPT 교차 검증 생략", "SOLO 모드에서는 선택", "TEAM 모드 — 생략 금지"])
    doc = read(rel)
    h85 = next((ln for ln in doc.split("\n") if ln.startswith("8.5.")), "")
    if "GPT 를 켠 세션" not in h85:
        raise Fail(f"{rel} 8.5 의 GPT 조건이 사용 여부가 아니다: {h85[:80]}")
    if "plan-light.md" not in doc:
        raise Fail(f"{rel} 옛 plan-light.md 읽기 폴백이 사라졌다(호환)")


def cell_fix_order():
    order_in("skills/fz-fix/SKILL.md", "실행 절차 (Lead)", "mode_gate.py", "Workflow({ scriptPath")


def cell_discover_auto():
    rel = "skills/fz-discover/SKILL.md"
    absent(rel, ["복잡도 4+ 또는"])
    order_in(rel, "실행 절차 (Lead)", "mode_gate.py", "Workflow({ scriptPath")


# Workflow 를 부르는 곳 — 준비 사이트 10곳(tests/fixtures/workflow-prep/copy-cmp --cells sites · guides 1 = swarm 정본 사이트) + fz-plan
EFFORT_SITES = ["skills/fz-code/SKILL.md", "skills/fz-discover/SKILL.md", "skills/fz-fix/SKILL.md", "skills/fz-pr-digest/SKILL.md",
                "skills/fz-review/SKILL.md", "skills/fz-search/SKILL.md", "skills/fz/SKILL.md", "modules/peer-review-workflow.md",
                "modules/peer-review-tiers.md", "skills/fz-plan/SKILL.md", "guides/skill-authoring.md"]
EFFORT_RE = re.compile(r"`?effort`?[^\n]*(lead-effort|mode_gate\.py|mode-gate\.json)")


def cell_effort_args():
    miss = [rel for rel in EFFORT_SITES if not EFFORT_RE.search(read(rel))]
    if miss:
        raise Fail(f"Workflow args 에 lead-effort 출처 effort 가 없다: {', '.join(miss)}")


def cell_effort_docs():
    for rel in ("CLAUDE.md", "guides/skill-authoring.md", "guides/model-guide.md", "modules/peer-review-tiers.md", "modules/native-agents.md"):
        need(read(rel), ["Lead 세션 effort", "2026-10-19"], rel)
    for rel in ("guides/skill-authoring.md", "guides/model-guide.md"):
        need(read(rel), ["§5.8 ⑥"], rel)
    absent("guides/model-guide.md", ["`xhigh`는 사용자가 유지를 택한 결정된 값", "36콜"])
    absent("modules/peer-review-tiers.md", ["`xhigh` 는 관성이 아니라 **결정된 값**"])
    absent("guides/skill-authoring.md", ["fz 는 `xhigh` 유지(사용자 결정 2026-09-25", "현행 워크플로는 전 호출 `'xhigh'` 단일값"])
    absent("CLAUDE.md", ["워크플로 콜 명시 `xhigh` 유지"])


def cell_fz_phase4():
    # 2026-11-12 — /fz 는 명시 선택만 인자로 · 그 밖은 스킬 게이트가 잰다 · Phase 5 는 스킬 게이트를 건너뛰지 않는다
    fz = read("skills/fz/SKILL.md")
    p4 = section(fz, "Phase 4: User Confirmation", "skills/fz/SKILL.md")
    need(p4, ["modules/mode-gate.md", "인자", "**명시로 고른** 모드만", "스킬 모드를 정하지 않는다", "같은 게이트로 판정"], "fz SKILL § Phase 4")
    absent_in(p4, ["사용자가 고른 모드를 스킬에 인자", "스킬은 다시 묻지 않는다"], "fz SKILL § Phase 4")
    need(section(fz, "5.1 SOLO Execution", "skills/fz/SKILL.md"), ["모드 게이트도 그대로 거친다"], "fz SKILL § 5.1")
    need(section(fz, "5.2 Workflow Execution", "skills/fz/SKILL.md"), ["5.2 는 스킬 게이트를 건너뛰는 길이 아니다", "최종 모드가 full 일 때만"], "fz SKILL § 5.2")
    rel = "modules/fz-pipeline-proposal.md"
    sel = section(read(rel), "AskUserQuestion 선택지", rel)
    need(sel, ["**명시로 고른** 모드만", "모드 선택지를 두지 않는다", "Phase 3 의 SOLO/TEAM 을 모드 인자로 바꿔 넘기지 않는다"], f"{rel} § AskUserQuestion 선택지")
    absent_in(sel, ["full (Phase 3 추천)", "light (Phase 3 추천)", "모드 변경 (full ↔ light)", "light (Recommended — 단순 요청)", "스킬은 다시 묻지 않는다"], f"{rel} § AskUserQuestion 선택지")
    absent(rel, ["역전 금지", "TEAM 자동 전환"])
    cx = read("modules/complexity.md")
    need(cx, ["modules/mode-gate.md", "스킬 모드(light · full)는 정하지 않는다"], "modules/complexity.md")
    absent_in(cx, ["SOLO(= light) / TEAM(= full) **추천**"], "modules/complexity.md")


PERMS = {  # 스킬 → (python3 scripts, gpt-choice) 필요 여부 — 계획 S7 표
    "fz-review": (1, 1), "fz-plan": (1, 1), "fz-peer-review": (1, 1), "fz-code": (1, 1), "fz-fix": (1, 1),
    "fz-discover": (1, 1), "fz-search": (1, 0), "fz-pr-digest": (1, 0), "fz": (1, 1),
}


def frontmatter(text):
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise Fail("frontmatter 없음")
    return m.group(1)


def cell_perms():
    miss = []
    for skill, (py, gc) in PERMS.items():
        fm = frontmatter(read(f"skills/{skill}/SKILL.md"))
        if py and "Bash(python3 */scripts/*)" not in fm:
            miss.append(f"{skill}: python3 scripts")
        if gc and "Bash(*/scripts/gpt-choice.sh*)" not in fm:
            miss.append(f"{skill}: gpt-choice")
    if miss:
        raise Fail("frontmatter 권한 없음 — " + ", ".join(miss))


SIGNAL = re.compile(r"그냥|가볍게|단순|빠르게|확인해줘|한 번 봐줘|해도 돼\?|맞아\?")
A1 = re.compile(r"effort\s*:\s*['\"]")


def signal_copy(line):
    return len(SIGNAL.findall(line)) >= 4


def cell_anti():
    # 판정 함수 자체의 대조 — 위반 문구는 잡고 정상 문구는 통과시켜야 한다
    controls = [
        (bool(A1.search("{ effort: 'xhigh' }")), True), (bool(A1.search("{ effort: EFFORT }")), False),
        (bool(GPT_DROP.search("- GPT 교차 검증 생략")) and not GPT_KEEP.search("- GPT 교차 검증 생략"), True),
        (bool(GPT_DROP.search("GPT 리뷰 생략 금지")) and not GPT_KEEP.search("GPT 리뷰 생략 금지"), False),
        (signal_copy('"그냥/가볍게/단순/빠르게"'), True), (signal_copy('"가볍게 봐줘"'), False),
    ]
    bad = [i for i, (got, want) in enumerate(controls) if got != want]
    if bad:
        raise Fail(f"anti 판정 함수 대조 실패: {bad}")
    wf = tree / "workflows"
    js = sorted(wf.glob("*.js")) if wf.is_dir() else []
    if not js:
        raise Fail("workflows/*.js 없음")
    a1 = [f"{p.name}:{i}" for p in js for i, ln in enumerate(p.read_text(encoding="utf-8").split("\n"), 1) if A1.search(ln)]
    if a1:
        raise Fail(f"A1 effort 리터럴: {', '.join(a1[:3])}")
    for rel in ("skills/fz-plan/SKILL.md", "skills/fz-review/SKILL.md", "skills/fz-code/SKILL.md"):
        sec = section(read(rel), "light 모드", rel)
        if any(GPT_DROP.search(ln) and not GPT_KEEP.search(ln) for ln in sec.split("\n")):
            raise Fail(f"A2 {rel} light 절 GPT 생략")
    copies = []
    for p in sorted(list((tree / "skills").glob("*/SKILL.md")) + list((tree / "modules").glob("*.md"))):
        rel = p.relative_to(tree).as_posix()
        if rel == "modules/mode-gate.md":
            continue
        copies += [f"{rel}:{i}" for i, ln in enumerate(p.read_text(encoding="utf-8").split("\n"), 1) if signal_copy(ln)]
    if copies:
        raise Fail(f"A3 신호어 목록 사본: {', '.join(copies[:3])}")
    a4 = [p.relative_to(tree).as_posix() for p in (tree / "skills").rglob("*.md") if "full 모드 강제" in p.read_text(encoding="utf-8")]
    if a4:
        raise Fail(f"A4 full 모드 강제: {', '.join(a4)}")
    absent("skills/fz-review/SKILL.md", ["review-arch 단독"])
    # 실행자 홈 경로를 실행 시점에 구한다 — 저자 경로를 이 파일에 리터럴로 두면 검사기 자신이 그 경로를 싣는다
    me = f"{Path.home()}/"
    home = [p.relative_to(tree).as_posix() for d in ("skills", "modules", "guides", "scripts", "workflows", "agents")
            for p in (tree / d).rglob("*") if p.is_file() and me in p.read_text(encoding="utf-8", errors="replace")]
    if home:
        raise Fail(f"A6 저자 경로: {', '.join(home[:3])}")
    mg = read("scripts/mode_gate.py")
    if re.search(r"\b\d+(\.\d+)?\s*(분|min)\b", mg):
        raise Fail("A6 mode_gate.py 에 분 단위 소요 상수")


def cell_gpt_off():
    rel = "modules/gpt-strategy.md"
    doc = read(rel)
    need(section(doc, "GPT 미사용 (off · CLI 없음)", rel), ["exit 18", "GPT-OFF", "--gpt-unavailable", "Gate 2", "--model off", "[GPT 미사용"], f"{rel} § GPT 미사용")
    absent(rel, ["light 모드는 GPT 를 부르지 않는다"])


def cell_gpt_cond():
    fz = read("skills/fz/SKILL.md")
    if re.search(r"gpt (verify|check) \(TEAM\)", fz) or "모든 TEAM 스킬에 GPT CLI 포함" in fz:
        raise Fail("fz SKILL.md 에 TEAM 에만 GPT 를 거는 문장이 남았다")
    need(fz, ["GPT 켬 — light · full"], "skills/fz/SKILL.md")
    absent("modules/cross-validation.md", ["SOLO 모드에서는 에이전트 스폰/GPT 교차 검증 없이", "| gpt check | **필수** (TEAM 코드/계획) | SOLO 모드",
                                           "| Reflection Rate | **필수** (TEAM review) | SOLO 모드"])
    need(read("modules/cross-validation.md"), ["GPT 켬"], "modules/cross-validation.md")
    need(read("skills/fz-discover/SKILL.md"), ["--deep cross-model"], "fz-discover(명시 플래그 --deep GPT 유지)")
    # fz-fix GPT check 는 켬이면 필수(2026-11-01 사용자 결정) — 옛 opt-in 문구가 돌아오면 FAIL(기준 트리 음성 대조: 옛 문구가 있어 이 셀이 FAIL)
    absent("skills/fz-fix/SKILL.md", ["(옵션 `--gpt`) `/fz-gpt check`", "[--gpt]", "--gpt 옵션", "--gpt 처리 책임"])
    need(read("skills/fz-fix/SKILL.md"), ["GPT 를 켠 세션이면 필수", "§ 단계 실행 판정", "gpt-choice.sh\" decide"], "fz-fix(GPT check — 켬이면 필수 · 공통 판정 decide)")
    absent("modules/mode-gate.md", ["fz-fix 의 `--gpt` 는 명시 플래그"])
    need(read("modules/mode-gate.md"), ["fz-fix 의 GPT check 는 켬이면 필수", "§ 단계 실행 판정"], "modules/mode-gate.md § GPT 는 모드와 독립")


CELLS = {
    "module": cell_module,
    "consumers": cell_consumers,
    "review-order": cell_review_order,
    "review-light": cell_review_light,
    "peer-tier": cell_peer_tier,
    "plan-order": cell_plan_order,
    "plan-light": cell_plan_light,
    "code-order": cell_code_order,
    "code-light": cell_code_light,
    "fix-order": cell_fix_order,
    "discover-auto": cell_discover_auto,
    "effort-args": cell_effort_args,
    "effort-docs": cell_effort_docs,
    "fz-phase4": cell_fz_phase4,
    "perms": cell_perms,
    "anti": cell_anti,
    "gpt-off": cell_gpt_off,
    "gpt-cond": cell_gpt_cond,
}

names = sel if sel is not None else list(CELLS)
unknown = [n for n in names if n not in CELLS]
if unknown:
    print(f"UNRUN  모르는 셀: {', '.join(unknown)} — 등록: {', '.join(CELLS)}"); sys.exit(2)
ok_cells, fail_cells = [], []
for n in names:
    try:
        CELLS[n]()
        print(f"WIRING-OK {n}"); ok_cells.append(n)
    except Fail as e:
        print(f"WIRING-FAIL {n}: {e}"); fail_cells.append(n)
if expect_fail:
    if ok_cells:
        print(f"음성 대조 실패 — 옛 트리에서 통과한 셀: {', '.join(ok_cells)}"); sys.exit(1)
    print(f"음성 대조 통과 — 선택 셀 {len(fail_cells)} 개 전부 FAIL (대상 {tree})"); sys.exit(0)
print(f"모드 게이트 배선 {'실패 ' + str(len(fail_cells)) + '셀' if fail_cells else '전건 통과'} ({len(names)} 셀 · 대상 {tree})")
sys.exit(1 if fail_cells else 0)
PY
