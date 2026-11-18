"""The check that needs a browser. The site builds, and its other checks run, without it; before anything is published,
this one runs too (RUNBOOK.md, sections 2 and 3).

It serves docs/ on this computer as GitHub Pages does (text files with charset=utf-8), opens every
page at six widths, and fails if a page scrolls sideways or if anything is cut off or runs past
the edge of its box. It was written on 11 November 2026, after a table on the release page was found
cut off at phone width. Since 12 November 2026 it also fails if a line of text, as the browser lays it
out at 800 or 1,280 pixels wide, is longer than 80 characters (the site's frame, version 0.3), and if
a line begins with a mark of punctuation at any of the widths it tries. Since 12 November 2026, after the build check of
candidate 4 (C4-04, C4-05, C4-06), it also measures text contrast at 320 pixels as well as 1,280, and on paper as the
browser prints it, and fails if any words are not shown: given no box, put outside the page, clipped, or set in type
smaller than 12 pixels.

Needs Python with the `playwright` package, and Chrome or Chromium:
    pip install playwright
    playwright install chromium          (or set CHROME to the path of an installed browser)
Run:  python3 checks/look_check.py        (or give another folder to check as the first argument)
Set CHROME_ARGS=--no-sandbox where the browser asks for it.
Set AXE to the path of axe-core's axe.min.js (npm install axe-core) to run that accessibility checker on every page as well.
Set SWEEP=1 to look for a line that begins with a mark of punctuation at every width from 320 to 720 pixels (a few minutes).

Since 17 November 2026, for the design of decision sheet 15 (frame v0.6, sections 7 to 9), it also: runs every page with the site's script off,
and fails if the script removes a word or adds one that is not a tab's label or a theme button; opens every disclosure, as paper does, and
measures again; presses every reader's tab and measures each panel; measures the contrast of a saved color choice that differs from the device's;
presses the theme buttons and reads what the page and the browser's storage then hold; asks for reduced motion and fails if anything moves or waits
to appear; scrolls each page through, as a reader does, and fails if any words are still hidden, a count has not reached its number, or an animation
runs past the frame's limits; fails if a first visit loads more than 350 KB, or anything from an address that is not the site's own; and reads the
accessible name of the home link as the browser gives it. On paper it also reads the address that each link in a page's own text shows (frame v0.6, section 8).

Since 18 November 2026 (run 21, Must fix 1) it also loads each page as a screen with the script on, lets it settle, switches it to print as the browser does
(with the "beforeprint" event) and fails if a word that paper shows with the script off is not shown with the script on, or if any animation is in effect on paper.

Since 18 November 2026 (run 20, Should fix 1 and 2) it also watches what the pages do by themselves, which no rule on the script's text can settle: it fails on any request to the site's
own address that is not a plain read of one of the site's files (one with a query, one that is not a GET, one for a file the site does not hold); on a cookie; on anything in the browser's
storage but the color choice, and on anything at all before a choice is made; and on anything that moves or fades with no one touching the page, with motion allowed and with reduced motion asked for.
It also fails, with reduced motion asked for, on any change at all to a page as it is scrolled (an attribute, a text, an element added or taken away): that shows the script's own
check for the setting at work, which what a script leaves a moment later cannot, since by then a count-up and a reveal have finished (the case of the script that no longer asks was missed by the first form of this step).
"""
import asyncio, http.server, os, pathlib, socketserver, sys, threading

ROOT = pathlib.Path(__file__).resolve().parents[1]
PUB = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / 'docs'
WIDTHS = (320, 360, 375, 390, 412, 1280)      # nothing cut off, nothing scrolling sideways; 360, 375, 390 and 412 are common phone widths
SWEEP = os.environ.get('SWEEP')                 # set, the rule on a line's first character is also tried at every width from SWEEP_FROM to SWEEP_TO
SWEEP_FROM, SWEEP_TO = 320, 720                 # (found 12 Nov 2026: a footer line began with ")" at 346 to 349 and 366 to 373 pixels only)
LINE_WIDTHS = (800, 1280)      # no line of text longer than LINE_MAX characters, spaces included
LINE_MAX = 80
TYPES = {'.html': 'text/html; charset=utf-8', '.txt': 'text/plain; charset=utf-8', '.md': 'text/markdown; charset=utf-8',
         '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.svg': 'image/svg+xml', '.woff': 'font/woff', '.ico': 'image/vnd.microsoft.icon'}

PROBE = """() => {
  const vw = document.documentElement.clientWidth, out = [];
  if (document.documentElement.scrollWidth > vw + 1) out.push('the page scrolls sideways');
  for (const el of document.querySelectorAll('main *, header *, footer *')) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || el.closest('svg') || el.closest('.vh')) continue;   // .vh: words kept for screen readers only
    let shut = false;   // inside a disclosure that is closed (apart from its heading): its words are measured in the pass that opens it
    for (let up = el; up && up !== document.body; up = up.parentElement) if (up.tagName === 'DETAILS' && !up.open) { const s = el.closest('summary'); if (!s || s.parentElement !== up) { shut = true; break; } }
    if (shut) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0 || r.right <= 0) continue;
    const name = '<' + el.tagName.toLowerCase() + '> "' + (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 40) + '"';
    if (r.right > vw + 1) out.push(name + ' runs past the right edge of the window');
    if ((cs.overflowX !== 'visible' || cs.overflowY !== 'visible') && (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1)) {
      const box = el.getBoundingClientRect(), tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT), rg = document.createRange();
      let tn, cut = false;
      while ((tn = tw.nextNode())) {
        if (!tn.nodeValue.trim() || tn.parentElement.closest('svg, .vh')) continue;
        rg.selectNodeContents(tn);
        for (const q of rg.getClientRects()) if (q.width && q.height && ((cs.overflowX !== 'visible' && q.right > box.right + 1) || (cs.overflowY !== 'visible' && q.bottom > box.bottom + 1))) cut = true;
      }
      if (cut) out.push(name + ' is cut off or scrolls sideways');
    }
    const p = el.parentElement;
    if (p && getComputedStyle(p).overflowX === 'visible' && r.right > p.getBoundingClientRect().right + 1) out.push(name + ' runs past the edge of its box');
  }
  return [...new Set(out)];
}"""

