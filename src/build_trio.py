#!/usr/bin/env python3
"""Build the Trio shortcut for one locale.

Usage:  python3 src/build_trio.py <lang>
Output: dist/<lang>/Trio.shortcut  (unsigned; tools/build.sh signs it)

Trio is the Critique pair plus a third voice from a third company:
  1. ChatGPT answers the wrapped question (Ask ChatGPT, the person's own app);
  2. Claude answers the SAME wrapped question on its own, without seeing ChatGPT's answer (blind, as Critique in Duo);
  3. a third model, reached with «Get Contents of URL» on a FREE key, reads the question and BOTH independent
     answers and names only the errors and gaps that BOTH missed (prompt trio.txt). Its words come back as a
     separate block, never merged;
  4. one Claude message compares the three (prompt trio-compare.txt): «matched independently / did not match /
     what to check yourself», then «■ FINAL ANSWER». ChatGPT + Claude messages: 1 + 2 = 3, as before the blind scheme.

The third voice speaks the OpenAI chat-completions dialect, so one request template serves every
free provider: NVIDIA build (Kimi K3, GLM-5.3, DeepSeek V4.1), Google AI Studio (Gemini Flash),
OpenRouter (its `:free` models) and Groq. The person may save any number of free keys; each is
recognised by how it begins (nvapi- → NVIDIA, AIza/AQ. → Google, sk-or- → OpenRouter, gsk_ → Groq). Trio walks every model of every key until one answers: a busy model (503)
moves to the next model; a limit (429) never sends it to another key of the same provider — the free limit
belongs to the project/account, not to the key (see PER_MODEL_LIMIT below), a key with no money (402) or an invalid key (401)
is not asked again. Only when all of them failed does the block say what each one answered and what
to do — never «invalid key» for a key that merely ran out of money or was busy.

The keys are NOT in the shortcut. They are read from iCloud Drive → Shortcuts → poly-key.txt (one per
line); on the first run the shortcut asks for them and saves them there. A shared shortcut therefore
never carries a key.

PAID keys (owner, 2026-10-01: «a well-off person may paste their own paid API keys»). Free keys stay the
first thing a newcomer is asked for; a paid key is optional and recognised the same way, by how it begins:
sk-ant- → Anthropic, xai- → xAI, sk-<32 hex> → DeepSeek, any other sk- (sk-proj-, sk-svcacct-…) → OpenAI.
The person pays their provider directly; nothing passes through us. The third voice must come from a THIRD
company — ChatGPT (OpenAI) and Claude (Anthropic) already spoke — so a paid xAI (Grok) or DeepSeek key goes
first, ahead of every free key; a paid OpenAI or Anthropic key goes last, after the free chain: a third
company on a free key adds more than a second word from the same company. Models checked against the
providers' docs on 2026-10-01: grok-4.7 → grok-4.6 (docs.x.ai), deepseek-v4-pro → deepseek-flash
(api-docs.deepseek.com), claude-opus-5 → claude-sonnet-5 (native Messages API, thinking off so the first
content block is the text), gpt-6-astra → gpt-6.1-sol (Chat Completions, `max_completion_tokens`).

Locales without locales/<lang>/trio.json are skipped: Trio ships where its words exist.

The result comes in three blocks first, then Claude's final answer (both from the one comparing message,
prompt trio-compare.txt); the third voice follows in full as its own block. If the comparison does not come,
the person gets Claude's own independent answer in its place. (summary-trio.txt is no longer used by Trio.)

TRIO WITHOUT A KEY (plan item 12, owner 2026-10-11; `build(lang, nokey=True)` → dist/<lang>/nokey/Trio.shortcut,
only for locales whose trio.json has `nokey.comment` — Apple Intelligence languages: en, es, pt). The same
Trio, never asking for a key: if poly-key.txt holds keys, the key chain above runs as usual; with no key
file, or when none of the keys answered, the third voice is Shortcuts' own «Use Model» action
(Apple Intelligence; prompt trio-nokey.txt). It keeps the name «Trio» (Duo's «another mode» calls that name)
and has its own number in releases/version.json, `trio_nokey`, with links `trio_nokey_<lang>`.
"""
import json
import os
import plistlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_shortcut import (  # noqa: E402
    ROOT, Locale, new_uuid, text_token, attachment, variable, validate,
    act_ask, act_gpt, act_claude, act_text, act_set_variable, act_get_variable,
    act_comment, act_clipboard, act_quick_look, act_get_file, act_save_file, act_alert,
    if_has_value, if_else, if_close, if_output, version_check,
    act_delay, act_first_match, act_first_chars, repeat_open, repeat_close, if_item_missing, if_no_value, LONG_TEXT,
    clear_variable, if_text, if_output_text, act_replace_text, act_match_number,
)

# Endpoints and model ids live in src/models.json (tools/check_models.py checks them against the providers).
_P = json.loads((Path(__file__).resolve().parent / 'models.json').read_text(encoding='utf-8'))['providers']
# NVIDIA build first: the strongest free models today, three companies on one key without a card
# (Kimi K3 — Moonshot, DeepSeek V4.1 — DeepSeek, GLM-5.3 — Zhipu; integrate.api.nvidia.com/v1/models,
# 2026-10-01). About 40 requests a minute per account, no daily cap. Sign-up asks for a phone (SMS).
NVIDIA_URL = _P['nvidia']['url']
# Order Kimi → GLM → DeepSeek: live on 2026-10-01 GLM-5.3 answered in 12 s, DeepSeek V4.1 stayed
# silent for 90–120 s — the slow one goes last. «Get Contents of URL» has no timeout setting, so a
# silent model holds Trio until the system gives up; only order protects the person.
NVIDIA_MODELS = _P['nvidia']['models']
# Service tokens a model may leak into its text: Kimi K3 on NVIDIA ended a live answer (2026-10-01)
# with `<|close|>message`. A trailing «token + word» goes whole, any other token alone.
TOKEN_TAIL_RE = r'(?:<\|[^|>\n]{1,40}\|>[A-Za-z_]{0,20}\s*)+$'
TOKEN_RE = r'<\|[^|>\n]{1,40}\|>'
NVIDIA_KEY_RE = r'nvapi-[0-9A-Za-z_-]{20,}'
GEMINI_URL = _P['gemini']['url']
# Free quota is counted per model (~20 a day each), and a model may be «high demand» (503) while the
# next one answers — so one key walks a chain. Checked live 2026-10-01: 3.8 answered 503, 3.6 and 2.5
# answered; a key with a spent prepaid balance answers 402 on every model.
# Gemini Pro is not free any more (3.1-pro: 429 «limit 0», 2.5-pro: 404 «no longer available to new
# users» — live, 2026-10-01), so every free Flash, each with its own daily quota.
GEMINI_MODELS = _P['gemini']['models']
OPENROUTER_URL = _P['openrouter']['url']
# OpenRouter's free models (`:free`, price 0), four companies; checked against /api/v1/models and
# with real requests on 2026-10-01. `openrouter/free` is OpenRouter's own router over whichever free
# model is up — the last resort. Nemotron Ultra (empty replies) and Inkling (agent apps only) left out.
OPENROUTER_MODELS = _P['openrouter']['models']
GROQ_URL = _P['groq']['url']
GROQ_MODELS = _P['groq']['models']   # checked against /openai/v1/models
# Keys are picked out of poly-key.txt by how they begin, so the person may paste any number of keys,
# in any order, with any spaces or line breaks around them: nvapi-… → NVIDIA, AIza… / AQ.… → Google
# AI Studio, sk-or-… → OpenRouter, gsk_… → Groq.
GOOGLE_KEY_RE = r'(?:AIza[0-9A-Za-z_-]{30,}|AQ\.[0-9A-Za-z._-]{20,})'
OPENROUTER_KEY_RE = r'sk-or-[0-9A-Za-z_-]{20,}'
GROQ_KEY_RE = r'gsk_[A-Za-z0-9]+'
# Paid keys (optional). Lookarounds keep one key from being read as another: a DeepSeek key is exactly
# sk- and 32 lowercase hex characters; OpenAI is any other sk- that is not OpenRouter's or Anthropic's.
_EDGE_L, _EDGE_R = r'(?<![0-9A-Za-z_-])', r'(?![0-9A-Za-z_-])'
ANTHROPIC_KEY_RE = _EDGE_L + r'sk-ant-[0-9A-Za-z_-]{20,}'
XAI_KEY_RE = _EDGE_L + r'xai-[0-9A-Za-z_-]{20,}'
DEEPSEEK_KEY_RE = _EDGE_L + r'sk-[0-9a-f]{32}' + _EDGE_R
OPENAI_KEY_RE = _EDGE_L + r'sk-(?!ant-|or-)(?![0-9a-f]{32}' + _EDGE_R + r')[0-9A-Za-z_-]{20,}'
ANTHROPIC_URL = _P['anthropic']['url']
ANTHROPIC_MODELS = _P['anthropic']['models']
OPENAI_URL = _P['openai']['url']
OPENAI_MODELS = _P['openai']['models']
XAI_URL = _P['xai']['url']
XAI_MODELS = _P['xai']['models']
DEEPSEEK_URL = _P['deepseek']['url']
DEEPSEEK_MODELS = _P['deepseek']['models']
ANTHROPIC_MAX_TOKENS = '4096'
# OpenAI's reasoning models count their thinking against max_completion_tokens.
OPENAI_MAX_TOKENS = '8000'
# Groq's free tier allows 1000 OUTPUT tokens a minute; a request that may exceed it is refused
# outright, so the answer is capped below that. 900 is ample for «only what both missed».
MAX_TOKENS = '900'
# OpenRouter's free models think before they answer; the thinking counts against max_tokens.
OPENROUTER_MAX_TOKENS = '4000'


