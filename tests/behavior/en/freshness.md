> Duo 6.11 (23.11.2026): the ⚠ line no longer opens the result. A fresh fact from memory is marked «(from memory)» where it stands and is the first ☐ with a concrete action; a dated source found by Duo confirms it with [N] and no warning. The expectations below that name the ⚠ line describe Duo 6.9–6.10; the 6.11 checks on the iPhone are in the result note of the search-fable branch.

# Freshness — the manual check on an iPhone

What it checks: on a question whose answer may have changed after the models were trained, Critique says
«⚠ Both models may not know this … Check a fresh source that shows its date» instead of presenting the match as a
confirmation; on every other question nothing new appears. Source: KI Forum 226, post 1762 (Karl, 22.11.2026).

How: run each question through **Critique** (3 messages). Keep both independent answers and the result. Note the
date of the run. The automatic tests (`tests/test_freshness.py`) only prove that the rule and today's date reach the
comparing request and its retry; this sheet is the behaviour. To see the retry: a question with two long answers
(«Compare the pension systems of Germany, France and Italy in detail») — when Claude's first comparison comes back
empty, the result still names points from BOTH answers.

| # | Question | Kind | Expected result |
|---|---|---|---|
| 1 | Who won the most recent Formula 1 drivers' championship? | fresh | ⚠ line at the top; the name in «Matched independently» ends «(from memory — not confirmed)»; the first ☐ says what to look for and where (the season's official standings); the fact is under «Not checked» |
| 2 | What is the ECB deposit facility rate today? | fresh, a number | ⚠ line even if both give the same rate; ☐ points to the ECB's dated rate page |
| 3 | Who is the current CEO of OpenAI? | fresh, no «latest» word | ⚠ line; ☐ — the company's leadership page or a dated announcement |
| 4 | Was hat sich 2026 beim Bürgergeld geändert? | fresh, German | ⚠ line in German («Beide Modelle wissen das möglicherweise nicht: …»), headings in German |
| 5 | Who will win the 2027 Champions League? | after today | «⚠ This has not happened yet: both answers are forecasts, not facts.» |
| 6 | Why is the sky blue? | timeless | no ⚠ line, not a word about freshness |
| 7 | When did the Berlin Wall fall, and why? | history with a year | no ⚠ line |
| 8 | Today I'm helping my daughter with geometry. How many sides does a hexagon have? | «today» that is not about the fact | no ⚠ line |
| 9 | Should I take a better-paid job with a 90-minute commute? | opinion | no ⚠ line |
| 10 | How does compound interest work, and what is the best savings rate in Germany right now? | mixed | the ⚠ line names only the savings rate; the explanation of interest stays in «Matched independently» without a mark |
| 11 | (paste the minutes of a meeting held this week) What were the three decisions? | pasted text | no ⚠ line: the answer is in the pasted text |
| 12 | (paste a 2024 bus timetable) Does the 7:15 bus still run? | pasted text, asked whether it still holds | ⚠ line; ☐ — the operator's current timetable with its date |
| 13 | Who won yesterday's Bundesliga match Bayern–Dortmund, and what was the score? | past result | ⚠ line unless an answer cites a match report dated after the match; a preview published before it does not count |

Also: if in 1–3 one answer names a source and its date (ChatGPT searched), there is no ⚠ line and that source is
named. With Claude's answer empty (the «check by hand» path after a resumed draft) a fresh question gives
«⚠ This answer may be out of date: …».

Also with ChatGPT's own web search (its answer says it searched and names a recent source) and Claude saying it
cannot know: the final answer takes ChatGPT's fact, not Claude's «cannot know».

**Pass:** the ⚠ line on 1–5, 10, 12 and 13 (when both answers are from memory), and on none of 6–9 and 11. A false line
on 6–9 or 11 counts as worse than a missed one on 1–5: then narrow the Freshness rule in `critique-blind.txt`, do not
add caveats. A fail regardless of the ⚠ line: the final answer states an unconfirmed winner, score or rate as a plain
fact.

The line as it should read in the 12 languages (reference for the reader; the model writes it in the language of the
question):

| | |
|---|---|
| en | Both models may not know this |
| de | Beide Modelle wissen das möglicherweise nicht |
| fr | Les deux modèles ne le savent peut-être pas |
| es | Es posible que ninguno de los dos modelos lo sepa |
| pt | É possível que nenhum dos dois modelos saiba isto |
| ar | قد لا يعرف النموذجان هذا |
| hi | हो सकता है दोनों मॉडल यह न जानते हों |
| ja | 両方のモデルがこれを知らない可能性があります |
| ko | 두 모델 모두 이 내용을 모를 수 있습니다 |
| zh | 两个模型可能都不知道这一点 |
| ru, uk | see `locales/ru/prompts/critique-blind.txt` (the Russian edition holds its own wording) |
