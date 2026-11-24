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
ALLOWED_SPEAK = ('ready',)   # the Setup's own notification (first run only): it asks for the permission there
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
    assert all(item in m['main_title'] for item in m['main_items'][:8])
    assert not EMOJI.search(m['finale_title'])


@pytest.mark.parametrize('lang', LANGS)
def test_one_notification_per_run(tmp_path, lang):
    ui = ui_of(lang)
    n = ui['notify']
    actions = build(tmp_path, lang)
    allowed = {n[k] for k in ALLOWED} | {ui['speak'][k] for k in ALLOWED_SPEAK}
    bodies = [a['WFWorkflowActionParameters'].get('WFNotificationActionBody') for a in actions
              if kind(a) == 'notification']
    assert bodies and all(b in allowed for b in bodies), [b for b in bodies if b not in allowed][:3]
    assert sum(b == n['tail_done'] for b in bodies) == 1
    # «Duo: Answer ready» — the title is Duo, the body a few words
    done = next(a for a in actions if kind(a) == 'notification'
                and a['WFWorkflowActionParameters'].get('WFNotificationActionBody') == n['tail_done'])
    assert done['WFWorkflowActionParameters']['WFNotificationActionTitle'] == 'Duo'
    assert len(n['tail_done']) <= 50 and not EMOJI.search(n['tail_done'])


@pytest.mark.parametrize('lang', LANGS)
def test_first_run_setup_asks_everything_at_once(tmp_path, lang):
    """D-128 (18.11, the owner's Siri run): permission windows come up silently on a locked phone, at different steps.
    The first run (no Duo-setup.txt) is a Setup before the question: say what is coming → ChatGPT → Claude → the one
    notification → the update check on the web → the stamp file, named for the built version → say «ready»."""
    ui = ui_of(lang)
    actions = build(tmp_path, lang)
    ask = next(i for i, a in enumerate(actions) if kind(a) == 'ask')
    head = actions[:ask]
    kinds = [kind(a) for a in head]
    speaks = [i for i, k in enumerate(kinds) if k == 'speaktext']
    assert len(speaks) == 2
    said = [head[i]['WFWorkflowActionParameters']['WFText']['Value']['string'] for i in speaks]
    assert said == [ui['speak']['first_run'], ui['speak']['ready']]
    first, ready = speaks
    order = [k for k in kinds[first:ready] if k in ('AskIntent', 'ClaudeAppIntentsExtension', 'save', 'downloadurl',
                                                    'notification')]
    # ChatGPT, Claude, the notification, both update addresses on the web, then the one file write (the stamp, last: a
    # Setup cut short runs again next time)
    # (Duo 6.11, the council of 24.11: between ChatGPT/Claude and the notification the REAL sets are warmed — the
    # query call (Claude), the 5 engines and the reader; ChatGPT and Claude again; the 2 claim engines and the reader;
    # ChatGPT and Claude with what the search brought)
    assert order[:2] == ['AskIntent', 'ClaudeAppIntentsExtension']
    note = order.index('notification')
    warm = order[2:note]
    assert warm.count('downloadurl') == 5 + 1 + 2 + 1
    assert warm.count('AskIntent') == 2 and warm.count('ClaudeAppIntentsExtension') == 3
    assert order[-1] == 'save'
    # GitHub, the site as its fallback, and the site once more in the Setup; plus the warm-up downloads
    assert order.count('downloadurl') == 3 + 9
    # every action that can ask for a permission on the main path sits in the Setup: no save, append or copy elsewhere
    # before the finale menu, and the Setup is gated by the file
    assert any(a['WFWorkflowActionParameters'].get('WFGetFilePath') == f"Duo-setup-{json.loads((ROOT / 'releases' / 'version.json').read_text())['duo']}.txt" for a in head[:first])
    assert sum(k == 'save' for k in kinds) == 1   # before the question: only the Setup's stamp
    for k in ('first_run', 'ready'):
        assert not EMOJI.search(ui['speak'][k])


@pytest.mark.parametrize('lang', LANGS)
def test_main_path_copies_nothing(tmp_path, lang):
    """D-128: «Copy to Clipboard» only where the person picks it (Open Poly, by-hand check, Images)."""
    actions = build(tmp_path, lang)
    ui = ui_of(lang)
    done = next(i for i, a in enumerate(actions) if kind(a) == 'notification'
                and a['WFWorkflowActionParameters'].get('WFNotificationActionBody') == ui['notify']['tail_done'])
    finale = next(i for i, a in enumerate(actions) if kind(a) == 'choosefrommenu'
                  and a['WFWorkflowActionParameters'].get('WFMenuPrompt') == ui['menu']['finale_title'])
    # the copies left are the person's own picks: the by-hand check (Claude did not answer), both Images, Open Poly ×2
    assert sum(kind(a) == 'setclipboard' for a in actions) == 5
    assert not any(kind(a) == 'append' for a in actions)
    assert sum(kind(a) == 'setclipboard' for a in actions[done:finale]) == 0
