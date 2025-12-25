# Site-Spec.yaml Usage Guide

Complete guide for using the `site-spec.yaml` specification file with TaskRouter-MCP to automate project workflows.

---

## 📖 Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Creating Your Spec File](#creating-your-spec-file)
4. [Initializing Workflows with Warp](#initializing-workflows-with-warp)
5. [Executing Workflow Steps](#executing-workflow-steps)
6. [JSON Format Reference](#json-format-reference)
7. [Best Practices](#best-practices)
8. [Examples](#examples)
9. [Troubleshooting](#troubleshooting)

---

## Overview

### What is site-spec.yaml?

A YAML specification file that defines:
- **Project metadata** (name, description, goals)
- **Workflow steps** (sequence of tasks)
- **Agent assignments** (which agent handles each task)
- **Task details** (specific requirements)

### How It Works

```
1. You create site-spec.yaml in your project
   ↓
2. Warp reads the spec file
   ↓
3. Warp (with LLM) generates all_steps_json
   ↓
4. Warp calls taskrouter-mcp.initialize_workflow()
   ↓
5. MCP server stores workflow and returns first step
   ↓
6. You execute steps one by one
   ↓
7. Workflow completes with full execution log
```

---

## Quick Start

### Step 1: Copy the Template

```powershell
# Copy project template to your new project location
Copy-Item -Recurse project-template C:\path\to\my-new-project
```

### Step 2: Edit site-spec.yaml

Open `my-new-project/docs/site-spec.yaml` and customize:

```yaml
project:
  name: "My Project Name"
  description: "What this project does"
  goal: "What you want to build"

workflow:
  steps:
    - agent: FileCreator
      task: "Create project structure"
      details:
        - "Create /src directory"
        - "Create /tests directory"
```

### Step 3: Initialize Workflow

In Warp, using TaskRouter agent profile:

```
As TaskRouter: Read C:\path\to\my-new-project\docs\site-spec.yaml and initialize a workflow with taskrouter-mcp
```

### Step 4: Execute Steps

Warp will return formatted output like:

```
1. As FileCreator: Create project structure
2. As TaskRouter: "All the steps for FileCreator are DONE"
```

**Copy line 1**, switch to FileCreator agent in Warp, paste and execute.

When done, **copy line 2**, switch to TaskRouter agent, paste and execute.

Repeat until workflow completes.

---

## Creating Your Spec File

### File Location

**Standard location**: `<project-root>/docs/site-spec.yaml`

You can use custom paths, but the standard location is recommended for consistency.

### Basic Structure

```yaml
# Project metadata
project:
  name: "string"
  description: "string"
  goal: "string"

# Workflow definition
workflow:
  steps:
    - agent: "AgentName"
      task: "Task description"
      details:
        - "Detail 1"
        - "Detail 2"
```

### Project Section

```yaml
project:
  name: "E-Commerce Platform"
  description: "Full-stack e-commerce with cart and checkout"
  goal: "Build production-ready online store"
  
  # Optional but recommended
  type: "web-application"
  
  # Optional - helps agents understand tech choices
  stack:
    frontend: "Vue.js"
    backend: "Django"
    database: "PostgreSQL"
```

### Workflow Section

Each step requires:
- **agent**: Must match Warp agent profile name exactly
- **task**: High-level description (1 sentence)
- **details**: Array of specific sub-tasks

```yaml
workflow:
  steps:
    - agent: FileCreator
      task: "Set up project structure"
      details:
        - "Create /src, /tests, /docs directories"
        - "Add .gitignore for Python projects"
        - "Create README.md with project title"
    
    - agent: BackendDeveloper
      task: "Build product API"
      details:
        - "Create /api/products endpoint"
        - "Implement GET, POST, PUT, DELETE methods"
        - "Add pagination and filtering"
```

### Available Agents

Based on your Warp configuration:

| Agent | Purpose | Use For |
|-------|---------|---------|
| **FileCreator** | Create files and scaffolding | Directory structures, boilerplate |
| **BackendDeveloper** | Backend APIs and services | APIs, databases, business logic |
| **FrontendDeveloper** | Frontend UI components | HTML, CSS, JS, React/Vue components |
| **UIDesigner** | Design artifacts | Style guides, wireframes, design tokens |
| **UXResearcher** | UX research | Personas, journey maps, research plans |
| **TestRunner** | Run and interpret tests | Execute test suites, analyze results |
| **GitWorkflow** | Git operations | Commits, branches, PRs |
| **RapidPrototyper** | Quick prototypes | Proof-of-concepts, MVPs |
| **SprintPrioritizer** | Sprint planning | Backlogs, user stories, prioritization |

---

## Initializing Workflows with Warp

### The Prompt Format

**Basic format**:
```
As TaskRouter: Read <path-to-spec-file> and initialize a workflow with taskrouter-mcp
```

**Example**:
```
As TaskRouter: Read C:\projects\myapp\docs\site-spec.yaml and initialize a workflow with taskrouter-mcp
```

**With custom workflow ID**:
```
As TaskRouter: Read /project/docs/site-spec.yaml and initialize workflow "myapp-v1" with taskrouter-mcp
```

### What Happens Behind the Scenes

1. **Warp reads the spec file** using file reading tools
2. **Warp's LLM interprets** the YAML structure
3. **Warp generates** `all_steps_json` with correct format:

```json
{
  "type": "all_steps_json",
  "workflow_id": "myapp-001",
  "original_goal": "Build production-ready web app",
  "total_steps": 5,
  "steps": [
    {
      "step": 1,
      "agent_role": "FileCreator",
      "policy": "FileCreator Policy",
      "instruction": "Create project structure",
      "details": ["Create /src directory", "..."]
    }
  ]
}
```

4. **Warp calls** `taskrouter-mcp.initialize_workflow(all_steps_json)`
5. **MCP responds** with initialization confirmation and first step

### Validation

The MCP server validates:
- ✅ `type` field is "all_steps_json"
- ✅ `workflow_id` is unique
- ✅ `total_steps` matches steps array length
- ✅ Each step has required fields

If validation fails, you'll see a clear error message.

---

## Executing Workflow Steps

### Step Format

After initialization, TaskRouter returns:

```
1. As FileCreator: Create the project directory structure
2. As TaskRouter: "All the steps for FileCreator are DONE"
```

### Execution Flow

**Step 1: Execute the task**
1. Copy line 1: `As FileCreator: Create the project directory structure`
2. In Warp, switch to **FileCreator** agent profile
3. Paste the copied text into prompt
4. Send the prompt
5. FileCreator executes the task

**Step 2: Report completion**
1. Copy line 2: `As TaskRouter: "All the steps for FileCreator are DONE"`
2. Switch to **TaskRouter** agent profile
3. Paste and send
4. TaskRouter calls MCP to get next step

**Step 3: Repeat**
- TaskRouter returns the next step in same format
- Continue until workflow completes

### Completion

When all steps are done, TaskRouter returns:

```
Workflow complete! Summary:
- Total steps completed: 9
- Files created: 45
- Files modified: 12
- Agents used: FileCreator, BackendDeveloper, FrontendDeveloper, UIDesigner
```

---

## JSON Format Reference

### all_steps_json (Initialization)

Generated by Warp when reading site-spec.yaml:

```json
{
  "type": "all_steps_json",
  "workflow_id": "unique-id-123",
  "original_goal": "Project goal from spec",
  "total_steps": 5,
  "steps": [
    {
      "step": 1,
      "agent_role": "FileCreator",
      "policy": "FileCreator Policy",
      "instruction": "Task description",
      "details": ["Detail 1", "Detail 2"]
    },
    {
      "step": 2,
      "agent_role": "BackendDeveloper",
      "policy": "BackendDeveloper Policy",
      "instruction": "Another task",
      "details": ["Detail A", "Detail B"]
    }
  ]
}
```

### single_done_step_json (Step Completion)

Generated by TaskRouter when reporting completion:

```json
{
  "type": "single_done_step_json",
  "workflow_id": "unique-id-123",
  "step_number": 1,
  "total_steps": 5,
  "completed_agent_role": "FileCreator",
  "completed_policy": "FileCreator Policy",
  "completed_task": "Created project structure",
  "files_created": ["/src", "/tests", "/docs"],
  "files_modified": [],
  "original_goal": "Project goal"
}
```

### Required Fields

**For all_steps_json**:
- ✅ `type` (string): Must be "all_steps_json"
- ✅ `workflow_id` (string): Unique identifier
- ✅ `original_goal` (string): Project goal
- ✅ `total_steps` (integer): Number of steps
- ✅ `steps` (array): Step objects

**For each step object**:
- ✅ `step` (integer): Step number (1-indexed)
- ✅ `agent_role` (string): Agent name
- ✅ `policy` (string): Agent policy name
- ✅ `instruction` (string): Task description
- ✅ `details` (array of strings): Sub-tasks

---

## Best Practices

### 1. Writing Good Task Descriptions

**Good** ✅:
```yaml
task: "Create REST API endpoints for user management"
details:
  - "Implement POST /api/users for registration"
  - "Implement GET /api/users/:id for user profile"
  - "Add JWT authentication middleware"
```

**Bad** ❌:
```yaml
task: "Do the backend stuff"
details:
  - "Make it work"
```

### 2. Ordering Steps Logically

```yaml
workflow:
  steps:
    - agent: FileCreator        # 1. Structure first
      task: "Create directories"
    
    - agent: BackendDeveloper   # 2. Backend foundation
      task: "Set up server"
    
    - agent: BackendDeveloper   # 3. Backend features
      task: "Build APIs"
    
    - agent: FrontendDeveloper  # 4. Frontend (depends on APIs)
      task: "Build UI"
    
    - agent: TestRunner         # 5. Tests last
      task: "Run test suite"
```

### 3. Breaking Down Complex Tasks

Instead of one big step:

```yaml
# ❌ Too complex
- agent: BackendDeveloper
  task: "Build entire authentication system"
```

Use multiple focused steps:

```yaml
# ✅ Better
- agent: BackendDeveloper
  task: "Set up database schema for users"

- agent: BackendDeveloper
  task: "Implement registration endpoint"

- agent: BackendDeveloper
  task: "Implement login with JWT"
```

### 4. Matching Agents to Tasks

**Use the right agent for each job**:

| Task | Correct Agent | Why |
|------|--------------|-----|
| Create empty files | FileCreator | Boilerplate only |
| Write API code | BackendDeveloper | Business logic |
| Build React component | FrontendDeveloper | UI implementation |
| Define color palette | UIDesigner | Design tokens |
| Run pytest suite | TestRunner | Test execution |

### 5. Adding Sufficient Detail

Each detail should be a **single, clear action**:

```yaml
details:
  - "Create /backend/models/User.js with email, password, name fields"
  - "Add password hashing using bcrypt with salt rounds of 10"
  - "Implement email validation regex pattern"
  - "Add createdAt and updatedAt timestamp fields"
```

### 6. Validating Before Initialization

```powershell
# Check YAML syntax
python -c "import yaml; yaml.safe_load(open('docs/site-spec.yaml'))"

# Should print: no output = valid YAML
```

---

## Examples

### Example 1: Simple API Project

```yaml
project:
  name: "Todo API"
  goal: "RESTful API for todo items"

workflow:
  steps:
    - agent: FileCreator
      task: "Create project structure"
      details:
        - "Create /src, /tests directories"
        - "Add package.json and .gitignore"
    
    - agent: BackendDeveloper
      task: "Build todo CRUD API"
      details:
        - "Create Express server in /src/server.js"
        - "Implement GET /todos endpoint"
        - "Implement POST /todos endpoint"
        - "Implement DELETE /todos/:id endpoint"
```

### Example 2: Full-Stack App

```yaml
project:
  name: "Recipe Sharing Platform"
  goal: "Users can share and browse recipes"
  stack:
    frontend: "React"
    backend: "Node.js/Express"
    database: "MongoDB"

workflow:
  steps:
    - agent: FileCreator
      task: "Initialize project structure"
      details:
        - "Create /frontend and /backend directories"
        - "Add .gitignore, README.md"
    
    - agent: BackendDeveloper
      task: "Set up backend server"
      details:
        - "Initialize Express in /backend"
        - "Configure MongoDB connection"
        - "Set up environment variables"
    
    - agent: BackendDeveloper
      task: "Build recipe API"
      details:
        - "Create Recipe model (title, ingredients, instructions)"
        - "Implement POST /api/recipes"
        - "Implement GET /api/recipes with pagination"
    
    - agent: FrontendDeveloper
      task: "Build React frontend"
      details:
        - "Set up React app in /frontend"
        - "Create RecipeList component"
        - "Create RecipeForm component"
        - "Integrate with backend API"
    
    - agent: UIDesigner
      task: "Design component style guide"
      details:
        - "Define color palette"
        - "Document button and form styles"
```

---

## Troubleshooting

### YAML Syntax Errors

**Problem**: "Error parsing site-spec.yaml"

**Solution**:
```powershell
# Validate YAML
python -c "import yaml; yaml.safe_load(open('docs/site-spec.yaml'))"
```

Common YAML mistakes:
- Inconsistent indentation (use 2 spaces)
- Missing colons after keys
- Incorrect array syntax (use `- ` for list items)
- Quotes needed for strings with special chars

### Workflow Won't Initialize

**Problem**: MCP returns error on initialization

**Solutions**:
1. Verify taskrouter-mcp server is running
2. Check agent names match Warp profiles exactly
3. Ensure spec file path is correct
4. Validate all required fields are present

### Agent Name Mismatch

**Problem**: "Agent 'backend-dev' not found"

**Solution**: Use exact agent profile names from Warp:
- ✅ `BackendDeveloper` (correct)
- ❌ `backend-dev` (wrong)
- ❌ `Backend Developer` (wrong)

### Step Execution Fails

**Problem**: Agent can't complete the task

**Solutions**:
1. Check task is within agent's scope (see agent policies)
2. Add more specific details
3. Break complex tasks into smaller steps
4. Verify required files/dependencies exist

### JSON Format Errors

**Problem**: MCP rejects the all_steps_json

**Solution**: Ensure Warp generates correct format with:
- `"type": "all_steps_json"`
- Sequential step numbers (1, 2, 3...)
- `total_steps` matches array length
- Each step has all required fields

---

## Tips for Success

1. **Start with the template** - Easier than building from scratch
2. **Test YAML syntax** before initializing
3. **Use meaningful workflow IDs** - e.g., `myapp-v1`, `feature-auth`
4. **Keep steps focused** - 1 agent, 1 clear goal per step
5. **Add context in details** - File paths, specific requirements
6. **Review agent policies** - Understand what each agent can do
7. **Iterate on specs** - Refine based on what works
8. **Document assumptions** - Add comments in YAML for clarity

---

## Next Steps

1. **Copy the template**: `Copy-Item -Recurse project-template my-project`
2. **Edit site-spec.yaml**: Customize for your project
3. **Initialize workflow**: Use TaskRouter in Warp
4. **Execute steps**: Follow the formatted output
5. **Review results**: Check execution log on completion

---

## Additional Resources

- **Project Template**: `project-template/`
- **Template Spec**: `project-template/docs/site-spec.yaml`
- **MCP Documentation**: `README.md`
- **Setup Guide**: `SETUP_GUIDE.md`
- **Agent Policies**: Check your Warp rules configuration

---

**Ready to create your first workflow?**

Copy the template, edit site-spec.yaml, and initialize with Warp!
