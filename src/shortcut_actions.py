"""Locale and the building blocks of a shortcut: plist helpers, one function per action, control-flow groups."""
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


def act_gpt(prompt, uid, brief=True, split=True, parts=None):
    """22.11 live run (iPhone, Duo 6.10 limits): «Ask ChatGPT» is cut off with «unknown error» once the call passes about
    30 s, as «Ask Claude» is; a «detailed» question without a length line came back with ~1900 words in 28 s once and
    failed at 31-32 s three times. So every request to ChatGPT starts with «ui.brief.chatgpt» (a length cap only).
    brief=False: the SVG image steps."""
    if brief:
        prompt = with_brief(prompt, GPT_BRIEF, split)
        if split and MORE_LINE and parts:
            PARTS[uid] = parts
    return {'WFWorkflowActionIdentifier': 'com.openai.chat.AskIntent',
            'WFWorkflowActionParameters': {
                'AppIntentDescriptor': {'TeamIdentifier': '2DC432GLL2',
                                        'BundleIdentifier': 'com.openai.chat',
                                        'Name': 'ChatGPT', 'AppIntentIdentifier': 'AskIntent'},
                'newChat': True, 'continuous': False,
                'model': {'identifier': 'auto', 'title': {'key': 'Auto'},
                          'subtitle': {'key': 'Auto'}},
                'ShowWhenRun': False, 'prompt': prompt, 'UUID': uid}}


CLAUDE_BRIEF = ''   # set per build from ui.json «brief.claude»; goes first in every request to Claude (14.11 live run)
GPT_BRIEF = ''      # set per build from ui.json «brief.chatgpt»; goes first in every request to ChatGPT (22.11 live run)


MORE_MARK = '[[MORE]]'
MORE_LINE = ''      # set per Duo build from prompts/more.txt: «does not fit → stop at a paragraph, end with [[MORE]]»
PARTS = {}          # AI call UUID → how many parts its answer may have (default: shortcut_transforms.DEFAULT_PARTS)


def brief_prefix(line, split=True):
    """What stands in front of a request: the length line, then (Duo 6.11, a call whose answer may be continued by a
    second call) the line about [[MORE]]."""
    if not line:
        return ''
    return line + '\n\n' + (MORE_LINE + '\n\n' if split and MORE_LINE else '')


def with_brief(message, line=None, split=False):
    """Put `line` (default CLAUDE_BRIEF) in front of a Text token, moving its attachments by the length of the line
    (UTF-16 units)."""
    line = CLAUDE_BRIEF if line is None else line
    if not line:
        return message
    pre = brief_prefix(line, split)
    shift = len(pre.encode('utf-16-le')) // 2
    value = message['Value']
    moved = {}
    for key, att in value['attachmentsByRange'].items():
        pos, n = (int(x) for x in key.strip('{}').split(','))
        moved['{%d, %d}' % (pos + shift, n)] = att
    return {'Value': {'string': pre + value['string'], 'attachmentsByRange': moved},
            'WFSerializationType': 'WFTextTokenString'}


def act_claude(message, uid, brief=True, split=True, parts=None):
    """14.11 live run (Critique, Opus 5.5): a long Claude answer made iOS fail «Ask Claude» with «unknown error»
    although the answer was in the Claude app. 22.11 live run (iPhone, 20 timed calls): the action is cut off at about
    30 s from its start, whatever the length; Claude writes 20-35 words a second. A 300-word cap came back in 10-19 s
    on every question, 500 failed on a «detailed» one, no cap failed. So every request to Claude starts with the line
    «ui.brief.claude» (a length cap only: the action has no web search, and «do not think long» changed nothing).
    brief=False: the SVG image steps."""
    if brief:
        message = with_brief(message, None, split)
        if split and MORE_LINE and parts:
            PARTS[uid] = parts
    return {'WFWorkflowActionIdentifier': CLAUDE_INTENT,
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


def act_time_between(later_uid, later_name, earlier_uid, earlier_name, unit, uid):
    """«Get Time Between Dates» (output «Time Between Dates»). BOTH dates go in as text tokens: on iPhone 15.11 a probe
    (3 s apart, Seconds) gave «» for attachment/attachment and attachment/token, «3» only for token/token. Before
    that the resume age, the version check age and the diag seconds all came back blank."""
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.gettimebetweendates',
            'WFWorkflowActionParameters': {'WFInput': text_token('{D}', {'D': (later_uid, later_name)}),
                                           'WFTimeUntilFromDate': text_token('{D}', {'D': (earlier_uid, earlier_name)}),
                                           'WFTimeUntilUnit': unit, 'UUID': uid}}


