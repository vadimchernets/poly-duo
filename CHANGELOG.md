# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed (D-100, 2026-10-28; planned as Duo 6.3, not released yet)
- **Critique on the iPhone asked neither ChatGPT nor Claude's blind answer.** Live run 28.10: the result
  began «EMPTY: ChatGPT returned no text / EMPTY: Claude returned no text» and the judge wrote the answer
  alone; iOS never even asked for ChatGPT. Cause (checked with a test shortcut on Shortcuts 28.10): a
  variable set from an empty Text «has any value», so «no ChatGPT answer yet → ask» and «no blind answer
  yet → ask Claude» were always false. Now variables are emptied with «Nothing», and a text is tested by
  its characters (Match Text `\S`) everywhere an empty answer must trigger a call or a retry (Duo and
  Trio). Same iPhone after the fix: both blind answers came, real differences listed, ≈2 min.
- **Far fewer permission windows on the first run.** iOS asks once for every «Save File», «Copy» and
  «Append» action of a run, even after «Always Allow»: the fixed Critique still showed ~14 windows (Duo 5:
  ~6). The Critique and Debate drafts (six and up to eleven file writes) are gone, and with them the
  resume of a cut-off run (U-05); Critique copies the result once (in the shared tail); ChatGPT's answer
  is still copied before Claude (D-98) but no longer also saved as «Duo's own». Same iPhone: 8 windows
  on the first run (notifications, ChatGPT, Claude ×2, copy ×2, remember, journal).
- **«Another mode — same question», the Recipes and «go back» run this very shortcut.** They ran the
  shortcut called «Duo» by name; after «Keep Both» the new version is «Duo 1», so they started the old
  one. Now `isSelf` (checked on Shortcuts for macOS: the child gets the input and returns its output).

### Fixed (D-98, 2026-10-28; not released yet: live iPhone repeat and second-family review first)
- **ChatGPT's answer is no longer lost when Claude hits its message limit.** On a real iPhone
  (28.10) Claude's app action threw «You have reached your current Claude message limit…»; iOS
  stops the whole shortcut with that system alert, and Shortcuts has no built-in try/catch or «continue on error» for an app
  action's error, so the «Claude did not answer» menu (made for an empty answer) was never reached.
  Now, in every mode where ChatGPT answers before Claude (Critique, My mode, Side by side, both
  Syntheses, Decision, Dispute map, Debate, both Images, round 1 of Debate until agreement),
  ChatGPT's answer goes to the clipboard right before the first Claude call of the run (in Critique
  also when both drafts were resumed; in the debate, ChatGPT's opening itself, not the log), is
  remembered as Duo's own (so the next run does not offer it as a question), and that step's
  notification says so first. Only
  when there is an answer; no new screen, tap or message. New string `notify.gpt_kept` in all 12
  languages.

