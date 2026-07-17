import os, re, json, random
from bs4 import BeautifulSoup

SRC = "/app/wpbuild/src/ivory-digital-website"

# ---- design tokens ----
GOLD="#A78C46"; GOLD_D="#977937"; CHAR="#2E332B"; INK="#3C4237"; TAUPE="#79806E"
SAGE="#8A9A7B"; IVORY="#F8F7F1"; IVORY2="#EEF1E7"; WHITE="#ffffff"; LINE="#DEE3D3"
CREAM="#F1E9CF"
HEAD="Cormorant Garamond"; BODY="Jost"
SHADOW={"horizontal":0,"vertical":8,"blur":24,"spread":-14,"color":"rgba(52,60,44,0.35)"}

def nid(): return ''.join(random.choice('0123456789abcdef') for _ in range(7))

def dim(t,r,b,l,u="px"): return {"unit":u,"top":str(t),"right":str(r),"bottom":str(b),"left":str(l),"isLinked":False}
def sz(v,u="px"): return {"unit":u,"size":v,"sizes":[]}

def typo(pfx,fam,size,wt,lh=None,ls=None,tt=None):
    d={pfx+"_typography":"custom",pfx+"_font_family":fam,pfx+"_font_size":sz(size),pfx+"_font_weight":str(wt)}
    if lh is not None: d[pfx+"_line_height"]=sz(lh,"em")
    if ls is not None: d[pfx+"_letter_spacing"]=sz(ls)
    if tt: d[pfx+"_text_transform"]=tt
    return d

def W(t,s): return {"id":nid(),"elType":"widget","widgetType":t,"settings":s,"elements":[]}
def C(s,els,inner=True): return {"id":nid(),"elType":"container","settings":s,"elements":els,"isInner":inner}

def eyebrow(text,color=GOLD,align="left"):
    s={"title":text,"header_size":"div","align":align,"title_color":color,"_margin":dim(0,0,14,0)}
    s.update(typo("typography",BODY,12,500,1.4,3.5,"uppercase")); return W("heading",s)

def heading(text,tag="h2",align="left",color=CHAR,size=40,wt=500,lh=1.12,mb=0):
    s={"title":text,"header_size":tag,"align":align,"title_color":color}
    s.update(typo("typography",HEAD,size,wt,lh))
    if mb: s["_margin"]=dim(0,0,mb,0)
    return W("heading",s)

def rule(align="left",color=GOLD):
    s={"color":color,"weight":sz(1),"width":sz(64),"align":align,"gap":sz(18)}
    s["_margin"]=dim(16,0,16,0); return W("divider",s)

def text(html,align="left",color=INK,size=18,lh=1.7,maxw=None,wt=400):
    s={"editor":html if html.strip().startswith("<") else "<p>%s</p>"%html,"align":align,"text_color":color}
    s.update(typo("typography",BODY,size,wt,lh))
    if maxw: s["_element_custom_width"]=sz(maxw); # not critical
    return W("text-editor",s)

def button(txt,url="#",kind="outline",align="left"):
    s={"text":txt,"link":{"url":url,"is_external":"","nofollow":""},"align":align,
       "border_border":"solid","border_width":dim(1,1,1,1),"border_radius":dim(0,0,0,0),
       "text_padding":dim(15,34,15,34),"hover_animation":""}
    s.update(typo("typography",BODY,12,500,None,2.4,"uppercase"))
    if kind=="gold":
        s.update({"background_color":GOLD,"button_text_color":WHITE,"border_color":GOLD,
                  "button_background_hover_color":GOLD_D,"button_hover_color":WHITE,"button_hover_border_color":GOLD_D})
    elif kind=="light":
        s.update({"background_color":"rgba(0,0,0,0)","button_text_color":WHITE,"border_color":"rgba(255,255,255,0.7)",
                  "button_background_hover_color":WHITE,"button_hover_color":CHAR,"button_hover_border_color":WHITE})
    else:
        s.update({"background_color":"rgba(0,0,0,0)","button_text_color":CHAR,"border_color":CHAR,
                  "button_background_hover_color":CHAR,"button_hover_color":IVORY,"button_hover_border_color":CHAR})
    return W("button",s)

