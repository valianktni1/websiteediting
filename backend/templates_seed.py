"""Built-in page templates. Self-contained: namespaced (uc-) classes so they never
collide with a host site's CSS, and tokenised (var(--brand-*)) so they adopt each
site's accent colour + fonts when added as a page."""

USED_CARS_CSS = """
.uc-tpl{--acc:var(--brand-accent,#d7a24b);--accd:var(--brand-accent-dark,#b8863a);--onacc:var(--brand-on-accent,#1a1205);--hf:var(--brand-heading,'Sora','Segoe UI',sans-serif);--bf:var(--brand-body,'Manrope','Segoe UI',sans-serif);--ink:#14181e;--muted:#5b6472;--line:#e6e8ec;--dark:#0f1114;--surface:#fff;color:var(--ink);font-family:var(--bf);line-height:1.6}
.uc-tpl *{box-sizing:border-box}
.uc-tpl .uc-wrap{max-width:1160px;margin:0 auto;padding:0 6%}
.uc-tpl h1,.uc-tpl h2,.uc-tpl h3,.uc-tpl h4{font-family:var(--hf);font-weight:700;line-height:1.12;margin:0}
.uc-tpl .uc-eyebrow{display:inline-block;font-family:var(--hf);font-size:.72rem;font-weight:600;letter-spacing:.2em;text-transform:uppercase;color:var(--acc);margin-bottom:14px}
.uc-tpl .uc-lead{color:var(--muted);font-size:1.05rem;margin:16px 0 0}
.uc-tpl .uc-btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;font-family:var(--hf);font-weight:600;font-size:.95rem;padding:13px 24px;border-radius:10px;border:1.5px solid transparent;cursor:pointer;text-decoration:none;transition:transform .15s ease,background-color .15s ease,color .15s ease,border-color .15s ease}
.uc-tpl .uc-btn-solid{background:var(--acc);color:var(--onacc);border-color:var(--acc)}
.uc-tpl .uc-btn-solid:hover{background:var(--accd);border-color:var(--accd);transform:translateY(-2px)}
.uc-tpl .uc-btn-line{background:transparent;color:var(--ink);border-color:var(--line)}
.uc-tpl .uc-btn-line:hover{border-color:var(--acc);color:var(--acc);transform:translateY(-2px)}

.uc-tpl .uc-hero{background:var(--dark);color:#fff;padding:76px 0 84px}
.uc-tpl .uc-hero-grid{display:grid;grid-template-columns:1.05fr .95fr;gap:48px;align-items:center}
.uc-tpl .uc-hero h1{font-size:clamp(2.1rem,4.4vw,3.4rem);color:#fff}
.uc-tpl .uc-hero .uc-lead{color:#c8ccd3}
.uc-tpl .uc-hero-cta{display:flex;gap:14px;flex-wrap:wrap;margin-top:28px}
.uc-tpl .uc-hero .uc-btn-line{color:#fff;border-color:rgba(255,255,255,.24)}
.uc-tpl .uc-hero-stats{list-style:none;display:flex;gap:34px;margin:30px 0 0;padding:0;flex-wrap:wrap}
.uc-tpl .uc-hero-stats li{font-size:.9rem;color:#aeb4bd}
.uc-tpl .uc-hero-stats strong{display:block;font-family:var(--hf);color:var(--acc);font-size:1.05rem}
.uc-tpl .uc-hero-media img{width:100%;height:100%;max-height:430px;object-fit:cover;border-radius:16px;border:1px solid rgba(255,255,255,.1)}

.uc-tpl .uc-stock{padding:80px 0;background:#f6f7f9}
.uc-tpl .uc-sec-head{max-width:640px;margin-bottom:40px}
.uc-tpl .uc-sec-head h2{font-size:clamp(1.7rem,3vw,2.4rem)}
.uc-tpl .uc-sec-sub{color:var(--muted);margin-top:12px}
.uc-tpl .uc-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:28px}
.uc-tpl .uc-car{position:relative;background:var(--surface);border:1px solid var(--line);border-radius:16px;overflow:hidden;box-shadow:0 12px 30px -22px rgba(0,0,0,.45);transition:transform .18s ease,box-shadow .18s ease}
.uc-tpl .uc-car:hover{transform:translateY(-4px);box-shadow:0 22px 44px -24px rgba(0,0,0,.5)}
.uc-tpl .uc-slider{position:relative;background:#0b0d10}
.uc-tpl .uc-gallery{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;scrollbar-width:none;aspect-ratio:16/10}
.uc-tpl .uc-gallery::-webkit-scrollbar{display:none}
.uc-tpl .uc-slide{flex:0 0 100%;width:100%;height:100%;object-fit:cover;scroll-snap-align:center}
.uc-tpl .uc-slider .uc-nav{position:absolute;top:50%;transform:translateY(-50%);width:38px;height:38px;border-radius:50%;border:none;background:rgba(255,255,255,.9);color:#14181e;font-size:1.2rem;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background-color .15s,color .15s}
.uc-tpl .uc-slider .uc-nav:hover{background:var(--acc);color:var(--onacc)}
.uc-tpl .uc-slider .uc-prev{left:12px}.uc-tpl .uc-slider .uc-next{right:12px}
.uc-tpl .uc-dots{position:absolute;bottom:12px;left:0;right:0;display:flex;justify-content:center;gap:7px}
.uc-tpl .uc-dot{width:8px;height:8px;border-radius:50%;border:none;background:rgba(255,255,255,.5);cursor:pointer;padding:0}
.uc-tpl .uc-dot.on{background:var(--acc)}
.uc-tpl .uc-car-body{padding:22px}
.uc-tpl .uc-car-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.uc-tpl .uc-car-head h3{font-size:1.2rem}
.uc-tpl .uc-price{font-family:var(--hf);font-weight:700;color:var(--acc);font-size:1.25rem;white-space:nowrap}
.uc-tpl .uc-strap{color:var(--muted);font-size:.9rem;margin:6px 0 16px}
.uc-tpl .uc-specs{display:grid;grid-template-columns:1fr 1fr;gap:8px 18px;padding:16px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.uc-tpl .uc-spec{display:flex;justify-content:space-between;font-size:.86rem}
.uc-tpl .uc-spec span{color:var(--muted)}
.uc-tpl .uc-features{list-style:none;padding:0;margin:16px 0;display:flex;flex-wrap:wrap;gap:8px}
.uc-tpl .uc-features li{font-size:.8rem;background:#f1f3f6;border-radius:999px;padding:5px 12px;color:#3b424d}
.uc-tpl .uc-car-cta{display:flex;gap:10px;flex-wrap:wrap}
.uc-tpl .uc-car-cta .uc-btn{flex:1;padding:11px 14px;font-size:.9rem}

.uc-tpl .uc-car[data-status]::before{position:absolute;top:14px;left:14px;z-index:6;padding:6px 13px;border-radius:8px;font-family:var(--hf);font-weight:700;font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;color:#fff;box-shadow:0 8px 20px -8px rgba(0,0,0,.55)}
.uc-tpl .uc-car[data-status="sold"]::before{content:"Sold";background:#d12b2b}
.uc-tpl .uc-car[data-status="reserved"]::before{content:"Reserved";background:#E85D00}
.uc-tpl .uc-car[data-status="new"]::before{content:"New in";background:#1f9d55}
.uc-tpl .uc-car[data-status="sold"] .uc-slider{opacity:.5;filter:grayscale(.45)}
.uc-tpl .uc-car[data-status="sold"] .uc-price{color:#9aa1ac;text-decoration:line-through}

.uc-tpl .uc-why{padding:80px 0;background:var(--dark);color:#fff}
.uc-tpl .uc-why .uc-eyebrow{color:var(--acc)}
.uc-tpl .uc-why h2{font-size:clamp(1.7rem,3vw,2.4rem)}
.uc-tpl .uc-why-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:20px;margin-top:36px}
.uc-tpl .uc-why-card{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.09);border-radius:14px;padding:24px;transition:border-color .18s,transform .18s}
.uc-tpl .uc-why-card:hover{border-color:var(--acc);transform:translateY(-3px)}
.uc-tpl .uc-why-card h3{font-size:1.05rem;margin-bottom:8px}
.uc-tpl .uc-why-card p{color:#aeb4bd;font-size:.9rem;margin:0}

.uc-tpl .uc-cta{padding:60px 0;background:var(--acc)}
.uc-tpl .uc-cta-inner{display:flex;justify-content:space-between;align-items:center;gap:24px;flex-wrap:wrap}
.uc-tpl .uc-cta h2{color:var(--onacc);font-size:clamp(1.5rem,2.6vw,2rem)}
.uc-tpl .uc-cta p{color:rgba(26,18,5,.75);margin:6px 0 0}
.uc-tpl .uc-cta .uc-btn-solid{background:var(--onacc);color:#fff;border-color:var(--onacc)}
.uc-tpl .uc-cta .uc-btn-line{color:var(--onacc);border-color:rgba(26,18,5,.4)}

.uc-enq-overlay{position:fixed;inset:0;background:rgba(8,9,11,.72);display:none;align-items:center;justify-content:center;z-index:200;padding:20px}
.uc-enq-overlay.on{display:flex}
.uc-enq-modal{background:#fff;color:#14181e;border-radius:16px;max-width:440px;width:100%;padding:28px;position:relative;box-shadow:0 30px 80px -30px rgba(0,0,0,.6)}
.uc-enq-close{position:absolute;top:12px;right:16px;background:none;border:none;font-size:1.8rem;line-height:1;color:#8a8f98;cursor:pointer}
.uc-enq-title{font-family:'Sora',sans-serif;font-size:1.3rem;margin:0 0 4px}
.uc-enq-car{color:var(--brand-accent,#d7a24b);font-weight:600;font-size:.9rem;margin:0 0 16px}
.uc-enq-form{display:flex;flex-direction:column;gap:12px}
.uc-enq-form label{display:flex;flex-direction:column;font-size:.72rem;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:#616873;gap:5px}
.uc-enq-form input,.uc-enq-form textarea{font-family:inherit;font-size:.95rem;color:#14181e;border:1px solid #e6e8ec;border-radius:9px;padding:10px 12px}
.uc-enq-form input:focus,.uc-enq-form textarea:focus{outline:none;border-color:var(--brand-accent,#d7a24b)}

@media(max-width:860px){
  .uc-tpl .uc-hero-grid{grid-template-columns:1fr;gap:32px}
  .uc-tpl .uc-why-grid{grid-template-columns:1fr 1fr}
}
@media(max-width:600px){
  .uc-tpl .uc-grid{grid-template-columns:1fr}
  .uc-tpl .uc-why-grid{grid-template-columns:1fr}
  .uc-tpl .uc-cta-inner{flex-direction:column;align-items:flex-start}
}
"""

