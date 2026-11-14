#!/usr/bin/env python3
"""Checks the built site in docs/ (or the folder given). Fails loudly; prints a short result.
Standard library only; Python 3.10 or later.   python3 checks/check_site.py [folder]

What it cannot see: how a browser lays a page out (checks/look_check.py does part of that), whether the
HTML validates, and whether a link to another site still answers. "Zenodo's checksums" means the list
saved in src/releases/ on the date it names; this script never asks Zenodo."""
import hashlib, html, json, os, pathlib, re, shutil, subprocess, sys, tempfile
from html.parser import HTMLParser
def _stopped(kind, value, tb, _here=str(pathlib.Path(__file__).resolve())):   # the file's path, kept: Python 3.13 removes __file__ before the hook runs
    """If the check itself breaks, say so in one plain line, not a traceback (the build check of candidate 4, C4-22). The line named is
    the last one of this file in the error's trace, even when the error came from inside Python's own library (run 7, S7)."""
    import traceback
    frames_ = traceback.extract_tb(tb) if tb else []
    own_ = [f for f in frames_ if str(pathlib.Path(f.filename).resolve()) == _here]
    where = (own_ or frames_ or [None])[-1]
    print('PROBLEMS:'); print(f' - the check stopped{f" at line {where.lineno} of {os.path.basename(where.filename)}" if where else ""}: {kind.__name__}: {value}')
sys.excepthook = _stopped

ROOT = pathlib.Path(__file__).resolve().parent.parent
PUB = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / 'docs'
NAME = 'Timothy Smith'
SURNAME = NAME.split()[-1]
BYLINE = 'Prepared by Timothy Smith · Citizen-prepared working draft · Not legal advice'   # once: the home page's "Who prepares this work"
STATUS = 'Citizen-prepared working draft · Not legal advice'                               # on every page
GAPS = 'no county has adopted the model documents, no lawyer has reviewed them, and there is no organization yet.'
# The date line, the one sentence not counted in a page's words; it is taken out once, in this form only (run 7, S2).
DATE_LINE = r'Page updated \d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December) 20\d\d\.'
MAIL = 'contact@inkindstandard.org'
TITLE = 'Model Instruments for Data Center Development in Florida Counties'   # the public title (Political Neutrality Policy, section 3.15)
OUTSIDE = {'doi.org', 'screen.inkindstandard.org', 'docs.github.com'}   # the only hosts a page may link to
ALSO = {'https://github.com/InKindStandard/website',                     # and these two addresses: the site's own repository,
        'https://creativecommons.org/licenses/by/4.0/'}                  # and the license the license line names
# The license line for the site's own text, word for word (the founder's decision in the nonprofit project, step 60, choice 3 A;
# the wording as that project gave it in the shared log on 12 November 2026). The link's words carry four places where a line may
# break (<wbr>, which adds no character), so that at no width does a line begin with the mark that closes the bracket.
LICENSE = ('Except where otherwise noted, this page is licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). '
           'The name In-Kind Standard and its logo are not licensed, and material quoted from others stays under its own terms.')
LICENSE_HTML = ('<p class="license">Except where otherwise noted, this page is licensed under CC BY 4.0 (<a href="https://creativecommons.org/licenses/by/4.0/">'
                'https://<wbr>creativecommons.org/<wbr>licenses/<wbr>by/<wbr>4.0/</a>). The name In-Kind Standard and its logo are not licensed, and material quoted from others '
                'stays under its own terms.</p>')
# Each license in plain words, as the Materials page gives it (C3-08).
GLOSS = {'CC0 1.0': 'free to use without credit', 'CC BY 4.0': 'free to use with credit and a note of any changes'}
# Words the home page takes from the nonprofit project's released pages, word for word (their editions of 11 and 12 November 2026).
# Since 12 November 2026 the site hosts the funding statement: AI_FULL and PAYS must also be in it, word for word (run 7, S4).
ABOUT = ('In-Kind Standard is a citizen-prepared, nonpartisan project, planned to run as a charitable nonprofit. It writes free model documents '
         'that Florida counties may use when a large data center seeks to locate there, and keeps a public record of what Florida counties and '
         'cities have done and what communities could receive.')                                    # "About this project", in each policy
NOT_A = ('It is not a government body, a law firm, an advocacy group or a developer, and it enforces nothing. It does not say whether any '
         'project should be approved or built, and never urges a county to decide a particular way.')   # How In-Kind Standard Works v0.5, section 1 (as in v0.4 and v0.3)
AI_FULL = ('AI tools help draft and check the work, and the founder reviews every item and decides what is published, except work the founder '
           'steps aside from because of a tie, meaning a connection that might be, or look like, a conflict of interest.')   # the funding statement v0.5 (as in v0.4)
PAYS = 'No one but the founder has paid for it: the founder pays its small costs himself, and the project has received no money or other gifts.'   # the funding statement v0.5 (as in v0.4 and v0.3)
HOME_GAPS = ['No county has adopted the model documents, and no lawyer has reviewed them.',
             'Their fees and mitigation amounts stay blank until studies for the county that uses them supply them, and none of those studies has been done.',
             'The project has no organization of its own yet, and no fiscal sponsor (an established nonprofit that would oversee the work and hold its money) or board.']   # How In-Kind Standard Works v0.5, "Known gaps" (as in v0.4)
# The line on AI tools (Political Neutrality Policy v0.20, section 3.19, which reads as in v0.19 and v0.18): a page that mentions AI tools carries
# these words. The two pages that say how the work is made carry their whole sentence, word for word: the home page the funding
# statement's (AI_FULL), the accessibility statement the site's own (AI_SITE).
AI_LINE = 'decides what is published, except work the founder steps aside from because of a tie'
AI_SITE = ('AI tools help build and check this site, and the founder reviews every page and decides what is published, except work the founder '
           'steps aside from because of a tie.')
# Words that name AI tools, read without regard to capitals: on a page, and in NOTICE.md, any of them asks for the line on AI tools
# (run 14, Must fix 2: the pages' list had no tool's name, the documents' list had them).
AI_NAMED = (r'\bA(?:\.\s?)?I\b|artificial intelligence|machine[- ]learning|deep[- ]learning|language models?|\bLLMs?\b|chatbots?|neural|generative'
            r'|\bGPT|\bClaude\b|ChatGPT|Copilot|Gemini')
