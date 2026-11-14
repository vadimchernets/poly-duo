"""Yuri's iPhone report of 13.11 (iPhone XR, iOS 18.7.11, Ukrainian): a silent end with no answer (No.53), the false
«ChatGPT's limit» after «Claude alone» (No.61), «Back» in «More…» (No.67), and the diagnostic build for No.52/53."""
import os
import plistlib
import subprocess
import sys

import pytest

from test_first_run import LANGS, ROOT, build, kind, guard_var
from test_duo64 import groups_open, params, sets, ui_of


@pytest.mark.parametrize('lang', LANGS)
def test_no_answer_says_where_the_answers_are(tmp_path, lang):
    ui = ui_of(lang)
    actions = build(tmp_path, lang)
    both = [i for i, a in enumerate(actions) if params(a).get('WFAlertActionTitle') == ui['alert']['no_answer_title']]
    assert [params(actions[i])['WFAlertActionMessage'] for i in both] == [ui['alert']['no_answer_claude_body'],
                                                                           ui['alert']['no_answer_body']]
    # the notification gives the same advice as the window, in both wordings
    assert ui['notify']['tail_empty'] == ui['alert']['no_answer_body']
    assert ui['notify']['tail_empty_claude'] == ui['alert']['no_answer_claude_body']
    i = both[-1]
    # only when RESULT has no text, and nothing is copied there
    cond = [c for c in groups_open(actions, i, ('conditional',)) if guard_var(actions, c) != 'PolyOnlyClaude'][-1]
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


@pytest.mark.parametrize('lang', LANGS)
def test_claude_only_has_its_own_neutral_line(tmp_path, lang):
    """After the review of 13.11: «Ask Claude alone» is not «ChatGPT did not pass» (No.61); the Advisor and the
    «alone» resume set PolyOnlyClaude, and the Side by side with an empty ChatGPT says so instead of an empty block."""
    ui = ui_of(lang)
    actions = build(tmp_path, lang)
    assert '{C}' in ui['output']['claude_only'] and 'ChatGPT' not in ui['output']['claude_only'].split('{C}')[0]
    only = [i for i, a in enumerate(actions) if kind(a) == 'setvariable' and params(a).get('WFVariableName') == 'PolyOnlyClaude']
    assert len(only) == 2   # the Advisor, and «Ask Claude alone» in the resume menu
    texts = [t for _, t in sets(actions, ui['variables']['result']) if t]
    assert any(t.startswith(ui['output']['claude_only'].split('{C}')[0]) for t in texts)
