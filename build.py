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
PUB_FILES = PUB / 'files'   # the hosted release files, which the reader pages show
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
NAV = [('materials/', 'Model documents'), ('could-receive/', 'What communities could receive'), ('records/', 'Public records'), ('how-it-works/', 'How we work'), ('governance/', 'Governance'), ('plans/', 'What comes next')]   # frame v0.6, section 4; the whole menu since the founder's request of 18 November 2026, 16:03
READERS = [('sponsors/', 'For sponsors and funders'), ('press/', 'Press'), ('contact/', 'Contact')]
FOOT = {'The work': [('materials/', 'Model documents'), ('could-receive/', 'What communities could receive'), ('records/', 'Public records')],
        'The project': [('how-it-works/', 'How we work'), ('governance/', 'Governance'), ('plans/', 'What comes next'), ('funding/', 'Who pays for the work'), ('updates/', 'Updates and corrections')],
        'This site': [('sponsors/', 'For sponsors and funders'), ('press/', 'Press and citation'), ('contact/', 'Contact'), ('privacy/', 'Privacy statement'), ('accessibility/', 'Accessibility statement')]}
KEYS = {'title', 'tab', 'path', 'description', 'updated', 'budget', 'ceiling', 'release', 'nav', 'theirs'}
KEPT = {'files', 'CNAME'}
# The byline appears once on the site: the first line of the home page's section "Who prepares this work", placed there
# with {{byline}} (decision sheet 2, E2 B, 12 November 2026). Every page's footer carries the status line.
BYLINE = 'Prepared by In-Kind Standard · Citizen-prepared working draft · Not legal advice'   # the project's name in place of the founder's (the Core's sheet CO-6, decision 2, 17 November 2026), brought forward at his word of 18 November 2026, 16:26
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
VERDICT = {'Works': 'ok', 'Works with a condition': 'cond', 'Fits provisionally': 'prov', 'Not settled yet': 'prov', 'Not this kind of benefit': 'na',
           'State law does not allow this': 'no'}   # the class of each of the Screen's verdicts; any other verdict stops the build until its class is chosen


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


def item_card(it, page=False):
    """One of the Screen's cards, closed to its section, name, verdict, homes and condition, with what it would do in a fold and how far its model text has got
    under it (decision sheet 15, X2 A and X3 A). On the page What communities could receive (page=True), the fold's title is marked as the Screen's own label,
    the status lines appear only where the card has them, and the card adds the Screen's line "Tried elsewhere?" (frame v0.6, section 6.1)."""
    e = html.escape
    conds = ''.join(f'<p class="cond theirs">{e(x)}</p>' for x in (it['vsub'], it['hnote']) if x)   # the condition and the home note, each on a line of its own, as the record has them (run 19, N1)
    chips = ''.join(f'<span class="chip theirs">{e(c)}</span>' for c in it['chips'])
    meta = [f'<p class="ev theirs">{e(it["evLabel"])} {e(it["evStatus"])}</p><p class="evnote theirs">{e(it["evText"])}</p>'] if it['evStatus'] or not page else []
    if page and it.get('tried'):
        meta.append(f'<p class="evnote theirs">{e(it["tried"])}</p>')
    summary = '<summary class="theirs">What it would do</summary>' if page else '<summary>What it would do</summary>'
    h = 'h4' if page else 'h3'   # on the page, a card's name sits under its group's heading (run 27, Note 10)
    return ('<article class="item" data-reveal>'
            f'<p class="kick theirs">{e(it["sec"])}</p><{h} class="theirs">{e(it["name"])}</{h}>'
            f'<div class="tags"><span class="vd {VERDICT[it["verdict"]]} theirs">{e(it["verdict"])}</span>{chips}</div>'
            f'{conds}'
            f'<details class="more" open data-fold>{summary}<p class="theirs">{e(it["lead"])}</p></details>'
            + (f'<div class="meta">{"".join(meta)}</div>' if meta else '') + '</article>')


def home_items(root, index):
    return '\n'.join(['<div class="items">'] + [item_card(it) for it in saved_screen()['items']] + ['</div>'])


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
    return f'<h3>{NUMWORD[len(s["items"])]} of the {sum(len(i) for _, i in cr_allowed())} items allowed on the public record</h3>'


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


def home_all_link(root, index):
    """Home's link to the page with every item (frame v0.6, section 5, row 2). The number is the Screen's count, not typed."""
    return f'<a class="btn btn-2" href="{root}could-receive/{index}">All {sum(len(i) for _, i in cr_allowed())} allowed items</a>'


