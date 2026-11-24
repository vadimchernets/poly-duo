"""Duo 6.11: search without keys, done by the shortcut itself, in three depths (the owner's decisions of 23.11.2026).

«Ask Claude» has no web search and «Ask ChatGPT» answered fresh questions from memory (the 22.11 timings on the
iPhone), so Duo fetches the sources itself and hands them to the models as numbered DATA:

  * search (every depth): one short Claude call writes 2–3 queries from the question's own words (one in English) or
    NONE for a question the web cannot help (science, how-to, a pasted text) — then nothing is fetched. Each model
    gets its OWN engines, all of them at once (no fallback chain): Claude — Google News RSS + Wikipedia,
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
Pages are read through one reader (READER), so a dead site, a PDF or a script page is text, not a stopped shortcut,
and every site is one permission window; the Setup calls each host once (warm_up), so those windows come there.

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
# the 6.11 check (fable, astra): one engine may not crowd the others out — each answer gives at most ENGINE_MAX
# records BEFORE they are joined, and every record of a side (at most 7 answers × ENGINE_MAX) is ordered by age
ENGINE_MAX = 4
RECORDS_SEEN = 32         # records ordered by age before the cut to CARDS_MAX (above what the engines can give)
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
    # SearXNG: the parser stays, the engine is off the default path (the 6.11 check: fable, agy, kimi) — the public
    # searx.be answers with a browser check, and a server that does not answer at all stops the shortcut
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
SIDE_ENGINES = {'C': ('gnews', 'wiki'), 'G': ('bingnews', 'bingweb', 'ddg')}
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
    # Wikipedia's JSON writes «https:\/\/…» (the Mac run of 24.11)
    (r'\\/', '/'),
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
# one origin once: a later line with the same link, or the same headline (the WHOLE headline, the snippet after « — »
# aside) — a reprint of one wire story in five papers is one piece of evidence, not five. Headlines that only start
# alike («… decided to keep the rate» / «… decided to raise the rate») are different news and both stay (the 6.11
# check, astra). Two different stories of one publisher both stay: how many DIFFERENT publishers report a thing is a
# signal the model reads from the cards, not a filter of Duo's.
SAME_URL_RX = (r'(?m)^([^\n]*\t(\S+)\n(?:[^\n]*\n)*?)[^\n]*\t\2\n', '$1')
SAME_TITLE_RX = (r'(?im)^([^\t\n]*\t[^\t\n]*\t((?:(?! — )[^\t\n])+)(?: — [^\t\n]*)?\t[^\n]*\n(?:[^\n]*\n)*?)'
                 r'[^\t\n]*\t[^\t\n]*\t\2(?: — [^\t\n]*)?\t[^\n]*\n', '$1')
DEDUP_PASSES = 3
SEEN_RX = r'\A(?:[^\n]*\n){1,%d}' % RECORDS_SEEN
# one engine's answer: only record lines (three tabs) stay, at most ENGINE_MAX of them
ENGINE_KEEP_RX = (r'(?m)^(?![^\n]*\t[^\n]*\t[^\n]*\t)[^\n]*(?:\n|\z)', '')
ENGINE_CUT_RX = (r'(?s)\A((?:[^\n]*\n){%d}).*\z' % ENGINE_MAX, '$1')
# the age the phone counts may come with a minus (which date is «later» differs between iOS versions): the size only
AGE_SIGN_RX = (r'[^0-9]', '')   # a minus and the space of «1 200» (agy, the dozapros of 24.11: 3 of 4)
RECORD_LINES_RX = r'(?m)^[^\n]*\t[^\n]+$'
UNDATED_RX, UNDATED_MARK = r'(?m)^\t', '0000-00-00'
MARK = '§ '               # stands where Duo puts the number — at the start of a line, so a «§ 573 BGB» headline keeps it
NUMBER_RX = r'(?ms)\A(.*?)^§ '

# ---- the query call's answer: list marks («1.», «2)», «-») and quotes off — a year or a number that starts a query
# stays («2026 Formula 1 champion», the 6.11 check: fable, astra); NONE = no search
QUERY_CLEAN_RX = r'(?m)^[ \t]*(?:(?:[-*•]+|\d{1,2}[.)])[ \t]+)?["«“„]*|["»”]+[ \t]*$'
QUERY_LINE_RX = r'\A[^\n]{3,%d}' % QUERY_MAX
QUERY_REST_RX = r'\A[^\n]*\n+'
NONE_RX = r'\A\s*NONE\b'
# the question's kind on the query call's first line (FACT / OPEN); the line is taken off before the queries are read
# (case-sensitive and the whole line: a query that starts «Open source…» or «fact check…» is not a kind)
KIND_FACT_RX = r'(?-i)\A[\s*#_]*FACT[\s*_.:]*(?:\n|\z)'
KIND_LINE_RX = r'(?-i)\A[\s*#_]*(?:FACT|OPEN)[ \t*_.:]*(?:\n+|\z)'
QUESTION_RX = r'\A\s*[^\n]{1,%d}' % QUERY_CHARS

# ---- links and pages
_U = r'https?://[^\s\)\]>"\'»”]*[^\s\)\]>"\'»”.,;:!?]'
LINK_RX = _U
LINK1_RX = (r'(?s)\A.*?(' + _U + r').*\z', '$1')
# the second link: any link but the first one itself — a deeper page of the same site counts (the 6.11 check, agy)
# (each link whole: it ends where a link ends, so neither can be cut short to look different)
_END = r'(?=[.,;:!?]*(?:[\s\)\]>"\'»”]|\z))'
_NOT_FIRST = r'(?!\1' + _END + r')'
LINK2_RX = (r'(?s)\A.*?(' + _U + r')' + _END + r'.*?' + _NOT_FIRST + r'(' + _U + r')' + _END + r'.*\z', '$2')
LINK2_TEST_RX = r'(?s)(' + _U + r')' + _END + r'.*?' + _NOT_FIRST + r'(' + _U + r')' + _END
HTML_STRIP = ((r'(?is)<(script|style|noscript|svg|head)\b.*?</\1>', ' '), (r'(?s)<[^>]+>', ' '),
              (r'&nbsp;|&#160;', ' '), (r'\s{2,}', ' '))
# The pages are read through ONE reader, r.jina.ai (the 6.11 check: fable, opus): one permission window for every site
# instead of one per new site in the middle of an answer; a dead site, a 404, a PDF (eur-lex, cbr.ru) or a page behind
# a script come back as the reader's TEXT — an answer «Get Contents of URL» never throws on — instead of a network error
# that stops the shortcut. The direct download stays as the spare, only when the reader itself is out (its rate limit).
READER = 'https://r.jina.ai/'
READER_OK_RX = r'Markdown Content:'
READER_DEAD_RX = r'Target URL returned error|"code":\s*4(?!29)\d\d'   # the page is gone: no direct attempt either
MD_STRIP = ((r'(?m)^URL Source: \S*\s*', ''), (r'Markdown Content:\s*', ''),
            (r'!\[[^\]\n]*\]\([^)\n]*\)', ''), (r'\[([^\]\n]*)\]\([^)\n]*\)', '$1'),
            (r'(?m)^[ \t]*[#>|*-]+[ \t]+', ''), (r'\s{2,}', ' '))
# Google News hands out its own address that reaches the article only through a script (and the reader is refused
# there): such a card is found again by its headline in the web index, and that page is read
GNEWS_LINK_RX = r'^https?://news\.google\.'
ASKED_CHARS = 2500        # the page linked in the question (No.112): this much of it goes to each model
PAGE_RX = r'(?s)\A.{1,%d}' % PAGE_CHARS
CHUNK1_RX = r'(?s)\A.{1,%d}' % CHUNK
CHUNK2_RX = (r'(?s)\A.{%d}(.{1,%d}).*\z' % (CHUNK, CHUNK), '$1')

# ---- the divergence search: «claim || query || site» per line, at most CLAIMS_MAX lines
CLAIM_LINE_RX = r'(?m)^[^\n|]{4,}\|\|[^\n|]{3,}(?:\|\|[^\n|]*)?$'
# the claims answered: everything up to and including the claim line just used — also when it is the last line with
# no line break after it, or when a line of other text stands before it (the 6.11 check, astra: one claim twice)
CLAIM_REST_RX = r'\A(?:[^\n]*\n)*?[^\n|]{4,}\|\|[^\n|]{3,}(?:\|\|[^\n|]*)?(?:\n+|\z)'
CLAIM_TEXT_RX = (r'\A\s*([^|]*?)\s*\|\|.*\z', '$1')
CLAIM_QUERY_RX = (r'\A[^|]*\|\|\s*([^|]*?)\s*(?:\|\|.*)?\z', '$1')
# «Match Text» ignores case and the «Replace Text» here does not: both read the site the same way — any case, and
# whatever follows the host («ecb.europa.eu (official site)», «ECB.europa.eu/press») (the 6.11 check, opus)
CLAIM_SITE_RX = (r'(?i)\A[^|]*\|\|[^|]*\|\|\s*(?:https?://)?(?:www\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)+)[^|\n]*\s*\z',
                 ' site:$1')
CLAIM_NO_SITE_RX = r'(?i)\A[^|]*\|\|[^|]*\|\|\s*(?:https?://)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+'
FIRST_RECORD_RX = r'\A[^\n]+'
# a line of the claim list «<i>\t<claim line>»: the claim line, the number
CLAIM_ITEM_RX = r'[^\t\n|]{4,}\|\|[^\n]*'
CLAIM_INDEX_RX = (r'(?s)\A(\d)\t.*\z', '$1')
CLAIM_LIST = 'PolyClaimList'

# ---- deep research: the card numbers a model picked, the line with its next query
ENOUGH_RX = r'(?i)\A\s*(?:ENOUGH|NONE)\b'
MORE_QUERY_RX = (r'(?is)\A\s*(?:QUERY\s*:\s*)?([^\n]{3,%d}).*\z' % QUERY_MAX, '$1')
PICK_CODE_RX = r'\A\S+'
# a picked line: «<code> <url> <headline>»
PICK_LINE_RX = (r'(?m)^(\S+) (?:[^\n]*· )?([^\n]*)\n(\S+)$', '$1 $3 $2')
PICK_URL_RX = (r'(?s)\A\S+ (\S+).*\z', '$1')
PICK_TITLE_RX = (r'(?s)\A\S+ \S+ ?', '')

# ---- variables
NET, QUERIES = 'PolyNet', 'PolyQueries'
# The owner's choice of 24.11 («with search / without search», asked once in the Setup, kept in Duo-prefs.txt as the
# line SEARCH=0): set to «1» at the start of every run and only CLEARED when the file says SEARCH=0 (the D-29 rule
# for anything read from that file). Cleared → search_guard() clears NET too, and the run takes the airplane-mode
# path: no query call, no engine, no page read; every mode answers from the models' own knowledge.
SEARCH_ON = 'PolySearchOn'
DEEP, QUICK = 'PolyDeep', 'PolyQuick'           # set by the menu; neither = the default depth, «check»
CHECKS, PAGE, VERDICT = 'PolyChecks', 'PolyPage', 'PolyVerdict'
LIST_V = 'PolySourceListV'
CLAIMS, PICKS, NEWCARDS = 'PolyClaims', 'PolyPicks', 'PolyNewCards'
CITED = 'PolyCited'
READ_URL = 'PolyReadUrl'
NOWEB = 'PolyNoWeb'       # the query call said NONE: the web cannot help this question (no divergence search either)
KIND = 'PolyKind'         # the query call's first line: FACT or OPEN (agy, the dozapros of 23.11); empty — the judge decides
CROSS = 'PolyCross'       # Research: Claude developed an idea only ChatGPT had («crossing», the dozapros of 23.11)
LIST_U = 'PolySourceListU'
# The council of 24.11 (Opus, Kimi): iOS remembers «Always Allow» for a host together with the SOURCES of what is sent
# (an app's answer, the clipboard, a network name…). TAG holds an EMPTY text made from each AI answer of the run so far
# (Replace «(?s).+» with nothing): it is added to every address Duo fetches, so a host gets the same set of sources at
# the same stage of every run (search: the query call; the check: + ChatGPT's and Claude's answers) whichever branch
# built the address — and the Setup can grant exactly those sets once (warm_up). Empty: no query or page changes.
TAG = 'PolyTag'
TAG_RX = r'(?s).+'


def add_tag(src):
    """TAG += an empty text made from the output `src` ((uid, name)): its source joins every later address."""
    # the second fix of 24.11: TAG only added the answers' apps to every address (more windows, not fewer) — off
    return []


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


def parse_into(L, engine, txt, target):
    """The answer text `txt` (a Text action's uid) of `engine` → record lines added to `target`, only when it holds what
    a real answer holds (`test`: an RSS item, a DDG result, a Wikipedia page — a captcha, a rate limit or an error page
    does not)."""
    spec = ENGINES[engine]
    g = u()
    acts = [if_output(g, txt, 'Text', 99, WFConditionalActionString=spec['test'])]
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
        steps, last = pipeline((txt, 'Text'), (*parse_pairs(engine), ENGINE_KEEP_RX, ENGINE_CUT_RX))
        acts += [*steps, *append_to(target, '\n{R}\n', {'R': last})]
    return acts + [if_close(g)]


def download_text(url_src):
    """«Get Contents of URL» on the address `url_src` ((uid, name)) → (actions, uid of a Text of the answer as it came).
    D2 (the Mac run of 24.11; Opus, agy): «Text» of an RSS answer is its FILE NAME («search»), of a DuckDuckGo page its
    visible words without tags; named «r.txt» first, the answer is read as it came."""
    dl, named, txt = u(), u(), u()
    return [act_download(text_token('{U}', {'U': url_src}), dl),
            act_set_name(dl, 'Contents of URL', 'r.txt', named),
            act_text(text_token('{C}', {'C': (named, 'Renamed Item')}), txt)], txt


def fetch(L, engine, query, target, english=False):
    """One search with its own «Get Contents of URL» (the check and research steps; the search stage queues its
    searches instead: queue_fetch / run_queue). `query`: (uid, output) of the query text."""
    enc, url = u(), u()
    acts = [act_urlencode(query[0], query[1], enc),
            act_text(text_token(engine_address(L, engine, english), {'Q': (enc, 'URL Encoded Text')}), url)]
    dl_acts, txt = download_text((url, 'Text'))
    return acts + dl_acts + parse_into(L, engine, txt, target)


# The second fix of 24.11 (Mac, «Shortcuts», DuoPermDiag): iOS and macOS remember «Always Allow» for ONE ACTION of the
# shortcut (its own place in it) and the site — two «Get Contents of URL» actions sending the same thing to the same
# site asked twice; ONE action asked once and then never again, whatever set of data later went through it. So the
# search stage — every engine, every query (1, 2 in English, 3 in Research) — goes through ONE download action: the
# searches are queued as lines «⟦k⟧address» and one «Repeat with Each» downloads them; ⟦k⟧ says which engine parses
# the answer into which variable.
NETQ = 'PolyNetQueue'
QMARK = '\u27e6%d\u27e7'


def queue_fetch(L, engine, query, target, routes, english=False):
    """Queue one search (as fetch() would make it) in NETQ; `routes`: the list of (engine, target) of this queue —
    the line's ⟦k⟧ is its index there."""
    if (engine, target) not in routes:
        routes.append((engine, target))
    k = routes.index((engine, target))
    enc = u()
    return [act_urlencode(query[0], query[1], enc),
            *append_to(NETQ, QMARK % k + engine_address(L, engine, english) + '\n', {'Q': (enc, 'URL Encoded Text')})]


def run_queue(L, routes, item='Repeat Item'):
    """Download every queued line with ONE «Get Contents of URL» and parse each answer by its route; NETQ is emptied.
    `item`: the name of the «Repeat with Each» item at this place (see search_block)."""
    qv, split, g_rep, iv, it, url, g_url = (u() for _ in range(7))
    acts = [act_get_variable(NETQ, qv),
            {'WFWorkflowActionIdentifier': 'is.workflow.actions.text.split',
             'WFWorkflowActionParameters': {'text': text_token('{T}', {'T': (qv, 'Variable')}),
                                            'WFTextSeparator': 'New Lines', 'UUID': split}},
            repeat_open(g_rep, split, 'Split Text'),
            act_get_variable(item, iv),
            act_text(text_token('{I}', {'I': (iv, 'Variable')}), it),
            act_first_match(it, 'Text', r'https?://\S+', url),
            if_output(g_url, url, 'Matches', 100)]
    dl_acts, txt = download_text((url, 'Matches'))
    acts += dl_acts
    for k, (engine, target) in enumerate(routes):
        g_k = u()
        acts += [if_output(g_k, it, 'Text', 99, WFConditionalActionString=QMARK % k),
                 *parse_into(L, engine, txt, target),
                 if_close(g_k)]
    return acts + [if_close(g_url), repeat_close(g_rep), *clear_variable(NETQ)]


def sort_newest_first(var):
    """The record lines of `var` sorted Z→A: «2026-11-22…» before «2026-11-02…», the undated lines (they start with a
    tab) last — the order by age inside each bucket of `cards` (the 6.11 check, sol: the engines' own order is not an
    age). «Filter Files» sorts any list by Name, a text's name being the text; should it give nothing on some iOS,
    the lines stay in their first order."""
    get, lines, srt, joined, g = (u() for _ in range(5))
    # the Mac run of 24.11: «Filter Files» sorts like Finder and skips the leading tab of an undated line, so the
    # undated web pages came FIRST; for the sort they start with «0000-00-00», which sorts last, and get it off after
    return [*replace_var(var, ((UNDATED_RX, UNDATED_MARK + '\t'),)),
            act_get_variable(var, get),
            {'WFWorkflowActionIdentifier': 'is.workflow.actions.text.split',
             'WFWorkflowActionParameters': {'text': text_token('{T}', {'T': (get, 'Variable')}),
                                            'WFTextSeparator': 'New Lines', 'UUID': lines}},
            {'WFWorkflowActionIdentifier': 'is.workflow.actions.filter.files',
             'WFWorkflowActionParameters': {'WFContentItemInputParameter': attachment(lines, 'Split Text'),
                                            'WFContentItemSortProperty': 'Name',
                                            'WFContentItemSortOrder': 'Z to A', 'UUID': srt}},
            {'WFWorkflowActionIdentifier': 'is.workflow.actions.text.combine',
             'WFWorkflowActionParameters': {'text': attachment(srt, 'Files'), 'WFTextSeparator': 'New Lines',
                                            'UUID': joined}},
            act_first_match(joined, 'Text', RECORD_LINES_RX, g),
            *if_output_set(var, g, joined),
            *replace_var(var, ((r'(?m)^' + UNDATED_MARK + r'\t', '\t'),))]


def if_output_set_plain(var, match_uid):
    """`var` = the match, only when there is one."""
    g = u()
    return [if_output(g, match_uid, 'Matches', 100), act_set_variable(var, match_uid, 'Matches'), if_close(g)]


def if_output_set(var, test_uid, joined_uid):
    """`var` = the joined text (with a line break after it), only when the test found a record line in it."""
    g, txt = u(), u()
    return [if_output(g, test_uid, 'Matches', 100),
            act_text(text_token('{J}\n', {'J': (joined_uid, 'Text')}), txt),
            act_set_variable(var, txt, 'Text'),
            if_close(g)]


def clean_records(var, ordered=True):
    """The records of a side: one form, reprints glued, newest first."""
    return [*replace_var(var, CLEAN_PAIRS),
            *replace_var(var, (SAME_URL_RX, SAME_TITLE_RX), times=DEDUP_PASSES),
            *(sort_newest_first(var) if ordered else [])]


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
    a_date, d_txt, d_abs, g_ad = u(), u(), u(), u()

    def undated():
        p2, s2 = u(), u()
        return [act_replace_regex(it, 'Variable', RECORD_RX, MARK + L['search.undated'] + ' · $2 · $3', p2),
                act_replace_regex(it, 'Variable', RECORD_RX, MARK + L['search.undated'] + ' · $2 · $3\n$4', s2),
                *append_to(b_pack[1], '{L}\n', {'L': (p2, 'Updated Text')}),
                *append_to(b_list[1], '{L}\n', {'L': (s2, 'Updated Text')})]
    acts = [*(a for v in b_pack + b_list for a in clear_variable(v)),
            act_get_variable(records, get),
            act_first_match(get, 'Variable', SEEN_RX, seen),
            act_first_match(seen, 'Matches', RECORD_LINES_RX, recs),
            repeat_open(g_rep, recs, 'Matches'),
            act_get_variable(item, it),
            act_first_match(it, 'Variable', r'^\d{4}-\d\d-\d\d', day),
            if_output(g_day, day, 'Matches', 100),
            # «2026-11-22» made a date first (agy: a bare text may not read as one on every region setting), and the
            # number of days taken without its sign (sol: the count came out negative, and every old record «fresh»).
            # D1 (iPhone 24.11): the input is the match itself (an attachment, as «Count» takes it); a text token here
            # is not accepted and iOS put the shortcut's own input in its place («the first date is invalid» on the probe)
            {'WFWorkflowActionIdentifier': 'is.workflow.actions.detect.date',
             'WFWorkflowActionParameters': {'WFInput': attachment(day, 'Matches'), 'UUID': a_date}},
            # a date the phone cannot read is an undated card, never a stopped run (agy, the dozapros of 24.11)
            if_output(g_ad, a_date, 'Dates', 100),
            act_time_between(now, 'Date', a_date, 'Dates', 'Days', days),
            act_text(text_token('{N}', {'N': (days, 'Time Between Dates')}), d_txt),
            act_replace_regex(d_txt, 'Text', AGE_SIGN_RX[0], AGE_SIGN_RX[1], d_abs),
            act_text(text_token(L['search.age'], {'N': (d_abs, 'Updated Text')}), age),
            # for the models: no link (a model can neither open it nor is it to copy it)
            act_replace_regex_token(it, 'Variable', RECORD_RX,
                                    text_token(MARK + '$1 ({A}) · $2 · $3', {'A': (age, 'Text')}), p_line),
            act_replace_regex(it, 'Variable', RECORD_RX, MARK + '$1 · $2 · $3\n$4', s_line),
            # D-100: a number condition takes a Number (or a Count), never another action's output straight
            act_number(d_abs, 'Updated Text', num),
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
            if_else(g_ad),
            *undated(),
            if_close(g_ad),
            if_else(g_day)]
    # a record without a date (a web page: an official page, a register, an encyclopedia — what the web index holds
    # now): the middle bucket, «undated» instead of an age
    acts += [*undated(),
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


def search_guard():
    """network_guard(NET), then «without search» clears NET as having no network does: every step behind NET is
    skipped the same way offline. NET is still set OUTSIDE every condition and only cleared inside one."""
    g = u()
    return [*network_guard(NET), *if_text(g, SEARCH_ON, present=False), *clear_variable(NET), if_close(g)]


def query_lines(L, qsrc, ask_claude, today):
    """The query call: the question's kind (FACT / OPEN) on its first line, then 2–3 queries from the question's words
    (line 2 in English), or NONE. Leaves KIND (FACT, or OPEN for anything else — when in doubt OPEN) and QUERIES set
    (the kind's line taken off, cleaned) and returns the actions; the caller tests NONE. The kind costs no call: it
    rides on the call the search makes anyway (agy, the dozapros of 23.11)."""
    qp, qc, qk, kf, g_fact = u(), u(), u(), u(), u()
    return [act_step('search_queries'),
            act_text(text_token(L.prompt('search-queries'), {'Q': qsrc}, {'TODAY': today}), qp),
            ask_claude(qp, qc),
            act_set_variable(QUERIES, qc, 'Ask Claude'),
            *set_text(KIND, 'OPEN'),
            act_get_variable(QUERIES, qk),
            act_first_match(qk, 'Variable', KIND_FACT_RX, kf),
            if_output(g_fact, kf, 'Matches', 100),
            *set_text(KIND, 'FACT'),
            if_close(g_fact),
            *replace_var(QUERIES, ((KIND_LINE_RX, ''), (QUERY_CLEAN_RX, '')))]


def search_block(L, qsrc, long_question, ask_claude, now, today, item='Repeat Item'):
    """Leaves, per side, the packet (for the model) and the source list (for the person) set or empty; with no
    network, a long pasted text or NONE from the query call, all stay empty and the run goes on from memory.
    `ask_claude(prompt_uid, uid)`: the short «Ask Claude» action; `now`: a Current Date action's uid; `today`: the
    special attachment of today's date; `item`: the name of a «Repeat with Each» item where the block runs (inside
    the draft's «Repeat 3 times» it is «Repeat Item 2»)."""
    (q_txt, q_cnt, g_long, net_get, g_net, q_all, g_none, none_m, q1, g_q1, q_cut, q_rest, q2, g_q2, q_rest2, q3,
     g_q3, g_deep) = (u() for _ in range(18))
    sides = prefixes()
    acts = [*(a for s in ('C', 'G', 'S') for v in (records_var(s), packet_var(s), list_var(s))
              for a in clear_variable(v)),
            *(a for m in ('C', 'G') for a in clear_variable(notes_var(m))),
            *clear_variable(CHECKS), *clear_variable(LIST_V), *clear_variable(QUERIES), *clear_variable(NOWEB),
            *clear_variable(KIND), *clear_variable(CROSS),
            *clear_variable(LIST_U),
            act_text(text_token('{Q}', {'Q': qsrc}), q_txt),
            act_count_chars(q_txt, 'Text', q_cnt),
            if_output(g_long, q_cnt, 'Count', 2, WFNumberValue=long_question - 1),
            if_else(g_long),
            *search_guard(),
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
    routes = []
    acts += [*clear_variable(NETQ), act_get_variable('PolyQ1', q1_get)]
    for side in ('C', 'G'):
        target = records_var('S' if SHARED_SOURCES else side)
        for engine in SIDE_ENGINES[side]:
            acts += queue_fetch(L, engine, (q1_get, 'Variable'), target, routes)
    # query 2 — English — to the engines with an English edition; query 3 (deep research only) to the same
    acts += [act_replace_regex(q_all, 'Variable', QUERY_REST_RX, '', q_rest),
             act_first_match(q_rest, 'Updated Text', QUERY_LINE_RX, q2),
             if_output(g_q2, q2, 'Matches', 100)]
    for engine in EN_ENGINES:
        side = 'S' if SHARED_SOURCES else ENGINES[engine]['side']
        acts += queue_fetch(L, engine, (q2, 'Matches'), records_var(side), routes, english=True)
    acts += [if_close(g_q2),
             *if_text(g_deep, DEEP),
             act_replace_regex(q_rest, 'Updated Text', QUERY_REST_RX, '', q_rest2),
             act_first_match(q_rest2, 'Updated Text', QUERY_LINE_RX, q3),
             if_output(g_q3, q3, 'Matches', 100)]
    for engine in EN_ENGINES:
        side = 'S' if SHARED_SOURCES else ENGINES[engine]['side']
        acts += queue_fetch(L, engine, (q3, 'Matches'), records_var(side), routes)
    acts += [if_close(g_q3), if_close(g_deep), *run_queue(L, routes, item)]
    for side in sides:
        g_any = u()
        acts += [*clean_records(records_var(side)),
                 *if_text(g_any, records_var(side)),
                 *cards(L, side, now, 1, CARDS_MAX, item=item),
                 if_close(g_any)]
    acts += [if_else(g_none), *set_text(NOWEB, '1'), if_close(g_none)]
    return acts + [*asked_page(q_txt), if_close(g_net), if_close(g_long)]


def asked_page(q_txt):
    """No.112 (the 6.11 check: fable, sol, astra, kimi, opus): a link in the question itself is read FIRST, whatever the
    query call said — «is this true? <link>» is about that page. Up to ASKED_CHARS of it go to BOTH models as source
    [U1] (it is the question's own material, so the two answers stay independent); «Sources» lists its link."""
    found, g, link, link_t, g_page, cut_get = (u() for _ in range(6))
    acts = [act_first_match(q_txt, 'Text', LINK_RX, found),
            if_output(g, found, 'Matches', 100),
            act_step('asked_page'),
            act_replace_regex(q_txt, 'Text', LINK1_RX[0], LINK1_RX[1], link),
            act_text(text_token('{U}', {'U': (link, 'Updated Text')}), link_t),
            *read_page((link_t, 'Text'), r'(?s)\A.{1,%d}' % ASKED_CHARS, 'PolyAskedPage'),
            *if_text(g_page, 'PolyAskedPage'),
            act_get_variable('PolyAskedPage', cut_get),
            *set_text(LIST_U, '[U1] {U}\n', {'U': (link_t, 'Text')})]
    for side in prefixes():
        acts += append_to(packet_var(side), '[U1] (the page linked in the question) {P}\n',
                          {'P': (cut_get, 'Variable')})
    return acts + [if_close(g_page), if_close(g)]


# ------------------------------------------------------------------ reading a page

def read_page(url, cut_rx, target_var):
    """A page through the reader (READER): its text (title, date of publication, the page as plain text); a page that
    is gone, or the reader itself is out, leaves `target_var` empty (no direct download: a new site would ask a
    permission in the middle of an answer — the council of 24.11). No «Safari Reader» step: on a table, a PDF or an
    error page it stops the shortcut instead of giving nothing (the 6.11 check, agy). `target_var` gets at most what
    `cut_rx` keeps (or stays empty)."""
    r_url, r_dl, r_txt, dead, g_dead, ok, g_ok, p_get, cut = (u() for _ in range(9))
    return [*clear_variable(PAGE),
            act_text(text_token(READER + '{U}', {'U': url}), r_url),
            act_download(text_token('{U}', {'U': (r_url, 'Text')}), r_dl),
            act_text(text_token('{C}', {'C': (r_dl, 'Contents of URL')}), r_txt),
            act_first_match(r_txt, 'Text', READER_DEAD_RX, dead),
            if_output(g_dead, dead, 'Matches', 101),
            act_first_match(r_txt, 'Text', READER_OK_RX, ok),
            if_output(g_ok, ok, 'Matches', 100),
            act_set_variable(PAGE, r_txt, 'Text'),
            *replace_var(PAGE, MD_STRIP),
            # the council of 24.11 (OpenAI, agy): no direct download when the reader is out — it asked a permission
            # for a NEW site in the middle of an answer; the page counts as unread instead
            if_close(g_ok),
            if_close(g_dead),
            act_get_variable(PAGE, p_get),
            act_first_match(p_get, 'Variable', cut_rx, cut),
            act_set_variable(target_var, cut, 'Matches')]


# ------------------------------------------------------------------ check: ChatGPT's links and the divergence search

def link_check_block(L, gpt_var, claude_check, skip_var, today, item='Repeat Item'):
    """ChatGPT cited pages → Duo downloads up to LINK_MAX of them and asks Claude about each in a separate short call
    whether the page supports what the answer says. CHECKS gets one line a page. Not in the quick depth; never on a
    run resumed from a draft (`skip_var`): a page that stopped the run once must not stop it again.
    (The second fix of 24.11, the check — Opus, OpenAI: «Always Allow» is kept per action, and the pages were read by
    LINK_MAX unrolled copies — the second asked its own windows on whatever question first had two links. The links
    are listed in PolyLinks and ONE «Repeat with Each» reads them: one reader action, one Claude call.) `item`: the
    name of a «Repeat with Each» item at this place (inside the draft's loop «Repeat Item 2»)."""
    ans, found, g_has, g_skip, g_quick, net_get, g_net = (u() for _ in range(7))
    links = 'PolyLinks'
    link1, test, g_two, link2, lv, split, g_rep = (u() for _ in range(7))
    acts = [*if_text(g_quick, QUICK, present=False),
            *if_text(g_skip, skip_var, present=False),
            act_get_variable(gpt_var, ans),
            act_first_match(ans, 'Variable', LINK_RX, found),
            if_output(g_has, found, 'Matches', 100),
            *search_guard(),
            act_get_variable(NET, net_get),
            if_output(g_net, net_get, 'Variable', 100),
            act_step('link_check'),
            act_replace_regex(ans, 'Variable', LINK1_RX[0], LINK1_RX[1], link1),
            *set_text(links, '{U}\n', {'U': (link1, 'Updated Text')})]
    if LINK_MAX > 1:
        acts += [act_first_match(ans, 'Variable', LINK2_TEST_RX, test),
                 if_output(g_two, test, 'Matches', 100),
                 act_replace_regex(ans, 'Variable', LINK2_RX[0], LINK2_RX[1], link2),
                 *append_to(links, '{U}\n', {'U': (link2, 'Updated Text')}),
                 if_close(g_two)]
    it, link, link_t, g_link, g_page, prompt, call, g_v, v_get, cut_get = (u() for _ in range(10))
    acts += [act_get_variable(links, lv),
             {'WFWorkflowActionIdentifier': 'is.workflow.actions.text.split',
              'WFWorkflowActionParameters': {'text': text_token('{T}', {'T': (lv, 'Variable')}),
                                             'WFTextSeparator': 'New Lines', 'UUID': split}},
             repeat_open(g_rep, split, 'Split Text'),
             act_get_variable(item, it),
             act_first_match(it, 'Variable', r'\Ahttps?://\S+', link),
             if_output(g_link, link, 'Matches', 100),
             act_text(text_token('{U}', {'U': (link, 'Matches')}), link_t),
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
             if_close(g_link),
             repeat_close(g_rep)]
    return acts + [if_close(g_net), if_close(g_has), if_close(g_skip), if_close(g_quick)]


def divergence_block(L, question, gpt_answer, claude_answer, claude_check, skip_var, today, nums_var=None,
                     item='Repeat Item'):
    """The owner's main idea of 23.11 (fable, agy, sol, astra): Duo searches where the two answers state a FACT
    differently (a number, a date, a name) — never where they agree (the council of 23.11 on the divergent, item 6:
    checking for checking's sake spends calls). `nums_var`: the numbers that stand in only one answer (found by rule);
    none → no call at all; some → they go to the claim finder as a hint. One short Claude call names at most
    CLAIMS_MAX such claims («claim || query || site of the primary source»); for each Duo searches the web index (then
    the news index), reads the first page and asks Claude in its own short call whether the page supports the claim.
    The page becomes source [V<i>] of the list Duo prints; CHECKS gets «[V<i>] claim — verdict». Not in the quick
    depth, not on a resumed run. `question`, `gpt_answer`, `claude_answer`: (uid, output) refs."""
    g_quick, g_skip, net_get, g_net, prompt, call, g_any, c_all = (u() for _ in range(8))
    ga, ca = u(), u()
    g_noweb, g_nums, nums_get = u(), u(), u()
    acts = [*if_text(g_quick, QUICK, present=False),
            *if_text(g_skip, skip_var, present=False),
            # a question the web cannot help (NONE: why the sky is blue, how mRNA works) has nothing to look up
            # (the 6.11 check, kimi)
            *if_text(g_noweb, NOWEB, present=False),
            # the answers agree on every number: no fact to settle, no call (the council of 23.11, item 6)
            *(if_text(g_nums, nums_var) if nums_var else []),
            *search_guard(),
            act_get_variable(NET, net_get),
            if_output(g_net, net_get, 'Variable', 100),
            act_step('divergence'),
            act_first_chars(gpt_answer[0], gpt_answer[1], 2500, ga),
            act_first_chars(claude_answer[0], claude_answer[1], 2500, ca),
            *([act_get_variable(nums_var, nums_get)] if nums_var else []),
            act_text(text_token(L.prompt('crux'), {'QUESTION': question, 'GPT_ANSWER': (ga, 'Matches'),
                                                   'CLAUDE_OWN': (ca, 'Matches'),
                                                   **({'NUMS': (nums_get, 'Variable')} if nums_var else {})},
                                {'TODAY': today}), prompt),
            claude_check(prompt, call),
            act_set_variable(CLAIMS, call, 'Ask Claude'),
            act_get_variable(CLAIMS, c_all)]
    # Prog-4 fix (iPhone 24.11, R1/R3): the claims are listed first (text only, no network), then ONE «Repeat with
    # Each» searches, reads and checks them — one bing action, one news action, one reader action and one Claude call
    # for every claim. Unrolled per claim, the second claim's actions were new places in the shortcut: they asked their
    # own windows on whatever question first had two claims, and the run that stopped and the one that hung both did
    # so on that second set of places.
    src = (c_all, 'Variable')
    closers = []
    acts += clear_variable(CLAIM_LIST)
    for i in range(1, CLAIMS_MAX + 1):
        line, g_line, rest = u(), u(), u()
        acts += [act_first_match(src[0], src[1], CLAIM_LINE_RX, line),
                 if_output(g_line, line, 'Matches', 100),
                 *append_to(CLAIM_LIST, '%d\t{L}\n' % i, {'L': (line, 'Matches')}),
                 act_replace_regex(src[0], src[1], CLAIM_REST_RX, '', rest)]
        src = (rest, 'Updated Text')
        closers.append(if_close(g_line))
    # the claims are nested (claim 2 only after a claim 1), so the Ifs close in reverse
    acts += closers[::-1]
    lv, split, g_rep, it, itt, line, g_line, idx = (u() for _ in range(8))
    claim, query, site, g_site, q_full, g_rec, rec, url, title_line, cut_get, g_page = (u() for _ in range(11))
    p2, call2, g_v, v_get, nsite, title2, first, g_web, vline = (u() for _ in range(9))
    tmp = 'PolyClaimRecords'
    acts += [act_get_variable(CLAIM_LIST, lv),
             {'WFWorkflowActionIdentifier': 'is.workflow.actions.text.split',
              'WFWorkflowActionParameters': {'text': text_token('{T}', {'T': (lv, 'Variable')}),
                                             'WFTextSeparator': 'New Lines', 'UUID': split}},
             repeat_open(g_rep, split, 'Split Text'),
             act_get_variable(item, it),
             act_text(text_token('{I}', {'I': (it, 'Variable')}), itt),
             act_first_match(itt, 'Text', CLAIM_ITEM_RX, line),
             if_output(g_line, line, 'Matches', 100),
             act_replace_regex(itt, 'Text', CLAIM_INDEX_RX[0], CLAIM_INDEX_RX[1], idx),
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
    acts += [*if_text(g_web, tmp, present=False),
             *fetch(L, CLAIM_ENGINES[1], (query, 'Updated Text'), tmp),
             if_close(g_web),
             *clean_records(tmp),
             *if_text(g_rec, tmp),
             act_get_variable(tmp, rec),
             act_first_match(rec, 'Variable', FIRST_RECORD_RX, first),
             act_replace_regex(first, 'Matches', RECORD_RX, '$4', url),
             act_replace_regex(first, 'Matches', RECORD_RX, '$1 · $2 · $3\n$4', title_line),
             act_replace_regex(title_line, 'Updated Text', r'\A · ', '', title2),   # an undated page
             act_text(text_token('[V{I}] {T}', {'I': (idx, 'Updated Text'), 'T': (title2, 'Updated Text')}), vline),
             *append_to(LIST_V, '{L}\n', {'L': (vline, 'Text')}),
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
             *append_to(CHECKS, '• [V{I}] {C} — {V}\n', {'I': (idx, 'Updated Text'), 'C': (claim, 'Updated Text'),
                                                         'V': (v_get, 'Variable')}),
             if_close(g_v),
             if_else(g_page),
             *append_to(CHECKS, '• [V{I}] {C} — ' + L['search.link_unread'] + '\n',
                        {'I': (idx, 'Updated Text'), 'C': (claim, 'Updated Text')}),
             if_close(g_page),
             if_else(g_rec),
             *append_to(CHECKS, '• {C} — ' + L['search.claim_unfound'] + '\n', {'C': (claim, 'Updated Text')}),
             if_close(g_rec),
             if_close(g_line),
             repeat_close(g_rep)]
    return acts + [if_close(g_net), *([if_close(g_nums)] if nums_var else []), if_close(g_noweb),
                   if_close(g_skip), if_close(g_quick)]


def cross_block(L, question, gpt_answer, claude_answer, claude_check):
    """«Crossing» (Opus; the dozapros of 23.11, 3 of 5): in Research only, ONE short Claude call takes the most useful
    idea that only ChatGPT's answer has and develops it («yes, and…»); the judge takes it into the answer and names it
    under «What the second opinion added». Leaves CROSS set, or empty (NONE, or not Research)."""
    g_deep, ga, ca, prompt, call, out, g_none, none_m = (u() for _ in range(8))
    return [*clear_variable(CROSS),
            *if_text(g_deep, DEEP),
            act_step('cross'),
            act_first_chars(gpt_answer[0], gpt_answer[1], 2500, ga),
            act_first_chars(claude_answer[0], claude_answer[1], 2500, ca),
            act_text(text_token(L.prompt('cross'), {'QUESTION': question, 'GPT_ANSWER': (ga, 'Matches'),
                                                    'CLAUDE_OWN': (ca, 'Matches')}), prompt),
            claude_check(prompt, call),
            act_first_match(call, 'Ask Claude', NONE_RX, none_m),
            if_output(g_none, none_m, 'Matches', 101),
            act_set_variable(CROSS, call, 'Ask Claude'),
            if_close(g_none),
            if_close(g_deep)]


# ------------------------------------------------------------------ deep research

def research_block(L, model, side, ask, qsrc, now, today, item='Repeat Item'):
    """Deep research of one model (`model`: 'C' Claude or 'G' ChatGPT) on the cards of `side`: it picks up to
    PICK_MAX pages; Duo reads each in up to CHUNKS parts, each part one short call of that model that returns a dated
    note; the model then says ENOUGH or gives one new query; a second round searches the side's own engines, adds up
    to ROUND2_MAX cards and reads up to PICK2_MAX of their pages. NOTES_<model> holds the notes; the model's answer
    is then written from them. `ask(prompt_uid, uid)` → (the short call of that model, its output name)."""
    notes = notes_var(model)
    g_have, g_net, net_get = u(), u(), u()
    acts = [act_step('research'),
            *if_text(g_have, packet_var(side)),
            *search_guard(),
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
            out += [act_first_match(reply, 'Text', r'(?<![\dU])%d(?![\d])' % n, hit),
                    if_output(g, hit, 'Matches', 100),
                    act_first_match(lst, 'Variable', entry_url_rx(side, n), entry),
                    *append_to(PICKS, '%s%d {E}\n' % (side, n), {'E': (entry, 'Matches')}),
                    if_close(g)]
        # «<code> <line>\n<url>» → «<code> <url> <headline>», at most `limit` pages
        out += replace_var(PICKS, (PICK_LINE_RX,))
        pk, firsts, lines, g_rep, it, code, url, cnt, g_more = (u() for _ in range(9))
        title, g_gn, gn, rec, first, real, rd_get = (u() for _ in range(7))
        resolve = 'PolyResolve'
        out += [act_get_variable(PICKS, pk),
                act_first_match(pk, 'Variable', r'\A(?:[^\n]*\n?){1,%d}' % limit, firsts),
                act_first_match(firsts, 'Matches', r'(?m)^\S+ https?://[^\n]+$', lines),
                repeat_open(g_rep, lines, 'Matches'),
                act_get_variable(item, it),
                act_first_match(it, 'Variable', PICK_CODE_RX, code),
                act_replace_regex(it, 'Variable', PICK_URL_RX[0], PICK_URL_RX[1], url),
                act_set_variable(READ_URL, url, 'Updated Text'),
                # a Google News card (the 6.11 check: fable, agy, opus, kimi — read through its own link it gives
                # nothing): its headline is looked up in the web index and that page is read
                act_first_match(url, 'Updated Text', GNEWS_LINK_RX, gn),
                if_output(g_gn, gn, 'Matches', 100),
                act_replace_regex(it, 'Variable', PICK_TITLE_RX[0], PICK_TITLE_RX[1], title),
                *clear_variable(resolve),
                *fetch(L, 'bingweb', (title, 'Updated Text'), resolve),
                *clean_records(resolve, ordered=False),
                act_get_variable(resolve, rec),
                act_first_match(rec, 'Variable', FIRST_RECORD_RX, first),
                act_replace_regex(first, 'Matches', RECORD_RX, '$4', real),
                act_first_match(real, 'Updated Text', r'\Ahttps?://\S+\z', rd_get),
                *if_output_set_plain(READ_URL, rd_get),
                if_close(g_gn)]
        read_get = u()
        out += [act_get_variable(READ_URL, read_get),
                *read_page((read_get, 'Variable'), r'(?s)\A.{1,%d}' % (CHUNK * CHUNKS), 'PolyResearchPage'),
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
    # (the second fix of 24.11: the second round's searches through ONE download action too)
    routes = []
    acts += clear_variable(NETQ)
    for engine in engines:
        acts += queue_fetch(L, engine, (q, 'Updated Text'), tmp, routes)
    acts += run_queue(L, routes, item)
    g_new, new_get = u(), u()
    acts += [*clean_records(tmp),
             *if_text(g_new, tmp),
             *cards(L, side, now, CARDS_MAX + 1, ROUND2_MAX, records=tmp, item=item),
             act_get_variable(NEWCARDS, new_get),
             *pick_and_read((new_get, 'Variable'), CARDS_MAX + 1, ROUND2_MAX, PICK2_MAX),
             if_close(g_new),
             if_close(nc),
             if_close(g_enough)]
    return acts + [if_close(g_net), if_close(g_have)]


# ------------------------------------------------------------------ the first run

def warm_up_addresses(L):
    """One address on each host the search and the reader use (both Bing engines share www.bing.com)."""
    hosts, out = set(), []
    for side in ('C', 'G'):
        for engine in SIDE_ENGINES[side]:
            url = engine_address(L, engine).replace('{Q}', 'duo')
            host = url.split('/')[2]
            if host not in hosts:
                hosts.add(host)
                out.append(url)
    return out + [READER + 'https://example.com/']


def warm_card_link(warm):
    """(The check of 24.11, Opus, OpenAI): in a run the reader also gets a link taken from a CARD (a site's answer):
    the first record's link of what the warm-up search brought is read too."""
    w, first, link = u(), u(), u()
    return [*clean_records(warm, ordered=False),
            act_get_variable(warm, w),
            act_first_match(w, 'Variable', FIRST_RECORD_RX, first),
            act_replace_regex(first, 'Matches', RECORD_RX, '$4', link),
            *read_page((link, 'Updated Text'), PAGE_RX, 'PolyWarmPage')]


def warm_up(L, ask_gpt=None, ask_claude=None, ping=None):
    """The Setup (the council of 24.11, all four families: warm the REAL sets of sources, not bare addresses). iOS
    remembers «Always Allow» for a host together with the sources of what is sent, so the Setup sends to every host
    what a run sends there, at each stage, through the same fetch() and read_page():
      stage 1 (the search, a page linked in the question): TAG = the query call's answer (Claude);
      stage 3 (the check): TAG + ChatGPT's and Claude's answers;
    and then one short ChatGPT and one short Claude call carry what the search brought (an empty text made from the
    answers of every host), as the answers and the comparison do in a run. `ask_gpt(prompt_uid, uid)` /
    `ask_claude(prompt_uid, uid)` give the one-word calls; `ping`: the one-word request. Without them (the tests of
    the old form) only the addresses are called."""
    net_get, g_net = u(), u()
    acts = [*network_guard(NET), act_get_variable(NET, net_get), if_output(g_net, net_get, 'Variable', 100)]
    if not (ask_gpt and ask_claude and ping):
        for url in warm_up_addresses(L):
            acts.append(act_download(url, u()))
        return acts + [if_close(g_net)]
    warm = 'PolyWarm'
    p0, c0, q, p1, g1, g1t, p2, c2, wg, p3, g3, p4, c4, link, link2 = (u() for _ in range(15))
    acts += [*clear_variable(TAG), *clear_variable(warm),
             # stage 1: the query call (Claude, a text of Duo's own) → every engine, the reader
             act_text(text_token(ping), p0), ask_claude(p0, c0), *add_tag((c0, 'Ask Claude')),
             act_text(text_token('duo'), q)]
    for side in ('C', 'G'):
        for engine in SIDE_ENGINES[side]:
            acts += fetch(L, engine, (q, 'Text'), warm)
    acts += [act_text(text_token('https://example.com/'), link),
             *read_page((link, 'Text'), PAGE_RX, 'PolyWarmPage'),
             *warm_card_link(warm),
             # stage 3: ChatGPT's answer and Claude's (which saw ChatGPT's, as the comparison does) join TAG
             act_text(text_token(ping), p1), ask_gpt(p1, g1),
             act_text(text_token('{A}', {'A': (g1, 'Ask ChatGPT')}), g1t), *add_tag((g1t, 'Text')),
             act_text(text_token(ping + '{A}', {'A': (g1t, 'Text')}), p2), ask_claude(p2, c2),
             *add_tag((c2, 'Ask Claude'))]
    # (the check of 24.11, Opus: deep research's second round sends ChatGPT's new query to ALL its engines, ddg too)
    for engine in dict.fromkeys(CLAIM_ENGINES + SIDE_ENGINES['G']):
        acts += fetch(L, engine, (q, 'Text'), warm)
    acts += [act_text(text_token('https://example.com/'), link2),
             *read_page((link2, 'Text'), PAGE_RX, 'PolyWarmPage'),
             *warm_card_link(warm),
             # the answers: what the search brought (the cards) goes to ChatGPT and to Claude
             act_get_variable(warm, wg)]
    e, c2t, g3t, p5, c5, p6, c6, p7, g7 = (u() for _ in range(9))
    acts += [act_replace_regex(wg, 'Variable', TAG_RX, '', e),
             act_text(text_token('{C}', {'C': (c2, 'Ask Claude')}), c2t),
             act_text(text_token(ping + '{E}', {'E': (e, 'Updated Text')}), p3), ask_gpt(p3, g3),
             act_text(text_token('{G}', {'G': (g3, 'Ask ChatGPT')}), g3t),
             act_text(text_token(ping + '{E}{G}', {'E': (e, 'Updated Text'), 'G': (g3t, 'Text')}), p4),
             ask_claude(p4, c4),
             # (the check of 24.11, Opus: the sets of a run — Claude's own answer from its cards alone; the judge and a
             # continued answer from the cards, ChatGPT's and Claude's answers; ChatGPT's continuation from its cards
             # and its own answer)
             act_text(text_token(ping + '{E}', {'E': (e, 'Updated Text')}), p5), ask_claude(p5, c5),
             act_text(text_token(ping + '{E}{G}{C}', {'E': (e, 'Updated Text'), 'G': (g3t, 'Text'),
                                                      'C': (c2t, 'Text')}), p6), ask_claude(p6, c6),
             act_text(text_token(ping + '{E}{G}', {'E': (e, 'Updated Text'), 'G': (g3t, 'Text')}), p7), ask_gpt(p7, g7),
             *clear_variable(warm), *clear_variable(TAG)]
    return acts + [if_close(g_net)]


# ------------------------------------------------------------------ the sources under the result

def card_numbers():
    """(prefix, highest number) of every list Duo may print."""
    top = CARDS_MAX + ROUND2_MAX
    return [(p, top) for p in prefixes()] + [('V', CLAIMS_MAX), ('U', 1)]


def append_sources(L, result_var):
    """Under the result: «Sources» with the entries whose numbers the text really cites — written by Duo from its own
    data, so a link that was never fetched cannot appear. No number cited (an ordinary question) → nothing is added."""
    g_r, g_c, res, c_get, r_get, out = (u() for _ in range(6))
    acts = [*clear_variable(CITED),
            *if_text(g_r, result_var),
            act_get_variable(result_var, res)]
    for prefix, top in card_numbers():
        lst = u()
        acts.append(act_get_variable({'V': LIST_V, 'U': LIST_U}.get(prefix) or list_var(prefix), lst))
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
