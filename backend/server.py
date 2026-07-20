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
from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient

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

BUILD_VERSION = "2026-07-19-editor-plus-v4"

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
        eid = f"t{n}"; n += 1
        el["data-eid"] = eid
        reg = {"type": "text", "value": el.decode_contents()}
        if el.name in ("a", "button") and el.has_attr("href"):
            reg["href"] = el.get("href", "")
            reg["link"] = True
        regions[eid] = reg
    for img in body.find_all("img"):
        eid = f"i{n}"; n += 1
        img["data-eid"] = eid
        regions[eid] = {"type": "image", "value": img.get("src", ""), "alt": img.get("alt", "")}
    return regions

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

async def ingest_site(site_slug):
    src = os.path.join(SITES_DIR, site_slug)
    if not os.path.isdir(src): return 0
    await db.sites.update_one({"slug":site_slug},{"$set":{"slug":site_slug,"name":site_slug,"source_dir":src,
        "updated_at":datetime.now(timezone.utc).isoformat()}}, upsert=True)
    order=[]
    count=0
    for path in sorted(glob.glob(os.path.join(src,"*.html"))):
        fn = os.path.basename(path)
        slug = "home" if fn=="index.html" else fn[:-5]
        data = ingest_page(open(path,encoding="utf-8").read(), slug)
        data["site"]=site_slug; data["filename"]=fn
        await db.pages.update_one({"site":site_slug,"slug":slug},{"$set":data}, upsert=True)
        order.append({"slug":slug,"filename":fn,"title":data["title"]})
        count+=1
    await db.sites.update_one({"slug":site_slug},{"$set":{"order":order}})
    if count and not await db.snapshots.find_one({"site":site_slug,"kind":"import"}):
        await create_snapshot(site_slug, "import", "Original (as imported)")
    await autofill_brand(site_slug, src)
    return count

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
    for eid, r in page["regions"].items():
        el = bodyel.find(attrs={"data-eid":eid})
        if not el: continue
        if r["type"]=="text":
            _set_html(el, r["value"])
            if r.get("href") is not None and el.name in ("a","button"):
                el["href"] = r["href"]
        elif r["type"]=="image":
            _apply_image(el, r["value"], r.get("alt"))
            cap = (el.get("data-caption") or "").strip()
            if cap:
                fc = soup.new_tag("figcaption"); fc["class"] = "ivd-caption"; fc.string = cap
                el.insert_after(fc)
            if not for_editor and el.has_attr("data-caption"):
                del el["data-caption"]
        if not for_editor and el.has_attr("data-eid"):
            del el["data-eid"]
    inner = bodyel.decode_contents()
    seo = page.get("seo",{})
    head = f"<title>{seo.get('title','')}</title>\n" + "\n".join(seo.get("metas",[]))
    if seo.get("canonical"): head += f'\n<link rel="canonical" href="{seo["canonical"]}">'
    head += "\n" + "\n".join(seo.get("jsonld",[]))
    head += "\n" + "\n".join(page.get("head_assets",[]))
    head += '\n<style>.ivd-caption{display:block;text-align:center;font-size:.85rem;color:#666;margin:.4rem auto 1rem;font-style:italic;max-width:90%;}</style>'
    base = f'<base href="{asset_base}">' if asset_base else ""
    editor_assets = EDITOR_INJECT if for_editor else ""
    return f"""<!DOCTYPE html><html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">{base}
{head}
{editor_assets}</head><body>{inner}</body></html>"""

