# Wife To Be — wifetobe.org (Chester & Cheshire)

A fast, mobile-responsive, SEO-optimised static HTML site for **Wife To Be**, built for the **wifetobe.org** domain and ready to upload to Hostinger File Manager (public_html).

## What's different from wifetobe.co.uk
- **Unique wording** on every page (rewritten so the two domains don't duplicate content).
- **Home page optimised for Chester & Cheshire.**
- **Local area landing pages replaced** with: **Wigan, Frodsham, Newton-le-Willows, Bolton** (each with unique copy + FAQ schema).
- **Fresh imagery** (different from the .co.uk site) — real Veni Infantino photos kept in `/assets`.
- **Same branding, colours, fonts, contact details & email** as the original.
- **SEO files updated for wifetobe.org:** `robots.txt`, `sitemap.xml`, `llms.txt`, `llms-full.txt`, JSON-LD schema and canonical tags.

## Pages
| File | Page |
|------|------|
| `index.html` | Home (Chester & Cheshire) |
| `about.html` | About Us |
| `bridal-collections.html` | Wedding Dresses / Designers |
| `mens-formal-wear.html` | Men's Formal Wear / Suit Hire |
| `brides.html` | Reviews & Real Weddings |
| `found-the-dress.html` | No More Stress, I Found The Dress |
| `boutiques.html` | Our Boutiques (with maps) |
| `contact.html` | Contact & Book Appointment |
| `big-screen-advertising.html` | Big Screen Advertising |
| `wigan.html` | Wedding Dresses Wigan |
| `frodsham.html` | Wedding Dresses Frodsham |
| `newton-le-willows.html` | Wedding Dresses Newton-le-Willows |
| `bolton.html` | Wedding Dresses Bolton |
| `404.html` | Not Found |

Assets (CSS, JS, logo, favicon, designer photos) live in `/assets/`.

## How to publish on Hostinger
1. In hPanel, open **File Manager** and go to `public_html` for wifetobe.org.
2. Upload the **entire contents** of this folder (not the folder itself) — including the hidden `.htaccess`.
3. Make sure `index.html` sits in the root of `public_html`.
4. In Hostinger File Manager, enable "show hidden files" (dotfiles) so `.htaccess` uploads correctly.
5. Visit https://wifetobe.org/ to check it live.

## Notes
- Every "Book Appointment" button opens an email to `thegroupuk@yahoo.com`.
- The contact form falls back to a pre-filled email (no backend needed).
- Images use fresh stock photography plus your real Veni Infantino photos. Swap in your own designer photos any time by replacing files in `/assets` or the `<img src>` URLs.

## Business details
- **Warrington (primary):** 3-5 Fennel Street, Warrington, WA1 2PA — 01925 570093 — Tue–Fri 11–5, Sat 10–5
- **Runcorn:** 136 Greenway Road, Runcorn, WA7 5BS — 0151 420 0151 — Suit hire by appointment
- **Email:** thegroupuk@yahoo.com