USED_CARS_JS = """
(function(){
  function initSlider(s){
    var t=s.querySelector('.uc-gallery'); if(!t) return;
    var n=t.querySelectorAll('.uc-slide').length; if(n<2) return;
    var dots=document.createElement('div'); dots.className='uc-dots';
    for(var i=0;i<n;i++){(function(idx){var d=document.createElement('button');d.type='button';d.className='uc-dot'+(idx===0?' on':'');d.addEventListener('click',function(){t.scrollTo({left:idx*t.clientWidth,behavior:'smooth'});});dots.appendChild(d);})(i);}
    s.appendChild(dots);
    var p=document.createElement('button');p.type='button';p.className='uc-nav uc-prev';p.setAttribute('aria-label','Previous photo');p.innerHTML='\\u2039';
    var nx=document.createElement('button');nx.type='button';nx.className='uc-nav uc-next';nx.setAttribute('aria-label','Next photo');nx.innerHTML='\\u203A';
    p.addEventListener('click',function(){t.scrollBy({left:-t.clientWidth,behavior:'smooth'});});
    nx.addEventListener('click',function(){t.scrollBy({left:t.clientWidth,behavior:'smooth'});});
    s.appendChild(p);s.appendChild(nx);
    t.addEventListener('scroll',function(){if(!t.clientWidth)return;var idx=Math.round(t.scrollLeft/t.clientWidth);var ds=dots.querySelectorAll('.uc-dot');for(var j=0;j<ds.length;j++)ds[j].classList.toggle('on',j===idx);},{passive:true});
  }
  function initEnquiry(root){
    var btns=root.querySelectorAll('.uc-enquire-btn'); if(!btns.length) return;
    var email=(root.getAttribute('data-enquiry-email')||'').trim();
    var ov=document.createElement('div'); ov.className='uc-enq-overlay';
    ov.innerHTML='<div class="uc-enq-modal" role="dialog" aria-modal="true"><button class="uc-enq-close" type="button" aria-label="Close">&times;</button><h3 class="uc-enq-title">Enquire about this car</h3><p class="uc-enq-car"></p><form class="uc-enq-form"><label>Your name<input name="name" required></label><label>Phone<input name="phone" type="tel"></label><label>Email<input name="email" type="email" required></label><label>Message<textarea name="message" rows="3">I\\'d like more information about this car, please.</textarea></label><button type="submit" class="uc-btn uc-btn-solid" style="width:100%;margin-top:6px">Send enquiry</button></form></div>';
    document.body.appendChild(ov);
    var carName=''; var carEl=ov.querySelector('.uc-enq-car');
    function open(name){carName=name;carEl.textContent=name?('Car: '+name):'';ov.classList.add('on');}
    function close(){ov.classList.remove('on');}
    ov.addEventListener('click',function(e){if(e.target===ov)close();});
    ov.querySelector('.uc-enq-close').addEventListener('click',close);
    btns.forEach(function(b){b.addEventListener('click',function(e){e.preventDefault();var card=b.closest('.uc-car');var h=card&&card.querySelector('.uc-car-head h3');open(h?h.textContent.trim():'');});});
    ov.querySelector('.uc-enq-form').addEventListener('submit',function(e){e.preventDefault();var f=e.target;var subj='Car enquiry: '+(carName||'used car');var body='Car: '+carName+'\\n\\nName: '+f.name.value+'\\nPhone: '+f.phone.value+'\\nEmail: '+f.email.value+'\\n\\n'+f.message.value;window.location.href='mailto:'+email+'?subject='+encodeURIComponent(subj)+'&body='+encodeURIComponent(body);close();});
  }
  function initAll(){var root=document.querySelector('.uc-tpl');if(!root)return;root.querySelectorAll('.uc-slider').forEach(initSlider);initEnquiry(root);}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',initAll);else initAll();
})();
"""

