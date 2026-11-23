"""Duo 6.11: search without keys, done by the shortcut itself (the owner's decisions of 23.11.2026).

«Ask Claude» has no web search and «Ask ChatGPT» answered fresh questions from memory (the 22.11 timings on the iPhone), so Duo fetches
dated sources itself, before any model is asked:

  1. Google News RSS («Get Items from RSS Feed», the edition of the build's language and country) with the question;
  2. when the question looks fresh: one short Claude call gives two search queries made of the question's own words,
     and Duo searches twice more;
  3. nothing found → GDELT DOC API; fewer than WIKI_BELOW records → one Wikipedia article with its last edit date;
  4. the records are filtered, de-duplicated by origin (one publisher once, one headline once), cut to SEARCH_MAX,
     dated «N days ago» and numbered [1]…[N] BY DUO. PACKET (no links) goes to Claude's own answer and to the
     comparing step; SOURCE_LIST (with links) is what Duo itself prints under the result for the numbers cited.

Every network step sits behind the guard that cannot throw (network_guard) and behind a test of the downloaded
text; anything unexpected (offline, a rate-limit page, an empty feed) leaves the packet empty, and the run goes on
from memory without a word.

A record is one line: DATE<tab>PUBLISHER<tab>TITLE<tab>URL. The regexes below are ICU (Shortcuts) and are written
in the subset Python's `re` shares, so tests/test_search.py runs them on saved answers of the three services.
"""
from shortcut_actions import *  # noqa: F401,F403
from shortcut_actions import iso_date

SEARCH_MAX = 5            # sources in a packet
RSS_ITEMS = 8             # items taken from one feed (before de-duplication)
WIKI_BELOW = 3            # fewer records than this → one Wikipedia article is added
QUERY_CHARS = 100         # the first search is the question's first line, at most this long
QUERY_MAX = 80            # one query from Claude, at most this long
LINK_MAX = 2              # pages cited by ChatGPT that are downloaded and checked (each: one short Claude call)
PAGE_CHARS = 3000         # of a page's text go to the check
DEDUP_PASSES = 3

GNEWS_URL = 'https://news.google.com/rss/search?q={Q}&'    # + ui «search.news» (hl, gl, ceid: all three are needed)
GDELT_URL = ('https://api.gdeltproject.org/api/v2/doc/doc?query={Q}&mode=artlist&maxrecords=8&format=json'
             '&sort=DateDesc&timespan=3m')
WIKI_URL = ('https://{LANG}.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch={Q}&gsrlimit=1'
            '&prop=extracts%7Cinfo%7Crevisions&exintro=1&explaintext=1&exchars=400&inprop=url&rvprop=timestamp'
            '&format=json&utf8=1')

# ---- the question
QUERY_RX = r'\A\s*[^\n]{1,%d}' % QUERY_CHARS
# fresh in any language: a year from 2024 on; the words of each language come from ui «search.fresh_words»
FRESH_ANY = r'(?<!\d)20(?:2[4-9]|3\d)(?!\d)'
# ---- records
RECORD_RX = r'^(\d{4}-\d\d-\d\d)\t([^\t\n]*)\t([^\t\n]+)\t(\S+)[ \t]*$'
NOT_RECORD_RX = r'(?m)^(?!\d{4}-\d\d-\d\d\t[^\t\n]*\t[^\t\n]+\t\S+[ \t]*$)[^\n]*\n?'
RECORD_LINES_RX = r'(?m)^\d{4}-\d\d-\d\d\t[^\n]+$'
# Google News: «Headline - Publisher» in the title → the publisher's own field
RSS_PUBLISHER_RX = (r'(?m)^(\d{4}-\d\d-\d\d)\t\t([^\t\n]*) - ([^\t\n]*)\t', '$1\t$3\t$2\t')
# GDELT artlist: one article object → one record line (anything else in the answer is dropped by NOT_RECORD_RX)
GDELT_RX = (r'\{\s*"url"\s*:\s*"([^"\s]+)"[^{}]*?"title"\s*:\s*"((?:[^"\\]|\\.)*)"[^{}]*?'
            r'"seendate"\s*:\s*"(\d{4})(\d\d)(\d\d)[^"]*"[^{}]*?"domain"\s*:\s*"([^"]*)"[^{}]*\}',
            '\n$3-$4-$5\t$6\t$2\t$1\n')
