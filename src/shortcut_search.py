"""Duo 6.11: search without keys, done by the shortcut itself, in three depths (the owner's decisions of 23.11.2026).

«Ask Claude» has no web search and «Ask ChatGPT» answered fresh questions from memory (the 22.11 timings on the
iPhone), so Duo fetches the sources itself and hands them to the models as numbered DATA:

  * search (every depth): one short Claude call writes 2–3 queries from the question's own words (one in English) or
    NONE for a question the web cannot help (science, how-to, a pasted text) — then nothing is fetched. Each model
    gets its OWN engines, all of them at once (no fallback chain): Claude — Google News RSS + Wikipedia + SearXNG,
    ChatGPT — Bing News RSS + Bing web RSS + DuckDuckGo (SHARED_SOURCES: one common set for both). An engine that
    answers with a captcha, a rate limit or nothing is skipped without a word. Duo glues reprints (one link, one
    headline = one card), orders the cards by age (this week; this quarter and the undated web pages; older — not by
    popularity, never by how many engines found them) and numbers at most CARDS_MAX: [C1]… for Claude, [G1]… for
    ChatGPT. The packet (no links) goes to the model; the list with links is what Duo itself prints under the result.
  * check (the default depth, «Critique»): after the two answers one Claude call names at most CLAIMS_MAX claims the
    answers diverge on, or on which the conclusion rests (a date, a number, a condition) — with a query and, when it
    knows one, the primary source's site. Duo searches for each, reads the first page and asks Claude in a separate
    short call whether the page supports the claim: [V1]… The pages ChatGPT cited are read the same way.
  * deep research: before the answers, each model researches its own cards — picks up to PICK_MAX pages, Duo reads
    them in parts of CHUNK characters (each part one short call of THAT model), the model says whether it has enough
    or gives one new query; a second round adds cards [C9]…, reads up to PICK2_MAX more pages; each model then
    answers from its notes.

Every network step sits behind the guard that cannot throw (network_guard) and behind a test of the downloaded
text; every AI call here is a short one (split=False, no [[MORE]]), each well under the 30 s iOS gives one action.

A record is one line: DATE<tab>PUBLISHER<tab>TITLE<tab>URL (DATE may be empty: a web page without a date). The
regexes below are ICU (Shortcuts) and are written in the subset Python's `re` shares, so tests/test_search.py runs the
same pipelines on saved answers of the services.
"""
import os

from shortcut_actions import *  # noqa: F401,F403
from shortcut_actions import iso_date  # noqa: F401

# ---- the builder's setting (fable, 23.11): one common set of sources for both models instead of two different ones
SHARED_SOURCES = os.environ.get('C1_SHARED_SOURCES') == '1'

CARDS_MAX = 8             # cards in one model's packet (the owner: «not more than ~8 best cards»)
ROUND2_MAX = 4            # deep research: cards added by the second round ([C9]…[C12])
RECORDS_SEEN = 20         # records ordered by age before the cut to CARDS_MAX
QUERY_CHARS = 100         # the question's first line as the query when the query call gave nothing
QUERY_MAX = 90            # one query from the model, at most this long
LINK_MAX = 2              # check: pages ChatGPT cited that are read (each: one short Claude call)
CLAIMS_MAX = 2            # check: claims searched by the divergence search
PAGE_CHARS = 3000         # check: of a page's text go to the claim or link check
PICK_MAX, PICK2_MAX = 3, 2  # deep: pages read in the first and in the second round
CHUNK = 3500              # deep: one reading call gets this many characters of a page; a page is read in CHUNKS parts
CHUNKS = 2
AGE_BUCKETS = (8, 91)     # this week (age < 8 days), this quarter (< 91) and the undated, the rest

# ---- engines. {Q}: the URL-encoded query; {LOC}: the build's language/country (ui «search.*»), or the English one
WIKI_URL = ('https://{LANG}.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch={Q}&gsrlimit=1'
            '&prop=extracts%7Cinfo%7Crevisions&exintro=1&explaintext=1&exchars=400&inprop=url&rvprop=timestamp'
            '&format=json&utf8=1')
ENGINES = {
    # Claude's side
    'gnews': {'side': 'C', 'url': 'https://news.google.com/rss/search?q={Q}&{LOC}', 'loc': 'search.news',
              'en': 'hl=en-US&gl=US&ceid=US:en', 'test': '<item', 'kind': 'rss', 'desc': False},
    'wiki': {'side': 'C', 'url': WIKI_URL, 'loc': 'search.wiki', 'en': None, 'test': '"fullurl"', 'kind': 'wiki'},
    'searx': {'side': 'C', 'url': 'https://searx.be/search?q={Q}&format=rss&language={LOC}', 'loc': 'search.wiki',
              'en': None, 'test': '<item', 'kind': 'rss', 'desc': True},
    # ChatGPT's side
    'bingnews': {'side': 'G', 'url': 'https://www.bing.com/news/search?q={Q}&format=RSS&{LOC}', 'loc': 'search.bing',
                 'en': 'mkt=en-US', 'test': '<item', 'kind': 'rss', 'desc': True},
    # Bing web's pubDate is the day Bing indexed the page, not the day it was written: its cards stay undated
    'bingweb': {'side': 'G', 'url': 'https://www.bing.com/search?q={Q}&format=rss&{LOC}', 'loc': 'search.bing',
                'en': 'mkt=en-US', 'test': '<item', 'kind': 'rss', 'desc': True, 'dated': False},
    'ddg': {'side': 'G', 'url': 'https://html.duckduckgo.com/html/?q={Q}&{LOC}', 'loc': 'search.ddg',
            'en': None, 'test': 'result__a', 'kind': 'ddg'},
}
SIDE_ENGINES = {'C': ('gnews', 'wiki', 'searx'), 'G': ('bingnews', 'bingweb', 'ddg')}
# the English query goes to the engines that have an English edition
EN_ENGINES = ('gnews', 'bingnews', 'bingweb')
# the divergence search looks for a primary source: the web index first, the news index when the web gave nothing
CLAIM_ENGINES = ('bingweb', 'bingnews')

