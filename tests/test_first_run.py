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


def guard_var(actions, cond):
    """The variable (or output) name an If tests. D-100: a text is tested through Match Text `\\S` (an empty Text
    «has any value» in Shortcuts), so an If on that Match's «Matches» is followed back to the variable it reads."""
    node = cond['WFWorkflowActionParameters']['WFInput']['Variable']['Value']
    if node.get('OutputName') == 'Matches':
        by_uid = {a['WFWorkflowActionParameters'].get('UUID'): a for a in actions}
        match = by_uid[node['OutputUUID']]['WFWorkflowActionParameters']
        if match['WFMatchTextPattern'] == r'\S':
            (src,) = match['text']['Value']['attachmentsByRange'].values()
            read = by_uid[src['OutputUUID']]
            if kind(read) == 'getvariable':
                return read['WFWorkflowActionParameters']['WFVariable']['Value']['VariableName']
            return src['OutputName']
    return node.get('VariableName') or node.get('OutputName')


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
    end = assert_duo_blank_guard(actions, ui)
    # Duo 6.4: the question goes to a variable (a resumed draft fills the same one), then the mode menu
    # D-29: then the «ask without editing» Else branch (QUICK) and the «Critique right away» branch (MODE), then the menu
    assert kind(actions[end]) == 'setvariable' and kind(actions[end + 1]) == 'conditional' and main > end
    assert actions[end]['WFWorkflowActionParameters']['WFVariableName'] == 'PolyQuestion'

    # «empty» comes only when RESULT has no text; «done» only inside «RESULT has text», right after its one clipboard
    # write and its save (Duo 6.4: the «check with…» menu comes between them, never together with «done»)
    done = next(i for i, a in enumerate(actions) if notification(a) == ui['notify']['tail_done'])
    empty = next(i for i, a in enumerate(actions) if notification(a) == ui['notify']['tail_empty'])
    assert empty < done
    for i, cond in ((empty, 101), (done, 100)):
        opener = max(j for j in range(i) if kind(actions[j]) == 'conditional'
                     and actions[j]['WFWorkflowActionParameters'].get('WFControlFlowMode') == 0)
        assert actions[opener]['WFWorkflowActionParameters']['WFCondition'] == cond
        assert guard_var(actions, actions[opener]) == ui['variables']['result']
    between = [kind(a) for a in actions[done - 5:done]]
    assert between[0] == 'setclipboard' and 'save' in between
    assert kind(actions[done + 1]) == 'conditional'
    assert actions[done + 1]['WFWorkflowActionParameters']['WFControlFlowMode'] == 2


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
