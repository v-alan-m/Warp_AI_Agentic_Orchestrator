# Software Consultancy Website — Spec (v1)

## Pages & Paths
- Home: `/src/pages/index.html`
- About: `/src/pages/about.html`
- Services:
  - Frontend: `/src/pages/services/frontend.html`
  - Backend: `/src/pages/services/backend.html`
  - Robotics: `/src/pages/services/robotics.html`

## Global Navigation
- Header: logo/title (links to `/src/pages/index.html`), nav links (Home, Services, About).
- “Services” in nav links to the **home** anchor `/#disciplines`.
- Footer: company info + link to `/#contact`.

## Home (`index.html`)
- **Hero**: headline, short subcopy, primary CTA button.
- **Skip link** at top: `href="#main"`.
- **Disciplines**: a `<section id="disciplines">` with 3 cards:
  - Frontend → `/src/pages/services/frontend.html`
  - Backend → `/src/pages/services/backend.html`
  - Robotics → `/src/pages/services/robotics.html`
- **Contact**: `<section id="contact">` with a simple form (name, email, message).
- Main landmark: `<main id="main">…</main>`.

## Service Pages (each of the 3)
- Hero/title, short overview paragraph.
- Bullet list of offerings.
- Mini case studies (2–3).
- CTA: button “Back to Services” linking to `/#disciplines`.
- Same header/footer as Home.

## About
- Company story, values, leadership highlights.
- CTA linking to `/#contact`.

## Assets
- CSS: `/src/assets/styles/main.css` (mobile-first, responsive).
- JS: `/src/assets/scripts/main.js`
  - Smooth-scroll internal anchors.
  - Required field guard for `#contact` form.
  - Simple mobile menu toggle.

## Accessibility (WCAG AA)
- Visible focus states; keyboard reachable.
- Color contrast AA; aria-labels where needed.
- Semantic HTML (landmarks: header/nav/main/footer).
- Form fields with `<label for>` and `aria-invalid` on error.

## Performance
- No frameworks required; defer non-critical JS.
- Optimized semantic markup; minimal CSS/JS.

## Acceptance Criteria (minimum)
1. All nav links and service links resolve to the correct pages.
2. `/#disciplines` and `/#contact` anchors work and smooth-scroll.
3. Service pages have “Back to Services” to `/#disciplines`.
4. HTML validates; CSS+JS load with no console errors.
5. Layout responsive at 360px, 768px, 1280px.
6. Skip link present and functional; focus styles visible.
