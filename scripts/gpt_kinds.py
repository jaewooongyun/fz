#!/usr/bin/env python3
"""GPT call-kind resolver — the single implementation behind scripts/gpt-call.sh.

The registry (scripts/gpt-kinds.json) says HOW each kind runs; callers say WHAT (kind + inputs). This module turns
(kind, caller inputs, caller env, caller cwd) into the exact adapter argv — scripts/gpt-exec.sh for wrapper kinds,
scripts/gpt_independent.sh for independent kinds. It never calls the GPT CLI (no --version / features probes — XE-07)
and never decides model or effort: --model / --effort given by the caller are passed through untouched (E1), anything
else is the wrapper's job (Z-02).

usage:
  gpt_kinds.py resolve --plan-dir DIR KIND [--experimental] [caller inputs...]
      Writes DIR/meta (KEY=VALUE lines), DIR/argv (NUL-separated adapter argv) and, when a prompt must be composed,
      DIR/compose.json. Pure — the gate takes the OUT lock before anything is written outside DIR.
      meta keys: ADAPTER (gpt-exec.sh | gpt_independent.sh) · LOCK (OUT for wrapper kinds, empty for independent kinds)
                 · SESSION_IN (--session-file input, kept on gate cleanup) · CODEX_HOME (adapter-only env, empty = inherit)
                 · CLEANUP_ISO (run `gpt_independent.sh cleanup --iso` after the adapter — verify-cross, E3)
                 · ERROR (message, on exit 10 / 11)
  gpt_kinds.py compose --plan-dir DIR      write the composed prompt described by DIR/compose.json
  gpt_kinds.py skill-path ROLE             Tier 1 -> 2a -> 2b role SKILL.md path for the caller's cwd / env ('' if none)
  gpt_kinds.py launcher-policy KIND [--gpt-agents] [--frame NAME]
                                           the launcher's policy for an independent kind (R-06 · SC-2): ROLE · SCHEMA ·
                                           SPAWN_LINE · FRAME as KEY=VALUE lines. The launcher asks this itself, so a gate
                                           call and a direct launcher call get the same answer and the argv stays as given
  gpt_kinds.py lint [--root DIR]           registry invariants + role-file model/effort pins (DIR = another plugin tree)
  gpt_kinds.py lint --consumers [--allowed-tools] [--root DIR] [--only FILE...]
                                           --allowed-tools: a skill that may call GPT has Bash(*/scripts/gpt-call.sh*)
                                           markdown ```bash blocks must not hand-assemble wrapper / launcher calls
  gpt_kinds.py table --write|--check [--root DIR]
                                           the generated blocks in skills/fz-gpt/SKILL.md (kind count · roles · kinds)
  gpt_kinds.py --self-test

exit: 0 ok · 10 usage (unknown kind, missing / unknown / forbidden input, experimental kind without --experimental,
      bad audit) · 11 registry or dependency failure (unreadable registry, missing schema, internal error).
      ⛔ never 1 or 2 — those mean something else elsewhere in fz (XE-02).
"""
import glob
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))   # ⛔ abspath, not realpath: a proxy root's registry copy is read
ROOT = os.path.dirname(HERE)
REGISTRY = os.path.join(HERE, "gpt-kinds.json")

FORBIDDEN_KEYS = {"model", "effort", "model_reasoning_effort", "review_model", "sandbox", "sandbox_mode", "timeout", "idle"}
# Policy flags a caller may never pass — the registry or the adapters own them (Z-04). `--x=v` forms are refused too.
FORBIDDEN_FLAGS = {"-p", "--profile", "--ignore-user-config", "--config-permissions", "-c", "--config", "--schema",
                   "--inject-skill", "--gpt-skill", "--gpt-skill-path", "--ephemeral", "--sandbox", "-s"}
VALUE_INPUTS = {"cd", "out", "prompt-file", "base", "commit", "title", "expected-branch", "session-file", "audit",
                "prompt-out", "model", "effort"}
FLAG_INPUTS = {"uncommitted"}
SCOPES = ("base", "uncommitted", "commit")
FIXED_OK = {"--uncommitted", "--ephemeral"}
LAUNCHERS = {"wrapper": ("gpt-exec.sh", ("review", "exec", "resume")), "independent": ("gpt_independent.sh", ("plan", "review"))}
DELIVERY = {None, "implicit", "inject", "path", "iso-copy"}
INDEPENDENCE = {"plain", "resumes-session", "isolated-fresh"}
SPAWN = {"inherit-audited", "forbid-prompt", "lenses-optin"}
STATUS = {"stable", "experimental"}
# The launcher's no-spawn / lens sentence comes from the kind's registry spawn value (SC-2) — the text lives here, keyed by
# that value, so the launcher holds no policy of its own. ⛔ forbid-prompt is byte-for-byte the S0 default prompt line.
SPAWN_LINES = {
    "forbid-prompt": "하위 에이전트를 만들지 않는다.",
    "lenses-optin": ("하위 에이전트는 역할 두 개만 만든다 — agent_type `fz-review-arch`(아키텍처 렌즈) · "
                     "`fz-review-quality`(품질 렌즈). 각 렌즈에 diff 와 네가 만든 규칙 레코드를 넘기고, "
                     "두 결과를 합쳐 스키마 JSON 하나로 낸다. 다른 하위 에이전트는 만들지 않는다."),
}
INDEP_KEYS = {"required", "optional", "repeatable", "flags", "experimental_only"}
CORE13 = {"review", "check", "verify", "verify-gates", "validate", "final", "adversarial", "drift", "plan", "micro-eval",
          "sprint-contract", "independent-plan", "independent-review"}


class Usage(Exception):
    """Caller error — exit 10."""


class Broken(Exception):
    """Registry / dependency error — exit 11."""


def load(path=REGISTRY):
    try:
        with open(path, encoding="utf-8") as f:
            reg = json.load(f)
    except (OSError, ValueError) as e:
        raise Broken(f"registry unreadable: {path}: {e}")
    if not isinstance(reg, dict) or not isinstance(reg.get("kinds"), dict) or not reg["kinds"]:
        raise Broken(f"registry has no kinds: {path}")
    return reg


def skill_path(role, env=None, cwd=None, root=ROOT):
    """Tier 1 -> 2a -> 2b, the same order and tests as the former get_gpt_skill_path (modules/cross-validation.md).
    Tier 1: the caller's cwd CLAUDE.md `## GPT Skills` table maps ROLE to an installed skill name.
    Tier 2a: ${CODEX_HOME:-$HOME/.codex}/skills/fz-ROLE. Tier 2b: this plugin's bundled gpt-skills/fz-ROLE.
    Returns '' when none resolves (Tier 3 — the kind's fallback_prompt applies)."""
    env = os.environ if env is None else env
    cwd = os.getcwd() if cwd is None else cwd
    sk_root = os.path.join(env.get("CODEX_HOME") or os.path.join(env.get("HOME", ""), ".codex"), "skills")
    try:
        lines = open(os.path.join(cwd, "CLAUDE.md"), encoding="utf-8", errors="replace").read().split("\n")
    except OSError:
        lines = []
    picked = []
    for i, line in enumerate(lines):            # grep -A 20 "^## GPT Skills" | grep "| ROLE " | awk -F'|' '{print $3}' | xargs
        if line.startswith("## GPT Skills"):
            for row in lines[i:i + 21]:
                if f"| {role} " in row:
                    cells = row.split("|")
                    if len(cells) > 2:
                        picked.extend(cells[2].split())
    name = " ".join(picked)
    if name and os.path.isfile(os.path.join(sk_root, name, "SKILL.md")):
        return os.path.join(sk_root, name, "SKILL.md")
    if os.path.isfile(os.path.join(sk_root, f"fz-{role}", "SKILL.md")):
        return os.path.join(sk_root, f"fz-{role}", "SKILL.md")
    bundled = os.path.join(root, "gpt-skills", f"fz-{role}", "SKILL.md")
    return bundled if os.path.isfile(bundled) else ""


