"""Duo 6.11, the one round of fixes after the one check of 23.11.2026 (opus, fable, agy, sol, astra, kimi): each
fixed finding has its test here — on Duo's own regular expressions (run as Shortcuts runs them: «Match Text» ignores
case, «Replace Text» does not) and on the built shortcut."""
import re

import pytest

from test_first_run import LANGS, build, is_step, kind
from test_search import FIX, critiques, icu, params, records, refs_of, replace, run, text_of, var_reads, ui_of

import shortcut_search as S  # noqa: E402  (test_search put src/ on the path)
import build_shortcut as B  # noqa: E402
from shortcut_actions import Locale  # noqa: E402
from shortcut_transforms import CUT_CHARS, cut_rx, more_or_cut_rx  # noqa: E402


def match(pattern, text):
    """«Match Text»: case-insensitive (WFMatchTextCaseSensitive False)."""
    return re.search(icu(pattern), text, re.I)


# ------------------------------------------------------------------ 1. the age of a card (sol, agy)

def test_the_age_is_taken_without_its_sign_and_the_date_is_made_a_date_first(tmp_path):
    for raw, shown in (('-12', '12'), ('12', '12'), ('−40', '40'), ('0', '0')):
        assert replace(raw, S.AGE_SIGN_RX) == shown
    actions = build(tmp_path, 'en')
    (s1, e1), (s2, e2) = critiques(actions)
    between = [i for i, a in enumerate(actions) if kind(a) == 'gettimebetweendates'
               and params(a)['WFTimeUntilUnit'] == 'Days' and (s1 <= i < e1 or s2 <= i < e2)
               and {n['OutputName'] for n in params(a)['WFTimeUntilFromDate']['Value']['attachmentsByRange'].values()}
               & {'Dates', 'Matches'}]     # the cards' ages (not the weekly version check's)
    assert between
    for i in between:
        # the earlier date is the output of «Get Dates from Input»
        earlier = refs_of(params(actions[i])['WFTimeUntilFromDate'])
        assert any(kind(a) == 'date' and params(a)['UUID'] in earlier for a in actions[i - 3:i])
        # the number the buckets test is made from the text with the sign taken off
        num = next(a for a in actions[i:i + 12] if kind(a) == 'number')
        src = refs_of(params(num)['WFNumberActionNumber'])
        assert any(kind(a) == 'replace' and params(a)['UUID'] in src
                   and params(a)['WFReplaceTextFind'] == S.AGE_SIGN_RX[0] for a in actions[i:i + 12])


# ------------------------------------------------------------------ 2. newest first inside a bucket (sol)

def test_records_are_sorted_newest_first_before_the_cards(tmp_path):
    lines = ['2026-10-01\tA\tOld\thttps://a/1', '\tB\tUndated\thttps://b/1', '2026-11-22\tC\tNew\thttps://c/1',
             '2026-11-02\tD\tMid\thttps://d/1']
    # «Filter Files», sorted by Name Z→A, on the record lines
    assert sorted(lines, reverse=True) == [lines[2], lines[3], lines[0], lines[1]]
    acts = S.sort_newest_first('PolyRecordsC')
    sort = next(a for a in acts if kind(a) == 'files')
    assert params(sort)['WFContentItemSortProperty'] == 'Name' and params(sort)['WFContentItemSortOrder'] == 'Z to A'
    # should the sort give nothing on some iOS, the variable keeps its first order (it is set only under an If)
    # (the Mac run of 24.11: undated lines carry «0000-00-00» through the sort, set before and taken off after)
    sets = [i for i, a in enumerate(acts) if kind(a) == 'setvariable']
    assert len(sets) == 3 and kind(acts[sets[1] - 1]) != 'setvariable'
    assert any(kind(a) == 'conditional' for a in acts[sets[0] + 1:sets[1]])
    assert sorted([S.UNDATED_MARK + l if l.startswith('\t') else l for l in lines], reverse=True)[-1].startswith(S.UNDATED_MARK)
    actions = build(tmp_path, 'en')
    for start, end in critiques(actions):
        block = actions[start:end]
        first_card = next(i for i, a in enumerate(block) if kind(a) == 'gettimebetweendates')
        assert any(kind(a) == 'files' for a in block[:first_card])


