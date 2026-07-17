# WordPress/Elementor Plugin Builder — PRD

## Problem
User wants HTML/structured sites converted into installable WordPress plugin ZIPs whose
pages are editable in Elementor. Delivery = downloadable .zip via /app/frontend/public/downloads/.

## Delivered
1. Car Sales home page plugin (your-car-sales-elementor.zip) — native Elementor widgets,
   classy dealership home page, placeholder branding. (2026-07-17)
2. Ivory Digital full-site plugin (ivory-digital-elementor.zip) — all 22 pages converted
   from static HTML to Elementor pages. (2026-07-17)
   - Body: native, editable Elementor widgets (headings/text/images) carrying original CSS
     classes; buttons/nav/lists/icons/header/footer kept as exact markup.
   - Bundles original style.v3.css + Google fonts (Cormorant Garamond + Jost).
   - Exact per-page SEO via wp_head: title, meta, OG/Twitter, canonical, JSON-LD graph.
   - Serves robots.txt, sitemap.xml, llms.txt, llms_full.txt at site root.
   - Clean URLs (.html -> /slug/), home set as front page, Elementor Canvas template.
   - Admin importer under "Ivory Digital" menu; idempotent import + re-import/reset.

## Build tooling
- /tmp/build2/convert.py — HTML -> Elementor JSON converter (BeautifulSoup).
- Plugin source: /tmp/build2/plugin/ivory-digital-elementor/

## Not verified
- Could NOT test on a live WordPress/Elementor instance (not available in this env).
  PHP linted clean; all JSON validated. Final install/activate is done by user on Hostinger.

## Backlog / Next
- Optional: Elementor Pro (Pro Elements) global header/footer via Theme Builder.
- Optional: working contact/enquiry Form (Pro Elements) replacing mailto buttons.
- Optional: convert buttons to native Elementor Button widgets with replicated styles.
