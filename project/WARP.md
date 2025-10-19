# Project Rules (Warp)

**North Star:** Build a multi-page consultancy site in vanilla HTML/CSS/JS; keep accessibility (WCAG AA) and consistent navigation/backlinks.  
**Source of truth:** See `./docs/site-spec.md` for detailed layouts, sections, copy, and acceptance criteria.

## Scope & Boundaries
- Frontend: vanilla HTML/JS; **Tailwind CSS allowed** (single compiled output under `project/static/css/main.css`).
- Backend: **FastAPI** (Python) only, templates with **Jinja2** under `project/templates/...`, static under `project/static/...`.
- Enhancements: **HTMX** optional as progressive enhancement.
- Keep semantic landmarks and a skip link to `#main`.

## Musts (Non-Negotiable)
- **Accessibility:** WCAG AA contrast; `<header> <nav> <main id="main"> <footer>`; `<a href="#main">Skip to main</a>`.
- **Navigation:** Global header/footer; each services page has a “Back to Services” link to `/#disciplines`.
- **JS:** Smooth internal anchors; basic form validation; no console errors.
- **CSS pipeline:** Tailwind build must output a single `project/static/css/main.css` referenced by all pages.

## Style & Structure
- Mobile-first CSS compiled to `project/static/css/main.css` (Tailwind).
- Test at 360/768/1280px.
- Shared header/footer via base template (`project/templates/base.html`).

## Prohibitions
- No **frontend** frameworks (React/Vue/etc.) unless explicitly requested.
- No heavy client libraries; keep JS vanilla (HTMX allowed).
- Do not introduce backend frameworks other than **FastAPI**.
- Avoid speculative files outside routes/spec.


> For complete page requirements and acceptance criteria, follow `./docs/site-spec.md`.