# ------------------------------------------------------------------ 3. one engine does not crowd out the others (fable, astra)

def _many_items(n):
    item = ('<item><title>Story {i} - Paper {i}</title><link>https://news.google.com/rss/articles/{i}</link>'
            '<pubDate>Sun, 22 Nov 2026 08:00:00 GMT</pubDate><source url="https://p{i}.com">Paper {i}</source></item>')
    return '<rss><channel><title>x</title>' + ''.join(item.format(i=i) for i in range(n)) + '</channel></rss>'


def test_each_engine_gives_at_most_engine_max_records_so_the_others_stay():
    pairs = (*S.parse_pairs('gnews'), S.ENGINE_KEEP_RX, S.ENGINE_CUT_RX)
    gnews = run(_many_items(30), pairs)
    assert len(gnews.splitlines()) == S.ENGINE_MAX
    wiki = '2026-11-20\t' + 'Wikipedia\tTim Cook: CEO\thttps://en.wikipedia.org/wiki/Tim_Cook\n'
    ddg = run((FIX / 'duckduckgo.html').read_text(encoding='utf-8'), (*S.DDG_PAIRS, S.ENGINE_KEEP_RX, S.ENGINE_CUT_RX))
    side = run('\n' + gnews + '\n' + wiki + '\n' + ddg + '\n', S.CLEAN_PAIRS)
    seen = re.match(S.SEEN_RX, side).group()
    assert 'wikipedia.org/wiki/Tim_Cook' in seen and 'apple.com/leadership' in seen
    # every record a side can get (7 answers at most) is looked at before the cut to CARDS_MAX
    assert S.RECORDS_SEEN >= 7 * S.ENGINE_MAX
    # a short answer is not touched by the cut
    two = run(_many_items(2), pairs)
    assert len(two.splitlines()) == 2


# ------------------------------------------------------------------ 4. reprints are glued by the whole headline (astra)

def test_headlines_that_only_start_alike_are_two_cards_and_a_reprint_is_one():
    keep = '2026-11-01\t\u0420\u0411\u041a\t\u0411\u0430\u043d\u043a \u0420\u043e\u0441\u0441\u0438\u0438 \u043f\u0440\u0438\u043d\u044f\u043b \u0440\u0435\u0448\u0435\u043d\u0438\u0435 \u0441\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u043a\u043b\u044e\u0447\u0435\u0432\u0443\u044e \u0441\u0442\u0430\u0432\u043a\u0443\thttps://rbc.ru/1\n'
    raise_ = '2026-11-01\t\u0422\u0410\u0421\u0421\t\u0411\u0430\u043d\u043a \u0420\u043e\u0441\u0441\u0438\u0438 \u043f\u0440\u0438\u043d\u044f\u043b \u0440\u0435\u0448\u0435\u043d\u0438\u0435 \u043f\u043e\u0432\u044b\u0441\u0438\u0442\u044c \u043a\u043b\u044e\u0447\u0435\u0432\u0443\u044e \u0441\u0442\u0430\u0432\u043a\u0443\thttps://tass.ru/2\n'
    reprint = '2026-11-01\t\u0418\u0437\u0432\u0435\u0441\u0442\u0438\u044f\t\u0411\u0430\u043d\u043a \u0420\u043e\u0441\u0441\u0438\u0438 \u043f\u0440\u0438\u043d\u044f\u043b \u0440\u0435\u0448\u0435\u043d\u0438\u0435 \u0441\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c \u043a\u043b\u044e\u0447\u0435\u0432\u0443\u044e \u0441\u0442\u0430\u0432\u043a\u0443 — \u0421\u043d\u0438\u043f\u0435\u0442\thttps://iz.ru/3\n'
    glued = replace(keep + raise_ + reprint, S.SAME_TITLE_RX, S.DEDUP_PASSES)
    assert glued == keep + raise_
    # a different snippet does not make another story; another case of letters neither
    other = '2026-11-01\tBBC\tbank of russia decided to keep the key rate — x\thttps://bbc/1\n'
    same = '2026-11-01\tCNN\tBank of Russia decided to keep the key rate — y\thttps://cnn/1\n'
    assert replace(other + same, S.SAME_TITLE_RX, S.DEDUP_PASSES) == other


# ------------------------------------------------------------------ 5. a year that starts a query stays (fable, astra)

