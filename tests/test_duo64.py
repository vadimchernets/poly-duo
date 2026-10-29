"""Duo 6.4 (D-101): the Critique draft through ONE «Save File», the resume menu after a run cut off by a message
limit, and the answer of whichever AI answered when the other one did not."""
import json

import pytest

from test_first_run import LANGS, ROOT, build, kind, guard_var

DRAFT_STEP0, DRAFT_STEP1, DRAFT_DONE = '⟦duo-draft:0⟧', '⟦duo-draft:1⟧', '⟦duo-draft:done⟧'


def params(a):
    return a['WFWorkflowActionParameters']


def ui_of(lang):
    return json.loads((ROOT / 'locales' / lang / 'ui.json').read_text(encoding='utf-8'))


def groups_open(actions, index, kinds=('conditional', 'count', 'each', 'choosefrommenu')):
    stack = []
    for a in actions[:index]:
        p = params(a)
        if 'GroupingIdentifier' not in p or kind(a) not in kinds:
            continue
        if p['WFControlFlowMode'] == 0:
            stack.append(a)
        elif p['WFControlFlowMode'] == 2:
            stack.pop()
    return stack


def text_of(actions, uid):
    a = next(a for a in actions if params(a).get('UUID') == uid)
    return params(a)['WFTextActionText']['Value']['string']


def sets(actions, var):
    """(index, text) of every «Set Variable var» fed by a Text action."""
    out = []
    for i, a in enumerate(actions):
        if kind(a) == 'setvariable' and params(a)['WFVariableName'] == var:
            src = params(a)['WFInput']['Value'].get('OutputUUID')
            src_a = next((b for b in actions if params(b).get('UUID') == src), None)
            out.append((i, params(src_a)['WFTextActionText']['Value']['string'] if src_a and kind(src_a) == 'gettext' else None))
    return out


@pytest.mark.parametrize('lang', LANGS)
def test_one_draft_save_runs_three_times(tmp_path, lang):
    actions = build(tmp_path, lang)
    saves = [i for i, a in enumerate(actions) if kind(a) == 'save'
             and str(params(a)['WFFileDestinationPath']).startswith('Duo-draft-')]
    assert len(saves) == 1 and params(actions[saves[0]])['WFFileDestinationPath'] == f'Duo-draft-{lang}-std.txt'
    s = saves[0]
    loop = [g for g in groups_open(actions, s) if kind(g) == 'count']
    assert len(loop) == 1 and params(loop[0])['WFRepeatCount'] == 3
    # the save writes PolyDraft (as a Text made from it), only when PolyDraft holds text
    assert guard_var(actions, groups_open(actions, s)[-1]) == 'PolyDraft'
    # step 0 before the loop, step 1 after ChatGPT, «done» after Claude's comparison, in this order
    drafts = sets(actions, 'PolyDraft')
    steps = [(i, t.split('\n')[0]) for i, t in drafts if t]
    assert [t for _, t in steps] == [DRAFT_STEP0, DRAFT_STEP1, DRAFT_DONE]
    loop_start = actions.index(loop[0])
    gpt = next(i for i in range(loop_start, len(actions)) if kind(actions[i]) == 'AskIntent')
    compare = max(i for i in range(loop_start, steps[2][0]) if kind(actions[i]) == 'ClaudeAppIntentsExtension')
    assert steps[0][0] < loop_start < s < gpt < steps[1][0] < compare < steps[2][0]
    # the step-1 draft carries the question and ChatGPT's answer, between the markers the resume reads
    assert '⟦Q⟧\n' in drafts[[i for i, _ in drafts].index(steps[1][0])][1]
    # the number pass inside the loop reads the inner loop's item: «Repeat Item 2» (checked on Shortcuts 28.10)
    inner = [params(a)['WFVariable']['Value']['VariableName'] for a in actions[loop_start:steps[2][0]]
             if kind(a) == 'getvariable' and params(a)['WFVariable']['Value']['VariableName'].startswith('Repeat Item')]
    assert inner == ['Repeat Item 2', 'Repeat Item 2']
    # My mode (no loop) still reads «Repeat Item»
    before = [params(a)['WFVariable']['Value']['VariableName'] for a in actions[:loop_start]
              if kind(a) == 'getvariable' and params(a)['WFVariable']['Value']['VariableName'].startswith('Repeat Item')]
    assert before == ['Repeat Item', 'Repeat Item']


