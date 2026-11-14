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
         '.css': 'text/css; charset=utf-8', '.woff': 'font/woff', '.ico': 'image/vnd.microsoft.icon'}

PROBE = """() => {
  const vw = document.documentElement.clientWidth, out = [];
  if (document.documentElement.scrollWidth > vw + 1) out.push('the page scrolls sideways');
  for (const el of document.querySelectorAll('main *, header *, footer *')) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || el.closest('svg') || el.closest('.vh')) continue;   // .vh: words kept for screen readers only
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0 || r.right <= 0) continue;
    const name = '<' + el.tagName.toLowerCase() + '> "' + (el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 40) + '"';
    if (r.right > vw + 1) out.push(name + ' runs past the right edge of the window');
    if (cs.overflowX !== 'visible' && el.scrollWidth > el.clientWidth + 1) out.push(name + ' is cut off or scrolls sideways');
    if (cs.overflowY !== 'visible' && el.scrollHeight > el.clientHeight + 1 && (el.textContent || '').trim()) out.push(name + ' is cut off at the bottom');
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
  const say = (kind, list) => list.map(v => kind + ' ' + v.id + ' (' + v.nodes.length + ' places): ' + v.help);
  return say('violation', r.violations).concat(say('could not decide', r.incomplete));
}"""


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=str(PUB), **k)
    def guess_type(self, path): return TYPES.get(os.path.splitext(path)[1].lower(), 'application/octet-stream')
    def log_message(self, *a): pass


async def look(base, addresses):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        sys.exit('look check not run: the playwright package is not installed (RUNBOOK.md, section 2, says how to install it)')
    found = []
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
        for width in sorted(set(WIDTHS) | set(LINE_WIDTHS)):
            ctx = await browser.new_context(viewport={'width': width, 'height': 800})
            page = await ctx.new_page()
            for address in addresses:
                resp = await page.goto(base + address, wait_until='networkidle')
                if not resp or resp.status != 200: found.append(f'{address} at {width}: not served')
                if width in WIDTHS:
                    for line in await page.evaluate(PROBE): found.append(f'{address} at {width}: {line}')
                    for line in await page.evaluate(TEXTBOX): found.append(f'{address} at {width}: {line}')
                for line in await page.evaluate(LINES, LINE_MAX if width in LINE_WIDTHS else 0): found.append(f'{address} at {width}: {line}')
            await ctx.close()
        for scheme in ('light', 'dark'):
            for width in CONTRAST_WIDTHS:
                ctx = await browser.new_context(viewport={'width': width, 'height': 800}, color_scheme=scheme)
                page = await ctx.new_page()
                for address in addresses:
                    await page.goto(base + address, wait_until='networkidle')
                    for line in await page.evaluate(CONTRAST, {'floor': TEXT_CONTRAST, 'paper': False}): found.append(f'{address} at {width} in {scheme} colors: {line}')
                await ctx.close()
        # On paper: the print colors, as the browser prints the page (C4-04).
        ctx = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await ctx.new_page()
        await page.emulate_media(media='print')
        for address in addresses:
            await page.goto(base + address, wait_until='networkidle')
            for line in await page.evaluate(CONTRAST, {'floor': TEXT_CONTRAST, 'paper': True}): found.append(f'{address} on paper: {line}')
        await ctx.close()
        layouts = 0
        if SWEEP:
            ctx = await browser.new_context(viewport={'width': SWEEP_FROM, 'height': 800})
            page = await ctx.new_page()
            for address in addresses:
                await page.goto(base + address, wait_until='networkidle')
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
                    ctx = await browser.new_context(viewport={'width': width, 'height': 800}, color_scheme=scheme, bypass_csp=True)
                    await ctx.add_init_script(path=AXE)
                    page = await ctx.new_page()
                    for address in addresses:
                        await page.goto(base + address, wait_until='networkidle')
                        for line in await page.evaluate(AXE_RUN, AXE_TAGS): found.append(f'{address} at {width} in {scheme} colors: axe-core: {line}')
                        runs += 1
                    await ctx.close()
        await browser.close()
    return found, runs, layouts


def main():
    assert (PUB / 'index.html').is_file(), f'no index.html in {PUB}'
    if AXE and not pathlib.Path(AXE).is_file():
        sys.exit(f'look check not run: AXE is set to "{AXE}", and no file is there. Give the path of axe-core\'s axe.min.js, or leave AXE unset.')
    addresses = sorted('/' + q.relative_to(PUB).as_posix().removesuffix('index.html') for q in PUB.rglob('*.html'))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('127.0.0.1', 0), Handler) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        found, runs, layouts = asyncio.run(look(f'http://127.0.0.1:{server.server_address[1]}', addresses))
        server.shutdown()
    print(f'look check: {len(addresses)} pages at {", ".join(map(str, WIDTHS))} pixels wide, every word shown; lines of text at {" and ".join(map(str, LINE_WIDTHS))}; text contrast in light and dark colors at {" and ".join(map(str, CONTRAST_WIDTHS))}, and on paper')
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