def parse_inputs(tokens):
    """Caller tokens after KIND -> ({input: value}, experimental). Refuses forbidden, unknown and repeated flags."""
    got, experimental, i = {}, False, 0
    while i < len(tokens):
        t = tokens[i]
        if t == "--experimental":
            experimental, i = True, i + 1
            continue
        flag = t.split("=", 1)[0]
        if flag in FORBIDDEN_FLAGS:
            raise Usage(f"{flag} is not a caller input — the registry and the adapters own it (Z-04)")
        if "=" in t and t.startswith("--"):
            raise Usage(f"use '{flag} VALUE', not '{t}'")
        if not t.startswith("--"):
            raise Usage(f"unexpected argument: '{t}'")
        key = t[2:]
        if key in got:
            raise Usage(f"--{key} given twice")
        if key in FLAG_INPUTS:
            got[key], i = True, i + 1
        elif key in VALUE_INPUTS:
            if i + 1 >= len(tokens):
                raise Usage(f"--{key} needs a value")
            v = tokens[i + 1]
            if v == "" or "\n" in v or "\0" in v:
                raise Usage(f"--{key} value is empty or has a newline")
            got[key], i = v, i + 2
        else:
            raise Usage(f"unknown input: --{key}")
    return got, experimental


def resolve(kind, tokens, env=None, cwd=None, root=ROOT, reg=None):
    """-> plan dict {adapter, argv, lock, session_in, codex_home, cleanup_iso, compose}. Raises Usage / Broken."""
    reg = load() if reg is None else reg
    k = reg["kinds"].get(kind)
    if not isinstance(k, dict):
        raise Usage(f"unknown kind: '{kind}' (known: {', '.join(sorted(reg['kinds']))})")
    launcher = k.get("launcher")
    if launcher not in LAUNCHERS or k.get("mode") not in LAUNCHERS[launcher][1]:
        raise Broken(f"kind {kind}: bad launcher/mode {launcher}/{k.get('mode')}")
    adapter = LAUNCHERS[launcher][0]
    plan = {"adapter": adapter, "argv": [], "lock": "", "session_in": "", "codex_home": "", "cleanup_iso": "", "compose": None}

    if launcher == "independent":
        plan["argv"] = [k["mode"]] + _independent_tokens(kind, k, tokens)
        return plan

    got, experimental = parse_inputs(tokens)
    _status_gate(kind, k, experimental)
    inputs = k.get("inputs") or {}
    req, opt = list(inputs.get("required") or []), set(inputs.get("optional") or [])
    allowed = (set(req) | opt) - {"scope"}
    if "scope" in req:
        allowed |= set(SCOPES)
    for key in got:
        if key not in allowed:
            raise Usage(f"--{key} is not an input of kind {kind}")
    for r in req:
        if r == "scope":
            n = sum(1 for s in SCOPES if s in got)
            if n != 1:
                raise Usage(f"kind {kind} needs exactly one of --base / --uncommitted / --commit")
        elif r not in got:
            raise Usage(f"kind {kind} needs --{r}")
    fixed = list(k.get("fixed_args") or [])
    if any(f not in FIXED_OK for f in fixed):
        raise Broken(f"kind {kind}: fixed_args outside {sorted(FIXED_OK)}: {fixed}")

    out = got["out"]
    for key in ("out", "prompt-out"):               # a missing parent is a usage error, not "another run holds the lock"
        if key in got and not os.path.isdir(os.path.dirname(os.path.abspath(got[key]))):
            raise Usage(f"--{key} parent folder does not exist: {os.path.dirname(os.path.abspath(got[key]))}")
    plan["lock"] = out
    plan["session_in"] = got.get("session-file", "")
    role, delivery = k.get("role"), k.get("skill_delivery")
    spath = skill_path(role, env, cwd, root) if delivery in ("inject", "path") else ""
    prompt = got.get("prompt-file")
    session = got.get("session-file")

    if kind == "verify-cross" or (k["mode"] == "resume" and "audit" in got):
        audit = _read_audit(got["audit"])
        iso, session = audit.get("iso") or "", audit.get("sessionFile") or ""
        plan["cleanup_iso"] = iso
        plan["session_in"] = session       # the gate's stale cleanup keeps it — <OUT>.session may be this very file (--out reusing the planner output)
        if not session:
            raise Usage(f"audit {got['audit']} has no sessionFile — the planner run was not kept or did not pass; run verify instead")
        if not iso:
            raise Usage(f"audit {got['audit']} has no iso — the planner run was not kept (--keep-iso)")
        plan["codex_home"] = os.path.join(iso, "gpt-home")
        clash = {os.path.realpath(x) for x in (out, out + ".session", got["audit"], got["prompt-file"])}
        if os.path.realpath(got["prompt-out"]) in clash:   # the wrapper erases OUT before it reads the prompt; the rest are inputs
            raise Usage(f"--prompt-out {got['prompt-out']} is --out / --out.session / --audit / --prompt-file — the composed prompt would be erased or overwrite its input")
        parts = ([{"file": spath}, {"text": "\n"}] if spath else [{"text": k.get("fallback_prompt") or ""}]) + [{"file": prompt}]
        plan["compose"] = {"to": got["prompt-out"], "parts": parts}
        prompt = got["prompt-out"]
    elif delivery == "inject" and not spath and k.get("fallback_prompt"):
        to = out + ".fallback-prompt.txt"           # Tier 3 — bundle missing: the kind's fallback instruction goes first
        plan["compose"] = {"to": to, "parts": [{"text": k["fallback_prompt"]}, {"file": prompt}]}
        prompt = to
    if k.get("frame"):                              # experimental frame kinds: the frame goes in front of the caller's prompt
        fpath = os.path.join(root, k["frame"])
        if not os.path.isfile(fpath):
            raise Broken(f"kind {kind}: frame missing: {fpath}")
        stem = os.path.splitext(os.path.basename(k["frame"]))[0]
        if os.path.basename(os.path.dirname(os.path.abspath(out))) != stem:
            raise Usage(f"kind {kind}: --out must sit in its own '{stem}/' folder — one frame per folder, "
                        "so a run never shares a folder with a sibling frame's logs (XE-24)")
        head = [{"file": fpath}, {"text": "\n"}]
        if plan["compose"]:
            plan["compose"]["parts"] = head + plan["compose"]["parts"]
        else:
            plan["compose"] = {"to": out + ".frame-prompt.txt", "parts": head + [{"file": prompt}]}
            prompt = out + ".frame-prompt.txt"

    argv = [k["mode"], "--cd", got["cd"], "--out", out]
    for s in SCOPES:
        if s in got:
            argv += ["--uncommitted"] if s == "uncommitted" else [f"--{s}", got[s]]
    if "--uncommitted" in fixed:
        argv += ["--uncommitted"]
    if prompt:
        argv += ["--prompt-file", prompt]
    if session:
        argv += ["--session-file", session]
    for key in ("title", "expected-branch"):
        if key in got:
            argv += [f"--{key}", got[key]]
    if "--ephemeral" in fixed:
        argv += ["--ephemeral"]
    if k.get("schema"):
        sch = os.path.join(root, k["schema"])
        if not os.path.isfile(sch):
            raise Broken(f"kind {kind}: schema missing: {sch}")
        argv += ["--schema", sch]
    for key in ("model", "effort"):                 # E1 — passed through, never produced or checked here
        if key in got:
            argv += [f"--{key}", got[key]]
    if role:
        argv += ["--gpt-skill", role]
        if spath and delivery == "inject":
            argv += ["--inject-skill", spath]
        elif spath and delivery == "path":
            argv += ["--gpt-skill-path", spath]
    plan["argv"] = argv
    return plan


