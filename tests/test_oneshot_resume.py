"""One-tap start (clipboard prefill), the ChatGPT retry + draft / resume, and the long-text guard for Claude."""
import json
import plistlib
from pathlib import Path

import pytest

from test_first_run import LANGS, ROOT, assert_blank_guard, assert_duo_blank_guard, build, kind, guard_var


def params(a):
    return a['WFWorkflowActionParameters']


def notes(actions):
    return [params(a).get('WFNotificationActionBody') for a in actions if kind(a) == 'notification']


@pytest.mark.parametrize('lang', LANGS)
def test_oneshot_resume_long(tmp_path, lang):
    ui = json.loads((ROOT / 'locales' / lang / 'ui.json').read_text(encoding='utf-8'))
    actions = build(tmp_path, lang)
    kinds = [kind(a) for a in actions]

    # --- U-16: the question field is pre-filled from the Share input, else from the clipboard (read ONLY when there
    # is no Shortcut Input), and the field itself is the single screen
    ask = next(i for i, a in enumerate(actions) if kind(a) == 'ask'
               and params(a)['WFAskActionPrompt'] == ui['ask']['question'])
    # (the first such If is the Duo 6.4 resume check, which only runs without input; the start's is the last one)
    shin = max(i for i, a in enumerate(actions[:ask]) if kind(a) == 'conditional'
               and params(a).get('WFInput', {}).get('Variable', {}).get('Value') == {'Type': 'ExtensionInput'})
    group = params(actions[shin])['GroupingIdentifier']
    same = [i for i, a in enumerate(actions) if params(a).get('GroupingIdentifier') == group]
    assert len(same) == 3  # If / Otherwise / End If
    clip = next(i for i, a in enumerate(actions) if kind(a) == 'getclipboard')
    assert same[1] < clip < same[2]               # the clipboard is read only in «Otherwise»
    assert not any(kind(a) == 'getclipboard' for a in actions[:same[1]])
    # a picture from Share: text first (a text, URL, article, text PDF); a file-name-only result counts as no text;
    # «Get Images from Input» + OCR only while the question text is still empty
    dtext = next(i for i in range(shin, ask) if actions[i]['WFWorkflowActionIdentifier'].endswith('detect.text'))
    fname = actions[dtext + 2]
    assert kind(fname) == 'match' and 'jpe?g' in params(fname)['WFMatchTextPattern']
    img = next(i for i in range(shin, ask) if actions[i]['WFWorkflowActionIdentifier'].endswith('detect.images'))
    ocr = next(i for i in range(shin, ask) if kind(actions[i]) == 'extracttextfromimage')
    assert dtext < img < ocr
    guard = params(actions[img - 1])
    assert guard['WFCondition'] == 101 and guard_var(actions, actions[img - 1]) == 'PolyStartText'
    # the clipboard counts only when it holds three words
    words = actions[clip + 1]
    assert params(words)['WFMatchTextPattern'] == r'\S+\s+\S+\s+\S+'
    assert params(actions[clip + 2])['WFCondition'] == 100
    assert params(actions[clip + 2])['WFInput']['Variable']['Value']['OutputUUID'] == params(words)['UUID']
    assert params(actions[clip + 3])['WFInput']['Value']['OutputUUID'] == params(actions[clip])['UUID']
    # Match Text takes a token STRING (as build_trio.act_match), never a bare attachment
    for a in actions:
        if kind(a) == 'match':
            assert params(a)['text']['WFSerializationType'] == 'WFTextTokenString'
    default = params(actions[ask])['WFAskActionDefaultAnswer']['Value']
    assert list(default['attachmentsByRange'].values())[0]['OutputUUID'] == params(actions[ask - 1])['UUID']
    main = next(i for i, a in enumerate(actions) if kind(a) == 'choosefrommenu'
                and params(a).get('WFMenuPrompt') == ui['menu']['main_title'])
    assert assert_duo_blank_guard(actions, ui) == main - 1   # then the question goes to PolyQuestion (Duo 6.4)

    # --- one retry after 3 s; Duo 6.4: the resume is back, through ONE draft «Save File» (test_duo64)
    n = ui['notify']
    assert sum(params(a).get('WFNotificationActionBody') == n['resume'] for a in actions) == 1
    gpt_calls = [i for i, a in enumerate(actions) if kind(a) == 'AskIntent'
                 and a['WFWorkflowActionIdentifier'] == 'com.openai.chat.AskIntent']
    delay = next(i for i, a in enumerate(actions) if kind(a) == 'delay')
    assert params(actions[delay])['WFDelayTime'] == 3
    first, second = [i for i in gpt_calls if i < delay][-1], [i for i in gpt_calls if i > delay][0]
    assert first < delay < second
    assert kind(actions[delay - 1]) == 'conditional' and params(actions[delay - 1])['WFCondition'] == 101
    assert sum(str(params(a).get('WFFileDestinationPath')).startswith('Duo-draft-') for a in actions) == 1
    same = [a for a in actions if kind(a) == 'conditional' and params(a).get('WFCondition') == 4]
    assert len(same) == 1  # Duo's own answer (test_duo61)

    # --- U-08: one notification (no alert) for a long request, one retry with the cut text
    long_note = next(i for i, a in enumerate(actions) if params(a).get('WFNotificationActionBody') == n['long_text'])
    count = actions[long_note - 2]
    assert kind(count) == 'count' and params(actions[long_note - 1])['WFNumberValue'] == 6000
    retries = [i for i, a in enumerate(actions) if params(a).get('WFNotificationActionBody') == n['claude_retry']]
    # per block: step 2 (Claude's own answer) is re-asked as it was; step 3 is re-asked with the request cut
    cut = [i for i in retries if kind(actions[i + 1]) == 'match']
    assert len(retries) == 4 and len(cut) == 2
    for retry in cut:
        assert params(actions[retry + 1])['WFMatchTextPattern'].endswith('{1,6000}')
        assert kind(actions[retry + 2]) == 'ClaudeAppIntentsExtension'
    alerts = [a for a in actions if kind(a) == 'alert']
    assert len(alerts) == 1  # still only the first-run warning
