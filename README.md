

# TaskRouter-MCP: Warp-RouterMCP Orchestration Server

FastMCP server implementation for managing multi-agent workflows in Warp. This server handles workflow initialization and step-by-step execution routing according to the Warp-RouterMCP Architecture.

# Why the Warp Orchestrator MCP exists 🧠

The Warp Orchestrator MCP turns “a collection of optimised agents” into a **repeatable, auditable workflow**. Instead of manually picking an agent and hoping Warp’s suggestions choose the right tools, the orchestrator codifies *how* work flows between agents (e.g. `FileCreator → FrontendDeveloper → BackendDeveloper → GitWorkflow`), which tools each is allowed to use, and how every step is logged. That means you get **deterministic multi-agent pipelines** with clear call stacks, build summaries, and change logs that can be replayed, debugged, or reused from any MCP-compatible client — not just Warp.

In practice, this MCP acts as a **policy + workflow brain** 🧩 on top of Warp’s agents:
- It enforces **hard boundaries** between sub-agents (who can read/write what, who can commit, who can refactor).
- It standardises cross-agent sequences (always plan → implement → test → commit → document) instead of leaving them to ad-hoc prompts.
- It produces **machine-readable logs** (`router_log.jsonl`, `build-summary.md`, `CHANGELOG.md`) so teams can inspect exactly what the AI did, when, and why.

The result is that AI work stops being a series of one-off chats and becomes a **governed, version-controlled pipeline** you can trust, repeat, and plug into other tools.

## Who is this for? (Use cases by scale) 🎯

### Individual developers & power users 👤💻
- **Structured solo workflows**  
  - Use TaskRouter as your “foreman” to always run a predictable chain: scaffold → implement → test → review → commit.
- **Reproducible refactors**  
  - Run the same orchestrated sequence on different repos and get comparable logs and summaries.
- **Safer automation experiments**  
  - Lock risky actions (e.g. `git push`, deployment scripts) behind a dedicated GitWorkflow agent, instead of giving every agent full shell access.

### Small businesses / agencies 🧑‍
- **Repeatable project templates**  
  - Define one orchestrated workflow for “new client project” (spec → scaffold → API → frontend → docs) and reuse it across clients.
- **Lightweight compliance & transparency**  
  - Hand clients a `build-summary.md` and `CHANGELOG.md` showing exactly what the AI changed in their repo.
- **Hybrid human+AI delivery**  
  - Humans review the orchestrator’s call stack and logs to quickly understand where to step in, fix, or extend work.

### Medium-sized product teams 🚀
- **Standardised multi-agent pipelines across squads**  
  - Keep the same orchestration logic (agents, order, safety rules) across multiple repos and services, instead of each team reinventing its own prompt stack.
- **Auditability for AI-generated changes**  
  - Feed router logs and summaries into internal dashboards, code review tooling, or incident post-mortems.
- **Policy enforcement via code, not culture**  
  - Encode rules like “only GitWorkflow can merge to `main`” or “BackendDeveloper must call TestRunner before handing off” directly into the orchestrator.

### Large organisations / platforms 🌐
- **Centralised AI governance layer**  
  - Treat the Orchestrator MCP as a **policy engine** that all Warp agents (and other MCP clients) must go through for critical repos.
- **Cross-tool reuse**  
  - Use the same orchestrated flows in Warp, in CI/CD bots, or in internal web portals, because the orchestration lives in an MCP server, not in a single UI.
- **Separation of concerns**  
  - Platform team maintains the orchestrator + policies; product teams just “ask for outcomes” and get consistent, logged multi-agent workflows in return.

> In short: Warp gives you powerful agents. This project gives you a **governed, portable way to orchestrate those agents** into real, production-grade workflows with clear rules, safety, and history.

## Architecture

This server implements two phases:

1. **Initialization Phase**: Receives `all_steps_json` containing the complete execution plan
2. **Execution Phase**: Processes `single_done_step_json` messages and returns next steps

See `Warp_RouterMCP_Architecture.md` for complete architecture documentation.

## Quick Start (Local Development)

### Prerequisites

- Python 3.9+
- pip

### Installation

1. **Clone/navigate to the project**:
   ```bash
   cd <your_directory_location_to_here>\taskrouter_mcp
   ```

