#!/usr/bin/env python3
"""fz_telemetry_report.py — 이미 기록된 데이터만 읽어 하네스 부하 리포트를 만드는 집계기.

⛔ 이 스크립트는 **새로 기록하지 않는다.** 입력 4종은 전부 다른 주체가 이미 쓴 것이다:
  1. 트랜스크립트 `~/.claude/projects/**/*.jsonl` — Claude Code가 쓴다
  2. 워크플로 journal `…/subagents/workflows/wf_*/journal.jsonl` — Workflow 도구가 쓴다
  3. fz-findings `entries/F-*.md` frontmatter — 사람이 쓴다
  4. `measure_constraint_load.py` 표1 — 호출 시 계산된다(정적)
중복 소스를 만들지 않는 것이 계측의 1차 제약이다(plan §2).

한계(정직성):
  · 비용은 **공식 단가 × usage 계산치**이며 실청구가 아니다. 캐시 쓰기는 1h TTL 단가로 고정 가정.
  · 지연은 직전 `user` 엔트리와 `assistant` 엔트리의 timestamp 차분이다. 사용자 입력 대기가
    섞일 수 있어 30분 초과는 잘랐다. 도구 실행 시간은 포함하지 않는다.
  · 워크플로 wall-time은 `agent-*.jsonl` mtime 최소~최대 차분이라 근사다(`[근사]` 표기).
  · 스테이지 판별은 result **키 집합** 휴리스틱이다. 미매치 키 집합은 부록에 전수 열거한다.

Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import glob
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile

# ── 단가 $/M: (input, cache_write_1h, cache_read, output) ────────────────────
# 출처: platform.claude.com/docs/en/about-claude/pricing (2026-09-06 확인).
# ⛔ evidence/usage_agg.py 의 표와 다르다 — 그 표는 Fable 5.1 캐시읽기를 1.0 으로,
#    Sonnet 5 를 3/6/0.3/15 로 적어 두었다. 정본은 아래(계약 §Step1).
PRICES = {
    "claude-fable-5-1": (10.0, 20.0, 0.25, 50.0),
    "claude-fable-5": (10.0, 20.0, 1.0, 50.0),
    "claude-opus-5": (5.0, 10.0, 0.5, 25.0),
    "claude-sonnet-5": (2.0, 4.0, 0.2, 10.0),
    "claude-opus-4-8": (5.0, 10.0, 0.5, 25.0),
}

# ⛔ usage 가 비어 있거나 컨텍스트 0인 합성 엔트리는 표에서 뺀다 — 모델 행이 아니다.
EXCLUDED_MODELS = ("<synthetic>", "<fallback>", "?")

# ── journal result 키 집합 → 스테이지 (계약 Step 4 STAGE_SIGNATURES) ──────────
# 판정 = 필수 키 집합의 **부분집합 포함**. 앞에 놓인 것이 먼저 이긴다(구체적인 것 우선).
STAGE_SIGNATURES = (
    (("issues", "overall_assessment", "strengths"), "review1"),
    (("finding_id", "refuted", "reason"), "counter"),
    (("challenges", "missedIssues"), "counter"),
    (("adjustments", "additions"), "cross"),
    (("files", "summary", "buildExpectation"), "changeset"),
    (("issues", "verdict"), "verify"),
)

# 워크플로 이름 정규화 — 인라인 스크립트는 `<name>-wf_<id>.js` 로 저장된다.
RE_WF_SUFFIX = re.compile(r"-wf_[0-9a-f]{8}-[0-9a-f]{3}$")
RE_WF_DIR = re.compile(r"Transcript dir:\s*(\S+)")
RE_WF_SCRIPT = re.compile(r"Script file:\s*(\S+)")
RE_INLINE_NAME = re.compile(r"name:\s*['\"]([^'\"]+)['\"]")

DEFAULT_TELEMETRY_DIR = "~/.fz/telemetry"  # 사용자 중립 기본값 — 개인 경로는 env FZ_TELEMETRY_DIR 로 (governance:146)
DEFAULT_FINDINGS_DIR = os.environ.get("FZ_FINDINGS_DIR", "")  # 비우면 §4 findings 절은 "미설정"으로 표기 (개인 레지스트리 경로는 배포물에 두지 않는다)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PLUGIN_ROOT = os.path.dirname(SCRIPT_DIR)  # 자기 위치에서 해석 (N6 앵커)


# ── 유틸 ────────────────────────────────────────────────────────────────────
def parse_day(s):
    """YYYY-MM-DD → UTC 자정 datetime."""
    y, m, d = (int(x) for x in s.split("-"))
    return datetime.datetime(y, m, d, tzinfo=datetime.timezone.utc)


def parse_ts(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def pct(values_sorted, p):
    """정렬된 리스트의 p분위. ⛔ 빈 리스트는 None — 0 으로 채우면 '측정됨'으로 읽힌다."""
    if not values_sorted:
        return None
    return values_sorted[min(len(values_sorted) - 1, int(len(values_sorted) * p))]


def med(values):
    return statistics.median(values) if values else None


def fmt(value, digits=1, dash="n/a"):
    if value is None:
        return dash
    if isinstance(value, float):
        return ("%%.%df" % digits) % value
    return str(value)


def price_for(model):
    """정확 일치 → 최장 접두 일치. 날짜 접미(`-20251001`)가 붙은 id 를 흡수한다."""
    if model in PRICES:
        return PRICES[model]
    best = None
    for key in PRICES:
        if model.startswith(key) and (best is None or len(key) > len(best)):
            best = key
    return PRICES[best] if best else None


def norm_wf_name(raw):
    """`/a/b/code-pair.js` · `foo-wf_1234abcd-56f.js` · `foo` → 공통 이름."""
    if not raw:
        return "?"
    name = os.path.basename(str(raw).rstrip("/"))
    if name.endswith(".js"):
        name = name[:-3]
    return RE_WF_SUFFIX.sub("", name)


def tool_result_text(block):
    """tool_result content 는 문자열이거나 [{type:text,text:…}] 다."""
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)
    return ""


# ── 1. 트랜스크립트 집계 ────────────────────────────────────────────────────
class TranscriptAgg(object):
    """assistant 메시지의 usage·timestamp·attributionSkill·isSidechain 집계.

    ⛔ 중복 제거는 **파일 단위**로 `message.id` 를 본다. 같은 메시지가 세션 파일과
       sidechain 파일에 각각 나타나는 경우가 있어 전역 dedup 을 걸면 worker 행이 사라진다
       (evidence/latency_agg.py 와 같은 범위 — report.md §2.1 이 그 값으로 나왔다).
    """

    def __init__(self):
        self.by_model = collections.defaultdict(lambda: collections.Counter())
        self.lat = collections.defaultdict(list)
        self.ctx = collections.defaultdict(list)
        self.cost_per_call = collections.defaultdict(list)
        self.by_skill = collections.defaultdict(lambda: collections.Counter())
        self.skill_lat = collections.defaultdict(list)
        self.skill_effort = collections.defaultdict(lambda: collections.Counter())
        self.wf_calls = collections.Counter()
        self.wf_id_to_name = {}
        self.n_files = 0
        self.n_files_with_msgs = 0
        self.n_msgs = 0
        self.effort_all = collections.Counter()

    def add_file(self, path, since, until):
        self.n_files += 1
        entries = []
        try:
            handle = open(path, "r", errors="replace")
        except OSError:
            return
        with handle:
            for line in handle:
                if not line.startswith("{"):
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if obj.get("type") not in ("user", "assistant"):
                    continue
                stamp = parse_ts(obj.get("timestamp"))
                if stamp is None or stamp < since or stamp >= until:
                    continue
                entries.append((stamp, obj))
        if not entries:
            return
        used = False
        prev_user = None
        seen_ids = set()
        seen_tool_ids = set()
        for stamp, obj in entries:
            if obj.get("type") == "user":
                prev_user = stamp
                self._scan_tool_results(obj)
                continue
            # ⛔ 하나의 assistant 메시지가 **content 블록마다 한 줄씩** 기록된다 —
            #    thinking·text·tool_use 가 같은 `message.id` 를 공유하고 `usage` 도 매 줄
            #    반복된다(실측: code-pair Workflow 호출 11건 중 5건이 그 메시지의 두 번째
            #    이후 줄에 있다). 그래서 축마다 dedup 키가 다르다:
            #      · usage/지연 → `message.id` (줄 반복을 한 번으로)
            #      · tool_use  → 블록 `id` (⛔ message.id 로 거르면 블록이 통째로 사라진다)
            self._scan_workflow_calls(obj, seen_tool_ids)
            message = obj.get("message") or {}
            usage = message.get("usage") or {}
            if not usage:
                continue
            key_id = message.get("id") or obj.get("requestId")
            if key_id is not None:
                if key_id in seen_ids:
                    continue
                seen_ids.add(key_id)
            model = message.get("model") or "?"
            if model in EXCLUDED_MODELS:
                continue
            used = True
            self.n_msgs += 1
            side = "worker" if obj.get("isSidechain") else "main"
            self._accumulate(model, side, obj, usage, stamp, prev_user)
        if used:
            self.n_files_with_msgs += 1

    def _accumulate(self, model, side, obj, usage, stamp, prev_user):
        tin = usage.get("input_tokens", 0) or 0
        cw = usage.get("cache_creation_input_tokens", 0) or 0
        cr = usage.get("cache_read_input_tokens", 0) or 0
        out = usage.get("output_tokens", 0) or 0
        think = ((usage.get("output_tokens_details") or {}).get("thinking_tokens", 0)) or 0
        key = (model, side)
        counter = self.by_model[key]
        counter["msgs"] += 1
        counter["in"] += tin
        counter["cache_w"] += cw
        counter["cache_r"] += cr
        counter["out"] += out
        counter["think"] += think
        self.ctx[key].append(tin + cw + cr)
        price = price_for(model)
        if price:
            cost = (tin * price[0] + cw * price[1] + cr * price[2] + out * price[3]) / 1e6
            counter["cost_micro"] += int(round(cost * 1e6))
            self.cost_per_call[key].append(cost)
        latency = None
        if prev_user is not None:
            delta = (stamp - prev_user).total_seconds()
            if 0 < delta < 1800:
                latency = delta
                self.lat[key].append(delta)

        effort = obj.get("effort") or "-"
        self.effort_all[effort] += 1
        skill = obj.get("attributionSkill") or "-"
        sk = self.by_skill[skill]
        sk["msgs"] += 1
        sk["out"] += out
        sk["think"] += think
        sk["cache_r"] += cr
        sk["cache_w"] += cw
        if side == "worker":
            sk["worker_msgs"] += 1
        self.skill_effort[skill][effort] += 1
        if latency is not None:
            self.skill_lat[skill].append(latency)

    def _scan_workflow_calls(self, obj, seen_tool_ids):
        content = (obj.get("message") or {}).get("content")
        if not isinstance(content, list):
            return
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            if block.get("name") != "Workflow":
                continue
            block_id = block.get("id")
            if block_id is not None:
                if block_id in seen_tool_ids:
                    continue
                seen_tool_ids.add(block_id)
            payload = block.get("input") or {}
            script = payload.get("script") or ""
            found = RE_INLINE_NAME.search(script) if script else None
            if payload.get("scriptPath"):
                name = norm_wf_name(payload.get("scriptPath"))
            elif found:
                name = norm_wf_name(found.group(1))
            else:
                name = norm_wf_name(payload.get("name") or "?")
            self.wf_calls[name] += 1

    def _scan_tool_results(self, obj):
        """Workflow 기동 응답에서 `wf_<id>` ↔ 스크립트 파일명을 잇는다.

        ⛔ 계약이 적은 `…/workflows/scripts/<name>-wf_<id>.js` 형제 파일은 **scriptPath 로
           띄운 워크플로에는 존재하지 않는다**(인라인 스크립트만 저장된다). 실측상
           code-pair·peer-review 가 정확히 그 경우여서, 그 경로만 쓰면 스테이지 카운트가
           달린 wf 폴더들의 이름이 전부 미해결로 남는다. 기동 응답 본문의
           `Transcript dir:` + `Script file:` 짝이 54/54 를 덮는다(실측).
        """
        content = (obj.get("message") or {}).get("content")
        if not isinstance(content, list):
            return
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            text = tool_result_text(block)
            if "Transcript dir:" not in text:
                continue
            dir_m = RE_WF_DIR.search(text)
            script_m = RE_WF_SCRIPT.search(text)
            if dir_m and script_m:
                wf_id = os.path.basename(dir_m.group(1).rstrip("/"))
                self.wf_id_to_name[wf_id] = norm_wf_name(script_m.group(1))


def collect_transcripts(projects_root, since, until):
    agg = TranscriptAgg()
    pattern = os.path.join(projects_root, "**", "*.jsonl")
    # ⛔ recursive glob 유지 — subagents/**/agent-*.jsonl 이 worker 행의 유일한 출처다.
    for path in sorted(glob.glob(pattern, recursive=True)):
        agg.add_file(path, since, until)
    return agg


# ── 2. 워크플로 journal ─────────────────────────────────────────────────────
OVERTURN_WORDS = {"refute", "false_positive"}
UPHOLD_WORDS = {"uphold", "agree"}
ADJUST_WORDS = {"adjust"}


def count_verdicts(result):
    """result 트리를 걸어 판정 어휘를 (overturn, uphold, adjust) 로 센다.

    `refuted` bool 과 `verdict` 문자열을 같은 축에 놓는다. 값이 위 세 집합에 없으면 세지 않는다
    (예: verify 의 `verdict: "issues"`). 한 판정 = 1 카운트, 중첩 깊이 무관.
    """
    ov = up = ad = 0
    stack = [result]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if node.get("refuted") is True:
                ov += 1
            elif node.get("refuted") is False:
                up += 1
            verdict = node.get("verdict")
            if isinstance(verdict, str):
                if verdict in OVERTURN_WORDS:
                    ov += 1
                elif verdict in UPHOLD_WORDS:
                    up += 1
                elif verdict in ADJUST_WORDS:
                    ad += 1
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return ov, up, ad


def classify_result(result):
    """result dict → (stage, 기여도 카운터). 미매치는 ('other', keys)."""
    if not isinstance(result, dict):
        return "other", None
    keys = set(result.keys())
    for required, stage in STAGE_SIGNATURES:
        if set(required).issubset(keys):
            return stage, None
    return "other", tuple(sorted(keys))


def collect_journals(projects_root, since, until, wf_id_to_name):
    """wf 폴더별 실행 1건. 기간 판정은 journal.jsonl mtime(근사)."""
    rows = {}
    unknown = collections.Counter()
    pattern = os.path.join(projects_root, "*", "*", "subagents", "workflows", "wf_*", "journal.jsonl")
    for journal in sorted(glob.glob(pattern)):
        folder = os.path.dirname(journal)
        wf_id = os.path.basename(folder)
        try:
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(journal), datetime.timezone.utc)
        except OSError:
            continue
        if mtime < since or mtime >= until:
            continue
        name = wf_id_to_name.get(wf_id)
        if not name:
            name = _name_from_sibling_script(folder, wf_id) or ("unnamed:" + wf_id)
        row = rows.setdefault(
            name,
            {
                "runs": 0,
                "walls": [],
                "stages": collections.Counter(),
                "stage_verdicts": {},  # stage → {overturn, uphold, adjust} — §8.2 "스테이지 X 제거 후보" 판정의 분모 (Codex 리뷰 2026-09-06)
                "issues": 0,
                "overturn": 0,   # refuted=true · verdict refute · verdict false_positive — 판정 어휘 표준화
                "uphold": 0,     # verdict uphold · agree
                "adjust": 0,     # verdict adjust
                "adjustments": 0,
                "additions": 0,
                "results": 0,
            },
        )
        row["runs"] += 1
        wall = _wall_seconds(folder)
        if wall is not None:
            row["walls"].append(wall)
        _read_journal(journal, row, unknown)
    return rows, unknown


def _name_from_sibling_script(folder, wf_id):
    """`<session>/workflows/scripts/<name>-wf_<id>.js` 폴백.

    journal 은 `<session>/subagents/workflows/wf_<id>/`, 스크립트는
    `<session>/workflows/scripts/` 로 **서브트리가 다르다**(계약의 경로는 부정확 — 실측 정정).
    """
    session_dir = os.path.dirname(os.path.dirname(os.path.dirname(folder)))
    for candidate in glob.glob(os.path.join(session_dir, "workflows", "scripts", "*" + wf_id + ".js")):
        return norm_wf_name(candidate)
    return None


def _wall_seconds(folder):
    stamps = []
    for path in glob.glob(os.path.join(folder, "agent-*.jsonl")):
        try:
            stamps.append(os.path.getmtime(path))
        except OSError:
            continue
    if len(stamps) < 2:
        return None
    return max(stamps) - min(stamps)


def _read_journal(journal, row, unknown):
    try:
        handle = open(journal, "r", errors="replace")
    except OSError:
        return
    with handle:
        for line in handle:
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if obj.get("type") != "result":
                continue
            row["results"] += 1
            result = obj.get("result")
            stage, unknown_keys = classify_result(result)
            row["stages"][stage] += 1
            if unknown_keys is not None:
                unknown[unknown_keys] += 1
            if not isinstance(result, dict):
                continue
            issues = result.get("issues")
            if isinstance(issues, list):
                row["issues"] += len(issues)
            # ⛔ 판정은 최상위에만 있지 않다 — `challenges[].verdict`(peer-review counter)·
            #    `adjustments[].verdict`(교차)·top-level `refuted`(refute 스테이지) 세 형태를
            #    실측했다(2026-09-06: refuted 33 · uphold/refute 23 · agree/adjust/false_positive 226).
            #    최상위 `refuted` 만 세면 peer-review 의 counter 기여도가 0 으로 찍힌다(측정 실패).
            overturn, uphold, adjust = count_verdicts(result)
            row["overturn"] += overturn
            row["uphold"] += uphold
            row["adjust"] += adjust
            # ⛔ 합계만 남기면 "교차가 뒤집고 counter 가 유지"와 그 반대가 같은 숫자가 된다 — 스테이지 키를 보존한다.
            sv = row["stage_verdicts"].setdefault(stage, {"overturn": 0, "uphold": 0, "adjust": 0})
            sv["overturn"] += overturn
            sv["uphold"] += uphold
            sv["adjust"] += adjust
            for field in ("adjustments", "additions"):
                value = result.get(field)
                if isinstance(value, list):
                    row[field] += len(value)


# ── 3. fz-findings frontmatter ──────────────────────────────────────────────
def collect_findings(findings_dir, since, until):
    """`---` 블록에서 date·detector·stage·status·gap_type·harness_verdict 만 읽는다.

    ⛔ harness_verdict 는 **읽기만** 한다. 없으면 detector 로 추정:
       user→missed · self→caught · 그 외→external. 추정치는 표에 `(추정)` 로 표기한다.
    """
    out = {
        "n": 0,
        "by_month": collections.Counter(),
        "detector": collections.Counter(),
        "stage": collections.Counter(),
        "status": collections.Counter(),
        "gap_type": collections.Counter(),
        "verdict": collections.Counter(),
        "verdict_estimated": 0,
    }
    for path in sorted(glob.glob(os.path.join(findings_dir, "F-*.md"))):
        meta = _read_frontmatter(path)
        if meta is None:
            continue
        day = meta.get("date")
        stamp = parse_day(day) if re.match(r"^\d{4}-\d{2}-\d{2}$", str(day or "")) else None
        if stamp is not None and (stamp < since or stamp >= until):
            continue
        out["n"] += 1
        if stamp is not None:
            out["by_month"][str(day)[:7]] += 1
        else:
            out["by_month"]["(date 없음)"] += 1
        detector = str(meta.get("detector") or "-").split()[0] if meta.get("detector") else "-"
        detector = detector.rstrip(",")
        out["detector"][detector] += 1
        for stage in _as_list(meta.get("stage")):
            out["stage"][stage] += 1
        out["status"][str(meta.get("status") or "-")] += 1
        out["gap_type"][str(meta.get("gap_type") or "-")] += 1
        verdict = meta.get("harness_verdict")
        if verdict:
            out["verdict"][str(verdict)] += 1
        else:
            out["verdict_estimated"] += 1
            if detector == "user":
                out["verdict"]["missed(추정)"] += 1
            elif detector == "self":
                out["verdict"]["caught(추정)"] += 1
            else:
                out["verdict"]["external(추정)"] += 1
    return out


def _as_list(value):
    if value is None:
        return []
    text = str(value).strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    return [part.strip().strip("'\"") for part in text.split(",") if part.strip()]


def _read_frontmatter(path):
    try:
        handle = open(path, "r", errors="replace")
    except OSError:
        return None
    meta = {}
    with handle:
        first = handle.readline()
        if first.strip() != "---":
            return None
        for line in handle:
            if line.strip() == "---":
                break
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line.rstrip("\n"))
            if match:
                meta[match.group(1)] = match.group(2).strip().strip('"')
    return meta


# ── 4. 정적 부하 (measure_constraint_load.py 표1 파싱) ───────────────────────
RE_LOAD_ROW = re.compile(r"^([A-Za-z][\w-]*)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)%\s*$")


def parse_constraint_table(text):
    """표1 행: `skill  refs  floor~tok  ceil~tok  floor%`. 열 폭 고정이 아니라 공백 분해."""
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


def collect_static_load(plugin_root):
    """실패는 `n/a` 로 흘린다 — 플러그인이 없는 머신에서도 리포트는 나와야 한다."""
    script = os.path.join(plugin_root, "scripts", "measure_constraint_load.py")
    if not os.path.isfile(script):
        return {}, "measure_constraint_load.py 없음: " + script
    try:
        proc = subprocess.run(
            [sys.executable, script, plugin_root],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180,
        )
    except Exception as exc:  # noqa: BLE001 — 리포트가 도구 실패로 죽으면 안 된다
        return {}, "실행 실패: %s" % exc
    text = proc.stdout.decode("utf-8", "replace")
    rows = parse_constraint_table(text)
    if not rows:
        return {}, "표1 파싱 0행 (exit %d) — ⛔ 측정 실패 의심" % proc.returncode
    return rows, None


def read_last_snapshot(telemetry_dir):
    """snapshots.tsv 직전 행(dict). 없으면 None."""
    path = os.path.join(telemetry_dir, "snapshots.tsv")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", errors="replace") as handle:
            lines = [ln.rstrip("\n") for ln in handle if ln.strip()]
    except OSError:
        return None
    if len(lines) < 2:
        return None
    header = lines[0].split("\t")
    return dict(zip(header, lines[-1].split("\t")))


# ── 5. 렌더링 ───────────────────────────────────────────────────────────────
def build_payload(args, agg, wf_rows, unknown, findings, static_rows, static_err, last_snapshot):
    models = []
    for key in sorted(agg.by_model, key=lambda k: -agg.by_model[k]["out"]):
        counter = agg.by_model[key]
        lat_sorted = sorted(agg.lat[key])
        ctx_sorted = sorted(agg.ctx[key])
        costs = sorted(agg.cost_per_call[key])
        models.append(
            {
                "model": key[0],
                "side": key[1],
                "msgs": counter["msgs"],
                "input": counter["in"],
                "cache_write": counter["cache_w"],
                "cache_read": counter["cache_r"],
                "output": counter["out"],
                "thinking": counter["think"],
                "thinking_pct": round(100.0 * counter["think"] / counter["out"], 1) if counter["out"] else None,
                "cost_total_usd": round(counter["cost_micro"] / 1e6, 2) if counter["cost_micro"] else None,
                "cost_median_usd": round(med(costs), 4) if costs else None,
                "latency_median_s": round(med(lat_sorted), 1) if lat_sorted else None,
                "latency_p90_s": round(pct(lat_sorted, 0.9), 1) if lat_sorted else None,
                "latency_n": len(lat_sorted),
                "ctx_median": int(med(ctx_sorted)) if ctx_sorted else None,
                "ctx_p90": int(pct(ctx_sorted, 0.9)) if ctx_sorted else None,
            }
        )

    skills = []
    for name in sorted(agg.by_skill, key=lambda s: -agg.by_skill[s]["msgs"]):
        counter = agg.by_skill[name]
        lat_sorted = sorted(agg.skill_lat[name])
        skills.append(
            {
                "skill": name,
                "msgs": counter["msgs"],
                "output": counter["out"],
                "thinking_pct": round(100.0 * counter["think"] / counter["out"], 1) if counter["out"] else None,
                "cache_read": counter["cache_r"],
                "cache_write": counter["cache_w"],
                "latency_median_s": round(med(lat_sorted), 1) if lat_sorted else None,
                "latency_p90_s": round(pct(lat_sorted, 0.9), 1) if lat_sorted else None,
                "worker_pct": round(100.0 * counter["worker_msgs"] / counter["msgs"], 1) if counter["msgs"] else None,
                "effort": dict(agg.skill_effort[name]),
            }
        )

    workflows = []
    names = set(wf_rows) | set(agg.wf_calls)
    for name in sorted(names, key=lambda n: (-agg.wf_calls.get(n, 0), -wf_rows.get(n, {}).get("runs", 0), n)):
        row = wf_rows.get(name, {})
        walls = sorted(row.get("walls", []))
        workflows.append(
            {
                "workflow": name,
                "calls_transcript": agg.wf_calls.get(name, 0),
                "journal_runs": row.get("runs", 0),
                "wall_median_min": round(med(walls) / 60.0, 1) if walls else None,
                "wall_n": len(walls),
                "results": row.get("results", 0),
                "stages": dict(row.get("stages", {})),
                "stage_verdicts": {k: dict(v) for k, v in sorted(row.get("stage_verdicts", {}).items())},
                "issues": row.get("issues", 0),
                "overturn": row.get("overturn", 0),
                "uphold": row.get("uphold", 0),
                "adjust": row.get("adjust", 0),
                "adjustments": row.get("adjustments", 0),
                "additions": row.get("additions", 0),
            }
        )

    static = []
    for skill in sorted(static_rows):
        entry = dict(static_rows[skill])
        entry["skill"] = skill
        entry["delta_pct"] = None
        if last_snapshot:
            previous = last_snapshot.get("floor_" + skill)
            if previous and previous.isdigit() and int(previous) > 0:
                entry["delta_pct"] = round(100.0 * (entry["floor"] - int(previous)) / int(previous), 1)
        static.append(entry)

    return {
        "window": {"since": args.since, "until": args.until, "until_exclusive": args.until_exclusive},
        "denominators": {
            "transcript_files": agg.n_files,
            "transcript_files_with_messages": agg.n_files_with_msgs,
            "assistant_messages": agg.n_msgs,
            "journal_runs": sum(r.get("runs", 0) for r in wf_rows.values()),
            "journal_results": sum(r.get("results", 0) for r in wf_rows.values()),
            "findings": findings["n"],
        },
        "models": models,
        "skills": skills,
        "workflows": workflows,
        "effort_all": dict(agg.effort_all),
        "findings": {
            "n": findings["n"],
            "by_month": dict(findings["by_month"]),
            "detector": dict(findings["detector"]),
            "stage": dict(findings["stage"]),
            "status": dict(findings["status"]),
            "gap_type": dict(findings["gap_type"]),
            "harness_verdict": dict(findings["verdict"]),
            "harness_verdict_estimated": findings["verdict_estimated"],
        },
        "static_load": static,
        "static_load_error": static_err,
        "unknown_result_shapes": [
            {"keys": list(keys), "n": count} for keys, count in sorted(unknown.items(), key=lambda kv: -kv[1])
        ],
        "snapshot_baseline": last_snapshot.get("date") if last_snapshot else None,
    }


def render_markdown(payload):
    lines = []
    win = payload["window"]
    lines.append("# fz 하네스 계측 리포트 — %s ~ %s" % (win["since"], win["until"]))
    lines.append("")
    lines.append(
        "집계 대상: 트랜스크립트 %d파일(메시지 있는 파일 %d) · assistant 메시지 %d건 · "
        "워크플로 journal %d실행 · findings %d건."
        % (
            payload["denominators"]["transcript_files"],
            payload["denominators"]["transcript_files_with_messages"],
            payload["denominators"]["assistant_messages"],
            payload["denominators"]["journal_runs"],
            payload["denominators"]["findings"],
        )
    )
    lines.append(
        "기간 경계는 `%s 00:00Z` 이상 `%s 00:00Z` 미만(UTC)이다 — `--until` 은 그날을 포함한다."
        % (win["since"], win["until_exclusive"])
    )
    lines.append("")

    lines.append("## 1. 모델·역할별 비용과 지연")
    lines.append("")
    lines.append("| 모델·역할 | 호출 | 호출당 비용 중앙값 | 총비용 | 지연 중앙값 | 지연 p90 | 컨텍스트 중앙값 | thinking |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for row in payload["models"]:
        lines.append(
            "| %s %s | %s | %s | %s | %s | %s | %s | %s |"
            % (
                row["model"],
                row["side"],
                "{:,}".format(row["msgs"]),
                ("$" + fmt(row["cost_median_usd"], 3)) if row["cost_median_usd"] is not None else "n/a",
                ("$" + "{:,.0f}".format(row["cost_total_usd"])) if row["cost_total_usd"] is not None else "n/a",
                (fmt(row["latency_median_s"]) + "s") if row["latency_median_s"] is not None else "n/a",
                (fmt(row["latency_p90_s"]) + "s") if row["latency_p90_s"] is not None else "n/a",
                ("{:,}K".format(row["ctx_median"] // 1000)) if row["ctx_median"] is not None else "n/a",
                (fmt(row["thinking_pct"], 0) + "%") if row["thinking_pct"] is not None else "n/a",
            )
        )
    lines.append("")
    lines.append(
        "> 비용은 공식 단가 × usage **계산치이며 실청구가 아니다**. 캐시 쓰기는 1h TTL 단가 고정 가정. "
        "지연은 직전 user 엔트리와의 timestamp 차분(30분 초과 절단)이라 도구 실행 시간을 포함하지 않는다."
    )
    lines.append("")

    lines.append("## 2. 스킬별 부하")
    lines.append("")
    lines.append("| 스킬 | 호출 | 출력 tok | thinking% | 캐시읽기 tok | 지연 중앙값 | 지연 p90 | 워커 비율 | effort 분포 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for row in payload["skills"]:
        effort = " · ".join("%s:%d" % (k, v) for k, v in sorted(row["effort"].items(), key=lambda kv: -kv[1]))
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %s | %s | %s |"
            % (
                row["skill"],
                "{:,}".format(row["msgs"]),
                "{:,}".format(row["output"]),
                (fmt(row["thinking_pct"], 0) + "%") if row["thinking_pct"] is not None else "n/a",
                "{:,}".format(row["cache_read"]),
                (fmt(row["latency_median_s"]) + "s") if row["latency_median_s"] is not None else "n/a",
                (fmt(row["latency_p90_s"]) + "s") if row["latency_p90_s"] is not None else "n/a",
                (fmt(row["worker_pct"], 0) + "%") if row["worker_pct"] is not None else "n/a",
                effort or "-",
            )
        )
    lines.append("")

    lines.append("## 3. 워크플로별 실행과 스테이지 기여도")
    lines.append("")
    lines.append("| 워크플로 | 호출(트랜스크립트) | journal 실행 | wall-time 중앙값 [근사] | result | issues | overturn | uphold | adjust | additions |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for row in payload["workflows"]:
        lines.append(
            "| %s | %d | %d | %s | %d | %d | %d | %d | %d | %d |"
            % (
                row["workflow"],
                row["calls_transcript"],
                row["journal_runs"],
                (fmt(row["wall_median_min"]) + "분 (n=%d)" % row["wall_n"]) if row["wall_median_min"] is not None else "n/a",
                row["results"],
                row["issues"],
                row["overturn"],
                row["uphold"],
                row["adjust"],
                row["additions"],
            )
        )
    lines.append("")
    lines.append(
        "> 호출 수는 트랜스크립트의 `Workflow` tool_use 이고, 나머지는 journal 이다. wall-time 은 "
        "`agent-*.jsonl` mtime 최소~최대 차분이라 근사다. 스테이지 카운트는 **뒤집음 판정이 아니라 카운트**다 — "
        "`overturn`(refuted=true·refute·false_positive) 은 검증 스테이지가 낸 **판정 건수**이지 그 판정이 옳았다는 뜻이 아니다. overturn 이 0 에 수렴하는 스테이지가 제거 A/B 후보다(`guides/skill-testing.md §8.2`)."
    )
    lines.append("")
    lines.append("### 3b. 스테이지별 판정 (제거 후보 판정의 분모)")
    lines.append("")
    lines.append("| 워크플로 | 스테이지 | result | overturn | uphold | adjust |")
    lines.append("|---|---|---|---|---|---|")
    for row in payload["workflows"]:
        for stage, sv in sorted((row.get("stage_verdicts") or {}).items()):
            lines.append("| %s | %s | %d | %d | %d | %d |" % (
                row["workflow"], stage, row["stages"].get(stage, 0), sv["overturn"], sv["uphold"], sv["adjust"]))
    lines.append("")

    lines.append("## 4. fz-findings")
    lines.append("")
    findings = payload["findings"]
    lines.append("월별 건수: " + (" · ".join("%s %d" % kv for kv in sorted(findings["by_month"].items())) or "0건"))
    lines.append("")
    lines.append("| 축 | 분포 |")
    lines.append("|---|---|")
    for label, key in (("detector", "detector"), ("stage", "stage"), ("status", "status"), ("gap_type", "gap_type"), ("harness_verdict", "harness_verdict")):
        dist = findings[key]
        lines.append("| %s | %s |" % (label, " · ".join("%s %d" % kv for kv in sorted(dist.items(), key=lambda kv: -kv[1])) or "-"))
    lines.append("")
    lines.append(
        "> `harness_verdict` 는 frontmatter 에 있으면 그대로 쓰고, 없으면 detector 로 추정한다"
        "(user→missed · self→caught · 그 외→external). 추정 %d건." % findings["harness_verdict_estimated"]
    )
    lines.append("")

    lines.append("## 5. 정적 부하 (floor / ceiling)")
    lines.append("")
    if payload["static_load_error"]:
        lines.append("`n/a` — %s" % payload["static_load_error"])
    else:
        baseline = payload["snapshot_baseline"]
        lines.append("| 스킬 | refs | floor~tok | ceil~tok | floor% | 직전 스냅샷 대비 |")
        lines.append("|---|---|---|---|---|---|")
        for row in sorted(payload["static_load"], key=lambda r: -r["floor"]):
            delta = "n/a"
            if row["delta_pct"] is not None:
                delta = ("%+.1f%%" % row["delta_pct"]) + (" ⚠️" if row["delta_pct"] >= 10 else "")
            lines.append(
                "| %s | %d | %s | %s | %d%% | %s |"
                % (row["skill"], row["refs"], "{:,}".format(row["floor"]), "{:,}".format(row["ceil"]), row["floor_pct"], delta)
            )
        lines.append("")
        lines.append("> 직전 스냅샷 기준일: %s" % (baseline or "없음 (snapshots.tsv 미생성)"))
    lines.append("")

    lines.append("## 6. 부록 — 분모와 미해결 형태")
    lines.append("")
    lines.append("| 분모 | 값 |")
    lines.append("|---|---|")
    warn = []
    for label, key in (
        ("트랜스크립트 파일", "transcript_files"),
        ("메시지 있는 파일", "transcript_files_with_messages"),
        ("assistant 메시지", "assistant_messages"),
        ("워크플로 journal 실행", "journal_runs"),
        ("journal result 줄", "journal_results"),
        ("fz-findings 항목", "findings"),
    ):
        value = payload["denominators"][key]
        mark = ""
        if value == 0:
            mark = " ⛔ 0건 — 측정 실패를 먼저 의심하라 (경로·기간·권한)"
            warn.append(label)
        lines.append("| %s | %s%s |" % (label, "{:,}".format(value), mark))
    lines.append("")
    if warn:
        lines.append("⛔ 0건 분모: %s — 이 값들이 0인 리포트는 '부하 없음'이 아니라 **측정 실패**일 수 있다." % ", ".join(warn))
        lines.append("")
    lines.append("전체 effort 분포: " + (" · ".join("%s:%d" % kv for kv in sorted(payload["effort_all"].items(), key=lambda kv: -kv[1])) or "-"))
    lines.append("")
    lines.append("미매치 result 키 집합 (`unknown_result_shapes` — 다음 어댑터 확장 입력):")
    lines.append("")
    if payload["unknown_result_shapes"]:
        for entry in payload["unknown_result_shapes"]:
            lines.append("- `%s` — %d건" % (", ".join(entry["keys"]), entry["n"]))
    else:
        lines.append("- 없음")
    lines.append("")
    return "\n".join(lines) + "\n"


# ── 6. 실행 ─────────────────────────────────────────────────────────────────
def run_report(args):
    since = parse_day(args.since)
    until_incl = parse_day(args.until)
    until = until_incl + datetime.timedelta(days=1)  # `--until` 은 그날을 포함한다
    args.until_exclusive = until.strftime("%Y-%m-%d")

    agg = collect_transcripts(os.path.expanduser(args.projects_root), since, until)
    wf_rows, unknown = collect_journals(os.path.expanduser(args.projects_root), since, until, agg.wf_id_to_name)
    findings = collect_findings(os.path.expanduser(args.findings_dir), since, until)
    static_rows, static_err = collect_static_load(os.path.expanduser(args.plugin_root))
    telemetry_dir = os.path.expanduser(args.telemetry_dir)
    last_snapshot = read_last_snapshot(telemetry_dir)

    payload = build_payload(args, agg, wf_rows, unknown, findings, static_rows, static_err, last_snapshot)

    if args.out:
        out_path = os.path.expanduser(args.out)
    else:
        out_path = os.path.join(telemetry_dir, "reports", args.until + (".json" if args.json else ".md"))
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n" if args.json else render_markdown(payload)
    with open(out_path, "w") as handle:
        handle.write(text)
    print("리포트: %s (%d bytes)" % (out_path, len(text.encode("utf-8"))))
    return 0


# ── 7. self-test ────────────────────────────────────────────────────────────
SELFTEST_ASSISTANT = {
    "type": "assistant",
    "timestamp": "2026-08-01T00:00:20Z",
    "effort": "xhigh",
    "attributionSkill": "fz:fz-code",
    "isSidechain": False,
    "message": {
        "id": "msg_1",
        "model": "claude-opus-5",
        "usage": {
            "input_tokens": 1000,
            "cache_creation_input_tokens": 2000,
            "cache_read_input_tokens": 400000,
            "output_tokens": 4000,
            "output_tokens_details": {"thinking_tokens": 1000},
        },
        "content": [{"type": "tool_use", "id": "toolu_1", "name": "Workflow", "input": {"scriptPath": "/x/code-pair.js"}}],
    },
}


def _write_selftest_tree(base):
    projects = os.path.join(base, "projects", "-proj")
    session = os.path.join(projects, "sess")
    os.makedirs(os.path.join(session, "subagents", "workflows", "wf_aaaaaaaa-bbb"), exist_ok=True)
    entries = [
        {"type": "user", "timestamp": "2026-08-01T00:00:00Z", "message": {"content": "hi"}},
        SELFTEST_ASSISTANT,
        {
            "type": "user",
            "timestamp": "2026-08-01T00:00:30Z",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "content": "Workflow launched.\nTranscript dir: %s/subagents/workflows/wf_aaaaaaaa-bbb\nScript file: /x/code-pair.js\n" % session,
                    }
                ]
            },
        },
        {  # 같은 message.id 의 두 번째 줄 — usage 는 1회만, tool_use 블록도 1회만 센다
            "type": "assistant",
            "timestamp": "2026-08-01T00:00:40Z",
            "message": SELFTEST_ASSISTANT["message"],
        },
        {  # 같은 message.id 인데 **다른** tool_use 블록 — ⛔ 이건 세야 한다
            "type": "assistant",
            "timestamp": "2026-08-01T00:00:45Z",
            "message": {
                "id": "msg_1",
                "model": "claude-opus-5",
                "usage": SELFTEST_ASSISTANT["message"]["usage"],
                "content": [{"type": "tool_use", "id": "toolu_2", "name": "Workflow", "input": {"scriptPath": "/x/peer-review.js"}}],
            },
        },
        {  # 기간 밖
            "type": "assistant",
            "timestamp": "2026-06-01T00:00:00Z",
            "message": {"id": "msg_old", "model": "claude-opus-5", "usage": {"output_tokens": 9999}},
        },
        {  # 합성 행 — 표에서 제외
            "type": "assistant",
            "timestamp": "2026-08-01T00:01:00Z",
            "message": {"id": "msg_syn", "model": "<synthetic>", "usage": {"output_tokens": 5}},
        },
    ]
    with open(os.path.join(projects, "sess.jsonl"), "w") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")

    wf_dir = os.path.join(session, "subagents", "workflows", "wf_aaaaaaaa-bbb")
    with open(os.path.join(wf_dir, "journal.jsonl"), "w") as handle:
        handle.write(json.dumps({"type": "started", "key": "k", "agentId": "a1"}) + "\n")
        handle.write(json.dumps({"type": "result", "key": "k", "agentId": "a1", "result": {"issues": [1, 2], "overall_assessment": "x", "strengths": []}}) + "\n")
        handle.write(json.dumps({"type": "result", "key": "k2", "agentId": "a2", "result": {"finding_id": "F1", "refuted": True, "reason": "r"}}) + "\n")
        handle.write(json.dumps({"type": "result", "key": "k3", "agentId": "a3", "result": {"adjustments": [{"id": "A1", "verdict": "adjust"}, {"id": "A2", "verdict": "agree"}], "additions": [1, 2]}}) + "\n")
        # peer-review counter 형태 — 판정이 challenges[] 안에 중첩된다(최상위 refuted 없음)
        handle.write(json.dumps({"type": "result", "key": "k5", "agentId": "a5", "result": {"challenges": [{"target": "A1", "verdict": "refute", "note": ""}, {"target": "A2", "verdict": "uphold", "note": ""}], "missedIssues": []}}) + "\n")
        handle.write(json.dumps({"type": "result", "key": "k4", "agentId": "a4", "result": {"zzz": 1, "yyy": 2}}) + "\n")
    for name in ("agent-a1.jsonl", "agent-a2.jsonl"):
        with open(os.path.join(wf_dir, name), "w") as handle:
            handle.write("{}\n")
    os.utime(os.path.join(wf_dir, "agent-a1.jsonl"), (1785000000, 1785000000))
    os.utime(os.path.join(wf_dir, "agent-a2.jsonl"), (1785000600, 1785000600))
    stamp = parse_day("2026-08-01").timestamp() + 3600
    os.utime(os.path.join(wf_dir, "journal.jsonl"), (stamp, stamp))

    findings_dir = os.path.join(base, "findings")
    os.makedirs(findings_dir, exist_ok=True)
    with open(os.path.join(findings_dir, "F-001-x.md"), "w") as handle:
        handle.write("---\nid: F-001\ndate: 2026-08-12\nstatus: open\nstage: [discover, plan]\ngap_type: scope-gap\ndetector: user\n---\n\n# F-001\n")
    with open(os.path.join(findings_dir, "F-002-y.md"), "w") as handle:
        handle.write("---\nid: F-002\ndate: 2026-08-13\nstatus: open\nstage: [review]\ngap_type: not-fired\ndetector: gpt 교차검증\nharness_verdict: caught\n---\n\n# F-002\n")
    return os.path.join(base, "projects"), findings_dir


def self_test():
    checks = []

    def check(name, got, want):
        checks.append((name, got == want, got, want))

    check("표1 파싱", parse_constraint_table("■ 표1: x\nskill refs floor ceil pct\n---\nfz-review 25 57105 63440 90%\ncode-auditor 1 0 0 0%\n\n■ 표2\nnope 1 2 3 4%\n"),
          {"fz-review": {"refs": 25, "floor": 57105, "ceil": 63440, "floor_pct": 90},
           "code-auditor": {"refs": 1, "floor": 0, "ceil": 0, "floor_pct": 0}})
    check("스테이지 review1", classify_result({"issues": [], "overall_assessment": "", "strengths": []})[0], "review1")
    check("스테이지 counter", classify_result({"finding_id": "F", "refuted": False, "reason": "", "corrected_line": 1})[0], "counter")
    check("스테이지 cross", classify_result({"adjustments": [], "additions": []})[0], "cross")
    check("스테이지 changeset", classify_result({"files": [], "summary": "", "buildExpectation": ""})[0], "changeset")
    check("스테이지 verify", classify_result({"issues": [], "verdict": "ok"})[0], "verify")
    check("스테이지 other", classify_result({"zzz": 1})[0], "other")
    check("이름 정규화 scriptPath", norm_wf_name("/a/b/code-pair.js"), "code-pair")
    check("이름 정규화 인라인", norm_wf_name("fz-gap-audit-4axes-wf_beb7ee07-261.js"), "fz-gap-audit-4axes")
    check("단가 접두 일치", price_for("claude-opus-5-20260801"), PRICES["claude-opus-5"])
    check("단가 미등록", price_for("claude-unknown-9"), None)
    check("Fable 5.1 캐시읽기 단가", PRICES["claude-fable-5-1"][2], 0.25)

    base = tempfile.mkdtemp(prefix="fz-telemetry-selftest-")
    projects_root, findings_dir = _write_selftest_tree(base)
    args = argparse.Namespace(
        since="2026-07-24",
        until="2026-09-06",
        until_exclusive="2026-09-07",
        projects_root=projects_root,
        findings_dir=findings_dir,
        plugin_root=os.path.join(base, "no-such-plugin"),
        telemetry_dir=os.path.join(base, "telemetry"),
        out=os.path.join(base, "telemetry", "reports", "out.md"),
        json=False,
    )
    rc = run_report(args)
    check("run_report exit", rc, 0)

    since = parse_day(args.since)
    until = parse_day(args.until) + datetime.timedelta(days=1)
    agg = collect_transcripts(projects_root, since, until)
    check("dedup+기간+합성 제외 후 메시지 1건", agg.n_msgs, 1)
    check("워크플로 호출 — 같은 블록 id 반복은 1건", agg.wf_calls.get("code-pair"), 1)
    check("워크플로 호출 — 같은 message.id 의 다른 블록도 센다", agg.wf_calls.get("peer-review"), 1)
    check("wf_id→이름 해석", agg.wf_id_to_name.get("wf_aaaaaaaa-bbb"), "code-pair")
    wf_rows, unknown = collect_journals(projects_root, since, until, agg.wf_id_to_name)
    check("journal 이름 join", "code-pair" in wf_rows, True)
    check("issues 합", wf_rows["code-pair"]["issues"], 2)
    check("overturn — top-level refuted + 중첩 refute", wf_rows["code-pair"]["overturn"], 2)
    check("uphold — 중첩 agree + uphold", wf_rows["code-pair"]["uphold"], 2)
    check("adjust — 중첩 adjust", wf_rows["code-pair"]["adjust"], 1)
    check("stage_verdicts — counter 스테이지 키 보존", wf_rows["code-pair"]["stage_verdicts"].get("counter", {}).get("overturn"), 2)
    check("stage_verdicts — cross 스테이지 adjust", wf_rows["code-pair"]["stage_verdicts"].get("cross", {}).get("adjust"), 1)
    check("adjustments", wf_rows["code-pair"]["adjustments"], 2)
    check("count_verdicts 단위", count_verdicts({"a": [{"refuted": False}, {"verdict": "false_positive"}], "verdict": "issues"}), (1, 1, 0))
    check("additions", wf_rows["code-pair"]["additions"], 2)
    check("wall-time 10분", round(wf_rows["code-pair"]["walls"][0] / 60.0), 10)
    check("미매치 형태 1종", list(unknown), [("yyy", "zzz")])
    findings = collect_findings(findings_dir, since, until)
    check("findings 2건", findings["n"], 2)
    check("detector user", findings["detector"]["user"], 1)
    check("detector 첫 토큰만", findings["detector"]["gpt"], 1)
    check("stage 리스트 분해", findings["stage"]["discover"], 1)
    check("harness_verdict 읽기", findings["verdict"]["caught"], 1)
    check("harness_verdict 추정", findings["verdict"]["missed(추정)"], 1)
    static_rows, static_err = collect_static_load(args.plugin_root)
    check("정적 부하 n/a", static_rows == {} and static_err is not None, True)

    # --json 경로도 실제로 실행한다 — 한 번도 안 돈 직렬화는 검증된 것이 아니다.
    args_json = argparse.Namespace(**vars(args))
    args_json.json = True
    args_json.out = os.path.join(base, "telemetry", "reports", "out.json")
    check("run_report --json exit", run_report(args_json), 0)
    with open(args_json.out) as handle:
        payload = json.load(handle)
    check("JSON 왕복 — 워크플로 항목", payload["workflows"][0]["workflow"], "code-pair")
    check("JSON 왕복 — 미매치 형태", payload["unknown_result_shapes"][0]["keys"], ["yyy", "zzz"])
    check("JSON 왕복 — 분모", payload["denominators"]["assistant_messages"], 1)

    with open(args.out) as handle:
        text = handle.read()
    check("리포트에 §3 표 존재", "## 3. 워크플로별 실행과 스테이지 기여도" in text, True)
    check("리포트에 0건 경고 문구 없음(분모>0)", "측정 실패를 먼저 의심하라" in text, False)
    check("모델에게 지시하는 문장 0", ("반드시 " in text) or ("하라." in text), False)

    failed = [c for c in checks if not c[1]]
    for name, ok, got, want in checks:
        print("%s %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "  got=%r want=%r" % (got, want)))
    print("%d/%d passed" % (len(checks) - len(failed), len(checks)))
    return 1 if failed else 0


def main(argv):
    parser = argparse.ArgumentParser(description="fz 하네스 계측 집계기 (기록 없음, 집계만)")
    parser.add_argument("--since", default=None, help="YYYY-MM-DD (기본: until-30일)")
    parser.add_argument("--until", default=None, help="YYYY-MM-DD, 그날을 포함 (기본: 오늘)")
    parser.add_argument("--out", default=None, help="출력 경로 (기본: <telemetry>/reports/<until>.md)")
    parser.add_argument("--json", action="store_true", help="같은 내용을 JSON 으로")
    parser.add_argument("--projects-root", default="~/.claude/projects")
    parser.add_argument("--findings-dir", default=DEFAULT_FINDINGS_DIR)
    parser.add_argument("--plugin-root", default=DEFAULT_PLUGIN_ROOT)
    parser.add_argument(
        "--telemetry-dir",
        default=os.environ.get("FZ_TELEMETRY_DIR", DEFAULT_TELEMETRY_DIR),
        help="저장 루트 (env FZ_TELEMETRY_DIR)",
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()
    if args.until is None:
        args.until = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    if args.since is None:
        args.since = (parse_day(args.until) - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    args.until_exclusive = ""
    return run_report(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
