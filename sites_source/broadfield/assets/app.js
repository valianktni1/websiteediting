// year
var yrEl = document.getElementById('yr'); if (yrEl) yrEl.textContent = new Date().getFullYear();

// mobile nav
var toggle = document.getElementById('navToggle');
var mobile = document.getElementById('navMobile');
if (toggle && mobile) {
  toggle.addEventListener('click', function () { mobile.classList.toggle('open'); });
  mobile.querySelectorAll('a').forEach(function (a) {
    a.addEventListener('click', function () { mobile.classList.remove('open'); });
  });
}

// scroll reveal
var io = new IntersectionObserver(function (entries) {
  entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
}, { threshold: 0.15 });
document.querySelectorAll('.reveal').forEach(function (el) { io.observe(el); });

// vehicle photo sliders — add up to 10 photos per vehicle; visitors slide through them
function initVehSliders(scope) {
  (scope || document).querySelectorAll('.veh-slider').forEach(function (s) {
    if (s.__init) return; s.__init = 1;
    var g = s.querySelector('.veh-gallery'); if (!g) return;
    var prev = s.querySelector('.veh-prev'), next = s.querySelector('.veh-next'), count = s.querySelector('.veh-count');
    function n() { return g.querySelectorAll('.veh-slide').length; }
    function refresh() {
      s.classList.toggle('has-multi', n() > 1);
      if (count) { var i = Math.round(g.scrollLeft / (s.clientWidth || 1)) + 1; count.textContent = i + ' / ' + n(); }
    }
    if (prev) prev.addEventListener('click', function (e) { e.preventDefault(); g.scrollBy({ left: -s.clientWidth, behavior: 'smooth' }); });
    if (next) next.addEventListener('click', function (e) { e.preventDefault(); g.scrollBy({ left: s.clientWidth, behavior: 'smooth' }); });
    g.addEventListener('scroll', refresh);
    refresh();
  });
}
initVehSliders();

// contact form -> compose an email to the dealership
var enquiryForm = document.getElementById('enquiryForm');
if (enquiryForm) {
  enquiryForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var f = enquiryForm;
    var name = (f.querySelector('[name=name]') || {}).value || '';
    var phone = (f.querySelector('[name=phone]') || {}).value || '';
    var interest = (f.querySelector('[name=interest]') || {}).value || '';
    var message = (f.querySelector('[name=message]') || {}).value || '';
    var subject = 'Website enquiry' + (interest ? ' - ' + interest : '');
    var body = 'Name: ' + name + '\nPhone: ' + phone + '\nInterested in: ' + interest + '\n\n' + message;
    window.location.href = 'mailto:sales@broadfieldalfaromeo.com?subject=' +
      encodeURIComponent(subject) + '&body=' + encodeURIComponent(body);
  });
}
