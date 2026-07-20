IVORY DIGITAL — WEBSITE PACKAGE
================================

Thank you! This ZIP contains a complete, static HTML website for Ivory Digital.
It needs no database and no server-side code — just upload the files.

WHAT'S INSIDE
-------------
  index.html                        Home
  booking-system.html               The Booking System (features + branding + FAQ schema)
  studioapp.html                    StudioApp client galleries (FAQ schema)
  web-design-seo.html               Website Design & SEO (FAQ schema)
  web-seo-enquiry.html              Web design / SEO enquiry form
  pricing.html                      Pricing & Packages
  about.html                        About
  faq.html                          FAQ (FAQ rich-result schema)
  contact.html                      Free-trial / contact form
  thank-you.html                    Form thank-you / confirmation page
  locations.html                    Bridal booking "by location" hub

  Bridal city landing pages (unique content + local + FAQ schema):
  bridal-booking-system-london.html
  bridal-booking-system-manchester.html
  bridal-booking-system-birmingham.html
  bridal-booking-system-leeds.html
  bridal-booking-system-liverpool.html
  bridal-booking-system-sheffield.html
  bridal-booking-system-bristol.html
  bridal-booking-system-newcastle.html
  bridal-booking-system-nottingham.html
  bridal-booking-system-leicester.html

  404.html               Friendly "page not found" page
  robots.txt             Search-engine + AI crawler rules
  sitemap.xml            Sitemap for search engines (all pages)
  llms.txt / llms_full.txt   AI/LLM summary of the site
  assets/css/style.v3.css    Styles (sage + ivory + soft gold theme)
  assets/js/main.js          Mobile menu, footer year, etc.
  assets/img/                Logo, favicon, social image, screenshots

HOW TO UPLOAD (cPanel / hosting file manager)
---------------------------------------------
  1. Log in to your hosting control panel and open File Manager.
  2. Go into your website root folder (usually "public_html").
  3. Upload EVERYTHING inside this "ivory-digital-website" folder
     (all the .html files, the .txt/.xml files, and the "assets" folder)
     directly into public_html — keep the folder structure intact.
  4. Visit https://ivorydigital.uk — the home page loads automatically.

RECOMMENDED HOST REDIRECTS (helps Google indexing)
--------------------------------------------------
To keep Google seeing ONE version of every page, make sure your host forces:
  • HTTPS (not http)
  • one domain form — we recommend NON-www: ivorydigital.uk (not www.)
  • the clean home URL "/" (not /index.html)

If your host runs Apache, create a file named ".htaccess" in public_html
with the following (adjust only if your host advises otherwise):

    RewriteEngine On
    # Force HTTPS
    RewriteCond %{HTTPS} off
    RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [L,R=301]
    # Force non-www
    RewriteCond %{HTTP_HOST} ^www\.(.+)$ [NC]
    RewriteRule ^ https://%1%{REQUEST_URI} [L,R=301]
    # Send /index.html to the clean "/"
    RewriteCond %{THE_REQUEST} \s/index\.html[\s?] [NC]
    RewriteRule ^index\.html$ / [L,R=301]

(If you're on Nginx or a managed host, just enable "Force HTTPS" and set your
preferred domain to ivorydigital.uk in the control panel — that's enough.)

AFTER GOING LIVE (recommended)
------------------------------
  • In Google Search Console, submit the sitemap:
        https://ivorydigital.uk/sitemap.xml
  • Use "URL Inspection" on your key pages (home, booking-system, each city
    page) and click "Request indexing" to speed things up.
  • The contact and enquiry forms send automatically via Web3Forms and then
    redirect the visitor to thank-you.html. Emails arrive at
    sales@ivorydigital.uk. No email app or server code is needed.
  • Replace demo screenshots in assets/img/ with your own any time
    (keep the same file names).

NOTES
-----
  • All links are root-relative (e.g. /pricing.html), so the site must live
    at the domain root (public_html), not inside a sub-folder.
  • Every page is SEO-ready: unique titles/descriptions, canonical URLs that
    match internal links, Open Graph/Twitter cards, JSON-LD structured data
    (Organisation, LocalBusiness, Service, Breadcrumbs, FAQ), sitemap, robots
    and llms files.

Designed & Hosted by Ivory Digital
sales@ivorydigital.uk · +44 7712 117357