@pytest.mark.parametrize('lang', LANGS)
def test_resume_menu_before_the_question(tmp_path, lang):
    ui = ui_of(lang)
    m = ui['menu']
    actions = build(tmp_path, lang)
    ask = next(i for i, a in enumerate(actions) if kind(a) == 'ask' and params(a)['WFAskActionPrompt'] == ui['ask']['question'])
    m1 = next(i for i, a in enumerate(actions) if params(a).get('WFMenuPrompt') == m['resume1_title'])
    m0 = next(i for i, a in enumerate(actions) if params(a).get('WFMenuPrompt') == m['resume0_title'])
    assert m1 < m0 < ask
    assert len(m['resume1_items']) == 4 and len(m['resume0_items']) == 3
    for menu in (m1, m0):
        outer = groups_open(actions, menu)
        # only without Shortcut Input (in its Otherwise), with a draft file younger than 30 minutes
        assert params(outer[0])['WFInput']['Variable']['Value'] == {'Type': 'ExtensionInput'}
        age = next(c for c in outer if params(c)['WFCondition'] == 1003)
        assert (params(age)['WFNumberValue'], params(age)['WFAnotherNumber']) == (-30, 30)
        assert params(age)['WFInput']['Variable']['Value']['OutputName'] == 'Number'
    marks = [params(c).get('WFConditionalActionString') for c in groups_open(actions, m0) if params(c)['WFCondition'] == 99]
    assert marks == [DRAFT_STEP1, DRAFT_STEP0]   # step 0 is tested in the Otherwise of «step 1»
    marks = [params(c).get('WFConditionalActionString') for c in groups_open(actions, m1) if params(c)['WFCondition'] == 99]
    assert marks == [DRAFT_STEP1]
    # every choice but «new question» resumes: PolyResume set, the question from the draft
    for menu, items in ((m1, m['resume1_items']), (m0, m['resume0_items'])):
        group = params(actions[menu])['GroupingIdentifier']
        cases = [i for i, a in enumerate(actions) if params(a).get('GroupingIdentifier') == group]
        for c, nxt, item in zip(cases[1:-1], cases[2:], items):
            body = actions[c + 1:nxt]
            names = [params(a)['WFVariableName'] for a in body if kind(a) == 'setvariable']
            if item == items[-1]:
                assert names == []
            else:
                assert 'PolyResume' in names and 'PolyQuestion' in names
    # step 1: go on (ChatGPT's answer from the draft, Critique, no new ChatGPT message) / check / show
    g1 = params(actions[m1])['GroupingIdentifier']
    c1 = [i for i, a in enumerate(actions) if params(a).get('GroupingIdentifier') == g1]
    go = [params(a)['WFVariableName'] for a in actions[c1[1]:c1[2]] if kind(a) == 'setvariable']
    assert {'PolyChatGPTAnswer', 'PolyCritique'} <= set(go)
    assert any(params(a).get('WFNotificationActionBody') == ui['notify']['resume'] for a in actions[c1[1]:c1[2]])
    check = [params(a)['WFVariableName'] for a in actions[c1[2]:c1[3]] if kind(a) == 'setvariable']
    assert {'PolyCheckRequest', 'PolyClaudeDown', ui['variables']['result']} <= set(check)
    show = [params(a)['WFVariableName'] for a in actions[c1[3]:c1[4]] if kind(a) == 'setvariable']
    assert ui['variables']['result'] in show and 'PolyCritique' not in show and 'PolyClaudeDown' not in show
    # step 0: Claude alone skips ChatGPT; «both again» does not
    g0 = params(actions[m0])['GroupingIdentifier']
    c0 = [i for i, a in enumerate(actions) if params(a).get('GroupingIdentifier') == g0]
    alone = [params(a)['WFVariableName'] for a in actions[c0[1]:c0[2]] if kind(a) == 'setvariable']
    again = [params(a)['WFVariableName'] for a in actions[c0[2]:c0[3]] if kind(a) == 'setvariable']
    assert 'PolySkipChatGPT' in alone and 'PolySkipChatGPT' not in again and 'PolyCritique' in again
    # nothing is asked of an AI and nothing is written before the question field
    # (the one save before them is the first-run notice's marker, as in Duo 6.3)
    assert not any(kind(a) in ('AskIntent', 'ClaudeAppIntentsExtension', 'save', 'setclipboard') for a in actions[m1 - 40:ask])
    # the question field and the mode menu are skipped when resuming
    assert guard_var(actions, groups_open(actions, ask)[0]) == 'PolyResume'


