# router_mcp.py
# Warp Router MCP — auto-loop router with Markdown + JSONL persistence,
# workflow_id support, TaskRouter kickoff enforcement, and Warp Rule
# guardrails (with explicit ack) injected per sub-agent.
#
# Run:
#   pip install fastapi uvicorn pydantic
#   python router_mcp.py
#
# Env (optional):
#   ROUTER_LOG_DIR=/abs/path/to/docs      # default: ./docs
#   ROUTER_MAX_STEPS=10                   # safety cap
#   ROUTER_ENFORCE_RULE_ACK=true|false    # default: true
#   ROUTER_PORT=8085                      # default: 8085
#
# HTTP:
#   GET  /health          -> 200 OK
#   POST /route           -> { "task": "...", "auto_loop": bool, "workflow_id": "...", "from_taskrouter": bool }
#                            "task" is "SubAgent: instruction" or "DONE\nsummary"
#
# NOTE: This file includes two clear INTEGRATION HOOKS that you should wire to Warp: 1) call_sub_agent(agent_key,
# guarded_instruction) -> str - Send the instruction to the corresponding Warp Agent (profile) so *Warp* makes the
# LLM call & uses MCP tools. 2) call_taskrouter_next_step(prev_agent, agent_response) -> str | "DONE\n..." - Ask your
# TaskRouter (running in Warp) for the *next* routing line given the last agent’s response. For immediate
# smoke-tests, both hooks currently simulate behavior and return canned results so the app runs end-to-end.

import os
import re
import json
import time
from datetime import datetime
from typing import Optional, Tuple

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# -----------------------------
# Config & constants
# -----------------------------

APP = FastAPI(title="Warp Router MCP")

LOG_DIR = os.getenv("ROUTER_LOG_DIR", os.path.join(os.path.dirname(__file__), "docs"))
os.makedirs(LOG_DIR, exist_ok=True)

BUILD_SUMMARY_MD = os.path.join(LOG_DIR, "build-summary.md")
CHANGELOG_MD = os.path.join(LOG_DIR, "CHANGELOG.md")
ROUTER_LOG_JSONL = os.path.join(LOG_DIR, "router_log.jsonl")

# Touch files so tails don’t fail
for f in (BUILD_SUMMARY_MD, CHANGELOG_MD, ROUTER_LOG_JSONL):
    if not os.path.exists(f):
        with open(f, "w", encoding="utf-8") as _fh:
            _fh.write("")

MAX_STEPS = int(os.getenv("ROUTER_MAX_STEPS", "10"))
ENFORCE_RULE_ACK = os.getenv("ROUTER_ENFORCE_RULE_ACK", "true").lower() in ("1", "true", "yes", "on")

# Maps human routing names to your Warp profile keys (adjust to your setup)
SUB_AGENTS = {
    "FileCreator": "file-creator",
    "GitWorkflow": "git-workflow",
    "TestRunner": "test-runner",
    "FrontendDeveloper": "frontend-developer",
    "BackendDeveloper": "backend-developer",
    "UIDesigner": "ui-designer",
    "SprintPrioritizer": "sprint-prioritizer",
    "RapidPrototyper": "rapid-prototyper",
    "UXResearcher": "ux-researcher",
}

# Warp Rule titles to apply per sub-agent
RULE_TITLES = {
    "FileCreator": "FileCreator — File Ops Policy",
    "GitWorkflow": "GitWorkflow — Safe Git Policy",
    "TestRunner": "TestRunner — Testing Policy",
    "FrontendDeveloper": "FrontendDeveloper — UI Policy",
    "BackendDeveloper": "BackendDeveloper — API Policy",
    "UIDesigner": "UIDesigner — Design Artifacts Policy",
    "UXResearcher": "UXResearcher — Research Artifacts Policy",
    "SprintPrioritizer": "SprintPrioritizer — Planning Policy",
    "RapidPrototyper": "RapidPrototyper — Prototype Policy",
}

ACK_PATTERN = r'^rules loaded \(agent=(?P<agent>[^|]+)\s*\|\s*rule=(?P<rule>.+)\)$'
MAX_ACK_RETRY = 1

ROUTING_LINE_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_-]+)\s*:\s*(.+)$", re.DOTALL)


# -----------------------------
# Models
# -----------------------------

class RouteRequest(BaseModel):
    task: str  # "SubAgent: instruction" or "DONE\nsummary"
    auto_loop: bool = False  # true: TaskRouter loop until DONE
    workflow_id: Optional[str] = None
    from_taskrouter: bool = False  # kickoff came from TaskRouter


class RouteResponse(BaseModel):
    ok: bool
    workflow_id: str
    step: int
    agent: Optional[str] = None
    message: Optional[str] = None
    done: bool = False


