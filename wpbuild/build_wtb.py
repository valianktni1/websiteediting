import os, re, json, glob, random, shutil
from bs4 import BeautifulSoup

SRC = "/app/wpbuild/src2/wifetobe-org (4)"
OUT = "/app/wpbuild/plugin2/wifetobe-elementor"
TPL = os.path.join(OUT, "templates")
TOKEN = "__WTB_BASE__"
DOMAIN = "wifetobe.org"
ROOT_FILES = ["robots.txt", "llms.txt", "llms-full.txt", "sitemap.xml"]
os.makedirs(TPL, exist_ok=True)
os.makedirs(os.path.join(OUT, "data"), exist_ok=True)

def nid(): return ''.join(random.choice('0123456789abcdef') for _ in range(7))

def url_clean(s):
    s = re.sub(r'(https?://%s)/index\.html' % re.escape(DOMAIN), r'\1/', s)
    s = re.sub(r'(https?://%s)/([a-z0-9-]+)\.html' % re.escape(DOMAIN), r'\1/\2/', s)
    s = s.replace('/index.html', '/')
    s = re.sub(r'/([a-z0-9][a-z0-9-]*)\.html', r'/\1/', s)
    s = re.sub(r'"index\.html"', '"/"', s)
    s = re.sub(r'"([a-z0-9][a-z0-9-]*)\.html"', r'"/\1/"', s)
    s = re.sub(r"'index\.html'", "'/'", s)
    s = re.sub(r"'([a-z0-9][a-z0-9-]*)\.html'", r"'/\1/'", s)
    return s

def rewrite_assets(html):
    for pre in ('="./assets/', '="/assets/', '="assets/'):
        html = html.replace(pre, '="%s/assets/' % TOKEN)
    for pre in ("url('./assets/", "url('/assets/", "url('assets/"):
        html = html.replace(pre, "url('%s/assets/" % TOKEN)
    for pre in ('url("./assets/', 'url("/assets/', 'url("assets/'):
        html = html.replace(pre, 'url("%s/assets/' % TOKEN)
    return html

def html_widget(markup):
    return {"id": nid(), "elType": "widget", "widgetType": "html",
            "settings": {"html": url_clean(rewrite_assets(markup))}, "elements": []}

def full_container(child):
    s = {"content_width": "full", "width": {"unit": "%", "size": 100, "sizes": []},
         "padding": {"unit":"px","top":"0","right":"0","bottom":"0","left":"0","isLinked":True},
         "margin": {"unit":"px","top":"0","right":"0","bottom":"0","left":"0","isLinked":True},
         "flex_gap": {"unit":"px","size":0,"sizes":[],"column":"0","row":"0"}, "flex_direction":"column"}
    return {"id": nid(), "elType": "container", "settings": s, "elements": [child], "isInner": False}

def slug_for(fn):
    base = os.path.basename(fn)[:-5]
    return 'home' if base == 'index' else base

def extract_seo(soup):
    head = soup.head
    title = soup.title.string if soup.title else ''
    metas = []
    for m in head.find_all('meta'):
        name = m.get('name'); prop = m.get('property')
        if name in ('description','keywords','robots','author','theme-color') \
           or (prop and (prop.startswith('og:') or prop.startswith('article:'))) \
           or (name and name.startswith('twitter:')):
            metas.append(str(m))
    canonical = ''
    link = head.find('link', rel='canonical')
    if link: canonical = url_clean(link.get('href',''))
    metas = [url_clean(m) for m in metas]
    jsonld = [url_clean(str(s)) for s in head.find_all('script', type='application/ld+json')]
    return {"title": title, "metas": metas, "canonical": canonical, "jsonld": jsonld}

manifest={}; seo_map={}; order=[]
for path in sorted(glob.glob(os.path.join(SRC, "*.html"))):
    slug = slug_for(path)
    soup = BeautifulSoup(open(path, encoding='utf-8').read(), 'lxml')
    seo_map[slug] = extract_seo(soup)
    content=[]
    body=soup.body
    for child in body.find_all(recursive=False):
        if child.name in ('script','noscript'): continue
        if child.name == 'main':
            secs=child.find_all(recursive=False)
            if secs:
                for sec in secs: content.append(full_container(html_widget(str(sec))))
            else: content.append(full_container(html_widget(child.decode_contents())))
        else:
            content.append(full_container(html_widget(str(child))))
    doc={"content":content,"page_settings":{"hide_title":"yes"},"version":"0.4",
         "title":(seo_map[slug]['title'] or slug),"type":"page"}
    open(os.path.join(TPL, slug+".json"),"w",encoding='utf-8').write(json.dumps(doc))
    manifest[slug]={"title":seo_map[slug]['title'],"source":os.path.basename(path)}
    order.append(slug)

json.dump({"order":order,"pages":manifest}, open(os.path.join(OUT,"data","manifest.json"),"w"))
open(os.path.join(OUT,"data","seo.json"),"w",encoding='utf-8').write(json.dumps(seo_map,ensure_ascii=False))
for extra in ROOT_FILES:
    p=os.path.join(SRC, extra)
    if os.path.exists(p): shutil.copy(p, os.path.join(OUT,"data",extra))
dst=os.path.join(OUT,"assets")
if os.path.exists(dst): shutil.rmtree(dst)
shutil.copytree(os.path.join(SRC,"assets"), dst)
print("pages:", len(order))
print("slugs:", order)
print("root files copied:", [f for f in ROOT_FILES if os.path.exists(os.path.join(OUT,'data',f))])