# ---- parsing: each kind of answer → record lines (pairs of ICU find / replace, applied in order)
MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
_ONE_LINE = (r'\s+', ' ')
_SPLIT_ITEMS = (r'<item\b', '\n<item')
_ITEM_END = (r'</item>', '</item>\n')


def rss_pairs(desc, dated=True):
    """An RSS 2.0 answer (Google News, Bing News, Bing web, SearXNG) → record lines. Each <item> becomes one line,
    and the fields are read by lookaheads, so their order and absence do not matter: title, link, pubDate
    («Sun, 22 Nov 2026 …» → 2026-Nov-22, the month made a number below), the publisher (<source> of Google News,
    <News:Source> of Bing News; else taken from the link's host later) and, where it is plain text, the description
    (Bing's snippet; Google's is HTML of links and is not read)."""
    snippet = r'(?=(?:[^\n]*?<description>(?:<!\[CDATA\[)?([^<\n]{1,220}))?)' if desc else '()'
    item = (r'(?m)^<item\b(?=[^\n]*?<title>(?:<!\[CDATA\[)?([^\n]*?)(?:\]\]>)?</title>)'
            r'(?=[^\n]*?<link>(?:<!\[CDATA\[)?([^\n<\]]+)(?:\]\]>)?</link>)'
            r'(?=(?:[^\n]*?<pubDate>[A-Za-z]{3}, (\d{1,2}) ([A-Za-z]{3}) (\d{4}))?)'
            r'(?=(?:[^\n]*?<(?:News:Source|source)\b[^>]*>([^<\n]*)<)?)' + snippet + r'[^\n]*$')
    return (_ONE_LINE, _SPLIT_ITEMS, _ITEM_END, (item, ('$5-$4-$3' if dated else '--') + '\t$6\t$1 — $7\t$2'))


# DuckDuckGo's HTML page: each result's link and title, its snippet when there is one (the link is DDG's redirect)
DDG_PAIRS = (
    _ONE_LINE,
    (r'<a\b[^>]*?class="result__a"', '\n<ddg>'),
    (r'(?m)^<ddg>[^>]*?href="([^"]+)"[^>]*>(.*?)</a>(?=(?:.*?class="result__snippet"[^>]*>(.*?)</a>)?)[^\n]*$',
     '--\t\t$2 — $3\t$1'),
)
# Wikipedia (gsrlimit=1: one page in the answer)
WIKI_TITLE_RX = r'(?<="title":")(?:[^"\\]|\\.)+'
WIKI_DATE_RX = r'(?<="timestamp":")\d{4}-\d\d-\d\d'
WIKI_LINK_RX = r'(?<="fullurl":")[^"\s]+'
WIKI_TEXT_RX = r'(?<="extract":")(?:[^"\\]|\\.)+'

# ---- the records of a side, after all its engines: one clean form
RECORD_RX = r'^(\d{4}-\d\d-\d\d)?\t([^\t\n]*)\t([^\t\n]+)\t(\S+)[ \t]*$'
NOT_RECORD_RX = r'(?m)^(?!(?:\d{4}-\d\d-\d\d)?\t[^\t\n]*\t[^\t\n]+\t\S+[ \t]*$)[^\n]*\n?'
CLEAN_PAIRS = (
    *((r'(?m)^(\d{4})-%s-' % m, '$1-%02d-' % (i + 1)) for i, m in enumerate(MONTHS)),
    (r'(?m)^(\d{4}-\d\d)-(\d)\t', '$1-0$2\t'),
    (r'(?m)^--\t', '\t'),
    # Bing News and DuckDuckGo hand out their own redirect; the real address stands inside it
    (r'https?://www\.bing\.com/news/apiclick\.aspx\?[^\t\n]*?url=([^&\t\n]+)[^\t\n]*', '$1'),
    (r'(?:https?:)?//duckduckgo\.com/l/\?uddg=([^&\t\n]+)[^\t\n]*', '$1'),
    (r'(?i)%3a', ':'), (r'(?i)%2f', '/'), (r'(?i)%3f', '?'), (r'(?i)%3d', '='), (r'(?i)%26', '&'),
    (r'&amp;', '&'), (r'&quot;|&#34;', '"'), (r'&#39;|&#x27;|&apos;', "'"), (r'&nbsp;|&#160;', ' '),
    (r'&lt;', '<'), (r'&gt;', '>'), (r'<[^>\n]*>', ''),
    # the snippet's separator when there was no snippet
    (r' — [ ]*(?=\t)', ''),
    # no publisher in the answer → the link's host (www. and m. off)
    (r'(?m)^([^\t\n]*)\t\t([^\t\n]+)\t(https?://(?:www\.|m\.)?([^/\s]+)\S*)[ \t]*$', '$1\t$4\t$2\t$3'),
    # Google News ends a headline with « - Publisher»
    (r'(?m)^([^\t\n]*\t([^\t\n]+)\t[^\t\n]*?) - \2(?=\t| — )', '$1'),
    (r'(?m)^ +| +$', ''),
    (NOT_RECORD_RX, ''),
)
# one origin once: a later line with the same link, or a headline that starts the same way — a reprint of one wire
# story in five papers is one piece of evidence, not five. Two different stories of one publisher both stay: how many
# DIFFERENT publishers report a thing is a signal the model reads from the cards, not a filter of Duo's.
SAME_URL_RX = (r'(?m)^([^\n]*\t(\S+)\n(?:[^\n]*\n)*?)[^\n]*\t\2\n', '$1')
SAME_TITLE_RX = (r'(?im)^([^\t\n]*\t[^\t\n]*\t([^\t\n]{25})[^\n]*\n(?:[^\n]*\n)*?)[^\t\n]*\t[^\t\n]*\t\2[^\n]*\n',
                 '$1')
