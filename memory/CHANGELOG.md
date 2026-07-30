# Changelog — Website Editor CMS

## 2026-06 (fork continuation)

### Integrated the interactive client tour (DONE, verified) — cms-v35
- Integrated the user-supplied frontend-only "interactive tour" drop-in (App.js/App.css/version.js).
  The drop-in was built on top of the current code, so all recent features are retained (verified:
  ForcePasswordChange, ThemeModal+presets, SectionPicker+thumbnails, add-section, Find&Replace).
- Adds a guided spotlight tour for BOTH the dashboard (7 steps) and the page editor: Back/Next/
  Skip/Finish, progress dots, keyboard arrows, Esc; auto-launch on first visit (per-login via
  localStorage), permanent "▶ Tour" buttons + replay link in Help. Footer stamped cms-v35 (UI+API).
- Testing agent: 31/33 (94%). All regression-critical features intact. One HIGH bug found+FIXED:
  both tours failed to auto-launch on first visit (React StrictMode double-invoke cleared the
  setTimeout because `tourAutoStarted.current=true` was set synchronously before the timer). Fix:
  set the guard INSIDE the setTimeout callback (App.js dashboard ~1631, editor ~1943). Re-verified
  via screenshot: dashboard tour auto-launches ("Step 1 of 7 · Welcome"). Manual/Help replay always worked.


### Fix: deleting a feature bullet corrupted the whole list (DONE, verified) — cms-v34
- SYMPTOM (from user screenshot): deleting one repetitive feature bullet made the list explode —
  duplicated/merged bullets, stray "ADD A FEATURE" prompts, broken layout, repeated description.
- ROOT CAUSE: a bullet's stored text region value had been polluted by a PASTE (browser inserts
  <div>/<li>/<ul> when you paste multi-line text). Baking that value back into a single <li> via
  _set_html created nested lists / extra bullets; deleting then re-baked and made it worse.
- FIX: _set_html now FLATTENS block-level tags (div/p/li/ul/ol/section/pasted cards) inside every
  text region, keeping only inline formatting (b/i/em/u/br/span/a). A pasted mess collapses into
  one clean bullet. SELF-HEALING: every op re-bakes all regions through the hardened _set_html, so
  existing corrupted cards auto-clean on the next edit.
- Verified by reproduction: a bullet value with <div>+<ul><li>..</li></ul> bakes into a single
  clean <li> (no nested ul/div), and deleting it leaves a clean list. Clean-case delete already worked.


### Fix: "+ Add another car/bike" copied the previous vehicle's specs (DONE, verified) — cms-v33
- ROOT CAUSE: the used-bikes (and any) page uses the `veh-` card layout, but the add-blank-car op
  only fully blanked the `uc-` layout. So a "new" bike inherited the donor's specs (year/mileage/
  engine/gearbox/MOT) and description — which looked like it was "duplicating".
- FIX: add-blank-car now also blanks veh/generic price (£0000), spec VALUES (.veh-specs dd + any
  dd + .uc-spec b/span -> "–"), .veh-strap and .veh-features. Confirmed on the real broadfield
  used-bikes structure: donor "14,993 miles" no longer leaks into the new card; delete of the new
  card then works (parent data-block=veh, decompose ok). add-blank-block already did this (cms-v24).
- Live safety unchanged: blank/placeholder vehicle cards (title Edit/Make & Model/Coming soon or
  price £0000) are still auto-hidden on the published site. broadfield /used-bikes is currently a
  404 (not published), so nothing has leaked live.
- Delete verified working in code for card-level selections; if the user still sees a delete issue,
  need the exact symptom (nothing happens / only part disappears / reappears after publish).


### Insert section under the selected one (DONE, verified) — cms-v32
- "Add section" now inserts the new stripe **directly below the section you've selected** in the
  editor (was always page-bottom). The editor iframe now posts {t:'sel',eid} on select/deselect;
  Editor tracks selEid and passes it to POST add-section; backend climbs to the selected element's
  top-level section (child of <main>/<body>) and inserts after it. With nothing selected it still
  appends at the bottom. Picker hint switches wording based on whether something is selected.
