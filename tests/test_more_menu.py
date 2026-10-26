"""Final menu «Done / Another mode / More…», Recipes, Critique ⇄, My mode, numbers found by rule."""
import json

import pytest

from test_first_run import LANGS, ROOT, build, kind


def params(a):
    return a['WFWorkflowActionParameters']


@pytest.mark.parametrize('lang', LANGS)
def test_more_menu(tmp_path, lang):
    ui = json.loads((ROOT / 'locales' / lang / 'ui.json').read_text(encoding='utf-8'))
    m = ui['menu']
    assert (len(m['extra_items']), len(m['finale_items']), len(m['finale_more_items'])) == (10, 3, 4)
    assert len(m['recipes_items']) == len(m['recipes_texts']) == 5
    actions = build(tmp_path, lang)

    # the ordinary ending stays «Done / Another mode»; everything else sits behind «More…»
    finale = next(a for a in actions if kind(a) == 'choosefrommenu'
                  and params(a).get('WFMenuItems') == m['finale_items'])
    assert params(finale)['WFMenuItems'][0].startswith('✅')
    more = next(a for a in actions if kind(a) == 'choosefrommenu'
                and params(a).get('WFMenuItems') == m['finale_more_items'])
    assert more

    ids = [a['WFWorkflowActionIdentifier'] for a in actions]
    for needed in ('is.workflow.actions.createnote', 'is.workflow.actions.addnewreminder',
                   'is.workflow.actions.getdevicedetails', 'is.workflow.actions.repeat.each'):
        assert needed in ids
    # the report link carries the device and the mode, never the question or the answers
    url = next(params(a)['WFInput']['Value']['string'] for a in actions if kind(a) == 'openurl'
               and 'run-report.yml' in str(params(a)['WFInput']['Value']['string']))
    assert url.startswith('https://github.com/vadimchernets/poly-duo/issues/new?template=run-report.yml')
    refs = [v for a in actions if kind(a) == 'openurl' and 'run-report' in str(params(a))
            for v in params(a)['WFInput']['Value']['attachmentsByRange'].values()]
    assert len(refs) == 3 and not any(r.get('OutputName') == 'Provided Input' for r in refs)

    # Recipes put a ready wording into the question box by running Duo with it as input; Critique ⇄ asks Claude first and ChatGPT second
    texts = [params(a)['WFTextActionText']['Value']['string'] for a in actions if kind(a) == 'gettext']
    assert all(r in texts for r in m['recipes_texts'])
    assert 'my_mode_missing' not in ui['notify']   # Duo 6.1: a menu, not a dead-end notice (test_duo61)
    rev = next(i for i, a in enumerate(actions) if params(a).get('WFNotificationActionBody')
               == ui['notify']['reverse_start'])
    order = [kind(a) for a in actions[rev:rev + 14] if kind(a) in ('AskIntent', 'ClaudeAppIntentsExtension')]
    assert order[:2] == ['ClaudeAppIntentsExtension', 'AskIntent']  # then ChatGPT's one retry, then the summary

    # numbers that stand in only one of the two independent answers: Match Text (a token STRING) → Repeat with Each →
    # whole-number Match Text in the OTHER answer (details: test_duo_review_fixes), in both directions, and only when both answers exist
    nums = [i for i, a in enumerate(actions) if kind(a) == 'match' and 'd+' in params(a)['WFMatchTextPattern']]
    assert len(nums) == 4  # Critique and My mode, two directions each
    for num in nums:
        assert params(actions[num])['text']['WFSerializationType'] == 'WFTextTokenString'
        assert kind(actions[num + 1]) == 'each' and kind(actions[num + 2]) == 'getvariable'
        assert actions[num + 3]['WFWorkflowActionIdentifier'].endswith('text.replace')
    other = [params(actions[n + 4])['WFVariable']['Value']['VariableName'] for n in nums[:2]]
    assert other == ['PolyClaudeOwn', 'PolyChatGPTAnswer']

    # Save to Notes: the text goes to the Create Note BODY; Match Text for Reminders takes a token string too
    note = next(a for a in actions if kind(a) == 'createnote')
    assert params(note)['WFCreateNoteBody']['WFSerializationType'] == 'WFTextTokenString'
    assert 'WFCreateNoteInput' not in params(note)
