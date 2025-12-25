# TaskRouter-MCP Project Index

**Project Location**: `<your_directory_location_to_here>\taskrouter_mcp\`

## 📋 Quick Navigation

### Getting Started
1. **First time setup?** → Read `SETUP_GUIDE.md` (Part 1: Local Development)
2. **Want Docker?** → Read `SETUP_GUIDE.md` (Part 2: Docker Setup)
3. **Need full reference?** → Read `README.md`
4. **Architecture questions?** → Read `Warp_RouterMCP_Architecture.md`

### What This Project Is
FastMCP server that orchestrates multi-agent workflows in Warp. It manages:
- Workflow initialization from complete execution plans
- Step-by-step routing as tasks complete
- Execution tracking and logging
- State management across workflow lifecycle

## 📁 Files in This Project

### Application Code
| File | Purpose | Lines |
|------|---------|-------|
| `taskrouter_mcp.py` | Main FastMCP server | 267 |
| `requirements.txt` | Python dependencies | 1 |

### Docker Configuration
| File | Purpose |
|------|---------|
| `Dockerfile` | Container build configuration |
| `docker-compose.yml` | Compose service definition |
| `.dockerignore` | Build exclusion rules |

### Documentation
| File | Purpose | Audience |
|------|---------|----------|
| `README.md` | Full project documentation | Everyone |
| `SETUP_GUIDE.md` | Step-by-step setup instructions | Developers |
| `PROJECT_SUMMARY.md` | Project overview & reference | Quick lookup |
| `INDEX.md` | This file - quick navigation | Everyone |

### Reference
| File | Purpose |
|------|---------|
| `Warp_RouterMCP_Architecture.md` | Complete architecture specification |

## 🚀 Quick Start Commands

### Local (30 seconds to run)
```powershell
pip install -r requirements.txt
python taskrouter_mcp.py
```

### Docker (2 minutes to run)
```powershell
docker build -t taskrouter-mcp:latest .
docker-compose up -d
```

## 📊 Architecture Overview

```
Phase 1: Initialization
┌─────────────────┐
│ Warp            │
│ (creates plan)  │
└────────┬────────┘
         │ sends all_steps_json
         ↓
┌─────────────────┐
│ taskrouter-mcp  │
│ (stores plan)   │
└────────┬────────┘
         │ returns first step
         ↓
┌─────────────────┐
│ Warp            │
│ (executes)      │
└─────────────────┘

Phase 2: Execution Loop
┌─────────────────┐
│ Warp executes   │
│ current step    │
└────────┬────────┘
         │ sends single_done_step_json
         ↓
┌─────────────────┐
│ taskrouter-mcp  │
│ (track, find    │
│  next)          │
└────────┬────────┘
         │ returns next step or complete
         ↓
┌─────────────────┐
│ Warp            │
│ (next step)     │
└─────────────────┘
         ↑
         └── Loop until complete
