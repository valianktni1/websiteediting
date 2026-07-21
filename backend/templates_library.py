"""Extra built-in page templates (Gallery, Pricing, Services, FAQ, About, Contact,
Testimonials). All self-contained: namespaced .ivt-* classes (won't clash with a host
site's CSS) and tokenised with var(--brand-*) so they adopt each site's accent colour
+ fonts. Headings, sub-headings, paragraphs, buttons and captions are all click-to-edit;
photos use the editor's Replace / + Add photos machinery. Repeatable items carry
data-block so a whole card/photo can be duplicated, moved or deleted in the editor."""

# ---------- shared base (typography, buttons, layout, lightbox, faq) ----------
IVT_BASE = """
.ivt{--acc:var(--brand-accent,#c19a5b);--accd:var(--brand-accent-dark,#a07f42);--onacc:var(--brand-on-accent,#ffffff);--hf:var(--brand-heading,'Sora','Segoe UI',sans-serif);--bf:var(--brand-body,'Manrope','Segoe UI',sans-serif);--ink:#17191d;--muted:#5c6470;--line:#e6e3dd;--surface:#ffffff;--soft:#f6f4ef;--dark:#14161a;color:var(--ink);font-family:var(--bf);line-height:1.65}
.ivt *{box-sizing:border-box}
.ivt img{display:block;max-width:100%}
.ivt-wrap{max-width:1160px;margin:0 auto;padding:0 6%}
.ivt-sec{padding:76px 0}
.ivt-sec.soft{background:var(--soft)}
.ivt h1,.ivt h2,.ivt h3,.ivt h4{font-family:var(--hf);font-weight:700;line-height:1.14;margin:0;color:var(--ink)}
.ivt-eyebrow{display:inline-block;font-family:var(--hf);font-size:.72rem;font-weight:600;letter-spacing:.2em;text-transform:uppercase;color:var(--acc);margin-bottom:12px}
.ivt-head{max-width:700px;margin-bottom:46px}
.ivt-head.center{margin-left:auto;margin-right:auto;text-align:center}
.ivt-head h2{font-size:clamp(1.8rem,3.4vw,2.6rem)}
.ivt-lead{color:var(--muted);font-size:1.06rem;margin:14px 0 0}
.ivt-btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;font-family:var(--hf);font-weight:600;font-size:.95rem;padding:13px 26px;border-radius:10px;border:1.5px solid transparent;cursor:pointer;text-decoration:none;transition:transform .15s ease,background-color .15s,color .15s,border-color .15s}
.ivt-btn-solid{background:var(--acc);color:var(--onacc);border-color:var(--acc)}
.ivt-btn-solid:hover{background:var(--accd);border-color:var(--accd);transform:translateY(-2px)}
.ivt-btn-line{background:transparent;color:var(--ink);border-color:var(--line)}
.ivt-btn-line:hover{border-color:var(--acc);color:var(--acc);transform:translateY(-2px)}
.ivt-ctas{display:flex;gap:14px;flex-wrap:wrap;margin-top:26px}
/* lightbox (max ~640px, mobile-first) */
.ivt-lb{position:fixed;inset:0;background:rgba(15,14,12,.93);z-index:99999;display:none;align-items:center;justify-content:center;padding:22px}
.ivt-lb.on{display:flex}
.ivt-lb img{max-width:640px;width:100%;max-height:82vh;object-fit:contain;border-radius:8px;box-shadow:0 22px 60px rgba(0,0,0,.55)}
.ivt-lb-x{position:absolute;top:16px;right:20px;background:none;border:none;color:#fff;font-size:2.3rem;line-height:1;cursor:pointer;opacity:.85}
.ivt-lb-x:hover{opacity:1}
.ivt-lb-nav{position:absolute;top:50%;transform:translateY(-50%);background:rgba(255,255,255,.12);border:none;color:#fff;font-size:1.9rem;width:46px;height:46px;border-radius:50%;cursor:pointer;opacity:.85}
.ivt-lb-nav:hover{opacity:1;background:rgba(255,255,255,.22)}
.ivt-lb-prev{left:14px}.ivt-lb-next{right:14px}
@media(max-width:640px){.ivt-lb-nav{width:40px;height:40px;font-size:1.5rem}}
"""

