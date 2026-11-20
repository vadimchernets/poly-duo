"""Structural checks of a built action list."""
import json
import plistlib
import re
import os
import sys
import uuid as uuidlib
from pathlib import Path
from shortcut_actions import *  # noqa: F401,F403
from shortcut_actions import ROOT, OBJ, Locale  # noqa: F401


def validate(actions):
    """Structural checks that must hold for the shortcut to run correctly."""
    seen_uuid, flow_stack, produced, var_sources = {}, [], set(), {}
    menus = {}
    for i, action in enumerate(actions):
        params = action['WFWorkflowActionParameters']

        uid = params.get('UUID')
        if uid:
            assert uid not in seen_uuid, f'duplicate action UUID at {i} and {seen_uuid[uid]}'
            seen_uuid[uid] = i

        mode = params.get('WFControlFlowMode')
        if mode == 0:
            flow_stack.append(params['GroupingIdentifier'])
            if 'WFMenuItems' in params:
                menus[params['GroupingIdentifier']] = list(params['WFMenuItems'])
        elif mode == 1:
            assert flow_stack and flow_stack[-1] == params['GroupingIdentifier'], \
                f'case outside its group at {i}'
            title = params.get('WFMenuItemTitle')
            if title is not None:
                items = menus[params['GroupingIdentifier']]
                assert title in items, f'menu case without a matching item: {title!r}'
                items.remove(title)
        elif mode == 2:
            assert flow_stack and flow_stack.pop() == params['GroupingIdentifier'], \
                f'group closed out of order at {i}'

        for ref in collect_references(params):
            assert ref in produced or ref == uid, f'action {i} references a later action'
        if uid:
            produced.add(uid)

        # «contains» on a variable or a file stops the run on device with «Choose values for each parameter in this
        # action» (D-100 28.10, Debate 15.11); only a Text action's output works
        # «Get Time Between Dates» with a date as an attachment returns blank on iPhone (probe 15.11): both as text tokens
        if action['WFWorkflowActionIdentifier'] == 'is.workflow.actions.gettimebetweendates':
            for key in ('WFInput', 'WFTimeUntilFromDate'):
                assert params[key].get('WFSerializationType') == 'WFTextTokenString', \
                    f'Time Between Dates at {i}: {key} must be a text token'
        # (the debate log was first set from «Nothing», so its type was not text)
        if action['WFWorkflowActionIdentifier'] == 'is.workflow.actions.setvariable':
            var_sources.setdefault(params['WFVariableName'], set()).add(
                params['WFInput'].get('Value', {}).get('OutputName'))
        if action['WFWorkflowActionIdentifier'] == 'is.workflow.actions.conditional' and params.get('WFCondition') == 99:
            src = params['WFInput'].get('Variable', {}).get('Value', {})
            if src.get('Type') == 'Variable':
                assert var_sources.get(src.get('VariableName'), set()) <= {'Text'}, \
                    f'«contains» at {i} tests a variable not always set from Text'
            else:
                assert src.get('OutputName') == 'Text', f'«contains» at {i} must test a Text action output'

    assert not flow_stack, 'unbalanced control flow'
    for group, leftovers in menus.items():
        assert not leftovers, f'menu items without a case: {leftovers}'

    for token in collect_text_tokens(actions):
        string, ranges = token['string'], token.get('attachmentsByRange', {})
        utf16 = string.encode('utf-16-le')
        for position, att in ranges.items():
            offset = int(position.strip('{}').split(',')[0])
            assert utf16[offset * 2:offset * 2 + 2].decode('utf-16-le', 'replace') == OBJ, \
                'text token offset does not point at a placeholder'
            assert att.get('Type') in ('ActionOutput', 'ExtensionInput'), \
                'only action outputs and share input may be embedded in text'


def collect_references(node, found=None):
    found = set() if found is None else found
    if isinstance(node, dict):
        if node.get('Type') == 'ActionOutput':
            found.add(node['OutputUUID'])
        for value in node.values():
            collect_references(value, found)
    elif isinstance(node, list):
        for value in node:
            collect_references(value, found)
    return found


def collect_text_tokens(node, found=None):
    found = [] if found is None else found
    if isinstance(node, dict):
        if node.get('WFSerializationType') == 'WFTextTokenString':
            found.append(node['Value'])
        for value in node.values():
            collect_text_tokens(value, found)
    elif isinstance(node, list):
        for value in node:
            collect_text_tokens(value, found)
    return found
