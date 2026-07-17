// Wife To Be — interactions: sticky header, mobile nav, scroll reveal, year
(function () {
  var header = document.getElementById('siteHeader');
  var toggle = document.getElementById('navToggle');
  var nav = document.getElementById('siteNav');

  function onScroll() {
    if (!header) return;
    if (window.scrollY > 40) header.classList.add('solid');
    else header.classList.remove('solid');
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      nav.classList.toggle('open');
      document.body.classList.toggle('nav-open');
    });
    nav.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        nav.classList.remove('open');
        document.body.classList.remove('nav-open');
      });
    });
  }

  // Scroll reveal
  var els = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
      });
    }, { threshold: 0.12 });
    els.forEach(function (el) { io.observe(el); });
  } else {
    els.forEach(function (el) { el.classList.add('in'); });
  }

  // Footer year
  var y = document.getElementById('year');
  if (y) y.textContent = new Date().getFullYear();

  // Contact form -> mailto fallback
  var form = document.getElementById('contactForm');
  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var d = new FormData(form);
      var subject = encodeURIComponent('Appointment Enquiry — ' + (d.get('name') || ''));
      var body = encodeURIComponent(
        'Name: ' + (d.get('name') || '') + '\n' +
        'Phone: ' + (d.get('phone') || '') + '\n' +
        'Email: ' + (d.get('email') || '') + '\n' +
        'Preferred boutique: ' + (d.get('boutique') || '') + '\n' +
        'Interested in: ' + (d.get('interest') || '') + '\n\n' +
        'Message:\n' + (d.get('message') || '')
      );
      window.location.href = 'mailto:thegroupuk@yahoo.com?subject=' + subject + '&body=' + body;
    });
  }
})();