# The length of each line of text as the browser lays it out. Letters are grouped into a line when they overlap
# in height, so a line that mixes two sizes of type is still one line. Words kept for screen readers only (.vh)
# and anything not shown on screen are left out.
LINES = """(max) => {
  const out = [], blocks = new Map(), range = document.createRange();
  // Every piece of text under the header, the main text and the footer, grouped by the block it sits in (the nearest box that is not inline).
  for (const root of document.querySelectorAll('header, main, footer')) {
    const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walk.nextNode())) {
      if (!n.nodeValue.trim() || n.parentElement.closest('.vh, svg')) continue;
      let el = n.parentElement;
      while (el && el !== root && getComputedStyle(el).display.startsWith('inline')) el = el.parentElement;
      if (!blocks.has(el)) blocks.set(el, []);
      blocks.get(el).push(n);
    }
  }
  for (const [el, nodes] of blocks) {
    const cs = getComputedStyle(el), lines = [];
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    for (const n of nodes) {
      const t = n.nodeValue;
      for (let i = 0; i < t.length; i++) {
        range.setStart(n, i); range.setEnd(n, i + 1);
        const b = range.getBoundingClientRect();
        if (!b.width && !b.height) continue;
        const mid = (b.top + b.bottom) / 2;
        let line = lines.find(l => mid > l.top && mid < l.bottom);
        if (!line) { line = {top: b.top, bottom: b.bottom, s: ''}; lines.push(line); }
        line.top = Math.min(line.top, b.top); line.bottom = Math.max(line.bottom, b.bottom); line.s += t[i];
      }
    }
    for (const l of lines) {
      const s = l.s.replace(/\\s+/g, ' ').trim();
      if (max && s.length > max) out.push('a line of ' + s.length + ' characters: "' + s.slice(0, 50) + '..."');
      if (/^[.,;:!?)]/.test(s)) out.push('a line that begins with "' + s[0] + '": "' + s.slice(0, 40) + '"');
    }
  }
  return [...new Set(out)];
}"""


# The contrast of every piece of text against what is painted behind it, as the browser shows it. The site check tests the named
# pairs of colors; this finds a text color put on a background it was not tested against. Text must reach TEXT_CONTRAST to 1.
TEXT_CONTRAST = 7.0
CONTRAST_WIDTHS = (1280, 320)
CONTRAST = """(args) => {
  const floor = args.floor, paper = args.paper, out = [], seen = new Set();
  const rgba = s => { const m = s.match(/rgba?\\(([^)]+)\\)/); if (!m) return null; const p = m[1].split(/[,\\s\\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walk.nextNode())) {
    if (!n.nodeValue.trim()) continue;
    const el = n.parentElement;
    if (el.closest(paper ? '.vh, svg' : '.vh, svg, .print-only')) continue;   // on paper the lines kept for paper are measured too
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect(); if (!r.width || !r.height || r.right <= 0) continue;   // the skip link waits off the page
    const fg = rgba(cs.color);
    let bg = null, up = el;
    while (up && !bg) { const b = rgba(getComputedStyle(up).backgroundColor); if (b && b[3] > 0) bg = b; up = up.parentElement; }
    if (!bg) bg = rgba(getComputedStyle(document.documentElement).backgroundColor) || [255, 255, 255, 1];
    if (!fg || fg[3] < 1 || bg[3] < 1) { out.push('text that is not fully opaque, or on a see-through background: "' + n.nodeValue.trim().slice(0, 40) + '"'); continue; }
    const a = lum(fg), b = lum(bg), ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    const key = cs.color + '|' + bg.join(',');
    if (ratio < floor && !seen.has(key)) { seen.add(key); out.push('text at ' + ratio.toFixed(2) + ' to 1: "' + n.nodeValue.trim().slice(0, 40) + '"'); }
  }
  for (const t of document.querySelectorAll('main svg text')) {
    const cs = getComputedStyle(t), say = (t.textContent || '').trim().slice(0, 40);
    if (!say || cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = t.getBoundingClientRect(); if (!r.width || !r.height) continue;
    const fg = rgba(cs.fill);
    if (!fg || fg[3] < 1) { out.push('picture text with no solid fill: "' + say + '"'); continue; }
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    let bg = null;
    for (const q of t.ownerSVGElement.querySelectorAll('rect')) { const b = q.getBoundingClientRect(), f = rgba(getComputedStyle(q).fill); if (f && f[3] === 1 && cx > b.left && cx < b.right && cy > b.top && cy < b.bottom) bg = f; }   // a card drawn behind it
    for (let up = t.ownerSVGElement; up && !bg; up = up.parentElement) { const b = rgba(getComputedStyle(up).backgroundColor); if (b && b[3] > 0) bg = b; }
    if (!bg) bg = rgba(getComputedStyle(document.documentElement).backgroundColor) || [255, 255, 255, 1];
    if (bg[3] < 1) { out.push('picture text on a see-through background: "' + say + '"'); continue; }
    const a = lum(fg), b2 = lum(bg), ratio = (Math.max(a, b2) + 0.05) / (Math.min(a, b2) + 0.05), key = 'svg|' + cs.fill + '|' + bg.join(',');
    if (ratio < floor && !seen.has(key)) { seen.add(key); out.push('picture text at ' + ratio.toFixed(2) + ' to 1: "' + say + '"'); }
  }
  // Generated content that is placed on the page (the numbers and the connecting line of the steps) lies over no text: a contrast checker cannot decide the background of text it lies over
  const px = v => parseFloat(v) || 0, over = [];
  for (const host of document.querySelectorAll('main *, header *, footer *')) for (const which of ['::before', '::after']) {
    const ps = getComputedStyle(host, which);
    if (ps.content === 'none' || ps.content === 'normal' || ps.display === 'none' || (ps.position !== 'absolute' && ps.position !== 'fixed')) continue;
    let cb = host; while (cb && getComputedStyle(cb).position === 'static') cb = cb.parentElement;
    const c = (cb || document.documentElement).getBoundingClientRect(), l = c.left + (cb ? cb.clientLeft : 0) + px(ps.left), t = c.top + (cb ? cb.clientTop : 0) + px(ps.top);
    if (px(ps.width) > 0 && px(ps.height) > 0) over.push({host, which, l, t, r: l + px(ps.width), b: t + px(ps.height)});
  }
  if (over.length) {
    const rg = document.createRange(), tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let tn;
    while ((tn = tw.nextNode())) {
      if (!tn.nodeValue.trim() || tn.parentElement.closest('.vh, svg, .print-only')) continue;
      rg.selectNodeContents(tn);
      for (const q of rg.getClientRects()) if (q.width && q.height) for (const o of over) if (q.left < o.r - 1 && q.right > o.l + 1 && q.top < o.b - 1 && q.bottom > o.t + 1) {
        const k = 'gen|' + o.host.tagName + o.which + tn.nodeValue.trim().slice(0, 20);
        if (!seen.has(k)) { seen.add(k); out.push('generated content (' + o.which + ' of <' + o.host.tagName.toLowerCase() + (typeof o.host.className === 'string' && o.host.className ? ' class="' + o.host.className.slice(0, 20) + '"' : '') + '>) lies over text: "' + tn.nodeValue.trim().slice(0, 40) + '"'); }
      }
    }
  }
  return out;
}"""


