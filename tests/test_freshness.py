"""Freshness (KI Forum 226, post 1762, Karl, 22.11.2026): on a question about events after the models' training both
answers can be the same guess, and two matching guesses look convincing. The comparing step of Critique is told
today's date and says «Both models may not know this — check a fresh source that shows its date» instead of
presenting the match as a confirmation; ordinary questions get no new line. What a model then writes is checked on
the phone (tests/behavior/en/freshness.md); these tests check that the rule reaches every comparing request, with
today's date, and nowhere else."""
import json
import re
import sys

import pytest

from test_first_run import LANGS, ROOT, build, kind, is_step

sys.path.insert(0, str(ROOT / 'src'))
from build_shortcut import LONG_DATA, RETRY_CUT, compare_head_len  # noqa: E402
from shortcut_actions import Locale  # noqa: E402

PROMPTS = ROOT / 'locales'
# Duo 6.11 (the owner's decision 6 of 23.11): the warning no longer opens the result. A fresh fact from memory is marked
# «(from memory)» where it stands and is the first ☐ with a concrete action; a dated source that confirms it counts.
EN_CONTRACT = ('Today is {TODAY}', 'not a confirmation', 'materially change the answer', 'for the period asked about',
               'a bare link, a citation date', 'merely because a date appears', 'the rule above does not keep them',
               'Not fresh: history', 'Never invent', 'never mention freshness', '"(from memory)"',
               'Do not open with a warning', 'your reply begins with section 1', 'add no warning',
               'never a warning or a remark about the models', 'one concrete action', 'is the first ☐',
               'check BOTH answers against them', 'Duo prints the list itself', 'use only numbers that stand in SOURCES',
               'is called a forecast', 'goes under "Not checked"')
GONE = ('Both models may not know this', 'This answer may be out of date', '\n0. ', '⚠',
        '\u041e\u0431\u0435 \u043c\u043e\u0434\u0435\u043b\u0438 \u043c\u043e\u0433\u0443\u0442')


class _Mark(dict):
    """The first sentence of a language's comparing prompt: it names every comparing request in a built shortcut."""
    def __missing__(self, lang):
        return (PROMPTS / lang / 'prompts' / 'critique-blind.txt').read_text(encoding='utf-8').split('.')[0]


WARNING = _Mark()


def edition(lang):
    return lang if (PROMPTS / lang / 'prompts' / 'critique-blind.txt').exists() else 'en'


def template(lang):
    return (PROMPTS / edition(lang) / 'prompts' / 'critique-blind.txt').read_text(encoding='utf-8')


def placeholders(text):
    return set(re.findall(r'\{[A-Z_0-9]+\}', text))


@pytest.mark.parametrize('lang', LANGS)
def test_compare_prompt_carries_the_freshness_rule(lang):
    text = template(lang)
    assert '{TODAY}' in text
    for gone in GONE:
        assert gone not in text, gone   # no warning line in front of the result
    # the skeleton of the three sections is kept, and nothing stands in front of section 1
    one = text.index('\n1. ')
    assert one < text.index('\n2. ') < text.index('\n3. ') and '220' in text and '■' in text and '☐' in text
    # the rules sit in the head, before the data (the retry rebuilds the whole head, see test_retry_keeps_both_answers)
    assert text.index('{TODAY}') < text.index('{SPLIT}') < text.index('{NUMS}') < text.index('{QUESTION}')
    assert text.index('{QUESTION}') < text.index('{SOURCES}') < text.index('{LINKS}') < text.index('{GPT_ANSWER}')
    assert 'two years' not in text   # no arbitrary window: «since the models were trained» and «materially»
    if edition(lang) == 'en':
        for phrase in EN_CONTRACT:
            assert phrase in text, phrase


def test_every_prompt_override_keeps_the_english_placeholders():
    """A translated override that drops {TODAY} (or any other placeholder) breaks silently on the phone."""
    for lang_dir in sorted(PROMPTS.iterdir()):
        if lang_dir.name == 'en' or not (lang_dir / 'prompts').is_dir():
            continue
        for f in sorted((lang_dir / 'prompts').glob('*.txt')):
            base = PROMPTS / 'en' / 'prompts' / f.name
            assert placeholders(f.read_text(encoding='utf-8')) == placeholders(base.read_text(encoding='utf-8')), \
                f'{lang_dir.name}/prompts/{f.name}'


def texts_with(actions, marker):
    out = []
    for i, a in enumerate(actions):
        if kind(a) != 'gettext':
            continue
        node = a['WFWorkflowActionParameters'].get('WFTextActionText')
        if isinstance(node, dict) and marker in node['Value']['string']:
            out.append(i)
    return out


