#!/usr/bin/env python3
"""Makes src/releases/<release>.json from the release's own files, so that every document name and
description on the release page is the release's own words. Run once for each release, then read the result.
  python3 tools/make_release_data.py 2026.4            write the file
  python3 tools/make_release_data.py 2026.4 --print    print it, and write nothing

Where each part comes from:
  document names        the tables in sections 3 and 4 of the release's change log
  descriptions          the "Contents" tables of the two README files
  record names, DOIs    the table at the top of 000_START_HERE.md
  Record 1's license    one sentence from README_RECORD_1_INSTRUMENTS.md and one from LICENSE_RECORD_1_CC0.txt
  known gaps            002_MANIFEST.txt
The two sentences on Record 1's license, and the line on crediting Record 2 with its link to that record's
license file, are the data center project's choice for this site (its note of 11 November 2026, point 4).
The labels on the copies ("Annotated copy", "Clean copy", "Open the file") and the names of the About,
navigation and license files are this site's own.
"""
import json, pathlib, re, sys
def _stopped(kind, value, tb, _here=str(pathlib.Path(__file__).resolve())):   # the file's path, kept: Python 3.13 removes __file__ before the hook runs
    """If the tool breaks, say so in one plain line, not a traceback (the build check of candidate 4, C4-22)."""
    import traceback, os.path
    frames_ = traceback.extract_tb(tb) if tb else []
    own_ = [f for f in frames_ if str(pathlib.Path(f.filename).resolve()) == _here]   # this file's line, not the library's (run 7, S7)
    where = (own_ or frames_ or [None])[-1]
    print(f'The release tool stopped{f" at line {where.lineno} of {os.path.basename(where.filename)}" if where else ""}: {kind.__name__}: {value}', file=sys.stderr)
sys.excepthook = _stopped

ROOT = pathlib.Path(__file__).resolve().parent.parent
if len(sys.argv) < 2 or sys.argv[1].startswith('-'): sys.exit('Give the release, for example: python3 tools/make_release_data.py 2026.4')
rel = sys.argv[1]
files = ROOT / 'docs' / 'files' / rel
if not files.is_dir(): sys.exit(f'Release {rel}: there is no folder docs/files/{rel}/. Put the release\'s files there first, unchanged.')
if not (ROOT / 'src' / 'releases' / f'{rel}.zenodo.json').is_file():
    sys.exit(f'Release {rel}: src/releases/{rel}.zenodo.json is missing. Save Zenodo\'s list of the release\'s files there first (see RUNBOOK.md, section 4).')
zen = json.loads((ROOT / 'src' / 'releases' / f'{rel}.zenodo.json').read_text(encoding='utf-8'))
have = {k: {f['name'] for f in r['files']} for k, r in zen['records'].items()}
def read(p):
    if not (files / p).is_file():
        sys.exit(f'Release {rel}: the file {p} is not in docs/files/{rel}/. Each release names its own change log (CHANGELOG_v{rel}.md).')
    return (files / p).read_text(encoding='utf-8')
start, manifest, changelog = read('instruments/000_START_HERE.md'), read('instruments/002_MANIFEST.txt'), read(f'instruments/CHANGELOG_v{rel}.md')


def name_version(stem):
    m = re.search(r'_v(\d+)_(\d+)$', stem)
    if m: return stem[:m.start()], f'{m.group(1)}.{m.group(2)}'
    m = re.search(r'_Release_(\d{4})_(\d+)$', stem)
    if m: return stem[:m.start()], f'Release {m.group(1)}.{m.group(2)}'
    return stem, ''


def contents(readme):
    t = read(readme)
    block = t[t.index('## Contents'):]
    block = block[:block.index('\n## ', 5)]
    return block, re.findall(r'^\| `([^`]+)`(?: \((\.\w+)\))? \| (.+?) \|$', block, flags=re.M)


