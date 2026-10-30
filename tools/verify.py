#!/usr/bin/env python3
"""Verify a built C1 release.

    python3 tools/verify.py [lang ...]

Checks, per locale:
  * every locale carries the same keys and prompt files as the base locale (en);
  * every shipped shortcut is signed (AEA1) and unpacks;
  * the shipped file matches what the sources build right now;
  * structure: unique action ids, balanced control flow, menu items ↔ cases,
    no forward references, no risky in-string tokens;
  * the kit archive is in sync with its sources and stores names as UTF-8.

Unpacking signed shortcuts needs the `aea` and `aa` tools that ship with macOS;
without them the structural checks are skipped and everything else still runs.
"""
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE_LANG = 'en'
OBJ = '￼'

failures = []


def ok(msg):
    print(f'  [ok] {msg}')


def fail(msg):
    print(f'  [FAIL] {msg}')
    failures.append(msg)


# ---------------------------------------------------------------- locales

def check_locales():
    print('locales')
    base_ui = json.loads((ROOT / 'locales' / BASE_LANG / 'ui.json').read_text(encoding='utf-8'))
    base_keys = set(flatten(base_ui))
    base_prompts = {p.name for p in (ROOT / 'locales' / BASE_LANG / 'prompts').glob('*.txt')}

    for locale in sorted((ROOT / 'locales').iterdir()):
        if not locale.is_dir():
            continue
        ui = json.loads((locale / 'ui.json').read_text(encoding='utf-8'))
        missing = base_keys - set(flatten(ui))
        # prompt overrides are optional; anything absent falls back to the base language
        overrides = {p.name for p in (locale / 'prompts').glob('*.txt')}
        unknown = overrides - base_prompts
        if missing:
            fail(f'{locale.name}: missing ui keys: {sorted(missing)[:5]}')
        elif unknown:
            fail(f'{locale.name}: prompt overrides with no base counterpart: {sorted(unknown)}')
        else:
            note = f', {len(overrides)} prompt overrides' if overrides else ', shared prompts'
            ok(f'{locale.name}: {len(base_keys)} ui keys{note}')

        for name, items in (('main_items', 7), ('extra_items', 10), ('finale_items', 3),
                            ('finale_more_items', 7), ('recipes_items', 5), ('recipes_texts', 5)):
            if len(ui['menu'][name]) != items:
                fail(f'{locale.name}: menu.{name} must hold exactly {items} entries')


def flatten(node, prefix=''):
    if isinstance(node, dict):
        for key, value in node.items():
            if key.startswith('_'):
                continue
            yield from flatten(value, f'{prefix}.{key}' if prefix else key)
    elif isinstance(node, list):
        yield prefix
    else:
        yield prefix


# ---------------------------------------------------------------- shortcuts

P256 = bytes.fromhex('06082a8648ce3d030107')
BITSTRING = bytes.fromhex('03420004')


def unpack(path, workdir):
    """Read a signed .shortcut without any key: the public key travels in the file."""
    data = path.read_bytes()
    if data[:4] != b'AEA1':
        raise ValueError('not signed')
    prologue = int.from_bytes(data[8:12], 'little')
    chain = plistlib.loads(data[12:12 + prologue])['SigningCertificateChain'][0]
    der = bytes(chain)
    start = der.index(BITSTRING, der.index(P256))
    public = der[start + 3:start + 3 + 65]
    archive, extracted = workdir / 'a.aar', workdir / 'x'
    subprocess.run(['aea', 'decrypt', '-i', str(path), '-o', str(archive),
                    '-sign-pub-value', 'hex:' + public.hex()], check=True, capture_output=True)
    extracted.mkdir(exist_ok=True)
    subprocess.run(['aa', 'extract', '-i', str(archive), '-d', str(extracted)],
                   check=True, capture_output=True)
    return plistlib.loads((extracted / 'Shortcut.wflow').read_bytes())


