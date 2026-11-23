# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [Unreleased] — Duo 6.11 (candidate, branch duo-search: the five search branches merged)

### Changed — the divergent first (the council of 23.11.2026 on the owner's words; dozapros of the single votes)
- **Critique → Second opinion** in all 12 languages (menu, «right away next time», notifications, journal, help,
  Auto's list), each in its own language.
- The judge's reply: the answer first (one answer from the best of both, no heading); then «■ What the second
  opinion added» — 2–5 points only one model had, each labelled new option / new risk / new criterion / new step, an
  idea not taken ends «— not taken: <reason>»; then «■ Basis» — what both reached independently with codes, a fact
  stated differently as one «Taken: … — reason [code]» line, something substantial left open as one «Open:» line.
  A FACT question: the exact answer first, «Basis» before the second opinion, which appears only if it added something.
- The question's kind (FACT / OPEN) rides on the search's query call (first line; 0 extra calls); empty → the judge
  decides, when in doubt OPEN.
- Removed: «(from memory)» (judge and answering models), «What to check yourself ☐», «(selected, the originals
  differ…)», the evidence map in the default depth and every «Not checked». Research keeps the map with ✓ / ✗ only;
  Quick keeps one «Checked against» line, left out when nothing was checked.
- The divergence search runs only when the two answers state a fact differently: no call when every number stands in
  both answers; the claim finder gets those numbers and skips points they agree on (no more «even when they agree»).
- Research: «crossing» — one short Claude call develops the most useful idea only ChatGPT had; the judge takes it
  into the answer («ChatGPT → Claude · …»).

### Added — three depths in the mode menu (the owner's decision of 23.11.2026)
- **Quick** (new item): Duo's own search, one set of cards per model, two answers, the comparison — about a minute.
- **Critique** (the default, as before the first item) = the check: the same, then the divergence search — one short
  Claude call names at most 2 claims the answers diverge on or rest on (a date, a number, a condition — even when they
  agree); Duo searches each (Bing web, narrowed to the primary source's site when named; Bing News when the web gave
  nothing), reads the page and checks the claim in its own short call ([V1], [V2]); the pages ChatGPT cited are read
  the same way. The comparison ends with an evidence map: ✓ confirmed with its code and date, ✗ contradicted,
  ○ open.
- **Research** (new item): before the answers each model researches its own cards — picks up to 3 pages, Duo reads
  them in parts (each part one short call of that model), the model says ENOUGH or gives a new query; the second
  round adds up to 4 cards and reads up to 2 more pages; each model answers from its notes; then the check.

### Added — Duo searches by itself, without keys
- Each model gets its own engines, all at once, no fallback chain: Claude — Google News RSS + Wikipedia (MediaWiki,
  last edit date) + SearXNG; ChatGPT — Bing News RSS + Bing web RSS + DuckDuckGo HTML. An engine that answers with a
  captcha, a rate limit, an error or nothing is skipped without a word; offline or a long pasted text: no search.
- Queries: one short Claude call writes 2–3 from the question's own words — line 2 in English (sent to the English
  editions), line 3 a primary-source wording (deep research) — or NONE for a question the web cannot help; then
  nothing is fetched.
- Cards: reprints glued (one link, one headline = one card), ordered by age (this week; this quarter and undated web
  pages; older), at most 8 per model, numbered by Duo: [C1]… Claude's, [G1]… ChatGPT's. Never counted or shown: how
  many engines found a thing (popularity, not truth). The judge sees both sets; the models write only codes; «Sources»
  under the result is printed by Duo from its own lists, for the codes the text cites.
- Builder setting `C1_SHARED_SOURCES=1`: one shared set [S…] for both models instead of two (default: two).
- Answers in parts (from search-fable): every request keeps its measured cap (Claude ~300 words, ChatGPT ~600); an
  answer that does not fit ends with [[MORE]] and is continued by a new call with its own 30 s. Two long answers: the
  comparison is two calls (sections, then the final answer).

### Changed
- The comparing prompt no longer opens the result with «⚠ Both models may not know this»: the first line is the
  answer; a fresh fact without a dated source is marked «(from memory)» and is the first ☐ with a concrete action; a
  dated source or a page check for the period asked about counts as a confirmation, with no warning.