# Every piece of text is shown (C4-05): it has a box with a size, inside the page, not clipped away, in type of at least
# 12 pixels. Words kept for screen readers (.vh), the drawing, the lines kept for paper and the skip link, which waits off
# the page until it has the keyboard's focus, are set aside.
TEXTBOX = """() => {
  const out = [], vw = document.documentElement.clientWidth, height = document.documentElement.scrollHeight, range = document.createRange();
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walk.nextNode())) {
    const t = n.nodeValue.replace(/\\s+/g, ' ').trim(); if (!t) continue;
    const el = n.parentElement;
    if (el.closest('.vh, svg, .print-only, .skip')) continue;
    const name = '"' + t.slice(0, 40) + '"';
    let shut = false;   // inside a disclosure that is closed (apart from its heading) or a panel the script has put away: measured in the passes that open or select it
    for (let up = el; up; up = up.parentElement) {
      if (up.hasAttribute && up.hasAttribute('hidden')) shut = true;
      if (up.tagName === 'DETAILS' && !up.open) { const s = el.closest('summary'); if (!s || s.parentElement !== up) shut = true; }
    }
    for (let up = el; up; up = up.parentElement) if (up.matches && up.matches('.mnav, .mast-nav, .util, .ledger thead') && getComputedStyle(up).display === 'none') shut = true;   // the menu and the table head the design puts away at this width
    if (shut) continue;
    let hidden = false, clipped = false;
    for (let up = el; up; up = up.parentElement) {
      const s = getComputedStyle(up);
      if (s.display === 'none' || s.visibility !== 'visible' || parseFloat(s.opacity) === 0) hidden = true;
      if (s.clipPath !== 'none' || (s.clip && s.clip !== 'auto')) clipped = true;
    }
    range.selectNodeContents(n);
    const rects = [...range.getClientRects()].filter(r => r.width > 0 && r.height > 0);
    if (hidden || !rects.length) { out.push('words not shown: ' + name); continue; }
    if (clipped) out.push('words clipped: ' + name);
    if (parseFloat(getComputedStyle(el).fontSize) < 12) out.push('words in type smaller than 12 pixels: ' + name);
    if (rects.some(r => r.right <= 0 || r.left >= vw || r.bottom + window.scrollY <= 0 || r.top + window.scrollY >= height)) out.push('words outside the page: ' + name);
  }
  return [...new Set(out)];
}"""


# axe-core, an open accessibility checker (Deque Systems; MPL 2.0), is not kept in this folder. Where the file is at hand,
# set AXE to its path and every page is also run through it: the rules for WCAG 2.2 at levels A and AA, its best-practice
# rules, and its rule for a text contrast of 7 to 1. A violation fails; so does a case it could not decide.
AXE = os.environ.get('AXE')
AXE_WIDTHS = (1280, 320)
AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice']
AXE_RUN = """async (tags) => {
  const r = await axe.run(document, {runOnly: {type: 'tag', values: tags}, rules: {'color-contrast-enhanced': {enabled: true}}});
  const inPicture = n => { try { const e = document.querySelector(n.target[0]); return !!e && !!e.closest('svg'); } catch (x) { return false; } };
  const behindGenerated = n => { const a = (n.any && n.any[0]) || (n.all && n.all[0]) || (n.none && n.none[0]) || {}; return !!(a.data && a.data.messageKey === 'pseudoContent'); };
  const say = (kind, list) => list.map(v => { const nodes = kind === 'violation' || !v.id.startsWith('color-contrast') ? v.nodes : v.nodes.filter(n => !inPicture(n) && !behindGenerated(n)); return nodes.length ? kind + ' ' + v.id + ' (' + nodes.length + ' places): ' + v.help + ' [' + nodes.slice(0, 3).map(n => n.target.join(' ')).join('; ') + ']' : null; }).filter(Boolean);
  return say('violation', r.violations).concat(say('could not decide', r.incomplete));
}"""


# Paper, the addresses (frame v0.6, section 8): a link to another page of the site, or to another host, shows the address a reader of the paper can use after its words; a link inside the page, a
# mail link, a DOI (its words are the address) and another project's released text show none. The address is worked out here from where the browser says the link goes, not from the page's own
# data-url, so that a wrong data-url, a missing rule and a rule that hides the address are all found.
# A link that is not on paper at all is found too (run 22, Should fix 2: the buttons were put away by a rule for paper, and a reader of the paper lost the page's only link to the release).
PAPER_LINKS = """(site) => [...document.querySelectorAll('main a[href]')].map(a => {
  const href = a.getAttribute('href'), cs = getComputedStyle(a, '::after'), shown = cs.content, u = new URL(a.href);
  const quiet = a.closest('.released') || a.classList.contains('doi') || href.startsWith('#') || href.startsWith('mailto:');
  const want = quiet ? null : (u.origin === location.origin ? site + u.pathname + u.search + u.hash : a.href);
  if (!a.checkVisibility({opacityProperty: true, visibilityProperty: true})) return href + ' is not on paper: its words "' + a.textContent.replace(/\\s+/g, ' ').trim().slice(0, 50) + '" are put away, hidden or faded out';
  const ok = want === null ? (shown === 'none' || shown === 'normal' || !shown.includes('(')) : (shown === '" (' + want + ')"' && cs.display !== 'none' && cs.visibility !== 'hidden' && cs.opacity !== '0' && parseFloat(cs.fontSize) >= 8);
  const notShown = [cs.display === 'none' ? 'its display is none' : '', cs.visibility === 'hidden' ? 'it is hidden' : '', cs.opacity === '0' ? 'it is transparent' : '', parseFloat(cs.fontSize) < 8 ? 'its type is under 8 pixels' : ''].filter(x => x).join(', ');
  return ok ? '' : href + ' prints ' + shown + (want ? ', and should print " (' + want + ')"' : ', and should print no address') + (want && shown === '" (' + want + ')"' && notShown ? ' (the address is there but is not shown on paper: ' + notShown + ')' : '');
}).filter(x => x)"""
SITE_ADDRESS = 'https://inkindstandard.org'
OPEN_ALL = "() => { document.querySelectorAll('details').forEach(d => { d.open = true; }); }"   # what paper does (the script opens them at "beforeprint")
# Paper without the script (run 19, M3): a disclosure that is closed prints only its heading. Nothing here opens one; the page must already be open, as its HTML writes it.
LEFT_OUT = """() => [...document.querySelectorAll('main details, footer details')].filter(d => {
  const kids = [...d.children].filter(c => c.tagName !== 'SUMMARY');
  return kids.some(k => { const r = k.getBoundingClientRect(); return !(r.height > 0 && r.width > 0 && k.checkVisibility()); });
}).map(d => ((d.querySelector('summary') || {}).textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 60))"""
# Paper with the script on (run 19, M3): a listener added after the page's own sees what the page left closed when the browser starts to print.
WATCH_PRINT = """() => { window.__closedAtPrint = null; window.addEventListener('beforeprint', () => {
  window.__closedAtPrint = [...document.querySelectorAll('main details, footer details')].filter(d => !d.open)
    .map(d => ((d.querySelector('summary') || {}).textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 60)); }); }"""