@pytest.mark.parametrize('lang', LANGS)
def test_whoever_answered_is_delivered(tmp_path, lang):
    ui = ui_of(lang)
    result = ui['variables']['result']
    actions = build(tmp_path, lang)
    assert '{A}' in ui['output']['claude_down'] and '{C}' in ui['output']['gpt_down']
    for key, needle in (('claude_down', '{A}'), ('gpt_down', '{C}')):
        head = ui['output'][key].split(needle)[0]
        found = [(i, t) for i, t in sets(actions, result) if t and t.startswith(head)]
        if key == 'claude_down':
            assert len(found) == 4   # both Critique blocks, and the resume's «check» and «show»
        else:
            assert len(found) == 2   # both Critique blocks
    # in-run: Claude did not compare → ChatGPT's answer + CLAUDE_DOWN, in the Otherwise of «Claude compared»
    main_start = max(i for i, a in enumerate(actions)
                     if params(a).get('WFNotificationActionBody') == ui['notify']['critique_start'])
    head = ui['output']['claude_down'].split('{A}')[0]
    i = next(i for i, t in sets(actions, result) if i > main_start and t and t.startswith(head))
    assert guard_var(actions, groups_open(actions, i, ('conditional',))[-1]) == 'PolyClaudeAnswer'
    down = next(j for j, _ in sets(actions, 'PolyClaudeDown') if j > i)
    assert down - i <= 3
    # ChatGPT gave nothing → Claude's own answer, no comparing message (the compare call is not in that branch)
    head = ui['output']['gpt_down'].split('{C}')[0]
    j = next(j for j, t in sets(actions, result) if j > main_start and t and t.startswith(head))
    assert guard_var(actions, groups_open(actions, j, ('conditional',))[-1]) == 'PolyClaudeOwn'
    both = groups_open(actions, j, ('conditional',))[-2]
    assert guard_var(actions, both) == 'PolyChatGPTAnswer'
    # the person is told at once when ChatGPT gave nothing
    assert sum(params(a).get('WFNotificationActionBody') == ui['notify']['gpt_down'] for a in actions) == 2


@pytest.mark.parametrize('lang', LANGS)
def test_tail_offers_check_then_copies_once(tmp_path, lang):
    ui = ui_of(lang)
    actions = build(tmp_path, lang)
    down = next(i for i, a in enumerate(actions) if params(a).get('WFMenuItems') == ui['menu']['claude_down_items'])
    assert guard_var(actions, groups_open(actions, down, ('conditional',))[0]) == 'PolyClaudeDown'
    group = params(actions[down])['GroupingIdentifier']
    end = max(i for i, a in enumerate(actions) if params(a).get('GroupingIdentifier') == group)
    # inside the menu only «by hand» copies (its own request) — and then empties RESULT so the tail keeps it there
    copies = [i for i in range(down, end) if kind(actions[i]) == 'setclipboard']
    assert len(copies) == 1
    manual = [params(a)['WFVariableName'] for a in actions[copies[0]:end] if kind(a) == 'setvariable']
    assert manual == [ui['variables']['result']]
    done = next(i for i, a in enumerate(actions) if params(a).get('WFNotificationActionBody') == ui['notify']['tail_done'])
    assert end < done


@pytest.mark.parametrize('lang', LANGS)
def test_resume_strings_keep_their_shape(lang):
    ui = ui_of(lang)
    en = ui_of('en')
    for key in ('resume1_items', 'resume0_items'):
        assert len(ui['menu'][key]) == len(en['menu'][key])
        assert [x.split(' ')[0] for x in ui['menu'][key]] == [x.split(' ')[0] for x in en['menu'][key]]
        assert [x.endswith('✉') for x in ui['menu'][key]] == [x.endswith('✉') for x in en['menu'][key]]
    assert ui['output']['claude_down'].endswith('{A}') and ui['output']['gpt_down'].endswith('{C}')


def test_trio_search_sources_need_no_dictionary_walk(tmp_path):
    """D-101 (live iPhone 29.10): Trio stopped with «Choose values for each parameter in this action» first on «If
    <groundingChunks> has any value», then inside the walk over the chunks (Get Dictionary Value «web» / «uri» on a chunk
    without them). The sources come from the answer's text now: no lookups of those keys, no Repeat over chunks."""
    actions = build(tmp_path, 'en', 'build_trio.py', 'Trio.shortcut')
    keys = {params(a).get('WFDictionaryKey') for a in actions if kind(a) == 'getvalueforkey'}
    assert not keys & {'groundingChunks', 'groundingMetadata', 'web', 'uri', 'title'}
