#!/usr/bin/env python3
"""Assembles inkindstandard.org: joins each page's text (src/pages) to the one header and footer
(src/layout.html) and writes plain files to docs/, the folder GitHub Pages publishes from the main branch
(decision sheet 2, E5 A, 12 November 2026; until then the folder was public/). Standard library only.

  python3 build.py            write docs/
  python3 build.py --check    fail if docs/ differs from what this script would write
  python3 build.py --local    write a copy into local/ with links as folder/index.html, for opening from a disk

Needs Python 3.10 or later, and nothing else.
docs/files/ holds the hosted release files. This script never writes or removes them;
checks/check_site.py checks each one against Zenodo's checksum. It also leaves a CNAME file alone,
which GitHub Pages adds to the published folder for a custom domain.
The pages are written to a temporary folder first and put in place only when every page has been made,
so an error in one page leaves docs/ as it was.
"""
import filecmp, hashlib, html, json, pathlib, re, shutil, sys, tempfile, urllib.parse
def _stopped(kind, value, tb, _here=str(pathlib.Path(__file__).resolve())):   # the file's path, kept: Python 3.13 removes __file__ before the hook runs
    """When the build refuses or breaks, say why in one plain line, not a traceback (the build check of candidate 4, C4-22)."""
    import traceback, os.path
    frames_ = traceback.extract_tb(tb) if tb else []
    own_ = [f for f in frames_ if str(pathlib.Path(f.filename).resolve()) == _here]   # this file's line, not the library's (run 7, S7)
    where = (own_ or frames_ or [None])[-1]
    print(f'The build stopped{f" at line {where.lineno} of {os.path.basename(where.filename)}" if where else ""}: {kind.__name__}: {value}', file=sys.stderr)
sys.excepthook = _stopped

ROOT = pathlib.Path(__file__).resolve().parent
SRC, PUB = ROOT / 'src', ROOT / 'docs'
SITE = 'https://inkindstandard.org/'
CURRENT = '2026.4'   # the release the pages show as current; a new release changes this line and the words that name it (RUNBOOK.md)


def zenodo_list(name):
    """A release's saved Zenodo list, read with the keys the build uses; a list that lacks one stops the build with the file's name, not a bare KeyError (run 20, Note 2)."""
    z = json.loads((SRC / 'releases' / f'{name}.zenodo.json').read_text(encoding='utf-8'))
    ok = (isinstance(z, dict) and 'release' in z and isinstance(z.get('records'), dict) and {'instruments', 'guide'} <= set(z['records'])
          and all(isinstance(r, dict) and {'doi', 'conceptdoi', 'total', 'published', 'files'} <= set(r) and isinstance(r['files'], list)
                  and all(isinstance(f, dict) and {'name', 'size'} <= set(f) for f in r['files']) for r in z['records'].values()))
    if not ok:
        sys.exit(f'src/releases/{name}.zenodo.json: the saved list lacks "release" or "records", or a record in it lacks "doi", "conceptdoi", "total", "published" or "files" with names and sizes; save Zenodo\'s list of the release\'s files there again (RUNBOOK.md, section 4)')
    return z
# The menu, in the frame's order (frame v0.6, section 4). A page is listed here only once it is live. "@screen" is the Screen's own page,
# at the address in src/screen.json ("Public records" in the menu). The reader links stand above the menu, and the footer has three lists.
NAV = [('materials/', 'Model documents'), ('@screen', 'Public records')]
READERS = [('contact/', 'Contact')]
FOOT = {'The work': [('materials/', 'Model documents'), ('@screen', 'Public records')],
        'The project': [('funding/', 'Who pays for the work')],
        'This site': [('contact/', 'Contact'), ('privacy/', 'Privacy statement'), ('accessibility/', 'Accessibility statement')]}
KEYS = {'title', 'tab', 'path', 'description', 'updated', 'budget', 'ceiling', 'release', 'nav', 'theirs'}
KEPT = {'files', 'CNAME'}
# The byline appears once on the site: the first line of the home page's section "Who prepares this work", placed there
# with {{byline}} (decision sheet 2, E2 B, 12 November 2026). Every page's footer carries the status line.
BYLINE = 'Prepared by Timothy Smith · Citizen-prepared working draft · Not legal advice'
STATUS = 'Citizen-prepared working draft · Not legal advice'
FORMATS = {'.txt': 'plain text', '.md': 'Markdown text'}
# The known gaps, in the same words wherever they appear. A page places this notice with {{gaps}}.
GAPS = 'no county has adopted the model documents, no lawyer has reviewed them, and there is no organization yet.'
GAPS_NOTICE = f'<p class="notice fixed"><strong>Known gaps:</strong> {GAPS}</p>'


def unbroken(line):
    """The byline or status line with each of its parts in a span, so that where there is room a line ends
    after a dot between parts and not inside "Citizen-prepared". The words are unchanged."""
    parts = line.split(' · ')
    return ' '.join(f'<span class="nb">{html.escape(p)}{" ·" if i < len(parts) - 1 else ""}</span>' for i, p in enumerate(parts))


def screen_words():
    """The title and opening line of the Screen, as given for the link
    (src/screen.json). A page places them with {{screen:title}}, {{screen:opening}} and {{screen:address}}."""
    return json.loads((SRC / 'screen.json').read_text(encoding='utf-8'))


