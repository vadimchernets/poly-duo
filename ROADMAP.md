# C1M Duo roadmap

No dates — this is a direction, not a schedule. Priorities shift with
feedback from whoever is using it — write to info@polyhelper.ai and say what you hit.

## Now

- Collect feedback from the first users of the 1.0.0 release.
- Finish the demo GIF and screenshots for the README and the docs.
- New locales. The translation files and how they are built are described in [BUILD.md](BUILD.md);
  translations and fixes are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).
- **The first real run of the Android path.** The Tasker projects in
  [android/](android/) are built and verified but have never touched a
  physical phone; one report from a real device turns them from
  experimental into a supported half of the product.
- Filling the compatibility table ([docs/en/compat.md](docs/en/compat.md)) from run reports.

## Done

- The compatibility table and a «Run report» issue form: phone, iOS version, app versions, what was tried.
- The result in three blocks ("both agree / where they differ / what to check yourself") on iPhone, in Duo 5 and Trio 4. The Poly A1 app already did it on Android.
- Trio without a key on iPhones with Apple Intelligence (iOS 26+), in English, Spanish and Portuguese.
- Duo inside Poly A1 on Android, on free keys.

## Next

- Verify the build and install flow on iPad.
- Real example outputs for each mode in `docs/` — what a Critique run, a
  Debate, a Dispute map actually look like, not just a description.
- New modes, shaped by what comes out of Discussions.

## Considering

- Carrying a question from Poly into the full council of the sibling
  project: the journal already holds the question and every draft, so
  "run this one past ten AIs" is a short step rather than a rewrite.
- A pilot of Poly itself. Not a benchmark of the pair — that the pattern
  exists has been measured by other people, and the results are collected
  in [Why a pair: the evidence, 2025–2026](docs/en/evidence.md). The pilot
  asks the narrower question: does *this* implementation keep the pattern?
  Does a factual disagreement actually reach the first lines, and does the
  canon produce a final no worse than a free-form phrase?

Nothing in this section is committed; it's what we're weighing.

## Not planned

- A server of our own.
- API keys.
- Collecting user data.
- Paid access to functionality that exists today: everything shipped stays free.