# Wikipedia (gsrlimit=1: one page in the answer)
WIKI_TITLE_RX = r'(?<="title":")(?:[^"\\]|\\.)+'
WIKI_DATE_RX = r'(?<="timestamp":")\d{4}-\d\d-\d\d'
WIKI_LINK_RX = r'(?<="fullurl":")[^"\s]+'
WIKI_TEXT_RX = r'(?<="extract":")(?:[^"\\]|\\.)+'
# JSON escapes left in a title: \" \/ → the character, \n \t → a space
UNESCAPE = ((r'\\[nrt]', ' '), (r'\\(["/\\])', '$1'))
# one origin once: a later line of the same publisher, then a later line whose headline starts the same way
SAME_PUBLISHER_RX = (r'(?im)^([^\t\n]*\t([^\t\n]+)\t[^\n]*\n(?:[^\n]*\n)*?)[^\t\n]*\t\2\t[^\n]*\n', '$1')
SAME_TITLE_RX = (r'(?im)^([^\t\n]*\t[^\t\n]*\t([^\t\n]{25})[^\n]*\n(?:[^\n]*\n)*?)[^\t\n]*\t[^\t\n]*\t\2[^\n]*\n',
                 '$1')
FIRST_RECORDS_RX = r'\A(?:[^\n]*\n){1,%d}' % SEARCH_MAX
ENOUGH_RX = r'\A(?:[^\n]*\n){%d}' % WIKI_BELOW
MARK = '§ '               # stands where Duo puts the number
NUMBER_RX = r'(?s)\A(.*?)§ '
# ---- queries from Claude: list marks and quotes off, then line 1 and line 2
QUERY_CLEAN_RX = r'(?m)^[\s\-\*•\d\.\)"«“„]+|["»”]+[ \t]*$'
QUERY_LINE_RX = r'\A[^\n]{3,%d}' % QUERY_MAX
QUERY_REST_RX = r'\A[^\n]*\n+'
# ---- links in ChatGPT's answer
_U = r'https?://[^\s\)\]>"\'»”]*[^\s\)\]>"\'»”.,;:!?]'
LINK_RX = _U
LINK1_RX = (r'(?s)\A.*?(' + _U + r').*\z', '$1')
LINK2_RX = (r'(?s)\A.*?(' + _U + r').*?(?!\1)(' + _U + r').*\z', '$2')
LINK2_TEST_RX = r'(?s)(' + _U + r').*?(?!\1)(' + _U + r')'
HTML_STRIP = ((r'(?is)<(script|style|noscript|svg|head)\b.*?</\1>', ' '), (r'(?s)<[^>]+>', ' '),
              (r'&nbsp;|&#160;', ' '), (r'\s{2,}', ' '))
PAGE_RX = r'(?s)\A.{1,%d}' % PAGE_CHARS


def fresh_regex(words):
    """A question that looks fresh: a recent year, or one of the language's own words (ui «search.fresh_words»)."""
    return FRESH_ANY + '|(?i:' + words + ')'


def cited_rx(n):
    """[n] in a text, also inside «[1, 2]»."""
    return r'\[(?:\d\s*[,;]\s*)*%d(?:\s*[,;]\s*\d)*\]' % n


def source_entry_rx(n):
    """Entry n of SOURCE_LIST: its line and the link under it."""
    return r'(?m)^\[%d\] [^\n]*(?:\n(?!\[\d\] )[^\n]+)?' % n


# variables
NET, RECORDS, PACKET, SOURCE_LIST, CITED = 'PolyNet', 'PolyRecords', 'PolySources', 'PolySourceList', 'PolyCited'
QUERIES, PAGE, LINKS, FRESH, VERDICT = 'PolyQueries', 'PolyPage', 'PolyLinkChecks', 'PolyFresh', 'PolyLinkVerdict'


def u():
    return new_uuid()