def icon(fa,color=GOLD):
    return W("icon",{"selected_icon":{"value":fa,"library":"fa-solid"},"primary_color":color,
                     "size":sz(34),"align":"left","_margin":dim(0,0,12,0)})

ICONMAP=[("logo","fas fa-palette"),("colour","fas fa-palette"),("color","fas fa-palette"),
         ("photo","fas fa-camera"),("web","fas fa-globe"),("address","fas fa-globe"),
         ("domain","fas fa-globe"),("enquir","fas fa-calendar-check"),("book","fas fa-calendar-check"),
         ("slot","fas fa-bell"),("remind","fas fa-bell"),("yours","fas fa-heart"),("truly","fas fa-heart")]
def pick_icon(title):
    t=title.lower()
    for k,v in ICONMAP:
        if k in t: return v
    return "fas fa-star"

def row(children,justify="flex-start",gap=14,wrap="wrap",mt=26):
    s={"content_width":"full","flex_direction":"row","flex_wrap":wrap,"flex_justify_content":justify,
       "flex_gap":{"unit":"px","size":gap,"sizes":[],"column":str(gap),"row":str(gap)},
       "width":sz(100,"%"),"padding":dim(0,0,0,0)}
    if mt: s["margin"]=dim(mt,0,0,0)
    return C(s,children)

def card(children,pad=(30,28)):
    s={"content_width":"full","flex_direction":"column","background_background":"classic","background_color":WHITE,
       "border_border":"solid","border_width":dim(1,1,1,1),"border_color":LINE,
       "box_shadow_box_shadow_type":"yes","box_shadow_box_shadow":SHADOW,
       "padding":dim(pad[0],pad[1],pad[0],pad[1]),"width":sz(31,"%"),
       "flex_gap":{"unit":"px","size":6,"sizes":[],"column":"6","row":"6"}}
    return C(s,children)

def card_grid(cards,center=False):
    s={"content_width":"boxed","flex_direction":"row","flex_wrap":"wrap",
       "flex_justify_content":"center" if center else "flex-start",
       "flex_gap":{"unit":"px","size":26,"sizes":[],"column":"26","row":"26"},
       "padding":dim(0,0,0,0)}
    return C(s,cards)

def accordion(items):
    tabs=[]
    for q,a in items:
        tabs.append({"tab_title":q,"tab_content":"<p>%s</p>"%a,"_id":nid()})
    s={"tabs":tabs,"title_color":CHAR,"tab_active_color":GOLD,"content_color":TAUPE}
    s.update(typo("title_typography",HEAD,20,500))
    s.update(typo("content_typography",BODY,15.5,400,1.7))
    return W("accordion",s)

# ---- section builders ----
def sub_boxed(children,center=False,maxw=None,mb=0):
    s={"content_width":"boxed","flex_direction":"column",
       "flex_align_items":"center" if center else "flex-start",
       "flex_gap":{"unit":"px","size":0,"sizes":[],"column":"0","row":"0"},"padding":dim(0,0,0,0)}
    if maxw: s["content_width"]="boxed"; s["boxed_width"]=sz(maxw)
    if mb: s["margin"]=dim(0,0,mb,0)
    return C(s,children)

def section_wrap(children,bg=WHITE,pad_tb=78,gradient=False):
    s={"content_width":"full","flex_direction":"column","flex_align_items":"center",
       "background_background":"gradient" if gradient else "classic",
       "padding":dim(pad_tb,20,pad_tb,20),"flex_gap":{"unit":"px","size":0,"sizes":[],"column":"0","row":"0"}}
    if gradient:
        s.update({"background_color":IVORY2,"background_color_b":IVORY,
                  "background_gradient_angle":{"unit":"deg","size":180,"sizes":[]},"background_gradient_type":"linear"})
    else:
        s["background_color"]=bg
    return C(s,children,inner=False)

