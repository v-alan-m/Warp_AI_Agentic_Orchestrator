# mcp_gui_manager.py
# Local GUI to add MCP servers, AI-generate Rules (no local fallback),
# add new agent Profiles (with live YAML view), and patch router_mcp.py
# with live views of SUB_AGENTS and RULE_TITLES.
#
# This version:
# - Uses fixed RULES_DIR = ./warp_config/warp_rules
# - Header shows the active rules directory path
# - “(Context: N rules)” includes a dropdown of rule files  preview textarea
# - AI-only rule creation (requires OPENAI_API_KEY; model gpt-5-chat-latest)
# - Live view of warp-agent-config.yaml  live views of SUB_AGENTS and RULE_TITLES
# - FIX: SUB_AGENTS patch now writes `"TitleName": "kebab-title"` (not just `"TitleName",`)
#
# Run:
#   pip install flask pyyaml openai python-dotenv
#   export OPENAI_API_KEY=sk-...
#   python mcp_gui_manager.py
#
# UI: http://127.0.0.1:5057  (override port with MCP_MANAGER_GUI_PORT)

from __future__ import annotations
import os, re, json, time, shutil, glob, difflib
from dataclasses import dataclass
from typing import Any, Dict, Tuple, Optional

import yaml
from flask import Flask, request, render_template_string, jsonify

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

# OpenAI (required for rule generation)
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

# Fixed rules directory (your canonical location)
RULES_DIR = os.path.join(ROOT, "warp_config", "warp_rules")


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
    s = re.sub(r"[\s_]", "-", name.strip())
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", s)
    s = s.lower()
    s = re.sub(r"[^a-z0-9\-]", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def to_title(name: str) -> str:
    parts = re.split(r"[\s\-_]", name.strip())
    return "".join(p.capitalize() for p in parts if p)


# ---------------------------
# Load prior rules (context)
# ---------------------------

def load_rule_corpus() -> Tuple[int, str]:
    """
    Returns (count, combined_text) of prior rules from RULES_DIR.
    """
    if not os.path.isdir(RULES_DIR):
        return 0, ""
    paths = sorted(glob.glob(os.path.join(RULES_DIR, "*.md")))
    blocks = []
    for p in paths:
        try:
            txt = read_text(p).strip()
            if txt:
                blocks.append(f"# FILE: {os.path.basename(p)}\n{txt}")
        except Exception:
            continue
    combined = "\n\n\n".join(blocks)
    return len(blocks), combined


def list_rule_files() -> list[str]:
    if not os.path.isdir(RULES_DIR):
        return []
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(RULES_DIR, "*.md")))


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


def _extract_block(src: str, varname: str) -> Optional[str]:
    m = re.search(rf"({varname}\s*=\s*\{{[^}}]*\}})", src, re.DOTALL)
    return m.group(1) if m else None


def extract_subagents_and_ruletitles(src: str) -> Tuple[str, str]:
    sub = _extract_block(src, "SUB_AGENTS") or "SUB_AGENTS = {\n}\n"
    rtl = _extract_block(src, "RULE_TITLES") or "RULE_TITLES = {\n}\n"
    return sub, rtl


def patch_router_mcp(router_src: str, agent_title: str, rule_title: str) -> RouterPatchPreview:
    """
    Insert into:
      SUB_AGENTS:   "Title": "kebab-title",
      RULE_TITLES:  "Title": "Title — Policy",
    only if missing.
    """
    sub_agents_pat = r"(SUB_AGENTS\s*=\s*\{[^}]*\})"
    rule_titles_pat = r"(RULE_TITLES\s*=\s*\{[^}]*\})"
    sub_m = re.search(sub_agents_pat, router_src, re.DOTALL)
    rule_m = re.search(rule_titles_pat, router_src, re.DOTALL)
    found_sub = sub_m is not None
    found_rule = rule_m is not None
    updated_src = router_src
    sub_new = None
    rule_new = None

    kebab = to_kebab(agent_title)

    if found_sub:
        block = sub_m.group(1)
        # Check key presence like  "Title":
        if re.search(rf'["\']{re.escape(agent_title)}["\']\s*:', block) is None:
            insertion = f'    "{agent_title}": "{kebab}",\n'
            new_block = re.sub(r"\}\s*$", insertion + "}", block, flags=re.DOTALL)
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
        diff = difflib.unified_diff(
            router_src.splitlines(True),
            updated_src.splitlines(True),
            fromfile="router_mcp.py (old)",
            tofile="router_mcp.py (new)",
            n=4
        )
        before_after = "".join(diff)
    return RouterPatchPreview(found_sub, found_rule, sub_new, rule_new, before_after)


