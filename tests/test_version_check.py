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
    assert urls == ['https://raw.githubusercontent.com/vadimchernets/c1m-duo/main/releases/version.json',
                    'https://polyhelper.ai/duo/version.json']
    weekly = [p for p in params(actions, 'conditional') if p.get('WFCondition') == 1003
              and p['WFAnotherNumber'] == 7]  # the 15-minute draft window of Critique is another check
    assert [(p['WFNumberValue'], p['WFAnotherNumber']) for p in weekly] == [(-7, 7)]
    assert [p['WFTimeUntilUnit'] for p in params(actions, 'gettimebetweendates')
            if p['WFTimeUntilUnit'] == 'Days'] == ['Days']
    newer = [p['WFNumberValue'] for p in params(actions, 'conditional') if p.get('WFCondition') == 2
             and p['WFNumberValue'] != 6000]  # 6000 = the long-text threshold for Claude
    assert newer == [VERSION[key]]
    keys = [p['WFDictionaryKey'] for p in params(actions, 'getvalueforkey')]
    assert f'{key}_{lang}' in keys
    # the update link; besides it only the report link and (Duo, Claude did not answer) the Claude App Store page
    assert len([p for p in params(actions, 'openurl')
                if 'run-report' not in str(p) and 'apps.apple.com/app/id6473753684' not in str(p)]) == 1
    # the network goes first, by actions that never throw; a non-JSON answer is «no update»
    nets = [p['WFNetworkDetailsNetwork'] for p in params(actions, 'getwifi')]
    assert nets == ['Wi-Fi', 'Cellular']
    first_net = next(i for i, a in enumerate(actions) if a['WFWorkflowActionIdentifier'].endswith('getwifi'))
    first_get = next(i for i, a in enumerate(actions) if a['WFWorkflowActionIdentifier'].endswith('downloadurl')
                     and isinstance(a['WFWorkflowActionParameters']['WFURL'], str))
    assert first_net < first_get
    guards = [p for p in params(actions, 'conditional') if p.get('WFConditionalActionString') == f'"{key}":']
    assert len(guards) == 3
    # the check is the last thing a run does: nothing of the answer waits on the network
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
