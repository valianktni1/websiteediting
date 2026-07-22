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

## 2026-07 (fork) — Editor power-up (structured rich editing)
- User: editor was "way too basic" (text + image-swap only). Upgraded to click-element → floating
  toolbar (injected in iframe, id #ed-tb) with actions, kept "structured" so layouts can't break.
- NEW abilities (all publish-clean, no data-eid leak):
  * Edit link/button URL — PUT /api/pages/{site}/{slug}/link {eid,href}; validates target is <a>/<button>.
  * Add another image (clone) / Duplicate / Delete / Add button — POST /api/pages/{site}/{slug}/op
    {op:add-image|duplicate|delete|add-button, eid}. add-button copies an existing .btn class.
- Backend refactor (careful, no regressions): shared assign_regions(body) re-indexes data-eid + builds
  regions with href/link flags (used by ingest AND ops); _set_html() clean fragment injection;
  render_page applies link hrefs. page_op BAKES current region values into the DOM before mutating so
  clones carry live edits, then re-indexes. Editor iframe reloads (setNonce) after each structural op.
- Frontend: Editor onMessage handles text/image/link/op; link uses window.prompt, delete uses confirm.
  Toolbar buttons are plain <button> in #ed-tb (no testids) — trigger via mousedown (handler uses
  mousedown+preventDefault to keep contenteditable focus).
- Verified 68/68 backend (new tests/test_editor_ops.py) + all frontend flows (iteration_7.json).
- BACKLOG (offered, not built): move up/down reordering of items; per-client branded login screen;
  Remove-site button; consider splitting server.py (~860 lines) into routes/ modules.


## 2026-07 (fork) — Fool-proof ROLLBACK (content snapshots)
- User wanted clients to self-rescue: roll back to "where they started" or an earlier time.
- DB CONTENT snapshots (Mongo 'snapshots' coll), separate from SFTP publish-file backups:
  * 'Original (as imported)' baseline once on first ingest (kind=import, kept forever).
  * 'Auto-saved' THROTTLED to max 1 per 10 min (maybe_auto_snapshot in update_region/update_link/
    page_op/update_seo). Prunes auto/pre-publish to newest 80.
  * 'Before publishing' snapshot on publish. Manual 'Save a restore point now' (kind=manual).
  * Restore deletes+reinserts all pages + restores site.order, and FIRST creates a 'Before restore'
    snapshot so the rollback itself is undoable.
- Endpoints: GET/POST /api/sites/{slug}/snapshots, POST /api/sites/{slug}/snapshots/{id}/restore
  (all scope_ok — editors roll back only their own site).
- Frontend: 'Restore points' modal (was Version history) — colour badges, friendly dates + 'X ago',
  'Roll back to here', 'Save a restore point now'; onRestored reloads dashboard site.
- CLOSED pre-existing RBAC hole: update_region + update_seo now enforce scope_ok.
- Verified 68/68 backend (tests/test_snapshots.py) + frontend (iteration_8.json).
- Test editor: editor_demo_couk@test.local / EditorPass!2026 (site_id=demo-couk) in preview DB.
- NOTE: rollback restores CONTENT into the editor; user then hits Publish to push it live.

## 2026-07-19 (fork) — 5-feature batch + CRITICAL image srcset bug fix
Shipped 5 backlog features (backend curl-verified; frontend UI test cut short, pending):
1. Auto restore point per session — POST /api/sites/{slug}/session-snapshot (kind='session',
   pruned with auto/pre-publish). Frontend fires once/session via sessionStorage key ivd_sess_<slug>.
2. Reorder items — page_op now supports move-up/move-down (find_previous/next_sibling + extract/insert).
   Editor toolbar gained '↑ Up' / '↓ Down' buttons (EDITOR_INJECT).
3. Undo last change — push_undo() saves page state to db.edit_history (cap 50/site) on every
   region/link/op/seo edit. POST /api/sites/{slug}/undo restores latest; GET .../undo-status for button
   enabled state. Editor header '↶ Undo last change' (data-testid editor-undo).
4. Client branding — sites get branding{brand_name,logo_url}+subdomain. Public GET /api/branding?host=
   maps first host label→site. Login screen shows logo+name. Admin → Branding tab (get/set + logo upload).
5. Remove site — DELETE /api/sites/{slug} (require_super): purges pages/snapshots/edit_history/add_jobs/
   site doc + SITES/MEDIA/DIST dirs, unassigns users. UI: Sites tab remove-site-<slug> w/ typed-slug prompt.

CRITICAL BUG (user: "added images to wifetobe.co.uk, published, not showing live"):
- ROOT CAUSE: source <img> tags use responsive srcset+sizes. Editor only updated `src`; browsers
  PREFER srcset, so the OLD image kept showing after replace.
- FIX: _apply_image(el,value) — when an image's value differs from its original template src, strip
  srcset/sizes/data-src(set)/data-lazy-*. Applied in render_page (editor + publish) AND page_op bake.
  Works RETROACTIVELY (compares value vs original src, no flag/migration). Unchanged imgs keep srcset.
- Verified via build render: replaced img → src set, srcset/sizes removed; unchanged imgs keep srcset.
- USER ACTION: Save to GitHub → rebuild containers → RE-PUBLISH (their existing edits auto-fix on re-publish).

## 2026-07-19 (fork) — Editor UX: in-editor Publish + Alt text + Bulk gallery upload
Follow-up to the srcset fix. Verified 100% (10/10) frontend UI in iteration_10.json (backend curl-verified).
1. Publish from the editor — Editor header now has a 'Publish to Hostinger' button (data-testid
   editor-publish-btn) that opens the SAME PublishConfirm modal; no need to go back to the dashboard.
2. Image alt text — regions now store `alt` (captured on ingest). Toolbar 'Alt text' button →
   window.prompt (prefilled from element) → PUT /api/pages/{site}/{slug}/alt {eid,alt}. _apply_image()
   gained an optional alt arg; render_page + page_op + bulk_image all apply it. Editors keep SEO after swaps.
3. Bulk gallery upload — toolbar '+ Add photos' (replaced '+ Add another') opens a MULTIPLE file input
   (bulk-image-input). Frontend uploads each file, then POST /api/pages/{site}/{slug}/bulk-image
   {eid, urls[]} clones the selected <img> once per url (srcset stripped via _apply_image), preserving order.
- Toolbar (in EDITOR_INJECT, inside iframe): Replace | + Add photos | Alt text | ↑ Up | ↓ Down |
  Duplicate | + Button | Delete | Link.
- NOTE (minor UX, not blocking, flagged by tester): hero <h1 contenteditable> can overlap the hero <img>,
  so a click near the very top may select the heading instead of the image. Consider pointer-events tweak.
- Carry-over review notes from tester were STALE: update_region/update_seo DO enforce scope_ok, and
  make_snapshot uses `body: dict | None = None` (not a mutable default). No action needed.

## 2026-07-19 (fork) — AI alt text + image crop/zoom + drag-to-swap reorder
Verified 100% for the 3 new features + regressions in iteration_11.json (backend curl-verified).
1. AI-suggested alt text — AltModal (replaces window.prompt): textarea + '✨ Suggest with AI' + Save.
   Backend POST /api/pages/{site}/{slug}/suggest-alt {eid} loads the image bytes (uploaded file / site
   asset / remote URL) and calls Gemini 2.5 Flash for a one-sentence alt. Returned a real description
   in testing (~4-8s). OPT-IN only (fires on button click) to keep cost near-zero.
   *** IMPORTANT — deployment-safe LLM call: DID NOT add emergentintegrations to requirements.txt
   (it broke their public-PyPI Docker build before). Instead call the Emergent proxy directly via
   stdlib urllib: POST https://integrations.emergentagent.com/llm/chat/completions (OpenAI-compatible),
   model 'gemini/gemini-2.5-flash', Authorization: Bearer EMERGENT_LLM_KEY. No new backend deps. ***
   USER DEPLOY ACTION: add EMERGENT_LLM_KEY to their Dockge environment for AI to work in production.
