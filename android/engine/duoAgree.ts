// "Both agree / They differ (who is likely right)" (P-013, 18.10.2026): the second AI is asked to end its
// check with two labelled lines (`duo.a.check`, `duo.a.trio_text`); the automatic Duo reads them and shows
// them as a block of their own above the answers. The labels are the words of the person's language
// (the instruction quotes them), and this parser knows all eleven, so it works even when the model
// answers in another language than the screen.
//
// Under the block goes one small honest line (P-014, `duo.a.notproof`): agreement is a strong sign, not proof.

export type Agreement = {
  /** What they agree on. */
  agree: string;
  /** Where they differ, and who is more likely right. */
  differ: string;
  /** `all` — the label said "all" (three AIs). */
  all: boolean;
};

type Labels = { agree: string; all: string; differ: string };

/** The three labels per language: the same words the dictionaries put into the instruction. */
export const AGREE_LABELS: Record<string, Labels> = {
  en: { agree: 'Both agree', all: 'All agree', differ: 'They differ' },
  de: { agree: 'Beide stimmen überein', all: 'Alle stimmen überein', differ: 'Sie unterscheiden sich' },
  es: { agree: 'Ambas coinciden', all: 'Todas coinciden', differ: 'Difieren' },
  fr: { agree: 'Les deux sont d’accord', all: 'Toutes sont d’accord', differ: 'Elles divergent' },
  hi: { agree: 'दोनों सहमत हैं', all: 'सभी सहमत हैं', differ: 'इनमें अंतर है' },
  ja: { agree: '両者の一致点', all: '全員の一致点', differ: '相違点' },
  ko: { agree: '둘 다 동의', all: '모두 동의', differ: '차이점' },
  pt: { agree: 'Ambas concordam', all: 'Todas concordam', differ: 'Elas divergem' },
  ru: { agree: '\u041e\u0431\u0435 \u0441\u043e\u0433\u043b\u0430\u0441\u043d\u044b', all: '\u0412\u0441\u0435 \u0441\u043e\u0433\u043b\u0430\u0441\u043d\u044b', differ: '\u0420\u0430\u0441\u0445\u043e\u0434\u044f\u0442\u0441\u044f' },
  uk: { agree: '\u041e\u0431\u0438\u0434\u0432\u0456 \u0437\u0433\u043e\u0434\u043d\u0456', all: '\u0423\u0441\u0456 \u0437\u0433\u043e\u0434\u043d\u0456', differ: '\u0420\u043e\u0437\u0445\u043e\u0434\u044f\u0442\u044c\u0441\u044f' },
  zh: { agree: '双方一致', all: '全部一致', differ: '分歧' },
};

const norm = (s: string) => s.replace(/['’`]/g, '’').toLowerCase();

/** A line's label, if it starts with one: `**Both agree:** …`, `- They differ: …`, `Both agree：…`. */
function labelOf(line: string): { kind: 'agree' | 'all' | 'differ'; rest: string } | null {
  const lead = /^[\s>#•\-–—\d.)]*[*_]*/.exec(line)?.[0].length ?? 0;
  const body = norm(line.slice(lead));
  for (const L of Object.values(AGREE_LABELS)) {
    for (const kind of ['agree', 'all', 'differ'] as const) {
      const w = norm(L[kind]);
      if (!body.startsWith(w)) continue;
      const m = /^[\s*_]*[:：]/.exec(body.slice(w.length));
      if (!m) continue;
      const rest = line.slice(lead + w.length + m[0].length).replace(/^[\s*_]+/, '').replace(/[*_]+\s*$/, '');
      return { kind, rest: rest.trim() };
    }
  }
  return null;
}

/**
 * Reads the two lines out of an AI's text. A continuation (the next lines up to a blank line or the next
 * label) belongs to the line before it. Both lines must be there — one alone is not shown.
 */
export function parseAgreement(text: string): Agreement | null {
  let agree = '';
  let differ = '';
  let all = false;
  let at: 'agree' | 'differ' | null = null;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trimEnd();
    const lab = labelOf(line);
    if (lab) {
      if (lab.kind === 'differ') {
        at = 'differ';
        differ = lab.rest;
      } else {
        at = 'agree';
        agree = lab.rest;
        all = lab.kind === 'all';
      }
      continue;
    }
    if (!line.trim()) {
      at = null;
      continue;
    }
    // Another section starts (the confidence line, the corrections, a [check] list): the line is over.
    if (/^\W*(confidence|corrections|\u0443\u0432\u0435\u0440\u0435\u043d\u043d|\u043f\u043e\u043f\u0440\u0430\u0432\u043a|\u0432\u0438\u043f\u0440\u0430\u0432\u043b\u0435\u043d|confianza|confiança|confiance|konfidenz)/i.test(line)) {
      at = null;
      continue;
    }
    if (at === 'agree') agree = `${agree} ${line.trim()}`.trim();
    else if (at === 'differ') differ = `${differ} ${line.trim()}`.trim();
  }
  if (!agree || !differ) return null;
  return { agree, differ, all };
}

/** The labels of one language as the dictionaries quote them (`en` when the language is unknown). */
export function labelsFor(lang: string): Labels {
  return AGREE_LABELS[lang] ?? AGREE_LABELS.en;
}
