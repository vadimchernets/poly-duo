"""tools/check_models.py finds a wrong model id from a /models answer — no network."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('check_models', ROOT / 'tools' / 'check_models.py')
check_models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_models)

OPENROUTER_REPLY = {'data': [{'id': 'qwen/qwen3.8-27b:free'}, {'id': 'google/gemma-4-31b-it:free'},
                             {'id': 'brand/new-model:free'}, {'id': 'brand/paid-model'}]}


def test_wrong_id_is_dead_and_new_free_is_reported():
    cfg = {'models': ['qwen/qwen3.8-27b:free', 'wrong/id-that-never-existed:free', 'openrouter/free']}
    dead, new = check_models.compare('openrouter', cfg, check_models.listed_ids(OPENROUTER_REPLY))
    assert dead == ['wrong/id-that-never-existed:free']          # openrouter/free is the router, never dead
    assert new == ['brand/new-model:free', 'google/gemma-4-31b-it:free']


def test_google_prefix_is_stripped():
    listed = check_models.listed_ids({'data': [{'id': 'models/gemini-3.8-flash'}]})
    assert listed == {'gemini-3.8-flash'}
    assert check_models.compare('gemini', {'models': ['gemini-3.8-flash']}, listed) == ([], [])


def test_us_models_are_checked_too():
    cfg = {'models': ['a'], 'us_models': ['b']}
    dead, _ = check_models.compare('nvidia', cfg, {'a'})
    assert dead == ['b']


def test_models_json_is_complete():
    providers = json.loads((ROOT / 'src' / 'models.json').read_text(encoding='utf-8'))['providers']
    for name in check_models.FREE_ONLY:
        assert providers[name]['models_url'] and providers[name]['key_env'] and providers[name]['models']


def test_gemini_search_native_list():
    reply = {'models': [{'name': 'models/gemini-2.5-flash'}, {'name': 'models/other'}]}
    listed = check_models.listed_native_ids(reply)
    assert listed == {'gemini-2.5-flash', 'other'}
    cfg = {'models': ['gemini-2.5-flash', 'gemini-2.5-flash-lite']}
    assert check_models.check_search(cfg, listed) == ['gemini-2.5-flash-lite']