IVT_JS = """
(function(){
 function lightbox(root){
  var imgs=[].slice.call(root.querySelectorAll('.ivt-gallery img'));
  if(!imgs.length)return;
  var ov=document.createElement('div');ov.className='ivt-lb';
  ov.innerHTML='<button class="ivt-lb-x" type="button" aria-label="Close">&times;</button><button class="ivt-lb-nav ivt-lb-prev" type="button" aria-label="Previous">&#8249;</button><img alt=""><button class="ivt-lb-nav ivt-lb-next" type="button" aria-label="Next">&#8250;</button>';
  document.body.appendChild(ov);var big=ov.querySelector('img');var cur=0;
  function show(i){cur=(i+imgs.length)%imgs.length;big.src=imgs[cur].currentSrc||imgs[cur].src;}
  function open(i){show(i);ov.classList.add('on');document.body.style.overflow='hidden';}
  function close(){ov.classList.remove('on');document.body.style.overflow='';}
  imgs.forEach(function(im,i){im.style.cursor='zoom-in';im.addEventListener('click',function(){if(window.self!==window.top)return;open(i);});});
  ov.querySelector('.ivt-lb-x').addEventListener('click',close);
  ov.querySelector('.ivt-lb-prev').addEventListener('click',function(e){e.stopPropagation();show(cur-1);});
  ov.querySelector('.ivt-lb-next').addEventListener('click',function(e){e.stopPropagation();show(cur+1);});
  ov.addEventListener('click',function(e){if(e.target===ov)close();});
  document.addEventListener('keydown',function(e){if(!ov.classList.contains('on'))return;if(e.key==='Escape')close();if(e.key==='ArrowLeft')show(cur-1);if(e.key==='ArrowRight')show(cur+1);});
 }
 function faq(root){
  var items=[].slice.call(root.querySelectorAll('.ivt-faq-item'));if(!items.length)return;
  var inEditor=(window.self!==window.top);
  items.forEach(function(it){var q=it.querySelector('.ivt-faq-q');if(!q)return;
   if(!inEditor)it.classList.remove('on');
   q.addEventListener('click',function(){if(inEditor)return;it.classList.toggle('on');});
  });
 }
 function init(){document.querySelectorAll('.ivt').forEach(function(r){lightbox(r);faq(r);});}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
"""

_G = ["https://images.unsplash.com/photo-1519741497674-611481863552?auto=format&fit=crop&w=900&q=80",
      "https://images.unsplash.com/photo-1520854221256-17451cc331bf?auto=format&fit=crop&w=900&q=80",
      "https://images.unsplash.com/photo-1511285560929-80b456fea0bc?auto=format&fit=crop&w=900&q=80",
      "https://images.unsplash.com/photo-1465495976277-4387d4b0b4c6?auto=format&fit=crop&w=900&q=80",
      "https://images.unsplash.com/photo-1522673607200-164d1b6ce486?auto=format&fit=crop&w=900&q=80",
      "https://images.unsplash.com/photo-1519225421980-715cb0215aed?auto=format&fit=crop&w=900&q=80",
      "https://images.unsplash.com/photo-1460978812857-470ed1c77af0?auto=format&fit=crop&w=900&q=80",
      "https://images.unsplash.com/photo-1537633552985-df8429e8048b?auto=format&fit=crop&w=900&q=80",
      "https://images.unsplash.com/photo-1583939003579-730e3918a45a?auto=format&fit=crop&w=900&q=80"]