- The main menu has 9 items (Critique, Quick, Research, Argue, …); its title gives the price of each depth.

## [1.0.10] — 2026-11-23 — Duo 6.10 (built-in number duo 16)

Signed Duo files for 12 languages in `releases/` (SHA256SUMS), built from dded14e with duo 16. Measured and run on the
owner's iPhone on 22.11.2026 (Shortcuts, the Claude and ChatGPT apps, ~35 timed calls; the report is LIMITS-6.10 in the
promotion folder). The iCloud links in `releases/version.json`, README and `docs/*/install.md` are re-created from these
files on a device (Share → Copy iCloud Link).

### Changed — the length lines are now only what the measurements proved
- **«Ask Claude» and «Ask ChatGPT» are both cut off at about 30 s** from the start of the call («Could not run the
  action … unknown error» at 31-32 s, every time), whatever the answer length. Claude writes 20-35 words a second,
  ChatGPT 40-70.
- **Claude: about 300 words** (was 150). 300 came back in 10-22 s on every long and medium question (English and
  Russian); 400 failed once in five and took up to 24 s; 500 and no cap failed on «detailed» questions.
- **ChatGPT: about 600 words** (new; it had no line). 600 came back in 13-19 s; 800 took up to 25 s; no cap failed
  three times in five on «detailed» questions.
- **Gone from the line:** «do not search the web» (the Claude action has no web search at all), «do not think for
  long» (no change in time: 17 s with it, 18 s without) and «only the result, the main disagreements and what to
  check» (it cut Claude's own blind answer down to a comparison). Left: «no introduction» and the word cap.
- 12 languages; zh and ja count characters (600 / 1200 字). The SVG image steps carry neither line.
- New key `brief.chatgpt` in every `ui.json`; `set_gpt_brief` / `act_gpt(..., brief=True)` as for Claude.

## [1.0.9] — 2026-11-22 — Duo 6.9 (built-in number duo 15)

Signed Duo files for 12 languages in `releases/` (SHA256SUMS), built from ca96a42 with duo 15; run on an iPhone by the
owner (5 Critique questions: the ⚠ line came exactly where it should). Trio files are unchanged. The iCloud links in
`releases/version.json`, README and `docs/*/install.md` are re-created from these files on a device (Share → Copy
iCloud Link).

### Added — «Both models may not know this» (KI Forum 226, post 1762, Karl, 22.11.2026)
- **Critique no longer counts two matching guesses as a confirmation.** The comparing step is told today's date (from
  the phone, ISO 8601 `2026-11-22`, Gregorian on any calendar setting, one «Current Date» action: no permission, no
  extra message) and a Freshness rule: when a fact may have changed since the models were trained, or lies after
  today, and that would materially change the answer, and no answer cites dated material that supports it for the
  period asked about (a bare link, a citation date or a preview does not count), the result opens with one line «⚠ Both models may not know this: <fact>. Check a fresh source that shows its date —
  <where>», the matched point is marked «(from memory — not confirmed)», the first ☐ says what to look for and where,
  the bottom line says the models may be out of date on it and the fact goes under «Not checked». A question about
  the future gets «⚠ This has not happened yet: both answers are forecasts, not facts»; a single answer gets «⚠ This
  answer may be out of date». An answer that says it searched and cites a recent source outweighs one that says it
  cannot know. Ordinary questions (history, science, how-to, opinions, a pasted text, a date in the question or in an
  answer) get no line and no word about freshness. Written by the model in the language of the
  question, 12 languages; English prompt and the Russian edition (`locales/ru/prompts/critique-blind.txt`). Same in
  My mode and in the by-hand check after a resumed draft. The two answering models do not see the rule.
- **The retry after an empty comparison keeps both answers.** It used to cut the whole request to its first 6000
  characters, so Claude's own answer (it comes last) fell off; now the request is rebuilt with the question (400),
  each answer (1200) and the numbers (200) cut on their own. The «Long text» notice counts the data only (2500
  characters, as before), so the longer instructions do not make an ordinary run «long».
