# Auto-Run vs Manual Modes - How One-Liners Execute (Warp + TaskRouter + Router MCP)

> **Note**: We do not enter prompts into Warp's terminal with the agent toggle on, rather it uses:
> > **Warp's tool-call channel**

---

## 1) 🎚 One switch to rule them all (auto-run on/off)

Use a single environment flag that the Router enforces for every kickoff coming from TaskRouter:

In `router_mcp.py` (top of file / config block):
```python
ROUTER_FORCE_AUTORUN = os.getenv("ROUTER_FORCE_AUTORUN", "true").lower() == "true"
```

Where the request is normalized (the code that currently respects `from_taskrouter`), force it:
```python
if payload.get("from_taskrouter"):
    payload["auto_loop"] = True if ROUTER_FORCE_AUTORUN else False
```

Now flip behavior everywhere by exporting one env var before starting the Router:
```bash
# Auto-run everywhere (default)
export ROUTER_FORCE_AUTORUN=true

# Single-step/manual everywhere
export ROUTER_FORCE_AUTORUN=false
```

> You can still override per request (`auto_loop`), but the Router will pin it according to this flag whenever the call originates from TaskRouter (`from_taskrouter: true`).

---

## 2) 👉 Who generates content after the first prompt?

**TaskRouter’s LLM** generates code/content for each step, guided by:
- The structured step from the Router (`next_agent`, `instruction`).
- The target agent’s **rule/policy** (e.g., *FrontendDeveloper - UI Policy*).
- The **allowed MCP servers** for that step (e.g., `file-mcp` to write files).

All LLM calls happen inside the Warp session (so Warp’s context features apply). The Router only coordinates; it doesn’t need to call LLMs itself.

---

## 3) 🔧 Manual mode UX (when auto-run is off)

Two patterns-pick one:

**A. “Show and wait” (no copy/paste)**
- TaskRouter prints the next routing line to chat and asks “Proceed?”
- You reply `yes`, `next`, or `continue`.
- TaskRouter then issues the tool calls and returns with the next routing line.

**B. “Operator enters line” (explicit control)**
- TaskRouter prints the one-liner and waits for you to submit/confirm.
- You paste the line or just type `run` / `continue`.

Warp doesn’t add a special “Continue” button; it’s just a normal chat reply from you to advance.

---

## 4) 🏎️💨 In auto-run: how are the one-liners “answered” if not shown in chat?

They’re consumed and acted on *inside the session*, not typed back into chat.

Behind-the-scenes flow:

1. **You** send one human brief to **TaskRouter** in Warp chat.
2. **TaskRouter → tool call**:
   ```json
   {
     "name": "route",
     "arguments": {
       "task": "<SubAgent>: <instruction>",
       "auto_loop": true,
       "workflow_id": "…",
       "from_taskrouter": true
     }
   }
   ```
3. The **router-mcp shim** forwards to your FastAPI Router and returns a **JSON tool result**, e.g.:
   ```json
   {
     "next_agent": "FrontendDeveloper",
     "instruction": "Implement project/templates/pages/index.html …",
     "status": "step"
   }
   ```
4. **TaskRouter (LLM turn)** sees that tool result as input context (an *observation*), applies the selected agent’s **rule/policy**, and then issues the **appropriate MCP tool calls** directly (e.g., `file-mcp` writes/edits files). None of this is typed into chat; it’s internal **assistant tool calls**.
5. When that step is done, **TaskRouter → tool call** again to `router-mcp.route(…)` to ask for the **next one-liner**.
6. Repeat until the router signals **done**. Then TaskRouter prints:
   ```text
   DONE
   <final summary>
   ```

So:
- Yes, it is “one one-liner at a time.”
- The “prompts” for those one-liners are **tool results** fed into TaskRouter, which then responds by making **more tool calls** (not chat messages).
- The only visible chat messages are your initial brief (and, optionally, echoed one-liners if you enable an “echo” flag) and the final `DONE` + summary.

---

## 5) 📋 Summary

- TaskRouter calls the Router via the **tool call**,
- Router returns the **next one-liner**,
- TaskRouter executes with MCP tools,
- and repeats until **DONE**.

```text
Warp (your brief)
  → TaskRouter (tool call)
  → router-mcp shim
  → FastAPI Router
  ← tool result (one-liner)
  ← TaskRouter executes with MCP tools
  → TaskRouter asks Router for next step
  … repeats …
  → DONE + summary (printed to chat)
```
