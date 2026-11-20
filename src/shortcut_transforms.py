"""Transformations of a finished action list: ChatGPT retry and clean, Claude variables, diagnostic build."""
import json
import plistlib
import re
import os
import sys
import uuid as uuidlib
from pathlib import Path
from shortcut_actions import *  # noqa: F401,F403
from shortcut_actions import ROOT, OBJ, Locale  # noqa: F401


def with_gpt_retry(actions, skip=()):
    """One retry of an empty ChatGPT answer, 3 s later, for every «Ask ChatGPT» in the list (U-05). Each call is
    followed by: save to a variable → if that has no value → wait 3 s → ask again → save → end if → read the
    variable back; later references to the call's output now point at that last read. Calls that already carry
    their own retry (Critique, the debate opening) are named in `skip`."""
    out, rewrites, n = [], {}, 0
    for action in actions:
        action = rename_outputs(action, rewrites)
        out.append(action)
        params = action['WFWorkflowActionParameters']
        if action['WFWorkflowActionIdentifier'] != 'com.openai.chat.AskIntent' or params['UUID'] in skip:
            continue
        n += 1
        var, group = f'PolyGPTRetry{n}', new_uuid()
        again, final = new_uuid(), new_uuid()
        second = {'WFWorkflowActionIdentifier': action['WFWorkflowActionIdentifier'],
                  'WFWorkflowActionParameters': {**params, 'UUID': again}}
        out += [act_set_variable(var, params['UUID'], 'Ask ChatGPT'),
                *if_text(group, var, present=False), act_delay(3), second,
                act_set_variable(var, again, 'Ask ChatGPT'), if_close(group),
                act_get_variable(var, final)]
        rewrites[params['UUID']] = final
    return out


PUA = r'[\x{E000}-\x{F8FF}]'   # ChatGPT wraps its markup in private-use marker characters (U+E200..U+E206)
GPT_MARKUP = [
    # entity["city","Ottawa","..."] -> Ottawa (the second argument is the name shown to the reader)
    (PUA + r'*entity' + PUA + r'*\[\s*"(?:[^"\\]|\\.)*"\s*,\s*"((?:[^"\\]|\\.)*)"(?:[^\[\]]|\[[^\]]*\])*\]' + PUA + '*', '$1'),
    # image_group{"query":[...],"aspect_ratio":"5:3","layout":"carousel"} -> removed whole (one nested level of braces)
    (PUA + r'*image_group' + PUA + r'*\{(?:[^{}]|\{[^{}]*\})*\}' + PUA + '*', ''),
    # citeturn752459search6turn752459search11 (and navlist/filecite relatives): citation markers, removed whole
    (PUA + r'*(?:file|nav)?(?:cite|list)(?:' + PUA + r'*turn[0-9]+[a-z]+[0-9]+)+' + PUA + '*', ''),
    # any marker character left over
    (PUA, ''),
]


def with_gpt_clean(actions):
    """Every «Ask ChatGPT» output goes through Replace Text (regex) right after the call (14.11 live run on iPhone):
    (1) the raw markup Ask ChatGPT returns («entity[...]», «image_group{...}», private-use marker characters) is taken
    off before the answer is shown or compared; (2) the text that continues is a NEW text made by Replace Text, not the
    app's output itself. Critique wrote ChatGPT's output straight into «Save File» and iOS asked «Allow to add 1 text
    object to a text file?» in the middle of the run (from Shortcuts the run then ended, «Always Allow» was not
    remembered); Survey passed the same output through strip_markdown (Replace Text) before the file and ran on.
    Call → Set Variable → Get Variable → Replace Text ×3 → Set Variable → Get Variable; later references to the call's
    output point at that last read (an empty answer stays empty: Replace Text of an empty text is an empty text, and
    every test of an answer looks for a visible character, see if_text)."""
    out, rewrites, n = [], {}, 0
    for action in actions:
        action = rename_outputs(action, rewrites)
        out.append(action)
        params = action['WFWorkflowActionParameters']
        if action['WFWorkflowActionIdentifier'] != 'com.openai.chat.AskIntent':
            continue
        n += 1
        var, final = f'PolyGPTClean{n}', new_uuid()
        get, src, steps = new_uuid(), params['UUID'], []
        src_uid, src_name = get, 'Variable'
        for find, repl in GPT_MARKUP:
            r = new_uuid()
            steps.append(act_replace_regex(src_uid, src_name, find, repl, r))
            src_uid, src_name = r, 'Updated Text'
        out += [act_set_variable(var, src, 'Ask ChatGPT'),
                act_get_variable(var, get), *steps,
                act_set_variable(var, src_uid, 'Updated Text'),
                act_get_variable(var, final)]
        rewrites[src] = final
    return out


