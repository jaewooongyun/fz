#!/usr/bin/env python3
"""스킬 실행 경로별 **필수 read-set** 을 잰다 — Lead 가 실제로 읽는 양.

왜 `wc -l` 총합이 아닌가: 레포 총량이 같아도 조건부 모듈 100줄을 지우고
필수 경로에 100줄을 넣으면 총합 게이트는 통과하지만 Lead 비용은 늘어난다.
줄여야 할 것은 **경로마다 매번 읽는 양**이지 레포 크기가 아니다.

⛔ 이 스크립트는 판정하지 않는다. 수치를 낸다 — 임계는 호출자가 정한다.

usage:
  hydration_manifest.py [--json] [--baseline FILE]

exit: 0 = 측정 성공 / 2 = 파일 누락 (⛔ 0 이 "괜찮다"가 아니다)
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 경로별 필수 read-set. ⛔ 조건부 참조는 넣지 않는다 — 매번 읽는 것만이 대상이다.
SKILL = "skills/fz-peer-review/SKILL.md"
TIERS = "modules/peer-review-tiers.md"
AXES = "modules/review-structural-axes.md"
EVIDENCE = "modules/evidence-collection.md"
GATES = "modules/peer-review-gates.md"
# ⛔ Tier 2/3 전용 — Tier 0/1 은 sub-agent·Codex 가 없어 읽지 않는다 (2026-08-26 추출)
WORKFLOW = "modules/peer-review-workflow.md"

# ⛔ Tier 0/1 도 GATES·EVIDENCE 를 읽는다. 경량 경로라고 빼면 측정이 거짓이 된다:
#   · GATES     § MergeContract 가 **전 경로** 병합 SSOT 다 (tiers.md Tier 0/1 Synthesize 가 참조)
#   · EVIDENCE  § InputHygiene 의 Tier 0/1 탐지·표시 + 강등 결정식이 여기 있다 (SKILL.md § Orchestrator Bias)
#   두 모듈 안의 개별 Gate·절차는 조건부지만, **파일을 열어야** 그 절을 적용할 수 있다 —
#   비용은 파일 단위로 발생하므로 파일 단위로 센다.
MANIFEST = {
    "peer-review/tier0": [SKILL, TIERS, AXES, EVIDENCE, GATES],
    "peer-review/tier1": [SKILL, TIERS, AXES, EVIDENCE, GATES],
    "peer-review/tier2": [SKILL, TIERS, AXES, EVIDENCE, GATES, WORKFLOW],
    "peer-review/tier3": [SKILL, TIERS, AXES, EVIDENCE, GATES, WORKFLOW],
}

# 조건부 — 발동했을 때만 더해진다. 참고로 표시하되 필수 합계에는 넣지 않는다.
CONDITIONAL = {
    "--post 게시": ["modules/peer-review-inline-anchoring.md"],
    "서술형 발견": ["modules/peer-review-finding-anatomy.md"],
    "전수·부정 주장": ["modules/cross-validation.md"],
}


def count(root, rel):
    path = os.path.join(root, rel)
    try:
        with open(path, encoding="utf-8") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return None


def measure(root):
    out, missing = {}, []
    for name, files in MANIFEST.items():
        total = 0
        for rel in files:
            n = count(root, rel)
            if n is None:
                missing.append(rel)
                continue
            total += n
        out[name] = {"lines": total, "files": len(files)}
    cond = {}
    for name, files in CONDITIONAL.items():
        total = 0
        for rel in files:
            n = count(root, rel)
            if n is None:
                missing.append(rel)
                continue
            total += n
        cond[name] = total
    return out, cond, sorted(set(missing))


def main(argv):
    root = str(ROOT)
    required, conditional, missing = measure(root)

    baseline = {}
    if "--baseline" in argv:
        idx = argv.index("--baseline")
        if idx + 1 < len(argv):
            try:
                with open(argv[idx + 1], encoding="utf-8") as fh:
                    baseline = json.load(fh).get("required", {})
            except (OSError, ValueError):
                sys.stderr.write("⚠️ baseline 을 읽지 못했다 — 비교 없이 측정만 한다\n")

    payload = {"required": required, "conditional": conditional, "missing": missing}

    if "--json" in argv:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
    else:
        print("필수 read-set (경로마다 매번 읽는 양)")
        for name, d in required.items():
            delta = ""
            if name in baseline:
                diff = d["lines"] - baseline[name]["lines"]
                delta = "  (%+d)" % diff if diff else "  (=)"
            print("  %-22s %6d줄  파일 %d개%s" % (name, d["lines"], d["files"], delta))
        print("\n조건부 (발동 시 추가)")
        for name, n in conditional.items():
            print("  %-22s %6d줄" % (name, n))
        if missing:
            print("\n⛔ 누락 파일 %d개 — 합계가 실제보다 작다" % len(missing))
            for m in missing:
                print("   " + m)
    return 2 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