2. Image crop/zoom on upload — react-easy-crop (added to package.json). Replace flow opens CropModal
   with aspect = the selected image's on-screen slot (clientW/H, sent as d.ar from the iframe), so photos
   always fit the layout. crop-stage/crop-zoom/crop-save. Bulk '+ Add photos' auto-center-crops each file
   to the slot aspect (no per-photo UI) then uploads. All uploads go through /media then region/bulk-image.
3. Drag-to-swap reorder (images only, user's choice) — galleries here wrap each <img> in its own card
   div, so DOM ↑/↓ moves are ineffective; instead images are draggable=true and dropping one onto another
   posts op 'swap-image' {eid, ref} which swaps the two image regions' value+alt (layout-safe, no DOM move).
   ↑/↓ buttons remain as fallback. Backend: PageOp gained optional `ref`; swap-image handled early in page_op.
- MINOR (non-blocking, flagged twice by tester, not fixed): hero <h1 contenteditable> overlays the hero
  <img>, so a click near the very top can select the heading instead of the image. Gallery images unaffected.

## 2026-07-19 (fork) — Alt-Everywhere (bulk AI alt) + optional gallery captions
Both backend-verified end-to-end via curl (job lifecycle, caption render/leak/blank cases).
1. Fill missing alt text — SEO panel button (data-testid fill-alt-btn). POST /api/pages/{site}/{slug}/fill-alt
   finds image regions with empty alt and runs a BACKGROUND JOB (alt_jobs coll, 24h TTL, tracked in
   _bg_tasks) that AI-fills each via Gemini 2.5 Flash; frontend polls GET .../fill-alt-status/{job_id}
   every 2s and shows "Writing alt text… X/Y". Background job avoids the reverse-proxy timeout that a
   long synchronous multi-image request would hit. One push_undo + snapshot taken at job start.
2. Gallery captions — toolbar 'Caption' button → window.prompt. Stored as `data-caption` ON THE IMG in the
   template (PUT /api/pages/{site}/{slug}/caption {eid,caption}) so it survives structural ops (clones carry
   it, assign_regions leaves it intact). render_page inserts a <figcaption class="ivd-caption"> after the img
   ONLY when caption is non-empty (blank = image only, verified 0 figcaptions). data-caption is stripped on
   publish (never leaks). A tiny .ivd-caption style is injected into <head> so captions look right on the live
   site. Editor keeps data-caption so the toolbar prefills the current value.
- No new backend deps. react-easy-crop remains the only added npm package.

## 2026-07-19 (fork) — Block-level duplicate/delete (whole "card") — for car listings etc.
Backward-compatible, verified end-to-end (temp cars-test page: duplicate 2→3, delete 3→2, data-block kept on
publish, data-eid stripped, 400 guard when no block ancestor). Frontend compiles.
- MECHANISM (explicit, no guessing): a container is duplicatable ONLY if the DESIGNER marks it with a
  `data-block="car"` (any value) attribute when building the site. The editor toolbar then shows gold
  "Duplicate <name>" / "Delete <name>" buttons (class ed-block-btn) whenever the selected element has a
  [data-block] ancestor (el.closest('[data-block]')). Sites without data-block are UNCHANGED.
- Backend: page_op ops 'duplicate-block'/'delete-block' — finds target by data-eid, then
  target.find_parent(attrs={'data-block':True}); clones (copy) or decomposes that whole container; then
  assign_regions re-indexes. Guard: 400 if no [data-block] ancestor. push_undo + snapshot as usual (undoable).
- data-block is a plain data attribute: preserved through ingest, edits, and publish (harmless, keeps blocks
  duplicatable). Only data-eid + data-caption are stripped on publish.
- Frontend: delete-block asks a confirm ("Remove this whole card/block?"); flashes "Card duplicated"/"Card removed".
- DESIGN GUIDANCE for car-sales pages (when building in Emergent, then ingesting):
  * Wrap each car in a self-contained container with data-block="car" (gallery + specs + enquiry button inside).
  * Make the image slider AUTO-DETECT its images from children on load (CSS scroll-snap or JS that inits from
    child imgs) so clients' "+ Add photos" become new slides on the published static page. Avoid sliders that
    hard-code slide counts or need manual re-init.
  * Clients then: edit spec text, replace/add/crop/reorder/caption photos, AI alt, Duplicate car (new listing),
    Delete car (sold). All self-serve, per-site scoped.

## 2026-07-19 (fork) — Reusable car-sales page TEMPLATE (static, CMS-ready)
Built a professional static car-sales page and verified it ingests cleanly.
- FILES: /app/sites_source/car-demo/ (index.html + assets/style.css + assets/slider.js). Now also a live
  demo site "car-demo" in the preview CMS (superadmin can open it in the editor).
- DESIGN: dark premium dealership aesthetic; Sora (headings) + Manrope (body); amber accent (#d7a24b);
  sticky header, two-col hero (showroom img in framed card + stats), light "Our latest arrivals" grid of car
  cards, dark "Why us" + CTA strip + footer. Micro-interactions (hover lift/zoom). No AI-slop patterns.
- CMS-READY BY DESIGN: 54 editable text regions, 8 editable <img>, 2 <article data-block="car"> cards
  (→ Duplicate/Delete car buttons), galleries are .gallery>img.slide (each img IS a slide, so "+ Add photos"
  = new slides), slider.js auto-inits from child imgs on load (CSS scroll-snap + arrows/dots), full SEO head.
- Placeholder photos are remote Unsplash/Pexels (client replaces via editor upload). For real garage sites,
  reuse this folder as the starting point (rename brand, swap images) OR build fresh in a separate Emergent
  chat following the same rules (static HTML, editable content as <img>+text, data-block per car).

## 2026-07-19 (fork) — Car dealership template enhancements FINALIZED (badges + enquiry + block reorder)
Completed the 4-feature batch the user requested ("do 1, 2, 4 & 5"): Sold/Reserved/New-in status
badges, per-car Enquiry form, whole-car block reordering, and status styling. Verified 100% (6/6)
frontend editor flows in iteration_12.json; backend ops curl-verified.
1. Status badges — page_op ops 'status-sold'/'status-reserved'/'status-new'/'status-clear' set/clear
   data-status on the closest [data-block] car card. Editor toolbar 'Status' button (posts t:'status')
   opens StatusModal (App.js:723) with SOLD/RESERVED/NEW IN/Clear (data-testid status-sold|reserved|new|clear).
   CSS: .car[data-status='sold']::before red 'Sold' pill + grayscale slider + strikethrough price;
   reserved=orange, new=green.
2. Enquiry form — static template: each car has .enquire-btn + <body data-enquiry-email>. slider.js
   initEnquiry() builds a per-car popup (name/phone/email/message) that opens a prefilled mailto: to the
   dealer. Ribble Valley baked with sales@ribblevalleychequeredflag.co.uk.
3. Whole-car block reorder — page_op 'move-block-up'/'move-block-down' sibling-swaps the [data-block]
   card. Editor toolbar gold '◀ Move' / 'Move ▶' buttons (ed-block-btn). Persists to Mongo, iframe reloads.
4. Static assets merged into BOTH templates: /app/sites_source/car-demo (the live CMS demo, re-ingested)
   AND the branded Ribble Valley site. Appended status/enquiry CSS + upgraded slider.js (slider+menu+enquiry).
DELIVERABLES (clickable, served from /app/frontend/public/downloads/):
- car-sales-template.zip — clean generic starter template (Apex Motors placeholder) for reuse.
- ribble-valley-chequered-flag-website.zip — full branded client site with the new features integrated.
CLEANUP: removed stray zips accidentally left inside /app/sites_source/car-demo by the prior session.
BACKLOG: Finance Calculator (P2, user postponed); modularize server.py + App.js (P3).

## 2026-07-19 (fork) — Live RV site "looks unstyled" — diagnosed as STALE CACHE (not a bug)
- User shared a GoFullPage PDF of live https://maroon-mouse-620417.hostingersite.com/car-sales/ showing
  the whole page UNSTYLED (giant SVG icons, plain nav, car images stacked full-width, no cards/slider).
- INVESTIGATION: all assets return 200 with correct MIME (style.css=text/css, slider.js=application/x-javascript);
  live style.css (12232 bytes) already contains BOTH brand chrome AND the new badge/enquiry rules (== our
  latest file); live slider.js has initEnquiry. A clean headless Chromium (Playwright) renders the page
  PERFECTLY. => The user's captured browser used a STALE cached stylesheet/script (Hostinger sets
  cache-control: public, max-age=604800 = 7 days) from an earlier upload stage.
- FIX (real, forward-looking): appended cache-busting ?v=20260719 to the style.css + slider.js links in
  BOTH car-sales/index.html (RV) and /app/sites_source/car-demo/index.html, so every browser fetches the
  fresh files. Rebuilt both download ZIPs. User needs to re-upload car-sales/index.html (assets unchanged).
- NOTE: car-demo DB copy in the CMS was NOT re-ingested (keeps clean no-query asset paths for the editor
  preview, which serves assets via /api/asset/). Only the deliverable HTML carries ?v=.

## 2026-07-19 (fork) — Page Templates library + brand-adaptive "Add page from template"
Superadmin can add reusable page designs to any site; the added page adopts the site's own header/footer
and auto-adapts to its brand colours + fonts. Verified 100% (8/8) frontend E2E in iteration_13.json;
backend curl-verified + rendered-preview screenshot.
- BRAND TOKENS: sites.branding extended with accent, accent_dark, on_accent, heading_font, body_font,
  font_link. Auto-extracted on ingest (extract_brand/autofill_brand: scans site CSS for --accent/--primary/
  etc. + Google-Fonts <link> families; fills blanks only, never overwrites). Editable in Admin > Branding
  (colour pickers + font fields). GET/PUT /api/sites/{slug}/branding now include tokens.
- TEMPLATE LIBRARY: new `templates` collection. Built-in seeded on startup (idempotent by key). CRUD:
  GET /api/templates (admin), POST /api/templates (super, paste name+HTML+CSS+JS), DELETE (super, builtin
  protected). Admin > Templates tab (list + add-your-own + delete; built-ins show a badge, no delete).
- ADD FROM TEMPLATE: POST /api/pages/{site}/from-template {template_id, slug, title, enquiry_email}.
  Composes: site Home <header> + <main>{template.sections_html}</main> + site <footer> (_chrome_from_home);
  head_assets = Home head_assets + injected :root {--brand-accent/-dark/-heading/-body} (_brand_root_style)
  + template CSS <style> + template JS <script>; strips stale data-eid/data-caption then assign_regions.
  Frontend AddPageModal has a blank/template segmented toggle; enquiry-email field shows only for car template.
- SEED TEMPLATE (/app/backend/templates_seed.py): "Used Cars / Stock page" — NAMESPACED 'uc-' classes (no
  collision with host site CSS) + TOKENISED var(--brand-accent)/var(--brand-heading) so it takes on the
  site palette; hero + 2 data-block='car' cards (sliders, Sold/Reserved badges, per-car enquiry) + why + CTA.
  Fully editable in the CMS (Status/Move/Duplicate car buttons work on template-created pages).
- Verified on car-demo: added page adopted Apex Motors header/footer + amber #d7a24b accent + Sora/Manrope.

## 2026-07-19 (fork) — ivorydigital.uk prepped: editor-ready + performance + SEO (deliverable ZIP)
User supplied their real Hostinger public_html.zip (22 pages). Preserve-&-enhance (no rebuild, nothing lost).
Transform script /tmp/ivory_ph/transform.py (regex-only, NOT bs4 — avoids lowercasing SVG viewBox):
- COMPATIBILITY: rewrote root-absolute ="/assets/" → relative ="assets/" on all 22 pages so the editor
  canvas renders STYLED (base-href only rewrites relative). Publish output unaffected (root-relative works live).
- EDITOR-FRIENDLY: added data-block to 122 repeating containers (card/step/plan divs + 10 <a class="card">
  city cards on locations.html) → duplicate/delete whole card in the editor.
- PERFORMANCE: loading="lazy" on all non-first images (20). Images already well-optimised (948KB total).
- SEO: tightened 19 over-long meta descriptions (180–216ch) to ≤158ch, keywords+intent preserved; og/twitter
  descriptions left untouched. City pages already had excellent schema (Service/BreadcrumbList/FAQPage/
  areaServed/ProfessionalService) — no change needed. Added hyphenated llms-full.txt (publisher looks for hyphen).
- VERIFIED: diff shows only intended changes; viewBox intact (7, 0 lowercase); rendered preview fully styled
  (logo, gold accents, fonts, cards). All 22 pages valid (header+footer+</html>), 0 leftover root-absolute assets.
- DELIVERABLE: /api/download/ivorydigital-editor-ready.zip (50 files, drop-in replacement for public_html).
  NOTE: accent auto-detect won't fire (palette var is --gold #A78C46 not --accent) → set #A78C46 in Brand panel.

## 2026-07-20 (fork) — Broadfield Motor Co: ultra-modern demo front page (bikes-first)
User asked for an "ultra modern but elegant" front page for Broadfield Motor Company (Alfa Romeo used-car
specialist, Blackburn, now expanding into used MOTORBIKE sales) with EQUAL/MORE emphasis on motorbikes.
Built a self-contained static page in /app/sites_source/broadfield (index.html + assets/style.css + app.js).
- Design (via design_agent, /app/design_guidelines.json): Obsidian black #050505 + Rosso Corsa #C82829;
  fonts Oswald (condensed headings) + Playfair Display italic (heritage) + Manrope (body). Sections: glass
  sticky nav w/ red phone CTA (01254 875970), 60/40 HERO split (bikes 60% left / Alfa 40% right, hover-zoom),
  red Playfair marquee, BIKES bento grid (4 cards, data-block, Sold/Reserved badges), Alfa editorial split,
  servicing (dark workshop bg + 3 cards), red trust strip, VISIT contact + enquiry form, big "LET'S TALK" footer.
- Editor-ready: data-block on all repeating cards; images+text editable; relative asset paths.
- Real imagery via image_selector (bikes/Alfa/workshop) — all 8 image URLs verified 200.
- Verified: hero renders pixel-perfect to brief (screenshot); CSS valid (161/161 braces); all 7 sections
  present + well-formed. NOTE: screenshot tool only returns top-of-page frame, so lower sections verified
  structurally + via CSS validity rather than visually.
- DELIVERABLES: live preview /bf-check/index.html (temp, scrollable in real browser) +
  /api/download/broadfield-motor-co-homepage.zip (drop-in demo to show the client).
- Phone/contact used: 01254 875970, 07412 707606, Blackburn Lancashire.
- 2026-07-20: replaced text wordmark with user's uploaded logo (assets/logo.png, whitespace trimmed +
  white→transparent via Pillow, 463x500, 132KB). Displayed white on dark nav/footer via CSS filter:invert(1).
  Logo is now an <img> (nav + footer) so it's click-to-replace in the editor. ZIP re-packaged.

