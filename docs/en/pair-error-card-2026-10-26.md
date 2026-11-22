# Pair error correlation by task class — 26 October 2026

Local draft prepared on 22 November 2026 for D-227 / C-5. No publication performed.
These are exploratory, post hoc calculations from the archived CLI experiment.

ChatGPT A was invoked as `codex exec -m gpt-5.6-sol`; blind Claude C as
`claude -p --model sonnet`. The alias does not pin an exact Claude version.
These data are separate from the flagship agreement measurement (72/74).
A and C each answered independently; D and B are review variants and are not the
pair used for the correlation below. See the [archived method and reports](../../evidence/pair-check-2026-10-26/README.md).

## Definition and counting

An error is any verdict other than `correct`, including `partial`, using the
archived `judge/final.json` files. Round 1 includes its recorded first-line
adjudications, including overrides of the judges; it is not the judges-only tally.
For binary error indicators, phi is Pearson correlation, not an error rate:

`phi = (n11*n00 - n10*n01) / sqrt((n10+n11)*(n00+n01)*(n01+n11)*(n00+n10))`.

Here `n00` means both correct, `n01` means A correct / C wrong, `n10` means
A wrong / C correct, and `n11` means both wrong. When either error indicator is
constant, phi is undefined (shown as n/a), rather than zero. Each rate interval
below is 95% Wilson for that model's error proportion, not for phi.

## Round 1: all 67 tasks

| Class | N | n00 | n01 | n10 | n11 | phi | A errors, 95% Wilson | C errors, 95% Wilson |
|---|---:|---:|---:|---:|---:|---:|---|---|
| ALL | 67 | 62 | 4 | 0 | 1 | 0.4334 | 1/67 [0.3–8.0%] | 5/67 [3.2–16.3%] |
| adversarial | 12 | 12 | 0 | 0 | 0 | n/a | 0/12 [0.0–24.3%] | 0/12 [0.0–24.3%] |
| everyday | 10 | 9 | 1 | 0 | 0 | n/a | 0/10 [0.0–27.8%] | 1/10 [1.8–40.4%] |
| hard | 15 | 12 | 2 | 0 | 1 | 0.5345 | 1/15 [1.2–29.8%] | 3/15 [7.0–45.2%] |
| ordinary | 15 | 15 | 0 | 0 | 0 | n/a | 0/15 [0.0–20.4%] | 0/15 [0.0–20.4%] |
| tricky | 15 | 14 | 1 | 0 | 0 | n/a | 0/15 [0.0–20.4%] | 1/15 [1.2–29.8%] |

## Round 2: all 46 selected tasks

| Class | N | n00 | n01 | n10 | n11 | phi | A errors, 95% Wilson | C errors, 95% Wilson |
|---|---:|---:|---:|---:|---:|---:|---|---|
| ALL | 46 | 20 | 3 | 18 | 5 | 0.1147 | 23/46 [36.1–63.9%] | 8/46 [9.1–30.7%] |
| arithmetic | 16 | 6 | 2 | 4 | 4 | 0.2582 | 8/16 [28.0–72.0%] | 6/16 [18.5–61.4%] |
| calendar | 8 | 6 | 0 | 2 | 0 | n/a | 2/8 [7.1–59.1%] | 0/8 [0.0–32.4%] |
| characters | 5 | 1 | 0 | 4 | 0 | n/a | 4/5 [37.6–96.4%] | 0/5 [0.0–43.4%] |
| letters | 2 | 1 | 0 | 1 | 0 | n/a | 1/2 [9.5–90.5%] | 0/2 [0.0–65.8%] |
| percent | 5 | 0 | 0 | 4 | 1 | n/a | 5/5 [56.6–100.0%] | 1/5 [3.6–62.4%] |
| puzzle | 6 | 4 | 1 | 1 | 0 | -0.2000 | 1/6 [3.0–56.4%] | 1/6 [3.0–56.4%] |
| units | 1 | 0 | 0 | 1 | 0 | n/a | 1/1 [20.7–100.0%] | 0/1 [0.0–79.3%] |
| words | 3 | 2 | 0 | 1 | 0 | n/a | 1/3 [6.1–79.2%] | 0/3 [0.0–56.2%] |

