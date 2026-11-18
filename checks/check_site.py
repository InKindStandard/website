#!/usr/bin/env python3
"""Checks the built site in docs/ (or the folder given). Fails loudly; prints a short result.
Standard library only; Python 3.10 or later.   python3 checks/check_site.py [folder]

What it cannot see: how a browser lays a page out (checks/look_check.py does part of that), whether the
HTML validates, and whether a link to another site still answers. "Zenodo's checksums" means the list
saved in src/releases/ on the date it names; this script never asks Zenodo."""
import hashlib, html, json, os, pathlib, re, shutil, subprocess, sys, tempfile, urllib.parse
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
LICENSE_HTML = ('<p class="lic">Except where otherwise noted, this page is licensed under CC BY 4.0 (<a href="https://creativecommons.org/licenses/by/4.0/">'
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
# Home's opening quotes How In-Kind Standard Works v0.5, section 1, which speaks of large projects, such as data centers, in place of ABOUT, which speaks of data
# centers only and stays the README's (decision sheet 17, T1 A, 18 November 2026): its first paragraph, and the first sentence of its second before NOT_A.
WORKS_WHAT = ('In-Kind Standard is a nonpartisan, educational project that gives communities and their local governments free model doc'
              'uments, plain explanations and public records about large projects, such as data centers, so that they can decide knowing the facts: what they could gain, and what it would cost them.')
WORKS_WHO = 'It is citizen-prepared and planned to become a charitable nonprofit.'
# The logistics series' title, as its package gives it (approved by the founder on 18 November 2026, not yet published): Home lists it as in preparation, with
# no date and no DOI (decision sheet 17, T2 A). It is quoted, so it is held here; on publication day it becomes a release like 2026.4 (RUNBOOK.md, section 4).
LOGISTICS_TITLE = 'Model Instruments for Logistics Facility Development in Florida Counties and Cities'
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
        '<meta name="color-scheme" content="light dark">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'self\'; style-src \'self\'; img-src \'self\'; font-src \'self\'; base-uri \'none\'; form-action \'none\'">',
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
ROOM = 1.05   # decision sheet 16, S2, option A (approved by the founder on 18 November 2026, 08:46): a page may be 5 percent over its budget, where decision sheet 2 allowed 20
# The numbers in force are also held here, so that a page cannot raise its own: its heading block must give exactly these. The founder approved them on 18 November 2026, 08:46 (decision sheet 16, S2 A; Home's ceiling of 1,520 with S3 C).
# Every release page has the release page's budget. A new page has none until the founder approves its frame; add it then.
APPROVED = {'index.html': (415, 1540), 'materials/index.html': (320, 3090), 'contact/index.html': (170, 230),
            'privacy/index.html': (600, 610), 'accessibility/index.html': (390, 400), '404.html': (40, 60),
            'funding/index.html': (15, None)}   # frame v0.6, section 4 gave 320, 280, 140, 525, 330 and 40; the pages' own words are over those (run 19, S4), so these are the pages' measured words of 18 November 2026, rounded up to five, approved by the founder (decision sheet 16, S2 A); Home's are 415 and 1,540 since decision sheet 17 (18 November 2026), which added the logistics series' row and the broader opening: 430 own words, inside its room; the funding page's words are the nonprofit project's as released (decision sheet 6, A)
# The ceilings of Stage 1 are each page's measured words of 18 November 2026, rounded up to ten (decision sheet 5, A); the founder approved them with the pages (decision sheet 16, S2 A, 18 November 2026).
# Another project's released pages: each page's fragments, in order, and each fragment's SHA-256 as that project released it
# (the nonprofit project's folder Website_2026-11-14b, its README, and its log entries of 14 November 2026, 01:32 to 01:48 and 01:55 to
# 02:23: the funding statement v0.5, and the record of ties with its license line; it replaces Website_2026-11-12b, which stays as it was).
# The build places them unchanged; a new version comes in a new dated folder, and is added here when the founder approves the change.
RELEASED_PAGES = {'funding/index.html': ['nonprofit/Website_2026-11-14b/funding-statement.html', 'nonprofit/Website_2026-11-14b/founder-ties.html']}
RELEASED_SHA = {'nonprofit/Website_2026-11-14b/funding-statement.html': 'a70929c16defe8a35b3ac2bc7214a25bbf357523ef5aa1d3df7688657111bd5b',
                'nonprofit/Website_2026-11-14b/founder-ties.html': 'cc65225fbb6a7a4d74972237920c9abd85490b0746886ade0529bd174014626d'}
SCREEN = 'https://screen.inkindstandard.org/'
SITE = 'https://inkindstandard.org/'
def printed_address_(href_, rel_):
    """The address a link to another page of the site shows on paper: the link as written, made whole from the page's own address, with a folder's index.html left off."""
    own_ = '' if rel_ == 'index.html' else (rel_[:-len('index.html')] if rel_.endswith('/index.html') else rel_)
    full_ = urllib.parse.urljoin(SITE + own_, html.unescape(href_))
    return full_[:-len('index.html')] if full_.endswith('/index.html') else full_
# The three lists of links in every page's header, each with its label and in order (frame v0.6, section 4, "On every page": the readers' links above the menu;
# a page joins the menu only once it is live), and the footer's three columns (the same section; the funding page's link is in the footer, as the frame places it).
# Addresses are read from the site's root; the Screen is another site's page.
NAVS = [('For particular readers', [('contact/', 'Contact')]),
        ('Main, at phone width', [('materials/', 'Model documents'), (SCREEN, 'Public records'), ('contact/', 'Contact')]),
        ('Main', [('materials/', 'Model documents'), (SCREEN, 'Public records')])]
FOOT = [('The work', [('materials/', 'Model documents'), (SCREEN, 'Public records')]), ('The project', [('funding/', 'Who pays for the work')]),
        ('This site', [('contact/', 'Contact'), ('privacy/', 'Privacy statement'), ('accessibility/', 'Accessibility statement')])]
RELEASE_PAGE = 270   # every release page's budget (decision sheet 2, E4 A gave 220; the page's own words are 268 since run 19, N4, so 270, approved on decision sheet 16, S2 A, 18 November 2026)
# The logo's mark, the browser icon and the two full-colour files, held as approved (logo kit v2.3; decision sheet 15, X6 A, 17 November 2026). A new mark, icon or file
# also needs its checksum here, with the founder's approval (RUNBOOK.md, section 6). The mark is src/logo.inc after its note, as the build takes it.
MARK_SHA = '9aca9bd910f141b4b772a8c19b8f2d4f60f23b0d0e2af4a54036d8f42b0c9ae5'
ICON_SHA = '1a51afde2dd22cdaae7635cad12b209b731604b19380298c991f7c8e163bd4c2'
LOGO_FILES = {'assets/logo.svg': 'd03e7569fc6bec5d417e7656e7f73d6a545bc5f470b89627ebd93ff55100e2f0',            # the mark on navy
              'assets/logo-on-cream.svg': '7a72a46a3731179dacf75dcf6b1d932698aabf879e7e2bad7979d874c869dec7'}   # and on cream: the only image files on the site
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
ASSETS = {'site.css', 'site.js', 'favicon.ico', 'logo.svg', 'logo-on-cream.svg', 'fonts/AtkinsonHyperlegible-Regular.woff', 'fonts/AtkinsonHyperlegible-Bold.woff',
          'fonts/AtkinsonHyperlegible-Italic.woff', 'fonts/AtkinsonHyperlegible-BoldItalic.woff', 'fonts/AtkinsonHyperlegibleMono-wght.woff',
          'fonts/OFL-AtkinsonHyperlegible.txt', 'fonts/OFL-AtkinsonHyperlegibleMono.txt'}

class Page(HTMLParser):
    """Collects tags, text and links. Text inside an element of class "theirs" (another project's words) or
    "fixed" (the standard known-gaps notice) is not counted against a page's word budget."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.tags, self.own_text, self.all_text, self.main_text, self.unbalanced, self.links = [], [], [], [], [], [], []
        self.their_text = []; self.units = []; self.unit = None   # units: another project's words, one for each run of text between block tags
        self.in_main = 0; self.skip = 0; self.link = None
        # Run 8, the build check: where each tag sits (the open tags around it, with their classes), each start tag as written,
        # and the menu's links and loose words, so that the rules read the parsed page and not one way of writing it.
        self.ancestors, self.raw, self.classes_open, self.navs, self.cur_nav, self.link_aria = [], [], [], [], None, None
    def flush_(self):
        s_ = re.sub(r'\s+', ' ', ''.join(self.unit or [])).strip()
        if s_: self.units.append(s_)
        self.unit = [] if self.skip else None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs); self.tags.append((tag, a)); self.ancestors.append(tuple(self.classes_open)); self.raw.append(self.get_starttag_text() or '')
        if tag == 'main': self.in_main += 1
        if self.skip and tag in UNIT_BREAKS: self.flush_()
        if self.skip and tag == 'span' and self.stack and self.stack[-1][0] == 'li': self.flush_()   # a document's name and its version stand in two spans of one list item
        if tag in BLOCKS and any(x == 'p' for x, _ in self.stack): self.unbalanced.append(f'<{tag}> inside a paragraph')
        if tag in VOID: return
        t = bool({'theirs', 'fixed'} & set((a.get('class') or '').split()))
        if t and not self.skip and self.in_main: self.unit = []   # the outermost element of another project's words begins
        self.stack.append((tag, t)); self.skip += t; self.classes_open.append((tag, frozenset((a.get('class') or '').split())))
        if tag == 'nav': self.cur_nav = {'label': a.get('aria-label'), 'links': [], 'loose': []}; self.navs.append(self.cur_nav)
        if tag == 'a': self.link = [a.get('href') or '', a.get('class') or '', '']; self.link_aria = a.get('aria-current')
    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, dict(attrs))); self.ancestors.append(tuple(self.classes_open)); self.raw.append(self.get_starttag_text() or '')
        if tag in BLOCKS and any(x == 'p' for x, _ in self.stack): self.unbalanced.append(f'<{tag}> inside a paragraph')
        if self.skip and tag == 'br': self.flush_()
    def handle_endtag(self, tag):
        if tag == 'main': self.in_main -= 1
        if tag == 'a' and self.link:
            self.links.append(tuple(self.link))
            if self.cur_nav is not None: self.cur_nav['links'].append((self.link[0], self.link[2], self.link[1], self.link_aria))
            self.link = None
        if tag == 'nav': self.cur_nav = None
        if self.skip and tag in UNIT_BREAKS: self.flush_()
        if self.skip and tag == 'span' and len(self.stack) > 1 and self.stack[-2][0] == 'li': self.flush_()
        if not self.stack or self.stack[-1][0] != tag: self.unbalanced.append(tag)
        else: self.skip -= self.stack.pop()[1]; self.classes_open.pop()
        if not self.skip and self.unit is not None: self.flush_()   # the outermost element of another project's words closed
    def handle_data(self, data):
        self.all_text.append(data)
        if self.link: self.link[2] += data
        elif self.cur_nav is not None: self.cur_nav['loose'].append(data)
        if self.in_main: self.main_text.append(data)
        if self.in_main and not self.skip: self.own_text.append(data)
        if self.in_main and self.skip:
            self.their_text.append(data)
            if self.unit is not None: self.unit.append(data)

UNIT_BREAKS = BLOCKS | {'td', 'th', 'tr', 'thead', 'tbody', 'br', 'li', 'dd', 'dt', 'summary', 'text', 'g'}   # where one run of another project's words ends and the next begins
BLOCK_TAGS_ = r'(?:address|article|aside|blockquote|br|dd|details|div|dl|dt|figcaption|figure|footer|h[1-6]|header|hr|li|main|nav|ol|p|pre|section|summary|table|tbody|td|tfoot|th|thead|tr|ul)'
def block_text(h):
    """A page's words with a space at every block tag and none at an inline one, so that a phrase can be tested across table cells and definition lists."""
    h = re.sub(r'<(script|style|svg)\b.*?</\1>', ' ', h, flags=re.S)
    h = re.sub(rf'</?{BLOCK_TAGS_}\b[^>]*>', ' ', h)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', h))).strip()
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
        s_ = pathlib.Path(tmp_) / 'site'; (s_ / 'docs').mkdir(parents=True)
        shutil.copytree(ROOT / 'docs' / 'files', s_ / 'docs' / 'files')   # the build reads the hosted Plain Language Guide (the eight steps on Materials), so a clean copy needs the hosted files
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
def zenodo_list_ok_(z_):   # the keys this check reads from a saved list (run 20, Note 2: a list without "release" stopped the check with a bare KeyError)
    return (isinstance(z_, dict) and 'release' in z_ and isinstance(z_.get('records'), dict) and bool(z_['records'])
            and all(isinstance(r_, dict) and {'doi', 'conceptdoi', 'files', 'total'} <= set(r_) and isinstance(r_['files'], list)
                    and all(isinstance(f_, dict) and {'name', 'size'} <= set(f_) for f_ in r_['files']) for r_ in z_['records'].values()))
for f_ in sorted((ROOT / 'src' / 'releases').glob('*.zenodo.json')):
    if not zenodo_list_ok_(json_of(f_)):
        stop_now(f'src/releases/{f_.name}: the saved list lacks "release" or "records", or a record in it lacks "doi", "conceptdoi", "total" or "files" with names and sizes; save Zenodo\'s list of the release\'s files there again (RUNBOOK.md, section 4)')
zlists = {z['release']: z for z in (json_of(f) for f in sorted((ROOT / 'src' / 'releases').glob('*.zenodo.json')))}
for f_ in sorted((ROOT / 'src' / 'releases').glob('*.json')):   # each release's data has the saved Zenodo list it is made from; without it the release pages cannot be checked
    if f_.name != 'earlier.json' and not f_.name.endswith('.zenodo.json') and not f_.with_name(f_.name[:-len('.json')] + '.zenodo.json').is_file():
        stop_now(f'src/releases/{f_.name[:-len(".json")]}.zenodo.json: missing; save Zenodo\'s list of the release\'s files there (RUNBOOK.md, section 4)')
if not zlists: stop_now('src/releases: no saved Zenodo list (*.zenodo.json), so the site has no release to show (RUNBOOK.md, section 4)')
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
shared, counts, every, names, texts, theirs, texts_own, units_ = {}, {}, {}, {}, {}, {}, {}, {}
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
    for one in ('h1', 'title', 'main', 'header', 'footer'):
        if tagnames.count(one) != 1: bad(f'{rel}: {tagnames.count(one)} <{one}>')
    if tagnames.count('nav') != 3: bad(f'{rel}: {tagnames.count("nav")} <nav>; the header has three lists of links')
    # No form, frame, inline style or button in the files: the script adds the buttons, and nothing a visitor types goes anywhere.
    for banned in ('form', 'iframe', 'style', 'object', 'embed', 'video', 'audio', 'input', 'button', 'base'):
        if banned in tagnames: bad(f'{rel}: <{banned}> present')   # in another project's released pages too, since their version of 15:57 (point 33)
    # The site's one script (frame v0.6, section 7): a file of the site's own, named in the head, with nothing written inside it, and no other script.
    scripts_ = [a for tag, a in pg.tags if tag == 'script']
    css_href_ = next((a.get('href') for tag, a in pg.tags if tag == 'link' and a.get('rel') == 'stylesheet'), None)
    if len(scripts_) != 1 or scripts_[0] != {'src': (css_href_ or '').replace('site.css', 'site.js')} or re.search(r'<script\b[^>]*>\s*(?!</script>)\S', t) or t.find('<script') > t.find('</head>'):
        bad(f'{rel}: the page must carry the site\'s one script, <script src="...assets/site.js"> in the head with nothing inside it, and no other')
    # Tables: only the ledger, with a header row naming its columns, inside a box that scrolls on its own, so that a wide table never widens the page.
    for (tag, a), anc in zip(pg.tags, pg.ancestors):
        if tag == 'table' and (a.get('class') != 'ledger' or not any('scroll' in k_ for x_, k_ in anc if x_ == 'div')): bad(f'{rel}: a table that is not <table class="ledger"> inside <div class="scroll">')
        if tag == 'th' and a.get('scope') != 'col': bad(f'{rel}: a header cell without scope="col"')
    if tagnames.count('thead') != tagnames.count('table'): bad(f'{rel}: a table without a header row')
    # A heading holds words: a reader's tab and a link to a heading take their names from it (run 20, P11: the Reporters tab with no name).
    for m_ in re.finditer(r'<h([1-6])\b[^>]*>(.*?)</h\1>', t, flags=re.S):
        if not re.sub(r'\s+', '', html.unescape(re.sub(r'<svg\b.*?</svg>|<[^>]+>', '', m_.group(2), flags=re.S))): bad(f'{rel}: a heading with no words: an <h{m_.group(1)}> that holds {"an icon" if "<svg" in m_.group(2) else "nothing"} and no text')
    # An icon box holds its drawing and no words (its color is measured as a mark, not as text), and a numeral that is hidden from a screen reader has its twin.
    if len(re.findall(r'<span class="ico">', t)) != len(re.findall(r'<span class="ico"><svg\b[^>]*>(?:(?!</svg>).)*</svg></span>', t, flags=re.S)): bad(f'{rel}: an icon box that holds more than its drawing')
    twins_ = re.findall(r'<span class="fig" data-count="(\d+)"><span class="fig-n" aria-hidden="true">\1</span><span class="vh">\1</span></span>', t)
    if t.count('class="fig-n" aria-hidden="true"') != len(twins_): bad(f'{rel}: a counted figure whose hidden numeral is not followed by the same numeral for a screen reader')
    # Words the check reads but a reader is not shown (run 7, S1): the classes and attributes that hide words, only where the build
    # puts them: "vh" on a file's document name inside its link on a release page, "print-only" on the footer's lines for paper,
    # "skip" on the skip link, aria-hidden on the logo's drawing; never <template>, <noscript> or inert.
    for banned in ('template', 'noscript'):
        if banned in tagnames: bad(f'{rel}: <{banned}> present: words the check reads but a reader is not shown')
    for tag, a in pg.tags:
        cls_ = set((a.get('class') or '').split())
        if 'inert' in a: bad(f'{rel}: the inert attribute on <{tag}>: words a reader cannot reach')
        if 'aria-hidden' in a and not (tag == 'svg' or (tag == 'span' and cls_ == {'fig-n'})): bad(f'{rel}: aria-hidden on <{tag}>: words a screen reader is not given')
        if 'skip' in cls_ and not (tag == 'a' and a.get('href') == '#main' and cls_ == {'skip'}): bad(f'{rel}: the class "skip" on <{tag} class="{a.get("class")}">; it belongs to the skip link only')
        if 'print-only' in cls_ and not (tag == 'p' and cls_ == {'print-only'}): bad(f'{rel}: the class "print-only" on <{tag} class="{a.get("class")}">; it belongs to the footer\'s lines for paper only')
        if 'vh' in cls_ and not (tag == 'span' and cls_ == {'vh'}): bad(f'{rel}: the class "vh" on <{tag} class="{a.get("class")}">; it belongs to a span that holds words for a screen reader only')
    footer_ = re.search(r'<footer\b.*?</footer>', t, flags=re.S)
    if t.count('class="print-only"') != (footer_.group(0).count('class="print-only"') if footer_ else -1) or t.count('class="print-only"') > 2: bad(f'{rel}: words for paper only outside the footer, or more than its two lines')
    if t.count('class="skip"') != 1: bad(f'{rel}: the skip link is not there once')
    # Words kept for a screen reader (class "vh") stand in three places only: the home link's last word, a counted figure's twin, and a file's document name inside its link on a release page.
    vh_ok_ = (len(re.findall(r'<a href="[^"]*"(?: data-url="[^"]*")?>[^<]*<span class="vh">: [^<]+</span></a>', t)) if release_page(rel) else 0) \
        + len(re.findall(r'</span></span> <span class="vh"> home page</span></a>|</span></span><span class="vh"> home page</span></a>', t)) + len(twins_)
    if len(re.findall(r'<span class="vh">', t)) != vh_ok_: bad(f'{rel}: words hidden from the eye that are not the home link\'s "home page", a counted figure\'s twin or a file\'s document name inside its link')
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
    if any(not (any(x == 'a' for x, _ in anc) or any('fig' in k_ for x, k_ in anc if x == 'span')) for anc in marks_['vh']): bad(f'{rel}: words hidden from the eye outside a link or a counted figure (read from the parsed page)')
    # Run 19, M3: a disclosure in a page's main text is written open, with data-fold, which the script closes for the screen; so a reader without the script, and paper, have every word.
    shut_ = sum(1 for (tag, a), anc in zip(pg.tags, pg.ancestors) if tag == 'details' and any(x == 'main' for x, _ in anc) and not ('open' in a and 'data-fold' in a))
    if shut_: bad(f'{rel}: {shut_} disclosures in the main text are written closed, or without data-fold; the page writes each one open and the script closes it for the screen, so that paper and a reader without scripts have every word (run 19, M3)')
    # Run 8, Should fix 2: on a page of another project's released pages, words marked as another project's are those pages
    # alone, inside their one <div class="theirs released">; no other page has such a block.
    rb_ = frozenset({'theirs', 'released'}); n_rb_ = sum(1 for _, a in pg.tags if frozenset((a.get('class') or '').split()) == rb_)
    if n_rb_ != (1 if rel in RELEASED_PAGES else 0): bad(f'{rel}: {n_rb_} blocks of another project\'s released pages; {1 if rel in RELEASED_PAGES else 0} expected')
    if rel in RELEASED_PAGES:
        for (tag, a), anc in zip(pg.tags, pg.ancestors):
            c_ = frozenset((a.get('class') or '').split())
            if c_ & {'theirs', 'fixed'} and c_ != rb_ and rb_ not in {k_ for _, k_ in anc}: bad(f'{rel}: words marked as another project\'s outside the released pages it shows, on <{tag}> (run 8, Should fix 2)')
    # Run 8, Should fix 3: the three lists of links read from the parsed page, with their labels and in order, no loose words in them, and the page's own link marked as the build marks it.
    def norm_(h_): return h_ if re.match(r'[a-z]+:', h_) else re.sub(r'index\.html$', '', re.sub(r'^(?:\./|/)', '', h_.replace('../', '')))
    navs_ = [(n_['label'], [(norm_(h_), w_.strip()) for h_, w_, _, _ in n_['links']]) for n_ in pg.navs]
    if navs_ != NAVS: bad(f'{rel}: the header\'s lists of links, read from the parsed page, are {navs_}; the frame sets {NAVS} (run 8, Should fix 3)')
    here_ = '' if rel == 'index.html' else (rel[:-len('index.html')] if rel.endswith('/index.html') else rel)
    for n_ in pg.navs:
        if ''.join(n_['loose']).strip(): bad(f'{rel}: words in the menu that are not a link: "{"".join(n_["loose"]).strip()[:40]}"')
        for h_, w_, c_, cur_ in n_['links']:
            tgt_ = norm_(h_); want_ = 'page' if tgt_ == here_ else ('true' if tgt_ and not re.match(r'[a-z]+:', tgt_) and here_.startswith(tgt_) else None)
            if (cur_, c_) != (want_, 'on' if want_ else ''): bad(f'{rel}: the link "{w_.strip()}" is marked class "{c_}" and aria-current {cur_}; the page\'s own link carries class "on" and aria-current "page", the section it sits in "true", and no other link either')
    levels = [int(x[1]) for x in tagnames if re.fullmatch(r'h[1-6]', x)]
    if any(b - a > 1 for a, b in zip(levels, levels[1:])): bad(f'{rel}: a heading level is skipped')
    ids = [a['id'] for _, a in pg.tags if a.get('id')]
    if len(ids) != len(set(ids)): bad(f'{rel}: an id is used twice')
    # Paper (frame v0.6, section 8): a link to another page of the site, in the page's own words, prints with the address a reader of the paper can use; the style sheet prints data-url
    # for it and href for an absolute link. So each such link carries data-url, equal to its address on the site, and no other link carries one. Another project's released text is held
    # as it was released, and prints no addresses.
    for i_, (tag_, a_) in enumerate(pg.tags):
        if tag_ != 'a': continue
        href_ = a_.get('href') or ''; open_ = pg.ancestors[i_]
        relative_ = bool(href_) and not href_.startswith('#') and not re.match(r'[a-z][a-z0-9+.-]*:|//', href_)
        want_ = printed_address_(href_, rel) if (relative_ and any(x_ == 'main' for x_, _ in open_) and not any('released' in c_ for _, c_ in open_)) else None
        if a_.get('data-url') != want_: bad(f'{rel}: the link {href_!r} carries data-url {a_.get("data-url")!r}; on paper it must show {want_!r}' if want_ else f'{rel}: the link {href_!r} carries data-url {a_.get("data-url")!r}, which only a link to another page of the site, in the page\'s own words, carries')
    for tag, a in pg.tags:
        if 'style' in a or any(k.startswith('on') for k in a): bad(f'{rel}: inline style or script on <{tag}>')
        if 'srcset' in a or 'ping' in a or (a.get('http-equiv') or '').lower() == 'refresh': bad(f'{rel}: srcset, ping or refresh on <{tag}>')
        if 'hidden' in a: bad(f'{rel}: the hidden attribute on <{tag}>: words the check reads but a reader does not see (N7)')
        for k, v in a.items():
            if v and re.search(r'[a-z][a-z0-9+.-]*://|^//', v) and not (tag == 'a' and k in ('href', 'data-url')): bad(f'{rel}: an address in {k} of <{tag}>: {v[:60]}')
        if tag == 'svg' and a.get('aria-hidden') != 'true': bad(f'{rel}: a drawing that is neither labelled nor hidden')
        if tag == 'img':
            if a.get('alt') != '' or a.get('class') not in ('only-light', 'only-dark') or a.get('loading') != 'lazy': bad(f'{rel}: an image other than the two logos in the home page\'s "Who prepares this work", which carry no alt text (the words beside them say all they say) and load when near')
            if not (a.get('width') and a.get('height')): bad(f'{rel}: image without a size')
        # 2. Nothing loads from another host; every link resolves, to a page, a hosted file or a place in a page.
        for attr in ('src', 'href'):
            u = a.get(attr)
            if u is None: continue
            loads = tag in ('img', 'link', 'source', 'script')
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
        if cls == 'brand' and re.sub(r'\s+', ' ', words).strip() != 'In-Kind Standard Model documents and public records home page': bad(f'{rel}: the home link\'s name reads "{re.sub(chr(10), " ", words).strip()}"; it must read "In-Kind Standard Model documents and public records home page", with a space between its parts')
    if sum(1 for _, c_, _ in pg.links if c_ == 'brand') != 1: bad(f'{rel}: the home link is not there once')
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
    units_[rel] = pg.units
    # 5. The header and footer are the same on every page, the home page's and the not-found page's included (decision sheet 2,
    # E2 B). The not-found page's addresses start at the domain's root, and every other page's line "Printed from" names it.
    for part in ('header', 'footer'):
        m = re.search(rf'<{part}.*?</{part}>', t, flags=re.S)
        if not m: bad(f'{rel}: no <{part}>'); continue
        block = re.sub(r' aria-current="\w+"', '', m.group(0).replace('../', '')).replace(' class="on"', '').replace('href="./', 'href="').replace('href="/', 'href="')
        shared.setdefault(part, {})[rel] = re.sub(r'<p class="print-only">Printed from \S+</p>\n', '', block)
for part, blocks in shared.items():
    if len(set(blocks.values())) != 1: bad(f'the {part} differs between pages')
# Every footer carries the short line, and its link "Who prepares this work" lands on the home page's section (E2 B).
for rel, block in shared.get('footer', {}).items():
    if f'<p class="status">{unbroken(STATUS)}</p>' not in block: bad(f'{rel}: the footer does not carry the short line "{STATUS}"')
    foot_ = [(re.sub(r'<[^>]+>', '', h_), [(re.sub(r'index\.html$', '', a_), html.unescape(re.sub(r'<[^>]+>', '', w_))) for a_, w_ in re.findall(r'<li><a href="([^"]*)">(.*?)</a></li>', ul_)])
             for h_, ul_ in re.findall(r'<p class="fh">(.*?)</p><ul>(.*?)</ul>', block, flags=re.S)]
    if foot_ != FOOT: bad(f'{rel}: the footer\'s lists of links are {foot_}; the frame sets {FOOT}')
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
for need in [WORKS_WHAT, WORKS_WHO + ' ' + NOT_A, AI_FULL, PAYS, LOGISTICS_TITLE] + HOME_GAPS:
    if need not in home_text: bad(f'index.html: not word for word as released: "{need[:50]}"')
if AI_SITE not in texts.get('accessibility/index.html', ''): bad('accessibility: the sentence on AI tools is not there word for word')
contact_text = texts.get('contact/index.html', '')
if f'"{COMPLAINTS_GAP}"' not in contact_text: bad('contact: the released known gap on complaints about the project\'s own work is not there word for word, in quotation marks')
# The home page's section "Who prepares this work" links to the funding page (decision sheet 4, H1 A), and every page's menu is the
# frame's, in its order, with only the pages that are live.
home_html_ = (PUB / 'index.html').read_text(encoding='utf-8') if (PUB / 'index.html').is_file() else ''
who_m_ = re.search(r'<h2 id="who">Who prepares this work</h2>(.*?)</section>', home_html_, flags=re.S); who_html_ = who_m_.group(1) if who_m_ else ''   # the section only
if not re.search(r'<a href="funding/(?:index\.html)?#founder-ties"(?: data-url="[^"]*")?>a tie</a>', who_html_): bad('index.html: the section "Who prepares this work" does not link "a tie" to the record of ties on the funding page (run 7, Should fix 2)')
if not re.search(r'<a href="funding/(?:index\.html)?"(?: data-url="[^"]*")?>', who_html_): bad('index.html: the section "Who prepares this work" does not link to the funding page')
# The Screen is named by its title, word for word, in a link to its address (frame v0.6, section 5, row 5: the ledger's row). Its opening line, which the data center project gave
# for the link (note of 11 November 2026, point 3), is not on the home page in v0.6; the frame places the Screen's own words in section 2 (see the open choices on decision sheet 16).
screen = json_of((ROOT / 'src' / 'screen.json'))
home_page = (PUB / 'index.html').read_text(encoding='utf-8') if (PUB / 'index.html').is_file() else ''
if f'<a href="{screen["address"]}">{html.escape(screen["title"])}</a>' not in home_page: bad('index.html: the Screen is not named by its title, word for word, in a link to its address')
# Words marked as another project's are not counted against a budget, so each run of them must really be another project's: found, word for word, in what that project released, in
# what the site hosts of it, or in the saved data the build reads (frame v0.6, section 6; decision sheet 16). A sentence marked as theirs that is in none of these would let the page's
# own words go uncounted. A run ends at a block, a table cell, a list item or a line break; a capital that begins a sentence may be a small letter where it is quoted mid-sentence.
HIKSW_SHA = 'b9489293ba34e1d472c57ac386e0226122b6f580d356820ff3dbc52eef44e9cb'   # the nonprofit project's How In-Kind Standard Works v0.5, as saved in src/sources/nonprofit/
def squash_(s_): return re.sub(r'\s+', ' ', html.unescape(s_).replace('\u00a0', ' ').replace('\u202f', ' ').replace('\u200b', '')).strip()
def md_plain_(md_):
    md_ = re.sub(r'!\[([^\]]*)\]\([^)]*\)', r'\1', md_); md_ = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', md_)
    md_ = re.sub(r'`([^`]*)`', r'\1', md_); md_ = re.sub(r'(\*\*|__)(.+?)\1', r'\2', md_, flags=re.S)
    md_ = re.sub(r'(?<![\w*])([*_])(?=\S)(.+?)(?<=\S)\1(?![\w*])', r'\2', md_, flags=re.S)
    md_ = re.sub(r'(?m)^\s{0,3}#{1,6}\s+', '', md_); md_ = re.sub(r'(?m)^\s*(?:[-*+]|\d+[.)])\s+', '', md_); md_ = re.sub(r'(?m)^\s*>\s?', '', md_)
    return squash_(md_.replace('|', ' '))
def strings_of_(o_):
    if isinstance(o_, str): yield o_
    elif isinstance(o_, dict):
        for v_ in o_.values(): yield from strings_of_(v_)
    elif isinstance(o_, list):
        for v_ in o_: yield from strings_of_(v_)
    elif isinstance(o_, int) and not isinstance(o_, bool): yield str(o_)
hik_ = ROOT / 'src' / 'sources' / 'nonprofit' / 'How_In_Kind_Standard_Works_v0_5.md'
if not hik_.is_file() or hashlib.sha256(hik_.read_bytes()).hexdigest() != HIKSW_SHA:
    bad('src/sources/nonprofit/How_In_Kind_Standard_Works_v0_5.md: missing, or not the nonprofit project\'s released text; a new version also needs its checksum in HIKSW_SHA, with the founder\'s approval')
corpus_ = [md_plain_(hik_.read_text(encoding='utf-8'))] if hik_.is_file() else []
for names_ in RELEASED_PAGES.values():
    for n_ in names_: corpus_.append(block_text((ROOT / 'src' / 'released' / n_).read_text(encoding='utf-8')))
sv_ = json_of(ROOT / 'src' / 'screen_saved.json')
corpus_ += [squash_(x_) for x_ in strings_of_(sv_)] + [squash_(sv_['labels'][k_].format(**sv_['counts'])) for k_ in sv_['labels']] + [squash_(x_) for x_ in strings_of_(screen)]     + [squash_(f'{i_["evLabel"]} {i_["evStatus"]}') for i_ in sv_['items']]
for f_ in sorted((ROOT / 'src' / 'releases').glob('*.json')):
    if not f_.name.endswith('.zenodo.json'): corpus_ += [squash_(x_) for x_ in strings_of_(json_of(f_))]
for f_ in sorted((PUB / 'files').rglob('*')):
    if f_.is_file() and f_.suffix in ('.md', '.txt'): corpus_.append(md_plain_(f_.read_text(encoding='utf-8')))
corpus_ += [squash_(x_) for x_ in [ABOUT, NOT_A, PAYS, AI_FULL, COMPLAINTS_GAP, GAPS, 'Known gaps: ' + GAPS, LOGISTICS_TITLE] + HOME_GAPS]
fv_ = re.search(r'Version (\d+\.\d+) · (\d{1,2} [A-Z][a-z]+ 20\d\d) ·', block_text((ROOT / 'src' / 'released' / 'nonprofit' / 'Website_2026-11-14b' / 'funding-statement.html').read_text(encoding='utf-8')))
if fv_: corpus_.append(f'Version {fv_.group(1)}, {fv_.group(2)}')   # the version line the home page's ledger gives, made from the released statement's own line
corpus_text_ = ' | '.join(corpus_)
# Run 19, M2 and N1 (decision sheet 15, X2 A and X3 A: each card is closed to its name, verdict, home and condition; "a label and its note sit on separate lines, exactly as the record has them";
# "no character added to the record's words"): each card holds the saved record's words, all of them and only them, in this order: its section, its name, its verdict, its homes, its condition and its
# home note (a line each, whichever the record has), the title of its disclosure, what it would do, the label with its status, and the record's note on a line of its own.
def pieces_(h_): return [squash_(x_) for x_ in re.split(r'<[^>]+>', h_) if squash_(x_)]
cards_got_ = [pieces_(c_) for c_ in re.findall(r'<article class="item"[^>]*>(.*?)</article>', home_page, flags=re.S)]
cards_want_ = [[i_['sec'], i_['name'], i_['verdict'], *i_['chips'], *[x_ for x_ in (i_['vsub'], i_['hnote']) if x_], 'What it would do', i_['lead'], f'{i_["evLabel"]} {i_["evStatus"]}', i_['evText']] for i_ in sv_['items']]
if len(cards_got_) != len(cards_want_): bad(f'index.html: {len(cards_got_)} cards; the saved record has {len(cards_want_)} (decision sheet 15, X2 A)')
for n_, (g_, w_) in enumerate(zip(cards_got_, cards_want_), 1):
    if g_ != w_: bad(f'index.html: card {n_} reads {g_!r}; the saved record gives {w_!r} (decision sheet 15, X2 A and X3 A; run 19, M2 and N1)')
# Run 21, Should fix 1 and 2, and run 22, Should fix 1 and Note 1: rows of the ledger had cut the nonprofit project's sentence short ("drafts the founder has approved", without "; no organization has adopted
# them, and no lawyer has reviewed them"; "A live online course", without "paid", beside "Not yet scheduled", which is not that project's wording; the course without who may attend and the free recording;
# the committee without "and to review the founder's earlier decisions on them"; the open designs without "and would be dropped if an independent evaluation found that it does not lower costs"). A run of
# another project's words is held to be found word for word in its source, and a cut sentence is still found there, so these cells are held to the whole sentence the source gives.
for want_ in ('<span class="note theirs">The project\'s policies are drafts the founder has approved; no organization has adopted them, and no lawyer has reviewed them</span>',
              '<span class="what theirs">An unpaid advisory committee</span><span class="note theirs">to decide complaints about the founder and questions about the founder\'s own ties, and to review the founder\'s earlier decisions on them</span>',
              '<span class="what theirs">Open designs and kits</span></td><td class="theirs">At first, each would need, among other conditions, a gift for that purpose and a fiscal sponsor that agrees to run it before it could start, and would be dropped if an independent evaluation found that it does not lower costs</td>',
              '<span class="what theirs">One paid course: a live online course of about a day on the model documents</span></td><td class="theirs">At one published price, set before the first run, for county staff and officials and anyone else without a direct financial stake in how the documents are written or applied, with a free recording of each run published for everyone</td>'):
    if want_ not in home_page: bad(f'index.html: the ledger does not carry the nonprofit project\'s sentence whole: {want_[want_.index(">") + 1:][:90]}... (run 21, Should fix 1 and 2; run 22, Should fix 1)')
# Run 19, S1 and S2: after the cards' heading, the Screen's own lines on what a label means ("Passing the test only means an item is not ruled out. ...", with the link to its "What the colored labels mean"),
# and under the cards the State-law label with the Screen's line, preceded only by the count, which is this page's own.
lg_ = sv_['legend']; c_ = sv_['counts']
labels_ = re.findall(r'<p class="labels theirs">(.*?)</p>', home_page, flags=re.S)
if len(labels_) != 1 or pieces_(labels_[0]) != [lg_['passing'], lg_['heading']] or f'<a href="{screen["address"]}#{lg_["anchor"]}">' not in labels_[0]:
    bad(f'index.html: the note on what the labels mean is {[pieces_(x_) for x_ in labels_]!r}; the Screen\'s lines are {[lg_["passing"], lg_["heading"]]!r}, with the heading linked to {screen["address"]}#{lg_["anchor"]} (run 19, S1)')
law_ = re.findall(r'<p class="law">(.*?)</p>', home_page, flags=re.S)
law_want_ = [f'{c_["state_law_does_not_allow"]} of the {c_["items"]} items are labeled', lg_['state_law']['label'], lg_['state_law']['line']]
if [pieces_(x_) for x_ in law_] != [law_want_]: bad(f'index.html: the line on State law is {[pieces_(x_) for x_ in law_]!r}; it reads {law_want_!r}, the count and then the Screen\'s label and line (run 19, S2)')
# Run 19, M1 (Neutrality Test, gate 3, for items built on the 3.18 template): the headline says what the page shows; the page says that it does not weigh the benefits against costs, and that the
# project chose the three cards as examples, not as a ranking. Run 22 (gate 3 passed) asked that it also say that all three pass the test, and where the model documents' standards
# are; the founder chose those words on 18 November 2026, 08:46 (decision sheet 16, S3 C), and at 09:41 that the line name the test, as run 24 asked,
# with the Screen's own name for it, "the In-Kind test" (S6 A). A change of these words needs his answer.
HOME_H1 = 'What could a community receive under the model documents?'
HOME_SAYS = ['<p>Quoted from the public record: the homes, their lines, the cards and the labels. This page does not weigh the benefits against costs. '
             'What the model documents\' standards cover, among them water, sound and generator testing, is on <a href="materials/" data-url="https://inkindstandard.org/materials/">Model documents</a>.</p>',
             '<p>This project chose these three, all of which pass the In-Kind test, as examples, not a ranking.</p>']
h1s_ = re.findall(r'<h1\b[^>]*>(.*?)</h1>', home_page, flags=re.S)
if [squash_(re.sub(r'<[^>]+>', '', x_)) for x_ in h1s_] != [HOME_H1]: bad(f'index.html: the headline is {[squash_(re.sub(chr(60) + "[^>]+>", "", x_)) for x_ in h1s_]!r}; it reads "{HOME_H1}" (run 19, M1; decision sheet 16, S3)')
for s_ in HOME_SAYS:
    if home_page.count(s_) != 1: bad(f'index.html: the paragraph "{squash_(re.sub(chr(60) + "[^>]+>", "", s_))[:60]}..." is not there once, as written (run 19, M1; decision sheet 16, S3 C)')
# Home's notice says that Model documents lists what the standards cover, water, sound and generator testing among them: that page's list, in the release guide's words, must still name them.
mat_ = (PUB / 'materials' / 'index.html').read_text(encoding='utf-8') if (PUB / 'materials' / 'index.html').is_file() else ''
cover_ = re.search(r'What the standards cover:</strong>(.*?)</li>', mat_, flags=re.S)
# The list's own phrases are matched: a bare 'water' is also in 'stormwater' (run 24, Note 2).
if not cover_ or not all(w_ in cover_.group(1) for w_ in ('water and cooling', 'sound limits', 'generator testing')): bad('materials/index.html: the list item "What the standards cover:" does not name water, sound and generator testing, as Home\'s notice says it does (decision sheet 16, S3 C)')
# Run 19, S3 (frame v0.6, section 5, row 4: each figure "with its date and a link to its source"): the five figures each carry a link and a dated line.
figs_ = re.findall(r'<div class="num">(.*?)</div>', home_page, flags=re.S)
if len(figs_) != 5: bad(f'index.html: {len(figs_)} figures; there are five')
for n_, f_ in enumerate(figs_, 1):
    if '<a href="' not in f_ or not re.search(r'<small[^>]*>[^<]*\b20\d\d\b', f_): bad(f'index.html: figure {n_} lacks a link to its source or a dated line: {squash_(re.sub(chr(60) + "[^>]+>", " ", f_))[:80]!r} (run 19, S3)')
def found_(u_):
    u_ = squash_(u_).strip('"“”')   # quotation marks around a quoted sentence are the page's own
    if not re.search(r'[A-Za-z0-9]', u_): return True
    def one_(x_):
        x_ = x_.strip()
        if not x_: return True
        forms_ = [x_, x_[0].swapcase() + x_[1:]]; forms_ += [y_.rstrip('.;:,') for y_ in forms_ if y_.rstrip('.;:,') != y_]
        return any(y_ and y_ in corpus_text_ for y_ in forms_)
    if one_(u_): return True
    parts_ = re.split(r'(?<=[.!?])\s+(?=["\u201c]?[A-Z])', u_)   # a run may join sentences that the other project keeps apart
    return len(parts_) > 1 and all(one_(x_) for x_ in parts_)
for rel, us_ in units_.items():
    if rel in RELEASED_PAGES or release_page(rel): continue   # a release's page is tested against the release's own files in section 6
    for u_ in us_:
        if not found_(u_): bad(f'{rel}: words marked as another project\'s that are in none of its released texts or saved data: "{u_[:80]}"')
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
MONTHS_ = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
materials_html_ = (PUB / 'materials' / 'index.html').read_text(encoding='utf-8') if (PUB / 'materials' / 'index.html').is_file() else ''
materials_bt_ = block_text(materials_html_)   # the page's words with a space at every block tag, so that a line can be tested across the cells and lists it is set in
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
    read_ = re.search(r'\d{1,2} [A-Z][a-z]+ 20\d\d', z['read'])
    if not read_ or f"against Zenodo's own list, read on {read_.group(0)}" not in page_text: bad(f'{rel_id}: the page does not say that a program checks each file against Zenodo\'s own list, read on the day the saved list gives ({z["read"]}) (run 19, N4)')
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
        if f', {zr["license"]}, {GLOSS[zr["license"]]}' not in materials_bt_ or f'License: {zr["license"]}' not in page_text: bad(f'{rel_id}: the license of {r["key"]} is not shown as Zenodo has it')
    if data['title'] != TITLE or TITLE not in page_text: bad(f'{rel_id}: the public title is missing from the release page')
    linked = {md5.get((k, n)) for k, n in re.findall(r'href="(?:\.\./)*files/' + re.escape(rel_id) + r'/(\w+)/([^"]+)"', page)}
    unlinked = sorted(n for (k, n), m in md5.items() if m not in linked)
    if unlinked: bad(f'{rel_id}: hosted but not linked from the release page: {unlinked}')
materials = texts.get('materials/index.html', '')
# The table of releases on Materials (frame v0.6, section 5): a row for each release, the newest first, each with its date and the DOIs of its two records, as the saved lists give them.
# It is read from the parsed table, row by row, so that a date or a DOI cannot stand in another release's row.
def day_of_(d_): return f'{int(d_[8:])} {MONTHS_[int(d_[5:7]) - 1]} {d_[:4]}'
newest_ = max(zlists, key=lambda r: [int(x) for x in re.findall(r'\d+', r)])
cur_ = zlists[newest_]['records']
rows_want_ = [(newest_, day_of_(next(iter(cur_.values()))['published']), f'doi:{cur_["instruments"]["doi"]} · doi:{cur_["guide"]["doi"]}')] \
    + [(e['release'], day_of_(e['published']), f'doi:{e["instruments"]} · doi:{e["guide"]}') for e in earlier]
rows_want_.sort(key=lambda r: [int(x) for x in re.findall(r'\d+', r[0])], reverse=True)
rows_got_ = [tuple(block_text(c_) for c_ in re.findall(r'<td\b[^>]*>(.*?)</td>', r_, flags=re.S)) for r_ in re.findall(r'<tr\b[^>]*>(.*?)</tr>', materials_html_, flags=re.S)]
rows_got_ = [r_ for r_ in rows_got_ if r_]
if rows_got_ != rows_want_: bad(f'materials: the table of releases reads {rows_got_}; it must read {rows_want_}: the newest first, each with its date and the DOIs of its two records')
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
    if f.suffix.lower() in ('.png', '.svg', '.jpg', '.jpeg', '.gif', '.webp'):
        if rel not in LOGO_FILES or hashlib.sha256(f.read_bytes()).hexdigest() != LOGO_FILES[rel]: bad(f'image file {rel}: the site keeps the two approved logo files and no other image file; a new one needs its checksum in LOGO_FILES, with the founder\'s approval (the workspace the drafts are made in adds a provenance record to each PNG and SVG file it hands over, which changes the file)')
    elif rel not in expected: bad(f'a file that is not part of the site: {rel}')

# 7. Colors, paint and motion (frame v0.6, sections 7 to 9; decision sheet 15, X1 A and X4 A). Every color is named in one of four sets: the light set (:root), the dark
# set the switch gives (:root[data-theme="dark"]), the same dark set for a device that asks for dark unless the switch says light, and the print set. A rule uses a color only
# through a name. In each theme text reaches 7 to 1 and every mark that must be seen reaches 3 to 1 (the same pairs as the design's own tool, tools/contrast.py, which the
# founder's decision sheet 15 reports); the browser check (look_check.py) measures what the pages really show in both themes besides.
css = (PUB / 'assets' / 'site.css').read_text(encoding='utf-8')
plain_ = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
if re.search(r'url\(\s*["\']?(?:[a-z]+:|//)', css) or '@import' in css: bad('site.css loads from another host')
for f in re.findall(r'url\("([^"]+)"\)', css):
    if not (PUB / 'assets' / f).is_file(): bad(f'site.css: missing {f}')
def css_rules(sheet):
    """Each rule as (enclosing at-rules, selector, declarations). The first is '' outside an at-rule; a rule inside @keyframes inside @media is under
    '@media ... > @keyframes ...'. Selectors have their white space collapsed. The braces must balance."""
    text_, out_, stack_, start_ = re.sub(r'/\*.*?\*/', '', sheet, flags=re.S), [], [], 0
    for m_ in re.finditer(r'[{}]', text_):
        if m_.group() == '{':
            stack_.append(re.sub(r'\s+', ' ', text_[start_:m_.start()].strip())); start_ = m_.end()
        else:
            if not stack_: raise SystemExit('site.css: a } with no {')
            body_, head_ = text_[start_:m_.start()], stack_.pop()
            if body_.strip(): out_.append((' > '.join(h for h in stack_ if h.startswith('@')), head_, [(d.split(':', 1)[0].strip(), d.split(':', 1)[1].strip()) for d in body_.split(';') if ':' in d]))
            start_ = m_.end()
    if stack_: raise SystemExit('site.css: a { with no }')
    return out_

SETS = {('', ':root'): 'light', ('', ':root[data-theme="dark"]'): 'dark', ('@media (prefers-color-scheme:dark)', ':root:not([data-theme="light"])'): 'auto',
        ('@media print', ':root,:root[data-theme],:root:not([data-theme="light"])'): 'print'}
sheet_rules = css_rules(css)
sets_ = {SETS[(m_, s_)]: {k_[2:]: v_ for k_, v_ in d_ if k_.startswith('--')} for m_, s_, d_ in sheet_rules if (m_, s_) in SETS}   # names without their two hyphens
if set(sets_) != set(SETS.values()) or sum(1 for m_, s_, d_ in sheet_rules if (m_, s_) in SETS) != 4:
    bad('site.css: the colors are not named in exactly four sets (light, dark, dark for a device that asks, print)')
    sets_ = {k_: sets_.get(k_, {}) for k_ in SETS.values()}
if sets_['auto'] != sets_['dark']: bad('site.css: the dark set for a device that asks for dark differs from the dark set the switch gives')
if sets_['print'] != sets_['light']: bad('site.css: the print set differs from the light set')
THEME = {'light': dict(sets_['light']), 'dark': {**sets_['light'], **sets_['dark']}}   # the dark theme is the light set with the dark set laid over it
HEX6 = re.compile(r'#[0-9A-Fa-f]{6}')
RGBA = re.compile(r'rgba\((\d{1,3}),(\d{1,3}),(\d{1,3}),(\.\d+|1|0)\)')
for sname_, st_ in sets_.items():
    for n_, v_ in st_.items():
        if HEX6.fullmatch(v_) or RGBA.fullmatch(v_): continue
        if n_ == 'band-rule' and re.fullmatch(r'linear-gradient\(90deg(?:,#[0-9A-Fa-f]{6} (?:0|\d+%) \d+%){4}\)', v_): continue
        if n_ in ('sans', 'mono') and v_.startswith('"Atkinson Hyperlegible'): continue
        if (n_, v_) in (('link', 'var(--accent)'), ('focus', 'var(--focus-base)')): continue
        if n_ == 'wm-o' and re.fullmatch(r'\.\d+', v_): continue
        if n_ in ('r', 'r-s') and re.fullmatch(r'\d+px', v_): continue
        if n_.startswith('sh-') and re.fullmatch(r'0 [-\dpx ]+rgba\([\d,.]+\)(?:,0 [-\dpx ]+rgba\([\d,.]+\))*', v_): continue
        bad(f'site.css: --{n_} in the {sname_} set is "{v_}"; a named color is #RRGGBB, with rgba only for the lines, rings, soft fills and shadows this check lists')
def lum(hex_):
    c_ = [int(hex_[i_:i_ + 2], 16) / 255 for i_ in (1, 3, 5)]
    c_ = [v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4 for v in c_]
    return .2126 * c_[0] + .7152 * c_[1] + .0722 * c_[2]
def over(fg_, bg_):
    """The color a (maybe see-through) foreground shows on a solid ground, as #RRGGBB."""
    m_ = RGBA.fullmatch(fg_)
    if not m_: return fg_
    a_ = float(m_.group(4)); b_ = [int(bg_[i_:i_ + 2], 16) for i_ in (1, 3, 5)]
    return '#' + ''.join(f'{round(int(m_.group(k_ + 1)) * a_ + b_[k_] * (1 - a_)):02X}' for k_ in range(3))
def ratio(fg_, bg_):
    bg_ = bg_ if HEX6.fullmatch(bg_) else over(bg_, '#FFFFFF')
    fg_ = over(fg_, bg_)
    hi_, lo_ = sorted((lum(fg_), lum(bg_)), reverse=True)
    return (hi_ + .05) / (lo_ + .05)
def tokens(t, *pairs):
    """Each pair of names as (fg, bg) values in theme t; a name beginning # is a color as written."""
    return [(a, b, t[a] if not a.startswith('#') else a, t[b] if not b.startswith('#') else b) for a, b in pairs]
def text_pairs(t):
    P = [(fg, bg) for fg in ('ink', 'ink2', 'accent') for bg in ('bg', 'surface', 'card', 'tray', 'tint')]
    P += [('mast-ink', 'mast'), ('mast-sub', 'mast'), ('mast', '#FFFFFF'),   # the last: the pressed theme button, the header's color on white
          ('band-ink', 'band'), ('band-sub', 'band'), ('band-eye', 'band'), ('band-link', 'band'), ('band-btn-ink', 'band-btn'), ('band-btn-ink', 'band-btn-hover'), ('band-btn2', 'band'),
          ('nums-ink', 'nums'), ('nums-sub', 'nums'), ('nums-eye', 'nums'), ('fig', 'nums'), ('nums-link', 'nums'), ('nums-btn-ink', 'nums-btn'), ('nums-btn-ink', 'nums-btn-hover'), ('nums-btn2', 'nums'),
          ('gold-ink', 'gold'), ('gold-ink', 'gold-hover'), ('btn-ink', 'btn'), ('btn-ink', 'btn-hover'), ('pub-ink', 'pub-bg')]
    P += [(f'v-{v}', f'v-{v}-bg') for v in ('ok', 'prov', 'cond', 'no', 'na')]
    return tokens(t, *P)
def mark_pairs(t):
    P = [('ctl', bg) for bg in ('bg', 'surface', 'card', 'tray')] + [('focus-base', bg) for bg in ('bg', 'card', 'tray', 'tint')]
    P += [('gold', 'mast'), ('mast-ring', 'mast'), ('band-focus', 'band'), ('nums-focus', 'nums'), ('nums-mark', 'nums'), ('band-mark', 'band'), ('band-btn2-line', 'band'), ('nums-btn2-line', 'nums'),
          ('mark', 'bg'), ('mark', 'tray'), ('mark', 'card'), ('tab-on', 'card'), ('gaps-top', 'card'), ('ico-ink', 'ico-bg')]
    P += [(f'h-{h}-ink', f'h-{h}-bg') for h in ('std', 'item', 'lease', 'priv')]
    P += [('v-ok-line' if v == 'ok' else f'v-{v}', 'card') for v in ('ok', 'prov', 'cond', 'no', 'na')]
    return tokens(t, *P)
lowest = {7.0: 99, 3.0: 99}; n_pairs = 0; named_ = set()
for tname_, t_ in THEME.items():
    for pairs_, floor_ in ((text_pairs, 7.0), (mark_pairs, 3.0)):
        try: got_ = pairs_(t_)
        except KeyError as e_:
            bad(f'{tname_}: the color --{e_.args[0]} this check measures is not named'); continue
        for a_, b_, fa_, fb_ in got_:
            named_ |= {a_, b_}; n_pairs += 1
            c_ = ratio(fa_, fb_); lowest[floor_] = min(lowest[floor_], c_)
            if c_ < floor_: bad(f'{tname_}: {a_} on {b_} is {c_:.2f} to 1, under {floor_:g}')
# Every named #RRGGBB color is measured in some pair, or is listed here as a line that only separates; a new color cannot be added and used unchecked.
DECOR = {'rule', 'rule2', 'accent', 'focus-base', 'btn-line', 'tab-on'}   # accent and focus-base are measured as text and mark above; the rest only separate or underline
for n_ in sorted({n for st_ in sets_.values() for n, v in st_.items() if HEX6.fullmatch(v)} - named_ - DECOR): bad(f'site.css: --{n_} is a named color this check does not measure')
for n_ in sorted(n for n in named_ if not n.startswith('#') and n not in THEME['light']): bad(f'check_site.py names --{n_}, which site.css does not')   # a name that begins with # is a plain white, written as it is
# A color is used only through its name: none written outside the sets; a name set elsewhere only points at a name measured above, or is a plain step number.
if re.search(r'#[0-9A-Fa-f]{3,8}\b|\brgba?\(|\bhsla?\(', re.sub(r':root[^{}]*\{[^{}]*\}', '', plain_)): bad('site.css: a color is written outside the named sets')
POINTS = {'--link': {'var(--accent)', 'var(--mast-ink)', 'var(--band-link)', 'var(--nums-link)'}, '--focus': {'var(--focus-base)', 'var(--gold)', 'var(--band-focus)', 'var(--nums-focus)'},
          '--mark': {'var(--mark)', 'var(--band-mark)', 'var(--nums-mark)'}}
for media_, sel_, decls_ in sheet_rules:
    if (media_, sel_) in SETS: continue
    for p_, v_ in decls_:
        if p_.startswith('--') and not (v_ in POINTS.get(p_, ()) or (p_ == '--i' and re.fullmatch(r'\d', v_))): bad(f'site.css: {sel_} sets {p_}: {v_}; outside the four sets only the step number and the pointers this check lists may be set')
class NamesOnly(dict):
    def __missing__(self, k): return '#000000'   # only the names are used below
TEXT_NAMES = {a for a, _, _, _ in text_pairs(NamesOnly(THEME['light']))} | {'link'}
ICON_INKS = {'ico-ink'} | {f'h-{h}-ink' for h in ('std', 'item', 'lease', 'priv')}   # the icons' colors, measured as marks
WORDS = {'solid', 'dashed', 'dotted', 'none', 'transparent', 'currentColor', 'inherit', 'Canvas', 'CanvasText', 'LinkText', 'ButtonText', 'inset', 'px', 'rem', 'em', 'separate', 'collapse'}
PAINT = ('color', 'background', 'background-color', 'background-image', 'outline', 'outline-color', 'fill', 'stroke', 'text-decoration-color', 'box-shadow', 'caret-color', 'accent-color', 'column-rule')
for media_, sel_, decls_ in sheet_rules:
    if (media_, sel_) in SETS or sel_.startswith('@font-face'): continue
    for prop, value in decls_:
        if prop in ('filter', 'backdrop-filter', 'mix-blend-mode', '-webkit-text-fill-color', '-webkit-text-stroke', '-webkit-text-stroke-color', 'forced-color-adjust') or 'color-mix(' in value: bad(f'site.css: {sel_} changes a color with {prop}')
        if prop == 'color' and 'transparent' in value: bad(f'site.css: {sel_} makes text transparent')
        if prop == 'outline-color': bad(f'site.css: {sel_} changes the focus outline\'s color; the focus color is the name --focus, pointed at a measured name where the ground changes')
        if prop in PAINT or prop.startswith('border'):
            for word in re.findall(r'(?<![\w(-])[A-Za-z][A-Za-z-]*(?![\w(-])', re.sub(r'var\(--[\w-]+\)', ' ', value)):
                if word not in WORDS: bad(f'site.css: {sel_} sets {prop} with the word "{word}"; a color is used only through its name')
        if prop == 'color':
            for n in re.findall(r'var\(--([\w-]+)\)', value):
                if n not in TEXT_NAMES and not (n in ICON_INKS and sel_.endswith('.ico')): bad(f'site.css: {sel_} uses --{n} as a text color; it is not measured as one')   # an icon's ink is measured as a mark (3 to 1); the page rule keeps words out of .ico
        if prop.startswith('outline') and re.fullmatch(r'0|none|0 none|none 0', value): bad(f'site.css: {sel_} removes the focus outline')
top = {s_: dict(d_) for m_, s_, d_ in sheet_rules if not m_}
if top.get('a', {}).get('text-decoration') != 'underline': bad('site.css: links are not underlined (the rule for "a")')
if top.get('a:focus-visible,button:focus-visible,summary:focus-visible', {}).get('outline') != '3px solid var(--focus)': bad('site.css: missing the focus rule "outline:3px solid var(--focus)" for links, buttons and summaries')
if any('class="vh"' in q.read_text(encoding='utf-8') for q in pages) and top.get('.vh', {}).get('clip-path') != 'inset(50%)': bad('site.css: the rule that hides words kept for screen readers (.vh) is missing')
if top.get('[hidden]', {}).get('display') != 'none!important': bad('site.css: the rule that keeps a hidden element hidden ([hidden]) is missing')
# Paint is held as it is (C4-06): "all" is not used; generated content, underlines, focus outlines and opacity exactly as listed, by media block and selector. A deliberate
# change to these is made here too. Every opacity below is a still or a motion step that sits inside the media block for devices that have not asked for reduced motion,
# except the watermark's own (a fixed figure from the named set) and the diagram's dimming while a home is hovered, which dims other lines and labels, never text a reader needs.
HELD_PAINT = {
    ('', 'a', 'text-decoration'): 'underline',
    ('', 'a', 'text-decoration-thickness'): '.08em',
    ('', 'a', 'text-underline-offset'): '.18em',
    ('', 'a:hover', 'text-decoration-thickness'): '.16em',
    ('', 'a:focus-visible,button:focus-visible,summary:focus-visible', 'outline'): '3px solid var(--focus)',
    ('', 'a:focus-visible,button:focus-visible,summary:focus-visible', 'outline-offset'): '3px',
    ('', '.brand', 'text-decoration'): 'none',
    ('', '.util a', 'text-decoration'): 'none',
    ('', '.util a:hover,.util a.on', 'text-decoration'): 'underline',
    ('', '.nav a', 'text-decoration'): 'none',
    ('', '.mnav li a', 'text-decoration'): 'none',
    ('', '.wrap>.eyebrow::before,.wrap>div>.eyebrow::before,.sec-head .eyebrow::before,.read>.eyebrow::before,.hero .eyebrow::before,.phead .eyebrow::before', 'content'): '""',
    ('', '.hero .wm,.phead .wm', 'opacity'): 'var(--wm-o)',
    ('', '.btn', 'text-decoration'): 'none',
    ('', '.btn:hover', 'text-decoration'): 'underline',
    ('', '.steps li::before', 'content'): 'counter(s)',
    ('', '.vd::before', 'content'): '""',
    ('', '.stepper::before', 'content'): '""',
    ('', '.stepper>li::before', 'content'): 'counter(st)',
    ('', '.stepper>li::after', 'content'): '""',
    ('', '.stepper summary::after', 'content'): '""',
    ('@media (prefers-reduced-motion:no-preference)', '.fx-wait', 'opacity'): '0',
    ('@media (prefers-reduced-motion:no-preference) > @keyframes rise', 'from', 'opacity'): '.35',
    ('@media (prefers-reduced-motion:no-preference) > @keyframes rise', 'to', 'opacity'): '1',
    ('@media (prefers-reduced-motion:no-preference) > @keyframes reveal', 'from', 'opacity'): '0',
    ('@media (prefers-reduced-motion:no-preference) > @keyframes reveal', 'to', 'opacity'): '1',
    ('', '.more summary::before', 'content'): '""',
    ('', '.ways a', 'text-decoration'): 'none',
    ('', '.ways a::before', 'content'): 'counter(w)',
    ('', '.ways a::after', 'content'): '"\\2192"',
    ('', '.ways a:hover span', 'text-decoration'): 'underline',
    ('', '.ways a:hover span', 'text-decoration-thickness'): '.1em',
    ('', '.ways a:hover span', 'text-underline-offset'): '.18em',
    ('', '.where:has(.home[data-h="std"]:hover) .dg-line:not([data-h="std"]),.where:has(.home[data-h="item"]:hover) .dg-line:not([data-h="item"]),.where:has(.home[data-h="lease"]:hover) .dg-line:not([data-h="lease"]),.where:has(.home[data-h="priv"]:hover) .dg-line:not([data-h="priv"])', 'opacity'): '.22',
    ('', '.where:has(.home[data-h="std"]:hover) .dg-lab:not([data-h="std"]),.where:has(.home[data-h="item"]:hover) .dg-lab:not([data-h="item"]),.where:has(.home[data-h="lease"]:hover) .dg-lab:not([data-h="lease"]),.where:has(.home[data-h="priv"]:hover) .dg-lab:not([data-h="priv"])', 'opacity'): '.3',
    ('@media (prefers-reduced-motion:no-preference)', '.dg-wait .ah', 'opacity'): '0',
    ('@media (prefers-reduced-motion:no-preference) > @keyframes show', 'from', 'opacity'): '0',
    ('@media (prefers-reduced-motion:no-preference) > @keyframes show', 'to', 'opacity'): '1',
    ('@media print', '.fx-wait', 'opacity'): '1!important',
    ('@media print', 'main a[href^="http"]:not(.doi)::after', 'content'): '" (" attr(href) ")"',
    ('@media print', 'main a[data-url]::after', 'content'): '" (" attr(data-url) ")"',
    ('@media print', 'main .released a[href]::after', 'content'): 'none'}
seen_ = set()
for media_, sel_, decls_ in sheet_rules:
    for prop_, value_ in decls_:
        if prop_ == 'all': bad(f'site.css: {sel_} uses "all", which resets every property at once')
        elif prop_ in ('content', 'opacity') or prop_.startswith(('text-decoration', 'text-underline', 'outline')):
            seen_.add((media_, sel_, prop_))
            if HELD_PAINT.get((media_, sel_, prop_)) != value_: bad(f'site.css: {(media_ + " ") if media_ else ""}{sel_} sets {prop_}: {value_}; underlines, focus outlines, generated content and opacity are held as this check lists them')
for k_ in sorted(HELD_PAINT.keys() - seen_): bad(f'site.css: {k_[1]} no longer sets {k_[2]}: {HELD_PAINT[k_]}')
# Motion (frame section 7): everything that moves or changes is inside the media block for devices that have not asked for reduced motion; the print rule shows the
# still version; no step runs over the limits the frame gives (a reveal 400 ms and 16 px, the drawing 1.5 s, a switch 200 ms, five seconds in all).
NO_PREF = '@media (prefers-reduced-motion:no-preference)'
STEP_MAX = 3   # the largest step number the rules give (--i)
def seconds(t_): return float(t_[:-2]) / 1000 if t_.endswith('ms') else float(t_[:-1])
def delay_of(v_):
    m_ = re.fullmatch(r'calc\((?:(?P<a>[\d.]+m?s) ?\+ ?)?var\(--i,0\)\*(?P<b>[\d.]+m?s)\)', v_)
    if m_: return (seconds(m_.group('a')) if m_.group('a') else 0) + STEP_MAX * seconds(m_.group('b'))
    return seconds(v_) if re.fullmatch(r'[\d.]+m?s', v_) else None
ends = {}
for media_, sel_, decls_ in sheet_rules:
    d_ = dict(decls_)
    for prop_, value_ in decls_:
        v0_ = value_.replace('!important', '').strip()   # a declaration that takes motion away may carry !important (the print rule, run 21, Must fix 1)
        if prop_.startswith(('animation', 'transition', 'scroll-behavior')) and v0_ not in ('none', 'auto') and media_ != NO_PREF:
            bad(f'site.css: {sel_} sets {prop_} outside the media block for devices that have not asked for reduced motion')
        if prop_ == 'animation' and media_ == NO_PREF:
            if v0_ == 'none': continue   # a section waiting to be revealed has no animation yet
            m_ = re.match(r'(\w+) ([\d.]+m?s)\b', value_)
            if not m_: bad(f'site.css: {sel_} sets animation: {value_}, which this check cannot read'); continue
            name_, dur_ = m_.group(1), seconds(m_.group(2)); delay_ = delay_of(d_.get('animation-delay', '0s'))
            if delay_ is None: bad(f'site.css: {sel_} sets animation-delay: {d_["animation-delay"]}, which this check cannot read'); continue
            ends.setdefault(name_, []).append((sel_, dur_, delay_ + dur_))
        if prop_ == 'transition' and v0_ != 'none':
            for part_ in value_.split(','):
                m_ = re.search(r'\s([\d.]+m?s)\b', part_)
                if not m_ or seconds(m_.group(1)) > .2: bad(f'site.css: {sel_} sets transition: {part_.strip()}; a switch takes at most 200 ms')
LIMITS = {'rise': (.5, .8), 'reveal': (.4, .7), 'draw': (.6, 1.5), 'show': (.2, 1.5)}   # name: (longest single step, latest end counting the largest step delay); the tab switch, .2 s, is the "reveal" keyframes
for name_, rows_ in ends.items():
    if name_ not in LIMITS: bad(f'site.css: an animation named {name_} that this check does not know'); continue
    for sel_, dur_, end_ in rows_:
        if (name_ == 'reveal' and '.tabpanel' in sel_ and dur_ > .2) or dur_ > LIMITS[name_][0] or end_ > LIMITS[name_][1] or end_ > 5: bad(f'site.css: {sel_} runs the {name_} animation for {dur_:g} s, ending at {end_:g} s, over its limit')
for media_, sel_, decls_ in sheet_rules:
    if '@keyframes' in media_:
        for p_, v_ in decls_:
            if p_ == 'transform' and v_ != 'none' and not re.fullmatch(r'translateY\((\d+)px\)', v_): bad(f'site.css: a keyframe moves with {v_}; only a rise of at most 16 px is allowed')
            m_ = re.fullmatch(r'translateY\((\d+)px\)', v_)
            if m_ and int(m_.group(1)) > 16: bad(f'site.css: a keyframe moves {m_.group(1)} px; the limit is 16')
            if p_ not in ('opacity', 'transform', 'stroke-dashoffset'): bad(f'site.css: a keyframe sets {p_}; only opacity, a short rise and the drawing\'s dash may change')
if not any(m_ == '@media print' and s_ == '.fx-wait' and dict(d_).get('opacity') == '1!important' for m_, s_, d_ in sheet_rules): bad('site.css: the print rule that shows a section waiting to be revealed is missing')
# Paper shows every word (run 21, Must fix 1): the browser takes its copy as it switches to print, so nothing may be animating then (an animation that starts with the switch is at its first
# frame, with its words faded out), and a heading the script has put away with [hidden] must still print (a rule without !important loses to the one for [hidden]).
if not any(m_ == '@media print' and s_ == '*,*::before,*::after' and dict(d_).get('animation') == 'none!important' and dict(d_).get('transition') == 'none!important' for m_, s_, d_ in sheet_rules): bad('site.css: the print rule that stops every animation and transition on paper is missing (run 21, Must fix 1)')
if not any(m_ == '@media print' and s_ == '.readers .tabpanel h3' and dict(d_).get('display') == 'flex!important' for m_, s_, d_ in sheet_rules): bad('site.css: the print rule that shows each reader\'s name, which the script puts away with [hidden], is missing or does not use !important (run 21, Must fix 1)')
# Paper keeps every link (run 22, Should fix 2): a button is a link, and a link prints with its address (frame v0.6, section 8), so the print rules do not put a group of buttons away. Each prints as a plain link:
# dark text and no fill, because a fill is not printed unless the reader asks for background graphics, and the band's light text on it would vanish.
for m_, s_, d_ in sheet_rules:
    if m_ == '@media print' and dict(d_).get('display', '').startswith('none') and any(re.search(r'(?:^|[\s>+~])(?:\.actions|\.btn)$', x_.strip()) for x_ in s_.split(',')):
        bad(f'site.css: the print rule {s_} puts the buttons away; they are links, and a link prints with its address (run 22, Should fix 2)')
if not any(m_ == '@media print' and s_ == 'main .actions .btn' and dict(d_).get('background') == 'none' and dict(d_).get('border') == '0' and dict(d_).get('color') == 'var(--ink)' for m_, s_, d_ in sheet_rules):
    bad('site.css: the print rule that prints each button as a plain link (dark text, no fill, no border) is missing (run 22, Should fix 2)')
fonts = [f for f in (PUB / 'assets' / 'fonts').glob('*.woff')] if (PUB / 'assets' / 'fonts').is_dir() else []
if not fonts or not (PUB / 'assets' / 'fonts' / 'OFL-AtkinsonHyperlegible.txt').is_file(): bad('the font files or their license file are missing')
# No DOI is typed by hand on a page: the build places each one from src/releases/.
for f in sorted((ROOT / 'src' / 'pages').glob('*.html')) + [ROOT / 'src' / 'layout.html']:
    if 'zenodo.' in f.read_text(encoding='utf-8'): bad(f'src/{f.relative_to(ROOT / "src").as_posix()}: a DOI typed by hand; use {{{{doi:...}}}}, {{{{alldoi:...}}}} or {{{{earlier}}}}')
    if re.search(DATE_TYPED, re.sub(DATE_ALLOWED, '', f.read_text(encoding='utf-8'))):
        bad(f'src/{f.relative_to(ROOT / "src").as_posix()}: a date typed by hand; a release\'s date is placed with {{{{published:...}}}}, and a dated note begins '
            '"Automated checks,", "By hand," or "Correction," and gives the day, the month in full and the year')
# Each record's line reads as the release's own data gives it (frame v0.6, section 5): its contents, the count of its documents that have a version, its own DOI and its license; on
# Home and Materials the license's plain words follow (run 19, S5). A DOI or a license cannot stand beside the wrong record while both are on the page (the build check of candidate 4, C4-07).
newest = max(zlists, key=lambda r: [int(x) for x in re.findall(r'\d+', r)])   # the newest by number: 2026.10 comes after 2026.4
cur = zlists[newest]['records']
cur_data = json_of((ROOT / 'src' / 'releases' / f'{newest}.json'))
ndocs_ = {k_: sum(1 for d_ in cur_data[k_] if d_['version']) for k_ in ('instruments', 'guide')}
home_bt_ = block_text(home_html_)
read_n_ = re.search(r'\d{1,2} [A-Z][a-z]+ 20\d\d', zlists[newest]['read'])
if not read_n_ or f"checked against Zenodo's own list, read on {read_n_.group(0)}" not in materials_bt_: bad(f'materials: the release card does not say that the copies are checked against Zenodo\'s own list, read on the day the saved list gives ({zlists[newest]["read"]}) (run 19, N4)')
for r in cur_data['records']:
    head_, lic_, k_ = r['label'].split(':')[0], cur[r['key']]['license'], r['key']
    line_ = f'{head_} {r["contents"]} ({ndocs_[k_]} documents). doi:{cur[k_]["doi"]}, {lic_}'
    if f'{line_}, {GLOSS[lic_]}' not in home_bt_: bad(f'index.html: the line for {head_} does not read "{line_}, {GLOSS[lic_]}" (its contents, its count of documents, its own DOI, its license, and the license in plain words)')
    if line_ + f', {GLOSS[lic_]}' not in materials_bt_: bad(f'materials: the line for {head_} does not read "{line_}, {GLOSS[lic_]}"')
# The two DOIs that always lead to the newest release stand beside their own words on Materials; the release's own DOIs stand on the home page, Materials and the release's page only.
for need in (f'The instruments doi:{cur["instruments"]["conceptdoi"]}', f'The guide, the open legal questions and the methodology doi:{cur["guide"]["conceptdoi"]}'):
    if need not in materials_bt_: bad(f'materials: a DOI that leads to the newest release is not beside its own words: "{need}"')
for q in pages:
    rel_ = q.relative_to(PUB).as_posix()
    if rel_ in ('index.html', 'materials/index.html', f'materials/{newest}/index.html'): continue
    for key_, rec_ in cur.items():
        if rec_['doi'] in q.read_text(encoding='utf-8'): bad(f'{rel_}: the current release\'s own DOI for {key_} ({rec_["doi"]}) belongs on the home page, Materials and the release page only')
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
for rel_, prefix_ in (('index.html', 'materials/'), ('materials/index.html', '../materials/')):
    h_ = (PUB / rel_).read_text(encoding='utf-8') if (PUB / rel_).is_file() else ''
    btns_ = re.findall(r'<a class="btn" href="' + re.escape(prefix_) + r'(\d{4}\.\d+)/(?:index\.html)?"(?: data-url="[^"]*")?>([^<]*)</a>', h_)
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

# 8. The script, the sizes and the addresses (frame v0.6, section 7, "Speed" and "Motion"; decision sheet 15, X1 A). The site's one script is its own file: no network, no cookie, no library,
# no timer and no address. It keeps one choice, the color theme, in the browser's own storage under one name; the count-up runs 1.2 seconds; every other number in it is a fraction or a step.
js_ = (ROOT / 'src' / 'assets' / 'site.js').read_text(encoding='utf-8')
def js_code_of_(js):
    """The script's code with its comments taken out and its strings kept, read through once so that a "/*" inside a string is not taken for a comment. None where it cannot be read
    that way: a double quote, a backtick or a string left open (the script is written with single quotes only; run 20)."""
    out, i, n = [], 0, len(js)
    while i < n:
        c = js[i]
        if c == "'":
            j = i + 1
            while j < n and js[j] != "'":
                if js[j] == '\\': j += 1
                if j < n and js[j] == '\n': return None
                j += 1
            if j >= n: return None
            out.append(js[i:j + 1]); i = j + 1
        elif js.startswith('/*', i):
            j = js.find('*/', i + 2)
            if j < 0: return None
            out.append(' '); i = j + 2
        elif js.startswith('//', i):
            j = js.find('\n', i); i = n if j < 0 else j
        elif c in '"`': return None
        else: out.append(c); i += 1
    return ''.join(out)
js_code_ = js_code_of_(js_)
if js_code_ is None:
    bad("src/assets/site.js: a double quote, a backtick or a string left open; the script's text is written with single quotes only, so that these rules can read it")
    js_code_ = re.sub(r'(?m)^\s*//.*$', '', re.sub(r'/\*.*?\*/', '', js_, flags=re.S))
for pat_, why_ in ((r'\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon|importScripts|Worker|SharedWorker|serviceWorker|indexedDB|openDatabase)\b', 'a call to the network, a worker or a database'),
                   (r'\bdocument\s*\.\s*cookie\b', 'a cookie'), (r'\b(?:eval|Function)\s*\(', 'code made from text'), (r'\bdocument\s*\.\s*write', 'document.write'),
                   (r'\bsetInterval\b', 'a timer that repeats'), (r'\bsetTimeout\b', 'a timer'), (r'\bimport\b|\brequire\s*\(', 'a library'), (r'https?:|//[A-Za-z]', 'an address'),
                   (r'\binnerHTML\b|\bouterHTML\b|\binsertAdjacentHTML\b|\bcreateContextualFragment\b|\bparseFromString\b|\bsrcdoc\b', 'markup made from text'), (r'\bsessionStorage\b', 'session storage'), (r'\bnavigator\b', 'the navigator object'),
                   (r'\blocation\s*[.=]|\bwindow\s*\.\s*open\b', 'a move to another page'), (r'\bpostMessage\b', 'a message to another window')):
    if re.search(pat_, js_code_): bad(f'src/assets/site.js: {why_}; the site\'s script has no network, cookie, library, timer, address or move to another page (frame v0.6, section 7)')
if re.findall(r"\bKEY\s*=\s*'([^']*)'", js_code_) != ['iks-theme']: bad('src/assets/site.js: the one storage key must be "iks-theme", and the only one')
if len(re.findall(r'localStorage', js_code_)) != len(re.findall(r'window\s*\.\s*localStorage\s*\.\s*(?:getItem|setItem|removeItem)\s*\(\s*KEY\s*[,)]', js_code_)): bad('src/assets/site.js: browser storage is used for something other than the one theme key')
# The words above are a list of what the script may not use, and a list of words lets through what it does not name (run 20, the build check: a picture loaded from the site's own address, a name made from
# text, a second key built from the first). These hold the script to what it does: it makes elements only through its one helper and only as divs and buttons, loads no file and sets no address, makes no
# object but the reveal's observer and looks up no name made from text. What no rule on the text can settle (a name put together from pieces) the look check settles by what the pages do: no cookie, no
# request for a file the site does not hold, no storage but the one key, nothing that moves at rest.
LOADS_ = 'a file or an address loaded or set by the script'
LOADING_ATTRS_ = {'src', 'srcset', 'href', 'action', 'formaction', 'data', 'poster', 'ping', 'background', 'style', 'srcdoc', 'xlink:href'}
js_plain_ = re.sub(r"'(?:[^'\\\n]|\\.)*'", "''", js_code_)   # the code with every string emptied, so that a bracket inside a string is not read as a name
for m_ in re.finditer(r'\bnew\s+([A-Za-z_$][\w$]*)', js_plain_):
    if m_.group(1) != 'IntersectionObserver': bad(f"src/assets/site.js: {LOADS_} (an object made with new {m_.group(1)}; the script makes only the reveal's observer); frame v0.6, section 7")
if re.search(r'\.\s*(?:src|srcset|href|action|formAction|data|poster|ping|srcdoc|cssText)\s*=(?!=)', js_plain_): bad(f"src/assets/site.js: {LOADS_} (an address or a style written to an element); frame v0.6, section 7")
if re.search(r'\burl\s*\(', js_code_): bad(f"src/assets/site.js: {LOADS_} (url(); the style sheet draws, the script does not); frame v0.6, section 7")
GIVEN_ = re.compile(r'class|role|type|id|hidden|open|data-[a-z-]+|aria-[a-z-]+')   # the attributes the script gives, written out
def attr_(name_, what_):
    if name_.lower() in LOADING_ATTRS_: bad(f"src/assets/site.js: {LOADS_} ({what_}); frame v0.6, section 7")
    elif not GIVEN_.fullmatch(name_): bad(f"src/assets/site.js: an attribute the script does not give ({what_}; the script gives class, role, type, id, hidden, open, data- and aria- attributes); frame v0.6, section 7")
for m_ in re.finditer(r"\bsetAttribute\s*\(\s*'([^']*)'", js_code_): attr_(m_.group(1), f'setAttribute of {m_.group(1)}')
if [(a_, b_.strip()) for a_, b_ in re.findall(r"\b(\w+)\s*\.\s*setAttribute\s*\(\s*(?!')([^,)]*)", js_code_)] != [('n', 'k')]: bad(f"src/assets/site.js: {LOADS_} (setAttribute with a name that is not written out, anywhere but in the one helper); frame v0.6, section 7")
for m_ in re.finditer(r"(?<!function )(?<![\w$.])el\s*\(\s*([^,)]*)(,\s*\{([^}]*)\})?", js_code_):
    if m_.group(1).strip() not in ("'div'", "'button'"): bad(f"src/assets/site.js: an element that loads or sends (el({m_.group(1).strip()}); the script makes a div and a button and no other element); frame v0.6, section 7")
    for k_ in re.findall(r"(?:^|,)\s*'?([A-Za-z][\w:-]*)'?\s*:", m_.group(3) or ''): attr_(k_, f'the attribute {k_} given to an element')
if len(re.findall(r'\bcreateElement\w*\s*\(', js_code_)) != 1 or not re.search(r'function\s+el\s*\(\s*tag\s*,\s*attrs\s*,\s*text\s*\)\s*\{\s*var\s+n\s*=\s*document\s*\.\s*createElement\s*\(\s*tag\s*\)', js_code_):
    bad("src/assets/site.js: an element made outside the one helper (el); frame v0.6, section 7")
for m_ in re.finditer(r'\[', js_plain_):   # a name looked up in square brackets is allowed on the script's own lists, by a plain index, and on nothing else
    before_ = js_plain_[:m_.start()].rstrip()
    if not before_ or not (before_[-1] in ")]'$_" or before_[-1].isalnum()) or re.search(r'(?<![\w$.])(?:return|typeof|in|of|case|else|do|new|void|delete|yield|await|throw)$', before_): continue   # an array written out, not a name looked up
    if not (re.search(r'(?<![\w$.])(?:attrs|o|panels|tabs)$', before_) and re.match(r'\[\s*(?:[A-Za-z_]\w*|\d+)\s*\]', js_plain_[m_.start():])):
        bad("src/assets/site.js: a name made from text (a name looked up in square brackets on anything but the script's own lists, such as window or document); frame v0.6, section 7"); break
if [int(x) for x in re.findall(r'(?<![\w.])(\d{3,})(?![\w.])', js_code_)] != [1200]: bad('src/assets/site.js: its only duration is the count-up\'s 1200 milliseconds (frame v0.6, section 7: at most 1.2 seconds)')
css_b_, js_b_ = (PUB / 'assets' / 'site.css').stat().st_size, (PUB / 'assets' / 'site.js').stat().st_size
if css_b_ > 40000: bad(f'assets/site.css is {css_b_} bytes; the frame\'s limit is 40 KB (frame v0.6, section 7, "Speed")')
if js_b_ > 30000: bad(f'assets/site.js is {js_b_} bytes; the frame\'s limit is 30 KB (frame v0.6, section 7, "Speed")')
fonts_b_ = sum(f_.stat().st_size for f_ in (PUB / 'assets' / 'fonts').glob('*.woff')); logo_b_ = max(f_.stat().st_size for f_ in (PUB / 'assets').glob('logo*.svg'))
for q in pages:   # a first visit: the page, the style sheet, the script, every font the style sheet names, the largest logo where the page holds one and the icon (hosted documents are not pages)
    w_ = q.stat().st_size + css_b_ + js_b_ + fonts_b_ + (logo_b_ if '<img ' in q.read_text(encoding='utf-8') else 0) + (PUB / 'favicon.ico').stat().st_size
    if w_ > 350000: bad(f'{q.relative_to(PUB).as_posix()}: a first visit loads up to {w_} bytes; the frame\'s limit is 350 KB (frame v0.6, section 7, "Speed")')

# The repository's own documents, README.md, RUNBOOK.md and NOTICE.md (the frame for the repository's files, approved 13 November
# 2026; run 9, the build check, Should fix 6): the byline as the third line, the known gaps and a dated last line; the line on
# AI tools wherever a document names AI tools (Political Neutrality Policy, section 3.19); no address but the contact address,
# no telephone number, nothing hidden from readers and no key in a form services give; the site's word list; tables whose
# rows agree; and the frame's word budgets. LICENSE is Creative Commons' CC0 1.0 legal code, held by its checksum.
DOC_BUDGET = {'README.md': (450, 600), 'RUNBOOK.md': (2350, 2350), 'NOTICE.md': (300, 300)}   # (own words, all words); the runbook's was 2250 until run 20; the founder approved 2350 and the notice's 300 (decision sheet 16, S2 A, 18 November 2026)
LICENSE_SHA = 'a2010f343487d3f7618affe54f789f5487602331c0a8d03f49e9a7c547cf0499'
# The runbook says how far over its word budget a page may go; it must say what ROOM is (run 21, Must fix 2: it said "a fifth" when ROOM was 5 percent).
if (ROOT / 'RUNBOOK.md').is_file():   # a missing runbook is reported with the other documents below (this read once stopped the check with its general stop message, naming the exception, and not with "RUNBOOK.md: missing"; found when the whole planted set was re-run on the fourth freeze)
    rb_room_ = re.search(r'within its word budget plus ([^(]+?) \(`ROOM`\)', (ROOT / 'RUNBOOK.md').read_text(encoding='utf-8'))
    want_room_ = f'{round((ROOM - 1) * 100)} percent'
    if not rb_room_ or rb_room_.group(1).strip() != want_room_:
        bad(f'RUNBOOK.md, section 6: says a page may go over its word budget by "{rb_room_.group(1).strip() if rb_room_ else "(no such sentence)"}"; ROOM in this check is {want_room_}')
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
    if name_ == 'NOTICE.md':   # each file and folder directly under src/ has its license stated here (run 20, Should fix 3: the icons, the saved words of the Screen and the nonprofit's source text were left out)
        for e_ in sorted((ROOT / 'src').iterdir()):
            if e_.name not in ('__pycache__', 'desktop.ini') and f'src/{e_.name}' not in t_: bad(f'NOTICE.md: src/{e_.name} is not named; each file and folder under src/ needs its license stated here')
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
