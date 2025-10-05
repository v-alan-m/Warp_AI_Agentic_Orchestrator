# ✅ Works-First-Time Setup Checklist (Warp AI Agentic Orchestrator)

> Follow these steps **in order** so your first run succeeds.

---

## 0) One-time prerequisites
- Install **Python 3.10+**, **Node 18+**, and **Warp (latest)**.
- Clone the repo and ensure the structure exists (especially `/docs` and `/project/src`).
- (Windows) Confirm Node tools are on PATH:
  - `node -v`
  - `npx -v`

---

## 1) Add your GitHub API key (PAT)
Create a **fine-grained PAT** and make it available as an environment variable so Warp/MCP can read it.

**PowerShell (Windows)**
~~~powershell
setx GITHUB_TOKEN "ghp_XXXXXXXXXXXXXXXXXXXX"
~~~

**Recommended minimal scopes**
- **Contents (Read/Write)** – repo files/PR content
- **Pull requests (Read/Write)**
- **Issues** (optional, only if you’ll create issues)

> Prefer exporting `GITHUB_TOKEN` in your shell/profile over hardcoding it in any JSON.

---

## 2) Start the Router MCP (orchestrator)
Start this **before** wiring MCPs in Warp so the health check passes.

**Install deps & run (Windows / PowerShell)**
### 2.1) From repo root (Warp_AI_Agentic_Orchestrator)
~~~powershell
pip install fastapi uvicorn pydantic
~~~
### 2.2) Optional safety/env:
~~~powershell
$env:ROUTER_LOG_DIR = "$PWD\docs"
$env:ROUTER_MAX_STEPS = "10"
$env:ROUTER_ENFORCE_RULE_ACK = "true"
$env:ROUTER_PORT = "8085"
~~~
### 2.3) Launch (Windows - Powershell 7)
~~~powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\orchestrator.ps1~~~
# Expect: router prints health info; files appear/append in .\docs\
~~~

### 2.4) Quick health check (new terminal)
~~~powershell
curl http://localhost:8085/health
~~~
You should see something like:
~~~json
{ "ok": true, "ts": "..." }
~~~

---

## 3) Add MCP servers in Warp (JSON one-shot)
Open **Warp → Settings → AI → MCP Servers → JSON** and paste the **one-shot JSON** from your repo at:
- `warp_config/warp-mcp-config.yaml`  ← *(copy the JSON block from that file and paste it into Warp’s MCP Servers JSON box)*

**Before pasting, edit:**
- Replace **absolute paths** (e.g., `"/absolute/path/to/Warp_AI_Agentic_Orchestrator/project"`) with your real path:
  - Windows example: `C:\\Users\\you\\dev\\Warp_AI_Agentic_Orchestrator\\project`
- Confirm the Router URL:
  - `router-mcp` → `http://localhost:8085/route`
- Ensure `"start_on_launch": true` for each entry.

**After saving:**
- Verify each server shows **Running** (or starts cleanly).
- If a stdio server fails, use **View Logs** on that server for details.

**You should see these servers:**
- `file-mcp` (Official Filesystem, stdio)
- `git-mcp` (cyanheads local git, stdio)
- `github-mcp` (GitHub official, stdio; reads `GITHUB_TOKEN`)
- `test-mcp` (privsim test runner, stdio)
- `superdesign-mcp` (SuperDesign packaged MCP, stdio)
- `router-mcp` (HTTP → your FastAPI router)

---

## 4) Add agent profiles in Warp
Open **Warp → Settings → AI → Profiles** and create:

`TaskRouter`, `FileCreator`, `FrontendDeveloper`, `BackendDeveloper`, `TestRunner`, `GitWorkflow`, `UIDesigner`, `UXResearcher`, `SprintPrioritizer`, `RapidPrototyper`

For each profile:
- **Allowed MCP Servers** — mirror exactly from:
  - `warp_config/warp-agent-config.yaml`