DEDUP_PASSES = 3
SEEN_RX = r'\A(?:[^\n]*\n){1,%d}' % RECORDS_SEEN
RECORD_LINES_RX = r'(?m)^[^\n]*\t[^\n]+$'
MARK = '§ '               # stands where Duo puts the number
NUMBER_RX = r'(?s)\A(.*?)§ '

# ---- the query call's answer: list marks and quotes off; NONE = no search
QUERY_CLEAN_RX = r'(?m)^[\s\-\*•\d\.\)"«“„]+|["»”]+[ \t]*$'
QUERY_LINE_RX = r'\A[^\n]{3,%d}' % QUERY_MAX
QUERY_REST_RX = r'\A[^\n]*\n+'
NONE_RX = r'\A\s*NONE\b'
QUESTION_RX = r'\A\s*[^\n]{1,%d}' % QUERY_CHARS

# ---- links and pages
_U = r'https?://[^\s\)\]>"\'»”]*[^\s\)\]>"\'»”.,;:!?]'
LINK_RX = _U
LINK1_RX = (r'(?s)\A.*?(' + _U + r').*\z', '$1')
LINK2_RX = (r'(?s)\A.*?(' + _U + r').*?(?!\1)(' + _U + r').*\z', '$2')
LINK2_TEST_RX = r'(?s)(' + _U + r').*?(?!\1)(' + _U + r')'
HTML_STRIP = ((r'(?is)<(script|style|noscript|svg|head)\b.*?</\1>', ' '), (r'(?s)<[^>]+>', ' '),
              (r'&nbsp;|&#160;', ' '), (r'\s{2,}', ' '))
PAGE_RX = r'(?s)\A.{1,%d}' % PAGE_CHARS
CHUNK1_RX = r'(?s)\A.{1,%d}' % CHUNK
CHUNK2_RX = (r'(?s)\A.{%d}(.{1,%d}).*\z' % (CHUNK, CHUNK), '$1')

# ---- the divergence search: «claim || query || site» per line, at most CLAIMS_MAX lines
CLAIM_LINE_RX = r'(?m)^[^\n|]{4,}\|\|[^\n|]{3,}(?:\|\|[^\n|]*)?$'
CLAIM_REST_RX = r'\A[^\n]*\n+'
CLAIM_TEXT_RX = (r'\A\s*([^|]*?)\s*\|\|.*\z', '$1')
CLAIM_QUERY_RX = (r'\A[^|]*\|\|\s*([^|]*?)\s*(?:\|\|.*)?\z', '$1')
CLAIM_SITE_RX = (r'\A[^|]*\|\|[^|]*\|\|\s*(?:https?://)?(?:www\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)+)\S*\s*\z', ' site:$1')
CLAIM_NO_SITE_RX = r'\A[^|]*\|\|[^|]*\|\|\s*(?:https?://)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+'
FIRST_RECORD_RX = r'\A[^\n]+'

# ---- deep research: the card numbers a model picked, the line with its next query
ENOUGH_RX = r'(?i)\A\s*(?:ENOUGH|NONE)\b'
MORE_QUERY_RX = (r'(?is)\A\s*(?:QUERY\s*:\s*)?([^\n]{3,%d}).*\z' % QUERY_MAX, '$1')
PICK_CODE_RX = r'\A\S+'
PICK_URL_RX = r'\S+\z'

# ---- variables
NET, QUERIES = 'PolyNet', 'PolyQueries'
DEEP, QUICK = 'PolyDeep', 'PolyQuick'           # set by the menu; neither = the default depth, «check»
CHECKS, PAGE, VERDICT = 'PolyChecks', 'PolyPage', 'PolyVerdict'
LIST_V = 'PolySourceListV'
CLAIMS, PICKS, NEWCARDS = 'PolyClaims', 'PolyPicks', 'PolyNewCards'
CITED = 'PolyCited'


def prefixes():
    """The letters of the packets: Claude's and ChatGPT's own sets, or one shared set."""
    return ('S',) if SHARED_SOURCES else ('C', 'G')


def side_of(model):
    """The packet a model reads: 'C' for Claude, 'G' for ChatGPT; with SHARED_SOURCES both read 'S'."""
    return 'S' if SHARED_SOURCES else model


def records_var(side):
    return 'PolyRecords' + side


def packet_var(side):
    return 'PolySources' + side


def list_var(side):
    return 'PolySourceList' + side


def notes_var(model):
    return 'PolyNotes' + model


def cited_rx(prefix, n):
    """[C3] in a text, also inside «[C1, C3]» or «[G2; C3]»; never [C30]."""
    other = r'[A-Z]?\d+'
    return r'\[(?:%s\s*[,;]\s*)*%s%d(?:\s*[,;]\s*%s)*\]' % (other, prefix, n, other)


def source_entry_rx(prefix, n):
    """Entry [<prefix>n] of a source list: its line and the link under it."""
    return r'(?m)^\[%s%d\] [^\n]*(?:\n(?!\[[A-Z]?\d+\] )[^\n]+)?' % (prefix, n)


def entry_url_rx(prefix, n):
    return r'(?m)(?<=^\[%s%d\] )[^\n]*\n\S+' % (prefix, n)


def u():
    return new_uuid()


def append_to(var, template, refs, special=None):
    """<var> = <var> + a text ({V} is the variable's present text; an unset variable reads as nothing)."""
    get, txt = u(), u()
    return [act_get_variable(var, get),
            act_text(text_token('{V}' + template, {**refs, 'V': (get, 'Variable')}, special), txt),
            act_set_variable(var, txt, 'Text')]


def replace_var(var, pairs, times=1):
    """Run the regex replacements `pairs` on the variable's text, in place."""
    get, out = u(), []
    out.append(act_get_variable(var, get))
    src = (get, 'Variable')
    for _ in range(times):
        for find, repl in pairs:
            r = u()
            out.append(act_replace_regex(src[0], src[1], find, repl, r))
            src = (r, 'Updated Text')
    return out + [act_set_variable(var, *src)]


