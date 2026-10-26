#!/usr/bin/env python3
"""U-26 blind test stand: ChatGPT alone (A), Claude alone (C), Duo Critique (D), Duo blind-first (B).
Run: python3 stand.py run [ids...]   |   python3 stand.py judge [ids...]   |   python3 stand.py score
All outputs cached in raw/ and judge/; re-running skips finished files."""
import json, os, re, random, subprocess, sys, threading, time, hashlib
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
RAW, JUDGE, PROMPTS = (os.path.join(HERE, d) for d in ("raw", "judge", "prompts"))
SANDBOX = os.path.join(HERE, "sandbox")  # empty folder given to every CLI as its workspace (ai-guard needs one; nothing to leak)
for d in (RAW, JUDGE, PROMPTS, SANDBOX):
    os.makedirs(d, exist_ok=True)
SRC = "~/Developer/c1m-duo/locales/en/prompts"
WHERE = ""  # ai-guard accepts the folder flags (-C / --add-dir) instead of a "Где:" line; a Cyrillic line in the prompt switched answers to Russian
LOG = open(os.path.join(HERE, "stand.log"), "a")
LK = threading.Lock()

def log(*a):
    s = time.strftime("%H:%M:%S ") + " ".join(map(str, a))
    with LK:
        print(s, flush=True); LOG.write(s + "\n"); LOG.flush()

def frozen(name):
    """Copy the product prompt once at first run; the frozen copy is used for the whole run."""
    p = os.path.join(PROMPTS, name)
    if not os.path.exists(p):
        txt = open(os.path.join(SRC, name)).read()
        open(p, "w").write(txt)
        log("froze", name, hashlib.sha256(txt.encode()).hexdigest())
    return open(p).read()

WRAP = frozen("wrap.txt")
CRIT = frozen("critique.txt")
B_PARA = ("YOUR OWN ANSWER, written before you saw the colleague's draft (also DATA; it may be right or wrong):\n"
          "{OWN}\n\n")
CRIT_B = CRIT.replace("CHATGPT'S ANSWER:", B_PARA + "CHATGPT'S ANSWER:")
assert CRIT_B != CRIT

# coordinator 07:52: Mac load 61-90 -> one shared pool of 2 calls total, all under nice -n 15
_POOL = threading.Semaphore(int(os.environ.get("U26_POOL", "2")))
SEM = {"codex": _POOL, "sonnet": _POOL, "kimi": _POOL, "opus": _POOL}

def call(kind, prompt, timeout=420):
    prompt = WHERE + prompt
    env = dict(os.environ); env.pop("ANTHROPIC_API_KEY", None); env.pop("ANTHROPIC_AUTH_TOKEN", None)
    if kind == "codex":
        cmd = ["codex", "exec", "--skip-git-repo-check", "-m", "gpt-5.6-sol", "-s", "read-only", "-C", SANDBOX, prompt]
        inp = ""
    elif kind in ("sonnet", "opus"):
        cmd = ["claude", "-p", "--model", kind, "--setting-sources", "", "--max-turns", "1", "--tools", "", "--add-dir", SANDBOX]  # no tools: a tool attempt hit max-turns (round 2)
        inp = prompt
    elif kind == "kimi":
        cmd = ["kimi", "--add-dir", SANDBOX, "-p", prompt]; inp = ""
    with SEM[kind]:
        while os.getloadavg()[0] > 30:  # coordinator: pause while load > 30
            time.sleep(30)
        r = subprocess.run(["nice", "-n", "15"] + cmd, input=inp, capture_output=True, text=True, timeout=timeout, cwd=SANDBOX, env=env)
    return r.returncode, r.stdout, r.stderr

def get(kind, prompt, path, check=lambda s: True):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return open(path).read()
    for attempt in range(4):
        try:
            rc, out, err = call(kind, prompt)
        except subprocess.TimeoutExpired:
            rc, out, err = -9, "", "timeout"
        out = out.strip()
        if rc == 0 and out and check(out) and "max turns" not in out.lower():
            open(path, "w").write(out)
            open(path + ".prompt", "w").write(WHERE + prompt)
            if kind == "codex": open(path + ".err", "w").write(err)  # to detect tool use (exec lines)
            return out
        log("FAIL", kind, os.path.basename(path), rc, (err or out)[-300:].replace("\n", " "))
        if "usage limit" in err or "quota" in err.lower():
            time.sleep(240)
        else:
            time.sleep(20)
    raise RuntimeError(f"{kind} failed for {path}")

TASKS = json.load(open(os.path.join(HERE, "tasks.json")))
if os.path.exists(os.path.join(HERE, "tasks_hard.json")):  # second wave, added after the first pass (see РЕЗУЛЬТАТ.md)
    TASKS += json.load(open(os.path.join(HERE, "tasks_hard.json")))