# -----------------------------
# Utilities
# -----------------------------

def ts() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def append_text(path: str, text: str) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(text)
        if not text.endswith("\n"):
            fh.write("\n")


def log_event_jsonl(obj: dict) -> None:
    line = json.dumps(obj, ensure_ascii=False)
    with open(ROUTER_LOG_JSONL, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def md_step_line(workflow_id: str, step: int, agent: str, instruction: str) -> str:
    return f"- {ts()} • `{workflow_id}` • **{agent}** → {instruction}\n"


def finalize_markdown(workflow_id: str, summary: str) -> None:
    append_text(BUILD_SUMMARY_MD, f"\n### {ts()} — Final Summary ({workflow_id})\n{summary}\n")
    append_text(CHANGELOG_MD, f"## {ts()} — Workflow {workflow_id} Completed\n{summary}\n")


def ensure_workflow_id(req: RouteRequest) -> str:
    if req.workflow_id:
        return req.workflow_id
    # Generate simple kebab id from first words of task
    base = re.sub(r"[^a-z0-9]+", "-", req.task.lower()).strip("-")
    return f"wf-{base[:24]}-{int(time.time())}"


def guard_instruction(sub_agent: str, raw_instruction: str) -> str:
    """Build guarded instruction with explicit SubAgent prefix + rule application + exact ack line."""
    rule_title = RULE_TITLES.get(sub_agent, "")
    lines = [f'{sub_agent}: Verify you are the "{sub_agent}" agent.']
    if rule_title:
        lines.append(f'Then apply Warp Rule "{rule_title}".')
        lines.append("Respond EXACTLY on a single line with:")
        lines.append(f"rules loaded (agent={sub_agent} | rule={rule_title})")
        lines.append("")
        lines.append("After that acknowledgment, proceed with the task below.")
        lines.append("")
    lines.append(f"Task: {raw_instruction}")
    return "\n".join(lines)


def parse_routing_line(task: str) -> Tuple[str, str]:
    """Return (sub_agent, instruction) or raise 400."""
    m = ROUTING_LINE_RE.match(task.strip())
    if not m:
        raise HTTPException(status_code=400, detail="invalid_format: expected 'SubAgent: instruction'")
    return m.group(1), m.group(2)


# -----------------------------
# INTEGRATION HOOKS (replace with real Warp calls)
# -----------------------------

def call_sub_agent(agent_key: str, guarded_instruction: str) -> str:
    """
    TODO: Wire this to Warp so the *agent profile* with key `agent_key`
    receives `guarded_instruction` as the next user turn.
    Warp should make the LLM call (so you keep code-diff/context) and run MCP tools as needed.

    For now, we simulate:
      - Echo the expected rules-ack as the first line (so ack passes).
      - Return a short faux result.
    """
    # Simulate agent acknowledging the rule + a short result
    # Extract expected ack from the guarded_instruction for realism:
    expected_ack = None
    for line in guarded_instruction.splitlines():
        if line.startswith("rules loaded (agent="):
            expected_ack = line.strip()
            break
    if not expected_ack:
        # Fallback: craft a best-effort ack using the agent_key & rule title
        rule = RULE_TITLES.get(agent_key.title().replace("-", ""), "N/A")
        expected_ack = f"rules loaded (agent={agent_key} | rule={rule})"

    faux_result = "\n".join([
        expected_ack,
        f"[SIMULATED OUTPUT] {agent_key} executed the task successfully."
    ])
    return faux_result


def call_taskrouter_next_step(prev_agent: str, agent_response: str) -> str:
    """
    TODO: Ask your TaskRouter (in Warp) for the *next* routing line.
    You can expose TaskRouter via an MCP tool or HTTP and pass it:
      - prev_agent
      - agent_response
      - any needed context

    Return either:
      - "SubAgent: next instruction"
      - or  "DONE\n<final summary>"

    For now, we simulate a tiny 2–3 step workflow that ends with DONE.
    """
    # Heuristic simulation: after GitWorkflow or after 3 steps, finish
    if "git-workflow" in prev_agent or "GitWorkflow" in prev_agent:
        return "DONE\nCommitted initial version."
    # Otherwise route to a sensible next step:
    if "frontend" in prev_agent or "Frontend" in prev_agent:
        return "GitWorkflow: Stage all changes and commit with message 'feat(site): initial scaffold and UI'"
    # Default next step
    return "FrontendDeveloper: Implement /project/src/pages/index.html per /docs/site-spec.md"


# -----------------------------
# Core routing with auto-loop
# -----------------------------

@APP.get("/health")
def health():
    return {"ok": True, "ts": ts()}


@APP.post("/route", response_model=RouteResponse)
def route_task(request: RouteRequest):
    """
    Handle a routing request. If auto_loop is enabled, iteratively ask TaskRouter
    for the next routing line and continue until DONE or MAX_STEPS.
    """
    workflow_id = ensure_workflow_id(request)

    # Enforce auto-loop at kickoff when called by TaskRouter
    if request.from_taskrouter and request.auto_loop is False:
        request.auto_loop = True

    # Early DONE (allows TaskRouter to finish)
    if request.task.strip().upper().startswith("DONE"):
        final_summary = request.task.strip().split("\n", 1)[1] if "\n" in request.task else ""
        finalize_markdown(workflow_id, final_summary)
        log_event_jsonl({"ts": ts(), "workflow_id": workflow_id, "type": "done", "summary": final_summary})
        return RouteResponse(ok=True, workflow_id=workflow_id, step=0, done=True, message="done")

    step = 0
    current_task = request.task

    while True:
        step += 1
        if step > MAX_STEPS:
            summary = f"Stopped after {MAX_STEPS} steps (safety cap)."
            finalize_markdown(workflow_id, summary)
            log_event_jsonl({"ts": ts(), "workflow_id": workflow_id, "type": "stopped_max_steps", "summary": summary})
            return RouteResponse(ok=True, workflow_id=workflow_id, step=step, done=True, message=summary)

        # Parse routing line
        sub_agent, raw_instruction = parse_routing_line(current_task)

        if sub_agent not in SUB_AGENTS:
            raise HTTPException(status_code=400, detail=f"unknown_agent:{sub_agent}")

        # Build guarded instruction (adds SubAgent prefix + Rule + exact ack line)
        guarded_instruction = guard_instruction(sub_agent, raw_instruction)

        # Persist step to Markdown + JSONL
        append_text(BUILD_SUMMARY_MD, md_step_line(workflow_id, step, sub_agent, guarded_instruction))
        log_event_jsonl({
            "ts": ts(),
            "workflow_id": workflow_id,
            "type": "step",
            "step": step,
            "agent": sub_agent,
            "instruction": guarded_instruction
        })

        # Call sub-agent (INTEGRATE THIS WITH WARP)
        agent_key = SUB_AGENTS[sub_agent]
        agent_response = call_sub_agent(agent_key, guarded_instruction)

        # Optional: enforce explicit rules-ack on first line
        if ENFORCE_RULE_ACK and RULE_TITLES.get(sub_agent):
            first_line = (agent_response or "").splitlines()[0].strip()
            m = re.match(ACK_PATTERN, first_line)
            ok_ack = m and (m.group("agent").strip() == sub_agent) and (
                        m.group("rule").strip() == RULE_TITLES[sub_agent])
            if not ok_ack:
                log_event_jsonl({
                    "ts": ts(),
                    "workflow_id": workflow_id,
                    "type": "warn",
                    "agent": sub_agent,
                    "warning": "rule_ack_missing_or_mismatch",
                    "expected": f"rules loaded (agent={sub_agent} | rule={RULE_TITLES.get(sub_agent, '')})",
                    "received": first_line
                })
                # Retry once with same instruction (idempotent)
                retries = 0
                while retries < MAX_ACK_RETRY and not ok_ack:
                    retries += 1
                    agent_response = call_sub_agent(agent_key, guarded_instruction)
                    first_line = (agent_response or "").splitlines()[0].strip()
                    m = re.match(ACK_PATTERN, first_line)
                    ok_ack = m and (m.group("agent").strip() == sub_agent) and (
                                m.group("rule").strip() == RULE_TITLES[sub_agent])

        # Persist agent response (truncated in JSONL for sanity)
        log_event_jsonl({
            "ts": ts(),
            "workflow_id": workflow_id,
            "type": "agent_response",
            "agent": sub_agent,
            "response_preview": (agent_response or "")[:4000]
        })

        # Auto-loop end?
        if not request.auto_loop:
            return RouteResponse(ok=True, workflow_id=workflow_id, step=step, agent=sub_agent, message="step_complete",
                                 done=False)

        # Ask TaskRouter for next routing line (INTEGRATE THIS WITH WARP)
        next_task = call_taskrouter_next_step(sub_agent, agent_response).strip()

        # DONE?
        if next_task.upper().startswith("DONE"):
            final_summary = next_task.split("\n", 1)[1] if "\n" in next_task else ""
            finalize_markdown(workflow_id, final_summary)
            log_event_jsonl({"ts": ts(), "workflow_id": workflow_id, "type": "done", "summary": final_summary})
            return RouteResponse(ok=True, workflow_id=workflow_id, step=step, agent=sub_agent, done=True,
                                 message="done")

        # Otherwise continue
        current_task = next_task


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("ROUTER_PORT", "8085"))
    uvicorn.run("router_mcp:APP", host="0.0.0.0", port=port, reload=False)
