#!/usr/bin/env python3
"""
FastMCP Router Server for Warp-RouterMCP Orchestration
Handles workflow initialization and step-by-step execution routing
"""

import json
import logging
from typing import Any, Optional, Dict, List
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
server = FastMCP("taskrouter-mcp")

# In-memory workflow storage
workflows = {}


class WorkflowState:
    """Manages workflow state including plan storage and execution tracking"""

    def __init__(self, workflow_id: str, all_steps: dict):
        self.workflow_id = workflow_id
        self.all_steps = all_steps
        self.completed_steps: set = set()
        self.execution_log: List[dict] = []
        self.file_manifest: Dict[str, List[str]] = {"created": [], "modified": []}
        # Build step lookup for O(1) access
        self._step_lookup: Dict[int, dict] = {
            step["step"]: step for step in all_steps.get("steps", [])
        }

    def mark_step_completed(
        self,
        step_number: int,
        agent_role: str,
        policy: str,
        task: str,
        files_created: list,
        files_modified: list,
    ):
        """Record step completion"""
        self.completed_steps.add(step_number)

        # Update file manifest
        self.file_manifest["created"].extend(files_created)
        self.file_manifest["modified"].extend(files_modified)

        # Add to execution log
        log_entry = {
            "step": step_number,
            "agent_role": agent_role,
            "policy": policy,
            "instruction": task,
            "status": "completed",
        }
        self.execution_log.append(log_entry)

        logger.info(f"Step {step_number} completed by {agent_role}")

    def is_complete(self) -> bool:
        """Check if all steps are completed"""
        total_steps = self.all_steps["total_steps"]
        return len(self.completed_steps) == total_steps

    def get_next_step(self) -> Optional[dict]:
        """Get the next unexecuted step"""
        total_steps = self.all_steps["total_steps"]

        for step_num in range(1, total_steps + 1):
            if step_num not in self.completed_steps:
                # Use lookup dict for O(1) access
                return self._step_lookup.get(step_num)
        return None

    def get_completion_response(self) -> dict:
        """Generate workflow completion response"""
        return {
            "status": "complete",
            "workflow_id": self.workflow_id,
            "message": f"Workflow {self.workflow_id} completed successfully.",
            "execution_log": self.execution_log,
            "summary": {
                "total_steps_completed": len(self.completed_steps),
                "files_created": len(set(self.file_manifest["created"])),
                "files_modified": len(set(self.file_manifest["modified"])),
                "agents_used": list(
                    set(
                        [
                            entry["agent_role"]
                            for entry in self.execution_log
                        ]
                    )
                ),
            },
        }


@server.tool()
def initialize_workflow(payload: dict) -> str:
    """
    Initialize workflow with all_steps_json
    Stores the complete plan and returns first step
    """
    try:
        # Validate payload type
        if payload.get("type") != "all_steps_json":
            return json.dumps(
                {"error": "Invalid type. Expected 'all_steps_json'"}
            )

        workflow_id = payload.get("workflow_id")
        if not workflow_id:
            return json.dumps({"error": "Missing workflow_id"})

        # Check for duplicate workflow
        if workflow_id in workflows:
            return json.dumps(
                {"error": f"Workflow {workflow_id} already exists. Use a unique workflow_id."}
            )

        # Validate payload structure
        if "total_steps" not in payload or "steps" not in payload:
            return json.dumps(
                {"error": "Missing required fields: total_steps or steps"}
            )

        if not isinstance(payload["steps"], list) or len(payload["steps"]) == 0:
            return json.dumps({"error": "steps must be a non-empty list"})

        # Create workflow state
        workflow_state = WorkflowState(workflow_id, payload)
        workflows[workflow_id] = workflow_state

        logger.info(
            f"Workflow {workflow_id} initialized with "
            f"{payload['total_steps']} steps"
        )

        # Get first step
        first_step = workflow_state.get_next_step()

        if not first_step:
            return json.dumps(
                {"error": "No valid first step found in workflow"}
            )

        response = {
            "status": "initialized",
            "workflow_id": workflow_id,
            "total_steps": payload["total_steps"],
            "message": "Workflow initialized and stored. Ready for step execution.",
            "first_step": {
                "step": first_step["step"],
                "agent_role": first_step["agent_role"],
                "policy": first_step["policy"],
                "instruction": first_step["instruction"],
                "context": f"Total steps: {payload['total_steps']}. "
                f"Goal: {payload.get('original_goal', 'Not specified')}",
            },
        }

        return json.dumps(response)

    except Exception as e:
        logger.error(f"Error initializing workflow: {str(e)}")
        return json.dumps({"error": f"Workflow initialization failed: {str(e)}"})