def structure_report(actions):
    """Return a list of problems found in an action list."""
    problems, seen, produced, stack, menus = [], {}, set(), [], {}
    for index, action in enumerate(actions):
        params = action['WFWorkflowActionParameters']
        uid = params.get('UUID')
        if uid:
            if uid in seen:
                problems.append(f'duplicate action id at {seen[uid]} and {index}')
            seen[uid] = index
        mode = params.get('WFControlFlowMode')
        group = params.get('GroupingIdentifier')
        if mode == 0:
            stack.append(group)
            if 'WFMenuItems' in params:
                menus[group] = list(params['WFMenuItems'])
        elif mode == 1:
            if not stack or stack[-1] != group:
                problems.append(f'case outside its group at {index}')
            title = params.get('WFMenuItemTitle')
            if title is not None and group in menus:
                if title in menus[group]:
                    menus[group].remove(title)
                else:
                    problems.append(f'menu case without an item: {title}')
        elif mode == 2:
            if not stack or stack.pop() != group:
                problems.append(f'group closed out of order at {index}')
        for ref in references(params):
            if ref not in produced and ref != uid:
                problems.append(f'action {index} references a later action')
        if uid:
            produced.add(uid)
    if stack:
        problems.append('unbalanced control flow')
    for leftovers in menus.values():
        if leftovers:
            problems.append(f'menu items without a case: {leftovers}')
    for token in tokens(actions):
        utf16 = token['string'].encode('utf-16-le')
        for position, attachment in token.get('attachmentsByRange', {}).items():
            offset = int(position.strip('{}').split(',')[0])
            if utf16[offset * 2:offset * 2 + 2].decode('utf-16-le', 'replace') != OBJ:
                problems.append('text token offset does not point at a placeholder')
            if attachment.get('Type') not in ('ActionOutput', 'ExtensionInput'):
                problems.append(f"in-string token of type {attachment.get('Type')} "
                                'does not render on device')
    return problems


def references(node, found=None):
    found = set() if found is None else found
    if isinstance(node, dict):
        if node.get('Type') == 'ActionOutput':
            found.add(node['OutputUUID'])
        for value in node.values():
            references(value, found)
    elif isinstance(node, list):
        for value in node:
            references(value, found)
    return found


def tokens(node, found=None):
    found = [] if found is None else found
    if isinstance(node, dict):
        if node.get('WFSerializationType') == 'WFTextTokenString':
            found.append(node['Value'])
        for value in node.values():
            tokens(value, found)
    elif isinstance(node, list):
        for value in node:
            tokens(value, found)
    return found


def signature(actions):
    """Full action list with freshly generated ids made canonical.

    Every UUID / OutputUUID / GroupingIdentifier is replaced by an ordinal label in order of first
    appearance, so two builds of the same sources compare equal while any change in a URL, model,
    body, header, text or reference differs. Signing (AEA) wraps the plist without rewriting it,
    so nothing else is excluded."""
    labels = {}

    def label(value):
        return labels.setdefault(value, f'#{len(labels)}')

    def walk(node):
        if isinstance(node, dict):
            return {k: (label(v) if k in ID_KEYS and isinstance(v, str) else walk(v))
                    for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(actions)


ID_KEYS = {'UUID', 'OutputUUID', 'GroupingIdentifier'}


def check_sources_build(langs):
    """Build every locale into a scratch folder and audit the result.

    This is what runs on CI, where dist/ does not exist: it proves that each
    locale still produces a structurally valid shortcut from the sources.
    """
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, C1_DIST=tmp)
        for lang in langs:
            print(f'sources [{lang}]')
            for builder in ('build_shortcut.py', 'build_companions.py', 'build_trio.py'):
                result = subprocess.run([sys.executable, str(ROOT / 'src' / builder), lang],
                                        capture_output=True, cwd=ROOT, env=env, text=True)
                if result.returncode != 0:
                    fail(f'{lang}: {builder} failed: {result.stderr.strip().splitlines()[-1:]}')
                    break
            else:
                built = sorted((Path(tmp) / lang).rglob('*.shortcut'))
                problems = []
                for path in built:
                    actions = plistlib.loads(path.read_bytes())['WFWorkflowActions']
                    problems += [f'{path.relative_to(Path(tmp) / lang)}: {p}' for p in structure_report(actions)]
                if problems:
                    for problem in problems[:3]:
                        fail(f'{lang}: {problem}')
                else:
                    ok(f'{lang}: {len(built)} shortcuts build clean from sources')


