# gui_manager.py
# Local GUI to add MCP servers, draft/AI-generate Rules (with titled policy line),
# add new agent Profiles, and patch router_mcp.py (SUB_AGENTS + RULE_TITLES).
# - Adds a "Copy JSON" button for MCP Servers block.
# - Rule generation now begins with: "<TitleName> — <PolicyName>"
#   where <PolicyName> reflects the role (e.g., "UXResearcher — Research Artifacts Policy").
# - Sections included (plain text, no Markdown): Role, Scope, Strict Prohibitions, Allowed Tools,
#   Method & Equity, Design & Security, Quality, Accessibility (WCAG AA), Spec Alignment,
#   Safety, Guidelines, Output, Success Criteria, Deliverables.
#
# Run:
#   pip install flask pyyaml openai
#   (optional) export OPENAI_API_KEY=sk-...
#   python gui_manager.py
#
# UI: http://127.0.0.1:5057

from __future__ import annotations

import json
import os
import re
import shutil
import time
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Any, Dict, Tuple, Optional

import yaml
from flask import Flask, request, render_template_string, jsonify

# Loads variables from .env into os.environ
load_dotenv()

# Optional OpenAI
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

APP = Flask(__name__)
APP.config["JSON_SORT_KEYS"] = False

ROOT = os.path.abspath(os.path.dirname(__file__))
MCP_JSON_PATH = os.path.join(ROOT, "warp_config", "warp-mcp-config.yaml")
AGENTS_YAML_PATH = os.path.join(ROOT, "warp_config", "warp-agent-config.yaml")
ROUTER_PY_PATH = os.path.join(ROOT, "router_mcp.py")


# ---------------------------
# File helpers
# ---------------------------

def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text_atomic(path: str, content: str) -> None:
    ts = time.strftime("%Y%m%d-%H%M%S")
    if os.path.exists(path):
        shutil.copy2(path, f"{path}.bak.{ts}")
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


def load_yaml_or_json(path: str) -> Any:
    if not os.path.exists(path):
        return {}
    raw = read_text(path).strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return yaml.safe_load(raw)


