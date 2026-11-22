#!/usr/bin/env python3
"""Derive error correlation by class from archived judgments; no model calls.

Run with python3 -I evidence/pair-check-2026-10-26/pair_card.py.
Only stdout is written. Existing inputs are never changed.
"""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HASHES = {}


def read(path):
    data = path.read_bytes()
    HASHES[str(path.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
    return data.decode("utf-8")


def load(path):
    return json.loads(read(path))


def wilson(k, n):
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [max(0, c - h), min(1, c + h)]


def summarize(ids, tasks, final):
    rows = []
    for group in ["ALL"] + sorted({tasks[i]["group"] for i in ids}):
        selected = sorted(i for i in ids if group == "ALL" or tasks[i]["group"] == group)
        cells = {"00": [], "01": [], "10": [], "11": []}
        for i in selected:
            # First digit: A error. Second digit: blind C error.
            a, c = (int(final[i][v] != "correct") for v in "AC")
            cells[f"{a}{c}"].append(i)
        n00, n01, n10, n11 = (len(cells[k]) for k in ("00", "01", "10", "11"))
        n = len(selected)
        denominator = math.sqrt((n10 + n11) * (n00 + n01) * (n01 + n11) * (n00 + n10))
        rows.append(dict(group=group, n=n, cells=cells,
                         phi=(n11 * n00 - n10 * n01) / denominator if denominator else None,
                         A_errors=n10 + n11, C_errors=n01 + n11,
                         A_error_wilson95=wilson(n10 + n11, n),
                         C_error_wilson95=wilson(n01 + n11, n)))
    return rows


def main():
    result = {"measurement_date": "2026-10-26", "derived_on": "2026-11-22", "samples": {}}
    for round_name, expected in (("round-1", 67), ("round-2", 46)):
        base = ROOT / round_name
        tasks = load(base / "tasks.json")
        if round_name == "round-1":
            for name in ("tasks_hard.json", "tasks_hard2.json"):
                tasks += load(base / name)
        by_id = {t["id"]: t for t in tasks}
        assert len(by_id) == len(tasks), "Duplicate task ids"
        final = load(base / "judge/final.json")
        assert len(final) == expected and set(final) <= set(by_id)
        assert all(set(row) == set("ABCD") and
                   set(row.values()) <= {"correct", "partial", "incorrect"}
                   for row in final.values())
        result["samples"][round_name] = summarize(set(final), by_id, final)
        if round_name == "round-2":
            artifacts = set()
            for i in final:
                for v in "CDB":
                    raw = base / "raw" / f"{i}.{v}.txt"
                    if not raw.exists():
                        raw = base / "raw" / f"{i}.{v}.ru.txt"
                    if "<invoke" in read(raw):
                        artifacts.add(i)
            assert len(artifacts) == 8
            result["excluded_tool_artifacts"] = sorted(artifacts)
            result["samples"]["round-2-no-tool-artifacts"] = summarize(set(final) - artifacts, by_id, final)
            candidates = load(base / "tasks_candidates.json")
            assert len(candidates) == 108 and candidates == tasks
            selection = load(base / "selection.json")
            prelim = selection["prelim"]
            assert set(prelim) == set(by_id)
            usable = {i for i, v in prelim.items() if v in ("right", "wrong")}
            assert len(usable) == 107
            assert {i for i in usable if prelim[i] == "wrong"} == set(selection["selected_wrong"])
            assert set(final) == set(selection["selected_wrong"] + selection["selected_right_control"])
            result["candidate_A_precheck"] = [
                dict(group=g, n=sum(by_id[i]["group"] == g for i in usable),
                     errors=sum(by_id[i]["group"] == g and prelim[i] == "wrong" for i in usable))
                for g in sorted({by_id[i]["group"] for i in usable})
            ]
            result["candidate_exclusions"] = {i: v for i, v in prelim.items() if i not in usable}
    result["input_sha256"] = HASHES
    print(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False))


if __name__ == "__main__":
    main()
