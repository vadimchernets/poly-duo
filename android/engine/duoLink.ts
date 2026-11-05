// The Duo door from outside (test "as a person", 27.10.2026, P14): the Duo landing's Android button must open Duo
// itself, not home "What shall we sort out?". Three ways in, one screen (`/job/duo`, `src/screens/DuoAndroid.tsx`):
// - `polya1://duo` — the app's own scheme;
// - `https://polyhelper.ai/get/?to=duo` — an installed app gets it as a verified app link (`/get` is already in
//   app.json `intentFilters`); without the app the site's /get page sends Play `to=duo` as the install referrer;
// - the Play install referrer `to=duo` — read once on the first launch (`parseFirstOpen`, src/installSetup.ts).
// No new dependency and nothing goes out: the referrer comes from the Play Store app on the same phone.

/** The Duo screen: on Android the free-key automatic Duo first, the manual one second. */
export const DUO_PATH = '/job/duo';

/** `null` — not a Duo link (the other handlers go on). Never throws. */
export function duoPath(input: string): string | null {
  if (typeof input !== 'string') return null;
  // `polya1://duo`, `polya1:///duo/`, `/duo`, `duo?x=1` — the phone hands over the full URL or just the path.
  if (/^(?:polya1:\/{2,3}|\/)?duo\/?(?:[?#].*)?$/iu.test(input)) return DUO_PATH;
  let u: URL;
  try {
    u = new URL(input, 'https://polyhelper.ai');
  } catch {
    return null;
  }
  if (u.protocol !== 'https:' && u.protocol !== 'http:') return null;
  const host = u.hostname.toLowerCase();
  if (host !== 'polyhelper.ai' && host !== 'www.polyhelper.ai') return null;
  if (!/^\/get(\/|$)/u.test(u.pathname)) return null;
  return new URLSearchParams(u.search).get('to') === 'duo' ? DUO_PATH : null;
}
