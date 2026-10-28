#!/usr/bin/env python3
"""Build the main C1 shortcut (Poly) for one locale.

Usage:  python3 src/build_shortcut.py <lang>        # e.g. en, ru
Output: dist/<lang>/Poly.shortcut  (unsigned; tools/build.sh signs it)

Every user-visible string comes from locales/<lang>/ — the code carries no text.
Adding a language means adding a locale folder, nothing else.
"""
import json
import plistlib
import re
import os
import sys
import uuid as uuidlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OBJ = '￼'  # object replacement char: marks an inserted value inside a text token

# ---------------------------------------------------------------- locale

class Locale:
    def __init__(self, lang):
        self.lang = lang
        base = ROOT / 'locales' / lang
        if not base.is_dir():
            sys.exit(f'locale not found: {base}')
        self.ui = json.loads((base / 'ui.json').read_text(encoding='utf-8'))
        # prompts are shared: the models read them, not the user, and English works best.
        # A locale may override any of them by dropping a file into locales/<lang>/prompts/.
        self.prompts_dirs = [base / 'prompts', ROOT / 'locales' / 'en' / 'prompts']

    def __getitem__(self, dotted):
        node = self.ui
        for part in dotted.split('.'):
            node = node[part]
        return node

    def prompt(self, name):
        for directory in self.prompts_dirs:
            path = directory / f'{name}.txt'
            if path.exists():
                return path.read_text(encoding='utf-8').rstrip('\n')
        sys.exit(f'prompt not found: {name}')


# ---------------------------------------------------------------- plist helpers

def new_uuid():
    return str(uuidlib.uuid4()).upper()


def text_token(template, refs=None, special=None):
    """Build a WFTextTokenString.

    refs:    marker -> (action uuid, output name)   — reference to an action's output
    special: marker -> ready-made attachment dict   — e.g. the share-sheet input

    Only ActionOutput references are placed inside strings; dates and variables are
    fetched by their own actions first (see act_date / act_get_variable) so that the
    text always renders on device.
    """
    refs, special = refs or {}, special or {}
    keys = list(refs) + list(special)
    out, attachments = '', {}
    if keys:
        pattern = re.compile(r'\{(' + '|'.join(re.escape(k) for k in keys) + r')\}')
        last = 0
        for m in pattern.finditer(template):
            out += template[last:m.start()]
            key = m.group(1)
            if key in refs:
                attachment = {'OutputUUID': refs[key][0], 'Type': 'ActionOutput',
                              'OutputName': refs[key][1]}
            else:
                attachment = dict(special[key])
            # offsets are counted in UTF-16 code units, as Shortcuts expects
            attachments['{%d, 1}' % (len(out.encode('utf-16-le')) // 2)] = attachment
            out += OBJ
            last = m.end()
        out += template[last:]
    else:
        out = template
    return {'Value': {'string': out, 'attachmentsByRange': attachments},
            'WFSerializationType': 'WFTextTokenString'}


def attachment(uid, name):
    return {'Value': {'OutputUUID': uid, 'Type': 'ActionOutput', 'OutputName': name},
            'WFSerializationType': 'WFTextTokenAttachment'}


def variable(name):
    return {'Value': {'Type': 'Variable', 'VariableName': name},
            'WFSerializationType': 'WFTextTokenAttachment'}


SHARE_INPUT = {'Type': 'ExtensionInput'}


def act_ask(prompt, uid, default=None, prefill_from_share=False, default_from=None):
    params = {'WFAskActionPrompt': prompt, 'UUID': uid}
    if default_from:  # (action uuid, output name) — e.g. the Share input or, failing that, the clipboard
        params['WFAskActionDefaultAnswer'] = text_token('{S}', {'S': default_from})
    elif prefill_from_share:
        params['WFAskActionDefaultAnswer'] = text_token('{S}', special={'S': SHARE_INPUT})
    elif default is not None:
        params['WFAskActionDefaultAnswer'] = text_token(default)
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.ask',
            'WFWorkflowActionParameters': params}


def act_gpt(prompt, uid):
    return {'WFWorkflowActionIdentifier': 'com.openai.chat.AskIntent',
            'WFWorkflowActionParameters': {
                'AppIntentDescriptor': {'TeamIdentifier': '2DC432GLL2',
                                        'BundleIdentifier': 'com.openai.chat',
                                        'Name': 'ChatGPT', 'AppIntentIdentifier': 'AskIntent'},
                'newChat': True, 'continuous': False,
                'model': {'identifier': 'auto', 'title': {'key': 'Auto'},
                          'subtitle': {'key': 'Auto'}},
                'ShowWhenRun': False, 'prompt': prompt, 'UUID': uid}}


def act_claude(message, uid):
    return {'WFWorkflowActionIdentifier': 'com.anthropic.claude.ClaudeAppIntentsExtension',
            'WFWorkflowActionParameters': {
                'AppIntentDescriptor': {'TeamIdentifier': 'Q6L2SF6YDW',
                                        'BundleIdentifier': 'com.anthropic.claude',
                                        'Name': 'Claude',
                                        'AppIntentIdentifier': 'ClaudeAppIntentsExtension'},
                'ShowWhenRun': False, 'message': message, 'UUID': uid}}


def act_text(token, uid):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.gettext',
            'WFWorkflowActionParameters': {'WFTextActionText': token, 'UUID': uid}}


def act_set_variable(name, src_uid, src_name):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.setvariable',
            'WFWorkflowActionParameters': {'WFVariableName': name,
                                           'WFInput': attachment(src_uid, src_name)}}


def act_get_variable(name, uid):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.getvariable',
            'WFWorkflowActionParameters': {'WFVariable': variable(name), 'UUID': uid}}


def act_date(uid):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.date',
            'WFWorkflowActionParameters': {'WFDateActionMode': 'Current Date', 'UUID': uid}}


def act_notify(body):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.notification',
            'WFWorkflowActionParameters': {'WFNotificationActionTitle': 'Poly',
                                           'WFNotificationActionBody': body,
                                           'WFNotificationActionSound': False}}


def act_comment(text):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.comment',
            'WFWorkflowActionParameters': {'WFCommentActionText': text}}


def act_clipboard(source):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.setclipboard',
            'WFWorkflowActionParameters': {'WFInput': source, 'WFLocalOnly': False}}


def act_detect(what, source, uid):
    """«Get Images from Input» (`detect.images`) / «Get Text from Input» (`detect.text`) on the Share input."""
    return {'WFWorkflowActionIdentifier': f'is.workflow.actions.detect.{what}',
            'WFWorkflowActionParameters': {'WFInput': {'Value': source, 'WFSerializationType': 'WFTextTokenAttachment'},
                                           'UUID': uid}}


def act_clipboard_get(uid):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.getclipboard',
            'WFWorkflowActionParameters': {'UUID': uid}}


def act_count_chars(src_uid, src_name, uid):
    # «Count» action (is.workflow.actions.count), WFCountType Characters; output name «Count». Not checked on device.
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.count',
            'WFWorkflowActionParameters': {'WFCountType': 'Characters',
                                           'Input': attachment(src_uid, src_name), 'UUID': uid}}


def act_delay(seconds):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.delay',
            'WFWorkflowActionParameters': {'WFDelayTime': seconds}}


def act_first_match(src_uid, src_name, pattern, uid):
    # «Match Text» with any regex; output name «Matches». The input is a token STRING, as in build_trio.act_match.
    # Not checked on device.
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.text.match',
            'WFWorkflowActionParameters': {'WFMatchTextPattern': pattern,
                                           'WFMatchTextCaseSensitive': False,
                                           'text': text_token('{T}', {'T': (src_uid, src_name)}), 'UUID': uid}}


def act_first_chars(src_uid, src_name, limit, uid):
    # «Match Text» (is.workflow.actions.text.match) with a regex that takes the first `limit` characters
    # (`(?s)` lets the dot cross line breaks); output name «Matches». Not checked on device.
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.text.match',
            'WFWorkflowActionParameters': {'WFMatchTextPattern': '(?s)^.{1,%d}' % limit,
                                           'WFMatchTextCaseSensitive': False,
                                           'text': text_token('{T}', {'T': (src_uid, src_name)}), 'UUID': uid}}


def act_quick_look(source):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.previewdocument',
            'WFWorkflowActionParameters': {'WFInput': source}}


def act_append_file(path, src_uid):
    # a text field needs a token STRING (not a bare attachment) to receive a value
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.file.append',
            'WFWorkflowActionParameters': {'WFFileStorageService': 'iCloud Drive',
                                           'WFFilePath': path,
                                           'WFAppendFileWriteMode': 'Append',
                                           'WFInput': text_token('{T}', {'T': (src_uid, 'Text')})}}


def act_save_file(path, src_uid, uid):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.documentpicker.save',
            'WFWorkflowActionParameters': {'WFFileStorageService': 'iCloud Drive',
                                           'WFAskWhereToSave': False,
                                           'WFFileDestinationPath': path,
                                           'WFSaveFileOverwrite': True,
                                           'WFInput': text_token('{H}', {'H': (src_uid, 'Text')}),
                                           'UUID': uid}}


def act_get_file(path, uid):
    # a missing file is not an error here: the action returns nothing and the shortcut goes on
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.documentpicker.open',
            'WFWorkflowActionParameters': {'WFFileStorageService': 'iCloud Drive',
                                           'WFGetFilePath': path,
                                           'WFShowFilePicker': False,
                                           'WFFileErrorIfNotFound': False,
                                           'UUID': uid}}


def act_alert(title, message):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.alert',
            'WFWorkflowActionParameters': {'WFAlertActionTitle': title,
                                           'WFAlertActionMessage': message,
                                           'WFAlertActionCancelButtonShown': False}}


def act_run_shortcut(name, src_uid, src_name):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.runworkflow',
            'WFWorkflowActionParameters': {'WFWorkflowName': name, 'WFShowWorkflow': False,
                                           'WFInput': attachment(src_uid, src_name)}}


def act_run_self(name, src_uid, src_name):
    """Run THIS shortcut again (`isSelf`), whatever it is called on the phone. D-100: by name, «Another mode — same
    question», the Recipes and «go back» ran the shortcut called «Duo»; after «Keep Both» the new version is «Duo 1»,
    so they started the OLD one (live iPhone 28.10). `isSelf` checked on Shortcuts (macOS) 28.10: the child run gets
    the input and returns its output to the parent. `name` stays for older Shortcuts that read only the name."""
    action = act_run_shortcut(name, src_uid, src_name)
    action['WFWorkflowActionParameters']['WFWorkflow'] = {'isSelf': True, 'workflowName': name}
    return action


def menu_open(group, title, items):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.choosefrommenu',
            'WFWorkflowActionParameters': {'GroupingIdentifier': group, 'WFControlFlowMode': 0,
                                           'WFMenuPrompt': title, 'WFMenuItems': items}}


def menu_case(group, title):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.choosefrommenu',
            'WFWorkflowActionParameters': {'GroupingIdentifier': group, 'WFControlFlowMode': 1,
                                           'WFMenuItemTitle': title}}


def menu_close(group):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.choosefrommenu',
            'WFWorkflowActionParameters': {'GroupingIdentifier': group, 'WFControlFlowMode': 2}}


