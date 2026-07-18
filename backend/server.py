from dotenv import load_dotenv
load_dotenv()

import os, io, re, json, shutil, zipfile, glob, socket, asyncio, logging, uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

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

app = FastAPI(title="Website Editor")
api = APIRouter(prefix="/api")

BUILD_VERSION = "2026-07-18-add-site-async-v3"

@api.get("/version")
async def version():
    return {"version": BUILD_VERSION, "features": ["add-site-async", "sftp-test", "domain-lock", "multi-site", "publish-confirm"]}

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
class PageOp(BaseModel):
    op: str
    eid: str
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

# ---------------- ingestion ----------------
def _clean_links(s):
    s = re.sub(r'href="index\.html"', 'href="/"', s)
    s = re.sub(r'href="([a-z0-9][a-z0-9-]*)\.html"', r'href="/\1/"', s)
    s = re.sub(r'href="https?://[^"]*?/([a-z0-9-]+)\.html"', r'href="/\1/"', s)
    return s

def _set_html(el, html):
    el.clear()
    frag = BeautifulSoup(html or "", "html.parser")
    for c in list(frag.contents):
        el.append(c)

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
        regions[eid] = {"type": "image", "value": img.get("src", "")}
    return regions

def ingest_page(html, slug):
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
    return count

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
    # prune auto/pre-publish to the 80 most recent (imports + manual kept forever)
    olds = db.snapshots.find({"site":site,"kind":{"$in":["auto","pre-publish"]}}).sort("created",-1)
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
            el["src"] = r["value"]
        if not for_editor and el.has_attr("data-eid"):
            del el["data-eid"]
    inner = bodyel.decode_contents()
    seo = page.get("seo",{})
    head = f"<title>{seo.get('title','')}</title>\n" + "\n".join(seo.get("metas",[]))
    if seo.get("canonical"): head += f'\n<link rel="canonical" href="{seo["canonical"]}">'
    head += "\n" + "\n".join(seo.get("jsonld",[]))
    head += "\n" + "\n".join(page.get("head_assets",[]))
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
#ed-tb{position:absolute;z-index:2147483000;display:none;gap:4px;background:#12151b;border:1px solid #A78C46;border-radius:8px;padding:5px;box-shadow:0 10px 30px rgba(0,0,0,.5);font-family:Arial,sans-serif}
#ed-tb button{background:#232833;color:#e9ecf1;border:1px solid #3a4150;border-radius:5px;padding:5px 9px;font-size:12px;line-height:1;cursor:pointer;white-space:nowrap}
#ed-tb button:hover{background:#A78C46;color:#161616;border-color:#A78C46}
</style>
<script>
document.addEventListener('DOMContentLoaded',function(){
  var tb=document.createElement('div'); tb.id='ed-tb'; document.body.appendChild(tb);
  var sel=null;
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
      tb.appendChild(mk('Replace',function(){post({t:'image',eid:eid});}));
      tb.appendChild(mk('+ Add another',function(){post({t:'op',op:'add-image',eid:eid});}));
    }
    if(isLink){
      tb.appendChild(mk('Link',function(){post({t:'link',eid:eid,href:el.getAttribute('href')||''});}));
    }
    tb.appendChild(mk('Duplicate',function(){post({t:'op',op:'duplicate',eid:eid});}));
    tb.appendChild(mk('+ Button',function(){post({t:'op',op:'add-button',eid:eid});}));
    tb.appendChild(mk('Delete',function(){post({t:'op',op:'delete',eid:eid});}));
    tb.style.display='flex';
    place(el);
  }
  document.querySelectorAll('[data-eid]').forEach(function(el){
    var eid=el.getAttribute('data-eid');
    if(el.tagName==='IMG'){
      el.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();select(el);});
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
    p = await db.pages.find_one({"site":slug_site,"slug":slug})
    if not p: raise HTTPException(404,"Page not found")
    if body.eid not in p.get("regions",{}): raise HTTPException(400,"Unknown region")
    await maybe_auto_snapshot(slug_site)
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
    await db.pages.update_one({"_id":p["_id"]},{"$set":{f"regions.{body.eid}.href":body.href,f"regions.{body.eid}.link":True}})
    return {"ok":True}

@api.post("/pages/{slug_site}/{slug}/op")
async def page_op(slug_site: str, slug: str, body: PageOp, u=Depends(current_user)):
    if not scope_ok(u, slug_site): raise HTTPException(403,"Not allowed to edit this site")
    p = await db.pages.find_one({"site":slug_site,"slug":slug})
    if not p: raise HTTPException(404,"Page not found")
    if body.op not in ("duplicate","delete","add-image","add-button"):
        raise HTTPException(400,"Unknown operation")
    await maybe_auto_snapshot(slug_site)
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
            el["src"] = r["value"]
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
    regions = assign_regions(bodyel)
    await db.pages.update_one({"_id":p["_id"]},{"$set":{"template":str(bodyel),"regions":regions}})
    return {"ok":True}

@api.put("/pages/{slug_site}/{slug}/seo")
async def update_seo(slug_site: str, slug: str, body: SeoUpdate, u=Depends(current_user)):
    await maybe_auto_snapshot(slug_site)
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
async def make_snapshot(slug: str, body: dict = {}, u=Depends(current_user)):
    if not scope_ok(u, slug): raise HTTPException(403,"Not allowed for this site")
    sid = await create_snapshot(slug, "manual", (body.get("label") or "Manual restore point"))
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