def file_note(release, record, name):
    """The format and size of a hosted file, as the release page shows them: "(Markdown, 33 KB)"."""
    zen = zenodo_list(release)
    size = {f['name']: f['size'] for f in zen['records'][record]['files']}[name]
    return f'({FORMATS[pathlib.PurePosixPath(name).suffix]}, {max(1, round(size / 1000))} KB)'


# Each license in plain words, as the Materials page gives it (the build check of candidate 3, C3-08): the license's own name, then what it lets a reader do.
GLOSS = {'CC0 1.0': 'free to use without credit', 'CC BY 4.0': 'free to use with credit and a note of any changes'}


def doi_link(doi):
    return f'<a class="doi" href="https://doi.org/{html.escape(doi)}">doi:{html.escape(doi).replace("/", "/<wbr>")}</a>'   # a line may break after the slash, never inside the number


def zenodo_read(release):
    """The day the saved copy of Zenodo's list was read, from the list's own note, so that a page says how old the check's reference is (run 19, N4)."""
    zen = zenodo_list(release)
    m = re.search(r'\d{1,2} [A-Z][a-z]+ 20\d\d', zen['read'])
    assert m, f'{release}: the saved Zenodo list gives no day it was read'
    return m.group(0)


def record_doi(release, record, which='doi'):
    """A record's DOI from Zenodo's saved list: its own ('doi'), or the one that always leads to the newest release ('conceptdoi')."""
    zen = zenodo_list(release)
    return doi_link(zen['records'][record][which])


MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']


def published(release):
    """The day a release was published, in words, from Zenodo's saved list: no release date is typed by hand on a page."""
    zen = zenodo_list(release)
    days = {r['published'] for r in zen['records'].values()}
    assert len(days) == 1, f'{release}: its two records have different dates'
    y, m, d = days.pop().split('-')
    return f'{int(d)} {MONTHS[int(m) - 1]} {y}'


ICONS = json.loads((SRC / 'icons.json').read_text(encoding='utf-8'))['icons']
HOME_ICON = {'std': 'STD', 'item': 'ITEM', 'lease': 'LEASE', 'priv': 'PRIV'}
VERDICT = {'Works': 'ok', 'Works with a condition': 'cond', 'Fits provisionally': 'prov'}   # the classes of the verdicts the home page shows; any other verdict stops the build until its class is chosen


def release_json(rel):
    return json.loads((SRC / 'releases' / f'{rel}.json').read_text(encoding='utf-8'))


def earlier_json():
    return json.loads((SRC / 'releases' / 'earlier.json').read_text(encoding='utf-8'))['releases']


def icon(name):
    """A line icon from src/icons.json, drawn for the site; it names a thing and is hidden from a screen reader."""
    return f'<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">{ICONS[name]}</svg>'


def mark_inner():
    return (SRC / 'logo.inc').read_text(encoding='utf-8').split('-->\n', 1)[1].strip()


def mark_svg(cls=''):
    """The logo's mark from src/logo.inc: small in the page header, large and faint in a page's head."""
    attr = f' class="{cls}"' if cls else ''
    return f'<svg{attr} viewBox="497 502 1005 995" aria-hidden="true" focusable="false">{mark_inner()}</svg>'


def saved_screen():
    """The Screen's words and counts as saved on the day read (src/screen_saved.json). The home page quotes them, and the check holds every quoted word to them."""
    return json.loads((SRC / 'screen_saved.json').read_text(encoding='utf-8'))


def day_short(iso):
    y, m, d = iso.split('-')
    return f'{int(d)} {MONTHS[int(m) - 1]}'


def versioned(data):
    """The documents of a release that show a version: the release's own list, without its About, start-here, change-log, manifest and license files."""
    return [d for d in data['instruments'] + data['guide'] if d['version']]


def guide_file(data):
    return next(b['file'] for b in data['begin'] if b['name'] == 'Plain Language Guide')


def guide_link(root, data):
    return f'{root}files/{data["release"]}/guide/{guide_file(data)}'


def home_release(root, index):
    """The release card in the opening, from the release's own data (src/releases/)."""
    data = release_json(CURRENT); e = html.escape
    early = sorted(earlier_json(), key=lambda r: r['published'])
    recs = {r['key']: r for r in data['records']}
    count = {'instruments': len([d for d in data['instruments'] if d['version']]), 'guide': len([d for d in data['guide'] if d['version']])}

    def rec(k):
        r = recs[k]
        return f'<span class="theirs">{e(r["contents"])}</span> ({count[k]} documents). {doi_link(r["doi"])}, {e(r["license"])}, {GLOSS[r["license"]]}'
    earlier = ', '.join(f'{e(r["release"])} ({day_short(r["published"])})' for r in early)
    note = file_note(CURRENT, 'guide', guide_file(data))
    return ('<article class="release rise" aria-labelledby="rel-title">\n'
            f'<div class="release-top"><span class="pill p-pub">Published</span><span class="mono muted">Release {CURRENT}</span></div>\n'
            '<div class="release-body">\n'
            f'<h2 id="rel-title" class="h3 theirs">{e(data["title"])}</h2>\n<dl class="facts">\n'
            f'<dt>Published</dt><dd>{published(CURRENT)}</dd>\n<dt>Record 1</dt><dd>{rec("instruments")}</dd>\n<dt>Record 2</dt><dd>{rec("guide")}</dd>\n'
            f'<dt>Earlier</dt><dd>{earlier}</dd>\n</dl>\n'
            '<p class="small muted">Not legal advice. <span class="theirs">No county has adopted the model documents, and no lawyer has reviewed them.</span></p>\n'
            f'<div class="actions"><a class="btn" href="{root}materials/{CURRENT}/{index}">Open Release {CURRENT}</a>'
            f'<a class="btn btn-2" href="{guide_link(root, data)}"><span>Plain Language Guide <span class="nb">{e(note)}</span></span></a></div>\n</div>\n</article>')


