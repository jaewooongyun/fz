#!/usr/bin/env python3
# lint:no-root-anchor — 리포트 JSON 경로와 저장소 루트를 인수로만 받는다(트리 해석은 run.sh 몫).
"""stage-class fixture 판정기 (F-462) — `fz_telemetry_report.py --json` 출력 한 덩이와 저장소 루트를 읽어 case 줄을 찍는다.

usage: check.py <report.json> <repo-root>
출력: case 마다 `<case>: PASS` · `<case>: FAIL <why>` 한 줄, 끝에 `stage-class: PASS|FAIL`.
exit: 0 전건 통과 · 1 단언 실패 · 2 준비 실패(`UNRUN:` — JSON 읽기 실패 · fixture 가 기간에 안 잡힘 ·
      workflows/*.js 못 읽음 · 단언기 고장)
⛔ 키는 방어적으로 읽는다 — 새 필드가 없는 트리(수정 전)는 traceback 이 아니라 그 case 의 FAIL 줄이어야 한다.
⛔ 분모(journal 실행 3 · result 6)가 안 맞으면 단언하지 않는다 — fixture 가 안 잡혀 전부 FAIL 인 것을
   '수정 전이라 실패' 로 읽으면 되돌림 검사가 거짓 통과한다.
label-drift: 리포트 LABEL_STAGE 의 라벨이 전부 `<repo-root>/workflows/*.js` 에 `label: '<라벨>'` 로 있어야 한다 —
   라벨을 바꾸면 그 결과가 unknown 이 아니라 키 서명 스테이지(review1 · cross)로 조용히 빠지기 때문이다.
"""
import importlib.util
import json
import os
import sys
import traceback


def _crash(*exc):
    print("UNRUN: check.py 단언기 고장")
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(2)


sys.excepthook = _crash

# 워크플로 이름은 형제 스크립트가 없어 `unnamed:<wf_id>` 로 잡힌다. 셋째 실행 wf_33333333-ccc 는
# lean2-merge:8811b9 하나(agentType 은 기본값 — 라벨 줄기만으로 plan-merge 가 돼야 한다)로 stages 에만 든다.
REVIEW_LIVE = "unnamed:wf_11111111-aaa"   # stage1-arch · stage2-quality-on-arch · stage3-counter · 라벨 없는 형태
PEER = "unnamed:wf_22222222-bbb"          # stage2-arch-on-peers (delta)
WANT_RUNS, WANT_RESULTS = 3, 6


def dig(node, *path):
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def pick(node, keys):
    if not isinstance(node, dict):
        return None
    return {k: node.get(k) for k in keys}


def show(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def label_table(root):
    """리포트 모듈의 LABEL_STAGE — 없거나 dict 가 아니면 None(수정 전 트리)."""
    spec = importlib.util.spec_from_file_location(
        "fz_telemetry_report_stage_class", os.path.join(root, "scripts", "fz_telemetry_report.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    table = getattr(mod, "LABEL_STAGE", None)
    return table if isinstance(table, dict) else None


def workflow_sources(root):
    """`<root>/workflows/*.js` 본문 목록. 폴더나 파일을 못 읽으면 None."""
    folder = os.path.join(root, "workflows")
    texts = []
    try:
        for name in sorted(os.listdir(folder)):
            if name.endswith(".js"):
                with open(os.path.join(folder, name), encoding="utf-8", errors="replace") as handle:
                    texts.append(handle.read())
    except OSError:
        return None
    return texts


def label_present(label, sources):
    needles = ("label: '%s'" % label, 'label: "%s"' % label, "label: `%s`" % label)
    return any(needle in text for text in sources for needle in needles)


def main(argv):
    if len(argv) != 3:
        print("UNRUN: usage: check.py <report.json> <repo-root>")
        return 2
    try:
        with open(argv[1], encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        print("UNRUN: 리포트 JSON 읽기 실패: %s" % exc)
        return 2
    runs, results = dig(payload, "denominators", "journal_runs"), dig(payload, "denominators", "journal_results")
    if (runs, results) != (WANT_RUNS, WANT_RESULTS) or not isinstance(dig(payload, "workflows"), list):
        print("UNRUN: fixture journal 이 기간에 잡히지 않았다 — 실행 %s · result %s (기대 %d · %d)"
              % (runs, results, WANT_RUNS, WANT_RESULTS))
        return 2
    sources = workflow_sources(argv[2])
    if not sources:
        print("UNRUN: workflows/*.js 를 못 읽었다: %s" % os.path.join(argv[2], "workflows"))
        return 2
    table = label_table(argv[2])
    rows = {r.get("workflow"): r for r in payload["workflows"] if isinstance(r, dict)}
    failed = []

    def case(name, got, want):
        if got == want:
            print("%s: PASS" % name)
        else:
            print("%s: FAIL got=%s want=%s" % (name, show(got), show(want)))
            failed.append(name)

    stages = {}
    for row in rows.values():
        counts = row.get("stages")
        for stage, n in (counts.items() if isinstance(counts, dict) else ()):
            if isinstance(n, int):
                stages[stage] = stages.get(stage, 0) + n
    case("stages", stages, {"lens": 1, "cross": 2, "counter": 1, "plan-merge": 1, "unknown": 1})
    rl, pr = rows.get(REVIEW_LIVE), rows.get(PEER)
    case("review-live-verdicts",
         {"verdicts": pick(dig(rl, "stage_judgments", "cross"), ("agree", "adjust", "false_positive")),
          "aggregate": dig(rl, "stage_verdicts", "cross")},
         {"verdicts": {"agree": 2, "adjust": 1, "false_positive": 1},
          "aggregate": {"overturn": 1, "uphold": 2, "adjust": 1}})
    case("peer-delta-verdicts",
         {"verdicts": pick(dig(pr, "stage_judgments", "cross"), ("agree", "adjust", "false_positive")),
          "aggregate": dig(pr, "stage_verdicts", "cross")},
         {"verdicts": {"agree": 3, "adjust": 1, "false_positive": 1},
          "aggregate": {"overturn": 1, "uphold": 3, "adjust": 1}})
    case("counter-verdicts",
         {"verdicts": pick(dig(rl, "stage_judgments", "counter"), ("uphold", "refute")),
          "aggregate": dig(rl, "stage_verdicts", "counter")},
         {"verdicts": {"uphold": 2, "refute": 1},
          "aggregate": {"overturn": 1, "uphold": 2, "adjust": 0}})
    case("additions",
         {"review-live-cross": dig(rl, "stage_judgments", "cross", "additions"),
          "counter": dig(rl, "stage_judgments", "counter", "additions"),
          "peer-cross": dig(pr, "stage_judgments", "cross", "additions"),
          "review-live-row": dig(rl, "additions"),
          "peer-row": dig(pr, "additions")},
         {"review-live-cross": 1, "counter": 2, "peer-cross": 3, "review-live-row": 3, "peer-row": 3})
    case("unknown-shape",
         {"unknown": stages.get("unknown"), "other": stages.get("other"),
          "shapes": dig(payload, "unknown_result_shapes")},
         {"unknown": 1, "other": None, "shapes": [{"keys": ["score", "verdictText"], "n": 1}]})
    if not table:
        drift = "LABEL_STAGE 없음 또는 빈 표"
    else:
        drift = sorted(label for label in table if not label_present(label, sources))
    case("label-drift", drift, [])
    print("stage-class: %s" % ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