## 2026-07-20 (fork) — Auto image optimisation on upload (free, no AI)
Client uploads are now compressed automatically at the single upload choke point
(POST /api/media/{slug}/upload → upload_media, uses optimize_image()).
- Converts to WebP quality 82 method 6; caps longest side at MAX_IMG_DIM=2000px; auto-rotates by EXIF;
  preserves transparency (RGBA); strips metadata. SVG + animated GIF pass through untouched; any file
  Pillow can't read falls back to original bytes.
- Verified via curl: 3000x2000 JPEG 976KB → 2000x1333 WebP 97KB (~90% smaller); transparent PNG stays RGBA.
  Response now also returns {bytes, original_bytes}.
- Transparent to the frontend (same endpoint/response shape; url now .webp). Covers both crop-replace and
  bulk-photo upload flows (both POST to /media/{slug}/upload).
- DEPENDENCY: added Pillow==12.3.0 to backend/requirements.txt (surgical append). Pillow has manylinux
  wheels — safe for the TrueNAS Docker build. REQUIRED for this feature on their instance.

## 2026-07-20 (fork) — Editor fixes: link-click-through + whole-card duplicate for portfolio cards
User bug on ivorydigital web-design-seo 'Our Work' grid (<a class="folio" href target=_blank> cards):
clicking a card's text to edit opened the linked example site; duplicate broke grid spacing; no add-card.
- FIX 1 (EDITOR_INJECT): capture-phase document click handler preventDefault on any e.target.closest('a')
  → links NEVER navigate in the editor canvas. Applies at render time (no re-ingest needed).