def materials_release(root, index):
    """The release card on the Model documents page: two columns, the release's own words and data."""
    data = release_json(CURRENT); e = html.escape
    recs = {r['key']: r for r in data['records']}
    count = {'instruments': len([d for d in data['instruments'] if d['version']]), 'guide': len([d for d in data['guide'] if d['version']])}
    note = file_note(CURRENT, 'guide', guide_file(data))

    def rec(k):
        r = recs[k]
        return f'<span class="theirs">{e(r["contents"])}</span> ({count[k]} documents). {doi_link(r["doi"])}, {e(r["license"])}, {GLOSS[r["license"]]}'
    return ('<article class="release" aria-labelledby="rel-title">\n'
            f'<div class="release-top"><span class="pill p-pub">Published</span><span class="mono muted">Release {CURRENT} · {published(CURRENT)}</span></div>\n'
            '<div class="release-body two">\n<div>\n<p class="eyebrow">Data centers · Florida</p>\n'
            f'<h2 id="rel-title" class="h3 theirs">{e(data["title"])}</h2>\n'
            f'<p class="muted">Every file is kept at Zenodo, a public archive, as two records, each with its own license and permanent address (DOI). The copies on this site are checked against Zenodo\'s own list, read on {zenodo_read(CURRENT)}.</p>\n'
            f'<div class="actions"><a class="btn" href="{root}materials/{CURRENT}/{index}">Open Release {CURRENT}</a>'
            f'<a class="btn btn-2" href="{guide_link(root, data)}"><span>Plain Language Guide <span class="nb">{e(note)}</span></span></a></div>\n</div>\n'
            f'<dl class="facts">\n<dt>Record 1</dt><dd>{rec("instruments")}</dd>\n<dt>Record 2</dt><dd>{rec("guide")}</dd>\n'
            f'<dt>Known gaps</dt><dd class="theirs">{e(data["gaps"].removeprefix("Known gaps: ")[0].upper() + data["gaps"].removeprefix("Known gaps: ")[1:])}</dd>\n</dl>\n</div>\n</article>')


def home_homes(root, index):
    s = saved_screen(); e = html.escape
    out = ['<div class="homes">']
    for h in s['homes']:
        out.append(f'<div class="home" data-h="{h["key"]}"><h3><span class="ico">{icon(HOME_ICON[h["key"]])}</span><span class="theirs">{e(h["name"])}</span></h3>'
                   f'<p class="theirs">{e(h["line"])}</p></div>')
    return '\n'.join(out + ['</div>'])


def home_diagram(root, index):
    """A drawing of who is party to what, made from the four homes' names. It repeats the four lines under it, so a screen reader skips it, and it is left out on a narrow page."""
    def card(x, name, key):
        return (f'<g class="dg-card"><rect x="{x + 1}" y="45" width="182" height="146" rx="14"/>'
                f'<g class="dg-ico" transform="translate({x + 77} 88) scale(1.25)">{ICONS[key]}</g>'
                f'<text x="{x + 92}" y="143" text-anchor="middle">{name}</text></g>')

    def line(h, x1, x2, y, w=2, arrow=False):
        head = f'<path class="ah" d="M{x2 - 7} {y - 4}L{x2} {y}L{x2 - 7} {y + 4}Z"/>' if arrow else ''
        return f'<g class="dg-line" data-h="{h}"><path class="ln" pathLength="1" d="M{x1} {y}H{x2 - (6 if arrow else 0)}" stroke-width="{w}"/>{head}</g>'

    def lab(h, x, y, text, cls=''):
        return f'<text class="dg-lab{cls}" data-h="{h}" x="{x}" y="{y}" text-anchor="middle">{text}</text>'
    names = {h['key']: h['name'] for h in saved_screen()['homes']}
    return ('<div class="dg-box"><svg class="dg" viewBox="0 0 984 200" aria-hidden="true" focusable="false">'
            '<text class="dg-cap" x="0" y="17">Who is party to what</text>'
            + card(0, 'County', 'COUNTY') + card(400, 'Developer', 'DEV') + card(800, 'Community group', 'GROUP')
            + line('std', 185, 399, 81, arrow=True) + line('item', 185, 400, 118) + line('lease', 185, 400, 155) + line('priv', 584, 800, 118, 3)
            + f'<g class="theirs">{lab("std", 292, 65, names["std"])}{lab("item", 292, 102, names["item"])}{lab("lease", 292, 139, names["lease"])}{lab("priv", 692, 102, names["priv"])}</g>'
            + f'<g class="theirs">{lab("priv", 692, 142, "The county is not a party", " dg-note")}</g>'
            + '</svg></div>')


