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

Peer dependencies (React Native): `@react-native-async-storage/async-storage` and `expo` (used by `duoKeys.ts`).

## How Poly A1 uses it

The Poly A1 app (Google Play) pulls these files with `scripts/duo-engine-sync.mjs` into its `src/duo*.ts`, adds a "Synced from" header and records the commit and the sha256 of each file in `src/duo-engine.lock.json`. A test fails if a synced file is edited in Poly instead of here. Edit the engine here, then run the sync.

Not part of the engine: the Poly screens and `duoReady.ts` (translations, notifications, sound).

## Tests

The tests currently live in the Poly A1 repository: `__tests__/duo-*.test.ts(x)`.
