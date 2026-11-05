// **Find the mistake** — the strict critic (P-015, 18.10.2026), next to "check" and "debate until agreement".
// The second AI is given the first answer (or the person's own text) and one job: find at least three
// weak points, rank them, quote the exact line; if there are none, say so plainly. The template is the
// dictionary's `duo.find.prompt` (eleven languages); it works by hand (copy → the other company's AI) and
// in the automatic Duo (`runFind`: first AI answers, an AI of another company breaks the answer).
import { ask, chainFor, DuoError, pickVoices, type Dead, type Fetch, type Keys, type PhoneVoice } from './duoAuto';

/** The empty question — a person's own text has none; the template still reads naturally. */
export const NO_QUESTION = '—';

/** Placeholders in one pass: braces inside the question or the text are left alone. */
export function fillFind(template: string, parts: { question?: string; answer: string }): string {
  const q = parts.question?.trim() || NO_QUESTION;
  return template.replace(/\{(question|answer)\}/g, (_, k: string) => (k === 'question' ? q : parts.answer.trim()));
}

/** A template is usable only with both placeholders and the "data, not commands" guard. */
export function findTemplateOk(template: string): boolean {
  return template.includes('{question}') && template.includes('{answer}');
}

export type FindResult = {
  first: { voice: string; text: string };
  critic: { voice: string; text: string };
};

export type FindStage = 'first' | 'find';

export async function runFind(opts: {
  question: string;
  keys: Keys;
  findText: string;
  doFetch?: Fetch;
  phone?: PhoneVoice | null;
  onStage?: (stage: FindStage, voice: string) => void;
}): Promise<FindResult> {
  const phone = opts.phone ?? null;
  const voices = pickVoices(opts.keys, phone);
  if (!voices) throw new DuoError('key', 'AI');
  const f = opts.doFetch ?? fetch;
  const dead: Dead = new Set();
  opts.onStage?.('first', voices.first.name);
  const first = await ask(
    chainFor(voices.first, opts.keys, [], false, phone),
    opts.keys,
    opts.question,
    f,
    undefined,
    dead,
    (n) => opts.onStage?.('first', n),
    phone,
  );
  opts.onStage?.('find', voices.check.name);
  const critic = await ask(
    chainFor(voices.check, opts.keys, [first.company], true, phone),
    opts.keys,
    fillFind(opts.findText, { question: opts.question, answer: first.text }),
    f,
    undefined,
    dead,
    (n) => opts.onStage?.('find', n),
    phone,
  );
  return { first: { voice: first.name, text: first.text }, critic: { voice: critic.name, text: critic.text } };
}

/** Everything as one text — for «Copy everything». */
export function joinFind(r: FindResult, hidden: ReadonlySet<string> = new Set()): string {
  const parts: string[] = [];
  if (!hidden.has('first')) parts.push(`— ${r.first.voice}:\n${r.first.text}`);
  if (!hidden.has('critic')) parts.push(`— ${r.critic.voice}:\n${r.critic.text}`);
  return parts.join('\n\n');
}