def _independent_tokens(kind, k, tokens):
    """Explicit inputs of an independent kind (D6): the caller's tokens are checked against the registry list and handed
    to the launcher in the caller's order — the argv stays byte-identical to the S0 golden. Measurement inputs (E8 —
    experimental_only) need --experimental; --experimental on a stable kind is accepted only to unlock them."""
    ins = k.get("inputs") or {}
    req, opt = list(ins.get("required") or []), set(ins.get("optional") or [])
    repeat, flags, exp_only = set(ins.get("repeatable") or []), set(ins.get("flags") or []), set(ins.get("experimental_only") or [])
    allowed = set(req) | opt | exp_only
    out, seen, used_exp, experimental, i = [], set(), set(), False, 0
    while i < len(tokens):
        t = tokens[i]
        if t == "--experimental":
            experimental, i = True, i + 1
            continue
        flag = t.split("=", 1)[0]
        if flag in FORBIDDEN_FLAGS:
            raise Usage(f"{flag} is not a caller input — the registry and the adapters own it (Z-04)")
        if "=" in t and t.startswith("--"):
            raise Usage(f"use '{flag} VALUE', not '{t}'")
        if not t.startswith("--"):
            raise Usage(f"unexpected argument: '{t}'")
        key = t[2:]
        if key not in allowed:
            raise Usage(f"--{key} is not an input of kind {kind}")
        if key in seen and key not in repeat:
            raise Usage(f"--{key} given twice")
        seen.add(key)
        if key in exp_only:
            used_exp.add(key)
        if key in flags:
            out.append(t)
            i += 1
            continue
        if i + 1 >= len(tokens):
            raise Usage(f"--{key} needs a value")
        v = tokens[i + 1]
        if v == "" or "\n" in v or "\0" in v:
            raise Usage(f"--{key} value is empty or has a newline")
        out += [t, v]
        i += 2
    for r in req:
        if r not in seen:
            raise Usage(f"kind {kind} needs --{r}")
    if used_exp and not experimental:
        raise Usage(f"--{sorted(used_exp)[0]} is a measurement input (E8) — kind {kind} takes it only with --experimental")
    if k.get("status") == "experimental":
        _status_gate(kind, k, experimental)
    elif experimental and not used_exp:
        raise Usage(f"kind {kind} is not experimental — drop --experimental (it only unlocks {sorted(exp_only) or 'nothing'})")
    return out


def launcher_policy(kind, gpt_agents=False, frame=None, root=ROOT, reg=None):
    """The launcher's policy for an independent kind (R-06 · SC-2) -> {ROLE, SCHEMA, SPAWN_LINE, FRAME}."""
    reg = load(os.path.join(root, "scripts", "gpt-kinds.json")) if reg is None else reg
    k = reg["kinds"].get(kind)
    if not isinstance(k, dict) or k.get("launcher") != "independent":
        raise Usage(f"{kind!r} is not an independent kind")
    spawn = k.get("spawn_opt_in") if gpt_agents else k.get("spawn")
    if gpt_agents and not spawn:
        raise Usage(f"--gpt-agents: kind {kind} has no lens opt-in (spawn_opt_in)")
    if spawn not in SPAWN_LINES:
        raise Broken(f"kind {kind}: spawn {spawn!r} has no launcher sentence")
    schema = os.path.join(root, k.get("schema") or "")
    if not k.get("schema") or not os.path.isfile(schema):
        raise Broken(f"kind {kind}: schema missing: {schema}")
    fpath = ""
    if frame is not None:
        rel = f"templates/gpt-frames/{frame}-{k['mode']}.md"
        known = {x.get("frame") for x in reg["kinds"].values() if x.get("status") == "experimental"}
        if k["mode"] != "review" or not re.fullmatch(r"[a-z][a-z0-9-]*", frame) or rel not in known:
            raise Usage(f"--frame {frame!r}: not a registered {k['mode']} frame (registry experimental kinds name the frames)")
        fpath = os.path.join(root, rel)
        if not os.path.isfile(fpath):
            raise Broken(f"frame missing: {fpath}")
    return {"ROLE": k.get("role") or "", "SCHEMA": schema, "SPAWN_LINE": SPAWN_LINES[spawn], "FRAME": fpath}


def _status_gate(kind, k, experimental):
    status = k.get("status")
    if status == "experimental" and not experimental:
        raise Usage(f"kind {kind} is experimental — it runs only with --experimental and is in no default flow")
    if status != "experimental" and experimental:
        raise Usage(f"kind {kind} is not experimental — drop --experimental")


def _read_audit(path):
    try:
        with open(path, encoding="utf-8") as f:
            a = json.load(f)
    except (OSError, ValueError) as e:
        raise Usage(f"audit unreadable: {path}: {e}")
    if not isinstance(a, dict):
        raise Usage(f"audit is not an object: {path}")
    return a


def write_plan(d, plan, error=""):
    meta = {"ADAPTER": plan.get("adapter", ""), "LOCK": plan.get("lock", ""), "SESSION_IN": plan.get("session_in", ""),
            "CODEX_HOME": plan.get("codex_home", ""), "CLEANUP_ISO": plan.get("cleanup_iso", ""), "ERROR": error.replace("\n", " ")}
    with open(os.path.join(d, "meta"), "w", encoding="utf-8") as f:
        f.write("".join(f"{k}={v}\n" for k, v in meta.items()))
    with open(os.path.join(d, "argv"), "wb") as f:
        f.write(b"".join(a.encode("utf-8") + b"\0" for a in plan.get("argv", [])))
    if plan.get("compose"):
        with open(os.path.join(d, "compose.json"), "w", encoding="utf-8") as f:
            json.dump(plan["compose"], f, ensure_ascii=False)


def compose(d):
    with open(os.path.join(d, "compose.json"), encoding="utf-8") as f:
        spec = json.load(f)
    data = b""
    for p in spec["parts"]:
        if "text" in p:
            data += p["text"].encode("utf-8")
        else:
            with open(p["file"], "rb") as f:
                data += f.read()
    with open(spec["to"], "wb") as f:
        f.write(data)


SCHEMA_NULL = {"check", "micro-eval"}   # XE-08: check is judged by grep on severity words; micro-eval is a prose contract
# A2 — role files must not pin model / effort: the session choice (wrapper) decides. TOML `key = …` · YAML `key: …`
PIN_TOML = re.compile(r"^\s*(model|model_reasoning_effort|review_model|reasoning_effort|model_provider)\s*=", re.M)
PIN_YAML = re.compile(r"^\s*(model|model_reasoning_effort|reasoning_effort|effort)\s*:", re.M)


def role_pins(root=ROOT):
    """-> (violations, files checked) for gpt-agents/*.toml and gpt-skills/*/agents/*.yaml."""
    v, seen = [], 0
    for pat, rx in ((os.path.join(root, "gpt-agents", "*.toml"), PIN_TOML), (os.path.join(root, "gpt-skills", "*", "agents", "*.yaml"), PIN_YAML)):
        for f in sorted(glob.glob(pat)):
            seen += 1
            txt = open(f, encoding="utf-8", errors="replace").read()
            for m in rx.finditer(txt):
                v.append(f"{os.path.relpath(f, root)}:{txt[:m.start()].count(chr(10)) + 1}: pins {m.group(1)} — role files must not pin model / effort (A2)")
    return v, seen


