// Duo keys and the manual-mode draft — on this phone only. The key never goes anywhere except to
// the provider itself.
//
// Keys live in the phone's secure store (iOS Keychain / Android Keystore via the ExpoSecureStore
// native module), one item per provider: `poly-a1-duo-key.<provider>`. One item per provider keeps
// each value well under the store's ~2 KB per-item size, and the item names stay in [A-Za-z0-9._-].
// iOS items are WHEN_UNLOCKED_THIS_DEVICE_ONLY: never in an iCloud backup, never on another phone.
//
// The module is looked up at run time (`requireOptionalNativeModule`), so the same JS works in a
// build with the native module and in one without it (web, Expo Go, an older build): there the
// keys stay in AsyncStorage under their own key, separate from the shared state object, and are
// wiped along with "Delete my data". As soon as a build with the secure store opens, `loadKeys`
// moves the old keys over: copy each one, read it back, and only then delete the AsyncStorage
// copy. Running it twice changes nothing.
import AsyncStorage from '@react-native-async-storage/async-storage';
import { requireOptionalNativeModule } from 'expo';

import { keyList, PROVIDERS, type Keys, type Provider } from './duoAuto';

/** The old (and fallback) place: one JSON object with every provider's keys. */
export const KEYS_KEY = 'poly-a1-duo-keys';
export const DRAFT_KEY = 'poly-a1-duo-draft';
/** Secure-store item name prefix; the provider id is appended. */
export const SECURE_PREFIX = 'poly-a1-duo-key.';

/** The duel's signing key: its own item, removed by "Delete my data" with the Duo keys. */
export const DUEL_KEY_ITEM = 'poly-a1-duel-signing-key';

export const secureItem = (p: Provider) => `${SECURE_PREFIX}${p}`;

/** The three calls this file needs from a secure store. */
export type SecureBackend = {
  get(name: string): Promise<string | null>;
  set(name: string, value: string): Promise<void>;
  remove(name: string): Promise<void>;
};

type NativeSecureStore = {
  getValueWithKeyAsync(key: string, options: object): Promise<string | null>;
  setValueWithKeyAsync(value: string, key: string, options: object): Promise<void>;
  deleteValueWithKeyAsync(key: string, options: object): Promise<void>;
  WHEN_UNLOCKED_THIS_DEVICE_ONLY?: number;
};

function nativeBackend(): SecureBackend | null {
  let mod: NativeSecureStore | null = null;
  try {
    mod = requireOptionalNativeModule<NativeSecureStore>('ExpoSecureStore');
  } catch {
    mod = null;
  }
  if (!mod || typeof mod.setValueWithKeyAsync !== 'function') return null;
  const options: Record<string, unknown> = {};
  if (typeof mod.WHEN_UNLOCKED_THIS_DEVICE_ONLY === 'number')
    options.keychainAccessible = mod.WHEN_UNLOCKED_THIS_DEVICE_ONLY;
  const m = mod;
  return {
    get: (name) => m.getValueWithKeyAsync(name, options),
    set: (name, value) => m.setValueWithKeyAsync(value, name, options),
    remove: (name) => m.deleteValueWithKeyAsync(name, options),
  };
}

let backend: SecureBackend | null | undefined;

function secure(): SecureBackend | null {
  if (backend === undefined) backend = nativeBackend();
  return backend;
}

/** The secure store for other modules (the duel's signing key lives beside the Duo keys); null when this build has none. */
export const secureBackend = (): SecureBackend | null => secure();

/** Tests swap in an in-memory store (or `null` for "no secure store in this build"). */
export function setSecureBackend(b: SecureBackend | null | undefined): void {
  backend = b;
}

function clean(got: Keys): Keys {
  const out: Keys = {};
  for (const p of PROVIDERS) if (typeof got[p] === 'string' && got[p]) out[p] = got[p];
  return out;
}

async function loadLegacy(): Promise<Keys> {
  try {
    const raw = await AsyncStorage.getItem(KEYS_KEY);
    return raw ? clean(JSON.parse(raw) as Keys) : {};
  } catch {
    return {};
  }
}

