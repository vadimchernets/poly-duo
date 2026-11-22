"""Freshness (KI Forum 226, post 1762, Karl, 22.11.2026): on a question about events after the models' training both
answers can be the same guess, and two matching guesses look convincing. The comparing step of Critique is told
today's date and says «Both models may not know this — check a fresh source that shows its date» instead of
presenting the match as a confirmation; ordinary questions get no new line. What a model then writes is checked on
the phone (tests/behavior/en/freshness.md); these tests check that the rule reaches every comparing request, with
today's date, and nowhere else."""
import json
import re

import pytest

from test_first_run import LANGS, ROOT, build, kind

PROMPTS = ROOT / 'locales'
LONG_TEXT = int(re.search(r'^LONG_TEXT = (\d+)', (ROOT / 'src' / 'build_shortcut.py').read_text(encoding='utf-8'),
                          re.M).group(1))
# the visible warning line of each prompt edition (ru in escapes: Cyrillic lives only in a language place)
WARNING = {'en': 'Both models may not know this',
           'ru': '\u041e\u0431\u0435 \u043c\u043e\u0434\u0435\u043b\u0438 '
                 '\u043c\u043e\u0433\u0443\u0442 \u044d\u0442\u043e\u0433\u043e \u043d\u0435 \u0437\u043d\u0430\u0442\u044c'}
EN_CONTRACT = ('Today is {TODAY}', 'not a confirmation', 'not enough', 'never fresh', 'Never invent',
               'never mention freshness', '(from memory — not confirmed)', 'This answer may be out of date',
               'This has not happened yet', 'Outside the 220 words', 'A ⚠ fact is the first ☐', 'a ⚠ fact is "Not checked"')


def edition(lang):
    return lang if (PROMPTS / lang / 'prompts' / 'critique-blind.txt').exists() else 'en'


def template(lang):
    return (PROMPTS / edition(lang) / 'prompts' / 'critique-blind.txt').read_text(encoding='utf-8')


def placeholders(text):
    return set(re.findall(r'\{[A-Z_0-9]+\}', text))


@pytest.mark.parametrize('lang', LANGS)
def test_compare_prompt_carries_the_freshness_rule(lang):
    text = template(lang)
    assert WARNING[edition(lang)] in text and '{TODAY}' in text
    # line 0 (the warning) comes right before section 1, and the skeleton of the three sections is kept
    zero, one = text.index('\n0. '), text.index('\n1. ')
    assert zero < one < text.index('\n2. ') < text.index('\n3. ') and '220' in text and '■' in text
    # the rule sits in the head, before the data: a retry cut to LONG_TEXT characters still carries it, and leaves
    # at least 1000 characters for the question and the answers
    assert text.index('{TODAY}') < text.index('{NUMS}') <= LONG_TEXT - 1000
    assert text.count('⚠') >= 6
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
    # My mode, the main Critique, and the by-hand check after a resumed draft (ChatGPT's answer alone)
    assert len(found) == 3
    index = {a['WFWorkflowActionParameters'].get('UUID'): i for i, a in enumerate(actions)}
    for i in found:
        attached = actions[i]['WFWorkflowActionParameters']['WFTextActionText']['Value']['attachmentsByRange'].values()
        dates = [v for v in attached if v.get('Aggrandizements')]
        assert len(dates) == 1
        (fmt,) = dates[0]['Aggrandizements']
        assert fmt['WFDateFormat'] == 'yyyy-MM-dd' and dates[0]['OutputName'] == 'Date'
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
    wrap = (PROMPTS / 'en' / 'prompts' / 'wrap.txt').read_text(encoding='utf-8')
    assert 'Freshness' not in wrap and '⚠' not in wrap