### Added (Duo 6.2, 2026-10-27; built-in number duo 8)
- **When Claude does not answer, the first item is now «📲 No Claude app or not signed in? Open the App
  Store».** It opens the Claude app's App Store page; nothing is sent and the run ends there. The three
  other ways to still have the answer checked follow it as before. New iCloud links for Duo in all 11
  languages (README, docs/*/install.md, releases/version.json). Trio and Trio without a key are
  unchanged (the rebuilt files match the 6.1 ones action for action), so their links and numbers
  (trio 6, trio_nokey 3) stay.

### Fixed (Duo 6.1, 2026-10-26)
- **Duo no longer offers its own last answer as the next question.** Duo leaves its answer in the
  clipboard; the next run pre-filled the question box with it, and one «Done» spent 3 messages on
  it. Now, right after each time Duo writes to the clipboard, the first 200 characters go to
  `Poly-last-answer.txt` next to the journal; a clipboard whose first 200 characters are the same
  text leaves the box empty. A text that starts differently, or one that merely includes a short
  answer, is still offered; a text that begins with the same 200 characters (a Duo answer with
  your own lines added after it) counts as Duo's, so paste it (one tap), as when running Duo's
  own answer again on purpose. No new menu or tap. Not checked on a phone: whether iOS asks once
  for access to the new file (it sits in the same folder as the journal); the first save comes
  before the result screen, so a missed request there would end that run before the screen
  (the answer is already in the clipboard). The iPhone check before the links should cover the
  first run after updating from Duo 6, and a second run without copying anything new.
- **Recipes without typing a question.** An empty question still spends nothing, but instead of
  stopping it opens the Recipes; the menu's Cancel ends the run (one tap more than the old stop).
- **«My own checking rule» without its file is no longer a dead end.** A two-item menu: write
  the rule now (the field opens with a sample; Done saves `Poly-my-mode.txt` and the check goes
  on; a cleared or blank field saves nothing and stops) or go back to the question and the mode menu.

### Changed (2026-10-26, the strengthening plan; not yet in the iCloud links)
- **Duo: the checker no longer rewrites a correct draft.** critique, advisor and argue-2 (en, ru)
  ask it to say first that the draft is right, to list only real errors and to suggest removing
  before adding. Every prompt (en 29, ru 22) also asks ChatGPT and Claude not to save the request
  to the person's memory.
- **Duo: the question box comes pre-filled** with the shared text, or else with the clipboard
  when it holds a real sentence.
- **Duo Critique survives a hiccup.** An empty ChatGPT answer is asked once more after 3 s; the
  answer is saved as a draft next to the journal, and a run that broke off resumes from it within
  15 minutes for the same question, without asking ChatGPT again. A request over 6000 characters
  shows one notification; an empty Claude answer gets one retry with the text cut to 6000.
  None of these steps has been run on a phone yet.
- **Duo: more after the answer, without a longer menu.** The final menu is «✅ Done / 🔁 Another
  mode / ➕ More…»; More… holds «check the result once more» (ChatGPT looks for errors in Claude's
  final, prompt `ratify.txt`, 1✉), «save to Notes», «what to check → Reminders» (one reminder per
  ☐ line, Critique) and «report this run» (opens a GitHub issue form with iPhone, iOS, Duo version
  and mode, never the question). The main menu's More… gains Recipes (five ready questions),
  «Critique ⇄» (Claude writes, ChatGPT checks; `critique-reverse.txt`, `summary-reverse.txt`, known
  to Auto) and «My mode» (one line of your own for the checker, from `Poly-my-mode.txt`). In
  Critique, numbers from ChatGPT's answer that are missing from Claude's final reach the summary as
  data. Menu lengths in `tools/verify.py`, BUILD.md, CONTRIBUTING.md. Not run on a phone yet.
- **Duo: when Claude gives no answer, there is a way on.** Instead of a dead end, a small menu
  offers a free key (if `poly-key.txt` has one), Apple Intelligence on this iPhone (15 Pro or
  newer), or doing it by hand in Gemini or Meta AI with the check request already copied. The
  usual path is unchanged.
- **Duo takes a picture or a PDF from Share**: the text is read on the phone and lands in the
  question box. Debate to agreement resumes from its last finished round within 15 minutes; in
  every mode where ChatGPT speaks first, an empty answer is asked once more after 3 s.
- **Critique now starts blind, at the same 3 messages.** ChatGPT answers; Claude answers the same
  question on its own, without seeing ChatGPT; then Claude compares the two and writes the final,
  opened by «Matched independently / Did not match / What to check yourself»
  (`critique-blind.txt`). Debate to agreement and Debate also open with independent answers.
  Why: a reviewer who has read an answer tends to agree with it (the owner's «Verification
  Theater» study). Our own check (2026-10-26, CLI models, not the phone apps; blind
  judges): on 67 tasks with known answers the review turned none of 66 correct drafts wrong; on 38
  tasks picked where ChatGPT was wrong (plus controls), the review repaired 18 of 18 and harmed 1 of
  20. Between the blind and the earlier Critique no difference was established (McNemar p = 1.0;
  p = 0.25 on all 46 tasks, the three split pairs against the blind one), so we keep measuring.
- **Trio goes blind too, still 3 messages from your plans.** ChatGPT answers; Claude answers on its
  own; the third voice reads both independent answers and names only what both missed; then one
  Claude message compares all three (`trio-compare.txt`): matched independently / did not match /
  check yourself, then the final answer.
- **Fewer «confident» words, more of what was actually checked.** Prompts replace
  «Confidence: high/medium/low» with «Checked against … / Not checked …»; a side in a debate
  concedes only with a named reason (`[[CONCEDE]] because: …`); the checker changes its view only
  for a specific, checkable reason; Delta and Critique ⇄ present themselves as editing, not as fact
  checks; Auto sends facts, figures, law and medicine to Synthesis or Dispute map, where both AIs
  answer on their own first. Based on the owner's «Verification Theater» study: a reviewer who has
  seen an answer tends to agree with it.
- **Duo with Apple Intelligence** (a separate file, `dist/<lang>/ai/`, en/es/pt): Auto and
  Clarify's questions run on the iPhone itself and no longer spend a ChatGPT message.
- **Trio: the third voice can cite sources.** With a Google key, it first asks Gemini 2.5 Flash
  with Google Search (free tier) and adds up to five «Sources» under its words; any failure falls
  back silently to the usual chain. The live response format has not been seen yet.
- **Korean:** `locales/ko` (Duo and Trio, Trio without a key too) and `docs/ko`; Ukrainian docs
  (`docs/uk`). Docs now exist in twelve languages.
- **Docs call the shortcut by the name people see, «Duo»**, and say plainly that the companions
  (Voice, Photo, Quiet, Compress, Multi) are built from source and not in the iCloud links yet.
- **Trio: plainer words.** The key window went from 240 to 118 words (en), Groq and Google first
  (no SMS), NVIDIA, OpenRouter and your own paid key still there; shorter notifications; «Run Trio
  again» instead of the shared «Run Poly again»; an empty key field stops before anything is saved;
  Trio without a key says plainly when the iPhone has no Apple Intelligence. The install page puts
  «no key at all» first.
- **Trio: the first run warns about the permission windows.** With a key, the warning is now the
  first paragraph of the key window (no extra screen); without a key, the same one-time window as
  Duo's.
- **Trio in six more languages:** ar, de, fr, hi, ja, zh (`locales/<lang>/trio.json`); Trio without
  a key also in de, fr, ja, zh, where Apple Intelligence speaks the language.
- **One list of models:** `src/models.json`, read by `build_trio.py`; `tools/check_models.py`
  checks it against each provider's `/models` (keys from the environment). It found
  `qwen/qwen3.8-27b:free` gone from OpenRouter: removed; Kimi K2.6 (NVIDIA) and gpt-oss-20b (Groq)
  added, as on Android.
- **Release hashes:** `releases/SHA256SUMS`, written by `tools/build.sh` and checked by
  `tools/verify.py`; how to check a file in `docs/en/install.md`.
- **Docs match Duo 5 / Trio 4:** twelve modes, 1–8 messages with the price shown before you choose,
  Trio without a key, Android first through Poly A1 (Tasker is the older, untested path), «C1M Duo»
  as the full name, «If it doesn't work» in all ten docs languages, «Who else does this» in
  evidence.md; the 71.6→89.7% figure is marked as someone else's result, not measured on Duo.
  New: `docs/en/launch.md` (Siri, Back Tap, Control Center, Lock Screen, Action Button), issue
  forms «Run report» and «Worse after review», `docs/en/compat.md`.

### Changed (2026-10-26, the first minute; not yet in the iCloud links)
- **Duo: the first run warns before the permission prompts.** One window: iPhone will ask 4–6 times
  for access to ChatGPT and Claude, tap «Always Allow» (or «Allow») right away. It replaces the
  laptop/PC notice, which stays on the help screen. People who already ran Duo do not see it again.
- **Duo and Trio: an empty question stops the run** with one notification, before any AI is asked.
- **Duo: plain words at the end.** «Done» and «no answer» are the two branches of one check; no
  «intent timed out». The menu title points a first-timer to Critique; the second mode reads
  «🤝 Debate to agreement · 3–8✉» so the price is no longer cut off (en, de, es, fr).
- All 11 languages. Found by a screen-by-screen audit with a busy non-technical reader.

### Added (2026-10-07, debate until agreement)
- **Duo: a new mode «🤝 Debate until agreement · 3–8✉»**, second in the main menu, right after
  Critique. For life choices with no right answer («which to choose», «should I agree»): ChatGPT
  takes a side, Claude objects, ChatGPT answers the objections — up to three rounds. A side that is
  genuinely convinced starts its reply with `[[CONCEDE]]`, and the shortcut stops the rounds there
  (`If <debate log> contains [[CONCEDE]]` before every turn). Then Claude, as a neutral recorder,
  writes three sections: where they agreed / where the dispute remains / what you decide; the whole
  debate follows the outcome. Prompts `locales/en/prompts/argue-1-open … argue-4-verdict.txt`
  (shared by every language); strings in all eleven `locales/<lang>/ui.json` (menu, notifications,
  output, journal, variable, help line); the auto-router knows the mode (en, ru). `menu.main_items`
  now holds 7 entries (verify.py, BUILD.md, CONTRIBUTING.md). Test `tests/test_argue_mode.py`.
  This build is **duo 3**; signed en/es/pt/ru/uk Duo rebuilt — their iCloud links must be
  re-created (`duo_<lang>` in `releases/version.json`, README, docs/*/install.md, poly-a1).