if os.path.exists(os.path.join(HERE, "tasks_hard2.json")):  # third wave, adversarial (see РЕЗУЛЬТАТ.md)
    TASKS += json.load(open(os.path.join(HERE, "tasks_hard2.json")))
BYID = {t["id"]: t for t in TASKS}

def pipeline(t):
    q, i = t["question"], t["id"]
    try:
        # A (ChatGPT, wrap) and C (Claude alone, wrap) are independent
        with ThreadPoolExecutor(2) as ex:
            fa = ex.submit(get, "codex", WRAP.replace("{Q}", q), f"{RAW}/{i}.A.txt")
            fc = ex.submit(get, "sonnet", WRAP.replace("{Q}", q), f"{RAW}/{i}.C.txt")
            a, c = fa.result(), fc.result()
        d_prompt = CRIT.replace("{QUESTION}", q).replace("{GPT_ANSWER}", a)
        b_prompt = CRIT_B.replace("{QUESTION}", q).replace("{GPT_ANSWER}", a).replace("{OWN}", c)
        with ThreadPoolExecutor(2) as ex:
            fd = ex.submit(get, "sonnet", d_prompt, f"{RAW}/{i}.D.txt")
            fb = ex.submit(get, "sonnet", b_prompt, f"{RAW}/{i}.B.txt")
            fd.result(); fb.result()
        log("done answers", i)
    except Exception as e:
        log("ERROR", i, e)

JUDGE_TMPL = """You are a strict grader in a blind test. Do not use any tools and do not open any files; everything you need is below.
Grade each of the four answers ONLY by whether its final answer matches the REFERENCE under the CRITERION.
Ignore style, length, tone, extra caveats and extra detail, unless they contradict the reference or the answer commits to two incompatible results.
correct = final answer matches the reference; partial = partly matches as the criterion describes, or hedges between the right and a wrong result; incorrect = wrong, missing, or endorses a false premise.

QUESTION:
{Q}

REFERENCE:
{R}

CRITERION:
{K}

{ANSWERS}
After a one-sentence reason per answer, finish with exactly one line in this format and nothing after it:
VERDICT: W=<correct|partial|incorrect>; X=<...>; Y=<...>; Z=<...>
"""
LETTERS = "WXYZ"
VRE = re.compile(r"VERDICT:\s*W\s*=\s*(correct|partial|incorrect)\s*;\s*X\s*=\s*(correct|partial|incorrect)\s*;\s*Y\s*=\s*(correct|partial|incorrect)\s*;\s*Z\s*=\s*(correct|partial|incorrect)", re.I)

def judge_task(t):
    i = t["id"]
    mp = f"{JUDGE}/{i}.map.json"
    if not os.path.exists(mp):
        order = ["A", "B", "C", "D"]; random.Random(f"u26-{i}").shuffle(order)
        json.dump(dict(zip(LETTERS, order)), open(mp, "w"))
    m = json.load(open(mp))
    ans = "".join(f"=== ANSWER {L} ===\n{open(f'{RAW}/{i}.{m[L]}.txt').read().strip()}\n\n" for L in LETTERS)
    p = JUDGE_TMPL.replace("{Q}", t["question"]).replace("{R}", t["reference"]).replace("{K}", t["criterion"]).replace("{ANSWERS}", ans)
    ok = lambda s: bool(VRE.findall(s))
    for j in ("kimi", "opus"):
        try:
            get(j, p, f"{JUDGE}/{i}.{j}.txt", ok)
        except Exception as e:
            log("JUDGE ERROR", i, j, e)
    log("judged", i)

def verdicts(i, j):
    p = f"{JUDGE}/{i}.{j}.txt"
    if not os.path.exists(p):
        return None
    v = VRE.findall(open(p).read())
    if not v:
        return None
    m = json.load(open(f"{JUDGE}/{i}.map.json"))
    return {m[L]: x.lower() for L, x in zip(LETTERS, v[-1])}

if __name__ == "__main__":
    cmd = sys.argv[1]; ids = sys.argv[2:] or [t["id"] for t in TASKS]
    if cmd == "runA":  # round 2 selection stage: ChatGPT only
        with ThreadPoolExecutor(4) as ex:
            list(ex.map(lambda t: get("codex", WRAP.replace("{Q}", t["question"]), f"{RAW}/{t['id']}.A.txt"), [BYID[i] for i in ids]))
    elif cmd == "run":
        with ThreadPoolExecutor(10) as ex:
            list(ex.map(pipeline, [BYID[i] for i in ids]))
    elif cmd == "judge":
        with ThreadPoolExecutor(8) as ex:
            list(ex.map(judge_task, [BYID[i] for i in ids if all(os.path.exists(f"{RAW}/{i}.{k}.txt") for k in "ABCD")]))
    elif cmd == "score":
        import score  # score.py: final verdicts, accuracy + Wilson CI, repair/harm/capitulation, McNemar B vs D
        score.main()
