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

from shortcut_actions import *  # noqa: F401,F403,E402
from shortcut_actions import ROOT, OBJ, Locale, set_claude_brief, set_gpt_brief, set_more_line, POLY_URL, CLAUDE_INTENT  # noqa: F401,E402
import shortcut_search as S  # noqa: E402

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
# D-128: its presence means the first-run Setup has run (and when the update check last ran)
# Named for the built version: a new Duo is a new shortcut on the iPhone, its permissions start empty, so its Setup runs
# again (iPhone 18.11: the reinstalled Duo found the previous version's file, skipped the Setup and asked 5 windows
# during its first Critique)
# «Another mode», «Back», recipes start this shortcut again by name: in the diagnostic build that is Duo-diag, not Duo
# C1_RUN_NAME: the diag file is installed on the phone under a dated name (Duo-diag-0154), and «Back»/«Another mode»
# must start THAT shortcut, not an older «Duo-diag» still sitting there (15.11 run, No.67)
RUN_NAME = os.environ.get('C1_RUN_NAME') or RELEASE_NAME + ('-diag' if os.environ.get('C1_DIAG') == '1' else '')
# «Debate until agreement»: a side that is genuinely convinced starts its reply with this marker
# (the prompts argue-2-object / argue-3-reply ask for it); the shortcut stops the rounds when it appears.
ARGUE_MARKER = '[[CONCEDE]]'
# Duo 6.4 (D-101): the Critique draft. ONE «Save File» action writes it (iOS asks for each such action on the first
# run, so a second one would be a second permission window): before ChatGPT (step 0: the question), after ChatGPT
# (step 1: the question and ChatGPT's answer) and at the end (done). A run cut off by an app's message limit (iOS stops
# the whole shortcut with a system alert, there is no try/catch) leaves step 0 or 1 behind; the next run, within
# DRAFT_MINUTES, offers to go on from there.
DRAFT_MINUTES = 30
# Yuri 13.11 (No.63): iOS shows the start of the file in the «Save File» permission window, and the person saw
# «⟦duo-draft:0⟧ ⟦Q⟧» in front of the question. The markers are invisible format characters (U+2060…U+2064) now: the
# window shows the question and the answer only. They are tested with Match Text (ICU, literal code points), never with
# «contains», which may compare ignoring such characters.
DRAFT_STEP0, DRAFT_STEP1, DRAFT_DONE = '\u2063\u2060\u2063', '\u2063\u2061\u2063', '\u2063\u2062\u2063'
DRAFT_Q, DRAFT_A = '\u2064\u2060\u2064', '\u2064\u2061\u2064'
# «between −30 and 30 minutes» as TEXT: 0…30 with an optional minus. A Number made from «Time Between Dates» goes
# through the phone's number format: in Ukrainian or Russian 4320 minutes read «4 320», which a Number may take for 4,
# so a draft days old was offered as fresh (Yuri 13.11, No.62).
DRAFT_FRESH = r'^\s*[-−]?(?:[0-9]|[12][0-9]|30)(?:[.,][0-9]{1,2})?\s*$'
assert DRAFT_MINUTES == 30, 'DRAFT_FRESH is written for 30 minutes'
# «Back» from «More…» (Yuri 13.11, No.67): Duo runs itself with this mark in front of the question — the mode menu
# again, WITHOUT the question field (the question is already there)
MODE_MARK = '⟦duo-mode⟧\n'
# a «Repeat with Each» inside another loop: Shortcuts calls its item «Repeat Item 2» (checked on Shortcuts, see
# critique_block — the number pass runs inside the draft loop)
INNER_REPEAT_ITEM = 'Repeat Item 2'


def draft_file(lang, ai):
    """The language and the build variant are in the name, so another language or the Apple Intelligence build on the
    same iCloud never picks up a draft written with other prompts."""
    # the build is in the name too (Yuri 13.11, No.62): deleting the shortcut keeps iCloud Drive → Shortcuts, so a draft
    # left by an older build raised the resume menu on the first run of a fresh install. The version number alone is
    # not enough (a candidate carries the released number until its release), so the name holds a short hash of the
    # builder and of this language's texts: any change of either gives the drafts a new name.
    return f"Duo-draft-{lang}-{'ai' if ai else 'std'}-{build_id(lang)}.txt"


def build_id(lang):
    import hashlib
    h = hashlib.sha256(Path(__file__).read_bytes())
    h.update(b'diag' if os.environ.get('C1_DIAG') == '1' else b'std')   # Duo and Duo-diag never share drafts
    for f in sorted((ROOT / 'locales' / lang).rglob('*')) + sorted((ROOT / 'locales' / 'en' / 'prompts').glob('*.txt')):
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()[:6]


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
# D-29 (C-1, C-3): the person's two optional shortcuts, in ONE small file next to the journal: «MODE=critique» (the mode
# menu is skipped) and «QUICK=1» (a text shared to Duo is sent without the question box). Read by ONE «Get File» at
# the start, written by ONE «Save File» in the final «More actions» menu. Duo's own re-runs («Another mode», Recipes,
# «go back») start with MENU_MARK, which is cut off again at once and forces the question box and the mode menu.
PREFS_FILE = 'Duo-prefs.txt'
PREFS_HEAD = '⟦duo-prefs⟧\n'
MENU_MARK = '⟦duo-menu⟧\n'
# How much of the answer Duo left in the clipboard is remembered (files.last_answer), to recognise it next run
LAST_ANSWER_CHARS = 200
REPORT_URL = 'https://github.com/vadimchernets/poly-duo/issues/new?template=run-report.yml'
FEEDBACK_URL = 'https://github.com/vadimchernets/poly-duo/issues/new?template=feedback.yml'
LONG_TEXT = 6000
# Critique's comparing request (step 3) is counted by its DATA, not by its whole length: the fixed instructions grew
# with the Freshness rule (Karl, KI Forum 226/1762), and a whole-length limit would have flagged ordinary runs as long
# and, on the retry, cut Claude's own answer off entirely. A request is long when the question, the two answers and
# the numbers together pass LONG_DATA characters (as before the rule: 6000 minus the old instructions). The retry
# after an empty comparison rebuilds the request from the same instructions with EACH part cut on its own, so both
# answers always reach it.
LONG_DATA = 2500
RETRY_CUT = {'QUESTION': 400, 'GPT_ANSWER': 1200, 'CLAUDE_OWN': 1200, 'NUMS': 200}
# Duo 6.11 (the owner's decisions of 23.11, item 4): an answer may come in parts, each call under its measured cap
# (the 22.11 timings on the iPhone: Claude ~300 words in 10-22 s, ChatGPT ~600 words in 13-19 s) — see shortcut_transforms.with_continuation.
# Critique's two answers: ChatGPT up to 2 parts (~1200 words), Claude up to 3 (~900 words). Once the two answers
# together pass JUDGE_SPLIT characters, the comparing request is told to stop after its three sections; the final
# answer then comes from a second call (prompts/judge-split.txt), so neither call writes more than its cap.
GPT_PARTS, CLAUDE_PARTS = 2, 3
JUDGE_SPLIT = 5000
# a number that is a source mark («[2]», «[1, 3]») is not a number of the answer
NUMBER_RX = r'(?<![\[\d])\d+(?:[.,:/-]\d+)*(?!\d*(?:\s*[,;]\s*\d+)*\])'


def compare_head_len(template):
    """Characters of a comparing prompt without its data (placeholders out, {TODAY} as a 10-character date)."""
    return len(re.sub(r'\{(?!TODAY\})[A-Z_0-9]+\}', '', template).replace('{TODAY}', '2026-11-22'))


def compare_blank(template):
    """The comparing prompt for a request without sources, link checks or a split (a resumed draft's by-hand check)."""
    return template.replace('{SOURCES}', '').replace('{LINKS}', '').replace('{SPLIT}', '')
# A long question (Yuri 10.11, No.53, iPhone XR, iOS 18.7): with a question of ~1800 characters iOS stopped «Ask ChatGPT»
# with «the action was interrupted because it did not finish in time» while ChatGPT was still writing a long answer; the
# answer stayed in the ChatGPT app and the run never reached Claude. iOS gives an app action a time limit that a
# shortcut cannot change or catch. From LONG_QUESTION characters on, both AIs are asked for a shorter answer (the line
# goes in front of the usual request) and one notification says so; the Critique draft still lets the next run go on.
LONG_QUESTION = 1200
BRIEF_LINE = ('The question is long, and this answer has to arrive within the time limit iOS gives one phone action: '
              'put the essentials first and keep the whole answer under about 200 words.\n\n')


def built_version(key):
    """The number this build carries: the one in releases/version.json at build time."""
    versions = json.loads(VERSION_FILE.read_text(encoding='utf-8'))
    if key == 'duo_ai' and key not in versions:
        return int(versions['duo'])  # releases/version.json gets its own duo_ai number when the build is released
    return int(versions[key])