2. **Create virtual environment** (recommended):
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Running Locally

```bash
python taskrouter_mcp.py
```

The server starts and listens for MCP connections via stdio.

**Note**: When using with Warp, you typically **do NOT need to run this manually**. Warp will automatically start the server when you use the TaskRouter agent. See the [Warp Integration](#warp-integration) section below.

## Warp Integration

### Configure MCP Server in Warp

The MCP server needs to be configured in Warp so the TaskRouter agent can access it.

#### Option 1: Configure via Warp Settings UI (Recommended)

1. Open **Warp Settings**
2. Navigate to **Features → Model Context Protocol**
3. Click **Add Server**
4. Configure the server:

   **Server Name**: `taskrouter-mcp`)
   
   **Command**: `python`
   
   **Arguments**: Add one argument:
   ```
   C:\Users\..\taskrouter_mcp.py
   ```
   (Replace with your actual path to `taskrouter_mcp.py`)
   
   **Working Directory**: 
   ```
   C:\Users\...taskrouter_mcp
   ```
   
   **Environment Variables**: Leave empty (or keep default)

5. Click **Save**
6. Test the connection using the test button

#### Record: Edit Configuration File Directly

Edit `warp_config/warp-mcp-config.yaml` and add/update:

```yaml
"taskrouter-mcp": {
  "command": "python",
  "args": [
    "C:\\Users\\...\\taskrouter_mcp.py"
  ],
  "env": {},
  "working_directory": "C:\\Users\\...\\taskrouter_mcp"
}
```

**Important**: Use double backslashes (`\\`) in the YAML file.

After editing, restart Warp to reload the configuration.

### Add to Agent Allowlist

Ensure the TaskRouter agent profile has access to the MCP server:

1. Open **Warp Settings → AI → Agent Profiles**
2. Create **TaskRouter** profile
3. Under **MCP Allowlist**, ensure `taskrouter-mcp` is listed
4. Repeat for any other agents that need access (typically only TaskRouter needs it)

### How It Works

When you use a prompt like:
```
As TaskRouter: Read C:\projects\my-app\docs\site-spec.yaml and initialize a workflow with taskrouter-mcp
```

Warp automatically:
1. ✅ Starts `taskrouter_mcp.py` in the background
2. ✅ Sends requests via stdin/stdout (stdio protocol)
3. ✅ Receives responses from the server
4. ✅ Closes the process when done

**No manual server startup required!**

### Troubleshooting

#### Server not found
- Verify the server name matches in both MCP config and agent allowlist
- Check the path to `taskrouter_mcp.py` is correct
- Ensure Python is in your PATH or use absolute path to python.exe

#### Connection timeout
- Verify dependencies are installed: `pip install -r requirements.txt`
- Check the working directory is set correctly
- Try running `python taskrouter_mcp.py` manually to test

#### Import errors
- Activate virtual environment if using one
- Reinstall dependencies: `pip install --force-reinstall -r requirements.txt`

## Docker Setup

### Prerequisites

- Docker 20.10+
- Docker Compose (optional but recommended)

### Files Needed

Create these files in the project directory:

#### 1. Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY taskrouter_mcp.py .

# Run the server
CMD ["python", "taskrouter_mcp.py"]
```

#### 2. docker-compose.yml (Optional)

```yaml
version: '3.8'

services:
  taskrouter-mcp:
    build: .
    container_name: taskrouter-mcp-server
    restart: unless-stopped
    environment:
      - PYTHONUNBUFFERED=1
    stdin_open: true
    tty: true
```

#### 3. .dockerignore

```
__pycache__
*.pyc
.pytest_cache
.git
.gitignore
venv/
README.md
```

### Building Docker Image

```bash
# Build the image
docker build -t taskrouter-mcp:latest .

# Verify build
docker images | grep taskrouter-mcp
```

### Running Docker Container

#### Using Docker (direct):

```bash
docker run --name taskrouter-mcp \
  -i \
  -t \
  taskrouter-mcp:latest
```

#### Using Docker Compose:

```bash
# Start service
docker-compose up -d

# View logs
docker-compose logs -f taskrouter-mcp

# Stop service
docker-compose down
```

### Stopping the Container

```bash
# Using docker
docker stop taskrouter-mcp
docker rm taskrouter-mcp