def act_notify(body):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.notification',
            'WFWorkflowActionParameters': {'WFNotificationActionTitle': 'Duo',
                                           'WFNotificationActionBody': body,
                                           'WFNotificationActionSound': False}}


def act_comment(text):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.comment',
            'WFWorkflowActionParameters': {'WFCommentActionText': text}}


def act_step(key):
    """D-128 (18.11, the owner's voice run with Siri and VoiceOver): a step of the run is a Comment, not a
    notification. VoiceOver read every progress banner aloud, several per run, and the person could not speak until
    it finished; Duo now sends ONE notification, at the end («Answer ready»). The Comment shows nothing and asks for
    nothing; it names the step for whoever reads the shortcut (and for the tests)."""
    return act_comment('Duo step: ' + key)


def act_speak(text):
    """«Speak Text» (is.workflow.actions.speaktext): said aloud in the system voice; asks for no permission."""
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.speaktext',
            'WFWorkflowActionParameters': {'WFText': text_token(text, {})}}


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


def open_poly_url(src):
    """D-185: Open URL polyhelper.ai/get/?to=answer&from=<duo|trio>; no encoding, no extra parameters."""
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.openurl',
            'WFWorkflowActionParameters': {'WFInput': text_token(POLY_URL + src, {}), 'Show-WFInput': True}}


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
    """If the variable's text contains `needle`. 15.11 live run (iPhone, «Debate to agreement»): «contains» put straight on
    the variable stopped the run with «Choose values for each parameter in this action» (the editor marks the
    condition red), as «contains» on «Contents of URL» did in D-100; on a Text made from it, it works. So: Get Variable
    → Text → If Text contains."""
    get, txt = new_uuid(), new_uuid()
    return [act_get_variable(var_name, get),
            act_text(text_token('{V}', {'V': (get, 'Variable')}), txt),
            if_output(group, txt, 'Text', 99, WFConditionalActionString=needle)]


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


def repeat_count_open(group, count):
    """«Repeat N times» with a fixed count (is.workflow.actions.repeat.count)."""
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.repeat.count',
            'WFWorkflowActionParameters': {'GroupingIdentifier': group, 'WFControlFlowMode': 0,
                                           'WFRepeatCount': count}}


def repeat_count_close(group):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.repeat.count',
            'WFWorkflowActionParameters': {'GroupingIdentifier': group, 'WFControlFlowMode': 2}}


def set_text(var_name, template, refs=None, special=None):
    """Set a variable to a text (a Text action first: a variable inside a string does not render). `special`: as in
    text_token (e.g. a formatted date)."""
    uid = new_uuid()
    return [act_text(text_token(template, refs, special), uid), act_set_variable(var_name, uid, 'Text')]


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


def act_replace_regex(src_uid, src_name, find, replacement, uid):
    """Replace Text with a regular expression (ICU; `$1` is the first group); output name «Updated Text»."""
    action = act_replace_text(src_uid, src_name, find, replacement, uid)
    action['WFWorkflowActionParameters']['WFReplaceTextRegularExpression'] = True
    return action


def strip_markdown(var):
    """Yuri 10.11 (No.56): the models answer in Markdown, and the result screen, its title (the first line) and the
    clipboard showed raw «**1. Matched independently**», «**Bottom line:**». Bold and italic marks and heading hashes are
    taken off the text in `var`; the words stay. A single star with a space after it (a list bullet) and a star between
    letters or digits («2*3») are not touched."""
    get, r1, r2, r3, code, g = (new_uuid() for _ in range(6))
    return [act_get_variable(var, get),
            # an answer with a code block is left as it is: «x**2», «**kwargs» and «# comment» are code there
            act_first_match(get, 'Variable', '```', code),
            if_output(g, code, 'Matches', 101),
            act_replace_regex(get, 'Variable', r'(?<![\*\w])\*\*(?=\S)(.+?)(?<=\S)\*\*(?![\*\w])', '$1', r1),
            act_replace_regex(r1, 'Updated Text', r'(?<![\*\w])\*(?=[^\s*])([^*\n]+?)(?<=[^\s*])\*(?![\*\w])', '$1', r2),
            act_replace_regex(r2, 'Updated Text', r'(?m)^[ \t]*#{1,6}[ \t]+', '', r3),
            act_set_variable(var, r3, 'Updated Text'),
            if_close(g)]


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



POLY_URL = 'https://polyhelper.ai/get/?to=answer&from='   # D-185: Poly takes the answer from the clipboard
CLAUDE_INTENT = 'com.anthropic.claude.ClaudeAppIntentsExtension'


def act_download(url, uid):
    """`url`: a plain string or a text token."""
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




def set_claude_brief(text):
    """Per build: what goes first in every request to Claude."""
    global CLAUDE_BRIEF
    CLAUDE_BRIEF = text