def if_has_value(group, var_name):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.conditional',
            'WFWorkflowActionParameters': {'GroupingIdentifier': group, 'WFControlFlowMode': 0,
                                           'WFCondition': 100,
                                           'WFInput': {'Type': 'Variable',
                                                       'Variable': variable(var_name)}}}


def if_contains(group, var_name, needle):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.conditional',
            'WFWorkflowActionParameters': {'GroupingIdentifier': group, 'WFControlFlowMode': 0,
                                           'WFCondition': 99,  # «contains»
                                           'WFConditionalActionString': needle,
                                           'WFInput': {'Type': 'Variable',
                                                       'Variable': variable(var_name)}}}


def if_shortcut_input(group):
    """If Shortcut Input has any value (the Share Sheet text/URL; empty when run from the app list, Back Tap,
    Action Button, Siri). NOT yet checked on a device: the WFInput encoding is the one Shortcuts itself writes
    for «Shortcut Input» in a condition. TO CHECK ON AN iPhone before release: run Duo from the app list (the
    condition must be false, the clipboard is read) and from the Share Sheet (true, the clipboard is NOT read);
    if it misbehaves, export the condition «If Shortcut Input has any value» from Shortcuts and copy its WFInput."""
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.conditional',
            'WFWorkflowActionParameters': {'GroupingIdentifier': group, 'WFControlFlowMode': 0,
                                           'WFCondition': 100,
                                           'WFInput': {'Type': 'Variable',
                                                       'Variable': {'Value': SHARE_INPUT,
                                                                    'WFSerializationType': 'WFTextTokenAttachment'}}}}


REPEAT_ITEM = {'Type': 'Variable', 'VariableName': 'Repeat Item'}


def repeat_open(group, src_uid, src_name):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.repeat.each',
            'WFWorkflowActionParameters': {'GroupingIdentifier': group, 'WFControlFlowMode': 0,
                                           'WFInput': attachment(src_uid, src_name)}}


def repeat_close(group):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.repeat.each',
            'WFWorkflowActionParameters': {'GroupingIdentifier': group, 'WFControlFlowMode': 2}}


def if_item_missing(group, var_name, item_uid):
    """If <variable> does not contain the current Repeat Item (condition 999 «does not contain»); the item is
    first fetched by its own Get Variable action, because a variable inside a string does not render."""
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.conditional',
            'WFWorkflowActionParameters': {
                'GroupingIdentifier': group, 'WFControlFlowMode': 0, 'WFCondition': 999,
                'WFConditionalActionString': text_token('{I}', {'I': (item_uid, 'Variable')}),
                'WFInput': {'Type': 'Variable', 'Variable': variable(var_name)}}}


def act_replace_text(src_uid, src_name, find, replacement, uid):
    """Replace Text (plain, not regex) on a token string; output name «Updated Text». Not checked on device."""
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.text.replace',
            'WFWorkflowActionParameters': {'WFReplaceTextFind': find, 'WFReplaceTextReplace': replacement,
                                           'WFReplaceTextRegularExpression': False,
                                           'WFReplaceTextCaseSensitive': True,
                                           'WFInput': text_token('{T}', {'T': (src_uid, src_name)}), 'UUID': uid}}


def act_number(src_uid, src_name, uid):
    """Number action fed with an earlier output (text → a real number); output name «Number». Not checked on device."""
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.number',
            'WFWorkflowActionParameters': {'WFNumberActionNumber': text_token('{N}', {'N': (src_uid, src_name)}),
                                           'UUID': uid}}


def act_match_number(src_uid, src_name, number_uid, number_name, uid):
    """Match Text: the number `number_uid` (its dots already escaped) as a WHOLE number inside the text — not a part
    of a longer one: «7» is not found in «17» or «7.5» or «1,7», but is found in «7.» at the end of a sentence."""
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.text.match',
            'WFWorkflowActionParameters': {
                'WFMatchTextPattern': text_token(r'(?<!\d)(?<!\d[.,]){E}(?!\d)(?![.,]\d)', {'E': (number_uid, number_name)}),
                'WFMatchTextCaseSensitive': False,
                'text': text_token('{T}', {'T': (src_uid, src_name)}), 'UUID': uid}}


def act_nothing(uid):
    """«Nothing» (is.workflow.actions.nothing): its output has no value."""
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.nothing',
            'WFWorkflowActionParameters': {'UUID': uid}}


def clear_variable(name):
    """Set the variable to NOTHING — never to an empty Text. D-100, checked on Shortcuts 28.10: a variable set from
    a Text action with an empty string «has any value» (and «does not have any value» is false), so every «no answer
    yet → ask» branch behind such a variable was skipped: on the iPhone Duo 6 Critique never called ChatGPT nor
    Claude's blind answer. A variable set from «Nothing» has no value, as an unset one."""
    uid = new_uuid()
    return [act_nothing(uid), act_set_variable(name, uid, 'Nothing')]


def if_text(group, var_name, present=True):
    """If the variable holds at least one non-space character (present=True), or not (present=False). D-100: «has any
    value» is true for an empty or blank text, so an answer that came back as empty text (or a text read from an
    emptied draft file) must be tested by its characters, not by «has any value». Match Text `\\S` → its Matches has a
    value only when there is a visible character; for a variable with nothing in it Matches has no value either
    (both checked on Shortcuts 28.10)."""
    get, match = new_uuid(), new_uuid()
    return [act_get_variable(var_name, get),
            act_first_match(get, 'Variable', r'\S', match),
            if_output(group, match, 'Matches', 100 if present else 101)]


def if_output_text(group, src_uid, src_name, present=True):
    """As if_text, for an earlier action's output instead of a variable."""
    match = new_uuid()
    return [act_first_match(src_uid, src_name, r'\S', match),
            if_output(group, match, 'Matches', 100 if present else 101)]


def if_else(group):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.conditional',
            'WFWorkflowActionParameters': {'GroupingIdentifier': group, 'WFControlFlowMode': 1}}


def if_close(group):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.conditional',
            'WFWorkflowActionParameters': {'GroupingIdentifier': group, 'WFControlFlowMode': 2}}


# ---------------------------------------------------------------- weekly version check
#
# A shortcut cannot replace itself, so it only offers the new one (distribution decision of 2026-10-02, item e).
# At most once in 7 days, at the very END of a run — after the answer is on screen, in the clipboard
# and in the journal — it reads releases/version.json: GitHub raw first, the site copy second. If the
# number there is higher than the one built in, one line asks «a new version is out — install?» and
# «Install» opens the iCloud link for this language from the same file. The day of the last check is
# the modification date of a small file next to poly-key.txt (iCloud Drive → Shortcuts). The network
# is checked first by actions that cannot throw (Wi-Fi name, else cellular radio): offline, the check
# is silently skipped and tried again on the next run; an empty or non-JSON answer means «no update».

VERSION_FILE = ROOT / 'releases' / 'version.json'
VERSION_URLS = ('https://raw.githubusercontent.com/vadimchernets/c1m-duo/main/releases/version.json',
                'https://polyhelper.ai/duo/version.json')
VERSION_DAYS = 7
# The name the main shortcut is released under (releases/<lang>/Duo.shortcut, the iCloud record, the
# site). iOS names an imported shortcut after it, so «another mode — same question» calls this name.
RELEASE_NAME = 'Duo'
# «Debate until agreement»: a side that is genuinely convinced starts its reply with this marker
# (the prompts argue-2-object / argue-3-reply ask for it); the shortcut stops the rounds when it appears.
ARGUE_MARKER = '[[CONCEDE]]'


def version_key(ai):
    """The releases/version.json key of this build: the AI build uses its own `duo_ai` once the file has it; until
    then it follows `duo` (the same number, the same iCloud links), for the check, the report and the build alike."""
    versions = json.loads(VERSION_FILE.read_text(encoding='utf-8'))
    return 'duo_ai' if ai and 'duo_ai' in versions else 'duo'
# the dropdown of .github/ISSUE_TEMPLATE/run-report.yml: a pre-filled value must equal an option exactly
REPORT_MODES = {'critique': 'Critique', 'argue': 'Debate%20to%20agreement', 'survey': 'Side%20by%20side',
                'synthesis_claude': 'Synthesis', 'synthesis_gpt': 'Synthesis', 'advisor': 'Advisor',
                None: 'Another%20mode%20from%20the%20menu'}
MY_MODE_FILE = 'Poly-my-mode.txt'
# How much of the answer Duo left in the clipboard is remembered (files.last_answer), to recognise it next run
LAST_ANSWER_CHARS = 200
REPORT_URL = 'https://github.com/vadimchernets/poly-duo/issues/new?template=run-report.yml'
LONG_TEXT = 6000


def built_version(key):
    """The number this build carries: the one in releases/version.json at build time."""
    versions = json.loads(VERSION_FILE.read_text(encoding='utf-8'))
    if key == 'duo_ai' and key not in versions:
        return int(versions['duo'])  # releases/version.json gets its own duo_ai number when the build is released
    return int(versions[key])


def act_download(url, uid):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.downloadurl',
            'WFWorkflowActionParameters': {'WFURL': url, 'UUID': uid}}


def act_dict_value(key, src_uid, src_name, uid):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.getvalueforkey',
            'WFWorkflowActionParameters': {'WFGetDictionaryValueType': 'Value',
                                           'WFDictionaryKey': key,
                                           'WFInput': attachment(src_uid, src_name),
                                           'UUID': uid}}


def if_output(group, src_uid, src_name, condition, **numbers):
    """If <an earlier action's output> <condition> — 100 has any value, 2 greater than, 1003 between."""
    params = {'GroupingIdentifier': group, 'WFControlFlowMode': 0, 'WFCondition': condition,
              'WFInput': {'Type': 'Variable', 'Variable': attachment(src_uid, src_name)}}
    params.update(numbers)
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.conditional',
            'WFWorkflowActionParameters': params}


def if_no_value(group, var_name):
    action = if_has_value(group, var_name)
    action['WFWorkflowActionParameters']['WFCondition'] = 101  # «does not have any value»
    return action


