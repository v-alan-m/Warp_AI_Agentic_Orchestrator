# mcp_gui_manager.py
# Local GUI to add MCP servers, AI-generate Rules (no local fallback),
# add new agent Profiles (with live YAML view), and patch router_mcp.py
# with live views of SUB_AGENTS and RULE_TITLES.
#
# This version:
# - Uses fixed RULES_DIR = ./warp_config/warp_rules
# - Header shows the active rules directory path
# - “(Context: N rules)” includes a dropdown of rule files + preview textarea
# - AI-only rule creation (requires LLM_API_KEY; model gpt-5-chat-latest)
# - Live view of warp-mcp-config.yaml  (auto-polling)
# - Live view of warp-agent-config.yaml (auto-polling)
# - SUB_AGENTS patch writes `"TitleName": "kebab-title"`
# - Save MCP honors Warp schema ({ "mcpServers": { ... } }) and pretty-prints the whole file
# - Profile builder:
#     * Title, Model dropdown
#     * Bold checkboxes for permissions (Apply Code Diffs, Read Files)
#     * Bold dynamic checklist of MCP servers loaded from warp-mcp-config.yaml
#     * Notes auto-fills to: Rule "<TitleName> — <PolicyName>"
#     * Preview renders with two-space indent and '- name:' to match profiles list style
#
# Run:
#   pip install flask pyyaml openai python-dotenv
#   export LLM_API_KEY=sk-...
#   python mcp_gui_manager.py
#
# UI: http://127.0.0.1:5057  (override port with MCP_MANAGER_GUI_PORT)

