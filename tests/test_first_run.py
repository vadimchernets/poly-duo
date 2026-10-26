"""The first minute of Duo for a busy person: warned before the permission requests, never charged for an empty
question, and told «done» only when there is an answer."""
import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LANGS = sorted(d.name for d in (ROOT / 'locales').iterdir() if (d / 'ui.json').exists())


TRIO_LANGS = sorted(d.name for d in (ROOT / 'locales').iterdir() if (d / 'trio.json').exists())


def build(tmp_path, lang, builder='build_shortcut.py', name='Poly.shortcut'):
    env = dict(os.environ, C1_DIST=str(tmp_path))
    subprocess.run([sys.executable, str(ROOT / 'src' / builder), lang], check=True, cwd=ROOT,
                   env=env, capture_output=True)
    return plistlib.loads((tmp_path / lang / name).read_bytes())['WFWorkflowActions']


def assert_blank_guard(actions, ui, prompt, message=None):
    """Right after the question: If <the question> has no value → say so → stop → End If."""
    ask = next(i for i, a in enumerate(actions)
               if kind(a) == 'ask' and a['WFWorkflowActionParameters']['WFAskActionPrompt'] == prompt)
    guard = actions[ask + 1:ask + 5]
    assert [kind(a) for a in guard] == ['conditional', 'notification', 'exit', 'conditional']
    condition = guard[0]['WFWorkflowActionParameters']
    assert condition['WFCondition'] == 101
    source = condition['WFInput']['Variable']['Value']
    assert (source['OutputUUID'], source['OutputName']) == \
        (actions[ask]['WFWorkflowActionParameters']['UUID'], 'Provided Input')
    assert notification(guard[1]) == (message or ui['notify']['empty_question'])
    assert guard[3]['WFWorkflowActionParameters']['WFControlFlowMode'] == 2
    return ask + 5


def assert_duo_blank_guard(actions, ui):
    """Duo 6.1: right after the question, If <the question> has no value → the Recipes menu (a ready task runs Duo
    again with its wording; the menu's own Cancel ends the run) → stop → End If. No AI is asked in this branch."""
    prompt = ui['ask']['question']
    ask = next(i for i, a in enumerate(actions)
               if kind(a) == 'ask' and a['WFWorkflowActionParameters']['WFAskActionPrompt'] == prompt)
    condition = actions[ask + 1]['WFWorkflowActionParameters']
    assert kind(actions[ask + 1]) == 'conditional' and condition['WFCondition'] == 101
    source = condition['WFInput']['Variable']['Value']
    assert (source['OutputUUID'], source['OutputName']) == \
        (actions[ask]['WFWorkflowActionParameters']['UUID'], 'Provided Input')
    menu = actions[ask + 2]['WFWorkflowActionParameters']
    assert menu['WFMenuPrompt'] == ui['menu']['empty_title']
    assert menu['WFMenuItems'] == ui['menu']['recipes_items']
    n = len(ui['menu']['recipes_items'])
    body = [kind(a) for a in actions[ask + 3:ask + 3 + 4 * n]]
    assert body == ['choosefrommenu', 'gettext', 'runworkflow', 'exit'] * n
    end = ask + 3 + 4 * n
    assert [kind(a) for a in actions[end:end + 3]] == ['choosefrommenu', 'exit', 'conditional']
    assert actions[end + 2]['WFWorkflowActionParameters']['GroupingIdentifier'] == condition['GroupingIdentifier']
    branch = actions[ask + 1:end + 3]
    assert not any(kind(a) in ('AskIntent', 'ClaudeAppIntentsExtension', 'askllm') for a in branch)
    return end + 3


def kind(action):
    return action['WFWorkflowActionIdentifier'].rsplit('.', 1)[-1]


def notification(action):
    body = action['WFWorkflowActionParameters'].get('WFNotificationActionBody')
    return body if isinstance(body, str) else None


