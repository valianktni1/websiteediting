# WordPress/Elementor Plugin Builder — PRD

## Goal
Convert static HTML sites into installable WordPress plugin ZIPs whose pages are
Elementor-editable. Deliver via /app/frontend/public/downloads/.

## Live test harness (persistent in /app/wpbuild, WP in /var/www/wp)
- Real WordPress + Elementor + plugin installed locally (MariaDB, php -S :8080).
- Playwright (local) screenshots front-end AND the Elementor editor for true verification.
- WP admin: admin/admin (LOCAL TEST ONLY).

## Deliverables
1. your-car-sales-elementor.zip — dealership home page (native widgets).
2. ivory-digital-elementor.zip — full Ivory Digital site, 22 pages. Current v1.4.0.
   - v1.0 native (broken layout) -> v1.1/1.2 exact-HTML blocks (fixed /assets/ double path)
     -> v1.3 version-aware auto-reimport -> v1.4 NATIVE editable rebuild.
   - v1.4: body sections rebuilt as NATIVE Elementor widgets (Heading/Text/Button/Divider/
     Icon/Accordion, card grids) styled to Ivory tokens (~99% match, 685 native widgets).
   - Complex sections kept as exact HTML blocks (safe fallback, still pixel-perfect):
     home hero w/ dashboard image, steps, 2-col showcases, pricing plans table,
     contact form, header, footer, breadcrumbs (76 html blocks total).
   - Exact per-page SEO via wp_head (title/meta/OG/Twitter/canonical + JSON-LD graph),
     robots.txt, sitemap.xml, llms.txt, llms_full.txt. Locked to https://ivorydigital.uk/.
   - Auto-refresh on version change; Home set as front page; clean URLs.

## Build tooling
- /app/wpbuild/convert.py         -> SEO/manifest/assets + (legacy) exact-HTML templates
- /app/wpbuild/native_convert.py  -> NATIVE Elementor templates (run: python3 native_convert.py all)
  (run convert.py first for data files, then native_convert.py to overwrite templates)

## Verified on real WP (screenshots)
- Front-end: home, pricing, contact, faq, studioapp, about, liverpool — match ~99%.
- Editor: heading shows editable Title field; Structure tree lists native widgets.

## Backlog
- Native mappings for steps / 2-col showcase / pricing plans / contact form (currently HTML).
- Optional: Pro Elements global header/footer (Theme Builder) + working Form widget.
