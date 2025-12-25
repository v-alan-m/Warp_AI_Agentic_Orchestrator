# Project Template for TaskRouter-MCP Workflows

This template provides a standardized project structure for use with the TaskRouter-MCP orchestration system.

## 🚀 Quick Start

### 1. Copy This Template

```powershell
# Copy template to your new project location
cp -r project-template /path/to/your-new-project

# Or on Windows PowerShell:
Copy-Item -Recurse project-template C:\path\to\your-new-project
```

### 2. Customize the Spec File

Edit `docs/site-spec.yaml` to define your project:
- Update project metadata (name, description, goal)
- Define the workflow steps
- Specify which agents handle which tasks

### 3. Initialize Workflow with Warp

In Warp, use the TaskRouter agent:

```
As TaskRouter: Read /path/to/your-new-project/docs/site-spec.yaml and initialize a workflow with taskrouter-mcp
```

### 4. Execute the Workflow

Warp will return formatted steps. Copy and execute each one:

```
1. As FileCreator: Create the project directory structure
2. As TaskRouter: "All the steps for FileCreator are DONE"
```

## 📁 Template Structure

```
project-template/
├── README.md                 # This file
├── docs/
│   └── site-spec.yaml       # Project specification (EDIT THIS)
├── frontend/                 # Placeholder for frontend code
├── backend/                  # Placeholder for backend code
├── tests/                    # Placeholder for tests
├── design/                   # Placeholder for design artifacts
├── ux-research/             # Placeholder for UX research
└── planning/                # Placeholder for sprint planning
```

## 📝 Editing site-spec.yaml

The spec file uses YAML format. Key sections:

### Project Metadata
```yaml
project:
  name: "My Project"
  description: "Full description"
  goal: "What you want to build"
```

### Workflow Steps
```yaml
workflow:
  steps:
    - agent: FileCreator
      task: "What to create"
      details:
        - Specific detail 1
        - Specific detail 2
```

See `docs/site-spec.yaml` for the full template with examples.

## 🔧 Available Agents

Based on your Warp agent profiles:

- **FileCreator** - Creates files and scaffolding
- **BackendDeveloper** - Backend APIs and services
- **FrontendDeveloper** - Frontend UI components
- **UIDesigner** - Design artifacts and style guides
- **UXResearcher** - UX research deliverables
- **TestRunner** - Run and interpret tests
- **GitWorkflow** - Git operations
- **RapidPrototyper** - Quick prototypes
- **SprintPrioritizer** - Sprint planning

## 📖 Full Documentation

For complete usage instructions, see:
- `../SPEC_USAGE_GUIDE.md` - Detailed workflow guide
- `../README.md` - TaskRouter-MCP documentation
- `../SETUP_GUIDE.md` - Server setup instructions

## ✨ Tips

1. **Start Small**: Begin with 3-5 steps, expand later
2. **Be Specific**: Detailed instructions help agents work better
3. **Use Right Agent**: Match tasks to agent capabilities
4. **Check Spec**: Validate YAML syntax before initializing
5. **Iterate**: You can always create new workflows

## 🆘 Troubleshooting

### YAML Syntax Errors
```powershell
# Validate YAML (if you have Python)
python -c "import yaml; yaml.safe_load(open('docs/site-spec.yaml'))"
```

### Workflow Won't Initialize
- Check that taskrouter-mcp server is running
- Verify spec file path is correct
- Ensure all required fields are present

### Agent Not Available
- Check agent is configured in Warp
- Verify agent name matches your profile names
- Review agent policy restrictions

## 📞 Support

- See `../SPEC_USAGE_GUIDE.md` for detailed examples
- Check `../SETUP_GUIDE.md` for server setup
- Review agent policies in Warp settings

---

**Ready to start?** Edit `docs/site-spec.yaml` and initialize your workflow!