# ---------------- 1. GALLERY ----------------
GALLERY_CSS = IVT_BASE + """
.ivt-gal-hero{text-align:center;padding-top:84px}
.ivt-gallery{column-count:3;column-gap:16px;margin-top:8px}
.ivt-ph{break-inside:avoid;margin:0 0 16px;position:relative;overflow:hidden;border-radius:12px;background:var(--soft)}
.ivt-ph img{width:100%;transition:transform .6s ease}
.ivt-ph:hover img{transform:scale(1.05)}
.ivt-ph figcaption{font-size:.85rem;color:var(--muted);padding:8px 4px 2px;font-style:italic}
@media(max-width:900px){.ivt-gallery{column-count:2}}
@media(max-width:560px){.ivt-gallery{column-count:1}}
"""
def _ph(u, cap, i):
    lazy = "" if i < 3 else ' loading="lazy"'
    return f'<figure class="ivt-ph" data-block="photo"><img{lazy} src="{u}" alt="Gallery photo {i+1}"><figcaption>{cap}</figcaption></figure>'
GALLERY_HTML = f"""
<div class="ivt ivt-gallery-tpl">
  <section class="ivt-sec ivt-gal-hero">
    <div class="ivt-wrap">
      <span class="ivt-eyebrow">Our Work</span>
      <h1>A gallery of moments</h1>
      <p class="ivt-lead" style="margin-left:auto;margin-right:auto;max-width:600px">A hand-picked selection of our favourite photographs. Tap any image to see it larger.</p>
    </div>
  </section>
  <section class="ivt-sec" style="padding-top:0">
    <div class="ivt-wrap">
      <div class="ivt-gallery">
        {_ph(_G[0],"Add a caption",0)}{_ph(_G[1],"Add a caption",1)}{_ph(_G[2],"Add a caption",2)}
        {_ph(_G[3],"Add a caption",3)}{_ph(_G[4],"Add a caption",4)}{_ph(_G[5],"Add a caption",5)}
        {_ph(_G[6],"Add a caption",6)}{_ph(_G[7],"Add a caption",7)}{_ph(_G[8],"Add a caption",8)}
      </div>
    </div>
  </section>
</div>
"""

# ---------------- 2. PRICING ----------------
PRICING_CSS = IVT_BASE + """
.ivt-price-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:26px;align-items:stretch}
.ivt-price{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:38px 32px;display:flex;flex-direction:column;transition:transform .18s ease,box-shadow .18s ease}
.ivt-price:hover{transform:translateY(-6px);box-shadow:0 22px 44px -26px rgba(0,0,0,.4)}
.ivt-price.feat{border-color:var(--acc);position:relative}
.ivt-price.feat::before{content:"Most popular";position:absolute;top:-13px;left:50%;transform:translateX(-50%);background:var(--acc);color:var(--onacc);font-family:var(--hf);font-size:.66rem;font-weight:600;letter-spacing:.14em;text-transform:uppercase;padding:6px 15px;border-radius:999px}
.ivt-price-name{font-size:1.35rem}
.ivt-price-amt{font-family:var(--hf);font-weight:700;font-size:2.6rem;color:var(--acc);margin:14px 0 2px}
.ivt-price-amt small{font-size:.9rem;color:var(--muted);font-weight:500}
.ivt-price-desc{color:var(--muted);font-size:.92rem;margin-bottom:8px}
.ivt-price ul{list-style:none;padding:20px 0;margin:0;border-top:1px solid var(--line);flex:1}
.ivt-price li{position:relative;padding:8px 0 8px 26px;font-size:.92rem;color:#3b424d}
.ivt-price li::before{content:"";position:absolute;left:0;top:14px;width:9px;height:9px;border:2px solid var(--acc);border-top:0;border-right:0;transform:rotate(-45deg)}
.ivt-price .ivt-btn{width:100%;margin-top:8px}
@media(max-width:860px){.ivt-price-grid{grid-template-columns:1fr}}
"""
def _tier(name, amt, per, desc, feats, feat=False):
    lis = "".join(f"<li>{f}</li>" for f in feats)
    cls = "ivt-price feat" if feat else "ivt-price"
    btn = "ivt-btn ivt-btn-solid" if feat else "ivt-btn ivt-btn-line"
    return f'<div class="{cls}" data-block="tier"><h3 class="ivt-price-name">{name}</h3><div class="ivt-price-amt">{amt}<small> {per}</small></div><p class="ivt-price-desc">{desc}</p><ul>{lis}</ul><a class="{btn}" href="#contact">Get started</a></div>'
