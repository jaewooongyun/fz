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
  gpt_kinds.py launcher-policy KIND [--frame NAME]
                                           the launcher's policy for an independent kind (R-06 · SC-2): ROLE · SCHEMA ·
                                           SPAWN_LINE · FRAME as KEY=VALUE lines. The launcher asks this itself, so a gate
                                           call and a direct launcher call get the same answer and the argv stays as given
  gpt_kinds.py lint [--root DIR]           registry invariants + role-file model/effort pins (DIR = another plugin tree)
  gpt_kinds.py lint --consumers [--allowed-tools] [--root DIR] [--only FILE...]
                                           --allowed-tools: a skill that may call GPT has Bash(*/scripts/gpt-call.sh*)
                                           markdown ```bash blocks must not hand-assemble wrapper / launcher calls
                                           a counted-kind call line (gpt_rounds.py KIND_SLOTS) carries FZ_GPT_ARTIFACT=
                                           a literal `gpt-call.sh <kind>` word in a command shape (fence · backtick span · line-head
                                           command) (skills · modules · guides · agents · workflows · README · CLAUDE.md) is a
                                           registry kind — variables and placeholders are not kind words; a full run (no --only)
                                           that reads no kind word fails (measured nothing)
  gpt_kinds.py table --write|--check [--root DIR]
                                           the generated blocks in skills/fz-gpt/SKILL.md (kind count · roles · kinds)
  gpt_kinds.py --self-test

exit: 0 ok · 10 usage (unknown kind, removed kind — the message names the kind to use instead (registry removed_kinds),
      removed input — the message names it and why (registry removed_inputs), missing / unknown / forbidden input,
      experimental kind without --experimental, bad audit) · 11 registry or dependency failure (unreadable registry,
      missing schema, internal error).
      ⛔ never 1 or 2 — those mean something else elsewhere in fz (XE-02).
"""
import ast
import contextlib
import glob
import io
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
SPAWN = {"inherit-audited", "forbid-prompt"}
STATUS = {"stable", "experimental"}
# The launcher's no-spawn sentence comes from the kind's registry spawn value (SC-2) — the text lives here, keyed by
# that value, so the launcher holds no policy of its own. ⛔ forbid-prompt is byte-for-byte the S0 default prompt line.
SPAWN_LINES = {
    "forbid-prompt": "하위 에이전트를 만들지 않는다.",
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
    Exception: a Tier 2a entry whose real path is gpt-skills/fz-ROLE of another install root carrying the same plugin name
    (root manifest name — an older cached version that setup linked before an update) yields to this tree's bundle when the bundle
    exists — the running version's role body is injected, not the old one. A real folder, another plugin's link, a link into this
    root, an unreadable manifest and Tier 1 keep their answer.
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
    bundled = os.path.join(root, "gpt-skills", f"fz-{role}", "SKILL.md")
    if os.path.isfile(os.path.join(sk_root, f"fz-{role}", "SKILL.md")):
        real = os.path.realpath(os.path.join(sk_root, f"fz-{role}"))
        other = os.path.dirname(os.path.dirname(real))
        if (os.path.basename(real) == f"fz-{role}" and os.path.basename(os.path.dirname(real)) == "gpt-skills"
                and other != os.path.realpath(root) and os.path.isfile(bundled)
                and _plugin_name(root) and _plugin_name(other) == _plugin_name(root)):
            return bundled
        return os.path.join(sk_root, f"fz-{role}", "SKILL.md")
    return bundled if os.path.isfile(bundled) else ""


def _plugin_name(root):
    """The top-level name of <root>/.claude-plugin/plugin.json — '' when missing or unreadable (no comparison then)."""
    try:
        with open(os.path.join(root, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return ""
    name = d.get("name") if isinstance(d, dict) else None
    return name if isinstance(name, str) else ""


def _gone_input(key, removed):
    """A caller written for an older version passes an input taken out of the registry (removed_inputs): the refusal names it
    and why instead of 'unknown input'."""
    gone = (removed or {}).get(key)
    if isinstance(gone, dict):
        raise Usage(f"--{key} was removed — drop it ({gone.get('why') or 'scripts/gpt-kinds.json removed_inputs'})")


def parse_inputs(tokens, removed=None):
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
            _gone_input(key, removed)
            raise Usage(f"unknown input: --{key}")
    return got, experimental


def resolve(kind, tokens, env=None, cwd=None, root=ROOT, reg=None):
    """-> plan dict {adapter, argv, lock, session_in, codex_home, cleanup_iso, compose}. Raises Usage / Broken."""
    reg = load() if reg is None else reg
    k = reg["kinds"].get(kind)
    if not isinstance(k, dict):
        gone = (reg.get("removed_kinds") or {}).get(kind)
        if isinstance(gone, dict) and gone.get("use"):   # a caller written for an older version — say what replaced it
            raise Usage(f"kind '{kind}' was removed — use '{gone['use']}' instead ({gone.get('why') or 'scripts/gpt-kinds.json removed_kinds'})")
        raise Usage(f"unknown kind: '{kind}' (known: {', '.join(sorted(reg['kinds']))})")
    launcher = k.get("launcher")
    if launcher not in LAUNCHERS or k.get("mode") not in LAUNCHERS[launcher][1]:
        raise Broken(f"kind {kind}: bad launcher/mode {launcher}/{k.get('mode')}")
    adapter = LAUNCHERS[launcher][0]
    plan = {"adapter": adapter, "argv": [], "lock": "", "session_in": "", "codex_home": "", "cleanup_iso": "", "compose": None}

    if launcher == "independent":
        plan["argv"] = [k["mode"]] + _independent_tokens(kind, k, tokens, reg.get("removed_inputs"))
        return plan

    got, experimental = parse_inputs(tokens, reg.get("removed_inputs"))
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
        if not os.path.isdir(iso):
            # F-578 — an earlier resume cross already cleaned this isolation dir (E3). Same exit as no session: the caller falls back to verify
            raise Usage(f"audit {got['audit']} iso {iso} is gone — an earlier verify-cross cleaned it; run verify instead")
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


def _independent_tokens(kind, k, tokens, removed=None):
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
            _gone_input(key, removed)
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


def launcher_policy(kind, frame=None, root=ROOT, reg=None):
    """The launcher's policy for an independent kind (R-06 · SC-2) -> {ROLE, SCHEMA, SPAWN_LINE, FRAME}."""
    reg = load(os.path.join(root, "scripts", "gpt-kinds.json")) if reg is None else reg
    k = reg["kinds"].get(kind)
    if not isinstance(k, dict) or k.get("launcher") != "independent":
        raise Usage(f"{kind!r} is not an independent kind")
    spawn = k.get("spawn")
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
# A2 — role files must not pin model / effort: the session choice (wrapper) decides. YAML `key: …`
PIN_YAML = re.compile(r"^\s*(model|model_reasoning_effort|reasoning_effort|effort)\s*:", re.M)


def role_pins(root=ROOT):
    """-> (violations, files checked) for gpt-skills/*/agents/*.yaml."""
    v, seen = [], 0
    for f in sorted(glob.glob(os.path.join(root, "gpt-skills", "*", "agents", "*.yaml"))):
        seen += 1
        txt = open(f, encoding="utf-8", errors="replace").read()
        for m in PIN_YAML.finditer(txt):
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
            if k.get("spawn") and k.get("spawn") not in SPAWN_LINES:
                v.append(f"{name}: spawn {k.get('spawn')!r} has no launcher sentence")
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


# ── kind-name lint: a literal kind word after gpt-call.sh names a registry kind ──────────────────────────────────────────
# An unknown kind fails only when the call runs (exit 10), so a typo or a renamed / dropped kind in a page stays silent until then.
# Command shapes only: inside a fence of any info string (``` · ```bash · ```yaml · ~~~ — closed by the same mark at least as long,
# code to the end when unclosed) · inside a backtick code span · the line-head command (indent and NAME=value prefixes allowed) ·
# every line of workflows/*.js. A word in .md prose ("The gate scripts/gpt-call.sh is …") is not a call and is not read.
# A variable ("$KIND", ${K}) or a placeholder (<kind>, {kind}, KIND) does not start with a lowercase letter
# and is not a kind word; a quoted literal ("review") is. The word runs over ASCII letters · digits · _ · - (verify_x is not read as
# verify; a Korean particle ends it). Own scope, not CONSUMER_DIRS — widening that would widen the bash-block and round lints too.
# Approximate: a kind word on the next line after a `\` continuation, or a kind held in a variable, is not checked; a code span over
# two lines, HTML <code>, a fence inside a `>` quote and a 4-space indented block are not read as code, nor a second call after `;`
# on a prose line; an English sentence that opens with the script name at the line head ("gpt-call.sh wraps …") is still read as a call.
KIND_REF_RE = re.compile(r'gpt-call\.sh["\']?\s+["\']?([a-z][A-Za-z0-9_-]*)')
KIND_REF_FENCE_RE = re.compile(r'\s*(`{3,}|~{3,})(.*)')   # a fence line; a ``` info string holding a backtick is an inline span instead
KIND_REF_HEAD_RE = re.compile(r'\s*(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*[^\s`]*(?=gpt-call\.sh)')   # ends where the line-head command's script name starts
KIND_REF_DIRS = ("skills", "modules", "guides", "agents")   # *.md, plus workflows/**/*.js and KIND_REF_FILES
KIND_REF_FILES = ("README.md", "CLAUDE.md")