# ---------------------------------------------------------------- actions this shortcut adds

def act_notify(title, body):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.notification',
            'WFWorkflowActionParameters': {'WFNotificationActionTitle': title,
                                           'WFNotificationActionBody': body,
                                           'WFNotificationActionSound': False}}


def act_match(pattern, src_uid, src_name, uid):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.text.match',
            'WFWorkflowActionParameters': {'WFMatchTextPattern': pattern,
                                           'WFMatchTextCaseSensitive': True,
                                           'text': text_token('{T}', {'T': (src_uid, src_name)}),
                                           'UUID': uid}}


def if_contains(group, var_name, needle):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.conditional',
            'WFWorkflowActionParameters': {'GroupingIdentifier': group, 'WFControlFlowMode': 0,
                                           'WFCondition': 99,  # «contains»
                                           'WFConditionalActionString': needle,
                                           'WFInput': {'Type': 'Variable',
                                                       'Variable': variable(var_name)}}}


def act_use_model(prompt_uid, uid):
    """Shortcuts' «Use Model» (Apple Intelligence), output «Response».

    Encoding checked 2026-10-11 against the system (the identifier `is.workflow.actions.askllm` and
    `WFLLMModel` / `WFGenerativeResultType` are in WorkflowKit on macOS 26.6) and against shortcuts built in
    the Shortcuts editor and exported (github.com/jagdishpal02000/apple-llm, shortcut_definition):
      · the prompt key is WFLLMPrompt — NOT WFInput: a wrong key imports fine, is silently dropped, and
        the action then waits forever on its interactive panel;
      · no WFLLMModel key on purpose: the action then uses its default model — Private Cloud Compute on
        iOS/macOS 26; on 27 the old values «Private Cloud Compute» / «On-Device» fail to load and the
        default is «Apple Intelligence», which is what a missing key gives. One file works on both;
      · WFGenerativeResultType «Text»: plain text out (Automatic would reshape it for the next action);
      · no Follow Up key: off by default, the run never stops for a chat.
    """
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.askllm',
            'WFWorkflowActionParameters': {'WFLLMPrompt': text_token('{P}', {'P': (prompt_uid, 'Text')}),
                                           'WFGenerativeResultType': 'Text',
                                           'UUID': uid}}


def plain(text):
    return {'Value': {'string': text, 'attachmentsByRange': {}},
            'WFSerializationType': 'WFTextTokenString'}


def item_text(key, value):
    return {'WFItemType': 0, 'WFKey': plain(key), 'WFValue': value}


def item_number(key, number):
    return {'WFItemType': 3, 'WFKey': plain(key), 'WFValue': plain(number)}


def nested_dict(items):
    # a dictionary inside a dictionary or a list is wrapped twice — that is how Shortcuts writes it
    return {'Value': {'Value': {'WFDictionaryFieldValueItems': items},
                      'WFSerializationType': 'WFDictionaryFieldValue'},
            'WFSerializationType': 'WFDictionaryFieldValue'}


def top_dict(items):
    return {'Value': {'WFDictionaryFieldValueItems': items},
            'WFSerializationType': 'WFDictionaryFieldValue'}


def act_post_json(url_uid, key_uid, model_uid, prompt_uid, uid, max_uid=None,
                  max_field='max_tokens'):
    """POST {model, messages:[{role:user, content:prompt}], max_tokens} with a Bearer key.

    OpenAI's current models refuse `max_tokens` on Chat Completions and want `max_completion_tokens`."""
    src = 'Item from List' if max_uid else 'Variable'
    body = top_dict([
        item_text('model', text_token('{M}', {'M': (model_uid, src)})),
        {'WFItemType': 2, 'WFKey': plain('messages'),
         'WFValue': {'Value': [{'WFItemType': 1, 'WFValue': nested_dict([
             item_text('role', plain('user')),
             item_text('content', text_token('{P}', {'P': (prompt_uid, 'Text')})),
         ])}], 'WFSerializationType': 'WFArrayParameterState'}},
        (item_number(max_field, MAX_TOKENS) if max_uid is None else
         {'WFItemType': 3, 'WFKey': plain(max_field),
          'WFValue': text_token('{X}', {'X': (max_uid, 'Item from List')})}),
    ])
    headers = top_dict([
        item_text('Authorization', text_token('Bearer {K}', {'K': (key_uid, src)})),
        item_text('Content-Type', plain('application/json')),
    ])
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.downloadurl',
            'WFWorkflowActionParameters': {'WFURL': text_token('{U}', {'U': (url_uid, src)}),
                                           'WFHTTPMethod': 'POST',
                                           'ShowHeaders': True,
                                           'WFHTTPHeaders': headers,
                                           'WFHTTPBodyType': 'JSON',
                                           'WFJSONValues': body,
                                           'UUID': uid}}


def act_post_anthropic(url_uid, key_uid, model_uid, prompt_uid, max_uid, uid):
    """POST to Anthropic's native Messages API: `x-api-key`, `anthropic-version`, thinking off — so
    content[0] is the text block (with thinking on, content[0] is an empty thinking block)."""
    src = 'Item from List'
    body = top_dict([
        item_text('model', text_token('{M}', {'M': (model_uid, src)})),
        {'WFItemType': 3, 'WFKey': plain('max_tokens'),
         'WFValue': text_token('{X}', {'X': (max_uid, src)})},
        {'WFItemType': 1, 'WFKey': plain('thinking'),
         'WFValue': nested_dict([item_text('type', plain('disabled'))])},
        {'WFItemType': 2, 'WFKey': plain('messages'),
         'WFValue': {'Value': [{'WFItemType': 1, 'WFValue': nested_dict([
             item_text('role', plain('user')),
             item_text('content', text_token('{P}', {'P': (prompt_uid, 'Text')})),
         ])}], 'WFSerializationType': 'WFArrayParameterState'}},
    ])
    headers = top_dict([
        item_text('x-api-key', text_token('{K}', {'K': (key_uid, src)})),
        item_text('anthropic-version', plain('2023-06-01')),
        item_text('Content-Type', plain('application/json')),
    ])
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.downloadurl',
            'WFWorkflowActionParameters': {'WFURL': text_token('{U}', {'U': (url_uid, src)}),
                                           'WFHTTPMethod': 'POST',
                                           'ShowHeaders': True,
                                           'WFHTTPHeaders': headers,
                                           'WFHTTPBodyType': 'JSON',
                                           'WFJSONValues': body,
                                           'UUID': uid}}