# The page What communities could receive (frame v0.6, sections 4 and 6.1; decision sheet 17, T4): the Screen's words as saved by tools/save_screen_words.py
# under the key "page" of src/screen_saved.json, in the Screen's own order. The check holds every quoted word to that copy.
def cr_page():
    p = saved_screen()['page']
    if [i['name'] for i in p['groups'][3]['items']] != [i['name'] for i in p['law']['groups'][0]['items']]:
        sys.exit('src/screen_saved.json: the cards State law does not allow are not the items of the law section\'s first group; the page shows them there only')
    return p


def cr_caution(root, index):
    return f'<p class="muted read theirs">{html.escape(cr_page()["caution"])}</p>'


def cr_standards(root, index):
    """The standards every project must meet, by their names, as the Screen opens its list of them; the full text of each is on the Screen and in the model documents."""
    s = saved_screen(); st = cr_page()['standards']; e = html.escape
    first, rest = st['lead'].split('. ', 1)
    if first + '.' != s['county_line']:
        sys.exit('src/screen_saved.json: the standards\' paragraph no longer opens with the county line')
    return (f'<p class="eyebrow theirs">{e(st["summary"])}</p><h2 class="theirs">{e(first)}.</h2><p class="lead theirs">{e(rest)}</p>'
            '<ul>' + ''.join(f'<li class="theirs">{e(n)}</li>' for n in st['names']) + '</ul>'
            f'<p class="theirs">{e(st["numbers"])}</p><p class="muted theirs">{e(st["evidence"])}</p>'
            f'<p><a href="{e(s["source"]["page"])}">Each standard in full, on the public record</a></p>')


def cr_allowed():
    """The items the page shows: those that pass the In-Kind test, in the Screen's group of drafted items and in its other items allowed (the founder's request of
    18 November 2026, 16:03: the page shows what is allowed; what was set aside, what fails and what State law does not allow are left to the Screen)."""
    g = cr_page()['groups']
    return [(g[0]['title'], [i for i in g[0]['items'] if i['verdict'] in PASSING]), ('Other items allowed', [i for i in g[2]['items'] if i['verdict'] in PASSING])]


def cr_jump(root, index):
    e = html.escape
    links = [(f'#g{n}', t, len(i)) for n, (t, i) in enumerate(cr_allowed(), 1)]
    return '<ul>' + ''.join(f'<li><a href="{h}"><span class="theirs">{e(t)}</span> ({c})</a></li>' for h, t, c in links) + '</ul>'


def cr_groups(root, index):
    """The cards of the items allowed in Florida, in the Screen's groups and order. The items State law does not allow are under the law (cr_law), in its words."""
    e = html.escape; out = []
    for n, (title, items) in enumerate(cr_allowed(), 1):   # each group folds, to help with scrolling (the founder's request of 18 November 2026, 16:03)
        mark = ' class="theirs"' if n == 1 else ''
        out.append(f'<details class="grp" id="g{n}" open data-fold><summary><h3><span{mark}>{e(title)}</span> ({len(items)})</h3></summary>'
                   '<div class="items">' + '\n'.join(item_card(it, page=True) for it in items) + '</div></details>')
    return '\n'.join(out)


def cr_law(root, index):
    L = cr_page()['law']; e = html.escape
    out = [f'<h2 class="theirs">{e(L["title"])}</h2><p class="read theirs">{e(L["intro"])}</p><p class="read theirs">{e(L["describes"])}</p>']   # the record's count line counts across its project types, so it is left out (run 26, Should fix 8)
    out.append('<div class="card">')   # one card for both groups, so that the short one does not stand as a tall empty box beside the long one
    for g, cls in zip(L['groups'], ('no', 'na')):
        out.append(f'<h3><span class="vd {cls} theirs">{e(g["title"])}</span> ({g["count"]})</h3><p class="muted theirs">{e(g["note"])}</p><ul>'
                   + ''.join(f'<li><p class="theirs"><strong>{e(i["name"])}</strong></p>' + (f'<p class="theirs">{e(i["would"])}</p>' if i['would'] else '') + '</li>' for i in g['items'])
                   + '</ul>')
    return '\n'.join(out + ['</div>', f'<p><a href="{e(saved_screen()["source"]["page"])}">The details of each, on the public record</a></p>'])