def with_claude_vars(actions):
    """Every «Ask Claude» output is read through a variable (Set Variable → Get Variable) before anything else uses it.
    Yuri 10.11 (No.52, iPhone XR, iOS 18.7.11): Side by side stopped twice out of two with the bare iOS alert «There was
    a problem running the shortcut» right after ChatGPT's step, while Critique and Advisor ran to the end on the same
    phone. Side by side was the only one of the three that put Claude's output straight into a Text; Critique reads it
    from a variable and Advisor only stores it in one. On a newer iOS (iPhone 30.10) the direct form ran, so this is the
    form proven on both. A Claude call already followed by a Set Variable of its output is left as it is."""
    out, rewrites, n = [], {}, 0
    for i, action in enumerate(actions):
        action = rename_outputs(action, rewrites)
        out.append(action)
        if action['WFWorkflowActionIdentifier'] != CLAUDE_INTENT:
            continue
        uid = action['WFWorkflowActionParameters']['UUID']
        nxt = actions[i + 1] if i + 1 < len(actions) else None
        if (nxt and nxt['WFWorkflowActionIdentifier'] == 'is.workflow.actions.setvariable'
                and nxt['WFWorkflowActionParameters']['WFInput']['Value'].get('OutputUUID') == uid):
            continue
        n += 1
        var, final = f'PolyClaudeOut{n}', new_uuid()
        out += [act_set_variable(var, uid, 'Ask Claude'), act_get_variable(var, final)]
        rewrites[uid] = final
    return out


def hms(uid):
    """A «Current Date» output formatted HH:mm:ss: the diag log lines carry seconds, so the time of each AI step is
    readable from the stamps even when «Time Between Dates» comes back blank (14.11 run: «1697 chars,  s»)."""
    return {'OutputUUID': uid, 'Type': 'ActionOutput', 'OutputName': 'Date',
            'Aggrandizements': [{'Type': 'WFDateFormatVariableAggrandizement', 'WFDateFormatStyle': 'Custom',
                                 'WFDateFormat': 'HH:mm:ss'}]}


def with_diag(actions):
    """C1_DIAG=1: the diagnostic build for a live run (Yuri 13.11, No.52/53: from the Shortcuts app a run stopped with the
    bare iOS alert or ended empty, through Siri it ran; which action fails could only be guessed). Around EVERY «Ask
    ChatGPT» / «Ask Claude»: a notification «→ #n ChatGPT» before it, and «← #n ChatGPT: N characters, S s» after it,
    read from the variable the output is stored in. The last «→» without its «←» in Notification Centre names the
    action iOS stopped; «0 characters» names one that came back empty; the seconds measure the time limit. Never
    released: dist-diag/, «Duo-diag» on the phone."""
    out, n = [], 0
    names = {'com.openai.chat.AskIntent': ('ChatGPT', 'Ask ChatGPT'), CLAUDE_INTENT: ('Claude', 'Ask Claude')}
    i = 0
    while i < len(actions):
        action = actions[i]
        kind_ = action['WFWorkflowActionIdentifier']
        if kind_ not in names:
            out.append(action)
            i += 1
            continue
        n += 1
        who, output = names[kind_]
        uid = action['WFWorkflowActionParameters']['UUID']
        t0, t1, dt, get, txt, cnt = (new_uuid() for _ in range(6))
        l0 = new_uuid()
        out += [act_date(t0), act_notify(f'🔧 → #{n} {who}'),
                act_text(text_token(f'{{D}} 🔧 → #{n} {who}\n', special={'D': hms(t0)}), l0),
                act_append_file('Duo-diag-log.txt', l0), action]
        nxt = actions[i + 1] if i + 1 < len(actions) else None
        if (nxt and nxt['WFWorkflowActionIdentifier'] == 'is.workflow.actions.setvariable'
                and nxt['WFWorkflowActionParameters']['WFInput']['Value'].get('OutputUUID') == uid):
            var = nxt['WFWorkflowActionParameters']['WFVariableName']
            out.append(nxt)
            i += 2
        else:
            var = 'PolyDiagOut'
            out.append(act_set_variable(var, uid, output))
            i += 1
        out += [act_date(t1),
                act_time_between(t1, 'Date', t0, 'Date', 'Seconds', dt),
                act_get_variable(var, get),
                act_text(text_token('{V}', {'V': (get, 'Variable')}), txt),
                act_count_chars(txt, 'Text', cnt),
                act_notify(text_token(f'🔧 ← #{n} {who}: {{C}} chars, {{S}} s',
                                      {'C': (cnt, 'Count'), 'S': (dt, 'Time Between Dates')})),
                # the same line into iCloud Drive → Shortcuts/Duo-diag-log.txt: readable from the Mac (14.11 run:
                # Notification Centre cannot be opened through iPhone Mirroring)
                act_text(text_token(f'{{D}} 🔧 ← #{n} {who}: {{C}} chars, {{S}} s\n',
                                    {'C': (cnt, 'Count'), 'S': (dt, 'Time Between Dates')}, {'D': hms(t1)}), l1 := new_uuid()),
                act_append_file('Duo-diag-log.txt', l1)]
    return out


def rename_outputs(node, rewrites):
    """A copy of `node` in which every reference to an output in `rewrites` reads «Variable» of the new action."""
    if isinstance(node, dict):
        if node.get('Type') == 'ActionOutput' and node.get('OutputUUID') in rewrites:
            return {**node, 'OutputUUID': rewrites[node['OutputUUID']], 'OutputName': 'Variable'}
        return {k: rename_outputs(v, rewrites) for k, v in node.items()}
    if isinstance(node, list):
        return [rename_outputs(v, rewrites) for v in node]
    return node