@pytest.mark.parametrize('lang', LANGS)
def test_first_minute(tmp_path, lang):
    ui = json.loads((ROOT / 'locales' / lang / 'ui.json').read_text(encoding='utf-8'))
    actions = build(tmp_path, lang)
    kinds = [kind(a) for a in actions]

    # the only alert before the question is the permission warning, and no AI is asked before the question
    ask = kinds.index('ask')
    alerts = [a['WFWorkflowActionParameters'] for a in actions[:ask] if kind(a) == 'alert']
    assert [a['WFAlertActionTitle'] for a in alerts] == [ui['alert']['first_run_title']]
    assert not any(k in ('AskIntent', 'ClaudeAppIntentsExtension') for k in kinds[:ask])

    # an empty question never reaches the mode menu, so it spends nothing; it offers the Recipes instead (Duo 6.1)
    main = next(i for i, a in enumerate(actions) if kind(a) == 'choosefrommenu'
                and a['WFWorkflowActionParameters'].get('WFMenuPrompt') == ui['menu']['main_title'])
    assert assert_duo_blank_guard(actions, ui) == main

    # «done» and «empty» are the two branches of one check, never shown together
    done = next(i for i, a in enumerate(actions) if notification(a) == ui['notify']['tail_done'])
    empty = next(i for i, a in enumerate(actions) if notification(a) == ui['notify']['tail_empty'])
    assert kind(actions[done - 2]) == 'conditional' and kind(actions[done - 1]) == 'setclipboard'
    assert kind(actions[done + 1]) == 'conditional'
    assert actions[done + 1]['WFWorkflowActionParameters']['WFControlFlowMode'] == 1
    assert empty == done + 2


def key_ask_of(actions, trio):
    return next(a for a in actions
                if kind(a) == 'ask' and a['WFWorkflowActionParameters']['WFAskActionPrompt'] == trio['ask.key'])


@pytest.mark.parametrize('lang', TRIO_LANGS)
def test_trio_stops_on_empty_question(tmp_path, lang):
    ui = json.loads((ROOT / 'locales' / lang / 'ui.json').read_text(encoding='utf-8'))
    trio = json.loads((ROOT / 'locales' / lang / 'trio.json').read_text(encoding='utf-8'))
    prompt = trio['ask.question']
    actions = build(tmp_path, lang, 'build_trio.py', 'Trio.shortcut')
    assert_blank_guard(actions, ui, prompt, trio['notify.empty_question'])
    assert 'Poly' not in trio['notify.empty_question'] or lang != 'en'
    # an empty key field stops the run before poly-key.txt is written
    ki = actions.index(key_ask_of(actions, trio))
    # blank = nothing but spaces / line breaks: Match Text `\S` first, then the guard on «no match»
    match = actions[ki + 1]
    assert match['WFWorkflowActionIdentifier'].endswith('text.match')
    assert match['WFWorkflowActionParameters']['WFMatchTextPattern'] == r'\S'
    kg = actions[ki + 2:ki + 6]
    assert [kind(a) for a in kg] == ['conditional', 'notification', 'exit', 'conditional']
    assert kg[0]['WFWorkflowActionParameters']['WFCondition'] == 101
    assert notification(kg[1]) == trio['notify.empty_key']
    assert kind(actions[ki + 6]) == 'save'
    # the keyed Trio warns about the permission windows first thing in its key prompt, adding no screen
    key_ask = next(a for a in actions
                   if kind(a) == 'ask' and a['WFWorkflowActionParameters']['WFAskActionPrompt'] == trio['ask.key'])
    assert '4–6' in '\n\n'.join(trio['ask.key'].split('\n\n')[:2])  # the warning is in the first two paragraphs
    assert actions.index(key_ask) < actions.index(next(a for a in actions if kind(a) == 'ask'
                                                      and a['WFWorkflowActionParameters']['WFAskActionPrompt'] == prompt))
    nokey = tmp_path / lang / 'nokey' / 'Trio.shortcut'
    if nokey.exists():  # Trio without a key is built only where trio.json has its words
        nk = plistlib.loads(nokey.read_bytes())['WFWorkflowActions']
        ask = assert_blank_guard(nk, ui, prompt, trio['notify.empty_question']) - 5
        # asks nothing before the question, so it warns once with Duo's window
        alerts = [a['WFWorkflowActionParameters']['WFAlertActionTitle'] for a in nk[:ask] if kind(a) == 'alert']
        assert alerts == [ui['alert']['first_run_title']]