def act_value(key, src_uid, src_name, uid):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.getvalueforkey',
            'WFWorkflowActionParameters': {'WFGetDictionaryValueType': 'Value',
                                           'WFDictionaryKey': key,
                                           'WFInput': attachment(src_uid, src_name),
                                           'UUID': uid}}


def act_first_item(src_uid, src_name, uid):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.getitemfromlist',
            'WFWorkflowActionParameters': {'WFItemSpecifier': 'First Item',
                                           'WFInput': attachment(src_uid, src_name),
                                           'UUID': uid}}


def set_text(var_name, template, uid, refs=None):
    return [act_text(text_token(template, refs or {}), uid),
            act_set_variable(var_name, uid, 'Text')]


def act_replace(src_uid, src_name, find, repl, uid):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.text.replace',
            'WFWorkflowActionParameters': {'WFInput': text_token('{T}', {'T': (src_uid, src_name)}),
                                           'WFReplaceTextFind': find,
                                           'WFReplaceTextReplace': repl,
                                           'WFReplaceTextRegularExpression': True,
                                           'WFReplaceTextCaseSensitive': True,
                                           'UUID': uid}}


def act_combine(src_uid, src_name, uid):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.text.combine',
            'WFWorkflowActionParameters': {'text': attachment(src_uid, src_name),
                                           'WFTextSeparator': 'New Lines', 'UUID': uid}}


def act_split(src_uid, src_name, separator, uid):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.text.split',
            'WFWorkflowActionParameters': {'text': text_token('{T}', {'T': (src_uid, src_name)}),
                                           'WFTextSeparator': 'Custom',
                                           'WFTextCustomSeparator': separator, 'UUID': uid}}


def act_item_at(src_uid, src_name, index, uid):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.getitemfromlist',
            'WFWorkflowActionParameters': {'WFItemSpecifier': 'Item At Index', 'WFItemIndex': index,
                                           'WFInput': attachment(src_uid, src_name), 'UUID': uid}}


def repeat_each(group, src_uid, src_name):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.repeat.each',
            'WFWorkflowActionParameters': {'GroupingIdentifier': group, 'WFControlFlowMode': 0,
                                           'WFInput': attachment(src_uid, src_name)}}


def repeat_each_close(group):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.repeat.each',
            'WFWorkflowActionParameters': {'GroupingIdentifier': group, 'WFControlFlowMode': 2}}


def act_set_from_repeat_item(var_name):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.setvariable',
            'WFWorkflowActionParameters': {'WFVariableName': var_name,
                                           'WFInput': {'Value': {'Type': 'Variable',
                                                                 'VariableName': 'Repeat Item'},
                                                       'WFSerializationType': 'WFTextTokenAttachment'}}}


def if_contains_ref(group, var_name, src_uid, src_name):
    """If <variable> contains the text of an earlier action's output."""
    action = if_contains(group, var_name, '')
    action['WFWorkflowActionParameters']['WFConditionalActionString'] = \
        text_token('{N}', {'N': (src_uid, src_name)})
    return action


def if_output_has_value(group, src_uid, src_name):
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.conditional',
            'WFWorkflowActionParameters': {'GroupingIdentifier': group, 'WFControlFlowMode': 0,
                                           'WFCondition': 100,
                                           'WFInput': {'Type': 'Variable',
                                                       'Variable': attachment(src_uid, src_name)}}}


def if_dict_text(group, src_uid):
    """If a Dictionary Value holds visible text: a Text made from it, Match Text `\\S`, If its Matches has a value."""
    t = new_uuid()
    return [act_text(text_token('{V}', {'V': (src_uid, 'Dictionary Value')}), t), *if_output_text(group, t, 'Text')]


def if_number_missing(group, var_name, item_uid):
    """If the number `item_uid` (a Get Variable of the Repeat Item) does not stand, as a whole number, in `var_name`."""
    esc, other, m = new_uuid(), new_uuid(), new_uuid()
    return [act_replace_text(item_uid, 'Variable', '.', '\\.', esc),
            act_get_variable(var_name, other),
            act_match_number(other, 'Variable', esc, 'Updated Text', m),
            if_output(group, m, 'Matches', 101)]


def if_no_value(group, var_name):
    action = if_has_value(group, var_name)
    action['WFWorkflowActionParameters']['WFCondition'] = 101  # «does not have any value»
    return action


# Every free provider and its model chain. One attempt = one (model, key) pair; the shortcut walks
# them in this order — every model of a provider over every key of that provider, then the next
# provider — until someone answers. Names checked live on 2026-10-01 (models lists + real requests).
PROVIDERS = [  # (locale name key, url, key regex, models, max_tokens)
    # paid keys of a THIRD company first (ChatGPT and Claude already spoke)
    ('provider.xai', XAI_URL, XAI_KEY_RE, XAI_MODELS, OPENROUTER_MAX_TOKENS),
    ('provider.deepseek', DEEPSEEK_URL, DEEPSEEK_KEY_RE, DEEPSEEK_MODELS, OPENROUTER_MAX_TOKENS),
    # then the free keys, strongest first
    ('provider.nvidia', NVIDIA_URL, NVIDIA_KEY_RE, NVIDIA_MODELS, OPENROUTER_MAX_TOKENS),
    ('provider.gemini', GEMINI_URL, GOOGLE_KEY_RE, GEMINI_MODELS, MAX_TOKENS),
    ('provider.openrouter', OPENROUTER_URL, OPENROUTER_KEY_RE, OPENROUTER_MODELS, OPENROUTER_MAX_TOKENS),
    ('provider.groq', GROQ_URL, GROQ_KEY_RE, GROQ_MODELS, MAX_TOKENS),
    # paid keys of the two companies already in the pair — last: same company, another model
    ('provider.anthropic', ANTHROPIC_URL, ANTHROPIC_KEY_RE, ANTHROPIC_MODELS, ANTHROPIC_MAX_TOKENS),
    ('provider.openai', OPENAI_URL, OPENAI_KEY_RE, OPENAI_MODELS, OPENAI_MAX_TOKENS),
]

# Trio without a key serves BOTH Poly A1 modes with one link, ordinary and USA (poly-a1
# store/TRIO-NO-KEY-RECIPE.md: «the third voice has no Chinese models»; TrioScreen shows the no-key card in
# USA mode too). So its saved-keys chain is the USA Trio's chain (poly-a1 scripts/trio-usa.py, ids checked
# 2026-10-07 against integrate.api.nvidia.com/v1/models and openrouter.ai/api/v1/models): US companies only,
# no DeepSeek paid key, no `openrouter/free` (OpenRouter picks that model itself, and it can be anyone's).
US_NVIDIA_MODELS = _P['nvidia']['us_models']
US_GROQ_MODELS = _P['groq']['us_models']
US_OPENROUTER_MODELS = _P['openrouter']['us_models']


def us_providers(providers):
    """`providers` with US models only: the DeepSeek paid key dropped, NVIDIA / Groq / OpenRouter swapped."""
    swap = {'provider.nvidia': US_NVIDIA_MODELS, 'provider.groq': US_GROQ_MODELS,
            'provider.openrouter': US_OPENROUTER_MODELS}
    return [(k, url, rx, swap.get(k, models), mt)
            for (k, url, rx, models, mt) in providers if k != 'provider.deepseek']

