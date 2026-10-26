"""Duo 6.1: (2) Duo's own last answer in the clipboard is not offered back as the next question; (3) Recipes are
reachable with an empty question, and «My own checking rule» without its file offers to write it or go back."""
import json

import pytest

from test_first_run import LANGS, ROOT, build, kind


def params(a):
    return a['WFWorkflowActionParameters']


def ui_of(lang):
    return json.loads((ROOT / 'locales' / lang / 'ui.json').read_text(encoding='utf-8'))


def saves_of(actions, path):
    return [i for i, a in enumerate(actions) if kind(a) == 'save' and params(a).get('WFFileDestinationPath') == path]


def ref(token):
    """The single action output inside a text token string."""
    (att,) = token['Value']['attachmentsByRange'].values()
    return att['OutputUUID'], att['OutputName']


@pytest.mark.parametrize('lang', LANGS)
def test_own_answer_not_prefilled(tmp_path, lang):
    ui = ui_of(lang)
    actions = build(tmp_path, lang)
    last = ui['files']['last_answer']
    uid = {params(a).get('UUID'): i for i, a in enumerate(actions) if params(a).get('UUID')}

    # --- at the start: clipboard (3+ words) → START; then, if the clipboard's first 200 characters are the same
    # text as the remembered start of Duo's last clipboard write, START is emptied again. All of it inside the
    # clipboard branch, before the question field.
    clip = next(i for i, a in enumerate(actions) if kind(a) == 'getclipboard')
    ask = next(i for i, a in enumerate(actions) if kind(a) == 'ask'
               and params(a)['WFAskActionPrompt'] == ui['ask']['question'])
    seq = [kind(a) for a in actions[clip:clip + 16]]
    assert seq == ['getclipboard', 'match', 'conditional', 'setvariable',
                   'open', 'gettext', 'conditional', 'match', 'gettext', 'conditional',
                   'gettext', 'setvariable', 'conditional', 'conditional', 'conditional', 'conditional']
    get = params(actions[clip + 4])
    assert get['WFGetFilePath'] == last and get['WFFileErrorIfNotFound'] is False and get['WFShowFilePicker'] is False
    file_text = params(actions[clip + 5])['UUID']
    assert ref(params(actions[clip + 5])['WFTextActionText']) == (get['UUID'], 'File')
    # a missing / empty file is «no value»: the clipboard is used as before
    has = params(actions[clip + 6])
    assert has['WFCondition'] == 100 and has['WFInput']['Variable']['Value']['OutputUUID'] == file_text
    # the clipboard is cut exactly as the saved text was (same pattern, same Match Text → Text), then compared with «is»
    cut = params(actions[clip + 7])
    assert cut['WFMatchTextPattern'] == '(?s)^.{1,200}'
    assert ref(cut['text']) == (params(actions[clip])['UUID'], 'Clipboard')
    assert ref(params(actions[clip + 8])['WFTextActionText']) == (cut['UUID'], 'Matches')
    mine = params(actions[clip + 9])
    assert mine['WFCondition'] == 4
    assert mine['WFInput']['Variable']['Value'] == {'OutputUUID': params(actions[clip + 8])['UUID'],
                                                     'Type': 'ActionOutput', 'OutputName': 'Text'}
    assert ref(mine['WFConditionalActionString']) == (file_text, 'Text')
    assert params(actions[clip + 10])['WFTextActionText']['Value']['string'] == ''
    assert params(actions[clip + 11])['WFVariableName'] == 'PolyStartText'
    groups = [params(actions[i])['GroupingIdentifier'] for i in (clip + 9, clip + 6, clip + 2)]
    assert [params(actions[i])['GroupingIdentifier'] for i in (clip + 12, clip + 13, clip + 14)] == groups
    assert clip + 15 < ask
    # no screen and no tap are added: the only things the person sees before the field are the same as in Duo 6
    assert not any(kind(a) in ('alert', 'choosefrommenu', 'ask') for a in actions[clip:ask])

    # --- every text Duo leaves in the clipboard is remembered RIGHT AFTER it is written — before any screen that waits
    # for the person and before any further AI call: «by hand» check request, Image (both), Claude writes / ChatGPT
    # checks, the tail (RESULT, also when the «Claude did not answer» menu delivered it), and the re-checked result.
    saves = saves_of(actions, last)
    assert len(saves) == 6
    for s in saves:
        txt, cut = actions[s - 1], actions[s - 2]
        assert kind(txt) == 'gettext' and kind(cut) == 'match'
        assert params(cut)['WFMatchTextPattern'] == '(?s)^.{1,200}'
        assert ref(params(txt)['WFTextActionText']) == (params(cut)['UUID'], 'Matches')
        assert ref(params(actions[s])['WFInput']) == (params(txt)['UUID'], 'Text')
        assert params(actions[s])['WFSaveFileOverwrite'] is True and params(actions[s])['WFAskWhereToSave'] is False
    src = lambda s: ref(params(actions[s - 2])['text'])[0]
    copies = [i for i, a in enumerate(actions) if kind(a) == 'setclipboard']
    waits = ('previewdocument', 'choosefrommenu', 'ask', 'alert', 'AskIntent', 'ClaudeAppIntentsExtension', 'askllm')
    for s in saves:
        copy = max(i for i in copies if i < s)
        assert not any(kind(a) in waits and params(a).get('WFControlFlowMode', 0) == 0 for a in actions[copy:s]), \
            'a screen or an AI call between the clipboard write and its save'
    down = next(i for i, a in enumerate(actions) if kind(a) == 'choosefrommenu'
                and params(a).get('WFMenuPrompt') == ui['menu']['claude_down_title'])
    down_end = next(i for i in range(down + 1, len(actions)) if params(actions[i]).get('GroupingIdentifier')
                    == params(actions[down])['GroupingIdentifier'] and params(actions[i])['WFControlFlowMode'] == 2)
    def run_from(c):
        """Actions executed after index c up to the next last-answer save: at the end of a menu case (or of an If
        branch) execution jumps to that group's End."""
        end_of = {}
        for i, a in enumerate(actions):
            if params(a).get('WFControlFlowMode') == 2:
                end_of[params(a)['GroupingIdentifier']] = i
        i, path = c + 1, []
        while i not in saves:
            g, m = params(actions[i]).get('GroupingIdentifier'), params(actions[i]).get('WFControlFlowMode')
            if m == 1:      # the next case / Otherwise: follow the branch already taken (the first one) to the End
                i = end_of[g]
                continue
            path.append(actions[i])
            i += 1
        return path
    for c in copies:
        if down < c < down_end:
            continue      # its three branches are checked through the tail save (the menu itself comes first)
        assert not any(kind(a) in waits and params(a).get('WFControlFlowMode', 0) == 0 for a in run_from(c)), \
            f'clipboard write at {c} is not remembered before a screen or an AI call'
    img1, img2, rev, manual, tail, ratify = saves
    for s in (manual, img1, img2, rev):                # Copy <an action output> → remember the same output
        copy = max(i for i in copies if i < s)
        assert params(actions[copy])['WFInput']['Value']['OutputUUID'] == src(s)
    assert params(actions[manual + 1]).get('WFNotificationActionBody') == ui['notify']['manual_copied']
    # the tail one: after «done / empty» (and the Claude-did-not-answer menu), only when there is a result, before the
    # one result screen and the journal
    got = actions[uid[src(tail)]]
    assert kind(got) == 'getvariable' and params(got)['WFVariable']['Value']['VariableName'] == ui['variables']['result']
    assert kind(actions[tail - 4]) == 'conditional' and params(actions[tail - 4])['WFCondition'] == 100
    assert kind(actions[tail + 1]) == 'conditional' and params(actions[tail + 1])['WFControlFlowMode'] == 2
    look = next(i for i in range(tail, len(actions)) if kind(actions[i]) == 'previewdocument')
    journal = next(i for i in range(tail, len(actions)) if kind(actions[i]) == 'append')
    assert tail < look < journal
    # the re-check: Copy <RESULT> where RESULT was just set from the same text
    set_ratify = next(a for a in reversed(actions[:ratify]) if kind(a) == 'setvariable')
    assert params(set_ratify)['WFInput']['Value']['OutputUUID'] == src(ratify)
    assert kind(actions[ratify + 1]) == 'previewdocument'