def pipeline(src, pairs):
    """Replace actions on an output; returns (actions, (uid, 'Updated Text') of the last)."""
    out = []
    for find, repl in pairs:
        r = u()
        out.append(act_replace_regex(src[0], src[1], find, repl, r))
        src = (r, 'Updated Text')
    return out, src


def parse_pairs(engine):
    spec = ENGINES[engine]
    return rss_pairs(spec['desc'], spec.get('dated', True)) if spec['kind'] == 'rss' else DDG_PAIRS


def engine_address(L, engine, english=False):
    spec = ENGINES[engine]
    loc = spec['en'] if english and spec['en'] else L[spec['loc']]
    return spec['url'].replace('{LOC}', loc).replace('{LANG}', L['search.wiki'])


def fetch(L, engine, query, target, english=False):
    """One search: the answer is read as text; only when it holds what a real answer holds (`test`: an RSS item, a
    DDG result, a Wikipedia page — a captcha, a rate limit or an error page does not) it is turned into record lines
    and added to the variable `target`. `query`: (uid, output) of the query text."""
    spec = ENGINES[engine]
    enc, url, dl, txt, g = (u() for _ in range(5))
    acts = [act_urlencode(query[0], query[1], enc),
            act_text(text_token(engine_address(L, engine, english), {'Q': (enc, 'URL Encoded Text')}), url),
            act_download(text_token('{U}', {'U': (url, 'Text')}), dl),
            act_text(text_token('{C}', {'C': (dl, 'Contents of URL')}), txt),
            if_output(g, txt, 'Text', 99, WFConditionalActionString=spec['test'])]
    if spec['kind'] == 'wiki':
        title, date, link, body = u(), u(), u(), u()
        acts += [act_first_match(txt, 'Text', WIKI_TITLE_RX, title),
                 act_first_match(txt, 'Text', WIKI_DATE_RX, date),
                 act_first_match(txt, 'Text', WIKI_LINK_RX, link),
                 act_first_match(txt, 'Text', WIKI_TEXT_RX, body),
                 *append_to(target, '\n{D}\t' + L['search.wiki_label'] + '\t{T}: {B}\t{U}\n',
                            {'D': (date, 'Matches'), 'T': (title, 'Matches'), 'B': (body, 'Matches'),
                             'U': (link, 'Matches')})]
    else:
        steps, last = pipeline((txt, 'Text'), parse_pairs(engine))
        acts += [*steps, *append_to(target, '\n{R}\n', {'R': last})]
    return acts + [if_close(g)]


def clean_records(var):
    """The records of a side: one form, reprints glued, at most RECORDS_SEEN kept for ordering."""
    return [*replace_var(var, CLEAN_PAIRS),
            *replace_var(var, (SAME_URL_RX, SAME_TITLE_RX), times=DEDUP_PASSES)]


def cards(L, side, now, start, count, records=None, packet=None, listing=None, item='Repeat Item'):
    """Records of `side` → at most `count` cards numbered [<side>start]…, newest first (three age buckets: this
    week; this quarter and the undated web pages; the rest). The packet line (no link, for the models) and the list entry (with
    its link, for the person) are appended to `packet` / `listing` (default: the side's own)."""
    records = records or records_var(side)
    packet = packet or packet_var(side)
    listing = listing or list_var(side)
    b_pack = ['PolyB%dP' % i for i in range(3)]
    b_list = ['PolyB%dL' % i for i in range(3)]
    get, seen, recs, g_rep, it, day, g_day, days, age, p_line, s_line, g_b1, g_b2, num = (u() for _ in range(14))
    acts = [*(a for v in b_pack + b_list for a in clear_variable(v)),
            act_get_variable(records, get),
            act_first_match(get, 'Variable', SEEN_RX, seen),
            act_first_match(seen, 'Matches', RECORD_LINES_RX, recs),
            repeat_open(g_rep, recs, 'Matches'),
            act_get_variable(item, it),
            act_first_match(it, 'Variable', r'^\d{4}-\d\d-\d\d', day),
            if_output(g_day, day, 'Matches', 100),
            act_time_between(now, 'Date', day, 'Matches', 'Days', days),
            act_text(text_token(L['search.age'], {'N': (days, 'Time Between Dates')}), age),
            # for the models: no link (a model can neither open it nor is it to copy it)
            act_replace_regex_token(it, 'Variable', RECORD_RX,
                                    text_token(MARK + '$1 ({A}) · $2 · $3', {'A': (age, 'Text')}), p_line),
            act_replace_regex(it, 'Variable', RECORD_RX, MARK + '$1 · $2 · $3\n$4', s_line),
            # D-100: a number condition takes a Number (or a Count), never another action's output straight
            act_number(days, 'Time Between Dates', num),
            if_output(g_b1, num, 'Number', 0, WFNumberValue=AGE_BUCKETS[0]),
            *append_to(b_pack[0], '{L}\n', {'L': (p_line, 'Updated Text')}),
            *append_to(b_list[0], '{L}\n', {'L': (s_line, 'Updated Text')}),
            if_else(g_b1),
            if_output(g_b2, num, 'Number', 0, WFNumberValue=AGE_BUCKETS[1]),
            *append_to(b_pack[1], '{L}\n', {'L': (p_line, 'Updated Text')}),
            *append_to(b_list[1], '{L}\n', {'L': (s_line, 'Updated Text')}),
            if_else(g_b2),
            *append_to(b_pack[2], '{L}\n', {'L': (p_line, 'Updated Text')}),
            *append_to(b_list[2], '{L}\n', {'L': (s_line, 'Updated Text')}),
            if_close(g_b2),
            if_close(g_b1),
            if_else(g_day)]
    # a record without a date (a web page: an official page, a register, an encyclopedia — what the web index holds
    # now): the middle bucket, «undated» instead of an age
    p2, s2 = u(), u()
    acts += [act_replace_regex(it, 'Variable', RECORD_RX, MARK + L['search.undated'] + ' · $2 · $3', p2),
             act_replace_regex(it, 'Variable', RECORD_RX, MARK + L['search.undated'] + ' · $2 · $3\n$4', s2),
             *append_to(b_pack[1], '{L}\n', {'L': (p2, 'Updated Text')}),
             *append_to(b_list[1], '{L}\n', {'L': (s2, 'Updated Text')}),
             if_close(g_day),
             repeat_close(g_rep)]
    # newest first, cut to `count`, numbered by Duo; NEWCARDS keeps just these cards (deep research picks from them)
    for bucket, target, per in ((b_pack, packet, 1), (b_list, listing, 2)):
        gets = [u() for _ in range(3)]
        joined, cut = u(), u()
        acts += [act_get_variable(v, g) for v, g in zip(bucket, gets)]
        acts += [act_text(text_token('{A}{B}{C}', {'A': (gets[0], 'Variable'), 'B': (gets[1], 'Variable'),
                                                   'C': (gets[2], 'Variable')}), joined),
                 act_first_match(joined, 'Text', r'\A(?:[^\n]*\n){1,%d}' % (count * per), cut)]
        src = (cut, 'Matches')
        for n in range(start, start + count):
            r = u()
            acts.append(act_replace_regex(src[0], src[1], NUMBER_RX, '$1[%s%d] ' % (side, n), r))
            src = (r, 'Updated Text')
        if per == 1:
            acts.append(act_set_variable(NEWCARDS, *src))
        acts += append_to(target, '{N}', {'N': src})
    return acts


