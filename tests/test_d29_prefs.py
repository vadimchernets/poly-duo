"""D-29: «Critique right away» (C-1), «ask without editing» (C-3, off by default), the menu marker on Duo's own
re-runs, and the shorter start notifications (C-6) with the «logged out» hint moved to where it is needed."""
import json

import pytest

from test_first_run import LANGS, ROOT, build, kind

MARK = '⟦duo-menu⟧\n'


def params(a):
    return a['WFWorkflowActionParameters']


def ui_of(lang):
    return json.loads((ROOT / 'locales' / lang / 'ui.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('lang', LANGS)
def test_prefs_file_is_read_once_and_written_once(tmp_path, lang):
    actions = build(tmp_path, lang)
    gets = [a for a in actions if kind(a) == 'documentpicker.open' or params(a).get('WFGetFilePath') == 'Duo-prefs.txt']
    reads = [a for a in actions if params(a).get('WFGetFilePath') == 'Duo-prefs.txt']
    saves = [a for a in actions if params(a).get('WFFileDestinationPath') == 'Duo-prefs.txt']
    assert len(reads) == 1 and len(saves) == 1 and gets
    # the read comes before the question box; both options are off when the file is missing (default)
    ask = next(i for i, a in enumerate(actions) if kind(a) == 'ask')
    assert actions.index(reads[0]) < ask
    pats = [params(a).get('WFMatchTextPattern') for a in actions[:ask] if kind(a) == 'match']
    assert r'(?m)^MODE=critique$' in pats and r'(?m)^QUICK=1$' in pats   # whole lines only


@pytest.mark.parametrize('lang', LANGS)
def test_every_rerun_carries_the_menu_marker(tmp_path, lang):
    actions = build(tmp_path, lang)
    by_uid = {params(a).get('UUID'): a for a in actions}
    runs = [a for a in actions if kind(a) == 'runworkflow']
    assert len(runs) >= 7   # 5 recipes x2 menus is 10, plus «go back» and «Another mode»
    for r in runs:
        src = by_uid[params(r)['WFInput']['Value']['OutputUUID']]
        assert kind(src) == 'gettext' and params(src)['WFTextActionText']['Value']['string'].startswith(MARK)
    # the marker is cut off again before the question box
    pats = [params(a).get('WFMatchTextPattern') for a in actions if kind(a) == 'match']
    assert r'^⟦duo-menu⟧\n' in pats and r'(?s)(?<=^⟦duo-menu⟧\n).*' in pats   # only at the very start of the text


@pytest.mark.parametrize('lang', LANGS)
def test_hint_moved_out_of_start_notifications(tmp_path, lang):
    ui = ui_of(lang)
    n = ui['notify']
    for k, v in n.items():
        if k not in ('gpt_down', 'critique_start'):   # critique_start keeps the short «Stuck? Open ChatGPT and sign in»
            assert 'logged out' not in v, k
    assert 'logged out' in n['gpt_down'] and 'logged out' in ui['alert']['first_run_body']
    assert 'ChatGPT' in ui['notify']['critique_start'].split('.')[-2 if ui['notify']['critique_start'].endswith('.') else -1] or 'ChatGPT' in ui['notify']['critique_start'][-40:]
    assert len(ui['menu']['finale_more_items']) == 7
    for k in ('pref_mode', 'pref_quick', 'pref_reset'):
        assert n[k].strip()


# ---------------------------------------------------------------------------------------------------------------------
# Leak test (iPhone 29.10, d30): with «Critique right away» on, the text of Duo-prefs.txt («⟦duo-prefs⟧ MODE=critique»)
# went to ChatGPT, Claude and the clipboard together with the question, and iOS asked for 8 permissions again.
# The data flow is modelled the way Shortcuts really runs a list of actions, with the worst case for each unknown:
#  * a value is tainted when it is built from a tainted output (an attachment in any text or parameter), from a
#    tainted variable, or — for Text / Notification actions — INSIDE an If whose input is tainted (an action without
#    its own input may take the previous output; the iPhone showed exactly this);
#  * «Nothing» is clean, and so is a variable set from it (the only thing a prefs-dependent If may do);
#  * every request to an AI app, every clipboard write, every file write except Duo-prefs.txt itself, every run of
#    Duo and every question box must be untainted. Branches are all treated as run (the worst case).
def _taint_violations(actions):
    tainted_uid, tainted_var, ctx, bad = set(), set(), [], []

    def refs(value, out):
        if isinstance(value, dict):
            if 'OutputUUID' in value:
                out.append(('uid', value['OutputUUID']))
            if value.get('Type') == 'Variable' and 'VariableName' in value:
                out.append(('var', value['VariableName']))
            for v in value.values():
                refs(v, out)
        elif isinstance(value, list):
            for v in value:
                refs(v, out)

    for i, a in enumerate(actions):
        k, p = kind(a), params(a)
        uid = p.get('UUID')
        found = []
        refs({x: v for x, v in p.items() if x != 'UUID'}, found)
        tainted_in = any((t == 'uid' and v in tainted_uid) or (t == 'var' and v in tainted_var) for t, v in found)
        if p.get('WFGetFilePath') == 'Duo-prefs.txt':
            tainted_uid.add(uid)
            continue
        if k == 'conditional':
            mode = p['WFControlFlowMode']
            if mode == 0:
                ctx.append(tainted_in)
            elif mode == 2 and ctx:
                ctx.pop()
            continue
        in_tainted_if = any(ctx)
        sink = (k in ('AskIntent', 'ClaudeAppIntentsExtension', 'setclipboard', 'append', 'runworkflow', 'ask', 'notification')
                or (k == 'save' and p.get('WFFileDestinationPath') != 'Duo-prefs.txt'))
        if sink and (tainted_in or in_tainted_if):
            bad.append((i, k))
        if k == 'nothing':
            out = False
        elif k == 'setvariable':
            out = tainted_in
            (tainted_var.add if out else tainted_var.discard)(p['WFVariableName'])
            continue
        else:   # any other action may take the previous output when it has no input of its own (Kimi: not only Text)
            out = tainted_in or in_tainted_if
        if out and uid:
            tainted_uid.add(uid)
    return bad


@pytest.mark.parametrize('lang', LANGS)
def test_prefs_text_never_reaches_a_request_the_clipboard_or_a_file(tmp_path, lang):
    assert _taint_violations(build(tmp_path, lang)) == []


def test_the_leak_test_catches_the_old_shape():
    """The same model flags the build that leaked on the iPhone: a flag made by a Text inside an If on the file."""
    get = {'WFWorkflowActionIdentifier': 'is.workflow.actions.documentpicker.open',
           'WFWorkflowActionParameters': {'WFGetFilePath': 'Duo-prefs.txt', 'UUID': 'F'}}
    cond = {'WFWorkflowActionIdentifier': 'is.workflow.actions.conditional',
            'WFWorkflowActionParameters': {'WFControlFlowMode': 0, 'GroupingIdentifier': 'g',
                                           'WFInput': {'Value': {'OutputUUID': 'F'}}}}
    text = {'WFWorkflowActionIdentifier': 'is.workflow.actions.gettext',
            'WFWorkflowActionParameters': {'WFTextActionText': 'MODE', 'UUID': 'T'}}
    setv = {'WFWorkflowActionIdentifier': 'is.workflow.actions.setvariable',
            'WFWorkflowActionParameters': {'WFVariableName': 'Flag', 'WFInput': {'Value': {'OutputUUID': 'T'}}}}
    end = {'WFWorkflowActionIdentifier': 'is.workflow.actions.conditional',
           'WFWorkflowActionParameters': {'WFControlFlowMode': 2, 'GroupingIdentifier': 'g'}}
    gpt = {'WFWorkflowActionIdentifier': 'com.openai.chat.AskIntent',
           'WFWorkflowActionParameters': {'prompt': {'Value': {'attachmentsByRange': {'{0, 1}': {
               'OutputUUID': 'X', 'Type': 'ActionOutput'}}}}}}
    assert _taint_violations([get, cond, text, setv, end, gpt]) == []   # a Text in the If is tainted, but unused
    use = {'WFWorkflowActionIdentifier': 'is.workflow.actions.getvariable',
           'WFWorkflowActionParameters': {'WFVariable': {'Value': {'Type': 'Variable', 'VariableName': 'Flag'}},
                                          'UUID': 'U'}}
    gpt2 = {'WFWorkflowActionIdentifier': 'com.openai.chat.AskIntent',
            'WFWorkflowActionParameters': {'prompt': {'Value': {'attachmentsByRange': {'{0, 1}': {
                'OutputUUID': 'U', 'Type': 'ActionOutput'}}}}}}
    assert _taint_violations([get, cond, text, setv, end, use, gpt2]) == [(6, 'AskIntent')]
    inside = {'WFWorkflowActionIdentifier': 'com.openai.chat.AskIntent', 'WFWorkflowActionParameters': {'prompt': 'x'}}
    assert _taint_violations([get, cond, inside, end]) == [(2, 'AskIntent')]


@pytest.mark.parametrize('lang', LANGS)
def test_prefs_flags_are_only_cleared_inside_the_file_dependent_ifs(tmp_path, lang):
    actions = build(tmp_path, lang)
    read = next(i for i, a in enumerate(actions) if params(a).get('WFGetFilePath') == 'Duo-prefs.txt')
    ask = next(i for i, a in enumerate(actions) if kind(a) == 'ask')
    # between the read and the end of its two Ifs only Match / If / Nothing / Set Variable (from Nothing) appear
    end_of_ifs = [i for i in range(read, ask) if kind(actions[i]) == 'conditional'
                  and params(actions[i])['WFControlFlowMode'] == 2][1]
    inside = [kind(a) for a in actions[read + 2:end_of_ifs + 1]]
    assert set(inside) <= {'match', 'conditional', 'nothing', 'setvariable'}, inside
