#!/usr/bin/env python3
"""launch smoke 산출기 — 실행이 필요한 변경 표면이면 smoke 를 한 번 돌리거나 '실행 미검증' 배너를 남긴다 (F-366).

왜 스크립트인가: Tier 1 리뷰는 "빌드·런타임 미실행" 을 리포트에 적기만 했다 — 실행 여부를 Lead 의 기억에 맡기면
루트 화면을 바꾼 PR 에서도 실행 단계가 빠진다. 여기서는 판정(대상인가 · 돌릴 수 있는가 · 결과)을 결정적으로 낸다.

입력:
  --risk risk.json      gather 의 risk_scan 산출. `launch_surface.flag` 가 false 면 '대상 아님' 만 쓰고 실행하지 않는다
  --rule rules.json     project-rules 레코드(`modules/project-rules.md` §3). 최상위 `launchSmoke: {command, expect, timeout_s}`
  --repo DIR            smoke 를 돌릴 작업 트리
  --expect-head SHA     리뷰 대상 head(PR 이면 headRefOid). repo HEAD 와 다르면 실행하지 않고 배너 — 다른 리비전을 돌린 결과는 근거가 아니다
  --out launch-smoke.md 산출 경로. 첫 줄이 요약 줄이다(--check-report 가 리포트에서 이 줄을 찾는다)
  --check-report REPORT --smoke launch-smoke.md   리포트에 요약 줄이 없으면 exit 1('대상 아님' 은 검사하지 않는다)

출력 첫 줄(요약):
  launch smoke — 대상 아님(launch_surface 없음)
  launch smoke — ⛔ 실행 미검증 — <사유>
  launch smoke — SMOKE PASS|FAIL|TIMEOUT · exit N · expect 일치|불일치 · HEAD <sha7>

exit: 0 산출 · 1 --check-report 누락 · 2 사용법 · 입력 해독 실패(⛔ 통과 아님)
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time

HEAD = "launch smoke — "
TAIL_LINES = 20
TAIL_BYTES = 64 * 1024


def _load(path, what):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as e:
        raise SystemExit(f"{what} 를 읽지 못했다: {path} — {e}") from None


def _rule(path):
    """launchSmoke 레코드를 고른다. 형식이 틀리면 None + 사유 — 지어낸 기본값으로 돌리지 않는다."""
    if not path:
        return None, "규칙 없음(--rule 미지정 — project-rules 의 launchSmoke)"
    if not os.path.exists(path):
        return None, f"규칙 없음({path} 부재)"
    data = _load(path, "규칙")
    ls = data.get("launchSmoke") if isinstance(data, dict) else None
    if ls is None:
        return None, "규칙 없음(project-rules 에 launchSmoke 레코드가 없다)"
    if not isinstance(ls, dict):   # 검사기(check_project_rules)는 이 필드를 보지 않는다 — 여기서 형식을 가린다
        return None, "규칙 형식 오류(launchSmoke 는 객체여야 한다)"
    cmd, exp, tmo = ls.get("command"), ls.get("expect"), ls.get("timeout_s")
    if not (isinstance(cmd, str) and cmd.strip() and isinstance(exp, str) and exp
            and isinstance(tmo, (int, float)) and not isinstance(tmo, bool) and 0 < tmo <= 3600):
        return None, "규칙 형식 오류(launchSmoke 는 command · expect 문자열 · timeout_s 1~3600 초)"
    return {"command": cmd, "expect": exp, "timeout_s": float(tmo)}, ""


def _repo_head(repo):
    try:
        return subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _scan(log, needle):
    """로그 전체에서 expect 를 찾는다 — 꼬리만 보면 expect 뒤 긴 로그가 그 줄을 밀어내 성공을 FAIL 로 판정한다."""
    log.seek(0)
    carry, need = b"", needle.encode("utf-8")
    while True:
        chunk = log.read(1 << 20)
        if not chunk:
            return False
        buf = carry + chunk
        if need in buf:
            return True
        carry = buf[-(len(need) - 1):] if len(need) > 1 else b""


def _run(rule, repo):
    """유한 실행 — 출력은 임시 파일로 받는다(손자가 파이프를 붙잡아 읽기가 끝나지 않는 문제를 피한다).
    시간 초과면 프로세스 그룹째 죽인다(gate_check.py run_check 와 같은 계약: stdin 닫음 · 새 세션).
    expect 는 로그 전체에서 찾고, 리포트에는 끝 TAIL_BYTES 만 싣는다."""
    with tempfile.TemporaryFile() as log:
        proc = subprocess.Popen(["/bin/sh", "-c", rule["command"]], cwd=repo, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        timed_out = False
        try:
            proc.wait(timeout=rule["timeout_s"])
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
            proc.wait()
        hit = _scan(log, rule["expect"])
        log.seek(0, os.SEEK_END)
        log.seek(max(0, log.tell() - TAIL_BYTES))
        text = log.read().decode("utf-8", errors="replace")
    return proc.returncode, timed_out, text, hit


def produce(a):
    risk = _load(a.risk, "risk.json")
    surf = risk.get("launch_surface") if isinstance(risk, dict) else None
    if not isinstance(surf, dict) or "flag" not in surf:
        raise SystemExit("risk.json 에 launch_surface 가 없다 — risk_scan.py 가 이 판보다 낡았다(재수집)")
    if not surf["flag"]:
        return HEAD + "대상 아님(launch_surface 없음)", []
    why = ", ".join(surf.get("signals") or [])[:200]
    rule, reason = _rule(a.rule)
    if rule is None:
        return HEAD + "⛔ 실행 미검증 — " + reason, [f"표면: {why}"]
    head = _repo_head(a.repo)
    if not head:
        return HEAD + f"⛔ 실행 미검증 — repo HEAD 를 읽지 못했다({a.repo})", [f"표면: {why}"]
    if head != a.expect_head:
        return (HEAD + f"⛔ 실행 미검증 — HEAD 불일치(repo {head[:7]} ≠ 리뷰 대상 {a.expect_head[:7]})",
                [f"표면: {why}", "리뷰 대상 head 를 체크아웃한 트리에서 다시 돌린다"])
    rc, timed_out, text, hit = _run(rule, a.repo)
    verdict = "TIMEOUT" if timed_out else ("PASS" if rc == 0 and hit else "FAIL")
    summary = (HEAD + f"SMOKE {verdict} · exit {'-' if timed_out else rc} · expect {'일치' if hit else '불일치'}"
               f" · HEAD {head[:7]}")
    tail = text.splitlines()[-TAIL_LINES:]
    body = [f"표면: {why}", f"명령: `{rule['command']}` · 상한 {rule['timeout_s']:g}초 · expect `{rule['expect']}`",
            "", f"끝 {len(tail)}줄:", "```", *tail, "```"]
    return summary, body


def check_report(a):
    try:
        with open(a.smoke, encoding="utf-8") as fh:
            summary = fh.readline().rstrip("\n")
    except OSError:
        print(f"⛔ smoke 산출물이 없다: {a.smoke} — launch_smoke.py 를 먼저 돌린다")
        return 1
    if not summary.startswith(HEAD):
        print(f"⛔ smoke 산출물 첫 줄이 요약 줄이 아니다: {summary[:80]}")
        return 1
    if summary.startswith(HEAD + "대상 아님"):
        print("OK — 대상 아님(리포트 검사 생략)")
        return 0
    try:
        with open(a.check_report, encoding="utf-8") as fh:
            report = fh.read()
    except OSError:
        print(f"⛔ 리포트를 읽지 못했다: {a.check_report}")
        return 1
    if summary not in report:
        print(f"⛔ 리포트에 smoke 요약 줄이 없다 — 이 줄을 리포트 상단에 그대로 넣는다:\n{summary}")
        return 1
    print("OK — 리포트에 smoke 요약 줄이 있다")
    return 0


def main(argv):
    p = argparse.ArgumentParser(description="launch smoke 산출기 (F-366)")
    p.add_argument("--risk")
    p.add_argument("--rule")
    p.add_argument("--repo")
    p.add_argument("--expect-head")
    p.add_argument("--out")
    p.add_argument("--check-report")
    p.add_argument("--smoke")
    a = p.parse_args(argv)
    try:
        if a.check_report:
            if not a.smoke:
                p.error("--check-report 는 --smoke 와 함께 쓴다")
            return check_report(a)
        if not (a.risk and a.repo and a.expect_head and a.out):
            p.error("--risk · --repo · --expect-head · --out 필수 (--rule 은 없으면 배너)")
        summary, body = produce(a)
    except SystemExit as e:
        if isinstance(e.code, str):
            print("⛔ " + e.code, file=sys.stderr)
            return 2
        raise
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write("\n".join([summary, "", *body]).rstrip("\n") + "\n")
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
