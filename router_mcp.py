# router_mcp.py
# Drop-in Router MCP with:
# - Markdown persistence (CHANGELOG.md, build-summary.md)
# - JSONL structured logs
# - workflow_id support
# - Auto-loop toggle + step limit
#
# Usage:
#   pip install fastapi uvicorn pydantic
#   python router_mcp.py
#
# POST /route with JSON body:
# {
#   "task": "SubAgentName: instruction" | "DONE\nsummary...",
#   "auto_loop": false,
#   "workflow_id": "optional-custom-id"
# }
#
# Env vars (optional):
#   ROUTER_LOG_DIR=./docs
#   ROUTER_MAX_STEPS=10

import os
import re
import json
import uuid
import datetime as dt
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field
import uvicorn
from threading import Lock

# ----------------------------
# Config & Globals
# ----------------------------
LOG_DIR = os.environ.get("ROUTER_LOG_DIR", "./docs")
os.makedirs(LOG_DIR, exist_ok=True)
CHANGELOG_MD = os.path.join(LOG_DIR, "CHANGELOG.md")
BUILD_SUMMARY_MD = os.path.join(LOG_DIR, "build-summary.md")
JSONL_PATH = os.path.join(LOG_DIR, "router_log.jsonl")
MAX_STEPS_DEFAULT = int(os.environ.get("ROUTER_MAX_STEPS", "10"))

# simple file-append lock to avoid interleaving in concurrent calls
_write_lock = Lock()

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

# ----------------------------
# Models
# ----------------------------
class RouteRequest(BaseModel):
    task: str                       # "SubAgent: instruction" or "DONE\nsummary"
    auto_loop: bool = False         # toggle orchestration
    from_taskrouter: bool = False   # NEW: set True when TaskRouter auto-forwards
    workflow_id: Optional[str] = Field(default=None, description="Optional workflow/session id")
    max_steps: Optional[int] = Field(default=None, description="Optional per-request step cap")

class RouteResponse(BaseModel):
    target: str
    instruction: str
    forwarded: bool
    auto_loop: bool
    final_summary: Optional[str] = None
    workflow_id: str
    step_count: int

# ----------------------------
# Utilities: time, ids, I/O
# ----------------------------
def ts() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")

def ensure_workflow_id(maybe_id: Optional[str]) -> str:
    return maybe_id or str(uuid.uuid4())

def append_text(path: str, content: str) -> None:
    with _write_lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)