def lint(reg=None, root=ROOT):
    """Registry invariants + role-file pins. -> list of violations."""
    v = []
    try:
        reg = load(os.path.join(root, "scripts", "gpt-kinds.json")) if reg is None else reg
    except Broken as e:
        return [str(e)]
    kinds = reg["kinds"]
    v += role_pins(root)[0]
    v += lint_allow(reg, root)
    for name in sorted(CORE13 - set(kinds)):
        v.append(f"core kind missing: {name}")
    for name, k in sorted(kinds.items()):
        bad = FORBIDDEN_KEYS & set(k)
        if bad:
            v.append(f"{name}: forbidden keys {sorted(bad)} — model / effort / sandbox / timeout belong to the adapters")
        lau = k.get("launcher")
        if lau not in LAUNCHERS or k.get("mode") not in LAUNCHERS[lau][1]:
            v.append(f"{name}: launcher/mode {lau}/{k.get('mode')} not one of {LAUNCHERS}")
        if k.get("skill_delivery") not in DELIVERY:
            v.append(f"{name}: skill_delivery {k.get('skill_delivery')!r}")
        if k.get("skill_delivery") in ("inject", "path", "implicit", "iso-copy") and not k.get("role"):
            v.append(f"{name}: skill_delivery {k.get('skill_delivery')} without role")
        if k.get("skill_delivery") in ("inject", "path") and not os.path.isfile(os.path.join(root, "gpt-skills", f"fz-{k['role']}", "SKILL.md")):
            v.append(f"{name}: role skill gpt-skills/fz-{k.get('role')}/SKILL.md missing")
        if k.get("schema") and not os.path.isfile(os.path.join(root, k["schema"])):
            v.append(f"{name}: schema {k['schema']} missing")
        if k.get("frame") and not os.path.isfile(os.path.join(root, k["frame"])):
            v.append(f"{name}: frame {k['frame']} missing")
        if k.get("independence") not in INDEPENDENCE:
            v.append(f"{name}: independence {k.get('independence')!r}")
        if k.get("mode") == "resume" and k.get("independence") != "resumes-session":
            v.append(f"{name}: a resume kind continues a session — independence must be resumes-session")
        if k.get("spawn") not in SPAWN:
            v.append(f"{name}: spawn {k.get('spawn')!r}")
        if k.get("status") not in STATUS:
            v.append(f"{name}: status {k.get('status')!r}")
        if k.get("status") == "experimental" and (not k.get("evidence") or k.get("callers")):
            v.append(f"{name}: an experimental kind needs evidence ids and no default-flow callers")
        if any(f not in FIXED_OK for f in (k.get("fixed_args") or [])):
            v.append(f"{name}: fixed_args {k.get('fixed_args')} outside {sorted(FIXED_OK)}")
        if name in SCHEMA_NULL and k.get("schema"):
            v.append(f"{name}: must have schema null — check is judged by severity words (a schema's 'critical': 0 reads as fail) and micro-eval is prose (XE-08)")
        if k.get("mode") == "resume":
            target = kinds.get(k.get("resumes") or "")
            if not isinstance(target, dict):
                v.append(f"{name}: a resume kind names the kind it continues (resumes) — got {k.get('resumes')!r}")
            elif "--ephemeral" in (target.get("fixed_args") or []):
                v.append(f"{name}: continues {k['resumes']}, which is --ephemeral — the resume would find no session (XE-09)")
        if lau == "wrapper" and k.get("mode") == "review" and k.get("role") and k.get("skill_delivery") != "implicit":
            v.append(f"{name}: review mode takes no prompt — its role is implicit (CLI choice), not {k.get('skill_delivery')!r}")
        if lau == "independent" and k.get("frame") and k.get("mode") != "review":
            v.append(f"{name}: a launcher frame runs on review only — plan inputs hit the launcher's artifact guard (XE-11)")
        if lau == "independent" and name.startswith("verify"):
            v.append(f"{name}: plan verification cannot be an isolated first pass — its inputs are Claude artifacts (XE-11)")
        if lau == "independent":
            ins = k.get("inputs") or {}
            alln = set(ins.get("required") or []) | set(ins.get("optional") or [])
            if set(ins) - INDEP_KEYS or not ins.get("required") or "passthrough" in ins:
                v.append(f"{name}: an independent kind lists its inputs (required · optional · …) — no passthrough (D6)")
            if not (set(ins.get("repeatable") or []) | set(ins.get("flags") or [])) <= alln:
                v.append(f"{name}: repeatable / flags must be listed inputs")
            if set(ins.get("experimental_only") or []) & alln:
                v.append(f"{name}: an E8 input cannot also be a normal input")
            for sv in (k.get("spawn"), k.get("spawn_opt_in")):
                if sv and sv not in SPAWN_LINES:
                    v.append(f"{name}: spawn {sv!r} has no launcher sentence")
        if k.get("spawn_opt_in") and not (lau == "independent" and k.get("mode") == "review"):
            v.append(f"{name}: spawn_opt_in (lens opt-in) is for the review launcher only")
        if k.get("spawn_opt_in") and k.get("spawn_opt_in") not in SPAWN:
            v.append(f"{name}: spawn_opt_in {k.get('spawn_opt_in')!r}")
        rec = k.get("recipe")
        if rec:
            rp = os.path.join(root, rec)
            body = open(rp, encoding="utf-8").read() if os.path.isfile(rp) else ""
            if not re.search(r'gpt-call\.sh["\']?\s+' + re.escape(name) + r'(\s|$|`)', body):
                v.append(f"{name}: recipe {rec} shows no `gpt-call.sh {name}` call — a stale pointer or a recipe that bypasses the gate")
        elif k.get("status") == "stable":
            v.append(f"{name}: a stable kind needs a recipe — the document that shows its gate call")
    return v


# ── consumer lint (Z-04): a caller says WHAT through scripts/gpt-call.sh; HOW stays in the registry ──────────────────────
RECIPE_RE = [re.compile(r'gpt-exec\.sh["\']?\s+(review|exec|resume)\b'), re.compile(r'gpt_independent\.sh["\']?\s+(plan|review)\b'),
             re.compile(r'--inject-skill\b'), re.compile(r'--gpt-skill-path\b'), re.compile(r'get_gpt_skill_path\s+"')]
E_IDS = {f"E{i}" for i in range(1, 9)}   # registered exceptions (Z-04): E1 --model/--effort … E8 frozen measurement manifests
CONSUMER_DIRS = ("skills", "modules", "guides")


def bash_blocks(text):
    """-> [(first line number, [lines])] of ```bash fences."""
    out, lines, i = [], text.split("\n"), 0
    while i < len(lines):
        if lines[i].strip() == "```bash":
            j = i + 1
            while j < len(lines) and lines[j].strip() != "```":
                j += 1
            out.append((i + 2, lines[i + 1:j]))
            i = j
        i += 1
    return out


def lint_consumers(root=ROOT, only=None, reg=None):
    """-> (violations, files scanned, bash blocks scanned)."""
    reg = load(os.path.join(root, "scripts", "gpt-kinds.json")) if reg is None else reg
    allow = reg.get("consumer_allow") or []
    if only:
        files = list(only)
    else:
        files = sorted(os.path.relpath(f, root) for d in CONSUMER_DIRS
                       for f in glob.glob(os.path.join(root, d, "**", "*.md"), recursive=True))
    v, nb = [], 0
    for rel in files:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            v.append(f"{rel}: file not found")
            continue
        for start, block in bash_blocks(open(path, encoding="utf-8", errors="replace").read()):
            nb += 1
            for off, line in enumerate(block):
                if line.strip().startswith("#"):
                    continue
                if any(rx.search(line) for rx in RECIPE_RE) and not any(a.get("file") == rel and re.search(a.get("line_re", "$^"), line) for a in allow):
                    v.append(f"{rel}:{start + off}: hand-assembled GPT recipe — call scripts/gpt-call.sh <kind>: {line.strip()[:110]}")
    return v, len(files), nb


def lint_allow(reg, root=ROOT):
    v = []
    for i, a in enumerate(reg.get("consumer_allow") or []):
        if not isinstance(a, dict) or not os.path.isfile(os.path.join(root, a.get("file", ""))):
            v.append(f"consumer_allow[{i}]: file missing: {a.get('file') if isinstance(a, dict) else a!r}")
            continue
        if a.get("exception") not in E_IDS or not (a.get("reason") or "").strip():
            v.append(f"consumer_allow[{i}]: needs an exception id E1-E8 and a reason — an unaudited allow row is a bypass")
        try:
            re.compile(a.get("line_re") or "")
        except re.error as e:
            v.append(f"consumer_allow[{i}]: line_re does not compile: {e}")
        if not a.get("line_re"):
            v.append(f"consumer_allow[{i}]: line_re is empty")
    return v


GATE_PERM = "Bash(*/scripts/gpt-call.sh*)"


