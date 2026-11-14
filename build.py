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
import filecmp, hashlib, html, json, pathlib, re, shutil, sys, tempfile
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
# The menu, in the frame's order. A page is listed here only once its content is released.
NAV = [('materials/', 'Materials'), ('funding/', 'Funding'), ('contact/', 'Contact')]
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
    zen = json.loads((SRC / 'releases' / f'{release}.zenodo.json').read_text(encoding='utf-8'))
    size = {f['name']: f['size'] for f in zen['records'][record]['files']}[name]
    return f'({FORMATS[pathlib.PurePosixPath(name).suffix]}, {max(1, round(size / 1000))} KB)'


def doi_link(doi):
    return f'<a class="doi" href="https://doi.org/{html.escape(doi)}">doi:{html.escape(doi)}</a>'


def record_doi(release, record, which='doi'):
    """A record's DOI from Zenodo's saved list: its own ('doi'), or the one that always leads to the newest release ('conceptdoi')."""
    zen = json.loads((SRC / 'releases' / f'{release}.zenodo.json').read_text(encoding='utf-8'))
    return doi_link(zen['records'][record][which])


MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']


def published(release):
    """The day a release was published, in words, from Zenodo's saved list: no release date is typed by hand on a page."""
    zen = json.loads((SRC / 'releases' / f'{release}.zenodo.json').read_text(encoding='utf-8'))
    days = {r['published'] for r in zen['records'].values()}
    assert len(days) == 1, f'{release}: its two records have different dates'
    y, m, d = days.pop().split('-')
    return f'{int(d)} {MONTHS[int(m) - 1]} {y}'


def earlier_releases():
    """The Materials page's list of earlier releases, from src/releases/earlier.json: no DOI is typed by hand on a page."""
    out = ['<ul class="docs">']
    for r in json.loads((SRC / 'releases' / 'earlier.json').read_text(encoding='utf-8'))['releases']:
        y, m, d = r['published'].split('-')
        out.append(f'<li class="doc"><h3>Release {html.escape(r["release"])} <span class="ver">{int(d)} {MONTHS[int(m) - 1]} {y}</span></h3><ul class="copies">'
                   f'<li>{html.escape(r["instruments_label"])}: {doi_link(r["instruments"])}</li>'
                   f'<li>{html.escape(r["guide_label"])}: {doi_link(r["guide"])}</li></ul></li>')
    return '\n'.join(out + ['</ul>'])


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
    zen = json.loads((SRC / 'releases' / f'{rel}.zenodo.json').read_text(encoding='utf-8'))
    size = {(k, f['name']): f['size'] for k, r in zen['records'].items() for f in r['files']}
    e = html.escape

    def link(record, name, text, doc):
        # The document's name is added for anyone who hears or lists the links without the heading above them.
        fmt = FORMATS[pathlib.PurePosixPath(name).suffix]
        kb = max(1, round(size[(record, name)] / 1000))
        return (f'<a href="{root}files/{rel}/{record}/{e(name)}">{e(text)}<span class="vh">: {e(doc)}</span></a> '
                f'<span class="meta">({fmt}, {kb} KB)</span>')

    def docs(items, record):
        out = ['<ul class="docs theirs">']
        for d in items:
            r = d.get('record', record)
            v = d['version']
            ver = f' <span class="ver">{"" if v.startswith("Release") else "version "}{e(v)}</span>' if v else ''
            copies = ''.join(f'<li>{link(r, f["file"], f["label"], d["name"])}</li>' for f in d['files'])
            about = f'<p>{e(d["about"])}</p>' if d['about'] else ''
            out.append(f'<li class="doc"><h3>{e(d["name"])}{ver}</h3>{about}<ul class="copies">{copies}</ul></li>')
        return '\n'.join(out + ['</ul>'])

    # A list of cards, not a table: at phone width a four-column table was cut off (found 11 Nov 2026).
    recs = ['<ul class="docs theirs">']
    for r in data['records']:
        notes = ''.join(f'<p>{e(n["text"])}</p>' for n in r['notes'])
        if r['credit']:   # the data center project's line on credit, linked to the record's license file
            c = r['credit']
            lead = c['text'][:-len(c['link'])]
            notes += f'<p>{e(lead)}<a href="{root}files/{rel}/{r["key"]}/{e(c["file"])}">{e(c["link"])}</a>.</p>'
        recs.append(f'<li class="doc"><h3>{e(r["label"])}</h3><p class="meta">License: {e(r["license"])}</p><p>{e(r["contents"])}</p>'
                    f'{notes}'
                    f'<p class="cite">To cite: <a class="doi" href="https://doi.org/{e(r["doi"])}">doi:{e(r["doi"])}</a></p></li>')
    records = '\n'.join(recs + ['</ul>'])
    begin = '\n'.join(['<ol class="theirs">'] + [f'<li><a href="{root}files/{rel}/{b["record"]}/{e(b["file"])}">{e(b["name"])}</a>: {e(b["quote"])}</li>'
                                                 for b in data['begin']] + ['</ol>'])
    return {'records': records, 'begin': begin, 'instruments': docs(data['instruments'], 'instruments'),
            'guide': docs(data['guide'], 'guide'), 'shared': docs(data['shared'], 'instruments'),
            # The release's sentence begins "Known gaps:"; the label says whose they are, and the rest is word for word.
            'gaps': f'<p class="notice"><strong>The release\'s own known gaps:</strong> <span class="theirs">{e(data["gaps"].removeprefix("Known gaps: "))}</span></p>'}


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