# A 429 (owner, 2026-10-02; providers' docs checked that day): the free limit is per project or account,
# not per key — Google: «Rate limits are applied per project, not per API key»
# (ai.google.dev/gemini-api/docs/rate-limits); Groq: «at the organization level»
# (console.groq.com/docs/rate-limits); OpenRouter: «Making additional accounts or API keys will not affect
# your rate limits» (openrouter.ai/docs/api/reference/limits); NVIDIA: per account. Keys of different
# accounts cannot be told apart, so a 429 pauses that provider for the rest of the run instead of trying
# its other keys: only that model at Google and Groq (their quota is per model too — the next Flash still
# has its own), the whole provider elsewhere (OpenRouter's free-models-per-day covers every :free model;
# NVIDIA's ~40 a minute is per account). One run is one question, so a per-minute limit is not retried.
PER_MODEL_LIMIT = ('generativelanguage.googleapis.com', 'api.groq.com')

# What a failed reply means. «Get Contents of URL» gives no status code, so the reply's own words
# decide: `"code": 402` (Gemini, OpenRouter) or a known phrase (Groq has no numeric code).
# (kind, dead key?, needles in the reply) — first match wins.
FAILS = [
    # a free-tier 429 first: Gemini's says «check your plan and billing details» — not «no money»
    ('limit', False, ['"code": 429', '"code":429', 'RESOURCE_EXHAUSTED']),
    ('billing', True, ['"code": 402', '"code":402', 'credits', 'billing', 'credit balance',
                       'insufficient_quota', 'Insufficient Balance']),
    ('region', True, ['location is not supported', 'not available in your country']),
    ('key', True, ['"code": 401', '"code":401', '"code": 403', '"code":403', 'API key', 'API Key',
                   'API_KEY', 'User not found', 'invalid_api_key', 'PERMISSION_DENIED',
                   '"status":401', '"status":403', 'Authorization failed', 'Unauthorized',
                   'authentication_error', 'permission_error', 'Authentication Fails',
                   'Incorrect API key']),
    ('limit', False, ['"code": 429', '"code":429', 'quota', 'rate_limit', 'rate-limited',
                      'RESOURCE_EXHAUSTED', 'Rate limit', '"status":429', 'Too Many Requests',
                      'rate_limit_error']),
    ('busy', False, ['"code": 503', '"code":503', '"code": 500', '"code":500', '"code": 502',
                     '"code":502', 'UNAVAILABLE', 'over capacity', 'high demand', 'overloaded',
                     '"status":500', '"status":502', '"status":503', '"status":504']),
    ('model', False, ['"code": 404', '"code":404', 'NOT_FOUND', 'model_not_found', 'No endpoints',
                      '"status":404', 'not_found_error']),
]


def pause_actions(u, V, paused_v):
    """Append «url|model#» (Google, Groq: quota per model) or «url#all» (everyone else) to the paused list."""
    pu, pm, old, m, mg, new_one, new_all = (u() for _ in range(7))
    return [
        act_get_variable(V['url'], pu), act_get_variable(V['model'], pm), act_get_variable(paused_v, old),
        act_match('|'.join(h.replace('.', r'\.') for h in PER_MODEL_LIMIT), pu, 'Variable', m),
        if_output_has_value(mg, m, 'Matches'),
        act_text(text_token('{D}\n{U}|{M}#', {'D': (old, 'Variable'), 'U': (pu, 'Variable'),
                                               'M': (pm, 'Variable')}), new_one),
        act_set_variable(paused_v, new_one, 'Text'),
        if_else(mg),
        act_text(text_token('{D}\n{U}#all', {'D': (old, 'Variable'), 'U': (pu, 'Variable')}), new_all),
        act_set_variable(paused_v, new_all, 'Text'),
        if_close(mg),
    ]


# ---------------------------------------------------------------- third voice with web search (plan item 12, 2026-10-26)
# Gemini's native generateContent with the google_search tool: free Flash models can ground an answer in a
# search and return the pages (groundingMetadata.groundingChunks[].web.{uri,title}). The OpenAI-compatible
# Gemini endpoint of PROVIDERS cannot do that, so this is a separate, first, silent attempt: any failure
# (4xx — e.g. a new key without 2.5 access —, 429, empty text, no network) leaves V['third'] empty and
# the ordinary chain below runs exactly as before.
# NOTE: a sample of a LIVE generateContent reply with groundingMetadata was not obtained (no Google key was
# used on this Mac); the paths below follow ai.google.dev docs. Verify with ONE real request.
_GS = json.loads((Path(__file__).resolve().parent / 'models.json').read_text(encoding='utf-8'))['gemini_search']
GEMINI_SEARCH_URL = _GS['base_url']
GEMINI_SEARCH_MODELS = _GS['models']
GEMINI_SEARCH_MAX_SOURCES = _GS['max_sources']


def act_post_gemini_search(url, key_uid, prompt_uid, uid):
    """POST {contents:[{role:user, parts:[{text}]}], tools:[{google_search:{}}]} with x-goog-api-key."""
    def array(key, dicts):
        return {'WFItemType': 2, 'WFKey': plain(key),
                'WFValue': {'Value': [{'WFItemType': 1, 'WFValue': d} for d in dicts],
                            'WFSerializationType': 'WFArrayParameterState'}}
    body = top_dict([
        array('contents', [nested_dict([
            item_text('role', plain('user')),
            array('parts', [nested_dict([
                item_text('text', text_token('{P}', {'P': (prompt_uid, 'Text')}))])]),
        ])]),
        array('tools', [nested_dict([{'WFItemType': 1, 'WFKey': plain('google_search'),
                                      'WFValue': nested_dict([])}])]),
    ])
    headers = top_dict([
        item_text('x-goog-api-key', text_token('{K}', {'K': (key_uid, 'Variable')})),
        item_text('Content-Type', plain('application/json')),
    ])
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.downloadurl',
            'WFWorkflowActionParameters': {'WFURL': plain(url), 'WFHTTPMethod': 'POST',
                                           'ShowHeaders': True, 'WFHTTPHeaders': headers,
                                           'WFHTTPBodyType': 'JSON', 'WFJSONValues': body,
                                           'UUID': uid}}


def act_first_items(src_uid, src_name, count, uid):
    """Get Items from List → «Items in Range» 1…count (the standard parameters WFItemRangeStart/End)."""
    return {'WFWorkflowActionIdentifier': 'is.workflow.actions.getitemfromlist',
            'WFWorkflowActionParameters': {'WFItemSpecifier': 'Items in Range', 'WFItemRangeStart': 1,
                                           'WFItemRangeEnd': count,
                                           'WFInput': attachment(src_uid, src_name), 'UUID': uid}}


