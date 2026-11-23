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
        # 14.11: «→» notification, its line appended to Duo-diag-log.txt, then the AI call
        before = next(a for a in reversed(actions[:i]) if kind(a) == 'notification')
        assert params(before).get('WFNotificationActionBody', '').startswith(f'🔧 → #{n} ')
        assert kind(actions[i - 1]) == 'append'
        assert params(actions[i - 1])['WFFilePath'] == 'Duo-diag-log.txt'
        after = next(a for a in actions[i:] if kind(a) == 'notification')
        assert params(after)['WFNotificationActionBody']['Value']['string'].startswith(f'🔧 ← #{n} ')
        # the log lines carry HH:mm:ss, so the seconds of each step are readable even if «Time Between Dates» is blank
        log_after = next(a for a in actions[i:] if kind(a) == 'append')
        src = next(a for a in reversed(actions[:actions.index(log_after)]) if kind(a) == 'gettext')
        assert "'WFDateFormat': 'HH:mm:ss'" in str(params(src))
    # 14.11: resume_block logs each decision point (file, age, step, branch) in the diag build only
    logs = [str(params(a)) for a in actions if kind(a) == 'gettext' and 'resume:' in str(params(a))]
    for word in ('found', 'age', 'step', 'branch'):
        assert any(word in l for l in logs), word
    # the release build has none of it
    plain = build(tmp_path / 'plain', 'uk')
    assert not any('🔧' in str(params(a).get('WFNotificationActionBody', '')) for a in plain)
    assert not any('🔧' in str(a) for a in plain)


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


# ---- 14.11 live run on iPhone: raw markup in ChatGPT's answer, and the permission window on writing it to a file
AI_KINDS = ('AskIntent', 'ClaudeAppIntentsExtension')


def _refs(node):
    if isinstance(node, dict):
        if node.get('Type') == 'ActionOutput' and 'OutputUUID' in node:
            yield node['OutputUUID']
        for v in node.values():
            yield from _refs(v)
    elif isinstance(node, list):
        for v in node:
            yield from _refs(v)


@pytest.mark.parametrize('lang', LANGS)
def test_chatgpt_output_is_cleaned_and_never_used_raw(tmp_path, lang):
    actions = build(tmp_path, lang)
    asks = [i for i, a in enumerate(actions) if kind(a) == 'AskIntent']
    assert asks
    for i in asks:
        uid = params(actions[i])['UUID']
        users = [j for j, a in enumerate(actions) if uid in set(_refs(params(a))) and j != i]
        # the only user of the raw output is the Set Variable that starts the cleaning block
        assert [kind(actions[j]) for j in users] == ['setvariable'], (i, users)
        block = actions[users[0]:users[0] + 13]
        replaces = [a for a in block if kind(a) == 'text.replace' or kind(a) == 'replace']
        assert len(replaces) == 4 and all(params(a)['WFReplaceTextRegularExpression'] for a in replaces)
    # no file action (Save File / Append to File) takes the output of an AI app directly
    ai_uids = {params(a)['UUID'] for a in actions if kind(a) in AI_KINDS}
    for a in actions:
        if kind(a) in ('save', 'append', 'file.append', 'documentpicker.save'):
            assert not (set(_refs(params(a))) & ai_uids)


def _py(pattern):
    import re
    return re.compile(re.sub(r'\\x\{([0-9A-Fa-f]+)\}', lambda m: '\\u' + m.group(1).rjust(4, '0'), pattern))


def test_chatgpt_markup_regexes():
    sys.path.insert(0, str(ROOT / 'src'))
    import build_shortcut as b
    text = ('The capital is \ue200entity\ue202["city","Ottawa","capital of Canada"]\ue201, on the Ottawa River.\n'
            '\ue200image_group\ue202{"query":["Ottawa skyline","Parliament Hill"],"aspect_ratio":"5:3","layout":"carousel"}\ue201\n'
            'Also entity["city","Toronto"] and a stray \ue206 mark.')
    for find, repl in b.GPT_MARKUP:
        text = _py(find).sub(repl.replace('$1', r'\1'), text)
    assert text == 'The capital is Ottawa, on the Ottawa River.\n\nAlso Toronto and a stray  mark.'


def test_chatgpt_cite_markers_removed():
    sys.path.insert(0, str(ROOT / 'src'))
    import build_shortcut as b

    def clean(text):
        for find, repl in b.GPT_MARKUP:
            text = _py(find).sub(repl.replace('$1', r'\1'), text)
        return text
    assert clean('ok. citeturn752459search6turn752459search11') == 'ok. '
    assert clean('a\ue200cite\ue202turn0search1\ue202turn0news2\ue201 b') == 'a b'
    assert clean('x \ue200filecite\ue202turn3file0\ue201.') == 'x .'
    assert clean('He cited turn-by-turn directions; a list of things') == 'He cited turn-by-turn directions; a list of things'


