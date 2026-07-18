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

## 2026-07 — Second site: Wife To Be (wifetobe.org)
- Delivered wifetobe-elementor.zip (v1.0.0) — 14 pages via EXACT-HTML approach
  (user asked to preserve everything, so 100% fidelity over native editability).
- Full SEO preserved (title/desc/keywords/canonical/OG/Twitter + JSON-LD),
  robots.txt, sitemap.xml, llms.txt, llms-full.txt served at root. Domain kept wifetobe.org.
- Build: /app/wpbuild/build_wtb.py ; plugin src /app/wpbuild/plugin2/wifetobe-elementor
- Verified on local WP: home + collections + boutiques render 1:1 (gaps were scroll-reveal
  animation, not lost content). Fixed duplicate <title> (block-theme + Canvas) via
  template_redirect ob_start dedup — added to BOTH plugins.
- Ivory bumped to 1.4.1 with the same single-title guard.

## Reusable pattern for future sites
1. build_wtb.py style exact converter (parameterize SRC/OUT/TOKEN/DOMAIN/ROOT_FILES).
2. Adapt PHP (prefix, asset css/js/font URLs, favicon, root-file list incl. any llms variants).
3. Test on local WP (/var/www/wp), screenshot with scroll, verify single <title> + SEO.

## 2026-07 — Website Editor (self-hosted in-context CMS) MVP
Goal: client logs into private TrueNAS app, edits existing Hostinger static site in-context
(click text to edit, click image to replace), Publish renders + backs up + SFTP-pushes to Hostinger.
Stack: React + FastAPI + MongoDB. Verified 16/16 backend + all frontend flows (testing agent iter 1).
- Auth: JWT httpOnly cookie, roles admin/editor, seeded admin from .env.
- Ingestion: parse each page HTML -> inject data-eid on leaf text + <img>, store template+regions+seo+head_assets.
- Editor: iframe loads editor-mode HTML (contenteditable + click-to-replace images), autosave.
- Publish: render clean HTML (data-eid stripped), copy assets + robots/llms/llms-full/sitemap,
  zip backup to backup dataset, SFTP upload (paramiko). SFTP unset -> render+backup only.
- Docker: docker-compose (mongo+backend+web nginx), app on :30042, volumes to TrueNAS datasets.
- Files: backend/server.py, frontend/src/App.js+App.css, docker-compose.yml, backend/Dockerfile,
  frontend/Dockerfile+nginx.conf, .env.example, README.md, backend/tests/backend_test.py.
Hardening backlog: brute-force lockout on login, cookie secure=True in prod, specific CORS origins,
2FA (deferred), multi-site management UI, version/rollback UI, per-user site scoping enforcement in editor.

## 2026-07 (fork) — Admin & client management UI shipped
Backend already had endpoints; added the full frontend + 3 hardening fixes. Verified 30/30 backend
pytest + 12/12 frontend E2E (iteration_2.json).
- Admin Settings modal (admin-only, App.js): Users tab (list/create/delete client users),
  Hostinger SFTP tab (per-site host/port/user/pass/remote_path), Sites tab (available-sites + ingest/re-ingest).
- Client page management: "+ New page" (copy of Home) and per-card delete (× on non-home pages);
  editors allowed, home page protected.
- Version history modal: lists auto-backups (per publish), one-click Restore (admin-only).
- Login hardening LIVE: 5 failed attempts -> 15-min lockout (db.login_attempts), 429 shown in UI.
- Fixes applied this fork:
  1. PUT /sites/{slug}/sftp preserves existing password when submitted blank ("leave blank to keep").
  2. create_page/delete_page scoped by user site_id for non-admin editors (scope_ok helper).
  3. /sites/{slug}/restore now require_admin.
- STILL MOCKED: SFTP publish/restore (no live Hostinger creds). publish=false/restore=false with a
  clear "SFTP not configured" message is EXPECTED until creds entered in Admin > SFTP tab.
- Backlog: cookie secure=True + specific CORS in prod, 2FA, editor iframe per-site scoping.