# Paper, the words (run 21, Must fix 1): the words a page shows on paper, read as the browser shows them: a piece of text whose element is displayed and not faded out. Text kept in <noscript>
# is not part of a page with the script on, so it is set aside on both sides.
PAPER_WORDS = """() => { const out = [], w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
  while ((n = w.nextNode())) { const t = n.nodeValue.replace(/\\s+/g, ' ').trim(); if (!t || n.parentElement.closest('script, style, noscript, template')) continue;
    if (n.parentElement.checkVisibility({opacityProperty: true, visibilityProperty: true})) out.push(t); }
  return out; }"""
# Paper, nothing animates (run 21, Must fix 1): the browser takes its copy as it switches to print, and an animation that starts with the switch is at its first frame, with its words faded out.
PAPER_ANIMATIONS = """() => document.getAnimations().map(a => { const t = a.effect && a.effect.target;
  return a.playState + ' "' + (a.animationName || a.transitionProperty || '?') + '" on <' + (t ? t.tagName.toLowerCase() + (typeof t.className === 'string' && t.className ? ' class="' + t.className.slice(0, 30) + '"' : '') : '?') + '>'; })"""
WORDS = """() => ['header', 'main', 'footer'].map(s => { const e = document.querySelector(s); if (!e) return ''; const w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT), out = []; let n; while ((n = w.nextNode())) out.push(n.nodeValue); return out.join(' ').replace(/\\s+/g, ' ').trim(); })"""
EXTRA_WORDS = """() => ({
  tabs: [...document.querySelectorAll('[data-tab] h3')].map(h => h.textContent.replace(/\\s+/g, ' ').trim()).join(' '),
  switches: document.querySelectorAll('.util, .mnav').length })"""
STILL = """() => {
  const bad = [];
  for (const el of document.querySelectorAll('*')) {
    const cs = getComputedStyle(el), at = '<' + el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? ' class="' + el.className.slice(0, 30) + '"' : '') + '>';
    if (cs.animationName !== 'none') bad.push('an animation on ' + at);
    if (cs.transitionDuration.split(',').some(d => parseFloat(d) > 0)) bad.push('a transition on ' + at);
    if (cs.scrollBehavior !== 'auto') bad.push('smooth scrolling on ' + at);
  }
  if (document.querySelectorAll('.fx-wait, .dg-wait').length) bad.push('words or drawings left waiting to appear');
  if (document.getAnimations().length) bad.push('an animation is running');
  return [...new Set(bad)];
}"""
ANIMATIONS = """() => document.getAnimations().map(a => { const t = a.effect && a.effect.getComputedTiming ? a.effect.getComputedTiming() : null; return [a.animationName || a.transitionProperty || 'an animation', t ? t.endTime : 0, t ? t.iterations : 1]; })"""
COUNTS = """() => [...document.querySelectorAll('[data-count]')].map(f => { const n = f.querySelector('.fig-n'); return [f.getAttribute('data-count'), n ? n.textContent.trim() : null]; })"""
WAITING = """() => [...document.querySelectorAll('.fx-wait, .dg-wait')].map(e => e.tagName.toLowerCase() + '.' + e.className.slice(0, 30))"""
NAV_STATE = "() => ['.mast-nav nav', 'details.mnav'].map(s => { const e = document.querySelector(s); return !!e && e.getBoundingClientRect().width > 0 && getComputedStyle(e).display !== 'none'; })"
BG = "() => getComputedStyle(document.body).backgroundColor"
STORAGE_LINES = """(allowed) => {   // what the browser's storage holds besides the keys the site may keep; session storage holds nothing
  const out = [];
  try { const k = Object.keys(window.localStorage).filter(x => !allowed.includes(x)); if (k.length) out.push("the browser's storage holds " + JSON.stringify(k) + "; the one key the site keeps is \\"iks-theme\\", and only once a color is chosen"); } catch (e) { out.push('the storage could not be read'); }
  try { const s = Object.keys(window.sessionStorage); if (s.length) out.push('session storage holds ' + JSON.stringify(s) + '; the site keeps nothing there'); } catch (e) { /* off: nothing is kept */ }
  return out;
}"""
REST = """() => [...document.querySelectorAll('html, body, body *')].map(el => {   // where every element is, and how it is drawn, at this moment
  const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
  return [r.x, r.y, r.width, r.height].map(v => Math.round(v * 100) / 100).join(',') + '|' + cs.opacity + '|' + cs.transform;
})"""
REST_NAMES = """(indexes) => { const all = [...document.querySelectorAll('html, body, body *')]; return indexes.map(i => '<' + all[i].tagName.toLowerCase() + (all[i].className && typeof all[i].className === 'string' ? ' class="' + all[i].className.slice(0, 30) + '"' : '') + '> "' + (all[i].textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 30) + '"'); }"""
THEME_STATE = "() => [document.documentElement.getAttribute('data-theme'), (() => { try { return window.localStorage.getItem('iks-theme'); } catch (e) { return 'error'; } })()]"
PRESSED = "() => [...document.querySelectorAll('.theme button')].filter(b => b.getBoundingClientRect().width > 0).map(b => [b.getAttribute('data-theme'), b.getAttribute('aria-pressed')])"
FONTS = """() => ({ok: document.fonts.check('1em "Atkinson Hyperlegible"'), bad: [...document.fonts].filter(f => f.status === 'error').map(f => f.family + ' ' + f.style + ' ' + f.weight),
  family: getComputedStyle(document.body).fontFamily})"""
DIAGRAM = "() => { const b = document.querySelector('.dg-box'); if (!b) return null; const r = b.getBoundingClientRect(); return [getComputedStyle(b).display, Math.round(r.width), Math.round(r.height)]; }"
SCROLL = """async () => {
  const h = () => document.documentElement.scrollHeight, step = Math.max(200, Math.floor(window.innerHeight * 0.6));
  for (let y = 0; y < h(); y += step) { window.scrollTo(0, y); document.dispatchEvent(new Event('scroll')); await new Promise(r => setTimeout(r, 140)); }
  window.scrollTo(0, h()); await new Promise(r => setTimeout(r, 300)); window.scrollTo(0, 0);
}"""

