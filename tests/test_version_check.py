"""Duo and Trio carry the weekly version check: version.json from GitHub, then the site, 7 days."""
import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VERSION = json.loads((ROOT / 'releases' / 'version.json').read_text(encoding='utf-8'))
sys.path.insert(0, str(ROOT / 'src'))
from build_shortcut import LONG_TEXT  # noqa: E402
LANGS = ['en', 'es', 'pt', 'ru', 'uk']


def build(tmp_path, builder, lang, name):
    env = dict(os.environ, C1_DIST=str(tmp_path))
    subprocess.run([sys.executable, str(ROOT / 'src' / builder), lang], check=True, cwd=ROOT,
                   env=env, capture_output=True)
    return plistlib.loads((tmp_path / lang / name).read_bytes())['WFWorkflowActions']


def params(actions, identifier):
    return [a['WFWorkflowActionParameters'] for a in actions
            if a['WFWorkflowActionIdentifier'] == 'is.workflow.actions.' + identifier]


def test_version_file_has_every_link():
    for key in ('duo', 'trio'):
        assert isinstance(VERSION[key], int)
        for lang in LANGS:
            assert VERSION[f'{key}_{lang}'].startswith('https://www.icloud.com/shortcuts/')


@pytest.mark.parametrize('lang', LANGS)
@pytest.mark.parametrize('builder,name,key', [('build_shortcut.py', 'Poly.shortcut', 'duo'),
                                              ('build_trio.py', 'Trio.shortcut', 'trio')])
def test_shortcut_checks_its_version(tmp_path, lang, builder, name, key):
    actions = build(tmp_path, builder, lang, name)
    urls = [p['WFURL'] for p in params(actions, 'downloadurl') if isinstance(p['WFURL'], str)]
    pair = ['https://raw.githubusercontent.com/vadimchernets/c1m-duo/main/releases/version.json',
            'https://polyhelper.ai/duo/version.json']
    if key == 'duo':
        # D-128: the first-run Setup (before the question) visits both addresses, the weekly check stays at the end
        assert urls == pair + [pair[1]] + pair
        actions = actions[max(i for i, a in enumerate(actions) if a['WFWorkflowActionIdentifier'].endswith('.ask')):]
        urls = [p['WFURL'] for p in params(actions, 'downloadurl') if isinstance(p['WFURL'], str)]
    assert urls == pair
    weekly = [p for p in params(actions, 'conditional') if p.get('WFCondition') == 1003
              and p['WFAnotherNumber'] == 7]  # the 15-minute draft window of Critique is another check
    assert [(p['WFNumberValue'], p['WFAnotherNumber']) for p in weekly] == [(-7, 7)]
    assert [p['WFTimeUntilUnit'] for p in params(actions, 'gettimebetweendates')
            if p['WFTimeUntilUnit'] == 'Days'] == ['Days'] * (3 if builder == 'build_shortcut.py' else 1)   # Duo 6.11: + the age of a source, in each Critique
    # Critique's long-request thresholds: the If right before the «long_text» step (instructions + LONG_DATA)
    long_ifs = {id(a['WFWorkflowActionParameters']) for i, a in enumerate(actions[:-1])
                if actions[i + 1]['WFWorkflowActionIdentifier'] == 'is.workflow.actions.comment'
                and actions[i + 1]['WFWorkflowActionParameters'].get('WFCommentActionText') == 'Duo step: long_text'}
    newer = [p['WFNumberValue'] for p in params(actions, 'conditional') if p.get('WFCondition') == 2
             and id(p) not in long_ifs
             and p['WFNumberValue'] not in (LONG_TEXT, 0, 1199, 5000)]  # 5000 = JUDGE_SPLIT (Duo 6.11)
    #   # LONG_TEXT = Trio's long-text threshold; 0 = Trio's
    # sources count; 1199 = the long-question threshold (Yuri 10.11)
    assert newer == [VERSION[key]]
    keys = [p['WFDictionaryKey'] for p in params(actions, 'getvalueforkey')]
    assert f'{key}_{lang}' in keys
    # the update link; besides it only the report link and (Duo, Claude did not answer) the Claude App Store page
    assert len([p for p in params(actions, 'openurl')
                if 'run-report' not in str(p) and 'template=feedback.yml' not in str(p) and 'polyhelper.ai' not in str(p) and 'apps.apple.com/app/id6473753684' not in str(p)]) == 1
    # the network goes first, by actions that never throw; a non-JSON answer is «no update»
    nets = [p['WFNetworkDetailsNetwork'] for p in params(actions, 'getwifi')]
    # Duo 6.11: the same guard stands in front of the search and of the link check, in each Critique
    assert nets == ['Wi-Fi', 'Cellular'] * (5 if builder == 'build_shortcut.py' else 1)
    first_net = next(i for i, a in enumerate(actions) if a['WFWorkflowActionIdentifier'].endswith('getwifi'))
    first_get = next(i for i, a in enumerate(actions) if a['WFWorkflowActionIdentifier'].endswith('downloadurl')
                     and isinstance(a['WFWorkflowActionParameters']['WFURL'], str))
    assert first_net < first_get
    guards = [p for p in params(actions, 'conditional') if p.get('WFConditionalActionString') == f'"{key}":']
    assert len(guards) == 3
    # the weekly check is the last thing a run does: nothing of the answer waits on the network
    assert actions[-1]['WFWorkflowActionIdentifier'] == 'is.workflow.actions.conditional'