def code_spans(line):
    """-> [(start, end)] of the backtick code spans on one line: a run of n backticks opens, the next run of exactly n closes it
    (an opener without its closer is a literal backtick)."""
    runs, out, i = [m.span() for m in re.finditer(r'`+', line)], [], 0
    while i < len(runs):
        n = runs[i][1] - runs[i][0]
        j = next((k for k in range(i + 1, len(runs)) if runs[k][1] - runs[k][0] == n), None)
        if j is None:
            i += 1
        else:
            out.append((runs[i][1], runs[j][0]))
            i = j + 1
    return out


def lint_kind_refs(root=ROOT, reg=None, only=None):
    """-> (violations, literal kind words checked)."""
    reg = load(os.path.join(root, "scripts", "gpt-kinds.json")) if reg is None else reg
    if only:
        files = list(only)
    else:
        files = sorted([os.path.relpath(f, root) for d in KIND_REF_DIRS for f in glob.glob(os.path.join(root, d, "**", "*.md"), recursive=True)]
                       + [os.path.relpath(f, root) for f in glob.glob(os.path.join(root, "workflows", "**", "*.js"), recursive=True)]
                       + [f for f in KIND_REF_FILES if os.path.isfile(os.path.join(root, f))])
    v, n = [], 0
    for rel in files:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            v.append(f"{rel}: file not found")
            continue
        md, fence = rel.endswith(".md"), None   # fence: the open fence's mark (``` · ~~~ run) while inside one
        for i, line in enumerate(open(path, encoding="utf-8", errors="replace").read().split("\n"), 1):
            f = KIND_REF_FENCE_RE.match(line) if md else None
            if f and fence is None and not (f.group(1)[0] == "`" and "`" in f.group(2)):
                fence = f.group(1)
                continue
            if f and fence is not None and f.group(1)[0] == fence[0] and len(f.group(1)) >= len(fence) and not f.group(2).strip():
                fence = None
                continue
            prose = md and fence is None   # outside a fence a hit counts only in a backtick span or as the line-head command
            spans = code_spans(line) if prose else []
            head = KIND_REF_HEAD_RE.match(line) if prose else None
            for m in KIND_REF_RE.finditer(line):
                if prose and not (any(s <= m.start() < e for s, e in spans) or (head and head.end() == m.start())):
                    continue
                n += 1
                if m.group(1) not in reg["kinds"]:
                    v.append(f"{rel}:{i}: `gpt-call.sh {m.group(1)}` — {m.group(1)!r} is not a registry kind (scripts/gpt-kinds.json): "
                             f"{line.strip()[:100]}")
    return v, n


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


