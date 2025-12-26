# 🧩 Warp UI Setup (Profiles, MCP Servers, Rules)

## 1) 🖥️ MCP Servers
- Open **Warp → Settings → AI → MCP Servers**
- Use the **JSON** input method and paste the **one-shot JSON** from this repo’s `warp_config/warp-mcp-config.yaml` (**do not retype**; just copy/paste it into Warp).  
  - That JSON registers:
    - `file-mcp` (Official Filesystem, stdio)
    - `git-mcp` (cyanheads local git, stdio)
    - `github-mcp` (GitHub official server, stdio)
    - `test-mcp` (privsim test runner, stdio)
    - `superdesign-mcp` (SuperDesign packaged MCP, stdio)
    - `taskrouter-mcp` (HTTP → `http://localhost:8085/route`)
  - **Then** keep a copy of the same JSON in this repo at `warp_config/warp-mcp-config.yaml` (source of truth for teammates).

> Replace all placeholder absolute paths with your real path to `Warp_AI_Agentic_Orchestrator/project`, and set a real `GITHUB_TOKEN` in your shell.

> `IMPORTANT`:  Before starting update the absolute paths in all the MCP servers.
> > **So the agents can only edit files inside that folder and never anything outside if it.**

## 2) 📦 IMPORTANT: Local MCP Servers

- `Important`: Some open-sourse repos such as test-mcp will have to be `cloned and run locally`, instead of using `npx`.
  - Keep them in a `single shared folder outside your project` so you don’t re-clone per repo.
  - For each MCP server, sometimes specific file paths will have to be referenced within the respective Warp MCP server config JSON 
> Having dedicated MCP folder prevents having to change the stored path(s) in that MCP server JSON config, when changing projects.
> > Note: The `working directory` value will still have to be changed when switching projects.

## 3) 🖼️ Profiles (Agents)
- Open **Warp → Settings → AI → Profiles + Add**
- Create profiles named exactly:
  - `TaskRouter`, `FileCreator`, `FrontendDeveloper`, `BackendDeveloper`, `TestRunner`, `GitWorkflow`, `UIDesigner`, `UXResearcher`, `SprintPrioritizer`, `RapidPrototyper`
- Create profiles with these **Allowed MCP Servers** and **Permissions**:
  - **TaskRouter** → Allowed: `taskrouter-mcp`; *no* file write; *no* execute commands.
  - **FileCreator** → Allowed: `file-mcp`; file read/write **on**, execute commands **off**.
  - **FrontendDeveloper** → Allowed: `file-mcp`; file read/write **on**, execute **off**.
  - **BackendDeveloper** → Allowed: `file-mcp`; file read/write **on**, execute **off**.
  - **GitWorkflow** → Allowed: `git-mcp`; file write **off**, execute **off**.
  - **TestRunner** → Allowed: `test-mcp`; file write **off**, execute **off**.
  - **UIDesigner** → Allowed: `superdesign-mcp` (+ `file-mcp` if you want to save artifacts); file read/write **on**.
  - **UXResearcher** → Allowed: `superdesign-mcp` (+ `file-mcp` if you want to save artifacts); file read/write **on**.
  - **SprintPrioritizer** → Allowed: `file-mcp`; file read/write **on**.
  - **RapidPrototyper** → Allowed: `file-mcp`; file read/write **on**.
- For each profile:
  - **Allowed MCP Servers**: match the spec in `warp_config/warp-agent-config.yaml` (copy from that file into the UI)
  - **Permissions**: set minimal privileges (e.g., GitWorkflow: no file writes; FileCreator: file writes allowed; no command execution for all)
  - **Model**: Sonnet (latest) for TaskRouter/FE/BE/FileCreator; Haiku for GitWorkflow/TestRunner

> Use `warp_config/warp-agent-config.yaml` as the authoritative checklist (drag/drop to view; copy values into Warp UI).

## 4) ⚖️ Rules (acts like system prompts)
- Open **Warp Drive → Rules**
- Create one Rule per profile with the exact titles:
  - `TaskRouter — TaskRouter Policy`
  - `FileCreator — FileCreator Policy`
  - `FrontendDeveloper — FrontendDeveloper Policy`
  - `BackendDeveloper — BackendDeveloper Policy`
  - `GitWorkflow — GitWorkflow Policy`
  - `TestRunner — TestRunner Policy`
  - `UIDesigner — UIDesigner Policy`
  - `UXResearcher — UXResearcher Policy`
  - `SprintPrioritizer — SprintPrioritizer Policy`
  - `RapidPrototyper — RapidPrototyper Policy`
- Paste the text from `warp_config/warp_rules/*.md` for each role.

**Good to know:**  
`taskrouter_mcp.py` auto-injects the correct Rule each step and requires the agent to acknowledge with:
```
rules loaded (agent=<Role> | rule=<Rule Title>)
```
- No extra user action needed in chat; the Router guarantees each profile loads its Rule before executing.