- Verified: curl (insert after a top eid lands the section at ~22% of the body, not the end; undo
  reverts) + screenshot (select element -> picker reads "directly under the section you've selected").

### 4 more section types (DONE, verified) — cms-v31
- Added FAQ accordion (CSS-only <details>/<summary>, editable Q via h3 + A via p), Pricing/packages
  (3 cards Starter/Standard/Premium, editable price), Logo/partner strip (row of editable images),
  Opening hours + map (editable hours list + address + map image placeholder). Section library now 10.
- Same insert/edit/undo pipeline as cms-v29. Verified via curl: list=10; add faq/pricing/logos/hours
  all render + SECTIONS_CSS + editable data-eids (faq h3, hours li); undo x4 reverts clean. Picker
  thumbnails verified via screenshot (all 10 render correctly). wifetobe left clean.

### Section picker live thumbnails (DONE) — cms-v30
- The "Add section" picker now shows a real scaled-down live preview of each section (rendered
  in a tiny sandboxed iframe from the section's own HTML + SECTIONS_CSS), so you see the layout
  before inserting. GET /api/sections now returns {css, items:[{key,label,html}]}. Single-column
  picker, centered 396px previews. Verified via screenshot (6 thumbnails render correctly:
  CTA/split/features/banner/quote/heading). Insert/undo flow unchanged from cms-v29.

### Theme presets + "Add section" block library (DONE, verified 100%) — cms-v29
- THEME PRESETS: Colours & Fonts panel now has a "Quick presets" row — Classic Elegant,
  Bold Modern, Warm Boutique, Fresh & Clean — each sets accent + heading/body font in one click.
- ADD SECTION (SUPERADMIN-ONLY, experimental): '+ Add section' button in the editor topbar
  (shown only when user.role === 'superadmin'). Opens a picker of 6 drop-in sections: CTA strip,
  text+image split, three feature columns, image banner, testimonial/quote band, heading+intro.
  Backend: GET /api/sections + POST /api/pages/{site}/{slug}/add-section (both require_super).
  Insert bakes existing region edits, appends the section to <main>/<body>, re-runs assign_regions
  so all text/images become editable, and snapshots+undo like normal ops. Sections use namespaced
  ivds- classes + var(--brand-accent)/--brand-heading (with fallbacks) so they adopt the site theme;
  SECTIONS_CSS injected once per page when an ivds section is present (editor+preview+published).
- Verified: backend curl (list 6, add CTA -> ivds-cta + SECTIONS_CSS + editable data-eid, undo
  reverts) + testing agent frontend 100% (iteration_25.json): presets update preview+save, picker
  inserts + editable + undo, superadmin gating. wifetobe left clean.
- NOTE: sections currently insert at the END of the page. Positioning ("insert after selected
  block") + exposing to clients are the natural phase-2 follow-ups.


### Site-wide Theme panel: Colours & Fonts (DONE, verified 100%) — cms-v28
- New "Colours & Fonts" button on the dashboard (available to admins AND the site's own editor
  clients). Opens a Theme panel: accent colour picker + hex + 9 preset swatches, button-text
  colour, heading font + body font dropdowns (~30 curated Google Fonts), and a live preview.
- Backend: GET/PUT /api/sites/{slug}/theme (scope_ok, so clients can self-serve). Values stored
  in site.branding (accent/accent_dark/on_accent/heading_font/body_font/font_link). Hex validated
  server-side (prevents CSS injection); fonts must be in CURATED_FONTS. _theme_style(branding)
  builds injected CSS: :root remaps common accent var names (--accent/--primary/--gold/etc.) so
  var()-based sites repaint free, plus !important font overrides (headings vs body) and accent
  rules for links + .btn/.cta/[type=submit] (bare <button>/sliders left alone). _google_fonts_link
  builds the <link>. render_page now takes `branding` and injects the theme AFTER the site's own
  CSS; wired through editor_page, editor_preview and build_dist (shows in editor canvas + Preview
  + published). ~90% repaint of hand-coded sites as agreed with the user.
- Verified: backend curl (GET 30 fonts, PUT save, invalid hex 400, render injects accent var +
  Playfair/Manrope + Google Fonts link + button rule) and testing agent frontend 100%
  (iteration_24.json): panel opens, swatch/hex/fonts/live-preview/save/persistence/invalid-hex/
  reset all pass; render injection cross-verified; wifetobe reset after test.
- BACKLOG (phase 2, user wants eventually): per-element colour/font control in the editor.


### Forced password change on first login (DONE, verified 100%) — cms-v27
- New client users (created via Admin > Users, or whose password an admin resets) get
  `must_change_password: true`. The seeded superadmin is created with the flag = false.
- Backend: POST /api/auth/login returns `must_change_password`; a FastAPI middleware BLOCKS
  every /api route with 403 `{code:"must_change_password"}` until the flag is cleared
  (allowlist: login/logout/me/change-password/version/asset/branding). New endpoint
  POST /api/auth/change-password verifies the current/temp password, enforces min 8 chars +
  different-from-current, sets the new bcrypt hash, clears the flag, and rotates the cookie.
  update_user re-sets the flag when an admin sets a new password. No new pip deps.
- Frontend: AuthProvider exposes setUser + an axios interceptor that flips the flag on any
  403 must_change_password; ForcePasswordChange screen (blocking, non-dismissible, reuses the
  login card) with temp/new/confirm fields + client validation + "Sign out instead". Shell
  renders it whenever user.must_change_password is true, so the dashboard is genuinely gated.
- Verified: backend curl (create→login→403 gate→validations→success→re-login) + testing agent
  frontend 9/9 (iteration_23.json): popup blocks dashboard, all validations fire, wrong temp pw
  errors, success enters dashboard, re-login clean, admin never forced.


### Click-to-enlarge LIGHTBOX for galleries (DONE, verified 100%) — cms-v26
- New `LIGHTBOX_INJECT` (server.py): self-contained CSS+JS, injected by `render_page` only on
  the LIVE/Preview render (`not for_editor` and page has an `<img>`). Guarded by
  `window.self!==window.top` so it NEVER runs inside the CMS editor iframe (click-to-edit stays clean).
- Behaviour: click any content photo → full-screen dark overlay with the enlarged image; prev/next
  circular buttons + counter (N/M) for multi-image galleries; close via ×, Escape, or backdrop click;
  swipe left/right on mobile. Galleries grouped by tightest ancestor containing 2+ eligible images
  (so each car slider / photo grid navigates within itself).
- SAFE by design: skips logos/icons/tiny (<110px) images, skips images inside real page links
  (only intercepts image-file links), no new files, no SFTP/publish changes, editor untouched.
- Testing: iteration_21 found 2 HIGH UX defects (full-height prev/next buttons covered the close
  button + backdrop). Fixed → compact 56px vertically-centered circular nav buttons + close z-index:3.
  Re-test iteration_22 = 100% (6/6): open/close/prev/next/counter/Escape/backdrop all work; editor
  iframe confirmed lightbox-free.


### Lazy-load off-screen images site-wide (DONE, verified) — cms-v25
- `render_page` (LIVE/Preview only, not editor): first image on the page stays eager (fast
  LCP/first paint); every other `<img>` gets `loading="lazy"` + `decoding="async"` unless it
  already has a `loading` attr. Big win on image-heavy pages (car sliders load ~1 photo/car
  up front instead of all 12; photographer galleries only fetch what's on screen).
- Zero new files, no srcset (avoids the old srcset swap bug), no SFTP/dist changes, editor
  unchanged (images stay eager so they're always visible for editing). Near-zero breakage risk.
- Verified: first img eager, rest lazy+async, pre-set eager images respected.


### Auto-hide unfinished/placeholder car cards on LIVE site (DONE, verified) — cms-v24
- Problem: half-finished cars (title "Edit", price "£0000", "Edit" bullet points) from
  the "+ Blank card / Add another car" flow leaked onto the published site
  (seen live on broadfieldmotorco.co.uk/used-cars).
- FIX 1 (public render only, `render_page` when `not for_editor`): any `[data-block]` card
  that contains a price element is REMOVED from the live/Preview HTML if its title is
  empty/"Edit"/"Make & Model"/"Coming soon" OR its price is empty/all-zeros (£0000, £0, £0.00).
  Card is still visible in the EDITOR so the client can finish or delete it. Also strips any
  leftover leaf `<li>/<p>/<span>` whose text is exactly "Edit" inside surviving cards.
  Guards nested `data-block` (e.g. veh-cta buttons) via `card.attrs is None` + price-required
  gate so Enquire/Call buttons on real cars are never touched.
- FIX 2 (`add-blank-block` op): a new blank card no longer inherits the donor car's numbers —
  price set to £0000, spec VALUES (`<dd>` spans, `.uc-spec b/span`) blanked to "–" (labels
  Year/Mileage/... kept), title/strap/features already blanked to "Edit".
- VERIFIED against the REAL live page fixture: 9 car cards → 7 kept (BMW Z4, CITROEN DS3, …),
  exactly the 2 "Edit/£0000" placeholders removed, all real Enquire/Call buttons intact,
  zero "£0000"/"<h3>Edit</h3>"/"<li>Edit</li>" left. add-blank clone: donor "2008" gone.
- USER ACTION: rebuild Docker to cms-v24, open used-cars, Publish — the 2 broken cards
  vanish from the live site automatically (they stay editable/deletable in the CMS).


### Clean URLs — sitemap enrichment (DONE, verified)
- `_apply_clean_urls` in `server.py` now **preserves** the existing sitemap's
  `<lastmod>`/`<changefreq>`/`<priority>` tags, re-keyed to the new clean URLs
  (falls back to defaults: lastmod=today, priority 1.0 home / 0.8 others, monthly).
  Wrapped in try/except so a malformed old sitemap can never break a publish.
- Verified: ivorydigital.uk live — clean URLs, 301 redirects (`/page.html`→`/page`,
  `/index.html`→`/`), llms.txt/llms-full.txt/robots.txt untouched (served via
  `.htaccess !-f/!-d` rule), sitemap regenerated with clean locs + preserved tags.
- New pages are auto-added to sitemap/canonical/.htaccess on each publish **when
  Clean URLs is ON**. If toggle is OFF, source sitemap is copied as-is (no regen).

### Safer Publishing framework (DONE — A+B+C + advanced)
Backend (`server.py`):
- NEW `GET /sites/{slug}/publish-changes`: builds site, MD5-diffs against the most
  recent backup zip (= current live), returns added/changed/removed file lists.
  Build is **deterministic** — verified a no-edit publish reports 0 changes.
- Reused existing `GET /sites/{slug}/backups` and `POST /sites/{slug}/restore`
  (restore-live via SFTP, admin-only) for the rollback UI.
Frontend (`App.js`):
- `PublishConfirm` rebuilt: plain-English "here's what will change" summary
  (Updated/New/Removed, pages named, supporting files counted), a
  **"Preview exactly what will go live"** button, friendlier copy, and a
  post-publish **"Publish complete"** screen with a one-click **"Undo this publish"**
  (restores previous backup live — admin only, shown only when published live).
- NEW `PublishHistory` modal (admin only, "Publish history" dashboard button):
  lists all backups, newest tagged **● Live now**, older ones get
  **"Restore this version live"**. Verified visually (48 restore buttons + live badge).
- CSS added for chg-summary/chg-line/pd-icon/vbadge.b-live in `App.css`.

Notes:
- Change-summary + preview + undo blocks are SFTP-gated → visible in TrueNAS (prod),
  not in preview (SFTP unconfigured). Endpoint logic verified via curl.
- test_credentials unchanged.

### Used-Cars template editor improvements (DONE — all verified)
Requested against the Ribble Valley / used-cars template; applied to ALL car-style pages.
1. **Delete single photo** — `select()` in `server.py` editor JS now shows a **"Delete photo"**
   button for images inside a `[data-block]` (posts `op:delete` on the img eid). Verified:
   deleting one slider image removes just that image, the car card stays intact.
2. **Add/remove features** — feature `<li>` now shows **"+ Add feature"** (new op path
   `add-el kind=listitem` inserts `<li>New feature</li>` after the clicked chip) and
   **"Delete feature"**. Verified new editable chip is added.
3. **Enquire button** — confirmed working: template JS reads `.uc-car-head h3` (make & model)
   and mails to `data-enquiry-email`, which `create_page_from_template` replaces with the
   site's chosen email. Verified `sales@yourgarage.co.uk` → site email on page create.
4. **Blank starter cars** — `_CAR1`/`_CAR2` in `templates_seed.py` rewritten to
   "Make & Model / £0000 / dash specs / spec chips" with a compressed inline
   **COMING SOON** webp data-URI (`backend/assets_data.py`, ~49KB). Self-contained so it
   survives SFTP publish. Matches user's PDF.
Files: `server.py` (editor JS + add-el op), `templates_seed.py` (blank cars + import),
`assets_data.py` (NEW inline coming-soon asset).

### "+ Add another car" one-click button (DONE — verified)
- New editor op `add-blank-car` in `server.py`: clones the selected car card, collapses its
  gallery to a single COMING SOON slide, and resets title→"Make & Model", price→"£0000",
  strap→placeholder, spec values→"–", feature chips→"spec". Graceful fallback (blank editable
  text) for non-uc car markup.
- Toolbar: **"+ Add another car"** button added to the Card group, shown only on car cards
  (same detection as the Status button). Verified: 2 cars → 3, new card is a proper blank
  Coming-Soon car. Lets clients build a stock list without duplicating an existing card.

### Multi-tenant access-control hardening (DONE — verified via API)
Closed read/write gaps so a client (editor) is fully isolated to their own site at the
SERVER level, not just hidden in the UI. Changes in `server.py`:
- `scope_ok` tightened: only admin/superadmin get all-site access; an editor MUST have a
  matching `site_id` (an editor with no site assigned is now denied, not granted-all).
- `GET /sites` now filters to the editor's own site (returns [] if unassigned).
- Added `scope_ok` guards to previously-open endpoints: `site_pages`, `reorder_pages`,
  `get_page`, `fill_alt_status`, `editor_page`, `upload_media`, `preview`, `find_replace`,
  `publish_target`, `publish`, `list_backups`, `publish_changes`.
- All sensitive config (SFTP get/set/test, branding, site-meta, clean-urls, remove-site,
  live-restore) was already `require_admin`/`require_super` — left unchanged.
Verified with curl (3 angles):
- Owner/superadmin → sees all 5 sites, full access (200).
- Scoped editor (site_id=demo-couk) → `/sites` returns ONLY demo-couk; own site fully works
  (pages/publish-target/snapshots/backups/page/editor all 200).
- Scoped editor → every wifetobe endpoint (pages/content/publish/reorder/publish-target/
  editor-page) returns 403.
- Owner dashboard UI smoke-tested: loads normally, nothing broken.
Test editor creds are in test_credentials.md.

### CRITICAL editor bug fix — stable element IDs (DONE, verified)
Symptom (reported on Mark's used-cars page): after adding a feature / duplicating a car,
the "Enquire about this car" button text got overwritten with "New feature", and a stray
"New feature" appeared near the CTA.
Root cause: `assign_regions` in `server.py` DELETED and re-numbered every element's
`data-eid` sequentially on EVERY structural edit. Because ids shifted by position, a text
save meant for a new feature chip could land on the neighbouring Enquire button (classic
positional-id race with blur-save + reload).
Fix: `assign_regions` now assigns **stable ids** — existing `data-eid`s are preserved,
only new or duplicate-cloned elements get a fresh id (via a used-number set + duplicate
detection in document order), and stale ids on no-longer-editable elements are stripped.
Backward compatible (fresh ingest still yields t0,t1,…; existing pages keep their ids).
Verified via API: adding a feature keeps the Enquire button's id (t26) and text intact;
duplicating a card produces ZERO duplicate ids; clone gets fresh ids.
NOTE: this prevents FUTURE corruption. A page already damaged before the fix must be
repaired manually (retype the button text, delete the stray chip) or rolled back via a
Restore point.
Gold outlines around cards = normal editor hover/selection highlight on `[data-eid]`
elements only; never shows on the live site. Not a bug.

### Deploy-time data-loss guard (DONE — startup auto-ingest hardened)
Symptom: after a deploy, Broadfield's used-cars listings reset to the blank "Coming Soon"
starter. Cause: startup auto-ingest rebuilt the site from the stale/blank HTML in
`/data/sites/<slug>/` because the site was (momentarily) absent from MongoDB.
Persistence itself is fine — compose mounts `/mnt/apps/website_editor/mongo:/data/db`
and a `backup` service mongodumps daily (30-day retention).
Fix in `server.py` startup: a site is auto-ingested from disk ONCE (drops a `.ingested`
marker in its source folder). If a site with that marker later goes missing from the DB,
startup SKIPS re-ingest and logs a warning instead of overwriting edits with stale files.
DB remains the source of truth; recover from the daily DB backup if needed.
Verified: backend restarts clean, /api/version = 2026-06-13-cms-v20-stable-ids.
CRITICAL deploy note: build context is the GitHub repo
(github.com/valianktni1/websiteediting#main), so the user MUST push latest code via
"Save to GitHub" BEFORE rebuilding on TrueNAS, and must REBUILD the image (not just
restart) + recreate the container. Confirm with /api/version showing v20-stable-ids.

### 2026-06 (fork) — Broadfield live cache fix + CMS re-sync + "Pull latest from server" button

**1. Live-site not updating (Broadfield) — root cause: HTML cache.**
The generated `.htaccess` had `ExpiresByType text/html "access plus 1 day"`, so browsers
held pages for 24h and edits appeared not to publish. Fixed the site's `.htaccess`:
- `text/html` -> `access plus 0 seconds`
- Added `mod_headers` block for `\.html$`: `Cache-Control no-cache, no-store, must-revalidate`,
  `Pragma no-cache`, `Expires 0` (assets css/js/img still cached 30d/1y).
User uploaded the corrected `.htaccess` to Hostinger; verified live pages render correctly.
NOTE: this was a hand-added block in the Broadfield source `.htaccess`, NOT from the CMS
generator (`_write_clean_htaccess`). If we ever want this global, add it to that generator.

**2. Re-synced Broadfield into the CMS editor (preview instance).**
CMS only held the `home` page; used-cars/used-bikes existed only live. Downloaded the
user's `public_html` zip, placed it in `/app/sites_source/broadfield`, ran
`ingest_site(force=True)` -> 4 pages (home, used-cars, used-bikes, 404). Editor now matches
live (BMW Z4 + Alfa Giulietta w/ 4 new photos). used-bikes still contains a user's
half-added blank bike (MAKE & MODEL / £0000) — left as-is (real live content).
NOTE: this sync was on the PREVIEW DB, not the user's TrueNAS. It does not carry to prod.

**3. NEW FEATURE — "Pull latest from server" button (SFTP tab).**
Backend `server.py`: `POST /api/sites/{slug}/pull` (require_admin + scope_ok) + `_run_pull_job`.
Pulls the selected site's live files from Hostinger via SFTP into a staging dir, verifies
.html present, snapshots ("pull" kind), swaps into source dir, then `ingest_site(force=True)`.
Read-only from server — NEVER publishes. Reuses proven `_sftp_pull` + polling via
`GET /api/sites/add-status/{job_id}` (relaxed from require_super -> require_admin).
Frontend `App.js` SftpTab (~line 701): one `pull-box` under the existing site dropdown with
`sftp-pull` button, confirm dialog, progress polling, result in `sftp-pull-result`.
Tested (iteration_19.json, frontend 100%): renders, confirm works, friendly 400 when no
SFTP configured. Full successful pull not testable in preview (no live SFTP creds) — works
on TrueNAS where SFTP is set.
DEPLOY: this is CODE — user must "Save to GitHub" then rebuild+recreate the TrueNAS
container for the button to appear on their real editor.

### 2026-06-14 — v23-client-ux: 6 client-friendly editor UX improvements (additive)

All additive, no existing edit/publish logic changed. Tested iteration_20.json (frontend 100%, no regressions).
1. First-visit COACH MARKS overlay (data-testid coach-overlay/coach-dismiss). Persisted via
   localStorage 'ivd_coach_seen'. 3 tips: click text / click photo / nothing live till Publish.
2. Always-visible STATUS BAR (data-testid status-bar) replacing the old dirty-bar. Reassures
   "editing a private draft, nothing live till Publish"; green "Saved" badge (status-saved)
   flashes on each text save (setJustSaved).
3. PREVIEW button (editor-preview) -> new backend GET /api/editor/preview/{site}/{page}
   renders for_editor=False (no toolbar/data-eid) = clean visitor view.
4. Softer Publish wording: modal title "Publish to Hostinger" -> "Make your changes live";
   plain-English reassurance copy.
5. RESET PAGE button (editor-reset) -> new backend POST /api/pages/{site}/{slug}/reset.
   Snapshots ("pre-reset") + push_undo, then re-ingests the page from its source file on disk
   (last pulled/imported). Friendly 400 if page has no source file. Live site untouched.
6. Empty-state hint: EDITOR_INJECT CSS `[data-eid]:empty::before{content:"Click to edit"}`
   (editor-only, never on live).
Version bumped backend BUILD_VERSION + frontend UI_BUILD to 2026-06-14-cms-v23-client-ux.
DEPLOY: CODE — user must Save to GitHub then rebuild+recreate TrueNAS container; footer will
read v23-client-ux when live.

Repo sync check (this session): user's GitHub zip == preview code (only CRLF vs LF differ);
Pull button confirmed present in their repo before these UX additions.

## 2026-06 (fork) — FIX: "used bikes gallery only accepts one image". Build cms-v36.
ROOT CAUSE (verified, not guessed): the POST /api/pages/{site}/{slug}/bulk-image endpoint had NO
route decorator — the @api.post(".../bulk-image") line was dropped when the add-section endpoint
(cms-v30) was inserted directly ABOVE bulk_image (same regression pattern as the /sites/add publish
404). So bulk-image was UNREGISTERED and returned 404 "Not Found" for ALL pages. Cars only "looked"
fine because their multiple images were added BEFORE the break; any new bulk add (bikes or cars)
silently failed with "Could not add photos". Reproduced via curl: 404 before fix, {ok:true,added:3}
after; bikes card0 went 1→4 imgs, then undone to clean up. Fix = restored the decorator.
LESSON (again): when inserting an endpoint above another, keep the NEXT function's @api decorator.
USER ACTION: Save to GitHub → rebuild TrueNAS container → footer should read cms-v36.