def version_check(L, key, name, lang):
    """Actions of the weekly version check for the shortcut `key` ('duo' or 'trio') in `lang`."""
    ids = lambda n: [new_uuid() for _ in range(n)]
    (f_get, f_date, now, age, far, age_get, stamp_now, stamp, stamp_save,
     wifi, cell, net_get, gh, site, json_get, remote, link) = ids(17)
    age_num, remote_num, gh_t, site_t, json_t = ids(5)
    g_file, g_due, g_wifi, g_net, g_gh, g_site, g_json, g_new, g_menu, g_link = ids(10)
    age_var, json_var, net_var = f'{name}VersionAge', f'{name}VersionJson', f'{name}Network'
    stamp_file = f'{name}-version-check.txt'
    needle = f'"{key}":'
    install, later = L['update.install'], L['update.later']
    return [
        act_comment(f'Version check: at most once in {VERSION_DAYS} days, '
                    f'{VERSION_URLS[0]} then {VERSION_URLS[1]}; this build is '
                    f'{key} {built_version(key)}.'),
        act_get_file(stamp_file, f_get),
        if_output(g_file, f_get, 'File', 100),
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.properties.files',
         'WFWorkflowActionParameters': {'WFInput': attachment(f_get, 'File'),
                                        'WFContentItemPropertyName': 'Last Modified Date',
                                        'UUID': f_date}},
        act_date(now),
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.gettimebetweendates',
         'WFWorkflowActionParameters': {'WFInput': attachment(now, 'Date'),
                                        'WFTimeUntilFromDate': text_token(
                                            '{D}', {'D': (f_date, 'Last Modified Date')}),
                                        'WFTimeUntilUnit': 'Days', 'UUID': age}},
        act_set_variable(age_var, age, 'Time Between Dates'),
        if_else(g_file),
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.number',
         'WFWorkflowActionParameters': {'WFNumberActionNumber': 999, 'UUID': far}},
        act_set_variable(age_var, far, 'Number'),
        if_close(g_file),
        act_get_variable(age_var, age_get),
        # D-100 (6.3.1): a number condition on a «Get Variable» output stops the run with «Choose values for each
        # parameter in this action» (iPhone and Mac, 28.10: right after «Done» of every run, so the check never ran and
        # never stamped). Through a Number action, as the debate rounds do, it works.
        act_number(age_get, 'Variable', age_num),
        # «between −7 and 7 days» reads the same whichever way the system counts the difference
        if_output(g_due, age_num, 'Number', 1003,
                  WFNumberValue=-VERSION_DAYS, WFAnotherNumber=VERSION_DAYS),
        if_else(g_due),
        # Offline, «Get Contents of URL» stops the shortcut with a system error, and Shortcuts has
        # no try/catch. So the network goes first, by actions that never throw: a Wi-Fi network
        # name, else a cellular radio technology. Neither → no check this run, no stamp, no error.
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.getwifi',
         'WFWorkflowActionParameters': {'WFNetworkDetailsNetwork': 'Wi-Fi',
                                        'WFWiFiDetail': 'Network Name', 'UUID': wifi}},
        act_set_variable(net_var, wifi, 'Network Details'),
        if_no_value(g_wifi, net_var),
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.getwifi',
         'WFWorkflowActionParameters': {'WFNetworkDetailsNetwork': 'Cellular',
                                        'WFCellularDetail': 'Radio Technology', 'UUID': cell}},
        act_set_variable(net_var, cell, 'Network Details'),
        if_close(g_wifi),
        act_get_variable(net_var, net_get),
        if_output(g_net, net_get, 'Variable', 100),
        act_date(stamp_now),
        act_text(text_token('{D}', {'D': (stamp_now, 'Date')}), stamp),
        act_save_file(stamp_file, stamp, stamp_save),
        # An empty answer, a 404 page or HTML from a proxy is «no update»: only a text that
        # contains the key is ever read as a dictionary.
        # D-100 (6.3.1): «contains» straight on «Contents of URL» (a file) stops the run with «Choose values for each
        # parameter in this action» (checked on Shortcuts, 28.10); on a Text made from it, it works.
        act_download(VERSION_URLS[0], gh),
        act_text(text_token('{C}', {'C': (gh, 'Contents of URL')}), gh_t),
        if_output(g_gh, gh_t, 'Text', 99, WFConditionalActionString=needle),
        act_set_variable(json_var, gh_t, 'Text'),
        if_else(g_gh),
        act_download(VERSION_URLS[1], site),
        act_text(text_token('{C}', {'C': (site, 'Contents of URL')}), site_t),
        if_output(g_site, site_t, 'Text', 99, WFConditionalActionString=needle),
        act_set_variable(json_var, site_t, 'Text'),
        if_close(g_site),
        if_close(g_gh),
        act_get_variable(json_var, json_get),
        act_text(text_token('{J}', {'J': (json_get, 'Variable')}), json_t),
        if_output(g_json, json_t, 'Text', 99, WFConditionalActionString=needle),
        act_dict_value(key, json_t, 'Text', remote),
        act_number(remote, 'Dictionary Value', remote_num),   # a number condition needs a Number input (D-100)
        if_output(g_new, remote_num, 'Number', 2, WFNumberValue=built_version(key)),
        act_dict_value(f'{key}_{lang}', json_t, 'Text', link),
        # only with a link for this language: an empty one would open nothing (Codex, D-100)
        *if_output_text(g_link, link, 'Dictionary Value'),
        menu_open(g_menu, L['update.prompt'].replace('{NAME}', name), [install, later]),
        menu_case(g_menu, install),
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.openurl',
         'WFWorkflowActionParameters': {'WFInput': text_token('{L}', {'L': (link, 'Dictionary Value')}),
                                        'Show-WFInput': True}},
        menu_case(g_menu, later),
        menu_close(g_menu),
        if_close(g_link),
        if_close(g_new),
        if_close(g_json),
        if_close(g_net),
        if_close(g_due),
    ]


IMAGE_GALLERY_HTML = (
    '<!DOCTYPE html><html><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1"><style>'
    'body{font-family:-apple-system,sans-serif;background:#111;color:#eee;margin:0;padding:14px}'
    'h2{margin:4px 0 14px}figure{margin:0 0 26px}'
    'svg{width:100%;height:auto;background:#fff;border-radius:14px;display:block}'
    'figcaption{margin-top:8px;font-size:15px;letter-spacing:.5px;color:#9ad}'
    '</style></head><body><h2>{TITLE}</h2>'
    '<figure>{C}<figcaption>{CAP_C}</figcaption></figure>'
    '<figure>{G}<figcaption>{CAP_G}</figcaption></figure></body></html>'
)


# ---------------------------------------------------------------- build

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


def rename_outputs(node, rewrites):
    """A copy of `node` in which every reference to an output in `rewrites` reads «Variable» of the new action."""
    if isinstance(node, dict):
        if node.get('Type') == 'ActionOutput' and node.get('OutputUUID') in rewrites:
            return {**node, 'OutputUUID': rewrites[node['OutputUUID']], 'OutputName': 'Variable'}
        return {k: rename_outputs(v, rewrites) for k, v in node.items()}
    if isinstance(node, list):
        return [rename_outputs(v, rewrites) for v in node]
    return node


