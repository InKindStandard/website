"""Save the Screen's words for the page "What communities could receive" (frame v0.6, section 6.1; decision sheet 17, T4).

The Screen draws its cards with its own script, so the words are read from its page as a browser renders it:

    git clone https://github.com/InKindStandard/florida-data-center-screen screen   (then check out the commit to read)
    google-chrome --headless=new --no-sandbox --virtual-time-budget=8000 --dump-dom file://$PWD/screen/index.html > screen_dom.html
    python3 tools/save_screen_words.py screen_dom.html <commit> "<day read, as 18 November 2026>"

It writes the key "page" of src/screen_saved.json and leaves every other key as it was. It stops, and writes nothing, if the
Screen does not draw 36 cards, if Home's three cards differ from the saved copy in any field, if a group's count differs from
its cards, or if a passage it quotes is not where it was. The data center project and the Core project own the words; until the
Core project releases them as a data file, this saved copy is what the site quotes and the check holds every quoted word to.
"""
import html
import json
import pathlib
import re
import sys

SAVED = pathlib.Path(__file__).resolve().parent.parent / 'src' / 'screen_saved.json'
CARD_GROUPS = ['Drafted in the model instruments', 'Set aside: in the model instruments, not relied on',
               'Other items allowed in Florida (not county items)', 'Not allowed in Florida (for comparison)']
SET_ASIDE_NOTE = 'These are in the model instruments but are not relied on as benefits.'
LAW_INTRO_END = '(Open Legal Questions, Question 1).'   # the paragraph's first four sentences, with the limit on how a county is drawn into a private agreement (run 26, Must fix 1)
DESCRIBES = 'It describes; it does not recommend a change.'
ABOUT_END = 'the site and the terms agreed.'   # "About the descriptions", to its sentences on what a description is not (run 26, Should fix 5)


def text(s):
    s = re.sub(r'<button[^>]*class="info"[^>]*>.*?</button>', '', s, flags=re.S)   # the Screen's "i" buttons are controls, not words
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', s))).strip()


def one(rx, s):
    m = re.findall(rx, s, flags=re.S)
    return text(m[0]) if m else ''


def stop(msg):
    sys.exit(f'save_screen_words: {msg}; nothing written')