def dump_json_pretty(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def dump_yaml(data: Any) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


# ---------------------------
# Name normalization
# ---------------------------

def to_kebab(name: str) -> str:
    s = re.sub(r"[\s_]+", "-", name.strip())
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", s)
    s = s.lower()
    s = re.sub(r"[^a-z0-9\-]+", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def to_title(name: str) -> str:
    parts = re.split(r"[\s\-_]+", name.strip())
    return "".join(p.capitalize() for p in parts if p)


# ---------------------------
# Agent profile scaffolding
# ---------------------------

AGENT_TEMPLATE = lambda TitleName: {
    "name": TitleName,
    "description": f"A sub-agent named {TitleName}. Customize description.",
    "system_prompt": f"""You are {TitleName}, a specialized sub-agent.
- Scope: Describe what this agent does (and does NOT do).
- Inputs: Clarify any required inputs.
- Guardrails: State safety, least-privilege, and out-of-scope behaviors.
- Tooling: If applicable, specify which MCP server(s) to call and when.
""",
    "permissions": {
        "allow_file_write": False,
        "allow_file_read": True,
        "allow_command_execution": False,
        "allowed_mcp_servers": []
    }
}


def add_agent_profile(agent_config: Dict[str, Any], title_name: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    profiles = agent_config.get("profiles")
    if profiles is None:
        profiles = []
        agent_config["profiles"] = profiles
    for p in profiles:
        if str(p.get("name", "")).strip().lower() == title_name.strip().lower():
            return agent_config, p
    block = AGENT_TEMPLATE(title_name)
    profiles.append(block)
    return agent_config, block


# ---------------------------
# Router MCP patching
# ---------------------------

@dataclass
class RouterPatchPreview:
    found_sub_agents: bool
    found_rule_titles: bool
    sub_agents_new: Optional[str]
    rule_titles_new: Optional[str]
    before_after: Optional[str]


def patch_router_mcp(router_src: str, agent_title: str, rule_title: str) -> RouterPatchPreview:
    sub_agents_pat = r"(SUB_AGENTS\s*=\s*\{[^}]*\})"
    rule_titles_pat = r"(RULE_TITLES\s*=\s*\{[^}]*\})"
    sub_m = re.search(sub_agents_pat, router_src, re.DOTALL)
    rule_m = re.search(rule_titles_pat, router_src, re.DOTALL)
    found_sub = sub_m is not None
    found_rule = rule_m is not None
    updated_src = router_src
    sub_new = None
    rule_new = None
    if found_sub:
        block = sub_m.group(1)
        if re.search(rf'["\']{re.escape(agent_title)}["\']', block) is None:
            new_block = re.sub(r"\}\s*$", f'    "{agent_title}",\n}}', block, flags=re.DOTALL)
            updated_src = updated_src.replace(block, new_block)
            sub_new = new_block
    if found_rule:
        block = rule_m.group(1)
        if re.search(rf'["\']{re.escape(agent_title)}["\']\s*:', block) is None:
            insertion = f'    "{agent_title}": "{rule_title}",\n'
            new_block = re.sub(r"\}\s*$", insertion + "}", block, flags=re.DOTALL)
            updated_src = updated_src.replace(block, new_block)
            rule_new = new_block
    before_after = None
    if updated_src != router_src:
        before_after = diff_preview(router_src, updated_src)
    return RouterPatchPreview(found_sub, found_rule, sub_new, rule_new, before_after)


def diff_preview(old: str, new: str, ctx: int = 4) -> str:
    import difflib
    diff = difflib.unified_diff(
        old.splitlines(True),
        new.splitlines(True),
        fromfile="router_mcp.py (old)",
        tofile="router_mcp.py (new)",
        n=ctx
    )
    return "".join(diff)


def apply_patch_again(src: str, agent_title: str, rule_title: str) -> str:
    sub_agents_pat = r"(SUB_AGENTS\s*=\s*\{[^}]*\})"
    rule_titles_pat = r"(RULE_TITLES\s*=\s*\{[^}]*\})"
    out = src
    sub_m = re.search(sub_agents_pat, out, re.DOTALL)
    if sub_m:
        block = sub_m.group(1)
        if re.search(rf'["\']{re.escape(agent_title)}["\']', block) is None:
            new_block = re.sub(r"\}\s*$", f'    "{agent_title}",\n}}', block, flags=re.DOTALL)
            out = out.replace(block, new_block)
    rule_m = re.search(rule_titles_pat, out, re.DOTALL)
    if rule_m:
        block = rule_m.group(1)
        if re.search(rf'["\']{re.escape(agent_title)}["\']\s*:', block) is None:
            new_block = re.sub(r"\}\s*$", f'    "{agent_title}": "{rule_title}",\n}}', block, flags=re.DOTALL)
            out = out.replace(block, new_block)
    return out


# ---------------------------
# Policy name heuristics
# ---------------------------

def policy_name_for_title(title_name: str) -> str:
    t = title_name.lower()
    if "ux" in t or "research" in t: return "Research Artifacts Policy"
    if "design" in t or "ui" in t and "front" not in t: return "Design Artifacts Policy"
    if "front" in t: return "UI Policy"
    if "back" in t or "api" in t or "service" in t: return "API & Services Policy"
    if "file" in t: return "File Ops Policy"
    if "git" in t: return "Safe Git Policy"
    if "test" in t: return "Testing Policy"
    if "proto" in t or "rapid" in t: return "Prototype Policy"
    if "sprint" in t or "priorit" in t: return "Planning Policy"
    if "router" in t or "taskrouter" in t: return "Orchestrator Policy"
    return f"{title_name} Policy"


# ---------------------------
# Rule generation
# ---------------------------

SECTIONS_ORDER = [
    "Role",
    "Scope",
    "Strict Prohibitions",
    "Allowed Tools",
    "Method & Equity",
    "Design & Security",
    "Quality",
    "Accessibility (WCAG AA)",
    "Spec Alignment",
    "Safety",
    "Guidelines",
    "Output",
    "Success Criteria",
    "Deliverables",
]

LOCAL_RULE_BODY = """Role:
- State this agent’s mission in one sentence.

Scope:
- Enumerate activities this agent is responsible for.

Strict Prohibitions:
- Call out activities the agent must NOT perform.

Allowed Tools:
- List MCP servers/tools this agent may call and for what.

Method & Equity:
- Note inclusive research/practices and representative sampling where relevant.

Design & Security:
- Call out secure defaults, privacy hygiene, and design/system constraints.

Quality:
- Define “good” (readability, maintainability, testability, etc.).

Accessibility (WCAG AA):
- Landmarks, keyboard nav, color contrast, aria-labels/roles, error states, focus order.

Spec Alignment:
- Follow `/project/docs/site-spec.md` when present (anchors, back-links, nav consistency).

Safety:
- Avoid destructive operations; least privilege; explain risky actions before proceeding.

Guidelines:
- Any coding/style/UX standards specific to your team.

Output:
- Where to write artifacts in /project, filename conventions, and what to return.

Success Criteria:
- What constitutes “done” for this agent’s tasks.

Deliverables:
- Concrete files/changes this agent will produce.
"""


def ai_generate_rule(title_name: str, user_notes: str) -> str:
    """
    Returns a plain-text rule starting with:
      "<TitleName> — <PolicyName>"
    followed by ordered sections in SECTIONS_ORDER.
    Uses OpenAI if available; otherwise falls back to a local scaffold.
    """
    policy_name = policy_name_for_title(title_name)

    # Attempt AI refinement
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key and OpenAI is not None:
        try:
            client = OpenAI(api_key=api_key)
            sys_msg = (
                    "You draft operational rules for Warp agent profiles. "
                    "Output plain text (no Markdown). Start with a single title line: "
                    f"\"{title_name} — {policy_name}\" then include the following sections in EXACT order, "
                    "each as a header line followed by succinct bullet points: "
                    + ", ".join(SECTIONS_ORDER) + ". "
                                                  "Keep it concise, actionable, and aligned with least-privilege and safety."
            )
            user_msg = (
                f"Agent name: {title_name}\n"
                f"Policy title: {title_name} — {policy_name}\n"
                f"Context/notes:\n{user_notes}\n\n"
                "Include these specifics where relevant:\n"
                "- Accessibility (WCAG AA) requirements\n"
                "- Spec Alignment to `/project/docs/site-spec.md` (anchors, back-links, nav consistency)\n"
                "- What tools (MCP servers) are allowed and when\n"
                "- Clear success criteria and deliverables\n"
            )
            resp = client.chat.completions.create(
                model="gpt-5-chat-latest",
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.3,
            )
            text = resp.choices[0].message.content.strip()
            # Ensure first line has the expected titled policy; if not, prefix it
            first = text.splitlines()[0].strip() if text else ""
            titled = f"{title_name} — {policy_name}"
            if not first or titled.lower() not in first.lower():
                text = titled + "\n\n" + text
            return text
        except Exception:
            pass  # fall through to local scaffold

    # Local scaffold
    titled = f"{title_name} — {policy_name}"
    return f"{titled}\n\n{LOCAL_RULE_BODY}"


# ---------------------------
# HTML (with Copy button for MCP JSON)
# ---------------------------

HTML = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Warp Orchestrator — GUI</title>
  <style>
    body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; margin: 24px; color: #111; }
    h1 { margin-bottom: 8px; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    textarea, input[type=text] { width: 100%; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, Monaco, monospace; }
    textarea { min-height: 200px; padding: 8px; border: 1px solid #ccc; border-radius: 8px; }
    input[type=text] { padding: 8px; border: 1px solid #ccc; border-radius: 8px; }
    .card { border: 1px solid #ddd; border-radius: 10px; padding: 16px; background: #fafafa; }
    .btn { padding: 8px 12px; border-radius: 8px; border: 1px solid #444; background: #111; color: white; cursor: pointer; }
    .btn.secondary { background: white; color: #111; }
    .ok { color: #058; }
    .err { color: #b00; white-space: pre-wrap; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, Monaco, monospace; white-space: pre; background: #fff; border: 1px solid #ddd; padding: 8px; border-radius: 8px; }
    .small { font-size: 12px; color: #555; }
    .grid2 { display: grid; grid-template-columns: 220px 1fr auto; gap: 8px; align-items: center; }
  </style>
  <script>
    function copyById(id) {
      const el = document.getElementById(id);
      el.select(); el.setSelectionRange(0, 99999);
      const ok = document.execCommand('copy');
      const btn = document.getElementById(id + '_copy_btn');
      if (btn) { btn.textContent = ok ? 'Copied!' : 'Copy failed'; setTimeout(()=>btn.textContent='Copy',1200); }
    }
    function validateJSON() {
      const el = document.getElementById('mcp_json');
      const err = document.getElementById('json_err');
      try {
        JSON.parse(el.value);
        err.textContent = "OK: Valid JSON";
        err.className = "ok small";
      } catch (e) {
        err.textContent = "JSON Error: " + e.message;
        err.className = "err small";
      }
    }
    function toKebab() {
      const name = document.getElementById('agent_name').value;
      fetch('/to_kebab?name=' + encodeURIComponent(name))
        .then(r => r.json()).then(d => {
          document.getElementById('name_preview').textContent =
            'agent-name: ' + d.kebab + '   |   Title: ' + d.title;
        });
    }
    async function genRule() {
      const name = document.getElementById('agent_name').value;
      const notes = document.getElementById('rule_notes').value;
      const btn = document.getElementById('btn_gen');
      btn.disabled = true; btn.textContent = 'Generating...';
      const r = await fetch('/ai_rule', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name, notes })
      });
      const j = await r.json();
      btn.disabled = false; btn.textContent = 'AI: Generate/Refine Rule';
      document.getElementById('rule_text').value = j.text || '';
    }
    async function saveMcp() {
      const name = document.getElementById('agent_name').value;
      const jsonText = document.getElementById('mcp_json').value;
      const r = await fetch('/save_mcp', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name, mcp_json: jsonText })
      });
      const j = await r.json();
      const out = document.getElementById('mcp_result');
      out.className = j.ok ? 'ok' : 'err';
      out.textContent = j.msg;
    }
    async function addProfile() {
      const name = document.getElementById('agent_name').value;
      const r = await fetch('/add_profile', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name })
      });
      const j = await r.json();
      document.getElementById('profile_preview').textContent = j.preview || '';
      const out = document.getElementById('profile_result');
      out.className = j.ok ? 'ok' : 'err';
      out.textContent = j.msg || '';
    }
    async function patchRouter() {
      const name = document.getElementById('agent_name').value;
      const rule = document.getElementById('rule_text').value;
      const r = await fetch('/patch_router', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name, rule })
      });
      const j = await r.json();
      document.getElementById('router_diff').textContent = j.diff || '';
      const out = document.getElementById('router_result');
      out.className = j.ok ? 'ok' : 'err';
      out.textContent = j.msg || '';
    }
  </script>