def search_voice(T, V, prompt_uid, keys_uid, keys_name='Variable'):
    """If a Google key is among the keys: ask Gemini with search; on success V['third'] = text + «Sources:» lines."""
    u = new_uuid
    gkey_v = V.get('gkey', 'GoogleKey')
    found, g_loop = u(), u()
    # every Google key in turn (a revoked first one must not hide a working second one); once a model
    # has answered, V['third'] has a value and every later attempt is skipped by its own guard
    actions = [act_match(GOOGLE_KEY_RE, keys_uid, keys_name, found),
               repeat_each(g_loop, found, 'Matches'),
               act_set_from_repeat_item(gkey_v)]
    for model in GEMINI_SEARCH_MODELS:
        todo, k_get, post, raw, ok = u(), u(), u(), u(), u()
        cands, cand, content, parts, part, text, has_text = (u() for _ in range(7))
        chunks, five = u(), u()
        c_get, s_new = u(), u()
        s_has, joined_t, joined = u(), u(), u()
        actions += [
            if_no_value(todo, V['third']),
            act_get_variable(gkey_v, k_get),
            act_post_gemini_search(f'{GEMINI_SEARCH_URL}/{model}:generateContent', k_get, prompt_uid, post),
            act_text(text_token('{R}', {'R': (post, 'Contents of URL')}), raw),
            act_set_variable(V['raw'], raw, 'Text'),
            # an answer carries "candidates"; every error (4xx, 429, 5xx) does not → fall through quietly
            if_contains(ok, V['raw'], '"candidates"'),
            act_value('candidates', post, 'Contents of URL', cands),
            act_first_item(cands, 'Dictionary Value', cand),
            act_value('content', cand, 'Item from List', content),
            act_value('parts', content, 'Dictionary Value', parts),
            act_first_item(parts, 'Dictionary Value', part),
            act_value('text', part, 'Item from List', text),
            # D-101 (live iPhone 29.10): «has any value» straight on a Dictionary Value stops the run with «Choose values for
            # each parameter in this action»; a Text made from it is tested by its characters instead
            *if_dict_text(has_text, text),
            act_set_variable(V['third'], text, 'Dictionary Value'),
            act_text(text_token(T['provider.gemini_search'] + ' · ' + model), joined_t),
            act_set_variable(V['provider'], joined_t, 'Text'),
            # sources: up to N «• title» lines, read from the answer's own JSON text (the raw response). D-101 (live
            # iPhone 29.10): walking groundingChunks with «Get Dictionary Value» stopped Trio with «Choose values for
            # each parameter in this action» — a chunk without «web», or a condition straight on the list; Match / Replace
            # Text on the text never has an empty required input. Titles are the sites' names (the uris are Google
            # redirect links). No titles (Gemini chose not to search): the answer stays as it is.
            # only the «title» inside a source's «web» object, never words of the answer itself (Kimi, D-101)
            act_match(r'"web"\s*:\s*\{[^{}]*?"title"\s*:\s*"[^"]+"', raw, 'Text', chunks),
            # no titles (Gemini chose not to search): Matches has no value and nothing below may read it — «Get Items
            # from List» with an empty required input is the same «Choose values» stop (Kimi, D-101)
            if_output(s_has, chunks, 'Matches', 100),
            # all of them, one per line, then the first N lines — not «Get Items in Range 1…N», which stops the run
            # when there are fewer than N («you asked for items 1 to 5, the list has 2», Shortcuts for Mac 29.10)
            act_combine(chunks, 'Matches', c_get),
            act_replace(c_get, 'Combined Text', r'"web"\s*:\s*\{[^{}]*?"title"\s*:\s*"([^"]+)"', '• $1', s_new),
            act_first_match(s_new, 'Updated Text', r'\A[^\n]*(?:\n[^\n]*){0,%d}' % (GEMINI_SEARCH_MAX_SOURCES - 1), five),
            act_get_variable(V['third'], joined),
            *set_text(V['third'], '{R}\n\n' + T['search.sources'] + '\n{S}', u(),
                      {'R': (joined, 'Variable'), 'S': (five, 'Matches')}),
            if_close(s_has),
            if_close(has_text),
            if_close(ok),
            if_close(todo),
        ]
    actions.append(repeat_each_close(g_loop))
    return actions