# Using docker-compose
docker-compose down
```

## Add other MCP servers

- To set up the other MCP servers in this porject please refer to the [MCP Server Setup Guide](MCP_servers_setup_guide.md).
  - Other MCP servers can be integrated into this project, using the same guide.

- We suggest you have a local backup of your MCP setup configuration (as Warp does not keep backups for you.)
  - The files [warp-agent-config.yaml](warp-agent-config.yaml) and [warp-mcp-config.yaml](warp-mcp-config.yaml)
  - To update this files please use this [GUI manager]: [mcp_gui_manager.py](mcp_gui_manager.py)

- If you add an LLM key into an .env file in the parent directory, it will autogenerate the new MCP server rule!
  - Paste this rule into Warp's rules for easy integration with this Taskrouter MCP server.
    - You can add more context to the rule after you autogenerate it with the GUI.

## Usage Examples

### How to Use This MCP Server

This MCP server is designed to work with the **TaskRouter agent** in Warp. The TaskRouter agent acts as the orchestrator that calls the MCP tools.

**Important**: 
- Always use `As TaskRouter:` at the start of your prompts (NOT `As taskrouter-mcp`)
- The TaskRouter agent has access to the `taskrouter-mcp` MCP server tools
- The MCP server name is `taskrouter-mcp`, but you interact through the TaskRouter agent

### Example 1: Initialize Workflow from Spec File

**Prompt to use in Warp**:
```
As TaskRouter: Read C:\projects\my-app\docs\site-spec.yaml and initialize a workflow with taskrouter-mcp
```

**What happens**:
1. TaskRouter agent reads the spec file
2. Generates `all_steps_json` from the spec
3. Calls `taskrouter-mcp.initialize_workflow()` MCP tool
4. Returns the first step in format:
   ```
   1. As FileCreator: Create the project directory structure
   2. As TaskRouter: "All the steps for FileCreator are DONE"
   ```

### Example 2: Execute a Workflow Step

**Step 1 - Execute the task**:
```
As FileCreator: Create the project directory structure
```
(Copy line 1 from TaskRouter's response, switch to FileCreator agent, paste and execute)

**Step 2 - Report completion**:
```
As TaskRouter: "All the steps for FileCreator are DONE"
```
(Copy line 2, switch back to TaskRouter agent, paste and execute)

**What happens**:
1. TaskRouter generates `single_done_step_json`
2. Calls `taskrouter-mcp.process_step_completion()` MCP tool
3. Returns next step or completion summary

### Example 3: Check Workflow Status

**Prompt to use in Warp**:
```
As TaskRouter: Check the status of workflow "myapp-001" using taskrouter-mcp
```

**What happens**:
- TaskRouter calls `taskrouter-mcp.get_workflow_status()` MCP tool
- Returns progress, execution log, and file manifest

### Example 4: Health Check

**Prompt to use in Warp**:
```
As TaskRouter: Check the health of taskrouter-mcp server
```

**What happens**:
- TaskRouter calls `taskrouter-mcp.health_check()` MCP tool
- Returns server status and active workflows count

### Complete Workflow Example

**Step 1: Copy project template**
```powershell
Copy-Item -Recurse project-template C:\projects\my-new-app
```

**Step 2: Edit spec file**
Edit `C:\projects\my-new-app\docs\site-spec.yaml` with your project details

**Step 3: Initialize workflow** (in Warp with TaskRouter agent):
```
As TaskRouter: Read C:\projects\my-new-app\docs\site-spec.yaml and initialize a workflow with taskrouter-mcp
```

**Step 4: Execute each step** (copy/paste from TaskRouter responses):
- Copy line 1, switch agent, execute
- Copy line 2, switch to TaskRouter, execute
- Repeat until complete

**Result**: Complete project built following your spec!

### Key Prompting Rules

1. **Always start with** `As TaskRouter:` - This activates the TaskRouter agent profile
2. **Reference the MCP** with `taskrouter-mcp` or `taskrouter-mcp` in your prompt (both work)
3. **Don't use** `As taskrouter-mcp:` - The MCP is a tool, not an agent
4. **For spec files**, use format: `Read [path] and initialize a workflow with taskrouter-mcp`
5. **For completions**, copy exact text: `"All the steps for [AgentName] are DONE"`

## API Endpoints (MCP Tools)

The server exposes these MCP tools:

### 1. `initialize_workflow`

**Input**: `all_steps_json` format
```json
{
  "type": "all_steps_json",
  "workflow_id": "site-scaffold-001",
  "original_goal": "Build website",
  "total_steps": 5,
  "steps": [
    {
      "step": 1,
      "agent_role": "FileCreator",
      "policy": "FileCreator Policy",
      "instruction": "Create directory structure",
      "details": ["detail 1", "detail 2"]
    }
  ]
}
```

**Output**: Initialization acknowledgment with first step

### 2. `process_step_completion`

**Input**: `single_done_step_json` format
```json
{
  "type": "single_done_step_json",
  "workflow_id": "site-scaffold-001",
  "step_number": 1,
  "total_steps": 5,
  "completed_agent_role": "FileCreator",
  "completed_policy": "FileCreator Policy",
  "completed_task": "Created directory structure",
  "files_created": ["project/api/", "project/templates/"],
  "files_modified": [],
  "original_goal": "Build website"
}
```

**Output**: Next step or completion status

### 3. `get_workflow_status`

**Input**: `workflow_id` (string)

**Output**: Current workflow status with progress and execution log

### 4. `health_check`

**Input**: None

**Output**: Service health status

## Workflow Execution Flow

```
Warp                      taskrouter-mcp
  |                              |
  |-- all_steps_json ----------->|
  |                              | (store plan)
  |<-- initialized + step 1 -----|
  |
  | Execute step 1
  |
  |-- single_done_step_json ---->|
  |                              | (mark complete, find next)
  |<-- continue + step 2 ---------|
  |
  | Execute step 2
  |
  |-- single_done_step_json ---->|
  |                              |
  | ... continue until ...       |
  |                              |
  |<-- complete + summary -------|