# From the moment it is run, writes down every change to the document (an attribute, a text, an element added or taken away); CHANGES reads the list.
# With reduced motion asked for, a scroll through a page changes nothing (run 20): this shows the script's own check for that setting at work,
# which the words, counts and classes left a moment later cannot, since by then a count-up and a reveal have finished.
WATCH = """() => {
  window.__changes = [];
  new MutationObserver(list => list.forEach(m => {
    const t = m.target, el = t.nodeType === 1 ? t : t.parentElement;
    window.__changes.push((m.type === 'attributes' ? 'the ' + m.attributeName + ' of ' : m.type === 'characterData' ? 'the text of ' : 'the contents of ')
      + '<' + (el ? el.tagName.toLowerCase() : '?') + (el && typeof el.className === 'string' && el.className ? ' class="' + el.className.slice(0, 30) + '"' : '') + '>');
  })).observe(document.documentElement, { attributes: true, childList: true, subtree: true, characterData: true });
}"""
CHANGES = "() => window.__changes"
WEIGHT_LIMIT = 350000          # frame v0.6, section 7, "Speed": no page over 350 KB on a first visit, fonts included, hosted documents apart
BRAND_NAME = 'In-Kind Standard Model documents and public records home page'
TAB_WIDTHS = (320, 390, 1280)
JS_OFF_WIDTHS = (320, 390, 1280)
MOTION_LIMIT = 5000            # no motion longer than five seconds (frame v0.6, section 7); the effects themselves are held by the site check


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=str(PUB), **k)
    def guess_type(self, path): return TYPES.get(os.path.splitext(path)[1].lower(), 'application/octet-stream')
    def log_message(self, *a): pass


async def whole_page_on_paper(browser, base, addresses, fresh, found):
    """Run 21, Must fix 1. Paper is the page as printed from a screen: loaded with the script on, settled, then switched to print. Every word that the page shows on paper with the script off must
    be shown with the script on, with motion allowed and with reduced motion; and no animation may be in effect then, because an animation that starts with the switch is at its first frame when the
    browser takes its copy. (Found in Home's tabbed section: a heading the script had put away, and a panel that faded in again when paper showed it.)"""
    import collections
    for motion in ('no-preference', 'reduce'):
        tag = 'on paper with the script on' + (' and reduced motion' if motion == 'reduce' else '')
        ctx_off, page_off = await fresh(browser, viewport={'width': 1280, 'height': 800}, java_script_enabled=False, reduced_motion=motion)
        ctx_on, page_on = await fresh(browser, viewport={'width': 1280, 'height': 800}, reduced_motion=motion)
        for address in addresses:
            await page_off.goto(base + address, wait_until='networkidle')
            await page_off.emulate_media(media='print')
            off_ = collections.Counter(await page_off.evaluate(PAPER_WORDS))
            await page_off.emulate_media(media='screen')
            await page_on.goto(base + address, wait_until='networkidle')
            await page_on.wait_for_timeout(700)   # a reader has been reading: the page is still
            await page_on.emulate_media(media='print')
            await page_on.evaluate("() => window.dispatchEvent(new Event('beforeprint'))")   # what the browser sends first; the script opens the disclosures there
            on_ = collections.Counter(await page_on.evaluate(PAPER_WORDS))
            moving = await page_on.evaluate(PAPER_ANIMATIONS)
            await page_on.emulate_media(media='screen')
            for words in sorted((off_ - on_).elements()): found.append(f'{address} {tag}: the words "{words[:60]}" are shown with the script off and not with it on')
            for what in sorted(set(moving)): found.append(f'{address} {tag}: an animation is in effect ({what}); on paper nothing may be animated, because the copy is taken as the page switches to print')
        await ctx_off.close(); await ctx_on.close()