@pytest.mark.parametrize('lang', LANGS)
def test_recipes_and_my_rule_reachable(tmp_path, lang):
    ui = ui_of(lang)
    m = ui['menu']
    actions = build(tmp_path, lang)

    # --- (3a) the empty question opens the Recipes; each recipe re-runs Duo with its wording, as from «More…»
    empty = [i for i, a in enumerate(actions) if kind(a) == 'choosefrommenu' and params(a).get('WFMenuPrompt') == m['empty_title']]
    more = [i for i, a in enumerate(actions) if kind(a) == 'choosefrommenu' and params(a).get('WFMenuPrompt') == m['recipes_title']]
    assert len(empty) == 1 and len(more) == 1
    for start in (empty[0], more[0]):
        runs = [a for a in actions[start:start + 4 * len(m['recipes_items']) + 2] if kind(a) == 'runworkflow']
        assert len(runs) == len(m['recipes_texts'])
        assert all(params(r)['WFWorkflowName'] == 'Duo' for r in runs)
    texts = [params(a)['WFTextActionText']['Value']['string'] for a in actions[empty[0]:empty[0] + 22] if kind(a) == 'gettext']
    assert texts == m['recipes_texts']
    # the main menu still comes right after the question, unchanged
    ask = next(i for i, a in enumerate(actions) if kind(a) == 'ask' and params(a)['WFAskActionPrompt'] == ui['ask']['question'])
    main = next(i for i, a in enumerate(actions) if kind(a) == 'choosefrommenu' and params(a).get('WFMenuPrompt') == m['main_title'])
    assert ask < empty[0] < main
    assert [kind(a) for a in actions[ask + 1:ask + 3]] == ['conditional', 'choosefrommenu']

    # --- (3b) My mode without its file: a two-item menu instead of a stop
    assert len(m['my_mode_missing_items']) == 2
    g = next(i for i, a in enumerate(actions) if kind(a) == 'choosefrommenu'
             and params(a).get('WFMenuPrompt') == m['my_mode_missing_title'])
    guard = params(actions[g - 1])
    assert kind(actions[g - 1]) == 'conditional' and guard['WFCondition'] == 101
    assert guard['WFInput']['Variable']['Value']['VariableName'] == 'PolyMyRule'
    seq = [kind(a) for a in actions[g:g + 15]]
    assert seq == ['choosefrommenu', 'choosefrommenu', 'ask', 'match', 'conditional', 'exit', 'conditional',
                   'gettext', 'save', 'setvariable',
                   'choosefrommenu', 'runworkflow', 'exit', 'choosefrommenu', 'conditional']
    # 1. write it now: the field opens with the sample, Done saves the file and the check goes on with that rule
    write = params(actions[g + 2])
    assert write['WFAskActionPrompt'] == ui['ask']['my_rule']
    assert write['WFAskActionDefaultAnswer']['Value']['string'] == ui['ask']['my_rule_sample']
    # a cleared or blank field: stop, nothing saved, nothing spent
    chars = params(actions[g + 3])
    assert chars['WFMatchTextPattern'] == r'\S' and ref(chars['text']) == (write['UUID'], 'Provided Input')
    empty_rule = params(actions[g + 4])
    assert empty_rule['WFCondition'] == 101 and empty_rule['WFInput']['Variable']['Value']['OutputUUID'] == chars['UUID']
    assert params(actions[g + 8])['WFFileDestinationPath'] == 'Poly-my-mode.txt'
    assert params(actions[g + 9])['WFVariableName'] == 'PolyMyRule'
    rule = actions[g + 15]
    assert kind(rule) == 'getvariable' and params(rule)['WFVariable']['Value']['VariableName'] == 'PolyMyRule'
    # nothing is spent before the rule is there: the first AI call of My mode comes after this menu
    first_ai = next(i for i in range(g, len(actions)) if kind(actions[i]) in ('AskIntent', 'ClaudeAppIntentsExtension'))
    assert first_ai > g + 15
    # 2. back: Duo runs again with the same question in the field, then the mode menu
    back = params(actions[g + 11])
    assert back['WFWorkflowName'] == 'Duo'
    ask_uid = params(actions[ask])['UUID']
    assert back['WFInput']['Value']['OutputUUID'] == ask_uid
    # the old dead-end notice is gone from every language
    assert 'my_mode_missing' not in ui['notify']