</head>
<body>
  <h1>Warp Orchestrator — GUI</h1>
  <p class="small">Root: {{root}}</p>

  <div class="card">
    <div class="grid2">
      <label>Agent Name (e.g., FileCreator)</label>
      <input type="text" id="agent_name" oninput="toKebab()" placeholder="FileCreator"/>
      <span id="name_preview" class="mono small">agent-name: —</span>
    </div>
  </div>

  <div class="row" style="margin-top:16px;">
    <div class="card">
      <h3>1) Add MCP Server JSON</h3>
      <div class="grid2">
        <span class="small">Paste JSON below</span>
        <span></span>
        <button id="mcp_json_copy_btn" class="btn secondary" onclick="copyById('mcp_json')">Copy</button>
      </div>
      <textarea id="mcp_json" oninput="validateJSON()" placeholder='{"file-mcp": { "type":"stdio", "command":"node", "args":["..."] }}'></textarea>
      <p id="json_err" class="small">Paste JSON to validate…</p>
      <button class="btn" onclick="saveMcp()">Save MCP → warp-mcp-config.yaml</button>
      <p id="mcp_result" class="small"></p>
    </div>

    <div class="card">
      <h3>2) Create/Refine Rule (plain text; starts with “Title — Policy”)</h3>
      <textarea id="rule_notes" placeholder="Optional: describe capabilities, guardrails, deliverables…"></textarea>
      <button id="btn_gen" class="btn secondary" onclick="genRule()" style="margin: 20px 0 10px 0;">AI: Generate/Refine Rule</button>
      <textarea id="rule_text" placeholder="Final rule text (plain, no markdown). Paste to Warp → Rules."></textarea>
      <p class="small">The first line will be like: <code>UXResearcher — Research Artifacts Policy</code></p>
    </div>
  </div>

  <div class="row" style="margin-top:16px;">
    <div class="card">
      <h3>3) Add Agent Profile → warp-agent-config.yaml</h3>
      <button class="btn" onclick="addProfile()">Add Profile (Preview + Save)</button>
      <pre id="profile_preview" class="mono" style="min-height:160px;"></pre>
      <p id="profile_result" class="small"></p>
    </div>

    <div class="card">
      <h3>4) Patch router_mcp.py (SUB_AGENTS + RULE_TITLES)</h3>
      <button class="btn" onclick="patchRouter()">Patch Router (Preview + Save)</button>
      <pre id="router_diff" class="mono" style="min-height:160px;"></pre>
      <p id="router_result" class="small"></p>
    </div>
  </div>

  <p class="small">Backups are created as <code>.bak.YYYYMMDD-HHMMSS</code> next to each file before writing.</p>