def render(meta, body, layout, local):
    path = meta['path']
    is_404 = path == '404.html'
    depth = 0 if is_404 else path.count('/')
    root = '/' if is_404 else '../' * depth
    index = 'index.html' if local else ''
    home = '/' if is_404 else (root + index if (root or local) else './')
    items = []
    for target, label in NAV:
        cur = ' aria-current="page"' if target == path else (' aria-current="true"' if path.startswith(target) else '')
        items.append(f'<li><a href="{root}{target}{index}"{cur}>{html.escape(label)}</a></li>')
    body = body.replace('{{gaps}}', GAPS_NOTICE)
    words = screen_words()
    body = re.sub(r'\{\{screen:(title|opening|address)\}\}', lambda m: html.escape(words[m.group(1)]), body)
    # The note stays on one line where there is room, and a mark of punctuation that follows it stays with it.
    body = re.sub(r'\{\{file:([\w.]+)/(\w+)/([^}]+)\}\}([.,;:]?)', lambda m: '<span class="nb">' + html.escape(file_note(m.group(1), m.group(2), m.group(3))) + m.group(4) + '</span>', body)
    body = re.sub(r'\{\{doi:([\w.]+)/(\w+)\}\}', lambda m: record_doi(m.group(1), m.group(2)), body)
    body = re.sub(r'\{\{alldoi:([\w.]+)/(\w+)\}\}', lambda m: record_doi(m.group(1), m.group(2), 'conceptdoi'), body)
    body = body.replace('{{earlier}}', earlier_releases())
    body = re.sub(r'\{\{published:([\w.]+)\}\}', lambda m: published(m.group(1)), body)
    if 'release' in meta:
        blocks = release_blocks(meta['release'], root)
        body = re.sub(r'\{\{release:(\w+)\}\}', lambda m: blocks[m.group(1)], body)
    if 'theirs' in meta:
        body = body.replace('{{theirs}}', released(meta['theirs'].split()))
    if '{{byline}}' in body:
        assert path == '' and body.count('{{byline}}') == 1, f'{path!r}: the byline is placed once, on the home page only'
        body = body.replace('{{byline}}', unbroken(BYLINE))
    title = meta['title']
    fill = {
        'body': body,
        'logo': (SRC / 'logo.inc').read_text(encoding='utf-8').split('-->\n', 1)[1].strip(),
        'title_tag': html.escape(title if not path else f'{meta.get("tab", title)} · In-Kind Standard'),
        'description': html.escape(meta['description'], quote=True),
        'footline': unbroken(STATUS),
        'nav': '<ul>' + ''.join(items) + '</ul>',
        'updated': meta['updated'],
        'gaps_line': GAPS,
        # A not-found page has no address of its own, so it prints none.
        'printed': '' if is_404 else f'<p class="print-only">Printed from {SITE}{path}</p>\n',
        'home': home, 'root': root, 'index': index,
    }
    out = layout
    for k in ('body', 'logo', 'title_tag', 'description', 'footline', 'nav', 'updated', 'gaps_line', 'printed', 'home', 'root', 'index'):
        out = out.replace('{{' + k + '}}', fill[k])
    assert '{{' not in out, f'{path}: unfilled placeholder'
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
        for target, _ in NAV:
            assert target in seen, f'menu item {target!r} has no page'
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