def cr_not(root, index):
    s = saved_screen(); n = cr_page()['not_this']; e = html.escape
    d = cr_page()['descriptions']
    return (f'<div class="gaps"><h2 class="theirs">{e(n["title"])}</h2><p class="theirs">{e(n["text"])}</p>'
            f'<p class="theirs"><strong>{e(d["title"])}.</strong> {e(d["text"])}</p><p>No benefits under these model instruments have been delivered anywhere yet.</p></div>')


MAKERS = {'ledger-release': ledger_release, 'ledger-screen': ledger_screen, 'home-release': home_release, 'materials-release': materials_release, 'home-homes': home_homes, 'home-diagram': home_diagram,
          'home-items': home_items, 'home-numbers': home_numbers, 'guide-steps': guide_steps, 'begin': begin_list,
          'docs-instruments': docs_list('instruments'), 'docs-guide': docs_list('guide'), 'releases': releases_table, 'cite': cite_list,
          'home-items-heading': home_items_heading, 'home-law-line': home_law_line, 'home-items-note': home_items_note, 'home-labels': home_labels, 'releases-heading': releases_heading,
          'home-all-link': home_all_link, 'cr-caution': cr_caution, 'cr-standards': cr_standards, 'cr-jump': cr_jump, 'cr-groups': cr_groups, 'cr-law': cr_law, 'cr-not': cr_not}


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


# Reader pages (the founder's request of 24 November 2026: "nothing should send the visitor to an unformatted Markdown page").
# Each hosted .md or .txt file of a release gets a page of its own at read/<release>/<record>/<name>/, which shows the file's text,
# word for word, as headings, paragraphs, lists and tables, with a list of contents and a button to download the file as released.
# The file itself is unchanged; every link the site makes to it goes to its page instead (see reader_links), except the download button.
READER_UPDATED = '24 November 2026'   # the date the reader pages were first made; a change to how they are made changes it
RECORD_NAME = {'instruments': 'Record 1, the model documents', 'guide': 'Record 2, the guide and the tests'}
PLAIN_FILES = ('002_MANIFEST.txt',)   # set out in columns with spaces, so shown as written, in a fixed-width block
HEAD_WORDS = re.compile(r'(?:ARTICLE|PART|CHAPTER|EXHIBIT|SCHEDULE|APPENDIX|ATTACHMENT|ANNEX)\b')


def reader_slug(name):
    return pathlib.PurePosixPath(name).stem.lower().replace('_', '-')


def reader_path(rel, record, name):
    """A file in both records has one page, under the record the release's data names for it."""
    shared = {f['file']: d['record'] for d in release_json(rel)['shared'] for f in d['files']} if (SRC / 'releases' / f'{rel}.json').is_file() else {}
    return f'read/{rel}/{shared.get(name, record)}/{reader_slug(name)}/'


def reader_links(body, local):
    """Points every link to a hosted .md or .txt file at that file's reader page. A link with the download attribute
    written before its address (the reader page's own button) is left as it is."""
    index = 'index.html' if local else ''
    return re.sub(r'(?<!download )href="((?:\.\./)*|/)files/([\w.]+)/(\w+)/([^"/]+\.(?:md|txt))"',
                  lambda m: f'href="{m.group(1)}{reader_path(m.group(2), m.group(3), html.unescape(m.group(4)))}{index}"', body)


def doc_inline(s):
    """A line of the file: its text escaped, with bold, italic and code shown as such. Nothing is added or left out."""
    s = html.escape(s, quote=False)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*(?=\S)(.+?)(?<=\S)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])', r'<em>\1</em>', s)
    return s


def doc_text(s):
    return html.unescape(re.sub(r'<[^>]+>', '', s))


def doc_cells(line):
    t = line.strip()
    if t.startswith('|'): t = t[1:]
    if t.endswith('|') and not t.endswith('\\|'): t = t[:-1]
    return [c.strip() for c in re.split(r'(?<!\\)\|', t)]


