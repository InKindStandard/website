"""Writes each built page as plain text, for anyone who reviews the words.

A reviewer reads the words a visitor meets, so this
takes them from the built pages in docs/, not from src/: the header is left out (the skip link, the site's name
and the menu), the main text and the footer are kept, headings are marked with #, list items with -, and a link is
shown by its words alone. Words kept for screen readers only (class "vh") are left out; lines shown only on paper
are marked. Also left out: each page's description, and the addresses the style sheet prints after a link on paper.

Run:  python3 tools/pages_as_text.py            (prints every page)
      python3 tools/pages_as_text.py OUT        (writes OUT/<page>.txt, one file for each page)
Needs Python 3.10 or later and nothing else.
"""
import html.parser, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PUB = ROOT / 'docs'
HEAD = {'h1': '# ', 'h2': '## ', 'h3': '### ', 'h4': '#### '}
BLOCK = {'p', 'li', 'h1', 'h2', 'h3', 'h4', 'div', 'ul', 'ol', 'footer', 'main', 'section', 'article', 'details', 'summary', 'table', 'tr', 'td', 'th', 'dl', 'dt', 'dd', 'figure', 'figcaption'}   # each starts a new line, so that two cells or a term and its meaning are never run together
VOID = {'meta', 'link', 'img', 'br', 'hr', 'input', 'source', 'path', 'wbr'}
INLINE = {'span', 'a', 'b', 'strong', 'em', 'i', 'code', 'time'}   # two of these side by side with no space between them are shown apart (a label and its text), so a space is put between them here


class Text(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.line, self.stack, self.title, self.in_title, self.after_inline = [], '', [], '', False, False
    def hidden(self):
        return any(h for _, h in self.stack)
    def shown(self):
        return any(t in ('main', 'footer') for t, _ in self.stack) and not self.hidden()
    def flush(self):
        s = re.sub(r'\s+', ' ', self.line).strip()
        if s and not re.fullmatch(r'-|#{1,4}', s): self.out.append(s)   # a marker with no words after it (a list item that begins with a heading) is not a line
        self.line = ''
    def handle_starttag(self, tag, attrs):
        if tag in VOID: return
        a = dict(attrs); cls = set((a.get('class') or '').split())
        self.stack.append((tag, tag in ('svg', 'nav', 'script', 'style') or 'vh' in cls))
        if tag == 'title': self.in_title = True
        if tag in BLOCK: self.flush()
        if self.shown():
            if tag in INLINE and self.after_inline and self.line and not self.line.endswith(' '): self.line += ' '
            if tag in HEAD: self.line = HEAD[tag]
            if tag == 'li': self.line = '- '
            if 'print-only' in cls: self.line += '[on paper only] '
    def handle_endtag(self, tag):
        if tag in VOID or tag not in [t for t, _ in self.stack]: return   # a self-closing <path/> or <br/> reaches here with no start tag kept; an end tag nothing opened is ignored
        if tag == 'title': self.in_title = False
        if tag in BLOCK: self.flush()
        while self.stack and self.stack[-1][0] != tag: self.stack.pop()
        if self.stack: self.stack.pop()
        self.after_inline = tag in INLINE
    def handle_data(self, data):
        if self.in_title: self.title += data
        if data.strip(): self.after_inline = False
        if self.shown(): self.line += data


def page_text(path):
    p = Text(); p.feed(path.read_text(encoding='utf-8')); p.flush()
    return f'PAGE: {p.title.strip()}  ({"/" + path.relative_to(PUB).as_posix().removesuffix("index.html")})\n\n' + '\n\n'.join(p.out) + '\n'


def main():
    pages = sorted(PUB.rglob('*.html'), key=lambda q: (q.name != 'index.html' or q.parent != PUB, q.as_posix()))
    assert pages, f'no pages in {PUB}; run build.py first'
    if len(sys.argv) > 1:
        out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
        for q in pages:
            name = (q.relative_to(PUB).as_posix().removesuffix('/index.html').removesuffix('index.html').removesuffix('.html').replace('/', '_') or 'home') + '.txt'
            (out / name).write_text(page_text(q), encoding='utf-8', newline='\n')
        print(f'wrote {len(pages)} pages as text to {out}')
    else:
        print('\n\n'.join(page_text(q) for q in pages))


if __name__ == '__main__':
    main()