def home_items(root, index):
    s = saved_screen(); e = html.escape
    out = ['<div class="items">']
    for it in s['items']:
        conds = ''.join(f'<p class="cond theirs">{e(x)}</p>' for x in (it['vsub'], it['hnote']) if x)   # the condition and the home note, each on a line of its own, as the record has them (run 19, N1)
        chips = ''.join(f'<span class="chip theirs">{e(c)}</span>' for c in it['chips'])
        out.append('<article class="item" data-reveal>'
                   f'<p class="kick theirs">{e(it["sec"])}</p><h3 class="theirs">{e(it["name"])}</h3>'
                   f'<div class="tags"><span class="vd {VERDICT[it["verdict"]]} theirs">{e(it["verdict"])}</span>{chips}</div>'
                   f'{conds}'
                   f'<details class="more" open data-fold><summary>What it would do</summary><p class="theirs">{e(it["lead"])}</p></details>'
                   f'<div class="meta"><p class="ev theirs">{e(it["evLabel"])} {e(it["evStatus"])}</p><p class="evnote theirs">{e(it["evText"])}</p></div></article>')
    return '\n'.join(out + ['</div>'])


def home_numbers(root, index):
    s = saved_screen(); e = html.escape
    data = release_json(CURRENT)
    early = earlier_json()
    days = sorted([r['published'] for r in early] + [published_iso(CURRENT)])
    ver = re.search(r'Version (\d+ \w+ \d{4})', s['version_line']).group(1)
    stat = re.search(r'County status as of (\d+ \w+ \d{4})', s['version_line']).group(1)
    c = s['counts']; page = e(s['source']['page'])

    def fig(n, label, small, href):
        return (f'<div class="num"><span class="fig" data-count="{n}"><span class="fig-n" aria-hidden="true">{n}</span><span class="vh">{n}</span></span>'
                f'<p><a href="{href}">{label}</a></p><small>{small}</small></div>')
    return '<div class="nums-grid">\n' + '\n'.join([
        fig(len(early) + 1, 'releases published', f'{day_short(days[0])} to {published(CURRENT)}', f'{root}materials/{index}#releases'),
        fig(len(versioned(data)), f'documents in Release {CURRENT}, each with its version', f'{published(CURRENT)}', f'{root}materials/{index}#all'),
        fig(c['items'], 'items on the public record', f'Version {ver}', page),
        fig(c['actions'], f'<span class="theirs">{e(s["labels"]["actions"].format(**c))}</span>', f'County status as of {stat}', page),
        f'<div class="num"><span class="fig"><span class="fig-n">{c["provisions_delivered"]}</span></span><p><a href="{page}"><span class="theirs">{e(s["labels"]["delivered"])}</span></a></p>'
        f'<small>Version {ver}</small><small class="theirs">{e(s["labels"]["none_delivered"])}</small></div>',
    ]) + '\n</div>'


def published_iso(release):
    zen = zenodo_list(release)
    days = {r['published'] for r in zen['records'].values()}
    assert len(days) == 1, f'{release}: its two records have different dates'
    return days.pop()


def md_inline(s):
    """Bold is the only inline markup in the Guide's steps; anything else stops the build."""
    s = html.escape(s, quote=False)
    assert not re.search(r'[`_<>\\]|\*(?!\*)', s.replace('**', '')), f'markup the build does not carry: {s[:60]!r}'
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)


def md_blocks(lines):
    """Paragraphs and bullet lists, as the Guide writes them."""
    out, para, items = [], [], []

    def flush():
        nonlocal para, items
        if para: out.append('<p>' + md_inline(' '.join(para)) + '</p>'); para = []
        if items: out.append('<ul>' + ''.join(f'<li>{md_inline(i)}</li>' for i in items) + '</ul>'); items = []
    for l in lines:
        if not l.strip(): flush()
        elif l.startswith('- '):
            if para: flush()
            items.append(l[2:].strip())
        else:
            if items: flush()
            para.append(l.strip())
    flush()
    return ''.join(out)


def guide_steps(root, index):
    """The eight steps of the Plain Language Guide's section 2, in the Guide's own words (frame v0.6, section 6.2): step 1 open,
    each other step behind the browser's own disclosure control, so that it works without scripts."""
    data = release_json(CURRENT)
    g = (PUB / 'files' / CURRENT / 'guide' / guide_file(data)).read_text(encoding='utf-8')
    sec = g[g.index('## 2. The instruments, in the order a county would use them'):g.index('### The two methodology tests')]
    parts = re.split(r'(?m)^### ', sec)[1:]
    steps = [p for p in parts if p.startswith('Step ')]
    track = [p for p in parts if p.startswith('Outside the county')]
    assert len(steps) == 8 and len(track) == 1, (len(steps), len(track))
    out = ['<ol class="stepper theirs">']
    for n, p in enumerate(steps, 1):
        head, _, body = p.partition('\n')
        title = re.sub(r'^Step \d+\. ', '', head.strip())
        assert title != head.strip(), f'step {n}: its heading does not begin "Step {n}."'
        opt = ' class="opt"' if title.startswith('Optional') else ''
        text = md_blocks(body.split('\n'))
        if n == 1:
            out.append(f'<li{opt}><div class="stepcard"><h3>{html.escape(title)}</h3><div class="body">{text}</div></div></li>')
        else:
            out.append(f'<li{opt}><details open data-fold><summary>{html.escape(title)}</summary><div class="body">{text}</div></details></li>')
    out.append('</ol>')
    thead, _, tbody = track[0].partition('\n')
    first = [l for l in tbody.split('\n') if l.strip()][0]
    note = file_note(CURRENT, 'guide', guide_file(data))
    out.append(f'<div class="card community"><h3 class="theirs">{html.escape(thead.strip())}</h3><p class="muted"><span class="theirs">{html.escape(first)}</span> '
               f'<a href="{guide_link(root, data)}">Read it in the Plain Language Guide</a> <span class="nb">{html.escape(note)}</span></p></div>')
    return '\n'.join(out)