def apply_patch_again(src: str, agent_title: str, rule_title: str) -> str:
    """
    Apply the same logic directly (used after preview).
    """
    sub_agents_pat = r"(SUB_AGENTS\s*=\s*\{[^}]*\})"
    rule_titles_pat = r"(RULE_TITLES\s*=\s*\{[^}]*\})"
    out = src
    kebab = to_kebab(agent_title)

    sub_m = re.search(sub_agents_pat, out, re.DOTALL)
    if sub_m:
        block = sub_m.group(1)
        if re.search(rf'["\']{re.escape(agent_title)}["\']\s*:', block) is None:
            new_block = re.sub(r"\}\s*$", f'    "{agent_title}": "{kebab}",\n}}', block, flags=re.DOTALL)
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
    if "design" in t or ("ui" in t and "front" not in t): return "Design Artifacts Policy"
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
# Rule generation (AI only)
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


def ai_generate_rule(title_name: str, user_notes: str, prior_rules_text: str) -> str:
    """
    Returns a plain-text rule starting with:
      "<TitleName> — <PolicyName>"
    followed by ordered sections in SECTIONS_ORDER.
    Requires OpenAI + OPENAI_API_KEY; no local fallback.
    """
    if OpenAI is None or not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY missing or OpenAI SDK not available")

    policy_name = policy_name_for_title(title_name)
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    sys_msg = (
            "You draft operational rules for Warp agent profiles. "
            "Output plain text (no Markdown). Start with a single title line: "
            f"\"{title_name} — {policy_name}\" then include the following sections in EXACT order, "
            "each as a header line followed by succinct bullet points: "
            + ", ".join(SECTIONS_ORDER) + ". "
                                          "Keep it concise, actionable, least-privilege, and safe."
    )

    user_msg = (
        f"Agent name: {title_name}\n"
        f"Policy title: {title_name} — {policy_name}\n"
        f"User notes:\n{user_notes}\n\n"
        "Prior Rules Context (verbatim):\n"
        f"{prior_rules_text}\n"
        "Include these specifics where relevant:\n"
        "- Accessibility (WCAG AA) requirements\n"
        "- Spec Alignment to `/project/docs/site-spec.md` (anchors, back-links, nav consistency)\n"
        "- What tools (MCP servers) are allowed and when\n"
        "- Clear success criteria and deliverables\n"
    )

    resp = client.chat.completions.create(
        model="gpt-5-chat-latest",
        messages=[{"role": "system", "content": sys_msg},
                  {"role": "user", "content": user_msg}],
        temperature=0.3,
    )
    text = resp.choices[0].message.content.strip()
    titled = f"{title_name} — {policy_name}"
    if not text.splitlines():
        raise RuntimeError("Model returned empty text")
    first = text.splitlines()[0].strip()
    if titled.lower() not in first.lower():
        text = titled + "\n\n" + text
    return text