from __future__ import annotations
import os, re, json, time, shutil, glob, difflib
from dataclasses import dataclass
from typing import Any, Dict, Tuple, Optional, List

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
    s = re.sub(r"[\s_]+", "-", name.strip())
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", s)
    s = s.lower()
    s = re.sub(r"[^a-z0-9\-]+", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def to_title(name: str) -> str:
    """
    Normalize to a Title/PascalCase label while preserving existing inner capitals.
    - "file creator" -> "FileCreator"
    - "file_creator" -> "FileCreator"
    - "fileCreator"  -> "FileCreator"
    - "FileCreator"  -> "FileCreator" (unchanged)
    """
    s = name.strip()
    if not s:
       return ""
    words = [w for w in re.split(r"[\s\-_]+", s) if w]
    if len(words) >= 2:
       # Capitalize only the first letter of each token; preserve the rest
       return "".join(w[:1].upper() + w[1:] for w in words)
    # Single token: ensure first letter is upper, keep rest as-is (preserve CamelCase)
    w = words[0]
    return w[:1].upper() + w[1:]

# ---------------------------
# Rules corpus
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


def list_rule_files() -> List[str]:
    if not os.path.isdir(RULES_DIR):
        return []
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(RULES_DIR, "*.md")))


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
    Requires OpenAI + LLM_API_KEY; no local fallback.
    """
    if OpenAI is None or not os.environ.get("LLM_API_KEY"):
        raise RuntimeError("LLM_API_KEY missing or OpenAI SDK not available")

    policy_name = policy_name_for_title(title_name)
    client = OpenAI(api_key=os.environ["LLM_API_KEY"])

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
    :root {
      --bg: #ffffff;
      --fg: #0b1220;
      --muted: #5b677a;
      --card: #f7f9fc;
      --border: #e5e9f2;
      --accent: #3ccfcf;
      --accent-fg: #0b1220;
      --input: #ffffff;
      --code-bg: #f3f4f6;
    }
    body[data-theme="dark"] {
      --bg: #0b1220;
      --fg: #e5eefc;
      --muted: #9fb3c8;
      --card: #111a2b;
      --border: #1c2a44;
      --accent: #1aa8a8;
      --accent-fg: #0b1220;
      --input: #0d1526;
      --code-bg: #0f1a2e;
    }

    /* Base layout */
    * { box-sizing: border-box; }
    body {
      margin: 0; padding: 24px;
      background: var(--bg);
      color: var(--fg);
      font: 14px/1.5 system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
    }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }

    .container { max-width: 1200px; margin: 0 auto; }
    h1, h2, h3 { margin: 0 0 12px; }
    p { margin: 0 0 10px; color: var(--muted); }

    /* Cards and rows */
    .row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }
    .row2.single { grid-template-columns: 1fr; }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
    }

    /* Inputs */
    input[type="text"], input[type="number"], select, textarea {
      width: 100%;
      background: var(--input);
      color: var(--fg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 12px;
      outline: none;
    }
    textarea { min-height: 160px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; }
    input::placeholder, textarea::placeholder { color: var(--muted); }

    /* Buttons */
    .btn {
      background: var(--accent);
      color: var(--accent-fg);
      border: none;
      border-radius: 10px;
      padding: 10px 14px;
      cursor: pointer;
      font-weight: 600;
    }
    .btn.secondary {
      background: transparent;
      color: var(--fg);
      border: 1px solid var(--border);
    }
    .btn:disabled { opacity: 0.6; cursor: not-allowed; }

    /* Code blocks */
    pre, code {
      background: var(--code-bg);
      color: var(--fg);
      border-radius: 8px;
    }
    pre { padding: 10px; overflow: auto; }

    /* Labels */
    .bold { font-weight: 700; color: var(--fg); }
    .mcp-label { display: block; margin: 12px 0 8px; }
    .mcp-row { display: flex; flex-wrap: wrap; gap: 8px 14px; }

    /* Live file viewers */
    .livebox {
      width: 100%; min-height: 220px; white-space: pre; overflow: auto;
      background: var(--code-bg); color: var(--fg);
      border: 1px solid var(--border); border-radius: 8px; padding: 12px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
    }

    /* Dark-mode toggle button (top-right) */
    .theme-toggle {
      position: fixed; top: 12px; right: 12px; z-index: 1000;
      background: var(--card); color: var(--fg);
      border: 1px solid var(--border); border-radius: 999px;
      padding: 8px 12px; font-weight: 700; cursor: pointer;
    }

    @media (max-width: 980px) {
      .row2 { grid-template-columns: 1fr; }
    }
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
          // refresh derived notes
          updateDerivedNotes();
        });
    }

    // --- Live preview of warp-mcp-config.yaml ---
    let MCP_LAST_MTIME = null;
    async function refreshMcpPreview() {
      const r = await fetch('/get_mcp');
      const j = await r.json();
      document.getElementById('mcp_preview').value = j.text || '';
    }
    async function pollMcpPreview() {
      try {
        const r = await fetch('/get_mcp_mtime');
        const j = await r.json();
        const m = j.mtime || 0;
        if (MCP_LAST_MTIME === null || m > MCP_LAST_MTIME) {
          MCP_LAST_MTIME = m;
          await refreshMcpPreview();
          await populateMcpChecklist(); // ensure new servers show up
        }
      } catch (e) {}
    }
    // --- end live preview ---

    // --- Live preview of warp-agent-config.yaml ---
    let AGENTS_LAST_MTIME = null;
    async function refreshAgentYaml() {
      const r = await fetch('/get_agent_yaml');
      const j = await r.json();
      document.getElementById('agent_yaml_text').value = j.text || '';
    }
    async function pollAgentYaml() {
      try {
        const r = await fetch('/get_agent_yaml_mtime');
        const j = await r.json();
        const m = j.mtime || 0;
        if (AGENTS_LAST_MTIME === null || m > AGENTS_LAST_MTIME) {
          AGENTS_LAST_MTIME = m;
          await refreshAgentYaml();
        }
      } catch (e) {}
    }

    // --- MCP names -> checklist ---
    async function populateMcpChecklist() {
      try {
        const r = await fetch('/mcp_names');
        const j = await r.json();
        const box = document.getElementById('mcp_checklist');
        box.innerHTML = '';
        (j.names || []).forEach(name => {
          const id = 'mcp_' + name.replace(/[^a-zA-Z0-9_\-]/g,'_');
          const wrap = document.createElement('div');
          wrap.className = 'mcp-pill';
          const cb = document.createElement('input');
          cb.type = 'checkbox'; cb.name = 'mcp_name'; cb.id = id; cb.value = name;
          if (name === 'file-mcp') cb.checked = true;
          const label = document.createElement('label');
          label.setAttribute('for', id);
          label.textContent = name;
          wrap.appendChild(cb);
          wrap.appendChild(label);
          box.appendChild(wrap);
        });
        if ((j.names || []).length === 0) {
          box.innerHTML = '<span class="small">No MCP servers found in warp-mcp-config.yaml</span>';
        }
      } catch (e) {
        document.getElementById('mcp_checklist').innerHTML = '<span class="small err">Error loading MCP servers</span>';
      }
    }

    // --- Derived "notes" content: Rule "<Title — Policy>" ---
    function updateDerivedNotes() {
      const name = document.getElementById('agent_name').value.trim() || "NewAgent";
      fetch('/rule_title_for_name?name=' + encodeURIComponent(name))
        .then(r => r.json()).then(j => {
          const ruleTitle = j.rule_title || (name + " — Policy");
          document.getElementById('notes').value = 'Rule "' + ruleTitle + '"';
        });
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
      if (j.ok && j.text) {
        document.getElementById('mcp_preview').value = j.text;
        // next poll will also reflect new mtime
      }
    }

    async function addProfile() {
      const name  = document.getElementById('agent_name').value;
      const model = document.getElementById('model_select').value;
      const apply_code_files = document.getElementById('perm_apply_code_files').checked;
      const read_files       = document.getElementById('perm_read_files').checked;
      const notes_text       = document.getElementById('notes').value;

      // gather selected MCP servers
      const selected = Array.from(document.querySelectorAll('input[name="mcp_name"]:checked')).map(el => el.value);

      const r = await fetch('/add_profile', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          name, model, apply_code_files, read_files,
          allowed_mcp_servers: selected, notes: notes_text
        })
      });
      const j = await r.json();
      const out = document.getElementById('profile_result');
      document.getElementById('profile_preview').textContent = j.preview || '';
      out.className = j.ok ? 'ok small' : 'err small';
      out.textContent = j.msg || '';
      // still refresh immediately
      refreshAgentYaml();
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

    window.addEventListener('DOMContentLoaded', async ()=>{
      // initial loads
      await refreshMcpPreview();
      await populateMcpChecklist();
      await refreshRulesMeta();
      await refreshAgentYaml();
      await refreshRouterBlocks();
      // polling loops (1.5s)
      try { pollMcpPreview(); setInterval(pollMcpPreview, 1500); } catch (e) {}
      try { pollAgentYaml(); setInterval(pollAgentYaml, 1500); } catch (e) {}
      // rules select change
      const sel = document.getElementById('rules_select');
      if (sel) sel.addEventListener('change', ()=>loadRuleText(sel.value));
      // seed derived notes
      updateDerivedNotes();
    });

    document.addEventListener('DOMContentLoaded', () => {
      const KEY  = 'mcp_gui_theme';
      const btn  = document.getElementById('themeToggle');
      const root = document.body;
    
      if (!btn) return; // safety
    
      function apply(theme) {
        root.setAttribute('data-theme', theme);
        btn.textContent = (theme === 'dark') ? '☀️ Light' : '🌙 Dark';
      }
    
      // Prefer saved theme; fall back to system setting
      const saved = localStorage.getItem(KEY)
          || (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    
      apply(saved);
    
      btn.addEventListener('click', () => {
        const next = (root.getAttribute('data-theme') === 'dark') ? 'light' : 'dark';
        localStorage.setItem(KEY, next);
        apply(next);
      });
    });
  </script>
</head>
<body>
  <button id="themeToggle" class="theme-toggle" title="Toggle theme">🌙 Dark</button>
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
      <!--<button id="mcp_json_copy_btn" class="btn secondary" onclick="copyById('mcp_json')">Copy</button>-->
    </div>
    <textarea id="mcp_json" oninput="validateJSON()" placeholder='{"file-mcp": { "command":"npx", "args":["-y","@modelcontextprotocol/server-filesystem","current_working_directory"], "env":{}, "working_directory":"current_working_directory" }}'></textarea>
    <p id="json_err" class="small">Paste JSON to validate…</p>
    <button class="btn" onclick="saveMcp()">Save MCP → warp-mcp-config.yaml</button>
    <p id="mcp_result" class="small"></p>
    <h4 class="small">Current warp-mcp-config.yaml:</h4>
    <textarea id="mcp_preview" readonly></textarea>
  </div>

  <!-- BOTTOM: Agent + Profile + Rule + Router -->
  <div class="card">
    <div class="grid2">
      <label>Title (Agent Name, e.g., FileCreator)</label>
      <input type="text" id="agent_name" oninput="toKebab()" placeholder="FileCreator"/>
      <span id="name_preview" class="mono small">agent-name: —</span>
    </div>
  </div>

  <div class="row2 single">
    <div class="card">
      <h3>2) Add Agent Profile → warp-agent-config.yaml</h3>

      <div class="form-block bold">
        <label>Model</label>
        <select id="model_select" style="margin-top: 4px;">
          <option value="claude-sonnet-latest" selected>claude-sonnet-latest</option>
        </select>
      </div>
    
      <div class="form-block">
        <label class="bold mcp-label">Allowed MCP Servers</label>
        <div id="mcp_checklist" class="mcp-row"></div>
      </div>


      <div class="checkrow" style="margin-top:8px;">
        <label class="bold mcp-label"><input type="checkbox" id="perm_apply_code_files" checked/> Apply Code Diffs</label>
        <label class="bold mcp-label"><input type="checkbox" id="perm_read_files" checked/> Read Files</label>
      </div>

      <div style="margin-top:12px;">
        <label>Notes (auto)</label>
        <input type="text" id="notes" readonly value='Rule "NewAgent — Policy"' style="margin-top:4px;"/>
      </div>

      <button class="btn" style="margin-top:12px;" onclick="addProfile()">Add Profile (Preview + Save)</button>
      <pre id="profile_preview" class="mono" style="min-height:120px;"></pre>
      <p id="profile_result" class="small"></p>

      <h4 class="small">Current warp-agent-config.yaml (This is only a reference, to add agents go to Warp's settings and enter these created settings):</h4>
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
        <h4 class="small">SUB_AGENTS (refresh webpage to see new changes):</h4>
        <textarea id="sub_agents_box" readonly></textarea>
      </div>
      <div>
        <h4 class="small">RULE_TITLES (refresh webpage to see new changes):</h4>
        <textarea id="rule_titles_box" readonly></textarea>
      </div>
    </div>
  </div>

  <p class="small">Backups saved as <code>.bak.YYYYMMDD-HHMMSS</code> before writes.</p>
</body>
</html>
"""