- Tests: `tests/test_freshness.py` (the rule and today's date reach all five comparing requests, never the
  answering models; every prompt override keeps the English placeholders; the retry carries both answers; without
  the Freshness additions the English prompt equals the one before; the ⚠ line and the ☐ items survive
  strip_markdown and reach Reminders; no new permission window or message); the manual sheet
  `tests/behavior/en/freshness.md` (13 questions: fresh / timeless / opinion / mixed / pasted text / past result).
- README: the agreement figures hold for what the models could have learned; after their training Duo does not count
  a match.

## [1.0.8] — 2026-11-18 — Duo 6.8 (built-in number duo 14)

Signed files in `releases/` (SHA256SUMS; Arabic added: `releases/ar/Duo.shortcut`) and new iCloud links for 12
languages in `releases/version.json` and README. Built from e4ab303 with duo 14; run on an iPhone (ru) through iPhone
Mirroring, and by voice by the owner. Trio files are unchanged.

### Changed — voice-first Duo (D-128, the owner's run with Siri and VoiceOver, 2026-11-18)
- **The mode menu and «What next?» can be used by voice**: each item is one or two plain words without emoji
  («Critique», «Argue», «Advisor», «Compare», «Synthesis», «Auto», «More»; «Done», «Another mode», «Open Poly», «More»),
  12 languages. What each mode is for and its price in messages sit once in the menu title. VoiceOver used to read the
  emoji's name and the whole explanation before every item, and Siri looped on «Survey».
- **One notification per run**, at the end: «Duo — Answer ready». The progress banners
  (start, steps, retries) are now Comments in the shortcut; VoiceOver read each of them aloud. «1–4 minutes, do not
  lock the phone» moved into the question box. Failure notices (no answer, ChatGPT down) stay.
- Run on an iPhone (ru, through iPhone Mirroring): question → Critique → both answers → «What next?» → Done.
- **First run is a spoken Setup, before the question** (the owner's Siri run: a «Copy to clipboard» permission window
  came up silently on the locked phone and the run stood still). Duo says aloud that several windows follow and to tap
  «Always Allow» / «Allow» (ask someone to help if tapping is hard; only this once), then calls in a row everything
  that asks: ChatGPT and Claude (a one-word request each), the notification, the update check on both web addresses, the one file write (`Duo-setup-<version>.txt`, written last so a
  Setup cut short runs again; a new version runs its own Setup) — and says «Done, Duo now works by voice». The weekly update check stays at the end of a run.