# ---------------------------
# HTML
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
    .row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    textarea, input[type=text] { width: 100%; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, Monaco, monospace; }
    textarea { min-height: 200px; padding: 8px; border: 1px solid #ccc; border-radius: 8px; }
    input[type=text] { padding: 8px; border: 1px solid #ccc; border-radius: 8px; }
    .card { border: 1px solid #ddd; border-radius: 10px; padding: 16px; background: #fafafa; margin-bottom: 16px; }
    .btn { padding: 8px 12px; border-radius: 8px; border: 1px solid #444; background: #111; color: white; cursor: pointer; }
    .btn.secondary { background: white; color: #111; }
    .ok { color: #058; }
    .err { color: #b00; white-space: pre-wrap; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, Monaco, monospace; white-space: pre; background: #fff; border: 1px solid #ddd; padding: 8px; border-radius: 8px; }
    .small { font-size: 12px; color: #555; }
    .grid2 { display: grid; grid-template-columns: auto 1fr auto; gap: 8px; align-items: center; }
    .grid3 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
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
    async function refreshRulesMeta() {
      const r = await fetch('/rules_meta');
      const j = await r.json();
      document.getElementById('rules_loaded').textContent = '(Context: ' + j.count + ' rules)';
      document.getElementById('active_rules_dir').textContent = j.dir || '';
      const sel = document.getElementById('rules_select');
      sel.innerHTML = '';
      (j.files || []).forEach(name => {
        const opt = document.createElement('option');
        opt.value = name; opt.textContent = name;
        sel.appendChild(opt);
      });
      if ((j.files || []).length > 0) {
        loadRuleText(sel.value);
      } else {
        document.getElementById('rules_view').value = '';
      }
    }
    async function loadRuleText(name) {
      if (!name) return;
      const r = await fetch('/rule_text?name=' + encodeURIComponent(name));
      const j = await r.json();
      document.getElementById('rules_view').value = j.text || '';
    }
    async function genRule() {
      const name = document.getElementById('agent_name').value;
      const notes = document.getElementById('rule_notes').value;
      const btn = document.getElementById('btn_gen');
      const out = document.getElementById('rule_result');
      btn.disabled = true; btn.textContent = 'Generating...';
      out.textContent = '';
      const r = await fetch('/ai_rule', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name, notes })
      });
      const j = await r.json();
      btn.disabled = false; btn.textContent = 'AI: Generate/Refine Rule';
      if (j.ok) {
        document.getElementById('rule_text').value = j.text || '';
      } else {
        out.className = 'err small';
        out.textContent = j.msg || 'Error';
      }
    }
    async function refreshMcpPreview() {
      const r = await fetch('/get_mcp');
      const j = await r.json();
      document.getElementById('mcp_preview').value = j.text || '';
    }
    async function saveMcp() {
      const jsonText = document.getElementById('mcp_json').value;
      const r = await fetch('/save_mcp', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ mcp_json: jsonText })
      });
      const j = await r.json();
      const out = document.getElementById('mcp_result');
      out.className = j.ok ? 'ok small' : 'err small';
      out.textContent = j.msg;
    }
    async function addProfile() {
      const name = document.getElementById('agent_name').value;
      const r = await fetch('/add_profile', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name })
      });
      const j = await r.json();
      const out = document.getElementById('profile_result');
      document.getElementById('profile_preview').textContent = j.preview || '';
      out.className = j.ok ? 'ok small' : 'err small';
      out.textContent = j.msg || '';
      if (j.ok && j.text) {
        document.getElementById('mcp_preview').value = j.text;
      }
      refreshAgentYaml();
    }
    async function refreshAgentYaml() {
      const r = await fetch('/get_agent_yaml');
      const j = await r.json();
      document.getElementById('agent_yaml_text').value = j.text || '';
    }
    async function patchRouter() {
      const name = document.getElementById('agent_name').value;
      const rule = document.getElementById('rule_text').value;
      const r = await fetch('/patch_router', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name, rule })
      });
      const j = await r.json();
      const out = document.getElementById('router_result');
      out.className = j.ok ? 'ok small' : 'err small';
      out.textContent = j.msg || '';
      refreshRouterBlocks();
    }
    async function refreshRouterBlocks() {
      const r = await fetch('/get_router_blocks');
      const j = await r.json();
      document.getElementById('sub_agents_box').value = j.sub_agents || '';
      document.getElementById('rule_titles_box').value = j.rule_titles || '';
    }
    window.addEventListener('DOMContentLoaded', ()=>{
      refreshMcpPreview();
      refreshRulesMeta();
      refreshAgentYaml();
      refreshRouterBlocks();
      const sel = document.getElementById('rules_select');
      if (sel) sel.addEventListener('change', ()=>loadRuleText(sel.value));
    });
  </script>
