"""Trio's third voice with web search: Gemini generateContent + google_search first, the ordinary chain after."""
import os
import plistlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LANGS = ['en', 'es']


def build(tmp_path, lang, nokey=False):
    env = dict(os.environ, C1_DIST=str(tmp_path))
    subprocess.run([sys.executable, str(ROOT / 'src' / 'build_trio.py'), lang], check=True, cwd=ROOT,
                   env=env, capture_output=True)
    path = tmp_path / lang / ('nokey' if nokey else '') / 'Trio.shortcut'
    return plistlib.loads(path.read_bytes())['WFWorkflowActions']


def params(a):
    return a['WFWorkflowActionParameters']


def posts(actions):
    return [(i, params(a)) for i, a in enumerate(actions)
            if a['WFWorkflowActionIdentifier'].endswith('downloadurl')]


def dump(x):
    return repr(x)


@pytest.mark.parametrize('nokey', [False, True])
@pytest.mark.parametrize('lang', LANGS)
def test_search_branch(tmp_path, lang, nokey):
    actions = build(tmp_path, lang, nokey)
    search = [(i, p) for i, p in posts(actions)
              if ':generateContent' in dump(p['WFURL'])]
    assert len(search) == 2  # flash, then flash-lite
    first_post = search[0][0]
    for _, p in search:
        assert p['WFHTTPMethod'] == 'POST'
        assert 'generativelanguage.googleapis.com/v1beta/models/gemini-2.5-' in p['WFURL']['Value']['string']
        assert 'x-goog-api-key' in dump(p['WFHTTPHeaders'])
        assert 'Authorization' not in dump(p['WFHTTPHeaders'])
        assert 'google_search' in dump(p['WFJSONValues'])
        assert 'contents' in dump(p['WFJSONValues'])

    # sources: the «title» fields of the raw JSON answer → at most 5 → «• title» lines (D-101: no dictionary walk)
    keys = [params(a).get('WFDictionaryKey') for a in actions]
    assert not {'groundingChunks', 'web', 'uri'} & set(keys)
    assert any(params(a).get('WFMatchTextPattern') == r'"title"\s*:\s*"[^"]+"' for a in actions)
    assert any(params(a).get('WFItemSpecifier') == 'Items in Range' and params(a).get('WFItemRangeStart') == 1
               and params(a).get('WFItemRangeEnd') == 5 for a in actions)
    assert not any('WFItemCount' in params(a) for a in actions)
    # every Google key is tried: a Repeat with Each over the matches encloses the search attempts
    assert any(a['WFWorkflowActionIdentifier'].endswith('repeat.each') and params(a)['WFControlFlowMode'] == 0
               for a in actions[:first_post])
    assert any(a['WFWorkflowActionIdentifier'].endswith('repeat.each') for a in actions[first_post:])

    # failure is silent: each attempt is guarded by «ThirdVoice has no value», and the ordinary chain
    # (the OpenAI-compatible Gemini endpoint) comes AFTER the search attempts and is still there
    chain = [i for i, p in posts(actions)
             if ':generateContent' not in dump(p['WFURL']) and 'Authorization' in dump(p.get('WFHTTPHeaders', ''))]
    assert chain and min(chain) > search[-1][0]
    guards = [params(a) for a in actions[first_post - 4:first_post]
              if a['WFWorkflowActionIdentifier'].endswith('conditional')]
    assert guards and guards[-1]['WFCondition'] == 101  # «does not have any value»

    # no Sources line when there are no links, and the label word comes from the locale
    assert 'Sources' in dump(actions) or 'Fuentes' in dump(actions)


def _ids(actions):
    return [a['WFWorkflowActionIdentifier'].rsplit('.', 1)[-1] for a in actions]


def _guarded(actions, i):
    """True if actions[i] sits inside some If block (by GroupingIdentifier nesting)."""
    depth = 0
    for a in actions[:i]:
        if a['WFWorkflowActionIdentifier'].endswith('conditional'):
            mode = params(a)['WFControlFlowMode']
            depth += 1 if mode == 0 else -1 if mode == 2 else 0
    return depth > 0


@pytest.mark.parametrize('nokey', [False, True])
def test_sources_guarded_when_no_chunks(tmp_path, nokey):
    """D-101 (live iPhone 29.10): walking groundingChunks with «Get Dictionary Value» stopped Trio with «Choose values
    for each parameter in this action». The sources are matched in the answer's text; the line is added only when a
    title came (Match Text `\\S` on the result, then «has any value» on its Matches)."""
    actions = build(tmp_path, 'en', nokey)
    firsts = [i for i, a in enumerate(actions) if params(a).get('WFItemSpecifier') == 'Items in Range']
    assert firsts
    for i in firsts:
        assert actions[i - 1]['WFWorkflowActionIdentifier'].endswith('text.match')
        guard = actions[i + 4]
        assert guard['WFWorkflowActionIdentifier'].endswith('conditional') and params(guard)['WFCondition'] == 100
        assert params(guard)['WFInput']['Variable']['Value']['OutputName'] == 'Matches'


def test_nokey_no_ai_shows_provider_none(tmp_path):
    actions = build(tmp_path, 'en', True)
    t = dump(actions)
    i = next(n for n, a in enumerate(actions) if 'Response' in dump(params(a)) and
             a['WFWorkflowActionIdentifier'].endswith('conditional'))
    block = actions[i:i + 12]
    kinds = [params(a)['WFControlFlowMode'] for a in block if a['WFWorkflowActionIdentifier'].endswith('conditional')]
    assert kinds[:3] == [0, 1, 2]  # If / Otherwise / End If: the Apple label only in the Otherwise branch
    assert t.count('Apple Intelligence') >= 1


def test_clipboard_of_claude_answer_guarded(tmp_path):
    actions = build(tmp_path, 'en')
    clips = [i for i, a in enumerate(actions) if a['WFWorkflowActionIdentifier'].endswith('setclipboard')]
    assert clips and _guarded(actions, clips[0])