def doc_render(text, plain=False):
    """The file's text as HTML, and its list of headings (level, id, words) for the contents."""
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)   # the license tags meant for machines (SPDX); they are not shown
    if plain:
        return f'<pre class="plain">{html.escape(text.strip(chr(10)), quote=False)}</pre>', []
    out, heads, used = [], [], set()
    lines = text.split('\n')

    def heading(level, inner):
        words = doc_text(inner).strip()
        base = re.sub(r'[^a-z0-9]+', '-', words.lower()).strip('-')[:60] or 'part'
        hid, n = base, 2
        while hid in used: hid, n = f'{base}-{n}', n + 1
        used.add(hid)
        heads.append((level, hid, words))
        out.append(f'<h{level} id="{hid}">{inner}</h{level}>')
    i = 0
    while i < len(lines):
        line = lines[i]; s = line.strip()
        if not s: i += 1; continue
        m = re.match(r'(#{1,6})\s+(.*?)\s*#*\s*$', s)
        if m:
            heading(min(6, len(m.group(1)) + 1), doc_inline(m.group(2))); i += 1; continue
        if re.fullmatch(r'(?:-{3,}|\*{3,}|_{3,})', s):
            out.append('<hr>'); i += 1; continue
        if s.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                rows.append(lines[i]); i += 1
            sep = lambda r: re.fullmatch(r'\|?(?:\s*:?-{2,}:?\s*\|)*\s*:?-{2,}:?\s*\|?', r.strip())
            head = rows[0] if len(rows) > 1 and sep(rows[1]) else None
            body_rows = [r for r in (rows[2:] if head else rows) if not sep(r)]
            t = ['<div class="tbl"><table>']
            if head: t.append('<thead><tr>' + ''.join(f'<th scope="col">{doc_inline(c)}</th>' for c in doc_cells(head)) + '</tr></thead>')
            t.append('<tbody>' + ''.join('<tr>' + ''.join(f'<td>{doc_inline(c)}</td>' for c in doc_cells(r)) + '</tr>' for r in body_rows) + '</tbody></table></div>')
            out.append(''.join(t)); continue
        if re.match(r'>\s?', s):
            q = []
            while i < len(lines) and lines[i].strip().startswith('>'):
                q.append(re.sub(r'^\s*>\s?', '', lines[i])); i += 1
            out.append('<blockquote>' + ''.join(f'<p>{doc_inline(x)}</p>' for x in q if x.strip()) + '</blockquote>'); continue
        if re.match(r'[-*+]\s+\S', s) and not re.fullmatch(r'\*\*.*\*\*', s):
            items = []
            while i < len(lines) and re.match(r'\s*[-*+]\s+\S', lines[i]) and not re.fullmatch(r'\*\*.*\*\*', lines[i].strip()):
                items.append(re.sub(r'^\s*[-*+]\s+', '', lines[i]).strip()); i += 1
            out.append('<ul>' + ''.join(f'<li>{doc_inline(x)}</li>' for x in items) + '</ul>'); continue
        if re.match(r'\d+[.)]\s+\S', s):
            items = []
            while i < len(lines) and re.match(r'\s*\d+[.)]\s+\S', lines[i]):
                n, rest = re.match(r'\s*(\d+[.)])\s+(.*)', lines[i]).groups(); items.append((n, rest.strip())); i += 1
            # The number is the file's own text, so it is kept as text, not drawn by the list.
            out.append('<ol class="numbered">' + ''.join(f'<li><span class="n">{html.escape(n)}</span> {doc_inline(x)}</li>' for n, x in items) + '</ol>'); continue
        whole = re.fullmatch(r'\*\*([^*].*?)\*\*', s)
        if whole and len(s) < 160 and HEAD_WORDS.match(whole.group(1)):   # a part's title, set in bold on a line of its own
            heading(2, doc_inline(whole.group(1))); i += 1; continue
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(r'(#{1,6}\s|\||>|(?:-{3,}|\*{3,}|_{3,})\s*$|[-*+]\s+\S|\d+[.)]\s+\S)', lines[i].strip()):
            para.append(doc_inline(lines[i].strip())); i += 1
        if not para: para.append(doc_inline(s)); i += 1
        out.append('<p>' + '<br>'.join(para) + '</p>')
    return '\n'.join(out), heads


def doc_contents(heads, root_level):
    """The contents: the top two levels of headings, as links into the page."""
    keep = [(l, h, w) for l, h, w in heads if l <= root_level + 1]
    if len(keep) < 2: return ''
    items = ''.join(f'<li class="l{l - root_level + 1}"><a href="#{h}">{html.escape(w)}</a></li>' for l, h, w in keep)
    return (f'<nav class="toc toc-side" aria-label="Contents"><p class="toc-h">Contents</p><ol>{items}</ol></nav>\n'
            f'<details class="toc toc-top"><summary>Contents</summary><ol>{items}</ol></details>\n')