EDITOR_INJECT = """
<style>
[data-eid]{outline:1px dashed rgba(167,140,70,0);transition:outline .12s;cursor:pointer}
[data-eid]:hover{outline:2px dashed #A78C46;outline-offset:2px}
[data-eid].ed-sel{outline:2px solid #A78C46;outline-offset:2px}
[data-eid][contenteditable="true"]{cursor:text}
img[data-eid]{cursor:grab}
img[data-eid].ed-drag{opacity:.4}
img[data-eid].ed-over{outline:3px solid #A78C46 !important;outline-offset:2px}
#ed-tb{position:absolute;z-index:2147483000;display:none;gap:4px;background:#12151b;border:1px solid #A78C46;border-radius:8px;padding:5px;box-shadow:0 10px 30px rgba(0,0,0,.5);font-family:Arial,sans-serif}
#ed-tb button{background:#232833;color:#e9ecf1;border:1px solid #3a4150;border-radius:5px;padding:5px 9px;font-size:12px;line-height:1;cursor:pointer;white-space:nowrap}
#ed-tb button:hover{background:#A78C46;color:#161616;border-color:#A78C46}
#ed-tb button.ed-block-btn{background:#3a2f14;color:#e9d9a8;border-color:#A78C46}
#ed-tb button.ed-block-btn:hover{background:#A78C46;color:#161616}
</style>
<script>
document.addEventListener('DOMContentLoaded',function(){
  var tb=document.createElement('div'); tb.id='ed-tb'; document.body.appendChild(tb);
  var sel=null; var dragEid=null;
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
    tb.innerHTML='';
    if(isImg){
      tb.appendChild(mk('Replace',function(){post({t:'image',eid:eid,ar:_ar(el)});}));
      tb.appendChild(mk('+ Add photos',function(){post({t:'bulk-image',eid:eid,ar:_ar(el)});}));
      tb.appendChild(mk('Alt text',function(){post({t:'alt',eid:eid,alt:el.getAttribute('alt')||''});}));
      tb.appendChild(mk('Caption',function(){post({t:'caption',eid:eid,caption:el.getAttribute('data-caption')||''});}));
    }
    if(isLink){
      tb.appendChild(mk('Link',function(){post({t:'link',eid:eid,href:el.getAttribute('href')||''});}));
    }
    tb.appendChild(mk('↑ Up',function(){post({t:'op',op:'move-up',eid:eid});}));
    tb.appendChild(mk('↓ Down',function(){post({t:'op',op:'move-down',eid:eid});}));
    tb.appendChild(mk('Duplicate',function(){post({t:'op',op:'duplicate',eid:eid});}));
    tb.appendChild(mk('+ Button',function(){post({t:'op',op:'add-button',eid:eid});}));
    tb.appendChild(mk('Delete',function(){post({t:'op',op:'delete',eid:eid});}));
    var blk = el.closest ? el.closest('[data-block]') : null;
    if(blk){
      var bn = blk.getAttribute('data-block'); bn = (bn && bn.trim()) ? bn.trim() : 'block';
      var b1=mk('Duplicate '+bn,function(){post({t:'op',op:'duplicate-block',eid:eid});}); b1.className='ed-block-btn';
      var b2=mk('Delete '+bn,function(){post({t:'op',op:'delete-block',eid:eid});}); b2.className='ed-block-btn';
      var b3=mk('Status',function(){post({t:'status',eid:eid});}); b3.className='ed-block-btn';
      var b4=mk('\u25C0 Move',function(){post({t:'op',op:'move-block-up',eid:eid});}); b4.className='ed-block-btn';
      var b5=mk('Move \u25B6',function(){post({t:'op',op:'move-block-down',eid:eid});}); b5.className='ed-block-btn';
      tb.appendChild(b1); tb.appendChild(b2); tb.appendChild(b3); tb.appendChild(b4); tb.appendChild(b5);
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
      el.setAttribute('contenteditable','true');
      el.addEventListener('focus',function(){select(el);});
      el.addEventListener('click',function(e){ if(el.tagName==='A'||el.tagName==='BUTTON'){e.preventDefault();} select(el); });
      el.addEventListener('blur',function(){ post({t:'text',eid:eid,value:el.innerHTML}); });
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
        out.append({"slug":s["slug"],"name":s.get("name"),"order":s.get("order",[])})
    return out

@api.post("/sites/{slug}/ingest")
async def do_ingest(slug: str, u=Depends(require_admin)):
    n = await ingest_site(slug)
    if n==0: raise HTTPException(404,f"No pages found in {SITES_DIR}/{slug}")
    return {"ingested":n}

@api.get("/sites/{slug}/pages")
async def site_pages(slug: str, u=Depends(current_user)):
    s = await db.sites.find_one({"slug":slug})
    if not s: raise HTTPException(404,"Site not found")
    return s.get("order",[])

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
    if r.get("type") != "text" or not el or el.name not in ("a","button"):
        raise HTTPException(400,"That element isn't a link or button")
    await maybe_auto_snapshot(slug_site)
    await push_undo(slug_site, slug)
    await db.pages.update_one({"_id":p["_id"]},{"$set":{f"regions.{body.eid}.href":body.href,f"regions.{body.eid}.link":True}})
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
    if body.op not in ("duplicate","delete","add-image","add-button","move-up","move-down","swap-image","duplicate-block","delete-block","move-block-up","move-block-down","status-sold","status-reserved","status-new","status-clear"):
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
    base = f"/api/asset/{slug_site}/"
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
    safe = re.sub(r'[^a-zA-Z0-9_.-]','_', file.filename)
    name = f"{int(datetime.now().timestamp())}_{safe}"
    with open(os.path.join(d,name),"wb") as f: shutil.copyfileobj(file.file, f)
    return {"url": f"assets/uploads/{name}"}

# ---------------- publish ----------------
def build_dist(site_slug, pages, src_dir):
    out = os.path.join(DIST_DIR, site_slug)
    if os.path.exists(out): shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)
    # copy assets + root files from source
    if os.path.isdir(os.path.join(src_dir,"assets")):
        shutil.copytree(os.path.join(src_dir,"assets"), os.path.join(out,"assets"))
    for rf in ("robots.txt","llms.txt","llms-full.txt","sitemap.xml",".htaccess"):
        sp=os.path.join(src_dir,rf)
        if os.path.isfile(sp): shutil.copy(sp, os.path.join(out,rf))
    # copy uploaded media
    md = os.path.join(MEDIA_DIR, site_slug)
    if os.path.isdir(md):
        dst=os.path.join(out,"assets","uploads"); os.makedirs(dst, exist_ok=True)
        for f in os.listdir(md): shutil.copy(os.path.join(md,f), os.path.join(dst,f))
    # render pages (rewrite asset_base to relative for hosting)
    for p in pages:
        html = render_page(p, for_editor=False, asset_base="")
        # rewrite uploaded media src to relative path already 'assets/uploads/...'
        fn = "index.html" if p["slug"]=="home" else f"{p['slug']}.html"
        open(os.path.join(out,fn),"w",encoding="utf-8").write(html)
    return out

@api.post("/sites/{slug}/preview")
async def preview(slug: str, u=Depends(current_user)):
    s = await db.sites.find_one({"slug":slug})
    if not s: raise HTTPException(404,"Site not found")
    pages=[x async for x in db.pages.find({"site":slug})]
    out = build_dist(slug, pages, s["source_dir"])
    return {"dist":out,"pages":len(pages),"preview_url":f"/api/dist/{slug}/index.html"}

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
            "remote_path":remote,"pages":pages,"domain":domain,"path_ok":path_ok}

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
    n = await ingest_site(slug)
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

@api.post("/sites/{slug}/publish")
async def publish(slug: str, u=Depends(current_user)):
    s = await db.sites.find_one({"slug":slug})
    if not s: raise HTTPException(404,"Site not found")
    await create_snapshot(slug, "pre-publish", "Before publishing")
    pages=[x async for x in db.pages.find({"site":slug})]
    out = build_dist(slug, pages, s["source_dir"])
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
                out.append({"slug":name,"ingested":bool(ing),"pages":len(glob.glob(os.path.join(p,"*.html")))})
    return out

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
    return {"slug": slug}


@api.delete("/pages/{site}/{slug}")
async def delete_page(site: str, slug: str, u=Depends(current_user)):
    if not scope_ok(u, site): raise HTTPException(403,"Not allowed to edit this site")
    if slug=="home": raise HTTPException(400,"Cannot delete the home page")
    await db.pages.delete_one({"site":site,"slug":slug})
    s = await db.sites.find_one({"slug":site})
    order = [o for o in s.get("order",[]) if o["slug"]!=slug]
    await db.sites.update_one({"slug":site},{"$set":{"order":order}})
    return {"ok":True}

@api.get("/sites/{slug}/backups")
async def list_backups(slug: str, u=Depends(current_user)):
    out=[]
    for f in sorted(glob.glob(os.path.join(BACKUP_DIR,f"{slug}-*.zip")), reverse=True):
        st=os.stat(f)
        out.append({"name":os.path.basename(f),"size":st.st_size,
                    "created":datetime.fromtimestamp(st.st_mtime,timezone.utc).isoformat()})
    return out

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