</body>
</html>
"""


# ---------------------------
# Flask routes
# ---------------------------

@APP.get("/")
def home():
    return render_template_string(HTML, root=ROOT)


@APP.get("/to_kebab")
def api_to_kebab():
    name = request.args.get("name", "").strip() or "NewAgent"
    return jsonify({"kebab": to_kebab(name), "title": to_title(name)})


@APP.post("/ai_rule")
def api_ai_rule():
    data = request.get_json(force=True)
    title = to_title(data.get("name", "NewAgent"))
    notes = data.get("notes", "").strip()
    text = ai_generate_rule(title, notes)
    return jsonify({"text": text})


@APP.post("/save_mcp")
def api_save_mcp():
    data = request.get_json(force=True)
    text = data.get("mcp_json", "")
    # validate JSON
    try:
        mcp_obj = json.loads(text)
        if not isinstance(mcp_obj, dict):
            raise ValueError("Root must be an object")
    except Exception as e:
        return jsonify({"ok": False, "msg": f"JSON invalid: {e}"}), 400
    try:
        existing = load_yaml_or_json(MCP_JSON_PATH) or {}
        if not isinstance(existing, dict):
            existing = {}
    except Exception:
        existing = {}
    merged = {**existing}
    for k, v in mcp_obj.items():
        merged[k] = v
    try:
        write_text_atomic(MCP_JSON_PATH, dump_json_pretty(merged))
        return jsonify({"ok": True, "msg": f"MCP servers updated → {MCP_JSON_PATH}"})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Write failed: {e}"}), 500


@APP.post("/add_profile")
def api_add_profile():
    data = request.get_json(force=True)
    title = to_title(data.get("name", "NewAgent"))
    try:
        agent_cfg = yaml.safe_load(read_text(AGENTS_YAML_PATH)) if os.path.exists(AGENTS_YAML_PATH) else {}
        agent_cfg = agent_cfg or {}
        new_cfg, block = add_agent_profile(agent_cfg, title)
        preview = dump_yaml(block)
        if new_cfg != agent_cfg:
            write_text_atomic(AGENTS_YAML_PATH, dump_yaml(new_cfg))
        return jsonify({"ok": True, "preview": preview, "msg": f"Profile ensured/added → {AGENTS_YAML_PATH}"})
    except Exception as e:
        return jsonify({"ok": False, "preview": "", "msg": f"Error: {e}"}), 500


@APP.post("/patch_router")
def api_patch_router():
    data = request.get_json(force=True)
    title = to_title(data.get("name", "NewAgent"))
    rule_text = (data.get("rule") or "").strip()
    # Determine rule title for RULE_TITLES: prefer first line of provided rule; else synthesize
    first_line = rule_text.splitlines()[0].strip() if rule_text else ""
    if "—" in first_line and first_line.lower().startswith(title.lower()):
        rule_title = first_line
    else:
        rule_title = f"{title} — {policy_name_for_title(title)}"
    try:
        src = read_text(ROUTER_PY_PATH)
        preview = patch_router_mcp(src, title, rule_title)
        if not (preview.found_sub_agents and preview.found_rule_titles):
            return jsonify({
                               "ok": False, "diff": preview.before_after or "",
                               "msg": "Could not find SUB_AGENTS and/or RULE_TITLES blocks in router_mcp.py"
                           }), 400
        if preview.before_after:
            patched = apply_patch_again(src, title, rule_title)
            write_text_atomic(ROUTER_PY_PATH, patched)
            return jsonify({
                               "ok": True, "diff": preview.before_after,
                               "msg": f"router_mcp.py patched (SUB_AGENTS + RULE_TITLES) → {ROUTER_PY_PATH}"
                           })
        else:
            return jsonify({"ok": True, "diff": "", "msg": "No changes needed; entries already present."})
    except Exception as e:
        return jsonify({"ok": False, "diff": "", "msg": f"Error: {e}"}), 500


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("MCP_MANAGER_GUI_PORT"))
    APP.run(host="127.0.0.1", port=port, debug=True, use_reloader=True)