## 2026-07 (fork) — Hostinger SFTP go-live + Test Connection
- User located their Hostinger FTP/SSH details (IP 77.37.37.182, host wifetobe.org, user
  u897891218.wifetobe.org, SSH/SFTP port 65002, path public_html).
- Made publisher Hostinger-correct: SFTP now uses socket connect timeout (15s) and resolves
  home-RELATIVE remote paths (e.g. "public_html") via sf.normalize('.'), not absolute-from-root.
- Added "Test connection" button + POST /api/sites/{slug}/sftp/test (admin-only): connects, lists
  remote dir, returns friendly ok/fail message.
- CRITICAL FIX: paramiko is blocking — all SFTP work (test/publish/restore) now runs via
  asyncio.to_thread so a bad host can no longer hang/500 the event loop (was causing 502s).
  Verified: unroutable host fails in 15s with a clear message and server stays responsive.
- Default remote_path is now "public_html" (Hostinger-relative). SFTP creds NOT stored in preview
  (user enters their real password in the UI to go live).

## 2026-07 (fork) — Docker deploy: compose.yaml + dependency fix
- Wrote /app/compose.yaml (+ docker-compose.yml) in user's house style: git build-context
  (github.com/valianktni1/websiteediting.git#main:backend / #main:frontend), mongo + backend +
  frontend(:30042) + mongodump backup sidecar, network we-network. Datasets: app data
  /mnt/apps/website_editor/{mongo,sites,data}; backups /mnt/photographers_data/website_editor_backup/{site_backups,db_backups}.
- Backend now reads SUPERADMIN_EMAIL/PASSWORD/NAME (fallback ADMIN_*) and CORS_ORIGINS, and
  auto-ingests EVERY site subfolder in SITES_DIR on boot (not just wifetobe). frontend Dockerfile
  takes REACT_APP_BACKEND_URL build arg (default "" = same-origin via nginx /api proxy).
- BUILD FIX: backend/requirements.txt was the bloated default template incl. emergentintegrations==0.2.0
  (private index only) + boto3/pandas/numpy/jq/passlib/python-jose/etc. Docker build failed at pip.
  Trimmed to the 12 packages actually imported (fastapi, uvicorn, python-dotenv, pymongo, motor,
  pydantic, pyjwt, bcrypt, python-multipart, beautifulsoup4, lxml, paramiko). Verified: clean install
  from public PyPI in fresh venv, app imports (30 routes), pytest 30/30 (iteration_3.json).
- Deploy note: preview sandbox CANNOT reach Hostinger (their firewall blocks datacenter IPs) — SFTP
  Test/Publish only works from the TrueNAS deployment. User confirmed site files copied to
  /mnt/apps/website_editor/sites/wifetobe. Next: user Saves to GitHub + rebuilds in Dockge.

## 2026-07 (fork) — White-label + CRITICAL publish safety
- White-labelled: tab title "Ivory Digital Editor", removed ALL Emergent refs (emergent.sh desc,
  assets.emergent.sh script, PostHog analytics) from public/index.html; added Cormorant Garamond+Jost
  fonts. In-app brand → "Ivory Digital Editor". Footer "Hosted & powered by Ivory Digital · Weddings
  by Mark" on login + dashboard.
- NEAR-MISS FIXED: a bare remote_path "public_html" resolves (via sf.normalize('.')) to the account
  HOME (/home/USER/public_html) = the PRIMARY domain — publishing there overwrites the WRONG site.
  Hostinger per-domain path is /home/USER/domains/<domain>/public_html. 
  Guardrails added:
  1. SFTP tab hint now shows the full-path format and warns bare public_html is dangerous.
  2. Test connection returns the RESOLVED absolute target folder + item count + sample, with a warning.
  3. NEW Publish confirmation modal (PublishConfirm): Publish no longer fires immediately — it shows
     host + exact target folder + page count + overwrite warning, requires explicit confirm.
     Backed by GET /api/sites/{slug}/publish-target (current_user, no password leaked).
  4. wifetobe default remote_path set to /home/u897891218/domains/wifetobe.org/public_html.
  NOTE: _sftp_push only uploads/overwrites (sf.put) — it never deletes remote files.
