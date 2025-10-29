# taskrouter_mpc.py
# MCP stdio server that exposes a "route" tool and forwards it to your FastAPI router.

import os
import requests
from typing import Union, Dict, Any

from mcp.server.fastmcp import FastMCP  # <- current SDK import

ROUTER_URL = os.environ.get("ROUTER_URL", "http://127.0.0.1:8085/route")

mcp = FastMCP("router-mcp-stdio")

@mcp.tool()
def route(
    task: str,
    auto_loop: bool = True,
    workflow_id: str = "",
    from_taskrouter: bool = True,
) -> Union[Dict[str, Any], str]:
    """
    Forward a routing line to the local FastAPI Router and return its response.
    Returns dict (JSON) when possible; falls back to text.
    """
    payload: Dict[str, Any] = {
        "task": task,
        "auto_loop": bool(auto_loop),
        "from_taskrouter": bool(from_taskrouter),
    }
    if workflow_id:
        payload["workflow_id"] = workflow_id

    try:
        r = requests.post(ROUTER_URL, json=payload, timeout=300)
        r.raise_for_status()
    except requests.HTTPError:
        # Surface body text to the client for debugging
        return f"Router HTTP {r.status_code}: {r.text}"
    except Exception as e:
        return f"Router request failed: {e}"

    # Prefer structured JSON content so Warp/LLM can key off fields
    try:
        return r.json()  # MCP will encode this as JSON content
    except ValueError:
        return r.text     # Fall back to text content

if __name__ == "__main__":
    print("Start server")

    # Default run mode is stdio; suitable for Warp's "command" MCP
    mcp.run()