@pytest.mark.parametrize('lang', LANGS)
def test_another_mode_calls_the_released_name(tmp_path, lang):
    actions = build(tmp_path, 'build_shortcut.py', lang, 'Poly.shortcut')
    assert {p['WFWorkflowName'] for p in params(actions, 'runworkflow')} == {'Duo'}  # Another mode and Recipes


def test_reruns_start_this_very_shortcut(tmp_path):
    """D-100: «Another mode», the Recipes and «go back» run THIS shortcut (isSelf), not whatever is called «Duo»:
    after «Keep Both» on the iPhone the new version was «Duo 1» and the reruns started the old one."""
    actions = build(tmp_path, 'build_shortcut.py', 'en', 'Poly.shortcut')
    runs = [a['WFWorkflowActionParameters'] for a in actions if a['WFWorkflowActionIdentifier'].endswith('runworkflow')]
    assert runs and all(p['WFWorkflow'] == {'isSelf': True, 'workflowName': 'Duo'} for p in runs)


@pytest.mark.parametrize('builder,name', [('build_shortcut.py', 'Poly.shortcut'), ('build_trio.py', 'Trio.shortcut')])
def test_conditions_have_inputs_shortcuts_accepts(tmp_path, builder, name):
    """D-100 (6.3.1, checked on Shortcuts 28.10): a number condition (less / greater / between) on a «Get Variable» or
    «Dictionary Value» output, and «contains» straight on «Contents of URL», stop the run with «Choose values for each
    parameter in this action» — it came right after «Done» of every Duo run (the weekly version check). A number
    condition takes a Number or Count; «contains» takes a Text or a variable."""
    actions = build(tmp_path, builder, 'en', name)
    for a in actions:
        if not a['WFWorkflowActionIdentifier'].endswith('conditional'):
            continue
        p = a['WFWorkflowActionParameters']
        if p.get('WFControlFlowMode') != 0:
            continue
        node = p['WFInput']['Variable']['Value']
        if p['WFCondition'] in (0, 1, 2, 3, 1003):
            assert node.get('OutputName') in ('Number', 'Count'), node
        if p['WFCondition'] in (99, 999, 4, 5):
            assert node.get('OutputName') != 'Contents of URL', node
        # D-101 (live iPhone 29.10, Trio): «has any value / does not have any value» straight on a Dictionary Value
        # stopped the run with the same dialog; a Text made from it (or a Count) works
        if p['WFCondition'] in (100, 101):
            assert node.get('OutputName') not in ('Dictionary Value', 'Contents of URL'), node