def third_voice(T, V, prompt_uid, keys_uid, keys_name='Variable', providers=None, notify_silent=None, search=True,
                light=False):
    """From the finished trio prompt and the saved keys text to V['third'] holding the third voice.

    Every key the person saved is tried with every model of its provider until one answers; a key
    that answered «no money» or «invalid» is not asked again. Only when all failed does V['third']
    get an honest list of what each one said. Shared with the Mac probe, so what is tested on a Mac
    is exactly what ships.
    """
    u = new_uuid
    var = lambda name, default: V.get(name, default)
    attempts_v, log_v, dead_v, why_v = (var('attempts', 'Attempts'), var('log', 'Log'),
                                         var('dead', 'DeadKeys'), var('why', 'Why'))
    paused_v = var('paused', 'Paused')
    actions = []
    if search:
        # first, silently: Gemini with web search (sources); on any failure V['third'] stays empty
        actions += search_voice(T, V, prompt_uid, keys_uid, keys_name)

    # ---- the attempt list: one line «url|model|key|provider|max_tokens» per (model, key)
    parts = {}
    for n, (name_key, url, key_re, models, max_tokens) in enumerate(PROVIDERS if providers is None
                                                                     else providers):
        found, joined = u(), u()
        actions += [act_match(key_re, keys_uid, keys_name, found),
                    act_combine(found, 'Matches', joined)]
        for m, model in enumerate(models):
            line = u()
            actions.append(act_replace(joined, 'Combined Text', r'([^\n]+)',
                                       f'{url}|{model}|$1|{T[name_key]}|{max_tokens}', line))
            parts[f'P{n}_{m}'] = (line, 'Updated Text')
    all_lines, lines = u(), u()
    actions += [act_text(text_token('\n'.join('{%s}' % k for k in parts), parts), all_lines),
                act_match(r'[^\n]+', all_lines, 'Text', lines)]

    if light:
        # The light chain, for Duo's «Claude did not answer» menu (about a fifth of the actions): the caller passes
        # free providers with one model each; only the OpenAI-style dialect, no dead-key or pause bookkeeping, no
        # per-attempt log. The first answer wins; if none comes, V['third'] says there is no usable key.
        loop, skip_done, ok, has_text = u(), u(), u(), u()
        attempt, split, f_url, f_model, f_key, f_name, f_max = (u() for _ in range(7))
        post, raw, data, choices, first, message, content, c_tail, c_clean = (u() for _ in range(9))
        none = u()
        actions += [
            repeat_each(loop, lines, 'Matches'),
            act_set_from_repeat_item(attempts_v),
            if_no_value(skip_done, V['third']),
            act_get_variable(attempts_v, attempt),
            act_split(attempt, 'Variable', '|', split),
            act_item_at(split, 'Split Text', 1, f_url),
            act_item_at(split, 'Split Text', 2, f_model),
            act_item_at(split, 'Split Text', 3, f_key),
            act_item_at(split, 'Split Text', 4, f_name),
            act_item_at(split, 'Split Text', 5, f_max),
            act_post_json(f_url, f_key, f_model, prompt_uid, post, max_uid=f_max),
            act_set_variable(V['data'], post, 'Contents of URL'),
            act_text(text_token('{R}', {'R': (post, 'Contents of URL')}), raw),
            act_set_variable(V['raw'], raw, 'Text'),
            if_contains(ok, V['raw'], '"choices"'),
            act_get_variable(V['data'], data),
            act_value('choices', data, 'Variable', choices),
            act_first_item(choices, 'Dictionary Value', first),
            act_value('message', first, 'Item from List', message),
            act_value('content', message, 'Dictionary Value', content),
            # D-101 (live iPhone 29.10): «has any value» straight on a Dictionary Value stops the run with «Choose values for
            # each parameter in this action»; a Text made from it is tested by its characters instead
            *if_dict_text(has_text, content),
            act_replace(content, 'Dictionary Value', TOKEN_TAIL_RE, '', c_tail),
            act_replace(c_tail, 'Updated Text', TOKEN_RE, '', c_clean),
            act_set_variable(V['third'], c_clean, 'Updated Text'),
            act_set_variable(V['provider'], f_name, 'Item from List'),
            if_close(has_text),
            if_close(ok),
            if_close(skip_done),
            repeat_each_close(loop),
            if_no_value(none, V['third']),
            *set_text(V['third'], T['error.nokeys'], u()),
            *set_text(V['provider'], T['provider.none'], u()),
            if_close(none),
        ]
        return actions

    loop, skip_done, skip_dead, ok, has_text = u(), u(), u(), u(), u()
    attempt, split = u(), u()
    f_url, f_model, f_key, f_name, f_max = u(), u(), u(), u(), u()
    post, raw, raw_get, data, choices, first, message, content = (u() for _ in range(8))
    k_get, dead_get, tail_m, tail, label_n, label_m, label = (u() for _ in range(7))
    c_tail, c_clean = u(), u()
    g_ant, g_oai, post_a, raw_a, post_o, raw_o = (u() for _ in range(6))
    a_ok, a_has, a_data, a_content, a_first, a_text = (u() for _ in range(6))
    p_url, p_model, p_all, p_one, skip_all, skip_one = (u() for _ in range(6))
    actions += [
        repeat_each(loop, lines, 'Matches'),
        act_set_from_repeat_item(attempts_v),
        if_no_value(skip_done, V['third']),
        act_get_variable(attempts_v, attempt),
        act_split(attempt, 'Variable', '|', split),
        act_item_at(split, 'Split Text', 1, f_url), act_set_variable(V['url'], f_url, 'Item from List'),
        act_item_at(split, 'Split Text', 2, f_model), act_set_variable(V['model'], f_model, 'Item from List'),
        act_item_at(split, 'Split Text', 3, f_key), act_set_variable(V['key'], f_key, 'Item from List'),
        act_item_at(split, 'Split Text', 4, f_name), act_set_variable(V['provider'], f_name, 'Item from List'),
        act_item_at(split, 'Split Text', 5, f_max),
        act_get_variable(V['key'], k_get),
        # a key that already said «no money» / «invalid» is not asked again
        if_contains_ref(skip_dead, dead_v, k_get, 'Variable'),
        if_else(skip_dead),
        # a provider (or, at Google and Groq, a model) that answered 429 is not asked again this run
        act_get_variable(V['url'], p_url), act_get_variable(V['model'], p_model),
        act_text(text_token('{U}#all', {'U': (p_url, 'Variable')}), p_all),
        if_contains_ref(skip_all, paused_v, p_all, 'Text'),
        if_else(skip_all),
        act_text(text_token('{U}|{M}#', {'U': (p_url, 'Variable'), 'M': (p_model, 'Variable')}), p_one),
        if_contains_ref(skip_one, paused_v, p_one, 'Text'),
        if_else(skip_one),
        # three dialects: Anthropic's own, OpenAI's with max_completion_tokens, everyone else
        if_contains(g_ant, V['url'], 'api.anthropic.com'),
        act_post_anthropic(f_url, f_key, f_model, prompt_uid, f_max, post_a),
        act_set_variable(V['data'], post_a, 'Contents of URL'),
        act_text(text_token('{R}', {'R': (post_a, 'Contents of URL')}), raw_a),
        act_set_variable(V['raw'], raw_a, 'Text'),
        if_else(g_ant),
        if_contains(g_oai, V['url'], 'api.openai.com'),
        act_post_json(f_url, f_key, f_model, prompt_uid, post_o, max_uid=f_max,
                      max_field='max_completion_tokens'),
        act_set_variable(V['data'], post_o, 'Contents of URL'),
        act_text(text_token('{R}', {'R': (post_o, 'Contents of URL')}), raw_o),
        act_set_variable(V['raw'], raw_o, 'Text'),
        if_else(g_oai),
        act_post_json(f_url, f_key, f_model, prompt_uid, post, max_uid=f_max),
        act_set_variable(V['data'], post, 'Contents of URL'),
        act_text(text_token('{R}', {'R': (post, 'Contents of URL')}), raw),
        act_set_variable(V['raw'], raw, 'Text'),
        if_close(g_oai),
        if_close(g_ant),
        act_get_variable(V['provider'], label_n),
        act_get_variable(V['model'], label_m),
        act_text(text_token('{N} · {M}', {'N': (label_n, 'Variable'), 'M': (label_m, 'Variable')}), label),
        if_contains(ok, V['raw'], '"choices"'),
        act_get_variable(V['data'], data),
        act_value('choices', data, 'Variable', choices),
        act_first_item(choices, 'Dictionary Value', first),
        act_value('message', first, 'Item from List', message),
        act_value('content', message, 'Dictionary Value', content),
        # D-101 (live iPhone 29.10): «has any value» straight on a Dictionary Value stops the run with «Choose values for
        # each parameter in this action»; a Text made from it is tested by its characters instead
        *if_dict_text(has_text, content),
        act_replace(content, 'Dictionary Value', TOKEN_TAIL_RE, '', c_tail),
        act_replace(c_tail, 'Updated Text', TOKEN_RE, '', c_clean),
        act_set_variable(V['third'], c_clean, 'Updated Text'),
        act_set_variable(V['provider'], label, 'Text'),
        if_else(has_text),
        *set_text(why_v, T['why.empty'], u()),
        if_close(has_text),
        if_else(ok),
        # Anthropic's answer: {"content":[{"type":"text","text":…}], "stop_reason":…}; its errors
        # never carry stop_reason
        if_contains(a_ok, V['raw'], 'stop_reason'),
        act_get_variable(V['data'], a_data),
        act_value('content', a_data, 'Variable', a_content),
        act_first_item(a_content, 'Dictionary Value', a_first),
        act_value('text', a_first, 'Item from List', a_text),
        # D-101 (live iPhone 29.10): «has any value» straight on a Dictionary Value stops the run with «Choose values for
        # each parameter in this action»; a Text made from it is tested by its characters instead
        *if_dict_text(a_has, a_text),
        act_set_variable(V['third'], a_text, 'Dictionary Value'),
        act_set_variable(V['provider'], label, 'Text'),
        if_else(a_has),
        *set_text(why_v, T['why.empty'], u()),
        if_close(a_has),
        if_else(a_ok),
    ]

    groups = []
    for kind, dead, needles in FAILS:
        for needle in needles:
            group = u()
            groups.append(group)
            actions += [if_contains(group, V['raw'], needle), *set_text(why_v, T[f'why.{kind}'], u())]
            if kind == 'limit':
                actions += pause_actions(u, V, paused_v)
            if dead:
                d_old, d_new = u(), u()
                actions += [act_get_variable(dead_v, d_old),
                            act_text(text_token('{D}\n{K}', {'D': (d_old, 'Variable'),
                                                            'K': (k_get, 'Variable')}), d_new),
                            act_set_variable(dead_v, d_new, 'Text')]
            actions.append(if_else(group))
    actions += set_text(why_v, T['why.other'], u())
    actions += [if_close(group) for group in reversed(groups)]
    actions.append(if_close(a_ok))
    actions.append(if_close(ok))

    # one line of the honest list: «• Gemini · gemini-3.8-flash (key …x1Ab): overloaded»
    why_get, log_old, log_new = u(), u(), u()
    actions += [
        if_has_value(has_why := u(), why_v),
        act_match(r'.{4}$', k_get, 'Variable', tail_m),
        act_first_item(tail_m, 'Matches', tail),
        act_get_variable(why_v, why_get),
        act_get_variable(log_v, log_old),
        act_text(text_token('{L}\n• {P} (…{K}): {W}', {'L': (log_old, 'Variable'), 'P': (label, 'Text'),
                                                       'K': (tail, 'Item from List'),
                                                       'W': (why_get, 'Variable')}), log_new),
        act_set_variable(log_v, log_new, 'Text'),
        *set_text(why_v, '', u()),
        if_close(has_why),
        if_close(skip_one),
        if_close(skip_all),
        if_close(skip_dead),
        if_close(skip_done),
        repeat_each_close(loop),
    ]

    # ---- nobody answered: say what each one said and what to do
    none, any_log, log_get = u(), u(), u()
    actions += [
        if_no_value(none, V['third']),
        if_has_value(any_log, log_v),
        act_get_variable(log_v, log_get),
        *set_text(V['third'], T['error.all'], u(), {'L': (log_get, 'Variable')}),
        if_else(any_log),
        *set_text(V['third'], T['error.nokeys'], u()),
        if_close(any_log),
        # the block keeps the full reason; the banner only says, shortly, that the pair's answer is whole
        *([act_notify(notify_silent[0], notify_silent[1])] if notify_silent else []),
        *set_text(V['provider'], T['provider.none'], u()),
        if_close(none),
    ]
    return actions


# ---------------------------------------------------------------- build