def check_shortcuts(langs):
    have_tools = shutil.which('aea') and shutil.which('aa')
    for lang in langs:
        dist = ROOT / 'dist' / lang
        files = sorted(dist.rglob('*.shortcut'))
        if not files:
            continue
        print(f'shortcuts [{lang}]')
        for path in files:
            if path.read_bytes()[:4] != b'AEA1':
                fail(f'{lang}: {path.relative_to(dist)} is not signed')
        if not have_tools:
            ok(f'{lang}: {len(files)} shortcuts signed (structure check skipped: aea/aa missing)')
            continue

        with tempfile.TemporaryDirectory() as tmp:
            # rebuild from sources into a scratch folder and compare with what ships
            env = dict(os.environ, C1_DIST=tmp)
            subprocess.run([sys.executable, str(ROOT / 'src' / 'build_shortcut.py'), lang],
                           check=True, capture_output=True, cwd=ROOT, env=env)
            subprocess.run([sys.executable, str(ROOT / 'src' / 'build_companions.py'), lang],
                           check=True, capture_output=True, cwd=ROOT, env=env)
            subprocess.run([sys.executable, str(ROOT / 'src' / 'build_trio.py'), lang],
                           check=True, capture_output=True, cwd=ROOT, env=env)

            for path in files:
                rel = path.relative_to(dist)
                work = Path(tmp) / 'unpack' / rel.with_suffix('')
                work.mkdir(parents=True, exist_ok=True)
                try:
                    shipped = unpack(path, work)['WFWorkflowActions']
                except Exception as error:  # noqa: BLE001
                    fail(f'{lang}: cannot read {rel}: {error}')
                    continue
                problems = structure_report(shipped)
                fresh_path = Path(tmp) / lang / rel
                if fresh_path.exists():
                    fresh = plistlib.loads(fresh_path.read_bytes())['WFWorkflowActions']
                    if signature(fresh) != signature(shipped):
                        problems.append('shipped file does not match what the sources build')
                else:
                    problems.append('sources do not produce this file')
                if problems:
                    for problem in problems[:3]:
                        fail(f'{lang}/{rel}: {problem}')
                else:
                    ok(f'{lang}: {rel} — {len(shipped)} actions, matches sources')


# ---------------------------------------------------------------- kits

def check_kits(langs):
    for lang in langs:
        archive = ROOT / 'dist' / lang / 'poly-kit.zip'
        if not archive.exists():
            continue
        print(f'kit [{lang}]')
        with zipfile.ZipFile(archive) as z:
            names = z.namelist()
            for info in z.infolist():
                if not unicodedata.is_normalized('NFC', info.filename):
                    fail(f'{lang}: {info.filename} is not NFC-normalized')
                if any(ord(ch) > 127 for ch in info.filename) and not info.flag_bits & 0x800:
                    fail(f'{lang}: {info.filename} lacks the UTF-8 flag')
            stale = []
            for name in names:
                if name == 'poly.jpg':
                    candidates = [ROOT / 'assets' / 'poly.jpg']
                else:
                    candidates = [ROOT / 'dist' / lang / name, ROOT / 'docs' / lang / name]
                for source in candidates:
                    if source.exists():
                        if z.read(name) != source.read_bytes():
                            stale.append(name)
                        break
            if stale:
                fail(f'{lang}: kit is out of date: {stale}')
            else:
                ok(f'{lang}: {len(names)} entries, in sync')


