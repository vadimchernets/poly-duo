#!/usr/bin/env python3
"""Scoring for U-26. Final verdict = Kimi and Opus agree; otherwise judge/adjudication.json (hand check by reference).
Strict: only 'correct' counts as right (partial = not right). Lenient column counts partial as right."""
import json, os, math, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stand import TASKS, verdicts, RAW, JUDGE

ADJ_P = os.path.join(JUDGE, "adjudication.json")
ADJ = json.load(open(ADJ_P)) if os.path.exists(ADJ_P) else {}
if os.environ.get("U26_OVERRIDES", "1") == "0":  # judges only: drop the agent's rubric-consistency overrides
    ADJ = {k: v for k, v in ADJ.items() if v.get("type") != "override"}
V = "ABCD"

def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"),) * 2
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0, c - h), min(1, c + h)

def mcnemar_exact(b, c):
    """two-sided exact binomial McNemar on discordant pairs b, c"""
    n = b + c
    if n == 0: return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, j) for j in range(k + 1)) / 2 ** n)

def main():
    global final
    final, disagree, missing = {}, [], []
    for t in TASKS:
        i = t["id"]; k, o = verdicts(i, "kimi"), verdicts(i, "opus")
        if not k and not o: missing.append(i); continue
        final[i] = {}
        for v in V:
            a, b = (k or {}).get(v), (o or {}).get(v)
            key = f"{i}.{v}"
            if key in ADJ: final[i][v] = ADJ[key]["verdict"]
            elif a and b and a == b: final[i][v] = a
            elif a and b: disagree.append((key, a, b)); final[i][v] = None
            else: final[i][v] = a or b  # only one judge available
    ids = [i for i in final if all(final[i][v] for v in V)]
    FAKE = sorted(i for i in ids if any("<invoke" in open(f"{RAW}/{i}.{v}.txt").read() for v in "CDB"))
    if os.environ.get("U26_EXCLUDE_TOOLFAKE") == "1":  # sensitivity: drop tasks where Claude (tools off) printed a fake tool call instead of an answer
        ids = [i for i in ids if i not in FAKE]

    def acc(v, sel, lenient=False):
        ok = sum(final[i][v] == "correct" or (lenient and final[i][v] == "partial") for i in sel)
        return ok, len(sel)

    def pct(k, n):
        if n == 0: return "—"
        lo, hi = wilson(k, n); return f"{k}/{n} = {100*k/n:.0f}% [{100*lo:.0f}–{100*hi:.0f}]"

    R = lambda i, v: final[i][v] == "correct"
    out = []
    out.append(f"tasks with a fake tool call instead of an answer in C/D/B: {FAKE}" + (" (EXCLUDED)" if os.environ.get("U26_EXCLUDE_TOOLFAKE") == "1" else " (kept, graded as given)"))
    out.append(f"tasks scored: {len(ids)}; judge disagreements unresolved: {len(disagree)}; missing: {missing}")
    out.append(f"judge raw agreement (Kimi vs Opus, per answer): "
               f"{sum(1 for t in TASKS for v in V if verdicts(t['id'],'kimi') and verdicts(t['id'],'opus') and verdicts(t['id'],'kimi')[v]==verdicts(t['id'],'opus')[v])}"
               f"/{sum(4 for t in TASKS if verdicts(t['id'],'kimi') and verdicts(t['id'],'opus'))}")
    BYG = {t["id"]: t["group"] for t in TASKS}
    SEL = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "selection.json")))
    SW, SR = set(SEL["selected_wrong"]), set(SEL["selected_right_control"])
    out.append("\n| variant | all selected | selected as A-wrong (pre-check) | control: A-right (pre-check) | lenient (partial=ok) |")
    out.append("|---|---|---|---|---|")
    names = {"A": "A ChatGPT alone", "C": "C Claude alone", "D": "D Duo Critique", "B": "B Duo blind-first"}
    for v in "ACDB":
        row = [pct(*acc(v, ids))] + [pct(*acc(v, [i for i in ids if i in grp])) for grp in (SW, SR)] + [pct(*acc(v, ids, True))]
        out.append(f"| {names[v]} | " + " | ".join(row) + " |")
    for v in "DB":
        fixed = [i for i in ids if not R(i, "A") and R(i, v)]
        broke = [i for i in ids if R(i, "A") and not R(i, v)]
        kept = [i for i in ids if not R(i, "A") and not R(i, v)]
        anch_base = [i for i in ids if not R(i, "A") and R(i, "C")]
        anch = [i for i in anch_base if not R(i, v)]
        out.append(f"\n{names[v]} vs A: fixed {len(fixed)} {fixed}; broke {len(broke)} {broke}; kept A's error {len(kept)} {kept}; "
                   f"A wrong & blind C right -> {v} still wrong (anchoring): {len(anch)}/{len(anch_base)} {anch}")
        out.append(f"  A-right tasks broken by {v}: {pct(len(broke), sum(R(i,'A') for i in ids))}; "
                   f"A-wrong tasks fixed by {v}: " + (pct(len(fixed), sum(not R(i,'A') for i in ids)) if any(not R(i,'A') for i in ids) else "n/a"))
    split = [i for i in ids if R(i, "A") != R(i, "C")]
    out.append(f"\nTASKS THAT SPLIT THE MODELS (A right != C right): {len(split)} of {len(ids)} {split}"
               f" (by task type: " + ", ".join(f"{g} {sum(1 for i in split if BYG[i]==g)}" for g in sorted(set(BYG.values()))) + ")")
    for v in "DB":
        rep = [i for i in split if not R(i, "A") and R(i, v)]
        harm = [i for i in split if R(i, "A") and not R(i, v)]
        capb = [i for i in split if R(i, "C") and not R(i, "A")]
        cap = [i for i in capb if not R(i, v)]
        nA_wrong = sum(not R(i, "A") for i in split); nA_right = sum(R(i, "A") for i in split)
        out.append(f"on A!=C, {names[v]}: repair {len(rep)}/{nA_wrong} {rep}; harm {len(harm)}/{nA_right} {harm}; "
                   f"capitulation (C right, A wrong, {v} wrong) {len(cap)}/{len(capb)} {cap}")
    b_only = [i for i in ids if R(i, "B") and not R(i, "D")]
    d_only = [i for i in ids if R(i, "D") and not R(i, "B")]
    out.append(f"\nMcNemar exact, B vs D (all scored tasks): B right & D wrong {len(b_only)} {b_only}; D right & B wrong {len(d_only)} {d_only}; "
               f"two-sided p = {mcnemar_exact(len(b_only), len(d_only)):.3f}")
    b_only = [i for i in ids if R(i, "D") and not R(i, "A")]
    d_only = [i for i in ids if R(i, "A") and not R(i, "D")]
    out.append(f"McNemar exact, D vs A: D right & A wrong {len(b_only)}; A right & D wrong {len(d_only)}; p = {mcnemar_exact(len(b_only), len(d_only)):.3f}")
    b_only = [i for i in ids if R(i, "B") and not R(i, "A")]
    d_only = [i for i in ids if R(i, "A") and not R(i, "B")]
    out.append(f"McNemar exact, B vs A: B right & A wrong {len(b_only)}; A right & B wrong {len(d_only)}; p = {mcnemar_exact(len(b_only), len(d_only)):.3f}")
    out.append("\nper task (strict): " + " ".join(f"{i}:{''.join(v if R(i,v) else ('~' if final[i][v]=='partial' else '.') for v in 'ACDB')}" for i in ids))
    def L(v): return [len(open(f"{RAW}/{i}.{v}.txt").read().split()) for i in ids]
    out.append("\nlength, words (median / mean): " + "; ".join(f"{v} {statistics.median(L(v)):.0f} / {statistics.mean(L(v)):.0f}" for v in "ACDB"))
    def ru(v): return sum(1 for i in ids if sum('а' <= ch <= 'я' for ch in open(f"{RAW}/{i}.{v}.txt").read().lower()) > 30)
    out.append("answers written in Russian although the question was English: " + ", ".join(f"{v} {ru(v)}" for v in "ACDB"))
    if disagree:
        out.append("\nDISAGREEMENTS (key, kimi, opus): " + "; ".join(map(str, disagree)))
    print("\n".join(out))
    json.dump(final, open(os.path.join(JUDGE, "final.json" if os.environ.get("U26_OVERRIDES", "1") != "0" else "final_judges_only.json"), "w"), indent=1)

if __name__ == '__main__':
    main()