def test_query_cleaning_keeps_a_leading_year_and_takes_list_marks_off():
    reply = '2026 Formula 1 champion\n1. "ECB deposit rate 2026"\n2) «\u0411\u0430\u043d\u043a \u0420\u043e\u0441\u0441\u0438\u0438 \u0441\u0442\u0430\u0432\u043a\u0430»\n- 3 percent rule'
    clean = re.sub(S.QUERY_CLEAN_RX, '', reply)
    assert clean.splitlines() == ['2026 Formula 1 champion', 'ECB deposit rate 2026', '\u0411\u0430\u043d\u043a \u0420\u043e\u0441\u0441\u0438\u0438 \u0441\u0442\u0430\u0432\u043a\u0430',
                                  '3 percent rule']


# ------------------------------------------------------------------ 6. «§ » inside a headline (fable)

def test_a_paragraph_sign_in_a_headline_does_not_take_the_number():
    packet = (S.MARK + '2026-11-01 (22 d ago) · LTO · Mieter: § 573 BGB und Eigenbedarf\n'
              + S.MARK + '2026-11-02 (21 d ago) · FAZ · Kündigung\n')
    for n in (1, 2):
        packet = replace(packet, (S.NUMBER_RX, '$1[C%d] ' % n))
    assert packet.splitlines() == ['[C1] 2026-11-01 (22 d ago) · LTO · Mieter: § 573 BGB und Eigenbedarf',
                                   '[C2] 2026-11-02 (21 d ago) · FAZ · Kündigung']


# ------------------------------------------------------------------ 7. the primary source's site, any case, any tail (opus)

@pytest.mark.parametrize('site, host', [('ecb.europa.eu (official site)', 'ecb.europa.eu'),
                                        ('ECB.europa.eu', 'ECB.europa.eu'),
                                        ('https://www.ecb.europa.eu/press/pr', 'ecb.europa.eu'),
                                        ('ecb.europa.eu', 'ecb.europa.eu')])
def test_claim_site_is_read_whatever_its_case_and_tail(site, host):
    line = 'ECB deposit rate is 2.00% || ECB deposit facility rate || ' + site
    assert match(S.CLAIM_NO_SITE_RX, line)                 # the If lets it through …
    assert replace(line, S.CLAIM_SITE_RX) == ' site:' + host   # … and the query really gets only the site


# ------------------------------------------------------------------ 8. one claim is checked once (astra)

def test_a_single_claim_line_is_checked_once():
    one = 'Ternus became CEO on 1 September 2026 || Apple CEO Ternus September || apple.com'
    assert not re.search(S.CLAIM_LINE_RX, replace(one, (S.CLAIM_REST_RX, '')))
    # a line of other text before the claims: the second round takes the SECOND claim, not the first again
    reply = 'Here are the claims:\n' + one + '\nECB rate is 2% || ECB deposit rate || -'
    first = re.search(S.CLAIM_LINE_RX, reply).group()
    second = re.search(S.CLAIM_LINE_RX, replace(reply, (S.CLAIM_REST_RX, ''))).group()
    assert first == one and second.startswith('ECB rate is 2%')


# ------------------------------------------------------------------ 9. a second link on the same site (agy)

def test_a_deeper_page_of_the_same_site_is_the_second_link():
    answer = 'See https://www.ecb.europa.eu and the table https://www.ecb.europa.eu/stats/rates.html.'
    assert match(S.LINK2_TEST_RX, answer)
    assert replace(answer, S.LINK2_RX) == 'https://www.ecb.europa.eu/stats/rates.html'
    twice = 'Source: https://www.ecb.europa.eu, again https://www.ecb.europa.eu.'
    assert not match(S.LINK2_TEST_RX, twice)


# ------------------------------------------------------------------ 10. one reader for every page (fable, opus, agy, sol)

READER_OK = ('Title: Tim Cook\n\nURL Source: https://en.wikipedia.org/wiki/Tim_Cook\n\nPublished Time: 2005-04-11\n\n'
             'Markdown Content:\n![Image 1](https://x/y.jpg)\n# Tim Cook\n[Apple Inc.](https://en.wikipedia.org/a) '
             'chief executive until **2026**.\n- served as COO')
