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
    prev = False   # is the output of the PREVIOUS action tainted (what an action with no input of its own may take)

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
            prev = True
            continue
        if k == 'conditional':
            mode = p['WFControlFlowMode']
            if mode == 0:
                ctx.append(tainted_in)
                prev = tainted_in
            elif mode == 1:
                prev = prev or (ctx[-1] if ctx else False)   # the Otherwise branch starts from the If's input
            elif ctx:
                closed = ctx.pop()
                prev = prev or closed   # «End If» hands on the output of the branch that ran, or the If's input
            continue
        in_tainted_if = any(ctx)
        taken = tainted_in or in_tainted_if or prev   # worst case: an action with no input takes the previous output
        sink = (k in ('AskIntent', 'ClaudeAppIntentsExtension', 'setclipboard', 'append', 'runworkflow', 'ask',
                      'notification', 'openurl', 'speaktext')
                or (k == 'save' and p.get('WFFileDestinationPath') != 'Duo-prefs.txt'))
        if sink and taken:
            bad.append((i, k))
        if k == 'nothing':
            out = False
        elif k == 'setvariable':
            out = tainted_in
            (tainted_var.add if out else tainted_var.discard)(p['WFVariableName'])
        else:
            out = taken
        if out and uid:
            tainted_uid.add(uid)
        prev = out
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
    nothing_ = {'WFWorkflowActionIdentifier': 'is.workflow.actions.nothing', 'WFWorkflowActionParameters': {'UUID': 'N'}}
    # a Text in the If is tainted but unused; a «Nothing» after «End If» ends the chain
    assert _taint_violations([get, cond, text, setv, end, nothing_, gpt]) == []
    use = {'WFWorkflowActionIdentifier': 'is.workflow.actions.getvariable',
           'WFWorkflowActionParameters': {'WFVariable': {'Value': {'Type': 'Variable', 'VariableName': 'Flag'}},
                                          'UUID': 'U'}}
    gpt2 = {'WFWorkflowActionIdentifier': 'com.openai.chat.AskIntent',
            'WFWorkflowActionParameters': {'prompt': {'Value': {'attachmentsByRange': {'{0, 1}': {
                'OutputUUID': 'U', 'Type': 'ActionOutput'}}}}}}
    assert _taint_violations([get, cond, text, setv, end, use, gpt2]) == [(6, 'AskIntent')]   # taken through the variable
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


def _act(identifier, **p):
    return {'WFWorkflowActionIdentifier': identifier, 'WFWorkflowActionParameters': p}


def test_the_leak_test_follows_an_action_without_input_after_end_if_and_the_other_sinks():
    get = _act('is.workflow.actions.documentpicker.open', WFGetFilePath='Duo-prefs.txt', UUID='F')
    cond = _act('is.workflow.actions.conditional', WFControlFlowMode=0, GroupingIdentifier='g',
                WFInput={'Value': {'OutputUUID': 'F'}})
    end = _act('is.workflow.actions.conditional', WFControlFlowMode=2, GroupingIdentifier='g')
    # an action with no input of its own right after «End If» takes the If's output
    assert _taint_violations([get, cond, end, _act('is.workflow.actions.openurl')]) == [(3, 'openurl')]
    assert _taint_violations([get, cond, end, _act('is.workflow.actions.speaktext')]) == [(3, 'speaktext')]
    assert _taint_violations([get, cond, end, _act('is.workflow.actions.setclipboard')]) == [(3, 'setclipboard')]
    # …and a Text made there carries it on to a later request
    text = _act('is.workflow.actions.gettext', WFTextActionText='x', UUID='T')
    gpt = _act('com.openai.chat.AskIntent', prompt={'Value': {'attachmentsByRange': {'{0, 1}': {'OutputUUID': 'T'}}}})
    assert _taint_violations([get, cond, end, text, gpt]) == [(4, 'AskIntent')]
    # «Nothing» breaks the chain
    nothing = _act('is.workflow.actions.nothing', UUID='N')
    assert _taint_violations([get, cond, end, nothing, _act('is.workflow.actions.openurl')]) == []