async def look(base, addresses):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        sys.exit('look check not run: the playwright package is not installed (RUNBOOK.md, section 2, says how to install it)')
    import collections, re
    found, stats = [], {}
    stray = set()      # every address asked for that is not the site's own
    odd = {}           # every request to the site's own address that is not a plain read of one of its files, by (address asked for, page that asked) (run 20, Should fix 1)
    def asked_by(r):
        try: u_ = r.frame.url
        except Exception: u_ = ''
        return (u_[len(base):].split('#')[0] or '/') if u_.startswith(base) else 'a page'
    def watch_request(r):
        if not r.url.startswith(base): stray.add(r.url)
        elif '?' in r.url: odd.setdefault((r.url[len(base):], asked_by(r)), 'it carries a query, which a plain read of a file does not')
        elif r.method != 'GET': odd.setdefault((r.url[len(base):], asked_by(r)), f'it is a {r.method}, not a plain read')
    async def fresh(browser, **kw):
        ctx = await browser.new_context(**kw)
        page = await ctx.new_page()
        page.on('request', watch_request)
        page.on('response', lambda r: odd.setdefault((r.url[len(base):], asked_by(r.request)), f'the site holds no such file (status {r.status})') if r.url.startswith(base) and r.status >= 400 else None)
        return ctx, page
    async def measure(page, address, tag, widths_lines=False):
        for line in await page.evaluate(PROBE): found.append(f'{address} {tag}: {line}')
        for line in await page.evaluate(TEXTBOX): found.append(f'{address} {tag}: {line}')
        for line in await page.evaluate(LINES, LINE_MAX if widths_lines else 0): found.append(f'{address} {tag}: {line}')
    async with async_playwright() as p:
        kw = {'args': os.environ.get('CHROME_ARGS', '').split()}
        if os.environ.get('CHROME'): kw['executable_path'] = os.environ['CHROME']
        try:
            browser = await p.chromium.launch(**kw)
        except Exception as e_:   # one plain line, not Playwright's traceback (run 7, N5)
            which_ = 'CHROME=' + os.environ['CHROME'] if os.environ.get('CHROME') else "Playwright's own Chromium"
            sys.exit(f'look check not run: the browser did not start ({which_}): {str(e_).strip().splitlines()[0][:160]}')
        if AXE:   # is the file axe-core? Asked before anything is measured, so that a wrong file does not cost the other results.
            ctx = await browser.new_context(bypass_csp=True)
            await ctx.add_init_script(path=AXE)
            page = await ctx.new_page()
            await page.goto(base + addresses[0])
            is_axe = await page.evaluate("() => typeof axe !== 'undefined' && typeof axe.run === 'function'")
            await ctx.close()
            if not is_axe:
                await browser.close()
                sys.exit(f'look check not run: the file AXE names ("{AXE}") is not axe-core: it defines no axe.run. Give the path of axe.min.js, or leave AXE unset.')
        # 1. Every page at every width, with the script on: closed as it arrives, then every disclosure open, then each reader's tab pressed.
        for width in sorted(set(WIDTHS) | set(LINE_WIDTHS) | set(TAB_WIDTHS)):
            ctx, page = await fresh(browser, viewport={'width': width, 'height': 800}, reduced_motion='reduce')   # nothing waits to appear here: motion has its own pass
            for address in addresses:
                resp = await page.goto(base + address, wait_until='networkidle')
                if not resp or resp.status != 200: found.append(f'{address} at {width}: not served')
                nav_ = await page.evaluate(NAV_STATE)
                if nav_ not in ([True, False], [False, True]): found.append(f'{address} at {width}: the menu is shown as {nav_} (the main list of links, the phone menu); exactly one of them must be shown')
                if width in WIDTHS: await measure(page, address, f'at {width}', width in LINE_WIDTHS)
                elif width in LINE_WIDTHS: await measure(page, address, f'at {width}', True)
                await page.evaluate(OPEN_ALL)
                await measure(page, address, f'at {width} with every disclosure open', width in LINE_WIDTHS)
                if width in TAB_WIDTHS:
                    for i in range(await page.locator('[role=tab]').count()):
                        tab = page.locator('[role=tab]').nth(i)
                        await tab.click()
                        label = (await tab.text_content() or '').strip()[:30]
                        panel = page.locator('[role=tabpanel]').nth(i)
                        if not await panel.is_visible(): found.append(f'{address} at {width}: the tab "{label}" does not show its panel')
                        if await page.locator('[role=tab][aria-selected=true]').count() != 1: found.append(f'{address} at {width}: after the tab "{label}" is pressed, {await page.locator("[role=tab][aria-selected=true]").count()} tabs are selected')
                        await measure(page, address, f'at {width} with the tab "{label}" selected', width in LINE_WIDTHS)
            await ctx.close()
        # 2. The same pages with the script off: every word is there, and everything fits.
        words_on = {}
        ctx, page = await fresh(browser, viewport={'width': 1280, 'height': 800})
        for address in addresses:
            await page.goto(base + address, wait_until='networkidle'); words_on[address] = (await page.evaluate(WORDS), await page.evaluate(EXTRA_WORDS))
        await ctx.close()
        for width in JS_OFF_WIDTHS:
            ctx, page = await fresh(browser, viewport={'width': width, 'height': 800}, java_script_enabled=False)
            for address in addresses:
                await page.goto(base + address, wait_until='networkidle')
                await measure(page, address, f'at {width} with the script off', width in LINE_WIDTHS)
                await page.evaluate(OPEN_ALL)
                await measure(page, address, f'at {width} with the script off and every disclosure open', width in LINE_WIDTHS)
                if width == 1280:
                    off = await page.evaluate(WORDS); on, extra = words_on[address]
                    allowed = [collections.Counter(), collections.Counter(extra['tabs'].split()), collections.Counter()]
                    allowed[0].update({w_: extra['switches'] for w_ in ('Light', 'Dark', 'Device')})
                    for part, o_, n_, ok_ in zip(('header', 'main', 'footer'), off, on, allowed):
                        co, cn = collections.Counter(o_.split()), collections.Counter(n_.split())
                        if co - cn: found.append(f'{address} with the script off: the script takes away words from the {part}: {sorted((co - cn).elements())[:6]}')
                        if (cn - co) - ok_: found.append(f'{address} with the script off: the script adds words to the {part} other than a tab\'s label or a theme button: {sorted(((cn - co) - ok_).elements())[:6]}')
            await ctx.close()
        # 3. Text contrast in each theme, with every disclosure open: the device's own choice, and a saved choice that differs from it.
        for scheme in ('light', 'dark'):
            for width in CONTRAST_WIDTHS:
                ctx, page = await fresh(browser, viewport={'width': width, 'height': 800}, color_scheme=scheme)
                for address in addresses:
                    await page.goto(base + address, wait_until='networkidle'); await page.evaluate(OPEN_ALL)
                    for line in await page.evaluate(CONTRAST, {'floor': TEXT_CONTRAST, 'paper': False}): found.append(f'{address} at {width} in {scheme} colors: {line}')
                await ctx.close()
        for device, saved in (('light', 'dark'), ('dark', 'light')):
            for width in CONTRAST_WIDTHS:
                ctx, page = await fresh(browser, viewport={'width': width, 'height': 800}, color_scheme=device)
                await ctx.add_init_script(f"try {{ window.localStorage.setItem('iks-theme', '{saved}'); }} catch (e) {{}}")
                for address in addresses:
                    await page.goto(base + address, wait_until='networkidle'); await page.evaluate(OPEN_ALL)
                    state = await page.evaluate(THEME_STATE)
                    if state[0] != saved: found.append(f'{address} at {width}: with "{saved}" saved on a {device} device the page carries the theme {state[0]}')
                    m_ = re.findall(r'\d+', await page.evaluate(BG)); lum_ = sum(int(x) for x in m_[:3]) / 3
                    if (saved == 'dark') != (lum_ < 128): found.append(f'{address} at {width}: with "{saved}" saved on a {device} device the page is the wrong color ({await page.evaluate(BG)})')
                    for line in await page.evaluate(CONTRAST, {'floor': TEXT_CONTRAST, 'paper': False}): found.append(f'{address} at {width} with {saved} colors chosen on a {device} device: {line}')
                await ctx.close()
        # On paper: the print colors, as the browser prints the page (C4-04), with every disclosure open as paper has them.
        ctx, page = await fresh(browser, viewport={'width': 1280, 'height': 800})
        await page.emulate_media(media='print')
        for address in addresses:
            await page.goto(base + address, wait_until='networkidle'); await page.evaluate(OPEN_ALL)
            for line in await page.evaluate(CONTRAST, {'floor': TEXT_CONTRAST, 'paper': True}): found.append(f'{address} on paper: {line}')
            for line in await page.evaluate(PAPER_LINKS, SITE_ADDRESS): found.append(f'{address} on paper: the link {line}')
        await ctx.close()
        # On paper with the script off (run 19, M3): the script opens every disclosure for print, so a reader without it gets the text only if the page is written open.
        ctx, page = await fresh(browser, viewport={'width': 1280, 'height': 800}, java_script_enabled=False)
        await page.emulate_media(media='print')
        for address in addresses:
            await page.goto(base + address, wait_until='networkidle')
            for title in await page.evaluate(LEFT_OUT): found.append(f'{address} on paper with the script off: the disclosure "{title}" prints without its text')
        await ctx.close()
        # On paper with the script on (run 19, M3): the script closes the disclosures for the screen and opens them again when the browser starts to print, so the page printed with the
        # script on has every word only if that handler runs. The browser's own print path fires the event; if it does not, the check says so, so that it cannot pass without looking.
        ctx, page = await fresh(browser, viewport={'width': 1280, 'height': 800})
        for address in addresses:
            await page.goto(base + address, wait_until='networkidle')
            await page.evaluate(WATCH_PRINT); await page.pdf()
            closed = await page.evaluate('() => window.__closedAtPrint')
            if closed is None: found.append(f'{address} on paper with the script on: the browser did not announce that it was about to print, so the check could not see what the page left closed')
            else:
                for title in closed: found.append(f'{address} on paper with the script on: the disclosure "{title}" is still closed when the browser starts to print')
        await ctx.close()
        # On paper, every word (run 21, Must fix 1): see whole_page_on_paper().
        await whole_page_on_paper(browser, base, addresses, fresh, found)
        layouts = 0
        if SWEEP:
            ctx, page = await fresh(browser, viewport={'width': SWEEP_FROM, 'height': 800})
            for address in addresses:
                await page.goto(base + address, wait_until='networkidle'); await page.evaluate(OPEN_ALL)
                seen = {}
                for width in range(SWEEP_FROM, SWEEP_TO + 1):
                    await page.set_viewport_size({'width': width, 'height': 800})
                    for line in await page.evaluate(LINES, 0): seen.setdefault(line, []).append(width)
                    layouts += 1
                for line, at in seen.items(): found.append(f'{address} at {len(at)} of the widths from {at[0]} to {at[-1]}: {line}')
            await ctx.close()
        runs = 0
        if AXE:
            for scheme in ('light', 'dark'):
                for width in AXE_WIDTHS:
                    # The page's own policy would stop the checker's helpers, so it is set aside for these runs only.
                    ctx = await browser.new_context(viewport={'width': width, 'height': 800}, color_scheme=scheme, bypass_csp=True, reduced_motion='reduce')   # a text caught in the middle of its fade-in has less contrast: motion has its own pass
                    await ctx.add_init_script(path=AXE)
                    page = await ctx.new_page()
                    for address in addresses:
                        await page.goto(base + address, wait_until='networkidle')
                        for opened in (False, True):
                            if opened: await page.evaluate(OPEN_ALL)
                            for line in await page.evaluate(AXE_RUN, AXE_TAGS): found.append(f'{address} at {width} in {scheme} colors{" with every disclosure open" if opened else ""}: axe-core: {line}')
                            runs += 1
                    await ctx.close()
        # 4. Reduced motion: nothing moves, nothing waits to appear, every word is there after a scroll through the page, and the page itself does not change as it is scrolled.
        for width in (390, 1280):
            ctx, page = await fresh(browser, viewport={'width': width, 'height': 800}, reduced_motion='reduce')
            for address in addresses:
                await page.goto(base + address, wait_until='networkidle'); await page.evaluate(WATCH); await page.evaluate(SCROLL); await page.wait_for_timeout(300)
                changed = await page.evaluate(CHANGES)
                if changed: found.append(f'{address} at {width} with reduced motion asked for: the page changes as it is scrolled ({len(changed)} changes; the first is {changed[0]}); with reduced motion asked for the script does nothing as a page is scrolled')
                for line in await page.evaluate(STILL): found.append(f'{address} at {width} with reduced motion asked for: {line}')
                for want, got in await page.evaluate(COUNTS):
                    if want != got: found.append(f'{address} at {width} with reduced motion asked for: a count reads {got}, not {want}')
                await measure(page, address, f'at {width} with reduced motion asked for')
            await ctx.close()
        # 5. Motion allowed: a reader's scroll through each page leaves every word shown, every count at its number, nothing waiting, and no animation past the limits.
        for width in (390, 1280):
            ctx, page = await fresh(browser, viewport={'width': width, 'height': 800}, reduced_motion='no-preference')
            for address in addresses:
                await page.goto(base + address, wait_until='networkidle')
                await page.evaluate(SCROLL); await page.wait_for_timeout(600)
                for name, end, iterations in await page.evaluate(ANIMATIONS):
                    if iterations is None or iterations == float('inf') or str(iterations) == 'Infinity' or end is None or end > MOTION_LIMIT: found.append(f'{address} at {width}: an animation ({name}) that does not end, or runs past {MOTION_LIMIT} ms (ends at {end} ms)')
                await page.wait_for_timeout(2000)
                for want, got in await page.evaluate(COUNTS):
                    if want != got: found.append(f'{address} at {width}: after a scroll through the page a count reads {got}, not {want}')
                for w_ in await page.evaluate(WAITING): found.append(f'{address} at {width}: after a scroll through the page {w_} still waits to appear')
                for line in await page.evaluate(TEXTBOX): found.append(f'{address} at {width} after a scroll through the page: {line}')
            await ctx.close()
        # 6. The theme buttons: what each press leaves in the page and in the browser's storage (at phone width the menu is opened first).
        for width in (1280, 390):
            ctx, page = await fresh(browser, viewport={'width': width, 'height': 800}, color_scheme='light')
            for address in addresses:
                await page.goto(base + address, wait_until='networkidle')
                if width < 700 and await page.locator('details.mnav > summary').count(): await page.locator('details.mnav > summary').click()
                group = page.locator('.mnav .theme' if width < 700 else '.util .theme')
                if not await group.count(): found.append(f'{address} at {width}: no theme buttons'); continue
                for value, want in (('dark', 'dark'), ('light', 'light'), ('', None)):
                    await group.locator(f'button[data-theme="{value}"]').click()
                    state = await page.evaluate(THEME_STATE)
                    if state != [want, want]: found.append(f'{address} at {width}: after the "{value or "device"}" button the page and storage hold {state}, not {[want, want]}')
                    shown = dict((a_ or '', b_) for a_, b_ in await page.evaluate(PRESSED))
                    if shown.get(value) != 'true' or sum(v_ == 'true' for v_ in shown.values()) != 1: found.append(f'{address} at {width}: after the "{value or "device"}" button the pressed states read {shown}')
                await group.locator('button[data-theme="dark"]').click(); await page.reload(wait_until='networkidle')
                if (await page.evaluate(THEME_STATE))[0] != 'dark': found.append(f'{address} at {width}: a saved choice of dark colors is not carried to the next load')
                for line in await page.evaluate(STORAGE_LINES, ['iks-theme']): found.append(f'{address} at {width} after the theme buttons: {line}')
                await page.evaluate("() => window.localStorage.clear()")
            await ctx.close()
        # 7. A first visit: what it loads, the fonts, the home link's name as the browser gives it, and the drawing's place.
        heaviest = (0, '')
        for width in (390, 1280):
            for address in addresses:
                ctx, page = await fresh(browser, viewport={'width': width, 'height': 800})
                seen = []
                page.on('response', lambda r: seen.append(r))
                await page.goto(base + address, wait_until='networkidle')
                await page.evaluate(SCROLL); await page.wait_for_load_state('networkidle')
                total = 0
                for r in seen:
                    try: total += len(await r.body())
                    except Exception: pass
                if total > WEIGHT_LIMIT: found.append(f'{address} at {width}: a first visit loads {total} bytes; the frame\'s limit is {WEIGHT_LIMIT // 1000} KB (frame v0.6, section 7)')
                if total > heaviest[0]: heaviest = (total, f'{address} at {width}')
                fonts = await page.evaluate(FONTS)
                if not fonts['ok'] or fonts['bad'] or 'Atkinson Hyperlegible' not in fonts['family']: found.append(f'{address} at {width}: the site\'s typeface is not in use or did not load: {fonts}')
                if width == 1280:
                    snap = await page.locator('a.brand').aria_snapshot()
                    if f'link "{BRAND_NAME}"' not in snap: found.append(f'{address}: the home link\'s accessible name is not "{BRAND_NAME}": {snap.strip().splitlines()[0][:100]}')
                    d = await page.evaluate(DIAGRAM)
                    if address == '/' and (d is None or d[0] == 'none' or not d[1] or not d[2]): found.append(f'{address} at {width}: the drawing of who is party to what is not shown')
                    if address == '/':
                        await page.set_viewport_size({'width': 1024, 'height': 800}); d = await page.evaluate(DIAGRAM)
                        if d is not None and d[0] != 'none': found.append(f'{address} at 1024: the drawing is shown below the width it is made for')
                await ctx.close()
        stats['heaviest'] = heaviest
        # 8. What the pages do by themselves (run 20, Should fix 1 and 2): a first visit leaves no cookie and nothing in the browser's storage, and, with no one touching the page, nothing moves
        # or fades, with motion allowed and with reduced motion asked for. The text of the script cannot show this: a name put together from pieces passes every rule on its words.
        for reduced, width in ((False, 1280), (False, 390), (True, 1280)):
            for address in addresses:
                ctx, page = await fresh(browser, viewport={'width': width, 'height': 800}, reduced_motion='reduce' if reduced else 'no-preference')
                tag = f'at {width}' + (' with reduced motion asked for' if reduced else '')
                await page.goto(base + address, wait_until='networkidle')
                await page.evaluate('async () => { await document.fonts.ready; }'); await page.wait_for_timeout(1500)
                # A finite animation ends: read every 400 ms until two readings in a row agree, for at most six seconds (a slow machine may still be finishing the count-up), then read twice more
                # over a second. A page whose script keeps moving something never agrees, and is caught by the last two.
                readings = [await page.evaluate(REST)]
                for _ in range(15):
                    await page.wait_for_timeout(400); readings.append(await page.evaluate(REST))
                    if readings[-1] == readings[-2]: break
                for gap in (500, 500):
                    await page.wait_for_timeout(gap); readings.append(await page.evaluate(REST))
                readings = readings[-3:]
                if len({len(x_) for x_ in readings}) != 1: found.append(f'{address} {tag}: elements are added or taken away with no one touching the page')
                else:
                    moving = sorted({i for a_, b_ in zip(readings, readings[1:]) for i, (x_, y_) in enumerate(zip(a_, b_)) if x_ != y_})
                    if moving: found.append(f'{address} {tag}: {", ".join(await page.evaluate(REST_NAMES, moving[:3]))} moves or fades on its own, with no one touching the page')
                for c_ in await ctx.cookies(): found.append(f'{address} {tag}: a first visit left a cookie ({c_["name"]}); the site sets none')
                for line in await page.evaluate(STORAGE_LINES, []): found.append(f'{address} {tag}: a first visit: {line}')
                await ctx.close()
        for u_ in sorted(stray): found.append(f'a request for an address that is not the site\'s own: {u_}')
        for (u_, page_), why_ in sorted(odd.items()): found.append(f"{u_} (made by the page {page_}): a request to the site's own address that is not a plain read of one of its files; {why_}")
        await browser.close()
    return found, runs, layouts, stats


