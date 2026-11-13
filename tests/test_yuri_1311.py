"""Yuri's iPhone report of 13.11 (iPhone XR, iOS 18.7.11, Ukrainian): a silent end with no answer (No.53), the false
«ChatGPT's limit» after «Claude alone» (No.61), «Back» in «More…» (No.67), and the diagnostic build for No.52/53."""
import os
import plistlib
import subprocess
import sys

import pytest

from test_first_run import LANGS, ROOT, build, kind, guard_var
from test_duo64 import groups_open, params, ui_of


@pytest.mark.parametrize('lang', LANGS)
def test_no_answer_says_where_the_answers_are(tmp_path, lang):
    ui = ui_of(lang)
    actions = build(tmp_path, lang)
    i = next(i for i, a in enumerate(actions) if params(a).get('WFAlertActionTitle') == ui['alert']['no_answer_title'])
    assert params(actions[i])['WFAlertActionMessage'] == ui['alert']['no_answer_body']
    # only when RESULT has no text, and nothing is copied there
    cond = groups_open(actions, i, ('conditional',))[-1]
    assert guard_var(actions, cond) == ui['variables']['result'] and params(cond)['WFCondition'] == 101
    end = next(j for j in range(i, len(actions)) if params(actions[j]).get('GroupingIdentifier') == params(cond)['GroupingIdentifier'])
    assert not any(kind(a) in ('setclipboard', 'save') for a in actions[i:end])


@pytest.mark.parametrize('lang', LANGS)
def test_gpt_down_only_when_chatgpt_was_asked(tmp_path, lang):
    ui = ui_of(lang)
    actions = build(tmp_path, lang)
    notes = [i for i, a in enumerate(actions) if params(a).get('WFNotificationActionBody') == ui['notify']['gpt_down']]
    main = notes[-1]   # the main Critique (draft): inside «PolySkipChatGPT has no text»
    assert 'PolySkipChatGPT' in [guard_var(actions, c) for c in groups_open(actions, main, ('conditional',))]


@pytest.mark.parametrize('lang', LANGS)
def test_back_shows_the_modes_without_the_question_field(tmp_path, lang):
    ui = ui_of(lang)
    actions = build(tmp_path, lang)
    menu = next(a for a in actions if params(a).get('WFMenuPrompt') == ui['menu']['extra_title'])
    assert params(menu)['WFMenuItems'][-1] == ui['menu']['back']
    case = next(i for i, a in enumerate(actions) if params(a).get('WFMenuItemTitle') == ui['menu']['back'])
    assert [kind(a) for a in actions[case + 1:case + 4]] == ['gettext', 'runworkflow', 'exit']
    assert params(actions[case + 1])['WFTextActionText']['Value']['string'].startswith('⟦duo-mode⟧\n')
    # the mark sets PolyKeepQuestion, which sets PolySkipQuestion after every other rule about the field
    ask = next(i for i, a in enumerate(actions) if kind(a) == 'ask' and params(a)['WFAskActionPrompt'] == ui['ask']['question'])
    keeps = [i for i, a in enumerate(actions) if kind(a) == 'conditional' and params(a)['WFControlFlowMode'] == 0
             and guard_var(actions, a) == 'PolyKeepQuestion']
    assert len(keeps) == 1 and keeps[0] < ask
    sets = [i for i, a in enumerate(actions[:ask]) if kind(a) == 'setvariable'
            and params(a)['WFVariableName'] == 'PolySkipQuestion']
    assert max(sets) > keeps[0]
    assert all(len(ui_of(l)['menu']['back']) < 20 for l in LANGS)


def test_diagnostic_build_names_every_ai_call(tmp_path):
    env = dict(os.environ, C1_DIST=str(tmp_path), C1_DIAG='1')
    subprocess.run([sys.executable, str(ROOT / 'src' / 'build_shortcut.py'), 'uk'], check=True, cwd=ROOT, env=env,
                   capture_output=True)
    actions = plistlib.loads((tmp_path / 'uk' / 'Poly-diag.shortcut').read_bytes())['WFWorkflowActions']
    calls = [i for i, a in enumerate(actions) if kind(a) in ('AskIntent', 'ClaudeAppIntentsExtension')]
    assert calls
    for n, i in enumerate(calls, 1):
        assert params(actions[i - 1]).get('WFNotificationActionBody', '').startswith(f'🔧 → #{n} ')
        after = next(a for a in actions[i:] if kind(a) == 'notification')
        assert params(after)['WFNotificationActionBody']['Value']['string'].startswith(f'🔧 ← #{n} ')
    # the release build has none of it
    plain = build(tmp_path / 'plain', 'uk')
    assert not any('🔧' in str(params(a).get('WFNotificationActionBody', '')) for a in plain)
