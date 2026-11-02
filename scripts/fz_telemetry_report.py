#!/usr/bin/env python3
"""fz_telemetry_report.py — 이미 기록된 데이터만 읽어 하네스 부하 리포트를 만드는 집계기.

⛔ 이 스크립트는 **새로 기록하지 않는다.** 입력 5종은 전부 다른 주체가 이미 쓴 것이다:
  1. 트랜스크립트 `~/.claude/projects/**/*.jsonl` — Claude Code가 쓴다
  2. 워크플로 journal `…/subagents/workflows/wf_*/journal.jsonl` — Workflow 도구가 쓴다
  3. fz-findings `entries/F-*.md` frontmatter — 사람이 쓴다
  4. `measure_constraint_load.py` 표1 — 호출 시 계산된다(정적)
  5. 실행 기록 `${FZ_RUN_STATE:-~/.fz/runs}/*/runs.jsonl` — `run_metrics.py` 가 쓴다(스킬 실행 시도 1회 = 1행 ·
     gate_issues · findings 칸은 §8 Gate 기여도 판정 = JSON `harness` — experiment-log.md §5.4 손 기록을 대신한다)
중복 소스를 만들지 않는 것이 계측의 1차 제약이다(plan §2).

한계(정직성):
  · 비용은 **공식 단가 × usage 계산치**이며 실청구가 아니다. 캐시 쓰기는 1h TTL 단가로 고정 가정.
  · 지연은 직전 `user` 엔트리와 `assistant` 엔트리의 timestamp 차분이다. 사용자 입력 대기가
    섞일 수 있어 30분 초과는 잘랐다. 도구 실행 시간은 포함하지 않는다.
  · 워크플로 wall-time은 `agent-*.jsonl` mtime 최소~최대 차분이라 근사다(`[근사]` 표기).
  · 스테이지 판별은 started 줄 라벨 → 형제 meta.json agentType → result **키 집합** 휴리스틱 순이다. 셋 다 못 가르면 `unknown` 이고 그 키 집합은 부록에 전수 열거한다.

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
    "claude-opus-5-5": (4.0, 8.0, 0.2, 20.0),  # whats-new-opus-5-5 (2026-09-25 대조) — 1h 쓰기 = 입력 ×2
    "claude-opus-5": (5.0, 10.0, 0.5, 25.0),
    "claude-sonnet-5": (2.0, 4.0, 0.2, 10.0),
    "claude-opus-4-8": (5.0, 10.0, 0.5, 25.0),
}

# ⛔ usage 가 비어 있거나 컨텍스트 0인 합성 엔트리는 표에서 뺀다 — 모델 행이 아니다.
EXCLUDED_MODELS = ("<synthetic>", "<fallback>", "?")

# ── journal result 키 집합 → 스테이지 (계약 Step 4 STAGE_SIGNATURES) ──────────
# 판정 = 필수 키 집합의 **부분집합 포함**. 앞에 놓인 것이 먼저 이긴다(구체적인 것 우선). 보고 경로에서는 classify_stage(§2b)의 (c) 폴백이다 — 라벨 · agentType 이 먼저 가른다.
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

DEFAULT_RUN_STATE = "~/.fz/runs"  # 사용자 중립 기본값 — 개인 경로는 env FZ_RUN_STATE 로 (run_metrics.py 와 같은 이름 · 같은 값)
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


_ID_SUFFIX = re.compile(r"(-\d{8})?(\[1m\])?")


def price_for(model):
    """정확 일치 → 날짜·`[1m]` 접미만 흡수. 그 외 미등록 id 는 None.

    ⛔ 최장 접두 일치로 되돌리지 말 것 — `claude-opus-5-5` 가 `claude-opus-5` 행($5/$25)에
       조용히 흡수돼 입력·출력·1h 쓰기 ×1.25, 캐시 읽기 ×2.5 로 과다 계상됐다(2026-09-25 실측).
       새 자식 모델은 None(단가 미등록)으로 드러나야 PRICES 에 행이 추가된다.
    """
    if model in PRICES:
        return PRICES[model]
    for key in sorted(PRICES, key=len, reverse=True):
        if model.startswith(key) and _ID_SUFFIX.fullmatch(model[len(key):]):
            return PRICES[key]
    return None


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
        self.unpriced = collections.Counter()  # 단가 미등록 모델 → 호출 수 (비용 표에서 빠진 몫)
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
        else:
            self.unpriced[model] += 1
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
    """result dict → (stage, 기여도 카운터). 미매치는 ('other', keys) — 서명 단계 표지다. 보고 경로는 classify_stage(§2b)가 이를 unknown 으로 바꾼다."""
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
                "stage_verdicts": {},  # stage → {overturn, uphold, adjust} — §8.2 "스테이지 X 제거 후보" 판정의 분모 (GPT 리뷰 2026-09-06)
                "issues": 0,
                "overturn": 0,   # refuted=true · verdict refute · verdict false_positive — 판정 어휘 표준화
                "uphold": 0,     # verdict uphold · agree
                "adjust": 0,     # verdict adjust
                "adjustments": 0,
                "additions": 0,
                "results": 0,
                "stage_judgments": {},  # stage → {판정 칸…, additions} — 교차·counter 만, additions 는 판정 밖 (F-462)
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
    # ⛔ result 줄에는 분류 근거가 없다 — `started` 줄이 agentId · label 을, 형제 `agent-<agentId>.meta.json` 이
    #    agentType 을 든다. result 만 읽으면 키 집합 추측만 남는다(F-462). started 는 같은 에이전트의 result 보다
    #    먼저 쓰이고, 재시도는 새 agentId 로 started 를 다시 쓴다(실표본 tests/fixtures/wf-metrics/journal-replay).
    folder = os.path.dirname(journal)
    labels_by_agent = {}
    labels_by_key = {}   # agentId 가 빠진 result 의 폴백 — key 는 재시도에도 같다
    agent_types = {}
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
            if obj.get("type") == "started":
                label = obj.get("label")
                if isinstance(label, str):
                    if isinstance(obj.get("agentId"), str):
                        labels_by_agent[obj["agentId"]] = label
                    if isinstance(obj.get("key"), str):
                        labels_by_key[obj["key"]] = label
                continue
            if obj.get("type") != "result":
                continue
            row["results"] += 1
            result = obj.get("result")
            agent_id = obj.get("agentId")
            label = labels_by_agent.get(agent_id) if isinstance(agent_id, str) else None
            if label is None and isinstance(obj.get("key"), str):
                label = labels_by_key.get(obj["key"])
            stage, unknown_keys = classify_stage(result, label, _agent_type(folder, agent_id, agent_types))
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
            judgments = count_judgments(stage, result)
            if judgments is None:
                overturn, uphold, adjust = count_verdicts(result)
            else:
                # 교차·counter 는 형태별 판정에서 합계를 낸다 — peer delta 교차는 verdict 문자열이 없어 트리 걷기로는
                # (0, 0, 0) 이고(F-462), additions 원소는 판정이 아니다. agree·uphold → uphold · false_positive·refute → overturn.
                overturn = judgments.get("false_positive", 0) + judgments.get("refute", 0)
                uphold = judgments.get("agree", 0) + judgments.get("uphold", 0)
                adjust = judgments["adjust"]
                sj = row["stage_judgments"].setdefault(stage, dict.fromkeys(JUDGMENT_FIELDS[stage] + ("additions",), 0))
                for field, value in judgments.items():
                    sj[field] += value
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
            if stage == "counter":      # counter 의 새 지적 — 판정 칸 밖 additions (F-462) · review-live missedFindings · peer-review missedIssues
                row["additions"] += sum(len(result[k]) for k in ("missedFindings", "missedIssues") if isinstance(result.get(k), list))


# ── 2b. 스테이지 판별 · 교차/counter 판정 (F-462) ─────────────────────────────
# 판별 순서: (a) started 줄 라벨 줄기 → (b) 형제 meta.json agentType → (c) STAGE_SIGNATURES → (d) unknown.
# ⛔ 키 서명만으로는 실 review-live · peer-review · plan-lean2 결과를 못 가른다(2026-11-01 실 journal 49건):
#    search 렌즈 `{findings}` · counter `{challenges, missedFindings}` · plan-lean2 결과가 other 로 샜고,
#    peer delta 교차는 cross 로 잡혀도 판정이 (0, 0, 0) 이었다.
# ⛔ 라벨은 **정확 일치**만 쓴다 — `stage1-*`→렌즈 · `stage2-*`→교차 같은 접두 규칙 금지. code-pair 는
#    stage1-impl(changeset) · stage2-review*(verify), plan-collaborative 는 stage1-draft · stage2-impact 로 같은 접두를
#    다른 뜻에 쓴다(workflows/*.js label 실측). 표에 없는 라벨은 다음 단계로 넘어간다.
# ⛔ 라벨을 바꾸면 그 결과는 unknown 이 아니라 (c) 서명 스테이지(review1 · cross)로 조용히 빠진다 —
#    tests/fixtures/telemetry/stage-class 의 label-drift 칸이 표의 라벨이 workflows/*.js 에 그대로 있는지 본다.
# ⛔ `review1` 은 라벨 없는 journal 의 Stage 1 렌즈가 (c) 에서 받는 이름이다 — 라벨이 있으면 같은 형태가 `lens` 다.
#    (c) 에서 `lens` 로 바꾸지 않는다: 그 서명이 렌즈에만 붙는지 확인되지 않았고, (c) 는 옛 journal 을 옛 이름대로
#    두는 단계다. 라벨 있는 실행과 없는 실행이 섞인 기간이면 §3 · §3b · §3c 에서 두 행으로 갈린다.
LABEL_STAGE = {
    "stage1-arch": "lens",
    "stage1-quality": "lens",
    "stage1-correctness": "lens",
    "stage1-symbolic": "lens",
    "stage1-pattern": "lens",
    "stage2-arch-on-quality": "cross",
    "stage2-quality-on-arch": "cross",
    "stage2-arch-on-peers": "cross",
    "stage2-quality-on-peers": "cross",
    "stage2-sym-on-pat": "cross",
    "stage2-pat-on-sym": "cross",
    "stage3-counter": "counter",
    "stage3-merge": "merge",
    "lean2-full": "plan-full",
    "lean2-edge": "plan-edge",
    "lean2-impact-arch": "plan-impact",
    "lean2-merge": "plan-merge",
}
# agentType 은 스크립트가 넘길 때만 `workflow-subagent` 가 아니다. 한 스테이지에만 쓰이는 것만 둔다 —
# review-arch·quality·correctness(렌즈·교차 겸용) · plan-structure · plan-edge-case · plan-impact(여러 워크플로의
# 분석·교차 겸용)는 스테이지를 정하지 못한다.
AGENT_TYPE_STAGE = {
    "fz:review-counter": "counter",
    "fz:plan-merge": "plan-merge",
}
# 교차·counter 판정 칸. additions 는 판정이 아니라 새 지적이라 칸 밖에 따로 센다.
JUDGMENT_FIELDS = {
    "cross": ("agree", "adjust", "false_positive"),
    "counter": ("uphold", "adjust", "refute"),
}
# search 교차의 동의 어휘는 `confirmed` 다(workflows/search-cross-verify.js CrossSchema verdict enum).
# ⛔ 공용 UPHOLD_WORDS 에 넣지 않는다 — count_verdicts 트리 걷기를 쓰는 다른 스테이지의 의미가 바뀐다. search 분기에서만 넓힌다.
SEARCH_UPHOLD_WORDS = UPHOLD_WORDS | {"confirmed"}
RE_AGENT_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def label_stem(label):
    """`judge:8811b9` → `judge`. 라벨이 없거나 문자열이 아니면 None."""
    if not isinstance(label, str):
        return None
    return label.split(":", 1)[0].strip() or None


def _agent_type(folder, agent_id, cache):
    """`<folder>/agent-<agentId>.meta.json` 의 agentType. 없거나 못 읽으면 None — 분류는 다음 단계로 넘어간다."""
    if not isinstance(agent_id, str) or not RE_AGENT_ID.match(agent_id):
        return None
    if agent_id not in cache:
        cache[agent_id] = None
        try:
            with open(os.path.join(folder, "agent-%s.meta.json" % agent_id), "r", errors="replace") as handle:
                meta = json.load(handle)
        except (OSError, ValueError):
            meta = None
        if isinstance(meta, dict) and isinstance(meta.get("agentType"), str):
            cache[agent_id] = meta["agentType"]
    return cache[agent_id]


def classify_stage(result, label=None, agent_type=None):
    """(stage, 미매치 키) — (a) 라벨 줄기 → (b) agentType → (c) 키 서명(`classify_result`) → (d) `unknown`.

    미매치 키는 (d) 에서만 채운다(dict 아닌 result 는 `<타입명>` 한 원소). ⛔ (d) 를 `other` 로 되돌리지 말 것 —
    `other` 는 '분류했는데 기타' 로 읽혀 분류 실패가 보이지 않는다(F-462). `classify_result` 의 'other' 는
    서명 단계 안의 미매치 표지로 남는다(tests/telemetry/stage_signatures_keys.py 가 그 값으로 판별 불가 쌍을 가른다).
    """
    stage = LABEL_STAGE.get(label_stem(label))
    if stage is None and isinstance(agent_type, str):
        stage = AGENT_TYPE_STAGE.get(agent_type)
    if stage is not None:
        return stage, None
    stage, keys = classify_result(result)
    if stage != "other":
        return stage, None
    if keys is None:
        keys = ("<%s>" % type(result).__name__,)
    return "unknown", keys


def _list_or_empty(value):
    return value if isinstance(value, list) else []


def _scalar_ids(values):
    """스칼라 id 집합 — bool · None · 컨테이너는 뺀다."""
    return {v for v in values if isinstance(v, (str, int)) and not isinstance(v, bool)}


def _vocab_counts(items, upheld, overturned, uphold_words=UPHOLD_WORDS):
    """[{verdict}] → {upheld, adjust, overturned}. 어휘 밖 값은 세지 않는다(기본 어휘는 `count_verdicts` 와 같다)."""
    out = {upheld: 0, "adjust": 0, overturned: 0}
    for item in _list_or_empty(items):
        verdict = item.get("verdict") if isinstance(item, dict) else None
        if not isinstance(verdict, str):
            continue
        if verdict in uphold_words:
            out[upheld] += 1
        elif verdict in ADJUST_WORDS:
            out["adjust"] += 1
        elif verdict in OVERTURN_WORDS:
            out[overturned] += 1
    return out


def count_judgments(stage, result):
    """교차·counter result → {판정 칸…, additions}. 다른 스테이지 · dict 아님은 None.

    교차 세 형태(2026-11-01 실 journal):
      · review-live 쌍 `adjustments[{id, newSeverity, note, verdict}]` — verdict 를 공용 어휘로 센다
      · peer-review delta `{reviewedIds, adjustments, rejections}` — verdict 문자열이 없다. 규칙은
        workflows/peer-review.js `expandCrossDelta` 와 같다: agree = reviewedIds(중복 제거) 중 adjustments ·
        rejections 의 id 에 없는 것 · adjust = len(adjustments) · false_positive = len(rejections). 차집합이라 음수가 없다.
      · search 쌍 `reviewed[{id, note, verdict}]` — 동의 어휘가 `confirmed` 다(SEARCH_UPHOLD_WORDS)
    counter: `challenges[].verdict` uphold · refute + 옛 refute 워커의 최상위 `refuted` bool.
    additions = len(additions) (+ counter 는 len(missedFindings) · peer-review 는 len(missedIssues)) — 판정 칸에 섞지 않는다.
    """
    if stage not in JUDGMENT_FIELDS or not isinstance(result, dict):
        return None
    if stage == "counter":
        out = _vocab_counts(result.get("challenges"), "uphold", "refute")
        if result.get("refuted") is True:
            out["refute"] += 1
        elif result.get("refuted") is False:
            out["uphold"] += 1
        out["additions"] = sum(len(_list_or_empty(result.get(k))) for k in ("additions", "missedFindings", "missedIssues"))
        return out
    if isinstance(result.get("reviewedIds"), list):
        adjusted, rejected = _list_or_empty(result.get("adjustments")), _list_or_empty(result.get("rejections"))
        judged = _scalar_ids(e.get("id") for e in adjusted + rejected if isinstance(e, dict))
        out = {
            "agree": len(_scalar_ids(result["reviewedIds"]) - judged),
            "adjust": len(adjusted),
            "false_positive": len(rejected),
        }
    elif isinstance(result.get("reviewed"), list):
        out = _vocab_counts(result["reviewed"], "agree", "false_positive", SEARCH_UPHOLD_WORDS)
    else:
        out = _vocab_counts(result.get("adjustments"), "agree", "false_positive")
    out["additions"] = len(_list_or_empty(result.get("additions")))
    return out


# ── 3. fz-findings frontmatter ──────────────────────────────────────────────
def collect_findings(findings_dir, since, until):
    """`---` 블록에서 date·detector·stage·status·gap_type·harness_verdict 만 읽는다.

    ⛔ harness_verdict 는 **읽기만** 한다. 없으면 detector 로 추정:
       user→missed · self→caught · 그 외→external. 추정치는 표에 `(추정)` 로 표기한다.
    """
    out = {
        "n": 0,
        "total_files": 0,
        "skipped_no_frontmatter": 0,
        "unreadable": [],        # 읽기 실패 — frontmatter 없음과 섞지 않는다(미측정)
        "by_month": collections.Counter(),
        "detector": collections.Counter(),
        "stage": collections.Counter(),
        "status": collections.Counter(),
        "gap_type": collections.Counter(),
        "verdict": collections.Counter(),
        "verdict_estimated": 0,
        "axis": collections.Counter(),
        # 대기열 스냅샷 — 기간 창과 무관하게 entries 전체(미반영 재고). 나이는 until 기준.
        "backlog": {"n": 0, "weighted": 0, "axis": collections.Counter(), "axis_age60": collections.Counter(),
                    "age": collections.Counter(), "recurs_edges": 0, "recurs_roots": collections.Counter()},
        "enumeration_error": None,
    }
    names = []
    if not findings_dir:
        # ⛔ 빈 경로를 그대로 열거하면 현재 폴더를 훑는다(옛 glob("F-*.md") 가 그랬다) — 미설정으로 밝힌다
        out["enumeration_error"] = "미설정 (--findings-dir · FZ_FINDINGS_DIR 비어 있음)"
    else:
        try:
            # ⛔ glob 금지 — 권한 오류를 예외 없이 빈 목록으로 돌려줘 '0건' 이 된다(F-271). scandir 은 던진다.
            names = sorted(e.name for e in os.scandir(findings_dir)
                           if e.name.startswith("F-") and e.name.endswith(".md"))
        except OSError as e:
            out["enumeration_error"] = "%s: %s" % (type(e).__name__, e)
    for name in names:
        path = os.path.join(findings_dir, name)
        out["total_files"] += 1
        try:
            meta = _parse_frontmatter(open(path, encoding="utf-8", errors="replace").read().splitlines(keepends=True))
        except OSError as e:
            out["unreadable"].append("%s %s" % (name, type(e).__name__))
            continue
        if meta is None:
            # ⛔ 읽지 못한 파일을 세지 않으면 분모가 조용히 줄어든다.
            out["skipped_no_frontmatter"] += 1
            continue
        day = meta.get("date")
        stamp = parse_day(day) if re.match(r"^\d{4}-\d{2}-\d{2}$", str(day or "")) else None
        axis = str(meta.get("axis") or "-")
        backlog = out["backlog"]
        backlog["n"] += 1
        bundle = str(meta.get("bundle_size") or "")
        backlog["weighted"] += int(bundle) if bundle.isdigit() else 1
        backlog["axis"][axis] += 1
        if stamp is None:
            backlog["age"]["(date 없음)"] += 1
        else:
            days = (until - stamp).days
            backlog["age"]["<30" if days < 30 else "30-59" if days < 60 else "60+"] += 1
            if days >= 60:
                backlog["axis_age60"][axis] += 1
        root = re.match(r"^\[?\s*(F-\d{3}[a-z]?)", str(meta.get("recurs_of") or ""))
        if root:
            backlog["recurs_edges"] += 1
            backlog["recurs_roots"][root.group(1)] += 1
        if stamp is not None and (stamp < since or stamp >= until):
            continue
        out["n"] += 1
        out["axis"][axis] += 1
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
    # 열거가 실패했으면 배출도 재지 않는다 — 부모 폴더 추정이 엉뚱한 APPLIED.md 를 읽는다
    root = None if out["enumeration_error"] else os.path.dirname(os.path.normpath(findings_dir))
    out["outflow"] = _collect_outflow(root, since, until)
    out["track_d"] = _collect_track_d(None if out["enumeration_error"] else findings_dir)
    return out


RE_RECUR_PHRASE = re.compile(r"(F-\d{3}[a-z]?)[^\n]{0,40}재발|재발[^\n]{0,40}(F-\d{3}[a-z]?)")


def _collect_track_d(findings_dir):
    """트랙 D 후보 — 같은 `failure_class`(README §4) 묶음의 서로 다른 `date` 수(관측일). 기간 창과 무관하다.

    관측일은 세션 수가 아니다 — 자정을 넘긴 한 세션은 2일, 같은 날 별개 세션 둘은 1일이다.
    ⛔ `recurs_of` 는 묶지 않는다(같은 축이어도 원인이 다를 수 있다) — 클래스가 다른 간선만 `related` 로 보인다.
    ⛔ 본문 '재발' 언급도 잇지 않는다 — 클래스가 다른 대상을 가리키는 엔트리 수만 `unlinked` 로 센다.
    """
    out = {"candidates": [], "related": [], "unlinked": 0, "unmeasured": []}
    if not findings_dir:
        return out
    members = {}
    arc = os.path.join(os.path.dirname(os.path.normpath(findings_dir)), ".archive")
    for folder, archived in ((findings_dir, False), (arc, True)):
        try:
            names = sorted(e.name for e in os.scandir(folder) if re.match(r"^F-\d{3}", e.name) and e.name.endswith(".md"))
        except FileNotFoundError:
            continue                       # archive 가 없는 레지스트리 — 빈 것이 맞다
        except OSError as e:
            out["unmeasured"].append("%s 열거 %s" % (os.path.basename(folder), type(e).__name__))
            continue
        for name in names:
            path = os.path.join(folder, name)
            try:                           # 한 번만 읽는다 — 못 읽은 엔트리는 frontmatter 없음과 섞지 않고 미측정으로 센다
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError as e:
                out["unmeasured"].append("%s %s" % (name, type(e).__name__))
                continue
            meta = _parse_frontmatter(text.splitlines(keepends=True))
            if meta is None:
                continue
            fid = re.match(r"^F-\d{3}[a-z]?", name).group(0)
            body = text.split("\n---\n", 1)[1] if "\n---\n" in text else ""
            day = str(meta.get("date") or "")
            root = re.match(r"^\[?\s*(F-\d{3}[a-z]?)", str(meta.get("recurs_of") or ""))
            members[fid] = {"class": str(meta.get("failure_class") or ""), "archived": archived,
                            "day": day if re.match(r"^\d{4}-\d{2}-\d{2}$", day) else None,
                            "recurs_of": root.group(1) if root else None,
                            "refs": {a or b for a, b in RE_RECUR_PHRASE.findall(body)} - {fid}}
    groups = collections.defaultdict(list)
    for fid, m in members.items():
        if m["class"]:
            groups[m["class"]].append(fid)
        cls_of = lambda other: members.get(other, {}).get("class")  # noqa: E731
        if m["recurs_of"] and cls_of(m["recurs_of"]) != m["class"]:
            out["related"].append({"id": fid, "recurs_of": m["recurs_of"]})
        if any(cls_of(ref) != m["class"] or not m["class"] for ref in m["refs"]):
            out["unlinked"] += 1
    for cls, ids in groups.items():
        days = {members[i]["day"] for i in ids if members[i]["day"]}
        if len(days) >= 2 and any(not members[i]["archived"] for i in ids):
            out["candidates"].append({"class": cls, "days": len(days), "members": [
                {"id": i, "date": members[i]["day"] or "-", "archived": members[i]["archived"]}
                for i in sorted(ids, key=lambda i: (members[i]["day"] or "", i))]})
    out["candidates"].sort(key=lambda c: (-c["days"], c["class"]))
    return out


# APPLIED 4열 행(배출 · 수동)의 넷째 칸 머리 → 처리 값. 레거시 6열 대장은 다섯째 칸(`applied` 등)을 그대로 쓴다.
OUTFLOW_KIND = (("works", "works"), ("subsumed", "subsumed"), ("rejected", "rejected"), ("applied", "applied"),
                ("릴리즈", "closes"), ("CORRECTION", "correction"))


def _collect_outflow(root, since, until):
    """배출 흐름 — `.archive/` 의 axis 분포 + APPLIED 대장 행의 처리 값 분포(전체 · 창 안).

    ⛔ 창 안 집계는 첫 칸이 날짜인 행만 센다 — 릴리즈 배출 행의 첫 칸은 버전이라 날짜를 모른다(`undated_rows` 로 따로 센다).
    도구 대 그 밖의 배출 비율은 archive 에 axis 가 있는 엔트리로만 낸다 — axis 없는 옛 배출본은 `-` 로 남긴다.
    """
    out = {"archived": 0, "axis": collections.Counter(), "kind": collections.Counter(),
           "kind_in_window": collections.Counter(), "undated_rows": 0, "error": None, "unreadable": []}
    if root is None:
        out["error"] = "미측정 (entries 열거 실패 · 미설정)"
        return out
    arc = os.path.join(root, ".archive")
    if os.path.isdir(arc):
        try:
            names = sorted(e.name for e in os.scandir(arc) if e.name.startswith("F-") and e.name.endswith(".md"))
        except OSError as e:
            out["error"] = "archive %s: %s" % (type(e).__name__, e)
            names = []
        for name in names:
            out["archived"] += 1
            try:
                meta = _parse_frontmatter(open(os.path.join(arc, name), encoding="utf-8", errors="replace")
                                          .read().splitlines(keepends=True)) or {}
            except OSError as e:
                out["unreadable"].append("archive %s %s" % (name, type(e).__name__))   # axis 를 '-' 로 지어내지 않는다
                continue
            out["axis"][str(meta.get("axis") or "-")] += 1
    applied = os.path.join(root, "APPLIED.md")
    try:
        text = open(applied, encoding="utf-8").read()
    except OSError:
        return out
    for line in text.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 6 or not re.match(r"^\*{0,2}F-\d{3}", cells[2]):
            continue
        if len(cells) == 6:              # 4열: 날짜·버전 | slug | 근거 | 처리
            kind = next((k for head, k in OUTFLOW_KIND if cells[4].startswith(head)), "other")
        else:                            # 레거시 대장: 날짜 | ID | class | 한 줄 | 처리 | 반영처
            kind = cells[5].strip("`") if len(cells) > 6 else "other"
        out["kind"][kind] += 1
        if re.match(r"^\d{4}-\d{2}-\d{2}$", cells[1]):
            if since <= parse_day(cells[1]) < until:
                out["kind_in_window"][kind] += 1
        else:
            out["undated_rows"] += 1
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
    with handle:
        return _parse_frontmatter(handle)


def _parse_frontmatter(lines):
    """줄 묶음(파일 핸들 · 리스트) → frontmatter dict. 첫 줄이 `---` 가 아니면 None."""
    lines = iter(lines)
    if next(lines, "").strip() != "---":
        return None
    meta = {}
    for line in lines:
        if line.rstrip("\n") == "---":   # 열 0 의 `---` 만 끝이다 — 위생 검사기 FM 정규식과 같은 규칙(들여쓴 `  ---` 는 끝이 아니다)
            break
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line.rstrip("\n"))
        if match:
            # ⛔ 템플릿 시절 `class: hole   # hole | miss …` 꼴 주석이 값에 섞여 있었다(2026-10-29 실측 51줄)
            value = re.sub(r"\s{2,}#\s.*$", "", match.group(2))
            meta[match.group(1)] = value.strip().strip('"')
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


# ── 4b. 실행 기록 (run_metrics.py 가 쓴 runs.jsonl) ──────────────────────────
RUN_SCHEMA = 1                                           # run_metrics.py 와 같은 이름 · 같은 값
RUN_STATUSES = ("completed", "interrupted", "failed")    # run_metrics.py 와 같은 이름 · 같은 값
RUN_OPEN_STALE_HOURS = 24.0                              # run_metrics.py sweep 기본값과 같은 이름 · 같은 값
RUN_REQUIRED = ("run_id", "attempt", "skill", "mode", "status", "started_at")
# Harness 판정(experiment-log.md §5.4 "10건 → 이슈 0건 Gate = Neutral 후보") — 실행 수 경계는
# modules/cross-validation.md § Reflection Rate threshold 의 N<10 preliminary 와 같다
HARNESS_MIN_RUNS = 10
# 행 findings 객체의 키 — run_metrics.py FINDINGS_PARTS · FINDINGS_TOTAL 과 같은 이름(§5.4 의 이름 그대로)
HARNESS_FINDINGS = ("gpt_unique_findings", "claude_unique_findings", "convergent_findings", "total_findings")


def _run_ts(value):
    """ISO 시각 → aware datetime. 시간대 없는 값은 UTC 로 읽는다 — aware 와 섞어 비교하면 TypeError 다."""
    when = parse_ts(value)
    if when is not None and when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    return when


def collect_runs(runs_root, since=None, until=None):
    """`<runs_root>/*/runs.jsonl` → {rows, unreadable, files, open, open_stale}. since/until(aware datetime)이 있으면 started_at 이 그 안인 행만.

    ⛔ 못 읽은 것은 버리지 않고 센다 — 깨진 줄 · 모르는 schema · 필수 키 없음 · started_at 판독 실패 · 열리지 않는 파일.
       unreadable 은 기간과 무관하다(기간을 판정할 수 없는 행이다).
    open 은 `<runs_root>/*/open/*.json` 표지 수다 — start 뒤 end 가 불리지 않은 시도(지금 상태 · 기간 무관)이고, open_stale 은 그중
    표지 mtime 이 RUN_OPEN_STALE_HOURS 보다 오래된 것이다. 표지는 세기만 하고 닫지 않는다(이 스크립트는 기록하지 않는다).
    """
    out = {"rows": [], "unreadable": 0, "files": 0, "open": 0, "open_stale": 0}
    for path in sorted(glob.glob(os.path.join(runs_root, "*", "runs.jsonl"))):
        out["files"] += 1
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                lines = handle.read().splitlines()
        except OSError:
            out["unreadable"] += 1
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                out["unreadable"] += 1
                continue
            if (not isinstance(row, dict) or type(row.get("schema")) is not int or row["schema"] != RUN_SCHEMA
                    or any(key not in row for key in RUN_REQUIRED)):
                out["unreadable"] += 1
                continue
            started = _run_ts(row.get("started_at"))
            if started is None:
                out["unreadable"] += 1
                continue
            if (since is not None and started < since) or (until is not None and started >= until):
                continue
            out["rows"].append(row)
    out["rows"].sort(key=lambda r: _run_ts(r.get("started_at")))
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    for marker in sorted(glob.glob(os.path.join(runs_root, "*", "open", "*.json"))):
        out["open"] += 1
        try:
            age = now - os.stat(marker).st_mtime
        except OSError:
            continue
        if age > RUN_OPEN_STALE_HOURS * 3600.0:
            out["open_stale"] += 1
    return out


def summarize_runs(collected):
    """스킬 · 모드별 실행 · 완료 · 중단 · 실패 수와 완료 행 wall 중앙값(분). 중단 행은 끝 시각을 몰라 wall 에 넣지 않는다."""
    groups = {}
    for row in collected["rows"]:
        group = groups.setdefault((str(row.get("skill")), str(row.get("mode"))),
                                  {"n": 0, "completed": 0, "interrupted": 0, "failed": 0, "walls": []})
        group["n"] += 1
        status = row.get("status")
        if status in RUN_STATUSES:
            group[status] += 1
        if status == "completed":
            start, end = _run_ts(row.get("started_at")), _run_ts(row.get("ended_at"))
            if start is not None and end is not None and end >= start:
                group["walls"].append((end - start).total_seconds() / 60.0)
    by_skill_mode = []
    for (skill, mode), group in sorted(groups.items()):
        walls = group["walls"]
        by_skill_mode.append({
            "skill": skill,
            "mode": mode,
            "n": group["n"],
            "completed": group["completed"],
            "interrupted": group["interrupted"],
            "failed": group["failed"],
            "wall_median_min": round(med(walls), 1) if walls else None,
        })
    return {"n": len(collected["rows"]), "by_skill_mode": by_skill_mode, "unreadable": collected["unreadable"],
            "open": collected["open"], "open_stale": collected["open_stale"]}


def _harness_count(value):
    return type(value) is int and value >= 0   # bool 은 type 이 int 가 아니라 걸러진다


def harness_verdict(runs, issues):
    """Gate 하나의 판정 — 실행 HARNESS_MIN_RUNS 미만은 preliminary(판정 보류) · 이상에서 이슈 0 = neutral-candidate · 이슈 있음 = load-bearing."""
    if runs < HARNESS_MIN_RUNS:
        return "preliminary"
    return "neutral-candidate" if issues == 0 else "load-bearing"


def summarize_harness(rows):
    """run_metrics.py 행의 gate_issues · findings → experiment-log.md §5.4 계약의 판정(손 기록을 대신한다).

    ⛔ Gate 의 실행 수는 그 Gate 를 적은 행 수다 — 적지 않은 행은 이슈 0 이 아니라 미기록이다. Gate 는 (스킬, 이름)으로 가른다.
    findings 합도 findings 를 적은 행만 더한다 — 그런 행이 없으면 합은 0 이 아니라 None 이다.
    형식이 깨진 칸(정수 아님 · 음수 · total 이 세 값의 합과 다름)은 malformed 로 세고 판정에 넣지 않는다.
    """
    gates = {}
    sums = dict.fromkeys(HARNESS_FINDINGS, 0)
    finding_runs = malformed = 0
    for row in rows:
        issues = row.get("gate_issues")
        if issues is not None:
            if (isinstance(issues, dict) and issues
                    and all(isinstance(gate, str) and gate and _harness_count(n) for gate, n in issues.items())):
                for gate, n in issues.items():
                    slot = gates.setdefault((str(row.get("skill")), gate), [0, 0])
                    slot[0] += 1
                    slot[1] += n
            else:
                malformed += 1
        found = row.get("findings")
        if found is not None:
            if (isinstance(found, dict) and all(_harness_count(found.get(key)) for key in HARNESS_FINDINGS)
                    and found["total_findings"] == sum(found[key] for key in HARNESS_FINDINGS[:3])):
                finding_runs += 1
                for key in HARNESS_FINDINGS:
                    sums[key] += found[key]
            else:
                malformed += 1
    by_gate = [{"skill": skill, "gate": gate, "runs": runs, "issues": issues, "verdict": harness_verdict(runs, issues)}
               for (skill, gate), (runs, issues) in sorted(gates.items())]
    findings = {"runs": finding_runs}
    findings.update((key, sums[key] if finding_runs else None) for key in HARNESS_FINDINGS)
    return {"min_runs": HARNESS_MIN_RUNS, "gates": by_gate, "findings": findings, "malformed": malformed}


def render_harness_section(harness):
    """§8 줄 목록 — harness 는 summarize_harness 결과."""
    lines = ["## 8. Gate 기여도 (Harness Metrics)", ""]
    lines.append("> `run_metrics.py end --gate-issues` 로 남긴 Gate별 이슈 수다(기간은 §7 과 같다). Gate 를 적은 행만 그 Gate 의 "
                 "실행으로 센다 — 적지 않은 행은 이슈 0 이 아니라 미기록이다. 실행 %d 미만은 preliminary(판정 보류), 그 이상에서 "
                 "이슈 0 은 neutral-candidate · 이슈가 있으면 load-bearing 이다(experiment-log.md §5.4 · "
                 "modules/cross-validation.md § Reflection Rate threshold)." % harness["min_runs"])
    lines.append("")
    lines.append("| 스킬 | Gate | 실행 | 이슈 합 | 판정 |")
    lines.append("|---|---|---|---|---|")
    for row in harness["gates"]:
        lines.append("| %s | %s | %d | %d | %s |" % (row["skill"], row["gate"].replace("|", "\\|"), row["runs"], row["issues"],
                                                   row["verdict"]))
    if not harness["gates"]:
        lines.append("| - | - | 0 | n/a | 기록 없음 |")
    lines.append("")
    found = harness["findings"]
    if found["runs"]:
        lines.append("교차 검증 발견(`--findings` 를 적은 실행 %d): gpt_unique %d · claude_unique %d · convergent %d · total %d" % (
            found["runs"], found["gpt_unique_findings"], found["claude_unique_findings"], found["convergent_findings"],
            found["total_findings"]))
    else:
        lines.append("교차 검증 발견: 기록 없음(`--findings` 를 적은 실행 0 — 발견 0 과 다르다)")
    lines.append("")
    if harness["malformed"]:
        lines.append("형식이 깨진 Harness 칸 %d — 위 표와 합에 넣지 않았다(미측정)." % harness["malformed"])
        lines.append("")
    return lines


def render_runs_section(runs):
    """§7 줄 목록 — runs 는 summarize_runs 결과."""
    lines = ["## 7. 실행 기록", ""]
    lines.append("> `run_metrics.py` 가 남긴 스킬 실행 시도 1회 = 1행이다(기간은 started_at 기준). wall 은 완료 행의 "
                 "started_at ~ ended_at 차분이고, 중단 행은 끝 시각을 몰라 wall 에 넣지 않는다.")
    lines.append("")
    lines.append("| 스킬 | 모드 | 실행 | 완료 | 중단 | 실패 | wall 중앙값 |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in runs["by_skill_mode"]:
        lines.append("| %s | %s | %d | %d | %d | %d | %s |" % (
            row["skill"], row["mode"], row["n"], row["completed"], row["interrupted"], row["failed"],
            (fmt(row["wall_median_min"]) + "분") if row["wall_median_min"] is not None else "n/a"))
    if not runs["by_skill_mode"]:
        lines.append("| - | - | 0 | 0 | 0 | 0 | n/a |")
    lines.append("")
    if runs["open"]:
        lines.append("열린 채 남은 시도 %d(그중 %d시간 넘은 것 %d) — start 뒤 end 가 불리지 않은 시도다(지금 상태 · 기간 무관). "
                     "위 표의 완료 · 중단 · 실패 어디에도 들어 있지 않다." % (runs["open"], int(RUN_OPEN_STALE_HOURS), runs["open_stale"]))
        lines.append("")
    if runs["unreadable"]:
        lines.append("읽지 못한 행 %d — 깨진 줄 · 모르는 schema · 필수 키 없는 행은 위 표에 없다(미측정)." % runs["unreadable"])
        lines.append("")
    return lines


# ── 5. 렌더링 ───────────────────────────────────────────────────────────────
def build_payload(args, agg, wf_rows, unknown, findings, static_rows, static_err, last_snapshot, runs, harness):
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
                "unpriced": price_for(key[0]) is None,
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
                "stage_judgments": {k: dict(v) for k, v in sorted(row.get("stage_judgments", {}).items())},
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
        "unpriced_models": dict(agg.unpriced),
        "skills": skills,
        "workflows": workflows,
        "effort_all": dict(agg.effort_all),
        "findings": {
            "n": findings["n"],
            "total_files": findings["total_files"],
            "skipped_no_frontmatter": findings["skipped_no_frontmatter"],
            "unreadable": findings["unreadable"],
            "by_month": dict(findings["by_month"]),
            "detector": dict(findings["detector"]),
            "stage": dict(findings["stage"]),
            "status": dict(findings["status"]),
            "gap_type": dict(findings["gap_type"]),
            "harness_verdict": dict(findings["verdict"]),
            "harness_verdict_estimated": findings["verdict_estimated"],
            "axis": dict(findings["axis"]),
            "backlog": {k: (dict(v) if isinstance(v, collections.Counter) else v) for k, v in findings["backlog"].items()},
            "outflow": {k: (dict(v) if isinstance(v, collections.Counter) else v) for k, v in findings["outflow"].items()},
            "track_d": findings["track_d"],
            "enumeration_error": findings["enumeration_error"],
        },
        "static_load": static,
        "static_load_error": static_err,
        "unknown_result_shapes": [
            {"keys": list(keys), "n": count} for keys, count in sorted(unknown.items(), key=lambda kv: -kv[1])
        ],
        "snapshot_baseline": last_snapshot.get("date") if last_snapshot else None,
        "runs": runs,
        "harness": harness,
    }


def render_markdown(payload):
    lines = []
    win = payload["window"]
    lines.append("# fz 하네스 계측 리포트 — %s ~ %s" % (win["since"], win["until"]))
    lines.append("")
    lines.append(
        "집계 대상: 트랜스크립트 %d파일(메시지 있는 파일 %d) · assistant 메시지 %d건 · "
        "워크플로 journal %d실행 · findings %d/%d건 (frontmatter 없음 %d · 읽기 실패 %d)."
        % (
            payload["denominators"]["transcript_files"],
            payload["denominators"]["transcript_files_with_messages"],
            payload["denominators"]["assistant_messages"],
            payload["denominators"]["journal_runs"],
            payload["denominators"]["findings"],
            payload["findings"]["total_files"],
            payload["findings"]["skipped_no_frontmatter"],
            len(payload["findings"]["unreadable"]),
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
    if payload.get("unpriced_models"):
        lines.append("⚠️ 단가 미등록 모델: " + " · ".join(
            "%s×%s" % (m, "{:,}".format(n)) for m, n in sorted(payload["unpriced_models"].items())
        ) + " — 비용 표에서 빠졌다(n/a). `PRICES` 에 행을 추가하라.")
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
    lines.append("### 3c. 교차·counter 판정 (additions 는 판정 밖)")
    lines.append("")
    lines.append("| 워크플로 | 스테이지 | agree·uphold | adjust | false_positive·refute | additions |")
    lines.append("|---|---|---|---|---|---|")
    for row in payload["workflows"]:
        for stage, sj in sorted((row.get("stage_judgments") or {}).items()):
            lines.append("| %s | %s | %d | %d | %d | %d |" % (
                row["workflow"], stage, sj.get("agree", sj.get("uphold", 0)), sj.get("adjust", 0),
                sj.get("false_positive", sj.get("refute", 0)), sj.get("additions", 0)))
    lines.append("")
    lines.append("> peer-review delta 교차는 verdict 문자열이 없어 agree 를 `reviewedIds` 중 adjustments · rejections 의 id 에 없는 것의 수로 낸다"
                 "(workflows/peer-review.js `expandCrossDelta` 와 같은 규칙). search 교차의 `confirmed` 는 agree 다. counter 의 additions 는 `missedFindings` 를 포함한다.")
    lines.append(">")
    lines.append("> `review1` 은 started 라벨이 없는 journal 의 Stage 1 렌즈와 같은 형태다(라벨이 있으면 `lens`). "
                 "라벨 있는 실행과 없는 실행이 섞인 기간이면 §3 · §3b · §3c 에서 두 행으로 갈린다.")
    lines.append("")

    lines.append("## 4. fz-findings")
    lines.append("")
    findings = payload["findings"]
    lines.append("월별 건수: " + (" · ".join("%s %d" % kv for kv in sorted(findings["by_month"].items())) or "0건"))
    lines.append("")
    lines.append("| 축 | 분포 |")
    lines.append("|---|---|")
    for label, key in (("detector", "detector"), ("stage", "stage"), ("status", "status"), ("gap_type", "gap_type"), ("harness_verdict", "harness_verdict"), ("axis", "axis")):
        dist = findings[key]
        lines.append("| %s | %s |" % (label, " · ".join("%s %d" % kv for kv in sorted(dist.items(), key=lambda kv: -kv[1])) or "-"))
    lines.append("")
    lines.append(
        "> `harness_verdict` 는 frontmatter 에 있으면 그대로 쓰고, 없으면 detector 로 추정한다"
        "(user→missed · self→caught · 그 외→external). 추정 %d건." % findings["harness_verdict_estimated"]
    )
    lines.append("")
    if findings.get("enumeration_error"):
        lines.append("> ⛔ entries 열거 실패 — 아래 수치는 0 이 아니라 **미측정**이다: %s" % findings["enumeration_error"])
    unread = findings["unreadable"] + findings["outflow"].get("unreadable", [])
    if unread:
        lines.append("> ⛔ 엔트리 읽기 실패 %d — 그 엔트리는 아래 분포에 없다(미측정): %s" % (len(unread), " · ".join(unread[:8])))
        lines.append("")
    backlog, outflow = findings["backlog"], findings["outflow"]
    age = backlog["age"]
    lines.append("### 대기열 스냅샷 (미반영 전체 · 기간 무관)")
    lines.append("")
    lines.append("대기 %d건(묶음 가중 %d) · 나이 " % (backlog["n"], backlog["weighted"])
                 + " · ".join("%s %d" % (k, age.get(k, 0)) for k in ("<30", "30-59", "60+", "(date 없음)")))
    lines.append("")
    lines.append("| axis | 대기 | 60일+ | 배출 |")
    lines.append("|---|---|---|---|")
    for axis in sorted(set(backlog["axis"]) | set(outflow["axis"]), key=lambda a: -backlog["axis"].get(a, 0)):
        lines.append("| %s | %d | %d | %d |" % (axis, backlog["axis"].get(axis, 0), backlog["axis_age60"].get(axis, 0),
                                              outflow["axis"].get(axis, 0)))
    lines.append("")
    roots = sorted(backlog["recurs_roots"].items(), key=lambda kv: -kv[1])
    lines.append("재발 간선(`recurs_of`) %d · 뿌리: %s" % (backlog["recurs_edges"], " · ".join("%s %d" % kv for kv in roots) or "-"))
    tool_out = outflow["axis"].get("tool", 0)
    other_out = sum(v for k, v in outflow["axis"].items() if k not in ("tool", "works", "-"))
    lines.append("배출 %d건(axis 없는 옛 배출 %d) · 도구 %d 대 그 밖 %d · works %d" % (
        outflow["archived"], outflow["axis"].get("-", 0), tool_out, other_out, outflow["axis"].get("works", 0)))
    lines.append("처리 값(APPLIED 행): " + (" · ".join("%s %d" % kv for kv in sorted(outflow["kind"].items(), key=lambda kv: -kv[1])) or "-")
                 + " — 창 안 " + (" · ".join("%s %d" % kv for kv in sorted(outflow["kind_in_window"].items())) or "0")
                 + " · 날짜 없는 릴리즈 행 %d" % outflow["undated_rows"])
    lines.append("")
    lines.append("> ⭐ 판단·절차 갈래(axis ≠ tool)가 대기에 쌓이고 배출이 tool 로만 일어나면, 릴리즈 `Closes:` 밖의 출구"
                 "(README §1 수동 배출)가 돌지 않는 것이다.")
    lines.append("")
    track = findings["track_d"]
    lines.append("### 트랙 D 후보 (같은 failure_class · 관측일 2+ · live 1+ · 기간 무관)")
    lines.append("")
    lines.append("> 관측일은 엔트리 `date` 의 서로 다른 날 수다 — 세션 수가 아니다(자정을 넘긴 한 세션은 2일 · 같은 날 별개 세션 둘은 1일)."
                 " 별개 세션은 Lead 가 엔트리의 세션 · 맥락 줄로 확인해 이 줄과 함께 인용한다.")
    lines.append("")
    if track["unmeasured"]:
        lines.append("> ⛔ 일부 미측정 — 아래 목록은 빠진 엔트리가 있을 수 있다: " + " · ".join(track["unmeasured"]))
        lines.append("")
    for cand in track["candidates"]:
        lines.append("- `%s` — 트랙 D 후보(관측일 %d · 별개 세션 미확인): %s" % (cand["class"], cand["days"], " · ".join(
            "%s %s%s" % (m["id"], m["date"], "(archive)" if m["archived"] else "") for m in cand["members"])))
    if not track["candidates"]:
        lines.append("- 없음")
    lines.append("")
    lines.append("관련(`recurs_of` · 클래스 다름 · 원인 다를 수 있음 · 세지 않음) %d: %s" % (
        len(track["related"]), " · ".join("%s → %s" % (r["id"], r["recurs_of"]) for r in track["related"]) or "-"))
    lines.append("본문 '재발' 언급 미계수 %d — 클래스가 다른 엔트리를 가리켜 잇지 않았다" % track["unlinked"])
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
    lines.append("미매치 result 키 집합 (스테이지 `unknown` · `unknown_result_shapes` — 다음 어댑터 확장 입력):")
    lines.append("")
    if payload["unknown_result_shapes"]:
        for entry in payload["unknown_result_shapes"]:
            lines.append("- `%s` — %d건" % (", ".join(entry["keys"]), entry["n"]))
    else:
        lines.append("- 없음")
    lines.append("")
    lines.extend(render_runs_section(payload["runs"]))
    lines.extend(render_harness_section(payload["harness"]))
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
    collected_runs = collect_runs(os.path.expanduser(args.runs_root), since, until)
    runs = summarize_runs(collected_runs)
    harness = summarize_harness(collected_runs["rows"])

    payload = build_payload(args, agg, wf_rows, unknown, findings, static_rows, static_err, last_snapshot, runs, harness)

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
        handle.write(json.dumps({"type": "result", "key": "k5", "agentId": "a5", "result": {"challenges": [{"target": "A1", "verdict": "refute", "note": ""}, {"target": "A2", "verdict": "uphold", "note": ""}], "missedIssues": [{"id": "CT-1"}]}}) + "\n")
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
        handle.write("---\nid: F-002\ndate: 2026-08-13\nstatus: open\nstage: [review]\ngap_type: not-fired\ndetector: gpt 교차검증\nharness_verdict: caught\n"
                     "axis: tool\nrecurs_of: F-001\nbundle_size: 3\n---\n\n# F-002\n")
    # 측정 필드(2026-10-29) — 창 밖 엔트리 1(스냅샷에만) · 주석 섞인 값 · archive 2 · APPLIED 세 형식
    with open(os.path.join(findings_dir, "F-003-z.md"), "w") as handle:
        handle.write("---\nid: F-003\ndate: 2026-06-01\nstatus: open\nclass: hole            # hole | miss\n  ---\naxis: review\n---\n\n# F-003\n")
    archive = os.path.join(base, ".archive")
    os.makedirs(archive, exist_ok=True)
    with open(os.path.join(archive, "F-090-gone.md"), "w") as handle:
        handle.write("---\nid: F-090\ndate: 2026-08-01\nstatus: open\naxis: works\n---\n\n# F-090\n")
    with open(os.path.join(archive, "F-091-old.md"), "w") as handle:
        handle.write("---\nid: F-091\ndate: 2026-07-01\nstatus: open\n---\n\n# F-091\n")
    with open(os.path.join(base, "APPLIED.md"), "w") as handle:
        handle.write("# APPLIED\n\n| 날짜 | ID | failure_class | 한 줄 | 처리 | 반영처 |\n|---|---|---|---|---|---|\n"
                     "| 2026-08-24 | F-080 | x | y | `applied` | z |\n\n"
                     "| 9.9.9 | F-091-old | `v9.9.9.md` | 릴리즈 `Closes:` 로 배출 |\n\n"
                     "| 2026-08-20 | F-090-gone | triage-x | works — 근거 |\n"
                     "| 2026-08-22 | F-092-local | main abc1234 | applied — scripts/x.py |\n")
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
    # 보고 경로 classify_stage (F-462) — 라벨 줄기 → agentType → 키 서명 → unknown
    check("라벨 줄기 — `:` 뒤 접미를 뗀다", label_stem("judge:8811b9"), "judge")
    check("라벨 렌즈가 키 서명보다 먼저", classify_stage({"issues": [], "overall_assessment": "", "strengths": []}, "stage1-arch")[0], "lens")
    check("라벨 search 렌즈 {findings}", classify_stage({"findings": []}, "stage1-symbolic")[0], "lens")
    check("라벨 search 교차 {reviewed}", classify_stage({"reviewed": [], "additions": []}, "stage2-pat-on-sym")[0], "cross")
    check("라벨 접미 붙은 정확 일치", classify_stage({"stepAmendments": []}, "lean2-merge:8811b9")[0], "plan-merge")
    check("접두 규칙 없음 — code-pair stage2-review 는 키 서명(verify)", classify_stage({"issues": [], "verdict": "ok"}, "stage2-review")[0], "verify")
    check("접두 규칙 없음 — code-pair stage1-impl 은 키 서명(changeset)",
          classify_stage({"files": [], "summary": "", "buildExpectation": ""}, "stage1-impl")[0], "changeset")
    check("agentType — 라벨이 표에 없을 때", classify_stage({"challenges": [], "missedFindings": []}, "judge:1", "fz:review-counter")[0], "counter")
    check("agentType 기본값은 단서가 아니다", classify_stage({"zzz": 1}, None, "workflow-subagent"), ("unknown", ("zzz",)))
    check("라벨 없는 옛 journal 은 키 서명", classify_stage({"adjustments": [], "additions": []})[0], "cross")
    check("미매치 = unknown + 키 집합", classify_stage({"zzz": 1}), ("unknown", ("zzz",)))
    check("dict 아님 = unknown + 타입", classify_stage("x"), ("unknown", ("<str>",)))
    check("판정 peer delta — agree 는 reviewedIds 중 판정 안 된 id",
          count_judgments("cross", {"reviewedIds": ["A", "B", "C", "D"], "adjustments": [{"id": "B"}], "rejections": [{"id": "C"}], "additions": [1]}),
          {"agree": 2, "adjust": 1, "false_positive": 1, "additions": 1})
    # workflows/peer-review.js expandCrossDelta 와 같은 값 — reviewedIds 중복 · reviewedIds 밖 판정 id(X) · 조정과 기각 양쪽의 id(B)
    check("판정 peer delta — expandCrossDelta 와 같은 agree",
          count_judgments("cross", {"reviewedIds": ["A", "A", "B"], "adjustments": [{"id": "B"}, {"id": "X"}], "rejections": [{"id": "B"}]}),
          {"agree": 1, "adjust": 2, "false_positive": 1, "additions": 0})
    check("판정 search 교차 — 동의 어휘 confirmed",
          count_judgments("cross", {"reviewed": [{"id": "S1", "verdict": "confirmed"}, {"id": "S2", "verdict": "false_positive"}], "additions": []}),
          {"agree": 1, "adjust": 0, "false_positive": 1, "additions": 0})
    check("판정 counter — missedFindings 는 additions",
          count_judgments("counter", {"challenges": [{"target": "A", "verdict": "uphold"}, {"target": "B", "verdict": "refute"}], "missedFindings": [1, 2]}),
          {"uphold": 1, "adjust": 0, "refute": 1, "additions": 2})
    check("판정 counter — peer-review missedIssues 도 additions",
          count_judgments("counter", {"challenges": [{"target": "A", "verdict": "uphold"}], "missedIssues": [1, 2, 3]}),
          {"uphold": 1, "adjust": 0, "refute": 0, "additions": 3})
    check("판정 — 교차·counter 밖 스테이지는 None", count_judgments("lens", {"issues": []}), None)
    meta_dir = tempfile.mkdtemp(prefix="fz-telemetry-meta-")
    with open(os.path.join(meta_dir, "agent-m1.meta.json"), "w") as handle:
        json.dump({"agentType": "fz:review-counter", "description": "stage3-counter"}, handle)
    check("meta.json agentType 읽기", _agent_type(meta_dir, "m1", {}), "fz:review-counter")
    check("meta.json 없음 = None", _agent_type(meta_dir, "m2", {}), None)
    check("agentId 경로 문자 거부", _agent_type(meta_dir, "../m1", {}), None)
    check("이름 정규화 scriptPath", norm_wf_name("/a/b/code-pair.js"), "code-pair")
    check("이름 정규화 인라인", norm_wf_name("fz-gap-audit-4axes-wf_beb7ee07-261.js"), "fz-gap-audit-4axes")
    check("단가 접두 일치", price_for("claude-opus-5-20260801"), PRICES["claude-opus-5"])
    check("단가 미등록", price_for("claude-unknown-9"), None)
    for mid in ("claude-opus-5-5", "claude-opus-5-5[1m]", "claude-opus-5-5-20260922", "claude-opus-5-5-20260922[1m]"):
        check("단가 Opus 5.5 " + mid, price_for(mid), (4.0, 8.0, 0.2, 20.0))
    check("단가 자식 id 는 부모로 흡수 안 함", price_for("claude-opus-5-6"), None)
    ua = TranscriptAgg()
    ua._accumulate("claude-unknown-9", "main", {}, {"input_tokens": 1, "output_tokens": 1}, None, None)
    ua._accumulate("claude-unknown-9", "main", {}, {"input_tokens": 1, "output_tokens": 1}, None, None)
    check("단가 미등록 호출 수 집계", dict(ua.unpriced), {"claude-unknown-9": 2})
    check("Fable 5.1 캐시읽기 단가", PRICES["claude-fable-5-1"][2], 0.25)

    base = tempfile.mkdtemp(prefix="fz-telemetry-selftest-")
    projects_root, findings_dir = _write_selftest_tree(base)
    runs_root = os.path.join(base, "runs")
    os.makedirs(os.path.join(runs_root, "p1", "open"), exist_ok=True)
    with open(os.path.join(runs_root, "p1", "runs.jsonl"), "w") as handle:   # 행 2 · 깨진 줄 1 · 모르는 schema 1
        handle.write(json.dumps({"schema": 1, "run_id": "r1", "attempt": 1, "skill": "fz-plan", "mode": "light", "status": "completed",
                                 "started_at": "2026-08-01T00:00:00Z", "ended_at": "2026-08-01T00:10:00Z"}) + "\n")
        handle.write(json.dumps({"schema": 1, "run_id": "r1", "attempt": 2, "skill": "fz-plan", "mode": "light", "status": "interrupted",
                                 "started_at": "2026-08-02T00:00:00Z", "ended_at": None}) + "\n")
        handle.write("{깨진 줄\n")
        handle.write(json.dumps({"schema": 99, "run_id": "r9", "attempt": 1, "skill": "fz-plan", "mode": "light", "status": "completed",
                                 "started_at": "2026-08-01T00:00:00Z"}) + "\n")
    for marker in ("aaaaaaaaaaaa.1.json", "bbbbbbbbbbbb.1.json"):   # 열린 표지 2 — bbbb 는 24시간 넘게 열린 것
        with open(os.path.join(runs_root, "p1", "open", marker), "w") as handle:
            handle.write("{}")
    stale_epoch = parse_day("2026-08-01").timestamp()
    os.utime(os.path.join(runs_root, "p1", "open", "bbbbbbbbbbbb.1.json"), (stale_epoch, stale_epoch))
    args = argparse.Namespace(
        since="2026-07-24",
        until="2026-09-06",
        until_exclusive="2026-09-07",
        projects_root=projects_root,
        findings_dir=findings_dir,
        plugin_root=os.path.join(base, "no-such-plugin"),
        telemetry_dir=os.path.join(base, "telemetry"),
        runs_root=runs_root,
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
    check("additions", wf_rows["code-pair"]["additions"], 3)   # 교차 additions 2 + peer-review counter missedIssues 1
    check("wall-time 10분", round(wf_rows["code-pair"]["walls"][0] / 60.0), 10)
    check("미매치 형태 1종", list(unknown), [("yyy", "zzz")])
    findings = collect_findings(findings_dir, since, until)
    check("findings 2건", findings["n"], 2)
    if os.geteuid() != 0:                  # root 는 권한 0 파일도 읽는다
        locked = os.path.join(findings_dir, "F-004-locked.md")
        with open(locked, "w") as handle:
            handle.write("---\nid: F-004\ndate: 2026-08-01\n---\n")
        os.chmod(locked, 0)
        try:
            locked_run = collect_findings(findings_dir, since, until)
        finally:
            os.chmod(locked, 0o644)
            os.remove(locked)
        check("읽기 실패 = 미측정(frontmatter 없음과 섞지 않는다)",
              (len(locked_run["unreadable"]), locked_run["skipped_no_frontmatter"]), (1, findings["skipped_no_frontmatter"]))
    check("detector user", findings["detector"]["user"], 1)
    check("detector 첫 토큰만", findings["detector"]["gpt"], 1)
    check("stage 리스트 분해", findings["stage"]["discover"], 1)
    check("harness_verdict 읽기", findings["verdict"]["caught"], 1)
    check("harness_verdict 추정", findings["verdict"]["missed(추정)"], 1)
    check("주석 섞인 값 정리", _read_frontmatter(os.path.join(findings_dir, "F-003-z.md"))["class"], "hole")
    check("창 안 axis", (findings["axis"]["tool"], findings["axis"]["-"]), (1, 1))
    backlog, outflow = findings["backlog"], findings["outflow"]
    check("스냅샷은 창 밖도 센다", backlog["n"], 3)
    check("묶음 가중(1+3+1)", backlog["weighted"], 5)
    check("60일+ 와 그 axis", (backlog["age"]["60+"], backlog["axis_age60"]["review"]), (1, 1))
    check("재발 간선 · 뿌리", (backlog["recurs_edges"], backlog["recurs_roots"]["F-001"]), (1, 1))
    check("archive axis(없으면 -)", (outflow["archived"], outflow["axis"]["works"], outflow["axis"]["-"]), (2, 1, 1))
    check("APPLIED 세 형식 처리 값(4열 applied 포함)", dict(outflow["kind"]), {"applied": 2, "closes": 1, "works": 1})
    check("창 안 처리 값 · 날짜 없는 행", (dict(outflow["kind_in_window"]), outflow["undated_rows"]), ({"applied": 2, "works": 1}, 1))
    unset = collect_findings("", since, until)
    check("빈 경로 = 미설정(현재 폴더를 훑지 않는다)", (unset["total_files"], unset["enumeration_error"][:3], unset["outflow"]["archived"]), (0, "미설정", 0))
    gone = collect_findings(os.path.join(base, "없는-폴더"), since, until)
    check("열거 실패 = 미측정 표시", gone["enumeration_error"] is not None and gone["outflow"]["error"] is not None, True)
    static_rows, static_err = collect_static_load(args.plugin_root)
    check("정적 부하 n/a", static_rows == {} and static_err is not None, True)
    runs = collect_runs(runs_root, since, until)
    check("실행 기록 — 읽은 행 2 · 못 읽은 행 2(깨진 줄 · schema 99)", (len(runs["rows"]), runs["unreadable"]), (2, 2))
    check("실행 기록 — 열린 표지 2 · 24시간 넘은 것 1", (runs["open"], runs["open_stale"]), (2, 1))
    check("실행 기록 — 스킬·모드 묶음 · wall 은 완료 행만", summarize_runs(runs)["by_skill_mode"],
          [{"skill": "fz-plan", "mode": "light", "n": 2, "completed": 1, "interrupted": 1, "failed": 0, "wall_median_min": 10.0}])
    late = collect_runs(runs_root, parse_day("2026-08-02"), until)
    check("실행 기록 — 기간 밖 행은 빠지고 못 읽은 행 · 열린 표지는 그대로 센다", (len(late["rows"]), late["unreadable"], late["open"]), (1, 2, 2))
    no_runs = collect_runs(os.path.join(base, "없는-runs"))
    check("실행 기록 — 루트 없음 = 0행 · 열린 표지 0", (no_runs["rows"], no_runs["open"]), ([], 0))
    # Harness 판정(experiment-log.md §5.4) — A 는 10회 이슈 0 · B 는 10회 이슈 있음 · C 는 9회(경계 바로 아래) · 다른 스킬의 같은 이름 A 는 따로
    found3 = {"gpt_unique_findings": 1, "claude_unique_findings": 2, "convergent_findings": 3, "total_findings": 6}
    h_rows = [{"skill": "fz-review", "gate_issues": dict({"A": 0, "B": i % 2}, **({"C": 0} if i < 9 else {})), "findings": found3}
              for i in range(10)]
    h_rows += [{"skill": "fz-review"},                                                            # 칸 없는 행 — 미기록
               {"skill": "fz-plan", "gate_issues": {"A": 4}},
               {"skill": "fz-review", "gate_issues": {"A": -1}},                                  # 음수
               {"skill": "fz-review", "gate_issues": {"A": True}},                                # bool
               {"skill": "fz-review", "findings": dict(found3, total_findings=7)}]                # total ≠ 합
    harness = summarize_harness(h_rows)
    check("Harness — Gate 별 실행 · 이슈 · 판정(10회 0건 · 10회 있음 · 9회 · 다른 스킬)",
          [(g["skill"], g["gate"], g["runs"], g["issues"], g["verdict"]) for g in harness["gates"]],
          [("fz-plan", "A", 1, 4, "preliminary"), ("fz-review", "A", 10, 0, "neutral-candidate"),
           ("fz-review", "B", 10, 5, "load-bearing"), ("fz-review", "C", 9, 0, "preliminary")])
    check("Harness — findings 합은 적은 행만 · 깨진 칸은 malformed", (harness["findings"], harness["malformed"]),
          ({"runs": 10, "gpt_unique_findings": 10, "claude_unique_findings": 20, "convergent_findings": 30, "total_findings": 60}, 3))
    empty_h = summarize_harness([{"skill": "fz-review"}])
    check("Harness — 기록 없음은 0 이 아니라 None", (empty_h["gates"], empty_h["findings"]),
          ([], {"runs": 0, "gpt_unique_findings": None, "claude_unique_findings": None, "convergent_findings": None, "total_findings": None}))
    check("Harness — 판정 경계(9 · 10)", [harness_verdict(9, 0), harness_verdict(10, 0), harness_verdict(10, 1)],
          ["preliminary", "neutral-candidate", "load-bearing"])

    # --json 경로도 실제로 실행한다 — 한 번도 안 돈 직렬화는 검증된 것이 아니다.
    args_json = argparse.Namespace(**vars(args))
    args_json.json = True
    args_json.out = os.path.join(base, "telemetry", "reports", "out.json")
    check("run_report --json exit", run_report(args_json), 0)
    with open(args_json.out) as handle:
        payload = json.load(handle)
    check("JSON 왕복 — 워크플로 항목", payload["workflows"][0]["workflow"], "code-pair")
    check("JSON 왕복 — 미매치 형태", payload["unknown_result_shapes"][0]["keys"], ["yyy", "zzz"])
    check("JSON 모델 행 unpriced 필드(등록 모델=False)", payload["models"][0].get("unpriced"), False)
    check("JSON unpriced_models 필드(fixture=없음)", payload.get("unpriced_models"), {})
    md = render_markdown(dict(payload, unpriced_models={"claude-unknown-9": 2}))
    check("단가 미등록 경고 줄", "단가 미등록 모델: claude-unknown-9×2" in md, True)
    check("단가 미등록 없으면 경고 줄 없음", "단가 미등록 모델" in render_markdown(payload), False)
    check("JSON 왕복 — 분모", payload["denominators"]["assistant_messages"], 1)
    check("JSON 왕복 — 실행 기록 n · unreadable · open", (payload["runs"]["n"], payload["runs"]["unreadable"], payload["runs"]["open"]), (2, 2, 2))
    check("JSON 왕복 — harness(칸 없는 실행 기록 = Gate 0 · findings None)",
          (payload["harness"]["gates"], payload["harness"]["findings"]["runs"], payload["harness"]["findings"]["total_findings"]),
          ([], 0, None))
    md_h = render_markdown(dict(payload, harness=harness))
    check("리포트 §8 — 판정 행 · 깨진 칸 줄", ("| fz-review | A | 10 | 0 | neutral-candidate |" in md_h,
                                        "형식이 깨진 Harness 칸 3" in md_h), (True, True))

    with open(args.out) as handle:
        text = handle.read()
    check("리포트에 §3 표 존재", "## 3. 워크플로별 실행과 스테이지 기여도" in text, True)
    check("리포트에 §7 실행 기록", "## 7. 실행 기록" in text, True)
    check("리포트 §7 — 열린 채 남은 시도", "열린 채 남은 시도 2(그중 24시간 넘은 것 1)" in text, True)
    check("리포트에 §8 Gate 기여도 · 기록 없음", ("## 8. Gate 기여도 (Harness Metrics)" in text, "| - | - | 0 | n/a | 기록 없음 |" in text),
          (True, True))
    check("리포트에 0건 경고 문구 없음(분모>0)", "측정 실패를 먼저 의심하라" in text, False)
    check("모델에게 지시하는 문장 0", ("반드시 " in text) or ("하라." in text), False)

    failed = [c for c in checks if not c[1]]
    for name, ok, got, want in checks:
        print("%s %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "  got=%r want=%r" % (got, want)))
    print("%d/%d passed" % (len(checks) - len(failed), len(checks)))
    return 1 if failed else 0



# ── /fz-plan Lead 구간 분리 (plan-final S9c) ───────────────────────────────
# ⛔ 왜 필요한가: 워크플로 wall 만 재면 **Lead 자체 생성 시간이 보이지 않는다.** 실측(2026-09-11):
#    45분 넘은 `/fz-plan` 3건 중 Workflow 를 쓴 건은 **0건**이었다 — 시간은 Lead 생성(29~45분)과
#    GPT 호출(11회 24분)에 있었다. 층을 나누지 않으면 어느 레버가 유효한지 판정할 수 없다.
# ⛔ 구간을 못 가르면 `unavailable` + exit 1 이다 — 0 으로 쓰지 않는다.
PLAN_DOC_RE = re.compile(r"plan-(?:v\d+|final|light)\.md")
GPT_CALL_RE = re.compile(r"codex exec|gpt-exec\.sh")
GATE_CALL_RE = re.compile(r"gpt-call\.sh")   # 정문 호출도 GPT 호출이다(R-G1 S5 · XE-19) — 위 줄은 보존 행이라 따로 둔다


def _seg_events(path):
    """한 트랜스크립트에서 (/fz-plan 시작, plan 문서 기록, GPT 호출 구간) 을 뽑는다."""
    start = None
    end = None
    doc_writes = []
    gpt_spans = []
    pending = {}
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"type"' not in line:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if not isinstance(ev, dict):
                continue
            ts = ev.get("timestamp")
            when = None
            if ts:
                try:
                    when = datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                except ValueError:
                    when = None
            msg = ev.get("message")
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if ev.get("type") == "user":
                if isinstance(content, str) and "<command-name>" in content:
                    if "/fz:fz-plan" in content:
                        if start is None and when:
                            start = when
                    elif start is not None and end is None and when:
                        end = when
                if isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_result":
                            got = pending.pop(b.get("tool_use_id"), None)
                            if got and when:
                                gpt_spans.append((got, when))
            elif ev.get("type") == "assistant" and isinstance(content, list):
                if start is None or end is not None:
                    continue
                for b in content:
                    if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                        continue
                    blob = json.dumps(b.get("input", {}), ensure_ascii=False)
                    if PLAN_DOC_RE.search(blob) and when:
                        doc_writes.append(when)
                    if (GPT_CALL_RE.search(blob) or GATE_CALL_RE.search(blob)) and when:
                        pending[b.get("id")] = when
    return start, end, doc_writes, gpt_spans


def plan_segments(projects_root, session_prefix):
    """세션의 `/fz-plan` 1회를 3구간으로 분리해 인쇄한다. 성공 시 LEAD_SEGMENTS_OK."""
    root = os.path.expanduser(projects_root)
    hits = sorted(glob.glob(os.path.join(root, "*", f"{session_prefix}*.jsonl")))
    if not hits:
        print(f"FAIL: 세션 트랜스크립트를 찾지 못했다: {session_prefix} (root={root}) — unavailable")
        return 1
    start, end, docs, gpt = _seg_events(hits[0])
    if start is None:
        print(f"FAIL: 이 세션에 /fz-plan 호출이 없다: {session_prefix} — unavailable")
        return 1
    if not docs:
        print("FAIL: plan 문서 기록(plan-v*/final/light.md)을 찾지 못해 구간을 가를 수 없다 — unavailable")
        return 1
    first_doc = min(docs)
    last_doc = max(docs)
    gpt_total = sum((b - a).total_seconds() for a, b in gpt)
    last_gpt = max((b for _, b in gpt), default=None)
    seg1 = (first_doc - start).total_seconds()
    seg3 = (last_doc - last_gpt).total_seconds() if last_gpt and last_doc > last_gpt else None
    span = ((end or last_doc) - start).total_seconds()
    print(f"/fz-plan 구간 분리 — session {session_prefix} (전체 {span / 60:.0f}분)")
    print(f"  ① Lead 초기 생성 (호출 → 첫 plan 문서): {seg1 / 60:.1f}분")
    print(f"  ② GPT 호출 대기 합 ({len(gpt)}회): {gpt_total / 60:.1f}분")
    if seg3 is None:
        print("  ③ 피드백 통합: unavailable (마지막 GPT 이후 plan 기록 없음)")
    else:
        print(f"  ③ 피드백 통합 (마지막 GPT → 마지막 plan 기록): {seg3 / 60:.1f}분")
    other = span - seg1 - gpt_total - (seg3 or 0)
    print(f"  ④ 나머지(탐색·게이트·대화): {other / 60:.1f}분")
    if len(gpt) == 0:
        print("  ⚠️ GPT 호출 0건 — ② 는 측정값이 아니라 부재다")
    print(f"LEAD_SEGMENTS_OK ({3 if seg3 is not None else 2}/3 구간 산출)")
    return 0


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
    parser.add_argument(
        "--runs-root",
        default=os.environ.get("FZ_RUN_STATE") or DEFAULT_RUN_STATE,
        help="실행 기록 루트 — run_metrics.py 가 쓰는 <루트>/<pipeline>/runs.jsonl (env FZ_RUN_STATE)",
    )
    parser.add_argument("--runs-json", action="store_true",
                        help="실행 기록 행(started_at 순 · 기간 무관)을 stdout JSON 으로 내고 끝낸다 — 다른 집계는 하지 않는다")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--plan-segments", metavar="SESSION_PREFIX",
                        help="세션의 /fz-plan 1회를 Lead 생성·GPT 대기·피드백 통합으로 분리 (plan-final S9c)")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()
    if args.runs_json:
        print(json.dumps(collect_runs(os.path.expanduser(args.runs_root))["rows"], ensure_ascii=False, indent=1))
        return 0
    if args.plan_segments:
        return plan_segments(args.projects_root, args.plan_segments)
    if args.until is None:
        args.until = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    if args.since is None:
        args.since = (parse_day(args.until) - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    args.until_exclusive = ""
    return run_report(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