export async function loadKeys(): Promise<Keys> {
  const sec = secure();
  if (!sec) return loadLegacy();
  const out: Keys = {};
  for (const p of PROVIDERS) {
    try {
      const v = await sec.get(secureItem(p));
      if (v) out[p] = v;
    } catch {
      // unreadable item — treated as absent
    }
  }
  // Migration from AsyncStorage: the secure copy wins; the old copy goes only after every key
  // was written and read back.
  const legacy = await loadLegacy();
  const pending = PROVIDERS.filter((p) => legacy[p]);
  if (pending.length) {
    let allMoved = true;
    for (const p of pending) {
      if (out[p]) continue;
      try {
        await sec.set(secureItem(p), legacy[p] as string);
        if ((await sec.get(secureItem(p))) === legacy[p]) out[p] = legacy[p];
        else allMoved = false;
      } catch {
        allMoved = false;
      }
      if (!out[p]) out[p] = legacy[p];
    }
    if (allMoved) {
      try {
        await AsyncStorage.removeItem(KEYS_KEY);
      } catch {
        // stays for the next run; migration is idempotent
      }
    }
  }
  return out;
}

/** Whoever is currently showing keys. Change a key on one screen and the other screens in the
 *  stack (the automation screen stays mounted under the keys screen) find out right away,
 *  without re-reading on focus. */
const listeners = new Set<(k: Keys) => void>();

export function onKeys(fn: (k: Keys) => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

async function store(keys: Keys): Promise<Keys> {
  const sec = secure();
  let secured = false;
  if (sec) {
    secured = true;
    for (const p of PROVIDERS) {
      try {
        const v = keys[p];
        if (v) await sec.set(secureItem(p), v);
        else await sec.remove(secureItem(p));
      } catch {
        secured = false;
      }
    }
  }
  try {
    // Secure store took everything: no copy is left in AsyncStorage (a removed key must not come
    // back through the migration). Otherwise AsyncStorage holds them until the next save.
    if (secured) await AsyncStorage.removeItem(KEYS_KEY);
    else await AsyncStorage.setItem(KEYS_KEY, JSON.stringify(keys));
  } catch {
    // Failed to save — the key lives until the screen closes; the person will paste it again.
  }
  for (const fn of listeners) fn({ ...keys });
  return keys;
}

/** Save a provider's key (replacing previous ones) or remove all of its keys (`null`). */
export async function saveKey(provider: Provider, key: string | null): Promise<Keys> {
  const keys = await loadKeys();
  if (key && key.trim()) keys[provider] = key.trim();
  else delete keys[provider];
  return store(keys);
}

/** Add a key to a provider's already-saved keys (one provider can have several: if one runs out
 *  of money or hits a limit, the next one answers). */
export async function addKey(provider: Provider, key: string): Promise<Keys> {
  const keys = await loadKeys();
  const list = keyList(keys, provider);
  const k = key.trim();
  if (k && !list.includes(k)) list.push(k);
  if (list.length) keys[provider] = list.join('\n');
  return store(keys);
}

/** The key on screen is only the tail: "…a1B2". It's never shown in full anywhere. */
export function maskKey(key: string): string {
  return `…${key.slice(-4)}`;
}

export type Draft = { question: string; answer: string };

export async function loadDraft(): Promise<Draft> {
  try {
    const raw = await AsyncStorage.getItem(DRAFT_KEY);
    const got = raw ? (JSON.parse(raw) as Partial<Draft>) : {};
    return { question: got.question ?? '', answer: got.answer ?? '' };
  } catch {
    return { question: '', answer: '' };
  }
}

export async function saveDraft(draft: Draft): Promise<void> {
  try {
    await AsyncStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  } catch {
    // see above
  }
}

export async function wipeDuo(): Promise<void> {
  try {
    await AsyncStorage.multiRemove([KEYS_KEY, DRAFT_KEY]);
  } catch {
    // see above
  }
  await wipeSecureKeys();
  for (const fn of listeners) fn({});
}

/** Removes every provider's item from the secure store (used by "Delete my data" too). */
export async function wipeSecureKeys(): Promise<void> {
  const sec = secure();
  if (!sec) return;
  try {
    await sec.remove(DUEL_KEY_ITEM);
  } catch {
    // see above
  }
  for (const p of PROVIDERS) {
    try {
      await sec.remove(secureItem(p));
    } catch {
      // see above
    }
  }
}