def blocks_from_container(cont, align, dark=False):
    """Convert simple content blocks (eyebrow/h/gold-rule/p/btn-row) to widgets.
    dark=True only for the sage CTA band (white text)."""
    out=[]; buttons=[]
    for el in cont.find_all(recursive=False):
        cls=' '.join(el.get('class',[]))
        if el.name=='span' and 'eyebrow' in cls:
            out.append(eyebrow(el.get_text(' ',strip=True), CREAM if dark else GOLD, align))
        elif el.name=='span' and 'gold-rule' in cls:
            out.append(rule(align, CREAM if dark else GOLD))
        elif el.name in('h1','h2','h3','h4'):
            tag=el.name
            size={'h1':54,'h2':40,'h3':21,'h4':20}[tag]
            out.append(heading(el.decode_contents().strip(),tag,align,
                               (WHITE if dark else CHAR),size,500,1.12,10))
        elif el.name=='p':
            lead='lead' in cls
            out.append(text(el.decode_contents().strip(),align,
                            ("rgba(255,255,255,0.9)" if dark else (INK if lead else TAUPE)),
                            18 if lead else 16,1.7))
        elif el.name=='div' and 'btn-row' in cls:
            for a in el.find_all('a'):
                acls=' '.join(a.get('class',[]))
                kind='gold' if 'btn-gold' in acls else ('light' if 'btn-light' in acls else 'outline')
                buttons.append(button(a.get_text(' ',strip=True), a.get('href','#'), kind, align))
    if buttons:
        out.append(row(buttons, "center" if align=="center" else "flex-start"))
    return out

def html_block(markup):
    m=markup.replace('="/assets/','="__IVORY_BASE__/assets/').replace('="assets/','="__IVORY_BASE__/assets/')
    w={"id":nid(),"elType":"widget","widgetType":"html","settings":{"html":m},"elements":[]}
    s={"content_width":"full","width":sz(100,"%"),"padding":dim(0,0,0,0),"margin":dim(0,0,0,0),
       "flex_gap":{"unit":"px","size":0,"sizes":[],"column":"0","row":"0"},"flex_direction":"column"}
    return {"id":nid(),"elType":"container","settings":s,"elements":[w],"isInner":False}

PLAIN_OK = {'span','h1','h2','h3','h4','p','div'}
def container_is_native(cont):
    ccls=cont.get('class') or []
    if 'grid' in ccls:
        return all('card' in (c.get('class') or []) for c in cont.find_all(recursive=False))
    if 'faq' in ccls or 'section-head' in ccls:
        return True
    # plain content container: only eyebrow/headings/gold-rule/lead/btn-row, no images/forms
    if cont.find('img') or cont.find('form') or cont.find('iframe'):
        return False
    for el in cont.find_all(recursive=False):
        cls=' '.join(el.get('class',[]))
        if el.name in ('h1','h2','h3','h4'): continue
        if el.name=='span' and ('eyebrow' in cls or 'gold-rule' in cls): continue
        if el.name=='p': continue
        if el.name=='div' and 'btn-row' in cls: continue
        return False
    return True