PRICING_HTML = f"""
<div class="ivt ivt-pricing-tpl">
  <section class="ivt-sec">
    <div class="ivt-wrap">
      <div class="ivt-head center"><span class="ivt-eyebrow">Pricing</span><h2>Simple, honest pricing</h2><p class="ivt-lead">Choose the option that suits you best. No hidden fees, cancel any time.</p></div>
      <div class="ivt-price-grid">
        {_tier("Starter","&pound;29","/month","Perfect for getting going.",["Everything to get started","Up to 3 projects","Email support","Cancel any time"])}
        {_tier("Professional","&pound;59","/month","Our most popular option.",["Everything in Starter","Unlimited projects","Priority support","Advanced features","Monthly review"],feat=True)}
        {_tier("Premium","&pound;99","/month","For those who want it all.",["Everything in Professional","Dedicated account manager","Custom onboarding","Phone support"])}
      </div>
    </div>
  </section>
</div>
"""

# ---------------- 3. SERVICES ----------------
SERVICES_CSS = IVT_BASE + """
.ivt-serv-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:24px}
.ivt-serv{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:32px 28px;transition:transform .18s ease,box-shadow .18s ease}
.ivt-serv:hover{transform:translateY(-5px);box-shadow:0 20px 40px -26px rgba(0,0,0,.4)}
.ivt-serv-ico{width:52px;height:52px;border-radius:12px;background:color-mix(in srgb,var(--acc) 14%,#fff);display:flex;align-items:center;justify-content:center;margin-bottom:18px;font-family:var(--hf);font-weight:700;color:var(--acc);font-size:1.3rem}
.ivt-serv h3{font-size:1.2rem;margin-bottom:8px}
.ivt-serv p{color:var(--muted);font-size:.94rem;margin:0 0 14px}
.ivt-serv a{font-family:var(--hf);font-weight:600;font-size:.88rem;color:var(--acc);text-decoration:none}
@media(max-width:860px){.ivt-serv-grid{grid-template-columns:1fr 1fr}}
@media(max-width:560px){.ivt-serv-grid{grid-template-columns:1fr}}
"""
def _serv(ico, name, desc):
    return f'<div class="ivt-serv" data-block="service"><div class="ivt-serv-ico">{ico}</div><h3>{name}</h3><p>{desc}</p><a href="#contact">Learn more &rsaquo;</a></div>'
SERVICES_HTML = f"""
<div class="ivt ivt-services-tpl">
  <section class="ivt-sec">
    <div class="ivt-wrap">
      <div class="ivt-head center"><span class="ivt-eyebrow">What we do</span><h2>Our services</h2><p class="ivt-lead">Everything we offer, in one place &mdash; delivered with care and attention to detail.</p></div>
      <div class="ivt-serv-grid">
        {_serv("01","First service","A clear description of this service and the value it brings to your customers.")}
        {_serv("02","Second service","A clear description of this service and the value it brings to your customers.")}
        {_serv("03","Third service","A clear description of this service and the value it brings to your customers.")}
        {_serv("04","Fourth service","A clear description of this service and the value it brings to your customers.")}
        {_serv("05","Fifth service","A clear description of this service and the value it brings to your customers.")}
        {_serv("06","Sixth service","A clear description of this service and the value it brings to your customers.")}
      </div>
    </div>
  </section>
</div>
"""

