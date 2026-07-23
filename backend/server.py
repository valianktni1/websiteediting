from dotenv import load_dotenv
load_dotenv()

import os, io, re, json, shutil, zipfile, glob, socket, asyncio, logging, uuid
import base64, mimetypes, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from templates_seed import BUILTIN_TEMPLATES

import bcrypt, jwt
from bson import ObjectId
from bs4 import BeautifulSoup
from bs4.element import Tag, NavigableString, Comment, Doctype, CData, ProcessingInstruction
from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image, ImageOps
import io as _io

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
COOKIE_SECURE = os.environ.get("COOKIE_SECURE","false").lower() == "true"
SITES_DIR = os.environ.get("SITES_DIR", "/app/sites_source")
DATA_DIR = os.environ.get("DATA_DIR", "/app/site_data")
MEDIA_DIR = os.path.join(DATA_DIR, "media")
DIST_DIR = os.path.join(DATA_DIR, "dist")
BACKUP_DIR = os.environ.get("BACKUP_DIR", os.path.join(DATA_DIR, "backups"))
for d in (DATA_DIR, MEDIA_DIR, DIST_DIR, BACKUP_DIR):
    os.makedirs(d, exist_ok=True)

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
LLM_PROXY = os.environ.get("INTEGRATION_PROXY_URL", "https://integrations.emergentagent.com") + "/llm/chat/completions"

def _load_image_bytes(slug, src):
    if src.startswith("http://") or src.startswith("https://"):
        req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read(), (r.headers.get_content_type() or "image/jpeg")
    if src.startswith("assets/uploads/"):
        path = os.path.join(MEDIA_DIR, slug, src[len("assets/uploads/"):])
    else:
        path = os.path.join(SITES_DIR, slug, src)
    if not os.path.isfile(path):
        raise ValueError("Image not found on the server yet — save the image first.")
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    with open(path, "rb") as f:
        return f.read(), mime