```

## Project Structure

```
taskrouter_mcp.py/
├── taskrouter_mcp.py           # Main server implementation
├── requirements.txt        # Python dependencies
├── Dockerfile             # Docker build configuration
├── docker-compose.yml     # Docker Compose configuration
├── .dockerignore          # Files to exclude from Docker build
└── README.md              # This file
```

## Workflow State Management

The server maintains:

1. **Workflow Storage**: Complete execution plan from `all_steps_json`
2. **Execution Tracker**: Which steps have completed
3. **File Manifest**: All files created/modified during execution
4. **Execution Log**: Detailed record of each step

## Error Handling

The server handles:

- Invalid request types
- Missing workflow IDs
- Duplicate workflow initialization
- Non-existent workflow references
- Missing required fields

All errors are returned as JSON with descriptive messages.

## Logging

The server logs all operations:

- Workflow initialization
- Step completions
- Errors and exceptions
- Service status

Check logs to verify proper operation.

## Production Considerations

For production deployment:

1. **Persistence**: Consider replacing in-memory storage with database
2. **Authentication**: Add API key or JWT validation
3. **Rate Limiting**: Implement request throttling
4. **Monitoring**: Add health check endpoints and metrics
5. **Error Recovery**: Implement workflow resumption from checkpoints

## Development

### Running Tests

```bash
python -m pytest tests/
```

### Code Style

```bash
black taskrouter_mcp.py
flake8 taskrouter_mcp.py
```

## Troubleshooting

### Server won't start

- Verify Python 3.9+ installed: `python --version`
- Check dependencies: `pip list`
- Review logs for error messages

### Docker image build fails

- Verify Docker installed: `docker --version`
- Check file permissions
- Review Dockerfile syntax

### Connection issues

- Verify MCP client configuration in Warp
- Check server logs for errors
- Ensure no port conflicts

## References

- [Warp-RouterMCP Architecture](./Warp_RouterMCP_Architecture.md)
- [MCP Documentation](https://mcp.run)
- [Docker Documentation](https://docs.docker.com/)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

### Usage

You are free to use, modify, and distribute the software, but you must retain the original copyright and provide appropriate credit to the author(s). This includes referencing the original project when redistributing or using it publicly, whether as-is or with modifications.

For more details on the MIT License, please check [MIT License](https://opensource.org/licenses/MIT).