# ── round-cap wiring (C-S05): a counted-kind call line names its artifact family ──────────────────────────────────────
# Canonical: modules/cross-validation.md § 재검증 라운드 상한. The gate counts a call only when the caller sets FZ_GPT_ARTIFACT —
# a call line without it is outside the cap and the gate says nothing, so this lint does. Counted kinds = the KIND_SLOTS keys of the
# linted tree's scripts/gpt_rounds.py, read as a literal (counted_kinds — never imported). A call line is `gpt-call.sh <counted kind>`
# followed by an input (`--…`) on the same line, prose or ```bash alike (skill steps name their calls in prose); a mention without
# inputs is not. Every page under CONSUMER_DIRS is in scope — a new page is checked by default.
ROUND_ENV = "FZ_GPT_ARTIFACT="
# Line-level exemptions (page, line regex, why) — generic call-form examples, not pipeline call sites. A row covers only the lines
# its regex matches, and a row that matches no counted call line in its scanned page is stale and fails the lint (audited like
# consumer_allow / lint_allow), so an example cannot shield a real call line on the same page.
ROUND_EXEMPT = (
    ("skills/fz-gpt/SKILL.md", r'gpt-call\.sh" verify --cd "\$GIT_ROOT" --out "\$F" --prompt-file P ',
     "call form of an explicit /fz-gpt verify (custom instruction) - not a pipeline artifact"),
    ("modules/fz-gpt-bash-hygiene.md", r'gpt-call\.sh" verify --cd "\$WORK_DIR" --out "\$RESULT_FILE" --prompt-file /tmp/gpt-prompt\.txt',
     "hygiene template kept as a reference of what the wrapper does"),
    ("modules/fz-gpt-bash-hygiene.md", r'gpt-call\.sh" verify --cd "\$GIT_ROOT" --out "\$F" --prompt-file P \[--model M\]',
     "section 8 interface synopsis - the exec form with its optional flags"),
    ("modules/cross-validation.md", r'gpt-call\.sh" verify --cd "\$GIT_ROOT" --out "\$OUT" --prompt-file "\$P"\s*$',
     "call-contract example - the contract line points counted calls to the round-cap section"),
)


def counted_kinds(root=ROOT):
    """-> sorted counted kinds: the keys of KIND_SLOTS in <root>/scripts/gpt_rounds.py, read with ast.literal_eval.
    ⛔ Do not import gpt_rounds (here or at module top): it imports this module at its own top (sys.path + `import gpt_kinds`), so
    an import is a cycle, and it would run another tree's module code (sys.path, dont_write_bytecode, a second gpt_kinds).
    Missing, unparsable or not a literal -> Broken (measured nothing, not zero call lines)."""
    path = os.path.join(root, "scripts", "gpt_rounds.py")
    try:
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), path)
    except (OSError, SyntaxError, ValueError) as e:
        raise Broken(f"round lint: KIND_SLOTS unreadable from {path}: {type(e).__name__}: {e}")
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "KIND_SLOTS" for t in node.targets):
            try:
                slots = ast.literal_eval(node.value)
            except (ValueError, TypeError, SyntaxError) as e:
                raise Broken(f"round lint: KIND_SLOTS in {path} is not a literal: {e}")
            if not isinstance(slots, dict) or not slots:
                raise Broken(f"round lint: KIND_SLOTS in {path} is empty or not a dict")
            return sorted(slots)
    raise Broken(f"round lint: no top-level KIND_SLOTS assignment in {path}")


def round_call_re(kinds):
    """`gpt-call.sh <kind> --…` — longest kind first so verify-gates is not read as verify."""
    alt = "|".join(re.escape(k) for k in sorted(kinds, key=len, reverse=True))
    return re.compile(r'gpt-call\.sh["\']?\s+(' + alt + r')(?![-\w])\s+--')


def lint_rounds(root=ROOT, only=None, kinds=None, exempt=ROUND_EXEMPT):
    """-> (violations, counted call lines checked). Exempt lines are not counted; an exempt row that matches no counted call line in
    a scanned page is stale (a violation)."""
    rx = round_call_re(counted_kinds(root) if kinds is None else kinds)
    if only:
        files = list(only)
    else:
        files = sorted(os.path.relpath(f, root) for d in CONSUMER_DIRS
                       for f in glob.glob(os.path.join(root, d, "**", "*.md"), recursive=True))
    v, n, used = [], 0, set()
    for rel in files:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            v.append(f"{rel}: file not found")
            continue
        for i, line in enumerate(open(path, encoding="utf-8", errors="replace").read().split("\n"), 1):
            for m in rx.finditer(line):
                if ROUND_ENV in line[:m.start()]:
                    n += 1
                    continue
                rows = [j for j, (page, line_re, _) in enumerate(exempt) if page == rel and re.search(line_re, line)]
                if rows:
                    used.update(rows)
                    continue
                n += 1
                v.append(f"{rel}:{i}: `gpt-call.sh {m.group(1)}` call line without {ROUND_ENV}<family> — outside the round cap "
                         f"(modules/cross-validation.md § 재검증 라운드 상한): {line.strip()[:100]}")
    for j, (page, _, why) in enumerate(exempt):
        if page in files and j not in used:
            v.append(f"round exempt row {j} ({page}): matches no counted call line — stale, drop it or fix its regex")
        if not why.strip():
            v.append(f"round exempt row {j} ({page}): no reason — an unaudited exemption is a bypass")
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
        rows.append(f"| **{n}** | {how} | {k.get('purpose', '')} | {' · '.join(k.get('callers') or []) or f'명시 호출 전용(`/fz-gpt {n}`)'} |")
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


# ── declared callers vs real wiring (F-467) ──────────────────────────────────────────────────────────────────────────
# A caller label in the registry is a claim ("/fz-pr 전" runs final). Two directions are checked:
#   undeclared — a skill step really calls the kind (front door or /fz-gpt) but the registry does not name that skill;
#   unwired    — a declared label names a skill or module whose text (one hop through the modules it cites) never names the kind.
# /fz pipeline chains are wiring too (modules/pipelines.md `### N.` section · `| 체인 | fz-gpt <kind> |` row): a kind a section
#   chains cites that section in a caller label (`modules/pipelines.md §N`), and a label citing §N belongs to a kind §N chains.
# fz-gpt itself documents every kind for explicit use, so its own pages are recipes, not callers. A line that says
# "명시 호출" documents how a user calls a kind by hand (e.g. "commit/pr 전 → gpt check 는 명시 호출 전용") — not wiring.
CALLER_TOKEN = re.compile(r"(/fz(?:-[a-z]+)*)(?![\w-])|(modules/[\w.-]+\.md)")
EXPLICIT_ONLY = "명시 호출"
PIPELINES = "modules/pipelines.md"
PIPE_CITE = re.compile(re.escape(PIPELINES) + r"\s*§(\d+)")


def _strict(kind):
    return re.compile(r'gpt-call\.sh"?\s+' + re.escape(kind) + r"(?![-\w])|/fz-gpt\s+" + re.escape(kind) + r"(?![-\w])")


def _loose(kind):
    return re.compile(r"(?:gpt-call\.sh\"?\s+|fz-gpt\s+|`)" + re.escape(kind) + r"(?![-\w])")


