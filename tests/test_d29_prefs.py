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
    conds = [params(a).get('WFConditionalActionString') for a in actions[:ask] if kind(a) == 'conditional']
    assert 'MODE=critique' in conds and 'QUICK=1' in conds


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
    assert any(kind(a) == 'replace' and params(a)['WFReplaceTextFind'] == MARK for a in actions)


@pytest.mark.parametrize('lang', LANGS)
def test_hint_moved_out_of_start_notifications(tmp_path, lang):
    ui = ui_of(lang)
    n = ui['notify']
    for k, v in n.items():
        if k != 'gpt_down':
            assert 'logged out' not in v, k
    assert 'logged out' in n['gpt_down'] and 'logged out' in ui['alert']['first_run_body']
    assert len(ui['menu']['finale_more_items']) == 7
    for k in ('pref_mode', 'pref_quick', 'pref_reset'):
        assert n[k].strip()