def main():
    assert (PUB / 'index.html').is_file(), f'no index.html in {PUB}'
    if AXE and not pathlib.Path(AXE).is_file():
        sys.exit(f'look check not run: AXE is set to "{AXE}", and no file is there. Give the path of axe-core\'s axe.min.js, or leave AXE unset.')
    addresses = sorted('/' + q.relative_to(PUB).as_posix().removesuffix('index.html') for q in PUB.rglob('*.html'))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('127.0.0.1', 0), Handler) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        found, runs, layouts, stats = asyncio.run(look(f'http://127.0.0.1:{server.server_address[1]}', addresses))
        server.shutdown()
    print(f'look check: {len(addresses)} pages at {", ".join(map(str, WIDTHS))} pixels wide, every word shown; lines of text at {" and ".join(map(str, LINE_WIDTHS))}; text contrast in light and dark colors at {" and ".join(map(str, CONTRAST_WIDTHS))}, and on paper')
    print(f'also: every disclosure open and every tab pressed; the script off, on screen and on paper, and on paper with the script on, where it shows every word that paper shows without it and nothing is animated; the address each link shows on paper; a saved color choice; the theme buttons; reduced motion; a scroll through each page; a first visit at most {stats["heaviest"][0]} bytes ({stats["heaviest"][1]}), the limit being {WEIGHT_LIMIT} bytes; nothing the pages do by themselves: only plain reads of the site\'s own files, no cookie, no stored setting before a choice, nothing that moves at rest; with reduced motion asked for, no change to a page as it is scrolled')
    print(f'axe-core: {runs} runs (every page, light and dark colors, at {" and ".join(map(str, AXE_WIDTHS))} pixels wide)' if AXE
          else 'axe-core: not run. To run it, set AXE to the path of axe.min.js (npm install axe-core)')
    print(f'sweep: {layouts} layouts (every page at every width from {SWEEP_FROM} to {SWEEP_TO} pixels, for a line that begins with a mark of punctuation)' if SWEEP
          else f'sweep: not run. To try every width from {SWEEP_FROM} to {SWEEP_TO} pixels for a line that begins with a mark of punctuation, set SWEEP=1')
    if found:
        print('PROBLEMS:'); [print(' -', f) for f in found]; sys.exit(1)
    skipped = [n for n, on in (('axe-core', AXE), ('the sweep', SWEEP)) if not on]
    print('PASS' + (', without ' + ' and '.join(skipped) if skipped else ''))   # what was not run is said (run 11, Note 3)


if __name__ == '__main__':
    main()