- **Permissions** — set least-privilege per that same YAML (no command execution).
- **Model** — suggested defaults:
  - Sonnet (latest) → TaskRouter, FileCreator, FrontendDeveloper, BackendDeveloper
  - Haiku (latest) → GitWorkflow, TestRunner

> Keep the YAML open side-by-side and mirror into the UI. **Names must match exactly.**

---

## 5) Add Rules (system guardrails) in Warp
Open **Warp Drive → Rules** and create *one Rule per profile* with the titles:

- `TaskRouter — Orchestrator Policy`
- `FileCreator — File Ops Policy`
- `FrontendDeveloper — UI Policy`
- `BackendDeveloper — API Policy`
- `GitWorkflow — Safe Git Policy`
- `TestRunner — Testing Policy`
- `UIDesigner — Design Artifacts Policy`
- `UXResearcher — Research Artifacts Policy`
- `SprintPrioritizer — Planning Policy`
- `RapidPrototyper — Prototype Policy`

Paste the content from:
- `warp_config/warp_rules/*.md`  (each role → its Rule text)

> You don’t need to mention Rules in chat — **router_mcp.py auto-injects** the correct Rule each step and **requires** the first line to acknowledge:
>
> `rules loaded (agent=<Role> | rule=<Rule Title>)`

---

## 6) Sanity checks (do these before first run)
- **Filesystem root** — Ensure `file-mcp` args include the **absolute** path to your `/project` folder; otherwise file writes may fail.
- **Working directories** — `git-mcp` and `test-mcp` should have `working_directory` set to your `/project` path.
- **Docs writeable** — Router should append to:
  - `/docs/build-summary.md`
  - `/docs/router_log.jsonl`
- **Local Git identity** (optional but recommended):
~~~powershell
git config user.name  "Your Name"
git config user.email "you@example.com"
~~~

---

## 7) Run the first prompt (TaskRouter chat)
Open the **TaskRouter** profile chat in Warp and paste:

~~~text
workflow_id: site-scaffold-001

Use /docs/site-spec.md as the source of truth. Execute the full build:
- Scaffold structure and files as specified
- Implement Home (hero, #disciplines, #contact, skip link, landmarks)
- Implement all three service pages with back-to-/#disciplines CTA
- Implement About and minimal JS
- Commit safely

Respond only with routing lines internally via router-mcp (auto_loop:true).
When complete, output:
DONE
<1–3 sentence final summary>
~~~

**Expected:**
- TaskRouter replies briefly: “Kicked off workflow …”
- Router + TaskRouter loop (silent) until `DONE`
- Logs populate:
  - `/docs/build-summary.md`
  - `/docs/router_log.jsonl`
  - `/docs/CHANGELOG.md` (upon completion)
- Final TaskRouter chat shows:
  ~~~text
  DONE
  <short summary>
  ~~~

---

## If anything fails
- **Router health** — `curl http://localhost:8085/health`
- **Warp MCP logs** — Settings → AI → MCP Servers → (server) → **View Logs**
- **Ack mismatch** — Ensure Warp Rule titles exactly match `RULE_TITLES` in `router_mcp.py`
- **Path errors** — Double-check absolute paths (Windows escaping) and directory existence
- **Git issues** — Ensure `git-mcp` `working_directory` points at an initialized repo (`git init`)

---

## Your original plan (with fixes)
- Add GitHub API key and add to MCP server → ✅ Better: export **`GITHUB_TOKEN`** in your shell; MCP inherits it
- Add MCP servers into Warp config → ✅ Paste JSON from `warp_config/warp-mcp-config.yaml` (fix absolute paths)
- Add agents to Warp config → ✅ Create profiles in Warp UI, mirror `warp-agent-config.yaml`, then add **Rules**
- Run orchestrator.ps1 → ✅ Start Router **before** first prompt
- Run first prompt → ✅ Paste into **TaskRouter** chat (auto-loop to `DONE`)