def titles(heading, until):
    """The rows of the change log's tables under one heading: (the document's title, its version in this release)."""
    block = changelog[changelog.index(heading):changelog.index(until)]
    out = []
    for a, _, c in re.findall(r'^\| ([^|]+) \| ([^|]+) \| ([^|]+) \|$', block, flags=re.M):
        a, c = a.strip(), c.strip()
        if a in ('Instrument', 'Commentary', 'Document') or set(a) <= set('-'): continue
        out.append((a, c[1:] if re.fullmatch(r'v\d+\.\d+', c) else c))
    return out


def from_manifest(fname):
    m = re.search(r'^  ' + re.escape(fname) + r'\n\s+(?:\d+ words\s+)?(.+)$', manifest, flags=re.M)
    assert m, fname
    return m.group(1).strip()


title_of = {}
record1, record2 = titles('## 3. Instruments (Record 1)', '## 4. '), titles('## 4. Guide and methodology (Record 2)', '## 5. ')

# Record 1: the instruments, in the README's order, named as the change log names them.
block1, rows1 = contents('instruments/README_RECORD_1_INSTRUMENTS.md')
assert len(record1) == len(rows1) + 1, (len(record1), len(rows1))
instruments = []
for (stem, ext, about), (title, version) in zip(rows1, record1):
    base, ver = name_version(stem)
    assert ver == version, f'{stem}: the file says {ver}, the change log says {version} for "{title}"'
    fs = [{'file': f'{stem}_annotated{ext}', 'label': 'Annotated copy'}, {'file': f'{stem}_clean{ext}', 'label': 'Clean copy'}]
    assert all(f['file'] in have['instruments'] for f in fs), stem
    title_of[base] = title
    instruments.append({'name': title, 'version': ver, 'about': about, 'source': 'README_RECORD_1_INSTRUMENTS.md', 'files': fs})
# The Drafter's Notes: published once; the README describes them in a sentence, not in its table.
m = re.search(r'^Published once: `([^`]+)`, (.+)\.$', block1, flags=re.M)
assert m and m.group(1) in have['instruments'], 'the README\'s line on the Drafter\'s Notes'
dn, q = m.group(1), m.group(2)
base, ver = name_version(dn.rsplit('.', 1)[0])
title, version = record1[-1]
assert ver == version, (dn, ver, version)
title_of[base] = title
# The description is the README's own words; only its first letter is made a capital, to match the table's lines.
instruments.append({'name': title, 'version': ver, 'about': q[0].upper() + q[1:], 'quote': q, 'source': 'README_RECORD_1_INSTRUMENTS.md',
                    'files': [{'file': dn, 'label': 'Open the file'}]})
instruments.append({'name': 'About Record 1', 'version': '', 'about': '', 'source': '', 'files': [{'file': 'README_RECORD_1_INSTRUMENTS.md', 'label': 'Open the file'}]})

# Record 2.
_, rows2 = contents('guide/README_RECORD_2_METHODOLOGY.md')
assert len(record2) == len(rows2), (len(record2), len(rows2))
guide = []
for (fname, _, about), (title, version) in zip(rows2, record2):
    assert fname in have['guide'], fname
    base, ver = name_version(fname.rsplit('.', 1)[0])
    assert ver == version, f'{fname}: the file says {ver}, the change log says {version} for "{title}"'
    title_of[base] = title
    guide.append({'name': title, 'version': ver, 'about': about, 'source': 'README_RECORD_2_METHODOLOGY.md', 'files': [{'file': fname, 'label': 'Open the file'}]})
guide.append({'name': 'About Record 2', 'version': '', 'about': '', 'source': '', 'files': [{'file': 'README_RECORD_2_METHODOLOGY.md', 'label': 'Open the file'}]})
assert 'README_RECORD_1_INSTRUMENTS.md' in have['instruments'] - have['guide'] and 'README_RECORD_2_METHODOLOGY.md' in have['guide'] - have['instruments']

# The files that are in both records: what the release calls its navigation and license files.
both = have['instruments'] & have['guide']
named = [('000_START_HERE.md', 'Start here', True), (f'CHANGELOG_v{rel}.md', 'Change log', True), ('002_MANIFEST.txt', "List of the release's files (manifest)", False),
         ('LICENSE_RECORD_1_CC0.txt', 'License for Record 1', True), ('LICENSE_RECORD_2_CCBY.txt', 'License for Record 2', True)]