def query_lines(L, qsrc, ask_claude, today):
    """The query call: 2–3 queries from the question's words (line 2 in English), or NONE. Leaves QUERIES set
    (cleaned) and returns the actions; the caller tests NONE."""
    qp, qc = u(), u()
    return [act_step('search_queries'),
            act_text(text_token(L.prompt('search-queries'), {'Q': qsrc}, {'TODAY': today}), qp),
            ask_claude(qp, qc),
            act_set_variable(QUERIES, qc, 'Ask Claude'),
            *replace_var(QUERIES, ((QUERY_CLEAN_RX, ''),))]


def search_block(L, qsrc, long_question, ask_claude, now, today):
    """Leaves, per side, the packet (for the model) and the source list (for the person) set or empty; with no
    network, a long pasted text or NONE from the query call, all stay empty and the run goes on from memory.
    `ask_claude(prompt_uid, uid)`: the short «Ask Claude» action; `now`: a Current Date action's uid; `today`: the
    special attachment of today's date."""
    (q_txt, q_cnt, g_long, net_get, g_net, q_all, g_none, none_m, q1, g_q1, q_cut, q_rest, q2, g_q2, q_rest2, q3,
     g_q3, g_deep) = (u() for _ in range(18))
    sides = prefixes()
    acts = [*(a for s in ('C', 'G', 'S') for v in (records_var(s), packet_var(s), list_var(s))
              for a in clear_variable(v)),
            *(a for m in ('C', 'G') for a in clear_variable(notes_var(m))),
            *clear_variable(CHECKS), *clear_variable(LIST_V), *clear_variable(QUERIES),
            act_text(text_token('{Q}', {'Q': qsrc}), q_txt),
            act_count_chars(q_txt, 'Text', q_cnt),
            if_output(g_long, q_cnt, 'Count', 2, WFNumberValue=long_question - 1),
            if_else(g_long),
            *network_guard(NET),
            act_get_variable(NET, net_get),
            if_output(g_net, net_get, 'Variable', 100),
            *query_lines(L, qsrc, ask_claude, today),
            act_get_variable(QUERIES, q_all),
            act_first_match(q_all, 'Variable', NONE_RX, none_m),
            if_output(g_none, none_m, 'Matches', 101),
            act_step('search'),
            # query 1: the model's first line, or the question's first line when the call gave nothing usable
            act_first_match(q_all, 'Variable', QUERY_LINE_RX, q1),
            *set_text('PolyQ1', '{Q}', {'Q': (q1, 'Matches')}),
            if_output(g_q1, q1, 'Matches', 101),
            act_first_match(q_txt, 'Text', QUESTION_RX, q_cut),
            *set_text('PolyQ1', '{Q}', {'Q': (q_cut, 'Matches')}),
            if_close(g_q1)]
    q1_get = u()
    acts.append(act_get_variable('PolyQ1', q1_get))
    for side in ('C', 'G'):
        target = records_var('S' if SHARED_SOURCES else side)
        for engine in SIDE_ENGINES[side]:
            acts += fetch(L, engine, (q1_get, 'Variable'), target)
    # query 2 — English — to the engines with an English edition; query 3 (deep research only) to the same
    acts += [act_replace_regex(q_all, 'Variable', QUERY_REST_RX, '', q_rest),
             act_first_match(q_rest, 'Updated Text', QUERY_LINE_RX, q2),
             if_output(g_q2, q2, 'Matches', 100)]
    for engine in EN_ENGINES:
        side = 'S' if SHARED_SOURCES else ENGINES[engine]['side']
        acts += fetch(L, engine, (q2, 'Matches'), records_var(side), english=True)
    acts += [if_close(g_q2),
             *if_text(g_deep, DEEP),
             act_replace_regex(q_rest, 'Updated Text', QUERY_REST_RX, '', q_rest2),
             act_first_match(q_rest2, 'Updated Text', QUERY_LINE_RX, q3),
             if_output(g_q3, q3, 'Matches', 100)]
    for engine in EN_ENGINES:
        side = 'S' if SHARED_SOURCES else ENGINES[engine]['side']
        acts += fetch(L, engine, (q3, 'Matches'), records_var(side))
    acts += [if_close(g_q3), if_close(g_deep)]
    for side in sides:
        g_any = u()
        acts += [*clean_records(records_var(side)),
                 *if_text(g_any, records_var(side)),
                 *cards(L, side, now, 1, CARDS_MAX),
                 if_close(g_any)]
    return acts + [if_close(g_none), if_close(g_net), if_close(g_long)]


# ------------------------------------------------------------------ reading a page

