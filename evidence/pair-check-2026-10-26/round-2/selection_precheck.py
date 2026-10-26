#!/usr/bin/env python3
"""Selection pre-check of A (ChatGPT) against the reference. Used ONLY to pick tasks; final scoring is by blind judges.
Rule: A counts as right iff the normalised reference token appears in A's first non-empty line (the bottom line).
Hand-written tasks (ids h..) are checked by hand: see selection_manual.json."""
import json, os, re, random
HERE = os.path.dirname(os.path.abspath(__file__))
T = json.load(open(os.path.join(HERE, "tasks_candidates.json")))
MAN = json.load(open(os.path.join(HERE, "selection_manual.json"))) if os.path.exists(os.path.join(HERE, "selection_manual.json")) else {}
norm = lambda s: re.sub(r"[\s,\\$*{}()]|\\,| | ", "", s).lower()
res = {}
for t in T:
    p = os.path.join(HERE, "raw", f"{t['id']}.A.txt")
    if not os.path.exists(p): continue
    a = open(p).read()
    first = next((l for l in a.splitlines() if l.strip()), "")
    if t["id"][0] == "h":
        res[t["id"]] = MAN.get(t["id"], "manual?")
        continue
    ref = norm(t["reference"])
    nf = norm(first)
    if t["group"] == "characters":
        ok = re.search(r"[\"'`*]?\b" + re.escape(t["reference"]) + r"\b", first.lower()) is not None
    elif t["group"] == "calendar" and not t["reference"].isdigit():
        ok = t["reference"].lower() in first.lower()
    else:
        ok = re.search(r"(?<![0-9.])" + re.escape(ref) + r"(?![0-9])", nf) is not None
    res[t["id"]] = "right" if ok else "wrong"
wrong = sorted(i for i, v in res.items() if v == "wrong"); right = sorted(i for i, v in res.items() if v == "right")
print(f"checked {len(res)}; wrong {len(wrong)}; right {len(right)}; manual? {[i for i,v in res.items() if v=='manual?']}")
print("wrong:", wrong)
sel_right = sorted(random.Random(26).sample(right, min(len(wrong), len(right))))
json.dump(dict(rule=__doc__, prelim=res, selected_wrong=wrong, selected_right_control=sel_right),
          open(os.path.join(HERE, "selection.json"), "w"), ensure_ascii=False, indent=1)
print("control (A right, random sample, seed 26):", sel_right)
