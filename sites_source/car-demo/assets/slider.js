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

  function initAll() {
    document.querySelectorAll('[data-slider]').forEach(initSlider);
    initMenu();
    initEnquiry();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initAll);
  else initAll();
})();
