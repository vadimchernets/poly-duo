"""Duo 6.11 probe (No.45 of the list, the 6.11 check: fable, opus): a shortcut of ~30 actions that answers, on the
iPhone itself and in a minute, what the 6 000-action Duo depends on and what no test on a Mac can see:

  * each host of the search answers from the phone (news.google.com, <lang>.wikipedia.org, www.bing.com,
    html.duckduckgo.com) and gives what Duo tests for (an RSS item, a Wikipedia page, a DuckDuckGo result);
  * the reader r.jina.ai gives a page as text (and a Google News card is not needed: Duo looks those up in Bing);
  * «Get Time Between Dates» counts days from the text «2026-11-22» made a date (and which sign it gives);
  * «Filter Files» sorts text lines by Name, Z→A (Duo orders its cards by it; without it the order stays the engines');
  * every «Allow» window comes up here — tap «Always Allow»; Duo's own Setup asks for the same hosts.

The report is shown and copied: one line per check, «OK» or what came back. Build: python3 src/build_probe.py ru
(dist/probe/Duo-probe-<lang>.shortcut, unsigned; tools/build_probe.sh signs it)."""
import os
import plistlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shortcut_actions import (ROOT, Locale, act_clipboard, act_count_chars, act_date, act_download,  # noqa: E402
                              act_first_match, act_text, act_time_between, attachment, new_uuid, text_token)
import shortcut_search as S  # noqa: E402
from shortcut_validate import validate  # noqa: E402

CHECKS = (('<item', 'news.google.com'), ('"fullurl"', 'wikipedia.org'), ('<item', 'bing.com/news'),
          ('result__a', 'duckduckgo.com'))


def actions(lang):
    L = Locale(lang)
    u = new_uuid
    acts, lines = [], []
    addresses = S.warm_up_addresses(L)
    # the four search hosts: the size of the answer and whether it holds what Duo tests for
    for url in addresses[:-1]:
        dl, txt, n, hit = u(), u(), u(), u()
        test = next(t for t, h in CHECKS if h in url)
        acts += [act_download(url.replace('q=duo', 'q=Apple%20CEO'), dl),
                 act_text(text_token('{C}', {'C': (dl, 'Contents of URL')}), txt),
                 act_count_chars(txt, 'Text', n),
                 act_first_match(txt, 'Text', test, hit)]
        lines.append((url.split('/')[2] + ': {N} chars, «' + test + '» {H}', {'N': (n, 'Count'), 'H': (hit, 'Matches')}))
    # the reader: a page as text
    dl, txt, n, ok = u(), u(), u(), u()
    acts += [act_download(S.READER + 'https://en.wikipedia.org/wiki/Shortcuts_(app)', dl),
             act_text(text_token('{C}', {'C': (dl, 'Contents of URL')}), txt),
             act_count_chars(txt, 'Text', n),
             act_first_match(txt, 'Text', S.READER_OK_RX, ok)]
    lines.append(('r.jina.ai: {N} chars, «Markdown Content:» {H}', {'N': (n, 'Count'), 'H': (ok, 'Matches')}))
    # the age of a card: «2026-11-22» → a date → days to today
    day, date, now, days = u(), u(), u(), u()
    acts += [act_text(text_token('2026-11-22'), day),
             {'WFWorkflowActionIdentifier': 'is.workflow.actions.detect.date',
              'WFWorkflowActionParameters': {'WFInput': attachment(day, 'Text'), 'UUID': date}},
             act_date(now),
             act_time_between(now, 'Date', date, 'Dates', 'Days', days)]
    lines.append(('2026-11-22 → {D} days (Duo takes it without its sign)', {'D': (days, 'Time Between Dates')}))
    # the order of the cards: three lines sorted by Name, Z→A — expected 2026-11-22, 2026-10-01, the undated one
    three, split, srt, joined = u(), u(), u(), u()
    acts += [act_text(text_token('2026-10-01 old\n\tundated\n2026-11-22 new'), three),
             {'WFWorkflowActionIdentifier': 'is.workflow.actions.text.split',
              'WFWorkflowActionParameters': {'text': text_token('{T}', {'T': (three, 'Text')}),
                                             'WFTextSeparator': 'New Lines', 'UUID': split}},
             {'WFWorkflowActionIdentifier': 'is.workflow.actions.filter.files',
              'WFWorkflowActionParameters': {'WFContentItemInputParameter': attachment(split, 'Split Text'),
                                             'WFContentItemSortProperty': 'Name',
                                             'WFContentItemSortOrder': 'Z to A', 'UUID': srt}},
             {'WFWorkflowActionIdentifier': 'is.workflow.actions.text.combine',
              'WFWorkflowActionParameters': {'text': attachment(srt, 'Files'), 'WFTextSeparator': 'Custom',
                                             'WFTextCustomSeparator': ' | ', 'UUID': joined}}]
    lines.append(('sort Z→A: {S} (expected: 2026-11-22 new | 2026-10-01 old | undated)', {'S': (joined, 'Text')}))
    # the report
    refs, body = {}, []
    for k, (line, r) in enumerate(lines):
        for name, ref in r.items():
            refs[f'{name}{k}'] = ref
            line = line.replace('{' + name + '}', '{' + f'{name}{k}' + '}')
        body.append(line)
    report = u()
    acts += [act_text(text_token('Duo probe ' + lang + '\n' + '\n'.join(body), refs), report),
             act_clipboard(attachment(report, 'Text')),
             {'WFWorkflowActionIdentifier': 'is.workflow.actions.showresult',
              'WFWorkflowActionParameters': {'Text': text_token('{R}', {'R': (report, 'Text')})}}]
    return acts


def write(lang):
    acts = actions(lang)
    validate(acts)
    workflow = plistlib.loads((ROOT / 'src' / 'metadata.plist').read_bytes())
    workflow['WFWorkflowIcon'] = {'WFWorkflowIconStartColor': 4282601983, 'WFWorkflowIconGlyphNumber': 59511}
    workflow['WFWorkflowTypes'] = []
    workflow['WFWorkflowInputContentItemClasses'] = []
    workflow['WFWorkflowActions'] = acts
    out_dir = Path(os.environ.get('C1_DIST', ROOT / 'dist')) / 'probe'
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'Duo-probe-{lang}.shortcut'
    with out.open('wb') as f:
        plistlib.dump(workflow, f, fmt=plistlib.FMT_BINARY)
    print(f'{lang}: {out.name} — {len(acts)} actions')
    return out


if __name__ == '__main__':
    for lang in sys.argv[1:] or ['ru', 'en']:
        write(lang)
