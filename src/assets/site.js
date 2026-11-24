/* In-Kind Standard: the site's one script (decision sheet 15, X1 A, 17 November 2026; frame v0.6, sections 7 and 9).
   It adds, and nothing more: the color theme switch, the readers' tabs, the stepper's line, the reveal, the count-up and the
   drawing of who is party to what; it closes the disclosures that the pages write open, and opens them again for print. Every page reads, links and prints in full without it.
   Nothing is hidden until this script has shown it can bring it back. No libraries, no network calls, no cookies.
   The theme choice is kept in the browser's own storage on this device, under "iks-theme", and nowhere else; a link to the Screen carries it after its #, which no site receives.
   When the device asks for reduced motion, the reveal, the count-up, the drawing and the stepper's line do not run. */
(function () {
  'use strict';
  var root = document.documentElement;
  var KEY = 'iks-theme';

  /* Theme: applied at once, before the page is drawn, so a saved choice never flashes the other colors. */
  function saved() { try { var v = window.localStorage.getItem(KEY); return v === 'light' || v === 'dark' ? v : ''; } catch (e) { return ''; } }
  function save(v) { try { if (v) window.localStorage.setItem(KEY, v); else window.localStorage.removeItem(KEY); } catch (e) { /* storage may be off: the choice then lasts for this page only */ } }
  function apply(v) { if (v) root.setAttribute('data-theme', v); else root.removeAttribute('data-theme'); }
  apply(saved());

  /* A choice carried from the Screen (screen.inkindstandard.org): a link from it ends in theme=light, theme=dark or theme=device after its # (after any place on the page, joined with &). Browsers never send the part after #
     to either site. The choice is kept as if it were pressed here, and the mark is taken off the address. (Founder's choice of 24 November 2026: carry it in links, no cookie.) */
  var carried = window.location.hash;
  var at = carried.lastIndexOf('theme=');
  var mark = at === 1 || (at > 1 && carried.charAt(at - 1) === '&') ? carried.slice(at + 6) : null;
  var c = mark === 'light' ? 'light' : mark === 'dark' ? 'dark' : mark === 'device' ? '' : null;
  if (c !== null) { save(c); apply(c); window.history.replaceState(null, '', window.location.pathname + window.location.search + carried.slice(0, at > 1 ? at - 1 : 0)); }

  function ready(fn) { if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn); else fn(); }
  function each(list, fn) { Array.prototype.forEach.call(list, fn); }
  function el(tag, attrs, text) {
    var n = document.createElement(tag), k;
    for (k in attrs) n.setAttribute(k, attrs[k]);
    if (text) n.appendChild(document.createTextNode(text));
    return n;
  }
  var still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  ready(function () {
    /* Disclosures: each page writes them open, so that paper and a reader without this script have every word; with it they start closed. */
    each(document.querySelectorAll('details[data-fold]'), function (d) { d.removeAttribute('open'); });

    /* The color theme switch: in the header and in the phone menu. */
    var groups = [];
    function paint() {
      var cur = saved();
      each(groups, function (g) {
        each(g.querySelectorAll('button'), function (b) { b.setAttribute('aria-pressed', String((b.getAttribute('data-theme') || '') === cur)); });
      });
    }
    function makeSwitch() {
      var g = el('div', { 'class': 'theme', role: 'group', 'aria-label': 'Color theme' });
      [['light', 'Light'], ['dark', 'Dark'], ['', 'Device']].forEach(function (o) {
        var b = el('button', { type: 'button', 'data-theme': o[0], 'aria-pressed': 'false' }, o[1]);
        b.addEventListener('click', function () { save(o[0]); apply(o[0]); paint(); });
        g.appendChild(b);
      });
      groups.push(g);
      return g;
    }
    each(document.querySelectorAll('.util, .mnav'), function (h) { h.appendChild(makeSwitch()); });
    paint();

    /* Carrying the choice to the Screen: when a link to it is followed, the choice is written after the link's #, and the Screen keeps it. A link that already has its own # is left as it is. */
    function carry(ev) {
      var a = ev.target && ev.target.closest ? ev.target.closest('a') : null;
      if (!a || a.hostname !== 'screen.inkindstandard.org') return;
      var h = a.hash, at = h.lastIndexOf('theme=');
      if (at === 1 || (at > 1 && h.charAt(at - 1) === '&')) h = h.slice(0, at > 1 ? at - 1 : 0);
      a.hash = (h ? h.slice(1) + '&' : '') + 'theme=' + (saved() || 'device');
    }
    document.addEventListener('click', carry, true);
    document.addEventListener('auxclick', carry, true);

    /* The readers' tabs. Without this script each reader's way is a short list under its own heading. */
    each(document.querySelectorAll('[data-tabs]'), function (box, n) {
      var panels = box.querySelectorAll('[data-tab]');
      if (panels.length < 2) return;
      var list = el('div', { 'class': 'tabs', role: 'tablist', 'aria-label': box.getAttribute('data-tabs') });
      var tabs = [];
      function pick(i, focus) {
        tabs.forEach(function (t, j) {
          var on = i === j;
          t.setAttribute('aria-selected', String(on)); t.tabIndex = on ? 0 : -1;
          if (on) panels[j].removeAttribute('hidden'); else panels[j].setAttribute('hidden', '');
        });
        if (focus) tabs[i].focus();
      }
      each(panels, function (p, i) {
        var h = p.querySelector('h3'), id = 'tab-' + n + '-' + i;
        var b = el('button', { type: 'button', 'class': 'tab', role: 'tab', id: id, 'aria-controls': id + '-p' });
        each(h.childNodes, function (c) { b.appendChild(c.cloneNode(true)); });
        p.setAttribute('role', 'tabpanel'); p.id = id + '-p'; p.setAttribute('aria-labelledby', id);
        h.setAttribute('hidden', '');
        b.addEventListener('click', function () { pick(i); });
        b.addEventListener('keydown', function (e) {
          var k = e.key, j = k === 'ArrowRight' ? (i + 1) % tabs.length : k === 'ArrowLeft' ? (i + tabs.length - 1) % tabs.length : k === 'Home' ? 0 : k === 'End' ? tabs.length - 1 : -1;
          if (j < 0) return;
          e.preventDefault(); pick(j, true);
        });
        tabs.push(b); list.appendChild(b);
      });
      box.insertBefore(list, panels[0]);
      box.classList.add('is-tabs');
      pick(0);
    });

    /* Print: every disclosure is open on paper, and closed again after. */
    var shut = [];
    window.addEventListener('beforeprint', function () {
      each(document.querySelectorAll('details:not([open])'), function (d) { d.setAttribute('open', ''); shut.push(d); });
    });
    window.addEventListener('afterprint', function () { shut.forEach(function (d) { d.removeAttribute('open'); }); shut = []; });

    /* Motion: off when the device asks for reduced motion. */
    if (still || !('IntersectionObserver' in window)) return;
    var vh = function () { return window.innerHeight || document.documentElement.clientHeight; };
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        var t = e.target;
        io.unobserve(t);
        if (t.classList.contains('fx-wait')) { t.classList.remove('fx-wait'); t.classList.add('fx-in'); }
        if (t.classList.contains('dg-wait')) { t.classList.remove('dg-wait'); t.classList.add('dg-draw'); }
        if (t.hasAttribute('data-count')) count(t);
      });
    }, { threshold: 0.15 });

    function count(t) {
      var n = t.querySelector('.fig-n'), to = parseInt(t.getAttribute('data-count'), 10), t0 = null;
      if (!n || !n.firstChild || isNaN(to)) return;
      function step(now) {
        if (t0 === null) t0 = now;
        var p = Math.min(1, (now - t0) / 1200);
        n.firstChild.nodeValue = String(Math.round(to * (1 - Math.pow(1 - p, 3))));
        if (p < 1) window.requestAnimationFrame(step);
      }
      window.requestAnimationFrame(step);
    }

    /* A reveal waits for the reader's first scroll, so a page never scrolled shows everything; what is already in view stays as it is. */
    var armed = false;
    function arm() {
      if (armed) return;
      armed = true;
      each(document.querySelectorAll('[data-reveal], [data-count], .dg'), function (t) {
        if (t.getBoundingClientRect().top <= vh()) return;
        if (t.hasAttribute('data-reveal')) t.classList.add('fx-wait');
        if (t.classList.contains('dg')) t.classList.add('dg-wait');
        io.observe(t);
      });
    }

    var tick = false;
    function progress() {
      each(document.querySelectorAll('.stepper'), function (s) {
        var r = s.getBoundingClientRect();
        s.style.setProperty('--p', Math.max(0, Math.min(1, (vh() * 0.55 - r.top) / Math.max(1, r.height))).toFixed(3));
      });
    }
    document.addEventListener('scroll', function () {
      arm();
      if (tick) return;
      tick = true;
      window.requestAnimationFrame(function () { tick = false; progress(); });
    }, { capture: true, passive: true });
    progress();
  });
}());