def read_page(url, cut_rx, target_var):
    """«Get Contents of URL» → «Get Article using Safari Reader»; when the Reader gives nothing, the page's own text
    with the tags taken off. `target_var` gets at most what `cut_rx` keeps (or stays empty)."""
    page, art, art_t, g_blank, html, p_get, cut = (u() for _ in range(7))
    return [act_download(text_token('{U}', {'U': url}), page),
            act_get_article(page, 'Contents of URL', art),
            act_text(text_token('{A}', {'A': (art, 'Article')}), art_t),
            act_set_variable(PAGE, art_t, 'Text'),
            *if_text(g_blank, PAGE, present=False),
            act_text(text_token('{C}', {'C': (page, 'Contents of URL')}), html),
            act_set_variable(PAGE, html, 'Text'),
            *replace_var(PAGE, HTML_STRIP),
            if_close(g_blank),
            act_get_variable(PAGE, p_get),
            act_first_match(p_get, 'Variable', cut_rx, cut),
            act_set_variable(target_var, cut, 'Matches')]


# ------------------------------------------------------------------ check: ChatGPT's links and the divergence search

def link_check_block(L, gpt_var, claude_check, skip_var, today):
    """ChatGPT cited pages → Duo downloads up to LINK_MAX of them and asks Claude about each in a separate short call
    whether the page supports what the answer says. CHECKS gets one line a page. Not in the quick depth; never on a
    run resumed from a draft (`skip_var`): a page that stopped the run once must not stop it again."""
    ans, found, g_has, g_skip, g_quick, net_get, g_net = (u() for _ in range(7))
    acts = [*if_text(g_quick, QUICK, present=False),
            *if_text(g_skip, skip_var, present=False),
            act_get_variable(gpt_var, ans),
            act_first_match(ans, 'Variable', LINK_RX, found),
            if_output(g_has, found, 'Matches', 100),
            *network_guard(NET),
            act_get_variable(NET, net_get),
            if_output(g_net, net_get, 'Variable', 100),
            act_step('link_check')]
    closers = []
    for n in range(1, LINK_MAX + 1):
        link, link_t, g_page, prompt, call, g_v, v_get, cut_get = (u() for _ in range(8))
        if n == 1:
            acts.append(act_replace_regex(ans, 'Variable', LINK1_RX[0], LINK1_RX[1], link))
        else:
            test, g_two = u(), u()
            acts += [act_first_match(ans, 'Variable', LINK2_TEST_RX, test),
                     if_output(g_two, test, 'Matches', 100),
                     act_replace_regex(ans, 'Variable', LINK2_RX[0], LINK2_RX[1], link)]
            closers.append(if_close(g_two))
        acts += [
            act_text(text_token('{U}', {'U': (link, 'Updated Text')}), link_t),
            *read_page((link_t, 'Text'), PAGE_RX, 'PolyPageCut'),
            *if_text(g_page, 'PolyPageCut'),
            act_get_variable('PolyPageCut', cut_get),
            act_text(text_token(L.prompt('link-check'),
                                {'URL': (link_t, 'Text'), 'ANSWER': (ans, 'Variable'), 'PAGE': (cut_get, 'Variable')},
                                {'TODAY': today}), prompt),
            claude_check(prompt, call),
            act_set_variable(VERDICT, call, 'Ask Claude'),
            *if_text(g_v, VERDICT),
            act_get_variable(VERDICT, v_get),
            *append_to(CHECKS, '• ChatGPT → {U} — {V}\n', {'U': (link_t, 'Text'), 'V': (v_get, 'Variable')}),
            if_close(g_v),
            if_else(g_page),
            *append_to(CHECKS, '• ChatGPT → {U} — ' + L['search.link_unread'] + '\n', {'U': (link_t, 'Text')}),
            if_close(g_page),
        ]
    return acts + closers[::-1] + [if_close(g_net), if_close(g_has), if_close(g_skip), if_close(g_quick)]


