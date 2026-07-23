# Changelog — Website Editor CMS

## 2026-06 (fork continuation)

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