def append_to(var, template, refs):
    """<var> = <var> + a text ({V} is the variable's present text; an unset variable reads as nothing)."""
    get, txt = u(), u()
    return [act_get_variable(var, get), act_text(text_token('{V}' + template, {**refs, 'V': (get, 'Variable')}), txt),
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


def news_fetch(L, query_uid, query_name):
    """One Google News search: the feed is first read as text (an error page or a rate limit has no <item>, and the
    RSS action is never run on it), then «Get Items from RSS Feed»; each item becomes a record line."""
    enc, url, pre, pre_t, g, rss, g_rep, item, title, date, link, flat, get, line = (u() for _ in range(14))
    address = GNEWS_URL + L['search.news']
    return [
        act_urlencode(query_uid, query_name, enc),
        act_text(text_token(address, {'Q': (enc, 'URL Encoded Text')}), url),
        act_download(text_token('{U}', {'U': (url, 'Text')}), pre),
        act_text(text_token('{C}', {'C': (pre, 'Contents of URL')}), pre_t),
        if_output(g, pre_t, 'Text', 99, WFConditionalActionString='<item>'),
        act_rss(text_token('{U}', {'U': (url, 'Text')}), RSS_ITEMS, rss),
        repeat_open(g_rep, rss, 'Items from RSS Feed'),
        act_get_variable('Repeat Item', item),
        act_article_detail(item, 'Variable', 'Title', title),
        act_article_detail(item, 'Variable', 'Published Date', date),
        act_article_detail(item, 'Variable', 'URL', link),
        act_replace_regex(title, 'Title', r'\s+', ' ', flat),
        # the date as yyyy-MM-dd, whatever the phone's region
        act_get_variable(RECORDS, get),
        act_text(text_token('{V}{D}\t\t{T}\t{U}\n', {'V': (get, 'Variable'), 'T': (flat, 'Updated Text'),
                                                       'U': (link, 'URL')},
                            {'D': iso_date(date, 'Published Date')}), line),
        act_set_variable(RECORDS, line, 'Text'),
        repeat_close(g_rep),
        if_close(g),
    ]


def gdelt_fetch(query_uid, query_name):
    enc, url, dl, txt, g, rec = (u() for _ in range(6))
    return [
        act_urlencode(query_uid, query_name, enc),
        act_text(text_token(GDELT_URL, {'Q': (enc, 'URL Encoded Text')}), url),
        act_download(text_token('{U}', {'U': (url, 'Text')}), dl),
        act_text(text_token('{C}', {'C': (dl, 'Contents of URL')}), txt),
        # only an answer with articles is read (a rate-limit notice or an error is plain text)
        if_output(g, txt, 'Text', 99, WFConditionalActionString='"seendate"'),
        act_replace_regex(txt, 'Text', GDELT_RX[0], GDELT_RX[1], rec),
        *append_to(RECORDS, '{R}\n', {'R': (rec, 'Updated Text')}),
        if_close(g),
    ]


def wiki_fetch(L, query_uid, query_name):
    enc, url, dl, txt, g, title, date, link, body = (u() for _ in range(9))
    address = WIKI_URL.replace('{LANG}', L['search.wiki'])
    return [
        act_urlencode(query_uid, query_name, enc),
        act_text(text_token(address, {'Q': (enc, 'URL Encoded Text')}), url),
        act_download(text_token('{U}', {'U': (url, 'Text')}), dl),
        act_text(text_token('{C}', {'C': (dl, 'Contents of URL')}), txt),
        if_output(g, txt, 'Text', 99, WFConditionalActionString='"fullurl"'),
        act_first_match(txt, 'Text', WIKI_TITLE_RX, title),
        act_first_match(txt, 'Text', WIKI_DATE_RX, date),
        act_first_match(txt, 'Text', WIKI_LINK_RX, link),
        act_first_match(txt, 'Text', WIKI_TEXT_RX, body),
        *append_to(RECORDS, '{D}\t' + L['search.wiki_label'] + '\t{T}: {B}\t{U}\n',
                   {'D': (date, 'Matches'), 'T': (title, 'Matches'), 'B': (body, 'Matches'), 'U': (link, 'Matches')}),
        if_close(g),
    ]


def search_block(L, qsrc, long_question, claude_query):
    """Actions that leave PACKET (for the models) and SOURCE_LIST (for the person) set, or without a value.
    `qsrc`: (action, output) of the question. `long_question`: at this many characters the question is a pasted text
    to work on, not something to look up — no search. `claude_query(prompt_uid, uid)` → the «Ask Claude» action of
    the second pass."""
    (q_txt, q_cnt, g_long, net_get, g_net, q_cut, fresh, g_fresh, qp, qc, q_all, q1, q_rest, q2, g_q1, g_q2,
     g_none, g_few, few, now, lines, g_rep, item, day, days, age, p_line, s_line, g_any) = (u() for _ in range(29))
    fresh_rx = fresh_regex(L['search.fresh_words'])
    age_text = L['search.age']

    def finish():
        out = []
        for var in (PACKET, SOURCE_LIST):
            get, src = u(), None
            out.append(act_get_variable(var, get))
            src = (get, 'Variable')
            for n in range(1, SEARCH_MAX + 1):
                r = u()
                out.append(act_replace_regex(src[0], src[1], NUMBER_RX, '$1[%d] ' % n, r))
                src = (r, 'Updated Text')
            out.append(act_set_variable(var, *src))
        return out

    return [
        *clear_variable(RECORDS), *clear_variable(PACKET), *clear_variable(SOURCE_LIST), *clear_variable(FRESH),
        act_text(text_token('{Q}', {'Q': qsrc}), q_txt),
        act_count_chars(q_txt, 'Text', q_cnt),
        if_output(g_long, q_cnt, 'Count', 2, WFNumberValue=long_question - 1),
        if_else(g_long),
        *network_guard(NET),
        act_get_variable(NET, net_get),
        if_output(g_net, net_get, 'Variable', 100),
        act_step('search'),
        # ---- 1. the question itself (its first line)
        act_first_match(q_txt, 'Text', QUERY_RX, q_cut),
        *news_fetch(L, q_cut, 'Matches'),
        # ---- 2. a fresh question: two queries from Claude, made of the question's own words
        act_first_match(q_txt, 'Text', fresh_rx, fresh),
        if_output(g_fresh, fresh, 'Matches', 100),
        *set_text(FRESH, '1'),
        act_step('search_queries'),
        act_text(text_token(L.prompt('search-queries'), {'Q': qsrc}), qp),
        claude_query(qp, qc),
        act_set_variable(QUERIES, qc, 'Ask Claude'),
        *replace_var(QUERIES, ((QUERY_CLEAN_RX, ''),)),
        act_get_variable(QUERIES, q_all),
        act_first_match(q_all, 'Variable', QUERY_LINE_RX, q1),
        if_output(g_q1, q1, 'Matches', 100),
        *news_fetch(L, q1, 'Matches'),
        act_replace_regex(q_all, 'Variable', QUERY_REST_RX, '', q_rest),
        act_first_match(q_rest, 'Updated Text', QUERY_LINE_RX, q2),
        if_output(g_q2, q2, 'Matches', 100),
        *news_fetch(L, q2, 'Matches'),
        if_close(g_q2),
        if_close(g_q1),
        if_close(g_fresh),
        # ---- 3. the reserves: GDELT when the news feed gave nothing, Wikipedia when there is little
        *replace_var(RECORDS, (RSS_PUBLISHER_RX,)),
        *if_text(g_none, RECORDS, present=False),
        act_step('search_gdelt'),
        *gdelt_fetch(q_cut, 'Matches'),
        if_close(g_none),
        *replace_var(RECORDS, ((NOT_RECORD_RX, ''), *UNESCAPE)),
        *replace_var(RECORDS, (SAME_PUBLISHER_RX, SAME_TITLE_RX), times=DEDUP_PASSES),
        act_get_variable(RECORDS, few),
        act_first_match(few, 'Variable', ENOUGH_RX, lines),
        if_output(g_few, lines, 'Matches', 101),
        act_step('search_wikipedia'),
        *wiki_fetch(L, q_cut, 'Matches'),
        *replace_var(RECORDS, ((NOT_RECORD_RX, ''), *UNESCAPE)),
        if_close(g_few),
        # ---- 4. at most SEARCH_MAX, each with its age in days, numbered by Duo
        *if_text(g_any, RECORDS),
        act_date(now),
        *_dated_lines(now, age_text, g_rep, item, day, days, age, p_line, s_line),
        *finish(),
        if_close(g_any),
        if_close(g_net),
        if_close(g_long),
    ]


def _dated_lines(now, age_text, g_rep, item, day, days, age, p_line, s_line):
    get, first, recs = u(), u(), u()
    return [
        act_get_variable(RECORDS, get),
        act_first_match(get, 'Variable', FIRST_RECORDS_RX, first),
        act_first_match(first, 'Matches', RECORD_LINES_RX, recs),
        repeat_open(g_rep, recs, 'Matches'),
        act_get_variable('Repeat Item', item),
        act_first_match(item, 'Variable', r'^\d{4}-\d\d-\d\d', day),
        act_time_between(now, 'Date', day, 'Matches', 'Days', days),
        act_text(text_token(age_text, {'N': (days, 'Time Between Dates')}), age),
        # for the models: no link (a model can neither open it nor is it to copy it)
        act_replace_regex_token(item, 'Variable', RECORD_RX,
                                text_token(MARK + '$1 ({A}) · $2 · $3', {'A': (age, 'Text')}), p_line),
        *append_to(PACKET, '{L}\n', {'L': (p_line, 'Updated Text')}),
        # for the person: the same line with its link under it
        act_replace_regex(item, 'Variable', RECORD_RX, MARK + '$1 · $2 · $3\n$4', s_line),
        *append_to(SOURCE_LIST, '{L}\n', {'L': (s_line, 'Updated Text')}),
        repeat_close(g_rep),
    ]


def append_sources(L, result_var):
    """Under the result: «Sources» with the entries whose numbers the text really cites — written by Duo from its own
    data, so a link that was never fetched cannot appear. No number cited (an ordinary question) → nothing is added."""
    g_p, g_r, g_c, res, lst, c_get, r_get, out = (u() for _ in range(8))
    acts = [*clear_variable(CITED),
            *if_text(g_p, SOURCE_LIST),
            *if_text(g_r, result_var),
            act_get_variable(result_var, res),
            act_get_variable(SOURCE_LIST, lst)]
    for n in range(1, SEARCH_MAX + 1):
        hit, g, entry = u(), u(), u()
        acts += [act_first_match(res, 'Variable', cited_rx(n), hit),
                 if_output(g, hit, 'Matches', 100),
                 act_first_match(lst, 'Variable', source_entry_rx(n), entry),
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
        if_close(g_p),
    ]


def link_check_block(L, gpt_var, claude_check, skip_var, today):
    """ChatGPT cited pages → Duo downloads up to LINK_MAX of them («Get Contents of URL», then «Get Article using
    Safari Reader»; when the Reader gives nothing, the page's own text with the tags taken off) and asks Claude about
    each in a separate short call whether the page supports what the answer says. LINKS gets one line a page. Runs
    only when the answer holds a link and the network is there; never on a run resumed from a draft (`skip_var`): a
    page that stopped the run once must not stop it again. `claude_check(prompt_uid, uid)` → the «Ask Claude» action;
    `today`: a special attachment (today's date)."""
    ans, found, g_has, g_skip, net_get, g_net = (u() for _ in range(6))
    acts = [*clear_variable(LINKS),
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
        (link, link_t, page, art, art_t, g_blank, html, p_get, cut, g_page, prompt, call, g_v,
         v_get) = (u() for _ in range(14))
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
            act_download(text_token('{U}', {'U': (link_t, 'Text')}), page),
            act_get_article(page, 'Contents of URL', art),
            act_text(text_token('{A}', {'A': (art, 'Article')}), art_t),
            act_set_variable(PAGE, art_t, 'Text'),
            *if_text(g_blank, PAGE, present=False),
            act_text(text_token('{C}', {'C': (page, 'Contents of URL')}), html),
            act_set_variable(PAGE, html, 'Text'),
            *replace_var(PAGE, HTML_STRIP),
            if_close(g_blank),
            *if_text(g_page, PAGE),
            act_get_variable(PAGE, p_get),
            act_first_match(p_get, 'Variable', PAGE_RX, cut),
            act_text(text_token(L.prompt('link-check'),
                                {'URL': (link_t, 'Text'), 'ANSWER': (ans, 'Variable'), 'PAGE': (cut, 'Matches')},
                                {'TODAY': today}), prompt),
            claude_check(prompt, call),
            act_set_variable(VERDICT, call, 'Ask Claude'),
            *if_text(g_v, VERDICT),
            act_get_variable(VERDICT, v_get),
            *append_to(LINKS, '• {U} — {V}\n', {'U': (link_t, 'Text'), 'V': (v_get, 'Variable')}),
            if_close(g_v),
            if_else(g_page),
            *append_to(LINKS, '• {U} — ' + L['search.link_unread'] + '\n', {'U': (link_t, 'Text')}),
            if_close(g_page),
        ]
    return acts + closers + [if_close(g_net), if_close(g_has), if_close(g_skip)]