def lint_allowed_tools(root=ROOT):
    """A skill that may call GPT — its allowed-tools grant the wrapper or the launcher, or its body calls the gate — must grant
    the gate too. -> (violations, GPT-calling skills checked)."""
    v, n = [], 0
    for f in sorted(glob.glob(os.path.join(root, "skills", "*", "SKILL.md"))):
        text = open(f, encoding="utf-8", errors="replace").read()
        m = re.match(r"---\n(.*?)\n---\n", text, re.S)
        fm = m.group(1) if m else ""
        tools = re.search(r"(?ms)^allowed-tools:(.*?)(?=^[A-Za-z_-]+:|\Z)", fm)
        tools = tools.group(1) if tools else ""
        body = text[m.end():] if m else text
        if "gpt-exec.sh" in tools or "gpt_independent.sh" in tools or "scripts/gpt-call.sh" in body:
            n += 1
            if GATE_PERM not in tools:
                v.append(f"{os.path.relpath(f, root)}: may call GPT but allowed-tools lack {GATE_PERM}")
    if n == 0:
        v.append("allowed-tools: no GPT-calling skill found — the check measured nothing")
    return v, n


# ── generated tables in skills/fz-gpt/SKILL.md ───────────────────────────────────────────────────────────────────────
TABLE_DOC = os.path.join("skills", "fz-gpt", "SKILL.md")
BLOCK_NAMES = ("count", "roles", "kinds")


def _markers(name):
    return (f"<!-- gpt-kinds:{name} — generated by scripts/gpt_kinds.py table --write · do not edit -->", f"<!-- /gpt-kinds:{name} -->")


def _delivery(k):
    d, mode = k.get("skill_delivery"), k.get("mode")
    if d == "implicit":
        return "`review` 모드 — CLI 가 역할 스킬을 고른다(`--gpt-skill` 은 텔레메트리 라벨)" if mode == "review" else "`exec` — 이름만 넘긴다(`--gpt-skill` · 본문 주입 없음)"
    return {"inject": "`exec` + 래퍼가 본문 주입(`--inject-skill`)", "path": "`resume` + 정문이 본문을 앞에 붙임 · `--gpt-skill-path`(판정만)",
            "iso-copy": "격리 런처 — 격리 홈의 스킬 사본", None: "역할 없음"}[d]


def render(reg, root=ROOT):
    kinds = reg["kinds"]
    stable = [n for n, k in kinds.items() if k.get("status") == "stable"]
    exp = [n for n, k in kinds.items() if k.get("status") == "experimental"]
    core = [n for n in stable if kinds[n].get("tier") == "core"]
    out = {"count": [f"> 호출 kind {len(stable)}개 = core {len(core)} · 보조 {len(stable) - len(core)} — 실험 {len(exp)}개({', '.join(exp)})는 "
                     "`--experimental` 로만 돈다(기본 흐름에 없다). 정본 `scripts/gpt-kinds.json` · 호출 `scripts/gpt-call.sh <kind>`"]}
    roles = {}
    for n in stable:
        r = kinds[n].get("role")
        if r:
            roles.setdefault(r, []).append(n)
    rows = ["| 역할 | 스킬 | kind | 전달 |", "|------|------|------|------|"]
    for r, ns in roles.items():
        ways = sorted({_delivery(kinds[n]) for n in ns})
        skill = f"fz-{r}" if os.path.isfile(os.path.join(root, "gpt-skills", f"fz-{r}", "SKILL.md")) else f"{r} (GPT CLI system skill)"
        rows.append(f"| {r} | {skill} | {', '.join(ns)} | {' / '.join(ways)} |")
    out["roles"] = rows
    rows = ["| kind | 실행 | 용도 | 호출자 |", "|------|------|------|--------|"]
    for n in stable:
        k = kinds[n]
        how = f"런처 {k['mode']}" if k.get("launcher") == "independent" else f"래퍼 {k['mode']}"
        rows.append(f"| **{n}** | {how} | {k.get('purpose', '')} | {' · '.join(k.get('callers') or []) or '—'} |")
    out["kinds"] = rows
    return out


def table(root=ROOT, write=False):
    """-> list of problems (empty = in sync). With write=True, rewrites the blocks in place first."""
    path = os.path.join(root, TABLE_DOC)
    text = open(path, encoding="utf-8").read()
    gen = render(load(os.path.join(root, "scripts", "gpt-kinds.json")), root)
    problems = []
    for name in BLOCK_NAMES:
        b, e = _markers(name)
        if text.count(b) != 1 or text.count(e) != 1 or text.index(b) > text.index(e):
            problems.append(f"{TABLE_DOC}: generated block '{name}' markers missing or repeated")
            continue
        i, j = text.index(b) + len(b), text.index(e)
        want = "\n" + "\n".join(gen[name]) + "\n"
        if text[i:j] != want:
            if write:
                text = text[:i] + want + text[j:]
            else:
                problems.append(f"{TABLE_DOC}: generated block '{name}' differs from the registry — run gpt_kinds.py table --write")
    if write and not problems:
        open(path, "w", encoding="utf-8").write(text)
    return problems