def other_addresses(t):
    """Every email address in t but the contact address, read without regard to capitals. An address ends in letters, so a
    version such as axe-core@4.14.0 is not one; nor is git@github.com, GitHub's address for Git (runs 11 to 14). An address
    in the user part of a link is one too (run 14)."""
    return {m_.group(0).lower() for m_ in re.finditer(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}(?![A-Za-z])', t)} - {MAIL, 'git@github.com'}
# The words must say who reviews: the founder (the build check of candidate 7, N9). The two released forms say "every item" and "every page".
AI_LINE_RE = r'the founder reviews every (?:item|page) and ' + re.escape(AI_LINE)
# No release date is typed by hand. A date may be typed in a page's source in two places only: its "updated:" line, and a dated note
# that begins "Automated checks,", "By hand," or "Correction," (the accessibility statement's tests; a correction note on a release
# page). The rule looks for a date in words, day first or month first, a month with its year, and a date in figures.
MONTH_ = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\.?'
GAP_ = r'(?:\s|&nbsp;|&#160;|&#[xX][aA]0;)+'
DATE_TYPED = '|'.join([rf'\b\d{{1,2}}(?:st|nd|rd|th)?{GAP_}{MONTH_},?{GAP_}20\d\d\b', rf'\b{MONTH_}{GAP_}\d{{1,2}}(?:st|nd|rd|th)?,?{GAP_}20\d\d\b',
                       rf'\b{MONTH_}{GAP_}20\d\d\b', r'\b20\d\d[-/.]\d{1,2}[-/.]\d{1,2}\b', r'\b\d{1,2}[-/.]\d{1,2}[-/.]20\d\d\b',
                       # and, since the build check of candidate 7 (N8): "6-Nov-2026", "November the 6th, 2026", "the 6th of November, 2026"
                       rf'\b\d{{1,2}}[-/.]{MONTH_}[-/.]20\d\d\b', rf'\b{MONTH_}{GAP_}the{GAP_}\d{{1,2}}(?:st|nd|rd|th)?,?{GAP_}20\d\d\b',
                       rf'\bthe{GAP_}\d{{1,2}}(?:st|nd|rd|th)?{GAP_}of{GAP_}{MONTH_},?{GAP_}20\d\d\b'])
# A dated note's opening counts only where a paragraph or a list item begins (N8): elsewhere it could carry a release's date.
DATE_ALLOWED = (r'(?m)^updated:.*$|(?:(?<=<li>)|(?<=<p>))(?:Automated checks|By hand|Correction), \d{1,2} '
                r'(?:January|February|March|April|May|June|July|August|September|October|November|December) 20\d\d')
# The cases in which personal details are shared, which the privacy statement names (Records and Privacy Policy v0.7, sections 4.3 and 4.6, which read as in v0.6).
# The list on the page must be these seven items and no other; the sentence on a service that holds details follows it.
CASES = ['where the law requires it;', "where another of the project's policies requires it, such as publishing donors' names and gifts;", 'with your consent;',
         'with any fiscal sponsor (an established nonprofit that would oversee the work and hold its money) or partner nonprofit, for the work it runs;',
         'with any lawyer or accountant the project engages, who is bound to keep them confidential;',
         "with emergency services, when a message shows that someone's safety is at immediate risk;",       # the limit is the Complaints Policy's, section 8.5
         'copies of messages that threaten or harass a person acting for the project, if that person goes to the police.']
SERVICE = ('A service that processes personal details for the project, bound in writing to keep them confidential, may hold them for that '
           'purpose only; that is not sharing.')                                                    # the policy's own sentence (section 4.3)
# The Contact page takes complaints about the project's own work, so it carries the released known gap on them, word for word
# (How In-Kind Standard Works v0.5, "Known gaps", the fifth, as in v0.4).
COMPLAINTS_GAP = ('Because the founder prepared and approved all the published work, every complaint about it waits, with no date set, for an '
                  'advisory committee not yet formed; the founder is looking for its members. Reports of factual errors that show the official record '
                  'or text are checked and, if wrong, corrected now.')
META = ['<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'self\'; img-src \'self\'; font-src \'self\'; base-uri \'none\'; form-action \'none\'">',
        '<meta name="referrer" content="no-referrer">']
# Two-step sign-in: no page speaks of it except through the privacy statement's sentence below, which goes on the page
# when PRIVACY_SAYS_TWO_STEP is True. The founder decides when it does.
PRIVACY_SAYS_TWO_STEP = False
TWO_STEP = 'Every project account uses two-step sign-in where the service offers it.'
# Word budgets for each page's own words. Frame v0.3 (approved 11 November) set Home 250, Materials 200, a release 150, Contact 100,
# Privacy 350 and Accessibility 250. The Neutrality Test, the second check and the release editions of 11 to 12
# November added required words, so four budgets were proposed, and the founder approved them on 12 November (decision sheet 2,
# E4 A): Materials 235, a release 220, Contact 140 and Privacy 485, with a ceiling of 460 on all the home page's words. A page more than 20 percent over its budget fails, as the founder's rule sets.
# On 12 November 2026, 11:33, the founder approved the home page's ceiling at 480 in place of 460 (decision sheet 4, H2 A),
# since the released texts it quotes (How In-Kind Standard Works v0.4 and the funding statement v0.4) are 28 words longer than v0.3.
# Words marked as another project's are not counted, so a page that quotes may also carry a ceiling: the most words, of every kind,
# its main part may hold. Each page's heading block in src/pages/ gives its numbers, and they are read from there; they must equal the
# approved numbers held below. A release's own page also names its release there.
# On 12 November 2026, 13:44, the founder chose A on decision sheet 5: every page has a ceiling, the most own words its budget
# allows plus the words it quoted that day, rounded up to a multiple of ten (Home keeps 480). A release page's ceiling is approved
# with its page and held in RELEASE_CEILING; a page of another project's released pages may hold no more words, beside its date
# line, than those pages and the room its own budget leaves (C4-11 and N12 of the second check; decision sheet 6, A, 17:29).
BUDGET, CEILING, RELEASE_OF, THEIRS_OF = {}, {}, {}, {}
for f_ in sorted((ROOT / 'src' / 'pages').glob('*.html')):
    lines_ = f_.read_text(encoding='utf-8')[4:].split('\n---\n', 1)[0].splitlines()
    if any(':' not in l for l in lines_):   # named here, before the checks begin (run 7, N4)
        print('PROBLEMS:'); print(f' - src/pages/{f_.name}: a line of its heading block is not "key: value" (a blank line counts): {[l for l in lines_ if ":" not in l][0]!r}'); sys.exit(1)
    head_ = dict(l.split(':', 1) for l in lines_)
    path_ = head_['path'].strip()
    BUDGET[path_ if path_.endswith('.html') else path_ + 'index.html'] = int(head_['budget'])
    if 'ceiling' in head_: CEILING[path_ if path_.endswith('.html') else path_ + 'index.html'] = int(head_['ceiling'])
    if 'release' in head_: RELEASE_OF[path_ + 'index.html'] = head_['release'].strip()
    if 'theirs' in head_: THEIRS_OF[path_ + 'index.html'] = head_['theirs'].split()
ROOM = 1.2
# The approved numbers are also held here, so that a page cannot raise its own: its heading block must give exactly these.
# Every release page has the release page's budget. A new page has none until the founder approves its frame; add it then.
APPROVED = {'index.html': (250, 480), 'materials/index.html': (235, 310), 'contact/index.html': (140, 230),
            'privacy/index.html': (485, 590), 'accessibility/index.html': (250, 310), '404.html': (40, 60),
            'funding/index.html': (15, None)}   # frame v0.4: the nonprofit project's words as released; the site adds one line (decision sheet 6, A)
# Another project's released pages: each page's fragments, in order, and each fragment's SHA-256 as that project released it
# (the nonprofit project's folder Website_2026-11-14b, its README, and its log entries of 14 November 2026, 01:32 to 01:48 and 01:55 to
# 02:23: the funding statement v0.5, and the record of ties with its license line; it replaces Website_2026-11-12b, which stays as it was).
# The build places them unchanged; a new version comes in a new dated folder, and is added here when the founder approves the change.
RELEASED_PAGES = {'funding/index.html': ['nonprofit/Website_2026-11-14b/funding-statement.html', 'nonprofit/Website_2026-11-14b/founder-ties.html']}
RELEASED_SHA = {'nonprofit/Website_2026-11-14b/funding-statement.html': 'a70929c16defe8a35b3ac2bc7214a25bbf357523ef5aa1d3df7688657111bd5b',
                'nonprofit/Website_2026-11-14b/founder-ties.html': 'cc65225fbb6a7a4d74972237920c9abd85490b0746886ade0529bd174014626d'}
MENU = [('materials/', 'Materials'), ('funding/', 'Funding'), ('contact/', 'Contact')]   # frame v0.4 (G2 A), each item's address and words
# (run 7, S3): How it works and Policies join once their pages are live
RELEASE_PAGE = 220   # every release page's budget (decision sheet 2, E4 A)
# The logo's mark and the browser icon, held as approved (logo kit v2.2; decision sheet 9, M1 A). A new mark or icon also needs
# its checksum here, with the founder's approval (RUNBOOK.md, section 6). The mark is src/logo.inc after its note, as the build takes it.
MARK_SHA = 'e7f6ea5d97de3b2d3a99b4aa9f46a929c62ecfbea6933dbf75c7e8128df40a5e'
ICON_SHA = 'd9950757b21e6064e0c656841a9bc24252f524eed6e339e4d9bb95d1f14cb0eb'
RELEASE_CEILING = {'2026.4': 1570}   # each release page's ceiling, approved with its page (decision sheet 5, A)
VOID = {'meta', 'link', 'img', 'br', 'hr', 'input', 'source', 'path', 'wbr'}
# The 41 elements whose start tag ends an open paragraph (the HTML standard's parsing rules), so none may sit inside one.
BLOCKS = {'address', 'article', 'aside', 'blockquote', 'center', 'dd', 'details', 'dialog', 'dir', 'div', 'dl', 'dt', 'fieldset', 'figcaption',
          'figure', 'footer', 'form', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'header', 'hgroup', 'hr', 'li', 'listing', 'main', 'menu', 'nav', 'ol', 'p',
          'plaintext', 'pre', 'search', 'section', 'summary', 'table', 'ul', 'xmp'}
AVOID = [r'\brights\b', r'\buniversal\b', '—', r'\bequity\b', r'\bBig Tech\b', r'\bfair share\b', r'\bNIMBY\b',
         r'\bred tape\b', r'\bvulnerable\b', r'\bmarginalized\b', r'\bfrontline\b', r'\bCP\b']
problems = []
def bad(msg):
    if msg not in problems: problems.append(msg)   # a fault met twice is named once (run 8, the build check, Note 3)
def stop_now(msg):
    """Stops the check with the problems found so far and this one (run 9, the build check, Note 1)."""
    print('PROBLEMS:'); [print(' -', x) for x in problems + [msg]]; sys.exit(1)
def json_of(path):
    """A JSON file of the site's, read; one that is missing or not valid JSON stops the check with its name (run 8, the build
    check, Note 3; run 9, Note 1)."""
    rel_ = path.relative_to(ROOT).as_posix()
    try: return json.loads(path.read_bytes().decode('utf-8'))
    except FileNotFoundError:
        tool_ = (f'; make it with python3 tools/make_release_data.py {path.name[:-len(".json")]} (RUNBOOK.md, section 4)'
                 if path.parent.name == 'releases' and not path.name.endswith('.zenodo.json') else '')
        stop_now(f'{rel_}: missing{tool_}')
    except json.JSONDecodeError as e_:
        stop_now(f'{rel_}: not valid JSON, line {e_.lineno}, column {e_.colno}: {e_.msg}')
# An attribute in a start tag as written: its name, the spaces around "=", and its value with its quotes (run 8, Should fix 1).
ATTR_FORM = re.compile(r'''\s+([^\s"'>/=]+)(?:(\s*)=(\s*)("[^"]*"|'[^']*'|[^\s"'=<>`]+))?''')
def sums_of(path):
    """A checksum list as sha256sum writes it: \"<64 hex>  <name>\", or \"<64 hex> *<name>\" in its binary form (run 7, N4)."""
    out_ = {}
    for l in path.read_text(encoding='utf-8').splitlines():
        if not l.strip(): continue
        m = re.fullmatch(r'([0-9a-f]{64}) [ *](.+)', l.strip())
        if not m: bad(f'{path.relative_to(ROOT).as_posix()}: a line not in the form sha256sum writes (64 lowercase hex digits, two spaces or a space and *, a file name): {l[:60]!r}'); continue
        out_[m.group(2)] = m.group(1)
    return out_
# No page asks for gifts until the organization or its fiscal sponsor is registered (Gift Acceptance Policy, section 4.3;
# frame v0.4, section 4: the funding page asks for nothing). Read in the site's own words and in what a reader meets in attributes (run 7, S8).
ASK = [r'\bdonat(?:e|es|ed|ing|ion|ions)\b', r'\bgive to\b', r'\bsupport us\b', r'\bsupport (?:the|our) (?:project|work)\b', r'\bmake a gift\b',
       r'\bcontribute to (?:the|our) (?:project|work)\b', r'\bsponsor us\b', r'\bbecome a (?:donor|sponsor|member)\b', r'\bfund (?:us|our work|the project)\b']
# The asset files, by name: every file in src/assets/ is published, so nothing else may be there (run 7, N1).
ASSETS = {'site.css', 'favicon.ico', 'fonts/AtkinsonHyperlegible-Regular.woff', 'fonts/AtkinsonHyperlegible-Bold.woff',
          'fonts/AtkinsonHyperlegible-Italic.woff', 'fonts/AtkinsonHyperlegible-BoldItalic.woff', 'fonts/OFL-AtkinsonHyperlegible.txt'}

class Page(HTMLParser):
    """Collects tags, text and links. Text inside an element of class "theirs" (another project's words) or
    "fixed" (the standard known-gaps notice) is not counted against a page's word budget."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.tags, self.own_text, self.all_text, self.main_text, self.unbalanced, self.links = [], [], [], [], [], [], []
        self.their_text = []
        self.in_main = 0; self.skip = 0; self.link = None
        # Run 8, the build check: where each tag sits (the open tags around it, with their classes), each start tag as written,
        # and the menu's links and loose words, so that the rules read the parsed page and not one way of writing it.
        self.ancestors, self.raw, self.classes_open, self.nav_links, self.nav_loose, self.link_nav = [], [], [], [], [], False
    def handle_starttag(self, tag, attrs):
        a = dict(attrs); self.tags.append((tag, a)); self.ancestors.append(tuple(self.classes_open)); self.raw.append(self.get_starttag_text() or '')
        if tag == 'main': self.in_main += 1
        if tag in BLOCKS and any(x == 'p' for x, _ in self.stack): self.unbalanced.append(f'<{tag}> inside a paragraph')
        if tag in VOID: return
        t = bool({'theirs', 'fixed'} & set((a.get('class') or '').split()))
        self.stack.append((tag, t)); self.skip += t; self.classes_open.append((tag, frozenset((a.get('class') or '').split())))
        if tag == 'a': self.link = [a.get('href') or '', a.get('class') or '', '']; self.link_nav = any(x == 'nav' for x, _ in self.stack)
    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, dict(attrs))); self.ancestors.append(tuple(self.classes_open)); self.raw.append(self.get_starttag_text() or '')
        if tag in BLOCKS and any(x == 'p' for x, _ in self.stack): self.unbalanced.append(f'<{tag}> inside a paragraph')
    def handle_endtag(self, tag):
        if tag == 'main': self.in_main -= 1
        if tag == 'a' and self.link:
            self.links.append(tuple(self.link))
            if self.link_nav: self.nav_links.append((self.link[0], self.link[2]))
            self.link = None
        if not self.stack or self.stack[-1][0] != tag: self.unbalanced.append(tag)
        else: self.skip -= self.stack.pop()[1]; self.classes_open.pop()
    def handle_data(self, data):
        self.all_text.append(data)
        if self.link: self.link[2] += data
        elif any(x == 'nav' for x, _ in self.stack): self.nav_loose.append(data)
        if self.in_main: self.main_text.append(data)
        if self.in_main and not self.skip: self.own_text.append(data)
        if self.in_main and self.skip: self.their_text.append(data)

def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4 for v in c]
    return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]
def contrast(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True)
    return (x + .05) / (y + .05)
def unbroken(line):
    """The byline or status line as build.py writes it: each part in a span, the words unchanged."""
    parts = line.split(' · ')
    return ' '.join(f'<span class="nb">{html.escape(p)}{" ·" if i < len(parts) - 1 else ""}</span>' for i, p in enumerate(parts))
def exact(target):
    """True if the file exists under PUB with exactly these letters. Windows and macOS ignore case; the host does not."""
    here = PUB
    for part in target.relative_to(PUB).parts:
        if not here.is_dir() or part not in os.listdir(here): return False
        here = here / part
    return here.is_file()

def ignored(pattern, path):
    """True if one .gitignore line names this path (relative to the site's folder, with / between parts), or a folder on its
    way, read without regard to capitals, which errs toward naming it: a line that ends in / names a folder; one with a / before
    its end is read from the site's folder; any other names a file or folder at any depth; * and ? stand for anything but /,
    **/ for any number of folders, and a closing /** for all that a folder holds. A line that begins with ! names nothing. Only
    the rule that keeps the published folder in the repository (N5) uses it (run 16)."""
    if pattern.startswith('!'): return False
    folder_only = pattern.endswith('/'); p = pattern.rstrip('/'); anchored = '/' in p; p = p.lstrip('/')
    toks_, rx_ = re.findall(r'\*\*/|\*\*|\*|\?|[^*?]+', p), ''
    for i_, tok_ in enumerate(toks_):
        if tok_ == '**/': rx_ += '(?:[^/]*/)*'
        elif tok_ == '**' and i_ == len(toks_) - 1 and rx_.endswith('/'): rx_ += '.*'
        elif tok_ in ('*', '**'): rx_ += '[^/]*'
        elif tok_ == '?': rx_ += '[^/]'
        else: rx_ += re.escape(tok_)
    parts = path.split('/')
    for k in range(1, len(parts) + 1):
        if folder_only and k == len(parts): break
        if re.fullmatch(rx_, '/'.join(parts[:k]) if anchored else parts[k - 1], flags=re.I): return True
    return False

# 1. The published pages are what the assembling script writes, and the release data is what its tool makes.
if PUB == ROOT / 'docs':
    r = subprocess.run([sys.executable, str(ROOT / 'build.py'), '--check'], capture_output=True, text=True)
    if r.returncode: bad('build: ' + (r.stderr or r.stdout).strip())
# GitHub Pages builds a folder published from a branch with Jekyll, whose default plugins cannot be turned off, unless the folder
# holds an empty .nojekyll (GitHub's own pages, read 12 November 2026). The hosted files are to be served exactly as released.
if not (PUB / '.nojekyll').is_file(): bad('.nojekyll is missing from the published folder: without it GitHub Pages runs Jekyll on it')
# The CNAME file GitHub writes into the published folder when the custom domain is set names the domain and nothing else, and the
# build keeps it, as it keeps the hosted files (the build check of candidate 7, N4).
if (PUB / 'CNAME').is_file() and (PUB / 'CNAME').read_bytes() not in (b'inkindstandard.org', b'inkindstandard.org\n'): bad('CNAME: it must read exactly "inkindstandard.org"')
build_text_ = (ROOT / 'build.py').read_text(encoding='utf-8')
if PUB == ROOT / 'docs' and (len(re.findall(r'^\s*KEPT\s*(?:[-+|&^]?=)', build_text_, flags=re.M)) != 1 or re.search(r'\bKEPT\s*\.\s*(?:add|discard|remove|clear|pop|update|difference_update|intersection_update|symmetric_difference_update)\b', build_text_)):
    bad('build.py: KEPT is set more than once, or changed after it is set (run 7, N2)')
if PUB == ROOT / 'docs' and "KEPT = {'files', 'CNAME'}" not in build_text_: bad("build.py: KEPT must be {'files', 'CNAME'}, so that a build never deletes the hosted files or GitHub's CNAME file")
# What the build keeps, tried (run 8, the build check, Note 2): a build in a scratch copy of build.py and src/, with a CNAME file
# and a hosted file in its docs/, keeps both and removes a stray file.
if PUB == ROOT / 'docs':
    with tempfile.TemporaryDirectory() as tmp_:
        s_ = pathlib.Path(tmp_) / 'site'; (s_ / 'docs' / 'files').mkdir(parents=True)
        shutil.copy2(ROOT / 'build.py', s_ / 'build.py'); shutil.copytree(ROOT / 'src', s_ / 'src', ignore=shutil.ignore_patterns('desktop.ini'))
        (s_ / 'docs' / 'CNAME').write_text('inkindstandard.org\n', encoding='utf-8'); (s_ / 'docs' / 'files' / 'kept.txt').write_text('a hosted file\n', encoding='utf-8')
        (s_ / 'docs' / 'stray.txt').write_text('not part of the site\n', encoding='utf-8')
        r_ = subprocess.run([sys.executable, '-B', str(s_ / 'build.py')], capture_output=True, text=True)
        if r_.returncode or not (s_ / 'docs' / 'CNAME').is_file() or not (s_ / 'docs' / 'files' / 'kept.txt').is_file() or (s_ / 'docs' / 'stray.txt').exists():
            bad('build.py: a build in a scratch copy did not keep docs/CNAME and docs/files, or kept a stray file' + (f': {(r_.stderr or r_.stdout).strip()[-120:]}' if r_.returncode else ''))
# Nothing in .gitignore keeps the published folder, or any file in it, out of the repository (N5).
if PUB == ROOT / 'docs' and (ROOT / '.gitignore').is_file():
    lines_ = [l.strip() for l in (ROOT / '.gitignore').read_text(encoding='utf-8').splitlines() if l.strip() and not l.strip().startswith('#')]
    for f_ in sorted(q for q in PUB.rglob('*') if q.is_file() and q.name != 'desktop.ini'):   # Windows adds desktop.ini; .gitignore keeps it out on purpose
        hit_ = next((l for l in lines_ if ignored(l, 'docs/' + f_.relative_to(PUB).as_posix())), None)
        if hit_: bad(f'.gitignore: the line "{hit_}" keeps docs/{f_.relative_to(PUB).as_posix()} out of the repository'); break

# The DOIs the site may link to: the saved Zenodo lists, and the earlier releases.
zlists = {z['release']: z for z in (json_of(f) for f in sorted((ROOT / 'src' / 'releases').glob('*.zenodo.json')))}
earlier = json_of((ROOT / 'src' / 'releases' / 'earlier.json'))['releases']
dois = {r[k] for z in zlists.values() for r in z['records'].values() for k in ('doi', 'conceptdoi')} | {e[k] for e in earlier for k in ('instruments', 'guide')}

pages = sorted(PUB.rglob('*.html'))
if sorted(p.relative_to(PUB).as_posix() for p in pages) != sorted(BUDGET): bad(f'pages are not the expected set: {[p.relative_to(PUB).as_posix() for p in pages]}')
def release_page(rel):
    """A release's own page: at materials/<number>/, its heading block naming that release, with Zenodo's list of it saved."""
    m = re.fullmatch(r'materials/(\d{4}\.\d+)/index\.html', rel)
    return bool(m) and RELEASE_OF.get(rel) == m.group(1) and m.group(1) in zlists
for rel_ in sorted(BUDGET):
    want_ = (RELEASE_PAGE, RELEASE_CEILING.get(RELEASE_OF.get(rel_))) if release_page(rel_) else APPROVED.get(rel_)
    if want_ is None: bad(f'{rel_}: no approved word budget; it is added to APPROVED once the founder approves the page\'s frame')
    elif (BUDGET[rel_], CEILING.get(rel_)) != want_: bad(f'{rel_}: its heading block gives budget {BUDGET[rel_]} and ceiling {CEILING.get(rel_)}; the approved are {want_[0]} and {want_[1]}')
    elif want_[1] is None and rel_ not in RELEASED_PAGES: bad(f'{rel_}: no approved ceiling on all its words; it is added once the founder approves one (decision sheet 5)')
# The funding page's own words are the one line decision sheet 6 approved (A, 17:29) and nothing else: it says that the policies
# its texts name are not on the site yet. It comes off, or is reworded, in the change that publishes the first policy it names
# (decision sheet 6; run 8, the words check, Note 2).
POLICIES_GAP = 'The policies this page names are working drafts not yet published here.'
shared, counts, every, names, texts, theirs, texts_own = {}, {}, {}, {}, {}, {}, {}
for p in pages:
    rel = p.relative_to(PUB).as_posix(); t = p.read_text(encoding='utf-8')
    block = ''
    if rel in RELEASED_PAGES or rel in THEIRS_OF:
        names_ = RELEASED_PAGES.get(rel)
        if THEIRS_OF.get(rel) != names_: bad(f'{rel}: its heading block names the released pages {THEIRS_OF.get(rel)}; the check holds {names_}. A new version also needs RELEASED_PAGES and RELEASED_SHA in this check, with the founder\'s approval (RUNBOOK.md, section 5)')
        parts_ = []
        for name_ in names_ or []:
            f_ = ROOT / 'src' / 'released' / name_
            b_ = f_.read_bytes() if f_.is_file() else b''
            sums_ = sums_of(f_.parent / 'SHA256SUMS.txt') if (f_.parent / 'SHA256SUMS.txt').is_file() else {}
            if hashlib.sha256(b_).hexdigest() != RELEASED_SHA.get(name_) or sums_.get(f_.name) != RELEASED_SHA.get(name_): bad(f'src/released/{name_}: not the file as released (its SHA-256, or its checksum list, differs from what the check holds)')
            parts_.append(b_.decode('utf-8', 'replace'))
        block = '<div class="theirs released">\n' + ''.join(parts_) + '</div>'
        main_ = re.search(r'<main\b[^>]*>(.*?)</main>', t, flags=re.S)
        if not main_ or main_.group(1).count(block) != 1: bad(f'{rel}: the released pages are not in the main text once, whole and unchanged, in order')
    own_html = t.replace(block, '') if block else t   # the page without another project's released words
    pg = Page(); pg.feed(t); pg.close()
    released_words = None   # on a page of another project's released pages, the words of those pages are its ceiling (decision sheet 5, A)
    if block:
        pb_ = Page(); pb_.feed('<main>' + block + '</main>'); pb_.close()
        released_words = len(re.findall(r"[A-Za-z0-9][\w'’.-]*", re.sub(r'\s+', ' ', ' '.join(pb_.main_text))))
    pg_own = Page(); pg_own.feed(own_html); pg_own.close()
    if pg.unbalanced or pg.stack: bad(f'{rel}: tags do not balance {pg.unbalanced or pg.stack}')
    if not t.startswith('<!DOCTYPE html>\n<html lang="en">'): bad(f'{rel}: doctype or language missing')
    for line in META:
        if t.count(line) != 1: bad(f'{rel}: this line must be there once, word for word: {line[:60]}')
    tagnames = [x for x, _ in pg.tags]
    for one in ('h1', 'title', 'main', 'header', 'footer', 'nav', 'svg'):
        if tagnames.count(one) != 1: bad(f'{rel}: {tagnames.count(one)} <{one}>')
    # No tables: at phone width a wide table is cut off or scrolls sideways (found 11 Nov 2026). Lists are used instead.
    for banned in ('script', 'form', 'iframe', 'style', 'object', 'embed', 'video', 'audio', 'input', 'button', 'table', 'base'):
        if banned in tagnames: bad(f'{rel}: <{banned}> present')   # in another project's released pages too, since their version of 15:57 (point 33)
    # Words the check reads but a reader is not shown (run 7, S1): the classes and attributes that hide words, only where the build
    # puts them: "vh" on a file's document name inside its link on a release page, "print-only" on the footer's lines for paper,
    # "skip" on the skip link, aria-hidden on the logo's drawing; never <template>, <noscript> or inert.
    for banned in ('template', 'noscript'):
        if banned in tagnames: bad(f'{rel}: <{banned}> present: words the check reads but a reader is not shown')
    for tag, a in pg.tags:
        cls_ = set((a.get('class') or '').split())
        if 'inert' in a: bad(f'{rel}: the inert attribute on <{tag}>: words a reader cannot reach')
        if 'aria-hidden' in a and not (tag == 'svg' and 'logo' in cls_): bad(f'{rel}: aria-hidden on <{tag}>: words a screen reader is not given')
        if 'skip' in cls_ and not (tag == 'a' and a.get('href') == '#main' and cls_ == {'skip'}): bad(f'{rel}: the class "skip" on <{tag} class="{a.get("class")}">; it belongs to the skip link only')
        if 'print-only' in cls_ and not (tag == 'p' and cls_ == {'print-only'}): bad(f'{rel}: the class "print-only" on <{tag} class="{a.get("class")}">; it belongs to the footer\'s lines for paper only')
        if 'vh' in cls_ and not (tag == 'span' and cls_ == {'vh'} and release_page(rel)): bad(f'{rel}: the class "vh" on <{tag} class="{a.get("class")}">; it belongs to a file\'s document name on a release page only')
    footer_ = re.search(r'<footer\b.*?</footer>', t, flags=re.S)
    if t.count('class="print-only"') != (footer_.group(0).count('class="print-only"') if footer_ else -1) or t.count('class="print-only"') > 2: bad(f'{rel}: words for paper only outside the footer, or more than its two lines')
    if t.count('class="skip"') != 1: bad(f'{rel}: the skip link is not there once')
    if len(re.findall(r'<span class="vh">', t)) != len(re.findall(r'<a href="[^"]*">[^<]*<span class="vh">: [^<]+</span></a>', t)): bad(f'{rel}: words hidden from the eye that are not a file\'s document name inside its link')
    # Run 8, the build check, Should fix 1: the same rules read from the parsed page, so that no way of writing a tag escapes
    # them. Every attribute is written name="value" (the rules above that read the page as text expect it), a class has no stray
    # spaces, "print-only" stands only inside the footer and at most twice, "skip" once, and "vh" only inside a link.
    for (tag, a), raw_ in zip(pg.tags, pg.raw):
        for m_ in ATTR_FORM.finditer(raw_[len(tag) + 1:]):
            if m_.group(4) is not None and (m_.group(2) or m_.group(3) or not m_.group(4).startswith('"')): bad(f'{rel}: <{tag}> writes {m_.group(1)} another way than name="value": {raw_[:70]}')
        if a.get('class') is not None and a['class'] != ' '.join(a['class'].split()): bad(f'{rel}: <{tag}> has a class with stray spaces: "{a["class"]}"')
    marks_ = {k_: [anc for (tag, a), anc in zip(pg.tags, pg.ancestors) if k_ in (a.get('class') or '').split()] for k_ in ('print-only', 'skip', 'vh')}
    if len(marks_['print-only']) > 2 or any(not any(x == 'footer' for x, _ in anc) for anc in marks_['print-only']): bad(f'{rel}: words for paper only outside the footer, or more than its two lines (read from the parsed page)')
    if len(marks_['skip']) != 1: bad(f'{rel}: {len(marks_["skip"])} skip links, read from the parsed page; there is one')
    if any(not any(x == 'a' for x, _ in anc) for anc in marks_['vh']): bad(f'{rel}: words hidden from the eye outside a link (read from the parsed page)')
    # Run 8, Should fix 2: on a page of another project's released pages, words marked as another project's are those pages
    # alone, inside their one <div class="theirs released">; no other page has such a block.
    rb_ = frozenset({'theirs', 'released'}); n_rb_ = sum(1 for _, a in pg.tags if frozenset((a.get('class') or '').split()) == rb_)
    if n_rb_ != (1 if rel in RELEASED_PAGES else 0): bad(f'{rel}: {n_rb_} blocks of another project\'s released pages; {1 if rel in RELEASED_PAGES else 0} expected')
    if rel in RELEASED_PAGES:
        for (tag, a), anc in zip(pg.tags, pg.ancestors):
            c_ = frozenset((a.get('class') or '').split())
            if c_ & {'theirs', 'fixed'} and c_ != rb_ and rb_ not in {k_ for _, k_ in anc}: bad(f'{rel}: words marked as another project\'s outside the released pages it shows, on <{tag}> (run 8, Should fix 2)')
    # Run 8, Should fix 3: the menu read from the parsed page: every link inside <nav>, in order, and no loose words there.
    nav_ = [(re.sub(r'index\.html$', '', re.sub(r'^(?:\./|/)', '', h_.replace('../', ''))), w_.strip()) for h_, w_ in pg.nav_links]
    if nav_ != MENU: bad(f'{rel}: the menu\'s links, read from the parsed page, are {nav_}; the frame sets {MENU} (run 8, Should fix 3)')
    if ''.join(pg.nav_loose).strip(): bad(f'{rel}: words in the menu that are not a link: "{"".join(pg.nav_loose).strip()[:40]}"')
    levels = [int(x[1]) for x in tagnames if re.fullmatch(r'h[1-6]', x)]
    if any(b - a > 1 for a, b in zip(levels, levels[1:])): bad(f'{rel}: a heading level is skipped')
    ids = [a['id'] for _, a in pg.tags if a.get('id')]
    if len(ids) != len(set(ids)): bad(f'{rel}: an id is used twice')
    for tag, a in pg.tags:
        if 'style' in a or any(k.startswith('on') for k in a): bad(f'{rel}: inline style or script on <{tag}>')
        if 'srcset' in a or 'ping' in a or (a.get('http-equiv') or '').lower() == 'refresh': bad(f'{rel}: srcset, ping or refresh on <{tag}>')
        if 'hidden' in a: bad(f'{rel}: the hidden attribute on <{tag}>: words the check reads but a reader does not see (N7)')
        for k, v in a.items():
            if v and re.search(r'[a-z][a-z0-9+.-]*://|^//', v) and not (tag == 'a' and k == 'href'): bad(f'{rel}: an address in {k} of <{tag}>: {v[:60]}')
        if tag == 'svg' and a.get('aria-hidden') != 'true': bad(f'{rel}: a drawing that is neither labelled nor hidden')
        if tag == 'a' and a.get('class') == 'brand' and a.get('aria-label') != 'In-Kind Standard, home page': bad(f'{rel}: the home link has no name')
        if tag == 'img':
            if not a.get('alt'): bad(f'{rel}: image without alt text')
            if not (a.get('width') and a.get('height')): bad(f'{rel}: image without a size')
        # 2. Nothing loads from another host; every link resolves, to a page, a hosted file or a place in a page.
        for attr in ('src', 'href'):
            u = a.get(attr)
            if u is None: continue
            loads = tag in ('img', 'link', 'source')
            if u.startswith('mailto:'):
                if u != 'mailto:' + MAIL or loads: bad(f'{rel}: {u}')
            elif re.match(r'[a-z]+:|//', u):
                host = re.sub(r'^https://([^/]+).*$', r'\1', u)
                if loads: bad(f'{rel}: loads from another host: {u}')
                elif u in ALSO: pass
                elif not u.startswith('https://') or host not in OUTSIDE: bad(f'{rel}: link to a host not on the list: {u}')
                elif host == 'doi.org' and u.removeprefix('https://doi.org/') not in dois: bad(f'{rel}: a DOI that is not in the saved lists: {u}')
            else:
                path, _, frag = u.partition('#')
                # The path as written: nothing resolves a link or a letter case before exact() compares the names (Windows would).
                target = p if not path else pathlib.Path(os.path.normpath((PUB / path.lstrip('/')) if path.startswith('/') else (p.parent / path)))
                if target.is_dir(): target = target / 'index.html'
                if (PUB != target and PUB not in target.parents) or not exact(target): bad(f'{rel}: broken link {u}')
                elif frag and f'id="{frag}"' not in target.read_text(encoding='utf-8'): bad(f'{rel}: no place "{frag}" in {target.relative_to(PUB).as_posix()}')
    for href, cls, words in pg.links:
        if not words.strip(): bad(f'{rel}: a link with no words: {href}')
        if href.startswith('https://doi.org/') and 'doi' in cls.split() and words.strip() != 'doi:' + href.removeprefix('https://doi.org/'): bad(f'{rel}: the DOI shown is not the DOI linked: {words.strip()}')
    # 3. Every page carries the status line, the known gaps, its date and the skip link. The name appears once, on the home page.
    text = re.sub(r'\s+', ' ', ''.join(pg.all_text)); texts[rel] = text
    # What a reader also meets outside the text: an aria-label read aloud, a tooltip, an image's words and the description that
    # search results show. The rules on AI tools, two-step sign-in, the word list, telephone numbers and asks read it too (run 7, S5).
    said_ = ' '.join(v for _, a in pg.tags for k, v in a.items() if v and (k in ('aria-label', 'aria-description', 'title', 'alt') or (k == 'content' and a.get('name') == 'description')))
    heard_ = text + ' ' + said_
    for need in (STATUS, GAPS, 'Skip to the main text', MAIL, 'Who prepares this work', LICENSE):
        if need not in text: bad(f'{rel}: missing "{need[:40]}"')
    if t.count(LICENSE_HTML) != 1: bad(f'{rel}: the license line is not there once exactly as written, link and all')
    if re.search(AI_NAMED, heard_, flags=re.I) and not re.search(AI_LINE_RE, text): bad(f'{rel}: mentions AI tools without the words section 3.19 asks for: "the founder reviews every item (or page) and {AI_LINE}"')
    if not re.search(r'Page updated \d{1,2} [A-Z][a-z]+ 20\d\d\.', text): bad(f'{rel}: no page date')
    if not re.search(r'<title>[^<]*\S[^<]*</title>', t): bad(f'{rel}: empty title')
    # The name and the surname, in the HTML as written and in the text as shown (entities resolved, tags and line breaks set aside).
    own_text_ = re.sub(r'\s+', ' ', ''.join(pg_own.all_text))
    names[rel] = (own_html.count(NAME), own_text_.count(NAME), len(re.findall(rf'\b{SURNAME}\b', own_html)), len(re.findall(rf'\b{SURNAME}\b', own_text_)))
    if own_text_.count(BYLINE) != (1 if rel == 'index.html' else 0): bad(f'{rel}: the byline belongs once on the site, in the home page\'s section "Who prepares this work", and nowhere else')
    # An address in the HTML, its entities resolved (run 13, P8), or in what the page shows, where a tag such as <wbr> can split one (run 14, P3).
    for e in sorted(other_addresses(html.unescape(t) + '\n' + heard_)): bad(f'{rel}: another email address {e}')
    if re.search(r'\(\d{3}\)\s?\d{3}[-.\s]\d{4}|\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b', heard_): bad(f'{rel}: something that looks like a telephone number')
    for pat in AVOID:
        if re.search(pat, heard_, flags=re.I): bad(f'{rel}: word list: {pat}')   # read without case (run 11, Should fix 3)
    if not PRIVACY_SAYS_TWO_STEP and re.search(r'two[- ]step|two[- ]factor|2[- ]step|\b2FA\b|multi[- ]factor|second factor', heard_, flags=re.I): bad(f'{rel}: speaks of two-step sign-in; only the privacy statement\'s own sentence may, once PRIVACY_SAYS_TWO_STEP is True')
    # 4. Word budgets: the site's own words in the main text, without the date line. Pieces of text are joined with a space,
    # so that the last word of one element and the first of the next count as two.
    for pat in ASK:
        if re.search(pat, own_text_ + ' ' + said_ + ' ' + ' '.join(pg.their_text), flags=re.I): bad(f'{rel}: asks for gifts ({pat}): no page asks until the organization or its fiscal sponsor is registered (Gift Acceptance Policy, section 4.3)')
    if len(re.findall(r'Page updated', ' '.join(pg.main_text))) != 1: bad(f'{rel}: "Page updated" is in the main text {len(re.findall(r"Page updated", " ".join(pg.main_text)))} times; only the date line says it (run 7, S2)')
    own = re.sub(DATE_LINE, '', re.sub(r'\s+', ' ', ' '.join(pg.own_text)), count=1)
    if rel == 'funding/index.html':
        own_line_ = re.sub(r'\s+', ' ', own).strip()
        if own_line_ != POLICIES_GAP: bad(f'funding/index.html: the site\'s own words here are "{own_line_[:90]}"; decision sheet 6 approved only the line "{POLICIES_GAP}"')
    n = len(re.findall(r"[A-Za-z0-9][\w'’.-]*", own)); counts[rel] = n
    every[rel] = len(re.findall(r"[A-Za-z0-9][\w'’.-]*", re.sub(r'\s+', ' ', ' '.join(pg.main_text))))
    if rel in BUDGET and n > BUDGET[rel] * ROOM: bad(f'{rel}: {n} words of its own, budget {BUDGET[rel]}')
    if rel in CEILING and every[rel] > CEILING[rel]: bad(f'{rel}: {every[rel]} words in all, ceiling {CEILING[rel]}')
    if released_words is not None:
        beside_ = len(re.findall(r"[A-Za-z0-9][\w'’.-]*", re.sub(DATE_LINE, '', re.sub(r'\s+', ' ', ' '.join(pg.main_text)), count=1)))
        room_ = int(BUDGET.get(rel, 0) * ROOM)
        if beside_ > released_words + room_: bad(f'{rel}: {beside_} words beside its date line, more than the {released_words} of the released pages it shows and the {room_} its own budget allows')
    theirs[rel] = re.sub(r'\s+', ' ', ''.join(pg.their_text)).strip()   # joined as written: a link inside a quoted sentence does not split it
    texts_own[rel] = own_text_
    # 5. The header and footer are the same on every page, the home page's and the not-found page's included (decision sheet 2,
    # E2 B). The not-found page's addresses start at the domain's root, and every other page's line "Printed from" names it.
    for part in ('header', 'footer'):
        m = re.search(rf'<{part}.*?</{part}>', t, flags=re.S)
        if not m: bad(f'{rel}: no <{part}>'); continue
        block = re.sub(r' aria-current="\w+"', '', m.group(0).replace('../', '')).replace('href="./', 'href="').replace('href="/', 'href="')
        shared.setdefault(part, {})[rel] = re.sub(r'<p class="print-only">Printed from \S+</p>\n', '', block)
for part, blocks in shared.items():
    if len(set(blocks.values())) != 1: bad(f'the {part} differs between pages')
# Every footer carries the short line, and its link "Who prepares this work" lands on the home page's section (E2 B).
for rel, block in shared.get('footer', {}).items():
    if f'<p class="byline">{unbroken(STATUS)}</p>' not in block: bad(f'{rel}: the footer does not carry the short line "{STATUS}"')
    if '<a href="#who">Who prepares this work</a>' not in block: bad(f'{rel}: the footer\'s link "Who prepares this work" does not lead to the home page\'s section #who')
# The byline is the first line of the home page's section "Who prepares this work", where every page's link lands (E2 B).
if not re.search(r'<h2 id="who">Who prepares this work</h2>\s*<p class="byline">' + re.escape(unbroken(BYLINE)) + r'</p>', (PUB / 'index.html').read_text(encoding='utf-8') if (PUB / 'index.html').is_file() else ''):
    bad('index.html: the byline is not the first line of the section "Who prepares this work"')
for i_, what_ in enumerate(('the name in the HTML', 'the name as shown', 'the surname in the HTML', 'the surname as shown')):
    if sum(v[i_] for v in names.values()) != 1 or names.get('index.html', (0, 0, 0, 0))[i_] != 1:
        bad(f'{what_} should appear once, on the home page: {({k: v[i_] for k, v in names.items() if v[i_]})}')
if PRIVACY_SAYS_TWO_STEP and TWO_STEP not in texts.get('privacy/index.html', ''): bad('privacy: PRIVACY_SAYS_TWO_STEP is True, so the page must carry the TWO_STEP sentence word for word')
for rel in ('index.html', 'materials/index.html'):
    if TITLE not in texts.get(rel, ''): bad(f'{rel}: the public title of the model documents is missing')
# The home page's quotes from the funding statement are in the statement the site hosts, word for word (run 7, S4).
hosted_ = ' '.join(theirs.get(r_, '') for r_ in RELEASED_PAGES)
for need in (PAYS, AI_FULL):
    if need not in hosted_: bad(f'index.html quotes "{need[:50]}...", which the released pages the site hosts no longer say word for word')
# Every folder of another project's released pages in src/released/ is one a page shows: an old version would be published
# unchecked. An older version leaves src/released/ (RUNBOOK.md, section 5; run 7, the build check, N8).
shown_ = {n_.rsplit('/', 1)[0] for names_ in RELEASED_PAGES.values() for n_ in names_}
for d_ in sorted({f_.parent for f_ in (ROOT / 'src' / 'released').rglob('*') if f_.is_file() and f_.name != 'desktop.ini'}) if (ROOT / 'src' / 'released').is_dir() else []:   # at any depth (run 8, Note 6)
    if d_.relative_to(ROOT / 'src' / 'released').as_posix() not in shown_: bad(f'src/released/{d_.relative_to(ROOT / "src" / "released").as_posix()}: no page shows it, so it would be published unchecked; move the older folder out of src/released/ (RUNBOOK.md, section 5)')
# The home page states what the project is and its known gaps in the nonprofit project's released words.
home_text = texts.get('index.html', '')
for need in [ABOUT, NOT_A, AI_FULL, PAYS] + HOME_GAPS:
    if need not in home_text: bad(f'index.html: not word for word as released: "{need[:50]}"')
if AI_SITE not in texts.get('accessibility/index.html', ''): bad('accessibility: the sentence on AI tools is not there word for word')
contact_text = texts.get('contact/index.html', '')
if f'"{COMPLAINTS_GAP}"' not in contact_text: bad('contact: the released known gap on complaints about the project\'s own work is not there word for word, in quotation marks')
# The home page's section "Who prepares this work" links to the funding page (decision sheet 4, H1 A), and every page's menu is the
# frame's, in its order, with only the pages that are live.
home_html_ = (PUB / 'index.html').read_text(encoding='utf-8') if (PUB / 'index.html').is_file() else ''
if not re.search(r'<h2 id="who">Who prepares this work</h2>.*?<a href="funding/(?:index\.html)?#founder-ties">a tie</a>', home_html_, flags=re.S): bad('index.html: the section "Who prepares this work" does not link "a tie" to the record of ties on the funding page (run 7, Should fix 2)')
if not re.search(r'<h2 id="who">Who prepares this work</h2>.*?<a href="funding/(?:index\.html)?">', home_html_, flags=re.S): bad('index.html: the section "Who prepares this work" does not link to the funding page')
for rel, block_ in shared.get('header', {}).items():
    items_ = [(re.sub(r'index\.html$', '', h_), w_) for h_, w_ in re.findall(r'<li><a href="([^"]*)"[^>]*>([^<]+)</a></li>', block_)]
    if items_ != MENU: bad(f'{rel}: the menu is {items_}; the frame sets {MENU}')
# The Screen is named and described in the words given for the link (src/screen.json).
screen = json_of((ROOT / 'src' / 'screen.json'))
if screen['opening'] not in home_text: bad('index.html: the opening line of the Screen is not word for word')
home_page = (PUB / 'index.html').read_text(encoding='utf-8') if (PUB / 'index.html').is_file() else ''
if f'<a class="btn" href="{screen["address"]}">{html.escape(screen["title"])}</a>' not in home_page: bad('index.html: the link to the Screen does not carry its title')
# Words marked as another project's are not counted against a budget. Outside the release pages, whose words are tested
# against the release's files below, they may only be the released sentences this check knows.
KNOWN_THEIRS = sorted([ABOUT, NOT_A, PAYS, AI_FULL, f'"{COMPLAINTS_GAP}"', f'"{screen["opening"]}"', 'Known gaps: ' + GAPS] + HOME_GAPS, key=len, reverse=True)
for rel, said in theirs.items():
    if release_page(rel) or rel in RELEASED_PAGES: continue
    for k in KNOWN_THEIRS: said = said.replace(k, ' ')
    if re.search(r'[A-Za-z0-9]', said): bad(f'{rel}: words marked as another project\'s that are not among the released sentences: "{said.strip()[:60]}"')
for rel in ('privacy/index.html', 'accessibility/index.html'):
    if f'"{screen["title"]}"' not in texts.get(rel, ''): bad(f'{rel}: the Screen is not named by its title')
for rel_, t_ in texts_own.items():   # another project's released words keep their own form (the funding statement v0.4 used the older one)
    if 'What Florida Counties Can Do' in t_: bad(f'{rel_}: names the Screen in another form than src/screen.json gives')
# The privacy statement names each case in which details are shared.
privacy_page = (PUB / 'privacy' / 'index.html').read_text(encoding='utf-8') if (PUB / 'privacy' / 'index.html').is_file() else ''
# Tags are read in either case, as a browser reads them: <LI> is a list item too.
m_ = re.search(r'only in these cases:</p>\s*<ul>(.*?)</ul>', privacy_page, flags=re.S | re.I)
listed = [html.unescape(re.sub(r'<[^>]+>', '', x)).strip() for x in re.findall(r'<li\b[^>]*>(.*?)</li>', m_.group(1), flags=re.S | re.I)] if m_ else []
if listed != CASES: bad(f'privacy: the cases of sharing are not the seven the policy allows, one for one: {[x for x in listed if x not in CASES] or [x for x in CASES if x not in listed]}')
# The seven cases are the only list in the statement's main text: a second list could add a case the reading above does not see.
main_ = re.search(r'<main\b.*?</main>', privacy_page, flags=re.S | re.I)
if len(re.findall(r'<li\b', main_.group(0) if main_ else '', flags=re.I)) != len(CASES): bad('privacy: its main text holds a list item other than the seven cases of sharing')
if SERVICE not in texts.get('privacy/index.html', ''): bad('privacy: the sentence on a service that holds details is missing')
# A hold covers a claim, audit or investigation that is pending or expected (the policy's section 3.1); a rewording once dropped "or expected".
if 'pending or expected claim, audit or investigation' not in texts.get('privacy/index.html', ''): bad('privacy: the words "pending or expected claim, audit or investigation" are missing')

# 6. Hosted release files: exactly Zenodo's list, each the same size and MD5; the release page uses the release's own words.
hosted = 0; expected = {'.nojekyll', 'favicon.ico', 'CNAME'} | set(BUDGET)
found_assets_ = {f.relative_to(ROOT / 'src' / 'assets').as_posix() for f in (ROOT / 'src' / 'assets').rglob('*') if f.is_file() and f.name != 'desktop.ini'}
for x_ in sorted(found_assets_ - ASSETS): bad(f'src/assets/{x_}: not one of the site\'s asset files; everything in src/assets/ is published')
for x_ in sorted(ASSETS - found_assets_): bad(f'src/assets/{x_} is missing')
expected |= {'assets/' + x_ for x_ in ASSETS}
for rel_id, z in zlists.items():
    md5 = {}
    for key, r in z['records'].items():
        folder = PUB / 'files' / rel_id / key
        want = {f['name'] for f in r['files']}; got = {q.name for q in folder.iterdir() if q.name != 'desktop.ini'} if folder.is_dir() else set()   # Windows adds desktop.ini; it is not part of the site
        if want != got: bad(f'files/{rel_id}/{key}: missing {sorted(want - got)}, extra {sorted(got - want)}')
        if sum(f['size'] for f in r['files']) != r['total']: bad(f'{rel_id}: sizes of {key} do not add up to Zenodo\'s total')
        for f in r['files']:
            expected.add(f'files/{rel_id}/{key}/{f["name"]}')
            q = folder / f['name']
            if not q.is_file(): continue
            b = q.read_bytes(); hosted += 1; md5[(key, f['name'])] = f['md5']
            if len(b) != f['size'] or hashlib.md5(b).hexdigest() != f['md5']: bad(f'files/{rel_id}/{key}/{f["name"]} differs from the copy at Zenodo')
    data_file = ROOT / 'src' / 'releases' / f'{rel_id}.json'
    data = json_of(data_file)
    if PUB == ROOT / 'docs':   # the saved data is exactly what the tool makes from the release's own files
        r = subprocess.run([sys.executable, str(ROOT / 'tools' / 'make_release_data.py'), rel_id, '--print'], capture_output=True)
        if r.returncode or r.stdout != data_file.read_bytes(): bad(f'{rel_id}: src/releases/{rel_id}.json is not what tools/make_release_data.py makes: {(r.stderr.decode("utf-8", "replace") or "it differs").strip()[-200:]}')
    def words_of(name):
        for key in z['records']:
            q = PUB / 'files' / rel_id / key / name
            if q.is_file(): return q.read_text(encoding='utf-8')
        return ''
    page_file = PUB / 'materials' / rel_id / 'index.html'
    page = re.sub(r'<!--.*?-->', '', page_file.read_text(encoding='utf-8'), flags=re.S) if page_file.is_file() else ''   # a link inside a comment is not a link
    page_text = texts.get(f'materials/{rel_id}/index.html', '')
    both = set.intersection(*({f['name'] for f in r['files']} for r in z['records'].values()))
    if {f['file'] for d in data['shared'] for f in d['files']} != both: bad(f'{rel_id}: the files listed as in both records are not the files in both records')
    for d in data['instruments'] + data['guide'] + data['shared']:
        for f in d['files']:
            stem = f['file'].rsplit('.', 1)[0]
            if (f['label'] == 'Annotated copy') != stem.endswith('_annotated') or (f['label'] == 'Clean copy') != stem.endswith('_clean'): bad(f'{rel_id}: the label "{f["label"]}" is on {f["file"]}')
        if not d['about']: continue
        needle = d.get('quote') or d['about']
        if needle not in words_of(d['source']) or d['about'].lower() != needle.lower(): bad(f'{rel_id}: "{needle[:50]}" is not word for word in {d["source"]}')
        if html.escape(d['about']) not in page: bad(f'{rel_id}: the description of {d["name"]} is not on the release page')
    start, manifest = words_of('000_START_HERE.md'), re.sub(r'\s+', ' ', words_of('002_MANIFEST.txt'))
    for b in data['begin']:
        if b['quote'] not in start: bad(f'{rel_id}: "{b["quote"][:50]}" is not word for word in 000_START_HERE.md')
    if data['gaps'] not in manifest or data['gaps'].removeprefix('Known gaps: ') not in page_text: bad(f'{rel_id}: the known gaps are not word for word in the release, or not on the page')
    for r in data['records']:
        zr = z['records'][r['key']]
        if r['contents'] not in start or r['doi'] not in start: bad(f'{rel_id}: the line for {r["label"]} is not as in 000_START_HERE.md')
        for note in r['notes']:
            if note['text'] not in re.sub(r'\s+', ' ', words_of(note['source'])) or note['text'] not in page_text: bad(f'{rel_id}: "{note["text"][:50]}" is not word for word in {note["source"]}, or not on the page')
        if r['credit']:
            c = r['credit']
            if c['text'] not in page_text or f'files/{rel_id}/{r["key"]}/{c["file"]}">{c["link"]}</a>' not in page or c['file'] not in {f['name'] for f in zr['files']}: bad(f'{rel_id}: the line on crediting {r["label"]} is missing or does not link its license file')
        if zr['doi'] != r['doi'] or zr['license'] != r['license']: bad(f'{rel_id}: DOI or license of {r["key"]} differs from Zenodo\'s')
        if f'({zr["license"]}, {GLOSS[zr["license"]]})' not in texts.get('materials/index.html', '') or f'License: {zr["license"]}' not in page_text: bad(f'{rel_id}: the license of {r["key"]} is not shown as Zenodo has it')
    if data['title'] != TITLE or TITLE not in page_text: bad(f'{rel_id}: the public title is missing from the release page')
    linked = {md5.get((k, n)) for k, n in re.findall(r'href="(?:\.\./)*files/' + re.escape(rel_id) + r'/(\w+)/([^"]+)"', page)}
    unlinked = sorted(n for (k, n), m in md5.items() if m not in linked)
    if unlinked: bad(f'{rel_id}: hosted but not linked from the release page: {unlinked}')
materials = texts.get('materials/index.html', '')
for e in earlier:
    day = f'{int(e["published"][8:])} {["January","February","March","April","May","June","July","August","September","October","November","December"][int(e["published"][5:7]) - 1]} {e["published"][:4]}'
    if not re.search(rf'Release {re.escape(e["release"])} {day}[^R]*doi:{re.escape(e["instruments"])}[^R]*doi:{re.escape(e["guide"])}', materials): bad(f'materials: Release {e["release"]} is not listed with its date and both DOIs')
# The mark and the icon are the approved ones, and no built page carries a comment (run 9, the build check, Should fix 2).
if '-->\n' not in (ROOT / 'src' / 'logo.inc').read_text(encoding='utf-8'): bad('src/logo.inc: its note at the top is missing; the build takes the mark from after it')
elif hashlib.sha256((ROOT / 'src' / 'logo.inc').read_text(encoding='utf-8').split('-->\n', 1)[1].strip().encode('utf-8')).hexdigest() != MARK_SHA:
    bad('src/logo.inc: the mark differs from the approved one; a new mark also needs MARK_SHA in this check, with the founder\'s approval (RUNBOOK.md, section 6)')
for p_ in (ROOT / 'src' / 'assets' / 'favicon.ico', PUB / 'favicon.ico', PUB / 'assets' / 'favicon.ico'):
    if not p_.is_file() or hashlib.sha256(p_.read_bytes()).hexdigest() != ICON_SHA:
        bad(f'{p_.relative_to(ROOT).as_posix()}: the browser icon is missing or differs from the approved one; a new icon also needs ICON_SHA in this check, with the founder\'s approval (RUNBOOK.md, section 6)')
for p_ in sorted(PUB.rglob('*.html')):
    if p_.relative_to(PUB).parts[0] != 'files' and '<!--' in p_.read_text(encoding='utf-8'):
        bad(f'{p_.relative_to(PUB).as_posix()}: a comment in a built page; a published page carries none, so take it out of src/')
# Nothing else is in the folder: no stray file, no image file. (Windows adds desktop.ini to folders; it never reaches the repository.)
for f in PUB.rglob('*'):
    if not f.is_file() or f.name == 'desktop.ini': continue
    rel = f.relative_to(PUB).as_posix()
    if f.suffix.lower() in ('.png', '.svg', '.jpg', '.jpeg', '.gif', '.webp'): bad(f'image file {rel}: the site keeps no image files; the logo is drawn into each page (the workspace the drafts are made in adds a provenance record to each PNG and SVG file it hands over, which changes the file)')
    elif rel not in expected: bad(f'a file that is not part of the site: {rel}')

# 7. Colors: text at least 7 to 1, controls and focus marks at least 3 to 1, in both sets. A color may be named only in a :root block.
css = (PUB / 'assets' / 'site.css').read_text(encoding='utf-8')
if re.search(r'url\(\s*["\']?(?:[a-z]+:|//)', css) or '@import' in css: bad('site.css loads from another host')
for f in re.findall(r'url\("([^"]+)"\)', css):
    if not (PUB / 'assets' / f).is_file(): bad(f'site.css: missing {f}')
rest = re.sub(r':root\{[^}]*\}', '', re.sub(r'/\*.*?\*/', '', css, flags=re.S))
for stray in re.findall(r'#[0-9A-Fa-f]{3,8}\b|\brgba?\(|\bhsla?\(|\bopacity\s*:', rest): bad(f'site.css: a color or opacity set outside the named colors: {stray}')
light = dict(re.findall(r'--([\w-]+):(#[0-9A-Fa-f]{6})', css[css.index(':root{'):css.index('@media (prefers-color-scheme:dark)')]))
dark = dict(light); dark.update(re.findall(r'--([\w-]+):(#[0-9A-Fa-f]{6})', css[css.index('@media (prefers-color-scheme:dark)'):css.index('*{box-sizing')]))
TEXT = [('ink', 'bg'), ('ink', 'surface'), ('ink2', 'bg'), ('ink2', 'surface'), ('link', 'bg'), ('link', 'surface'), ('band-ink', 'band'), ('btn-ink', 'btn')]
MARK = [('btn-line', 'bg'), ('btn-line', 'surface'), ('focus', 'bg'), ('focus', 'surface'), ('gold', 'band'), ('band-sub', 'band'), ('mark', 'surface')]
lowest = {}
for name, s in (('light', light), ('dark', dark)):
    for pairs, floor in ((TEXT, 7.0), (MARK, 3.0)):
        for a, b in pairs:
            c = contrast(s[a], s[b]); lowest[floor] = min(lowest.get(floor, 99), c)
            if c < floor: bad(f'{name}: {a} on {b} is {c:.2f} to 1, under {floor}')
# The print colors too: black on white.
paper = dict(light); paper.update(re.findall(r'--([\w-]+):(#[0-9A-Fa-f]{6})', css[css.index('@media print'):]))
for a, b in TEXT:
    if contrast(paper[a], paper[b]) < 7.0 and (a, b) not in (('band-ink', 'band'), ('btn-ink', 'btn')): bad(f'print: {a} on {b} is under 7 to 1')   # on paper the band and the buttons take the ink color
# Every named color is one this check knows, so that a new one cannot be added and used unchecked.
KNOWN = {n for pair in TEXT + MARK for n in pair} | {'rule'}
for n in set(re.findall(r'--([\w-]+):#', css)) - KNOWN: bad(f'site.css: a named color this check does not know: --{n}')
# Colors are named in three blocks only: the light set, the dark set inside its media block, and the print set inside its own.
plain_ = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
roots = [m.start() for m in re.finditer(r':root\{', plain_)]
if len(roots) != 3 or not plain_[:roots[1]].rstrip().endswith('@media (prefers-color-scheme:dark){') or not plain_[:roots[2]].rstrip().endswith('@media print{'):
    bad('site.css: colors are named somewhere other than the light set, the dark set and the print set')
if re.search(r'--[\w-]+\s*:', re.sub(r':root\{[^}]*\}', '', plain_)): bad('site.css: a name is set outside the three sets of named colors')
# Each rule, as (selector, declarations). Colors are used only through their names; a text color only through a name checked as text.
plain = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
rules = [(s.strip(), dict((d.split(':', 1)[0].strip(), d.split(':', 1)[1].strip()) for d in body.split(';') if ':' in d)) for s, body in re.findall(r'([^{}]+)\{([^{}]*)\}', plain)]
TEXT_NAMES = {a for a, _ in TEXT}
PAINT = ('color', 'background', 'background-color', 'outline', 'outline-color', 'fill', 'stroke', 'text-decoration-color', 'box-shadow', 'caret-color', 'accent-color', 'column-rule')
WORDS = {'solid', 'none', 'transparent', 'currentColor', 'inherit', 'Canvas', 'CanvasText', 'LinkText', 'ButtonText', 'px', 'rem', 'em'}
for sel, decl in rules:
    if sel in (':root', '@font-face'): continue
    for prop, value in decl.items():
        if prop in ('filter', 'backdrop-filter', 'opacity', 'mix-blend-mode', '-webkit-text-fill-color', '-webkit-text-stroke', '-webkit-text-stroke-color') or 'color-mix(' in value: bad(f'site.css: {sel} changes a color with {prop}')
        if prop == 'color' and 'transparent' in value: bad(f'site.css: {sel} makes text transparent')
        if prop in ('text-decoration-line', 'text-decoration-color', 'text-decoration-style'): bad(f'site.css: {sel} sets {prop}; a link\'s underline is set only by the rule for "a"')
        if prop == 'outline-color' and not (sel in ('.band a:focus-visible', '.skip:focus-visible') and value == 'var(--gold)'): bad(f'site.css: {sel} changes the focus outline\'s color')
        if prop in PAINT or prop.startswith('border'):
            for word in re.findall(r'(?<![\w(-])[A-Za-z][A-Za-z-]*(?![\w(-])', re.sub(r'var\(--[\w-]+\)', ' ', value)):
                if word not in WORDS: bad(f'site.css: {sel} sets {prop} with the word "{word}"; a color is used only through its name')
        if prop == 'color':
            for n in re.findall(r'var\(--([\w-]+)\)', value):
                if n not in TEXT_NAMES: bad(f'site.css: {sel} uses --{n} as a text color; it is not checked as one')
        if prop.startswith('outline') and re.fullmatch(r'0|none|0 none|none 0', value): bad(f'site.css: {sel} removes the focus outline')
        if prop == 'text-decoration' and value == 'none' and sel not in ('.brand', 'nav a', '.btn'): bad(f'site.css: {sel} removes a link\'s underline')
top = {s: d for s, d in rules}
if top.get('a', {}).get('text-decoration') != 'underline': bad('site.css: links are not underlined (the rule for "a")')
if not top.get('a:focus-visible', {}).get('outline', '').startswith('3px solid var(--focus)'): bad('site.css: missing "a:focus-visible{outline:3px solid var(--focus)"')
if any('class="vh"' in q.read_text(encoding='utf-8') for q in pages) and top.get('.vh', {}).get('clip-path') != 'inset(50%)': bad('site.css: the rule that hides words kept for screen readers (.vh) is missing')
# Each named color is a six-figure value, so that every one is measured (the build check of candidate 4, C4-04): a shorter form,
# an added alpha figure or a function would be passed over by the reading above. The font stack is the one other name.
for m_ in re.finditer(r':root\{([^}]*)\}', plain_):
    for name_, value_ in re.findall(r'--([\w-]+)\s*:\s*([^;]+?)\s*(?:;|$)', m_.group(1)):
        if name_ != 'sans' and not re.fullmatch(r'#[0-9A-Fa-f]{6}', value_): bad(f'site.css: --{name_} is "{value_}"; a named color is written #RRGGBB')
# Paint is held as it is today (C4-06): "all" is not used; generated content only in the print rule that writes a link's address after
# it, and in its exception for another project's released pages, whose links show their address already (run 7, Should fix 1);
# underlines and focus outlines exactly as listed, by media block and selector. A deliberate change to these is made here too.
def css_rules(sheet):
    """Each rule as (media block, selector, declarations); the media block is '' outside one. One level of @media, as this sheet has."""
    out_, media_ = [], ''
    for m_ in re.finditer(r'(@media[^{]*)\{|([^{}]+)\{([^{}]*)\}|\}', re.sub(r'/\*.*?\*/', '', sheet, flags=re.S)):
        if m_.group(1) is not None: media_ = m_.group(1).strip()
        elif m_.group(2) is not None: out_.append((media_, m_.group(2).strip(), [(d.split(':', 1)[0].strip(), d.split(':', 1)[1].strip()) for d in m_.group(3).split(';') if ':' in d]))
        else: media_ = ''
    return out_
HELD_PAINT = {('', 'a', 'text-decoration'): 'underline', ('', 'a', 'text-decoration-thickness'): '.08em', ('', 'a', 'text-underline-offset'): '.18em',
              ('', 'a:hover', 'text-decoration-thickness'): '.16em', ('', 'a:focus-visible', 'outline'): '3px solid var(--focus)',
              ('', 'a:focus-visible', 'outline-offset'): '3px', ('', '.skip:focus-visible', 'outline-color'): 'var(--gold)',
              ('', '.brand', 'text-decoration'): 'none', ('', '.band a:focus-visible', 'outline-color'): 'var(--gold)', ('', 'nav a', 'text-decoration'): 'none',
              ('', '.btn', 'text-decoration'): 'none', ('', '.btn:hover', 'text-decoration'): 'underline', ('@media print', '.btn', 'text-decoration'): 'underline',
              ('@media print', 'main a[href^="http"]:not(.doi)::after', 'content'): '" (" attr(href) ")"',
              ('@media print', 'main .released a[href^="http"]::after', 'content'): 'none'}
seen_ = set()
for media_, sel_, decls_ in css_rules(css):
    for prop_, value_ in decls_:
        if prop_ == 'all': bad(f'site.css: {sel_} uses "all", which resets every property at once')
        elif prop_ == 'content' or prop_.startswith(('text-decoration', 'text-underline', 'outline')):
            seen_.add((media_, sel_, prop_))
            if HELD_PAINT.get((media_, sel_, prop_)) != value_: bad(f'site.css: {(media_ + " ") if media_ else ""}{sel_} sets {prop_}: {value_}; underlines, focus outlines and generated content are held as this check lists them')
for k_ in sorted(HELD_PAINT.keys() - seen_): bad(f'site.css: {k_[1]} no longer sets {k_[2]}: {HELD_PAINT[k_]}')
fonts = [f for f in (PUB / 'assets' / 'fonts').glob('*.woff')] if (PUB / 'assets' / 'fonts').is_dir() else []
if not fonts or not (PUB / 'assets' / 'fonts' / 'OFL-AtkinsonHyperlegible.txt').is_file(): bad('the font files or their license file are missing')
# No DOI is typed by hand on a page: the build places each one from src/releases/.
for f in sorted((ROOT / 'src' / 'pages').glob('*.html')) + [ROOT / 'src' / 'layout.html']:
    if 'zenodo.' in f.read_text(encoding='utf-8'): bad(f'src/{f.relative_to(ROOT / "src").as_posix()}: a DOI typed by hand; use {{{{doi:...}}}}, {{{{alldoi:...}}}} or {{{{earlier}}}}')
    if re.search(DATE_TYPED, re.sub(DATE_ALLOWED, '', f.read_text(encoding='utf-8'))):
        bad(f'src/{f.relative_to(ROOT / "src").as_posix()}: a date typed by hand; a release\'s date is placed with {{{{published:...}}}}, and a dated note begins '
            '"Automated checks,", "By hand," or "Correction," and gives the day, the month in full and the year')
# Each DOI stands beside its own record: the current release's on the home page, the two that lead to the newest release on Materials.
cur = zlists[max(zlists, key=lambda r: [int(x) for x in re.findall(r'\d+', r)])]['records']   # the newest by number: 2026.10 comes after 2026.4
for rel_, needs in (('index.html', [f'the model instruments, doi:{cur["instruments"]["doi"]}', f'the methodology, doi:{cur["guide"]["doi"]}']),
                    ('materials/index.html', [f'the instruments, doi:{cur["instruments"]["conceptdoi"]}', f'the methodology, doi:{cur["guide"]["conceptdoi"]}'])):
    for need in needs:
        if need not in texts.get(rel_, ''): bad(f'{rel_}: a DOI is not beside its own record: "{need}"')
# On Materials each record is followed by its own license, as Zenodo has it, and its gloss: a license can stand beside the wrong
# record while both appear on the page (the build check of candidate 4, C4-07). The current release's own DOIs appear only on the
# home page and its release page, each beside its record; Materials gives the DOIs that lead to the newest release.
newest = max(zlists, key=lambda r: [int(x) for x in re.findall(r'\d+', r)])
cur_data = json_of((ROOT / 'src' / 'releases' / f'{newest}.json'))
for r in cur_data['records']:
    head_, lic_ = r['label'].split(':')[0], cur[r['key']]['license']
    m_ = re.search(rf'{re.escape(head_)} holds [^()]*\(([^()]*)\)', materials)
    if not m_ or m_.group(1) != f'{lic_}, {GLOSS[lic_]}': bad(f'materials: "{head_} holds" is not followed by its own license, "{lic_}, {GLOSS[lic_]}"')
for q in pages:
    rel_ = q.relative_to(PUB).as_posix()
    if rel_ in ('index.html', f'materials/{newest}/index.html'): continue
    for key_, rec_ in cur.items():
        if rec_['doi'] in q.read_text(encoding='utf-8'): bad(f'{rel_}: the current release\'s own DOI for {key_} ({rec_["doi"]}) belongs on the home page and the release page only')
# Each release's page names its own release in its heading, its trail and its opening line, gives its own date, and links only its
# own files; the home page's and Materials' buttons lead to the newest release, in those words (C4-12).
MONTHS_ = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
def words_in(s): return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', s))).strip()
for rel_id, z in zlists.items():
    rp_ = PUB / 'materials' / rel_id / 'index.html'
    if not rp_.is_file(): bad(f'materials/{rel_id}: the release has no page'); continue
    h_ = re.sub(r'<!--.*?-->', '', rp_.read_text(encoding='utf-8'), flags=re.S)
    h1_, trail_, lead_ = (re.search(x, h_, flags=re.S) for x in (r'<h1\b[^>]*>(.*?)</h1>', r'<p class="crumbs">(.*?)</p>', r'<p class="lead">(.*?)</p>'))
    days_ = {r['published'] for r in z['records'].values()}
    day_ = (lambda y, m, d: f'{int(d)} {MONTHS_[int(m) - 1]} {y}')(*days_.pop().split('-')) if len(days_) == 1 else None
    if not h1_ or words_in(h1_.group(1)) != f'Release {rel_id}': bad(f'materials/{rel_id}: its heading does not read "Release {rel_id}"')
    if not trail_ or not words_in(trail_.group(1)).endswith(f'/ Release {rel_id}'): bad(f'materials/{rel_id}: its trail does not end with "Release {rel_id}"')
    if not lead_ or not words_in(lead_.group(1)).startswith(f'Release {rel_id} of "{TITLE}", published on {day_}.'): bad(f'materials/{rel_id}: its opening line does not name its own release and date')
    for href_ in re.findall(r'href="([^"]*files/[^"]*)"', h_):
        if f'files/{rel_id}/' not in href_: bad(f'materials/{rel_id}: a link to another release\'s files: {href_}')
for rel_, prefix_ in (('index.html', 'materials/'), ('materials/index.html', '')):
    h_ = (PUB / rel_).read_text(encoding='utf-8') if (PUB / rel_).is_file() else ''
    btns_ = re.findall(r'<a class="btn" href="' + re.escape(prefix_) + r'(\d{4}\.\d+)/(?:index\.html)?">([^<]*)</a>', h_)
    if not btns_ or any(x != newest or w != f'Open Release {newest}' for x, w in btns_): bad(f'{rel_}: its button does not lead to Release {newest}, the newest by number, with the words "Open Release {newest}"')
# Every page but the home page and the not-found page is linked from another page.
linked_pages = set()
for q in pages:
    if q.relative_to(PUB).as_posix() == '404.html': continue   # a link from the not-found page alone does not count; nor does one inside a comment
    for href in re.findall(r'<a [^>]*href="([^"#:]+)(?:#[^"]*)?"', re.sub(r'<!--.*?-->', '', q.read_text(encoding='utf-8'), flags=re.S)):
        target = pathlib.Path(os.path.normpath((PUB / href.lstrip('/')) if href.startswith('/') else (q.parent / href)))
        if target.is_dir(): target = target / 'index.html'
        if target != q and target.suffix == '.html' and (PUB in target.parents): linked_pages.add(target.relative_to(PUB).as_posix())
for q in pages:
    rel_ = q.relative_to(PUB).as_posix()
    if rel_ not in ('index.html', '404.html') and rel_ not in linked_pages: bad(f'{rel_}: no other page links to it')

# The repository's own documents, README.md, RUNBOOK.md and NOTICE.md (the frame for the repository's files, approved 13 November
# 2026; run 9, the build check, Should fix 6): the byline as the third line, the known gaps and a dated last line; the line on
# AI tools wherever a document names AI tools (Political Neutrality Policy, section 3.19); no address but the contact address,
# no telephone number, nothing hidden from readers and no key in a form services give; the site's word list; tables whose
# rows agree; and the frame's word budgets. LICENSE is Creative Commons' CC0 1.0 legal code, held by its checksum.
DOC_BUDGET = {'README.md': (450, 600), 'RUNBOOK.md': (2200, 2200), 'NOTICE.md': (300, 300)}   # (own words, all words)
LICENSE_SHA = 'a2010f343487d3f7618affe54f789f5487602331c0a8d03f49e9a7c547cf0499'
def doc_words(t):
    t = re.sub(r'`[^`]*`', ' x ', t); t = re.sub(r'https?://\S+', ' x ', t); t = re.sub(r'[|#*>\-]+', ' ', t)   # a file name, a command or a link counts as one word
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'.,:;()/@?!\"]*", t))
MONTHS_ = '(January|February|March|April|May|June|July|August|September|October|November|December)'
# Only rules that test exact forms are kept here (decision sheet 10, A, 13 November 2026). Whether a sentence gives away a
# secret, a private place or name, or a protection that is missing is for the privacy sweep, a full read of every public file
# before each publication (RUNBOOK.md, section 3).
# A key in the form a service gives it: a GitHub token, a Google API key, a Porkbun key (pk1_ and sk1_: Porkbun's "Getting
# Started with the Porkbun API", read 13 November 2026), or a private key's usual first line, PEM, OpenPGP, PuTTY or SSH2 (runs 13 and 14).
TOKEN_ = (r'\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,}|AIza[0-9A-Za-z_-]{35}|[ps]k1_[A-Za-z0-9]{16,})'
          r'|-----BEGIN [A-Z0-9 ]*PRIVATE KEY[A-Z ]*-----|PuTTY-User-Key-File-\d+:|---- BEGIN SSH2 [A-Z ]*PRIVATE KEY ----')
def code_like(t):
    """A code in a form services give: an authenticator's setup key, whole (16 or more of A to Z, or of a to z with a digit
    from 2 to 7) or in groups of four with a digit (runs 12 and 13); a code of three or more groups of 4 to 6 letters and
    digits, mixed, joined by hyphens (runs 10 and 13), or of two groups of five of 0 to 9 and a to f, with both, so that a
    word such as IPv6-only is not one (run 14, C5); or a run of 12 or more letters, digits and the marks ! # $ % ^ & * + = ~,
    with small and capital letters and a digit, so that a password broken by any other mark, such as @ or a dot, is not one
    (run 15, Must fix 3)."""
    return bool(re.search(r'\b[A-Z2-7]{16,}\b', t) or re.search(r'\b(?=[a-z2-7]*[2-7])[a-z2-7]{16,}\b', t)
                or re.search(r'\b(?=[A-Z2-7 ]*[2-7])[A-Z2-7]{4}(?: [A-Z2-7]{4}){3,}\b', t)
                or re.search(r'\b(?=[a-z2-7 ]*[2-7])[a-z2-7]{4}(?: [a-z2-7]{4}){3,}\b', t)
                or re.search(r'\b(?=[0-9a-f-]*[a-f])(?=[0-9a-f-]*\d)[0-9a-f]{5}-[0-9a-f]{5}\b', t)
                or re.search(r'\b(?=[A-Za-z0-9-]*[A-Za-z])(?=[A-Za-z0-9-]*\d)[A-Za-z0-9]{4,6}(?:-[A-Za-z0-9]{4,6}){2,}\b', t)
                or any(re.search(r'[a-z]', w_) and re.search(r'[A-Z]', w_) and re.search(r'\d', w_) for w_ in re.findall(r'[A-Za-z0-9!#$%^&*+=~]{12,}', t)))
def hidden(t):
    """Two forms in which a document can hide words from the readers of its page (runs 12 to 15): HTML, and a link or footnote
    definition, a line that begins, after any marks of a quotation or a list, with a label in brackets and a colon. The check
    reads all of a document for them, code included: telling code from text as GitHub does is where its rules failed in runs
    12 to 14. For HTML it takes any "<" before "!" or "?", which at a line's start can open a comment, a declaration or a
    processing instruction even where an autolink seems to begin (run 15, Must fix 1), and any "<" before a letter or "/"
    outside an autolink, such as <https://example.org>. So these documents use no HTML, no "<" before a letter, even in code,
    and no footnotes. Other forms, such as a link's title, are for the read before each publication (RUNBOOK.md, section 3)."""
    if re.search(r'<[!?]', t): return 'a "<" before "!" or "?" (code included), which can open a comment that hides words'
    t = re.sub(r'<[A-Za-z][A-Za-z0-9+.-]{1,31}:[^\s<>]*>|<[A-Za-z0-9.!#$%&\'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?'
               r'(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*>', ' ', t)   # autolinks
    if re.search(r'<[A-Za-z/]', t): return 'a "<" before a letter or "/" (code included), which the check reads as HTML; these documents use none'
    if re.search(r'(?m)^(?:[ \t]*>|[ \t]*(?:[-*+]|\d{1,9}[.)])(?=[ \t]))*[ \t]*\[(?:[^\]\\]|\\.)+\]:', t):
        return 'a link or footnote definition, which GitHub can hide; these documents use none'
    return ''
for name_, (own_max, all_max) in DOC_BUDGET.items():
    p_ = ROOT / name_
    if not p_.is_file(): bad(f'{name_}: missing'); continue
    t_ = p_.read_text(encoding='utf-8'); lines_ = t_.splitlines()
    if len(lines_) < 3 or lines_[2] != BYLINE or t_.count(BYLINE) != 1: bad(f'{name_}: the byline is not its third line, once, word for word')
    if t_.count('Known gaps: ' + GAPS) != 1: bad(f'{name_}: the known gaps are not there once, word for word')
    if not re.search(r'\nUpdated \d{1,2} ' + MONTHS_ + r' \d{4}\.\s*$', t_): bad(f'{name_}: its last line is not "Updated" and a date')
    if hidden(t_): bad(f'{name_}: {hidden(t_)}')
    if (name_ != 'NOTICE.md' or re.search(AI_NAMED, t_, flags=re.I)) and t_.count(AI_SITE) != 1:
        bad(f'{name_}: the line on AI tools is not there once, word for word (Political Neutrality Policy, section 3.19)')
    if other_addresses(html.unescape(t_)): bad(f'{name_}: an email address other than contact@inkindstandard.org')   # &#64; shows as @ (run 14, P2)
    if re.search(r'\(\d{3}\)\s?\d{3}[-.\s]\d{4}|\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b', t_): bad(f'{name_}: something that looks like a telephone number')   # the pages' rule
    if re.search(TOKEN_, t_) or code_like(t_): bad(f'{name_}: something in the form of a password, a code or a key')
    code_free_ = re.sub(r'`[^`]*`', ' ', t_)   # a command such as cp is not a word of the text
    for pat_ in AVOID:   # read without case; the dash counts inside a code span too (run 11, Should fix 3)
        for m_ in re.finditer(pat_, t_ if pat_ == '\u2014' else code_free_, flags=re.I): bad(f'{name_}: "{m_.group(0)}" is on the site\'s word list')
    if '\u2013' in t_: bad(f'{name_}: an en dash')
    for i_ in range(1, len(lines_)):
        if lines_[i_].startswith('|') and lines_[i_ - 1].startswith('|') and lines_[i_].count('|') != lines_[i_ - 1].count('|'): bad(f'{name_}: line {i_ + 1}, a table row with another number of cells than the row before')
    all_ = doc_words(t_); own_ = all_ - (doc_words(ABOUT) if ABOUT in t_ else 0)
    if own_ > own_max or all_ > all_max: bad(f'{name_}: {own_} words of its own and {all_} in all; the budget is {own_max} and {all_max}')
# Every file of the repository that the check can read as text, code included, but the hosted release files, which their
# checksums hold (decision sheet 10, A; runs 12 and 13): no email address but the contact address, and no key in a form a
# service gives. A file with no mark of UTF-16 or UTF-32 that holds a zero byte is taken for a font, an icon or another file
# that is not text. The check reads .gitignore for one thing only: that it keeps the released folders' READMEs, notes to this
# project, out of the repository (RUNBOOK.md, section 5), in the one form readme_kept_out() knows. It then leaves those READMEs
# unread, and reads every other file, whatever .gitignore says: telling what Git leaves out is where its rules failed in runs 14
# to 16.
def readme_kept_out():
    """Why Git might add a released folder's README.md, or '' when it cannot (run 16). The top .gitignore must hold the line
    src/released/**/README.md, or /src/released/**/README.md, as Git reads lines: each ends at a line feed, and a carriage
    return just before it and the spaces after the line are dropped. No carriage return may stand anywhere else, since Git then
    reads the lines on either side as one (run 16, P1); no line may begin with !, which can take a README back in, whatever its
    capitals (run 14, P6; run 16, P2); and no .gitignore may stand below the top folder, since Git reads that too (run 15, P3)."""
    g_ = ROOT / '.gitignore'
    lines_ = [l_[:-1] if l_.endswith(b'\r') else l_ for l_ in (g_.read_bytes() if g_.is_file() else b'').split(b'\n')]
    if any(b'\r' in l_ for l_ in lines_): return 'a carriage return that does not end a line, so Git reads two lines as one'
    lines_ = [l_.rstrip(b' ') for l_ in lines_]
    if any(l_.startswith(b'!') for l_ in lines_): return 'a line that begins with !, which can take a README back in'
    if not {b'src/released/**/README.md', b'/src/released/**/README.md'} & set(lines_): return 'no line src/released/**/README.md'
    below_ = [h_.relative_to(ROOT).as_posix() for h_ in sorted(ROOT.rglob('.gitignore')) if h_ != g_ and '.git' not in h_.relative_to(ROOT).parts]
    return f'{below_[0]}, a .gitignore below the top folder, which Git reads too' if below_ else ''
WHY_ = readme_kept_out()
if WHY_: bad(f'.gitignore: does not keep the released folders\' READMEs out of the repository in the one form the check knows (RUNBOOK.md, section 5): {WHY_}')
for f_ in sorted(ROOT.rglob('*')):
    rel_ = f_.relative_to(ROOT).as_posix()
    if not f_.is_file() or rel_.startswith(('docs/files/', '.git/')): continue
    if not WHY_ and rel_.startswith('src/released/') and f_.name == 'README.md': continue
    b_ = f_.read_bytes()
    if b_.startswith((b'\xff\xfe\x00\x00', b'\x00\x00\xfe\xff')): t_ = b_.decode('utf-32', errors='replace')
    elif b_.startswith((b'\xff\xfe', b'\xfe\xff')): t_ = b_.decode('utf-16', errors='replace')
    elif b'\x00' in b_: continue
    else: t_ = b_.decode('utf-8', errors='replace')
    if other_addresses(html.unescape(t_)): bad(f'{rel_}: an email address other than contact@inkindstandard.org; the repository is public')
    if re.search(TOKEN_, t_): bad(f'{rel_}: a key in a form a service gives; the repository is public')
if (ROOT / 'README.md').is_file():
    readme_ = (ROOT / 'README.md').read_text(encoding='utf-8')
    if 'contact@inkindstandard.org' not in readme_: bad('README.md: does not give contact@inkindstandard.org for reports')
    if f'"{ABOUT}"' not in readme_: bad('README.md: the project\'s own words on what it is are not quoted word for word')
if not (ROOT / 'LICENSE').is_file() or hashlib.sha256((ROOT / 'LICENSE').read_bytes()).hexdigest() != LICENSE_SHA:
    bad('LICENSE: missing, or not Creative Commons\' CC0 1.0 legal code byte for byte')
print('pages', len(pages), '· own words (all words)', ', '.join(f'{k.rsplit("/index.html", 1)[0] or k} {v} ({every[k]})' for k, v in counts.items()),
      f'· hosted files {hosted} · lowest text contrast {lowest[7.0]:.2f}, lowest mark contrast {lowest[3.0]:.2f}')
if problems:
    print('PROBLEMS:'); [print(' -', x) for x in problems]; sys.exit(1)
print('PASS')
