"""Duo «Debate until agreement»: ChatGPT takes a side, Claude objects, up to three rounds, a side
that is convinced starts its reply with the marker and the rounds stop; then Claude sums up."""
import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LANGS = sorted(d.name for d in (ROOT / 'locales').iterdir() if d.is_dir())
MARKER = '[[CONCEDE]]'
PROMPTS = ROOT / 'locales' / 'en' / 'prompts'


def ui(lang):
    return json.loads((ROOT / 'locales' / lang / 'ui.json').read_text(encoding='utf-8'))


def build(tmp_path, lang):
    env = dict(os.environ, C1_DIST=str(tmp_path))
    subprocess.run([sys.executable, str(ROOT / 'src' / 'build_shortcut.py'), lang], check=True,
                   cwd=ROOT, env=env, capture_output=True)
    name = ui(lang)['shortcut_names']['main']
    return plistlib.loads((tmp_path / lang / f'{name}.shortcut').read_bytes())['WFWorkflowActions']


def test_prompts_carry_the_marker_and_the_three_sections():
    for name in ('argue-2-object', 'argue-3-reply'):
        text = (PROMPTS / f'{name}.txt').read_text(encoding='utf-8')
        assert MARKER in text and '{ROUND}' in text and '{LOG}' in text and '{QUESTION}' in text
    opening = (PROMPTS / 'argue-1-open.txt').read_text(encoding='utf-8')
    assert MARKER not in opening and '{Q}' in opening
    verdict = (PROMPTS / 'argue-4-verdict.txt').read_text(encoding='utf-8')
    for section in ('Where they agreed', 'Where the dispute remains', 'What you decide'):
        assert section in verdict


@pytest.mark.parametrize('lang', LANGS)
def test_mode_sits_next_to_critique(lang):
    items = ui(lang)['menu']['main_items']
    assert len(items) == 7 and items[1].startswith('🤝') and '3–8✉' in items[1]
    assert '🤝' in ui(lang)['help']


@pytest.mark.parametrize('lang', ['en', 'es', 'pt', 'ru', 'uk'])
def test_three_rounds_that_stop_on_the_marker(tmp_path, lang):
    actions = build(tmp_path, lang)
    log = ui(lang)['variables']['argue_log']
    guards = [i for i, a in enumerate(actions)
              if a['WFWorkflowActionIdentifier'] == 'is.workflow.actions.conditional'
              and a['WFWorkflowActionParameters'].get('WFConditionalActionString') == MARKER]
    # each round: before Claude objects and before ChatGPT answers
    assert len(guards) == 6
    # 15.11 live run: «contains» straight on the log variable stopped the run («Choose values for each parameter»);
    # now Get Variable (the log) → Text → If Text contains the marker
    for i in guards:
        g = actions[i]['WFWorkflowActionParameters']
        get, txt = actions[i - 2]['WFWorkflowActionParameters'], actions[i - 1]['WFWorkflowActionParameters']
        assert g['WFCondition'] == 99
        assert get['WFVariable']['Value']['VariableName'] == log
        assert g['WFInput']['Variable']['Value'] == {'OutputUUID': txt['UUID'], 'Type': 'ActionOutput',
                                                    'OutputName': 'Text'}
    start = next(i for i, a in enumerate(actions)
                 if a['WFWorkflowActionParameters'].get('WFMenuItemTitle') == ui(lang)['menu']['main_items'][1])
    end = next(i for i, a in enumerate(actions)
               if a['WFWorkflowActionParameters'].get('WFMenuItemTitle') == ui(lang)['menu']['main_items'][2])
    branch = [a['WFWorkflowActionIdentifier'] for a in actions[start:end]]
    assert branch.count('com.openai.chat.AskIntent') == 5          # opening + its one retry + three answers
    assert branch.count('com.anthropic.claude.ClaudeAppIntentsExtension') == 4   # three objections + summary


def test_blind_first_in_argue_and_debate(tmp_path):
    """Claude's first reply never sees ChatGPT's text: in the debate until agreement round 1 is its own
    position (no {LOG}), in Debate it answers the question itself; the message counts do not grow."""
    blind_b = (PROMPTS / 'argue-1-open-b.txt').read_text(encoding='utf-8')
    assert '{LOG}' not in blind_b and '{Q}' in blind_b and MARKER not in blind_b
    for name in ('debate-2-compare', 'debate-3-judge-compare'):
        text = (PROMPTS / f'{name}.txt').read_text(encoding='utf-8')
        assert '{DRAFT}' in text and '{OTHER}' in text
    actions = build(tmp_path, 'en')
    dump = repr(actions)
    assert 'side B in a debate between two AIs about a personal decision. Side A is answering' in dump
    assert 'side B in a debate between two AIs about a personal decision. This is round 1 of 3' not in dump
    assert 'side B in a debate between two AIs about a personal decision. This is round 2 of 3' in dump
    assert 'Compare the two answers' in dump and 'independently of each other' in dump
    assert 'Find no more than three of the MOST substantial weaknesses' not in dump
    asks = [a for a in actions if a['WFWorkflowActionIdentifier'].endswith('askllm')
            or 'claude' in a['WFWorkflowActionIdentifier'].lower()]
    assert asks  # the model calls exist; counts are pinned by the mode tests above


@pytest.mark.parametrize('lang', ['en', 'uk', 'ru'])
def test_trio_has_duo_fixes(tmp_path, lang):
    """15.11: Trio gets the brevity line before every Ask Claude and the ChatGPT output cleaning, as Duo does."""
    import os, plistlib, subprocess, sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    subprocess.run([sys.executable, str(root / 'src' / 'build_trio.py'), lang], check=True, capture_output=True,
                   env={**os.environ, 'C1_DIST': str(tmp_path)})
    sys.path.insert(0, str(root / 'src'))
    import build_shortcut as b
    brief = b.Locale(lang)['brief.claude']
    actions = plistlib.loads((tmp_path / lang / 'Trio.shortcut').read_bytes())['WFWorkflowActions']
    claude = [a for a in actions if a['WFWorkflowActionIdentifier'] == b.CLAUDE_INTENT]
    assert claude and all(a['WFWorkflowActionParameters']['message']['Value']['string'].startswith(brief) for a in claude)
    gpt = sum(a['WFWorkflowActionIdentifier'] == 'com.openai.chat.AskIntent' for a in actions)
    cleans = sum('image_group' in str(a['WFWorkflowActionParameters'].get('WFReplaceTextFind', '')) for a in actions)
    assert gpt and cleans == gpt
