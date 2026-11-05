# Poly Duo engine for Android

Open source (Apache-2.0, see the repository `LICENSE`). This is the code that runs Duo on Android: one AI answers, an AI from another company checks, and the two are compared or argued to agreement. It is TypeScript, with no keys or secrets in it (keys are entered by the person and stay on the phone).

## Files

| File | What it does |
|---|---|
| `duoAuto.ts` | Providers, models, voice chains, key detection, `ask`, `pickVoices`. Has a `setDuoUsa(on)` switch for "US models only"; the host calls it. |
| `duoAgree.ts` | "Both agree / where they differ". |
| `duoArgue.ts` | A debate to agreement. |
| `duoFind.ts` | "Find the mistake". |
| `duoKeys.ts` | Storing the person's own keys on the device. |
| `duoLink.ts` | Links to the provider key pages. |

## Dependencies

Peer dependencies (React Native / Expo app):

- `@react-native-async-storage/async-storage`: used by `duoKeys.ts` for the key list and the draft.
- `expo`: `duoKeys.ts` imports only `requireOptionalNativeModule` from it, to reach the native `ExpoSecureStore` module (keys go to the device keychain/keystore). If the module is missing, keys fall back to AsyncStorage; you can also pass your own store with `setSecureBackend`.

Everything else uses the global `fetch` (no other packages).

## Public API

- `duoAuto.ts`: `runDuo({ question, keys, trio, checkText, trioText, doFetch?, phone?, onStage?, onPartial? })` runs the pair (or trio) and returns a `DuoResult`; `joinResult` formats it. `ask(chain, keys, content, ...)` sends one question down a chain of models. `pickVoices(keys, phone?)` chooses the first/check/third voice; `chainFor(voice, keys, avoid?, sameOk?, phone?)` builds the fallback chain. `failOf(status, body)` classifies a provider error. `parseKeys(text)` finds provider keys in pasted text; `testKey(provider, key)` checks a key; `providerOf`, `keyList`. `setDuoUsa(on)` / `isUsa()` switch "US models only".
- `duoAgree.ts`: `parseAgreement`, `labelsFor`. `duoArgue.ts`: `runArgue`, `joinArgue`. `duoFind.ts`: `runFind`, `joinFind`.
- `duoKeys.ts`: `loadKeys`, `saveKey`, `addKey`, `onKeys`, `maskKey`, `loadDraft`, `saveDraft`, `wipeDuo`, `setSecureBackend`.
- `duoLink.ts`: `duoPath`.

## Setup order

Call `setDuoUsa(...)` once at startup, before the first `runDuo` (it decides which voices `pickVoices` may choose).

```ts
import { setDuoUsa, runDuo } from './duoAuto';
import { loadKeys, addKey } from './duoKeys';

setDuoUsa(false);
await addKey('google', 'AIza...'); // the person's own key, stored on the device
const result = await runDuo({
  question: 'Should I rent or buy?',
  keys: await loadKeys(),
  trio: false,
  checkText: 'Check the answer above...', // the prompt for the second AI (the host owns its wording)
  trioText: '',
  onStage: (stage, voice) => console.log(stage, voice),
});
console.log(result);
```

## How Poly A1 uses it

The Poly A1 app (Google Play) pulls these files with `scripts/duo-engine-sync.mjs` into its `src/duo*.ts`, adds a "Synced from" header and records the commit and the sha256 of each file in `src/duo-engine.lock.json`. A test fails if a synced file is edited in Poly instead of here. Edit the engine here, then run the sync.

Not part of the engine: the Poly screens and `duoReady.ts` (translations, notifications, sound).

## Tests

The tests currently live in the Poly A1 repository (`__tests__/duo-*.test.ts(x)`, run with `npx jest __tests__/duo-`), not in this repository.
