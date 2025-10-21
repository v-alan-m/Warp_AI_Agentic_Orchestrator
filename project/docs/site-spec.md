# Software Consultancy Website - Spec (v1)

## Initial File Structure
```yaml
project/
├─ WARP.md
├─ README.md
├─ api/
│  └─ main.py             # FastAPI app, Jinja, static mount, routes
├─ templates/
│  ├─ base.html           # head/css/js, header/nav/footer, skip link
│  └─ pages/
│     ├─ index.html
│     ├─ about.html
│     └─ services/
│        ├─ service_1.html
│        ├─ service_2.html
│        └─ robotics.html
├─ static/
│  ├─ css/
│  │  └─ main.css          # ← Tailwind compiled output
│  └─ js/
│     └─ main.js           # vanilla JS; adds smooth-scroll, form guard, menu
├─ assets/
│  └─ styles/
│     └─ input.css         # @tailwind base; @tailwind components; @tailwind utilities
└─ docs/
   ├─ site-spec.md
   ├─ build-summary.md
   ├─ CHANGELOG.md
   └─ router_log.jsonl
```


## Pages & Paths
- Home (Jinja): `project/templates/pages/index.html`
- About (Jinja): `project/templates/pages/about.html`
- Services (Jinja):
  - Service_1: `project/templates/pages/services/service_1.html`
  - Service_2: `project/templates/pages/services/service_2.html`
  - Robotics: `project/templates/pages/services/robotics.html`

## Global Navigation
- Header: logo/title (links to `/`), nav links (Home `/`, Services → `/#disciplines`, About `/about`)
- Footer: company info + link to `/#contact`.


## Home (`index.html`)
- All page content is delivered via Jinja templates under `project/templates/pages/...` and rendered by FastAPI routes.
- **Hero**: headline, short subcopy, primary CTA button.
- **Skip link** at top: `href="#main"`.
- **Disciplines**: a `<section id="disciplines">` with 3 cards:
  - Service_1 → `project/templates/pages/services/service_1.html`
  - Service_2 → `project/templates/pages/services/service_2.html`
  - Robotics → `project/templates/pages/services/robotics.html`
- **Contact**: `<section id="contact">` with a simple form (name, email, message).
- Main landmark: `<main id="main">…</main>`.

## Service Pages (each of the 3)
- All page content is delivered via Jinja templates under `project/templates/pages/...` and rendered by FastAPI routes.
- Hero/title, short overview paragraph.
- Bullet list of offerings.
- Mini case studies (2–3).
- CTA: button “Back to Services” linking to `/#disciplines`.
- Same header/footer as Home.

## About
- All page content is delivered via Jinja templates under `project/templates/pages/...` and rendered by FastAPI routes.
- Company story, values, leadership highlights.
- CTA linking to `/#contact`.

## Assets
- Tailwind CSS:
  - Source (with @tailwind directives): `project/assets/styles/input.css`
  - Built output (served as static):     `project/static/css/main.css`
- JavaScript (vanilla):
  - `project/static/js/main.js` (smooth-scroll, form guard for `#contact` form, mobile menu)
- Optional HTMX:
  - Include via CDN in base layout (e.g., `project/templates/base.html`) to enable progressive enhancement


## Accessibility (WCAG AA)
- Visible focus states; keyboard reachable.
- Color contrast AA; aria-labels where needed.
- Semantic HTML (landmarks: header/nav/main/footer).
- Form fields with `<label for>` and `aria-invalid` on error.

## Performance
- Minimal client JS; defer non-critical scripts.
- Tailwind is allowed; generate a single minified CSS output (`project/static/css/main.css`).
- HTMX allowed as progressive enhancement (no hard dependency).

## Backend (FastAPI + Jinja2)
- Framework: FastAPI (Python)
- Templates: Jinja2 templates in `project/templates/...`
- Static files: served from `project/static/` (CSS/JS)
- Routes:
  - `/` → `pages/index.html`
  - `/about` → `pages/about.html`
  - `/services/<name>` (service_1|service_2|robotics) → `pages/services/<name>.html`
  - `/contact` (POST): handle contact form; return JSON `{ok:true}` or template partial for HTMX swap
- Base layout: `project/templates/base.html` (includes skip link, global header/footer, CSS/JS, optional HTMX)


## Acceptance Criteria (minimum)
1. All nav links and service links resolve to the correct **routes** (`/`, `/about`, `/services/...`).
2. `/#disciplines` and `/#contact` anchors work and smooth-scroll.
3. Services pages include a “Back to Services” link to `/#disciplines`.
4. HTML validates; JS loads with no console errors.
5. Layout responsive at 360px, 768px, 1280px.
6. Skip link present and functional; focus styles visible.
7. FastAPI serves templates without 5xx; `/contact` POST returns 200 + JSON/partial.

