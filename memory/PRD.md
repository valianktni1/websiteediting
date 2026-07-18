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

## 2026-07 (fork) — Per-site DOMAIN LOCK (belt-and-braces)
- Each site now has a `domain` field. If set, the app HARD-REFUSES to publish/restore unless the
  SFTP remote path contains that domain (case-insensitive substring). wifetobe locked to wifetobe.org.
- Enforced at TWO layers: _domain_guard() pre-check in publish/restore handlers (raises 400 BEFORE
  any SFTP connection — <1s, no 15s timeout), AND inside _sftp_push after path resolution.
- UI: Admin → Hostinger SFTP has a "Locked domain 🔒" field (sftp-domain). Publish confirm modal
  shows path_ok — when the path lacks the locked domain it renders a red "Blocked" state and DISABLES
  the confirm button (data-testid publish-blocked). publish-target endpoint returns domain + path_ok.
- Verified: 43/43 backend (new /app/backend/tests/test_domain_lock.py) + frontend flows (iteration_4.json).
- NOTE for future stateful backend tests: pytest.ini uses -n 2 --dist loadscope; keep stateful SFTP
  tests inside ONE class (TestDomainLockSuite) to avoid cross-worker DB races.

## 2026-07 (fork) — Multi-site + Super-admin "Add site" (SFTP pull)
- Role hierarchy: superadmin > admin > editor. Seeded admin auto-migrated to 'superadmin' on startup.
  require_admin allows admin+superadmin; require_super gates super-admin-only actions.
- NEW super-admin flow "Add a new site (pull from your server)" — POST /api/sites/add (require_super):
  connects via SFTP, recursively DOWNLOADS the whole remote folder into SITES_DIR/<slug>, ingests the
  pages, saves sftp config + locked domain. No uploads/redeploys. Self-cleans (rm dir + DB row) if no
  .html found. Guards: unique slug, required creds, 5000-file/500MB budget, 15s connect timeout,
  runs via asyncio.to_thread. Returns 200 {ok:false,message} on failure so UI shows it inline.
  Verified end-to-end against public SFTP test.rebex.net (pulled 16 files, ingested, self-cleaned).
- Multi-site dashboard: loads all sites; site-switcher dropdown when >1; editors are scoped to their
  assigned site_id (only see their site, no switcher). Admin settings → Sites add-site form is
  superadmin-only; regular admins still see the sites list + Re-ingest.
- Each new site gets its own client login via existing Users tab (assign editor to the site slug).
- REGRESSION (found+fixed by testing agent iter5): inserting /sites/add accidentally dropped the
  @api.post('/sites/{slug}/publish') decorator → publish 404. Restored. LESSON: when inserting an
  endpoint above another, keep the next endpoint's decorator in the replacement. 51/51 backend +
  frontend pass (iteration_5.json). Preview seeded with 2 sites: wifetobe (14pp) + demo-couk (2pp).

## 2026-07 (fork) — Add-site as ASYNC BACKGROUND JOB + Test connection
- USER ISSUE: "Add site does nothing" on live instance. Root cause: long synchronous SFTP pull held
  in one HTTP request → killed by their NGINX reverse proxy (timeout) → silent hang. Also they were on
  an OLD build (no Test button) and had left Remote path EMPTY.
- FIX: POST /api/sites/add now returns {job_id, slug} immediately; pull+ingest runs as an asyncio
  background task (tracked in _bg_tasks) that writes progress to Mongo collection add_jobs
  (state: starting/pulling/ingesting/done/error). Frontend polls GET /api/sites/add-status/{job_id}
  every 2s (90-tick cap) and shows live progress. No long-held request → proxy can't kill it.
  add_jobs has a 24h TTL index (created stored as Date).
- Added POST /api/sftp/test (super-admin, slug-less) + "Test connection" button on the add form for
  instant credential/path verification; missing-field hint shows which inputs are needed.
- Verified 55/55 backend + frontend against real SFTP (test.rebex.net) (iteration_6.json).
- HOSTINGER GOTCHAS for user: on port 65002 (SFTP-over-SSH) the username is the ACCOUNT user
  'u897891218' (NOT the FTP-style u897891218.wifetobe.org). Same host/user/password works for ALL
  their domains; only remote_path changes per site, e.g. /home/u897891218/domains/wifetobe.co.uk/public_html.
  User MUST fill Remote path (was left blank → defaults to primary domain public_html).