def main(dom_path, commit, read):
    dom = pathlib.Path(dom_path).read_text(encoding='utf-8')
    saved = json.loads(SAVED.read_text(encoding='utf-8'))
    cards = [(m.start(), m.group(2), m.group(3)) for m in re.finditer(r'<article class="item( muted)?" data-id="([^"]+)">(.*?)</article>', dom, flags=re.S)]
    if len(cards) != 36: stop(f'the Screen draws {len(cards)} cards, not 36')
    heads = [(m.start(), text(m.group(1))) for m in re.finditer(r'<h3>(.*?)</h3>', re.sub(r'<article class="item.*?</article>', lambda a: ' ' * len(a.group(0)), dom, flags=re.S), flags=re.S)]
    items = []
    for pos, iid, c in cards:
        it = {'id': iid, 'sec': one(r'<div class="sec">(.*?)</div>', c), 'name': one(r'<h3>(.*?)</h3>', c),
              'verdict': one(r'<span class="verdict [^"]*">(.*?)</span>', c), 'vsub': one(r'<span class="vsub">(.*?)</span>', c) or None,
              'hnote': one(r'<p class="hnote">(.*?)</p>', c) or None, 'evLabel': one(r'<span class="evl">(.*?)</span>', c),
              'evStatus': one(r'<div class="ev"[^>]*>.*?<b>(.*?)</b>', c), 'evText': one(r'<span class="evt">(.*?)</span>', c),
              'lead': one(r'<p class="lead">(.*?)</p>', c), 'chips': [text(x) for x in re.findall(r'<span class="pl[^"]*"[^>]*>(.*?)</span>', c, flags=re.S)],
              'tried': one(r'<span class="dn [^"]*">(.*?)</span>', c)}
        before = [h for p, h in heads if p < pos and any(h.startswith(g) for g in CARD_GROUPS)]
        if not before: stop(f'card {iid} has no group heading before it')
        it['group'] = before[-1]
        items.append(it)
    by_id = {i['id']: i for i in items}
    for s in saved['items']:
        for k, v in s.items():
            if by_id[s['id']].get(k) != v: stop(f'Home\'s card {s["id"]}: {k} reads {by_id[s["id"]].get(k)!r} on the Screen and {v!r} in the saved copy')
    groups = []
    for g in CARD_GROUPS:
        heading = [h for h in dict.fromkeys(i['group'] for i in items) if h.startswith(g)]
        if len(heading) != 1: stop(f'the group "{g}" is not one heading')
        m = re.fullmatch(re.escape(g) + r' (\d+)', heading[0])
        members = [i for i in items if i['group'] == heading[0]]
        if not m or int(m.group(1)) != len(members): stop(f'the group "{heading[0]}" has {len(members)} cards')
        groups.append({'title': g, 'count': len(members), 'items': [{k: v for k, v in i.items() if k != 'group'} for i in members]})
    note = re.search(r'<summary>Set aside \((\d+)\): why each one is not counted</summary>\s*<p class="note">(.*?)</p>', dom, flags=re.S)
    if not note or not text(note.group(2)).startswith(SET_ASIDE_NOTE): stop('the note on the items set aside is not where it was')
    groups[1]['note'] = text(note.group(2))
    P_ = r'((?:(?!</p>).)*)'   # a paragraph's content, never past its own end
    std = re.search(r'<summary>(Standards: what every project must meet)</summary>\s*<div class="tbody">\s*<p>' + P_ + r'</p>\s*<ul>((?:(?!</ul>).)*)</ul>\s*<p class="note">' + P_ + r'</p>\s*<p class="note">' + P_ + '</p>', dom, flags=re.S)
    if not std: stop('the standards are not where they were')
    names = [text(b).rstrip('.') for b in re.findall(r'<li>\s*<b>(.*?)</b>', std.group(3), flags=re.S)]
    numbers = text(std.group(4))   # the whole paragraph: the bar on weighing any agreement or gift, and the timing limit (run 26, Must fix 2)
    if len(names) != 9 or not numbers.startswith('Every number in that ordinance'): stop(f'the standards read {len(names)} names and "{numbers[:40]}"')
    standards = {'summary': text(std.group(1)), 'lead': text(std.group(2)), 'names': names, 'numbers': numbers, 'evidence': text(std.group(5))}
    law = re.search(r'<span id="ds-h">(.*?)</span>\s*</summary>\s*<div class="key kb">\s*<p class="note" id="dscount">(.*?)</p>\s*<p class="note">(.*?)</p>\s*<div id="decide">(.*?)</div>\s*</div>\s*</details>', dom, flags=re.S)
    if not law: stop('the section on Florida law is not where it was')
    intro = text(law.group(3))
    if LAW_INTRO_END not in intro or DESCRIBES not in intro: stop('the law section\'s opening paragraph changed')
    lgroups = []
    for gm in re.finditer(r'<h3 class="dgh">(.*?)<span class="dgc">(\d+)</span>\s*</h3>\s*<p class="note">(.*?)</p>(.*?)(?=<h3 class="dgh">|$)', law.group(4), flags=re.S):
        its = [{'name': text(s), 'would': text(w) if w else None}
               for s, w in re.findall(r'<details class="story">\s*<summary>(.*?)</summary>\s*(?:<p class="sout">\s*(<b>What it would do:</b>.*?)</p>)?', gm.group(4), flags=re.S)]
        if len(its) != int(gm.group(2)): stop(f'the law group "{text(gm.group(1))}" has {len(its)} items, not {gm.group(2)}')
        lgroups.append({'title': text(gm.group(1)), 'count': len(its), 'note': text(gm.group(3)), 'items': its})
    count_line = text(law.group(2))
    if count_line != f'{sum(g["count"] for g in lgroups)} of these apply to data centers.': stop(f'the law section\'s count line reads "{count_line}"')
    if [i['name'] for i in lgroups[0]['items']] != [i['name'] for i in groups[3]['items']]: stop('the law section\'s first group is not the 11 cards State law does not allow')
    if lgroups[0]['count'] != saved['counts']['state_law_does_not_allow']: stop(f'the law section has {lgroups[0]["count"]} items State law does not allow; Home\'s saved count is {saved["counts"]["state_law_does_not_allow"]}')   # run 27, Should fix 4
    about = re.search(r'<p>\s*<b>(About the descriptions)\.</b>(.*?)</p>', dom, flags=re.S)
    if not about or ABOUT_END not in text(about.group(2)): stop('"About the descriptions" is not where it was')
    nt = re.search(r'<p>\s*<b>(What this is not)\.</b>(.*?)</p>', dom, flags=re.S)
    caution = re.findall(r'<p[^>]*>(This page is not a county document\.[^<]*)</p>', dom)
    if not nt or len(set(caution)) != 1: stop('"What this is not" or the line on county staff is not where it was')
    saved['page'] = {'read': read, 'commit': commit,
                     'note': 'Words saved from the Screen for the page What communities could receive, as the Screen drew them on the day read (tools/save_screen_words.py).',
                     'caution': text(caution[0]), 'standards': standards, 'groups': groups,
                     'law': {'title': text(law.group(1)), 'count_line': count_line, 'intro': intro[:intro.index(LAW_INTRO_END) + len(LAW_INTRO_END)], 'describes': DESCRIBES, 'groups': lgroups},
                     'not_this': {'title': nt.group(1), 'text': text(nt.group(2))},
                     'descriptions': {'title': about.group(1), 'text': text(about.group(2))[:text(about.group(2)).index(ABOUT_END) + len(ABOUT_END)]}}
    SAVED.write_text(json.dumps(saved, ensure_ascii=False, indent=1), encoding='utf-8')   # the file's own format, so that only the new key shows as changed
    print(f'saved: {len(items)} cards in {len(groups)} groups ({", ".join(str(g["count"]) for g in groups)}), '
          f'{len(standards["names"])} standards, {sum(g["count"] for g in lgroups)} items under the law, read {read} at {commit[:7]}')


if __name__ == '__main__':
    if len(sys.argv) != 4: sys.exit(__doc__)
    main(*sys.argv[1:])