# ---------------- 4. FAQ ----------------
FAQ_CSS = IVT_BASE + """
.ivt-faq-list{max-width:820px;margin:0 auto}
.ivt-faq-item{border:1px solid var(--line);border-radius:12px;margin-bottom:14px;background:var(--surface);overflow:hidden}
.ivt-faq-q{width:100%;display:flex;justify-content:space-between;align-items:center;gap:16px;padding:20px 24px;cursor:pointer}
.ivt-faq-q h3{font-size:1.05rem}
.ivt-faq-q::after{content:"+";font-family:var(--hf);font-size:1.5rem;color:var(--acc);flex:none;transition:transform .3s ease}
.ivt-faq-item.on .ivt-faq-q::after{transform:rotate(45deg)}
.ivt-faq-a{max-height:0;overflow:hidden;transition:max-height .35s ease}
.ivt-faq-item.on .ivt-faq-a{max-height:400px}
.ivt-faq-a p{color:var(--muted);padding:0 24px 22px;margin:0;font-size:.96rem}
"""
def _faq(q, a):
    return f'<div class="ivt-faq-item on" data-block="faq"><div class="ivt-faq-q"><h3>{q}</h3></div><div class="ivt-faq-a"><p>{a}</p></div></div>'
FAQ_HTML = f"""
<div class="ivt ivt-faq-tpl">
  <section class="ivt-sec">
    <div class="ivt-wrap">
      <div class="ivt-head center"><span class="ivt-eyebrow">FAQs</span><h2>Frequently asked questions</h2><p class="ivt-lead">Everything you might want to know. Can&rsquo;t find your answer? Just get in touch.</p></div>
      <div class="ivt-faq-list">
        {_faq("What areas do you cover?","Replace this with your answer. Give a clear, friendly response that reassures the reader and covers the common details they&rsquo;re looking for.")}
        {_faq("How do I book?","Replace this with your answer. Give a clear, friendly response that reassures the reader and covers the common details they&rsquo;re looking for.")}
        {_faq("What does it cost?","Replace this with your answer. Give a clear, friendly response that reassures the reader and covers the common details they&rsquo;re looking for.")}
        {_faq("How long does it take?","Replace this with your answer. Give a clear, friendly response that reassures the reader and covers the common details they&rsquo;re looking for.")}
        {_faq("Do you offer a guarantee?","Replace this with your answer. Give a clear, friendly response that reassures the reader and covers the common details they&rsquo;re looking for.")}
      </div>
    </div>
  </section>
</div>
"""

# ---------------- 5. ABOUT ----------------
ABOUT_CSS = IVT_BASE + """
.ivt-about-grid{display:grid;grid-template-columns:1fr 1fr;gap:56px;align-items:center}
.ivt-about-media img{width:100%;height:100%;max-height:520px;object-fit:cover;border-radius:16px}
.ivt-about-copy p{color:var(--muted);margin:16px 0 0}
.ivt-stats{display:flex;gap:40px;flex-wrap:wrap;margin-top:56px;padding-top:40px;border-top:1px solid var(--line)}
.ivt-stat strong{display:block;font-family:var(--hf);font-size:2.2rem;color:var(--acc);line-height:1}
.ivt-stat span{color:var(--muted);font-size:.9rem}
@media(max-width:860px){.ivt-about-grid{grid-template-columns:1fr;gap:34px}}
"""
ABOUT_HTML = f"""
<div class="ivt ivt-about-tpl">
  <section class="ivt-sec">
    <div class="ivt-wrap">
      <div class="ivt-about-grid">
        <div class="ivt-about-media"><img src="https://images.unsplash.com/photo-1521737604893-d14cc237f11d?auto=format&fit=crop&w=1000&q=80" alt="Our team at work"></div>
        <div class="ivt-about-copy">
          <span class="ivt-eyebrow">Our story</span>
          <h2>People who genuinely care</h2>
          <p>Tell your story here. Where you started, what drives you, and why customers trust you. Keep it warm and personal &mdash; this is the paragraph that turns a visitor into a customer.</p>
          <p>Add a second paragraph about your values, your team, or a milestone you&rsquo;re proud of. A little personality goes a long way.</p>
          <div class="ivt-ctas"><a class="ivt-btn ivt-btn-solid" href="#contact">Work with us</a></div>
        </div>
      </div>
      <div class="ivt-stats">
        <div class="ivt-stat"><strong>10+</strong><span>Years&rsquo; experience</span></div>
        <div class="ivt-stat"><strong>500+</strong><span>Happy customers</span></div>
        <div class="ivt-stat"><strong>5&#9733;</strong><span>Average rating</span></div>
      </div>
    </div>
  </section>
</div>
"""

