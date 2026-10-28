# FAQ

About C1M Duo — the pair of ChatGPT and Claude on iPhone.

**Do I need an API key?**
No. Duo runs on the ChatGPT and Claude apps already installed and signed
in on your phone — there's no key to generate or paste anywhere.

**Does it spend my plan limits?**
Yes. Each run costs 1 to 8 messages (Critique 3, Debate to agreement 3–8, Advisor 1) against your ChatGPT and Claude
subscriptions, the same as chatting in those apps directly. The ✉ badge in
the menu shows the price before you pick a mode.

**Is it safe to install a shortcut from the internet?**
Official builds are published as signed files in this repository's `releases/` folder and on polyhelper.ai/duo. You can also open the shortcut in the
Shortcuts app and read every step before running it — nothing is hidden.

**Can I choose the model?**
Yes, in the apps: pick the model in the Claude and ChatGPT apps and Duo uses it. With Plus or Pro that means the strongest models of both companies, at no extra charge.

**Does it work with free ChatGPT / free Claude?**
Yes, both. ChatGPT — subject to its own free-tier limits. Claude — free Claude
runs Sonnet 5.5, the same model as the paid plan, with a daily limit; the Ask
Claude action uses the model chosen in the Claude app.

**Where does the journal live and how do I delete it?**
`Duo-journal.md` is a plain-text file in your own iCloud Drive (Files →
iCloud Drive → Shortcuts). Delete the file to erase the history, or remove
the journal action from the shortcut to stop new entries.

**Do I need paid iCloud?**
No. The core flow — question in, answer on screen and in the clipboard —
never touches iCloud. The free 5 GB on any Apple ID covers the journal for
years.

**Android or iPad?**
Duo is iPhone-first. iPad is expected to work but hasn't been verified.
On Android, use Duo inside the free Poly A1 app (Google Play): it runs the same pair automatically on free keys (verified on an emulator, not on a real phone). The older path — Tasker plus the clipboard — is built and verified on paper, but never run on a real device; the files and the guide are in [android/](../../android/). If you have an Android phone, trying either and reporting back is the most useful contribution available right now.

**Are you affiliated with OpenAI or Anthropic?**
No. See [TRADEMARKS.md](../../TRADEMARKS.md).

**One of the apps returned nothing — what now?**
See [If something's wrong](install.md#if-somethings-wrong). Two known cases: ChatGPT shows "you are logged out" while you're clearly
logged in — open the ChatGPT app, close it, and run Duo again. Claude goes
quiet on a long question because its action times out — the answer is still
being written inside the Claude app itself; open Claude to read it.

**How do I remove Duo completely?**
Delete the Duo shortcut (and any companions you installed) from the
Shortcuts app, and delete `Duo-journal.md` from Files if you kept a
journal.
