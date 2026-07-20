// year
document.getElementById('yr').textContent = new Date().getFullYear();

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