# --- Pretty-print helpers for profiles YAML -------------------------------

def _inline_single_allowed_mcp(yaml_text: str) -> str:
    """
    Turns:
      allowed_mcp_servers:
        - taskrouter-mcp
    into:
      allowed_mcp_servers: [router-mcp]
    (only when exactly one item)
    """
    import re
    lines = yaml_text.splitlines()
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        out.append(line)
        m = re.match(r"^(\s*)allowed_mcp_servers:\s*$", line)
        if m:
            base_indent = m.group(1)
            items = []
            j = i + 1
            while j < n:
                mj = re.match(rf"^{base_indent}\s*-\s*(.+?)\s*$", lines[j])
                if mj:
                    items.append(mj.group(1))
                    j += 1
                else:
                    break
            if len(items) == 1:
                out[-1] = f"{base_indent}allowed_mcp_servers: [{items[0]}]"
                i = j
                continue
        i += 1
    return "\n".join(out) + ("\n" if not yaml_text.endswith("\n") else "")


def _blank_line_between_profiles(yaml_text: str) -> str:
    """
    Insert a blank line between top-level items under 'profiles:'.
    Assumes proper 2-space list indent ('  - ').
    """
    import re
    lines = yaml_text.splitlines()
    out = []
    in_profiles = False
    first_item = True

    for idx, line in enumerate(lines):
        if not in_profiles and line.strip() == "profiles:":
            in_profiles = True
            out.append(line)
            continue

        # Leave profiles block when we hit a top-level key or EOF.
        if in_profiles and line and not line.startswith("  "):
            in_profiles = False

        if in_profiles and re.match(r"^\s{2}-\s", line):  # "  - "
            if not first_item:
                out.append("")  # blank line before subsequent items
            first_item = False

        out.append(line)

    return "\n".join(out) + ("\n" if not yaml_text.endswith("\n") else "")