### Added (2026-10-02, version check)
- **Duo and Trio look for a newer version at most once in 7 days.** At the very end of a run they
  read `releases/version.json` (GitHub raw, then `polyhelper.ai/duo/version.json`); if its number
  is higher than the one built in, one line asks «A new version of Duo is out — install it?» and
  «Install» opens that language's iCloud link from the same file. The day of the last check is the
  modification date of `Duo-version-check.txt` / `Trio-version-check.txt` next to `poly-key.txt`
  (iCloud Drive → Shortcuts). Strings `update.*` in every `locales/<lang>/ui.json`; code in
  `src/build_shortcut.py` (`version_check`), used by `src/build_trio.py`; test
  `tests/test_version_check.py`. This build is **duo 2, trio 2**. Signed en/es/pt/ru/uk Duo and
  Trio rebuilt — their iCloud links must be re-created.

### Fixed (2026-10-02)
- «🔁 Another mode — same question» in Duo called the shortcut «Poly», but the release installs
  as «Duo» (file name and iCloud record): it now calls «Duo».

### Changed (2026-10-02)
- Spanish speaks «usted» everywhere, like Poly A1 (pt «você», uk and ru formal «you»):
  `locales/es/ui.json` and `trio.json` (menus, notifications, help, key
  prompts), `docs/es/*`. Signed **es Duo and Trio rebuilt** — their iCloud links
  must be re-created. Russian docs (`docs/ru/*`) and the Russian Tasker flashes
  and choir steps moved from the informal to the formal «you» as well; Russian/Ukrainian/Portuguese
  shortcut strings were already formal and are unchanged.

