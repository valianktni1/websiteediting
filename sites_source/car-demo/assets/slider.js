// Gallery slider + mobile menu + per-car enquiry form.
// Sliders auto-detect images from each [data-slider]'s children; added photos become new slides.
(function () {
  function initSlider(slider) {
    var track = slider.querySelector('.gallery');
    if (!track) return;
    var n = track.querySelectorAll('.slide').length;
    if (n < 2) return;

    var dots = document.createElement('div');
    dots.className = 'dots';
    for (var i = 0; i < n; i++) {
      var d = document.createElement('button');
      d.type = 'button';
      d.className = 'dot' + (i === 0 ? ' on' : '');
      (function (idx) {
        d.addEventListener('click', function () {
          track.scrollTo({ left: idx * track.clientWidth, behavior: 'smooth' });
        });
      })(i);
      dots.appendChild(d);
    }
    slider.appendChild(dots);

    var prev = document.createElement('button');
    prev.type = 'button'; prev.className = 'nav prev';
    prev.setAttribute('aria-label', 'Previous photo'); prev.innerHTML = '\u2039';
    var next = document.createElement('button');
    next.type = 'button'; next.className = 'nav next';
    next.setAttribute('aria-label', 'Next photo'); next.innerHTML = '\u203A';
    prev.addEventListener('click', function () { track.scrollBy({ left: -track.clientWidth, behavior: 'smooth' }); });
    next.addEventListener('click', function () { track.scrollBy({ left: track.clientWidth, behavior: 'smooth' }); });
    slider.appendChild(prev);
    slider.appendChild(next);

    track.addEventListener('scroll', function () {
      if (!track.clientWidth) return;
      var idx = Math.round(track.scrollLeft / track.clientWidth);
      var ds = dots.querySelectorAll('.dot');
      for (var j = 0; j < ds.length; j++) ds[j].classList.toggle('on', j === idx);
    }, { passive: true });
  }

  function initMenu() {
    var toggle = document.querySelector('.menu-toggle');
    var nav = document.querySelector('.nav');
    if (!toggle || !nav) return;
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    nav.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        nav.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
      });
    });
  }

  function initEnquiry() {
    var btns = document.querySelectorAll('.enquire-btn');
    if (!btns.length) return;
    var email = (document.body.getAttribute('data-enquiry-email') || '').trim();
    var ov = document.createElement('div');
    ov.className = 'enq-overlay';
    ov.innerHTML =
      '<div class="enq-modal" role="dialog" aria-modal="true">' +
      '<button class="enq-close" type="button" aria-label="Close">&times;</button>' +
      '<h3 class="enq-title">Enquire about this car</h3>' +
      '<p class="enq-car"></p>' +
      '<form class="enq-form">' +
      '<label>Your name<input name="name" required></label>' +
      '<label>Phone<input name="phone" type="tel"></label>' +
      '<label>Email<input name="email" type="email" required></label>' +
      '<label>Message<textarea name="message" rows="3">I\'d like more information about this car, please.</textarea></label>' +
      '<button type="submit" class="btn btn-solid enq-send">Send enquiry</button>' +
      '</form></div>';
    document.body.appendChild(ov);
    var carName = '';
    var carEl = ov.querySelector('.enq-car');
    function open(name) { carName = name; carEl.textContent = name ? ('Car: ' + name) : ''; ov.classList.add('on'); }
    function close() { ov.classList.remove('on'); }
    ov.addEventListener('click', function (e) { if (e.target === ov) close(); });
    ov.querySelector('.enq-close').addEventListener('click', close);
    btns.forEach(function (b) {
      b.addEventListener('click', function (e) {
        e.preventDefault();
        var card = b.closest('.car');
        var h = card && card.querySelector('.car-head h3');
        open(h ? h.textContent.trim() : '');
      });
    });
    ov.querySelector('.enq-form').addEventListener('submit', function (e) {
      e.preventDefault();
      var f = e.target;
      var subj = 'Car enquiry: ' + (carName || 'used car');
      var body = 'Car: ' + carName + '\n\nName: ' + f.name.value + '\nPhone: ' + f.phone.value +
        '\nEmail: ' + f.email.value + '\n\n' + f.message.value;
      window.location.href = 'mailto:' + email + '?subject=' + encodeURIComponent(subj) + '&body=' + encodeURIComponent(body);
      close();
    });
  }

  // Buyer-facing finance estimator: adds "From £X/mo" under each car + a popup
  // calculator (deposit / term). Purely runtime, never saved — so it works on the
  // published site for every car (including cloned/added listings). Skipped inside
  // the CMS editor iframe to avoid interfering with click-to-edit.
  function fmtMoney(n) { return '£' + Math.round(n).toLocaleString('en-GB'); }
  function parsePrice(txt) {
    var m = (txt || '').replace(/[, ]/g, '').match(/(\d{3,})/);
    return m ? parseInt(m[1], 10) : 0;
  }
  function pmt(principal, aprPct, months) {
    var i = aprPct / 100 / 12;
    if (i <= 0) return principal / months;
    return principal * i / (1 - Math.pow(1 + i, -months));
  }
  function initFinance() {
    if (window.self !== window.top) return; // don't run in the editor canvas
    var cars = document.querySelectorAll('[data-block="car"], .car');
    if (!cars.length) return;
    var APR = parseFloat(document.body.getAttribute('data-finance-apr')) || 12.9;
    var TERM = parseInt(document.body.getAttribute('data-finance-term'), 10) || 48;
    var DEP = parseFloat(document.body.getAttribute('data-finance-deposit-pct'));
    if (isNaN(DEP)) DEP = 10;

    // shared popup
    var ov = document.createElement('div');
    ov.className = 'fin-overlay';
    ov.innerHTML =
      '<div class="fin-modal" role="dialog" aria-modal="true">' +
      '<button class="fin-close" type="button" aria-label="Close">&times;</button>' +
      '<h3 class="fin-title">Finance estimate</h3>' +
      '<p class="fin-car"></p>' +
      '<div class="fin-line"><span>Cash price</span><b class="fin-price"></b></div>' +
      '<label class="fin-ctl">Deposit <b class="fin-dep-val"></b>' +
      '<input class="fin-dep" type="range" min="0" max="50" step="5"></label>' +
      '<div class="fin-ctl"><span>Term</span><span class="fin-terms">' +
      '<button type="button" data-t="24">24</button><button type="button" data-t="36">36</button>' +
      '<button type="button" data-t="48">48</button><button type="button" data-t="60">60</button>' +
      '</span></div>' +
      '<div class="fin-result"><span>Estimated monthly</span><b class="fin-monthly"></b></div>' +
      '<p class="fin-note">Representative example at <b class="fin-apr"></b>% APR. This is an illustration only, not a quote or an offer of finance. Subject to status &amp; affordability.</p>' +
      '<button class="btn btn-solid fin-enquire" type="button">Ask us about finance</button>' +
      '</div>';
    document.body.appendChild(ov);
    var cur = { price: 0, dep: DEP, term: TERM, car: null };
    var elPrice = ov.querySelector('.fin-price'), elDepV = ov.querySelector('.fin-dep-val'),
        elDep = ov.querySelector('.fin-dep'), elMon = ov.querySelector('.fin-monthly'),
        elCar = ov.querySelector('.fin-car'), elApr = ov.querySelector('.fin-apr');
    elApr.textContent = APR;
    function recalc() {
      var principal = cur.price * (1 - cur.dep / 100);
      elPrice.textContent = fmtMoney(cur.price);
      elDepV.textContent = cur.dep + '% (' + fmtMoney(cur.price * cur.dep / 100) + ')';
      elMon.textContent = fmtMoney(pmt(principal, APR, cur.term)) + '/mo';
      ov.querySelectorAll('.fin-terms button').forEach(function (b) {
        b.classList.toggle('on', parseInt(b.getAttribute('data-t'), 10) === cur.term);
      });
    }
    function open(car, price) {
      cur.price = price; cur.dep = DEP; cur.term = TERM; cur.car = car;
      var h = car.querySelector('.car-head h3, h3');
      elCar.textContent = h ? h.textContent.trim() : '';
      elDep.value = DEP; recalc(); ov.classList.add('on');
    }
    function close() { ov.classList.remove('on'); }
    ov.addEventListener('click', function (e) { if (e.target === ov) close(); });
    ov.querySelector('.fin-close').addEventListener('click', close);
    elDep.addEventListener('input', function () { cur.dep = parseInt(elDep.value, 10); recalc(); });
    ov.querySelectorAll('.fin-terms button').forEach(function (b) {
      b.addEventListener('click', function () { cur.term = parseInt(b.getAttribute('data-t'), 10); recalc(); });
    });
    ov.querySelector('.fin-enquire').addEventListener('click', function () {
      close();
      var eb = cur.car && cur.car.querySelector('.enquire-btn');
      if (eb) eb.click();
    });

    cars.forEach(function (car) {
      var priceEl = car.querySelector('.price');
      if (!priceEl) return;
      var price = parsePrice(priceEl.textContent);
      if (!price || price < 500) return;
      var monthly = pmt(price * (1 - DEP / 100), APR, TERM);
      var fin = document.createElement('div');
      fin.className = 'finance';
      fin.innerHTML = '<span class="finance-from">From <b>' + fmtMoney(monthly) + '</b>/mo</span>' +
        '<button type="button" class="finance-btn">Finance example &rsaquo;</button>';
      var head = car.querySelector('.car-head');
      if (head) head.insertAdjacentElement('afterend', fin);
      else priceEl.insertAdjacentElement('afterend', fin);
      fin.querySelector('.finance-btn').addEventListener('click', function () { open(car, price); });
    });
  }

  function initAll() {
    document.querySelectorAll('[data-slider]').forEach(initSlider);
    initMenu();
    initEnquiry();
    initFinance();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initAll);
  else initAll();
})();
