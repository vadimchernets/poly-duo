"""Findings of the second-family review of the Duo shortcut (26.10): each test checks the behaviour, not just that an
action exists."""
import json
import plistlib

import pytest

from test_first_run import LANGS, ROOT, build, kind

VERSION = json.loads((ROOT / 'releases' / 'version.json').read_text(encoding='utf-8'))


def params(a):
    return a['WFWorkflowActionParameters']


def enclosing(actions, index):
    """The If / Repeat groups that are open at actions[index], outermost first (their opening actions)."""
    stack = []
    for a in actions[:index]:
        p = params(a)
        mode = p.get('WFControlFlowMode')
        if 'GroupingIdentifier' not in p or kind(a) not in ('conditional', 'each'):
            continue
        if mode == 0:
            stack.append(a)
        elif mode == 2:
            stack.pop()
    return stack


def var_name(cond):
    node = params(cond)['WFInput']['Variable']['Value']
    return node.get('VariableName') or node.get('OutputName')


def ui_of(lang):
    return json.loads((ROOT / 'locales' / lang / 'ui.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('lang', LANGS)
def test_critique_blind_scheme_and_claude_down_is_reachable(tmp_path, lang):
    ui = ui_of(lang)
    actions = build(tmp_path, lang)
    n = ui['notify']
    start = next(i for i, a in enumerate(actions) if params(a).get('WFNotificationActionBody') == n['critique_start'])
    s2 = next(i for i, a in enumerate(actions) if params(a).get('WFNotificationActionBody') == n['critique_blind'])
    s3 = next(i for i, a in enumerate(actions) if params(a).get('WFNotificationActionBody') == n['critique_step3'])
    assert start < s2 < s3
    # exactly three messages in the happy path: ChatGPT, Claude (blind), Claude (compare)
    asks = [(i, kind(actions[i])) for i in range(start, s3 + 12) if kind(actions[i]) in ('AskIntent', 'ClaudeAppIntentsExtension')]
    # step 1: ChatGPT (+ its own retry), step 2: Claude (+ retry), step 3: Claude (+ cut retry)
    assert [k for _, k in asks] == ['AskIntent', 'AskIntent', 'ClaudeAppIntentsExtension',
                                    'ClaudeAppIntentsExtension', 'ClaudeAppIntentsExtension',
                                    'ClaudeAppIntentsExtension'][:len(asks)]
    gpt1 = asks[0][0]
    blind = next(i for i, k in asks if k == 'ClaudeAppIntentsExtension')
    by_uid = {params(a).get('UUID'): a for a in actions}
    # the blind step sends the SAME wrapped question that ChatGPT got, and that text has no ChatGPT answer in it
    msg_blind = list(params(actions[blind])['message']['Value']['attachmentsByRange'].values())[0]['OutputUUID']
    msg_gpt = list(params(actions[gpt1])['prompt']['Value']['attachmentsByRange'].values())[0]['OutputUUID']
    assert msg_blind == msg_gpt
    wrap = by_uid[msg_blind]
    question = next(a for a in actions if kind(a) == 'ask')['WFWorkflowActionParameters']['UUID']
    assert {v['OutputUUID'] for v in params(wrap)['WFTextActionText']['Value']['attachmentsByRange'].values()} == {question}
    # step 3 sees both answers and the numbers found by rule
    compare = next(i for i in range(s3, len(actions)) if kind(actions[i]) == 'ClaudeAppIntentsExtension')
    prompt_uid = list(params(actions[compare])['message']['Value']['attachmentsByRange'].values())[0]['OutputUUID']
    prompt = params(by_uid[prompt_uid])['WFTextActionText']['Value']
    refs = [v['OutputUUID'] for v in prompt['attachmentsByRange'].values()]
    assert len(refs) == 4 and question in refs  # question, ChatGPT's answer, Claude's own answer, numbers
    # RESULT is set only inside «If PolyClaudeAnswer has any value», never from a text with a fixed header
    result_name = ui['variables']['result']
    setters = [i for i in range(s3, len(actions)) if kind(actions[i]) == 'setvariable'
               and params(actions[i])['WFVariableName'] == result_name]
    first = setters[0]
    conds = enclosing(actions, first)
    assert var_name(conds[-1]) == 'PolyClaudeAnswer' and params(conds[-1])['WFCondition'] == 100
    src = params(actions[first])['WFInput']['Value']
    assert by_uid[src['OutputUUID']]['WFWorkflowActionIdentifier'].endswith('getvariable')
    # the shared tail tests RESULT, so with no step-3 answer RESULT stays empty and the menu is offered
    tail_empty = next(i for i, a in enumerate(actions) if params(a).get('WFNotificationActionBody') == ui['notify']['tail_empty'])
    assert first < tail_empty
    assert not any(kind(a) == 'ClaudeAppIntentsExtension' and 'summary' in json.dumps(params(a)) for a in actions[s3:compare + 1])


@pytest.mark.parametrize('lang', LANGS)
def test_fallback_has_one_quick_look_and_no_empty_window(tmp_path, lang):
    ui = ui_of(lang)
    actions = build(tmp_path, lang)
    note = next(i for i, a in enumerate(actions) if params(a).get('WFNotificationActionBody') == ui['notify']['tail_empty'])
    menu = next(i for i, a in enumerate(actions) if kind(a) == 'choosefrommenu'
                and params(a).get('WFMenuItems') == ui['menu']['claude_down_items'])
    close = next(i for i in range(menu, len(actions)) if kind(actions[i]) == 'choosefrommenu'
                 and params(actions[i]).get('WFControlFlowMode') == 2 and params(actions[i])['GroupingIdentifier']
                 == params(actions[menu])['GroupingIdentifier'])
    # the fallback only fills RESULT / the clipboard; no Quick Look inside it
    assert not any(kind(a) == 'previewdocument' for a in actions[note:close + 1])
    # the one Quick Look after it is guarded by «RESULT has any value»
    look = next(i for i in range(close, len(actions)) if kind(actions[i]) == 'previewdocument')
    guard = enclosing(actions, look)[-1]
    assert var_name(guard) == ui['variables']['result'] and params(guard)['WFCondition'] == 100
    # the free-key chain of the fallback makes no Gemini web-search call
    chunk = json.dumps(actions[menu:close])
    assert 'google_search' not in chunk and 'googleSearch' not in chunk


@pytest.mark.parametrize('lang', LANGS)
def test_debate_round_survives_empty_chatgpt_reply(tmp_path, lang):
    actions = build(tmp_path, lang)
    saves = [i for i, a in enumerate(actions) if kind(a) == 'setvariable' and params(a)['WFVariableName'] == 'PolyArgueReply']
    assert len(saves) == 3
    for i in saves:
        assert var_name(actions[i + 1]) == 'PolyArgueReply' and params(actions[i + 1])['WFCondition'] == 100
        log_set = next(j for j in range(i, len(actions)) if kind(actions[j]) == 'setvariable'
                       and params(actions[j])['WFVariableName'] == ui_of(lang)['variables']['argue_log'])
        assert actions[i + 1] in enclosing(actions, log_set)


def test_ai_build_uses_existing_version_key_and_own_draft_names(tmp_path):
    assert 'duo_ai' not in VERSION  # the test documents the interim rule: until the key exists, `duo` is used
    build(tmp_path, 'en')
    ai = plistlib.loads((tmp_path / 'en' / 'ai' / 'Poly.shortcut').read_bytes())['WFWorkflowActions']
    keys = [params(a)['WFDictionaryKey'] for a in ai if kind(a) == 'getvalueforkey']
    assert keys[-2:] == ['duo', 'duo_en']  # the version check's two lookups (the key chain's come earlier)
    needles = [params(a)['WFConditionalActionString'] for a in ai if kind(a) == 'conditional' and params(a).get('WFCondition') == 99
               and isinstance(params(a).get('WFConditionalActionString'), str)]
    assert '"duo":' in needles
    report = next(params(a)['WFInput']['Value']['string'] for a in ai if kind(a) == 'openurl'
                  and 'run-report' in str(params(a)))
    assert f"version=duo%20{VERSION['duo']}" in report
    saves = {params(a)['WFFileDestinationPath'] for a in ai if kind(a) == 'save'}
    assert any(s.startswith('Duo-draft-en-ai-') for s in saves) and not any(s.startswith('Duo-draft-en-std-') for s in saves)


def token_text(node):
    return node['Value']['string'] if isinstance(node, dict) else node


@pytest.mark.parametrize('lang', LANGS)
def test_numbers_are_compared_as_whole_numbers_once(tmp_path, lang):
    actions = build(tmp_path, lang)
    # no «does not contain» (999) on a Repeat Item any more: that was a substring test («7» is inside «17»)
    assert not any(kind(a) == 'conditional' and params(a).get('WFCondition') == 999 for a in actions)
    pats = [i for i, a in enumerate(actions) if kind(a) == 'match' and isinstance(params(a)['WFMatchTextPattern'], dict)]
    assert len(pats) == 8  # two blocks (Critique, My mode) x two directions x (other answer, the list so far)
    for i in pats:
        pat = token_text(params(actions[i])['WFMatchTextPattern'])
        assert pat.startswith('(?<!\\d)') and '(?!\\d)' in pat
        ref = list(params(actions[i])['WFMatchTextPattern']['Value']['attachmentsByRange'].values())[0]['OutputUUID']
        esc = next(a for a in actions if params(a).get('UUID') == ref)
        # the dot of a number is escaped before it goes into the pattern
        assert esc['WFWorkflowActionIdentifier'].endswith('text.replace') and params(esc)['WFReplaceTextFind'] == '.'
        assert params(esc)['WFReplaceTextReplace'] == '\\.'
        # the number is added only when that match has no value (condition 101 on the match output)
        cond = actions[i + 1]
        assert kind(cond) == 'conditional' and params(cond)['WFCondition'] == 101
        assert params(cond)['WFInput']['Variable']['Value']['OutputUUID'] == params(actions[i])['UUID']


@pytest.mark.parametrize('lang', LANGS)
def test_resume_compares_text_not_file_objects(tmp_path, lang):
    actions = build(tmp_path, lang)
    same = [a for a in actions if kind(a) == 'conditional' and params(a).get('WFCondition') == 4
            and 'WFConditionalActionString' in params(a)]
    assert len(same) == 4  # + Duo 6.1: the clipboard's start against Duo's last answer (test_duo61)
    by_uid = {params(a).get('UUID'): a for a in actions}
    for c in same:
        node = params(c)['WFInput']['Variable']['Value']
        assert node['OutputName'] == 'Text'
        src = by_uid[node['OutputUUID']]
        assert kind(src) == 'gettext'   # the text made from the file, as for the own answer


@pytest.mark.parametrize('lang', LANGS)
def test_saving_a_draft_empties_the_question_file_first(tmp_path, lang):
    actions = build(tmp_path, lang)
    by_uid = {params(a).get('UUID'): a for a in actions}
    saves = [i for i, a in enumerate(actions) if kind(a) == 'save']
    base = f'Duo-draft-{lang}-std'

    def is_empty_save(i):
        src = list(params(actions[i])['WFInput']['Value']['attachmentsByRange'].values())[0]['OutputUUID']
        return params(by_uid[src])['WFTextActionText']['Value']['string'] == ''

    for first_name, then_name in ((f'{base}-question.txt', f'{base}-own.txt'),
                                  (f'{base}-argue-question.txt', f'{base}-argue-log.txt')):
        pairs = [i for i in saves if params(actions[i])['WFFileDestinationPath'] == then_name]
        assert pairs
        hit = False
        for i in pairs:
            prev = [j for j in saves if j < i][-2:]
            hit = hit or any(params(actions[j])['WFFileDestinationPath'] == first_name and is_empty_save(j) for j in prev)
        assert hit, first_name


@pytest.mark.parametrize('lang', LANGS)
def test_critique_reverse_has_its_own_attribution(tmp_path, lang):
    ui = ui_of(lang)
    assert ui['output']['critique_reverse'] != ui['output']['critique']
    assert 'ChatGPT' in ui['output']['critique_reverse'] and 'Claude' not in ui['output']['critique_reverse']
    assert 'Claude' in ui['journal']['critique_reverse'] and 'ChatGPT' not in ui['journal']['critique_reverse']
    actions = build(tmp_path, lang)
    texts = [token_text(params(a).get('WFTextActionText')) for a in actions if kind(a) == 'gettext']
    assert any(ui['output']['critique_reverse'].split('\n')[-2] in t for t in texts)
    assert any(ui['journal']['critique_reverse'].split('{X}')[0] in t for t in texts)