def self_test():
    fails, checks = [], [0]

    def expect(name, fn, want):
        checks[0] += 1
        try:
            got = fn()
            res = ("ok", got)
        except Usage as e:
            res = ("usage", str(e))
        except Broken as e:
            res = ("broken", str(e))
        good = res[0] == want[0] and (len(want) < 2 or want[1](res[1]))
        if not good:
            fails.append(f"{name}: got {res[0]} {str(res[1])[:160]}")

    t = tempfile.mkdtemp(prefix="fz-gptkinds-st.")
    try:
        home, cwd = os.path.join(t, "home"), os.path.join(t, "proj")
        os.makedirs(home); os.makedirs(cwd)
        env = {"HOME": home}
        base = ["--cd", cwd, "--out", os.path.join(t, "o.txt")]
        pf = os.path.join(t, "p.txt"); open(pf, "w").write("P\n")
        reg = load()
        # every stable kind resolves with its required inputs
        sample = {"cd": cwd, "out": os.path.join(t, "o.txt"), "prompt-file": pf, "base": "main", "session-file": os.path.join(t, "s"),
                  "audit": os.path.join(t, "audit.json"), "prompt-out": os.path.join(t, "pc.txt")}
        os.makedirs(os.path.join(t, "fz-gpt-iso.ABCDEF", "gpt-home"))
        json.dump({"iso": os.path.join(t, "fz-gpt-iso.ABCDEF"), "sessionFile": os.path.join(t, "s")}, open(sample["audit"], "w"))
        ind = {"diff": pf, "requirement": pf, "arm": "a", "run-id": "r", "out-dir": os.path.join(t, "od")}
        for name, k in reg["kinds"].items():
            if k["launcher"] == "independent":
                toks = [x for r in k["inputs"]["required"] for x in (f"--{r}", ind[r])]
                expect(f"resolve {name}", lambda toks=toks, name=name: resolve(name, toks, env, cwd, reg=reg),
                       ("ok", lambda p, toks=toks, k=k: p["argv"] == [k["mode"]] + toks))
                continue
            toks = []
            for r in k["inputs"]["required"]:
                v = sample.get(r)
                if r == "out" and k.get("frame"):
                    v = os.path.join(t, os.path.splitext(os.path.basename(k["frame"]))[0], "o.txt")
                    os.makedirs(os.path.dirname(v), exist_ok=True)
                toks += ["--base", "main"] if r == "scope" else [f"--{r}", v]
            if k["status"] == "experimental":
                expect(f"experimental {name} without flag", lambda toks=toks, name=name: resolve(name, toks, env, cwd, reg=reg), ("usage",))
                toks = toks + ["--experimental"]
            expect(f"resolve {name}", lambda toks=toks, name=name: resolve(name, toks, env, cwd, reg=reg),
                   ("ok", lambda p, k=k, toks=toks: p["argv"][0] == k["mode"] and p["argv"][1:5][0::2] == ["--cd", "--out"]
                    and p["lock"] == toks[toks.index("--out") + 1]))
        # independent kinds: explicit inputs (D6) · E8 inputs need --experimental · order kept
        ir = ["--diff", pf, "--arm", "a", "--run-id", "r", "--out-dir", os.path.join(t, "od")]
        expect("independent unknown input", lambda: resolve("independent-review", ir + ["--bogus", "x"], env, cwd, reg=reg), ("usage",))
        expect("independent missing required", lambda: resolve("independent-review", ir[2:], env, cwd, reg=reg), ("usage",))
        expect("E8 --timeout without --experimental", lambda: resolve("independent-review", ir + ["--timeout", "60"], env, cwd, reg=reg), ("usage",))
        expect("E8 --frame without --experimental", lambda: resolve("independent-review", ir + ["--frame", "falsify"], env, cwd, reg=reg), ("usage",))
        expect("E8 with --experimental, order kept", lambda: resolve("independent-review", ["--deny", cwd] + ir + ["--timeout", "60", "--experimental"], env, cwd, reg=reg),
               ("ok", lambda p: p["argv"] == ["review", "--deny", cwd] + ir + ["--timeout", "60"]))
        expect("--experimental alone on stable independent", lambda: resolve("independent-review", ir + ["--experimental"], env, cwd, reg=reg), ("usage",))
        expect("repeatable --deny", lambda: resolve("independent-review", ir + ["--deny", cwd, "--deny", t], env, cwd, reg=reg), ("ok", lambda p: p["argv"].count("--deny") == 2))
        expect("plan has no --frame", lambda: resolve("independent-plan", ["--requirement", pf, "--arm", "a", "--run-id", "r", "--out-dir", t, "--frame", "falsify", "--experimental"], env, cwd, reg=reg), ("usage",))
        # launcher policy (R-06 · SC-2)
        expect("policy review", lambda: launcher_policy("independent-review", reg=reg),
               ("ok", lambda d: d["ROLE"] == "reviewer" and d["SPAWN_LINE"] == SPAWN_LINES["forbid-prompt"] and d["SCHEMA"].endswith("gpt_independent_review_schema.json") and d["FRAME"] == ""))
        expect("policy lenses", lambda: launcher_policy("independent-review", gpt_agents=True, reg=reg), ("ok", lambda d: d["SPAWN_LINE"] == SPAWN_LINES["lenses-optin"]))
        expect("policy plan + lenses", lambda: launcher_policy("independent-plan", gpt_agents=True, reg=reg), ("usage",))
        expect("policy frame", lambda: launcher_policy("independent-review", frame="falsify", reg=reg), ("ok", lambda d: d["FRAME"].endswith("templates/gpt-frames/falsify-review.md")))
        expect("policy bad frame", lambda: launcher_policy("independent-review", frame="nope", reg=reg), ("usage",))
        expect("policy wrapper kind", lambda: launcher_policy("verify", reg=reg), ("usage",))
        # frame kinds: own folder, frame first
        expect("frame kind outside its folder", lambda: resolve("review-falsify", base + ["--prompt-file", pf, "--experimental"], env, cwd, reg=reg), ("usage",))
        # canonical order and registry-owned flags
        expect("check fixed args", lambda: resolve("check", base, env, cwd, reg=reg)["argv"],
               ("ok", lambda a: a[5:] == ["--uncommitted", "--ephemeral", "--gpt-skill", "reviewer"]))
        expect("verify inject from bundle", lambda: resolve("verify", base + ["--prompt-file", pf], env, cwd, reg=reg)["argv"],
               ("ok", lambda a: a[-4:] == ["--gpt-skill", "architect", "--inject-skill", os.path.join(ROOT, "gpt-skills", "fz-architect", "SKILL.md")]
                and a[a.index("--schema") + 1].endswith("schemas/gpt_review_schema.json")))
        expect("model/effort verbatim", lambda: resolve("verify", base + ["--prompt-file", pf, "--model", "x y", "--effort", "weird"], env, cwd, reg=reg)["argv"],
               ("ok", lambda a: a[a.index("--model") + 1] == "x y" and a[a.index("--effort") + 1] == "weird"))
        expect("no model/effort produced", lambda: resolve("review", base + ["--base", "main"], env, cwd, reg=reg)["argv"],
               ("ok", lambda a: "--model" not in a and "--effort" not in a))
        # refusals
        for flag in ("-p", "--profile", "--ignore-user-config", "--config-permissions", "-c", "--schema", "--inject-skill", "--gpt-skill",
                     "--gpt-skill-path", "--ephemeral", "--sandbox"):
            expect(f"forbidden {flag}", lambda flag=flag: resolve("verify", base + ["--prompt-file", pf, flag, "x"], env, cwd, reg=reg), ("usage",))
        expect("forbidden --profile=x", lambda: resolve("verify", base + ["--prompt-file", pf, "--profile=x"], env, cwd, reg=reg), ("usage",))
        expect("forbidden on independent", lambda: resolve("independent-plan", ["--config-permissions"], env, cwd, reg=reg), ("usage",))
        expect("unknown kind", lambda: resolve("nope", base, env, cwd, reg=reg), ("usage",))
        expect("missing required", lambda: resolve("verify", base, env, cwd, reg=reg), ("usage",))
        expect("input not of kind", lambda: resolve("check", base + ["--base", "main"], env, cwd, reg=reg), ("usage",))
        expect("two scopes", lambda: resolve("review", base + ["--base", "main", "--uncommitted"], env, cwd, reg=reg), ("usage",))
        expect("repeated flag", lambda: resolve("verify", base + ["--prompt-file", pf, "--prompt-file", pf], env, cwd, reg=reg), ("usage",))
        expect("--experimental on stable", lambda: resolve("verify", base + ["--prompt-file", pf, "--experimental"], env, cwd, reg=reg), ("usage",))
        # registry damage -> 11
        bad = os.path.join(t, "bad.json"); open(bad, "w").write("{not json")
        expect("broken registry", lambda: load(bad), ("broken",))
        # skill-path tiers: 2b (bundle) -> 2a (CODEX_HOME / HOME) -> 1 (cwd CLAUDE.md)
        expect("tier 2b", lambda: skill_path("architect", env, cwd), ("ok", lambda p: p == os.path.join(ROOT, "gpt-skills", "fz-architect", "SKILL.md")))
        sk = os.path.join(home, ".codex", "skills")
        os.makedirs(os.path.join(sk, "fz-architect")); open(os.path.join(sk, "fz-architect", "SKILL.md"), "w").write("2a\n")
        expect("tier 2a", lambda: skill_path("architect", env, cwd), ("ok", lambda p: p == os.path.join(sk, "fz-architect", "SKILL.md")))
        os.makedirs(os.path.join(sk, "my-arch")); open(os.path.join(sk, "my-arch", "SKILL.md"), "w").write("1\n")
        open(os.path.join(cwd, "CLAUDE.md"), "w").write("# x\n## GPT Skills\n| role | skill |\n|---|---|\n| architect | my-arch |\n")
        expect("tier 1 (cwd)", lambda: skill_path("architect", env, cwd), ("ok", lambda p: p == os.path.join(sk, "my-arch", "SKILL.md")))
        expect("tier 1 other cwd", lambda: skill_path("architect", env, home), ("ok", lambda p: p == os.path.join(sk, "fz-architect", "SKILL.md")))
        expect("no skill", lambda: skill_path("no-such-role", env, home), ("ok", lambda p: p == ""))
        # verify-cross: env from the audit, composed prompt, cleanup
        vc = lambda: resolve("verify-cross", ["--audit", sample["audit"], "--cd", cwd, "--out", sample["out"], "--prompt-file", pf, "--prompt-out", sample["prompt-out"]], env, home, reg=reg)
        expect("verify-cross plan", vc, ("ok", lambda p: p["codex_home"].endswith("fz-gpt-iso.ABCDEF/gpt-home") and p["cleanup_iso"].endswith("fz-gpt-iso.ABCDEF")
                                          and p["compose"]["to"] == sample["prompt-out"] and p["argv"][p["argv"].index("--session-file") + 1] == sample["session-file"]
                                          and "--gpt-skill-path" in p["argv"]))
        json.dump({"iso": os.path.join(t, "fz-gpt-iso.ABCDEF"), "sessionFile": None}, open(sample["audit"], "w"))
        expect("verify-cross without session", vc, ("usage",))
        # lint on the shipped registry
        expect("lint clean", lambda: lint(reg), ("ok", lambda v: v == []))
        expect("lint catches forbidden key", lambda: lint({"kinds": dict(reg["kinds"], x=dict(reg["kinds"]["verify"], model="m"))}), ("ok", lambda v: any("forbidden keys" in x for x in v)))
        mut = lambda name, **kw: {"kinds": dict(reg["kinds"], **{name: dict(reg["kinds"][name], **kw)})}
        neg = [("check with a schema (XE-08)", mut("check", schema="schemas/gpt_review_schema.json"), "XE-08"),
               ("micro-eval with a schema (XE-08)", mut("micro-eval", schema="schemas/gpt_review_schema.json"), "XE-08"),
               ("resume target made --ephemeral (XE-09)", mut("final", fixed_args=["--ephemeral"]), "XE-09"),
               ("resume kind without resumes", mut("final-deep", resumes=None), "resumes"),
               ("fork mode", mut("verify", mode="fork"), "launcher/mode"),
               ("array-form pin in fixed_args (P-06)", mut("verify", fixed_args=["-c", "model=x"]), "fixed_args"),
               ("profile in fixed_args (XE-10)", mut("review", fixed_args=["-p", "fast"]), "fixed_args"),
               ("review mode with injected role", mut("review", skill_delivery="inject"), "implicit"),
               ("launcher frame on plan (XE-11)", mut("independent-plan", frame="scripts/gpt-kinds.json"), "XE-11"),
               ("verify kind on the launcher (XE-11)", mut("verify-falsify", launcher="independent", mode="review", skill_delivery="iso-copy"), "XE-11"),
               ("experimental kind with a default-flow caller", mut("review-falsify", callers=["skills/fz-review/SKILL.md"]), "experimental"),
               ("experimental kind without evidence", mut("review-falsify", evidence=[]), "experimental"),
               ("independent passthrough (D6)", mut("independent-review", inputs={"passthrough": True}), "passthrough"),
               ("spawn opt-in on plan", mut("independent-plan", spawn_opt_in="lenses-optin"), "spawn_opt_in"),
               ("spawn value without a sentence", mut("independent-review", spawn="inherit-audited"), "launcher sentence"),
               ("resume kind marked fresh", mut("final-deep", independence="plain"), "resumes-session"),
               ("missing frame file", mut("review-falsify", frame="templates/gpt-frames/nope.md"), "frame"),
               ("missing role skill", mut("verify", role="no-such-role"), "role skill"),
               ("core kind removed", {"kinds": {k: x for k, x in reg["kinds"].items() if k != "drift"}}, "core kind missing"),
               ("recipe without the kind's gate call", mut("drift", recipe="CLAUDE.md"), "recipe"),
               ("stable kind without a recipe", mut("drift", recipe=None), "recipe")]
        for label, r, needle in neg:
            expect(f"lint negative: {label}", lambda r=r: lint(r), ("ok", lambda v, needle=needle: any(needle in x for x in v)))
        pin_root = os.path.join(t, "pinroot")
        for sub in ("gpt-agents", os.path.join("gpt-skills", "fz-x", "agents"), "scripts", "schemas"):
            os.makedirs(os.path.join(pin_root, sub))
        shutil.copy(REGISTRY, os.path.join(pin_root, "scripts", "gpt-kinds.json"))
        open(os.path.join(pin_root, "gpt-agents", "a.toml"), "w").write('name = "a"\ndescription = "d"\n')
        open(os.path.join(pin_root, "gpt-skills", "fz-x", "agents", "openai.yaml"), "w").write("interface:\n  display_name: x\n")
        expect("role files without pins", lambda: role_pins(pin_root), ("ok", lambda r: r == ([], 2)))
        open(os.path.join(pin_root, "gpt-agents", "a.toml"), "a").write('model = "gpt-x"\n')
        open(os.path.join(pin_root, "gpt-skills", "fz-x", "agents", "openai.yaml"), "a").write("  effort: high\n")
        expect("role-file pins caught (toml + yaml)", lambda: role_pins(pin_root), ("ok", lambda r: len(r[0]) == 2 and r[1] == 2))
        expect("shipped role files: no pins", lambda: role_pins(ROOT), ("ok", lambda r: r[0] == [] and r[1] > 0))
        # consumer lint: a hand-assembled wrapper call in a bash block is caught, the gate form passes, comments are skipped
        cr = os.path.join(t, "consroot")
        os.makedirs(os.path.join(cr, "scripts")); os.makedirs(os.path.join(cr, "modules"))
        shutil.copy(REGISTRY, os.path.join(cr, "scripts", "gpt-kinds.json"))
        md = os.path.join(cr, "modules", "m.md")
        bad_md = 'x\n```bash\n"${FZ_PLUGIN_ROOT}/scripts/gpt-exec.sh" exec --cd "$G" --out "$O" --prompt-file "$P" \\\n  --inject-skill "$S"\n```\n'
        open(md, "w").write(bad_md)
        expect("consumers: wrapper recipe caught", lambda: lint_consumers(cr, ["modules/m.md"]), ("ok", lambda r: len(r[0]) == 2 and r[2] == 1))
        open(md, "w").write('```bash\n# gpt-exec.sh exec is the adapter (comment)\n"${FZ_PLUGIN_ROOT}/scripts/gpt-call.sh" verify --cd "$G" --out "$O" --prompt-file "$P"\n```\n')
        expect("consumers: gate call passes · comments skipped", lambda: lint_consumers(cr, ["modules/m.md"]), ("ok", lambda r: r[0] == [] and r[2] == 1))
        open(md, "w").write('```bash\nSP=$(get_gpt_skill_path "architect")\n"$R/scripts/gpt_independent.sh" review --diff d\n```\n')
        expect("consumers: skill-path helper and launcher recipe caught", lambda: lint_consumers(cr, ["modules/m.md"]), ("ok", lambda r: len(r[0]) == 2))
        open(md, "w").write(bad_md)
        allow_reg = dict(reg, consumer_allow=[{"file": "modules/m.md", "line_re": "gpt-exec\\.sh\" exec|--inject-skill", "exception": "E6", "reason": "adapter interface doc"}])
        expect("consumers: allow row with E-id suppresses", lambda: lint_consumers(cr, ["modules/m.md"], allow_reg), ("ok", lambda r: r[0] == []))
        expect("allow row without E-id is itself a violation", lambda: lint_allow(dict(reg, consumer_allow=[{"file": "modules/m.md", "line_re": "x", "reason": "r"}]), cr),
               ("ok", lambda v: any("E1-E8" in x for x in v)))
        expect("allow row for a missing file is a violation", lambda: lint_allow(dict(reg, consumer_allow=[{"file": "modules/nope.md", "line_re": "x", "exception": "E6", "reason": "r"}]), cr),
               ("ok", lambda v: any("file missing" in x for x in v)))
        # table: missing markers fail · write then check passes · a registry change makes check fail
        os.makedirs(os.path.join(cr, "skills", "fz-gpt"))
        doc = os.path.join(cr, "skills", "fz-gpt", "SKILL.md")
        open(doc, "w").write("# t\n| old | table |\n")
        expect("table: no markers -> problems", lambda: table(cr), ("ok", lambda p: len(p) == 3))
        open(doc, "w").write("# t\n" + "".join(f"{_markers(n)[0]}\nstale\n{_markers(n)[1]}\n" for n in BLOCK_NAMES))
        expect("table: stale -> problems", lambda: table(cr), ("ok", lambda p: len(p) == 3))
        expect("table: write then check in sync", lambda: (table(cr, write=True), table(cr))[1], ("ok", lambda p: p == []))
        r2 = json.load(open(os.path.join(cr, "scripts", "gpt-kinds.json"), encoding="utf-8"))
        r2["kinds"]["drift"]["purpose"] = "changed"
        json.dump(r2, open(os.path.join(cr, "scripts", "gpt-kinds.json"), "w"), ensure_ascii=False)
        expect("table: registry change -> check fails", lambda: table(cr), ("ok", lambda p: len(p) == 1 and "'kinds'" in p[0]))
        # allowed-tools: a wrapper-granting skill without the gate permission is caught; with it, clean; no GPT skill = measured nothing
        atr = os.path.join(t, "atroot")      # own root — the table cells above left a skills/fz-gpt there
        sk = os.path.join(atr, "skills", "fz-a")
        os.makedirs(sk)
        open(os.path.join(sk, "SKILL.md"), "w").write("---\nname: a\nallowed-tools: >-\n  Read, Bash(*/scripts/gpt-exec.sh*)\nmetadata:\n  x: 1\n---\nbody\n")
        expect("allowed-tools: wrapper without gate caught", lambda: lint_allowed_tools(atr), ("ok", lambda r: len(r[0]) == 1 and r[1] >= 1))
        open(os.path.join(sk, "SKILL.md"), "w").write("---\nname: a\nallowed-tools: >-\n  Read, Bash(*/scripts/gpt-call.sh*), Bash(*/scripts/gpt-exec.sh*)\n---\nbody\n")
        expect("allowed-tools: gate granted -> clean", lambda: lint_allowed_tools(atr), ("ok", lambda r: r[0] == [] and r[1] >= 1))
        open(os.path.join(sk, "SKILL.md"), "w").write("---\nname: a\nallowed-tools: >-\n  Read, Bash\n---\n\"${FZ_PLUGIN_ROOT}/scripts/gpt-call.sh\" verify\n")
        expect("allowed-tools: body calls the gate, bare Bash only -> caught", lambda: lint_allowed_tools(atr), ("ok", lambda r: len(r[0]) == 1))
        shutil.rmtree(os.path.join(atr, "skills", "fz-a"))
        expect("allowed-tools: no GPT skill -> measured nothing", lambda: lint_allowed_tools(atr), ("ok", lambda r: r[1] == 0 and len(r[0]) == 1))
    finally:
        shutil.rmtree(t, ignore_errors=True)
    for f in fails:
        print("FAIL", f)
    print("GPT-KINDS-SELFTEST", "OK" if not fails else f"FAIL ({len(fails)})")
    print(f"self-test gpt_kinds: {'OK' if not fails else 'FAIL'} ({checks[0]} checks, {len(fails)} failed)")
    return 0 if not fails else 1