# ---------------- 6. CONTACT ----------------
CONTACT_CSS = IVT_BASE + """
.ivt-contact-grid{display:grid;grid-template-columns:1.1fr .9fr;gap:56px;align-items:start}
.ivt-cf label{display:block;font-family:var(--hf);font-size:.74rem;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);margin:18px 0 6px}
.ivt-cf input,.ivt-cf textarea{width:100%;border:1px solid var(--line);border-radius:10px;padding:12px 14px;font-family:var(--bf);font-size:1rem;color:var(--ink);background:var(--surface)}
.ivt-cf input:focus,.ivt-cf textarea:focus{outline:none;border-color:var(--acc)}
.ivt-cf .ivt-btn{margin-top:22px}
.ivt-cinfo{background:var(--soft);border-radius:16px;padding:34px}
.ivt-cinfo .blk{padding:16px 0;border-bottom:1px solid var(--line)}
.ivt-cinfo .blk:last-child{border-bottom:none}
.ivt-cinfo h4{font-family:var(--hf);font-size:.74rem;letter-spacing:.08em;text-transform:uppercase;color:var(--acc);margin-bottom:6px}
.ivt-cinfo p{margin:0;font-size:1.05rem}
@media(max-width:860px){.ivt-contact-grid{grid-template-columns:1fr;gap:34px}}
"""
CONTACT_HTML = f"""
<div class="ivt ivt-contact-tpl">
  <section class="ivt-sec">
    <div class="ivt-wrap">
      <div class="ivt-head center"><span class="ivt-eyebrow">Get in touch</span><h2>We&rsquo;d love to hear from you</h2><p class="ivt-lead">Send us a message and we&rsquo;ll get back to you as soon as we can.</p></div>
      <div class="ivt-contact-grid">
        <form class="ivt-cf" onsubmit="event.preventDefault();var f=this;window.location.href='mailto:sales@yourgarage.co.uk?subject='+encodeURIComponent('Website enquiry from '+(f.name.value||''))+'&body='+encodeURIComponent('Name: '+f.name.value+'\\nEmail: '+f.email.value+'\\nPhone: '+f.phone.value+'\\n\\n'+f.message.value);">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
            <div><label>Your name</label><input name="name" required></div>
            <div><label>Email</label><input type="email" name="email" required></div>
          </div>
          <label>Phone</label><input name="phone">
          <label>Message</label><textarea name="message" rows="5"></textarea>
          <button type="submit" class="ivt-btn ivt-btn-solid">Send message</button>
        </form>
        <div class="ivt-cinfo">
          <div class="blk"><h4>Phone</h4><p>01234 567 890</p></div>
          <div class="blk"><h4>Email</h4><p>hello@yourbusiness.co.uk</p></div>
          <div class="blk"><h4>Where to find us</h4><p>123 Example Street, Your Town, AB1 2CD</p></div>
          <div class="blk"><h4>Opening hours</h4><p>Mon&ndash;Fri: 9am&ndash;5pm<br>Sat: 9am&ndash;1pm<br>Sun: Closed</p></div>
        </div>
      </div>
    </div>
  </section>
</div>
"""

