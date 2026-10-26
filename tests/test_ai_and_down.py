"""Duo with Apple Intelligence (ai build) and the three ways out when Claude does not answer."""
import json
import plistlib

import pytest

from test_first_run import LANGS, ROOT, build, kind


def params(a):
    return a['WFWorkflowActionParameters']


def has_ai_words(lang):
    f = ROOT / 'locales' / lang / 'trio.json'
    return f.exists() and 'nokey.comment' in json.loads(f.read_text(encoding='utf-8'))


@pytest.mark.parametrize('lang', LANGS)
def test_ai_build_and_claude_down(tmp_path, lang):
    ui = json.loads((ROOT / 'locales' / lang / 'ui.json').read_text(encoding='utf-8'))
    actions = build(tmp_path, lang)
    ai_file = tmp_path / lang / 'ai' / 'Poly.shortcut'
    assert ai_file.exists() == has_ai_words(lang)

    # the usual path: the three-way menu sits only inside the «no answer» branch, after its notification
    note = next(i for i, a in enumerate(actions)
                if params(a).get('WFNotificationActionBody') == ui['notify']['tail_empty'])
    menu = next(i for i, a in enumerate(actions) if kind(a) == 'choosefrommenu'
                and params(a).get('WFMenuItems') == ui['menu']['claude_down_items'])
    assert menu > note and len(ui['menu']['claude_down_items']) == 3
    assert 'Apple Intelligence' in ui['menu']['claude_down_items'][1]
    assert any(a['WFWorkflowActionIdentifier'] == 'is.workflow.actions.askllm' for a in actions[menu:])
    # nothing of the plain Duo asks Apple Intelligence on the main path
    assert not any(a['WFWorkflowActionIdentifier'] == 'is.workflow.actions.askllm' for a in actions[:note])

    if ai_file.exists():
        ai = plistlib.loads(ai_file.read_bytes())['WFWorkflowActions']
        llm = [a for a in ai[:ai.index(next(a for a in ai if params(a).get('WFNotificationActionBody')
                                           == ui['notify']['tail_empty']))]
               if a['WFWorkflowActionIdentifier'] == 'is.workflow.actions.askllm']
        assert len(llm) == 2  # Auto and Clarify's questions
        # …and ChatGPT is no longer asked for those two: one call fewer in the ai build
        gpt = lambda acts: sum(a['WFWorkflowActionIdentifier'] == 'com.openai.chat.AskIntent' for a in acts)
        assert gpt(ai) == gpt(actions) - 2 or gpt(ai) < gpt(actions)


@pytest.mark.parametrize('lang', LANGS)
def test_debate_resume_and_retries(tmp_path, lang):
    ui = json.loads((ROOT / 'locales' / lang / 'ui.json').read_text(encoding='utf-8'))
    actions = build(tmp_path, lang)
    note = next(i for i, a in enumerate(actions)
                if params(a).get('WFNotificationActionBody') == ui['notify']['resume_debate'])
    saves = [params(a).get('WFFileDestinationPath') for a in actions if kind(a) == 'save']
    base = f'Duo-draft-{lang}-std-argue'
    assert {f'{base}-question.txt', f'{base}-log.txt', f'{base}-rounds.txt'} <= set(saves)
    # the question is written LAST (it stamps a complete draft): after the log and the round counter
    first = [i for i, a in enumerate(actions) if params(a).get('WFFileDestinationPath') == f'{base}-question.txt'][1]  # [0] is the empty one written first
    assert [params(actions[i]).get('WFFileDestinationPath') for i in range(first - 2, first + 1)] == \
        [f'{base}-log.txt', f'{base}-rounds.txt', f'{base}-question.txt']
    # each of the three rounds runs only while «rounds done» is between 0 and n-1, and records itself when over
    rounds = [a for a in actions if kind(a) == 'conditional' and params(a).get('WFCondition') == 1003
              and params(a).get('WFNumberValue') == 0]
    assert sorted(params(a)['WFAnotherNumber'] for a in rounds) == [0, 1, 2]
    assert note > 0
    # every ChatGPT call that opens a mode is followed by one retry after a 3-second wait
    delays = [i for i, a in enumerate(actions) if kind(a) == 'delay']
    assert len(delays) >= 10
    for i in delays:
        assert params(actions[i - 1])['WFCondition'] == 101
        assert actions[i + 1]['WFWorkflowActionIdentifier'] == 'com.openai.chat.AskIntent'
    # Critique ⇄ and Delta (the ChatGPT call that follows their notifications) are retried too
    for key in ('reverse_start', 'delta_step1'):
        start = next(i for i, a in enumerate(actions) if params(a).get('WFNotificationActionBody') == ui['notify'][key])
        gpt = next(i for i in range(start, len(actions)) if kind(actions[i]) == 'AskIntent'
                   and actions[i]['WFWorkflowActionIdentifier'] == 'com.openai.chat.AskIntent')
        assert kind(actions[gpt + 1]) == 'setvariable' and params(actions[gpt + 2])['WFCondition'] == 101
        assert kind(actions[gpt + 3]) == 'delay'