def _car(title, price, strap, specs, features, imgs):
    slide_parts = []
    for i, u in enumerate(imgs):
        lazy = "" if i == 0 else ' loading="lazy"'
        slide_parts.append(f'<img class="uc-slide"{lazy} src="{u}" alt="{title} photo {i+1}">')
    slides = "".join(slide_parts)
    spec_html = "".join(f'<div class="uc-spec"><span>{k}</span><b>{v}</b></div>' for k, v in specs)
    feat_html = "".join(f"<li>{f}</li>" for f in features)
    return f"""
      <article class="uc-car" data-block="car" data-status="">
        <div class="uc-slider" data-slider><div class="uc-gallery">{slides}</div></div>
        <div class="uc-car-body">
          <div class="uc-car-head"><h3>{title}</h3><p class="uc-price">{price}</p></div>
          <p class="uc-strap">{strap}</p>
          <div class="uc-specs">{spec_html}</div>
          <ul class="uc-features">{feat_html}</ul>
          <div class="uc-car-cta">
            <button class="uc-btn uc-btn-solid uc-enquire-btn" type="button">Enquire about this car</button>
            <a class="uc-btn uc-btn-line" href="tel:+441234567890">Call us</a>
          </div>
        </div>
      </article>"""

_CAR1 = _car(
    "2021 Mercedes-Benz C-Class", "&pound;21,995",
    "C220d AMG Line 9G-Tronic &middot; 1 owner &middot; Full service history",
    [("Year", "2021 (21)"), ("Mileage", "28,400 miles"), ("Engine", "2.0L Diesel"),
     ("Gearbox", "Automatic"), ("Fuel economy", "56.5 mpg"), ("Colour", "Cavansite Blue")],
    ["Heated leather seats", "Reversing camera", "Apple CarPlay", "LED headlights"],
    ["https://images.pexels.com/photos/27001011/pexels-photo-27001011.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
     "https://images.unsplash.com/photo-1625690180114-5530b1304127?crop=entropy&cs=srgb&fm=jpg&q=85&w=1000",
     "https://images.unsplash.com/photo-1667893591090-19729ae8fee3?crop=entropy&cs=srgb&fm=jpg&q=85&w=1000"])