def check_language():
    print('language')
    sys.path.insert(0, str(ROOT / 'tools'))
    import check_language as language_mod
    found = language_mod.violations(ROOT, language_mod.git_files(ROOT))
    if found:
        for line in found:
            fail(f'language: {line}')
    else:
        ok('no Cyrillic outside a language place')


def check_android():
    """Tasker projects: every language that has locales/<lang>/tasker.json carries the same
    five projects as English, and the four hand-shaped ones match what the generator makes."""
    print('android')
    import xml.etree.ElementTree as ET
    sys.path.insert(0, str(ROOT / 'android'))
    import generate_tasker
    base = sorted(p.name for p in (ROOT / 'android' / 'en').glob('*.prj.xml'))
    for lang in generate_tasker.tasker_langs():
        have = sorted(p.name for p in (ROOT / 'android' / lang).glob('*.prj.xml'))
        if have != base:
            fail(f'android/{lang}: projects {have} differ from en {base}')
            continue
        for name in have:
            try:
                ET.parse(ROOT / 'android' / lang / name)
            except ET.ParseError as exc:
                fail(f'android/{lang}/{name}: invalid XML: {exc}')
        stale = generate_tasker.generate(lang, check=True)
        if stale:
            fail(f'android/{lang}: out of date with locales/{lang}/tasker.json: {stale}')
        else:
            ok(f'android/{lang}: {len(have)} projects, in sync with locales/{lang}/tasker.json')


def check_release_sums():
    """releases/SHA256SUMS, if present, lists exactly the released files and every hash matches."""
    import hashlib
    releases = ROOT / 'releases'
    sums = releases / 'SHA256SUMS'
    if not sums.exists():
        if releases.exists() and any(releases.iterdir()):
            fail('releases/SHA256SUMS is missing although releases/ is not empty '
                 '(regenerate on purpose: python3 tools/verify.py --write-release-sums)')
        return
    listed = {}
    for line in sums.read_text(encoding='utf-8').splitlines():
        if line.strip():
            digest, _, name = line.partition('  ')
            listed[name] = digest
    actual = {p.relative_to(releases).as_posix() for p in releases.rglob('*.shortcut')} | {'version.json'}
    actual = {n for n in actual if (releases / n).exists()}
    problems = [f'{n}: not in SHA256SUMS' for n in sorted(actual - set(listed))]
    problems += [f'{n}: listed but missing' for n in sorted(set(listed) - actual)]
    problems += [f'{n}: hash differs from SHA256SUMS' for n in sorted(actual & set(listed))
                 if hashlib.sha256((releases / n).read_bytes()).hexdigest() != listed[n]]
    if problems:
        for problem in problems:
            fail(f'releases/{problem}')
    else:
        ok(f'releases/SHA256SUMS: {len(listed)} files match')


def write_release_sums():
    """Explicit release step: record the hashes of the files now in releases/ (never run by build.sh)."""
    import hashlib
    releases = ROOT / 'releases'
    names = sorted(['version.json'] + [p.relative_to(releases).as_posix() for p in releases.rglob('*.shortcut')])
    lines = [f"{hashlib.sha256((releases / n).read_bytes()).hexdigest()}  {n}\n" for n in names]
    (releases / 'SHA256SUMS').write_text(''.join(lines), encoding='utf-8')
    print(f'releases/SHA256SUMS written: {len(names)} files')


def main():
    if '--write-release-sums' in sys.argv[1:]:
        write_release_sums()
        return 0
    langs = sys.argv[1:] or [d.name for d in sorted((ROOT / 'locales').iterdir()) if d.is_dir()]
    check_locales()
    check_language()
    check_android()
    check_release_sums()
    check_sources_build(langs)
    check_shortcuts(langs)
    check_kits(langs)
    if not any((ROOT / 'dist' / l).exists() for l in langs):
        print('\n(no dist/ here — release artifacts live in GitHub Releases, '
              'so only the source build was checked)')
    print()
    if failures:
        print(f'FAILED — {len(failures)} problem(s)')
        return 1
    print('OK — release is consistent')
    return 0


if __name__ == '__main__':
    sys.exit(main())
