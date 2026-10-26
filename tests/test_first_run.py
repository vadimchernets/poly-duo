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


def assert_blank_guard(actions, ui, prompt):
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
    assert notification(guard[1]) == ui['notify']['empty_question']
    assert guard[3]['WFWorkflowActionParameters']['WFControlFlowMode'] == 2
    return ask + 5


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

    # an empty question stops the run before the mode menu, so it spends nothing
    assert assert_blank_guard(actions, ui, ui['ask']['question']) == kinds.index('choosefrommenu')

    # «done» and «empty» are the two branches of one check, never shown together
    done = next(i for i, a in enumerate(actions) if notification(a) == ui['notify']['tail_done'])
    empty = next(i for i, a in enumerate(actions) if notification(a) == ui['notify']['tail_empty'])
    assert kind(actions[done - 1]) == 'conditional' and kind(actions[done + 1]) == 'conditional'
    assert actions[done + 1]['WFWorkflowActionParameters']['WFControlFlowMode'] == 1
    assert empty == done + 2


@pytest.mark.parametrize('lang', TRIO_LANGS)
def test_trio_stops_on_empty_question(tmp_path, lang):
    ui = json.loads((ROOT / 'locales' / lang / 'ui.json').read_text(encoding='utf-8'))
    trio = json.loads((ROOT / 'locales' / lang / 'trio.json').read_text(encoding='utf-8'))
    prompt = trio['ask.question']
    actions = build(tmp_path, lang, 'build_trio.py', 'Trio.shortcut')
    assert_blank_guard(actions, ui, prompt)
    nokey = tmp_path / lang / 'nokey' / 'Trio.shortcut'
    if nokey.exists():  # Trio without a key is built only where trio.json has its words
        assert_blank_guard(plistlib.loads(nokey.read_bytes())['WFWorkflowActions'], ui, prompt)