READER_DEAD = ('{"data":null,"path":"url","code":422,"name":"SubmittedDataMalformedError","status":42203,'
               '"message":"Domain \'dead.example\' could not be resolved"}')
READER_404 = 'Title: Not found\n\nURL Source: https://x\n\nWarning: Target URL returned error 404: Not Found\n\nMarkdown Content:\n…'
READER_LIMIT = '{"data":null,"code":429,"name":"RateLimitTriggeredError","message":"Per IP rate limit exceeded"}'


def test_the_reader_answer_is_read_as_text_and_a_dead_page_is_no_page():
    assert match(S.READER_OK_RX, READER_OK) and not match(S.READER_DEAD_RX, READER_OK)
    page = run(READER_OK, S.MD_STRIP)
    assert 'Published Time: 2005-04-11' in page and 'Apple Inc. chief executive' in page
    assert 'https://' not in page and '![' not in page and '# ' not in page
    for gone in (READER_DEAD, READER_404):
        assert match(S.READER_DEAD_RX, gone)               # the page is gone: no direct download either
    # the reader's own limit: not a dead page → the direct download, the spare
    assert not match(S.READER_DEAD_RX, READER_LIMIT) and not match(S.READER_OK_RX, READER_LIMIT)


def test_read_page_goes_through_the_reader_and_never_through_safari_reader():
    acts = S.read_page(('X', 'Text'), S.PAGE_RX, 'PolyPageCut')
    assert not any(kind(a) == 'getarticle' for a in acts)
    first_text = next(a for a in acts if kind(a) == 'gettext')
    assert text_of(first_text).startswith(S.READER)
    downloads = [i for i, a in enumerate(acts) if kind(a) == 'downloadurl']
    # the council of 24.11 (OpenAI, agy): the reader only — a direct download asked a NEW site's permission mid-answer
    assert len(downloads) == 1
    # the run's TAG rides on the reader's address (one set of sources per stage)
    assert '{TAG}' not in text_of(first_text) and S.TAG in str(acts)


# ------------------------------------------------------------------ 11. a resumed Critique keeps ChatGPT's cards (opus, kimi)

def test_resumed_critique_restores_chatgpts_cards_and_saves_the_draft_before_searching(tmp_path):
    actions = build(tmp_path, 'en')
    (_, _), (start, end) = critiques(actions)
    block = actions[start:end]
    first_save = next(i for i, a in enumerate(block) if kind(a) == 'documentpicker.save' or kind(a) == 'save')
    search = next(i for i, a in enumerate(block) if is_step(a, 'search'))
    research = [i for i, a in enumerate(block) if is_step(a, 'research')]
    assert first_save < search                     # step 0 is on disk before any search (kimi)
    assert research and all(first_save < i for i in research)
    # the step-1 draft holds ChatGPT's packet and source list
    step1 = [a for a in block if kind(a) == 'gettext' and text_of(a).startswith(B.DRAFT_STEP1)]
    assert step1 and B.DRAFT_GP in text_of(step1[0]) and B.DRAFT_GL in text_of(step1[0])
    reads = var_reads(block)
    used = {reads.get(r) for r in refs_of(params(step1[0]))}
    assert {S.packet_var('G'), S.list_var('G')} <= used
    # restored after the new search, before the answers, only when ChatGPT's answer came from the draft
    sets = [i for i, a in enumerate(block) if kind(a) == 'setvariable'
            and params(a)['WFVariableName'] in (S.packet_var('G'), S.list_var('G'))
            and reads.get(next(iter(refs_of(params(a)['WFInput'])), None)) in ('PolyKeptCardsG', 'PolyKeptListG')]
    assert len(sets) == 2 and all(search < i for i in sets)
    # deep research is not run again on a resumed run
    gate = [j for j in range(research[0] - 8, research[0]) if kind(block[j]) == 'conditional'
            and params(block[j]).get('WFCondition') == 101]
    assert any(reads.get(params(block[g - 2]).get('UUID')) == 'PolyResume' for g in gate
               if kind(block[g - 2]) == 'getvariable')