@pytest.mark.parametrize('lang', LANGS)
def test_every_comparing_request_gets_todays_date(tmp_path, lang):
    actions = build(tmp_path, lang)
    assert '{TODAY}' not in json.dumps(actions, ensure_ascii=False)
    found = texts_with(actions, WARNING[edition(lang)])
    # My mode and the main Critique (each: the request and its cut retry), and the by-hand check after a resumed draft
    # (ChatGPT's answer alone)
    assert len(found) == 5
    index = {a['WFWorkflowActionParameters'].get('UUID'): i for i, a in enumerate(actions)}
    for i in found:
        attached = actions[i]['WFWorkflowActionParameters']['WFTextActionText']['Value']['attachmentsByRange'].values()
        dates = [v for v in attached if v.get('Aggrandizements')]
        assert len(dates) == 1
        (fmt,) = dates[0]['Aggrandizements']
        # ISO 8601 without time: 2026-11-22 in any region and in the Gregorian year on any calendar setting
        assert fmt['WFDateFormatStyle'] == 'ISO 8601' and fmt['WFISO8601IncludeTime'] is False
        assert dates[0]['OutputName'] == 'Date'
        source = index[dates[0]['OutputUUID']]
        assert kind(actions[source]) == 'date' and source < i
        assert actions[source]['WFWorkflowActionParameters']['WFDateActionMode'] == 'Current Date'


@pytest.mark.parametrize('lang', LANGS)
def test_the_two_answering_models_never_see_the_rule(tmp_path, lang):
    """The blind scheme: ChatGPT and Claude answer the plain wrapped question; only the comparing request (step 3)
    holds the Freshness rule, so neither answer is shaped by it."""
    actions = build(tmp_path, lang)
    marked = {actions[i]['WFWorkflowActionParameters']['UUID'] for i in texts_with(actions, WARNING[edition(lang)])}
    asks = [a for a in actions if kind(a) == 'AskIntent']
    assert asks
    for a in asks:
        refs = {v.get('OutputUUID') for v in a['WFWorkflowActionParameters']['prompt']['Value']['attachmentsByRange'].values()}
        assert not refs & marked
    # Claude's blind answer (step 2) gets the wrapped question, not the comparing text; only step 3 and its retry do
    claude = [a for a in actions if kind(a) == 'ClaudeAppIntentsExtension']
    fed = [a for a in claude
           if {v.get('OutputUUID') for v in a['WFWorkflowActionParameters']['message']['Value']['attachmentsByRange']
               .values()} & marked]
    # step 3 and its cut retry, in My mode and in the main Critique; never the blind answer of step 2
    assert len(fed) == 4 and len(claude) > len(fed)
    wrap = Locale(lang).prompt('wrap')
    assert 'Freshness' not in wrap and '⚠' not in wrap and '{TODAY}' not in wrap


@pytest.mark.parametrize('lang', LANGS)
def test_long_text_notice_counts_the_data_only(tmp_path, lang):
    """The «Long text» notice comes when the question, the answers and the numbers pass LONG_DATA characters, as
    before the Freshness rule; the longer instructions do not make an ordinary run «long»."""
    actions = build(tmp_path, lang)
    notes = [i for i, a in enumerate(actions) if is_step(a, 'long_text')]
    assert len(notes) == 2
    prompt = Locale(lang).prompt('critique-blind')
    heads = sorted(compare_head_len(t) for t in (prompt, 'Extra instruction from the user for this check '
                                                         '(apply it): {RULE}\n\n' + prompt))
    limits = sorted(actions[i - 1]['WFWorkflowActionParameters']['WFNumberValue'] for i in notes)
    assert limits == [h + LONG_DATA for h in heads]


