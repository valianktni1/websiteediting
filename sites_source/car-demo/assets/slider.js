// Lightweight gallery slider — auto-detects images from each [data-slider]'s children.
// Works with the editor: added photos become new slides automatically on the next load.
(function () {
  function initSlider(slider) {
    var track = slider.querySelector('.gallery');
    if (!track) return;
    var slideCount = function () { return track.querySelectorAll('.slide').length; };
    if (slideCount() < 1) return;

    // dots
    var dots = document.createElement('div');
    dots.className = 'dots';
    function buildDots() {
      dots.innerHTML = '';
      var n = slideCount();
      if (n < 2) return;
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
    }
    buildDots();
    slider.appendChild(dots);

    // arrows (only if more than one image)
    if (slideCount() > 1) {
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
    }

    track.addEventListener('scroll', function () {
      if (!track.clientWidth) return;
      var i = Math.round(track.scrollLeft / track.clientWidth);
      var ds = dots.querySelectorAll('.dot');
      for (var j = 0; j < ds.length; j++) ds[j].classList.toggle('on', j === i);
    }, { passive: true });
  }

  function initAll() {
    document.querySelectorAll('[data-slider]').forEach(initSlider);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
})();