- FIX 2 (importer): _tag_repeating_blocks(body) in ingest_page (before assign_regions) auto-tags repeating
  card-like siblings (div/article/li/a/section sharing a class, containing a heading OR img+p) with
  data-block=<firstclass>. Nav/link lists excluded (no heading/media). So .folio (and .card etc.) become
  whole-card blocks → "Duplicate <block>" clones the full card as a grid sibling (spacing preserved).
  Needs RE-INGEST of existing sites to take effect.
- "Add another placeholder" = "Duplicate <card>" (clones full card, then edit the copy).
- VERIFIED iteration_15.json 6/6 PASS: click-to-edit no longer opens linked site; Duplicate folio adds a
  complete 5th card in the same grid (gap 26px, 533px cols preserved, 5/5 children are A.folio); delete/undo
  work; car-demo block ops regression PASS.
- USER ACTION: rebuild Docker (new code) + RE-INGEST ivorydigital for the whole-card duplicate to appear.

## 2026-07-20 (fork) — Editor toolbar declutter + card Link button
User: toolbar "very messy and confusing" (~10 buttons incl. car-only Status on non-car cards); no Link
button to change an example card's destination URL.
- DECLUTTER (EDITOR_INJECT select()): split into element group + a "Card:" group (span.ed-div divider).
  Element move/dup/delete only shows for standalone elements (not block children). Status gated on
  blk.hasAttribute('data-status') → only car-template cards, NOT folio/generic cards.
- CARD LINK: assign_regions now gives non-leaf <a href> (card/image links) a data-eid + {type:'link'}
  region (render_page applies href). select() adds a "Link" button in the Card group when the block is an
  <a>. Card-wrapping <a> are NOT contenteditable.
- TESTING-AGENT-FOUND BUG (fixed by testing agent, reviewed OK): PUT /pages/{}/{}/link rejected type='link'
  regions with 400 — validator now accepts type in ('text','link'); adds legacy link:True only for text type.
- VERIFIED iteration_16.json 6/6 PASS: folio h3 toolbar = [Card: | Link, Duplicate, ◀Move, Move▶, Delete]
  (no Status); Link prompt edits + persists card URL; no navigation on click; standalone <p> shows element
  group only; car-demo cars still show Status; car card link N/A. Test data restored.
- USER ACTION: rebuild Docker + RE-INGEST ivorydigital (card links become editable at import time).

## 2026-07-20 (fork) — Importer fix: root-absolute /assets → relative (fixes "massive icons" in editor)
User reported (on their self-hosted TrueNAS) that ivorydigital renders unstyled ("massive icons") in the
editor and the Templates tab isn't visible after updating.
- ROOT CAUSE of massive icons: sites using root-absolute asset refs (src="/assets/..", href="/assets/x.css")
  bypass the editor's <base href="/api/asset/{slug}/"> and 404 → unstyled canvas.
- FIX: added _relativize_assets() in server.py, called at top of ingest_page(). Rewrites src="/..",
  srcset="/..", asset-extension href="/..*.css|js|png|svg|woff..", and url(/..) to relative. Nav links
  (href="/about/") are LEFT UNTOUCHED (no asset extension). Safe for publishing (pages are flat at site root).
- VERIFIED (iteration_14.json, 5/5 PASS): ingested ivorydigital renders fully styled in editor (Cormorant
  Garamond serif, ivory bg, gold accents, small logo, 0 root-absolute asset refs, style.v3.css 200 via
  /api/asset route). Templates tab present + functional. car-demo regression styled. from-template toggle works.
- CONCLUSION on user's report: the CODE is correct in preview. Their "can't see Templates" + "massive icons"
  = STALE Docker frontend build on their self-hosted instance. They must: (1) Save to GitHub, (2) REBUILD the
  Docker images in Dockge (not just restart) so the new React bundle builds, (3) hard-refresh browser,
  (4) RE-INGEST ivorydigital after deploy (the /assets fix applies at ingest time; existing DB pages keep old
  paths until re-imported).
- NOTE: existing sites already ingested before this fix need re-ingesting to pick up relativized paths.

## 2026-06-13 (fork) — ROOT CAUSE of recurring "can't see new features" = BuildKit git-cache
- User (correctly) runs: down → `build --no-cache backend frontend` → `up -d`, and re-ingests. Yet
  features kept "missing". Verified GitHub main HAS all latest code (every marker matched workspace),
  so "Save to GitHub" works fine.
