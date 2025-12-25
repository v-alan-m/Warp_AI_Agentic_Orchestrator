# TaskRouter-MCP Setup & Usage Guide

Complete step-by-step guide for setting up and running the taskrouter-mcp FastMCP server, both locally and with Docker.

---

## Part 1: Local Development Setup (30 minutes)

### Step 1: Verify Prerequisites

```powershell
# Check Python version (must be 3.9+)
python --version

# Check pip is installed
pip --version
```

Expected output: Python 3.9+ and pip installed

### Step 2: Navigate to Project Directory

```powershell
cd <your_directory_location_to_here>\taskrouter_mcp
```

### Step 3: Create Virtual Environment (Optional but recommended)

```powershell
# Create virtual environment
python -m venv venv

# Activate it (PowerShell)
.\venv\Scripts\Activate.ps1

# Or for Command Prompt
venv\Scripts\activate.bat
```

After activation, your prompt should show `(venv)` prefix.

### Step 4: Install Dependencies

```powershell
pip install -r requirements.txt
```

Verify installation:
```powershell
pip list
```

You should see `mcp==1.0.0` in the list.

### Step 5: Run the Server Locally

```powershell
python taskrouter_mcp.py
```

Expected output:
```
INFO:__main__:Starting router-mcp server...
```

The server is now running and listening for MCP connections via stdio.

**To stop the server**: Press `Ctrl+C`

---

## Part 2: Docker Setup (45 minutes)

### Prerequisites

