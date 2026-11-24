"""The owner's choice of 24.11: «with search / without search», asked once in the Setup and changed in «More…».

Without search every step behind PolyNet is skipped exactly as offline (the airplane-mode path); the choice lives in
Duo-prefs.txt as the line SEARCH=0 and follows the D-29 rule (a flag set outside, only cleared inside the file's If).
"""
import json

import pytest

from test_first_run import LANGS, ROOT, build, kind


def params(a):
    return a['WFWorkflowActionParameters']


def ui_of(lang):
    return json.loads((ROOT / 'locales' / lang / 'ui.json').read_text(encoding='utf-8'))


def var_of(a):
    v = params(a).get('WFVariable', {}).get('Value', {})
    return v.get('VariableName')


@pytest.mark.parametrize('lang', LANGS)
def test_texts_have_both_numbers_and_two_buttons(lang):
    s = ui_of(lang)['setup']
    assert '{WEB}' in s['search_text'] and '{LOCAL}' in s['search_text']
    assert 'ChatGPT' in s['search_text'] and 'Claude' in s['search_text']
    assert len(s['search_items']) == 2
    assert '{WEB}' in s['search_items'][0] and '{LOCAL}' in s['search_items'][1]
    assert ui_of(lang)['notify']['pref_search'].strip()


@pytest.mark.parametrize('lang', ['en', 'ru'])
def test_the_setup_asks_and_keeps_the_choice(tmp_path, lang):
    import sys
    sys.path.insert(0, str(ROOT / 'src'))
    import build_shortcut as B
    actions = build(tmp_path, lang)
    ask = next(i for i, a in enumerate(actions) if kind(a) == 'ask')
    head = actions[:ask]
    menus = [a for a in head if kind(a) == 'choosefrommenu' and params(a).get('WFMenuPrompt')]
    choice = menus[0]
    on, off = (x.replace('{WEB}', str(B.SEARCH_WINDOWS)).replace('{LOCAL}', str(B.LOCAL_WINDOWS))
               for x in ui_of(lang)['setup']['search_items'])
    assert params(choice)['WFMenuItems'] == [on, off]
    assert str(B.SEARCH_WINDOWS) in params(choice)['WFMenuPrompt'] and '{' not in params(choice)['WFMenuPrompt']
    # the prefs file is read before the Setup, and the Setup writes SEARCH=0 when search is off
    read = next(i for i, a in enumerate(head) if params(a).get('WFGetFilePath') == 'Duo-prefs.txt')
    save = next(i for i, a in enumerate(head) if params(a).get('WFFileDestinationPath') == 'Duo-prefs.txt')
    assert read < head.index(choice) < save
    texts = [params(a).get('WFTextActionText', {}) for a in head[head.index(choice):save]]
    assert any('SEARCH=0' in str(t) for t in texts)
    pats = [params(a).get('WFMatchTextPattern') for a in head if kind(a) == 'match']
    assert r'(?m)^SEARCH=0$' in pats


@pytest.mark.parametrize('lang', ['en', 'ru'])
def test_every_search_guard_follows_the_choice(tmp_path, lang):
    """Each place that sets PolyNet (search, link check, divergence, research) clears it again when PolySearchOn has no
    value; PolyNet itself is never set inside a condition."""
    actions = build(tmp_path, lang)
    sets = [i for i, a in enumerate(actions) if kind(a) == 'setvariable' and params(a).get('WFVariableName') == 'PolyNet']
    assert sets
    checked = 0
    for i in sets:
        src = params(actions[i - 1])
        if kind(actions[i - 1]) == 'gettext':   # «1», set outside every condition
            window = actions[i:i + 40]
            assert any(kind(a) == 'getvariable' and var_of(a) == 'PolySearchOn' for a in window)
            checked += 1
        else:
            assert kind(actions[i - 1]) == 'nothing', src
    assert checked >= 4


@pytest.mark.parametrize('lang', ['en', 'ru'])
def test_more_menu_changes_the_choice(tmp_path, lang):
    ui = ui_of(lang)
    actions = build(tmp_path, lang)
    item = ui['menu']['finale_more_items'][9]
    start = next(i for i, a in enumerate(actions) if kind(a) == 'choosefrommenu' and params(a).get('WFMenuItemTitle') == item)
    sub = actions[start + 1]
    assert kind(sub) == 'choosefrommenu' and len(params(sub)['WFMenuItems']) == 2
    names = [params(a)['WFVariableName'] for a in actions[start:start + 20] if kind(a) == 'setvariable']
    assert 'PolySearchOn' in names and 'PolyPrefsChanged' in names and 'PolyNoteSearch' in names