- REAL ROOT CAUSE: their compose builds from a GIT URL context (github…#main:backend / #main:frontend).
  Docker BuildKit caches git sources by commit SHA and `--no-cache` does NOT clear the git-source cache,
  so builds re-used a stale clone. Confirmed via docs/issues (buildx#2924, SO 77670224).
- FIX GIVEN TO USER (foolproof rebuild): add `docker builder prune -af` BEFORE build (+`--force-recreate`).
- PERMANENT VISIBILITY FIX (shipped): BUILD_VERSION bumped to 2026-06-13-cms-v5; NEW frontend/src/version.js
  (UI_BUILD, baked into the React bundle at build time); Footer now fetches /api/version and displays
  "Build · UI <x> · API <y>" (data-testid build-stamp) — turns RED "⚠️ mismatch — rebuild needed" if the UI
  and API builds differ, so a stale container is instantly visible. Verified: footer shows matching v5 in preview.
- USER WORKFLOW GOING FORWARD: after rebuild, glance at the login/dashboard footer. If it doesn't read the
  expected build (or shows a mismatch), the corresponding container is stale → prune + rebuild that service.

## 2026-06-13 (fork) — Finance Calculator + "+ Blank card" (car templates)
Both self-tested (curl + standalone render screenshot). BUILD bumped to cms-v5.
1. FINANCE CALCULATOR (buyer-facing, static, no backend/AI): initFinance() added to
   /app/sites_source/car-demo/assets/slider.js (+ CSS in style.css) AND to the "used-cars" page
   template (templates_seed.py USED_CARS_JS/CSS, refreshed on startup via $set upsert). Parses each
   car's price, injects a "From £X/mo" pill under the car head + a "Finance example ›" button that
   opens a shared popup: cash price, deposit range slider (default 10%), term buttons 24/36/48/60
   (default 48), live estimated monthly, representative-APR disclaimer (default 12.9%), and an
   "Ask us about finance" CTA that hands off to the existing enquiry modal. Configurable via body/root
   data-attrs: data-finance-apr / data-finance-term / data-finance-deposit-pct. PURELY RUNTIME — never
   stored, so it covers every car incl. cloned/blank ones; publish-clean. GUARDED with
   `if(window.self!==window.top)return` so it does NOT run inside the CMS editor iframe (keeps
   click-to-edit clean). Verified: £21,995 → £530/mo @48m/10%/12.9% (correct amortised PMT).
2. "+ BLANK CARD": new page_op op `add-blank-block`. Clones the selected [data-block] card, then
   (a) collapses each image gallery to ONE placeholder slide (BLANK_IMG grey "+ Add photo" SVG data-URI),
   (b) blanks editable text (h/p/li) to "Edit" so regions stay clickable, (c) keeps <a>/<button> CTA
   labels, (d) clears data-status. Editor toolbar gains a gold "+ Blank card" button in the Card group
   (EDITOR_INJECT). Frontend flash "Blank card added — click to fill it in". Verified via curl on
   car-demo: 2→3 cars, middle card = 1 placeholder img + 7 "Edit" fields + blank status; CTA preserved.
   NOTE: spec values (span/b) aren't editable regions in these templates, so a blank card keeps the
   donor car's spec numbers until spec editing is added (pre-existing editability gap, not new).
- BACKLOG still open: apply finance + blank-card assets to the client deliverable ZIPs (RV car-sales,
  Broadfield bikes) if the user wants them live on those specific static sites; modularize server.py/App.js.

## 2026-06-13 (fork) — Finance auto-inject for ANY car site (no per-site file changes)
User confusion: re-ingesting Ribble Valley didn't show finance, because RV's own files predate the
feature and re-ingest only re-reads a site's OWN files. FIX (chosen: auto-inject) so no hosting/file
juggling is ever needed. Build bumped to cms-v6.
- NEW FINANCE_INJECT (server.py): generic, theme-adaptive finance estimator (CSS+JS, `ivdfin-` classes).
  Targets [data-block="car"], finds price via `.price,.uc-price,[class*=price]`, injects a
  "From £X/mo" pill (accent auto-matched to the price element's computed colour so it fits any theme) +
  a popup calculator (deposit slider, term 24/36/48/60, live monthly, representative-APR disclaimer,
  "Ask us about finance" → clicks the car's `.enquire-btn/.uc-enquire-btn`). Config via body data-attrs
  data-finance-apr/term/deposit-pct (defaults 12.9% / 48m / 10%).
- render_page injects FINANCE_INJECT ONLY when `not for_editor` AND the page contains data-block="car"
  (so it shows on Preview + published live pages, NOT in the editor canvas). Runtime-only, never stored,
  publish-clean (data-eid still stripped).
- IDEMPOTENT: per-car skip `if(car.querySelector('.finance,.uc-finance,.ivdfin-row'))return` + a global
  `window.__ivdFinance` guard, so sites that already ship finance (car-demo slider.js, used-cars template)
  do NOT double up. Verified: car-demo dist = 2 own pills + 0 injected (no doubles); RV-style dark card
  with NO site finance JS = 1 injected pill + working modal (£18,450 → £445/mo @48, £377/mo @60, correct).
- USER PATH FOR RV: rebuild to cms-v6 → open Ribble Valley → click Preview (or Publish) → finance shows
  on the live page automatically. Nothing to upload.

## 2026-06-13 (fork) — CRITICAL: subfolder pages (e.g. /car-sales/) now ingest, edit & publish
User could only see the home page in the editor; the car-sales page (a SUBFOLDER, car-sales/index.html)
never appeared. ROOT CAUSE: ingest_site globbed only top-level `*.html` (`os.path.join(src,"*.html")`),
so nothing inside subfolders was ever imported. Build bumped to cms-v7. Fixed the WHOLE round-trip:
1. INGEST (ingest_site): now `glob(**/*.html, recursive=True)`; skips asset/hidden/node_modules dirs.
   Each page stores a `relpath` (site-relative path) + a URL-safe `slug` via new `_slug_for_relpath()`:
   index.html→home, about.html→about, car-sales/index.html→car-sales, car-sales/stock.html→car-sales__stock
   (slashes → `__` so path routing never breaks). order[] entries carry relpath too.
2. EDITOR (editor_page): asset base now points at the page's OWN folder
   (`/api/asset/{slug}/{dir}/`) so a subfolder page's relative assets (car-sales/assets/..) resolve and
   the canvas renders STYLED. Root pages unchanged.
3. PUBLISH/PREVIEW (build_dist): now mirrors the ENTIRE source tree except *.html
   (`copytree(..., ignore=ignore_patterns("*.html"))`) so nested folders + their own assets are
   preserved, then renders each page back to its `relpath` (subdirs created). _sftp_push already walks
   the tree recursively, so subfolder pages upload to the right remote path.
4. Backward compatible: pages without `relpath` fall back to slug-based filename + root asset base.
   NEEDS RE-INGEST of a site for existing pages to gain relpath and for subfolder pages to appear.
- VERIFIED (self-test on an RV-clone "rvtest": root index.html + car-sales/index.html + car-sales/assets):
  ingest found BOTH pages (home + car-sales); editor base = /api/asset/rvtest/car-sales/ (styled);
  publish dist mirrored root assets/ AND car-sales/assets/, wrote car-sales/index.html at the right path,
  data-eid stripped, finance auto-injected. Screenshot: RV car-sales renders fully styled with finance
  pills on both cars (£530/mo, £934/mo). Test site purged afterwards.
- USER ACTION: rebuild to cms-v7 → re-ingest (or re-pull) the site → the car-sales page now shows in the
  dashboard/editor; edit it, then Preview/Publish.

## 2026-06-13 (fork) — 3 editor bugs on subfolder car pages (image / specs / status). Build cms-v8.
All verified end-to-end on an RV clone (incl. a version with data-status stripped to mimic live files):
1. IMAGE UPLOAD didn't show on subfolder pages: upload returns a ROOT-relative url (assets/uploads/..),
   but a subfolder page's base is /api/asset/{slug}/car-sales/ so it resolved to car-sales/assets/uploads
   → 404. FIX: render_page now prefixes uploaded-image values with `../`*depth (from page relpath) so they
   point back to the site root — works in the editor (browser normalises the ../) AND on publish (relative
   to car-sales/index.html). Root pages (depth 0) unchanged. Verified: editor src=../assets/uploads/x serves
   200, dist src=../assets/uploads/x with media copied to dist/assets/uploads.
2. SPECS (Year/Mileage/Gearbox/mpg/Colour) weren't editable: they are <span>/<b>, which weren't in
   EDIT_TAGS. FIX: assign_regions now adds a PURELY ADDITIVE pass making standalone <span>/<b>/<strong>
   editable text regions — but ONLY when NOT inside a block-level edit tag, so prose paragraphs with inline
   <b>/<strong> still edit as ONE region (no split/regression). Verified: 12 spec values became editable;
   "2021 (21)" is contenteditable=true in the editor.
3. NO STATUS OPTION when clicking a car: the Status button was gated on the card already having a
   data-status attr, which the user's live files lacked. FIX: toolbar now shows Status when the card has
   data-status OR data-block contains "car" OR the card has a .price/[class*=price]. Also added STATUS_CSS
   (server-injected, generic [data-block][data-status]::before ribbons for Sold/Reserved/New-in +
   greyscale/strike-through) so ribbons ALWAYS render in editor + live even if the site CSS lacks them.
   Verified: status-sold op works on a card with NO prior data-status; toolbar shows
   [Duplicate, + Blank card, Move, Move, Delete, Status]; SOLD ribbon renders (screenshot).
- NOTE: the toolbar (incl. Status) appears when you click an EDITABLE element INSIDE a card (title, price,
  spec, image), not the empty card margin — expected behaviour.
- USER ACTION: rebuild to cms-v8 → re-ingest → click a car's title/price/spec → Card ▸ Status ▸ Sold.

## 2026-06-13 (fork) — Editable text inside logo/brand links (the un-editable "Apex" footer). Build cms-v9.
User removed "Apex" everywhere except a footer brand heading they couldn't edit. ROOT CAUSE: the brand is
a logo LINK wrapping the name in spans (`<a class="foot-brand"><svg/><span class="brand-name">Apex Ribble
Valley</span>..</a>`). The editor treats any link-with-children as a card-link (link-only, no text edit),
and the inline pass skipped spans inside links → the brand text was locked.
FIX (assign_regions): added `_is_card_link()` (a/button wrapping svg/img/span, i.e. not a plain text link).
- Block loop now SKIPS creating a whole-element text region for card-links (they get a link region instead).
- Inline pass now ALLOWS <span>/<b>/<strong> that sit inside a card-link to become their own editable text
  regions (previously blocked by the find_parent(EDIT_TAGS) check). Plain text links + prose paragraphs are
  unchanged (still one region; inline <b> not split).
- Editor: added e.stopPropagation() on element clicks so clicking an inner brand span selects/edits the SPAN
  rather than bubbling up and re-selecting the parent link.
VERIFIED: injected "Apex Ribble Valley" into brand-name spans on an RV clone → after ingest both the header
AND footer brand names are editable text regions; the brand link still exposes a link region (href editable);
clicking the footer brand text selects the span (contenteditable=true, ed-sel) so "Apex" can be edited out.
- USER ACTION: rebuild to cms-v9 → re-ingest → click the footer/header brand text → edit/delete "Apex".

## 2026-06-13 (fork) — Sold Auto-Sort + Find & Replace + friendlier Help. Build cms-v10.
1. SOLD AUTO-SORT: render_page (PUBLISH/PREVIEW only, not editor) now moves data-status="sold" car cards
   to the END of their grid (per parent, preserving order among sold/available). Editor keeps manual order.
   Verified: after marking the 1st car Sold, dist order = [available Porsche, sold Mercedes].
2. FIND & REPLACE: new POST /api/sites/{slug}/replace {find,replace,match_case,dry_run}. Replaces across
   ALL pages in region TEXT values + image ALT + seo.title. dry_run returns a match count; a real run saves
   a "Before replacing …" restore point first (undoable) then updates page docs. Frontend: "Find & Replace"
   button in the dashboard actions + FindReplaceModal (find/replace inputs, match-case, Find matches count,
   Replace all). Verified: dry-run counted 1, apply changed Porsche→Ferrari, restore point created.
3. HELP: added a "Help" button in the dashboard topbar → HelpModal (friendly, sectioned guide covering
   text/photos/cars/status/find&replace/undo/publish) with styled gold headings + bullets (App.css
   .help-guide). Also rewrote the in-editor "How to edit" tips to match current features. Screenshots confirm.
- USER ACTION: rebuild to cms-v10. Sold-sort + finance + status ribbons all apply automatically on
  Preview/Publish. Find & Replace and Help are on the dashboard.

## 2026-06-13 (fork) — CRITICAL: re-ingest no longer wipes edits. Build cms-v11.
User kept losing all their edits: every re-ingest re-parsed the source file and OVERWROTE the page
(template+regions+seo) via `$set data`, so edits reverted to the original template each time (they'd been
told to re-ingest after each code update → repeatedly redoing work). FIX: ingest_site now, for pages that
ALREADY exist in the CMS, PRESERVES them (only refreshes routing metadata filename/relpath) and never
re-imports from source; it imports ONLY genuinely NEW files. Returns {total, added, preserved}; do_ingest
and add_site updated; frontend toast now says e.g. "Added N new pages · kept your edits on M" or "Up to
date · your edits on all M pages were kept". VERIFIED: edited a title → re-ingested → edit preserved;
added a new .html → re-ingest added it (added:1) while preserving edits.
- IMPLICATION: to pull a genuinely fresh copy of an already-imported page from source, the user must
  delete that page/site first (edits win by default). This is the correct trade-off for their workflow.
- USER ACTION: rebuild to cms-v11 → re-ingest freely; edits are now kept.

## 2026-06-13 (fork) — Add-anywhere + max editability. Build cms-v12.
1. ADD ANYWHERE: new `add-el` page_op (kind = heading|paragraph|button|image) inserts a new element right
   after the selected element (or its block). Editor toolbar now has an "ADD:" group (+ Heading / + Text /
   + Button / + Image) on EVERY selection (removed the old "+ Button only shows on links" limitation).
   Buttons clone an existing .btn class if present. Frontend op handler forwards `kind`. Verified all 4 types
   insert and appear in the editor.
2. MAX EDITABILITY: new `_wrap_loose_text(soup, body)` in ingest_page wraps stray visible text (a word
   sitting directly in a <div>, or text beside a <span> in a logo link — e.g. the "Apex" footer) in
   `<span class="ivd-txt">` so it becomes an editable region. Skips script/style/svg/pre/etc and pure-text
   edit tags (already regions). Runs on INGEST, so NEW imports get near-total text editability. Verified:
   loose "Apex" + loose div text both became editable; footer/header both clickable (contenteditable span).
   NOTE: applies to newly-imported pages; existing pages keep their edits (edit-preserving re-ingest) so to
   gain wrapping on an old page, re-import it fresh (delete + re-add).
- ACCESS CONTROL: user chose to DEFER (leave for now).
- USER ACTION: rebuild to cms-v12 → new sites are near-fully editable + "Add:" appears on every element.

## 2026-06-13 (fork) — NEW SITE FROM A DESIGN (superadmin ZIP upload). Build cms-v13.
Superadmin can spin up a whole client site from a finished design ZIP in one flow — no SFTP pull needed.
- BACKEND: POST /api/sites/create-from-design (require_super, multipart). Fields: file(zip), slug, name,
  domain, client_email, client_password, sftp_host/port/username/password/remote_path (all optional
  except file+slug). _extract_design_zip() safely unpacks (zip-slip guard, 5000-file/500MB budget, skips
  __MACOSX/dotfiles) and FLATTENS a single wrapper folder so index.html lands at the site root. Then
  ingest_site (recurses subfolders e.g. car-sales/index.html), sets name/domain, optional sftp conf,
  optional scoped editor user (role=editor, site_id=slug). Rolls back (rm dir + delete site doc) on any
  failure incl. "no .html found". Does NOT auto-publish (user reviews then hits Publish).
- PHP passthrough: .php (and all non-.html) files copy through untouched via build_dist (ignore *.html
  only) → they publish as-is over SFTP but aren't click-to-edit (as intended). Verified contact.php in dist.
- FRONTEND: Admin ▸ Sites tab, superadmin-only "New site from a design" card (above the SFTP-pull "Add a
  new site"). Collapsed → "Create a site from a design ZIP" button; expanded form (data-testid design-*)
  with file picker, name/slug (auto-slug from name), locked domain, optional client login, optional SFTP.
  Uploads as FormData (180s timeout), shows result inline, refreshes site list.
- VERIFIED end-to-end via curl: 2-page zip (home + car-sales subfolder + php + assets) → created, both
  pages ingested, client user created & scoped, domain locked; PHP present in preview dist; error cases
  (duplicate slug / non-zip / no-html) all 400 with cleanup (dir + DB doc removed). Frontend form renders +
  opens (screenshot). Test data purged after.
- USER ACTION: rebuild to cms-v13 → Admin ▸ Sites ▸ "Create a site from a design ZIP".

## 2026-07-21 (fork) — Editor UX batch + Users/Sites edit + SFTP defaults. Build cms-v14.
Verified 8/8 frontend flows (iteration_17.json, 100%); backend endpoints curl-verified.
1. IMAGE-REPLACE NO LONGER JUMPS TO TOP: Editor now has reload() (captures iframe scrollY) + onFrameLoad
   (restores scrollY after the new iframe loads, x3 timed retries). ALL setNonce iframe reloads replaced with
   reload(), so text edits, image replace, ops, undo & fill-alt all preserve scroll. Same-origin iframe so
   contentWindow.scrollY is readable. Tester confirmed y=1500 preserved after a reload.
2. EDITOR LAYOUT — SEO/Help moved to topbar, left panel removed: aside.panel deleted → iframe full width
   (big win on mobile). Topbar now: ← All pages | Editing | ⚙ SEO title | ? Help | ↶ Undo | Publish.
   'SEO title' opens a Modal (page title input + Fill missing alt text + Save). 'Help' opens the existing
   HelpModal (full guide). A slim .dirty-bar shows under the topbar when there are unsaved changes.
   CSS added: .page-frame.full, .dirty-bar, .modal-label/.modal-input, mobile topbar wrap (@max-width 640px).
3. USERS EDIT: new PUT /api/users/{uid} (require_admin) updates name/role/site_id/optional password (guards
   self-demotion). UsersTab row gained 'Edit' → modal (eu-name/eu-role/eu-site/eu-password/eu-save). Remove
   now hidden for admin AND superadmin.
4. SITES EDIT: new PUT /api/sites/{slug}/meta (require_admin) updates name+domain. GET /api/available-sites
   now returns name+domain. SitesTab row shows name + 🔒domain and an 'Edit' → modal (es-name/es-domain/es-save).
5. HOSTINGER SFTP DEFAULTS (frontend consts SFTP_HOST=77.37.37.182 / SFTP_USER=u897891218 / SFTP_PORT=65002 +
   rpForDomain()). Both 'New site from a design' and 'Add site (pull)' forms prefill host/port/username; typing
   the locked domain auto-builds remote path /home/u897891218/domains/<domain>/public_html.
   BACKLOG (tester): move these to REACT_APP_* env vars so other deployments override without a rebuild.
- Also delivered clean Apex-free + brand-editable Ribble Valley raw HTML: /api/download/ribble-valley-chequered-flag-editable.zip
  (brand wordmark pulled out of the logo <a> into plain editable spans in header+footer of both pages).
- USER ACTION: rebuild to cms-v14. Footer should read UI+API cms-v14.

## 2026-07-21 (fork) — Replace SVG logo with an image. Build cms-v15.
Problem: clicking the site logo in the editor did nothing useful — the logo is an inline <svg>, and the
editor's Replace only worked on <img> tags, so users got odd Add/Link options ("weird").
Fix (general — works for ANY site whose logo is an SVG/icon):
- EDITOR_INJECT: when the selected element contains an <svg> and no <img>, a 'Replace logo' button is added
  to the toolbar (posts {t:'logo', eid}).
- Frontend: t==='logo' opens a dedicated hidden file input (logoFileRef, accept image/*,.svg) → uploads raw
  (no crop — logos keep their shape/transparency via optimize_image WebP-RGBA / SVG passthrough) → POST
  /pages/{site}/{page}/op {op:'set-logo', eid, url} → reload (scroll preserved).
- Backend page_op 'set-logo' (PageOp gained url field): bakes current regions, finds target by eid, replaces
  its inner <svg> with <img class=<svg's class> alt="Logo" style="max-height:56px;width:auto;object-fit:contain">
  (or updates an existing <img>, or appends if neither). assign_regions then makes the new <img> a normal
  IMAGE region, so clicking it again gives the standard Replace/Alt/Caption toolbar. Snapshot + undo pushed.
- VERIFIED end-to-end via curl (svg count 26→25, brand-logo now has <img>, region type=image, editor renders
  the uploaded webp) and via UI screenshot (toolbar shows 'Replace logo' on the RV checkered-flag logo).
- No new ZIP needed: once the user rebuilds to cms-v15 and re-pulls the clean editable RV files, they can
  click the logo → Replace logo → upload their own PNG/SVG.
- USER ACTION: rebuild to cms-v15. Footer should read UI+API cms-v15.

## 2026-07-21 (fork) — BUGFIX: HTML comments leaking as visible text on published site. (cms-v15)
Symptom: live site showed "===== HEADER =====", "===== HERO =====", "MOT", "Servicing" etc as visible text.
Root cause: _wrap_loose_text used body.find_all(string=True), which ALSO returns bs4 Comment nodes (Comment
subclasses NavigableString), and the isinstance(node, NavigableString) guard passed them → each
<!-- ===== HEADER ===== --> got turned into a visible <span class="ivd-txt">===== HEADER =====</span>.
Fix (two layers): (1) ingest_page now strips ALL HTML comments from the body before processing; (2)
_wrap_loose_text uses `type(node) is not NavigableString` so Comment/CData/Doctype are never wrapped.
IMPORTANT: re-ingest PRESERVES existing pages (never rebuilds their template), so the fix only takes effect
on a FRESH ingest. To clean an already-affected live site: rebuild to cms-v15, then delete the site in the
editor and re-pull (or use 'New site from a design' with the updated comment-free ZIP), then Publish.
Also rebuilt /api/download/ribble-valley-chequered-flag-editable.zip with all HTML comments removed (belt &
braces). Verified: fresh ingest of the ZIP → dist HTML has zero '===== ' leakage, real content intact.

## 2026-07-21 (fork) — "Re-import fresh" button. Build cms-v16.
Gives a one-click way to rebuild a site from its latest source files WITHOUT deleting + re-adding it — so
fixes like the comment-stripping above apply to an existing site.
- BACKEND: ingest_site(site_slug, force=False). When force=True it rebuilds EVERY page's template from source
  (added=all, preserved=0) instead of preserving existing pages; saves a 'reimport' restore point first.
  Endpoint POST /sites/{slug}/ingest now takes ?force=true.
- FRONTEND: SitesTab row shows a "Re-import fresh" button (data-testid reimport-<slug>) for ingested sites,
  next to Re-ingest. Strong confirm dialog explains it DISCARDS editor edits (restore point saved) and that
  the live site isn't touched until Publish.
- VERIFIED via curl: non-force ingest preserves an edit; force=true discards it, rebuilds from source
  (added=2/preserved=0), and creates a 'reimport' snapshot. UI shows the buttons.
- FIX PATH for the user's leaked-labels site: rebuild to cms-v16 → click "Re-import fresh" on Chequered Flag
  (comments now stripped on ingest) → Publish. No delete/re-add needed.
- USER ACTION: rebuild to cms-v16. Footer should read UI+API cms-v16.

## 2026-07-21 (fork) — Page-template LIBRARY (7 templates) + auto-nav. Build cms-v17.
Verified: testing agent 9/9 flows 100% (iteration_18.json) + curl. All templates adapt to the client's
brand colours/fonts, carry their real header+footer, are fully editable, and auto-add to the nav.
- NEW FILE backend/templates_library.py: 7 templates (LIBRARY_TEMPLATES) — Image Gallery (masonry + ~640px
  lightbox, 9 duplicatable data-block=photo figures w/ editable captions), Pricing (3 tiers), Services (6
  cards), FAQ (accordion — open in editor, collapsible on live), About (image+story+stats), Contact (mailto
  form + details + hours), Testimonials (review cards). All namespaced .ivt-* + tokenised var(--brand-*),
  shared IVT_BASE css + IVT_JS (lightbox + faq, both disabled inside the editor iframe so editing isn't
  hijacked). templates_seed.py appends LIBRARY_TEMPLATES to BUILTIN_TEMPLATES (seeded on startup).
- AUTO-NAV (server.py): new helpers _find_nav_container/_new_nav_anchor/_insert_nav_link/_href_at_depth.
  create_page_from_template now (a) inserts the new page's link into its OWN lifted header (depth 0, marked
  active, and strips inherited active/current from the other links so Home isn't wrongly highlighted), and
  (b) inserts a link into EVERY other page's nav (manual fresh eid 'nav<slug>' + a text region so it's
  editable; href uses ../ per that page's relpath depth — subfolder pages like car-sales get ../slug.html).
  Idempotent (skips if link already present). delete_page removes any nav links pointing at the deleted page
  (no dangling menu items) and drops their regions.
- FRONTEND AddPageModal: enquiry-email input now shows for BOTH used-cars AND contact templates
  (needsEmail = templateId in ['used-cars','contact']); backend substitutes sales@yourgarage.co.uk.
- BACKLOG (tester notes, non-blocking): App.js ~1363 lines (split AddPageModal/Editor); design-submit could
  re-fetch site page count.
- USER ACTION: rebuild to cms-v17. Add pages via dashboard '+ New page' -> 'From a template'.

## 2026-07-21 (fork) — Template thumbnails + drag-to-reorder nav menu. Build cms-v18.
Both verified via curl + UI screenshots.
1. TEMPLATE THUMBNAILS: generated 8 flat-wireframe preview images (gemini) saved to
   /app/frontend/public/template-thumbs/<key>.jpg (gallery, pricing, services, faq, about, contact,
   testimonials, used-cars). AddPageModal 'From a template' now shows a visual CARD GRID (.tpl-grid/.tpl-card
   in App.css) — thumbnail + name, selected card gold border + tick — instead of a plain dropdown (hidden
   <select> kept for the addpage-template test id). No backend change: thumb URL derived from template id.
   Also: enquiry-email field now shows for used-cars AND contact templates.
2. DRAG-TO-REORDER NAV: new NavMenuModal (App.js) opened by a 'Menu' button on each ingested site row
   (data-testid menu-<slug>). Lists nav items with drag handles + up/down arrows; Save posts the new order.
   Backend: GET /api/sites/{slug}/nav (reads home page nav container, returns ordered labels) and POST
   /api/sites/{slug}/nav/reorder {order:[labels]} — reorders the nav items on EVERY page to match (matches
   by link text/label; handles <nav><a> and <ul><li><a>; regions untouched so edits/eids preserved).
   Helpers _nav_items/_item_label added near _find_nav_container. Verified: moving 'Gallery' to position 2
   updated 3 pages incl the car-sales subfolder page; published nav reflects new order.
- USER ACTION: rebuild to cms-v18. Reorder menu: Admin ▸ Sites ▸ Menu (drag). Add page: visual template cards.

## 2026-07-21 (fork) — Drag-to-reorder the dashboard pages list. Build cms-v19.
- BACKEND: POST /api/sites/{slug}/pages/reorder {order:[slugs]} (current_user) reorders the site's `order`
  array by the given slug order (unlisted pages kept at the end). Verified via curl: order persists.
- FRONTEND: dashboard page-cards are now draggable (HTML5 drag) with a hover ⋮⋮ grip and a gold dashed
  drag-over highlight (.page-grip / .page-card.drag-over in App.css). Dropping reorders locally and POSTs the
  new order; clicking a card still opens the editor (drag vs click handled natively). reorderPages() in
  Dashboard persists + toasts "Page order saved".
- NOTE: page order affects the dashboard list (and the site `order`/publish sequence); it does NOT change the
  nav menu order — that's the separate Admin ▸ Sites ▸ Menu tool (cms-v18).
- USER ACTION: rebuild to cms-v19. Drag page cards on the dashboard to reorder them.

## Changelog — 2026-06 (fork)
- **Broadfield Motor Company site cleanup (DONE, visually verified):**
  - Replaced the split "Two Wheels / Four Wheels" hero with a full-width cinematic Alfa Romeo hero (old-design style): logo used as the badge, "Broadfield Motor Company" heading, "Alfa Romeo & quality used-car specialists" tagline, phone numbers, CTAs.
  - Removed ALL motorbike content (bikes showcase, Harley/Yamaha/Kawasaki/Triumph cards, bike nav/footer/marquee/form references).
  - Removed the servicing section entirely (client no longer offers servicing) and broadened messaging to multi-marque used cars.
  - Delivered clean ZIP: `/app/frontend/public/broadfield-motor-company.zip` (index.html + assets), ingestable via the CMS "new site from design" upload.
  - Answered client Qs: (1) CMS auto-optimizes uploads to WebP q82 + resize (fast loads); (2) vehicle image blocks are clonable so 10+ images per vehicle supported.



## Changelog — 2026-06 (fork, cont.)
- **Broadfield: bikes re-added + 2 new inventory pages (DONE, verified via CMS render):**
  - Homepage: added a modern on-brand "Explore Broadfield" services-tile grid (Used Alfa Romeo / Other Used Cars / Used Bikes / Contact Us — Servicing dropped per client). Tiles + nav + hero CTAs now link to the new pages. Copy reworded to include used motorbikes again.
  - New page `used-cars.html`: Broadfield-styled page hero + responsive vehicle-card grid (data-block="car", price/status badges, clonable, multi-image ready). Fully editable.
  - New page `used-bikes.html`: same template converted to bikes.
  - Nav (Home · Used Cars · Used Bikes · Visit) consistent across all 3 pages; internal links relative .html and publish correctly.
  - Verified by ingesting the ZIP into the preview CMS (3 pages) and screenshotting rendered index/used-cars/used-bikes — all correct incl. Reserved/Sold badges.
  - Cache-buster bumped to `?v=3`. Deliverable: /app/frontend/public/broadfield-motor-company.zip (7 files, 3 pages).


## Changelog — 2026-06 (fork, cont. 2)
- **Broadfield used-cars/used-bikes → blank Coming Soon placeholders + multi-image slider (DONE, verified via CMS op):**
  - Downloaded client's Coming Soon image to assets/comingsoon.webp.
  - Rebuilt all vehicle cards as blank placeholders (Make & Model / £0000 / Description / spec grid all "—" / Enquire + Call us) matching the Ribble Valley car-sales reference.
  - Replaced single img with a real photo slider: .veh-slider > .veh-gallery > .veh-slide (scroll-snap) + hover prev/next + photo counter; slider JS added to assets/app.js (initVehSliders).
  - Editor add-image op duplicates a .veh-slide → clients add up to 10 photos, visitors slide through. VERIFIED: ingested ZIP, called op add-image on a slide eid → gallery went 1→2 slides, counter rendered "1 / 2".
  - Cards use data-block="veh" (not "car") to avoid the auto finance "£0/mo" pill on blank placeholders.
  - Cache-buster ?v=5. Deliverable ZIP: 8 files, 3 pages.
  - NOTE: /tmp is wiped between turns — source of truth for site files is /app/frontend/public/broadfield-preview/ + the delivered zip.

## Changelog — 2026-06 (fork, cont. 3) — .htaccess / go-live fix
- **ROOT-CAUSE BUG FIXED:** `_extract_design_zip` (server.py ~1805) skipped ANY path part starting with "." — silently deleting `.htaccess` (and .well-known) on every "create from design" import. That's why client sites "wouldn't go live right" (no HTTPS/canonical/clean-URLs/caching config). Changed to skip only cruft (__MACOSX, .DS_Store, .git*, .idea, .vscode, Thumbs.db, ._*) and KEEP legitimate web dotfiles.
- build_dist (copytree) and _sftp_push (os.walk) already handle dotfiles — extractor was the only gap. VERIFIED: re-ingested Broadfield ZIP → .htaccess (2172B) + 404.html now present in dist root and would be SFTP-pushed.
- Broadfield ZIP now ships a proper `.htaccess` (Options -Indexes, DirectoryIndex, force HTTPS, strip www, /index.html→/, extensionless URL rewrite, gzip, browser caching, ErrorDocument 404) + branded `404.html`. Also fixed email to sales@broadfieldalfaromeo.com everywhere; Enquire/Register buttons + homepage form now compose emails (mailto). Cache-buster ?v=6. ZIP = 10 files.
- ⚠️ ACTION: the extractor fix is BACKEND code — user must redeploy their TrueNAS/Dockge backend for it to take effect on their instance. Until then, .htaccess would still be stripped on their import (workaround: upload .htaccess once via Hostinger File Manager with hidden files shown).