def build(lang, ai=False):
    """ai=True → dist/<lang>/ai/Duo.shortcut (U-07): the same Duo, but Auto and Clarify's questions are done by
    «Use Model» (Apple Intelligence, on the iPhone) instead of ChatGPT — one message cheaper each, and the service
    prompts never reach ChatGPT's history or memory. Built only for languages with Apple Intelligence (those whose
    trio.json has the nokey.* words)."""
    import build_trio  # lazy: build_trio imports this module
    L = Locale(lang)
    TRIO = ROOT / 'locales' / lang / 'trio.json'
    if ai and 'nokey.comment' not in json.loads(TRIO.read_text(encoding='utf-8') if TRIO.exists() else '{}'):
        print(f'{lang}: no Apple Intelligence words in trio.json — Duo with Apple Intelligence not built')
        return
    # the provider chain for «Claude did not answer → check with a key» is Trio's, not a copy; where a language has
    # no trio.json yet, its (brand-name and English) words are used
    T = json.loads((TRIO if TRIO.exists() else ROOT / 'locales' / 'en' / 'trio.json').read_text(encoding='utf-8'))
    TV = T['variables']

    def service_call(prompt_uid, uid):
        """The one cheap service call: (action, output name) — ChatGPT, or Use Model in the ai build."""
        if ai:
            return build_trio.act_use_model(prompt_uid, uid), 'Response'
        return act_gpt(text_token('{P}', {'P': (prompt_uid, 'Text')}), uid), 'Ask ChatGPT'

    RESULT = L['variables.result']
    JOURNAL_EXTRA = L['variables.journal_extra']
    MAIN = L['menu.main_items']
    EXTRA = L['menu.extra_items']

    ids = lambda n: [new_uuid() for _ in range(n)]
    question, = ids(1)
    Q = {'Q': (question, 'Provided Input')}
    QUESTION = {'QUESTION': (question, 'Provided Input')}

    g_main, g_extra, g_anchor, g_image, g_empty, g_finale = ids(6)
    g_notice, g_blank, g_start, g_show = ids(4)
    st_clip, st_share, st_get, st_empty, st_words, g_words = ids(6)
    st_img, st_ocr, st_dtext, g_img = ids(4)
    st_fn, st_clr, g_fn, g_nostart = ids(4)
    st_last, st_last_t, st_mine, g_last, g_mine, g_rec0, st_ccut, st_ctext = ids(8)
    START_VAR = 'PolyStartText'
    GPT_VAR, CLAUDE_VAR = 'PolyChatGPTAnswer', 'PolyClaudeAnswer'
    OWN_VAR = 'PolyClaudeOwn'   # Critique: Claude's blind answer (step 2); CLAUDE_VAR is the step-3 comparison
    VK = version_key(ai)
    CHECK_VAR = 'PolyCheckRequest'
    RETRY_SKIP = set()   # ChatGPT calls that have their own retry or are not a mode's first call (see with_gpt_retry)
    NUMS_VAR, MODE_VAR, MY_RULE = 'PolyOnlyInOne', 'PolyMode', 'PolyMyRule'
    g_rec, g_mm, g_more = ids(3)
    rv_wrap, rv_claude, rv_prompt, rv_gpt, rv_sum_prompt, rv_sum, rv_out, mm_file, mm_rule = ids(9)
    (fn_get, fn_prompt, fn_gpt, fn_out, nt_get, rm_get, rm_match, rm_item, dv_model, dv_ios, ue_model, ue_ios,
     md_get, rp_get, rp_title) = ids(15)
    g_rat, g_rem = ids(2)
    g_mmenu, mm_ask, mm_new, mm_save, tl_rget, g_tlrem, g_mmempty, mm_chars = ids(8)
    fn_date, fn_jx, fn_entry = ids(3)

    def journal_note(entry, refs=None):
        """Per-branch note: mode name plus the raw drafts that produced the result. `entry` is
        (mode id, template); the mode id (never the question) also goes to a variable for «Report this run»."""
        mode, template = entry
        uid, mid = new_uuid(), new_uuid()
        return [act_text(text_token(template, refs or {}), uid),
                act_set_variable(JOURNAL_EXTRA, uid, 'Text'),
                act_text(text_token(REPORT_MODES.get(mode, REPORT_MODES[None])), mid),
                act_set_variable(MODE_VAR, mid, 'Text')]

    def remember_answer(src_uid, src_name):
        """Duo 6.1: the first LAST_ANSWER_CHARS characters of what Duo just put into the clipboard go to a small
        file next to the journal, right after each clipboard write (before any screen that waits for the person or
        any further AI call, so a run cut off later still leaves the file in step with the clipboard). On the next
        run a clipboard whose first LAST_ANSWER_CHARS characters are the same text is Duo's own answer, not a new
        question, and is NOT put into the question field (one «Done» would otherwise spend 2–4 messages on it)."""
        cut, txt, save = new_uuid(), new_uuid(), new_uuid()
        return [act_first_chars(src_uid, src_name, LAST_ANSWER_CHARS, cut),
                act_text(text_token('{M}', {'M': (cut, 'Matches')}), txt),
                act_save_file(L['files.last_answer'], txt, save)]

    def keep_gpt(src_uid, src_name, note=None):
        """D-98: ChatGPT's answer goes to the clipboard BEFORE the next Claude call. When Claude's own app throws
        (on device 28.10: «You have reached your current Claude message limit…»), iOS stops the whole shortcut with a
        system alert — Shortcuts has no built-in try/catch or «continue on error» for an app action (x-error of a
        shortcuts:// x-callback-url only opens another URL after the run has ended), so the «Claude did not answer» menu (made for an
        EMPTY answer) is never reached and the answer ChatGPT already gave would be lost. Now it is in the clipboard
        and the step's notification says so. D-100: it is no longer also remembered as Duo's own (that was one more
        «Save File», one more permission window on the first run); when the run goes on, the tail's clipboard write
        replaces it and is remembered there. No extra screen, tap or message; only when there is an answer. `note`: that step's own notification; the
        clipboard line goes FIRST (a banner may cut a long text); with no note one notification with that line alone."""
        txt, g = new_uuid(), new_uuid()
        kept = L['notify.gpt_kept']
        return [act_text(text_token('{A}', {'A': (src_uid, src_name)}), txt),
                *if_output_text(g, txt, 'Text'),
                act_clipboard(attachment(txt, 'Text')),
                act_notify(kept + '\n' + note if note else kept),
                *([if_else(g), act_notify(note)] if note else []),
                if_close(g)]

    def recipes_menu(group, title):
        """Recipes: a ready task → the question box opens pre-filled with its wording (Duo runs itself with that
        text as its input, the same way the Share Sheet does), the person edits it and picks a mode."""
        items, out = L['menu.recipes_items'], [menu_open(group, title, L['menu.recipes_items'])]
        for i, item in enumerate(items):
            uid = new_uuid()
            out += [menu_case(group, item),
                    act_text(text_token(L['menu.recipes_texts'][i]), uid),
                    act_run_self(RELEASE_NAME, uid, 'Text'),
                    {'WFWorkflowActionIdentifier': 'is.workflow.actions.exit', 'WFWorkflowActionParameters': {}}]
        return out + [menu_close(group)]

    # --- Critique
    # --- Debate until agreement (see argue_round below)
    ar_open, ar_gpt, ar_log0, ar_get, ar_prompt, ar_verdict, ar_out, ar_log_final = ids(8)
    ar_gpt2, ar_open_get, ar_qtext, ar_lsave0, ar_qsave, g_aretry = ids(6)
    ARGUE_OPEN, ARGUE_ROUNDS, ARGUE_REPLY = 'PolyArgueOpening', 'PolyArgueRounds', 'PolyArgueReply'
    (ar_empty, ar_zero0, ar_rf, ar_rdate, ar_rnow, ar_rage, ar_lf, ar_nf, ar_zero, ar_zsave, ar_clear,
     ar_csave) = ids(12)
    g_a1, g_a2, g_a3, g_aopen = ids(4)
    ar_rft, ar_qclr, ar_qclr_save = ids(3)
    ARGUE_LOG = L['variables.argue_log']
    # --- Advisor
    ad_prompt, ad_claude = ids(2)
    # --- Side by side
    sb_wrap, sb_gpt, sb_claude, sb_join = ids(4)
    # --- Synthesis, Claude anchors / ChatGPT anchors
    sc_wrap, sc_gpt, sc_claude, sc_prompt, sc_final = ids(5)
    sg_wrap, sg_gpt, sg_claude, sg_prompt, sg_final = ids(5)
    # --- Auto
    au_prompt, au_gpt, au_text = ids(3)
    # --- Decision
    de_fast, de_gpt, de_caution, de_claude, de_referee, de_final = ids(6)
    # --- Dispute map
    dm_wrap, dm_gpt, dm_claude, dm_prompt, dm_final = ids(5)
    # --- Debate
    db_wrap, db_draft, db_crit_prompt, db_crit, db_rev_prompt, db_rev, db_judge_prompt, db_judge = ids(8)
    # --- Clarify
    cl_prompt, cl_gpt, cl_ask, cl_final_prompt, cl_final = ids(5)
    # --- Image: sketches only / sketches + judge
    i1_brief, i1_gpt, i1_claude, i1_html, i1_file, i1_codes = ids(6)
    i2_brief, i2_gpt, i2_claude, i2_html, i2_file, i2_raw, i2_judge_prompt, i2_judge, i2_codes = ids(9)
    # --- Delta
    dl_wrap, dl_claude, dl_prompt, dl_gpt, dl_join = ids(5)
    # --- Help
    hp_text, = ids(1)
    # --- Tail
    tl_date, tl_extra, tl_result, tl_entry = ids(4)
    # --- The one-time word about the PC version
    pc_get, pc_text, pc_save = ids(3)
    RETRY_SKIP.update((ar_gpt, ar_gpt2))   # only calls with their own retry; Critique ⇄, Delta, revision, ratify get the general one

    def argue_round(n):
        """One round of «Debate until agreement»: Claude objects, ChatGPT answers. Each half runs only
        while nobody has conceded — the debate log does not yet contain the marker."""
        g_obj, g_rep, g_gp = ids(3)
        get1, pr1, cl1, get2, add1, get3, pr2, gp2, get4, add2, op_get = ids(11)
        RETRY_SKIP.add(gp2)
        sv_get, sv_text, sv_save = ids(3)
        rnd = str(n)
        rd_get, rd_text, rd_save, g_rd, rd_num = ids(5)
        return [
            # skipped when this round was already finished before an interruption (rounds_done is 0…n-1 → run)
            # the saved count is text («0»…«3», or a file's text): the Number action turns it into a real number before
            # the «between» test. Not checked on device: on an iPhone, resume a cut-off debate and see that finished
            # rounds are not asked again.
            act_get_variable(ARGUE_ROUNDS, rd_get),
            act_number(rd_get, 'Variable', rd_num),
            if_output(g_rd, rd_num, 'Number', 1003, WFNumberValue=0, WFAnotherNumber=n - 1),
            if_contains(g_obj, ARGUE_LOG, ARGUE_MARKER),
            if_else(g_obj),
            act_get_variable(ARGUE_LOG, get1),
            *([act_get_variable(ARGUE_OPEN, op_get)] if n == 1 else []),
            # round 1: Claude states its OWN position on the question without seeing side A's opening
            # (blind first, same number of messages); from round 2 on the sides see each other
            # round 1: ChatGPT's opening goes to the clipboard first, see keep_gpt. The opening itself, not the log
            # (whose side-A header is there even when ChatGPT sent nothing); a resumed debate has no opening in memory
            # and copies nothing
            *(keep_gpt(op_get, 'Variable', L['notify.argue_blind'].replace('{N}', rnd)) if n == 1 else
              [act_notify(L['notify.argue_object'].replace('{N}', rnd))]),
            (act_text(text_token(L.prompt('argue-1-open-b'), Q), pr1) if n == 1 else
             act_text(text_token(L.prompt('argue-2-object').replace('{ROUND}', rnd),
                                 {**QUESTION, 'LOG': (get1, 'Variable')}), pr1)),
            act_claude(text_token('{P}', {'P': (pr1, 'Text')}), cl1),
            act_get_variable(ARGUE_LOG, get2),
            act_text(text_token('{L}\n\n' + L['output.argue_side_b_round'].replace('{N}', rnd) + '\n{B}',
                                {'L': (get2, 'Variable'), 'B': (cl1, 'Ask Claude')}), add1),
            act_set_variable(ARGUE_LOG, add1, 'Text'),
            if_contains(g_rep, ARGUE_LOG, ARGUE_MARKER),
            if_else(g_rep),
            act_notify(L['notify.argue_reply'].replace('{N}', rnd)),
            act_get_variable(ARGUE_LOG, get3),
            act_text(text_token(L.prompt('argue-3-reply').replace('{ROUND}', rnd),
                                {**QUESTION, 'LOG': (get3, 'Variable')}), pr2),
            act_gpt(text_token('{P}', {'P': (pr2, 'Text')}), gp2),
            # a round has no retry (it is an answer to an answer); if ChatGPT returns nothing, the log is left as it
            # was instead of getting an empty «side A» entry, and the debate goes on to the next step
            act_set_variable(ARGUE_REPLY, gp2, 'Ask ChatGPT'),
            *if_text(g_gp, ARGUE_REPLY),
            act_get_variable(ARGUE_LOG, get4),
            act_text(text_token('{L}\n\n' + L['output.argue_side_a_round'].replace('{N}', rnd) + '\n{A}',
                                {'L': (get4, 'Variable'), 'A': (gp2, 'Ask ChatGPT')}), add2),
            act_set_variable(ARGUE_LOG, add2, 'Text'),
            if_close(g_gp),
            if_close(g_rep),
            if_close(g_obj),
            act_text(text_token(rnd), rd_text),
            act_set_variable(ARGUE_ROUNDS, rd_text, 'Text'),
            if_close(g_rd),
        ]

    def critique_block(pre=(), rule_uid=None):
        """Critique, blind scheme (D-41), 3 messages as before: ChatGPT answers the wrapped question; Claude answers
        the SAME wrapped question on its own, without seeing ChatGPT's answer; then Claude compares both in one
        message (critique-blind.txt: three blocks «matched independently / did not match / what to check yourself»,
        then the final answer). `pre` runs first; `rule_uid` (an action whose text is the person's own one-line
        instruction to the checker, «My mode») is put in front of the comparing prompt (step 3)."""
        (cr_empty0, cr_empty1, cr_rf, cr_rdate, cr_rnow, cr_rage, cr_ra, cr_rb, cr_rb_t, cr_rget, cr_gpt2, cr_qtext,
         cr_qsave, cr_atext, cr_asave, cr_aget, cr_gpt_f, cr_len, cr_cut, cr_claude2, cr_claude_f, cr_clear,
         cr_clear_save, cr_num0, cr_numfin) = ids(29 - 4)
        cr_kget, = ids(1)
        (cr_oget, cr_own, cr_own2, cr_own_t, cr_own_save, cr_own_get,
         cr_own_f, cr_bclr, cr_bclr_save, cr_rft, cr_qclr, cr_qclr_save) = ids(12)
        g_r1, g_r2, g_r3, g_need, g_retry, g_save, g_long, g_cretry, g_cok = ids(9)
        g_own, g_oretry, g_osave, g_n1, g_n2, g_cstart, g_rbt, g_rag = ids(8)
        cr_wrap, cr_gpt, cr_prompt, cr_claude = ids(4)
        RETRY_SKIP.update((cr_gpt, cr_gpt2))
        rule_prefix = 'Extra instruction from the user for this check (apply it): {RULE}\n\n' if rule_uid else ''
        rule_ref = {'RULE': (rule_uid, 'Variable')} if rule_uid else {}

        def number_pass(src_var_uid, other_var):
            """Every number of the answer `src_var_uid` (a Get Variable output) that does NOT stand, as a whole
            number, in the other answer `other_var` is added to NUMS_VAR — once (checked against the list too).
            Whole-number match, not substring: «7» is not «17». Not checked on device: Match Text with a regex whose
            pattern holds a token, Replace Text, Repeat with Each, the «Repeat Item» variable."""
            nums, item, esc, other, g_rep, g_miss, g_dup = ids(7)
            m_other, m_list, lst, add_get, add_txt = ids(5)
            return [
                act_first_match(src_var_uid, 'Variable', r'\d+(?:[.,:/-]\d+)*', nums),
                repeat_open(g_rep, nums, 'Matches'),
                act_get_variable('Repeat Item', item),
                act_replace_text(item, 'Variable', '.', '\\.', esc),   # a dot in the number is a dot, not «any char»
                act_get_variable(other_var, other),
                act_match_number(other, 'Variable', esc, 'Updated Text', m_other),
                if_output(g_miss, m_other, 'Matches', 101),
                act_get_variable(NUMS_VAR, lst),
                act_match_number(lst, 'Variable', esc, 'Updated Text', m_list),
                if_output(g_dup, m_list, 'Matches', 101),
                act_get_variable(NUMS_VAR, add_get),
                act_text(text_token('{N} {I}', {'N': (add_get, 'Variable'), 'I': (item, 'Variable')}), add_txt),
                act_set_variable(NUMS_VAR, add_txt, 'Text'),
                if_close(g_dup),
                if_close(g_miss),
                repeat_close(g_rep),
            ]
        return [
            *pre,
            # D-100: no drafts. Writing them (question, ChatGPT's answer, Claude's own answer, then emptying them) was
            # six «Save File» actions, and iOS asks for each one on the first run, «Always Allow» or not: with the
            # clipboard and the journal that was ~14 permission windows (Duo 5: ~6). The resume of a cut-off run
            # (U-05) went with them; the answer is no longer lost to Claude's limit anyway (keep_gpt, D-98).
            # Emptied with «Nothing», not with an empty Text (an empty Text «has any value»).
            *clear_variable(GPT_VAR),
            *clear_variable(OWN_VAR),
            act_notify(L['notify.critique_start']),
            # the wrapped question is needed by step 1 AND step 2, so it is built outside both
            act_text(text_token(L.prompt('wrap'), Q), cr_wrap),
            # ---- Step 1: ChatGPT
            act_gpt(text_token('{P}', {'P': (cr_wrap, 'Text')}), cr_gpt),
            act_set_variable(GPT_VAR, cr_gpt, 'Ask ChatGPT'),
            # an empty ChatGPT answer (often a false «logged out» or a dropped call): wait 3 s, ask once more
            *if_text(g_retry, GPT_VAR, present=False),
            act_delay(3),
            act_gpt(text_token('{P}', {'P': (cr_wrap, 'Text')}), cr_gpt2),
            act_set_variable(GPT_VAR, cr_gpt2, 'Ask ChatGPT'),
            if_close(g_retry),
            # ---- Step 2: Claude answers the same wrapped question WITHOUT ChatGPT's answer (blind). An empty answer
            # is retried once; if it stays empty, step 3 works with ChatGPT's answer alone (the prompt says how).
            act_get_variable(GPT_VAR, cr_kget),
            *keep_gpt(cr_kget, 'Variable', L['notify.critique_blind']),
            act_claude(text_token('{P}', {'P': (cr_wrap, 'Text')}), cr_own),
            act_set_variable(OWN_VAR, cr_own, 'Ask Claude'),
            *if_text(g_oretry, OWN_VAR, present=False),
            act_notify(L['notify.claude_retry']),
            act_claude(text_token('{P}', {'P': (cr_wrap, 'Text')}), cr_own2),
            act_set_variable(OWN_VAR, cr_own2, 'Ask Claude'),
            if_close(g_oretry),
            # ---- Step 3: Claude compares both. Numbers that stand in only one of the two answers are found by rule,
            # not by Claude's attention, and handed over as data (not checked on device: Match Text with a regex,
            # Repeat with Each, «does not contain» = condition 999, the «Repeat Item» variable). Only when both
            # answers exist: with one of them missing every number would be «only in one».
            act_get_variable(GPT_VAR, cr_gpt_f),
            act_get_variable(OWN_VAR, cr_own_f),
            *clear_variable(NUMS_VAR),
            *if_text(g_n1, OWN_VAR),
            *if_text(g_n2, GPT_VAR),
            *number_pass(cr_gpt_f, OWN_VAR),
            *number_pass(cr_own_f, GPT_VAR),
            if_close(g_n2),
            if_close(g_n1),
            act_get_variable(NUMS_VAR, cr_numfin),
            act_text(text_token(rule_prefix + L.prompt('critique-blind'),
                                {**QUESTION, 'GPT_ANSWER': (cr_gpt_f, 'Variable'),
                                 'CLAUDE_OWN': (cr_own_f, 'Variable'), 'NUMS': (cr_numfin, 'Variable'),
                                 **rule_ref}), cr_prompt),
            act_set_variable(CHECK_VAR, cr_prompt, 'Text'),   # U-06: what the three fallbacks send
            act_notify(L['notify.critique_step3']),
            # ---- A long request (U-08): one notification, not a window; and if Claude returns nothing, one
            # automatic retry with the request cut to the first LONG_TEXT characters.
            act_count_chars(cr_prompt, 'Text', cr_len),
            if_output(g_long, cr_len, 'Count', 2, WFNumberValue=LONG_TEXT),
            act_notify(L['notify.long_text']),
            if_close(g_long),
            act_claude(text_token('{P}', {'P': (cr_prompt, 'Text')}), cr_claude),
            act_set_variable(CLAUDE_VAR, cr_claude, 'Ask Claude'),
            *if_text(g_cretry, CLAUDE_VAR, present=False),
            act_notify(L['notify.claude_retry']),
            act_first_chars(cr_prompt, 'Text', LONG_TEXT, cr_cut),
            act_claude(text_token('{P}', {'P': (cr_cut, 'Matches')}), cr_claude2),
            act_set_variable(CLAUDE_VAR, cr_claude2, 'Ask Claude'),
            if_close(g_cretry),
            act_get_variable(CLAUDE_VAR, cr_claude_f),
            # RESULT is set only when step 3 (CLAUDE_VAR, not a wrapped text) has an answer; otherwise RESULT stays
            # empty and the shared tail offers the «Claude did not answer» menu. The shared tail copies RESULT to the
            # clipboard (D-100: one clipboard action less, one permission window less on the first run).
            *if_text(g_cok, CLAUDE_VAR),
            act_set_variable(RESULT, cr_claude_f, 'Variable'),
            if_close(g_cok),
            *journal_note(('critique', L['journal.critique']), {'X': (cr_gpt_f, 'Variable')}),
        ]

    def claude_down_menu():
        """U-06: Claude gave nothing even after the retry. Only in this case (and only where a check request was
        made — Critique and My mode) the person gets three ways to still have the answer checked. The usual path
        never sees it. Not checked on device: Use Model's reach on iPhones without Apple Intelligence (it
        returns nothing; the run ends as before), and the key chain's long run time."""
        u = new_uuid
        g_chk, g_down, g_key = u(), u(), u()
        c_get, kf, kvar, kprompt, third_get, apple_p, apple, apple_get, man_get = (u() for _ in range(9))
        items = L['menu.claude_down_items']
        # items[0] opens the Claude app's App Store page (no Claude app, or signed out); items[1:] are the three
        # ways to still have the answer checked, in the order below
        # A light chain, so Duo stays small (a big shortcut opens slowly on an iPhone): the free keys only, found by
        # their prefix, ONE model each (the first in models.json); paid keys and the other models are Trio's job.
        free = ('provider.nvidia', 'provider.gemini', 'provider.openrouter', 'provider.groq')
        light = [(k, url, rx, models[:1], mt) for (k, url, rx, models, mt) in build_trio.PROVIDERS if k in free]
        third = build_trio.third_voice(T, TV, kprompt, kvar, keys_name='Text', providers=light, light=True,
                                       search=False)   # no Gemini web-search call on the emergency path
        def deliver():
            # only the clipboard: the one Quick Look comes from the shared tail, after this menu, if RESULT has text
            return [act_clipboard(variable(RESULT))]
        return [
            act_get_variable(CHECK_VAR, c_get),
            if_has_value(g_chk, CHECK_VAR),
            menu_open(g_down, L['menu.claude_down_title'], items),
            # 0. no Claude app (or signed out): open its App Store page; nothing is sent, the run ends as before
            menu_case(g_down, items[0]),
            {'WFWorkflowActionIdentifier': 'is.workflow.actions.openurl',
             'WFWorkflowActionParameters': {'WFInput': text_token('https://apps.apple.com/app/id6473753684'),
                                            'Show-WFInput': True}},
            # 1. a free key saved in poly-key.txt: Trio's provider chain, reused from build_trio
            menu_case(g_down, items[1]),
            act_get_file(T['files.key'], kf),
            act_set_variable(TV['key_file'], kf, 'File'),
            if_has_value(g_key, TV['key_file']),
            act_text(text_token('{F}', {'F': (kf, 'File')}), kvar),
            act_text(text_token('{P}', {'P': (c_get, 'Variable')}), kprompt),
            *third,
            act_get_variable(TV['third'], third_get),
            act_set_variable(RESULT, third_get, 'Variable'),
            *deliver(),
            if_else(g_key),
            act_notify(L['notify.no_key_file']),
            if_close(g_key),
            # 2. this iPhone (Apple Intelligence, iPhone 15 Pro and newer — the label says so)
            menu_case(g_down, items[2]),
            act_text(text_token('{P}', {'P': (c_get, 'Variable')}), apple_p),
            build_trio.act_use_model(apple_p, apple),
            act_set_variable(RESULT, apple, 'Response'),
            *deliver(),
            # 3. by hand: the check request goes to the clipboard
            menu_case(g_down, items[3]),
            act_get_variable(CHECK_VAR, man_get),
            act_clipboard(attachment(man_get, 'Variable')),
            *remember_answer(man_get, 'Variable'),
            act_notify(L['notify.manual_copied']),
            menu_close(g_down),
            if_close(g_chk),
        ]

    actions = [
        act_comment(L['comment.main']),

        # ---- Once, on the very first run: what the next minute looks like. Right after it the iPhone asks for
        # permission 4–6 times and an unanswered request vanishes in seconds, so the person is told before, not
        # after. A marker file next to the journal (iCloud Drive → Shortcuts) says it was shown, so it never comes
        # back; a missing file is not an error. The laptop/PC paragraph lives on the help screen.
        act_get_file(L['files.pc_notice'], pc_get),
        act_set_variable(L['variables.pc_notice_seen'], pc_get, 'File'),
        if_has_value(g_notice, L['variables.pc_notice_seen']),
        if_else(g_notice),
        act_alert(L['alert.first_run_title'], L['alert.first_run_body']),
        act_text(text_token(L['alert.first_run_body']), pc_text),
        act_save_file(L['files.pc_notice'], pc_text, pc_save),
        if_close(g_notice),

        # One-tap start (U-16): the question field is pre-filled with the Share input, else with the clipboard,
        # so Action Button / Back Tap / Lock Screen / Siri need no typing. The field is still shown (the person
        # may edit or clear it; clearing it hits the empty-question guard below) — no screen or tap is added.
        # `is.workflow.actions.getclipboard` is standard; its output is called «Clipboard» (not checked on device).
        # The clipboard counts only when it holds at least three words: a password, a one-time code or a lone
        # link must never land in the question field, where a busy person would send it on with one tap.
        *clear_variable(START_VAR),
        # Shortcut Input first, the clipboard ONLY when there is none (so a Share-Sheet run never reads, or asks
        # permission for, the clipboard). Share: «Get Text from Input» first (text, a URL, an article, a text PDF); a
        # result that is only a picture's file name counts as no text; only then «Get Images from Input» → Extract
        # Text from Image. «Get Images from Input» is NOT used as a type test: it also pulls pictures out of web
        # pages and PDFs, which would send an article to OCR. Not checked on a device: what «Get Text from Input»
        # returns for a bare image (a file name, or nothing); the file-name guard covers the first case.
        if_shortcut_input(g_start),
        act_detect('text', SHARE_INPUT, st_dtext),
        act_set_variable(START_VAR, st_dtext, 'Text'),
        act_first_match(st_dtext, 'Text', r'(?i)^\s*\S+\.(?:jpe?g|png|heic|heif|gif|webp|tiff?|bmp)\s*$', st_fn),
        if_output(g_fn, st_fn, 'Matches', 100),
        *clear_variable(START_VAR),
        if_close(g_fn),
        *if_text(g_nostart, START_VAR, present=False),
        act_detect('images', SHARE_INPUT, st_img),
        if_output(g_img, st_img, 'Images', 100),
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.extracttextfromimage',
         'WFWorkflowActionParameters': {'WFImage': attachment(st_img, 'Images'), 'UUID': st_ocr}},
        act_set_variable(START_VAR, st_ocr, 'Text from Image'),
        if_close(g_img),
        if_close(g_nostart),
        if_else(g_start),
        act_clipboard_get(st_clip),
        act_first_match(st_clip, 'Clipboard', r'\S+\s+\S+\s+\S+', st_words),
        if_output(g_words, st_words, 'Matches', 100),
        act_set_variable(START_VAR, st_clip, 'Clipboard'),
        # Duo 6.1: Duo leaves its answer in the clipboard. If the person copied nothing new, that answer must not
        # come back as the next question: when the clipboard's first LAST_ANSWER_CHARS characters are the same text
        # as the start of Duo's last clipboard write (files.last_answer, see remember_answer; both sides cut by the
        # same Match Text → Text), the field stays empty. «Is», not «contains»: a text that starts differently, or one
        # that merely includes a short answer such as «Yes.», is still offered; a text that begins with the same 200
        # characters (a Duo answer with the person's lines added after it) counts as Duo's and must be pasted. A
        # missing file (first run) is no value, and the clipboard is used as before. Same screens, same taps.
        act_get_file(L['files.last_answer'], st_last),
        act_text(text_token('{F}', {'F': (st_last, 'File')}), st_last_t),
        if_output(g_last, st_last_t, 'Text', 100),
        act_first_chars(st_clip, 'Clipboard', LAST_ANSWER_CHARS, st_ccut),
        act_text(text_token('{M}', {'M': (st_ccut, 'Matches')}), st_ctext),
        if_output(g_mine, st_ctext, 'Text', 4, WFConditionalActionString=text_token('{F}', {'F': (st_last_t, 'Text')})),
        *clear_variable(START_VAR),
        if_close(g_mine),
        if_close(g_last),
        if_close(g_words),
        if_close(g_start),
        act_get_variable(START_VAR, st_get),
        act_ask(L['ask.question'], question, default_from=(st_get, 'Variable')),
        # An empty question would spend 1–8 messages on nothing, so no AI is asked. Instead of a dead end the person
        # gets the Recipes (ready tasks): «I don't know what to ask» is one tap from a recipe; the menu's own Cancel
        # ends the run, as the old stop did. Recipes run Duo again with their wording in the question field.
        if_output(g_blank, question, 'Provided Input', 101),
        *recipes_menu(g_rec0, L['menu.empty_title']),
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.exit', 'WFWorkflowActionParameters': {}},
        if_close(g_blank),
        menu_open(g_main, L['menu.main_title'], MAIN),

        # ---- Critique: ChatGPT answers, Claude verifies and finalizes
        menu_case(g_main, MAIN[0]),
        *critique_block(),

        # ---- Debate until agreement: ChatGPT takes a side, Claude objects, ChatGPT answers… up to three
        # rounds; a side that is convinced starts its reply with the marker and the debate stops there.
        # Then Claude, as a neutral recorder: where they agreed / what is still disputed / what you decide.
        menu_case(g_main, MAIN[1]),
        act_notify(L['notify.argue_start']),
        # D-100: no drafts (each «Save File» is one more permission window on the first run), so no resume either
        *clear_variable(ARGUE_LOG),
        act_text(text_token('0'), ar_zero0),
        act_set_variable(ARGUE_ROUNDS, ar_zero0, 'Text'),
        act_text(text_token(L.prompt('argue-1-open'), Q), ar_open),
        act_gpt(text_token('{P}', {'P': (ar_open, 'Text')}), ar_gpt),
        act_set_variable(ARGUE_OPEN, ar_gpt, 'Ask ChatGPT'),
        # an empty opening answer: wait 3 s and ask once more (U-05)
        *if_text(g_aretry, ARGUE_OPEN, present=False),
        act_delay(3),
        act_gpt(text_token('{P}', {'P': (ar_open, 'Text')}), ar_gpt2),
        act_set_variable(ARGUE_OPEN, ar_gpt2, 'Ask ChatGPT'),
        if_close(g_aretry),
        act_get_variable(ARGUE_OPEN, ar_open_get),
        act_text(text_token(L['output.argue_side_a'] + '\n{A}', {'A': (ar_open_get, 'Variable')}), ar_log0),
        act_set_variable(ARGUE_LOG, ar_log0, 'Text'),
        *argue_round(1), *argue_round(2), *argue_round(3),
        act_notify(L['notify.argue_verdict']),
        act_get_variable(ARGUE_LOG, ar_get),
        act_text(text_token(L.prompt('argue-4-verdict'),
                            {**QUESTION, 'LOG': (ar_get, 'Variable')}), ar_prompt),
        act_claude(text_token('{P}', {'P': (ar_prompt, 'Text')}), ar_verdict),
        act_get_variable(ARGUE_LOG, ar_log_final),
        act_text(text_token(L['output.argue'], {'V': (ar_verdict, 'Ask Claude'),
                                                'L': (ar_log_final, 'Variable')}), ar_out),
        act_set_variable(RESULT, ar_out, 'Text'),
        *journal_note(('argue', L['journal.argue'])),

        # ---- Advisor: Claude reviews the user's own text without rewriting it
        menu_case(g_main, MAIN[2]),
        act_notify(L['notify.advisor_start']),
        act_text(text_token(L.prompt('advisor'), Q), ad_prompt),
        act_claude(text_token('{P}', {'P': (ad_prompt, 'Text')}), ad_claude),
        act_set_variable(RESULT, ad_claude, 'Ask Claude'),
        *journal_note(('advisor', L['journal.advisor'])),

        # ---- Side by side: both answer independently, answers shown together
        menu_case(g_main, MAIN[3]),
        act_notify(L['notify.survey_start']),
        act_text(text_token(L.prompt('wrap'), Q), sb_wrap),
        act_gpt(text_token('{P}', {'P': (sb_wrap, 'Text')}), sb_gpt),
        *keep_gpt(sb_gpt, 'Ask ChatGPT'),
        act_claude(text_token('{P}', {'P': (sb_wrap, 'Text')}), sb_claude),
        act_text(text_token(L['output.survey'],
                            {'G': (sb_gpt, 'Ask ChatGPT'), 'C': (sb_claude, 'Ask Claude')}), sb_join),
        act_set_variable(RESULT, sb_join, 'Text'),
        *journal_note(('survey', L['journal.survey'])),

        # ---- Synthesis: both answer blind, then one of them anchors the assembly
        menu_case(g_main, MAIN[4]),
        menu_open(g_anchor, L['menu.anchor_title'], L['menu.anchor_items']),

        menu_case(g_anchor, L['menu.anchor_items'][0]),
        act_notify(L['notify.synthesis_claude_start']),
        act_text(text_token(L.prompt('wrap'), Q), sc_wrap),
        act_gpt(text_token('{P}', {'P': (sc_wrap, 'Text')}), sc_gpt),
        *keep_gpt(sc_gpt, 'Ask ChatGPT'),
        act_claude(text_token('{P}', {'P': (sc_wrap, 'Text')}), sc_claude),
        act_text(text_token(L.prompt('synthesis-anchor-claude'),
                            {**QUESTION, 'GPT_ANSWER': (sc_gpt, 'Ask ChatGPT'),
                             'CLAUDE_ANSWER': (sc_claude, 'Ask Claude')}), sc_prompt),
        act_claude(text_token('{P}', {'P': (sc_prompt, 'Text')}), sc_final),
        act_set_variable(RESULT, sc_final, 'Ask Claude'),
        *journal_note(('synthesis_claude', L['journal.synthesis_claude']),
                      {'X': (sc_gpt, 'Ask ChatGPT'), 'Y': (sc_claude, 'Ask Claude')}),

        menu_case(g_anchor, L['menu.anchor_items'][1]),
        act_notify(L['notify.synthesis_gpt_start']),
        act_text(text_token(L.prompt('wrap'), Q), sg_wrap),
        act_gpt(text_token('{P}', {'P': (sg_wrap, 'Text')}), sg_gpt),
        *keep_gpt(sg_gpt, 'Ask ChatGPT'),
        act_claude(text_token('{P}', {'P': (sg_wrap, 'Text')}), sg_claude),
        act_text(text_token(L.prompt('synthesis-anchor-gpt'),
                            {**QUESTION, 'GPT_ANSWER': (sg_gpt, 'Ask ChatGPT'),
                             'CLAUDE_ANSWER': (sg_claude, 'Ask Claude')}), sg_prompt),
        act_claude(text_token('{P}', {'P': (sg_prompt, 'Text')}), sg_final),
        act_set_variable(RESULT, sg_final, 'Ask Claude'),
        *journal_note(('synthesis_gpt', L['journal.synthesis_gpt']),
                      {'X': (sg_gpt, 'Ask ChatGPT'), 'Y': (sg_claude, 'Ask Claude')}),
        menu_close(g_anchor),

        # ---- Auto: one classification call recommends the mode to use
        menu_case(g_main, MAIN[5]),
        act_notify(L['notify.auto_start']),
        act_text(text_token(L.prompt('auto-router'), Q), au_prompt),
        service_call(au_prompt, au_gpt)[0],
        act_text(text_token(L['output.auto'], {'R': (au_gpt, service_call(au_prompt, au_gpt)[1])}), au_text),
        act_set_variable(RESULT, au_text, 'Text'),
        *journal_note(('auto', L['journal.auto'])),

        # ---- More…: the less frequent modes plus built-in help
        menu_case(g_main, MAIN[6]),
        menu_open(g_extra, L['menu.extra_title'], EXTRA),

        # ---- Decision: fast view, cautious view, referee
        menu_case(g_extra, EXTRA[0]),
        act_notify(L['notify.decision_start']),
        act_text(text_token(L.prompt('decision-1-fast'), Q), de_fast),
        act_gpt(text_token('{P}', {'P': (de_fast, 'Text')}), de_gpt),
        *keep_gpt(de_gpt, 'Ask ChatGPT', L['notify.decision_step2']),
        act_text(text_token(L.prompt('decision-2-cautious'), Q), de_caution),
        act_claude(text_token('{P}', {'P': (de_caution, 'Text')}), de_claude),
        act_notify(L['notify.decision_step3']),
        act_text(text_token(L.prompt('decision-3-referee'),
                            {**QUESTION, 'FAST': (de_gpt, 'Ask ChatGPT'),
                             'CAUTIOUS': (de_claude, 'Ask Claude')}), de_referee),
        act_claude(text_token('{P}', {'P': (de_referee, 'Text')}), de_final),
        act_set_variable(RESULT, de_final, 'Ask Claude'),
        *journal_note(('decision', L['journal.decision']),
                      {'X': (de_gpt, 'Ask ChatGPT'), 'Y': (de_claude, 'Ask Claude')}),

        # ---- Dispute map: where the two agree, where they don't, what to verify
        menu_case(g_extra, EXTRA[1]),
        act_notify(L['notify.disputemap_start']),
        act_text(text_token(L.prompt('wrap'), Q), dm_wrap),
        act_gpt(text_token('{P}', {'P': (dm_wrap, 'Text')}), dm_gpt),
        *keep_gpt(dm_gpt, 'Ask ChatGPT'),
        act_claude(text_token('{P}', {'P': (dm_wrap, 'Text')}), dm_claude),
        act_text(text_token(L.prompt('dispute-map'),
                            {**QUESTION, 'GPT_ANSWER': (dm_gpt, 'Ask ChatGPT'),
                             'CLAUDE_ANSWER': (dm_claude, 'Ask Claude')}), dm_prompt),
        act_claude(text_token('{P}', {'P': (dm_prompt, 'Text')}), dm_final),
        act_set_variable(RESULT, dm_final, 'Ask Claude'),
        *journal_note(('disputemap', L['journal.disputemap']),
                      {'X': (dm_gpt, 'Ask ChatGPT'), 'Y': (dm_claude, 'Ask Claude')}),

        # ---- Debate: draft, opponent, revision, judge
        menu_case(g_extra, EXTRA[2]),
        act_notify(L['notify.debate_start']),
        act_text(text_token(L.prompt('wrap'), Q), db_wrap),
        act_gpt(text_token('{P}', {'P': (db_wrap, 'Text')}), db_draft),
        *keep_gpt(db_draft, 'Ask ChatGPT', L['notify.debate_step2']),
        # blind first: Claude answers the question on its own (it does not see ChatGPT's draft); only then
        # ChatGPT sees both and revises, and the judge sees both originals and the revision — still 4 messages
        act_claude(text_token('{P}', {'P': (db_wrap, 'Text')}), db_crit),
        act_notify(L['notify.debate_step3']),
        act_text(text_token(L.prompt('debate-2-compare'),
                            {**QUESTION, 'DRAFT': (db_draft, 'Ask ChatGPT'),
                             'OTHER': (db_crit, 'Ask Claude')}), db_rev_prompt),
        act_gpt(text_token('{P}', {'P': (db_rev_prompt, 'Text')}), db_rev),
        act_notify(L['notify.debate_step4']),
        act_text(text_token(L.prompt('debate-3-judge-compare'),
                            {**QUESTION, 'DRAFT': (db_draft, 'Ask ChatGPT'),
                             'OTHER': (db_crit, 'Ask Claude'),
                             'ANSWER': (db_rev, 'Ask ChatGPT')}), db_judge_prompt),
        act_claude(text_token('{P}', {'P': (db_judge_prompt, 'Text')}), db_judge),
        act_set_variable(RESULT, db_judge, 'Ask Claude'),
        *journal_note(('debate', L['journal.debate']),
                      {'X': (db_draft, 'Ask ChatGPT'), 'Y': (db_crit, 'Ask Claude'),
                       'Z': (db_rev, 'Ask ChatGPT')}),

        # ---- Clarify: ask the user what's missing, then answer
        menu_case(g_extra, EXTRA[3]),
        act_notify(L['notify.clarify_step1']),
        act_text(text_token(L.prompt('clarify-1-questions'), Q), cl_prompt),
        service_call(cl_prompt, cl_gpt)[0],
        act_ask(text_token('{Q}' + L['ask.clarify_suffix'], {'Q': (cl_gpt, service_call(cl_prompt, cl_gpt)[1])}),
                cl_ask, default=L['ask.clarify_default']),
        act_notify(L['notify.clarify_step2']),
        act_text(text_token(L.prompt('clarify-2-final'),
                            {**Q, 'QUESTIONS': (cl_gpt, service_call(cl_prompt, cl_gpt)[1]),
                             'USER_ANSWERS': (cl_ask, 'Provided Input')}), cl_final_prompt),
        act_claude(text_token('{P}', {'P': (cl_final_prompt, 'Text')}), cl_final),
        act_set_variable(RESULT, cl_final, 'Ask Claude'),
        *journal_note(('clarify', L['journal.clarify']),
                      {'X': (cl_gpt, service_call(cl_prompt, cl_gpt)[1]), 'Y': (cl_ask, 'Provided Input')}),

        # ---- Image: both draw SVG blind, gallery is shown, judge is optional
        menu_case(g_extra, EXTRA[4]),
        menu_open(g_image, L['menu.image_title'], L['menu.image_items']),

        menu_case(g_image, L['menu.image_items'][0]),
        act_notify(L['notify.image_step1']),
        act_text(text_token(L.prompt('image-svg-brief'), Q), i1_brief),
        act_gpt(text_token('{P}', {'P': (i1_brief, 'Text')}), i1_gpt),
        *keep_gpt(i1_gpt, 'Ask ChatGPT', L['notify.image_step2']),
        act_claude(text_token('{P}', {'P': (i1_brief, 'Text')}), i1_claude),
        act_text(text_token(IMAGE_GALLERY_HTML.replace('{TITLE}', L['output.image_html_title'])
                            .replace('{CAP_C}', L['output.image_html_claude'])
                            .replace('{CAP_G}', L['output.image_html_gpt']),
                            {'C': (i1_claude, 'Ask Claude'), 'G': (i1_gpt, 'Ask ChatGPT')}), i1_html),
        act_text(text_token(L['output.image_codes'],
                            {'C': (i1_claude, 'Ask Claude'), 'G': (i1_gpt, 'Ask ChatGPT')}), i1_codes),
        # the raw SVG code reaches the clipboard before the file is written
        act_clipboard(attachment(i1_codes, 'Text')),
        *remember_answer(i1_codes, 'Text'),
        act_save_file(L['files.image_html'], i1_html, i1_file),
        act_quick_look(attachment(i1_file, 'Saved File')),
        act_set_variable(RESULT, i1_codes, 'Text'),
        *journal_note(('image', L['journal.image'])),

        menu_case(g_image, L['menu.image_items'][1]),
        act_notify(L['notify.image_step1']),
        act_text(text_token(L.prompt('image-svg-brief'), Q), i2_brief),
        act_gpt(text_token('{P}', {'P': (i2_brief, 'Text')}), i2_gpt),
        *keep_gpt(i2_gpt, 'Ask ChatGPT', L['notify.image_step2']),
        act_claude(text_token('{P}', {'P': (i2_brief, 'Text')}), i2_claude),
        act_text(text_token(IMAGE_GALLERY_HTML.replace('{TITLE}', L['output.image_html_title'])
                            .replace('{CAP_C}', L['output.image_html_claude'])
                            .replace('{CAP_G}', L['output.image_html_gpt']),
                            {'C': (i2_claude, 'Ask Claude'), 'G': (i2_gpt, 'Ask ChatGPT')}), i2_html),
        act_text(text_token(L['output.image_codes'],
                            {'C': (i2_claude, 'Ask Claude'), 'G': (i2_gpt, 'Ask ChatGPT')}), i2_raw),
        act_clipboard(attachment(i2_raw, 'Text')),
        *remember_answer(i2_raw, 'Text'),
        act_save_file(L['files.image_html'], i2_html, i2_file),
        act_quick_look(attachment(i2_file, 'Saved File')),
        act_notify(L['notify.image_judge']),
        act_text(text_token(L.prompt('image-judge'),
                            {**QUESTION, 'SKETCH1': (i2_claude, 'Ask Claude'),
                             'SKETCH2': (i2_gpt, 'Ask ChatGPT')}), i2_judge_prompt),
        act_claude(text_token('{P}', {'P': (i2_judge_prompt, 'Text')}), i2_judge),
        act_text(text_token(L['output.image_codes_judged'],
                            {'J': (i2_judge, 'Ask Claude'), 'C': (i2_claude, 'Ask Claude'),
                             'G': (i2_gpt, 'Ask ChatGPT')}), i2_codes),
        act_set_variable(RESULT, i2_codes, 'Text'),
        *journal_note(('image', L['journal.image'])),
        menu_close(g_image),

        # ---- Delta: Claude anchors, ChatGPT returns only what it would add
        menu_case(g_extra, EXTRA[5]),
        act_notify(L['notify.delta_step1']),
        act_text(text_token(L.prompt('wrap'), Q), dl_wrap),
        act_claude(text_token('{P}', {'P': (dl_wrap, 'Text')}), dl_claude),
        act_notify(L['notify.delta_step2']),
        act_text(text_token(L.prompt('delta'),
                            {**QUESTION, 'ANCHOR': (dl_claude, 'Ask Claude')}), dl_prompt),
        act_gpt(text_token('{P}', {'P': (dl_prompt, 'Text')}), dl_gpt),
        act_text(text_token(L['output.delta'],
                            {'C': (dl_claude, 'Ask Claude'), 'G': (dl_gpt, 'Ask ChatGPT')}), dl_join),
        act_set_variable(RESULT, dl_join, 'Text'),
        *journal_note(('delta', L['journal.delta'])),

        # ---- Help: what C1 is and which mode to pick, free of AI calls
        menu_case(g_extra, EXTRA[6]),
        act_notify(L['notify.help']),
        act_text(text_token(L['help']), hp_text),
        act_set_variable(RESULT, hp_text, 'Text'),
        *journal_note(('help', L['journal.help'])),

        # ---- Recipes (also offered when the question is left empty, see above)
        menu_case(g_extra, EXTRA[7]),
        *recipes_menu(g_rec, L['menu.recipes_title']),

        # ---- Critique ⇄: Claude writes first, ChatGPT checks (texts, tone, strategy)
        menu_case(g_extra, EXTRA[8]),
        act_notify(L['notify.reverse_start']),
        act_text(text_token(L.prompt('wrap'), Q), rv_wrap),
        act_claude(text_token('{P}', {'P': (rv_wrap, 'Text')}), rv_claude),
        act_text(text_token(L.prompt('critique-reverse'),
                            {**QUESTION, 'CLAUDE_ANSWER': (rv_claude, 'Ask Claude')}), rv_prompt),
        act_notify(L['notify.critique_step2']),
        act_gpt(text_token('{P}', {'P': (rv_prompt, 'Text')}), rv_gpt),
        act_clipboard(attachment(rv_gpt, 'Ask ChatGPT')),
        *remember_answer(rv_gpt, 'Ask ChatGPT'),
        act_notify(L['notify.critique_summary']),
        act_text(text_token(L.prompt('summary-reverse'),
                            {**QUESTION, 'CLAUDE_ANSWER': (rv_claude, 'Ask Claude'),
                             'GPT_ANSWER': (rv_gpt, 'Ask ChatGPT')}), rv_sum_prompt),
        act_claude(text_token('{P}', {'P': (rv_sum_prompt, 'Text')}), rv_sum),
        act_text(text_token(L['output.critique_reverse'], {'S': (rv_sum, 'Ask Claude'),
                                                   'C': (rv_gpt, 'Ask ChatGPT')}), rv_out),
        act_set_variable(RESULT, rv_out, 'Text'),
        *journal_note(('critique_reverse', L['journal.critique_reverse']), {'X': (rv_claude, 'Ask Claude')}),

        # ---- My mode: Critique with the person's own one-line instruction to the checker, read from
        # Poly-my-mode.txt next to the journal. Without the file (Duo 6.1): a two-item menu instead of a dead end —
        # write the rule now from a sample (the field opens pre-filled; Done saves the file and the check goes on with
        # it, nothing spent before that), or go back: Duo runs again with the same question in the field, then the
        # mode menu.
        menu_case(g_extra, EXTRA[9]),
        *critique_block(pre=[
            act_get_file(MY_MODE_FILE, mm_file),
            act_set_variable(MY_RULE, mm_file, 'File'),
            if_no_value(g_mm, MY_RULE),
            menu_open(g_mmenu, L['menu.my_mode_missing_title'], L['menu.my_mode_missing_items']),
            menu_case(g_mmenu, L['menu.my_mode_missing_items'][0]),
            act_ask(L['ask.my_rule'], mm_ask, default=L['ask.my_rule_sample']),
            # a cleared (or blank) field saves no empty rule file (it would hide this menu for good) and spends nothing
            act_first_match(mm_ask, 'Provided Input', r'\S', mm_chars),
            if_output(g_mmempty, mm_chars, 'Matches', 101),
            {'WFWorkflowActionIdentifier': 'is.workflow.actions.exit', 'WFWorkflowActionParameters': {}},
            if_close(g_mmempty),
            act_text(text_token('{A}', {'A': (mm_ask, 'Provided Input')}), mm_new),
            act_save_file(MY_MODE_FILE, mm_new, mm_save),
            act_set_variable(MY_RULE, mm_new, 'Text'),
            menu_case(g_mmenu, L['menu.my_mode_missing_items'][1]),
            act_run_self(RELEASE_NAME, question, 'Provided Input'),
            {'WFWorkflowActionIdentifier': 'is.workflow.actions.exit', 'WFWorkflowActionParameters': {}},
            menu_close(g_mmenu),
            if_close(g_mm),
            act_get_variable(MY_RULE, mm_rule)], rule_uid=mm_rule),
        menu_close(g_extra),
        menu_close(g_main),

        # ---- Shared tail: deliver, then record, then offer another run
        *if_text(g_empty, RESULT),
        act_clipboard(variable(RESULT)),
        act_notify(L['notify.tail_done']),
        if_else(g_empty),
        act_notify(L['notify.tail_empty']),
        *claude_down_menu(),
        if_close(g_empty),
        # what the clipboard now holds (the result above, or the one the «Claude did not answer» menu delivered) is
        # remembered before the result screen, so the next run does not offer it back as a question
        *if_text(g_tlrem, RESULT),
        act_get_variable(RESULT, tl_rget),
        *remember_answer(tl_rget, 'Variable'),
        if_close(g_tlrem),
        # the journal entry is written BEFORE the result screen (D-100, 6.3.1): on the iPhone (28.10) the «Append to
        # file» permission window that came right after closing the result vanished on its own within ~1.5 s, and the
        # run ended there — no journal entry, no «What next?». Now every permission window comes before the result.
        act_date(tl_date),
        act_get_variable(JOURNAL_EXTRA, tl_extra),
        act_get_variable(RESULT, tl_result),
        act_text(text_token(L['journal.entry'],
                            {**Q, 'D': (tl_date, 'Date'), 'JX': (tl_extra, 'Variable'),
                             'R': (tl_result, 'Variable')}), tl_entry),
        act_append_file(L['files.journal'], tl_entry),
        # ONE Quick Look, after the «Claude did not answer» menu too, and only when there is something to show
        *if_text(g_show, RESULT),
        act_quick_look(variable(RESULT)),
        if_close(g_show),
        menu_open(g_finale, L['menu.finale_title'], L['menu.finale_items']),
        menu_case(g_finale, L['menu.finale_items'][0]),
        menu_case(g_finale, L['menu.finale_items'][1]),
        act_run_self(RELEASE_NAME, question, 'Provided Input'),
        # ---- More…: one extra step for the person who wants it; the usual «Done / Another mode» stays two taps
        menu_case(g_finale, L['menu.finale_items'][2]),
        menu_open(g_more, L['menu.finale_more_title'], L['menu.finale_more_items']),

        # Check the result again: ChatGPT looks for errors in the final result; the block is added below it
        menu_case(g_more, L['menu.finale_more_items'][0]),
        act_notify(L['notify.ratify']),
        act_get_variable(RESULT, fn_get),
        act_text(text_token(L.prompt('ratify'), {**QUESTION, 'RESULT': (fn_get, 'Variable')}), fn_prompt),
        act_gpt(text_token('{P}', {'P': (fn_prompt, 'Text')}), fn_gpt),
        act_text(text_token(L['output.ratify'], {'R': (fn_get, 'Variable'), 'X': (fn_gpt, 'Ask ChatGPT')}), fn_out),
        act_set_variable(RESULT, fn_out, 'Text'),
        act_clipboard(variable(RESULT)),
        *remember_answer(fn_out, 'Text'),
        # the corrected final answer goes into the journal as its own entry (the main entry above was written before
        # this menu and holds the earlier version) — BEFORE its result screen, as in the shared tail (D-100, 6.3.1)
        act_date(fn_date),
        act_get_variable(JOURNAL_EXTRA, fn_jx),
        act_text(text_token(L['journal.entry'],
                            {**Q, 'D': (fn_date, 'Date'), 'JX': (fn_jx, 'Variable'), 'R': (fn_out, 'Text')}), fn_entry),
        act_append_file(L['files.journal'], fn_entry),
        act_quick_look(variable(RESULT)),

        # Save to Notes (Create Note: the text goes to WFCreateNoteBody, Notes takes the first line as the title; not checked on device)
        menu_case(g_more, L['menu.finale_more_items'][1]),
        act_get_variable(RESULT, nt_get),
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.createnote',
         'WFWorkflowActionParameters': {'WFCreateNoteBody': text_token('{T}', {'T': (nt_get, 'Variable')})}},

        # What to check → Reminders: the summary prompt starts each «check yourself» line with ☐; one reminder
        # per such line (Match Text, Repeat with Each, Add New Reminder: not checked on device)
        menu_case(g_more, L['menu.finale_more_items'][2]),
        act_get_variable(RESULT, rm_get),
        act_first_match(rm_get, 'Variable', r'(?m)^.*☐.*$', rm_match),
        repeat_open(g_rem, rm_match, 'Matches'),
        act_get_variable('Repeat Item', rm_item),
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.addnewreminder',
         'WFWorkflowActionParameters': {'WFCalendarItemTitle': text_token('{I}', {'I': (rm_item, 'Variable')})}},
        repeat_close(g_rem),

        # Report this run: opens a pre-filled GitHub issue form — iPhone model, iOS, Duo version, mode. The
        # question and the answers are NOT in it. The person reviews it and presses Submit (nothing is sent here).
        menu_case(g_more, L['menu.finale_more_items'][3]),
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.getdevicedetails',
         'WFWorkflowActionParameters': {'WFDeviceDetail': 'Device Model', 'UUID': dv_model}},
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.urlencode',
         'WFWorkflowActionParameters': {'WFEncodeMode': 'Encode', 'WFInput': attachment(dv_model, 'Device Details'),
                                        'UUID': ue_model}},
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.getdevicedetails',
         'WFWorkflowActionParameters': {'WFDeviceDetail': 'System Version', 'UUID': dv_ios}},
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.urlencode',
         'WFWorkflowActionParameters': {'WFEncodeMode': 'Encode', 'WFInput': attachment(dv_ios, 'Device Details'),
                                        'UUID': ue_ios}},
        act_get_variable(MODE_VAR, md_get),
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.openurl',
         'WFWorkflowActionParameters': {
             'WFInput': text_token(REPORT_URL + '&iphone={M}&ios={I}&version=duo%20' + str(built_version(VK))
                                   + '&mode={D}', {'M': (ue_model, 'URL Encoded Text'),
                                                   'I': (ue_ios, 'URL Encoded Text'),
                                                   'D': (md_get, 'Variable')}),
             'Show-WFInput': True}},
        menu_close(g_more),
        menu_close(g_finale),

        # ---- Last of all, at most once a week: is there a newer Duo? (see version_check)
        *version_check(L, VK, RELEASE_NAME, lang),
    ]

    actions = with_gpt_retry(actions, skip=RETRY_SKIP)
    validate(actions)
    workflow = plistlib.loads((ROOT / 'src' / 'metadata.plist').read_bytes())
    workflow['WFWorkflowIcon'] = {'WFWorkflowIconStartColor': 2071128575,   # violet (lilac, near Poly A1 accent)
                                  'WFWorkflowIconGlyphNumber': 59403}      # two chat bubbles
    workflow['WFWorkflowTypes'] = ['ActionExtension']
    workflow['WFWorkflowInputContentItemClasses'] = ['WFStringContentItem', 'WFURLContentItem',
                                                     'WFRichTextContentItem', 'WFArticleContentItem',
                                                     'WFImageContentItem', 'WFPDFContentItem']
    workflow['WFWorkflowHasShortcutInputVariables'] = True
    workflow['WFQuickActionSurfaces'] = ['ShareSheet']
    workflow['WFWorkflowActions'] = actions

    out_dir = Path(os.environ.get('C1_DIST', ROOT / 'dist')) / lang / ('ai' if ai else '')
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{L['shortcut_names.main']}.shortcut"
    with out.open('wb') as f:
        plistlib.dump(workflow, f, fmt=plistlib.FMT_BINARY)
    print(f'{lang}: {out.name} — {len(actions)} actions')


def validate(actions):
    """Structural checks that must hold for the shortcut to run correctly."""
    seen_uuid, flow_stack, produced = {}, [], set()
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


if __name__ == '__main__':
    languages = sys.argv[1:] or [d.name for d in sorted((ROOT / 'locales').iterdir()) if d.is_dir()]
    for language in languages:
        build(language)
        build(language, ai=True)  # only where trio.json has the Apple Intelligence words