def set_more_line(text):
    """Per Duo build: the line that lets a long answer be continued by a second call ('' = no continuation)."""
    global MORE_LINE
    MORE_LINE = text
    PARTS.clear()


def set_gpt_brief(text):
    """Per build: what goes first in every request to ChatGPT."""
    global GPT_BRIEF
    GPT_BRIEF = text


# ---------------------------------------------------------------- Duo 6.11: search without keys (shortcut_search.py)

def act_urlencode(src_uid, src_name, uid):
    """«URL Encode» (output «URL Encoded Text»); the same action «Report this run» uses.
    D2 (24.11, run on the Mac's Shortcuts): with the input as an attachment the output is EMPTY, so every search went
    out with an empty query (Google News 404, Wikipedia an API error, Bing and DuckDuckGo their start pages) and no
    card was ever made. The input as a text token gives «Apple%20CEO»."""
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.urlencode',
            'WFWorkflowActionParameters': {'WFEncodeMode': 'Encode',
                                           'WFInput': text_token('{T}', {'T': (src_uid, src_name)}),
                                           'UUID': uid}}


def act_rss(url_token, count, uid):
    """«Get Items from RSS Feed» (output «Items from RSS Feed»: articles with Title, Published Date, URL)."""
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.rss',
            'WFWorkflowActionParameters': {'WFRSSFeedURL': url_token, 'WFRSSItemQuantity': count, 'UUID': uid}}


def act_article_detail(src_uid, src_name, prop, uid):
    """«Get Details of Articles»: one property of an article (output named after the property)."""
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.properties.articles',
            'WFWorkflowActionParameters': {'WFInput': attachment(src_uid, src_name),
                                           'WFContentItemPropertyName': prop, 'UUID': uid}}


def act_get_article(src_uid, src_name, uid):
    """«Get Article using Safari Reader» (output «Article»): the readable text of a page."""
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.getarticle',
            'WFWorkflowActionParameters': {'WFWebPage': attachment(src_uid, src_name), 'UUID': uid}}


def act_replace_regex_token(src_uid, src_name, find, replacement_token, uid):
    """Replace Text (regex) whose replacement is a text token (`$1` groups plus inserted values)."""
    action = act_replace_regex(src_uid, src_name, find, '', uid)
    action['WFWorkflowActionParameters']['WFReplaceTextReplace'] = replacement_token
    return action


def iso_date(uid, name):
    """An action's date output formatted yyyy-MM-dd (ISO 8601 without time; see shortcut_transforms.ymd)."""
    return {'OutputUUID': uid, 'Type': 'ActionOutput', 'OutputName': name,
            'Aggrandizements': [{'Type': 'WFDateFormatVariableAggrandizement', 'WFDateFormatStyle': 'ISO 8601',
                                 'WFISO8601IncludeTime': False}]}


def act_set_name(src_uid, src_name, name, uid):
    """«Set Name» (output «Renamed Item»): a downloaded answer named «r.txt» reads as its plain text (the Mac run of
    24.11: RSS, HTML and JSON came through whole)."""
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.setitemname',
            'WFWorkflowActionParameters': {'WFInput': attachment(src_uid, src_name), 'WFName': name,
                                           'WFDontIncludeFileExtension': False, 'UUID': uid}}


def act_local_ip(uid, kind='IPv4'):
    """«Get Current IP Address», the LOCAL one (no request to any host, no location): a value on Wi-Fi and on cellular,
    nothing offline."""
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.getipaddress',
            'WFWorkflowActionParameters': {'WFIPAddressSourceOption': 'Local', 'WFIPAddressTypeOption': kind,
                                           'UUID': uid}}


def network_guard(var):
    """Actions that never throw: `var` is the constant «1» when the phone has a network, nothing offline («Get Contents
    of URL» stops the whole shortcut offline; Shortcuts has no try/catch). The local IP address is asked, never the
    Wi-Fi name. The second fix of 24.11 (Mac, «Shortcuts», DuoPermDiag: a constant set INSIDE «If IP has any value»
    carries the IP as a data source — «Network Info» stood in 67 of 134 windows of the iPhone run): `var` is set to
    «1» OUTSIDE every condition and only CLEARED inside «If IPv4 and IPv6 have no value». Online that branch never
    runs, and the Mac showed no IP in the windows after such a check."""
    ip, ip6, g, g6 = new_uuid(), new_uuid(), new_uuid(), new_uuid()
    return [*set_text(var, '1'),
            act_local_ip(ip),
            if_output(g, ip, 'Current IP Address', 101),
            act_local_ip(ip6, 'IPv6'),
            if_output(g6, ip6, 'Current IP Address', 101),
            *clear_variable(var),
            if_close(g6),
            if_close(g)]