@server.tool()
def process_step_completion(payload: dict) -> str:
    """
    Process single_done_step_json
    Updates execution state and returns next step or completion status
    """
    try:
        # Validate payload type
        if payload.get("type") != "single_done_step_json":
            return json.dumps(
                {"error": "Invalid type. Expected 'single_done_step_json'"}
            )

        workflow_id = payload.get("workflow_id")
        if not workflow_id or workflow_id not in workflows:
            return json.dumps(
                {
                    "error": f"Workflow {workflow_id} not found. "
                    "Initialize with all_steps_json first."
                }
            )

        step_number = payload.get("step_number")
        if step_number is None:
            return json.dumps({"error": "Missing step_number"})

        workflow_state = workflows[workflow_id]

        # Validate step_number exists in workflow
        if step_number not in workflow_state._step_lookup:
            return json.dumps(
                {"error": f"Step {step_number} does not exist in workflow"}
            )

        # Check if step already completed
        if step_number in workflow_state.completed_steps:
            return json.dumps(
                {"error": f"Step {step_number} already completed"}
            )

        # Record step completion
        workflow_state.mark_step_completed(
            step_number=step_number,
            agent_role=payload.get("completed_agent_role", "Unknown"),
            policy=payload.get("completed_policy", "Unknown"),
            task=payload.get("completed_task", "Unknown"),
            files_created=payload.get("files_created", []),
            files_modified=payload.get("files_modified", []),
        )

        # Check if workflow is complete
        if workflow_state.is_complete():
            response = workflow_state.get_completion_response()
            logger.info(f"Workflow {workflow_id} completed")
            return json.dumps(response)

        # Get next step
        next_step = workflow_state.get_next_step()
        if not next_step:
            return json.dumps(
                {"error": "No next step found, but workflow not complete"}
            )

        response = {
            "status": "continue",
            "workflow_id": workflow_id,
            "next_step_number": next_step["step"],
            "total_steps": workflow_state.all_steps["total_steps"],
            "agent_role": next_step["agent_role"],
            "policy": next_step["policy"],
            "instruction": next_step["instruction"],
            "context": f"Step {next_step['step']} of "
            f"{workflow_state.all_steps['total_steps']}",
        }

        return json.dumps(response)

    except Exception as e:
        logger.error(f"Error processing step completion: {str(e)}")
        return json.dumps(
            {"error": f"Step processing failed: {str(e)}"}
        )


@server.tool()
def get_workflow_status(workflow_id: str) -> str:
    """Get current status of a workflow"""
    try:
        if workflow_id not in workflows:
            return json.dumps({"error": f"Workflow {workflow_id} not found"})

        workflow_state = workflows[workflow_id]
        total_steps = workflow_state.all_steps["total_steps"]
        completed = len(workflow_state.completed_steps)

        response = {
            "workflow_id": workflow_id,
            "status": "complete" if workflow_state.is_complete() else "in_progress",
            "progress": {
                "completed_steps": completed,
                "total_steps": total_steps,
                "percentage": (completed / total_steps * 100) if total_steps > 0 else 0,
            },
            "execution_log": workflow_state.execution_log,
            "file_manifest": workflow_state.file_manifest,
        }

        return json.dumps(response)

    except Exception as e:
        logger.error(f"Error getting workflow status: {str(e)}")
        return json.dumps(
            {"error": f"Status retrieval failed: {str(e)}"}
        )


@server.tool()
def health_check() -> str:
    """Health check endpoint"""
    return json.dumps(
        {
            "status": "healthy",
            "active_workflows": len(workflows),
            "service": "taskrouter-mcp",
        }
    )


if __name__ == "__main__":
    logger.info("Starting taskrouter-mcp server...")
    server.run(transport="stdio")
