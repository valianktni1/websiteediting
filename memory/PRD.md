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
