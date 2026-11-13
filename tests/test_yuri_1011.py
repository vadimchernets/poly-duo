"""Yuri's iPhone report of 10.11 (iPhone XR, iOS 18.7.11, Ukrainian): Side by side stopped after ChatGPT (No.52), a long
question was cut off at ChatGPT (No.53), Advisor on a question (No.54), raw Markdown (No.56), texts (No.54-60)."""
import json
import re

import pytest

from test_first_run import LANGS, ROOT, build, kind
from test_duo64 import groups_open, params, ui_of

CLAUDE = 'ClaudeAppIntentsExtension'


def by_uid(actions):
    return {params(a)['UUID']: a for a in actions if params(a).get('UUID')}


def text_refs(node, found=None):
    """Every ActionOutput attachment inside a text token (not a bare WFInput)."""
    found = [] if found is None else found
    if isinstance(node, dict):
        if node.get('WFSerializationType') == 'WFTextTokenString':
            found += [v['OutputUUID'] for v in node['Value'].get('attachmentsByRange', {}).values() if 'OutputUUID' in v]
        for v in node.values():
            text_refs(v, found)
    elif isinstance(node, list):
        for v in node:
            text_refs(v, found)
    return found


@pytest.mark.parametrize('lang', LANGS)
def test_claude_output_is_never_put_straight_into_a_text(tmp_path, lang):
    """No.52: an «Ask Claude» output is only ever stored by Set Variable; texts read it through Get Variable."""
    actions = build(tmp_path, lang)
    claude = {params(a)['UUID'] for a in actions if kind(a) == CLAUDE}
    assert claude
    for a in actions:
        assert not (set(text_refs(params(a))) & claude), a
    for a in actions:
        if kind(a) == 'setvariable':
            continue
        ref = params(a).get('WFInput', {})
        if isinstance(ref, dict) and ref.get('WFSerializationType') == 'WFTextTokenAttachment':
            assert ref['Value'].get('OutputUUID') not in claude, a


@pytest.mark.parametrize('lang', LANGS)
def test_side_by_side_names_its_step_and_keeps_chatgpt(tmp_path, lang):
    ui = ui_of(lang)
    actions = build(tmp_path, lang)
    n = ui['notify']
    start = next(i for i, a in enumerate(actions) if params(a).get('WFNotificationActionBody') == n['survey_start'])
    end = next(i for i in range(start, len(actions)) if kind(actions[i]) == 'choosefrommenu'
               and params(actions[i]).get('WFMenuItemTitle') == ui['menu']['main_items'][4])
    block = actions[start:end]
    gpt = next(i for i, a in enumerate(block) if kind(a) == 'AskIntent')
    first_claude = next(i for i, a in enumerate(block) if kind(a) == CLAUDE)
    # before Claude: ChatGPT's answer to the clipboard, and a notification that names step 2 of 2
    assert any(kind(a) == 'setclipboard' for a in block[gpt:first_claude])
    bodies = [params(a).get('WFNotificationActionBody') for a in block[gpt:first_claude] if kind(a) == 'notification']
    assert bodies and all(n['survey_step2'] in b for b in bodies)
    # Claude asked at most twice (one retry of an empty answer), both into PolySideClaude
    claudes = [i for i, a in enumerate(block) if kind(a) == CLAUDE]
    assert len(claudes) == 2
    for i in claudes:
        assert kind(block[i + 1]) == 'setvariable' and params(block[i + 1])['WFVariableName'] == 'PolySideClaude'
    # Claude gave nothing → ChatGPT's answer with the line about Claude
    head = ui['output']['claude_down'].split('{A}')[0]
    assert any(kind(a) == 'gettext' and params(a)['WFTextActionText']['Value']['string'].startswith(head) for a in block)


@pytest.mark.parametrize('lang', LANGS)
def test_long_question_asks_for_a_shorter_answer(tmp_path, lang):
    """No.53: from 1200 characters on, the request opens with the «answer shorter» line, and one notification says so;
    in Critique, My mode and Side by side, whose ChatGPT and Claude get the same wrapped question."""
    ui = ui_of(lang)
    actions = build(tmp_path, lang)
    u = by_uid(actions)
    notes = [i for i, a in enumerate(actions) if params(a).get('WFNotificationActionBody') == ui['notify']['long_question']]
    assert len(notes) == 3
    for i in notes:
        cond = groups_open(actions, i)[-1]
        p = params(cond)
        assert p['WFCondition'] == 2 and p['WFNumberValue'] == 1199
        assert kind(u[p['WFInput']['Variable']['Value']['OutputUUID']]) == 'count'
    wrap_dir = ROOT / 'locales' / lang / 'prompts'
    wrap_text = ((wrap_dir / 'wrap.txt') if (wrap_dir / 'wrap.txt').exists()
                 else ROOT / 'locales' / 'en' / 'prompts' / 'wrap.txt').read_text(encoding='utf-8')
    first_words = wrap_text.split('.')[0]
    wraps = [a for a in actions if kind(a) == 'gettext'
             and first_words in params(a)['WFTextActionText']['Value']['string']]
    briefed = [a for a in wraps if any(params(u[r]).get('WFVariable', {}).get('Value', {}).get('VariableName') == 'PolyBrief'
                                       for r in text_refs(params(a)) if r in u)]
    assert len(briefed) == 3
    for a in briefed:
        assert params(a)['WFTextActionText']['Value']['string'].startswith('￼' + first_words)