### Added (2026-10-02)
- Android Tasker projects in all five languages (en, es, pt, ru, uk): new
  `android/generate_tasker.py` builds `android/<lang>/` from the English
  projects and `locales/<lang>/tasker.json`; ru is now generated the same way
  (its old hand-made files are reproduced byte for byte). `generate_choirs.py`
  takes any language with `locales/<lang>/choirs.json`. `tools/verify.py` checks
  that every language has the five projects and that they are up to date;
  `tests/test_tasker_locales.py`.

### Changed
- Project language is English: the Russian duplicates in README.md and
  .zenodo.json were removed (English copies already present) and the BUILD.md
  note on iCloud links translated. Russian stays only in its localization places
  (locales/ru, docs/ru, android/ru), on par with the other languages. No shortcut
  was rebuilt or re-signed; iCloud links are unchanged.

### Added
- **Trio** (`Trio.shortcut`, en/es/pt/ru/uk): ChatGPT answers, Claude checks
  (the Critique pair, prompt `critique.txt`), then a third AI from a third
  company — Gemini Flash (`gemini-3.8-flash`) on a free Google AI Studio key —
  names only the errors and gaps both missed (new prompt `trio.txt`; ru has its
  own). Its words come as a separate block under Claude's answer, into the
  clipboard and on screen. Built by `src/build_trio.py`, words in
  `locales/<lang>/trio.json`; `tools/build.sh` and `tools/verify.py` build and
  check it.