## Round 2: 38 tasks without tool-call artifacts

| Class | N | n00 | n01 | n10 | n11 | phi | A errors, 95% Wilson | C errors, 95% Wilson |
|---|---:|---:|---:|---:|---:|---:|---|---|
| ALL | 38 | 19 | 1 | 17 | 1 | 0.0124 | 18/38 [32.5–62.7%] | 2/38 [1.5–17.3%] |
| arithmetic | 8 | 5 | 0 | 3 | 0 | n/a | 3/8 [13.7–69.4%] | 0/8 [0.0–32.4%] |
| calendar | 8 | 6 | 0 | 2 | 0 | n/a | 2/8 [7.1–59.1%] | 0/8 [0.0–32.4%] |
| characters | 5 | 1 | 0 | 4 | 0 | n/a | 4/5 [37.6–96.4%] | 0/5 [0.0–43.4%] |
| letters | 2 | 1 | 0 | 1 | 0 | n/a | 1/2 [9.5–90.5%] | 0/2 [0.0–65.8%] |
| percent | 5 | 0 | 0 | 4 | 1 | n/a | 5/5 [56.6–100.0%] | 1/5 [3.6–62.4%] |
| puzzle | 6 | 4 | 1 | 1 | 0 | -0.2000 | 1/6 [3.0–56.4%] | 1/6 [3.0–56.4%] |
| units | 1 | 0 | 0 | 1 | 0 | n/a | 1/1 [20.7–100.0%] | 0/1 [0.0–79.3%] |
| words | 3 | 2 | 0 | 1 | 0 | n/a | 1/3 [6.1–79.2%] | 0/3 [0.0–56.2%] |

Round 1 added 27 tasks after the first pass; its classes are not a random sample
of everyday usage. Round 2 selected all 23 preliminary A errors and 23 randomly
sampled A-correct controls. Its phi is conditional on that selection and is not
an estimate of correlation in normal usage. The 38-task sensitivity analysis
uses the archived exclusion rule: remove a task if any of C, D or B contains
`<invoke` instead of an answer. These exclusions therefore also depend on review
outputs, not just A and C. The eight excluded IDs are: m05, n03, n04, s04, s05, s07, s08, x04.

## All round-2 candidates: A-only preliminary screening

There were 108 candidates, 107 retained for screening after excluding h01
(the reference overlooked a historical US twenty-cent coin). Across those 107,
23 A answers were marked wrong. This is the archived token/manual pre-check used
for selection, not blind final grading. C was not graded on all candidates, so
these 107 records cannot supply pair phi. No Wilson interval or population error
rate is inferred from this screening table.

| Class | Candidates retained | A preliminary errors |
|---|---:|---:|
| arithmetic | 32 | 8 |
| calendar | 23 | 2 |
| characters | 8 | 4 |
| letters | 10 | 1 |
| logic | 4 | 0 |
| percent | 8 | 5 |
| premise | 4 | 0 |
| puzzle | 10 | 1 |
| units | 2 | 1 |
| words | 6 | 1 |

## Reproduce and inspect

From the repository root:

```sh
python3 -I evidence/pair-check-2026-10-26/pair_card.py
```

The [derived JSON](../../evidence/pair-check-2026-10-26/pair_card.json) records
every task ID in its contingency cell, exact values, intervals, exclusions, and
SHA-256 hashes of all calculation inputs. The [script](../../evidence/pair-check-2026-10-26/pair_card.py)
reads the archive without modifying it and performs no model or network calls.

The raw evidence and scoring rules are in
[round 1](../../evidence/pair-check-2026-10-26/round-1/score.ru.py) and
[round 2](../../evidence/pair-check-2026-10-26/round-2/score.ru.py).
Small cells and constant margins limit interpretation; no confidence interval
for phi or evidence of low population correlation is claimed.