- **No permission window in a working run**: no «Copy to Clipboard» on the main path (only when the person picks
  «Open Poly», the by-hand check or an Image), no journal entry (`Poly-journal.md` is no longer written; «Save to Notes»
  keeps a result). The Critique draft stays (its «Save File» asks no permission: (it does ask once, in the first Critique: iOS asks
  per action, so the Setup cannot ask it in advance), so a Critique cut off by a message limit still resumes. Draft for the site: `docs/draft-first-setup.md`, `docs/draft-first-setup.ru.md`.

## [1.0.7] — 2026-11-15 — Duo 6.7 / Trio 8 / Trio without a key 5 (built-in numbers duo 13, trio 8, trio_nokey 5)

Signed files in `releases/` (SHA256SUMS) and new iCloud links in `releases/version.json`, README and
`docs/*/install.md`. Duo built from 253b185 (its shortcut is the same as at ea2bff7, checked on an iPhone on 2026-11-15),
Trio from 253b185. Everything below down to «Duo 6.5» reaches people with this release.

### Fixed (live iPhone runs of 2026-11-14 and 2026-11-15)
- **Time Between Dates came back blank on the device** (the resume menu never appeared, the weekly version check age
  was blank): every date in it is now a text token (`act_time_between`); `validate()` rejects an attachment date.
- **Debate to agreement and Trio stopped with «Choose values for each parameter in this action»** right after
  ChatGPT's opening: «contains» now tests a Text action (Get Variable → Text → If Text contains), not a variable first
  set from «Nothing» or Contents of URL.
- **Long Claude answers broke «Ask Claude»** («unknown error»): every Claude request starts with a brevity line
  (about 150 words, no search) in all 12 languages; in Trio too (its four Claude requests).
- **ChatGPT output** is cleaned through Replace Text right after every «Ask ChatGPT» (citation markers,
  `entity[...]` / `image_group{...}` markup), in Duo and in Trio.

### Fixed (tester report of 2026-11-13: iPhone XR, iOS 18.7.11, Ukrainian; not yet re-run on that iPhone)
- **Side by side and a long Critique from the Shortcuts app** (Side by side stopped with the bare iOS alert 2 runs out
  of 2, through Siri it ran; a ~2400-character Critique ended with no result while both apps held answers): the cause is
  not proven yet. Duo's actions are the same whichever way it is started, so iOS stops or empties an app action there.
  Side by side keeps its form. Added: a diagnostic build (`C1_DIAG=1 python3 src/build_shortcut.py <lang>` →
  `dist-diag/`, never released) with a notification before and after every «Ask ChatGPT» / «Ask Claude» — characters
  returned and seconds — to see on the phone which action fails and how long it took.
- **No answer at all ended in silence**: when no AI answer reached Duo, one window now says that ChatGPT and Claude may
  have answered in their apps, iOS did not pass it on, and to open the app or run Duo through Siri (12 languages).
- **«ChatGPT sent no answer — most likely its limit»** after «Ask Claude alone» in the resume menu, where ChatGPT was
  not asked at all; and the «most likely its limit» wording in general. The lines now list the causes (limit, signed
  out, iOS cut a long step) and say that an answer that came is in that AI's app (12 languages).
- **The resume menu on the very first run** of a fresh install: the draft's age («Time Between Dates» in minutes) went
  through a Number, and in the Ukrainian or Russian number format «4 320» minutes could read as 4. The age is now tested
  as text (0–30, optional minus), and the draft's file name carries a short hash of the builder and the language's
  texts: deleting the shortcut keeps iCloud Drive → Shortcuts, and an older build's draft is never offered.
- **«⟦duo-draft:0⟧ ⟦Q⟧» in the Save File permission window**: the draft markers are invisible format characters now and
  are tested with Match Text only. A draft in the old format is not offered.
- **English headings in a Ukrainian result** («What to verify:», «■ FINAL ANSWER»): the prompts ask for the heading
  in the language of the question (`advisor.txt`, `critique-blind.txt`, `trio-compare.txt`).
- **«More…» had no way back**: «↩️ Back» (`menu.back`) opens the mode menu again with the same question, without the
  question field; nothing is spent.
- README and the built-in help (11 languages): a tap on the screen does not stop Duo (leaving Shortcuts or locking the
  phone may); README and the first-run window: each mode asks 1–4 more permissions the first time it is chosen. docs/uk/install.md: the Russian word for «several» replaced with the Ukrainian one (#6, #7).

### Fixed (Android engine, issues #1–#5 from the same tester)
- `ask()` and `testKey()` keep the time limit on while the response body is read (#1).
- `failOf()` calls a message with «region / country / location» a region block only for 400, 403 and 451 (#2).
- `testKey()` checks a Google key with the models of the GEMINI chain (Flash-Lite first), `googleCheckChain()` (#3).
- `conceded()` counts `[[CONCEDE]]` only at the start of the reply; `withoutMarker()` removes every copy (#4).
- `parseAgreement()` ends a line at the confidence / corrections section in every language, `SECTION_END` (#5).

### Changed (Critique and Trio: a value chosen between two answers is marked, KI Forum, Harry, 2026-11-06, owner's yes 2026-11-13)
- **«Adopted» became «Selected, the originals differ»**. Where ChatGPT and Claude gave a value differently (the ibuprofen
  example: 4–6 against 6–8 hours), «Did not match» now names the kept one as «Selected, the originals differ: … — because …»,
  and the FINAL ANSWER marks such a value right where it stands: «(selected, the originals differ: ChatGPT …, Claude …)»,
  so a person who reads only the final answer sees that the answers differed. `locales/en/prompts/critique-blind.txt`,
  `trio-compare.txt` and their Russian overrides. Android already shows «They differ» as a block of its own.

### Fixed (Android engine, the same tester report of 2026-11-10 carried over from the iPhone)
- **A check that failed no longer throws the first answer away** (the Android side of No.52). When every model of the
  check (`runDuo`) or of the critic (`runFind`) fails, the `DuoError` now carries the answer that already came
  (`DuoError.got`, made by `withGot`), so the host shows it with the reason instead of an error alone. The debate
  already kept its turns (`ArgueResult.cut`).
- **A long question asks for a shorter answer** (No.53): from `LONG_QUESTION` (1200) characters on, `briefed` puts
  `BRIEF_LINE` in front of the question in `runDuo`, `runFind` and `runArgue`, so a free model is less often dropped
  at `TIMEOUT_MS` mid-answer. `isLong` tells the host when to say so.
- **Markdown** (No.56): `plain` now also takes off `*italic*`, keeps «x**2» and «2*3*4», and leaves a fenced code block
  as it is (``` or ~~~, indented or not, and one left open runs to the end).

### Fixed (Duo 6.6 source, tester report of 2026-11-10: iPhone XR, iOS 18.7.11, Ukrainian; released as Duo 6.7, duo 13)
- **Side by side stopped with the bare iOS alert «There was a problem running the shortcut»** (2 runs out of 2, right
  after the ChatGPT step), while Critique and Advisor ran to the end on the same phone. Side by side was the only one of
  the three that put Claude's output straight into a Text; Critique reads it from a variable, Advisor only stores it.
  Every «Ask Claude» output in Duo is now read through Set Variable → Get Variable first (the form that runs on iOS 18
  and on newer iOS). Side by side also names its step («[2/2] Claude answers on its own…», next to «ChatGPT's answer is
  already in your clipboard»), asks Claude once more after an empty answer, and gives ChatGPT's answer with the line
  «Claude did not answer» when Claude gives nothing. Not yet re-run on an iOS 18 iPhone.
- **A long question (~1800 characters) was cut off at ChatGPT** («the action was interrupted because it did not finish
  in time»): iOS gives an app action a time limit that a shortcut cannot change or catch. From 1200 characters on, Critique,
  My mode and Side by side ask both AIs for a shorter answer (one line in front of the request) and say so in one
  notification. The menu after a Critique cut off at ChatGPT now names this cause too and says that ChatGPT's answer,
  if it came, is in the ChatGPT app. The other modes (Synthesis, Dispute map, Debate, Decision, Delta, Image, Debate to
  agreement) do not get the shorter-answer line yet.
- **Raw Markdown** («**1. Matched independently**», «**Bottom line:**») is taken off the result (bold, italic, heading
  marks) before it is copied, written to the journal and shown — also in the result screen's title. An answer with a
  code block is left as it is («x**2», «# comment» are code there).
- **Advisor on a question** (not a text) no longer answers «there is nothing to check»: it says that it checks a ready
  text, names Critique for questions, answers briefly and lists what to verify.

### Changed (same release, 12 languages)
- The mode menu says what each main mode is for («Advisor — checks a text you already have») and what ✉ counts
  («✉ = messages to the AIs»).
- Times: Critique, Side by side and Advisor say «1–3 min» (Advisor said «≈40 sec»; measured 2–3 min).
- The first-run window says that each mode asks for 1–3 more permissions the first time it is chosen.
- «logged out» is said in the language of the build (it stays in English only in English).
- «Done» adds: did not open by itself? tap the Duo notification (iOS shows the result as a notification when Shortcuts
  is not in front).

### Added (2026-11-05)
- **Android Duo engine is now open code in `android/engine/`** (duoAuto, duoAgree, duoArgue, duoFind, duoKeys, duoLink; Apache-2.0). The Poly A1 app pulls it from here instead of keeping its own copy. The "US models only" switch is injected with `setDuoUsa`, so the engine does not depend on Poly code.

## Earlier Duo / Trio releases (iCloud links only)

### Added / Fixed (Duo 6.5, D-29, 2026-10-30; built-in number duo 12)
- **Optional switches in «➕ More…» at the end of a run (off by default):** «Critique right away next time» (skips the
  mode menu), «Shared text: ask without editing» (a shared text of three words, or six Chinese / Japanese / Korean
  characters in a row, goes without the question box) and «Show all menus again». Kept in one small file,
  `Duo-prefs.txt`. «Another mode», the Recipes and «go back» start with a marker that is cut off at once and force
  the question box and the menu.
- **The text of `Duo-prefs.txt` no longer reaches the ChatGPT and Claude requests or the clipboard** (found on the
  iPhone 29.10 on the «Critique right away» path). The flags that depend on the file are only ever cleared; a leak
  test follows every request, clipboard write, file write, notification, link and speech action.
- **A run that goes on from an interrupted Critique reads the file first**, so «More… → Critique right away» can no
  longer write `QUICK=1` there (and the other way round). «Saved» is shown after the file is written.
- Shorter start notifications: the «logged out» hint moved to the first-run window and to the «ChatGPT sent no
  answer» notification, and the Critique start keeps a five-word «Stuck? Open ChatGPT and sign in». Gentler «please
  wait» wording and «Duo» instead of «Poly» in the notifications, 12 languages. The first-run window no longer
  promises a number of permission prompts.

### Fixed (Trio 7 / Trio without a key 4, D-101, 2026-10-29)
- **Trio stopped on the iPhone with «Choose values for each parameter in this action».** Live iPhone 29.10: after the
  third voice. Bisected on Shortcuts for Mac: «If <variable> does not contain <the Repeat Item>» in the number pass is
  rejected (the same dialog as D-100); it is now the whole-number Match Text of Duo's Critique. Also no «has any value»
  straight on a Dictionary Value (a Text made from it is tested), and Gemini's search sources are read from the
  answer's text instead of walking groundingChunks. The light key chain Duo's «Claude did not answer» menu reuses gets
  the same fix. Trio from source then ran to the end on the iPhone.
- Review by Kimi (other family): a Gemini answer WITHOUT search left the sources Match empty and the next action
  would have stopped the run; and «Get Items in Range 1…5» stops it when there are fewer than 5 sources (found on
  Shortcuts for Mac). Sources are now read only from a source's «web» object, guarded, and cut to 5 lines by Match
  Text; checked on Mac with and without sources. Built-in numbers trio 7, trio_nokey 4; iCloud links 11 + 9.

### Added (Duo 6.4, D-101, 2026-10-29; built-in number duo 11)
- **Whoever answered, you get that answer.** When one app stops on its message limit (or signs out),
  Critique no longer leaves you with nothing: ChatGPT gave nothing → Claude's own answer with a line
  «ChatGPT did not answer — most likely its message limit; no comparison this time; run Duo later or try
  Trio» (no comparing message is spent on a single answer); Claude did not compare → ChatGPT's answer with
  the same line about Claude, then the «check with…» menu (Trio's free keys, this iPhone, by hand).
- **A Critique cut off by a limit goes on where it stopped.** When the Claude app hits its limit, iOS stops
  the whole shortcut with a system alert (Shortcuts has no try/catch). Critique now keeps one draft file
  (the question, then ChatGPT's answer, then «done») through ONE «Save File» action run three times by a
  loop — one permission window, once. The next run within 30 minutes, started without input, offers: go on
  asking only Claude (no new ChatGPT message), check ChatGPT's answer without Claude, show it, or a new
  question; after a stop at ChatGPT: Claude alone, both again, or a new question. This brings back the
  resume removed in 6.3.
- The free-plan note: after the limit, an assistant may answer with a lighter model (said in the limit
  line; the apps' actions do not say which model answered, so Duo does not claim it).

### Fixed (Duo 6.3.1, 2026-10-28; built-in number duo 10)
- **The journal entry is written before the result screen.** On a real iPhone (28.10, Duo 6.3) the
  «Append to file» permission window that came right after the result screen was closed vanished on
  its own within ~1.5 s and the run ended there: no journal entry, no «What next?». Now every
  permission window of a run comes before the result screen (also for «Check the result again»).
- The weekly update offer is shown only when version.json has a link for this language (Codex).
- **No more «Choose values for each parameter in this action» after «Done».** The weekly version check
  stopped every run there (iPhone and Mac, 28.10), so it never ran nor stamped its date: a number
  condition on a «Get Variable» / «Dictionary Value» output, and «contains» straight on «Contents of
  URL», are rejected by Shortcuts. Both now go through a Number / a Text (checked on Shortcuts for Mac:
  the check passes, and the update offer appears when the number is higher).

### Fixed (Duo 6.3, D-100, 2026-10-28; built-in number duo 9)
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

### Fixed (Duo 6.3, D-98, 2026-10-28)
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
- **Duo: the first run warns before the permission prompts.** One window: iPhone will ask several times
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