def convert_section(sec):
    cls=sec.get('class') or []
    band = 'band-ivory2' in cls
    # complex layouts we don't yet map natively -> keep exact (still perfect, edit via HTML)
    complex_cls = {'steps','showcase','plans','contact-grid','reviews','logos','gallery','screens'}
    if sec.find('img') or (set(cls) & complex_cls) or sec.select_one('.steps,.showcase,.plans,.contact-grid,.reviews,.hero-grid,form'):
        return html_block(str(sec))
    if 'cta-band' in cls:
        cont=sec.find(recursive=False)
        widgets=blocks_from_container(cont,"center",dark=True)
        return section_wrap([sub_boxed(widgets,center=True,maxw=640)],bg=SAGE,pad_tb=70)
    if 'page-hero' in cls:
        cont=sec.find(recursive=False)
        widgets=blocks_from_container(cont,"left")
        w=section_wrap([sub_boxed(widgets,center=False)],gradient=True); w["settings"]["padding"]=dim(72,20,52,20)
        return w
    # generic: every child container must be native, else fall back whole section
    if not all(container_is_native(c) for c in sec.find_all(recursive=False)):
        return html_block(str(sec))
    subs=[]
    for cont in sec.find_all(recursive=False):
        ccls=cont.get('class') or []
        center='center' in ccls
        if 'grid' in ccls:
            cards=[]
            for cd in cont.find_all(recursive=False):
                items=[]
                for el in cd.find_all(recursive=False):
                    if el.name=='svg':
                        title=cd.find(['h3','h4'])
                        items.append(icon(pick_icon(title.get_text() if title else "")))
                    elif el.name in('h3','h4'):
                        items.append(heading(el.decode_contents().strip(),'h3','left',CHAR,21,500,1.15,6))
                    elif el.name=='p':
                        items.append(text(el.decode_contents().strip(),"left",TAUPE,15.5,1.65))
                cards.append(card(items))
            subs.append(card_grid(cards,center))
        elif 'faq' in ccls:
            items=[]
            for d in cont.find_all('details'):
                summ=d.find('summary'); p=d.find('p')
                items.append((summ.get_text(' ',strip=True) if summ else '', p.decode_contents().strip() if p else ''))
            subs.append(sub_boxed([accordion(items)],maxw=820))
        else:
            widgets=blocks_from_container(cont,"center" if center else "left")
            mw=640 if ('section-head' in ccls) else None
            subs.append(sub_boxed(widgets,center=center,maxw=mw,mb=(30 if 'section-head' in ccls else 0)))
    return section_wrap(subs,bg=(IVORY2 if band else WHITE))

def build_page(path):
    soup=BeautifulSoup(open(path,encoding='utf-8').read(),'lxml')
    content=[]
    body=soup.body
    header=soup.find('header'); footer=soup.find('footer'); main=soup.find('main')
    def html_widget(markup):
        m=markup.replace('="/assets/','="__IVORY_BASE__/assets/').replace('="assets/','="__IVORY_BASE__/assets/')
        return {"id":nid(),"elType":"widget","widgetType":"html","settings":{"html":m},"elements":[]}
    def wrap_full(child):
        s={"content_width":"full","width":sz(100,"%"),"padding":dim(0,0,0,0),"margin":dim(0,0,0,0),
           "flex_gap":{"unit":"px","size":0,"sizes":[],"column":"0","row":"0"},"flex_direction":"column"}
        return {"id":nid(),"elType":"container","settings":s,"elements":[child],"isInner":False}
    if header: content.append(wrap_full(html_widget(str(header))))
    if main:
        for sec in main.find_all(recursive=False):
            # breadcrumb stays as small html (has links)
            if 'container' in (sec.get('class') or []) and sec.find(class_='crumbs'):
                content.append(wrap_full(html_widget(str(sec)))); continue
            content.append(convert_section(sec))
    if footer: content.append(wrap_full(html_widget(str(footer))))
    return content

if __name__=="__main__":
    import sys, glob
    def slug_for(fn):
        base=os.path.basename(fn)[:-5]
        return 'home' if base=='index' else base
    def write_page(path):
        content=build_page(path)
        dump=json.dumps({"content":content,"page_settings":{"hide_title":"yes"},"version":"0.4",
                         "title":slug_for(path),"type":"page"})
        dump=dump.replace('/index.html','/'); dump=re.sub(r'/([a-z0-9][a-z0-9-]*)\.html',r'/\1/',dump)
        out="/app/wpbuild/plugin/ivory-digital-elementor/templates/%s.json"%slug_for(path)
        open(out,"w").write(dump)
        # report native vs html-fallback sections
        native=sum(1 for e in content if e['elType']=='container' and any(
            ch.get('widgetType') not in ('html',None) for ch in e.get('elements',[]) ) )
        return slug_for(path), len(content)
    arg=sys.argv[1] if len(sys.argv)>1 else "all"
    if arg=="all":
        for f in sorted(glob.glob(os.path.join(SRC,"*.html"))):
            s,n=write_page(f); print("%-40s %d blocks"%(s,n))
    else:
        write_page(os.path.join(SRC,arg+".html")); print("wrote",arg)