1. **Install Docker Desktop**: [Docker for Windows](https://docs.docker.com/docker-for-windows/)
2. **Verify installation**:
   ```powershell
   docker --version
   docker run hello-world
   ```

### Step 1: Verify Docker Files Exist

In `<your_directory_location_to_here>\taskrouter_mcp`, you should have:

```
✓ Dockerfile
✓ docker-compose.yml
✓ .dockerignore
✓ requirements.txt
✓ taskrouter_mcp.py
```

### Step 2: Build Docker Image

```powershell
# Navigate to project directory
cd <your_directory_location_to_here>\taskrouter_mcp

# Build image
docker build -t taskrouter-mcp:latest .
```

Expected output:
```
Successfully tagged taskrouter-mcp:latest
```

**Verify build**:
```powershell
docker images | findstr taskrouter-mcp
```

Should show:
```
taskrouter-mcp     latest    <IMAGE_ID>    2 minutes ago
```

### Step 3: Run Docker Container (Option A: Direct Docker)

```powershell
# Run container
docker run --name taskrouter-mcp -i -t taskrouter-mcp:latest
```

Expected output:
```
INFO:__main__:Starting router-mcp server...
```

**To stop**: Press `Ctrl+C`

**To remove container**:
```powershell
docker stop taskrouter-mcp
docker rm taskrouter-mcp
```

### Step 4: Run Docker Container (Option B: Docker Compose - Recommended)

```powershell
# Start service in background
docker-compose up -d

# View logs in real-time
docker-compose logs -f taskrouter-mcp
```

Expected logs:
```
taskrouter-mcp-server  | INFO:__main__:Starting taskrouter-mcp server...
```

**To stop**:
```powershell
docker-compose down
```

### Step 5: Verify Container is Running

```powershell
# List running containers
docker ps

# Should show taskrouter-mcp-server in the list
```

---

## Part 3: Configuring Warp Integration

### Step 1: Add taskrouter-mcp as MCP Server in Warp

1. Open **Warp Settings**
2. Go to **Tools → MCP Servers**
3. Click **Add Server**
4. Configure:

   **For Local Development:**
   ```
   Name: taskrouter-mcp (local)
   Type: stdio
   Command: python
   Arguments: <your_directory_location_to_here>\taskrouter_mcp\taskrouter_mcp.py
   ```

   **For Docker:**
   ```
   Name: taskrouter-mcp (docker)
   Type: stdio
   Command: docker
   Arguments: run --rm -i taskrouter-mcp:latest
   ```

5. Click **Save & Test**

### Step 2: Add taskrouter-mcp to Agent Profiles

For each agent profile (FileCreator, BackendDeveloper, FrontendDeveloper, etc.):

1. Go to **Settings → AI → Agents → [Agent Name]**
2. Under **Call MCP servers → MCP allowlist**
3. Add: `taskrouter-mcp`

---

## Part 4: Testing the Server

### Test 1: Health Check (Local)

```powershell
# Terminal 1: Start server
cd <your_directory_location_to_here>\taskrouter_mcp.py
python taskrouter_mcp.py
```

The server should start without errors.

### Test 2: Full Workflow Test (In Warp)

Send this prompt to a Warp chat with TaskRouter role activated:

```
Process these tasks in sequence:

1. As TaskRouter use the TaskRouter Policy: Check server health
```

Expected response: Health check confirmation

### Test 3: Initialize Workflow

```
Process these tasks in sequence:

1. As TaskRouter use the TaskRouter Policy: Initialize workflow with these steps:
{
  "type": "all_steps_json",
  "workflow_id": "test-workflow-001",
  "original_goal": "Test the router-mcp server",
  "total_steps": 2,
  "steps": [
    {
      "step": 1,
      "agent_role": "FileCreator",
      "policy": "FileCreator Policy",
      "instruction": "Create test files",
      "details": ["Create test.txt"]
    },
    {
      "step": 2,
      "agent_role": "BackendDeveloper",
      "policy": "BackendDeveloper Policy",
      "instruction": "Create test API",
      "details": ["Create test endpoint"]
    }
  ]
}
```

Expected response: Workflow initialized with first step details

---

## Part 5: Production Deployment

### Docker Push (Optional)

If you have a registry (Docker Hub, etc.):

```powershell
# Tag image
docker tag router-mcp:latest <your-registry>/router-mcp:latest

# Push
docker push <your-registry>/router-mcp:latest
```

### Docker Deployment

```powershell
# Stop current container
docker-compose down

# Pull latest
docker pull <your-registry>/router-mcp:latest

# Update docker-compose.yml image reference
# Change: build: .
# To: image: <your-registry>/router-mcp:latest

# Start updated service
docker-compose up -d
```

---

## Troubleshooting

### Problem: "ModuleNotFoundError: No module named 'mcp'"

**Solution**:
```powershell
# Verify virtual environment is activated (shows (venv) in prompt)
# If not: .\venv\Scripts\Activate.ps1

# Reinstall dependencies
pip install -r requirements.txt
```

### Problem: "Docker image build fails"

**Solution**:
```powershell
# Check Dockerfile syntax
docker build -t router-mcp:test .

# If still failing, rebuild with no cache
docker build --no-cache -t router-mcp:latest .
```

### Problem: "Container exits immediately"

**Solution**:
```powershell
# Check logs
docker logs router-mcp

# Run in interactive mode to see error
docker run -i -t router-mcp:latest

# If Python error, verify mcp module is installed
docker run -i -t router-mcp:latest python -c "import mcp; print('OK')"
```

### Problem: "Port already in use" (if using networking)

**Solution**:
```powershell
# Find process using port
netstat -ano | findstr :3000

# Kill process (replace PID with actual process ID)
taskkill /PID <PID> /F

# Or use different port in docker-compose.yml
```

---

## Useful Commands

### Local Development

```powershell
# Start server
python taskrouter_mcp.py

# Stop server
# Ctrl+C

# Deactivate virtual environment
deactivate
```

### Docker Management

```powershell
# List images
docker images

# List containers
docker ps

# View logs
docker logs router-mcp

# Remove image
docker rmi router-mcp:latest

# Remove all unused images
docker image prune -a
```

### Docker Compose

```powershell
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild image
docker-compose build --no-cache

# Restart services
docker-compose restart
```

---

## Next Steps

1. **Integrate with Warp** (Part 3 above)
2. **Configure agent profiles** to include router-mcp
3. **Test with sample workflows**
4. **Deploy to production** if needed

---

## References

- [Complete Architecture](./README.md)
- [Warp-RouterMCP Architecture](./Warp_RouterMCP_Architecture.md)
- [Docker Documentation](https://docs.docker.com/)
- [MCP Documentation](https://mcp.run)

---

## Support

For issues or questions, check:
1. Logs (in terminal or `docker logs`)
2. Troubleshooting section above
3. Architecture documentation