```

## 🔧 What Each File Does

### taskrouter_mcp.py
The main server with 4 MCP tools:

1. **initialize_workflow** - Receives all steps, stores plan, returns first step
2. **process_step_completion** - Records step completion, returns next step
3. **get_workflow_status** - Returns current progress and execution log
4. **health_check** - Returns service health status

### Dockerfile
- Base: Python 3.11-slim
- Installs dependencies from requirements.txt
- Runs taskrouter_mcp.py

### docker-compose.yml
- Service named `taskrouter-mcp`
- Builds from Dockerfile
- Enables stdin/tty for stdio communication
- Maps logs directory

## 📝 JSON Formats

### Input: all_steps_json (initialization)
```json
{
  "type": "all_steps_json",
  "workflow_id": "site-001",
  "original_goal": "Build website",
  "total_steps": 5,
  "steps": [
    {
      "step": 1,
      "agent_role": "FileCreator",
      "policy": "FileCreator Policy",
      "instruction": "Create directories",
      "details": ["..."]
    }
  ]
}
```

### Input: single_done_step_json (step completion)
```json
{
  "type": "single_done_step_json",
  "workflow_id": "site-001",
  "step_number": 1,
  "total_steps": 5,
  "completed_agent_role": "FileCreator",
  "completed_policy": "FileCreator Policy",
  "completed_task": "Created directories",
  "files_created": ["project/api/"],
  "files_modified": [],
  "original_goal": "Build website"
}
```

### Output: Continue Response
```json
{
  "status": "continue",
  "workflow_id": "site-001",
  "next_step_number": 2,
  "total_steps": 5,
  "agent_role": "BackendDeveloper",
  "policy": "BackendDeveloper Policy",
  "instruction": "Create API endpoints",
  "context": "Step 2 of 5"
}
```

### Output: Complete Response
```json
{
  "status": "complete",
  "workflow_id": "site-001",
  "message": "Workflow completed successfully",
  "execution_log": [...],
  "summary": {
    "total_steps_completed": 5,
    "files_created": 15,
    "files_modified": 3,
    "agents_used": ["FileCreator", "BackendDeveloper", ...]
  }
}
```

## ✅ Checklist: What's Included

- ✅ Fully functional FastMCP server
- ✅ Docker containerization (Dockerfile + docker-compose.yml)
- ✅ Complete JSON format support
- ✅ Workflow state management
- ✅ Execution tracking & logging
- ✅ Error handling
- ✅ Comprehensive documentation
- ✅ Setup guide with troubleshooting
- ✅ This quick reference

## 🔗 Integration with Warp

1. **Add MCP Server** in Warp Settings → Tools → MCP Servers
2. **Configure for local dev**:
   - Name: `taskrouter-mcp`
   - Type: `stdio`
   - Command: `python`
   - Arguments: `<your_directory_location_to_here>\taskrouter_mcp\taskrouter_mcp.py`
3. **Add to agent profiles**: Each profile's MCP allowlist should include `taskrouter-mcp`
4. **Use TaskRouter role** to call the server

## 📖 Documentation Map

```
Start Here
    ↓
SETUP_GUIDE.md ← For setup instructions
    ↓
README.md ← For full reference
    ↓
Warp_RouterMCP_Architecture.md ← For architecture details
    ↓
taskrouter_mcp.py ← For code details
```

## 🆘 Troubleshooting Quick Links

| Problem | Solution |
|---------|----------|
| Import error: `No module named 'mcp'` | Run `pip install -r requirements.txt` |
| Docker build fails | Run `docker build --no-cache -t taskrouter-mcp:latest .` |
| Server won't start | Check Python version: `python --version` (need 3.9+) |
| Can't connect from Warp | Verify MCP server config in Warp Settings |

See `SETUP_GUIDE.md` → Troubleshooting for detailed solutions.

## 📊 Project Status

| Component | Status |
|-----------|--------|
| FastMCP Server | ✅ Complete |
| Docker Setup | ✅ Complete |
| Documentation | ✅ Complete |
| Testing | ✅ Ready |
| Production | ⚠️ Ready with caveats* |

*For production: Consider adding database, authentication, monitoring

## 🎯 Next Steps

1. **Read SETUP_GUIDE.md** - Pick Part 1 (local) or Part 2 (Docker)
2. **Follow the setup steps** - Takes 30-45 minutes
3. **Test with Warp** - Use health_check tool first
4. **Run sample workflow** - See SETUP_GUIDE.md Part 4

## 📞 Key Resources

- **Setup Help**: `SETUP_GUIDE.md`
- **API Reference**: `README.md` → API Endpoints section
- **Architecture Details**: `Warp_RouterMCP_Architecture.md`
- **Code Reference**: `taskrouter_mcp.py` (well-commented)

---

**Ready?** → `SETUP_GUIDE.md` Part 1 (Local) or Part 2 (Docker)

**Questions?** → Check relevant documentation file above

**Issues?** → See Troubleshooting section in `SETUP_GUIDE.md`
