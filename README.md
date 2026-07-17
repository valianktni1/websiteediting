# Website Editor — self-hosted in-context CMS

Edit your existing static sites (hosted on Hostinger) from a private admin app on your
TrueNAS. Click any text to edit, click any image to replace, then **Publish** — the app
regenerates the HTML and pushes it to Hostinger over SFTP (with an automatic backup first).
The public site stays 100% static on Hostinger, so it's always up even if the NAS is off.

## Stack
- **backend/** — FastAPI + MongoDB (auth with roles, HTML ingestion, render, publish/SFTP)
- **frontend/** — React admin + in-context editor (served by nginx, proxies /api to backend)
- **docker-compose.yml** — mongo + backend + web, app published on port **30042**

## Deploy on TrueNAS (Dockge)
1. Push this folder to your GitHub repo, then point Dockge at it (or paste the compose).
2. Create the datasets (already planned):
   - `/mnt/apps/website_editor/sites`   → put each site's exported HTML in a subfolder
     (e.g. `/mnt/apps/website_editor/sites/wifetobe/` containing index.html, assets/, etc.)
   - `/mnt/apps/website_editor/data`    → app data (uploads, rendered output)
   - `/mnt/apps/website_editor/mongo`   → database
   - `/mnt/photographers_data/website_editor_backup` → pre-publish backups (zip per publish)
3. Create a `.env` next to the compose (see `.env.example`): set `JWT_SECRET`,
   `ADMIN_EMAIL`, `ADMIN_PASSWORD`.
4. Deploy the stack. The app runs on `http://<truenas-ip>:30042`.
5. In **Nginx Proxy Manager**: proxy host `client.wifetobe.org` → `http://<truenas-ip>:30042`,
   request a Let's Encrypt SSL cert (use DNS-challenge if your ISP blocks port 80).
6. Log in with your ADMIN credentials. On first boot it auto-ingests any site folders found.

## Connect a site to Hostinger (to publish live)
In the app, an admin sets the site's **SFTP** details (Hostinger host, port 22, username,
password, remote path e.g. `/public_html`). `Publish` then: renders all pages → zips a
backup to the backup dataset → SFTP-uploads to Hostinger. Until SFTP is set, Publish still
renders + backs up and reports it's ready.

## Adding another site later
Drop its exported HTML into `/mnt/apps/website_editor/sites/<name>/`, then (as admin)
POST `/api/sites/<name>/ingest`. Give it its own subdomain in NPM.

## What's preserved
Every page's title, meta description/keywords/robots, Open Graph, Twitter cards, canonical,
and JSON-LD schema are kept exactly and re-emitted on publish, plus robots.txt, sitemap.xml,
llms.txt and llms-full.txt.

## Roles
- **admin** (you): manage users, SFTP settings, ingest sites, edit + publish.
- **editor** (client): edit content + publish.
Create users (admin only) via `POST /api/users`.