def log_event_jsonl(event: dict) -> None:
    with _write_lock:
        with open(JSONL_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

def md_step_line(workflow_id: str, step: int, agent: str, instruction: str) -> str:
    return f"- {ts()} • `{workflow_id}` • **{agent}** → {instruction}\n"

def md_done_block(workflow_id: str, summary: Optional[str]) -> str:
    header = f"## {ts()} — Workflow {workflow_id} Completed\n"
    body = (summary or "_No summary provided._").strip() + "\n"
    return header + body + "\n"

# ----------------------------
# TaskRouter integration stub
# (Replace with real call to Claude API / Warp TaskRouter)
# ----------------------------
def call_taskrouter(workflow_id: str, result: str) -> str:
    # TODO: Replace this with actual call to your TaskRouter (Claude API or Warp profile)
    # Must return either:
    #  - "SubAgent: refined instruction"
    #  - "DONE\n<final summary>"
    print(f"[RouterMCP] ({workflow_id}) -> TaskRouter: {result}")
    # Placeholder demo behavior:
    return "DONE\nAll tasks completed successfully."

# ----------------------------
# Core router logic
# ----------------------------
app = FastAPI(title="Router MCP", version="1.1.0")

@app.get("/health")
def health():
    return {"ok": True, "time": ts()}

@app.post("/route", response_model=RouteResponse)
def route_task(request: RouteRequest, _step_count: int = 0):
    """
    Parses TaskRouter output and (optionally) auto-loops until DONE.
    Persists steps and final summary to Markdown + JSONL with workflow_id.
    """
    # Enforce auto-loop on the very first TaskRouter-triggered call
    if _step_count == 0 and request.from_taskrouter and not request.auto_loop:
        request.auto_loop = True
    workflow_id = ensure_workflow_id(request.workflow_id)
    max_steps = request.max_steps or MAX_STEPS_DEFAULT
    task = request.task.strip()

    # DONE branch (finalization)
    if task.upper().startswith("DONE"):
        summary = task.split("\n", 1)[1].strip() if "\n" in task else None

        # Persist final summary to Markdown and JSONL
        append_text(CHANGELOG_MD, md_done_block(workflow_id, summary))
        append_text(BUILD_SUMMARY_MD, f"\n### {ts()} — Final Summary ({workflow_id})\n{summary or '_No summary provided._'}\n\n")
        log_event_jsonl({
            "ts": ts(),
            "workflow_id": workflow_id,
            "type": "done",
            "summary": summary
        })
        print(f"[RouterMCP] ({workflow_id}) DONE ✓  Summary: {summary}")

        return RouteResponse(
            target="DONE",
            instruction="Workflow finished",
            forwarded=False,
            auto_loop=request.auto_loop,
            final_summary=summary,
            workflow_id=workflow_id,
            step_count=_step_count
        )

    # Normal instruction branch: "Agent: instruction"
    match = re.match(r"^(\w+):\s*(.+)$", task)
    if not match:
        # Persist invalid input for traceability
        log_event_jsonl({
            "ts": ts(),
            "workflow_id": workflow_id,
            "type": "error",
            "message": "Invalid route format",
            "raw_task": task
        })
        return RouteResponse(
            target="None",
            instruction="Invalid format. Must be 'SubAgentName: instruction' or DONE",
            forwarded=False,
            auto_loop=request.auto_loop,
            workflow_id=workflow_id,
            step_count=_step_count
        )

    sub_agent, instruction = match.groups()

    if sub_agent not in SUB_AGENTS:
        # Persist unknown agent event
        log_event_jsonl({
            "ts": ts(),
            "workflow_id": workflow_id,
            "type": "unknown_agent",
            "agent": sub_agent,
            "instruction": instruction
        })
        return RouteResponse(
            target=sub_agent,
            instruction=instruction,
            forwarded=False,
            auto_loop=request.auto_loop,
            workflow_id=workflow_id,
            step_count=_step_count
        )

    # Persist step to Markdown + JSONL
    append_text(BUILD_SUMMARY_MD, md_step_line(workflow_id, _step_count + 1, sub_agent, instruction))
    log_event_jsonl({
        "ts": ts(),
        "workflow_id": workflow_id,
        "type": "step",
        "step": _step_count + 1,
        "agent": sub_agent,
        "instruction": instruction
    })

    print(f"[RouterMCP] ({workflow_id}) → {sub_agent}: {instruction}")
    # Simulate sub-agent execution result (replace with real sub-agent call if needed)
    result = f"[{sub_agent}] executed: {instruction}"

    # Auto-loop handling
    if request.auto_loop:
        if _step_count + 1 >= max_steps:
            # Persist step-limit stop
            stop_msg = f"Stopped due to step limit ({max_steps})."
            append_text(BUILD_SUMMARY_MD, f"- {ts()} • `{workflow_id}` • **Router** → {stop_msg}\n")
            log_event_jsonl({
                "ts": ts(),
                "workflow_id": workflow_id,
                "type": "stopped",
                "reason": "max_steps",
                "max_steps": max_steps
            })
            print(f"[RouterMCP] ({workflow_id}) ⛔ Max steps reached ({max_steps}).")
            return RouteResponse(
                target=sub_agent,
                instruction=stop_msg,
                forwarded=True,
                auto_loop=True,
                workflow_id=workflow_id,
                step_count=_step_count + 1
            )

        # Ask TaskRouter for the next instruction or DONE
        next_task = call_taskrouter(workflow_id, result)
        # Recurse with incremented step count
        return route_task(
            RouteRequest(
                task=next_task,
                auto_loop=True,
                workflow_id=workflow_id,
                max_steps=max_steps
            ),
            _step_count=_step_count + 1
        )

    # Manual mode: return after a single forward
    return RouteResponse(
        target=sub_agent,
        instruction=instruction,
        forwarded=True,
        auto_loop=False,
        workflow_id=workflow_id,
        step_count=_step_count + 1
    )

# Optional: simple abort endpoint to mark a workflow as aborted (manual kill switch)
@app.post("/abort/{workflow_id}")
def abort(workflow_id: str):
    note = f"[RouterMCP] ({workflow_id}) ❗ Aborted by user at {ts()}\n"
    append_text(BUILD_SUMMARY_MD, f"\n### {ts()} — Aborted ({workflow_id})\n")
    log_event_jsonl({
        "ts": ts(),
        "workflow_id": workflow_id,
        "type": "aborted"
    })
    print(note)
    return {"ok": True, "workflow_id": workflow_id, "status": "aborted"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8085)