def main(argv):
    if argv[:1] == ["--self-test"]:
        return self_test()
    if argv[:1] == ["launcher-policy"] and len(argv) >= 2:
        rest, ga, fr = argv[2:], False, None
        while rest:
            if rest[0] == "--gpt-agents":
                ga, rest = True, rest[1:]
            elif rest[0] == "--frame" and len(rest) >= 2:
                fr, rest = rest[1], rest[2:]
            else:
                print(f"GPT-KINDS-USAGE(10): unknown argument {rest[0]}", file=sys.stderr)
                return 10
        try:
            pol = launcher_policy(argv[1], ga, fr)
        except Usage as e:
            print(f"GPT-KINDS-USAGE(10): {e}", file=sys.stderr)
            return 10
        except Broken as e:
            print(f"GPT-KINDS-BROKEN(11): {e}", file=sys.stderr)
            return 11
        for key in ("ROLE", "SCHEMA", "SPAWN_LINE", "FRAME"):
            print(f"{key}={pol[key]}")
        return 0
    if argv[:1] == ["skill-path"] and len(argv) == 2:
        print(skill_path(argv[1]))
        return 0
    if argv[:2] == ["lint", "--consumers"]:
        rest, root, only, tools = argv[2:], ROOT, [], False
        while rest:
            if rest[0] == "--root" and len(rest) >= 2:
                root, rest = os.path.abspath(rest[1]), rest[2:]
            elif rest[0] == "--allowed-tools":
                tools, rest = True, rest[1:]
            elif rest[0] == "--only":
                only, rest = [x for x in rest[1:] if not x.startswith("--")], [x for x in rest[1:] if x.startswith("--")]
            else:
                print(f"unknown argument: {rest[0]}", file=sys.stderr)
                return 10
        reg = load(os.path.join(root, "scripts", "gpt-kinds.json"))
        v, nf, nb = lint_consumers(root, only, reg)
        v += lint_allow(reg, root)
        nt = 0
        if tools:
            vt, nt = lint_allowed_tools(root)
            v += vt
        for x in v:
            print("LINT", x)
        print("GPT-KINDS-CONSUMERS", "OK" if not v else f"FAIL ({len(v)})", f"files={nf} bash-blocks={nb}" + (f" gpt-skills={nt}" if tools else ""))
        return 0 if not v and nb > 0 else 11
    if argv[:1] == ["table"] and len(argv) in (2, 4) and argv[1] in ("--write", "--check") and (len(argv) == 2 or argv[2] == "--root"):
        root = os.path.abspath(argv[3]) if len(argv) == 4 else ROOT
        problems = table(root, write=argv[1] == "--write")
        for x in problems:
            print("TABLE", x)
        print("GPT-KINDS-TABLE", "OK" if not problems else f"FAIL ({len(problems)})")
        return 0 if not problems else 11
    if argv[:1] == ["lint"] and (len(argv) == 1 or (argv[1:2] == ["--root"] and len(argv) == 3)):
        root = os.path.abspath(argv[2]) if len(argv) == 3 else ROOT
        v = lint(root=root)
        n_kinds = len(load(os.path.join(root, "scripts", "gpt-kinds.json"))["kinds"]) if not any("registry" in x for x in v) else 0
        for x in v:
            print("LINT", x)
        print("GPT-KINDS-LINT", "OK" if not v else f"FAIL ({len(v)})", f"kinds={n_kinds} role-files={role_pins(root)[1]}")
        return 0 if not v else 11
    if argv[:1] == ["compose"] and argv[1:2] == ["--plan-dir"] and len(argv) == 3:
        compose(argv[2])
        return 0
    if argv[:1] == ["resolve"] and argv[1:2] == ["--plan-dir"] and len(argv) >= 4:
        d, kind, tokens = argv[2], argv[3], argv[4:]
        plan = {}
        try:
            plan = resolve(kind, tokens)
        except Usage as e:
            write_plan(d, _partial(kind, tokens), f"GPT-CALL-USAGE(10): {e}")
            print(f"GPT-CALL-USAGE(10): {e}", file=sys.stderr)
            return 10
        except Broken as e:
            write_plan(d, _partial(kind, tokens), f"GPT-CALL-BROKEN(11): {e}")
            print(f"GPT-CALL-BROKEN(11): {e}", file=sys.stderr)
            return 11
        write_plan(d, plan)
        return 0
    print("usage: gpt_kinds.py resolve --plan-dir DIR KIND [inputs...] | compose --plan-dir DIR | skill-path ROLE | lint | --self-test", file=sys.stderr)
    return 10