assert {n for n, _, _ in named} == both, sorted(both ^ {n for n, _, _ in named})
shared = [{'name': title, 'version': '', 'about': from_manifest(fname) if described else '', 'source': '002_MANIFEST.txt' if described else '', 'record': 'instruments',
           'files': [{'file': fname, 'label': 'Open the file'}]} for fname, title, described in named]

# "Where to begin", in the start-here file's order and words.
begin = []
for fname, record, quote in re.findall(r'^\d\. \*\*`([^`]+)`\*\* \((Record \d)\)[,:] (.+?\.)(?: |$)', start[start.index('## Where to begin'):start.index('## Which instrument')], flags=re.M):
    key = {'Record 1': 'instruments', 'Record 2': 'guide'}[record]
    assert fname in have[key], fname
    base, _ = name_version(re.sub(r'_(annotated|clean)$', '', fname.rsplit('.', 1)[0]))
    begin.append({'name': title_of[base], 'record': key, 'file': fname, 'quote': quote})
assert len(begin) == 4, begin

# The two records, their licenses in the release's words, and its known gaps.
rec_rows = {n: (name.strip(), what.strip()) for n, name, what in re.findall(r'^\| (\d)\. ([^|]+?) \| ([^|]+?) \| [^|]+ \| `[^`]+` \|$', start, flags=re.M)}
gaps = re.sub(r'\s+', ' ', re.search(r'Known gaps: .+?\.(?=\n\n)', manifest, flags=re.S).group(0))
# Record 1's license in the release's words: one sentence from its README, one from its license file (which wraps its lines).
free = 'You may adopt, adapt, excerpt and codify this material without attribution and without permission.'
trace = 'If these instruments inform an adopted ordinance or executed agreement, a citation to the deposit DOI helps others trace provenance and locate errata.'
assert free in read('instruments/README_RECORD_1_INSTRUMENTS.md'), 'the README no longer has the sentence on adopting without attribution'
assert trace in re.sub(r'\s+', ' ', read('instruments/LICENSE_RECORD_1_CC0.txt')), 'the license file no longer has the sentence on citing the DOI'
notes = {'1': [{'text': free, 'source': 'README_RECORD_1_INSTRUMENTS.md'}, {'text': trace, 'source': 'LICENSE_RECORD_1_CC0.txt'}], '2': []}
# Record 2 is credited by a link to its license file, so that the attribution's exact words stay in that one file.
credit = {'1': None, '2': {'text': 'To credit this record, use the attribution in its license file', 'link': 'its license file', 'file': 'LICENSE_RECORD_2_CCBY.txt'}}
assert credit['2']['file'] in have['guide'] and credit['2']['text'].endswith(credit['2']['link'])
records = [{'key': key, 'label': f'Record {n}: {rec_rows[n][0]}', 'contents': rec_rows[n][1], 'license': zen['records'][key]['license'],
            'notes': notes[n], 'credit': credit[n], 'doi': zen['records'][key]['doi']} for n, key in (('1', 'instruments'), ('2', 'guide'))]

out = {'release': rel,
       'made_from': 'the change log, README_RECORD_1_INSTRUMENTS.md, README_RECORD_2_METHODOLOGY.md, 000_START_HERE.md and 002_MANIFEST.txt of the release',
       'title': zen['records']['instruments']['title'].rsplit(' (Release', 1)[0],
       'gaps': gaps, 'records': records, 'begin': begin, 'instruments': instruments, 'guide': guide, 'shared': shared}
text = json.dumps(out, indent=1, ensure_ascii=False) + '\n'
if '--print' in sys.argv:      # checks/check_site.py compares this with the saved file
    sys.stdout.buffer.write(text.encode('utf-8'))
else:
    (ROOT / 'src' / 'releases' / f'{rel}.json').write_text(text, encoding='utf-8', newline='\n')
    print(f'{len(instruments)} entries in Record 1, {len(guide)} in Record 2, {len(shared)} files in both records, {len(begin)} starting points')