def divergence_block(L, question, gpt_answer, claude_answer, claude_check, skip_var, today):
    """The owner's main idea of 23.11 (fable, agy, sol, astra): Duo searches where the two answers diverge, or where
    the conclusion rests on one date, number or condition even when they agree. One short Claude call names at most
    CLAIMS_MAX such claims («claim || query || site of the primary source»); for each Duo searches the web index (then
    the news index), reads the first page and asks Claude in its own short call whether the page supports the claim.
    The page becomes source [V<i>] of the list Duo prints; CHECKS gets «[V<i>] claim — verdict». Not in the quick
    depth, not on a resumed run. `question`, `gpt_answer`, `claude_answer`: (uid, output) refs."""
    g_quick, g_skip, net_get, g_net, prompt, call, g_any, c_all = (u() for _ in range(8))
    ga, ca = u(), u()
    acts = [*if_text(g_quick, QUICK, present=False),
            *if_text(g_skip, skip_var, present=False),
            *network_guard(NET),
            act_get_variable(NET, net_get),
            if_output(g_net, net_get, 'Variable', 100),
            act_step('divergence'),
            act_first_chars(gpt_answer[0], gpt_answer[1], 2500, ga),
            act_first_chars(claude_answer[0], claude_answer[1], 2500, ca),
            act_text(text_token(L.prompt('crux'), {'QUESTION': question, 'GPT_ANSWER': (ga, 'Matches'),
                                                   'CLAUDE_OWN': (ca, 'Matches')}, {'TODAY': today}), prompt),
            claude_check(prompt, call),
            act_set_variable(CLAIMS, call, 'Ask Claude'),
            act_get_variable(CLAIMS, c_all)]
    src = (c_all, 'Variable')
    closers = []
    for i in range(1, CLAIMS_MAX + 1):
        line, g_line, claim, query, site, g_site, q_full, g_rec, rec, url, title_line, cut_get, g_page = \
            (u() for _ in range(13))
        p2, call2, g_v, v_get, nsite, title2 = u(), u(), u(), u(), u(), u()
        tmp = 'PolyClaimRecords'
        acts += [act_first_match(src[0], src[1], CLAIM_LINE_RX, line),
                 if_output(g_line, line, 'Matches', 100),
                 act_replace_regex(line, 'Matches', CLAIM_TEXT_RX[0], CLAIM_TEXT_RX[1], claim),
                 act_replace_regex(line, 'Matches', CLAIM_QUERY_RX[0], CLAIM_QUERY_RX[1], query),
                 *set_text('PolyClaimQuery', '{Q}', {'Q': (query, 'Updated Text')}),
                 # a site named for the primary source narrows the web search to it
                 act_first_match(line, 'Matches', CLAIM_NO_SITE_RX, nsite),
                 if_output(g_site, nsite, 'Matches', 100),
                 act_replace_regex(line, 'Matches', CLAIM_SITE_RX[0], CLAIM_SITE_RX[1], site),
                 *set_text('PolyClaimQuery', '{Q}{S}', {'Q': (query, 'Updated Text'), 'S': (site, 'Updated Text')}),
                 if_close(g_site),
                 act_get_variable('PolyClaimQuery', q_full),
                 *clear_variable(tmp)]
        acts += fetch(L, CLAIM_ENGINES[0], (q_full, 'Variable'), tmp)
        g_web = u()
        acts += [*if_text(g_web, tmp, present=False),
                 *fetch(L, CLAIM_ENGINES[1], (query, 'Updated Text'), tmp),
                 if_close(g_web),
                 *clean_records(tmp),
                 *if_text(g_rec, tmp),
                 act_get_variable(tmp, rec)]
        first = u()
        acts += [act_first_match(rec, 'Variable', FIRST_RECORD_RX, first),
                 act_replace_regex(first, 'Matches', RECORD_RX, '$4', url),
                 act_replace_regex(first, 'Matches', RECORD_RX, '[V%d] $1 · $2 · $3\n$4' % i, title_line),
                 act_replace_regex(title_line, 'Updated Text', r'\]  · ', '] ', title2),   # an undated page
                 *append_to(LIST_V, '{L}\n', {'L': (title2, 'Updated Text')}),
                 *read_page((url, 'Updated Text'), PAGE_RX, 'PolyPageCut'),
                 *if_text(g_page, 'PolyPageCut'),
                 act_get_variable('PolyPageCut', cut_get),
                 act_text(text_token(L.prompt('claim-check'),
                                     {'CLAIM': (claim, 'Updated Text'), 'URL': (url, 'Updated Text'),
                                      'PAGE': (cut_get, 'Variable')}, {'TODAY': today}), p2),
                 claude_check(p2, call2),
                 act_set_variable(VERDICT, call2, 'Ask Claude'),
                 *if_text(g_v, VERDICT),
                 act_get_variable(VERDICT, v_get),
                 *append_to(CHECKS, '• [V%d] {C} — {V}\n' % i, {'C': (claim, 'Updated Text'),
                                                               'V': (v_get, 'Variable')}),
                 if_close(g_v),
                 if_else(g_page),
                 *append_to(CHECKS, '• [V%d] {C} — ' % i + L['search.link_unread'] + '\n',
                            {'C': (claim, 'Updated Text')}),
                 if_close(g_page),
                 if_else(g_rec),
                 *append_to(CHECKS, '• {C} — ' + L['search.claim_unfound'] + '\n', {'C': (claim, 'Updated Text')}),
                 if_close(g_rec)]
        rest = u()
        acts.append(act_replace_regex(src[0], src[1], CLAIM_REST_RX, '', rest))
        src = (rest, 'Updated Text')
        closers.append(if_close(g_line))
    # the claims are nested (claim 2 only after a claim 1), so the Ifs close in reverse
    return acts + closers[::-1] + [if_close(g_net), if_close(g_skip), if_close(g_quick)]


# ------------------------------------------------------------------ deep research

