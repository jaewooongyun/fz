#!/usr/bin/env python3
"""fz-plan light 경로 재생(S13 · F-578) — 스크립트가 닿는 마지막 소비자까지 가짜 CLI 로 돌린다.

light steps.json(riskMatrix 포함) ↔ GPT 독립 플랜 → plan_divergence 차이표 → P_VERIFY(플랜 본문 뒤에 차이표 — fz-plan Phase 2 규칙)
→ 정문 gpt-call.sh verify-cross(감사의 세션 · 격리 홈) → 가짜 CLI 가 받은 인자. 같은 감사로 두 번째 라운드를 부르면 첫 라운드가
격리 폴더를 지웠으므로 정문이 10 으로 끝나고, 호출자는 core § resume 교차의 폴백대로 기본 verify 로 간다.
kinds-resolve 의 가짜 세계(Env — 가짜 CLI · 프록시 루트 · 임시 홈)를 그대로 쓴다. 실제 GPT CLI · 사용자 홈을 건드리지 않는다.
셀(통과 줄 `PASS <셀>`):
  r3-light-divergence-produced-consumed       차이표 exit 0 · 차이표 머리가 정문이 합성한 verify-cross 프롬프트(CLI 마지막 인자)에 있다
  r3-light-replay-to-verify-cross-argv        CLI 인자 = exec resume · 감사의 세션 · read-only · 리뷰 스키마 · 그 뒤 격리 폴더 정리
  r3-f578-second-round-falls-back-to-verify   두 번째 verify-cross exit 10(12 아님) · 폴백 verify exit 0 · 판정 파일 verdict
exit: 0 전건 통과 · 1 실패
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.realpath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(R, "tests", "fixtures", "gpt", "kinds-resolve"))
sys.dont_write_bytecode = True
import capture as C  # noqa: E402 — 형제 fixture 의 가짜 세계

STEPS = {"title": "light", "steps": [
    {"id": "S1", "title": "목록 캐시", "files": ["Sources/App/List.swift (캐시 무효화)", "{FZ_WORK_DIR}/code/step-1.md"],
     "verify": {"kind": "command", "criterion": "c", "command": "echo S1_OK", "expect": "S1_OK"}},
    {"id": "S2", "title": "전용 화면", "files": ["Sources/App/Only.swift"],
     "verify": {"kind": "command", "criterion": "c", "command": "echo S2_OK", "expect": "S2_OK"}}],
    "rtm": [{"reqId": "R1", "requirement": "목록 갱신", "stepId": "S1"}],
    "riskMatrix": [{"risk": "캐시 무효화가 늦으면 목록이 옛 값을 보여 준다", "mitigation": "m"}]}
GPLAN = {"steps": [{"file": "Sources/App/List.swift", "action": "edit"}, {"file": "Sources/App/Extra.swift", "action": "add"}],
         "riskMatrix": [{"risk": "캐시 무효화가 늦으면 목록이 옛 값을 보여준다"}, {"risk": "동시 편집 충돌"}]}


def main():
    env = C.Env()
    res = {}
    try:
        kd = env.kdir("light-replay", "verify-cross")
        for name, doc in (("steps.json", STEPS), ("gpt-plan.json", GPLAN)):
            with open(os.path.join(kd, name), "w", encoding="utf-8") as fh:
                json.dump(doc, fh, ensure_ascii=False)
        d = subprocess.run([sys.executable, "-B", os.path.join(R, "scripts", "plan_divergence.py"), "--claude", f"{kd}/steps.json",
                            "--gpt", f"{kd}/gpt-plan.json", "--out", f"{kd}/divergence.md", "--json", f"{kd}/divergence.json"],
                           capture_output=True, text=True)
        div = open(f"{kd}/divergence.md", encoding="utf-8").read() if d.returncode == 0 else ""
        with open(f"{kd}/p_verify.txt", "w", encoding="utf-8") as fh:   # Phase 2 규칙: 플랜 본문 뒤에 4.5 차이표
            fh.write("## 검증할 플랜\nS1 목록 캐시 · S2 전용 화면\n\n" + div)
        iso = f"{kd}/fz-gpt-iso.L1GHT0"
        os.makedirs(f"{iso}/gpt-home", exist_ok=True)
        with open(f"{kd}/audit.json", "w") as fh:
            json.dump({"iso": iso, "sessionFile": f"{kd}/prev.json.session"}, fh)
        cross = C.GC_CALL + 'verify-cross --audit "$K/audit.json" --cd "$GIT_ROOT" --out "$K/cross.json" --prompt-file "$K/p_verify.txt" --prompt-out "$K/p_cross.txt"\n'
        p1, entry, cli = env.run(kd, cross, shim_output=C.REVIEW_OK)
        last = cli[-1] if cli else []
        res["r3-light-divergence-produced-consumed"] = (
            d.returncode == 0 and "# Claude ↔ GPT 독립 플랜 차이표" in div and "위험 대조 판정 불가" not in div
            and p1.returncode == 0 and bool(last) and "# Claude ↔ GPT 독립 플랜 차이표" in last[-1],
            f"divergence exit {d.returncode} · cross exit {p1.returncode} · {p1.stderr[-200:]}")
        res["r3-light-replay-to-verify-cross-argv"] = (
            p1.returncode == 0 and last[:2] == ["exec", "resume"] and "sandbox_mode=\"read-only\"" in last
            and any(x.endswith("schemas/gpt_review_schema.json") for x in last)
            and any(e[:2] == ["gpt-exec.sh", "resume"] and f"{kd}/prev.json.session" in e for e in entry)
            and any(e[:2] == ["gpt_independent.sh", "cleanup"] for e in entry) and not os.path.isdir(iso),
            f"cli {[x[:60] for x in last[:6]]} · entry {[e[:2] for e in entry]} · iso 남음 {os.path.isdir(iso)}")
        p2, _, _ = env.run(kd, cross, shim_output=C.REVIEW_OK)
        verify = C.GC_CALL + 'verify --cd "$GIT_ROOT" --out "$K/verify.json" --prompt-file "$K/p_verify.txt"\n'
        p3, _, _ = env.run(kd, verify, shim_output=C.REVIEW_OK) if p2.returncode == 10 else (None, None, None)
        verdict = json.load(open(f"{kd}/verify.json", encoding="utf-8")).get("verdict") if p3 and p3.returncode == 0 else None
        res["r3-f578-second-round-falls-back-to-verify"] = (
            p2.returncode == 10 and p3 is not None and p3.returncode == 0 and verdict == "approved",
            f"둘째 verify-cross exit {p2.returncode} ({p2.stderr.strip()[-160:]}) · verify exit {p3.returncode if p3 else '-'} · verdict {verdict}")
    finally:
        env.close()
    bad = 0
    for name, (ok, why) in res.items():
        print(f"PASS  {name}" if ok else f"FAIL  {name}  — {why}")
        bad += not ok
    return 1 if bad or len(res) != 3 else 0


if __name__ == "__main__":
    sys.exit(main())