def version_check(L, key, name, lang, setup=None, stamp_name=None):
    # D-128: with `setup` the block is the first-run Setup only: an existing stamp file means «not due» here (the weekly
    # check stays at the end of the run, where a network error cannot stop a run before its question)
    """Actions of the weekly version check for the shortcut `key` ('duo' or 'trio') in `lang`."""
    ids = lambda n: [new_uuid() for _ in range(n)]
    (f_get, f_date, now, age, far, age_get, stamp_now, stamp, stamp_save,
     wifi, cell, net_get, gh, site, json_get, remote, link) = ids(17)
    age_num, remote_num, gh_t, site_t, json_t = ids(5)
    far0, site2 = ids(2)
    g_file, g_due, g_wifi, g_net, g_gh, g_site, g_json, g_new, g_menu, g_link = ids(10)
    age_var, json_var, net_var = f'{name}VersionAge', f'{name}VersionJson', f'{name}Network'
    stamp_file = stamp_name or f'{name}-version-check.txt'
    # D-128 (18.11, the owner's Siri run): `setup` = (actions before, actions after). With it, a missing stamp file is
    # the FIRST run: the setup actions run right here, at the very start, and the stamp's one «Save File» is this
    # run's one file write — the same action every week after, so no other file window ever comes.
    first_var, g_first, g_first2 = f'{name}FirstRun', new_uuid(), new_uuid()
    needle = f'"{key}":'
    install, later = L['update.install'], L['update.later']
    return [
        act_comment(f'Version check: at most once in {VERSION_DAYS} days, '
                    f'{VERSION_URLS[0]} then {VERSION_URLS[1]}; this build is '
                    f'{key} {built_version(key)}.'),
        act_get_file(stamp_file, f_get),
        if_output(g_file, f_get, 'File', 100),
        *([{'WFWorkflowActionIdentifier': 'is.workflow.actions.number',
            'WFWorkflowActionParameters': {'WFNumberActionNumber': 0, 'UUID': far0}},
           act_set_variable(age_var, far0, 'Number')] if setup else []),
        *([] if setup else [
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.properties.files',
         'WFWorkflowActionParameters': {'WFInput': attachment(f_get, 'File'),
                                        'WFContentItemPropertyName': 'Last Modified Date',
                                        'UUID': f_date}},
        act_date(now),
        act_time_between(now, 'Date', f_date, 'Last Modified Date', 'Days', age),
        act_set_variable(age_var, age, 'Time Between Dates')]),
        if_else(g_file),
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.number',
         'WFWorkflowActionParameters': {'WFNumberActionNumber': 999, 'UUID': far}},
        act_set_variable(age_var, far, 'Number'),
        *(set_text(first_var, '1') if setup else []),
        if_close(g_file),
        *([*if_text(g_first, first_var), *setup[0], if_close(g_first)] if setup else []),
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
        *([] if setup else [act_date(stamp_now), act_text(text_token('{D}', {'D': (stamp_now, 'Date')}), stamp),
                            act_save_file(stamp_file, stamp, stamp_save)]),
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
        *([act_download(VERSION_URLS[1], site2)] if setup else []),
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
        *([*if_text(g_first2, first_var),
           act_date(stamp_now), act_text(text_token('{D}', {'D': (stamp_now, 'Date')}), stamp),
           act_save_file(stamp_file, stamp, stamp_save),
           *setup[1], if_close(g_first2)] if setup else []),
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