@pytest.mark.parametrize('lang', LANGS)
def test_prefs_are_known_before_the_resume_menu_and_every_more_item_is_safe(tmp_path, lang):
    """B-1: on a run that goes on from a saved draft the file used to be read AFTER the resume branch, so the «OFF»
    flags were unset (= «on») and «More… → Critique right away» wrote QUICK=1 (and the other way round)."""
    actions = build(tmp_path, lang)
    names = [(i, params(a).get('WFVariableName')) for i, a in enumerate(actions) if kind(a) == 'setvariable']
    read = next(i for i, a in enumerate(actions) if params(a).get('WFGetFilePath') == 'Duo-prefs.txt')
    draft = next(i for i, a in enumerate(actions) if str(params(a).get('WFGetFilePath', '')).startswith('Duo-draft'))
    first_flag = {n: min(i for i, x in names if x == n) for n in ('PolyModeOff', 'PolyQuickOff')}
    resume_menu = next(i for i, a in enumerate(actions) if kind(a) == 'choosefrommenu'
                       and params(a).get('WFMenuPrompt') == ui_of(lang)['menu']['resume1_title'])
    # the two flags are set, the file is read and its Ifs are done BEFORE the draft is looked at
    assert max(first_flag.values()) < read < draft < resume_menu
    # …and at the top level: no If or menu is open when the file is read, so every run (fresh, resumed, shared) reads it
    depth = 0
    for a in actions[:read]:
        if kind(a) in ('conditional', 'choosefrommenu'):
            mode = params(a)['WFControlFlowMode']
            depth += 1 if mode == 0 else (-1 if mode == 2 else 0)
    assert depth == 0
    # every use of the flags (the save block after «More…») comes after that read
    uses = [i for i, a in enumerate(actions) if kind(a) == 'getvariable'
            and params(a)['WFVariable']['Value'].get('VariableName') in ('PolyModeOff', 'PolyQuickOff')]
    assert uses and min(uses) > read
    # «Saved» is told after the file is written, once per switch
    save = next(i for i, a in enumerate(actions) if params(a).get('WFFileDestinationPath') == 'Duo-prefs.txt')
    n = ui_of(lang)['notify']
    for key in ('pref_mode', 'pref_quick', 'pref_reset'):
        at = [i for i, a in enumerate(actions) if params(a).get('WFNotificationActionBody') == n[key]]
        assert len(at) == 1 and at[0] > save


@pytest.mark.parametrize('lang', LANGS)
def test_each_more_switch_changes_only_its_own_flag(tmp_path, lang):
    ui = ui_of(lang)
    actions = build(tmp_path, lang)
    read = next(i for i, a in enumerate(actions) if params(a).get('WFGetFilePath') == 'Duo-prefs.txt')
    # both menus of the resumed run come after the read, and both prefs Ifs are closed before the draft is looked at
    for key in ('resume0_title', 'resume1_title'):
        menu = next(i for i, a in enumerate(actions) if params(a).get('WFMenuPrompt') == ui['menu'][key])
        assert menu > read
    draft = next(i for i, a in enumerate(actions) if str(params(a).get('WFGetFilePath', '')).startswith('Duo-draft'))
    closes = [i for i in range(read, draft) if kind(actions[i]) == 'conditional'
              and params(actions[i])['WFControlFlowMode'] == 2]
    assert len(closes) >= 2
    items = ui['menu']['finale_more_items']
    cases = []
    for item in items[4:7]:
        start = next(i for i, a in enumerate(actions)
                     if kind(a) == 'choosefrommenu' and params(a).get('WFMenuItemTitle') == item)
        end = next(i for i in range(start + 1, len(actions)) if kind(actions[i]) == 'choosefrommenu')
        cases.append([params(a)['WFVariableName'] for a in actions[start:end] if kind(a) == 'setvariable'])
    mode, quick, reset = cases
    assert mode == ['PolyModeOff', 'PolyPrefsChanged', 'PolyNoteMode']
    assert quick == ['PolyQuickOff', 'PolyPrefsChanged', 'PolyNoteQuick']
    assert reset == ['PolyModeOff', 'PolyQuickOff', 'PolyPrefsChanged', 'PolyNoteReset']
