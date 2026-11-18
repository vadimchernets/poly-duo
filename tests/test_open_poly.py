"""D-185 «Open in Poly» (menu item only, URL fixed) and D-209 «Open source on GitHub» in help, all 12 languages."""
import json

import pytest

from test_first_run import LANGS, ROOT, build, kind


def params(a):
    return a['WFWorkflowActionParameters']


def url_of(a):
    return params(a)['WFInput']['Value']['string']


def poly_urls(actions, src):
    want = f'https://polyhelper.ai/get/?to=answer&from={src}'
    return [a for a in actions if kind(a) == 'openurl' and url_of(a) == want]


def _menu_case_then_url(actions, title, src):
    i = next(i for i, a in enumerate(actions) if kind(a) == 'choosefrommenu'
             and params(a).get('WFControlFlowMode') == 1 and params(a).get('WFMenuItemTitle') == title)
    nxt = actions[i + 1]
    assert kind(nxt) == 'openurl' and url_of(nxt) == f'https://polyhelper.ai/get/?to=answer&from={src}'
    assert 'attachmentsByRange' not in params(nxt)['WFInput']['Value'] or not params(nxt)['WFInput']['Value']['attachmentsByRange']


@pytest.mark.parametrize('lang', LANGS)
def test_duo_open_poly(tmp_path, lang):
    ui = json.loads((ROOT / 'locales' / lang / 'ui.json').read_text(encoding='utf-8'))
    m = ui['menu']
    assert 'Poly' in m['open_poly']
    # D-128: in «What next?» the item is two short words without the emoji; «More actions» keeps the long label
    assert 'Poly' in m['finale_items'][2] and m['open_poly'] in m['finale_more_items']
    assert 'https://github.com/vadimchernets/poly-duo' in ui['help']
    actions = build(tmp_path, lang)
    assert len(poly_urls(actions, 'duo')) == 2
    _menu_case_then_url(actions, m['finale_items'][2], 'duo')
    _menu_case_then_url(actions, m['open_poly'], 'duo')
    assert not any(kind(a) == 'urlencode' and 'polyhelper' in str(a) for a in actions)
    # a menu item, not an automatic last step: the last action is not the Poly URL
    assert not (kind(actions[-1]) == 'openurl' and 'polyhelper' in url_of(actions[-1]))
    # the answer is in the clipboard before the menu opens
    menu = next(i for i, a in enumerate(actions) if kind(a) == 'choosefrommenu'
                and params(a).get('WFMenuItems') == m['finale_items'])
    assert any(kind(a) == 'setclipboard' for a in actions[:menu])


@pytest.mark.parametrize('lang', LANGS)
def test_trio_open_poly(tmp_path, lang):
    trio = json.loads((ROOT / 'locales' / lang / 'trio.json').read_text(encoding='utf-8'))
    assert 'Poly' in trio['menu.open_poly']
    from test_trio_search import build as build_trio
    actions = build_trio(tmp_path, lang)
    assert len(poly_urls(actions, 'trio')) == 1
    _menu_case_then_url(actions, trio['menu.open_poly'], 'trio')
    assert not (kind(actions[-1]) == 'openurl' and 'polyhelper' in url_of(actions[-1]))
    ui = json.loads((ROOT / 'locales' / lang / 'ui.json').read_text(encoding='utf-8'))
    menu = next(i for i, a in enumerate(actions) if kind(a) == 'choosefrommenu'
                and params(a).get('WFMenuItems') == [ui['menu']['finale_items'][0], trio['menu.open_poly']])
    assert any(kind(a) == 'setclipboard' for a in actions[:menu])
