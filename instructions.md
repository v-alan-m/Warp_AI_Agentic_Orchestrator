1) What the user types in Warp (TaskRouter chat)
E.g:
```
workflow_id: site-scaffold-001

Use /docs/site-spec.md as the source of truth. Execute the full build:
- Scaffold structure and files as specified
- Implement Home (hero, #disciplines, #contact, skip link, landmarks)
- Implement all three service pages with back-to-/#disciplines CTA
- Implement About and minimal JS
- Commit safely

Respond only with routing lines step-by-step internally via router-mcp (auto_loop:true).
When complete, output:
DONE
<1–3 sentence final summary>
```

- TaskRouter’s visible reply to user (short ack):
	- Kicked off workflow (id: site-scaffold-001). I’ll summarize when done.


2) What TaskRouter sends to Router MCP (its internal tool call)

Endpoint: 'POST http://localhost:8085/route'
Body JSON (constructed by TaskRouter):

```
{
  "task": "FileCreator: Create folders /src/pages/services, /src/assets/styles, /src/assets/scripts and create files /src/pages/index.html, /src/pages/about.html, /src/pages/services/frontend.html, /src/pages/services/backend.html, /src/pages/services/robotics.html, /src/assets/styles/main.css, /src/assets/scripts/main.js",
  "auto_loop": true,
  "workflow_id": "site-scaffold-001",
  "from_taskrouter": true
}


'task' = first routing line TaskRouter chose from your brief.
'auto_loop:true' + 'from_taskrouter:true '= guaranteed autonomous run.
'workflow_id' = trace ID used in logs.
```

3) What Router writes during execution (your persisted logs)
A) 'docs/build-summary.md' (human log)

Example lines as the flow progresses:
```
- 2025-09-29T10:02:11 • `site-scaffold-001` • **FileCreator** → Create folders /src/pages/services, /src/assets/styles, /src/assets/scripts and create files /src/pages/index.html, /src/pages/about.html, /src/pages/services/frontend.html, /src/pages/services/backend.html, /src/pages/services/robotics.html, /src/assets/styles/main.css, /src/assets/scripts/main.js
- 2025-09-29T10:02:18 • `site-scaffold-001` • **FrontendDeveloper** → Implement /src/pages/index.html per /docs/site-spec.md (hero, #disciplines cards, #contact form, skip link to #main, semantic landmarks) and add base responsive styles in /src/assets/styles/main.css (WCAG AA).
- 2025-09-29T10:02:35 • `site-scaffold-001` • **FrontendDeveloper** → Implement /src/pages/services/{frontend,backend,robotics}.html; each with hero, offerings list, mini case studies, CTA back to '/#disciplines'; keep shared header/footer and active nav
- 2025-09-29T10:02:54 • `site-scaffold-001` • **FrontendDeveloper** → Implement /src/pages/about.html with story, values, leadership highlights, CTA to '/#contact'; consistent header/footer
- 2025-09-29T10:03:05 • `site-scaffold-001` • **FrontendDeveloper** → Update /src/assets/scripts/main.js: smooth internal anchor scroll, required-fields guard for #contact form, simple mobile menu toggle
- 2025-09-29T10:03:15 • `site-scaffold-001` • **GitWorkflow** → Stage all changes and commit with message 'feat(site): scaffold pages, base styles, minimal JS for consultancy'
```

When finished, Router appends a final block:
```
### 2025-09-29T10:03:20 — Final Summary (site-scaffold-001)
Scaffolded the consultancy site; implemented home, three service pages, about, base
```

B) docs/router_log.jsonl (structured log; one JSON per line)

Example lines:
```
{"ts":"2025-09-29T10:02:11","workflow_id":"site-scaffold-001","type":"step","step":1,"agent":"FileCreator","instruction":"Create folders ..."}
{"ts":"2025-09-29T10:02:18","workflow_id":"site-scaffold-001","type":"step","step":2,"agent":"FrontendDeveloper","instruction":"Implement /src/pages/index.html ..."}
{"ts":"2025-09-29T10:02:35","workflow_id":"site-scaffold-001","type":"step","step":3,"agent":"FrontendDeveloper","instruction":"Implement service pages ..."}
{"ts":"2025-09-29T10:02:54","workflow_id":"site-scaffold-001","type":"step","step":4,"agent":"FrontendDeveloper","instruction":"Implement about ..."}
{"ts":"2025-09-29T10:03:05","workflow_id":"site-scaffold-001","type":"step","step":5,"agent":"FrontendDeveloper","instruction":"Update main.js ..."}
{"ts":"2025-09-29T10:03:15","workflow_id":"site-scaffold-001","type":"step","step":6,"agent":"GitWorkflow","instruction":"Stage and commit ..."}
{"ts":"2025-09-29T10:03:20","workflow_id":"site-scaffold-001","type":"done","summary":"Scaffolded the consultancy site; implemented home, three service pages, about, base CSS/JS; committed initial version."}
```

C) 'docs/CHANGELOG.md' (per-run completion entry)
```
## 2025-09-29T10:03:20 — Workflow site-scaffold-001 Completed
Scaffolded the consultancy site; implemented home, three service pages, about, bas
```

4) What TaskRouter does mid-flow (invisible to the user)

- After each sub-agent returns, Router calls TaskRouter with the result.
- TaskRouter responds with the next routing line (e.g., tell FrontendDeveloper to implement services).
- Router logs the step, forwards to that sub-agent, and repeats.

You don’t see these intermediate messages in chat; they’re recorded in the logs above.


5) What the user finally sees in Warp (TaskRouter chat)

When the Router signals completion back to TaskRouter, TaskRouter prints only the DONE block:
```
DONE
Scaffolded the consultancy site; implemented home, three service pages, about, base CSS/JS; committed initial version.
```

6) Summary of the “who sends what where”

User → TaskRouter (chat, plain text): high-level brief (one message).
TaskRouter → Router (HTTP JSON): first 'SubAgent: instruction' with '{auto_loop:true, from_taskrouter:true, workflow_id}'.
Router ↔ TaskRouter (HTTP JSON): loop next steps until 'DONE'.
Router → disk: writes 'docs/build-summary.md', 'docs/router_log.jsonl', and 'docs/CHANGELOG.md'.
TaskRouter → User (chat): short “kicked off” ack at start, 'DONE + summary' at the end.

This is the full auto-run flow from a single, human-readable prompt.