_CAR2 = _car(
    "2020 Porsche 718 Cayman", "&pound;38,750",
    "2.0T PDK &middot; Sport Chrono Pack &middot; Just serviced",
    [("Year", "2020 (70)"), ("Mileage", "19,100 miles"), ("Engine", "2.0L Petrol"),
     ("Gearbox", "Automatic (PDK)"), ("Fuel economy", "34.9 mpg"), ("Colour", "GT Silver")],
    ["Sport exhaust", "Bose sound", "20&Prime; alloys", "Heated seats"],
    ["https://images.pexels.com/photos/37742006/pexels-photo-37742006.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
     "https://images.unsplash.com/photo-1549064233-945d7063292f?crop=entropy&cs=srgb&fm=jpg&q=85&w=1000",
     "https://images.unsplash.com/photo-1621639532859-8b26570b96fc?crop=entropy&cs=srgb&fm=jpg&q=85&w=1000"])

USED_CARS_HTML = f"""
<div class="uc-tpl" data-enquiry-email="sales@yourgarage.co.uk">
  <section class="uc-hero">
    <div class="uc-wrap uc-hero-grid">
      <div class="uc-hero-copy">
        <span class="uc-eyebrow">Available now</span>
        <h1>Hand-picked used cars, honestly priced.</h1>
        <p class="uc-lead">Every car we sell is HPI-clear, fully serviced and backed by our own warranty. No pressure, no gimmicks &mdash; just good cars and straight talk.</p>
        <div class="uc-hero-cta">
          <a class="uc-btn uc-btn-solid" href="#uc-stock">View our stock</a>
          <a class="uc-btn uc-btn-line" href="tel:+441234567890">Book a viewing</a>
        </div>
        <ul class="uc-hero-stats">
          <li><strong>120-point</strong> inspection</li>
          <li><strong>Warranty</strong> included</li>
          <li><strong>Part-exchange</strong> welcome</li>
        </ul>
      </div>
      <div class="uc-hero-media">
        <img src="https://images.pexels.com/photos/16176576/pexels-photo-16176576.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940" alt="Cars on display in the showroom">
      </div>
    </div>
  </section>

  <section class="uc-stock" id="uc-stock">
    <div class="uc-wrap">
      <div class="uc-sec-head">
        <span class="uc-eyebrow">Our latest arrivals</span>
        <h2>Quality used cars, ready to drive away</h2>
        <p class="uc-sec-sub">A rotating selection of quality used cars. Ask us about any vehicle &mdash; we&rsquo;re happy to send more photos or arrange a test drive.</p>
      </div>
      <div class="uc-grid">{_CAR1}{_CAR2}</div>
    </div>
  </section>

  <section class="uc-why">
    <div class="uc-wrap">
      <span class="uc-eyebrow">Why buy from us</span>
      <h2>Straightforward, every step</h2>
      <div class="uc-why-grid">
        <div class="uc-why-card"><h3>No pressure, ever</h3><p>Browse at your own pace. We&rsquo;ll answer your questions and hand you the keys for a test drive.</p></div>
        <div class="uc-why-card"><h3>Honest history</h3><p>Every car comes with a full HPI check, service history and an MOT. We tell you the good and the bad up front.</p></div>
        <div class="uc-why-card"><h3>Servicing on site</h3><p>Our own workshop looks after every car before it&rsquo;s sold &mdash; and long after you drive away.</p></div>
        <div class="uc-why-card"><h3>Finance &amp; part-ex</h3><p>Competitive finance options and a fair price for your current car. Get a quote in minutes.</p></div>
      </div>
    </div>
  </section>

  <section class="uc-cta">
    <div class="uc-wrap uc-cta-inner">
      <div><h2>Come and see us</h2><p>Pop in for a coffee and a look around, or give us a call.</p></div>
      <div class="uc-hero-cta">
        <a class="uc-btn uc-btn-solid" href="tel:+441234567890">01234 567 890</a>
        <a class="uc-btn uc-btn-line" href="mailto:sales@yourgarage.co.uk">Email us</a>
      </div>
    </div>
  </section>
</div>
"""

BUILTIN_TEMPLATES = [
    {
        "key": "used-cars",
        "name": "Used Cars / Stock page",
        "description": "A full used-car listings page: hero, stock grid with photo sliders, Sold/Reserved badges, per-car enquiry form, why-us and call-to-action. Cars can be duplicated, deleted and reordered in the editor.",
        "sections_html": USED_CARS_HTML,
        "css": USED_CARS_CSS,
        "js": USED_CARS_JS,
    }
]