def _skill_files(root, skill):
    d = os.path.join(root, "skills", skill)
    return [p for p in [os.path.join(d, "SKILL.md")] + sorted(glob.glob(os.path.join(d, "references", "*.md"))) if os.path.isfile(p)]


def _read(p):
    return open(p, encoding="utf-8", errors="replace").read()


def callers_scan(root=ROOT, reg=None):
    """-> {kind: [skill, ...]} — skills (not fz-gpt) whose own pages really call the kind."""
    reg = load(os.path.join(root, "scripts", "gpt-kinds.json")) if reg is None else reg
    skills = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(root, "skills", "*", "SKILL.md")))
    texts = {s: "\n".join(l for p in _skill_files(root, s) for l in _read(p).split("\n") if EXPLICIT_ONLY not in l)
             for s in skills if s != "fz-gpt"}
    return {n: sorted(s for s, t in texts.items() if _strict(n).search(t)) for n in reg["kinds"]}


def pipeline_chains(root=ROOT):
    """-> {section number: {kind, ...}} — the kinds each `| 체인 |` row of modules/pipelines.md runs after `fz-gpt`."""
    p, out, sec = os.path.join(root, PIPELINES), {}, None
    for line in _read(p).split("\n") if os.path.isfile(p) else []:
        m = re.match(r"###\s+(\d+)\.\s", line)
        if m:
            sec = m.group(1)
        elif sec and line.startswith("| 체인 |"):
            out.setdefault(sec, set()).update(re.findall(r"fz-gpt\s+([a-z][a-z0-9-]*)", line))
    return out