def test_the_draft_answer_and_its_cards_are_read_back_apart():
    draft = (B.DRAFT_STEP1 + '\n' + B.DRAFT_Q + '\nWho is CEO?\n' + B.DRAFT_A + '\nTernus [G2].\n' + B.DRAFT_GP
             + '\n[G1] x\n[G2] y\n' + B.DRAFT_GL + '\n[G2] 2026-09-01 · Reuters · Ternus\nhttps://r/1\n')
    answer = re.search(icu('(?s)(?<=' + B.DRAFT_A + '\\n).*?(?=\\n' + B.DRAFT_GP + '|\\z)'), draft).group()
    assert answer == 'Ternus [G2].'
    packet = re.search(icu('(?s)(?<=' + B.DRAFT_GP + '\\n).*?(?=\\n' + B.DRAFT_GL + ')'), draft).group()
    listed = re.search(icu('(?s)(?<=' + B.DRAFT_GL + '\\n).*'), draft).group()
    assert packet == '[G1] x\n[G2] y' and re.search(S.source_entry_rx('G', 2), listed)
    # a draft of 6.10 (no cards) still gives its whole answer
    old = B.DRAFT_STEP1 + '\n' + B.DRAFT_Q + '\nQ\n' + B.DRAFT_A + '\nA whole answer.'
    assert re.search(icu('(?s)(?<=' + B.DRAFT_A + '\\n).*?(?=\\n' + B.DRAFT_GP + '|\\z)'), old).group() == 'A whole answer.'


# ------------------------------------------------------------------ 12. Google News cards in deep research (fable, agy, opus, kimi)

def test_a_google_news_pick_is_found_again_by_its_headline():
    picks = ('C2 2026-11-22 · Reuters · Apple names Ternus CEO\nhttps://news.google.com/rss/articles/CBMi\n'
             'C5 \u0431\u0435\u0437 \u0434\u0430\u0442\u044b · ecb.europa.eu · Key rates\nhttps://www.ecb.europa.eu/x\n')
    lines = replace(picks, S.PICK_LINE_RX).splitlines()
    assert lines == ['C2 https://news.google.com/rss/articles/CBMi Apple names Ternus CEO',
                     'C5 https://www.ecb.europa.eu/x Key rates']
    assert replace(lines[0], S.PICK_URL_RX) == 'https://news.google.com/rss/articles/CBMi'
    assert replace(lines[0], S.PICK_TITLE_RX) == 'Apple names Ternus CEO'
    assert match(S.GNEWS_LINK_RX, replace(lines[0], S.PICK_URL_RX))
    assert not match(S.GNEWS_LINK_RX, replace(lines[1], S.PICK_URL_RX))
    # «U1» (the question's page) in the model's reply is not card 1
    assert not re.search(r'(?<![\dU])%d(?![\d])' % 1, 'U1, C12')
    assert re.search(r'(?<![\dU])%d(?![\d])' % 1, 'U1, C1')


def test_research_looks_a_google_news_headline_up_in_the_web_index(tmp_path):
    actions = build(tmp_path, 'en')
    (_, _), (start, end) = critiques(actions)
    block = actions[start:end]
    gn = [i for i, a in enumerate(block) if kind(a) == 'match' and params(a)['WFMatchTextPattern'] == S.GNEWS_LINK_RX]
    assert len(gn) >= 4        # each model, both rounds
    for i in gn:
        nxt = next(a for a in block[i:i + 30] if kind(a) == 'gettext' and text_of(a).startswith('https://'))
        assert text_of(nxt).startswith('https://www.bing.com/search?q=')


# ------------------------------------------------------------------ 13. NONE: no divergence search either (kimi)

def test_a_question_the_web_cannot_help_has_no_divergence_search(tmp_path):
    actions = build(tmp_path, 'en')
    for start, end in critiques(actions):
        block = actions[start:end]
        reads = var_reads(block)
        i = next(i for i, a in enumerate(block) if is_step(a, 'divergence'))
        gates = [j for j in range(i - 40, i) if kind(block[j]) == 'conditional'
                 and params(block[j]).get('WFCondition') == 101]
        assert any(reads.get(params(block[g - 2]).get('UUID')) == S.NOWEB for g in gates
                   if kind(block[g - 2]) == 'getvariable')
        assert any(kind(a) == 'setvariable' and params(a)['WFVariableName'] == S.NOWEB for a in block)


# ------------------------------------------------------------------ No.112: the link in the question is read first