def begin_list(root, index):
    data = release_json(CURRENT); e = html.escape
    return '<ol class="steps">' + ''.join(
        f'<li><div><strong class="theirs"><a href="{root}files/{CURRENT}/{b["record"]}/{e(b["file"])}">{e(b["name"])}</a>:</strong> <span class="theirs">{e(b["quote"])}</span></div></li>'
        for b in data['begin']) + '</ol>'


def docs_list(key):
    """A record's heading, as the release names it, and its documents that show a version, each with that version."""
    def make(root, index):
        data = release_json(CURRENT); e = html.escape
        label = next(r['label'] for r in data['records'] if r['key'] == key)
        items = [d for d in data[key] if d['version']]
        return (f'<h3 class="theirs">{e(label)}</h3><ul class="docs theirs">'
                + ''.join(f'<li><span>{e(d["name"])}</span><span class="v">{e(d["version"].removeprefix("Release "))}</span></li>' for d in items) + '</ul>')
    return make


NUMWORD = {1: 'One', 2: 'Two', 3: 'Three', 4: 'Four', 5: 'Five', 6: 'Six', 7: 'Seven', 8: 'Eight', 9: 'Nine'}


def home_items_heading(root, index):
    s = saved_screen()
    return f'<h3>{NUMWORD[len(s["items"])]} of the {s["counts"]["items"]} items on the public record</h3>'


PASSING = ('Works', 'Works with a condition', 'Fits provisionally')   # the Screen's labels for an item that passes its test (in its source, "Passes" and "Passes with proviso"); Home's line on its cards says all of them pass


def home_items_note(root, index):
    """The project says that it chose the cards, that all of them pass the In-Kind test, and that they are examples, not a ranking (run 19, M1; run 22; run 24;
    decision sheet 16, S3 C and S6 A). "The In-Kind test" is the Screen's own name for the test its labels report."""
    items = saved_screen()['items']
    other = [i['name'] for i in items if i['verdict'] not in PASSING]
    if other:
        sys.exit(f'src/screen_saved.json: Home says that all its items pass the In-Kind test, and "{other[0]}" does not; the line in build.py (home_items_note) changes only with the founder\'s answer (decision sheet 16, S3)')
    return f'<p>This project chose these {NUMWORD[len(items)].lower()}, all of which pass the In-Kind test, as examples, not a ranking.</p>'


def home_labels(root, index):
    """The Screen's own lines on what passing its test means, with a link to its explanation of the labels (run 19, S1; frame v0.6, section 6.1)."""
    s = saved_screen(); lg = s['legend']; e = html.escape
    return f'<p class="labels theirs">{e(lg["passing"])} <a href="{e(s["source"]["page"])}#{lg["anchor"]}">{e(lg["heading"])}</a></p>'


def home_law_line(root, index):
    """The count, which is this page's own, and then the State-law label and its line as the Screen words them (run 19, S2)."""
    s = saved_screen(); lg = s['legend']['state_law']; e = html.escape
    return (f'<p class="law">{s["counts"]["state_law_does_not_allow"]} of the {s["counts"]["items"]} items are labeled '
            f'<span class="vd no theirs">{e(lg["label"])}</span> <span class="theirs">{e(lg["line"])}</span></p>')


def releases_heading(root, index):
    days = sorted([r['published'] for r in earlier_json()] + [published_iso(CURRENT)])
    return f'<h2>{NUMWORD[len(days)]} releases since {MONTHS[int(days[0].split("-")[1]) - 1]}</h2>'