</head>
<body>
  <h1>Warp Orchestrator — GUI</h1>
  <p class="small">
    Root: {{root}}<br/>
    Rules dir: <span id="active_rules_dir">{{rules_dir}}</span>
  </p>

  <!-- TOP: MCP servers -->
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
    <h4 class="small">Current warp-mcp-config.yaml</h4>
    <textarea id="mcp_preview" readonly></textarea>
  </div>

  <!-- BOTTOM: Agent + Profile + Rule + Router -->
  <div class="card">
    <div class="grid2">
      <label>Agent Name (e.g., FileCreator)</label>
      <input type="text" id="agent_name" oninput="toKebab()" placeholder="FileCreator"/>
      <span id="name_preview" class="mono small">agent-name: —</span>
    </div>
  </div>

  <div class="row2">
    <div class="card">
      <h3>2) Add Agent Profile → warp-agent-config.yaml</h3>
      <button class="btn" onclick="addProfile()">Add Profile (Preview + Save)</button>
      <pre id="profile_preview" class="mono" style="min-height:120px;"></pre>
      <p id="profile_result" class="small"></p>
      <h4 class="small">Current warp-agent-config.yaml</h4>
      <textarea id="agent_yaml_text" readonly></textarea>
    </div>

    <div class="card">
      <h3>3) Create/Refine Rule (plain text; starts with “Title — Policy”)
        <span id="rules_loaded" class="small" style="margin-left:8px;"></span>
      </h3>
      <div class="grid2" style="margin-bottom:8px;">
        <span class="small">Preview existing rule:</span>
        <select id="rules_select"></select>
        <span></span>
      </div>
      <textarea id="rules_view" readonly placeholder="Select a rule to preview its text…"></textarea>
      <textarea id="rule_notes" placeholder="Optional: describe capabilities, guardrails, deliverables…"></textarea>
      <button id="btn_gen" class="btn secondary" onclick="genRule()" style="margin: 12px 0 0px 0;">AI: Generate/Refine Rule</button>
      <p id="rule_result" class="small"></p>
      <textarea id="rule_text" placeholder="Final rule text (plain, no markdown). Paste to Warp → Rules."></textarea>
      <p class="small">First line example: <code>UXResearcher — Research Artifacts Policy</code></p>
    </div>
  </div>

  <div class="card">
    <h3>4) Patch router_mcp.py (live blocks)</h3>
    <button class="btn" onclick="patchRouter()">Patch Router (Preview + Save)</button>
    <p id="router_result" class="small"></p>
    <div class="grid3">
      <div>
        <h4 class="small">SUB_AGENTS (live)</h4>
        <textarea id="sub_agents_box" readonly></textarea>
      </div>
      <div>
        <h4 class="small">RULE_TITLES (live)</h4>
        <textarea id="rule_titles_box" readonly></textarea>
      </div>
    </div>
  </div>

  <p class="small">Backups saved as <code>.bak.YYYYMMDD-HHMMSS</code> before writes.</p>
