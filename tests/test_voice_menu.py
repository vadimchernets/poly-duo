"""D-128 (18.11, the owner's run with Siri and VoiceOver): the mode menu and «What next?» are said by voice.

VoiceOver read the emoji's name and the whole explanation before each item, Siri could not pick «Survey» from the
long labels and looped, and every progress notification was read aloud, several per run. Now: each item is one or
two plain words, what the modes are for is in the menu title (read once), and Duo sends one notification, at the end.
"""
import json
import re

import pytest

from test_first_run import LANGS, ROOT, build, kind

# pictographs, dingbats, arrows, variation selectors, the ✉ badge — anything VoiceOver reads by its name
EMOJI = re.compile('[\U0001F000-\U0001FAFF☀-➿⬀-⯿←-⇿️‍]')

# the notifications Duo may still send: the end of the run, an answer that did not come, and answers to something
# the person chose (help, a saved switch, a fallback); none of them reports a step of the run
ALLOWED = ('tail_done', 'tail_empty', 'tail_empty_claude', 'gpt_down', 'empty_question', 'no_key_file',
           'manual_copied', 'help', 'pref_mode', 'pref_quick', 'pref_reset')


def ui_of(lang):
    return json.loads((ROOT / 'locales' / lang / 'ui.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('lang', LANGS)
def test_menu_items_are_short_plain_words(lang):
    m = ui_of(lang)['menu']
    for key in ('main_items', 'finale_items'):
        for item in m[key]:
            assert not EMOJI.search(item), (key, item)
            assert len(item.split()) <= 2 and len(item) <= 16, (key, item)
            assert '—' not in item and '·' not in item and '…' not in item, (key, item)
        assert len(set(m[key])) == len(m[key])
    # the title, read once, has no emoji either and names every mode it explains
    assert not EMOJI.search(m['main_title'])
    assert all(item in m['main_title'] for item in m['main_items'][:6])
    assert not EMOJI.search(m['finale_title'])


@pytest.mark.parametrize('lang', LANGS)
def test_one_notification_per_run(tmp_path, lang):
    ui = ui_of(lang)
    n = ui['notify']
    actions = build(tmp_path, lang)
    allowed = {n[k] for k in ALLOWED}
    bodies = [a['WFWorkflowActionParameters'].get('WFNotificationActionBody') for a in actions
              if kind(a) == 'notification']
    assert bodies and all(b in allowed for b in bodies), [b for b in bodies if b not in allowed][:3]
    assert sum(b == n['tail_done'] for b in bodies) == 1
    # «Duo: Answer ready» — the title is Duo, the body a few words
    done = next(a for a in actions if kind(a) == 'notification'
                and a['WFWorkflowActionParameters'].get('WFNotificationActionBody') == n['tail_done'])
    assert done['WFWorkflowActionParameters']['WFNotificationActionTitle'] == 'Duo'
    assert len(n['tail_done']) <= 50 and not EMOJI.search(n['tail_done'])