- Keys never live in the shortcut: asked once (Gemini, then an optional Groq
  key), saved in iCloud Drive → Shortcuts → `poly-key.txt`, picked out by
  their shape (`gsk_…` is Groq). With both keys, Qwen on Groq
  (`qwen/qwen3.8-27b`) stands in when Gemini's free quota is spent or it is
  still overloaded after one automatic retry.
- Plain-words errors: daily/minute limit, wrong key, overloaded provider,
  renamed model, anything else with the provider's own reply.
- Ukrainian locale `locales/uk/ui.json` — the main shortcut and companions
  now build in uk too.
- Install docs (en, es, pt, ru): how to get the free key in three steps.
- `tools/check_language.py` — a gate that fails if Cyrillic appears anywhere
  outside a language place (a `ru/`/`uk/` path part, a `*.ru.*`/`*.uk.*` file,
  or a language's own self-name in a list where every language is named in
  its own script). Covered by `tests/test_check_language.py`; wired into
  `tools/verify.py`, which CI already runs on every push.
- `android/generate_choirs.py` now loads its per-language strings from
  `locales/<lang>/choirs.json` instead of an inline Python dict (en and ru
  carry the exact same text as before — the generated `android/en` and
  `android/ru` `poly-choirs.prj.xml` are byte-identical to what shipped
  previously). `locales/es/choirs.json`, `locales/pt/choirs.json` and
  `locales/uk/choirs.json` were added alongside, translated to match the
  wording already used in each locale's `ui.json`/`trio.json`; the Android
  generator itself still only builds en/ru (there is no `android/es`,
  `android/pt` or `android/uk` donor project yet to clone from), but the
  tables are ready for when one exists. Covered by
  `tests/test_choirs_locales.py` — every `locales/*/choirs.json` carries the
  same key set as the English base and every `.format()` template in it
  formats without error.

### Checked
- On a Mac (not on a phone), 01.10.2026: the third-voice block — the same
  actions `build_trio.py` ships — ran in macOS Shortcuts against both
  providers: Gemini 3.8 Flash and Qwen on Groq answered through
  `choices[0].message.content`; Gemini found a planted error both models
  missed; a fake key gave the «key did not work» message; a Gemini 503 gave
  the «overloaded» message. The ChatGPT/Claude steps, the key-file steps and
  the Groq stand-in were not run on a device.


## [1.1.0] — 2026-09-18

### Added
- Built-in help «What is Poly» (all ten languages) now says, in one
  paragraph, that PolyHelper on a laptop or PC does more — folders, agents,
  channels, schedules, a council of several AIs — and that Poly on the phone
  is the light version without the PC features. Prompts and the shortcut's
  logic are unchanged. Not yet run on a physical phone.
- A one-time notice (all ten languages): on the very first run, before the
  question, Poly shows once that PolyHelper on a laptop or PC does more and
  that Poly on the phone is the light version. A marker file next to the
  journal (iCloud Drive → Shortcuts → `Poly-pc-notice.txt`) keeps it from
  coming back. Prompts and the modes are unchanged. Not yet run on a physical
  phone.
- `android/` — the Tasker path, marked experimental: five projects in two
  languages, the choir generator and guides. Built and verified, never run
  on a physical device.
- `DISCLAIMER.md` — what Poly is for and what it is not.
- Language switcher in the README; every doc exists in all ten languages.

### Changed
- README leads with the economics of orchestration rather than the mechanics.
- `Verified` now states its exact coverage: one phone, two of ten languages.


## [1.0.0] — 2026-09-01

- 11 modes in a two-level menu: five everyday modes up top, the rest one tap
  away under More….
- 5 companions: Voice, Photo, Quiet, Compress, Multi.
- 10 languages via `locales/`, each a folder — no fork of the code.
- Signed, verified builds per locale, packaged as a ready-to-share kit.
- Plain-text journal, delivery to the clipboard (including Universal
  Clipboard), and an in-run "What is Poly" help screen that costs nothing.