def dump_yaml_profiles(data: dict) -> str:
    """
    Use a custom dumper so sequences under 'profiles:' are indented with 2 spaces,
    then apply our two formatting passes: inline single allowed_mcp_servers and
    blank line between top-level profile items.
    """
    import yaml

    class IndentDumper(yaml.SafeDumper):
        # Force PyYAML to indent sequences under mappings (no indentless lists)
        def increase_indent(self, flow=False, indentless=False):
            return super().increase_indent(flow, False)

    text = yaml.dump(
        data,
        Dumper=IndentDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        indent=2,
        width=4096,
    )
    if not text.endswith("\n"):
        text += "\n"

    text = _inline_single_allowed_mcp(text)
    text = _blank_line_between_profiles(text)
    return text

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


@APP.get("/rule_title_for_name")
def api_rule_title_for_name():
    name = request.args.get("name", "").strip() or "NewAgent"
    title = to_title(name)
    rule_title = f"{title} — {policy_name_for_title(title)}"
    return jsonify({"rule_title": rule_title})


# Rules meta + preview
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


# MCP servers names for checklist
@APP.get("/mcp_names")
def api_mcp_names():
    try:
        cfg = load_yaml_or_json(MCP_JSON_PATH) or {}
        names = []
        if isinstance(cfg, dict):
            if "mcpServers" in cfg and isinstance(cfg["mcpServers"], dict):
                names = list(cfg["mcpServers"].keys())
            else:
                names = list(cfg.keys())
        return jsonify({"names": sorted(names)})
    except Exception as e:
        return jsonify({"names": [], "error": str(e)}), 200