@pytest.mark.parametrize('lang', LANGS)
def test_every_claude_request_starts_with_brevity_line(tmp_path, lang):
    """14.11 live run: a long Claude answer broke «Ask Claude»; every request (except SVG image steps) is short-first."""
    ui = ui_of(lang)
    line = ui['brief']['claude']
    actions = build(tmp_path, lang)
    claude = [a for a in actions if a['WFWorkflowActionIdentifier'] == 'com.anthropic.claude.ClaudeAppIntentsExtension']
    assert claude
    with_line = [a for a in claude if params(a)['message']['Value']['string'].startswith(line)]
    assert len(claude) - len(with_line) == 2   # the two SVG image steps (the Setup's ping carries the line, D-128)
    for a in with_line:
        v = params(a)['message']['Value']
        for key in v['attachmentsByRange']:
            pos = int(key.strip('{}').split(',')[0])
            assert v['string'].encode('utf-16-le')[pos * 2:pos * 2 + 2].decode('utf-16-le') == '￼'


@pytest.mark.parametrize('lang', LANGS)
def test_every_chatgpt_request_starts_with_length_line(tmp_path, lang):
    """22.11 live run (Duo 6.10 limits): «Ask ChatGPT» is cut off at about 30 s as «Ask Claude» is; every request
    (except the SVG image steps) starts with ui.brief.chatgpt, and the attachments still point at their objects."""
    line = ui_of(lang)['brief']['chatgpt']
    actions = build(tmp_path, lang)
    gpt = [a for a in actions if a['WFWorkflowActionIdentifier'] == 'com.openai.chat.AskIntent']
    assert gpt
    with_line = [a for a in gpt if params(a)['prompt']['Value']['string'].startswith(line + '\n\n')]
    assert len(gpt) - len(with_line) == 4   # the two SVG image steps and their automatic retries
    for a in with_line:
        v = params(a)['prompt']['Value']
        assert v['attachmentsByRange']
        for key in v['attachmentsByRange']:
            pos = int(key.strip('{}').split(',')[0])
            assert v['string'].encode('utf-16-le')[pos * 2:pos * 2 + 2].decode('utf-16-le') == '\ufffc'


@pytest.mark.parametrize('lang', LANGS)
def test_length_lines_are_only_a_length_cap(lang):
    """22.11 live run: only the length was proven to matter. No «do not search» (the Claude action has no search), no
    «do not think long» (no change in time), no «only the result and what to check» (it cut the blind answer)."""
    brief = ui_of(lang)['brief']
    assert set(brief) == {'claude', 'chatgpt'}
    for text in brief.values():
        assert any(ch.isdigit() for ch in text)
        assert len(text) < 90, text


def test_run_name_follows_dated_diag_name(tmp_path):
    """15.11, No.67: Back / Another mode must run the SAME shortcut that is installed (Duo-diag-0154), not an old Duo-diag."""
    env = dict(os.environ, C1_DIST=str(tmp_path), C1_DIAG='1', C1_RUN_NAME='Duo-diag-0154')
    subprocess.run([sys.executable, str(ROOT / 'src' / 'build_shortcut.py'), 'uk'], check=True, cwd=ROOT, env=env,
                   capture_output=True)
    actions = plistlib.loads((tmp_path / 'uk' / 'Poly-diag.shortcut').read_bytes())['WFWorkflowActions']
    names = {str(params(a)['WFWorkflowName']) for a in actions if kind(a) == 'runworkflow'}
    assert names and all('Duo-diag-0154' in n for n in names), names


def test_finale_another_mode_ends_the_run():
    """«Another mode» in What next? starts a new run and ends this one (no fall-through into More…)."""
    src = (ROOT / 'src' / 'build_shortcut.py').read_text()
    i = src.index("*rerun_with_menu(q_get, 'Variable'),")
    assert 'is.workflow.actions.exit' in src[i:i + 200]


SVERENO = '\u0421\u0432\u0435\u0440\u0435\u043d\u043e'
RU_LANG = '\u043d\u0430 \u044f\u0437\u044b\u043a\u0435 \u0432\u043e\u043f\u0440\u043e\u0441\u0430'


@pytest.mark.parametrize('lang', LANGS)
def test_checked_against_line_follows_question_language(lang):
    """15.11: the status line «Checked against / Not checked» is written in the language of the question."""
    import glob
    d = ROOT / 'locales' / ('ru' if lang == 'ru' else 'en') / 'prompts'
    hits = [f for f in glob.glob(str(d / '*.txt')) if 'Checked against' in open(f).read() or SVERENO in open(f).read()]
    assert len(hits) >= 10
    for f in hits:
        t = open(f).read()
        assert 'language of the question' in t or RU_LANG in t, f