@pytest.mark.parametrize('lang', LANGS)
def test_markdown_is_taken_off_before_the_result_is_shown(tmp_path, lang):
    """No.56: «**bold**», «*italic*» and «# heading» marks are removed from RESULT before the copy and the screen."""
    ui = ui_of(lang)
    actions = build(tmp_path, lang)
    reps = [params(a) for a in actions if kind(a) == 'replace' and params(a).get('WFReplaceTextRegularExpression')
            and params(a)['WFReplaceTextFind'] in (r'(?<![\*\w])\*\*(?=\S)(.+?)(?<=\S)\*\*(?![\*\w])',
                                                  r'(?<![\*\w])\*(?=[^\s*])([^*\n]+?)(?<=[^\s*])\*(?![\*\w])',
                                                  r'(?m)^[ \t]*#{1,6}[ \t]+')]
    assert len(reps) == 6   # three in the tail, three after «check the result again»
    pats = [p['WFReplaceTextFind'] for p in reps[:3]]
    sample = '# Head\n**1. Matched independently**\n- *one* item\n* bullet 2*3*4 x**2\n**Bottom line:** yes'
    for pat, rep in zip(pats, [p['WFReplaceTextReplace'] for p in reps[:3]]):
        sample = re.sub(pat, rep.replace('$1', r'\1'), sample)
    assert sample == 'Head\n1. Matched independently\n- one item\n* bullet 2*3*4 x**2\nBottom line: yes'
    # each Quick Look of RESULT comes after its clean-up
    looks = [i for i, a in enumerate(actions) if kind(a) == 'previewdocument'
             and params(a)['WFInput'].get('Value', {}).get('VariableName') == ui['variables']['result']]
    cleans = [i for i, a in enumerate(actions) if kind(a) == 'setvariable'
              and params(a)['WFVariableName'] == ui['variables']['result']
              and params(a)['WFInput']['Value'].get('OutputName') == 'Updated Text']
    assert len(looks) == 2 and len(cleans) == 2 and all(c < l for c, l in zip(cleans, looks))


@pytest.mark.parametrize('lang', LANGS)
def test_advisor_on_a_question_points_to_critique(tmp_path, lang):
    """No.54: Advisor's request names this language's Critique for a question; no placeholder is left."""
    ui = ui_of(lang)
    actions = build(tmp_path, lang)
    name = ui['menu']['main_items'][0].split(' · ')[0].split(' — ')[0]
    adv_dir = ROOT / 'locales' / lang / 'prompts'
    adv_file = adv_dir / 'advisor.txt' if (adv_dir / 'advisor.txt').exists() else ROOT / 'locales' / 'en' / 'prompts' / 'advisor.txt'
    first_line = adv_file.read_text(encoding='utf-8').split('.')[0]
    adv = [params(a)['WFTextActionText']['Value']['string'] for a in actions if kind(a) == 'gettext'
           and first_line in params(a)['WFTextActionText']['Value']['string']]
    assert len(adv) == 1 and f'«{name}»' in adv[0] and '{CRITIQUE}' not in adv[0]


@pytest.mark.parametrize('lang', LANGS)
def test_menu_says_what_each_mode_is_for(tmp_path, lang):
    """No.54, No.59: each main mode has a few words of what it is for; the title says what ✉ counts."""
    ui = ui_of(lang)
    m = ui['menu']
    assert '✉ =' in m['main_title']
    for item in m['main_items'][:6]:
        assert ' — ' in item and item.endswith('✉')
    n = ui['notify']
    assert not re.search(r'40\s?(s|sec|\u0441)', n['advisor_start'])   # \u0441: the Cyrillic «s»
    if lang != 'en':
        assert 'logged out' not in json.dumps(ui, ensure_ascii=False)