def releases_table(root, index):
    """Every release, newest first, with its two records' DOIs in full, each linked, from the saved Zenodo list and src/releases/earlier.json."""
    zen = zenodo_list(CURRENT)['records']
    pre = '10.5281/zenodo.'
    rows = [(CURRENT, published(CURRENT), zen['instruments']['doi'], zen['guide']['doi'])]
    for r in earlier_json():
        y, m, d = r['published'].split('-')
        rows.append((r['release'], f'{int(d)} {MONTHS[int(m) - 1]} {y}', r['instruments'], r['guide']))
    for r in rows:
        assert r[2].startswith(pre) and r[3].startswith(pre), r
    body = ''.join(f'<tr><td class="mono">{a}</td><td>{b}</td><td class="mono">{doi_link(c)} · {doi_link(d)}</td></tr>' for a, b, c, d in rows)
    return ('<div class="scroll"><table class="ledger"><thead><tr><th scope="col">Release</th><th scope="col">Published</th><th scope="col">Record 1 · Record 2</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


def cite_list(root, index):
    data = release_json(CURRENT)
    recs = {r['key']: r['doi'] for r in data['records']}
    return ('<dl class="facts">'
            f'<dt>The instruments</dt><dd><a class="doi" href="https://doi.org/{recs["instruments"]}">https://doi.org/{recs["instruments"]}</a></dd>'
            f'<dt>The guide and methodology</dt><dd><a class="doi" href="https://doi.org/{recs["guide"]}">https://doi.org/{recs["guide"]}</a></dd></dl>')


def ledger_release(root, index):
    return f'<a class="theirs" href="{root}materials/{index}">{html.escape(release_json(CURRENT)["title"])}</a>'


def ledger_screen(root, index):
    ver = re.search(r'(Version \d+ \w+ \d{4})', saved_screen()['version_line']).group(1)
    return f'<span class="theirs">{html.escape(ver)}</span>'


MAKERS = {'ledger-release': ledger_release, 'ledger-screen': ledger_screen, 'home-release': home_release, 'materials-release': materials_release, 'home-homes': home_homes, 'home-diagram': home_diagram,
          'home-items': home_items, 'home-numbers': home_numbers, 'guide-steps': guide_steps, 'begin': begin_list,
          'docs-instruments': docs_list('instruments'), 'docs-guide': docs_list('guide'), 'releases': releases_table, 'cite': cite_list,
          'home-items-heading': home_items_heading, 'home-law-line': home_law_line, 'home-items-note': home_items_note, 'home-labels': home_labels, 'releases-heading': releases_heading}


def link_href(target, root, index):
    return screen_words()['address'] if target == '@screen' else f'{root}{target}{index}'


def current_attrs(target, path):
    if target.startswith('@'): return ''
    if target == path: return ' class="on" aria-current="page"'
    if path.startswith(target): return ' class="on" aria-current="true"'
    return ''


def foot_lists(root, index):
    out = []
    for head, links in FOOT.items():
        out.append(f'<div><p class="fh">{html.escape(head)}</p><ul>' + ''.join(f'<li><a href="{link_href(t, root, index)}">{html.escape(l)}</a></li>' for t, l in links) + '</ul></div>')
    return '\n'.join(out)


def read_page(p):
    text = p.read_text(encoding='utf-8')
    assert text.startswith('---\n'), f'{p.name}: no heading block'
    head, body = text[4:].split('\n---\n', 1)
    meta = {}
    for line in head.splitlines():
        k, _, v = line.partition(':')
        assert k in KEYS, f'{p.name}: unknown key {k!r}'
        meta[k] = v.strip()
    for k in ('title', 'path', 'description', 'updated', 'budget'):
        assert k in meta, f'{p.name}: missing {k}'
    return meta, body.strip()


def release_blocks(rel, root):
    """The parts of a release page that come from the release's own files (src/releases/<release>.json)."""
    data = json.loads((SRC / 'releases' / f'{rel}.json').read_text(encoding='utf-8'))
    zen = zenodo_list(rel)
    size = {(k, f['name']): f['size'] for k, r in zen['records'].items() for f in r['files']}
    e = html.escape

    def link(record, name, text, doc):
        # The document's name is added for anyone who hears or lists the links without the heading above them.
        fmt = FORMATS[pathlib.PurePosixPath(name).suffix]
        kb = max(1, round(size[(record, name)] / 1000))
        return (f'<a href="{root}files/{rel}/{record}/{e(name)}">{e(text)}<span class="vh">: {e(doc)}</span></a> '
                f'<span class="meta">({fmt}, {kb} KB)</span>')

    def docs(items, record):
        out = ['<ul class="rdocs theirs">']
        for d in items:
            r = d.get('record', record)
            v = d['version']
            ver = f' <span class="ver">{"" if v.startswith("Release") else "version "}{e(v)}</span>' if v else ''
            copies = ''.join(f'<li>{link(r, f["file"], f["label"], d["name"])}</li>' for f in d['files'])
            about = f'<p>{e(d["about"])}</p>' if d['about'] else ''
            out.append(f'<li class="rdoc"><h3>{e(d["name"])}{ver}</h3>{about}<ul class="copies">{copies}</ul></li>')
        return '\n'.join(out + ['</ul>'])

    # A list of cards, not a table: at phone width a four-column table was cut off (found 11 Nov 2026).
    recs = ['<ul class="rdocs theirs">']
    for r in data['records']:
        notes = ''.join(f'<p>{e(n["text"])}</p>' for n in r['notes'])
        if r['credit']:   # the data center project's line on credit, linked to the record's license file
            c = r['credit']
            lead = c['text'][:-len(c['link'])]
            notes += f'<p>{e(lead)}<a href="{root}files/{rel}/{r["key"]}/{e(c["file"])}">{e(c["link"])}</a>.</p>'
        recs.append(f'<li class="rdoc"><h3>{e(r["label"])}</h3><p class="meta">License: {e(r["license"])}</p><p>{e(r["contents"])}</p>'
                    f'{notes}'
                    f'<p class="tocite">To cite: <a class="doi" href="https://doi.org/{e(r["doi"])}">doi:{e(r["doi"]).replace("/", "/<wbr>")}</a></p></li>')
    records = '\n'.join(recs + ['</ul>'])
    begin = '\n'.join(['<ol class="theirs">'] + [f'<li><a href="{root}files/{rel}/{b["record"]}/{e(b["file"])}">{e(b["name"])}</a>: {e(b["quote"])}</li>'
                                                 for b in data['begin']] + ['</ol>'])
    return {'records': records, 'begin': begin, 'instruments': docs(data['instruments'], 'instruments'),
            'guide': docs(data['guide'], 'guide'), 'shared': docs(data['shared'], 'instruments'),
            # The release's sentence begins "Known gaps:"; the label says whose they are, and the rest is word for word.
            'gaps': f'<p class="notice"><strong>The release\'s own known gaps:</strong> <span class="theirs">{e(data["gaps"].removeprefix("Known gaps: "))}</span></p>'}


def funding_version():
    """The funding statement's version and date, as its own first line gives them (\"Working draft · Version 0.5 · 12 November 2026 · Released\"), so that no date of another project's release is typed on a page."""
    t = (SRC / 'released' / 'nonprofit' / 'Website_2026-11-14b' / 'funding-statement.html').read_text(encoding='utf-8')
    m = re.search(r'<em>[^<]*· Version (\d+\.\d+) · (\d{1,2} [A-Z][a-z]+ 20\d\d) ·[^<]*</em>', t)
    assert m, "the funding statement's first line is not in the form this build reads"
    return f'Version {m.group(1)}, {m.group(2)}'


def released(names):
    """Another project's released pages, each an HTML fragment in src/released/, placed in the order given and unchanged
    (frame v0.4, section 6; decision sheet 2, E6 A). Each file must match the checksum list released beside it."""
    parts = []
    for name in names:
        f = SRC / 'released' / name
        sums = {}
        for line in (f.parent / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():   # either of sha256sum's forms (run 7, N4)
            if not line.strip(): continue
            m = re.fullmatch(r'([0-9a-f]{64}) [ *](.+)', line.strip())
            assert m, f'{f.parent.name}/SHA256SUMS.txt: a line not in the form sha256sum writes (64 lowercase hex digits, two spaces or a space and *, a file name): {line[:60]!r}'
            sums[m.group(2)] = m.group(1)
        data = f.read_bytes()
        assert hashlib.sha256(data).hexdigest() == sums.get(f.name), f'{name}: not the file its checksum list names'
        parts.append(data.decode('utf-8'))
    return '<div class="theirs released">\n' + ''.join(parts) + '</div>'


STAND_IN = '\x00released text\x00'   # stands in for another project's released text while the page's own links are given their addresses


def print_addresses(page, path):
    """On paper a link shows the address a reader of the paper can use (frame v0.6, section 8). The style sheet prints an absolute link's href, and the data-url written here for a link
    to another page of the site: the link made whole from the page's own address, with a folder's index.html left off (a disk copy links to it). Only the page's main text; another
    project's released text is held as released."""
    span = re.search(r'<main\b.*?</main>', page, re.S)
    assert span, f'{path!r}: no main text'
    def one(m):
        tag = m.group(0)
        found = re.search(r'\shref="([^"]*)"', tag)
        if not found: return tag
        assert 'data-url' not in tag, f'{path!r}: a link already carries data-url: {tag}'
        href = html.unescape(found.group(1))
        if not href or href.startswith('#') or re.match(r'[a-z][a-z0-9+.-]*:|//', href): return tag
        full = urllib.parse.urljoin(SITE + path, href)
        if full.endswith('/index.html'): full = full[:-len('index.html')]
        return tag[:-1] + f' data-url="{html.escape(full, quote=True)}">'
    return page[:span.start()] + re.sub(r'<a\b[^>]*>', one, span.group(0)) + page[span.end():]


def render(meta, body, layout, local):
    path = meta['path']
    is_404 = path == '404.html'
    depth = 0 if is_404 else path.count('/')
    root = '/' if is_404 else '../' * depth
    index = 'index.html' if local else ''
    home = '/' if is_404 else (root + index if (root or local) else './')
    e = html.escape
    desk = ''.join(f'<a href="{link_href(t_, root, index)}"{current_attrs(t_, path)}>{e(l)}</a>' for t_, l in NAV)
    phone = ''.join(f'<li><a href="{link_href(t_, root, index)}"{current_attrs(t_, path)}>{e(l)}</a></li>' for t_, l in NAV) + \
        ''.join(f'<li class="sub"><a href="{link_href(t_, root, index)}"{current_attrs(t_, path)}>{e(l)}</a></li>' for t_, l in READERS)
    readers = ''.join(f'<a href="{link_href(t_, root, index)}"{current_attrs(t_, path)}>{e(l)}</a>' for t_, l in READERS)
    body = body.replace('{{gaps}}', GAPS_NOTICE)
    words = screen_words()
    body = re.sub(r'\{\{screen:(title|opening|address)\}\}', lambda m: e(words[m.group(1)]), body)
    # The note stays on one line where there is room, and a mark of punctuation that follows it stays with it.
    body = re.sub(r'\{\{file:([\w.]+)/(\w+)/([^}]+)\}\}([.,;:]?)', lambda m: '<span class="nb">' + e(file_note(m.group(1), m.group(2), m.group(3))) + m.group(4) + '</span>', body)
    body = re.sub(r'\{\{doi:([\w.]+)/(\w+)\}\}', lambda m: record_doi(m.group(1), m.group(2)), body)
    body = re.sub(r'\{\{alldoi:([\w.]+)/(\w+)\}\}', lambda m: record_doi(m.group(1), m.group(2), 'conceptdoi'), body)
    body = re.sub(r'\{\{published:([\w.]+)\}\}', lambda m: published(m.group(1)), body)
    body = re.sub(r'\{\{zenodoread:([\w.]+)\}\}', lambda m: zenodo_read(m.group(1)), body)
    body = body.replace('{{funding:version}}', funding_version())
    body = re.sub(r'\{\{make:([\w-]+)\}\}', lambda m: MAKERS[m.group(1)](root, index), body)
    body = re.sub(r'\{\{icon:(\w+)\}\}', lambda m: icon(m.group(1)), body)
    body = body.replace('{{wm}}', mark_svg('wm')).replace('{{current}}', CURRENT)
    if 'release' in meta:
        blocks = release_blocks(meta['release'], root)
        body = re.sub(r'\{\{release:(\w+)\}\}', lambda m: blocks[m.group(1)], body)
    kept = ''
    if 'theirs' in meta:
        kept = released(meta['theirs'].split())
        body = body.replace('{{theirs}}', STAND_IN)
    if '{{byline}}' in body:
        assert path == '' and body.count('{{byline}}') == 1, f'{path!r}: the byline is placed once, on the home page only'
        body = body.replace('{{byline}}', unbroken(BYLINE))
    title = meta['title']
    fill = {
        'body': body,
        'mark': mark_svg(),
        'title_tag': e(title if not path else f'{meta.get("tab", title)} · In-Kind Standard'),
        'description': e(meta['description'], quote=True),
        'footline': unbroken(STATUS),
        'readers': readers, 'nav': desk, 'navphone': '<ul>' + phone + '</ul>', 'foot_lists': foot_lists(root, index),
        'updated': meta['updated'],
        'gaps_line': GAPS,
        # A not-found page has no address of its own, so it prints none.
        'printed': '' if is_404 else f'<p class="print-only">Printed from {SITE}{path}</p>\n',
        'home': home, 'root': root, 'index': index,
    }
    out = layout
    for k in ('body', 'mark', 'title_tag', 'description', 'footline', 'readers', 'nav', 'navphone', 'foot_lists', 'updated', 'gaps_line', 'printed', 'home', 'root', 'index'):
        out = out.replace('{{' + k + '}}', fill[k])
    out = print_addresses(out, path)
    if kept:
        assert out.count(STAND_IN) == 1, f'{path}: the released text is not placed once'
        out = out.replace(STAND_IN, kept)
    assert STAND_IN not in out and '{{' not in out, f'{path}: unfilled placeholder'
    return out


def build(dest, local=False):
    layout = (SRC / 'layout.html').read_text(encoding='utf-8')
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=dest.parent) as t:
        new = pathlib.Path(t) / 'new'
        shutil.copytree(SRC / 'assets', new / 'assets', ignore=shutil.ignore_patterns('desktop.ini'))
        shutil.copyfile(SRC / 'assets' / 'favicon.ico', new / 'favicon.ico')   # a browser opening a hosted file asks for the icon here
        (new / '.nojekyll').write_text('', encoding='utf-8')
        seen, seen_made = set(), set()
        for p in sorted((SRC / 'pages').glob('*.html')):
            meta, body = read_page(p)
            path = meta['path']
            assert path == '' or path.endswith('/') or path.endswith('.html'), f'{p.name}: its path {path!r} must be empty (the home page), end with "/" or end with ".html" (run 8, the build check, Note 4)'
            assert path not in seen, f'two pages at {path!r}'
            seen.add(path)
            made = path if path.endswith('.html') else path + 'index.html'   # the file a path becomes (run 7, N3)
            assert made not in seen_made, f'{p.name}: its path {path!r} makes {made}, which another page makes too'
            seen_made.add(made)
            target = new / path if path.endswith('.html') else new / path / 'index.html'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(render(meta, body, layout, local), encoding='utf-8', newline='\n')
        for target, _ in NAV + READERS + [x for v in FOOT.values() for x in v]:
            assert target.startswith('@') or target in seen, f'menu item {target!r} has no page'
        # Every page was made: put the new files in place of the old ones.
        dest.mkdir(exist_ok=True)
        for child in dest.iterdir():
            if child.name in KEPT:
                continue
            shutil.rmtree(child) if child.is_dir() else child.unlink()
        for child in new.iterdir():
            shutil.move(str(child), str(dest / child.name))
    return sorted(seen)


def differences(a, b, top=True):
    c = filecmp.dircmp(a, b, ignore=(sorted(KEPT) if top else []) + ['desktop.ini'])   # Windows adds desktop.ini to folders; it is not part of the site
    bad = list(c.left_only) + list(c.right_only) + list(c.funny_files)
    _, mismatch, errors = filecmp.cmpfiles(a, b, c.common_files, shallow=False)
    bad += mismatch + errors
    for d in c.common_dirs:
        bad += [f'{d}/{x}' for x in differences(pathlib.Path(a) / d, pathlib.Path(b) / d, top=False)]
    return bad


if __name__ == '__main__':
    if '--check' in sys.argv:
        with tempfile.TemporaryDirectory() as t:
            build(pathlib.Path(t) / 'docs')
            bad = differences(pathlib.Path(t) / 'docs', PUB)
        if bad:
            sys.exit('docs/ differs from the build: ' + ', '.join(sorted(bad)))
        print('docs/ matches the build')
    else:
        local = '--local' in sys.argv
        where = ROOT / 'local' if local else PUB
        pages = build(where, local=local)
        if local:   # a copy to open from a disk, with the hosted files beside it; never published
            shutil.copytree(PUB / 'files', where / 'files', dirs_exist_ok=True)
        print(f'wrote {len(pages)} pages to {where}')