@pytest.mark.parametrize('lang', LANGS)
def test_retry_keeps_both_answers(tmp_path, lang):
    """After an empty comparison the retry rebuilds the same request with each part cut on its own: the rule, the
    date, the question and BOTH answers always reach it (before, the whole request was cut and Claude's own answer,
    which comes last, fell off)."""
    actions = build(tmp_path, lang)
    index = {a['WFWorkflowActionParameters'].get('UUID'): i for i, a in enumerate(actions)}
    retries = [i for i, a in enumerate(actions) if is_step(a, 'claude_retry') and kind(actions[i + 1]) == 'match']
    assert len(retries) == 2
    for r in retries:
        cuts = actions[r + 1:r + 5]
        assert [kind(a) for a in cuts] == ['match'] * 4
        limits = [int(re.search(r'\{1,(\d+)\}$', a['WFWorkflowActionParameters']['WFMatchTextPattern']).group(1))
                  for a in cuts]
        assert limits == [RETRY_CUT[k] for k in ('QUESTION', 'GPT_ANSWER', 'CLAUDE_OWN', 'NUMS')]
        text = actions[r + 5]
        assert kind(text) == 'gettext' and WARNING[edition(lang)] in json.dumps(text, ensure_ascii=False)
        attached = list(text['WFWorkflowActionParameters']['WFTextActionText']['Value']['attachmentsByRange'].values())
        cut_ids = {a['WFWorkflowActionParameters']['UUID'] for a in cuts}
        assert {v['OutputUUID'] for v in attached if v.get('OutputName') == 'Matches'} == cut_ids
        assert sum(1 for v in attached if v.get('Aggrandizements')) == 1   # today's date
        ask = actions[r + 6]
        assert kind(ask) == 'ClaudeAppIntentsExtension'
        assert text['WFWorkflowActionParameters']['UUID'] in json.dumps(ask)
        # the request Claude did not answer comes from the same template, with the whole data
        full = next(v['OutputUUID'] for v in attached if v.get('Aggrandizements'))
        assert kind(actions[index[full]]) == 'date'


# a reply in the shape the rule asks for: no warning in front, the fact marked, the fresh fact as the first ☐
SAMPLE_REPLY = ('**1. Matched independently**\n- Christine Lagarde chairs the ECB (from memory).\n'
                '**2. Did not match**\nNo differences.\n'
                '**3. What to check yourself**\n☐ The current ECB President on ecb.europa.eu, page dated 2026.\n'
                '☐ Her term end date in the same place.\n\n'
                '■ **Final answer**\nChristine Lagarde chairs the ECB (from memory).\n'
                'Checked against: none / Not checked: the current ECB President\n')


def test_output_keeps_the_warning_and_sends_the_check_to_reminders(tmp_path):
    """The ⚠ line and the ☐ items survive strip_markdown as the phone runs it, the ⚠ line stays the first line (the
    title of the result screen and of the note), and the ⚠ fact's ☐ reaches Reminders by the same pattern."""
    actions = build(tmp_path, 'en')
    finds = (r'(?<![\*\w])\*\*(?=\S)(.+?)(?<=\S)\*\*(?![\*\w])',
             r'(?<![\*\w])\*(?=[^\s*])([^*\n]+?)(?<=[^\s*])\*(?![\*\w])', r'(?m)^[ \t]*#{1,6}[ \t]+')
    reps = []
    for f in finds:
        p = next(a['WFWorkflowActionParameters'] for a in actions if kind(a) == 'replace'
                 and a['WFWorkflowActionParameters'].get('WFReplaceTextFind') == f)
        reps.append((p['WFReplaceTextFind'], p.get('WFReplaceTextReplace', '').replace('$1', r'\1')))
    cleaned = SAMPLE_REPLY
    for find, repl in reps:
        cleaned = re.sub(find, repl, cleaned)
    assert '**' not in cleaned
    assert cleaned.split('\n')[0] == '1. Matched independently'   # the first line is a section, never a warning
    pattern = next(a['WFWorkflowActionParameters']['WFMatchTextPattern'] for a in actions
                   if kind(a) == 'match' and '☐' in a['WFWorkflowActionParameters'].get('WFMatchTextPattern', ''))
    items = re.findall(pattern, cleaned)
    assert items[0] == '☐ The current ECB President on ecb.europa.eu, page dated 2026.' and len(items) == 2


@pytest.mark.parametrize('lang', LANGS)
def test_freshness_adds_no_permission_window_and_no_message(tmp_path, lang):
    """Critique writes no file but its draft and copies nothing. Duo 6.11: its AI calls on the ordinary path are
    ChatGPT (+ retry), Claude's own answer (+ retry) and the comparison (+ cut retry); the search's query call and
    the two link checks run only for a fresh question / an answer with links."""
    actions = build(tmp_path, lang)
    starts = [i for i, a in enumerate(actions) if is_step(a, 'critique_start')]
    assert len(starts) == 2
    for start, end in ((starts[0], starts[1]), (starts[1], len(actions))):
        block = actions[start:end]
        step3 = next(i for i, a in enumerate(block) if is_step(a, 'critique_step3'))
        compare = [i for i, a in enumerate(block) if i > step3 and kind(a) == 'ClaudeAppIntentsExtension'][:2]
        kinds = [kind(a) for a in block[:compare[1] + 1]]   # up to the cut retry of step 3
        for k in ('append', 'setclipboard'):
            assert k not in kinds
        assert kinds.count('AskIntent') == 2 and kinds.count('ClaudeAppIntentsExtension') == 4 + 1 + 2