def research_block(L, model, side, ask, qsrc, now, today):
    """Deep research of one model (`model`: 'C' Claude or 'G' ChatGPT) on the cards of `side`: it picks up to
    PICK_MAX pages; Duo reads each in up to CHUNKS parts, each part one short call of that model that returns a dated
    note; the model then says ENOUGH or gives one new query; a second round searches the side's own engines, adds up
    to ROUND2_MAX cards and reads up to PICK2_MAX of their pages. NOTES_<model> holds the notes; the model's answer
    is then written from them. `ask(prompt_uid, uid)` → (the short call of that model, its output name)."""
    notes = notes_var(model)
    g_have, g_net, net_get = u(), u(), u()
    acts = [act_step('research'),
            *if_text(g_have, packet_var(side)),
            *network_guard(NET),
            act_get_variable(NET, net_get),
            if_output(g_net, net_get, 'Variable', 100)]

    def pick_and_read(cards_src, start, count, limit):
        """The model picks from the cards in `cards_src` (an output ref), numbered start…start+count-1; the picked
        pages are read part by part. PICKS gets «<code> <url>» lines."""
        p, call, reply = u(), u(), u()
        lst = u()
        out = [*clear_variable(PICKS),
               act_text(text_token(L.prompt('research-pick'), {'Q': qsrc, 'CARDS': cards_src}, {'TODAY': today}), p)]
        a, name = ask(p, call)
        out += [a,
                act_text(text_token('{R}', {'R': (call, name)}), reply),
                act_get_variable(list_var(side), lst)]
        for n in range(start, start + count):
            hit, g, entry = u(), u(), u()
            out += [act_first_match(reply, 'Text', r'(?<![\d])%d(?![\d])' % n, hit),
                    if_output(g, hit, 'Matches', 100),
                    act_first_match(lst, 'Variable', entry_url_rx(side, n), entry),
                    *append_to(PICKS, '%s%d {E}\n' % (side, n), {'E': (entry, 'Matches')}),
                    if_close(g)]
        # «<code> <line>\n<url>» → «<code> <url>», at most `limit` pages
        out += replace_var(PICKS, ((r'(?m)^(\S+) [^\n]*\n(\S+)$', '$1 $2'),))
        pk, firsts, lines, g_rep, it, code, url, cnt, g_more = (u() for _ in range(9))
        out += [act_get_variable(PICKS, pk),
                act_first_match(pk, 'Variable', r'\A(?:[^\n]*\n?){1,%d}' % limit, firsts),
                act_first_match(firsts, 'Matches', r'(?m)^\S+ https?://\S+$', lines),
                repeat_open(g_rep, lines, 'Matches'),
                act_get_variable('Repeat Item', it),
                act_first_match(it, 'Variable', PICK_CODE_RX, code),
                act_first_match(it, 'Variable', PICK_URL_RX, url),
                *read_page((url, 'Matches'), r'(?s)\A.{1,%d}' % (CHUNK * CHUNKS), 'PolyResearchPage'),
                act_get_variable('PolyResearchPage', cnt)]
        g_page = u()
        out += [*if_text(g_page, 'PolyResearchPage')]
        for part in range(1, CHUNKS + 1):
            chunk, rp, rc, g_note, n_get, cc, g_len = (u() for _ in range(7))
            if part == 1:
                out.append(act_first_match(cnt, 'Variable', CHUNK1_RX, chunk))
                ref = (chunk, 'Matches')
            else:
                out += [act_count_chars(cnt, 'Variable', cc),
                        if_output(g_len, cc, 'Count', 2, WFNumberValue=CHUNK)]
                out.append(act_replace_regex(cnt, 'Variable', CHUNK2_RX[0], CHUNK2_RX[1], chunk))
                ref = (chunk, 'Updated Text')
            out.append(act_text(text_token(L.prompt('research-read'),
                                           {'Q': qsrc, 'CODE': (code, 'Matches'), 'PAGE': ref},
                                           {'TODAY': today}), rp))
            a, name = ask(rp, rc)
            out += [a,
                    act_set_variable('PolyNote', rc, name),
                    *if_text(g_note, 'PolyNote'),
                    act_get_variable('PolyNote', n_get),
                    *append_to(notes, '[{C}] {N}\n', {'C': (code, 'Matches'), 'N': (n_get, 'Variable')}),
                    if_close(g_note)]
            if part > 1:
                out.append(if_close(g_len))
        out += [if_close(g_page), repeat_close(g_rep)]
        return out

    pk_get = u()
    acts += [act_get_variable(packet_var(side), pk_get),
             *pick_and_read((pk_get, 'Variable'), 1, CARDS_MAX, PICK_MAX)]
    # enough, or one new query → the second round on the side's own engines
    mp, mc, mreply, g_enough, enough, q, g_q, nc = (u() for _ in range(8))
    notes_get = u()
    acts += [act_get_variable(notes, notes_get),
             act_text(text_token(L.prompt('research-more'), {'Q': qsrc, 'NOTES': (notes_get, 'Variable')},
                                 {'TODAY': today}), mp)]
    a, name = ask(mp, mc)
    tmp = 'PolyRound2' + side
    acts += [a,
             act_text(text_token('{R}', {'R': (mc, name)}), mreply),
             act_first_match(mreply, 'Text', ENOUGH_RX, enough),
             if_output(g_enough, enough, 'Matches', 101),
             act_replace_regex(mreply, 'Text', MORE_QUERY_RX[0], MORE_QUERY_RX[1], q),
             act_first_match(q, 'Updated Text', r'\S', g_q),
             if_output(nc, g_q, 'Matches', 100),
             act_step('research_round2'),
             *clear_variable(tmp)]
    engines = SIDE_ENGINES[model] if not SHARED_SOURCES else SIDE_ENGINES['C'] + SIDE_ENGINES['G']
    for engine in engines:
        acts += fetch(L, engine, (q, 'Updated Text'), tmp)
    g_new, new_get = u(), u()
    acts += [*clean_records(tmp),
             *if_text(g_new, tmp),
             *cards(L, side, now, CARDS_MAX + 1, ROUND2_MAX, records=tmp),
             act_get_variable(NEWCARDS, new_get),
             *pick_and_read((new_get, 'Variable'), CARDS_MAX + 1, ROUND2_MAX, PICK2_MAX),
             if_close(g_new),
             if_close(nc),
             if_close(g_enough)]
    return acts + [if_close(g_net), if_close(g_have)]


# ------------------------------------------------------------------ the sources under the result

def card_numbers():
    """(prefix, highest number) of every list Duo may print."""
    top = CARDS_MAX + ROUND2_MAX
    return [(p, top) for p in prefixes()] + [('V', CLAIMS_MAX)]


def append_sources(L, result_var):
    """Under the result: «Sources» with the entries whose numbers the text really cites — written by Duo from its own
    data, so a link that was never fetched cannot appear. No number cited (an ordinary question) → nothing is added."""
    g_r, g_c, res, c_get, r_get, out = (u() for _ in range(6))
    acts = [*clear_variable(CITED),
            *if_text(g_r, result_var),
            act_get_variable(result_var, res)]
    for prefix, top in card_numbers():
        lst = u()
        acts.append(act_get_variable(LIST_V if prefix == 'V' else list_var(prefix), lst))
        for n in range(1, top + 1):
            hit, g, entry = u(), u(), u()
            acts += [act_first_match(res, 'Variable', cited_rx(prefix, n), hit),
                     if_output(g, hit, 'Matches', 100),
                     act_first_match(lst, 'Variable', source_entry_rx(prefix, n), entry),
                     *append_to(CITED, '{E}\n', {'E': (entry, 'Matches')}),
                     if_close(g)]
    return acts + [
        *if_text(g_c, CITED),
        act_get_variable(CITED, c_get),
        act_get_variable(result_var, r_get),
        act_text(text_token('{R}\n\n' + L['search.sources_title'] + '\n{S}',
                            {'R': (r_get, 'Variable'), 'S': (c_get, 'Variable')}), out),
        act_set_variable(result_var, out, 'Text'),
        if_close(g_c),
        if_close(g_r),
    ]