def _suggest_alt_gemini(img_bytes, mime):
    if mime not in ("image/jpeg", "image/png", "image/webp"):
        mime = "image/jpeg"
    b64 = base64.b64encode(img_bytes).decode()
    payload = {
        "model": "gemini/gemini-2.5-flash",
        "messages": [
            {"role": "system", "content": "You write concise, descriptive alt text for website images for SEO and accessibility. Reply with ONLY the alt text: one sentence, no quotes, max 16 words."},
            {"role": "user", "content": [
                {"type": "text", "text": "Write alt text for this image."},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ]},
        ],
    }
    req = urllib.request.Request(LLM_PROXY, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {EMERGENT_LLM_KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"].strip().strip('"').strip()

app = FastAPI(title="Website Editor")
api = APIRouter(prefix="/api")

BUILD_VERSION = "2026-06-13-cms-v19"

@api.get("/version")
async def version():
    return {"version": BUILD_VERSION, "features": ["add-site-async", "sftp-test", "domain-lock", "multi-site", "publish-confirm", "session-snapshot", "reorder", "undo", "branding", "remove-site"]}

EDIT_TAGS = {"h1","h2","h3","h4","h5","h6","p","li","a","button","blockquote","figcaption"}

# ---------------- auth helpers ----------------
def hash_pw(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def verify_pw(p, h): 
    try: return bcrypt.checkpw(p.encode(), h.encode())
    except Exception: return False
def make_token(uid, email, role):
    return jwt.encode({"sub":uid,"email":email,"role":role,"type":"access",
                       "exp":datetime.now(timezone.utc)+timedelta(days=7)}, JWT_SECRET, algorithm=JWT_ALG)

async def current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        h = request.headers.get("Authorization","")
        if h.startswith("Bearer "): token = h[7:]
    if not token: raise HTTPException(401,"Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        u = await db.users.find_one({"_id":ObjectId(payload["sub"])})
        if not u: raise HTTPException(401,"User not found")
        u["id"]=str(u["_id"]); u.pop("_id"); u.pop("password_hash",None)
        return u
    except jwt.ExpiredSignatureError: raise HTTPException(401,"Token expired")
    except jwt.InvalidTokenError: raise HTTPException(401,"Invalid token")

async def require_admin(u=Depends(current_user)):
    if u.get("role") not in ("admin", "superadmin"): raise HTTPException(403,"Admin only")
    return u

async def require_super(u=Depends(current_user)):
    if u.get("role") != "superadmin": raise HTTPException(403,"Super admin only")
    return u

# ---------------- models ----------------
class Login(BaseModel):
    email: str
    password: str
class NewUser(BaseModel):
    email: str
    password: str
    name: str = ""
    role: str = "editor"
    site_id: str | None = None
class RegionUpdate(BaseModel):
    eid: str
    value: str
class LinkUpdate(BaseModel):
    eid: str
    href: str
class AltUpdate(BaseModel):
    eid: str
    alt: str
class BulkImage(BaseModel):
    eid: str
    urls: list[str]
class PageOp(BaseModel):
    op: str
    eid: str
    ref: str | None = None
    kind: str | None = None
    url: str | None = None
class AltSuggest(BaseModel):
    eid: str
class CaptionUpdate(BaseModel):
    eid: str
    caption: str
class SeoUpdate(BaseModel):
    seo: dict
class SftpSettings(BaseModel):
    host: str = ""
    port: int = 22
    username: str = ""
    password: str = ""
    remote_path: str = "public_html"
    domain: str = ""

class AddSite(BaseModel):
    slug: str
    name: str = ""
    domain: str = ""
    host: str
    port: int = 22
    username: str
    password: str
    remote_path: str = "public_html"

class Branding(BaseModel):
    brand_name: str = ""
    logo_url: str = ""
    subdomain: str = ""
    accent: str = ""
    accent_dark: str = ""
    on_accent: str = ""
    heading_font: str = ""
    body_font: str = ""
    font_link: str = ""

class TemplateIn(BaseModel):
    name: str
    description: str = ""
    sections_html: str
    css: str = ""
    js: str = ""

class FromTemplate(BaseModel):
    template_id: str
    slug: str
    title: str
    enquiry_email: str = ""

class UserUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    site_id: str | None = None
    password: str = ""

class SiteMeta(BaseModel):
    name: str | None = None
    domain: str | None = None

# ---------------- ingestion ----------------
def _clean_links(s):
    s = re.sub(r'href="index\.html"', 'href="/"', s)
    s = re.sub(r'href="([a-z0-9][a-z0-9-]*)\.html"', r'href="/\1/"', s)
    s = re.sub(r'href="https?://[^"]*?/([a-z0-9-]+)\.html"', r'href="/\1/"', s)
    return s

_ASSET_EXT = r'(?:css|js|mjs|png|jpe?g|gif|svg|webp|avif|ico|bmp|woff2?|ttf|otf|eot|mp4|webm|ogg|pdf)'
def _relativize_assets(html):
    """Root-absolute asset refs (e.g. src="/assets/..") bypass the editor's <base> tag and 404,
    which shows the site unstyled ('massive icons'). Published pages are flat at site root, so
    making these relative is safe for both the editor canvas and publishing. Nav links (e.g.
    /about/) are left untouched — only src, asset-file hrefs and url() are relativized."""
    html = re.sub(r'\bsrc="/(?!/)', 'src="', html)
    html = re.sub(r"\bsrc='/(?!/)", "src='", html)
    html = re.sub(r'\bsrcset="/(?!/)', 'srcset="', html)
    html = re.sub(r'\bhref="/(?!/)([^"]*\.' + _ASSET_EXT + r'(?:\?[^"]*)?)"', r'href="\1"', html, flags=re.I)
    html = re.sub(r'url\((["\']?)/(?!/)', r'url(\1', html)
    return html

def _set_html(el, html):
    el.clear()
    frag = BeautifulSoup(html or "", "html.parser")
    for c in list(frag.contents):
        el.append(c)

def _apply_image(el, value, alt=None):
    """Set an image src; if it was changed, drop responsive attrs (srcset/sizes/data-src)
    that would otherwise make the browser keep showing the OLD image. Optionally set alt."""
    orig = el.get("src", "")
    el["src"] = value
    if value != orig:
        for a in ("srcset", "sizes", "data-src", "data-srcset", "data-lazy-src", "data-lazy-srcset"):
            if el.has_attr(a): del el[a]
    if alt is not None:
        el["alt"] = alt

def _is_card_link(el):
    """A link/button that wraps structural content (svg/img/div/span) rather than being a
    plain text link. Its inner text isn't editable as one region, so we treat it as a link
    and expose its inner text spans separately."""
    INLINE_FMT = {"b","strong","i","em","u","small","br","sub","sup","mark"}
    return el.name in ("a","button") and any(
        isinstance(c, Tag) and c.name not in INLINE_FMT for c in el.children)

def assign_regions(body):
    """Clear + reassign data-eid across the body and return a fresh regions dict.
    Shared by ingest and structural edits so eids/regions stay consistent."""
    for el in body.find_all(attrs={"data-eid": True}):
        del el["data-eid"]
    regions = {}
    n = 0
    for el in body.find_all(list(EDIT_TAGS)):
        if el.find(list(EDIT_TAGS)):
            continue
        if not el.get_text(strip=True):
            continue
        # card-style links/buttons (wrapping svg/img/span) are handled as links below and their
        # inner text spans are made editable separately — don't lock their text into one region
        if _is_card_link(el):
            continue
        eid = f"t{n}"; n += 1
        el["data-eid"] = eid
        reg = {"type": "text", "value": el.decode_contents()}
        if el.name in ("a", "button") and el.has_attr("href"):
            reg["href"] = el.get("href", "")
            reg["link"] = True
        regions[eid] = reg
    # inline values that stand alone (e.g. car spec <span>Year</span><b>2021</b>, or the brand
    # name inside a logo link) — make them editable too, but NOT when inside a block-level text
    # region (so prose paragraphs with inline <b>/<strong> keep editing as one region).
    for el in body.find_all(["span", "b", "strong"]):
        if el.has_attr("data-eid"):
            continue
        if el.find(list(EDIT_TAGS) + ["span", "b", "strong"]):
            continue
        if not el.get_text(strip=True):
            continue
        parent_edit = el.find_parent(list(EDIT_TAGS))
        if parent_edit is not None and not _is_card_link(parent_edit):
            continue
        eid = f"t{n}"; n += 1
        el["data-eid"] = eid
        regions[eid] = {"type": "text", "value": el.decode_contents()}
    for img in body.find_all("img"):
        eid = f"i{n}"; n += 1
        img["data-eid"] = eid
        regions[eid] = {"type": "image", "value": img.get("src", ""), "alt": img.get("alt", "")}
    # card / image links: <a href> that wrap other elements (not leaf text links) — make editable
    for a in body.find_all("a"):
        if a.has_attr("data-eid") or not a.has_attr("href"):
            continue
        eid = f"a{n}"; n += 1
        a["data-eid"] = eid
        regions[eid] = {"type": "link", "href": a.get("href", "")}
    return regions

def _tag_repeating_blocks(soup):
    """Auto-tag repeating card-like siblings with data-block so a whole card can be
    duplicated/deleted/moved in the editor (keeps grid spacing). Detects any parent with
    >=2 direct children sharing a class that each look like a card (a heading, or an image
    plus a paragraph). Nav menus / link lists are excluded (no heading/media)."""
    from collections import Counter
    CARD_TAGS = {"div", "article", "li", "a", "section"}
    for parent in soup.find_all():
        kids = [c for c in parent.find_all(recursive=False)
                if getattr(c, "name", None) in CARD_TAGS and c.get("class")]
        if len(kids) < 2:
            continue
        sigs = Counter(tuple(sorted(c.get("class"))) for c in kids)
        for c in kids:
            if c.has_attr("data-block"):
                continue
            if sigs[tuple(sorted(c.get("class")))] < 2:
                continue
            has_head = c.find(["h2", "h3", "h4", "h5"]) is not None
            has_card = has_head or (c.find("img") is not None and c.find("p") is not None)
            if has_card:
                c["data-block"] = c.get("class")[0]

WRAP_SKIP = {"script","style","svg","title","textarea","noscript","code","pre","head","select","option","template","math"}

def _wrap_loose_text(soup, body):
    """Wrap stray visible text (e.g. a word sitting directly inside a <div>, or text next to a
    <span> inside a logo link) in a <span class="ivd-txt"> so it becomes an editable region.
    Makes almost all visible copy editable on ANY imported site. Skips scripts/styles/svg and
    text that is already the sole content of a normal edit tag (handled as a region already)."""
    for node in list(body.find_all(string=True)):
        # find_all(string=True) also returns Comment/CData/Doctype (NavigableString subclasses);
        # only wrap plain visible text, never comments — else <!-- x --> becomes visible <span>x</span>.
        if type(node) is not NavigableString:
            continue
        if not node.strip():
            continue
        parent = node.parent
        if parent is None or parent.name in WRAP_SKIP:
            continue
        if parent.find_parent(list(WRAP_SKIP)):
            continue
        has_tag_children = any(isinstance(c, Tag) for c in parent.children)
        # pure-text edit tags (e.g. <p>hi</p>, <h2>hi</h2>) are already editable regions — leave them
        if parent.name in EDIT_TAGS and not has_tag_children:
            continue
        if parent.name in ("span", "b", "strong", "i", "em") and not has_tag_children:
            continue
        span = soup.new_tag("span")
        span["class"] = ["ivd-txt"]
        span.string = str(node)
        node.replace_with(span)

def ingest_page(html, slug):
    html = _relativize_assets(html)
    soup = BeautifulSoup(html, "lxml")
    # SEO
    title = soup.title.string if soup.title else ""
    metas, canonical, jsonld = [], "", []
    if soup.head:
        for m in soup.head.find_all("meta"):
            n, pr = m.get("name"), m.get("property")
            if n in ("description","keywords","robots","author","theme-color") or \
               (pr and (pr.startswith("og:") or pr.startswith("article:"))) or \
               (n and n.startswith("twitter:")):
                metas.append(str(m))
        lk = soup.head.find("link", rel="canonical")
        if lk: canonical = lk.get("href","")
        jsonld = [str(s) for s in soup.head.find_all("script", type="application/ld+json")]
    # body only for template
    body = soup.body
    # strip HTML comments so they can never leak as visible text on the published page
    for c in list(body.find_all(string=lambda s: isinstance(s, Comment))):
        c.extract()
    _tag_repeating_blocks(body)
    _wrap_loose_text(soup, body)
    regions = assign_regions(body)
    n = len(regions)
    template = str(body)
    # capture stylesheet/style/font/favicon links so the design renders exactly
    head_assets = []
    if soup.head:
        for t in soup.head.find_all(["link","style"]):
            rel = t.get("rel") or []
            if t.name == "link" and "canonical" in rel:
                continue
            head_assets.append(str(t))
    return {
        "slug": slug,
        "title": title or slug,
        "seo": {"title":title,"metas":metas,"canonical":canonical,"jsonld":jsonld},
        "template": template,
        "regions": regions,
        "head_assets": head_assets,
    }

def _slug_for_relpath(relpath):
    """Map a site-relative HTML path to a URL-safe slug (no slashes, so routing works).
    index.html -> home ; about.html -> about ; car-sales/index.html -> car-sales ;
    car-sales/stock.html -> car-sales__stock ; a/b/index.html -> a__b."""
    relpath = relpath.replace("\\", "/")
    if relpath == "index.html":
        return "home"
    base = relpath[:-5] if relpath.endswith(".html") else relpath
    if base.endswith("/index"):
        base = base[:-len("/index")]
    return base.replace("/", "__")

async def ingest_site(site_slug, force=False):
    src = os.path.join(SITES_DIR, site_slug)
    if not os.path.isdir(src): return {"total": 0, "added": 0, "preserved": 0}
    if force and await db.pages.find_one({"site": site_slug}):
        await create_snapshot(site_slug, "reimport", "Before fresh re-import")
    await db.sites.update_one({"slug":site_slug},{"$set":{"slug":site_slug,"name":site_slug,"source_dir":src,
        "updated_at":datetime.now(timezone.utc).isoformat()}}, upsert=True)
    order=[]
    total=0; added=0; preserved=0
    # recurse into subfolders (e.g. car-sales/index.html) but skip asset/hidden dirs
    for path in sorted(glob.glob(os.path.join(src,"**","*.html"), recursive=True)):
        relpath = os.path.relpath(path, src).replace("\\","/")
        parts = relpath.split("/")
        if any(p.startswith(".") for p in parts) or "assets" in parts[:-1] or "node_modules" in parts:
            continue
        slug = _slug_for_relpath(relpath)
        fn = os.path.basename(path)
        existing = await db.pages.find_one({"site":site_slug,"slug":slug})
        if existing and not force:
            # PRESERVE the user's edits — never overwrite an already-imported page from source.
            # Only refresh routing metadata so subfolder publish keeps working.
            await db.pages.update_one({"site":site_slug,"slug":slug},
                {"$set":{"filename":fn,"relpath":relpath,"site":site_slug}})
            title = existing.get("title", slug)
            preserved += 1
        else:
            # fresh (new page, or a forced clean re-import that rebuilds the template from source)
            data = ingest_page(open(path,encoding="utf-8").read(), slug)
            data["site"]=site_slug; data["filename"]=fn; data["relpath"]=relpath
            await db.pages.update_one({"site":site_slug,"slug":slug},{"$set":data}, upsert=True)
            title = data["title"]; added += 1
        order.append({"slug":slug,"filename":fn,"relpath":relpath,"title":title})
        total+=1
    await db.sites.update_one({"slug":site_slug},{"$set":{"order":order}})
    if total and not await db.snapshots.find_one({"site":site_slug,"kind":"import"}):
        await create_snapshot(site_slug, "import", "Original (as imported)")
    await autofill_brand(site_slug, src)
    return {"total": total, "added": added, "preserved": preserved}

_HEX = r'#[0-9a-fA-F]{3,8}'

def extract_brand(src_dir):
    """Best-effort palette + fonts from a site's CSS/HTML. Fills what it can; blanks otherwise."""
    css = ""
    for p in glob.glob(os.path.join(src_dir, "**", "*.css"), recursive=True):
        try: css += open(p, encoding="utf-8", errors="ignore").read() + "\n"
        except Exception: pass
    home = ""
    for name in ("index.html",):
        fp = os.path.join(src_dir, name)
        if os.path.isfile(fp):
            try: home = open(fp, encoding="utf-8", errors="ignore").read()
            except Exception: pass
    # inline <style> too
    for m in re.finditer(r"<style[^>]*>(.*?)</style>", home, re.S | re.I):
        css += m.group(1) + "\n"
    out = {"accent": "", "accent_dark": "", "on_accent": "", "heading_font": "",
           "body_font": "", "font_link": ""}
    def find_var(names):
        for nm in names:
            m = re.search(r'--' + nm + r'\s*:\s*(' + _HEX + r')', css)
            if m: return m.group(1)
        return ""
    out["accent"] = find_var(["accent", "primary", "brand", "brand-color", "brand-colour",
                              "color-primary", "primary-color", "theme", "highlight"])
    out["accent_dark"] = find_var(["accent-dark", "accent-d", "primary-dark", "brand-dark"])
    # google fonts link
    m = re.search(r'<link[^>]+href="(https://fonts\.googleapis\.com/css2?[^"]+)"', home)
    if m:
        out["font_link"] = m.group(1)
        fams = re.findall(r'family=([^:&]+)', m.group(1))
        fams = [f.replace("+", " ") for f in fams]
        if fams: out["heading_font"] = fams[0]
        if len(fams) > 1: out["body_font"] = fams[1]
        elif fams: out["body_font"] = fams[0]
    return out

async def autofill_brand(site_slug, src_dir):
    """Populate site.branding tokens from the source, without overwriting anything already set."""
    try:
        ext = extract_brand(src_dir)
    except Exception:
        return
    s = await db.sites.find_one({"slug": site_slug})
    b = dict((s or {}).get("branding") or {})
    changed = False
    for k, v in ext.items():
        if v and not b.get(k):
            b[k] = v; changed = True
    if changed:
        await db.sites.update_one({"slug": site_slug}, {"$set": {"branding": b}})

def _brand_root_style(branding):
    """CSS :root block mapping a site's brand tokens to the --brand-* names templates read."""
    b = branding or {}
    lines = []
    if b.get("accent"): lines.append(f'--brand-accent:{b["accent"]};')
    if b.get("accent_dark"): lines.append(f'--brand-accent-dark:{b["accent_dark"]};')
    elif b.get("accent"): lines.append(f'--brand-accent-dark:{b["accent"]};')
    if b.get("on_accent"): lines.append(f'--brand-on-accent:{b["on_accent"]};')
    if b.get("heading_font"): lines.append(f"--brand-heading:'{b['heading_font']}',sans-serif;")
    if b.get("body_font"): lines.append(f"--brand-body:'{b['body_font']}',sans-serif;")
    if not lines: return ""
    return "<style>:root{" + "".join(lines) + "}</style>"

def _chrome_from_home(home_template):
    """Pull the site's header + footer markup so a template page looks native."""
    soup = BeautifulSoup(home_template, "lxml")
    body = soup.body or soup
    header = body.find("header")
    footer = body.find("footer")
    return (str(header) if header else ""), (str(footer) if footer else "")

def _find_nav_container(scope):
    """Best-effort: find the element inside a header that holds the nav links (the
    descendant with the most direct <a> children). Returns a bs4 Tag or None."""
    if scope is None: return None
    header = scope if getattr(scope, "name", "") == "header" else scope.find("header")
    root = header or scope
    best, best_n = None, 0
    for el in root.find_all(["nav", "ul", "ol", "div"]):
        n = sum(1 for c in el.find_all("a", recursive=False))
        if n > best_n:
            best, best_n = el, n
    if best_n >= 2:
        return best
    nav = root.find("nav")
    return nav if nav and nav.find("a") else None

def _href_at_depth(slug, depth):
    return ("../" * max(0, depth)) + f"{slug}.html"

def _nav_has_link(container, slug):
    for a in container.find_all("a"):
        h = (a.get("href") or "").split("#")[0].split("?")[0]
        if h.rstrip("/").endswith(f"{slug}.html"):
            return True
    return False

def _new_nav_anchor(soup, container, slug, title, depth):
    """Build a nav <a> that mimics the existing links' classes, sized/placed sensibly."""
    links = container.find_all("a", recursive=False) or container.find_all("a")
    a = soup.new_tag("a")
    a["href"] = _href_at_depth(slug, depth)
    a.string = title
    # copy classes from a plain (non-CTA) existing link so styling matches
    for l in links:
        cls = l.get("class") or []
        joined = " ".join(cls).lower()
        if not any(k in joined for k in ("btn", "button", "cta", "book", "call", "quote")):
            clean = [c for c in cls if c.lower() not in ("active", "current", "is-active", "selected")]
            if clean: a["class"] = clean
            break
    return a

def _insert_nav_link(container, a):
    """Insert the anchor before a trailing CTA button if present, else append."""
    kids = container.find_all("a", recursive=False)
    cta = None
    for l in kids:
        joined = " ".join(l.get("class") or []).lower()
        if any(k in joined for k in ("btn", "button", "cta", "book", "quote")):
            cta = l
    if cta is not None:
        cta.insert_before(a)
    else:
        container.append(a)


async def _page_docs_for(site):
    pages = []
    async for p in db.pages.find({"site":site}):
        p.pop("_id", None)
        pages.append(p)
    return pages

async def create_snapshot(site, kind, label):
    pages = await _page_docs_for(site)
    if not pages: return None
    s = await db.sites.find_one({"slug":site})
    doc = {"_id": uuid.uuid4().hex, "site": site, "kind": kind, "label": label,
           "created": datetime.now(timezone.utc), "order": (s or {}).get("order", []),
           "pages": pages, "page_count": len(pages)}
    await db.snapshots.insert_one(doc)
    # prune auto/pre-publish/session to the 80 most recent (imports + manual kept forever)
    olds = db.snapshots.find({"site":site,"kind":{"$in":["auto","pre-publish","session"]}}).sort("created",-1)
    i = 0
    async for d in olds:
        i += 1
        if i > 80: await db.snapshots.delete_one({"_id":d["_id"]})
    return doc["_id"]

async def maybe_auto_snapshot(site):
    last = await db.snapshots.find_one({"site":site}, sort=[("created",-1)])
    if last:
        lc = last.get("created")
        if isinstance(lc, str):
            try: lc = datetime.fromisoformat(lc)
            except Exception: lc = None
        if lc is not None:
            if lc.tzinfo is None: lc = lc.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - lc).total_seconds() < 600:
                return
    await create_snapshot(site, "auto", "Auto-saved")

async def push_undo(site, slug):
    """Save the current page state so the client can instantly undo their last edit."""
    p = await db.pages.find_one({"site":site,"slug":slug})
    if not p: return
    doc = dict(p); doc.pop("_id", None)
    await db.edit_history.insert_one({"_id": uuid.uuid4().hex, "site": site, "slug": slug,
        "page": doc, "created": datetime.now(timezone.utc)})
    i = 0
    async for d in db.edit_history.find({"site":site}).sort("created",-1):
        i += 1
        if i > 50: await db.edit_history.delete_one({"_id": d["_id"]})

# ---------------- render ----------------
def render_page(page, for_editor=False, asset_base=""):
    template = page["template"]
    soup = BeautifulSoup(template, "lxml")
    bodyel = soup.body or soup
    # uploaded media lives at the SITE ROOT (assets/uploads/..). For pages in a subfolder we must
    # point back up so the image resolves both in the editor and on the published site.
    rel = (page.get("relpath") or "").replace("\\", "/")
    up = "../" * rel.count("/")
    for eid, r in page["regions"].items():
        el = bodyel.find(attrs={"data-eid":eid})
        if not el: continue
        if r["type"]=="text":
            _set_html(el, r["value"])
            if r.get("href") is not None and el.name in ("a","button"):
                el["href"] = r["href"]
        elif r["type"]=="image":
            val = r["value"]
            if up and isinstance(val, str) and val.startswith("assets/uploads/"):
                val = up + val
            _apply_image(el, val, r.get("alt"))
            cap = (el.get("data-caption") or "").strip()
            if cap:
                fc = soup.new_tag("figcaption"); fc["class"] = "ivd-caption"; fc.string = cap
                el.insert_after(fc)
            if not for_editor and el.has_attr("data-caption"):
                del el["data-caption"]
        elif r["type"]=="link":
            if el.name in ("a","button"):
                el["href"] = r.get("href","")
        if not for_editor and el.has_attr("data-eid"):
            del el["data-eid"]
    if not for_editor:
        # drop Sold cars to the bottom of their grid so available stock shows first (live only)
        seen = set()
        for car in bodyel.find_all(attrs={"data-block": "car"}):
            p = car.parent
            if p is None or id(p) in seen:
                continue
            seen.add(id(p))
            cars = [c for c in p.find_all(attrs={"data-block": "car"}, recursive=False)]
            sold = [c for c in cars if (c.get("data-status") or "") == "sold"]
            keep = [c for c in cars if (c.get("data-status") or "") != "sold"]
            if not sold or not keep:
                continue
            for c in cars:
                c.extract()
            for c in keep + sold:
                p.append(c)
    inner = bodyel.decode_contents()
    seo = page.get("seo",{})
    head = f"<title>{seo.get('title','')}</title>\n" + "\n".join(seo.get("metas",[]))
    if seo.get("canonical"): head += f'\n<link rel="canonical" href="{seo["canonical"]}">'
    head += "\n" + "\n".join(seo.get("jsonld",[]))
    head += "\n" + "\n".join(page.get("head_assets",[]))
    head += '\n<style>.ivd-caption{display:block;text-align:center;font-size:.85rem;color:#666;margin:.4rem auto 1rem;font-style:italic;max-width:90%;}</style>'
    base = f'<base href="{asset_base}">' if asset_base else ""
    editor_assets = EDITOR_INJECT if for_editor else ""
    finance_assets = FINANCE_INJECT if (not for_editor and 'data-block="car"' in inner) else ""
    status_assets = STATUS_CSS if 'data-block=' in inner else ""
    return f"""<!DOCTYPE html><html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">{base}
{head}
{status_assets}
{editor_assets}</head><body>{inner}{finance_assets}</body></html>"""

BLANK_IMG = "data:image/svg+xml,%3Csvg%20xmlns%3D'http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg'%20width%3D'940'%20height%3D'705'%3E%3Crect%20width%3D'100%25'%20height%3D'100%25'%20fill%3D'%23e9ecf1'%2F%3E%3Ctext%20x%3D'50%25'%20y%3D'50%25'%20fill%3D'%239aa1ac'%20font-family%3D'Arial%2Csans-serif'%20font-size%3D'40'%20text-anchor%3D'middle'%20dominant-baseline%3D'middle'%3E%2B%20Add%20photo%3C%2Ftext%3E%3C%2Fsvg%3E"
from assets_data import COMING_SOON_IMG

# Sold / Reserved / New-in ribbon styling, injected by the CMS so badges always render on car cards,
# even when a site's own stylesheet doesn't include them. Generic: targets any [data-block][data-status].
STATUS_CSS = """<style>
[data-block][data-status="sold"],[data-block][data-status="reserved"],[data-block][data-status="new"]{position:relative}
[data-block][data-status="sold"]::before,[data-block][data-status="reserved"]::before,[data-block][data-status="new"]::before{position:absolute;top:14px;left:14px;z-index:6;padding:6px 13px;border-radius:8px;font-family:'Space Grotesk','Sora',system-ui,sans-serif;font-weight:700;font-size:.72rem;letter-spacing:.1em;text-transform:uppercase;color:#fff;box-shadow:0 8px 20px -8px rgba(0,0,0,.55)}
[data-block][data-status="sold"]::before{content:"Sold";background:#d12b2b}
[data-block][data-status="reserved"]::before{content:"Reserved";background:#E85D00}
[data-block][data-status="new"]::before{content:"New in";background:#1f9d55}
[data-block][data-status="sold"] img{filter:grayscale(.5);opacity:.72}
[data-block][data-status="sold"] .price,[data-block][data-status="sold"] .uc-price,[data-block][data-status="sold"] [class*="price"]{text-decoration:line-through;opacity:.7}
</style>"""

EDITOR_INJECT = """
<style>
[data-eid]{outline:1px dashed rgba(167,140,70,0);transition:outline .12s;cursor:pointer}
[data-eid]:hover{outline:2px dashed #A78C46;outline-offset:2px}
[data-eid].ed-sel{outline:2px solid #A78C46;outline-offset:2px}
[data-eid][contenteditable="true"]{cursor:text}
img[data-eid]{cursor:grab}
img[data-eid].ed-drag{opacity:.4}
img[data-eid].ed-over{outline:3px solid #A78C46 !important;outline-offset:2px}
#ed-tb{position:absolute;z-index:2147483000;display:none;flex-wrap:wrap;align-items:center;gap:4px;max-width:520px;background:#12151b;border:1px solid #A78C46;border-radius:8px;padding:6px;box-shadow:0 10px 30px rgba(0,0,0,.5);font-family:Arial,sans-serif}
#ed-tb button{background:#232833;color:#e9ecf1;border:1px solid #3a4150;border-radius:5px;padding:5px 9px;font-size:12px;line-height:1;cursor:pointer;white-space:nowrap}
#ed-tb button:hover{background:#A78C46;color:#161616;border-color:#A78C46}
#ed-tb button.ed-block-btn{background:#3a2f14;color:#e9d9a8;border-color:#A78C46}
#ed-tb button.ed-block-btn:hover{background:#A78C46;color:#161616}
#ed-tb .ed-div{color:#A78C46;font-size:10px;font-weight:bold;letter-spacing:.08em;text-transform:uppercase;padding:0 6px 0 8px;border-left:1px solid #3a4150;margin-left:4px;font-family:Arial,sans-serif}
#ed-tb .ed-div:first-child{border-left:none;margin-left:0}
</style>
<script>
document.addEventListener('DOMContentLoaded',function(){
  var tb=document.createElement('div'); tb.id='ed-tb'; document.body.appendChild(tb);
  var sel=null; var dragEid=null;
  // In the editor, links must never navigate (clicking a heading inside a card-link
  // would otherwise open the linked site). Block all link clicks in the canvas.
  document.addEventListener('click',function(e){
    var a=e.target && e.target.closest ? e.target.closest('a') : null;
    if(a){ e.preventDefault(); }
  },true);
  function _ar(el){var w=el.clientWidth||el.naturalWidth||1,h=el.clientHeight||el.naturalHeight||1;return (w>0&&h>0)?(w/h):1;}
  function post(m){parent.postMessage(m,'*');}
  function place(el){
    var r=el.getBoundingClientRect();
    var top=r.top+window.scrollY-tb.offsetHeight-8;
    if(top<window.scrollY+4) top=r.bottom+window.scrollY+8;
    tb.style.top=top+'px';
    tb.style.left=(r.left+window.scrollX)+'px';
  }
  function mk(label,fn){
    var b=document.createElement('button'); b.textContent=label;
    b.addEventListener('mousedown',function(e){e.preventDefault();e.stopPropagation();fn();});
    return b;
  }
  function select(el){
    if(sel && sel!==el) sel.classList.remove('ed-sel');
    sel=el; el.classList.add('ed-sel');
    var eid=el.getAttribute('data-eid');
    var isImg=el.tagName==='IMG';
    var isLink=el.tagName==='A'||el.tagName==='BUTTON';
    var blk=el.closest ? el.closest('[data-block]') : null;
    tb.innerHTML='';
    // --- this element ---
    if(isImg){
      tb.appendChild(mk('Replace',function(){post({t:'image',eid:eid,ar:_ar(el)});}));
      tb.appendChild(mk('+ Add photos',function(){post({t:'bulk-image',eid:eid,ar:_ar(el)});}));
      tb.appendChild(mk('Alt text',function(){post({t:'alt',eid:eid,alt:el.getAttribute('alt')||''});}));
      tb.appendChild(mk('Caption',function(){post({t:'caption',eid:eid,caption:el.getAttribute('data-caption')||''});}));
      if(blk){ tb.appendChild(mk('Delete photo',function(){if(confirm('Delete just this photo?'))post({t:'op',op:'delete',eid:eid});})); }
    }
    if(el.tagName==='LI'){
      tb.appendChild(mk('+ Add feature',function(){post({t:'op',op:'add-el',eid:eid,kind:'listitem'});}));
      tb.appendChild(mk('Delete feature',function(){if(confirm('Delete this feature?'))post({t:'op',op:'delete',eid:eid});}));
    }
    if(isLink && !blk){
      tb.appendChild(mk('Link',function(){post({t:'link',eid:eid,href:el.getAttribute('href')||''});}));
    }
    var _hasSvg = (el.tagName && el.tagName.toLowerCase()==='svg') || (el.querySelector && el.querySelector('svg'));
    var _hasImg = isImg || (el.querySelector && el.querySelector('img'));
    if(_hasSvg && !_hasImg){
      tb.appendChild(mk('Replace logo',function(){post({t:'logo',eid:eid});}));
    }
    if(!blk){
      tb.appendChild(mk('\u2191 Up',function(){post({t:'op',op:'move-up',eid:eid});}));
      tb.appendChild(mk('\u2193 Down',function(){post({t:'op',op:'move-down',eid:eid});}));
      tb.appendChild(mk('Duplicate',function(){post({t:'op',op:'duplicate',eid:eid});}));
      tb.appendChild(mk('Delete',function(){post({t:'op',op:'delete',eid:eid});}));
    }
    // --- add new element anywhere ---
    var alab=document.createElement('span'); alab.className='ed-div'; alab.textContent='Add:'; tb.appendChild(alab);
    tb.appendChild(mk('+ Heading',function(){post({t:'op',op:'add-el',eid:eid,kind:'heading'});}));
    tb.appendChild(mk('+ Text',function(){post({t:'op',op:'add-el',eid:eid,kind:'paragraph'});}));
    tb.appendChild(mk('+ Button',function(){post({t:'op',op:'add-el',eid:eid,kind:'button'});}));
    tb.appendChild(mk('+ Image',function(){post({t:'op',op:'add-el',eid:eid,kind:'image'});}));
    // --- whole card group ---
    if(blk){
      var lab=document.createElement('span'); lab.className='ed-div'; lab.textContent='Card:'; tb.appendChild(lab);
      if(blk.tagName==='A' && blk.getAttribute('data-eid')){
        var lk=mk('Link',function(){post({t:'link',eid:blk.getAttribute('data-eid'),href:blk.getAttribute('href')||''});}); lk.className='ed-block-btn'; tb.appendChild(lk);
      }
      var b1=mk('Duplicate',function(){post({t:'op',op:'duplicate-block',eid:eid});}); b1.className='ed-block-btn';
      var b6=mk('+ Blank card',function(){post({t:'op',op:'add-blank-block',eid:eid});}); b6.className='ed-block-btn';
      var b4=mk('\u25C0 Move',function(){post({t:'op',op:'move-block-up',eid:eid});}); b4.className='ed-block-btn';
      var b5=mk('Move \u25B6',function(){post({t:'op',op:'move-block-down',eid:eid});}); b5.className='ed-block-btn';
      var b2=mk('Delete',function(){post({t:'op',op:'delete-block',eid:eid});}); b2.className='ed-block-btn';
      tb.appendChild(b1); tb.appendChild(b6); tb.appendChild(b4); tb.appendChild(b5); tb.appendChild(b2);
      if(blk.hasAttribute('data-status') || (blk.getAttribute('data-block')||'').toLowerCase().indexOf('car')>=0 || blk.querySelector('.price,.uc-price,[class*="price"]')){
        var bc=mk('+ Add another car',function(){post({t:'op',op:'add-blank-car',eid:eid});}); bc.className='ed-block-btn'; tb.appendChild(bc);
        var b3=mk('Status',function(){post({t:'status',eid:eid});}); b3.className='ed-block-btn'; tb.appendChild(b3);
      }
    }
    tb.style.display='flex';
    place(el);
  }
  document.querySelectorAll('[data-eid]').forEach(function(el){
    var eid=el.getAttribute('data-eid');
    if(el.tagName==='IMG'){
      el.setAttribute('draggable','true');
      el.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();select(el);});
      el.addEventListener('dragstart',function(e){dragEid=eid;el.classList.add('ed-drag');try{e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',eid);}catch(_){}});
      el.addEventListener('dragend',function(){el.classList.remove('ed-drag');document.querySelectorAll('.ed-over').forEach(function(x){x.classList.remove('ed-over');});dragEid=null;});
      el.addEventListener('dragover',function(e){if(dragEid&&dragEid!==eid){e.preventDefault();e.dataTransfer.dropEffect='move';el.classList.add('ed-over');}});
      el.addEventListener('dragleave',function(){el.classList.remove('ed-over');});
      el.addEventListener('drop',function(e){e.preventDefault();el.classList.remove('ed-over');if(dragEid&&dragEid!==eid){post({t:'op',op:'swap-image',eid:dragEid,ref:eid});}dragEid=null;});
    } else {
      var isCardLink = el.tagName==='A' && el.children && el.children.length>0;
      if(!isCardLink){
        el.setAttribute('contenteditable','true');
        el.addEventListener('focus',function(){select(el);});
        el.addEventListener('blur',function(){ post({t:'text',eid:eid,value:el.innerHTML}); });
      }
      el.addEventListener('click',function(e){ if(el.tagName==='A'||el.tagName==='BUTTON'){e.preventDefault();} e.stopPropagation(); select(el); });
    }
  });
  document.addEventListener('scroll',function(){ if(sel && tb.style.display!=='none') place(sel); },true);
  document.body.addEventListener('click',function(e){
    if(!e.target.closest('[data-eid]') && !e.target.closest('#ed-tb')){
      tb.style.display='none'; if(sel){sel.classList.remove('ed-sel'); sel=null;}
    }
  });
});
</script>
"""

# Buyer-facing finance estimator, auto-injected by the CMS into ANY published/preview page
# that contains car cards ([data-block="car"]). Generic (works on .car/.price and .uc-car/.uc-price
# and any [class*=price]) and idempotent: skips cars that already show a finance pill from their
# own site JS. Runtime-only, never stored; hidden inside the editor canvas (top-level guard).
FINANCE_INJECT = """
<style>
.ivdfin-row{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:14px 0 4px;padding:11px 14px;background:rgba(127,127,127,.08);border:1px solid rgba(127,127,127,.22);border-radius:12px;font-family:inherit}
.ivdfin-from{font-size:.9rem;opacity:.82}
.ivdfin-from b{font-weight:700;font-size:1.08rem}
.ivdfin-btn{background:none;border:none;font-weight:600;font-size:.85rem;cursor:pointer;padding:4px 2px;font-family:inherit}
.ivdfin-ov{position:fixed;inset:0;background:rgba(8,9,11,.72);display:none;align-items:center;justify-content:center;z-index:2147482000;padding:20px}
.ivdfin-ov.on{display:flex}
.ivdfin-modal{background:#fff;color:#14181e;border-radius:16px;max-width:420px;width:100%;padding:28px;position:relative;box-shadow:0 30px 80px -30px rgba(0,0,0,.6);font-family:system-ui,-apple-system,Arial,sans-serif}
.ivdfin-close{position:absolute;top:12px;right:16px;background:none;border:none;font-size:1.8rem;line-height:1;color:#8a8f98;cursor:pointer}
.ivdfin-title{font-size:1.3rem;margin:0 0 4px;font-weight:700}
.ivdfin-car{font-weight:600;font-size:.9rem;margin:0 0 18px}
.ivdfin-line{display:flex;justify-content:space-between;font-size:.95rem;padding:8px 0;border-bottom:1px solid #eef0f3}
.ivdfin-line b{font-weight:700}
.ivdfin-ctl{display:block;font-size:.74rem;font-weight:600;letter-spacing:.03em;text-transform:uppercase;color:#616873;margin:16px 0 6px}
.ivdfin-ctl b{color:#14181e;text-transform:none;letter-spacing:0;font-size:.9rem}
.ivdfin-dep{width:100%;margin-top:8px}
.ivdfin-terms{display:flex;gap:8px;margin-top:8px}
.ivdfin-terms button{flex:1;padding:9px 0;border:1px solid #e6e8ec;background:#fff;border-radius:9px;font-weight:600;font-size:.9rem;color:#14181e;cursor:pointer;font-family:inherit}
.ivdfin-terms button.on{color:#fff}
.ivdfin-result{display:flex;justify-content:space-between;align-items:baseline;margin:22px 0 6px;padding:16px;background:#f6f7f9;border-radius:12px}
.ivdfin-result span{font-size:.76rem;text-transform:uppercase;letter-spacing:.06em;color:#616873}
.ivdfin-monthly{font-weight:700;font-size:1.5rem}
.ivdfin-note{font-size:.72rem;line-height:1.5;color:#8a8f98;margin:8px 0 16px}
.ivdfin-cta{display:block;width:100%;text-align:center;padding:13px;border:none;border-radius:10px;font-weight:700;font-size:.95rem;color:#fff;cursor:pointer;font-family:inherit}
</style>
<script>
(function(){
  if(window.self!==window.top) return;
  if(window.__ivdFinance) return; window.__ivdFinance=1;
  function ready(fn){ if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',fn); else fn(); }
  ready(function(){
    var cars=document.querySelectorAll('[data-block="car"]');
    if(!cars.length) return;
    function num(a,d){ var v=parseFloat(a); return isNaN(v)?d:v; }
    var APR=num(document.body.getAttribute('data-finance-apr'),12.9);
    var TERM=parseInt(document.body.getAttribute('data-finance-term'),10)||48;
    var DEP=num(document.body.getAttribute('data-finance-deposit-pct'),10);
    function fmt(n){ return '\\u00a3'+Math.round(n).toLocaleString('en-GB'); }
    function parsePrice(t){ var m=(t||'').replace(/[, ]/g,'').match(/(\\d{3,})/); return m?parseInt(m[1],10):0; }
    function pmt(pr,apr,mo){ var i=apr/100/12; if(i<=0) return pr/mo; return pr*i/(1-Math.pow(1+i,-mo)); }
    var ov=document.createElement('div'); ov.className='ivdfin-ov';
    ov.innerHTML='<div class="ivdfin-modal" role="dialog" aria-modal="true"><button class="ivdfin-close" type="button" aria-label="Close">&times;</button><h3 class="ivdfin-title">Finance estimate</h3><p class="ivdfin-car"></p><div class="ivdfin-line"><span>Cash price</span><b class="ivdfin-price"></b></div><label class="ivdfin-ctl">Deposit <b class="ivdfin-dep-val"></b><input class="ivdfin-dep" type="range" min="0" max="50" step="5"></label><div class="ivdfin-ctl"><span>Term (months)</span><span class="ivdfin-terms"><button type="button" data-t="24">24</button><button type="button" data-t="36">36</button><button type="button" data-t="48">48</button><button type="button" data-t="60">60</button></span></div><div class="ivdfin-result"><span>Estimated monthly</span><b class="ivdfin-monthly"></b></div><p class="ivdfin-note">Representative example at <b class="ivdfin-apr"></b>% APR. This is an illustration only, not a quote or an offer of finance. Subject to status &amp; affordability.</p><button class="ivdfin-cta" type="button">Ask us about finance</button></div>';
    document.body.appendChild(ov);
    var cur={price:0,dep:DEP,term:TERM,car:null,accent:'#b07f22'};
    var elPrice=ov.querySelector('.ivdfin-price'),elDepV=ov.querySelector('.ivdfin-dep-val'),elDep=ov.querySelector('.ivdfin-dep'),elMon=ov.querySelector('.ivdfin-monthly'),elCar=ov.querySelector('.ivdfin-car'),elApr=ov.querySelector('.ivdfin-apr'),cta=ov.querySelector('.ivdfin-cta');
    elApr.textContent=APR;
    function recalc(){
      var p=cur.price*(1-cur.dep/100);
      elPrice.textContent=fmt(cur.price);
      elDepV.textContent=cur.dep+'% ('+fmt(cur.price*cur.dep/100)+')';
      elMon.textContent=fmt(pmt(p,APR,cur.term))+'/mo'; elMon.style.color=cur.accent;
      elCar.style.color=cur.accent; cta.style.background=cur.accent;
      ov.querySelectorAll('.ivdfin-terms button').forEach(function(b){
        var on=parseInt(b.getAttribute('data-t'),10)===cur.term;
        b.classList.toggle('on',on); b.style.background=on?cur.accent:'#fff'; b.style.borderColor=on?cur.accent:'#e6e8ec';
      });
    }
    function open(car,price,accent){
      cur.price=price;cur.dep=DEP;cur.term=TERM;cur.car=car;cur.accent=accent||'#b07f22';
      var h=car.querySelector('h3,h2,.car-head h3,.uc-car-head h3');
      elCar.textContent=h?h.textContent.trim():'';
      elDep.value=DEP; recalc(); ov.classList.add('on');
    }
    function close(){ ov.classList.remove('on'); }
    ov.addEventListener('click',function(e){ if(e.target===ov) close(); });
    ov.querySelector('.ivdfin-close').addEventListener('click',close);
    elDep.addEventListener('input',function(){ cur.dep=parseInt(elDep.value,10); recalc(); });
    ov.querySelectorAll('.ivdfin-terms button').forEach(function(b){ b.addEventListener('click',function(){ cur.term=parseInt(b.getAttribute('data-t'),10); recalc(); }); });
    cta.addEventListener('click',function(){ close(); var eb=cur.car&&cur.car.querySelector('.enquire-btn,.uc-enquire-btn'); if(eb){ eb.click(); } });
    cars.forEach(function(car){
      if(car.querySelector('.finance,.uc-finance,.ivdfin-row')) return;
      var priceEl=car.querySelector('.price,.uc-price,[class*="price"]');
      if(!priceEl) return;
      var price=parsePrice(priceEl.textContent);
      if(!price||price<500) return;
      var accent=getComputedStyle(priceEl).color||'#b07f22';
      var monthly=pmt(price*(1-DEP/100),APR,TERM);
      var row=document.createElement('div'); row.className='ivdfin-row';
      row.innerHTML='<span class="ivdfin-from">From <b>'+fmt(monthly)+'</b>/mo</span><button type="button" class="ivdfin-btn">Finance example \\u203A</button>';
      row.querySelector('.ivdfin-from b').style.color=accent;
      row.querySelector('.ivdfin-btn').style.color=accent;
      var head=priceEl.closest('.car-head,.uc-car-head')||priceEl.parentElement;
      head.insertAdjacentElement('afterend',row);
      row.querySelector('.ivdfin-btn').addEventListener('click',function(){ open(car,price,accent); });
    });
  });
})();
</script>
"""


# ---------------- auth routes ----------------
@api.post("/auth/login")
async def login(body: Login, response: Response):
    email = body.email.lower()
    att = await db.login_attempts.find_one({"email": email})
    now = datetime.now(timezone.utc)
    if att and att.get("fails", 0) >= 5:
        locked_until = att.get("locked_until")
        if locked_until and now < datetime.fromisoformat(locked_until):
            raise HTTPException(429, "Too many attempts. Try again in a few minutes.")
    u = await db.users.find_one({"email": email})
    if not u or not verify_pw(body.password, u["password_hash"]):
        fails = (att.get("fails", 0) if att else 0) + 1
        upd = {"fails": fails, "last": now.isoformat()}
        if fails >= 5:
            upd["locked_until"] = (now + timedelta(minutes=15)).isoformat()
        await db.login_attempts.update_one({"email": email}, {"$set": upd}, upsert=True)
        raise HTTPException(401, "Invalid email or password")
    await db.login_attempts.delete_one({"email": email})
    tok = make_token(str(u["_id"]), u["email"], u.get("role","editor"))
    response.set_cookie("access_token", tok, httponly=True, secure=COOKIE_SECURE, samesite="lax", max_age=604800, path="/")
    return {"id":str(u["_id"]),"email":u["email"],"name":u.get("name",""),"role":u.get("role"),"site_id":u.get("site_id")}

@api.post("/auth/logout")
async def logout(response: Response, u=Depends(current_user)):
    response.delete_cookie("access_token", path="/")
    return {"ok":True}

@api.get("/auth/me")
async def me(u=Depends(current_user)): return u

@api.get("/users")
async def list_users(u=Depends(require_admin)):
    out=[]
    async for x in db.users.find({}):
        out.append({"id":str(x["_id"]),"email":x["email"],"name":x.get("name",""),"role":x.get("role"),"site_id":x.get("site_id")})
    return out

@api.post("/users")
async def create_user(body: NewUser, u=Depends(require_admin)):
    if await db.users.find_one({"email":body.email.lower()}):
        raise HTTPException(400,"Email already exists")
    doc={"email":body.email.lower(),"password_hash":hash_pw(body.password),"name":body.name,
         "role":body.role,"site_id":body.site_id,"created_at":datetime.now(timezone.utc).isoformat()}
    r=await db.users.insert_one(doc)
    return {"id":str(r.inserted_id),"email":doc["email"],"role":doc["role"]}

# ---------------- site/page routes ----------------
@api.get("/sites")
async def sites(u=Depends(current_user)):
    out=[]
    async for s in db.sites.find({}):
        out.append({"slug":s["slug"],"name":s.get("name"),"order":s.get("order",[]),"clean_urls":bool(s.get("clean_urls",False))})
    return out

@api.post("/sites/{slug}/ingest")
async def do_ingest(slug: str, force: bool = False, u=Depends(require_admin)):
    res = await ingest_site(slug, force=force)
    if res["total"]==0: raise HTTPException(404,f"No pages found in {SITES_DIR}/{slug}")
    return {"ingested":res["total"], "added":res["added"], "preserved":res["preserved"], "force":force}

@api.get("/sites/{slug}/pages")
async def site_pages(slug: str, u=Depends(current_user)):
    s = await db.sites.find_one({"slug":slug})
    if not s: raise HTTPException(404,"Site not found")
    return s.get("order",[])

class PagesOrder(BaseModel):
    order: list[str]

@api.post("/sites/{slug}/pages/reorder")
async def reorder_pages(slug: str, body: PagesOrder, u=Depends(current_user)):
    s = await db.sites.find_one({"slug":slug})
    if not s: raise HTTPException(404,"Site not found")
    cur = s.get("order",[])
    bykey = {o["slug"]: o for o in cur}
    new=[]; seen=set()
    for sl in body.order:
        if sl in bykey and sl not in seen:
            new.append(bykey[sl]); seen.add(sl)
    for o in cur:
        if o["slug"] not in seen:
            new.append(o); seen.add(o["slug"])
    await db.sites.update_one({"slug":slug},{"$set":{"order":new}})
    return {"ok":True, "count":len(new)}

@api.get("/pages/{slug_site}/{slug}")
async def get_page(slug_site: str, slug: str, u=Depends(current_user)):
    p = await db.pages.find_one({"site":slug_site,"slug":slug})
    if not p: raise HTTPException(404,"Page not found")
    return {"site":slug_site,"slug":slug,"title":p["title"],"seo":p.get("seo",{}),
            "regions":p.get("regions",{})}

@api.put("/pages/{slug_site}/{slug}/region")
async def update_region(slug_site: str, slug: str, body: RegionUpdate, u=Depends(current_user)):
    if not scope_ok(u, slug_site): raise HTTPException(403,"Not allowed to edit this site")
    p = await db.pages.find_one({"site":slug_site,"slug":slug})
    if not p: raise HTTPException(404,"Page not found")
    if body.eid not in p.get("regions",{}): raise HTTPException(400,"Unknown region")
    await maybe_auto_snapshot(slug_site)
    await push_undo(slug_site, slug)
    await db.pages.update_one({"_id":p["_id"]},{"$set":{f"regions.{body.eid}.value":body.value}})
    return {"ok":True}

@api.put("/pages/{slug_site}/{slug}/link")
async def update_link(slug_site: str, slug: str, body: LinkUpdate, u=Depends(current_user)):
    if not scope_ok(u, slug_site): raise HTTPException(403,"Not allowed to edit this site")
    p = await db.pages.find_one({"site":slug_site,"slug":slug})
    if not p: raise HTTPException(404,"Page not found")
    r = p.get("regions",{}).get(body.eid)
    if not r: raise HTTPException(400,"Unknown region")
    el = BeautifulSoup(p["template"], "lxml").find(attrs={"data-eid":body.eid})
    if not el or el.name not in ("a","button") or r.get("type") not in ("text","link"):
        raise HTTPException(400,"That element isn't a link or button")
    await maybe_auto_snapshot(slug_site)
    await push_undo(slug_site, slug)
    update = {f"regions.{body.eid}.href":body.href}
    if r.get("type") == "text":
        update[f"regions.{body.eid}.link"] = True
    await db.pages.update_one({"_id":p["_id"]},{"$set":update})
    return {"ok":True}

@api.put("/pages/{slug_site}/{slug}/alt")
async def update_alt(slug_site: str, slug: str, body: AltUpdate, u=Depends(current_user)):
    if not scope_ok(u, slug_site): raise HTTPException(403,"Not allowed to edit this site")
    p = await db.pages.find_one({"site":slug_site,"slug":slug})
    if not p: raise HTTPException(404,"Page not found")
    r = p.get("regions",{}).get(body.eid)
    if not r or r.get("type") != "image": raise HTTPException(400,"That element isn't an image")
    await maybe_auto_snapshot(slug_site)
    await push_undo(slug_site, slug)
    await db.pages.update_one({"_id":p["_id"]},{"$set":{f"regions.{body.eid}.alt":body.alt}})
    return {"ok":True}

@api.post("/pages/{slug_site}/{slug}/suggest-alt")
async def suggest_alt(slug_site: str, slug: str, body: AltSuggest, u=Depends(current_user)):
    if not scope_ok(u, slug_site): raise HTTPException(403,"Not allowed to edit this site")
    if not EMERGENT_LLM_KEY:
        return {"ok":False,"message":"AI suggestions aren't set up on this server yet."}
    p = await db.pages.find_one({"site":slug_site,"slug":slug})
    if not p: raise HTTPException(404,"Page not found")
    r = p.get("regions",{}).get(body.eid)
    if not r or r.get("type") != "image": raise HTTPException(400,"That element isn't an image")
    try:
        img, mime = await asyncio.to_thread(_load_image_bytes, slug_site, r.get("value",""))
        alt = await asyncio.to_thread(_suggest_alt_gemini, img, mime)
        if not alt: return {"ok":False,"message":"The AI couldn't describe that image — try typing it in."}
        return {"ok":True,"alt":alt}
    except Exception as e:
        logging.getLogger("uvicorn.error").warning(f"[suggest-alt] {slug_site}/{slug} {body.eid}: {e}")
        return {"ok":False,"message":f"Couldn't suggest alt text: {e}"}

@api.put("/pages/{slug_site}/{slug}/caption")
async def update_caption(slug_site: str, slug: str, body: CaptionUpdate, u=Depends(current_user)):
    if not scope_ok(u, slug_site): raise HTTPException(403,"Not allowed to edit this site")
    p = await db.pages.find_one({"site":slug_site,"slug":slug})
    if not p: raise HTTPException(404,"Page not found")
    r = p.get("regions",{}).get(body.eid)
    if not r or r.get("type") != "image": raise HTTPException(400,"That element isn't an image")
    soup = BeautifulSoup(p["template"], "lxml")
    bodyel = soup.body or soup
    el = bodyel.find(attrs={"data-eid":body.eid})
    if not el or el.name != "img": raise HTTPException(400,"That element isn't an image")
    await maybe_auto_snapshot(slug_site)
    await push_undo(slug_site, slug)
    cap = body.caption.strip()
    if cap: el["data-caption"] = cap
    elif el.has_attr("data-caption"): del el["data-caption"]
    await db.pages.update_one({"_id":p["_id"]},{"$set":{"template":str(bodyel)}})
    return {"ok":True,"caption":cap}

@api.post("/pages/{slug_site}/{slug}/fill-alt")
async def fill_alt(slug_site: str, slug: str, u=Depends(current_user)):
    if not scope_ok(u, slug_site): raise HTTPException(403,"Not allowed to edit this site")
    if not EMERGENT_LLM_KEY:
        return {"ok":False,"message":"AI suggestions aren't set up on this server yet."}
    p = await db.pages.find_one({"site":slug_site,"slug":slug})
    if not p: raise HTTPException(404,"Page not found")
    targets = [eid for eid, r in p.get("regions",{}).items()
               if r.get("type") == "image" and not (r.get("alt") or "").strip()]
    if not targets:
        return {"ok":True,"job_id":None,"total":0,"message":"Every image already has a description. 🎉"}
    await maybe_auto_snapshot(slug_site)
    await push_undo(slug_site, slug)
    job_id = uuid.uuid4().hex
    await db.alt_jobs.insert_one({"_id":job_id,"site":slug_site,"slug":slug,"state":"running",
        "done":0,"filled":0,"total":len(targets),"created":datetime.now(timezone.utc)})
    task = asyncio.create_task(_run_fill_alt(job_id, slug_site, slug, targets))
    _bg_tasks.add(task); task.add_done_callback(_bg_tasks.discard)
    return {"ok":True,"job_id":job_id,"total":len(targets)}

async def _run_fill_alt(job_id, site, slug, targets):
    log = logging.getLogger("uvicorn.error")
    done = filled = 0
    for eid in targets:
        p = await db.pages.find_one({"site":site,"slug":slug})
        r = (p or {}).get("regions",{}).get(eid)
        if r and r.get("type") == "image":
            try:
                img, mime = await asyncio.to_thread(_load_image_bytes, site, r.get("value",""))
                alt = await asyncio.to_thread(_suggest_alt_gemini, img, mime)
                if alt:
                    await db.pages.update_one({"site":site,"slug":slug},{"$set":{f"regions.{eid}.alt":alt}})
                    filled += 1
            except Exception as e:
                log.warning(f"[fill-alt] {site}/{slug} {eid}: {e}")
        done += 1
        await db.alt_jobs.update_one({"_id":job_id},{"$set":{"done":done,"filled":filled}})
    await db.alt_jobs.update_one({"_id":job_id},{"$set":{"state":"done","filled":filled}})

@api.get("/pages/{slug_site}/{slug}/fill-alt-status/{job_id}")
async def fill_alt_status(slug_site: str, slug: str, job_id: str, u=Depends(current_user)):
    j = await db.alt_jobs.find_one({"_id":job_id})
    if not j: raise HTTPException(404,"Job not found")
    return {"state":j.get("state"),"done":j.get("done",0),"total":j.get("total",0),"filled":j.get("filled",0)}

@api.post("/pages/{slug_site}/{slug}/op")
async def page_op(slug_site: str, slug: str, body: PageOp, u=Depends(current_user)):
    if not scope_ok(u, slug_site): raise HTTPException(403,"Not allowed to edit this site")
    p = await db.pages.find_one({"site":slug_site,"slug":slug})
    if not p: raise HTTPException(404,"Page not found")
    if body.op not in ("duplicate","delete","add-image","add-button","add-el","move-up","move-down","swap-image","duplicate-block","delete-block","add-blank-block","add-blank-car","move-block-up","move-block-down","status-sold","status-reserved","status-new","status-clear","set-logo"):
        raise HTTPException(400,"Unknown operation")
    if body.op == "swap-image":
        r1 = p.get("regions",{}).get(body.eid); r2 = p.get("regions",{}).get(body.ref or "")
        if not r1 or not r2 or r1.get("type") != "image" or r2.get("type") != "image":
            raise HTTPException(400,"Can only reorder images")
        await maybe_auto_snapshot(slug_site)
        await push_undo(slug_site, slug)
        await db.pages.update_one({"_id":p["_id"]},{"$set":{
            f"regions.{body.eid}.value": r2.get("value",""), f"regions.{body.eid}.alt": r2.get("alt",""),
            f"regions.{body.ref}.value": r1.get("value",""), f"regions.{body.ref}.alt": r1.get("alt","")}})
        return {"ok":True}
    await maybe_auto_snapshot(slug_site)
    await push_undo(slug_site, slug)
    soup = BeautifulSoup(p["template"], "lxml")
    bodyel = soup.body or soup
    # bake current region values into the template so clones carry live content
    for eid, r in p.get("regions",{}).items():
        el = bodyel.find(attrs={"data-eid":eid})
        if not el: continue
        if r["type"]=="text":
            _set_html(el, r["value"])
            if r.get("href") is not None and el.name in ("a","button"):
                el["href"] = r["href"]
        elif r["type"]=="image":
            _apply_image(el, r["value"], r.get("alt"))
    target = bodyel.find(attrs={"data-eid":body.eid})
    if not target: raise HTTPException(400,"Element not found")
    if body.op in ("duplicate","add-image"):
        import copy as _c
        target.insert_after(_c.copy(target))
    elif body.op=="delete":
        target.decompose()
    elif body.op=="add-button":
        ref = bodyel.find(lambda t: t.name in ("a","button") and t.get("class") and any("btn" in c.lower() for c in t.get("class")))
        new = soup.new_tag("a", href="#")
        if ref and ref.get("class"): new["class"] = ref.get("class")
        else: new["class"] = ["btn"]
        new.string = "New button"
        target.insert_after(new)
    elif body.op=="add-el":
        kind = (body.kind or "paragraph").lower()
        block = target.find_parent(attrs={"data-block": True})
        anchor = block if block is not None else target
        placed = False
        if kind == "heading":
            new = soup.new_tag("h2"); new.string = "New heading"
        elif kind == "button":
            ref = bodyel.find(lambda t: t.name in ("a","button") and t.get("class") and any("btn" in c.lower() for c in t.get("class")))
            new = soup.new_tag("a", href="#")
            new["class"] = ref.get("class") if (ref and ref.get("class")) else ["btn"]
            new.string = "New button"
        elif kind == "image":
            new = soup.new_tag("img"); new["src"] = BLANK_IMG; new["alt"] = ""
        elif kind == "listitem":
            new = soup.new_tag("li"); new.string = "New feature"
            li = target if target.name == "li" else target.find_parent("li")
            if li is not None:
                if li.get("class"): new["class"] = li.get("class")
                li.insert_after(new); placed = True
            else:
                ul = target if target.name in ("ul","ol") else target.find_parent(["ul","ol"])
                if ul is not None: ul.append(new); placed = True
        else:
            new = soup.new_tag("p"); new.string = "New paragraph — click to edit."
        if not placed:
            anchor.insert_after(new)
    elif body.op=="move-up":
        prev = target.find_previous_sibling()
        if prev: prev.insert_before(target.extract())
    elif body.op=="move-down":
        nxt = target.find_next_sibling()
        if nxt: nxt.insert_after(target.extract())
    elif body.op in ("duplicate-block","delete-block"):
        block = target.find_parent(attrs={"data-block": True})
        if not block:
            raise HTTPException(400,"This element isn't inside a duplicatable block (add data-block to its container).")
        if body.op=="duplicate-block":
            import copy as _c
            block.insert_after(_c.copy(block))
        else:
            block.decompose()
    elif body.op == "add-blank-block":
        block = target.find_parent(attrs={"data-block": True})
        if not block:
            raise HTTPException(400,"This element isn't inside a card.")
        import copy as _c
        clone = _c.copy(block)
        if clone.has_attr("data-status"): clone["data-status"] = ""
        # collapse each image gallery to a single placeholder slide
        seen = set()
        for img in list(clone.find_all("img")):
            pid = id(img.parent)
            if pid in seen: img.decompose()
            else: seen.add(pid)
        # neutral placeholder images
        for img in clone.find_all("img"):
            img["src"] = BLANK_IMG
            for a in ("srcset","sizes","data-src","data-srcset","data-lazy-src","loading"):
                if img.has_attr(a): del img[a]
            img["alt"] = ""
        # blank the editable text (keep a short placeholder so it stays clickable;
        # leave <a>/<button> CTA labels intact)
        for el in clone.find_all(list(EDIT_TAGS)):
            if el.find(list(EDIT_TAGS)): continue
            if not el.get_text(strip=True): continue
            if el.name in ("a","button"): continue
            el.clear(); el.append("Edit")
        block.insert_after(clone)
    elif body.op == "add-blank-car":
        block = target.find_parent(attrs={"data-block": True})
        if not block:
            raise HTTPException(400,"This element isn't inside a car card.")
        import copy as _c
        clone = _c.copy(block)
        if clone.has_attr("data-status"): clone["data-status"] = ""
        # collapse each gallery/slider down to a single Coming-Soon slide
        seen = set()
        for img in list(clone.find_all("img")):
            pid = id(img.parent)
            if pid in seen: img.decompose()
            else: seen.add(pid)
        for img in clone.find_all("img"):
            img["src"] = COMING_SOON_IMG
            for a in ("srcset","sizes","data-src","data-srcset","data-lazy-src","loading"):
                if img.has_attr(a): del img[a]
            img["alt"] = ""
        def _reset(el, txt):
            el.clear(); el.append(txt)
        title = clone.select_one(".uc-car-head h3") or clone.select_one("h3") or clone.select_one("h2")
        if title is not None: _reset(title, "Make & Model")
        price = clone.select_one(".uc-price")
        if price is None:
            for el in clone.find_all(True):
                if "price" in " ".join(el.get("class") or []).lower(): price = el; break
        if price is not None: _reset(price, "\u00a30000")
        strap = clone.select_one(".uc-strap")
        if strap is not None: _reset(strap, "Add a short description of this car here.")
        for sp in clone.select(".uc-spec b"):
            _reset(sp, "\u2013")
        for li in clone.select(".uc-features li"):
            _reset(li, "spec")
        # fallback for non-uc car markup: blank the editable text generically
        if not clone.select(".uc-car-head, .uc-price, .uc-specs, .uc-features"):
            for el in clone.find_all(list(EDIT_TAGS)):
                if el.find(list(EDIT_TAGS)): continue
                if not el.get_text(strip=True): continue
                if el.name in ("a","button"): continue
                el.clear(); el.append("Edit")
        block.insert_after(clone)
    elif body.op in ("move-block-up","move-block-down"):
        block = target.find_parent(attrs={"data-block": True})
        if not block:
            raise HTTPException(400,"This element isn't inside a movable card.")
        if body.op=="move-block-up":
            sib = block.find_previous_sibling()
            if sib: sib.insert_before(block.extract())
        else:
            sib = block.find_next_sibling()
            if sib: sib.insert_after(block.extract())
    elif body.op in ("status-sold","status-reserved","status-new","status-clear"):
        block = target.find_parent(attrs={"data-block": True})
        if not block:
            raise HTTPException(400,"This element isn't inside a card.")
        st = {"status-sold":"sold","status-reserved":"reserved","status-new":"new"}.get(body.op)
        if st: block["data-status"] = st
        elif block.has_attr("data-status"): del block["data-status"]
    elif body.op == "set-logo":
        if not body.url: raise HTTPException(400,"No logo image was provided")
        new = soup.new_tag("img"); new["src"] = body.url; new["alt"] = "Logo"
        svg = target if target.name == "svg" else target.find("svg")
        if svg is not None:
            svgcls = svg.get("class")
            if svgcls: new["class"] = svgcls
            new["style"] = "height:auto;max-height:56px;width:auto;display:block;object-fit:contain"
            svg.replace_with(new)
        else:
            img = target if target.name == "img" else target.find("img")
            if img is not None:
                _apply_image(img, body.url, "Logo")
            else:
                new["style"] = "height:auto;max-height:56px;width:auto;display:block;object-fit:contain"
                target.append(new)
    regions = assign_regions(bodyel)
    await db.pages.update_one({"_id":p["_id"]},{"$set":{"template":str(bodyel),"regions":regions}})
    return {"ok":True}

@api.post("/pages/{slug_site}/{slug}/bulk-image")
async def bulk_image(slug_site: str, slug: str, body: BulkImage, u=Depends(current_user)):
    if not scope_ok(u, slug_site): raise HTTPException(403,"Not allowed to edit this site")
    p = await db.pages.find_one({"site":slug_site,"slug":slug})
    if not p: raise HTTPException(404,"Page not found")
    if body.eid not in p.get("regions",{}): raise HTTPException(400,"Unknown region")
    urls = [u for u in (body.urls or []) if u]
    if not urls: raise HTTPException(400,"No images to add")
    await maybe_auto_snapshot(slug_site)
    await push_undo(slug_site, slug)
    soup = BeautifulSoup(p["template"], "lxml")
    bodyel = soup.body or soup
    for eid, r in p.get("regions",{}).items():
        el = bodyel.find(attrs={"data-eid":eid})
        if not el: continue
        if r["type"]=="text":
            _set_html(el, r["value"])
            if r.get("href") is not None and el.name in ("a","button"):
                el["href"] = r["href"]
        elif r["type"]=="image":
            _apply_image(el, r["value"], r.get("alt"))
    target = bodyel.find(attrs={"data-eid":body.eid})
    if not target or target.name != "img": raise HTTPException(400,"Select an image first")
    import copy as _c
    anchor = target
    for url in urls:
        clone = _c.copy(target)
        _apply_image(clone, url)
        anchor.insert_after(clone)
        anchor = clone
    regions = assign_regions(bodyel)
    await db.pages.update_one({"_id":p["_id"]},{"$set":{"template":str(bodyel),"regions":regions}})
    return {"ok":True,"added":len(urls)}

@api.put("/pages/{slug_site}/{slug}/seo")
async def update_seo(slug_site: str, slug: str, body: SeoUpdate, u=Depends(current_user)):
    if not scope_ok(u, slug_site): raise HTTPException(403,"Not allowed to edit this site")
    await maybe_auto_snapshot(slug_site)
    await push_undo(slug_site, slug)
    await db.pages.update_one({"site":slug_site,"slug":slug},{"$set":{"seo":body.seo}})
    return {"ok":True}

@api.get("/sites/{slug}/snapshots")
async def list_snapshots(slug: str, u=Depends(current_user)):
    if not scope_ok(u, slug): raise HTTPException(403,"Not allowed for this site")
    out = []
    async for d in db.snapshots.find({"site":slug}).sort("created",-1).limit(200):
        c = d.get("created")
        out.append({"id": d["_id"], "kind": d.get("kind"), "label": d.get("label"),
                    "created": c.isoformat() if hasattr(c,"isoformat") else c,
                    "pages": d.get("page_count", len(d.get("pages",[])))})
    return out

@api.post("/sites/{slug}/snapshots")
async def make_snapshot(slug: str, body: dict | None = None, u=Depends(current_user)):
    if not scope_ok(u, slug): raise HTTPException(403,"Not allowed for this site")
    sid = await create_snapshot(slug, "manual", ((body or {}).get("label") or "Manual restore point"))
    if not sid: raise HTTPException(400,"Nothing to snapshot yet")
    return {"ok":True,"id":sid}

@api.post("/sites/{slug}/snapshots/{sid}/restore")
async def restore_snapshot(slug: str, sid: str, u=Depends(current_user)):
    if not scope_ok(u, slug): raise HTTPException(403,"Not allowed for this site")
    snap = await db.snapshots.find_one({"_id":sid,"site":slug})
    if not snap: raise HTTPException(404,"Restore point not found")
    # snapshot the current state first so the restore itself is undoable
    await create_snapshot(slug, "auto", "Before restore")
    await db.pages.delete_many({"site":slug})
    for p in snap.get("pages",[]):
        doc = dict(p); doc.pop("_id",None); doc["site"] = slug
        await db.pages.insert_one(doc)
    await db.sites.update_one({"slug":slug},{"$set":{"order":snap.get("order",[])}})
    return {"ok":True,"label":snap.get("label"),"pages":len(snap.get("pages",[]))}

@api.post("/sites/{slug}/session-snapshot")
async def session_snapshot(slug: str, u=Depends(current_user)):
    if not scope_ok(u, slug): raise HTTPException(403,"Not allowed for this site")
    sid = await create_snapshot(slug, "session", "Session start (auto)")
    return {"ok": bool(sid), "id": sid}

@api.get("/sites/{slug}/undo-status")
async def undo_status(slug: str, u=Depends(current_user)):
    if not scope_ok(u, slug): raise HTTPException(403,"Not allowed for this site")
    n = await db.edit_history.count_documents({"site":slug})
    return {"can_undo": n > 0, "count": n}

@api.post("/sites/{slug}/undo")
async def undo(slug: str, u=Depends(current_user)):
    if not scope_ok(u, slug): raise HTTPException(403,"Not allowed for this site")
    h = await db.edit_history.find_one({"site":slug}, sort=[("created",-1)])
    if not h: return {"ok": False, "message": "Nothing to undo yet."}
    doc = dict(h["page"]); doc.pop("_id", None); doc["site"] = slug
    await db.pages.replace_one({"site":slug,"slug":doc["slug"]}, doc)
    await db.edit_history.delete_one({"_id": h["_id"]})
    remaining = await db.edit_history.count_documents({"site":slug})
    return {"ok": True, "slug": doc["slug"], "can_undo": remaining > 0, "message": "Undid your last change."}

@api.get("/branding")
async def public_branding(host: str = ""):
    label = host.split(":")[0].split(".")[0].lower().strip() if host else ""
    s = None
    if label:
        s = await db.sites.find_one({"$or":[{"subdomain":label},{"slug":label}]})
    if not s or not (s.get("branding") or {}).get("brand_name") and not (s.get("branding") or {}).get("logo_url"):
        return {"name":"Ivory Digital","logo":"","custom":False}
    b = s.get("branding") or {}
    logo = b.get("logo_url","")
    return {"name": b.get("brand_name") or s.get("name") or s.get("slug"),
            "logo": f"/api/asset/{s['slug']}/{logo}" if logo else "",
            "custom": True}

@api.get("/sites/{slug}/branding")
async def get_branding(slug: str, u=Depends(require_admin)):
    s = await db.sites.find_one({"slug":slug})
    if not s: raise HTTPException(404,"Site not found")
    b = s.get("branding") or {}
    return {"brand_name": b.get("brand_name",""), "logo_url": b.get("logo_url",""),
            "subdomain": s.get("subdomain",""),
            "accent": b.get("accent",""), "accent_dark": b.get("accent_dark",""),
            "on_accent": b.get("on_accent",""), "heading_font": b.get("heading_font",""),
            "body_font": b.get("body_font",""), "font_link": b.get("font_link","")}

@api.put("/sites/{slug}/branding")
async def set_branding(slug: str, body: Branding, u=Depends(require_admin)):
    s = await db.sites.find_one({"slug":slug})
    if not s: raise HTTPException(404,"Site not found")
    sub = re.sub(r'[^a-z0-9-]', '', body.subdomain.lower())
    prev = s.get("branding") or {}
    await db.sites.update_one({"slug":slug},{"$set":{
        "branding": {"brand_name": body.brand_name.strip(), "logo_url": body.logo_url.strip(),
                     "accent": body.accent.strip(), "accent_dark": body.accent_dark.strip(),
                     "on_accent": body.on_accent.strip(), "heading_font": body.heading_font.strip(),
                     "body_font": body.body_font.strip(), "font_link": body.font_link.strip()},
        "subdomain": sub}})
    return {"ok":True}

@api.delete("/sites/{slug}")
async def remove_site(slug: str, u=Depends(require_super)):
    s = await db.sites.find_one({"slug":slug})
    if not s: raise HTTPException(404,"Site not found")
    await db.pages.delete_many({"site":slug})
    await db.snapshots.delete_many({"site":slug})
    await db.edit_history.delete_many({"site":slug})
    await db.add_jobs.delete_many({"slug":slug})
    await db.sites.delete_one({"slug":slug})
    await db.users.update_many({"site_id":slug},{"$set":{"site_id":None}})
    for d in (os.path.join(SITES_DIR, slug), os.path.join(MEDIA_DIR, slug), os.path.join(DIST_DIR, slug)):
        shutil.rmtree(d, ignore_errors=True)
    return {"ok":True,"message":f"Removed '{slug}' from the editor. Your live site was not touched."}

# editor iframe html
@api.get("/editor/page/{slug_site}/{slug}", response_class=HTMLResponse)
async def editor_page(slug_site: str, slug: str, u=Depends(current_user)):
    p = await db.pages.find_one({"site":slug_site,"slug":slug})
    if not p: raise HTTPException(404,"Page not found")
    # base points at the page's OWN folder so its relative assets resolve (e.g. car-sales/assets/..)
    rel = (p.get("relpath") or "").replace("\\","/")
    folder = rel.rsplit("/",1)[0] if "/" in rel else ""
    base = f"/api/asset/{slug_site}/{folder}/" if folder else f"/api/asset/{slug_site}/"
    return render_page(p, for_editor=True, asset_base=base)

# serve site assets + uploaded media
@api.get("/asset/{slug_site}/{path:path}")
async def asset(slug_site: str, path: str):
    # uploaded media first
    mp = os.path.join(MEDIA_DIR, slug_site, path.replace("assets/uploads/",""))
    if path.startswith("assets/uploads/") and os.path.isfile(mp):
        return FileResponse(mp)
    fp = os.path.join(SITES_DIR, slug_site, path)
    if os.path.isfile(fp): return FileResponse(fp)
    raise HTTPException(404,"Asset not found")

DOWNLOADS_DIR = os.environ.get("DOWNLOADS_DIR", "/app/frontend/public/downloads")

@api.get("/download/{name}")
async def download_zip(name: str):
    safe = os.path.basename(name)
    fp = os.path.join(DOWNLOADS_DIR, safe)
    if not os.path.isfile(fp):
        raise HTTPException(404, "File not found")
    return FileResponse(fp, media_type="application/zip", filename=safe)


@api.post("/media/{slug_site}/upload")
async def upload_media(slug_site: str, file: UploadFile = File(...), u=Depends(current_user)):
    d = os.path.join(MEDIA_DIR, slug_site); os.makedirs(d, exist_ok=True)
    raw = await file.read()
    data, ext = optimize_image(raw, file.filename or "upload")
    base = re.sub(r'[^a-zA-Z0-9_-]', '_', os.path.splitext(file.filename or "image")[0])[:60] or "image"
    name = f"{int(datetime.now().timestamp())}_{base}.{ext}"
    with open(os.path.join(d, name), "wb") as f: f.write(data)
    return {"url": f"assets/uploads/{name}", "bytes": len(data), "original_bytes": len(raw)}

MAX_IMG_DIM = 2000  # longest side; keeps heroes crisp, tames giant phone photos

def optimize_image(raw: bytes, filename: str):
    """Compress uploads to lightweight, high-quality WebP. Free, no AI.
    Keeps transparency, auto-rotates by EXIF, caps the longest side.
    Falls back to the original bytes for SVG/animated GIF or anything Pillow can't read."""
    ext = (os.path.splitext(filename)[1] or "").lower().lstrip(".")
    if ext == "svg":
        return raw, "svg"
    try:
        im = Image.open(_io.BytesIO(raw))
        if getattr(im, "is_animated", False):
            return raw, (ext or "gif")  # don't flatten animations
        im = ImageOps.exif_transpose(im)  # honour phone orientation
        has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
        im = im.convert("RGBA" if has_alpha else "RGB")
        w, h = im.size
        if max(w, h) > MAX_IMG_DIM:
            im.thumbnail((MAX_IMG_DIM, MAX_IMG_DIM), Image.LANCZOS)
        out = _io.BytesIO()
        im.save(out, format="WEBP", quality=82, method=6)
        data = out.getvalue()
        if len(data) < len(raw) or ext not in ("webp",):
            return data, "webp"
        return raw, ext or "webp"
    except Exception:
        return raw, ext or "bin"



# ---------------- publish ----------------
def _page_relpath(p):
    return (p.get("relpath") or ("index.html" if p["slug"]=="home" else f"{p['slug']}.html")).replace("\\","/").lstrip("/")

def _clean_path(rel):
    """Map a page's on-disk relpath to its clean public URL path."""
    rel = rel.replace("\\","/").lstrip("/")
    if rel == "index.html": return "/"
    if rel.endswith("/index.html"): return "/" + rel[:-len("index.html")]  # dir/
    if rel.endswith(".html"): return "/" + rel[:-5]
    return "/" + rel

_CLEAN_HTACCESS_BEGIN = "# BEGIN CMS clean-urls (managed - do not edit)"
_CLEAN_HTACCESS_END = "# END CMS clean-urls"

def _write_clean_htaccess(out):
    block = _CLEAN_HTACCESS_BEGIN + "\n" + r"""DirectoryIndex index.html
<IfModule mod_rewrite.c>
  RewriteEngine On
  # Redirect a directly-typed /index.html to the clean root
  RewriteCond %{THE_REQUEST} \s/index\.html[\s?] [NC]
  RewriteRule ^index\.html$ / [R=301,L]
  # Redirect any directly-typed /page.html to the clean /page
  RewriteCond %{THE_REQUEST} \s/([^\s?]+)\.html[\s?] [NC]
  RewriteRule ^ /%1 [R=301,L]
  # Internally serve the real .html file for a clean URL (no redirect, no loop)
  RewriteCond %{REQUEST_FILENAME} !-f
  RewriteCond %{REQUEST_FILENAME} !-d
  RewriteCond %{DOCUMENT_ROOT}/$1.html -f
  RewriteRule ^(.+?)/?$ /$1.html [L]
</IfModule>
""" + _CLEAN_HTACCESS_END + "\n"
    path = os.path.join(out, ".htaccess")
    existing = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    if _CLEAN_HTACCESS_BEGIN in existing and _CLEAN_HTACCESS_END in existing:
        pre = existing.split(_CLEAN_HTACCESS_BEGIN)[0]
        post = existing.split(_CLEAN_HTACCESS_END, 1)[1]
        existing = (pre + post)
    existing = existing.strip("\n")
    open(path, "w", encoding="utf-8").write(block + (("\n" + existing + "\n") if existing else ""))

def _apply_clean_urls(out, pages, domain):
    """Post-process a built dist so it uses clean (extensionless) URLs. Opt-in only."""
    import re
    rels = {_page_relpath(p): _clean_path(_page_relpath(p)) for p in pages}
    href_re = re.compile(r'href="(?:\./)?([A-Za-z0-9_\-./]+?)\.html(#[^"]*)?"')
    def _rewrite(m):
        g1, frag = m.group(1), (m.group(2) or "")
        cp = rels.get(g1 + ".html")
        if cp is None:
            return m.group(0)              # unknown/external page -> leave untouched
        if cp == "/":
            return f'href="/{frag}"' if frag else 'href="/"'
        return f'href="{cp}{frag}"'
    canon_re = re.compile(r'[ \t]*<link[^>]+rel="canonical"[^>]*>\s*', re.I)
    for root, _, files in os.walk(out):
        for fn in files:
            if not fn.endswith(".html"): continue
            fp = os.path.join(root, fn)
            html = open(fp, encoding="utf-8").read()
            html = href_re.sub(_rewrite, html)
            html = canon_re.sub("", html)
            if domain:
                rel = os.path.relpath(fp, out).replace("\\","/")
                canon = f'{domain.rstrip("/")}{_clean_path(rel)}'
                if "</head>" in html:
                    html = html.replace("</head>", f'<link rel="canonical" href="{canon}">\n</head>', 1)
            open(fp, "w", encoding="utf-8").write(html)
    if domain:
        d = domain.rstrip("/")
        # Preserve any hand-crafted <lastmod>/<changefreq>/<priority> from the existing
        # sitemap, re-keyed to the new clean URLs. Falls back to sane defaults per page.
        def _norm(u):
            u = re.sub(r'^https?://[^/]+', '', (u or '').strip())
            if not u.startswith('/'): u = '/' + u
            u = re.sub(r'/index\.html$', '/', u)
            if u.endswith('.html'): u = u[:-5]
            if len(u) > 1: u = u.rstrip('/')
            return u or '/'
        preserved = {}
        sm_path = os.path.join(out, "sitemap.xml")
        try:
            if os.path.exists(sm_path):
                old = open(sm_path, encoding="utf-8").read()
                for blk in re.findall(r'<url>(.*?)</url>', old, re.S | re.I):
                    lm = re.search(r'<loc>(.*?)</loc>', blk, re.S | re.I)
                    if not lm: continue
                    key = _norm(lm.group(1))
                    def _tag(name):
                        m = re.search(rf'<{name}>(.*?)</{name}>', blk, re.S | re.I)
                        return m.group(1).strip() if m else None
                    preserved[key] = {"lastmod": _tag("lastmod"),
                                      "changefreq": _tag("changefreq"),
                                      "priority": _tag("priority")}
        except Exception:
            preserved = {}
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        urls = sorted({_clean_path(_page_relpath(p)) for p in pages})
        blocks = []
        for u in urls:
            info = preserved.get(_norm(u), {})
            lastmod = info.get("lastmod") or today
            changefreq = info.get("changefreq") or "monthly"
            priority = info.get("priority") or ("1.0" if u == "/" else "0.8")
            blocks.append(
                f'  <url>\n    <loc>{d}{u}</loc>\n    <lastmod>{lastmod}</lastmod>\n'
                f'    <changefreq>{changefreq}</changefreq>\n    <priority>{priority}</priority>\n  </url>')
        sm = ('<?xml version="1.0" encoding="UTF-8"?>\n'
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
              + "\n".join(blocks) + '\n</urlset>\n')
        open(sm_path, "w", encoding="utf-8").write(sm)
        rp = os.path.join(out, "robots.txt")
        if not os.path.exists(rp):
            open(rp, "w", encoding="utf-8").write(f"User-agent: *\nAllow: /\n\nSitemap: {d}/sitemap.xml\n")
    _write_clean_htaccess(out)

def build_dist(site_slug, pages, src_dir, site=None):
    out = os.path.join(DIST_DIR, site_slug)
    if os.path.exists(out): shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)
    # mirror the whole source tree EXCEPT html pages (those are rendered below),
    # so nested folders + their assets (e.g. car-sales/assets/..) are preserved
    if os.path.isdir(src_dir):
        shutil.copytree(src_dir, out, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.html"))
    # copy uploaded media
    md = os.path.join(MEDIA_DIR, site_slug)
    if os.path.isdir(md):
        dst=os.path.join(out,"assets","uploads"); os.makedirs(dst, exist_ok=True)
        for f in os.listdir(md): shutil.copy(os.path.join(md,f), os.path.join(dst,f))
    # render pages back to their own relative path (subfolders preserved)
    for p in pages:
        html = render_page(p, for_editor=False, asset_base="")
        rel = _page_relpath(p)
        dest = os.path.join(out, rel)
        os.makedirs(os.path.dirname(dest) or out, exist_ok=True)
        open(dest,"w",encoding="utf-8").write(html)
    # OPT-IN clean URLs (default off -> behaves exactly as before)
    if site and site.get("clean_urls"):
        dom = (site.get("domain") or "").strip()
        if dom and not dom.startswith("http"): dom = "https://" + dom
        _apply_clean_urls(out, pages, dom)
    return out

@api.post("/sites/{slug}/preview")
async def preview(slug: str, u=Depends(current_user)):
    s = await db.sites.find_one({"slug":slug})
    if not s: raise HTTPException(404,"Site not found")
    pages=[x async for x in db.pages.find({"site":slug})]
    out = build_dist(slug, pages, s["source_dir"], site=s)
    return {"dist":out,"pages":len(pages),"preview_url":f"/api/dist/{slug}/index.html"}

class ReplaceBody(BaseModel):
    find: str
    replace: str = ""
    match_case: bool = True
    dry_run: bool = False

def _count_and_replace(text, find, repl, match_case, do):
    if not text or not find:
        return text, 0
    if match_case:
        c = text.count(find)
        return (text.replace(find, repl) if do else text), c
    import re as _re
    pat = _re.compile(_re.escape(find), _re.IGNORECASE)
    c = len(pat.findall(text))
    return (pat.sub(lambda m: repl, text) if do else text), c

@api.post("/sites/{slug}/replace")
async def find_replace(slug: str, body: ReplaceBody, u=Depends(current_user)):
    s = await db.sites.find_one({"slug":slug})
    if not s: raise HTTPException(404,"Site not found")
    find = body.find
    if not find: raise HTTPException(400,"Enter the word or phrase to find.")
    do = not body.dry_run
    total = 0; pages_hit = 0
    if do:
        await create_snapshot(slug, "manual", f'Before replacing "{find[:40]}"')
    async for p in db.pages.find({"site":slug}):
        page_count = 0
        regions = p.get("regions", {})
        for eid, r in regions.items():
            if r.get("type") == "text":
                nv, c = _count_and_replace(r.get("value",""), find, body.replace, body.match_case, do)
                if c: r["value"] = nv; page_count += c
            elif r.get("type") == "image":
                na, c = _count_and_replace(r.get("alt",""), find, body.replace, body.match_case, do)
                if c: r["alt"] = na; page_count += c
        seo = p.get("seo", {})
        nt, c = _count_and_replace(seo.get("title",""), find, body.replace, body.match_case, do)
        if c: seo["title"] = nt; page_count += c
        if page_count:
            pages_hit += 1; total += page_count
            if do:
                await db.pages.update_one({"_id": p["_id"]}, {"$set": {"regions": regions, "seo": seo}})
    return {"replacements": total, "pages": pages_hit, "applied": do}

@api.get("/dist/{slug}/{path:path}")
async def serve_dist(slug: str, path: str):
    fp = os.path.join(DIST_DIR, slug, path)
    if os.path.isfile(fp):
        if fp.endswith(".html"): return HTMLResponse(open(fp,encoding="utf-8").read())
        return FileResponse(fp)
    raise HTTPException(404,"Not found")

@api.put("/sites/{slug}/sftp")
async def set_sftp(slug: str, body: SftpSettings, u=Depends(require_admin)):
    data = body.model_dump()
    domain = (data.pop("domain", "") or "").strip().lower()
    if not data.get("password"):
        existing = await db.sites.find_one({"slug":slug})
        data["password"] = (existing or {}).get("sftp",{}).get("password","")
    upd = {"sftp": data}
    if domain:
        upd["domain"] = domain
    await db.sites.update_one({"slug":slug},{"$set":upd})
    return {"ok":True}

@api.post("/sites/{slug}/sftp/test")
async def test_sftp(slug: str, body: SftpSettings, u=Depends(require_admin)):
    conf = body.model_dump()
    if not conf.get("password"):
        existing = await db.sites.find_one({"slug":slug})
        conf["password"] = (existing or {}).get("sftp",{}).get("password","")
    if not conf.get("host") or not conf.get("username") or not conf.get("password"):
        return {"ok":False,"message":"Enter host, username and password first (save the password once, then you can test)."}
    return await asyncio.to_thread(_do_test, conf)

@api.post("/sftp/test")
async def test_sftp_new(body: SftpSettings, u=Depends(require_super)):
    conf = body.model_dump()
    if not conf.get("host") or not conf.get("username") or not conf.get("password"):
        return {"ok":False,"message":"Enter host, username and password first."}
    return await asyncio.to_thread(_do_test, conf)

def _sftp_connect(conf, timeout=15):
    import paramiko
    sock = socket.create_connection((conf["host"], int(conf.get("port", 22))), timeout=timeout)
    t = paramiko.Transport(sock)
    t.banner_timeout = timeout
    t.connect(username=conf["username"], password=conf["password"])
    sf = paramiko.SFTPClient.from_transport(t)
    return t, sf

def _resolve_remote(sf, conf):
    remote = conf.get("remote_path", "public_html") or "public_html"
    if not remote.startswith("/"):
        return f"{sf.normalize('.').rstrip('/')}/{remote.strip('/')}"
    return remote.rstrip("/")

def _do_test(conf):
    try:
        t, sf = _sftp_connect(conf)
        try:
            remote = _resolve_remote(sf, conf)
            try:
                items = sf.listdir(remote); found = True
            except IOError:
                items = []; found = False
        finally:
            sf.close(); t.close()
        sample = sorted(items)[:12]
        if found:
            return {"ok":True,"remote":remote,"count":len(items),"sample":sample,
                    "message":f"Connected. Target folder is {remote} — it currently has {len(items)} item(s). ⚠️ Publishing will OVERWRITE matching files here, so make sure this is the right site's folder."}
        return {"ok":True,"remote":remote,"count":0,"sample":[],
                "message":f"Connected, but {remote} doesn't exist yet — it will be created on first publish. Double-check this is the correct folder for this site."}
    except socket.timeout:
        return {"ok":False,"message":"Connection timed out — check the host and port (Hostinger SFTP is usually port 65002)."}
    except Exception as e:
        return {"ok":False,"message":f"Connection failed: {e}"}

@api.get("/sites/{slug}/publish-target")
async def publish_target(slug: str, u=Depends(current_user)):
    s = await db.sites.find_one({"slug":slug})
    if not s: raise HTTPException(404,"Site not found")
    sftp = s.get("sftp") or {}
    pages = await db.pages.count_documents({"site":slug})
    configured = bool(sftp.get("host"))
    domain = (s.get("domain") or "").lower()
    remote = sftp.get("remote_path","") or ""
    path_ok = (not domain) or (domain in remote.lower())
    return {"configured":configured,"host":sftp.get("host",""),
            "remote_path":remote,"pages":pages,"domain":domain,"path_ok":path_ok,
            "clean_urls":bool(s.get("clean_urls",False))}

def _domain_guard(site, remote_path):
    """Raise if a site with a locked domain would publish to a path that doesn't contain it."""
    domain = (site.get("domain") or "").lower()
    if domain and domain not in (remote_path or "").lower():
        raise HTTPException(400,
            f"Blocked for safety: this site is locked to domain '{domain}', but the SFTP remote path "
            f"'{remote_path}' does not contain it. Set the path to that domain's own folder "
            f"(e.g. /home/USER/domains/{domain}/public_html) in Admin settings before publishing.")

def _sftp_push(sftp_conf, local_root, expect_domain=""):
    t, sf = _sftp_connect(sftp_conf)
    try:
        remote = _resolve_remote(sf, sftp_conf)
        if expect_domain and expect_domain.lower() not in remote.lower():
            raise ValueError(f"Refusing to upload: resolved path '{remote}' does not contain the locked domain '{expect_domain}'.")
        def _mkdirs(rpath):
            parts = rpath.strip("/").split("/"); cur = ""
            for p in parts:
                cur += "/" + p
                try: sf.stat(cur)
                except IOError: sf.mkdir(cur)
        _mkdirs(remote)
        for root, _, files in os.walk(local_root):
            rel = os.path.relpath(root, local_root)
            rdir = remote if rel == "." else f"{remote}/{rel}".replace("\\", "/")
            _mkdirs(rdir)
            for f in files:
                sf.put(os.path.join(root, f), f"{rdir}/{f}")
    finally:
        sf.close(); t.close()

def _download_dir(sf, rdir, ldir, budget):
    import stat
    os.makedirs(ldir, exist_ok=True)
    for entry in sf.listdir_attr(rdir):
        rp = f"{rdir}/{entry.filename}"
        lp = os.path.join(ldir, entry.filename)
        if stat.S_ISDIR(entry.st_mode):
            _download_dir(sf, rp, lp, budget)
        else:
            budget["files"] += 1
            budget["bytes"] += (entry.st_size or 0)
            if budget["files"] > 5000 or budget["bytes"] > 500 * 1024 * 1024:
                raise ValueError("Site is too large to pull (over 5000 files or 500MB). Narrow the remote path to the site's public_html.")
            sf.get(rp, lp)

def _sftp_pull(sftp_conf, local_root):
    t, sf = _sftp_connect(sftp_conf)
    try:
        remote = _resolve_remote(sf, sftp_conf)
        try:
            sf.stat(remote)
        except IOError:
            raise ValueError(f"Remote folder not found: {remote}. Check the path is this site's own public_html.")
        budget = {"files": 0, "bytes": 0}
        _download_dir(sf, remote, local_root, budget)
        return budget["files"]
    finally:
        sf.close(); t.close()

_bg_tasks = set()

@api.post("/sites/add")
async def add_site(body: AddSite, u=Depends(require_super)):
    slug = re.sub(r'[^a-z0-9-]', '-', body.slug.lower()).strip('-')
    if not slug: raise HTTPException(400, "Enter a valid site name (letters, numbers, hyphens).")
    if await db.sites.find_one({"slug": slug}):
        raise HTTPException(400, f"A site called '{slug}' already exists.")
    if not body.host or not body.username or not body.password:
        raise HTTPException(400, "Enter the SFTP host, username and password.")
    conf = {"host": body.host, "port": body.port, "username": body.username,
            "password": body.password, "remote_path": body.remote_path or "public_html"}
    job_id = uuid.uuid4().hex
    await db.add_jobs.insert_one({"_id": job_id, "slug": slug, "state": "starting",
        "message": "Connecting to your server…", "pulled": 0, "ingested": 0,
        "created": datetime.now(timezone.utc)})
    task = asyncio.create_task(_run_add_job(job_id, slug, conf, body.name, body.domain))
    _bg_tasks.add(task); task.add_done_callback(_bg_tasks.discard)
    return {"job_id": job_id, "slug": slug}

async def _run_add_job(job_id, slug, conf, name, domain):
    log = logging.getLogger("uvicorn.error")
    async def upd(**k): await db.add_jobs.update_one({"_id": job_id}, {"$set": k})
    local = os.path.join(SITES_DIR, slug)
    if os.path.exists(local): shutil.rmtree(local, ignore_errors=True)
    try:
        log.info(f"[add_site] pulling '{slug}' from {conf['host']}:{conf['port']} path={conf['remote_path']}")
        await upd(state="pulling", message="Downloading files from your server…")
        pulled = await asyncio.to_thread(_sftp_pull, conf, local)
    except socket.timeout:
        shutil.rmtree(local, ignore_errors=True)
        await upd(state="error", message="Connection timed out — check the host and port (Hostinger SFTP is usually 65002).")
        return
    except Exception as e:
        shutil.rmtree(local, ignore_errors=True)
        log.warning(f"[add_site] '{slug}' pull failed: {e}")
        await upd(state="error", message=f"Couldn't pull the site: {e}")
        return
    log.info(f"[add_site] '{slug}' pulled {pulled} files, ingesting…")
    await upd(state="ingesting", message=f"Downloaded {pulled} files. Reading your pages…", pulled=pulled)
    n = (await ingest_site(slug))["total"]
    if n == 0:
        shutil.rmtree(local, ignore_errors=True)
        await db.sites.delete_one({"slug": slug})
        await upd(state="error", message=f"Downloaded {pulled} file(s) but found no .html pages in '{conf['remote_path']}'. Point the Remote path at the folder that holds index.html.")
        return
    await db.sites.update_one({"slug": slug}, {"$set": {
        "name": name or slug, "domain": (domain or "").strip().lower(), "sftp": conf}})
    log.info(f"[add_site] '{slug}' DONE — {n} pages ingested")
    await upd(state="done", message=f"Added '{slug}' — pulled {pulled} files, {n} pages ready to edit.", ingested=n)

@api.get("/sites/add-status/{job_id}")
async def add_status(job_id: str, u=Depends(require_super)):
    j = await db.add_jobs.find_one({"_id": job_id})
    if not j: raise HTTPException(404, "Job not found")
    return {"state": j["state"], "message": j["message"], "pulled": j.get("pulled", 0),
            "ingested": j.get("ingested", 0), "slug": j.get("slug")}

def _extract_design_zip(zip_bytes, dest):
    """Safely unpack an uploaded site-design zip into dest. Guards against zip-slip and
    oversized archives, skips Mac/hidden cruft, and flattens a single wrapper folder
    (e.g. mysite.zip -> mysite/index.html) so index.html lands at the site root."""
    try:
        zf = zipfile.ZipFile(_io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        raise HTTPException(400, "That file isn't a valid .zip. Export your design as a ZIP and try again.")
    files = 0; total = 0
    dest_abs = os.path.abspath(dest)
    for info in zf.infolist():
        name = info.filename
        if info.is_dir(): continue
        parts = name.replace("\\", "/").split("/")
        _junk = {"__MACOSX", ".DS_Store", ".git", ".gitignore", ".idea", ".vscode", "Thumbs.db"}
        # skip Mac/editor cruft but KEEP legitimate web dotfiles like .htaccess / .well-known
        if any(p in _junk or p.startswith("._") for p in parts): continue
        target = os.path.abspath(os.path.join(dest, name))
        if not (target == dest_abs or target.startswith(dest_abs + os.sep)):
            raise HTTPException(400, "The zip contains an unsafe file path. Please re-export it.")
        files += 1; total += info.file_size
        if files > 5000 or total > 500 * 1024 * 1024:
            raise HTTPException(400, "That design is too large (over 5000 files or 500MB).")
        os.makedirs(os.path.dirname(target) or dest, exist_ok=True)
        with zf.open(info) as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out)
    # flatten a single wrapper directory if there's no top-level html
    entries = [e for e in os.listdir(dest) if not e.startswith(".")]
    top_html = glob.glob(os.path.join(dest, "*.html"))
    if not top_html and len(entries) == 1 and os.path.isdir(os.path.join(dest, entries[0])):
        inner = os.path.join(dest, entries[0])
        for e in os.listdir(inner):
            shutil.move(os.path.join(inner, e), os.path.join(dest, e))
        shutil.rmtree(inner, ignore_errors=True)
    return files

@api.post("/sites/create-from-design")
async def create_from_design(
    file: UploadFile = File(...),
    slug: str = Form(...), name: str = Form(""), domain: str = Form(""),
    client_email: str = Form(""), client_password: str = Form(""),
    sftp_host: str = Form(""), sftp_port: int = Form(22), sftp_username: str = Form(""),
    sftp_password: str = Form(""), sftp_remote_path: str = Form(""),
    u=Depends(require_super)):
    slug = re.sub(r'[^a-z0-9-]', '-', slug.lower()).strip('-')
    if not slug: raise HTTPException(400, "Enter a valid site ID (letters, numbers, hyphens).")
    if await db.sites.find_one({"slug": slug}):
        raise HTTPException(400, f"A site called '{slug}' already exists.")
    client_email = client_email.strip().lower()
    if client_email and await db.users.find_one({"email": client_email}):
        raise HTTPException(400, f"A user with email '{client_email}' already exists.")
    raw = await file.read()
    if not raw: raise HTTPException(400, "The uploaded file is empty.")
    local = os.path.join(SITES_DIR, slug)
    if os.path.exists(local): shutil.rmtree(local, ignore_errors=True)
    os.makedirs(local, exist_ok=True)
    try:
        extracted = _extract_design_zip(raw, local)
        n = (await ingest_site(slug))["total"]
        if n == 0:
            raise HTTPException(400, f"Unpacked {extracted} file(s) but found no .html pages. Make sure the ZIP contains an index.html.")
    except HTTPException:
        shutil.rmtree(local, ignore_errors=True); await db.sites.delete_one({"slug": slug})
        raise
    except Exception as e:
        shutil.rmtree(local, ignore_errors=True); await db.sites.delete_one({"slug": slug})
        raise HTTPException(400, f"Couldn't set up the site: {e}")
    set_fields = {"name": name.strip() or slug, "domain": (domain or "").strip().lower()}
    if sftp_host.strip():
        set_fields["sftp"] = {"host": sftp_host.strip(), "port": sftp_port or 22,
            "username": sftp_username.strip(), "password": sftp_password,
            "remote_path": (sftp_remote_path.strip() or "public_html")}
    await db.sites.update_one({"slug": slug}, {"$set": set_fields})
    created_user = None
    if client_email and client_password:
        await db.users.insert_one({"email": client_email, "password_hash": hash_pw(client_password),
            "name": name.strip() or slug, "role": "editor", "site_id": slug,
            "created_at": datetime.now(timezone.utc).isoformat()})
        created_user = client_email
    return {"ok": True, "slug": slug, "pages": n, "files": extracted,
            "client_user": created_user, "sftp_set": bool(sftp_host.strip()),
            "message": f"Created '{slug}' — {n} page{'s' if n!=1 else ''} ingested from {extracted} file(s)."}

@api.post("/sites/{slug}/publish")
async def publish(slug: str, u=Depends(current_user)):
    s = await db.sites.find_one({"slug":slug})
    if not s: raise HTTPException(404,"Site not found")
    await create_snapshot(slug, "pre-publish", "Before publishing")
    pages=[x async for x in db.pages.find({"site":slug})]
    out = build_dist(slug, pages, s["source_dir"], site=s)
    # backup current dist as zip
    ts=datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    bkp=os.path.join(BACKUP_DIR, f"{slug}-{ts}.zip")
    with zipfile.ZipFile(bkp,"w",zipfile.ZIP_DEFLATED) as z:
        for root,_,files in os.walk(out):
            for f in files:
                fp=os.path.join(root,f); z.write(fp, os.path.relpath(fp,out))
    sftp=s.get("sftp")
    if not sftp or not sftp.get("host"):
        return {"published":False,"backup":bkp,"dist":out,
                "message":"Rendered + backed up. SFTP not configured yet — set Hostinger SFTP credentials to push live."}
    _domain_guard(s, sftp.get("remote_path",""))
    try:
        await asyncio.to_thread(_sftp_push, sftp, out, (s.get("domain") or ""))
        await db.sites.update_one({"_id":s["_id"]},{"$set":{"last_published":ts}})
        return {"published":True,"backup":bkp,"files_pushed":True,"message":"Published live to Hostinger."}
    except Exception as e:
        return {"published":False,"backup":bkp,"error":str(e),
                "message":f"Render + backup OK but SFTP push failed: {e}"}

class NewPage(BaseModel):
    slug: str
    title: str
    from_slug: str | None = None

@api.delete("/users/{uid}")
async def delete_user(uid: str, u=Depends(require_admin)):
    if uid == u["id"]: raise HTTPException(400,"Cannot delete yourself")
    await db.users.delete_one({"_id":ObjectId(uid)})
    return {"ok":True}

@api.put("/users/{uid}")
async def update_user(uid: str, body: UserUpdate, u=Depends(require_admin)):
    existing = await db.users.find_one({"_id":ObjectId(uid)})
    if not existing: raise HTTPException(404,"User not found")
    upd = {}
    if body.name is not None: upd["name"] = body.name
    if body.role is not None: upd["role"] = body.role
    if body.site_id is not None: upd["site_id"] = body.site_id or None
    if body.password: upd["password_hash"] = hash_pw(body.password)
    if uid == u["id"] and body.role and body.role not in ("admin","superadmin"):
        raise HTTPException(400,"You cannot remove your own admin access")
    if upd: await db.users.update_one({"_id":ObjectId(uid)},{"$set":upd})
    return {"ok":True}

@api.get("/sites/{slug}/sftp")
async def get_sftp(slug: str, u=Depends(require_admin)):
    s = await db.sites.find_one({"slug":slug})
    if not s: raise HTTPException(404,"Site not found")
    sf = s.get("sftp",{}) or {}
    return {"host":sf.get("host",""),"port":sf.get("port",22),"username":sf.get("username",""),
            "remote_path":sf.get("remote_path","public_html"),"has_password":bool(sf.get("password")),
            "domain":s.get("domain","")}

@api.get("/available-sites")
async def available_sites(u=Depends(require_admin)):
    out=[]
    if os.path.isdir(SITES_DIR):
        for name in sorted(os.listdir(SITES_DIR)):
            p=os.path.join(SITES_DIR,name)
            if os.path.isdir(p) and glob.glob(os.path.join(p,"*.html")):
                ing = await db.sites.find_one({"slug":name})
                out.append({"slug":name,"ingested":bool(ing),"pages":len(glob.glob(os.path.join(p,"*.html"))),
                            "name":(ing or {}).get("name",name),"domain":(ing or {}).get("domain","")})
    return out

@api.put("/sites/{slug}/meta")
async def update_site_meta(slug: str, body: SiteMeta, u=Depends(require_admin)):
    s = await db.sites.find_one({"slug":slug})
    if not s: raise HTTPException(404,"Site not found")
    upd = {}
    if body.name is not None: upd["name"] = body.name.strip() or slug
    if body.domain is not None: upd["domain"] = (body.domain or "").strip().lower()
    if upd: await db.sites.update_one({"slug":slug},{"$set":upd})
    return {"ok":True, **upd}

class CleanUrlsBody(BaseModel):
    enabled: bool

@api.put("/sites/{slug}/clean-urls")
async def set_clean_urls(slug: str, body: CleanUrlsBody, u=Depends(require_admin)):
    s = await db.sites.find_one({"slug":slug})
    if not s: raise HTTPException(404,"Site not found")
    await db.sites.update_one({"slug":slug},{"$set":{"clean_urls":bool(body.enabled)}})
    return {"ok":True,"clean_urls":bool(body.enabled)}

def _nav_items(container):
    """Direct children of a nav container that are (or contain) a link — handles both
    <nav><a></nav> and <ul><li><a></li></ul> style menus."""
    out=[]
    for c in container.find_all(recursive=False):
        if getattr(c,"name",None) is None: continue
        if c.name=="a" or c.find("a"): out.append(c)
    return out

def _item_label(item):
    a = item if item.name=="a" else item.find("a")
    return (a.get_text() if a else "").strip()

@api.get("/sites/{slug}/nav")
async def get_nav(slug: str, u=Depends(require_admin)):
    home = await db.pages.find_one({"site":slug,"slug":"home"}) or await db.pages.find_one({"site":slug})
    if not home: return {"items": []}
    soup = BeautifulSoup(home.get("template",""), "lxml")
    body = soup.body or soup
    container = _find_nav_container(body.find("header"))
    if container is None: return {"items": []}
    items = [{"label": _item_label(it)} for it in _nav_items(container)]
    return {"items": [i for i in items if i["label"]]}

class NavOrder(BaseModel):
    order: list[str]

@api.post("/sites/{slug}/nav/reorder")
async def reorder_nav(slug: str, body: NavOrder, u=Depends(require_admin)):
    order = [l.strip() for l in body.order]
    updated = 0
    async for pg in db.pages.find({"site": slug}):
        soup = BeautifulSoup(pg.get("template",""), "lxml")
        b = soup.body or soup
        container = _find_nav_container(b.find("header"))
        if container is None: continue
        items = _nav_items(container)
        if len(items) < 2: continue
        bykey = {}
        for it in items:
            bykey.setdefault(_item_label(it), []).append(it)
        ordered = []; seen = set()
        for lb in order:
            lst = bykey.get(lb)
            if lst:
                it = lst.pop(0); ordered.append(it); seen.add(id(it))
        for it in items:
            if id(it) not in seen:
                ordered.append(it); seen.add(id(it))
        for it in ordered:
            container.append(it.extract())
        await db.pages.update_one({"_id": pg["_id"]}, {"$set": {"template": str(b)}})
        updated += 1
    return {"ok": True, "pages_updated": updated}

def scope_ok(u, site):
    return u.get("role")=="admin" or not u.get("site_id") or u["site_id"]==site

@api.post("/pages/{site}")
async def create_page(site: str, body: NewPage, u=Depends(current_user)):
    if not scope_ok(u, site): raise HTTPException(403,"Not allowed to edit this site")
    slug = re.sub(r'[^a-z0-9-]','-', body.slug.lower()).strip('-')
    if not slug: raise HTTPException(400,"Invalid URL slug")
    if slug=="home" or await db.pages.find_one({"site":site,"slug":slug}):
        raise HTTPException(400,"A page with that URL already exists")
    base = None
    if body.from_slug:
        base = await db.pages.find_one({"site":site,"slug":body.from_slug})
    if not base:
        base = await db.pages.find_one({"site":site,"slug":"home"})
    if not base: raise HTTPException(404,"No template page to base on")
    import copy
    seo = copy.deepcopy(base.get("seo",{})); seo["title"] = body.title
    doc = {"site":site,"slug":slug,"filename":f"{slug}.html","title":body.title,"seo":seo,
           "template":base["template"],"regions":copy.deepcopy(base.get("regions",{})),
           "head_assets":base.get("head_assets",[])}
    await db.pages.insert_one(doc)
    s = await db.sites.find_one({"slug":site})
    order = s.get("order",[]); order.append({"slug":slug,"filename":f"{slug}.html","title":body.title})
    await db.sites.update_one({"slug":site},{"$set":{"order":order}})
    return {"slug":slug}

# ---------------- page templates ----------------
@api.get("/templates")
async def list_templates(u=Depends(require_admin)):
    out = []
    async for t in db.templates.find().sort("name", 1):
        out.append({"id": t["_id"], "name": t.get("name",""), "description": t.get("description",""),
                    "builtin": bool(t.get("builtin"))})
    return out

@api.post("/templates")
async def create_template(body: TemplateIn, u=Depends(require_super)):
    if not body.name.strip() or not body.sections_html.strip():
        raise HTTPException(400, "Name and HTML are required")
    tid = uuid.uuid4().hex
    await db.templates.insert_one({"_id": tid, "name": body.name.strip(),
        "description": body.description.strip(), "sections_html": body.sections_html,
        "css": body.css, "js": body.js, "builtin": False,
        "created": datetime.now(timezone.utc)})
    return {"id": tid}

@api.delete("/templates/{tid}")
async def delete_template(tid: str, u=Depends(require_super)):
    t = await db.templates.find_one({"_id": tid})
    if t and t.get("builtin"):
        raise HTTPException(400, "Built-in templates can't be deleted")
    await db.templates.delete_one({"_id": tid})
    return {"ok": True}

@api.post("/pages/{site}/from-template")
async def create_page_from_template(site: str, body: FromTemplate, u=Depends(current_user)):
    if not scope_ok(u, site): raise HTTPException(403, "Not allowed to edit this site")
    slug = re.sub(r'[^a-z0-9-]', '-', body.slug.lower()).strip('-')
    if not slug: raise HTTPException(400, "Invalid URL slug")
    if slug == "home" or await db.pages.find_one({"site": site, "slug": slug}):
        raise HTTPException(400, "A page with that URL already exists")
    tpl = await db.templates.find_one({"_id": body.template_id})
    if not tpl: raise HTTPException(404, "Template not found")
    home = await db.pages.find_one({"site": site, "slug": "home"})
    if not home: raise HTTPException(404, "This site has no home page to take the header/footer from")
    s = await db.sites.find_one({"slug": site})
    header, footer = _chrome_from_home(home["template"])
    sections = tpl.get("sections_html", "")
    if body.enquiry_email.strip():
        sections = sections.replace("sales@yourgarage.co.uk", body.enquiry_email.strip())
    body_html = f'<body>{header}\n<main>{sections}</main>\n{footer}</body>'
    bodyel = BeautifulSoup(body_html, "lxml").body
    for el in bodyel.find_all(attrs={"data-eid": True}): del el["data-eid"]
    for el in bodyel.find_all(attrs={"data-caption": True}): del el["data-caption"]
    # add this page to its OWN nav (depth 0) before regions are assigned, so the link is editable
    _mk = BeautifulSoup("", "lxml")
    _STATE = ("active", "current", "is-active", "selected")
    navc0 = _find_nav_container(bodyel.find("header"))
    if navc0 is not None and not _nav_has_link(navc0, slug):
        # clear any "active/current" highlight inherited from the Home page, so the lifted
        # nav doesn't leave Home wrongly highlighted; then mark THIS page's own link active.
        active_cls = None
        for l in navc0.find_all("a"):
            cur = l.get("class") or []
            for c in cur:
                if c.lower() in _STATE: active_cls = c
            kept = [c for c in cur if c.lower() not in _STATE]
            if kept: l["class"] = kept
            elif l.has_attr("class"): del l["class"]
        a0 = _new_nav_anchor(_mk, navc0, slug, body.title, 0)
        if active_cls:
            a0["class"] = (a0.get("class") or []) + [active_cls]
        _insert_nav_link(navc0, a0)
    regions = assign_regions(bodyel)
    # head: reuse site chrome assets (fonts/css) + brand tokens + template component CSS + JS
    head_assets = list(home.get("head_assets", []))
    root_style = _brand_root_style(s.get("branding") if s else {})
    if root_style: head_assets.append(root_style)
    if tpl.get("css"): head_assets.append(f"<style>{tpl['css']}</style>")
    if tpl.get("js"): head_assets.append(f"<script>{tpl['js']}</script>")
    seo = {"title": body.title, "metas": [], "canonical": "", "jsonld": []}
    doc = {"site": site, "slug": slug, "filename": f"{slug}.html", "title": body.title,
           "seo": seo, "template": str(bodyel), "regions": regions, "head_assets": head_assets}
    await db.pages.insert_one(doc)
    order = s.get("order", []); order.append({"slug": slug, "filename": f"{slug}.html", "title": body.title})
    await db.sites.update_one({"slug": site}, {"$set": {"order": order}})
    # add a link to this new page into the nav on every OTHER page so the menu matches site-wide
    nav_added = 0
    eid = "nav" + re.sub(r'[^a-z0-9]', '', slug)
    async for pg in db.pages.find({"site": site, "slug": {"$ne": slug}}):
        soup2 = BeautifulSoup(pg.get("template", ""), "lxml")
        body2 = soup2.body or soup2
        navc = _find_nav_container(body2.find("header"))
        if navc is None or _nav_has_link(navc, slug):
            continue
        depth = (pg.get("relpath", "") or "").count("/")
        a = _new_nav_anchor(soup2, navc, slug, body.title, depth)
        a["data-eid"] = eid
        _insert_nav_link(navc, a)
        regions2 = dict(pg.get("regions") or {})
        regions2[eid] = {"type": "text", "value": body.title, "href": _href_at_depth(slug, depth), "link": True}
        await db.pages.update_one({"_id": pg["_id"]}, {"$set": {"template": str(body2), "regions": regions2}})
        nav_added += 1
    return {"slug": slug, "nav_added": nav_added}


@api.delete("/pages/{site}/{slug}")
async def delete_page(site: str, slug: str, u=Depends(current_user)):
    if not scope_ok(u, site): raise HTTPException(403,"Not allowed to edit this site")
    if slug=="home": raise HTTPException(400,"Cannot delete the home page")
    await db.pages.delete_one({"site":site,"slug":slug})
    s = await db.sites.find_one({"slug":site})
    order = [o for o in s.get("order",[]) if o["slug"]!=slug]
    await db.sites.update_one({"slug":site},{"$set":{"order":order}})
    # remove any nav links pointing at the deleted page so no menu items are left dangling
    async for pg in db.pages.find({"site":site}):
        soup2 = BeautifulSoup(pg.get("template",""), "lxml")
        body2 = soup2.body or soup2
        removed = []
        for a in body2.find_all("a"):
            h = (a.get("href") or "").split("#")[0].split("?")[0]
            if h.rstrip("/").endswith(f"{slug}.html"):
                if a.has_attr("data-eid"): removed.append(a["data-eid"])
                a.decompose()
        if removed:
            regions2 = {k:v for k,v in (pg.get("regions") or {}).items() if k not in removed}
            await db.pages.update_one({"_id":pg["_id"]},{"$set":{"template":str(body2),"regions":regions2}})
    return {"ok":True}

@api.get("/sites/{slug}/backups")
async def list_backups(slug: str, u=Depends(current_user)):
    out=[]
    for f in sorted(glob.glob(os.path.join(BACKUP_DIR,f"{slug}-*.zip")), reverse=True):
        st=os.stat(f)
        out.append({"name":os.path.basename(f),"size":st.st_size,
                    "created":datetime.fromtimestamp(st.st_mtime,timezone.utc).isoformat()})
    return out

@api.get("/sites/{slug}/publish-changes")
async def publish_changes(slug: str, u=Depends(current_user)):
    """Build the site now and compare it against the last published backup so the
    user sees exactly what will change BEFORE anything goes live."""
    import hashlib
    s = await db.sites.find_one({"slug":slug})
    if not s: raise HTTPException(404,"Site not found")
    pages=[x async for x in db.pages.find({"site":slug})]
    out = build_dist(slug, pages, s["source_dir"], site=s)
    def _md5(b): return hashlib.md5(b).hexdigest()
    new_files={}
    for root,_,files in os.walk(out):
        for f in files:
            fp=os.path.join(root,f); rel=os.path.relpath(fp,out).replace("\\","/")
            with open(fp,"rb") as fh: new_files[rel]=_md5(fh.read())
    backups=sorted(glob.glob(os.path.join(BACKUP_DIR,f"{slug}-*.zip")), reverse=True)
    if not backups:
        return {"has_baseline":False,"pages":len(pages),
                "added":sorted(new_files.keys()),"changed":[],"removed":[]}
    old_files={}
    try:
        with zipfile.ZipFile(backups[0]) as z:
            for n in z.namelist():
                if n.endswith("/"): continue
                old_files[n.replace("\\","/")]=_md5(z.read(n))
    except Exception:
        return {"has_baseline":False,"pages":len(pages),
                "added":sorted(new_files.keys()),"changed":[],"removed":[]}
    added=sorted(k for k in new_files if k not in old_files)
    removed=sorted(k for k in old_files if k not in new_files)
    changed=sorted(k for k in new_files if k in old_files and new_files[k]!=old_files[k])
    return {"has_baseline":True,"pages":len(pages),
            "baseline":os.path.basename(backups[0]),
            "added":added,"changed":changed,"removed":removed}

@api.post("/sites/{slug}/restore")
async def restore(slug: str, body: dict, u=Depends(require_admin)):
    import tempfile
    fp = os.path.join(BACKUP_DIR, os.path.basename(body.get("name","")))
    if not os.path.isfile(fp): raise HTTPException(404,"Backup not found")
    tmp = tempfile.mkdtemp()
    with zipfile.ZipFile(fp) as z: z.extractall(tmp)
    s = await db.sites.find_one({"slug":slug})
    sftp = (s or {}).get("sftp")
    if not sftp or not sftp.get("host"):
        shutil.rmtree(tmp, ignore_errors=True)
        return {"restored":False,"message":"Backup unpacked, but SFTP isn't configured — set credentials to push the rollback live."}
    _domain_guard(s, sftp.get("remote_path",""))
    try:
        await asyncio.to_thread(_sftp_push, sftp, tmp, (s.get("domain") or ""))
        return {"restored":True,"message":f"Rolled back to {body.get('name')} and pushed live."}
    except Exception as e:
        return {"restored":False,"error":str(e),"message":f"Rollback push failed: {e}"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

app.include_router(api)

@app.middleware("http")
async def _noindex_header(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet"
    return resp

_cors = os.environ.get("CORS_ORIGINS", "*")
_origins = ["*"] if _cors.strip() == "*" else [o.strip() for o in _cors.split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    try:
        await db.add_jobs.create_index("created", expireAfterSeconds=86400)
    except Exception:
        pass
    try:
        await db.alt_jobs.create_index("created", expireAfterSeconds=86400)
    except Exception:
        pass
    admin_email = os.environ.get("SUPERADMIN_EMAIL", os.environ.get("ADMIN_EMAIL", "admin@example.com")).lower()
    admin_pw = os.environ.get("SUPERADMIN_PASSWORD", os.environ.get("ADMIN_PASSWORD", "admin123"))
    admin_name = os.environ.get("SUPERADMIN_NAME", "Super Admin")
    ex = await db.users.find_one({"email": admin_email})
    if not ex:
        await db.users.insert_one({"email": admin_email, "password_hash": hash_pw(admin_pw),
            "name": admin_name, "role": "superadmin", "site_id": None, "created_at": datetime.now(timezone.utc).isoformat()})
    elif ex.get("role") != "superadmin":
        await db.users.update_one({"_id": ex["_id"]}, {"$set": {"role": "superadmin"}})
    # auto-ingest any site folder (with .html files) that isn't ingested yet
    if os.path.isdir(SITES_DIR):
        for name in sorted(os.listdir(SITES_DIR)):
            p = os.path.join(SITES_DIR, name)
            if os.path.isdir(p) and glob.glob(os.path.join(p, "*.html")):
                if not await db.sites.find_one({"slug": name}):
                    await ingest_site(name)
    # seed / refresh built-in page templates (idempotent by key)
    for t in BUILTIN_TEMPLATES:
        await db.templates.update_one({"key": t["key"]}, {"$set": {
            "_id": t["key"], "key": t["key"], "name": t["name"], "description": t["description"],
            "sections_html": t["sections_html"], "css": t["css"], "js": t["js"], "builtin": True}},
            upsert=True)