def build(lang, ai=False):
    """ai=True → dist/<lang>/ai/Duo.shortcut (U-07): the same Duo, but Auto and Clarify's questions are done by
    «Use Model» (Apple Intelligence, on the iPhone) instead of ChatGPT — one message cheaper each, and the service
    prompts never reach ChatGPT's history or memory. Built only for languages with Apple Intelligence (those whose
    trio.json has the nokey.* words)."""
    import build_trio  # lazy: build_trio imports this module
    L = Locale(lang)
    set_claude_brief(L['brief.claude'])
    set_gpt_brief(L['brief.chatgpt'])
    TRIO = ROOT / 'locales' / lang / 'trio.json'
    if ai and 'nokey.comment' not in json.loads(TRIO.read_text(encoding='utf-8') if TRIO.exists() else '{}'):
        print(f'{lang}: no Apple Intelligence words in trio.json — Duo with Apple Intelligence not built')
        return
    # the provider chain for «Claude did not answer → check with a key» is Trio's, not a copy; where a language has
    # no trio.json yet, its (brand-name and English) words are used
    T = json.loads((TRIO if TRIO.exists() else ROOT / 'locales' / 'en' / 'trio.json').read_text(encoding='utf-8'))
    TV = T['variables']
    set_more_line(L.prompt('more'))   # Duo only; cleared again at the end of this build (Trio is built in the same process by the tests)

    def service_call(prompt_uid, uid):
        """The one cheap service call: (action, output name) — ChatGPT, or Use Model in the ai build."""
        if ai:
            return build_trio.act_use_model(prompt_uid, uid), 'Response'
        return act_gpt(text_token('{P}', {'P': (prompt_uid, 'Text')}), uid, split=False), 'Ask ChatGPT'

    RESULT = L['variables.result']
    JOURNAL_EXTRA = L['variables.journal_extra']
    MAIN = L['menu.main_items']
    EXTRA = L['menu.extra_items']

    ids = lambda n: [new_uuid() for _ in range(n)]
    question, qpre = ids(2)
    # the modes read the question from a Get Variable (qpre) that runs after the question box OR after the skipped box
    Q = {'Q': (qpre, 'Variable')}
    QUESTION = {'QUESTION': (qpre, 'Variable')}
    q_get, g_fresh, g_crit, g_down = ids(4)
    QV = {'Q': (q_get, 'Variable')}   # the question after the mode menu (typed now, or from a resumed draft)

    g_main, g_extra, g_anchor, g_image, g_empty, g_finale, g_oc2 = ids(7)
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
    # Duo 6.4 (D-101): the draft and the resume of a Critique cut off by a message limit
    QVAR = 'PolyQuestion'            # the question, whether typed now or taken from a resumed draft
    RESUME_VAR = 'PolyResume'        # set → this run goes on from a saved draft: no question field, no mode menu
    CRIT_VAR = 'PolyCritique'        # set → the shared Critique runs after the mode menu
    ONLY_CLAUDE = 'PolyOnlyClaude'   # set → only Claude was asked in this run (Advisor, «Ask Claude alone»)
    SKIP_GPT = 'PolySkipChatGPT'     # set → ChatGPT is not asked (it stopped on its limit last time)
    CLAUDE_DOWN = 'PolyClaudeDown'   # set → the «check with…» menu follows the answer in the shared tail
    DRAFT_VAR, DRAFT_PASS_A, DRAFT_PASS_B = 'PolyDraft', 'PolyDraftPassA', 'PolyDraftPassB'
    DRAFT = draft_file(lang, ai)
    RETRY_SKIP = set()   # ChatGPT calls that have their own retry or are not a mode's first call (see with_gpt_retry)
    NUMS_VAR, MODE_VAR, MY_RULE = 'PolyOnlyInOne', 'PolyMode', 'PolyMyRule'
    # D-29 (the leak found on the iPhone 29.10: the text of Duo-prefs.txt rode into the ChatGPT request and the
    # clipboard on the «Critique right away» path): everything computed from that file is an «OFF» flag that is only
    # ever CLEARED («Nothing», the pattern last_answer already uses) inside an If that depends on the file. A Text
    # created inside such an If is never used; the skip flags below are constants made OUTSIDE it.
    MODE_OFF, QUICK_OFF, FORCE_MENU, PREFS_BODY = 'PolyModeOff', 'PolyQuickOff', 'PolyForceMenu', 'PolyPrefsBody'
    SHARED_VAR, SKIP_MENU, SKIP_Q, PREFS_CHANGED = 'PolyShared', 'PolySkipMenu', 'PolySkipQuestion', 'PolyPrefsChanged'
    g_rec, g_mm, g_more = ids(3)
    rv_wrap, rv_claude, rv_prompt, rv_gpt, rv_sum_prompt, rv_sum, rv_out, mm_file, mm_rule = ids(9)
    (fn_get, fn_prompt, fn_gpt, fn_out, nt_get, rm_get, rm_match, rm_item, dv_model, dv_ios, ue_model, ue_ios,
     md_get, rp_get, rp_title) = ids(15)
    g_rat, g_rem = ids(2)
    op_get, op_get2 = ids(2)
    g_mmenu, mm_ask, mm_new, mm_save, tl_rget, g_tlrem, g_mmempty, mm_chars = ids(8)
    fn_date, fn_jx, fn_entry, fn_clean = ids(4)
    pf_m1, pf_m2 = ids(2)
    pf_get, pf_txt, g_pf1, g_pf2, g_sh, mk_get, mk_m, mk_rep, g_mk, g_ka, g_kb, g_qa, g_qb, g_qc, g_qd = ids(15)
    qw_get, qw_m, g_askq, g_skm = ids(4)
    g_pc, pm_get, pq_get, pf_new, pf_save, sk_get = ids(6)
    g_n1, g_n2, g_n3 = ids(3)
    bk_text, bk_m, bk_rep, g_bk, g_keepq, bk_get = ids(6)
    KEEP_Q = 'PolyKeepQuestion'   # set by MODE_MARK: the question field is skipped, the mode menu is shown
    NOTE_MODE, NOTE_QUICK, NOTE_RESET = 'PolyNoteMode', 'PolyNoteQuick', 'PolyNoteReset'
    BRIEF_VAR, SIDE_CLAUDE = 'PolyBrief', 'PolySideClaude'   # Yuri 10.11: No.53 (long question), No.52 (Side by side)

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
        and the person can paste it. D-100: it is no longer also remembered as Duo's own (that was one more
        «Save File», one more permission window on the first run); when the run goes on, the tail's clipboard write
        replaces it and is remembered there. No extra screen, tap or message; only when there is an answer.
        D-128: no notification (one per run, at the end); `note` names the next step as a Comment (act_step).
        D-128 (18.11, the owner's Siri run): no clipboard write either. «Copy to Clipboard» is a permission window of
        its own, and with the phone locked under Siri it came up silently and the run stood still. A run cut off on
        Claude keeps ChatGPT's answer in the ChatGPT app."""
        return [*([act_step(note)] if note else [])]

    def brief_for_long(src_uid, src_name):
        """Yuri 10.11 (No.53): a question of LONG_QUESTION characters or more → BRIEF_LINE goes in front of the request
        and a Comment names the step (D-128: no notification). Returns (actions, uid of a Get Variable whose text is BRIEF_LINE or empty)."""
        txt, cnt, g, get = new_uuid(), new_uuid(), new_uuid(), new_uuid()
        return [act_text(text_token('{Q}', {'Q': (src_uid, src_name)}), txt),
                act_count_chars(txt, 'Text', cnt),
                *set_text(BRIEF_VAR, '\n'),   # not an empty Text (D-100); a blank line in front of the request is harmless
                if_output(g, cnt, 'Count', 2, WFNumberValue=LONG_QUESTION - 1),
                *set_text(BRIEF_VAR, BRIEF_LINE),
                act_step('long_question'),
                if_close(g),
                act_get_variable(BRIEF_VAR, get)], get

    def clear_when(test_var, present, target):
        """If <test_var> has text (present=True) or has none: set <target> to NOTHING. Used for every flag that depends
        on the prefs file: a flag is only ever cleared, never built from a Text inside such an If."""
        g = new_uuid()
        return [*if_text(g, test_var, present=present), *clear_variable(target), if_close(g)]

    def append_line_when(off_var, line):
        """The option is ON when its OFF flag has no value: add its line to PREFS_BODY."""
        g, get, txt = new_uuid(), new_uuid(), new_uuid()
        return [*if_text(g, off_var, present=False), act_get_variable(PREFS_BODY, get),
                act_text(text_token('{B}' + line + '\n', {'B': (get, 'Variable')}), txt),
                act_set_variable(PREFS_BODY, txt, 'Text'), if_close(g)]

    def rerun_with_menu(src_uid, src_name):
        """Run Duo again with this question and MENU_MARK in front: the new run forces the question box and the
        mode menu even when the person chose «Critique right away» or «ask without editing» (D-29)."""
        uid = new_uuid()
        return [act_text(text_token(MENU_MARK + '{Q}', {'Q': (src_uid, src_name)}), uid),
                act_run_self(RUN_NAME, uid, 'Text')]

    def recipes_menu(group, title):
        """Recipes: a ready task → the question box opens pre-filled with its wording (Duo runs itself with that
        text as its input, the same way the Share Sheet does), the person edits it and picks a mode."""
        items, out = L['menu.recipes_items'], [menu_open(group, title, L['menu.recipes_items'])]
        for i, item in enumerate(items):
            uid = new_uuid()
            out += [menu_case(group, item),
                    act_text(text_token(MENU_MARK + L['menu.recipes_texts'][i]), uid),
                    act_run_self(RUN_NAME, uid, 'Text'),
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
    sb_claude2, sb_cget, g_sbretry, g_sbok, g_sbgpt, g_sbg2 = ids(6)
    sb_brief, sb_brief_get = brief_for_long(qpre, 'Variable')
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
            *if_contains(g_obj, ARGUE_LOG, ARGUE_MARKER),
            if_else(g_obj),
            act_get_variable(ARGUE_LOG, get1),
            *([act_get_variable(ARGUE_OPEN, op_get)] if n == 1 else []),
            # round 1: Claude states its OWN position on the question without seeing side A's opening
            # (blind first, same number of messages); from round 2 on the sides see each other
            # round 1: ChatGPT's opening goes to the clipboard first, see keep_gpt. The opening itself, not the log
            # (whose side-A header is there even when ChatGPT sent nothing); a resumed debate has no opening in memory
            # and copies nothing
            *(keep_gpt(op_get, 'Variable', 'argue_blind') if n == 1 else
              [act_step('argue_object')]),
            (act_text(text_token(L.prompt('argue-1-open-b'), Q), pr1) if n == 1 else
             act_text(text_token(L.prompt('argue-2-object').replace('{ROUND}', rnd),
                                 {**QUESTION, 'LOG': (get1, 'Variable')}), pr1)),
            act_claude(text_token('{P}', {'P': (pr1, 'Text')}), cl1),
            act_get_variable(ARGUE_LOG, get2),
            act_text(text_token('{L}\n\n' + L['output.argue_side_b_round'].replace('{N}', rnd) + '\n{B}',
                                {'L': (get2, 'Variable'), 'B': (cl1, 'Ask Claude')}), add1),
            act_set_variable(ARGUE_LOG, add1, 'Text'),
            *if_contains(g_rep, ARGUE_LOG, ARGUE_MARKER),
            if_else(g_rep),
            act_step('argue_reply'),
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

    def critique_block(pre=(), rule_uid=None, qsrc=None, draft=False):
        """Critique, blind scheme (D-41), 3 messages as before: ChatGPT answers the wrapped question; Claude answers
        the SAME wrapped question on its own, without seeing ChatGPT's answer; then Claude compares both in one
        message (critique-blind.txt: three blocks «matched independently / did not match / what to check yourself»,
        then the final answer). `pre` runs first; `rule_uid` (an action whose text is the person's own one-line
        instruction to the checker, «My mode») is put in front of the comparing prompt (step 3). `qsrc`: the
        (action, output) that holds the question. `draft=True` (the main Critique, Duo 6.4, D-101): the run keeps a
        draft through ONE «Save File» action (see DRAFT_MINUTES) and may start from a resumed one — GPT_VAR already
        holds ChatGPT's saved answer, or SKIP_GPT says ChatGPT is not to be asked (its limit).

        Duo 6.4, the limit of either AI (D-101): whoever answered, the person gets that answer. ChatGPT gave nothing →
        Claude's own answer with a line «ChatGPT did not answer (limit?), no comparison» (no comparing message is
        spent on one answer). Claude gave nothing → ChatGPT's answer with the same line about Claude, and the
        «check with…» menu (Trio's free keys, this iPhone, by hand) follows in the shared tail (CLAUDE_DOWN)."""
        qsrc = qsrc or (qpre, 'Variable')
        QQ, QQUESTION = {'Q': qsrc}, {'QUESTION': qsrc}
        (cr_gpt2, cr_gpt_f, cr_len, cr_cut, cr_claude2, cr_claude_f, cr_numfin, cr_kget, cr_own, cr_own2,
         cr_own_f, cr_g1, cr_o1, cr_save, cr_dq, cr_da, cr_jg) = ids(17)
        (g_retry, g_long, g_cretry, g_cok, g_oretry, g_n1, g_n2, g_need, g_skip, g_gdown, g_both, g_own1,
         g_loop, g_dsave, g_pa, g_pb, g_d1, g_oc) = ids(18)
        cr_wrap, cr_gpt, cr_prompt, cr_claude, cr_today = ids(5)
        cr_cut_q, cr_cut_g, cr_cut_o, cr_cut_n = ids(4)
        brief_acts, brief_get = brief_for_long(*qsrc)   # Yuri 10.11, No.53
        (sr_today, sr_pk, g_pk, cr_wrap_s, cr_ow, cr_ow2, cr_pk, cr_lk, cr_sp, cr_both, cr_blen, g_split,
         cr_pk2, cr_lk2, cr_sp2) = ids(15)
        OWN_WRAP, SPLIT_VAR = 'PolyOwnRequest', 'PolyJudgeSplit'
        ask_service = lambda p, uid: act_claude(text_token('{P}', {'P': (p, 'Text')}), uid, split=False)
        # Duo 6.11: Duo's own search, before any model is asked; then Claude's request — with the numbered sources
        # when there are any, the plain wrapped question otherwise. ChatGPT gets the plain question either way.
        search = [
            *S.search_block(L, qsrc, LONG_QUESTION, ask_service),
            act_date(sr_today),
            act_get_variable(S.PACKET, sr_pk),
            *if_text(g_pk, S.PACKET),
            act_text(text_token('{B}' + L.prompt('wrap-sources'),
                                {**QQ, 'B': (brief_get, 'Variable'), 'SOURCES': (sr_pk, 'Variable')},
                                {'TODAY': ymd(sr_today)}), cr_wrap_s),
            act_set_variable(OWN_WRAP, cr_wrap_s, 'Text'),
            if_else(g_pk),
            act_set_variable(OWN_WRAP, cr_wrap, 'Text'),
            if_close(g_pk),
        ]
        RETRY_SKIP.update((cr_gpt, cr_gpt2))
        rule_prefix = 'Extra instruction from the user for this check (apply it): {RULE}\n\n' if rule_uid else ''
        rule_ref = {'RULE': (rule_uid, 'Variable')} if rule_uid else {}
        compare_template = rule_prefix + L.prompt('critique-blind')
        item_name = INNER_REPEAT_ITEM if draft else 'Repeat Item'

        def number_pass(src_var_uid, other_var):
            """Every number of the answer `src_var_uid` (a Get Variable output) that does NOT stand, as a whole
            number, in the other answer `other_var` is added to NUMS_VAR — once (checked against the list too).
            Whole-number match, not substring: «7» is not «17». Not checked on device: Match Text with a regex whose
            pattern holds a token, Replace Text, Repeat with Each, the «Repeat Item» variable."""
            nums, item, esc, other, g_rep, g_miss, g_dup = ids(7)
            m_other, m_list, lst, add_get, add_txt = ids(5)
            return [
                act_first_match(src_var_uid, 'Variable', NUMBER_RX, nums),
                repeat_open(g_rep, nums, 'Matches'),
                act_get_variable(item_name, item),
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

        # ---- Step 1: ChatGPT — in the main Critique, unless a resumed draft already holds its answer, or the person
        # chose «Claude alone» after ChatGPT's limit
        gate = [*if_text(g_need, GPT_VAR, present=False), *if_text(g_skip, SKIP_GPT, present=False)] if draft else []
        step1 = [
            *gate,
            act_gpt(text_token('{P}', {'P': (cr_wrap, 'Text')}), cr_gpt, parts=GPT_PARTS),
            act_set_variable(GPT_VAR, cr_gpt, 'Ask ChatGPT'),
            # an empty ChatGPT answer (often a false «logged out» or a dropped call): wait 3 s, ask once more
            *if_text(g_retry, GPT_VAR, present=False),
            act_delay(3),
            act_gpt(text_token('{P}', {'P': (cr_wrap, 'Text')}), cr_gpt2, parts=GPT_PARTS),
            act_set_variable(GPT_VAR, cr_gpt2, 'Ask ChatGPT'),
            if_close(g_retry),
            # ChatGPT gave nothing (its limit, signed out, iOS cut the step): Claude answers alone, and the person is
            # told now. Only where ChatGPT was really asked: after «Ask Claude alone» in the resume menu ChatGPT is
            # skipped by choice, and «ChatGPT sent no answer» was a false alarm (Yuri 13.11, No.61).
            *if_text(g_gdown, GPT_VAR, present=False),
            act_notify(L['notify.gpt_down']),
            if_close(g_gdown),
            *([if_close(g_skip), if_close(g_need)] if draft else []),
        ]
        # ---- Steps 2 and 3: Claude answers blind, then compares (only when there are two answers to compare)
        steps23 = [
            act_get_variable(GPT_VAR, cr_kget),
            *keep_gpt(cr_kget, 'Variable', 'critique_blind'),
            # Claude's own answer: the question (and Duo's sources, if any) — never ChatGPT's answer
            act_get_variable(OWN_WRAP, cr_ow),
            act_claude(text_token('{P}', {'P': (cr_ow, 'Variable')}), cr_own, parts=CLAUDE_PARTS),
            act_set_variable(OWN_VAR, cr_own, 'Ask Claude'),
            *if_text(g_oretry, OWN_VAR, present=False),
            act_step('claude_retry'),
            act_get_variable(OWN_WRAP, cr_ow2),
            act_claude(text_token('{P}', {'P': (cr_ow2, 'Variable')}), cr_own2, parts=CLAUDE_PARTS),
            act_set_variable(OWN_VAR, cr_own2, 'Ask Claude'),
            if_close(g_oretry),
            act_get_variable(GPT_VAR, cr_gpt_f),
            act_get_variable(OWN_VAR, cr_own_f),
            *if_text(g_both, GPT_VAR),
            # ---- Step 3: Claude compares both. Numbers that stand in only one of the two answers are found by rule,
            # not by Claude's attention, and handed over as data. Only when both answers exist: with one of them
            # missing every number would be «only in one». With Claude's own answer empty, step 3 still runs: Claude
            # checks ChatGPT's answer (the prompt says how).
            *clear_variable(NUMS_VAR),
            *if_text(g_n1, OWN_VAR),
            *number_pass(cr_gpt_f, OWN_VAR),
            *number_pass(cr_own_f, GPT_VAR),
            if_close(g_n1),
            act_get_variable(NUMS_VAR, cr_numfin),
            act_date(cr_today),
            # Duo 6.11: the pages ChatGPT cited are read by Duo and checked one by one (only when it cited any)
            *S.link_check_block(L, GPT_VAR, ask_service, RESUME_VAR, ymd(cr_today)),
            act_get_variable(S.PACKET, cr_pk),
            act_get_variable(S.LINKS, cr_lk),
            # two long answers: the comparison stops after its three sections, the final answer is a second call
            act_text(text_token('{G}{O}', {'G': (cr_gpt_f, 'Variable'), 'O': (cr_own_f, 'Variable')}), cr_both),
            act_count_chars(cr_both, 'Text', cr_blen),
            *set_text(SPLIT_VAR, '\n'),
            if_output(g_split, cr_blen, 'Count', 2, WFNumberValue=JUDGE_SPLIT),
            *set_text(SPLIT_VAR, L.prompt('judge-split')),
            act_step('judge_split'),
            if_close(g_split),
            act_get_variable(SPLIT_VAR, cr_sp),
            # today's date from the phone: the Freshness rule of critique-blind.txt (Karl, KI Forum 226/1762) needs it
            # to tell a fact that may have changed since the models were trained; no permission, no message
            act_text(text_token(compare_template,
                                {**QQUESTION, 'GPT_ANSWER': (cr_gpt_f, 'Variable'),
                                 'CLAUDE_OWN': (cr_own_f, 'Variable'), 'NUMS': (cr_numfin, 'Variable'),
                                 'SOURCES': (cr_pk, 'Variable'), 'LINKS': (cr_lk, 'Variable'),
                                 'SPLIT': (cr_sp, 'Variable'),
                                 **rule_ref}, {'TODAY': ymd(cr_today)}), cr_prompt),
            act_set_variable(CHECK_VAR, cr_prompt, 'Text'),   # U-06: what the three fallbacks send
            act_step('critique_step3'),
            # ---- A long request (U-08): one notification, not a window, once the data passes LONG_DATA characters;
            # and if Claude returns nothing, one automatic retry with each part cut on its own (RETRY_CUT).
            act_count_chars(cr_prompt, 'Text', cr_len),
            if_output(g_long, cr_len, 'Count', 2, WFNumberValue=compare_head_len(compare_template) + LONG_DATA),
            act_step('long_text'),
            if_close(g_long),
            act_claude(text_token('{P}', {'P': (cr_prompt, 'Text')}), cr_claude),
            act_set_variable(CLAUDE_VAR, cr_claude, 'Ask Claude'),
            *if_text(g_cretry, CLAUDE_VAR, present=False),
            act_step('claude_retry'),
            act_first_chars(qsrc[0], qsrc[1], RETRY_CUT['QUESTION'], cr_cut_q),
            act_first_chars(cr_gpt_f, 'Variable', RETRY_CUT['GPT_ANSWER'], cr_cut_g),
            act_first_chars(cr_own_f, 'Variable', RETRY_CUT['CLAUDE_OWN'], cr_cut_o),
            act_first_chars(cr_numfin, 'Variable', RETRY_CUT['NUMS'], cr_cut_n),
            act_text(text_token(compare_template,
                                {'QUESTION': (cr_cut_q, 'Matches'), 'GPT_ANSWER': (cr_cut_g, 'Matches'),
                                 'CLAUDE_OWN': (cr_cut_o, 'Matches'), 'NUMS': (cr_cut_n, 'Matches'),
                                 'SOURCES': (cr_pk, 'Variable'), 'LINKS': (cr_lk, 'Variable'),
                                 'SPLIT': (cr_sp, 'Variable'),
                                 **rule_ref}, {'TODAY': ymd(cr_today)}), cr_cut),
            act_claude(text_token('{P}', {'P': (cr_cut, 'Text')}), cr_claude2),
            act_set_variable(CLAUDE_VAR, cr_claude2, 'Ask Claude'),
            if_close(g_cretry),
            act_get_variable(CLAUDE_VAR, cr_claude_f),
            # the shared tail copies RESULT to the clipboard (D-100: one clipboard action, one permission window)
            *if_text(g_cok, CLAUDE_VAR),
            act_set_variable(RESULT, cr_claude_f, 'Variable'),
            if_else(g_cok),
            # Claude did not compare (its limit, signed out): ChatGPT's answer with the line about it, and the
            # «check with…» menu in the shared tail
            *set_text(RESULT, L['output.claude_down'], {'A': (cr_gpt_f, 'Variable')}),
            *set_text(CLAUDE_DOWN, '1'),
            if_close(g_cok),
            if_else(g_both),
            # ChatGPT gave nothing: Claude's own answer, with the line about ChatGPT; no comparing message is spent
            *if_text(g_own1, OWN_VAR),
            # ChatGPT was not asked at all («Ask Claude alone»): a neutral line, not «ChatGPT did not pass» (No.61)
            *if_text(g_oc, ONLY_CLAUDE),
            *set_text(RESULT, L['output.claude_only'], {'C': (cr_own_f, 'Variable')}),
            if_else(g_oc),
            *set_text(RESULT, L['output.gpt_down'], {'C': (cr_own_f, 'Variable')}),
            if_close(g_oc),
            if_close(g_own1),
            if_close(g_both),
            # Duo 6.11: «Sources» under the result — the entries whose [N] the text cites, printed by Duo itself
            *S.append_sources(L, RESULT),
            act_get_variable(GPT_VAR, cr_jg),
            *journal_note(('critique', L['journal.critique']), {'X': (cr_jg, 'Variable')}),
        ]
        if not draft:
            return [
                *pre,
                # Emptied with «Nothing», not with an empty Text (an empty Text «has any value»).
                *clear_variable(GPT_VAR),
                *clear_variable(OWN_VAR),
                act_step('critique_start'),
                # the wrapped question is needed by step 1 AND step 2, so it is built outside both
                *brief_acts,
                act_text(text_token('{B}' + L.prompt('wrap'), {**QQ, 'B': (brief_get, 'Variable')}), cr_wrap),
                *search,
                *step1,
                *steps23,
            ]
        # The draft: ONE «Save File», run three times by a loop — step 0 (the question) before ChatGPT, step 1 (the
        # question and ChatGPT's answer) before Claude, «done» after Claude's comparison. A run cut off by a limit
        # leaves step 0 or step 1; a finished one (whatever came back) leaves «done». The loop is the only way to run
        # one action at three moments: each «Save File» in a shortcut is its own permission window on the first run.
        return [
            *pre,
            *clear_variable(OWN_VAR),
            act_step('critique_start'),
            *brief_acts,
            act_text(text_token('{B}' + L.prompt('wrap'), {**QQ, 'B': (brief_get, 'Variable')}), cr_wrap),
            *search,
            *set_text(DRAFT_VAR, DRAFT_STEP0 + '\n' + DRAFT_Q + '\n{Q}\n' + DRAFT_A + '\n', QQ),
            repeat_count_open(g_loop, 3),
            *if_text(g_dsave, DRAFT_VAR),
            act_get_variable(DRAFT_VAR, cr_dq),
            act_text(text_token('{D}', {'D': (cr_dq, 'Variable')}), cr_da),
            act_save_file(DRAFT, cr_da, cr_save),
            if_close(g_dsave),
            # the first pass: ChatGPT; the second: Claude; the third only saves «done»
            *if_text(g_pa, DRAFT_PASS_A, present=False),
            *set_text(DRAFT_PASS_A, '1'),
            *step1,
            *clear_variable(DRAFT_VAR),
            *if_text(g_d1, GPT_VAR),
            act_get_variable(GPT_VAR, cr_g1),
            *set_text(DRAFT_VAR, DRAFT_STEP1 + '\n' + DRAFT_Q + '\n{Q}\n' + DRAFT_A + '\n{A}',
                      {**QQ, 'A': (cr_g1, 'Variable')}),
            # ChatGPT gave nothing: no second write, the step-0 draft already on disk stays as it is
            if_close(g_d1),
            if_else(g_pa),
            *if_text(g_pb, DRAFT_PASS_B, present=False),
            *set_text(DRAFT_PASS_B, '1'),
            *steps23,
            *set_text(DRAFT_VAR, DRAFT_DONE),
            if_else(g_pb),
            *clear_variable(DRAFT_VAR),
            if_close(g_pb),
            if_close(g_pa),
            repeat_count_close(g_loop),
        ]

    def resume_block():
        """Duo 6.4 (D-101): a Critique cut off within DRAFT_MINUTES (the draft is at step 0 or 1, not «done») → ONE
        menu before the question field. Only when Duo was started without input: a Share or a rerun brings its own
        question. Step 1 (ChatGPT answered, Claude stopped — its message limit): go on asking only Claude (no new
        ChatGPT message) / check ChatGPT's answer without Claude (Trio's free keys, this iPhone, by hand — the
        «Claude did not answer» menu) / show ChatGPT's saved answer / new question. Step 0 (ChatGPT stopped): Claude
        alone / both again / new question. Anything but «new question» skips the question field and the mode menu."""
        u = new_uuid
        g_in, g_f, g_age, g_q, g_1, g_0, g_m1, g_m0 = (u() for _ in range(8))
        rf, rt, rdate, rnow, rage, rnum, rqm, rq, ram, ra = (u() for _ in range(10))
        rfresh, rs1, rs0 = u(), u(), u()
        I1, I0 = L['menu.resume1_items'], L['menu.resume0_items']
        A = {'A': (ra, 'Text')}
        diag = os.environ.get('C1_DIAG') == '1'

        def dlog(msg, refs=None):
            # C1_DIAG only: a line «HH:mm:ss 🔧 resume: ...» into Duo-diag-log.txt at each decision point
            if not diag:
                return []
            t, lu = u(), u()
            return [act_date(t), act_text(text_token('{D} 🔧 resume: ' + msg + '\n', refs or {}, {'D': hms(t)}), lu),
                    act_append_file('Duo-diag-log.txt', lu)]

        def delse(g, msg):
            return [if_else(g), *dlog(msg)] if diag else []

        def resumed(*extra):
            return [*set_text(QVAR, '{Q}', {'Q': (rq, 'Text')}), *set_text(RESUME_VAR, '1'), *extra]

        def check_request():
            # the comparing prompt with ChatGPT's answer alone (it says how to treat a missing one)
            prompt = compare_blank(L.prompt('critique-blind')).replace('{CLAUDE_OWN}', '').replace('{NUMS}', '')
            # today's date: the «Current Date» already taken for the draft's age (rnow), no second action
            return set_text(CHECK_VAR, prompt, {'QUESTION': (rq, 'Text'), 'GPT_ANSWER': (ra, 'Text')},
                            {'TODAY': ymd(rnow)})
        rline = u()
        return [
            if_shortcut_input(g_in),
            *dlog('branch: Shortcut Input present, resume menu skipped'),
            if_else(g_in),
            act_get_file(DRAFT, rf),
            if_output(g_f, rf, 'File', 100),
            *dlog(f'file {DRAFT} found'),
            act_text(text_token('{F}', {'F': (rf, 'File')}), rt),
            {'WFWorkflowActionIdentifier': 'is.workflow.actions.properties.files',
             'WFWorkflowActionParameters': {'WFInput': attachment(rf, 'File'),
                                            'WFContentItemPropertyName': 'Last Modified Date', 'UUID': rdate}},
            act_date(rnow),
            act_time_between(rnow, 'Date', rdate, 'Last Modified Date', 'Minutes', rage),
            # «between −30 and 30 minutes» reads the same whichever way the system counts (as in version_check); tested
            # on the text, not on a Number (DRAFT_FRESH, Yuri 13.11, No.62)
            act_text(text_token('{M}', {'M': (rage, 'Time Between Dates')}), rnum),
            *dlog("age '{V}'", {'V': (rnum, 'Text')}),
            *((act_first_match(rt, 'Text', '^[^\\n]*', rline),
               *dlog("step '{V}'", {'V': (rline, 'Matches')})) if diag else ()),
            act_first_match(rnum, 'Text', DRAFT_FRESH, rfresh),
            if_output(g_age, rfresh, 'Matches', 100),
            *dlog('branch: age passed, looking for the question'),
            act_first_match(rt, 'Text', '(?s)(?<=' + DRAFT_Q + '\\n).*?(?=\\n' + DRAFT_A + ')', rqm),
            act_text(text_token('{M}', {'M': (rqm, 'Matches')}), rq),
            act_first_match(rt, 'Text', '(?s)(?<=' + DRAFT_A + '\\n).*', ram),
            act_text(text_token('{M}', {'M': (ram, 'Matches')}), ra),
            *if_output_text(g_q, rq, 'Text'),
            *dlog('branch: question found in the draft'),
            act_first_match(rt, 'Text', DRAFT_STEP1, rs1),
            if_output(g_1, rs1, 'Matches', 100),
            *dlog('branch: step 1, resume menu shown'),
            menu_open(g_m1, L['menu.resume1_title'], I1),
            menu_case(g_m1, I1[0]),
            *resumed(*set_text(GPT_VAR, '{A}', A), *set_text(CRIT_VAR, '1'), act_step('resume')),
            menu_case(g_m1, I1[1]),
            *resumed(*set_text(RESULT, L['output.claude_down'], A), *check_request(), *set_text(CLAUDE_DOWN, '1'),
                     *journal_note(('critique', L['journal.critique']), {'X': (ra, 'Text')})),
            menu_case(g_m1, I1[2]),
            *resumed(*set_text(RESULT, L['output.claude_down'], A),
                     *journal_note(('critique', L['journal.critique']), {'X': (ra, 'Text')})),
            menu_case(g_m1, I1[3]),
            menu_close(g_m1),
            if_else(g_1),
            act_first_match(rt, 'Text', DRAFT_STEP0, rs0),
            if_output(g_0, rs0, 'Matches', 100),
            *dlog('branch: step 0, resume menu shown'),
            menu_open(g_m0, L['menu.resume0_title'], I0),
            menu_case(g_m0, I0[0]),
            *resumed(*set_text(SKIP_GPT, '1'), *set_text(ONLY_CLAUDE, '1'), *set_text(CRIT_VAR, '1')),
            menu_case(g_m0, I0[1]),
            *resumed(*set_text(CRIT_VAR, '1')),
            menu_case(g_m0, I0[2]),
            menu_close(g_m0),
            *delse(g_0, 'branch: step is neither 0 nor 1 (done?), no menu'),
            if_close(g_0),
            if_close(g_1),
            *delse(g_q, 'branch: no question in the draft, no menu'),
            if_close(g_q),
            *delse(g_age, 'branch: age failed, no menu'),
            if_close(g_age),
            *delse(g_f, 'branch: file not found, no menu'),
            if_close(g_f),
            if_close(g_in),
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
            # nothing here: the one clipboard write, its save and the one Quick Look come from the shared tail, after
            # this menu, when RESULT has text (Duo 6.4: one clipboard action for every path)
            return []
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
            # the request stays in the clipboard: the tail does not copy ChatGPT's answer over it (it is in the request)
            *clear_variable(RESULT),
            menu_close(g_down),
            if_close(g_chk),
        ]

    SETUP_FILE = f'{RELEASE_NAME}-setup-{built_version(VK)}.txt'
    su_gpt, su_claude, su_ping, su_txt, su_save = ids(5)
    RETRY_SKIP.add(su_gpt)
    SETUP_PING = 'Reply with the single word OK.'
    # iPhone 18.11: a text of Duo's own asked only «run actions from Claude»; the first real Critique then asked «send
    # 2 text items to Claude» and «save 1 text item to a file» (the draft). Content that came from another app is what
    # those windows are about, so the Setup passes ChatGPT's own reply on to Claude. A «Save File» is asked for per
    # action (a Save File in the Setup did not spare the draft's own window), so the draft's one window stays in the
    # first Critique.
    setup_before = [act_speak(L['speak.first_run']),
                    act_text(text_token(SETUP_PING), su_ping),
                    act_gpt(text_token('{P}', {'P': (su_ping, 'Text')}), su_gpt, split=False),
                    act_text(text_token('{A}', {'A': (su_gpt, 'Ask ChatGPT')}), su_txt),
                    # the same shape as every real request (the brevity line + the text): iOS asked «send 2 text items to
                    # Claude» in the first Critique after a 1-item ping in the Setup
                    act_claude(text_token('{P}', {'P': (su_txt, 'Text')}), su_claude, split=False)]
    setup_before.append(act_notify(L['speak.ready']))
    setup_after = [act_speak(L['speak.ready'])]

    actions = [
        act_comment(L['comment.main']),

        # ---- D-128 (18.11, the owner's Siri run): the first run is a «Setup» step, before the question. Under Siri with
        # the phone locked a permission window comes up silently and the run stands still, and the windows came at
        # different steps. So, once: Duo says what is coming, then calls in a row every action that asks — ChatGPT,
        # Claude, the one file write (the stamp below), the update check on the web, the notification — and says it is
        # ready. A working run after that asks nothing. The two AI calls are one-word requests (one message each).
        *version_check(L, VK, RELEASE_NAME, lang, setup=(setup_before, setup_after), stamp_name=SETUP_FILE),

        # D-29: the person's two optional shortcuts (C-1 «Critique right away», C-3 «ask without editing»), read from
        # ONE small file; a missing file (the default) is no value and nothing changes. Each run starts with them unset. READ BEFORE the resume menu (D-29 B-1):
        # on a run that goes on from a saved draft the final «More…» menu still saves these two switches, and an unset
        # «OFF» flag would read as «on» and write QUICK=1 / MODE=critique the person never chose.
        *clear_variable(FORCE_MENU), *clear_variable(SHARED_VAR), *clear_variable(PREFS_CHANGED),
        *set_text(MODE_OFF, '1'), *set_text(QUICK_OFF, '1'),
        act_get_file(PREFS_FILE, pf_get),
        act_text(text_token('{F}', {'F': (pf_get, 'File')}), pf_txt),
        # whole lines only (Codex): «QUICK=10» or «XMODE=critique» switch nothing on
        act_first_match(pf_txt, 'Text', r'(?m)^MODE=critique$', pf_m1),
        if_output(g_pf1, pf_m1, 'Matches', 100),
        *clear_variable(MODE_OFF),
        if_close(g_pf1),
        act_first_match(pf_txt, 'Text', r'(?m)^QUICK=1$', pf_m2),
        if_output(g_pf2, pf_m2, 'Matches', 100),
        *clear_variable(QUICK_OFF),
        if_close(g_pf2),
        *clear_variable(PREFS_CHANGED),   # a plain Nothing right after the file's Ifs ends any chain from them

        # ---- Duo 6.4: a Critique cut off by a message limit within DRAFT_MINUTES → go on from its draft (D-101)
        *resume_block(),
        *if_text(g_fresh, RESUME_VAR, present=False),

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
        # the text came from Share (not from the clipboard): only then «ask without editing» may apply
        *if_text(g_sh, START_VAR),
        *set_text(SHARED_VAR, '1'),
        if_close(g_sh),
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
        # D-29: Duo's own re-runs («Another mode», Recipes, «go back») start with MENU_MARK: cut it off, and show the
        # question box and the mode menu whatever the person's two optional shortcuts say.
        act_get_variable(START_VAR, mk_get),
        # only at the very START of the text (Codex): a marker typed in the middle of a question is just text
        act_first_match(mk_get, 'Variable', r'^⟦duo-menu⟧\n', mk_m),
        if_output(g_mk, mk_m, 'Matches', 100),
        *set_text(FORCE_MENU, '1'),
        act_first_match(mk_get, 'Variable', r'(?s)(?<=^⟦duo-menu⟧\n).*', mk_rep),
        act_set_variable(START_VAR, mk_rep, 'Matches'),
        if_close(g_mk),
        *clear_variable(KEEP_Q),
        act_get_variable(START_VAR, bk_get),
        act_first_match(bk_get, 'Variable', r'^⟦duo-mode⟧\n', bk_m),
        if_output(g_bk, bk_m, 'Matches', 100),
        *set_text(FORCE_MENU, '1'),
        *set_text(KEEP_Q, '1'),
        act_first_match(bk_get, 'Variable', r'(?s)(?<=^⟦duo-mode⟧\n).*', bk_rep),
        act_set_variable(START_VAR, bk_rep, 'Matches'),
        if_close(g_bk),
        # «Critique right away» (C-1): skip the mode menu. «Ask without editing» (C-3): a text SHARED to Duo with at
        # least three words (a lone link or a code is still put in the box) goes without the question box.
        # Both start as constants and are only cleared (see MODE_OFF above): nothing here is built inside an If that
        # depends on the prefs file.
        *set_text(SKIP_MENU, '1'),
        *clear_when(MODE_OFF, True, SKIP_MENU),
        *clear_when(FORCE_MENU, True, SKIP_MENU),
        *set_text(SKIP_Q, '1'),
        *clear_when(QUICK_OFF, True, SKIP_Q),
        *clear_when(SHARED_VAR, False, SKIP_Q),
        *clear_when(FORCE_MENU, True, SKIP_Q),
        act_get_variable(START_VAR, qw_get),
        # three words, or six Chinese / Japanese / Korean characters in a row (their text has no spaces between words)
        act_first_match(qw_get, 'Variable', r'\S+\s+\S+\s+\S+|[\u3040-\u9fff\uac00-\ud7af]{6,}', qw_m),
        if_output(g_qd, qw_m, 'Matches', 101),
        *clear_variable(SKIP_Q),
        if_close(g_qd),
        # «Back» from «More…»: the question is already there, the field is skipped (whatever its length)
        *if_text(g_keepq, KEEP_Q),
        *set_text(SKIP_Q, '1'),
        if_close(g_keepq),
        *if_text(g_askq, SKIP_Q, present=False),
        act_get_variable(START_VAR, st_get),
        act_ask(L['ask.question'], question, default_from=(st_get, 'Variable')),
        # An empty question would spend 1–8 messages on nothing, so no AI is asked. Instead of a dead end the person
        # gets the Recipes (ready tasks): «I don't know what to ask» is one tap from a recipe; the menu's own Cancel
        # ends the run, as the old stop did. Recipes run Duo again with their wording in the question field.
        if_output(g_blank, question, 'Provided Input', 101),
        *recipes_menu(g_rec0, L['menu.empty_title']),
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.exit', 'WFWorkflowActionParameters': {}},
        if_close(g_blank),
        act_set_variable(QVAR, question, 'Provided Input'),
        if_else(g_askq),
        act_get_variable(START_VAR, sk_get),
        act_set_variable(QVAR, sk_get, 'Variable'),
        if_close(g_askq),
        act_get_variable(QVAR, qpre),
        # the mode menu, or straight to Critique (C-1)
        *if_text(g_skm, SKIP_MENU),
        *set_text(CRIT_VAR, '1'),
        if_else(g_skm),
        menu_open(g_main, L['menu.main_title'], MAIN),

        # ---- Critique: ChatGPT answers, Claude verifies and finalizes. It runs after the mode menu (below), so a
        # resumed draft reaches the same actions — and the same single «Save File» — without the menu (Duo 6.4)
        menu_case(g_main, MAIN[0]),
        *set_text(CRIT_VAR, '1'),

        # ---- Debate until agreement: ChatGPT takes a side, Claude objects, ChatGPT answers… up to three
        # rounds; a side that is convinced starts its reply with the marker and the debate stops there.
        # Then Claude, as a neutral recorder: where they agreed / what is still disputed / what you decide.
        menu_case(g_main, MAIN[1]),
        act_step('argue_start'),
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
        act_step('argue_verdict'),
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
        act_step('advisor_start'),
        *set_text(ONLY_CLAUDE, '1'),
        act_text(text_token(L.prompt('advisor').replace('{CRITIQUE}', MAIN[0].split(' · ')[0].split(' — ')[0]), Q), ad_prompt),
        act_claude(text_token('{P}', {'P': (ad_prompt, 'Text')}), ad_claude),
        act_set_variable(RESULT, ad_claude, 'Ask Claude'),
        *journal_note(('advisor', L['journal.advisor'])),

        # ---- Side by side: both answer independently, answers shown together
        menu_case(g_main, MAIN[3]),
        act_step('survey_start'),
        *sb_brief,
        act_text(text_token('{B}' + L.prompt('wrap'), {**Q, 'B': (sb_brief_get, 'Variable')}), sb_wrap),
        act_gpt(text_token('{P}', {'P': (sb_wrap, 'Text')}), sb_gpt),
        # Yuri 10.11 (No.52): the step is named in the notification, so a run that iOS stops here says where it stopped
        # (and that ChatGPT's answer is in the clipboard)
        *keep_gpt(sb_gpt, 'Ask ChatGPT', 'survey_step2'),
        act_claude(text_token('{P}', {'P': (sb_wrap, 'Text')}), sb_claude),
        act_set_variable(SIDE_CLAUDE, sb_claude, 'Ask Claude'),
        # an empty Claude answer: ask once more, as Critique does
        *if_text(g_sbretry, SIDE_CLAUDE, present=False),
        act_claude(text_token('{P}', {'P': (sb_wrap, 'Text')}), sb_claude2),
        act_set_variable(SIDE_CLAUDE, sb_claude2, 'Ask Claude'),
        if_close(g_sbretry),
        *if_text(g_sbok, SIDE_CLAUDE),
        act_get_variable(SIDE_CLAUDE, sb_cget),
        # ChatGPT empty, Claude answered: the honest line about ChatGPT instead of an empty block
        *if_output_text(g_sbg2, sb_gpt, 'Ask ChatGPT'),
        act_text(text_token(L['output.survey'],
                            {'G': (sb_gpt, 'Ask ChatGPT'), 'C': (sb_cget, 'Variable')}), sb_join),
        act_set_variable(RESULT, sb_join, 'Text'),
        if_else(g_sbg2),
        *set_text(RESULT, L['output.gpt_down'], {'C': (sb_cget, 'Variable')}),
        if_close(g_sbg2),
        if_else(g_sbok),
        # Claude gave nothing: ChatGPT's answer with the line about Claude (as in Critique); nothing at all → the tail
        # says «no answer came»
        *if_output_text(g_sbgpt, sb_gpt, 'Ask ChatGPT'),
        *set_text(RESULT, L['output.claude_down'], {'A': (sb_gpt, 'Ask ChatGPT')}),
        if_close(g_sbgpt),
        if_close(g_sbok),
        *journal_note(('survey', L['journal.survey'])),

        # ---- Synthesis: both answer blind, then one of them anchors the assembly
        menu_case(g_main, MAIN[4]),
        menu_open(g_anchor, L['menu.anchor_title'], L['menu.anchor_items']),

        menu_case(g_anchor, L['menu.anchor_items'][0]),
        act_step('synthesis_claude_start'),
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
        act_step('synthesis_gpt_start'),
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
        act_step('auto_start'),
        act_text(text_token(L.prompt('auto-router'), Q), au_prompt),
        service_call(au_prompt, au_gpt)[0],
        act_text(text_token(L['output.auto'], {'R': (au_gpt, service_call(au_prompt, au_gpt)[1])}), au_text),
        act_set_variable(RESULT, au_text, 'Text'),
        *journal_note(('auto', L['journal.auto'])),

        # ---- More…: the less frequent modes plus built-in help
        menu_case(g_main, MAIN[6]),
        menu_open(g_extra, L['menu.extra_title'], EXTRA + [L['menu.back']]),

        # ---- Decision: fast view, cautious view, referee
        menu_case(g_extra, EXTRA[0]),
        act_step('decision_start'),
        act_text(text_token(L.prompt('decision-1-fast'), Q), de_fast),
        act_gpt(text_token('{P}', {'P': (de_fast, 'Text')}), de_gpt),
        *keep_gpt(de_gpt, 'Ask ChatGPT', 'decision_step2'),
        act_text(text_token(L.prompt('decision-2-cautious'), Q), de_caution),
        act_claude(text_token('{P}', {'P': (de_caution, 'Text')}), de_claude),
        act_step('decision_step3'),
        act_text(text_token(L.prompt('decision-3-referee'),
                            {**QUESTION, 'FAST': (de_gpt, 'Ask ChatGPT'),
                             'CAUTIOUS': (de_claude, 'Ask Claude')}), de_referee),
        act_claude(text_token('{P}', {'P': (de_referee, 'Text')}), de_final),
        act_set_variable(RESULT, de_final, 'Ask Claude'),
        *journal_note(('decision', L['journal.decision']),
                      {'X': (de_gpt, 'Ask ChatGPT'), 'Y': (de_claude, 'Ask Claude')}),

        # ---- Dispute map: where the two agree, where they don't, what to verify
        menu_case(g_extra, EXTRA[1]),
        act_step('disputemap_start'),
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
        act_step('debate_start'),
        act_text(text_token(L.prompt('wrap'), Q), db_wrap),
        act_gpt(text_token('{P}', {'P': (db_wrap, 'Text')}), db_draft),
        *keep_gpt(db_draft, 'Ask ChatGPT', 'debate_step2'),
        # blind first: Claude answers the question on its own (it does not see ChatGPT's draft); only then
        # ChatGPT sees both and revises, and the judge sees both originals and the revision — still 4 messages
        act_claude(text_token('{P}', {'P': (db_wrap, 'Text')}), db_crit),
        act_step('debate_step3'),
        act_text(text_token(L.prompt('debate-2-compare'),
                            {**QUESTION, 'DRAFT': (db_draft, 'Ask ChatGPT'),
                             'OTHER': (db_crit, 'Ask Claude')}), db_rev_prompt),
        act_gpt(text_token('{P}', {'P': (db_rev_prompt, 'Text')}), db_rev),
        act_step('debate_step4'),
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
        act_step('clarify_step1'),
        act_text(text_token(L.prompt('clarify-1-questions'), Q), cl_prompt),
        service_call(cl_prompt, cl_gpt)[0],
        act_ask(text_token('{Q}' + L['ask.clarify_suffix'], {'Q': (cl_gpt, service_call(cl_prompt, cl_gpt)[1])}),
                cl_ask, default=L['ask.clarify_default']),
        act_step('clarify_step2'),
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
        act_step('image_step1'),
        act_text(text_token(L.prompt('image-svg-brief'), Q), i1_brief),
        act_gpt(text_token('{P}', {'P': (i1_brief, 'Text')}), i1_gpt, brief=False),
        *keep_gpt(i1_gpt, 'Ask ChatGPT', 'image_step2'),
        act_claude(text_token('{P}', {'P': (i1_brief, 'Text')}), i1_claude, brief=False),
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
        act_step('image_step1'),
        act_text(text_token(L.prompt('image-svg-brief'), Q), i2_brief),
        act_gpt(text_token('{P}', {'P': (i2_brief, 'Text')}), i2_gpt, brief=False),
        *keep_gpt(i2_gpt, 'Ask ChatGPT', 'image_step2'),
        act_claude(text_token('{P}', {'P': (i2_brief, 'Text')}), i2_claude, brief=False),
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
        act_step('image_judge'),
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
        act_step('delta_step1'),
        act_text(text_token(L.prompt('wrap'), Q), dl_wrap),
        act_claude(text_token('{P}', {'P': (dl_wrap, 'Text')}), dl_claude),
        act_step('delta_step2'),
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
        act_step('reverse_start'),
        act_text(text_token(L.prompt('wrap'), Q), rv_wrap),
        act_claude(text_token('{P}', {'P': (rv_wrap, 'Text')}), rv_claude),
        act_text(text_token(L.prompt('critique-reverse'),
                            {**QUESTION, 'CLAUDE_ANSWER': (rv_claude, 'Ask Claude')}), rv_prompt),
        act_step('critique_step2'),
        act_gpt(text_token('{P}', {'P': (rv_prompt, 'Text')}), rv_gpt),
        act_step('critique_summary'),
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
            *rerun_with_menu(qpre, 'Variable'),
            {'WFWorkflowActionIdentifier': 'is.workflow.actions.exit', 'WFWorkflowActionParameters': {}},
            menu_close(g_mmenu),
            if_close(g_mm),
            act_get_variable(MY_RULE, mm_rule)], rule_uid=mm_rule),
        # Back (Yuri 13.11, No.67): the main mode menu again with the same question; no question field, nothing spent
        menu_case(g_extra, L['menu.back']),
        act_text(text_token(MODE_MARK + '{Q}', {'Q': (qpre, 'Variable')}), bk_text),
        act_run_self(RUN_NAME, bk_text, 'Text'),
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.exit', 'WFWorkflowActionParameters': {}},
        menu_close(g_extra),
        menu_close(g_main),
        if_close(g_skm),
        if_close(g_fresh),
        # from here on the question is QVAR: typed now, or from a resumed draft (the question field did not run then)
        act_get_variable(QVAR, q_get),
        *if_text(g_crit, CRIT_VAR),
        *critique_block(qsrc=(q_get, 'Variable'), draft=True),
        if_close(g_crit),

        # ---- Shared tail: deliver, then record, then offer another run
        # no answer at all, or Claude stopped and RESULT is ChatGPT's answer alone (Duo 6.4): «check with…» comes
        # FIRST, so whatever it delivers is copied and remembered by the one clipboard write and the one save below
        # (each such action is its own permission window on the first run). Cancelling the menu ends the run, but
        # ChatGPT's answer is already in the clipboard then (keep_gpt).
        *if_text(g_empty, RESULT, present=False),
        *if_text(g_oc2, ONLY_CLAUDE),
        act_notify(L['notify.tail_empty_claude']),
        act_alert(L['alert.no_answer_title'], L['alert.no_answer_claude_body']),
        if_else(g_oc2),
        act_notify(L['notify.tail_empty']),
        # Yuri 13.11 (No.53): a run whose AI actions came back empty ended with nothing on screen, although both apps
        # held answers. One window says so and where the answers are; no clipboard write (the person's own clipboard,
        # often their question, stays as it is). Whoever DID answer is shown by the modes themselves (claude_down /
        # gpt_down) and never reaches this branch.
        act_alert(L['alert.no_answer_title'], L['alert.no_answer_body']),
        if_close(g_oc2),
        *set_text(CLAUDE_DOWN, '1'),
        if_close(g_empty),
        *if_text(g_down, CLAUDE_DOWN),
        *claude_down_menu(),
        if_close(g_down),
        # D-128 (18.11, the owner's Siri run): no «Copy to Clipboard» and no journal «Append to File» here. Each was a
        # permission window of its own on the first run, and under Siri with the phone locked such a window comes up
        # silently and the run stands still. The answer is shown; «Open Poly» and «Save to Notes» take it from there.
        # The Critique draft stays the run's one file write (rule No.7).
        *if_text(g_tlrem, RESULT),
        *strip_more(RESULT),
        *strip_markdown(RESULT),   # Yuri 10.11, No.56: no raw «**» on the result screen or in its title
        act_notify(L['notify.tail_done']),
        if_close(g_tlrem),
        # ONE Quick Look, after the «Claude did not answer» menu too, and only when there is something to show
        *if_text(g_show, RESULT),
        act_quick_look(variable(RESULT)),
        if_close(g_show),
        menu_open(g_finale, L['menu.finale_title'], L['menu.finale_items']),
        menu_case(g_finale, L['menu.finale_items'][0]),
        menu_case(g_finale, L['menu.finale_items'][1]),
        *rerun_with_menu(q_get, 'Variable'),
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.exit', 'WFWorkflowActionParameters': {}},
        # ---- More…: one extra step for the person who wants it; the usual «Done / Another mode» stays two taps
        # D-185: «Open in Poly» — a menu item only; Poly reads the answer from the clipboard, so it is copied here,
        # when the person picks it (D-128: no clipboard write on the main path)
        menu_case(g_finale, L['menu.finale_items'][2]),
        act_clipboard(variable(RESULT)),
        act_get_variable(RESULT, op_get),
        *remember_answer(op_get, 'Variable'),   # the next run must not take this answer for a new question
        open_poly_url('duo'),
        menu_case(g_finale, L['menu.finale_items'][3]),
        menu_open(g_more, L['menu.finale_more_title'], L['menu.finale_more_items']),

        # Check the result again: ChatGPT looks for errors in the final result; the block is added below it
        menu_case(g_more, L['menu.finale_more_items'][0]),
        act_step('ratify'),
        act_get_variable(RESULT, fn_get),
        act_text(text_token(L.prompt('ratify'), {'QUESTION': QV['Q'], 'RESULT': (fn_get, 'Variable')}), fn_prompt),
        act_gpt(text_token('{P}', {'P': (fn_prompt, 'Text')}), fn_gpt),
        act_text(text_token(L['output.ratify'], {'R': (fn_get, 'Variable'), 'X': (fn_gpt, 'Ask ChatGPT')}), fn_out),
        act_set_variable(RESULT, fn_out, 'Text'),
        *strip_markdown(RESULT),
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
        # D-29: the person's two optional shortcuts. Each case only changes the variables; ONE «Save File» below
        # writes the file when a case ran. «Show all menus again» empties both.
        menu_case(g_more, L['menu.finale_more_items'][4]),
        *clear_variable(MODE_OFF),
        *set_text(PREFS_CHANGED, '1'), *set_text(NOTE_MODE, '1'),
        menu_case(g_more, L['menu.finale_more_items'][5]),
        *clear_variable(QUICK_OFF),
        *set_text(PREFS_CHANGED, '1'), *set_text(NOTE_QUICK, '1'),
        menu_case(g_more, L['menu.finale_more_items'][6]),
        *set_text(MODE_OFF, '1'),
        *set_text(QUICK_OFF, '1'),
        *set_text(PREFS_CHANGED, '1'), *set_text(NOTE_RESET, '1'),
        # D-128: «Worked / didn't work / idea» — opens the Feedback issue form on GitHub (nothing is sent here)
        menu_case(g_more, L['menu.finale_more_items'][7]),
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.openurl',
         'WFWorkflowActionParameters': {'WFInput': text_token(FEEDBACK_URL, {}), 'Show-WFInput': True}},
        menu_case(g_more, L['menu.finale_more_items'][8]),
        act_clipboard(variable(RESULT)),   # D-128: Poly reads the answer from the clipboard; copied only on this pick
        act_get_variable(RESULT, op_get2),
        *remember_answer(op_get2, 'Variable'),
        open_poly_url('duo'),
        menu_close(g_more),
        *if_text(g_pc, PREFS_CHANGED),
        # the file is rebuilt from the two clean flags: the header, then one line for each option that is ON
        *set_text(PREFS_BODY, PREFS_HEAD),
        *append_line_when(MODE_OFF, 'MODE=critique'),
        *append_line_when(QUICK_OFF, 'QUICK=1'),
        act_get_variable(PREFS_BODY, pm_get),
        act_text(text_token('{B}', {'B': (pm_get, 'Variable')}), pf_new),
        act_save_file(PREFS_FILE, pf_new, pf_save),
        # «Saved» is told only AFTER the file is written (a refused or failed save must not say it worked)
        *if_text(g_n1, NOTE_MODE),
        act_notify(L['notify.pref_mode']),
        if_close(g_n1),
        *if_text(g_n2, NOTE_QUICK),
        act_notify(L['notify.pref_quick']),
        if_close(g_n2),
        *if_text(g_n3, NOTE_RESET),
        act_notify(L['notify.pref_reset']),
        if_close(g_n3),
        if_close(g_pc),
        menu_close(g_finale),

        # ---- Last of all, at most once a week: is there a newer Duo? (version_check; the first run's Setup checked)
        *version_check(L, VK, RELEASE_NAME, lang, stamp_name=SETUP_FILE),
    ]

    actions, continuing = with_continuation(actions, L.prompt('continue'))   # Duo 6.11: a long answer comes in parts
    set_more_line('')
    actions = with_gpt_retry(actions, skip=RETRY_SKIP | continuing)
    actions = with_gpt_clean(actions)
    actions = with_claude_vars(actions)
    diag = os.environ.get('C1_DIAG') == '1'
    if diag:
        actions = with_diag(actions)
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

    out_dir = Path(os.environ.get('C1_DIST', ROOT / ('dist-diag' if diag else 'dist'))) / lang / ('ai' if ai else '')
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{L['shortcut_names.main']}{'-diag' if diag else ''}.shortcut"
    with out.open('wb') as f:
        plistlib.dump(workflow, f, fmt=plistlib.FMT_BINARY)
    print(f'{lang}: {out.name} — {len(actions)} actions')



from shortcut_transforms import *  # noqa: F401,F403,E402
from shortcut_validate import *  # noqa: F401,F403,E402




if __name__ == '__main__':
    languages = sys.argv[1:] or [d.name for d in sorted((ROOT / 'locales').iterdir()) if d.is_dir()]
    for language in languages:
        build(language)
        build(language, ai=True)  # only where trio.json has the Apple Intelligence words