def build(lang, nokey=False):
    trio_file = ROOT / 'locales' / lang / 'trio.json'
    if not trio_file.exists():
        print(f'{lang}: no trio.json — Trio not built for this language')
        return
    L = Locale(lang)
    T = json.loads(trio_file.read_text(encoding='utf-8'))
    if nokey and 'nokey.comment' not in T:
        print(f'{lang}: no nokey words in trio.json — Trio without a key not built for this language')
        return
    NAME = T['name']
    V = T['variables']

    ids = lambda n: [new_uuid() for _ in range(n)]
    k_get, k_file, k_ask, k_save, k_var, k_visible = ids(6)
    question, wrap, gpt, gpt2, claude, claude2, claude_own, claude_own2 = ids(8)
    gpt_f, own_f, own_f2, own_g, gpt_g = ids(5)
    n0, n_get, n_f, n_g = ids(4)
    nums_a, nums_b, item_a, item_b, nget_a, nget_b, nadd_a, nadd_b = ids(8)
    g_retry, g_oretry, g_cretry, g_cfail, g_n1, g_n2, g_rep, g_miss, g_rep2, g_miss2 = ids(10)
    c_prompt, c_cut, c_fail = ids(3)
    GPT_VAR, OWN_VAR, NUMS_VAR, CMP_VAR = 'TrioGpt', 'TrioClaudeOwn', 'TrioNums', 'TrioCompare'
    t_prompt, n_prompt, apple = ids(3)
    f_third, f_provider, f_out, f_body = ids(4)
    s_claude = new_uuid()
    g_key, g_apple, g_blank, g_first, g_nokey, g_noai = ids(6)
    g_own_clip, g_dup_a, g_dup_b, g_dup_c = ids(4)
    r_get, r_text, r_save = ids(3)
    Q = {'Q': (question, 'Provided Input')}

    if nokey:
        # Nothing is asked before the question here, so the first run warns once about the permission
        # windows, with Duo's words; the keyed Trio says the same at the top of its key prompt instead
        keys_first = [
            act_get_file(T['files.first_run'], r_get),
            act_set_variable(L['variables.pc_notice_seen'], r_get, 'File'),
            if_has_value(g_first, L['variables.pc_notice_seen']),
            if_else(g_first),
            act_alert(L['alert.first_run_title'], L['alert.first_run_body']),
            act_text(text_token(L['alert.first_run_body']), r_text),
            act_save_file(T['files.first_run'], r_text, r_save),
            if_close(g_first),
        ]
    else:
        keys_first = [
            # ---- the keys: from iCloud Drive → Shortcuts → poly-key.txt, or asked once and saved there.
            # Any number of free keys, one per line; each is recognised by how it begins.
            act_get_file(T['files.key'], k_get),
            act_set_variable(V['key_file'], k_get, 'File'),
            if_has_value(g_key, V['key_file']),
            *set_text(V['keys'], '{F}', k_file, {'F': (k_get, 'File')}),
            if_else(g_key),
            dict(act_ask(T['ask.key'], k_ask), WFWorkflowActionParameters={
                **act_ask(T['ask.key'], k_ask)['WFWorkflowActionParameters'], 'WFAllowsMultilineText': True}),
            # an empty field (Done with nothing typed) must not become an empty poly-key.txt: the key
            # would never be asked for again. (Cancel stops the shortcut by itself, before this line.)
            # …and neither must spaces or blank lines alone: a non-whitespace character has to be there
            act_match(r'\S', k_ask, 'Provided Input', k_visible),
            if_output(g_nokey, k_visible, 'Matches', 101),
            act_notify(NAME, T['notify.empty_key']),
            {'WFWorkflowActionIdentifier': 'is.workflow.actions.exit', 'WFWorkflowActionParameters': {}},
            if_close(g_nokey),
            act_save_file(T['files.key'], k_ask, k_save),
            act_set_variable(V['keys'], k_ask, 'Provided Input'),
            if_close(g_key),
            act_get_variable(V['keys'], k_var),
        ]

    trio_prompt = act_text(text_token(L.prompt('trio'),
                                      {'QUESTION': (question, 'Provided Input'),
                                       'GPT_ANSWER': (gpt_g, 'Variable'),
                                       'CLAUDE_ANSWER': (own_g, 'Variable')}), t_prompt)
    # both independent answers are read from variables (a retry may have filled them from a second call)
    both = [act_get_variable(GPT_VAR, gpt_g), act_get_variable(OWN_VAR, own_g)]
    if nokey:
        third = [
            # ---- the third voice: saved keys first (never asked for), else Apple Intelligence
            *both,
            act_get_file(T['files.key'], k_get),
            act_set_variable(V['key_file'], k_get, 'File'),
            if_has_value(g_key, V['key_file']),
            act_notify(NAME, T['notify.step3']),
            *set_text(V['keys'], '{F}', k_file, {'F': (k_get, 'File')}),
            act_get_variable(V['keys'], k_var),
            trio_prompt,
            # US models only: this one file is also USA mode's Trio (us_providers above)
            *third_voice(T, V, t_prompt, k_var, providers=us_providers(PROVIDERS)),
            if_else(g_key),
            *set_text(V['provider'], T['provider.none'], new_uuid()),
            if_close(g_key),
            # no key file, or none of the keys answered → «Use Model»
            if_contains(g_apple, V['provider'], T['provider.none']),
            act_notify(NAME, T['nokey.notify.step3']),
            act_text(text_token(L.prompt('trio-nokey'),
                                {'QUESTION': (question, 'Provided Input'),
                                 'GPT_ANSWER': (gpt_g, 'Variable'),
                                 'CLAUDE_ANSWER': (own_g, 'Variable')}), n_prompt),
            act_use_model(n_prompt, apple),
            act_set_variable(V['third'], apple, 'Response'),
            # «Use Model» gave nothing (an iPhone without Apple Intelligence): say so, in words a person understands
            if_output(g_noai, apple, 'Response', 101),
            act_notify(NAME, T.get('nokey.no_ai', T['provider.none'])),
            *set_text(V['third'], T.get('nokey.no_ai', T['provider.none']), new_uuid()),
            *set_text(V['provider'], T['provider.none'], new_uuid()),
            if_else(g_noai),
            *set_text(V['provider'], T['provider.apple'], new_uuid()),
            if_close(g_noai),
            if_close(g_apple),
        ]
    else:
        third = [
            # ---- the third voice
            act_notify(NAME, T['notify.step3']),
            *both,
            trio_prompt,
            *third_voice(T, V, t_prompt, k_var, notify_silent=(NAME, T['notify.third_silent'])),
        ]

    actions = [
        act_comment(T['nokey.comment'] if nokey else T['comment']),
        *keys_first,

        # ---- the pair: blind, as Critique in Duo
        act_ask(T['ask.question'], question, prefill_from_share=True),
        # an empty question would spend messages and a key's quota on nothing: say so and stop
        if_output(g_blank, question, 'Provided Input', 101),
        act_notify(NAME, T.get('notify.empty_question', L['notify.empty_question'])),
        {'WFWorkflowActionIdentifier': 'is.workflow.actions.exit', 'WFWorkflowActionParameters': {}},
        if_close(g_blank),
        act_notify(NAME, T['notify.start']),
        act_text(text_token(L.prompt('wrap'), Q), wrap),
        # D-100: emptied with «Nothing» and tested by their characters: an empty Text «has any value» in Shortcuts
        *clear_variable(GPT_VAR),
        *clear_variable(OWN_VAR),
        # ---- Step 1: ChatGPT answers the wrapped question. An empty answer (often a false «logged out» or a
        # dropped call): wait 3 s, ask once more, as in Duo.
        act_gpt(text_token('{P}', {'P': (wrap, 'Text')}), gpt),
        act_set_variable(GPT_VAR, gpt, 'Ask ChatGPT'),
        *if_text(g_retry, GPT_VAR, present=False),
        act_delay(3),
        act_gpt(text_token('{P}', {'P': (wrap, 'Text')}), gpt2),
        act_set_variable(GPT_VAR, gpt2, 'Ask ChatGPT'),
        if_close(g_retry),
        # ---- Step 2: Claude answers the SAME wrapped question without ChatGPT's answer (blind); one retry.
        act_notify(NAME, T['notify.step2']),
        act_claude(text_token('{P}', {'P': (wrap, 'Text')}), claude_own),
        act_set_variable(OWN_VAR, claude_own, 'Ask Claude'),
        *if_text(g_oretry, OWN_VAR, present=False),
        act_notify(NAME, L['notify.claude_retry']),
        act_claude(text_token('{P}', {'P': (wrap, 'Text')}), claude_own2),
        act_set_variable(OWN_VAR, claude_own2, 'Ask Claude'),
        if_close(g_oretry),
        # Claude's own answer reaches the clipboard before the network call: if the third voice fails
        # in any way, the person still holds an answer.
        # (an empty answer must not wipe what the person already has on the clipboard)
        *if_text(g_own_clip, OWN_VAR),
        act_get_variable(OWN_VAR, own_f),
        act_clipboard(attachment(own_f, 'Variable')),
        if_close(g_own_clip),

        # ---- Step 3: the third voice reads the question and both independent answers
        *third,

        # ---- Step 4: numbers that stand in only one of the two answers are found by rule, not by Claude's
        # attention, and handed over as data (as in Duo's Critique; only when both answers exist).
        act_get_variable(GPT_VAR, gpt_f),
        act_get_variable(OWN_VAR, own_f2),
        *clear_variable(NUMS_VAR),
        *if_text(g_n1, OWN_VAR),
        *if_text(g_n2, GPT_VAR),
        act_first_match(gpt_f, 'Variable', r'\d+(?:[.,:/-]\d+)*', nums_a),
        repeat_open(g_rep, nums_a, 'Matches'),
        act_get_variable('Repeat Item', item_a),
        # D-101 (live iPhone 29.10): «If <variable> does not contain <the Repeat Item>» stopped Trio with «Choose values
        # for each parameter in this action»; as in Duo's Critique: the number, its dots escaped, is matched as a WHOLE
        # number (Match Text), and the If tests that Match's «Matches»
        *if_number_missing(g_miss, OWN_VAR, item_a),
        *if_number_missing(g_dup_a, NUMS_VAR, item_a),
        act_get_variable(NUMS_VAR, nget_a),
        act_text(text_token('{N} {I}', {'N': (nget_a, 'Variable'), 'I': (item_a, 'Variable')}), nadd_a),
        act_set_variable(NUMS_VAR, nadd_a, 'Text'),
        if_close(g_dup_a),
        if_close(g_miss),
        repeat_close(g_rep),
        act_first_match(own_f2, 'Variable', r'\d+(?:[.,:/-]\d+)*', nums_b),
        repeat_open(g_rep2, nums_b, 'Matches'),
        act_get_variable('Repeat Item', item_b),
        # D-101 (live iPhone 29.10): «If <variable> does not contain <the Repeat Item>» stopped Trio with «Choose values
        # for each parameter in this action»; as in Duo's Critique: the number, its dots escaped, is matched as a WHOLE
        # number (Match Text), and the If tests that Match's «Matches»
        *if_number_missing(g_miss2, GPT_VAR, item_b),
        *if_number_missing(g_dup_b, NUMS_VAR, item_b),
        act_get_variable(NUMS_VAR, nget_b),
        act_text(text_token('{N} {I}', {'N': (nget_b, 'Variable'), 'I': (item_b, 'Variable')}), nadd_b),
        act_set_variable(NUMS_VAR, nadd_b, 'Text'),
        if_close(g_dup_b),
        if_close(g_miss2),
        repeat_close(g_rep2),
        if_close(g_n2),
        if_close(g_n1),
        act_get_variable(NUMS_VAR, n_g),

        act_get_variable(V['third'], f_third),
        act_get_variable(V['provider'], f_provider),
        # Claude's own answer + the third voice reach the clipboard BEFORE the comparing call: if Claude hits
        # its limit there, the person still holds the third voice (output.draft = the document without the
        # comparison).
        act_text(text_token(T['output.draft'], {'C': (own_f2, 'Variable'),
                                                'P': (f_provider, 'Variable'),
                                                'T': (f_third, 'Variable')}), f_body),
        act_clipboard(attachment(f_body, 'Text')),
        act_notify(NAME, T['notify.summary']),
        act_text(text_token(L.prompt('trio-compare'),
                            {'QUESTION': (question, 'Provided Input'),
                             'GPT_ANSWER': (gpt_f, 'Variable'),
                             'CLAUDE_OWN': (own_f2, 'Variable'),
                             'NUMS': (n_g, 'Variable'),
                             'PROVIDER': (f_provider, 'Variable'),
                             'THIRD': (f_third, 'Variable')}), c_prompt),
        act_claude(text_token('{P}', {'P': (c_prompt, 'Text')}), claude),
        act_set_variable(CMP_VAR, claude, 'Ask Claude'),
        # empty comparison: one retry with the request cut to the first LONG_TEXT characters (as in Duo)
        *if_text(g_cretry, CMP_VAR, present=False),
        act_notify(NAME, T.get('notify.compare_retry', L['notify.claude_retry'])),
        act_first_chars(c_prompt, 'Text', LONG_TEXT, c_cut),
        act_claude(text_token('{P}', {'P': (c_cut, 'Matches')}), claude2),
        act_set_variable(CMP_VAR, claude2, 'Ask Claude'),
        if_close(g_cretry),
        # still empty: Claude's own independent answer takes the place of the comparison, with a line saying so
        *if_text(g_cfail, CMP_VAR, present=False),
        *set_text(CMP_VAR, T['error.compare'], c_fail, {'C': (own_f2, 'Variable')}),
        if_close(g_cfail),
        act_get_variable(CMP_VAR, s_claude),

        # ---- one document: the three blocks and the final answer, then the third voice as its own block
        act_text(text_token(T['output'], {'S': (s_claude, 'Variable'),
                                          'P': (f_provider, 'Variable'),
                                          'T': (f_third, 'Variable')}), f_out),
        act_clipboard(attachment(f_out, 'Text')),
        act_notify(NAME, T['notify.done']),
        act_quick_look(attachment(f_out, 'Text')),

        # ---- Last of all, at most once a week: is there a newer Trio? (build_shortcut.version_check)
        *version_check(L, 'trio_nokey' if nokey else 'trio', NAME, lang),
    ]

    validate(actions)
    workflow = plistlib.loads((ROOT / 'src' / 'metadata.plist').read_bytes())
    workflow['WFWorkflowIcon'] = {'WFWorkflowIconStartColor': 3679049983,   # purple (kin to Duo's violet)
                                  'WFWorkflowIconGlyphNumber': 59800}      # people (a group)
    workflow['WFWorkflowTypes'] = ['ActionExtension']
    workflow['WFWorkflowInputContentItemClasses'] = ['WFStringContentItem', 'WFURLContentItem',
                                                     'WFRichTextContentItem', 'WFArticleContentItem']
    workflow['WFWorkflowHasShortcutInputVariables'] = True
    workflow['WFQuickActionSurfaces'] = ['ShareSheet']
    workflow['WFWorkflowActions'] = actions

    out_dir = Path(os.environ.get('C1_DIST', ROOT / 'dist')) / lang
    if nokey:
        out_dir = out_dir / 'nokey'
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'{NAME}.shortcut'
    with out.open('wb') as f:
        plistlib.dump(workflow, f, fmt=plistlib.FMT_BINARY)
    print(f'{lang}: {"nokey/" if nokey else ""}{out.name} — {len(actions)} actions')


if __name__ == '__main__':
    languages = sys.argv[1:] or [d.name for d in sorted((ROOT / 'locales').iterdir()) if d.is_dir()]
    for language in languages:
        build(language)
        build(language, nokey=True)