# MCP preview + mtime
@APP.get("/get_mcp")
def api_get_mcp():
    try:
        text = read_text(MCP_JSON_PATH) if os.path.exists(MCP_JSON_PATH) else "{}"
    except Exception as e:
        text = f'{{"#error": "{e}"}}'
    return jsonify({"text": text})


@APP.get("/get_mcp_mtime")
def api_get_mcp_mtime():
    try:
        if os.path.exists(MCP_JSON_PATH):
            m = os.path.getmtime(MCP_JSON_PATH)
        else:
            m = 0
    except Exception:
        m = 0
    return jsonify({"mtime": m})


# Agent YAML preview + mtime
@APP.get("/get_agent_yaml")
def api_get_agent_yaml():
    try:
        text = read_text(AGENTS_YAML_PATH) if os.path.exists(AGENTS_YAML_PATH) else ""
    except Exception as e:
        text = f"# Error reading {AGENTS_YAML_PATH}: {e}"
    return jsonify({"text": text})


@APP.get("/get_agent_yaml_mtime")
def api_get_agent_yaml_mtime():
    try:
        if os.path.exists(AGENTS_YAML_PATH):
            m = os.path.getmtime(AGENTS_YAML_PATH)
        else:
            m = 0
    except Exception:
        m = 0
    return jsonify({"mtime": m})


# Router blocks (live)
@APP.get("/get_router_blocks")
def api_get_router_blocks():
    try:
        src = read_text(ROUTER_PY_PATH) if os.path.exists(ROUTER_PY_PATH) else ""
        sub, rtl = extract_subagents_and_ruletitles(src) if src else ("", "")
    except Exception as e:
        sub, rtl = (f"# Error: {e}", "")
    return jsonify({"sub_agents": sub, "rule_titles": rtl})


# AI rule generation
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