def reader_docs(rel):
    """Each hosted document's name, label and version, from the release's own data, by (record, file)."""
    data = release_json(rel); found = {}
    for key, record in (('instruments', 'instruments'), ('guide', 'guide'), ('shared', None)):
        for d in data[key]:
            for f in d['files']:
                r = d.get('record') or f.get('record') or record
                found[(r, f['file'])] = (d['name'], f['label'], d['version'])
    return found


BYLINE_FILE, BYLINE_SHOWN = 'Prepared by Timothy Smith · ', 'Prepared by In-Kind Standard · '   # a release file's byline, and as its reader page shows it


def reader_pages(rel, local):
    """The meta and body of each reader page of a release, from its hosted files."""
    zen = zenodo_list(rel); docs = reader_docs(rel); e = html.escape
    index = 'index.html' if local else ''
    for record, r in zen['records'].items():
        for f in r['files']:
            name = f['name']
            if pathlib.PurePosixPath(name).suffix not in FORMATS: continue
            q = PUB_FILES / rel / record / name
            doc, label, version = docs.get((record, name), docs.get(('instruments', name), (name, '', '')))
            if label == 'Open the file': label = ''
            path = reader_path(rel, record, name); root = '../' * path.count('/')
            if not path.startswith(f'read/{rel}/{record}/'): continue   # the other record's copy of a shared file
            # The founder's choice of 24 November 2026 (option 2): each byline shows the project's name in place of his, and the page says so; the hosted file
            # is unchanged, its license lines included. The next release of each document carries the project's name itself.
            body_html, heads = doc_render(q.read_text(encoding='utf-8').replace(BYLINE_FILE, BYLINE_SHOWN), plain=name in PLAIN_FILES)
            top = min((l for l, _, _ in heads), default=2)
            ver = '' if not version else (f'{version}' if version.startswith('Release') else f'Version {version}')
            sub = ' · '.join(x for x in (label, ver) if x)
            kb = max(1, round(f['size'] / 1000))
            fmt = FORMATS[pathlib.PurePosixPath(name).suffix]
            body = (f'<section class="phead">\n{mark_svg("wm")}\n<div class="wrap">\n'
                    f'<p class="crumbs"><a href="{root}{index}">Home</a> / <a href="{root}materials/{index}">Model documents</a> / '
                    f'<a href="{root}materials/{rel}/{index}">Release {rel}</a></p>\n'
                    f'<p class="eyebrow">Release {rel} · {RECORD_NAME.get(record, record)}</p>\n'
                    f'<h1><span class="theirs">{e(doc)}</span></h1>\n'
                    + (f'<p class="lead">{e(sub)}</p>\n' if sub else '') +
                    f'<p class="muted read">The text below is the release\'s file, set out for reading, with the project\'s name in place of the founder\'s in its byline. Not legal advice.</p>\n'
                    f'<div class="actions"><a class="btn" download href="{root}files/{rel}/{record}/{e(name)}"><span>Download the file <span class="nb">({fmt}, {kb} KB)</span></span></a>'
                    f'<a class="btn btn-2" href="{root}materials/{rel}/{index}">Every document in Release {rel}</a></div>\n'
                    f'</div>\n</section>\n'
                    f'<section class="sec">\n<div class="wrap">\n'
                    f'<article class="doc theirs{" has-toc" if len([h for h in heads if h[0] <= top + 1]) >= 2 else ""}" data-source="files/{rel}/{record}/{e(name)}">\n'
                    f'{doc_contents(heads, top)}<section class="doc-body">\n{body_html}\n</section>\n</article>\n</div>\n</section>')
            meta = {'title': f'{doc}' + (f', {label.lower()}' if label else ''), 'tab': doc + (f' ({label.lower()})' if label else ''), 'path': path,
                    'description': f'{doc}, from Release {rel} of In-Kind Standard\'s model documents, to read here or download.',
                    'updated': READER_UPDATED, 'budget': '0'}
            yield meta, body


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
    body = reader_links(body, local)
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
    if path.startswith('read/'):   # the reader pages' own style sheet, after the site's
        out = out.replace('assets/site.css">', 'assets/site.css">\n<link rel="stylesheet" href="' + root + 'assets/read.css">', 1)
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
        for rel in sorted(q.name for q in PUB_FILES.iterdir() if q.is_dir() and (SRC / 'releases' / f'{q.name}.json').is_file()):
            for meta, body in reader_pages(rel, local):
                path = meta['path']
                assert path not in seen, f'two pages at {path!r}'
                seen.add(path)
                target = new / path / 'index.html'
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
