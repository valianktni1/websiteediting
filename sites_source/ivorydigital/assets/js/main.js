// Ivory Digital — small progressive-enhancement helpers
(function(){
  'use strict';
  // Mobile nav toggle
  var toggle = document.querySelector('.nav-toggle');
  var nav = document.querySelector('.site-nav');
  if(toggle && nav){
    toggle.addEventListener('click', function(){
      var open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }
  // Current year in footer
  var yr = document.getElementById('yr');
  if(yr){ yr.textContent = new Date().getFullYear(); }
  // Services dropdown toggle (click / mobile)
  var dropToggle = document.querySelector('.nav-drop-toggle');
  if(dropToggle){
    dropToggle.addEventListener('click', function(e){
      e.preventDefault();
      var item = dropToggle.closest('.has-dropdown');
      var open = item.classList.toggle('open');
      dropToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }
})();