def test_a_link_in_the_question_is_read_first_and_given_to_both_models(tmp_path):
    actions = build(tmp_path, 'en')
    for start, end in critiques(actions):
        block = actions[start:end]
        asked = next(i for i, a in enumerate(block) if is_step(a, 'asked_page'))
        first_answer = next(i for i, a in enumerate(block) if is_step(a, 'critique_blind'))
        assert asked < first_answer
        part = block[asked:first_answer]
        assert any(kind(a) == 'gettext' and text_of(a).startswith(S.READER) for a in part)
        appended = {params(a)['WFVariableName'] for a in part[:80] if kind(a) == 'setvariable'}
        assert {S.packet_var('C'), S.packet_var('G'), S.LIST_U} <= appended
    assert ('U', 1) in S.card_numbers()
    assert re.search(S.cited_rx('U', 1), 'As the page says [U1].')
    entry = re.search(S.source_entry_rx('U', 1), '[U1] https://cbr.ru/press/1\n').group()
    assert entry == '[U1] https://cbr.ru/press/1'


# ------------------------------------------------------------------ the first run: every «Allow» window at the Setup

@pytest.mark.parametrize('lang', ['en', 'ru'])
def test_setup_calls_every_search_host_and_the_reader_once(tmp_path, lang):
    """The council of 24.11: the Setup warms the REAL sets of sources — every engine through fetch() and the reader
    through read_page(), with the query call's TAG (stage 1), then with ChatGPT's and Claude's (stage 3), then one
    ChatGPT and one Claude call carry what the search brought — behind the local-IP guard, before «ready»."""
    actions = build(tmp_path, lang)
    assert len(S.warm_up_addresses(Locale(lang))) == 5
    ready = Locale(lang)['speak.ready']
    ready_at = next(i for i, a in enumerate(actions) if kind(a) == 'notification' and ready in str(params(a)))
    setup = actions[max(0, ready_at - 1600):ready_at]
    texts = [text_of(a) for a in setup if kind(a) == 'gettext']
    wiki = ui_of(lang)['search']['wiki']
    for host in ('news.google.com', f'{wiki}.wikipedia.org', 'www.bing.com/news', 'www.bing.com/search',
                 'html.duckduckgo.com', 'r.jina.ai'):
        assert any(t.startswith('https://' + host) for t in texts), host
    assert any(kind(a) == 'getipaddress' for a in setup)
    assert not any(kind(a) == 'getwifi' for a in actions)
    assert sum(kind(a) == 'setitemname' for a in setup) >= 7      # 5 engines + the 2 claim engines again


# ------------------------------------------------------------------ No.158: an answer cut off without the marker

def test_an_answer_cut_off_without_the_marker_is_continued_and_a_finished_one_is_not():
    body = 'The European Central Bank kept its deposit facility rate unchanged at the meeting. ' * 50
    for output, chars in CUT_CHARS.items():
        rx = icu(more_or_cut_rx(output))
        long = body[:chars + 200]
        assert re.search(rx, long.rstrip('. ') + ' and the next decision is due on the eighteenth of')
        assert not re.search(rx, long.rstrip() + '.')                  # ends on a full stop
        assert not re.search(rx, long + '\n- check ecb.europa.eu for the date')   # a list line
        assert not re.search(rx, long + '\nSources: [C2]')                      # a source code
        assert not re.search(rx, 'A short answer without a full stop at the end of the last line')
        assert re.search(rx, 'Part one. [[MORE]]')
    assert cut_rx(1600) != cut_rx(3200)


def test_continue_prompt_resolves_the_split_judge():
    for lang, phrase in (('en', 'write the rest'), ('ru', '\u043f\u0438\u0448\u0438 \u043e\u0441\u0442\u0430\u043b\u044c\u043d\u043e\u0435')):
        assert phrase in Locale(lang).prompt('continue')


# ------------------------------------------------------------------ the test shortcut (No.45)

def test_the_probe_shortcut_is_small_and_reaches_every_host(tmp_path):
    import build_probe
    acts = build_probe.actions('ru')
    assert 10 <= len(acts) <= 40
    urls = ' '.join(str(params(a).get('WFURL', '')) + text_of(a) for a in acts)
    for host in ('news.google.com', 'ru.wikipedia.org', 'www.bing.com', 'html.duckduckgo.com', 'r.jina.ai'):
        assert host in urls, host
    assert any(kind(a) == 'gettimebetweendates' for a in acts)