</body>
</html>
"""


# ---------------------------
# Flask routes
# ---------------------------

@APP.get("/")
def home():
    return render_template_string(HTML, root=ROOT, rules_dir=RULES_DIR)


@APP.get("/to_kebab")
def api_to_kebab():
    name = request.args.get("name", "").strip() or "NewAgent"
    return jsonify({"kebab": to_kebab(name), "title": to_title(name)})


@APP.get("/rules_meta")
def api_rules_meta():
    if not os.path.isdir(RULES_DIR):
        return jsonify({"dir": RULES_DIR, "count": 0, "files": []})
    files = list_rule_files()
    return jsonify({"dir": RULES_DIR, "count": len(files), "files": files})


@APP.get("/rule_text")
def api_rule_text():
    name = request.args.get("name", "").strip()
    safe = re.match(r"^[\w\-. ]+\.md$", name or "")
    path = os.path.join(RULES_DIR, name) if safe else None
    if not (path and os.path.isfile(path)):
        return jsonify({"text": ""})
    try:
        return jsonify({"text": read_text(path)})
    except Exception as e:
        return jsonify({"text": f"# Error reading rule: {e}"})


# Back-compat: still provide simple count
@APP.get("/rules_count")
def api_rules_count():
    cnt, _ = load_rule_corpus()
    return jsonify({"count": cnt})


@APP.get("/get_agent_yaml")
def api_get_agent_yaml():
    try:
        text = read_text(AGENTS_YAML_PATH) if os.path.exists(AGENTS_YAML_PATH) else ""
    except Exception as e:
        text = f"# Error reading {AGENTS_YAML_PATH}: {e}"
    return jsonify({"text": text})


@APP.get("/get_router_blocks")
def api_get_router_blocks():
    try:
        src = read_text(ROUTER_PY_PATH) if os.path.exists(ROUTER_PY_PATH) else ""
        sub, rtl = extract_subagents_and_ruletitles(src) if src else ("", "")
    except Exception as e:
        sub, rtl = (f"# Error: {e}", "")
    return jsonify({"sub_agents": sub, "rule_titles": rtl})


@APP.post("/ai_rule")
def api_ai_rule():
    data = request.get_json(force=True)
    title = to_title(data.get("name", "NewAgent"))
    notes = data.get("notes", "").strip()
    cnt, corpus = load_rule_corpus()
    try:
        text = ai_generate_rule(title, notes, corpus)
        return jsonify({"ok": True, "text": text, "context_rules": cnt})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e), "context_rules": cnt}), 400


def _normalize_mcp_payload(text: str) -> Dict[str, Any]:
    """
    Accept either:
      A) {"MyServer": {...}, "OtherServer": {...}}
      B) {"mcpServers": { "MyServer": {...} }}
    Return always the *servers mapping* (not wrapped).
    """
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("Top-level JSON must be an object.")

    # Wrapped payload form
    if "mcpServers" in obj:
        servers = obj["mcpServers"]
        if not isinstance(servers, dict):
            raise ValueError('"mcpServers" must be an object mapping serverName → config')
        return servers

    # Bare payload form (preferred for GUI input)
    # If user pasted a single bare config (has 'command'/'type'), guide them.
    if ("command" in obj) or ("type" in obj):
        raise ValueError(
            'Provide a mapping like {"MyServer": { ...config... }} '
            'or wrap as {"mcpServers": { "MyServer": { ... } }}'
        )
    return obj


@APP.get("/get_mcp")
def api_get_mcp():
    try:
        text = read_text(MCP_JSON_PATH) if os.path.exists(MCP_JSON_PATH) else "{}"
    except Exception as e:
        text = f'{{"#error": "{e}"}}'
    return jsonify({"text": text})


@APP.post("/save_mcp")
def api_save_mcp():
    data = request.get_json(force=True)
    text = (data.get("mcp_json") or "").strip()
    try:
        incoming = _normalize_mcp_payload(text)
    except Exception as e:
        return jsonify({"ok": False, "msg": f"JSON invalid: {e}"}), 400
    # Load existing (supports YAML/JSON), ensure dict
    try:
        existing = load_yaml_or_json(MCP_JSON_PATH) or {}
        if not isinstance(existing, dict):
            existing = {}
    except Exception:
        existing = {}

    # --- Merge respecting Warp schema ---
    # If the file already uses the Warp schema { "mcpServers": { ... } },
    # merge into that inner object. Otherwise, treat the root as the servers map.
    result = None
    if "mcpServers" in existing and isinstance(existing["mcpServers"], dict):
        # Preserve any other top-level keys; only update mcpServers.
        result = dict(existing)  # shallow copy
        servers = dict(existing.get("mcpServers", {}))
        servers.update(incoming)
        result["mcpServers"] = servers
    else:
        # No warp schema present; keep flat mapping and merge at root.
        result = dict(existing)
        result.update(incoming)

    # Pretty-print full file and validate round-trip JSON
    pretty = dump_json_pretty(result)
    json.loads(pretty)  # round-trip validation
    try:
        write_text_atomic(MCP_JSON_PATH, pretty)
        count = len(result.get("mcpServers", result))  # number of servers merged
        return jsonify({"ok": True, "msg": f"MCP servers updated → {MCP_JSON_PATH}", "text": pretty, "count": count})
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
    # Prefer first line of rule if it starts with "<Title> — …"
    first = rule_text.splitlines()[0].strip() if rule_text else ""
    rule_title = first if ("—" in first and first.lower().startswith(
        title.lower())) else f"{title} — {policy_name_for_title(title)}"
    try:
        src = read_text(ROUTER_PY_PATH)
        preview = patch_router_mcp(src, title, rule_title)
        if not (preview.found_sub_agents and preview.found_rule_titles):
            return jsonify({
                "ok": False, "msg": "Could not find SUB_AGENTS and/or RULE_TITLES in router_mcp.py",
                "diff": preview.before_after or ""
            }), 400
        if preview.before_after:
            patched = apply_patch_again(src, title, rule_title)
            write_text_atomic(ROUTER_PY_PATH, patched)
            # Return updated blocks for live view
            sub, rtl = extract_subagents_and_ruletitles(patched)
            return jsonify({
                "ok": True,
                "msg": f"router_mcp.py patched (SUB_AGENTS + RULE_TITLES) → {ROUTER_PY_PATH}",
                "diff": preview.before_after, "sub_agents": sub, "rule_titles": rtl
            })
        else:
            # Still return current blocks
            sub, rtl = extract_subagents_and_ruletitles(src)
            return jsonify({
                "ok": True, "msg": "No changes needed; entries already present.", "diff": "",
                "sub_agents": sub, "rule_titles": rtl
            })
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Error: {e}", "diff": ""}), 500


if __name__ == "__main__":
    port = int(os.environ.get("MCP_MANAGER_GUI_PORT"))
    APP.run(host="127.0.0.1", port=port, debug=True, use_reloader=True)
