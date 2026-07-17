from dotenv import load_dotenv
load_dotenv()

import os, io, re, json, shutil, zipfile, glob
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
    if u.get("role")!="admin": raise HTTPException(403,"Admin only")
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
class SeoUpdate(BaseModel):
    seo: dict
class SftpSettings(BaseModel):
    host: str = ""
    port: int = 22
    username: str = ""
    password: str = ""
    remote_path: str = "/public_html"

# ---------------- ingestion ----------------
def _clean_links(s):
    s = re.sub(r'href="index\.html"', 'href="/"', s)
    s = re.sub(r'href="([a-z0-9][a-z0-9-]*)\.html"', r'href="/\1/"', s)
    s = re.sub(r'href="https?://[^"]*?/([a-z0-9-]+)\.html"', r'href="/\1/"', s)
    return s

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
    regions = {}
    n = 0
    for el in body.find_all(list(EDIT_TAGS)):
        if el.find(list(EDIT_TAGS)):  # not a leaf text element
            continue
        txt = el.get_text(strip=True)
        if not txt: continue
        eid = f"t{n}"; n += 1
        el["data-eid"] = eid
        regions[eid] = {"type":"text","value":el.decode_contents()}
    for img in body.find_all("img"):
        eid = f"i{n}"; n += 1
        img["data-eid"] = eid
        regions[eid] = {"type":"image","value":img.get("src","")}
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
    return count

# ---------------- render ----------------
def render_page(page, for_editor=False, asset_base=""):
    template = page["template"]
    soup = BeautifulSoup(template, "lxml")
    bodyel = soup.body or soup
    for eid, r in page["regions"].items():
        el = bodyel.find(attrs={"data-eid":eid})
        if not el: continue
        if r["type"]=="text":
            el.clear()
            el.append(BeautifulSoup(r["value"], "lxml"))
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
[data-eid]{outline:1px dashed rgba(167,140,70,.0);transition:outline .12s;cursor:text}
[data-eid]:hover{outline:2px dashed #A78C46;outline-offset:2px}
img[data-eid]{cursor:pointer}
[data-eid].editing{outline:2px solid #A78C46;background:rgba(167,140,70,.06)}
</style>
<script>
document.addEventListener('DOMContentLoaded',function(){
  document.querySelectorAll('[data-eid]').forEach(function(el){
    var eid=el.getAttribute('data-eid');
    if(el.tagName==='IMG'){
      el.addEventListener('click',function(e){e.preventDefault();parent.postMessage({t:'image',eid:eid},'*');});
    } else {
      el.addEventListener('click',function(e){
        if(el.tagName==='A') e.preventDefault();
      });
      el.setAttribute('contenteditable','true');
      el.addEventListener('focus',function(){el.classList.add('editing');});
      el.addEventListener('blur',function(){el.classList.remove('editing');parent.postMessage({t:'text',eid:eid,value:el.innerHTML},'*');});
    }
  });
  document.querySelectorAll('a').forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();});});
});
</script>
"""

# ---------------- auth routes ----------------
@api.post("/auth/login")
async def login(body: Login, response: Response):
    u = await db.users.find_one({"email":body.email.lower()})
    if not u or not verify_pw(body.password, u["password_hash"]):
        raise HTTPException(401,"Invalid email or password")
    tok = make_token(str(u["_id"]), u["email"], u.get("role","editor"))
    response.set_cookie("access_token", tok, httponly=True, secure=False, samesite="lax", max_age=604800, path="/")
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
    await db.pages.update_one({"_id":p["_id"]},{"$set":{f"regions.{body.eid}.value":body.value}})
    return {"ok":True}

@api.put("/pages/{slug_site}/{slug}/seo")
async def update_seo(slug_site: str, slug: str, body: SeoUpdate, u=Depends(current_user)):
    await db.pages.update_one({"site":slug_site,"slug":slug},{"$set":{"seo":body.seo}})
    return {"ok":True}

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
    await db.sites.update_one({"slug":slug},{"$set":{"sftp":body.model_dump()}})
    return {"ok":True}

@api.post("/sites/{slug}/publish")
async def publish(slug: str, u=Depends(current_user)):
    s = await db.sites.find_one({"slug":slug})
    if not s: raise HTTPException(404,"Site not found")
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
    # SFTP upload
    try:
        import paramiko
        t=paramiko.Transport((sftp["host"], int(sftp.get("port",22))))
        t.connect(username=sftp["username"], password=sftp["password"])
        sf=paramiko.SFTPClient.from_transport(t)
        remote=sftp.get("remote_path","/public_html")
        def _mkdirs(rpath):
            parts=rpath.strip("/").split("/"); cur=""
            for p in parts:
                cur+="/"+p
                try: sf.stat(cur)
                except IOError: sf.mkdir(cur)
        for root,_,files in os.walk(out):
            rel=os.path.relpath(root,out)
            rdir=remote if rel=="." else f"{remote}/{rel}".replace("\\","/")
            _mkdirs(rdir)
            for f in files:
                sf.put(os.path.join(root,f), f"{rdir}/{f}")
        sf.close(); t.close()
        await db.sites.update_one({"_id":s["_id"]},{"$set":{"last_published":ts}})
        return {"published":True,"backup":bkp,"files_pushed":True,"message":"Published to Hostinger."}
    except Exception as e:
        return {"published":False,"backup":bkp,"error":str(e),
                "message":"Render + backup OK but SFTP push failed. Check credentials/host."}

app.include_router(api)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    admin_email=os.environ.get("ADMIN_EMAIL","admin@example.com").lower()
    admin_pw=os.environ.get("ADMIN_PASSWORD","admin123")
    ex=await db.users.find_one({"email":admin_email})
    if not ex:
        await db.users.insert_one({"email":admin_email,"password_hash":hash_pw(admin_pw),
            "name":"Super Admin","role":"admin","site_id":None,"created_at":datetime.now(timezone.utc).isoformat()})
    # auto-ingest wifetobe on first boot
    if not await db.sites.find_one({"slug":"wifetobe"}) and os.path.isdir(os.path.join(SITES_DIR,"wifetobe")):
        await ingest_site("wifetobe")
