#!/usr/bin/env python3
"""fz_snapshot.py — 릴리즈마다 하네스 정적 부하를 1행 기록한다 (R3 시계열).

왜: floor·규칙 수·`⛔` 개수는 **매 릴리즈 찍어 두지 않으면 성장을 못 본다**(F-139).
지금 값만 보면 "언제 자랐나"를 6주 뒤 재구성해야 한다. 이 스크립트는 append-only TSV
1행이고, 그 이상 하지 않는다.

⛔ 결정론: 같은 트리 + 같은 `--date` 는 같은 행을 만든다. 같은 `(date, version)` 이
   이미 있으면 **덮어쓰지 않고** 알린다(`--force` 만 예외).

Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

DEFAULT_TELEMETRY_DIR = "~/.fz/telemetry"  # 사용자 중립 기본값 — 개인 경로는 env FZ_TELEMETRY_DIR 로 (governance:146)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PLUGIN_ROOT = os.path.dirname(SCRIPT_DIR)  # 자기 위치에서 해석 — 캐시 설치·다른 클론 경로에서도 맞는다 (N6 앵커)
SNAPSHOT_FILE = "snapshots.tsv"

# 고정 열 — floor_<skill> 열은 이 뒤에 **스킬명 정렬**로 붙는다.
BASE_COLUMNS = ("date", "version", "skills")
TAIL_COLUMNS = (
    "ban_skills",
    "ban_modules",
    "ban_claude_md",
    "ban_memory",
    "bullets_claude_md",
    "wf_calls",
    "wf_effort_dist",
    "guides_lines",
    "modules_lines",
    "skills_lines",
)

RE_LOAD_ROW = re.compile(r"^([A-Za-z][\w-]*)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)%\s*$")
RE_BULLET = re.compile(r"^\s*[-*]\s+")
RE_EFFORT = re.compile(r"effort\s*:\s*['\"]([a-z]+)['\"]")


def parse_constraint_table(text):
    """measure_constraint_load.py 표1 파싱: `skill refs floor ceil floor%`.

    ⛔ `--json` 대신 표1 텍스트를 본다(계약 지정). floor 0 인 스킬(`code-auditor`)은
       **데이터이지 파싱 실패가 아니다** — 행이 하나도 안 잡힐 때만 실패로 본다.
    """
    rows = {}
    in_table = False
    for line in text.splitlines():
        if line.startswith("■ 표1"):
            in_table = True
            continue
        if in_table and line.startswith("■"):
            break
        if not in_table:
            continue
        match = RE_LOAD_ROW.match(line.strip())
        if match:
            rows[match.group(1)] = {
                "refs": int(match.group(2)),
                "floor": int(match.group(3)),
                "ceil": int(match.group(4)),
                "floor_pct": int(match.group(5)),
            }
    return rows


def measure_floors(root):
    script = os.path.join(root, "scripts", "measure_constraint_load.py")
    if not os.path.isfile(script):
        return {}, "measure_constraint_load.py 없음: " + script
    try:
        proc = subprocess.run(
            [sys.executable, script, root], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180
        )
    except Exception as exc:  # noqa: BLE001
        return {}, "실행 실패: %s" % exc
    rows = parse_constraint_table(proc.stdout.decode("utf-8", "replace"))
    if not rows:
        return {}, "표1 파싱 0행 (exit %d) — ⛔ 0건은 측정 실패를 먼저 의심" % proc.returncode
    return rows, None


def count_marker(paths, marker="⛔"):
    total = 0
    for path in paths:
        try:
            with open(path, "r", errors="replace") as handle:
                total += handle.read().count(marker)
        except OSError:
            continue
    return total


def count_lines(paths):
    total = 0
    for path in paths:
        try:
            with open(path, "r", errors="replace") as handle:
                total += sum(1 for _ in handle)
        except OSError:
            continue
    return total


def count_bullets(path):
    if not path or not os.path.isfile(path):
        return 0
    try:
        with open(path, "r", errors="replace") as handle:
            return sum(1 for line in handle if RE_BULLET.match(line))
    except OSError:
        return 0


def read_version(root):
    for candidate in (os.path.join(root, ".claude-plugin", "plugin.json"), os.path.join(root, "plugin.json")):
        if os.path.isfile(candidate):
            try:
                with open(candidate, "r", errors="replace") as handle:
                    return str(json.load(handle).get("version") or "?")
            except (OSError, ValueError):
                return "?"
    return "?"


def collect(root, date_str, memory_md):
    skills_md = sorted(glob.glob(os.path.join(root, "skills", "*", "SKILL.md")))
    modules_md = sorted(glob.glob(os.path.join(root, "modules", "*.md")))
    guides_md = sorted(glob.glob(os.path.join(root, "guides", "*.md")))
    wf_js = sorted(glob.glob(os.path.join(root, "workflows", "*.js")))
    claude_md = os.path.join(root, "CLAUDE.md")

    wf_calls = 0
    effort = {}
    for path in wf_js:
        try:
            with open(path, "r", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        wf_calls += text.count("agent(")
        for value in RE_EFFORT.findall(text):
            effort[value] = effort.get(value, 0) + 1
    effort_dist = " ".join("%s:%d" % (k, effort[k]) for k in sorted(effort)) or "-"

    floors, floor_err = measure_floors(root)
    row = {
        "date": date_str,
        "version": read_version(root),
        "skills": len(skills_md),
        "ban_skills": count_marker(skills_md),
        "ban_modules": count_marker(modules_md),
        "ban_claude_md": count_marker([claude_md]) if os.path.isfile(claude_md) else 0,
        "ban_memory": count_marker([memory_md]) if memory_md and os.path.isfile(memory_md) else "-",
        "bullets_claude_md": count_bullets(claude_md),
        "wf_calls": wf_calls,
        "wf_effort_dist": effort_dist,
        "guides_lines": count_lines(guides_md),
        "modules_lines": count_lines(modules_md),
        "skills_lines": count_lines(skills_md),
    }
    for skill in floors:
        row["floor_" + skill] = floors[skill]["floor"]
    columns = list(BASE_COLUMNS) + ["floor_" + s for s in sorted(floors)] + list(TAIL_COLUMNS)
    return row, columns, floor_err


class SnapshotUnreadable(Exception):
    """존재하는 스냅샷을 읽지 못했다 — 부재(정상)와 다른 상태. ⛔ 이것을 (None, []) 로 돌리면
    `--diff` 가 "행 2개 미만" 으로 통과하고 `write_snapshot` 이 `w` 로 열어 **이력을 지운다**
    (GPT 리뷰 2026-09-06). 전파해서 호출부가 exit 2 를 내게 한다."""


def read_tsv(path):
    if not os.path.isfile(path):
        return None, []
    try:
        with open(path, "r", errors="replace") as handle:
            lines = [ln.rstrip("\n") for ln in handle if ln.strip()]
    except OSError as exc:
        raise SnapshotUnreadable("%s: %s" % (path, exc))
    if not lines:
        return None, []
    header = lines[0].split("\t")
    rows = [dict(zip(header, ln.split("\t"))) for ln in lines[1:]]
    return header, rows


def write_snapshot(args, out):
    root = os.path.expanduser(args.root)
    if not os.path.isdir(os.path.join(root, "skills")):
        out("⛔ 플러그인 루트가 아님: %s" % root)
        return 2
    memory_md = os.environ.get("FZ_MEMORY_MD")
    row, columns, floor_err = collect(root, args.date, os.path.expanduser(memory_md) if memory_md else None)
    if floor_err:
        out("⚠️ floor 미측정 — %s (floor_* 열 없음)" % floor_err)

    telemetry_dir = os.path.expanduser(args.telemetry_dir)
    os.makedirs(telemetry_dir, exist_ok=True)
    path = os.path.join(telemetry_dir, SNAPSHOT_FILE)
    try:
        header, rows = read_tsv(path)
    except SnapshotUnreadable as exc:
        out("⛔ 기존 스냅샷을 읽지 못했다 — 기록하지 않는다(이력 보호): %s" % exc)
        return 2

    if header is None:
        header = columns
        with open(path, "w") as handle:
            handle.write("\t".join(header) + "\n")
    else:
        missing = [c for c in columns if c not in header]
        extra = [c for c in header if c not in columns]
        if missing or extra:
            # ⛔ append-only 라 헤더를 고치지 않는다. 열 집합이 달라진 사실만 알리고
            #    기존 헤더에 맞춰 쓴다 — 조용히 열을 밀면 과거 행이 다른 뜻이 된다.
            out("⚠️ 열 집합 변동 — 새 열 %s / 사라진 열 %s (기존 헤더 유지, 값은 `-`)"
                % (missing or "없음", extra or "없음"))

    for existing in rows:
        if existing.get("date") == row["date"] and existing.get("version") == row["version"]:
            if not args.force:
                out("이미 존재: date=%s version=%s (행 %d개 유지). 덮어쓰려면 --force"
                    % (row["date"], row["version"], len(rows)))
                return 0
            out("--force: 같은 (date, version) 위에 행을 추가한다")
            break

    with open(path, "a") as handle:
        handle.write("\t".join(str(row.get(c, "-")) for c in header) + "\n")
    out("기록: %s (행 %d개)" % (path, len(rows) + 1))
    return 0


def diff_snapshot(args, out):
    path = os.path.join(os.path.expanduser(args.telemetry_dir), SNAPSHOT_FILE)
    try:
        header, rows = read_tsv(path)
    except SnapshotUnreadable as exc:
        out("⛔ 스냅샷을 읽지 못했다 — 비교 불가와 다른 상태(측정 실패): %s" % exc)
        return 2
    if header is None or len(rows) < 2:
        out("비교 불가: 행이 2개 미만 (%s)" % path)
        return 0
    before, after = rows[-2], rows[-1]
    out("%s(v%s) → %s(v%s)" % (before.get("date"), before.get("version"), after.get("date"), after.get("version")))
    warned = 0
    for column in header:
        if column in ("date", "version"):
            continue
        old, new = before.get(column, "-"), after.get(column, "-")
        if old == new:
            continue
        mark = ""
        if column.startswith("floor_") and old.isdigit() and new.isdigit() and int(old) > 0:
            growth = 100.0 * (int(new) - int(old)) / int(old)
            mark = "  (%+.1f%%)" % growth
            if growth >= 10:
                mark += " ⚠️"
                warned += 1
        out("  %-28s %s → %s%s" % (column, old, new, mark))
    out("floor 10%% 이상 증가: %d개 (경고, 실패 아님)" % warned)
    return 0


# ── self-test ───────────────────────────────────────────────────────────────
FAKE_MEASURE = '''\
import sys
print("■ 표1: x")
print("skill            refs  floor~tok  ceil~tok  floor%")
print("-" * 51)
print("alpha              3       1000      1200     83%")
print("beta               1          0         0      0%")
print("")
print("■ 표2: y")
print("noise              9       9999      9999     99%")
'''


def _fake_plugin(base, floor_alpha=1000):
    root = os.path.join(base, "plugin")
    for sub in ("skills/alpha", "skills/beta", "modules", "guides", "workflows", "scripts", ".claude-plugin"):
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    with open(os.path.join(root, "skills", "alpha", "SKILL.md"), "w") as h:
        h.write("# alpha\n⛔ 금지 1\n- bullet\n⛔ 금지 2\n")
    with open(os.path.join(root, "skills", "beta", "SKILL.md"), "w") as h:
        h.write("# beta\n⛔ 금지 3\n")
    with open(os.path.join(root, "modules", "m.md"), "w") as h:
        h.write("⛔ a\n⛔ b\nplain\n")
    with open(os.path.join(root, "guides", "g.md"), "w") as h:
        h.write("l1\nl2\nl3\n")
    with open(os.path.join(root, "workflows", "w.js"), "w") as h:
        h.write("agent('a', {effort: 'xhigh'});\nagent('b', {effort: 'xhigh'});\nagent('c', {effort: 'high'});\n")
    with open(os.path.join(root, "CLAUDE.md"), "w") as h:
        h.write("# t\n- b1\n- b2\n* b3\n⛔ x\n")
    with open(os.path.join(root, ".claude-plugin", "plugin.json"), "w") as h:
        json.dump({"version": "9.9.9"}, h)
    with open(os.path.join(root, "scripts", "measure_constraint_load.py"), "w") as h:
        h.write(FAKE_MEASURE.replace("1000", str(floor_alpha)))
    return root


def self_test():
    checks = []

    def check(name, got, want):
        checks.append((name, got == want, got, want))

    check("표1 파싱 (표2 미포함, floor 0 보존)",
          parse_constraint_table(subprocess.run([sys.executable, "-c", FAKE_MEASURE], stdout=subprocess.PIPE).stdout.decode()),
          {"alpha": {"refs": 3, "floor": 1000, "ceil": 1200, "floor_pct": 83},
           "beta": {"refs": 1, "floor": 0, "ceil": 0, "floor_pct": 0}})

    base = tempfile.mkdtemp(prefix="fz-snapshot-selftest-")
    root = _fake_plugin(base)
    telemetry = os.path.join(base, "telemetry")
    lines = []
    args = argparse.Namespace(root=root, date="2026-09-06", telemetry_dir=telemetry, force=False)
    check("1회차 exit", write_snapshot(args, lines.append), 0)
    header, rows = read_tsv(os.path.join(telemetry, SNAPSHOT_FILE))
    check("헤더 열 순서", header,
          ["date", "version", "skills", "floor_alpha", "floor_beta"] + list(TAIL_COLUMNS))
    check("행 1개", len(rows), 1)
    check("version", rows[0]["version"], "9.9.9")
    check("skills 수", rows[0]["skills"], "2")
    check("ban_skills", rows[0]["ban_skills"], "3")
    check("ban_modules", rows[0]["ban_modules"], "2")
    check("ban_claude_md", rows[0]["ban_claude_md"], "1")
    check("ban_memory 미설정", rows[0]["ban_memory"], "-")
    check("bullets_claude_md", rows[0]["bullets_claude_md"], "3")
    check("wf_calls(agent( 수)", rows[0]["wf_calls"], "3")
    check("wf_effort_dist", rows[0]["wf_effort_dist"], "high:1 xhigh:2")
    check("floor_beta 0 보존", rows[0]["floor_beta"], "0")
    check("guides_lines", rows[0]["guides_lines"], "3")

    lines2 = []
    check("2회차 exit", write_snapshot(args, lines2.append), 0)
    _, rows2 = read_tsv(os.path.join(telemetry, SNAPSHOT_FILE))
    check("2회차 행 수 불변", len(rows2), 1)
    check("2회차 '이미 존재' 안내", any("이미 존재" in ln for ln in lines2), True)

    # floor 20% 증가 + 날짜 변경 → --diff 가 ⚠️ 를 낸다
    _fake_plugin(base, floor_alpha=1200)
    args3 = argparse.Namespace(root=root, date="2026-09-13", telemetry_dir=telemetry, force=False)
    lines3 = []
    check("3회차 exit", write_snapshot(args3, lines3.append), 0)
    _, rows3 = read_tsv(os.path.join(telemetry, SNAPSHOT_FILE))
    check("3회차 행 2개", len(rows3), 2)
    dlines = []
    check("--diff exit 0", diff_snapshot(argparse.Namespace(telemetry_dir=telemetry), dlines.append), 0)
    # ⛔ 읽을 수 없는 기존 스냅샷 — 부재로 오인해 `w` 로 덮으면 이력이 사라진다 (GPT 리뷰 2026-09-06)
    locked = os.path.join(telemetry, "snapshots.tsv")
    before_bytes = open(locked, "rb").read()
    os.chmod(locked, 0)
    try:
        code_unreadable = diff_snapshot(argparse.Namespace(telemetry_dir=telemetry), (lambda _l: None))
    finally:
        os.chmod(locked, 0o644)
    check("--diff 읽기 실패 → exit 2 (비교 불가 아님)", code_unreadable, 2)
    check("읽기 실패 후 파일 무손실", open(locked, "rb").read() == before_bytes, True)
    check("--diff floor 증가 ⚠️", any("floor_alpha" in ln and "⚠️" in ln for ln in dlines), True)
    check("--diff 요약", any("floor 10% 이상 증가: 1개" in ln for ln in dlines), True)

    bad = argparse.Namespace(root=os.path.join(base, "nope"), date="2026-09-06", telemetry_dir=telemetry, force=False)
    check("플러그인 루트 아님 → exit 2", write_snapshot(bad, lambda s: None), 2)

    failed = [c for c in checks if not c[1]]
    for name, ok, got, want in checks:
        print("%s %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "  got=%r want=%r" % (got, want)))
    print("%d/%d passed" % (len(checks) - len(failed), len(checks)))
    return 1 if failed else 0


def main(argv):
    parser = argparse.ArgumentParser(description="fz 정적 부하 스냅샷 (append-only 1행)")
    parser.add_argument("--root", default=DEFAULT_PLUGIN_ROOT, help="플러그인 루트")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (기본: 오늘 UTC) — 결정론용")
    parser.add_argument(
        "--telemetry-dir", default=os.environ.get("FZ_TELEMETRY_DIR", DEFAULT_TELEMETRY_DIR)
    )
    parser.add_argument("--force", action="store_true", help="같은 (date, version) 이어도 행 추가")
    parser.add_argument("--diff", action="store_true", help="마지막 두 행 비교 (exit 0, 경고만)")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()
    if args.diff:
        return diff_snapshot(args, print)
    if args.date is None:
        args.date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    return write_snapshot(args, print)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
