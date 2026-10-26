#!/usr/bin/env python3
"""Check src/models.json against what each free provider lists today.

    NVIDIA_API_KEY=... GEMINI_API_KEY=... GROQ_API_KEY=... OPENROUTER_API_KEY=... python3 tools/check_models.py

Run by hand about once a week. Keys come from the environment only; a provider with no key is skipped
(OpenRouter's list is public, so it is read without one). Reports

  * DEAD  — an id in models.json (also gemini_search.models, via Google's native list) that the provider no longer lists;
  * NEW   — ids that look like new free models (OpenRouter `:free`; Google `*flash*`; every id on Groq,
            whose list is short) that models.json does not use yet.

Exit code 1 if anything is dead, 0 otherwise (skipped providers do not fail the run).
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / 'src' / 'models.json'
# not real list entries: OpenRouter's own router
ALWAYS_OK = {'openrouter/free'}
FREE_ONLY = ('nvidia', 'gemini', 'openrouter', 'groq')


def configured_ids(cfg):
    return list(dict.fromkeys(cfg.get('models', []) + cfg.get('us_models', [])))


def normalise(model_id):
    """Google's OpenAI-compatible list answers `models/gemini-3.8-flash`."""
    return model_id[len('models/'):] if model_id.startswith('models/') else model_id


def listed_ids(payload):
    return {normalise(m['id']) for m in payload.get('data', []) if 'id' in m}


def listed_native_ids(payload):
    """Google's native list answers {'models': [{'name': 'models/gemini-2.5-flash'}, ...]}."""
    return {normalise(m['name']) for m in payload.get('models', []) if 'name' in m}


def looks_new_free(name, model_id):
    if name == 'openrouter':
        return model_id.endswith(':free')
    if name == 'gemini':
        return 'flash' in model_id
    if name == 'groq':
        return True
    return False   # NVIDIA lists hundreds of ids and marks none as free: only dead ids are reported


def compare(name, cfg, listed):
    """-> (dead ids, new free ids) for one provider; `listed` is the set of ids the provider returns."""
    used = configured_ids(cfg)
    dead = [m for m in used if m not in listed and m not in ALWAYS_OK]
    new = sorted(m for m in listed if m not in used and looks_new_free(name, m))
    return dead, new


def fetch(url, key, native_google=False):
    if native_google:
        headers = {'x-goog-api-key': key}
    else:
        headers = {'Authorization': f'Bearer {key}'} if key else {}
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode('utf-8'))


def check_search(cfg, listed):
    """models.json -> gemini_search.models against Google's native list -> dead ids."""
    return [m for m in cfg.get('models', []) if m not in listed]


def main():
    models_json = json.loads(MODELS.read_text(encoding='utf-8'))
    providers = models_json['providers']
    dead_total = 0
    for name in FREE_ONLY:
        cfg = providers[name]
        key = os.environ.get(cfg['key_env'])
        if not key and name != 'openrouter':
            print(f'{name}: skipped (no {cfg["key_env"]})')
            continue
        try:
            listed = listed_ids(fetch(cfg['models_url'], key))
        except Exception as error:   # network, 401, bad JSON: say so, do not guess
            print(f'{name}: cannot read {cfg["models_url"]}: {error}')
            continue
        dead, new = compare(name, cfg, listed)
        dead_total += len(dead)
        print(f'{name}: {len(listed)} listed, {len(configured_ids(cfg))} used')
        for m in dead:
            print(f'  DEAD  {m}')
        for m in new:
            print(f'  NEW   {m}')
    search = models_json.get('gemini_search')
    key = os.environ.get(providers['gemini']['key_env'])
    if search and not key:
        print(f'gemini_search: skipped (no {providers["gemini"]["key_env"]})')
    elif search:
        try:
            listed = listed_native_ids(fetch(search['base_url'] + '?pageSize=1000', key, native_google=True))
            dead = check_search(search, listed)
            dead_total += len(dead)
            print(f'gemini_search: {len(listed)} listed, {len(search["models"])} used')
            for m in dead:
                print(f'  DEAD  {m}')
        except Exception as error:
            print(f'gemini_search: cannot read {search["base_url"]}: {error}')
    return 1 if dead_total else 0


if __name__ == '__main__':
    sys.exit(main())