def _partial(kind, tokens):
    """What the gate needs to clean up after a refused call: the OUT lock of a wrapper kind, the --session-file to keep,
    and an audit's iso for a kind that takes --audit (verify-cross). Best effort — never raises."""
    p = {"adapter": "", "argv": [], "lock": "", "session_in": "", "codex_home": "", "cleanup_iso": ""}
    try:
        k = load()["kinds"].get(kind) or {}
        if k.get("launcher") == "wrapper":
            for flag, key in (("--out", "lock"), ("--session-file", "session_in")):
                if flag in tokens and tokens.index(flag) + 1 < len(tokens):
                    p[key] = tokens[tokens.index(flag) + 1]
            ins = k.get("inputs") or {}
            # only a kind that takes --audit owns that session — a refused call must not clean an iso it would never have used
            if "audit" in ins.get("required", []) + ins.get("optional", []) and "--audit" in tokens and tokens.index("--audit") + 1 < len(tokens):
                audit = _read_audit(tokens[tokens.index("--audit") + 1])
                p["cleanup_iso"] = audit.get("iso") or ""
                p["session_in"] = p["session_in"] or audit.get("sessionFile") or ""
    except Exception:   # noqa: BLE001 — cleanup hints only
        pass
    return p


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception as e:   # noqa: BLE001 — an internal error is a dependency failure (11), never 1
        print(f"GPT-CALL-BROKEN(11): resolver error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(11)