# Save MCP (merge respecting Warp schema)
def _normalize_mcp_payload(text: str) -> Dict[str, Any]:
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("Top-level JSON must be an object mapping serverName → config")
    if ("command" in obj) or ("type" in obj):
        raise ValueError('Provide a mapping like {"MyServer": { ...config... }}')
    return obj


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

    # Merge respecting Warp schema { "mcpServers": { ... } }
    if "mcpServers" in existing and isinstance(existing["mcpServers"], dict):
        result = dict(existing)
        servers = dict(existing.get("mcpServers", {}))
        servers.update(incoming)
        result["mcpServers"] = servers
        count = len(servers)
    else:
        result = dict(existing)
        result.update(incoming)
        count = len(result)

    # Pretty-print full file and validate round-trip JSON
    pretty = dump_json_pretty(result)
    json.loads(pretty)  # round-trip validation

    try:
        write_text_atomic(MCP_JSON_PATH, pretty)
        return jsonify({"ok": True, "msg": f"MCP servers updated → {MCP_JSON_PATH}", "text": pretty, "count": count})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Write failed: {e}"}), 500


# Add agent profile (requested schema)
@APP.post("/add_profile")
def api_add_profile():
    data = request.get_json(force=True)
    title = to_title(data.get("name", "NewAgent"))
    model = (data.get("model") or "claude-sonnet-latest").strip()
    apply_code_files = bool(data.get("apply_code_files", True))
    read_files = bool(data.get("read_files", True))
    notes_in = (data.get("notes") or "").strip()

    # allowed MCPs can be a list (preferred) or a string
    allowed_field = data.get("allowed_mcp_servers", [])
    if isinstance(allowed_field, list):
        allowed_mcp_servers = [str(s).strip() for s in allowed_field if str(s).strip()]
    else:
        raw = str(allowed_field or "").strip()
        allowed_mcp_servers = [s.strip() for s in re.split(r"[,\s]+", raw) if s.strip()] or ["file-mcp"]

    # Derive rule title used in notes if empty
    profile_rule_title = f"{title} — {policy_name_for_title(title)}"
    notes = notes_in if notes_in else f'Rule "{profile_rule_title}"'

    # Load existing YAML (list under 'profiles')
    try:
        agent_cfg = yaml.safe_load(read_text(AGENTS_YAML_PATH)) if os.path.exists(AGENTS_YAML_PATH) else {}
        agent_cfg = agent_cfg or {}
        profiles = agent_cfg.get("profiles")
        if profiles is None or not isinstance(profiles, list):
            profiles = []
            agent_cfg["profiles"] = profiles
        # Check existence by name
        existing = None
        for p in profiles:
            if str(p.get("name", "")).strip().lower() == title.lower():
                existing = p
                break

        new_block = {
            "name": title,
            "model": model,
            "permissions": {
                "apply_code_files": apply_code_files,
                "read_files": read_files
            },
            "allowed_mcp_servers": allowed_mcp_servers,
            "notes": notes
        }

        if existing:
            # Replace existing block with new one (explicit overwrite to match requested schema)
            idx = profiles.index(existing)
            profiles[idx] = new_block
            action = "updated"
        else:
            profiles.append(new_block)
            action = "added"

        # Write full file with pretty formatting (2-space list indent, blank lines)
        pretty_yaml = dump_yaml_profiles(agent_cfg)
        write_text_atomic(AGENTS_YAML_PATH, pretty_yaml)

        # Preview a single item using same style (under 'profiles:')
        preview_agent_cfg = {"profiles": [new_block]}
        preview_yaml_full = dump_yaml_profiles(preview_agent_cfg)
        # remove the 'profiles:' line from the preview box:
        preview_lines = preview_yaml_full.splitlines()
        if preview_lines and preview_lines[0].strip() == "profiles:":
            preview_yaml = "\n".join(preview_lines[1:]) + "\n"
        else:
            preview_yaml = preview_yaml_full

        return jsonify({
            "ok": True,
            "preview": preview_yaml,
            "msg": f'Profile {action} → {AGENTS_YAML_PATH}'
        })
    except Exception as e:
        return jsonify({
            "ok": False,
            "preview": "",
            "msg": f"Error: {e}"
        }), 500


# Patch router
@APP.post("/patch_router")
def api_patch_router():
    data = request.get_json(force=True)
    title = to_title(data.get("name", "NewAgent"))
    rule_text = (data.get("rule") or "").strip()
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
    port = int(os.environ.get("MCP_MANAGER_GUI_PORT", "5057"))
    APP.run(host="127.0.0.1", port=port, debug=True, use_reloader=True)