# ---------------- 7. TESTIMONIALS ----------------
TESTI_CSS = IVT_BASE + """
.ivt-testi-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:24px}
.ivt-testi{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:32px 28px;display:flex;flex-direction:column}
.ivt-testi .stars{color:var(--acc);letter-spacing:.15em;margin-bottom:14px}
.ivt-testi blockquote{margin:0;font-size:1.02rem;line-height:1.6;color:#3b424d;flex:1}
.ivt-testi .who{margin-top:20px;font-family:var(--hf);font-weight:600;font-size:.92rem}
.ivt-testi .who span{display:block;color:var(--muted);font-weight:500;font-size:.82rem}
@media(max-width:860px){.ivt-testi-grid{grid-template-columns:1fr}}
"""
def _testi(quote, who, role):
    return f'<div class="ivt-testi" data-block="review"><div class="stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div><blockquote>&ldquo;{quote}&rdquo;</blockquote><div class="who">{who}<span>{role}</span></div></div>'
TESTI_HTML = f"""
<div class="ivt ivt-testi-tpl">
  <section class="ivt-sec soft">
    <div class="ivt-wrap">
      <div class="ivt-head center"><span class="ivt-eyebrow">Reviews</span><h2>What our customers say</h2><p class="ivt-lead">Don&rsquo;t just take our word for it &mdash; here&rsquo;s what people think of us.</p></div>
      <div class="ivt-testi-grid">
        {_testi("Replace with a real review. Genuine, specific customer words build far more trust than anything you could write about yourself.","Jane D.","Verified customer")}
        {_testi("Replace with a real review. Genuine, specific customer words build far more trust than anything you could write about yourself.","Mark T.","Verified customer")}
        {_testi("Replace with a real review. Genuine, specific customer words build far more trust than anything you could write about yourself.","Sarah L.","Verified customer")}
      </div>
    </div>
  </section>
</div>
"""

LIBRARY_TEMPLATES = [
    {"key": "gallery", "name": "Image Gallery", "js": IVT_JS, "css": GALLERY_CSS, "sections_html": GALLERY_HTML,
     "description": "A photo gallery (weddings, portfolios, projects) with an editable title, sub-heading and intro, a masonry grid and a tap-to-enlarge lightbox. Use Replace or '+ Add photos' on any image; each photo can be duplicated, moved or removed."},
    {"key": "pricing", "name": "Pricing", "js": "", "css": PRICING_CSS, "sections_html": PRICING_HTML,
     "description": "Three editable pricing tiers with feature lists and buttons. Duplicate or remove a tier in the editor; every price, feature and label is click-to-edit."},
    {"key": "services", "name": "Services", "js": "", "css": SERVICES_CSS, "sections_html": SERVICES_HTML,
     "description": "A grid of service cards (number/icon, heading, description, link). Add, duplicate or remove cards; all text is editable."},
    {"key": "faq", "name": "FAQ", "js": IVT_JS, "css": FAQ_CSS, "sections_html": FAQ_HTML,
     "description": "An expandable question-and-answer accordion. Edit each question and answer; add or remove items. Answers open on the live site when clicked."},
    {"key": "about", "name": "About / Our Story", "js": "", "css": ABOUT_CSS, "sections_html": ABOUT_HTML,
     "description": "An about section: an image beside your story, plus an editable stats strip. Replace the photo and rewrite the copy to tell your story."},
    {"key": "contact", "name": "Contact", "js": "", "css": CONTACT_CSS, "sections_html": CONTACT_HTML,
     "description": "A contact page with an enquiry form (opens the visitor's email app), contact details and opening hours. Set the enquiry email when you add the page."},
    {"key": "testimonials", "name": "Testimonials / Reviews", "js": "", "css": TESTI_CSS, "sections_html": TESTI_HTML,
     "description": "Customer review cards with star ratings. Duplicate or remove cards and edit every quote and name."},
]