def check_callers(reg, root=ROOT):
    problems, real = [], callers_scan(root, reg)
    for n, k in reg["kinds"].items():
        decl = k.get("callers") or []
        declared_skills = set()
        for label in decl:
            files = []
            for m in CALLER_TOKEN.finditer(label):
                if m.group(1):
                    skill = m.group(1)[1:]
                    declared_skills.add(skill)
                    own = _skill_files(root, skill)
                    files += own
                    for p in own:   # one hop: modules the skill's pages cite
                        files += [os.path.join(root, x) for x in re.findall(r"modules/[\w.-]+\.md", _read(p))]
                else:
                    files.append(os.path.join(root, m.group(2)))
            files = [p for p in dict.fromkeys(files) if os.path.isfile(p)]
            if CALLER_TOKEN.search(label) and not any(_loose(n).search(_read(p)) for p in files):
                problems.append(f"kind {n}: declared caller '{label}' never names the kind — unwired claim (F-467)")
        for s in real[n]:
            if s not in declared_skills:
                problems.append(f"kind {n}: skills/{s} calls it but the registry callers do not name /{s}")
    chains = pipeline_chains(root)
    for n, k in reg["kinds"].items():
        cites = {}
        for label in k.get("callers") or []:
            for sec in PIPE_CITE.findall(label):
                cites.setdefault(sec, label)
        for sec, ks in sorted(chains.items()):
            if n in ks and sec not in cites:
                problems.append(f"kind {n}: {PIPELINES} §{sec} chains it but the registry callers do not cite that section")
        for sec, label in sorted(cites.items()):
            if n not in chains.get(sec, set()):
                problems.append(f"kind {n}: declared caller '{label}' cites {PIPELINES} §{sec}, whose chain does not run it")
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
        elif os.environ.get("FZ_SELFTEST_LIST") and name.startswith("r3-"):
            print(f"PASS {name}")   # gate cell line — round 3 cells only (the rest keep the summary line)

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
        # removed inputs (registry removed_inputs): a caller written for an older version is refused with the input's name and why,
        #   on an independent and a wrapper kind alike — not as an unknown input · without the registry row it is a plain refusal
        gone_in = sorted(reg.get("removed_inputs") or {})
        expect("removed inputs listed in the registry", lambda: gone_in, ("ok", lambda g: len(g) > 0))
        for key in gone_in:
            expect(f"removed input --{key} on an independent kind names it", lambda key=key: resolve("independent-review", ir + [f"--{key}"], env, cwd, reg=reg),
                   ("usage", lambda m, key=key: m.startswith(f"--{key} was removed — ") and "not an input" not in m))
            expect(f"removed input --{key} on a wrapper kind names it", lambda key=key: resolve("verify", base + ["--prompt-file", pf, f"--{key}"], env, cwd, reg=reg),
                   ("usage", lambda m, key=key: m.startswith(f"--{key} was removed — ") and "unknown input" not in m))
            expect(f"removed input --{key} without the registry row -> plain refusal",
                   lambda key=key: resolve("independent-review", ir + [f"--{key}"], env, cwd, reg=dict(reg, removed_inputs={})), ("usage", lambda m: "is not an input of kind" in m))
        expect("independent missing required", lambda: resolve("independent-review", ir[2:], env, cwd, reg=reg), ("usage",))
        expect("E8 --timeout without --experimental", lambda: resolve("independent-review", ir + ["--timeout", "60"], env, cwd, reg=reg), ("usage",))
        expect("E8 --frame without --experimental", lambda: resolve("independent-review", ir + ["--frame", "repro"], env, cwd, reg=reg), ("usage",))
        expect("E8 with --experimental, order kept", lambda: resolve("independent-review", ["--deny", cwd] + ir + ["--timeout", "60", "--experimental"], env, cwd, reg=reg),
               ("ok", lambda p: p["argv"] == ["review", "--deny", cwd] + ir + ["--timeout", "60"]))
        expect("--experimental alone on stable independent", lambda: resolve("independent-review", ir + ["--experimental"], env, cwd, reg=reg), ("usage",))
        expect("repeatable --deny", lambda: resolve("independent-review", ir + ["--deny", cwd, "--deny", t], env, cwd, reg=reg), ("ok", lambda p: p["argv"].count("--deny") == 2))
        expect("plan has no --frame", lambda: resolve("independent-plan", ["--requirement", pf, "--arm", "a", "--run-id", "r", "--out-dir", t, "--frame", "repro", "--experimental"], env, cwd, reg=reg), ("usage",))
        # launcher policy (R-06 · SC-2)
        expect("policy review", lambda: launcher_policy("independent-review", reg=reg),
               ("ok", lambda d: d["ROLE"] == "reviewer" and d["SPAWN_LINE"] == SPAWN_LINES["forbid-prompt"] and d["SCHEMA"].endswith("gpt_independent_review_schema.json") and d["FRAME"] == ""))
        expect("policy frame", lambda: launcher_policy("independent-review", frame="repro", reg=reg), ("ok", lambda d: d["FRAME"].endswith("templates/gpt-frames/repro-review.md")))
        expect("policy falsify frame rolled back (E1)", lambda: launcher_policy("independent-review", frame="falsify", reg=reg), ("usage",))
        expect("policy bad frame", lambda: launcher_policy("independent-review", frame="nope", reg=reg), ("usage",))
        expect("policy wrapper kind", lambda: launcher_policy("verify", reg=reg), ("usage",))
        # frame kinds: own folder, frame first
        expect("frame kind outside its folder", lambda: resolve("review-repro", base + ["--prompt-file", pf, "--experimental"], env, cwd, reg=reg), ("usage",))
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
        # tier 2a link into another install root with the same plugin name (an older cached version) -> this tree's bundle ·
        #   a link into this root, another plugin's link, a run root without the bundle or without a manifest (also when the other
        #   root has none), a link to another folder or another role of a same-name root keep the 2a path
        vr = os.path.join(t, "vroots")

        def vroot(tag, name, bundle=True):
            r = os.path.join(vr, tag)
            os.makedirs(os.path.join(r, "gpt-skills", "fz-architect") if bundle else r)
            if name:
                os.makedirs(os.path.join(r, ".claude-plugin"))
                json.dump({"name": name}, open(os.path.join(r, ".claude-plugin", "plugin.json"), "w"))
            if bundle:
                open(os.path.join(r, "gpt-skills", "fz-architect", "SKILL.md"), "w").write(tag + "\n")
            return r
        run_r, old_r, oth_r, bare_r, noman_r = vroot("run", "fz"), vroot("old", "fz"), vroot("oth", "zz"), vroot("bare", "fz", False), vroot("noman", "")
        noman2_r = vroot("noman2", "")
        for sub in ("skills", "gpt-skills"):   # same-name root: a Claude skill folder of the role's name · another role's bundle
            os.makedirs(os.path.join(old_r, sub, "fz-architect" if sub == "skills" else "fz-planner"))
            open(os.path.join(old_r, sub, "fz-architect" if sub == "skills" else "fz-planner", "SKILL.md"), "w").write("x\n")
        vh = os.path.join(vr, "home")
        vlink = os.path.join(vh, ".codex", "skills", "fz-architect")
        os.makedirs(os.path.dirname(vlink))

        def via(target, root, rel=os.path.join("gpt-skills", "fz-architect")):
            if os.path.lexists(vlink):
                os.remove(vlink)
            os.symlink(os.path.join(target, rel), vlink)
            return skill_path("architect", {"HOME": vh}, home, root)
        v2a = os.path.join(vlink, "SKILL.md")
        expect("tier 2a other-version link -> bundle", lambda: via(old_r, run_r), ("ok", lambda p: p == os.path.join(run_r, "gpt-skills", "fz-architect", "SKILL.md")))
        expect("tier 2a link to this root -> 2a path", lambda: via(run_r, run_r), ("ok", lambda p: p == v2a))
        expect("tier 2a other plugin link -> 2a", lambda: via(oth_r, run_r), ("ok", lambda p: p == v2a))
        expect("tier 2a other-version link, no bundle -> 2a", lambda: via(old_r, bare_r), ("ok", lambda p: p == v2a))
        expect("tier 2a other-version link, run root without a manifest -> 2a", lambda: via(old_r, noman_r), ("ok", lambda p: p == v2a))
        expect("tier 2a link between two roots without a manifest -> 2a", lambda: via(noman2_r, noman_r), ("ok", lambda p: p == v2a))
        expect("tier 2a link to another folder of a same-name root -> 2a", lambda: via(old_r, run_r, os.path.join("skills", "fz-architect")), ("ok", lambda p: p == v2a))
        expect("tier 2a link to another role of a same-name root -> 2a", lambda: via(old_r, run_r, os.path.join("gpt-skills", "fz-planner")), ("ok", lambda p: p == v2a))
        # verify-cross: env from the audit, composed prompt, cleanup
        vc = lambda: resolve("verify-cross", ["--audit", sample["audit"], "--cd", cwd, "--out", sample["out"], "--prompt-file", pf, "--prompt-out", sample["prompt-out"]], env, home, reg=reg)
        expect("verify-cross plan", vc, ("ok", lambda p: p["codex_home"].endswith("fz-gpt-iso.ABCDEF/gpt-home") and p["cleanup_iso"].endswith("fz-gpt-iso.ABCDEF")
                                          and p["compose"]["to"] == sample["prompt-out"] and p["argv"][p["argv"].index("--session-file") + 1] == sample["session-file"]
                                          and "--gpt-skill-path" in p["argv"]))
        # F-578 — a second Phase 2 round reuses the audit after the first resume cleaned the iso: usage (10), not a measurement failure (12)
        os.rename(os.path.join(t, "fz-gpt-iso.ABCDEF"), os.path.join(t, "fz-gpt-iso.GONE00"))
        expect("r3-f578-cleaned-iso-is-usage-10", vc, ("usage", lambda m: "is gone" in m and "run verify instead" in m))
        os.rename(os.path.join(t, "fz-gpt-iso.GONE00"), os.path.join(t, "fz-gpt-iso.ABCDEF"))
        expect("verify-cross plan after restore", vc, ("ok",))
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
               ("experimental kind with a default-flow caller", mut("review-repro", callers=["skills/fz-review/SKILL.md"]), "experimental"),
               ("experimental kind without evidence", mut("review-repro", evidence=[]), "experimental"),
               ("independent passthrough (D6)", mut("independent-review", inputs={"passthrough": True}), "passthrough"),
               ("spawn value without a sentence", mut("independent-review", spawn="inherit-audited"), "launcher sentence"),
               ("resume kind marked fresh", mut("final-deep", independence="plain"), "resumes-session"),
               ("missing frame file", mut("review-repro", frame="templates/gpt-frames/nope.md"), "frame"),
               ("missing role skill", mut("verify", role="no-such-role"), "role skill"),
               ("core kind removed", {"kinds": {k: x for k, x in reg["kinds"].items() if k != "drift"}}, "core kind missing"),
               ("recipe without the kind's gate call", mut("drift", recipe="CLAUDE.md"), "recipe"),
               ("stable kind without a recipe", mut("drift", recipe=None), "recipe")]
        for label, r, needle in neg:
            expect(f"lint negative: {label}", lambda r=r: lint(r), ("ok", lambda v, needle=needle: any(needle in x for x in v)))
        pin_root = os.path.join(t, "pinroot")
        for sub in (os.path.join("gpt-skills", "fz-x", "agents"), "scripts", "schemas"):
            os.makedirs(os.path.join(pin_root, sub))
        shutil.copy(REGISTRY, os.path.join(pin_root, "scripts", "gpt-kinds.json"))
        open(os.path.join(pin_root, "gpt-skills", "fz-x", "agents", "openai.yaml"), "w").write("interface:\n  display_name: x\n")
        expect("role files without pins", lambda: role_pins(pin_root), ("ok", lambda r: r == ([], 1)))
        open(os.path.join(pin_root, "gpt-skills", "fz-x", "agents", "openai.yaml"), "a").write("  effort: high\n")
        expect("role-file pins caught (yaml)", lambda: role_pins(pin_root), ("ok", lambda r: len(r[0]) == 1 and r[1] == 1))
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
        # round-cap wiring: a counted-kind call line carries FZ_GPT_ARTIFACT= on that line (bash or prose) · a mention without inputs
        #   and an uncounted kind are not call lines · an exempt row covers only its own lines and goes stale when unused ·
        #   KIND_SLOTS is read from the tree's gpt_rounds.py as a literal (missing or non-literal -> broken)
        try:
            rk = counted_kinds(ROOT)
        except Broken:
            rk = ["independent-plan", "validate", "verify", "verify-gates"]   # the read cell below fails; keep the others meaningful
        rmd = os.path.join(cr, "modules", "r.md")
        open(rmd, "w").write('```bash\n"${FZ_PLUGIN_ROOT}/scripts/gpt-call.sh" verify-gates --cd "$G" --out "$O" --prompt-file "$P"\n```\n'
                             'launch `"${FZ_PLUGIN_ROOT}"/scripts/gpt-call.sh independent-plan --requirement R --arm gpt` in the background\n')
        expect("rounds: call lines without the family caught (bash + prose)", lambda: lint_rounds(cr, ["modules/r.md"], rk, ()),
               ("ok", lambda r: len(r[0]) == 2 and r[1] == 2))
        open(rmd, "w").write('```bash\nFZ_GPT_ARTIFACT=plan FZ_WORK_DIR="$W" "${FZ_PLUGIN_ROOT}/scripts/gpt-call.sh" verify --cd "$G" --out "$O" --prompt-file "$P"\n'
                             '"${FZ_PLUGIN_ROOT}/scripts/gpt-call.sh" review --cd "$G" --out "$O" --base main\n```\n'
                             'the exec form (`gpt-call.sh verify`) is only named here\n')
        expect("rounds: family given · uncounted kind · bare mention -> clean", lambda: lint_rounds(cr, ["modules/r.md"], rk, ()),
               ("ok", lambda r: r[0] == [] and r[1] == 1))
        open(rmd, "w").write('FZ_GPT_ARTIFACT=plan is exported above\n"${FZ_PLUGIN_ROOT}/scripts/gpt-call.sh" validate --cd "$G" --out "$O" --prompt-file "$P"\n')
        expect("rounds: the family sits on the call line itself", lambda: lint_rounds(cr, ["modules/r.md"], rk, ()), ("ok", lambda r: len(r[0]) == 1))
        open(rmd, "w").write('"${FZ_PLUGIN_ROOT}/scripts/gpt-call.sh" verify --cd "$G" --out "$F" --prompt-file "$P"\n'
                             '"${FZ_PLUGIN_ROOT}/scripts/gpt-call.sh" validate --cd "$G" --out "$F" --prompt-file "$Q"\n')
        own = (("modules/r.md", r'--prompt-file "\$P"$', "example"),)
        expect("rounds: an exempt row covers only its own line", lambda: lint_rounds(cr, ["modules/r.md"], rk, own),
               ("ok", lambda r: len(r[0]) == 1 and "validate" in r[0][0] and r[1] == 1))
        expect("rounds: an exempt row that matches nothing is stale", lambda: lint_rounds(cr, ["modules/r.md"], rk, (("modules/r.md", "no-such-line", "x"),)),
               ("ok", lambda r: any("stale" in x for x in r[0])))
        expect("rounds: KIND_SLOTS read from the tree", lambda: counted_kinds(ROOT),
               ("ok", lambda k: {"verify", "verify-gates", "independent-plan"} <= set(k)))
        expect("rounds: tree without gpt_rounds.py -> broken", lambda: counted_kinds(cr), ("broken",))
        open(os.path.join(cr, "scripts", "gpt_rounds.py"), "w").write("KIND_SLOTS = dict(verify=1)\n")
        expect("rounds: KIND_SLOTS not a literal -> broken", lambda: counted_kinds(cr), ("broken",))
        # kind-name lint: a literal kind word after gpt-call.sh in a command shape (a fence of any info string · a backtick span ·
        #   a line-head command; every line of workflows/*.js) is a registry kind — a word in .md prose is not read · a variable or a
        #   placeholder is not a kind word, a quoted literal and a word tail (verify_x) are · own scope (agents · workflows/*.js ·
        #   README · CLAUDE.md too — not tests/ · docs/ · scripts/) · `lint --consumers` fails on it (exit 11) and counts kind-refs
        kr = os.path.join(t, "kindroot")
        for sub in ("scripts", "modules", os.path.join("skills", "s"), "guides", "agents", "workflows", "tests", "docs"):
            os.makedirs(os.path.join(kr, sub))
        kmd = os.path.join(kr, "modules", "k.md")
        open(kmd, "w").write('```bash\n"${FZ_PLUGIN_ROOT}/scripts/gpt-call.sh" reviews --cd x\n"${FZ_PLUGIN_ROOT}/scripts/gpt-call.sh" "$KIND" --cd x\n'
                             '"${FZ_PLUGIN_ROOT}/scripts/gpt-call.sh" ${KIND} --cd x\n"${FZ_PLUGIN_ROOT}/scripts/gpt-call.sh" <kind> --cd x\n'
                             '"${FZ_PLUGIN_ROOT}/scripts/gpt-call.sh" {kind} --cd x\n```\nthe gate is `scripts/gpt-call.sh KIND` · `gpt-call.sh <kind>`\n')
        expect("kind-refs: unregistered literal caught · variables and placeholders skipped", lambda: lint_kind_refs(kr, reg, ["modules/k.md"]),
               ("ok", lambda r: len(r[0]) == 1 and r[0][0].startswith("modules/k.md:2:") and "'reviews'" in r[0][0] and r[1] == 1))
        open(kmd, "w").write('```bash\n"${FZ_PLUGIN_ROOT}/scripts/gpt-call.sh" review --cd x\n```\nprose: `gpt-call.sh verify-gates` · gpt-call.sh check, then gpt-call.sh final을\n')
        expect("kind-refs: registered kinds (bash + backtick) -> clean · bare prose is not read", lambda: lint_kind_refs(kr, reg, ["modules/k.md"]),
               ("ok", lambda r: r == ([], 2)))
        open(kmd, "w").write('```bash\n"$R/scripts/gpt-call.sh" "reviews" --cd x\n"$R/scripts/gpt-call.sh" verify_x --cd x\n```\n')
        expect("kind-refs: a quoted literal and a word tail are kind words", lambda: lint_kind_refs(kr, reg, ["modules/k.md"]),
               ("ok", lambda r: len(r[0]) == 2 and "'verify_x'" in r[0][1] and r[1] == 2))

        def lint_k(lines, hits=None):
            # hits: each line must hold that many KIND_REF_RE hits first — a cell then cannot pass because the regex missed the word
            if hits is not None and [len(KIND_REF_RE.findall(x)) for x in lines] != [hits] * len(lines):
                raise Broken(f"precondition: each line holds {hits} `gpt-call.sh <word>` hit(s)")
            open(kmd, "w").write("\n".join(lines) + "\n")
            return lint_kind_refs(kr, reg, ["modules/k.md"])
        expect("kind-refs: English prose after the script name is not a kind word",
               lambda: lint_k(["The gate scripts/gpt-call.sh is the only entry", 'Use "gpt-call.sh" and "gpt-exec.sh" together',
                               "- gpt-call.sh wraps the adapters", "정문 gpt-call.sh kind 를 넘긴다"], 1), ("ok", lambda r: r == ([], 0)))
        expect("kind-refs: a typo kind in a command shape is caught",
               lambda: lint_k(["`gpt-call.sh reviews --cd x`", "`FZ_GPT_ARTIFACT=plan gpt-call.sh verfy --cd x`", "```yaml", 'then: "gpt-call.sh reviews 실행"',
                               "```", "~~~", "gpt-call.sh reviews", "~~~"]), ("ok", lambda r: [x.split(":")[1] for x in r[0]] == ["1", "2", "4", "7"] and r[1] == 4))
        expect("kind-refs: an English word in a backtick span is a kind word — the place decides, not the word",
               lambda: lint_k(["the gate is `gpt-call.sh is`"], 1), ("ok", lambda r: len(r[0]) == 1 and "'is'" in r[0][0] and r[1] == 1))
        expect("kind-refs: prose after a line-head command is not read", lambda: lint_k(["gpt-call.sh review --cd x · like gpt-call.sh wraps the adapters"], 2),
               ("ok", lambda r: r == ([], 1)))
        # kind-ref-grid: place × name form × separator × word, every product cell run on its own file. Oracle: counted ⇔ a command
        #   shape ∧ a lowercase literal · violation ⇔ counted ∧ not a registry kind. Each text holds its KIND_REF_RE hit first (literal
        #   words only), so a place cannot pass because the regex missed the word. A call in a fence never opens its line (`run …` ·
        #   `then: …`), so a fence cell is not passed by the line-head rule. Not made here: a code span over two lines · the line after a `\`
        #   continuation · HTML <code> · a fence inside a `>` quote · a 4-space indented code block · a NAME=value prefix whose quoted
        #   value holds a space
        gr = os.path.join(t, "gridroot")
        os.makedirs(os.path.join(gr, "modules")); os.makedirs(os.path.join(gr, "workflows"))
        places = (("fence-bash", "x\n```bash\nif true; then {c} --cd x; fi\n```\n", True), ("fence-plain", "x\n```\nrun {c} --cd x\n```\n", True),
                  ("fence-yaml", 'x\n```yaml\nthen: "{c} 실행"\n```\n', True), ("fence-tilde", "x\n~~~\nrun {c} --cd x\n~~~\n", True),
                  ("fence-nested", "x\n````md\n```\nrun {c} --cd x\n```\n````\n", True), ("fence-unclosed", "x\n```\nrun {c} --cd x\n", True),
                  ("fence-info-line-not-a-closer", "x\n```\n```bash\nrun {c} --cd x\n```\n", True),
                  ("fence-tilde-not-closed-by-backticks", "x\n~~~\n```\nrun {c} --cd x\n~~~\n", True),
                  ("after-fence", "```bash\necho x\n```\nThe gate {c} is the only entry\n", False),
                  ("span-single", "the gate: `{c} --cd x` here\n", True), ("span-double", "the gate: ``{c} --cd x`` here\n", True),
                  ("span-triple-inline", "```{c} --cd x```\n", True), ("span-after-double", "``a`b`` then `{c} --cd x`\n", True),
                  ("after-span", "`x` then {c} is here\n", False), ("head", "{c} --cd x\n", True), ("head-indent", "x\n  {c} --cd x\n", True),
                  ("head-env", 'FZ_GPT_ARTIFACT=plan FZ_WORK_DIR="$W" {c} --cd x\n', True), ("list", "- {c} wraps the adapters\n", False),
                  ("quote", "> {c} --cd x\n", False), ("table", "| {c} --cd x | ok |\n", False), ("prose", "The gate {c} is the only entry\n", False),
                  ("prose-ko", "정문 {c} 를 넘긴다\n", False), ("js", "// the gate {c} is the only entry\n", True))
        names = ("gpt-call.sh", "scripts/gpt-call.sh", '"${FZ_PLUGIN_ROOT}/scripts/gpt-call.sh"', '"${FZ_PLUGIN_ROOT}"/scripts/gpt-call.sh', "'scripts/gpt-call.sh'")
        words = (("review", "review"), ("reviews", "reviews"), ("is", "is"), ("실행", None), ("<kind>", None), ('"$KIND"', None), ('"reviews"', "reviews"),
                 ("verify_x", "verify_x"))

        def grid(place, text, code):
            rel = "workflows/w.js" if place == "js" else "modules/g.md"
            line = str([i for i, x in enumerate(text.split("\n"), 1) if "{c}" in x][0])
            miss = []
            for nm in names:
                for sep in (" ", "\t", "\u00a0", "   "):
                    for word, kind in words:
                        body, counted = text.replace("{c}", nm + sep + word), code and kind is not None
                        if len(KIND_REF_RE.findall(body)) != (kind is not None):
                            miss.append(f"{nm} + {sep!r} + {word}: regex precondition")
                            continue
                        open(os.path.join(gr, rel), "w").write(body)
                        v, n = lint_kind_refs(gr, reg, [rel])
                        if n != int(counted) or [x.split(":")[1] for x in v] != ([line] if counted and kind not in reg["kinds"] else []):
                            miss.append(f"{nm} + {sep!r} + {word}: {len(v)} violation(s) · {n} counted")
            return miss
        for place, text, code in places:
            expect(f"kind-ref-grid {place}", lambda p=place, x=text, c=code: grid(p, x, c), ("ok", lambda r: r == []))
        in_scope = ["CLAUDE.md", "README.md", "agents/a.md", "guides/g.md", "modules/k.md", "skills/s/SKILL.md", "workflows/w.js"]
        for rel in in_scope + ["tests/t.md", "docs/d.md", "scripts/x.py"]:
            open(os.path.join(kr, rel), "w").write("x\ngpt-call.sh reviews --cd x\n")
        expect("kind-refs: scope = skills · modules · guides · agents · workflows/*.js · README · CLAUDE.md", lambda: lint_kind_refs(kr, reg),
               ("ok", lambda r: sorted(x.split(":")[0] for x in r[0]) == in_scope and r[1] == len(in_scope)))
        json.dump(dict(reg, consumer_allow=[]), open(os.path.join(kr, "scripts", "gpt-kinds.json"), "w"), ensure_ascii=False)
        open(os.path.join(kr, "scripts", "gpt_rounds.py"), "w").write('KIND_SLOTS = {"verify": ("verify", "main")}\n')
        open(kmd, "w").write('```bash\n"${FZ_PLUGIN_ROOT}/scripts/gpt-call.sh" reviews --cd x\n```\n')

        def run_main(args):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(args)
            return rc, buf.getvalue()
        expect("kind-refs: lint --consumers fails on an unregistered kind (exit 11)", lambda: run_main(["lint", "--consumers", "--root", kr, "--only", "modules/k.md"]),
               ("ok", lambda r: r[0] == 11 and "LINT modules/k.md:2:" in r[1] and "FAIL (1)" in r[1] and "kind-refs=1" in r[1]))
        # a full run that reads no kind word measured nothing (a scope shrunk to zero stays green otherwise) — the tree has a bash
        #   block and a counted call line, so only the kind-name guard can fail it · --only keeps 0 (the round guard's rule)
        zr = os.path.join(t, "zeroroot")
        os.makedirs(os.path.join(zr, "scripts")); os.makedirs(os.path.join(zr, "skills", "s"))
        json.dump(dict(reg, consumer_allow=[]), open(os.path.join(zr, "scripts", "gpt-kinds.json"), "w"), ensure_ascii=False)
        open(os.path.join(zr, "scripts", "gpt_rounds.py"), "w").write('KIND_SLOTS = {"verify": ("verify", "main")}\n')
        open(os.path.join(zr, "skills", "s", "SKILL.md"), "w").write("```bash\necho x\n```\nrun FZ_GPT_ARTIFACT=plan gpt-call.sh verify --cd x\n")
        expect("kind-refs: a full run that reads no kind word fails (exit 11)", lambda: run_main(["lint", "--consumers", "--root", zr]),
               ("ok", lambda r: r[0] == 11 and "LINT kind-name lint: no literal kind word" in r[1] and "measured nothing" in r[1] and "kind-refs=0" in r[1]
                and "round-calls=1" in r[1] and "FAIL (1)" in r[1]))
        expect("kind-refs: --only that reads no kind word stays 0", lambda: run_main(["lint", "--consumers", "--root", zr, "--only", "skills/s/SKILL.md"]),
               ("ok", lambda r: r[0] == 0 and "kind-refs=0" in r[1] and "measured nothing" not in r[1]))
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
        rest, fr = argv[2:], None
        while rest:
            if rest[0] == "--frame" and len(rest) >= 2:
                fr, rest = rest[1], rest[2:]
            else:
                print(f"GPT-KINDS-USAGE(10): unknown argument {rest[0]}", file=sys.stderr)
                return 10
        try:
            pol = launcher_policy(argv[1], fr)
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
        try:
            vr, nr = lint_rounds(root, only)
        except Broken as e:
            vr, nr = [str(e)], 0
        if not vr and nr == 0 and not only:
            vr = ["round lint: no counted-kind call line under skills · modules · guides — measured nothing"]
        v += vr
        vk, nk = lint_kind_refs(root, reg, only)
        if not vk and nk == 0 and not only:
            vk = ["kind-name lint: no literal kind word after gpt-call.sh in a command shape (skills · modules · guides · agents · "
                  "workflows · README · CLAUDE.md) — measured nothing"]
        v += vk
        nt = 0
        if tools:
            vt, nt = lint_allowed_tools(root)
            v += vt
        for x in v:
            print("LINT", x)
        print("GPT-KINDS-CONSUMERS", "OK" if not v else f"FAIL ({len(v)})", f"files={nf} bash-blocks={nb} round-calls={nr} kind-refs={nk}" + (f" gpt-skills={nt}" if tools else ""))
        return 0 if not v and nb > 0 else 11
    if argv[:1] == ["table"] and len(argv) in (2, 4) and argv[1] in ("--write", "--check") and (len(argv) == 2 or argv[2] == "--root"):
        root = os.path.abspath(argv[3]) if len(argv) == 4 else ROOT
        problems = table(root, write=argv[1] == "--write")
        if argv[1] == "--check":   # the rendered 호출자 column is only true if the declared callers match real wiring
            problems += check_callers(load(os.path.join(root, "scripts", "gpt-kinds.json")), root)
        for x in problems:
            print("TABLE", x)
        print("GPT-KINDS-TABLE", "OK" if not problems else f"FAIL ({len(problems)})")
        return 0 if not problems else 11
    if argv[:1] == ["callers"] and len(argv) in (1, 3) and (len(argv) == 1 or argv[1] == "--root"):
        root = os.path.abspath(argv[2]) if len(argv) == 3 else ROOT
        reg = load(os.path.join(root, "scripts", "gpt-kinds.json"))
        print(json.dumps(callers_scan(root, reg), ensure_ascii=False, indent=1))
        problems = check_callers(reg, root)
        for x in problems:
            print("CALLERS", x)
        print("GPT-KINDS-CALLERS", "OK" if not problems else f"FAIL ({len(problems)})")
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
