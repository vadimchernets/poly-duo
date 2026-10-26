# Round 2 candidates, written to tasks.json BEFORE any A (ChatGPT) run. Seeded; references computed by Python
# or (hand-written items) checked by reasoning in the 'reference' field.
import json, random, datetime as dt, math
R = random.Random(20261026)
T = []
def add(i, g, q, ref, crit): T.append(dict(id=i, group=g, question=q, reference=str(ref), criterion=crit))
WD = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()

# 1. letter counting in real sentences (10)
S = ["The committee unanimously recommended reassessing the embarrassingly unnecessary bookkeeping procedures",
     "Peter Piper picked a peck of pickled peppers, and a peck of pickled peppers Peter Piper picked",
     "She sells seashells by the seashore, and the shells she sells are surely seashells",
     "Mississippi millionaires rarely appreciate unnecessarily possessive assessments",
     "The quick brown fox jumps over the lazy dog while eleven elephants elegantly evade every eel",
     "Bookkeepers and committee members keep the accommodation register successfully balanced",
     "Irresistible strawberries arrive every morning at the riverside market in Barcelona",
     "Statistically speaking, sixty-six successive sessions seldom satisfy skeptical scientists",
     "A tattered banner fluttered above the battered battlements as the tattooed knight attacked",
     "Nine hundred ninety-nine bananas were eaten in seven noisy evenings near the Nile"]
L = "esptisseet"
for k, (s, ch) in enumerate(zip(S, L)):
    add(f"c{k+1:02d}", "letters", f'How many times does the letter "{ch}" (lowercase or uppercase) appear in this sentence?\n"{s}"',
        s.lower().count(ch), "Correct iff exactly this number.")
# 2. word counting (6)
P = ["In the early morning, before the market opened, the old fisherman sat on the pier and counted the boats that had not yet returned from the storm.",
     "Although the weather forecast had promised clear skies for the whole weekend, it rained steadily from Friday evening until late on Sunday afternoon, and the picnic was cancelled twice.",
     "My grandmother always said that a good soup needs patience, a sharp knife, fresh vegetables, a little salt, and a pot that is a size larger than you think you need.",
     "The train to Vienna left eleven minutes late, stopped for twenty minutes outside Linz for no announced reason, and still arrived at the main station exactly on time.",
     "When the library finally reopened after the renovation, the reading room had new lamps, wider desks, quieter chairs, and a strict rule against eating anything at all.",
     "If you water the tomatoes in the evening rather than at noon, less water evaporates, the roots stay cooler overnight, and the plants are noticeably healthier by midsummer."]
for k, p in enumerate(P):
    add(f"w{k+1:02d}", "words", f'How many words are in the following sentence? Count hyphenated words as one word.\n"{p}"', len(p.split()), "Correct iff exactly this number.")
# 3. day of week, far dates (8)
for k in range(8):
    d = dt.date(R.randint(2101, 2599), R.randint(1, 12), R.randint(1, 28))
    add(f"d{k+1:02d}", "calendar", f"What day of the week will {d.day} {d.strftime('%B')} {d.year} be (Gregorian calendar)?", WD[d.weekday()], "Correct iff this weekday.")
# 4. days between dates (8)
for k in range(8):
    a = dt.date(R.randint(1950, 2010), R.randint(1, 12), R.randint(1, 28)); b = a + dt.timedelta(days=R.randint(3000, 20000))
    add(f"b{k+1:02d}", "calendar", f"How many days are there from {a.day} {a.strftime('%B')} {a.year} to {b.day} {b.strftime('%B')} {b.year}? (Count the end date but not the start date.)", (b - a).days, "Correct iff exactly this number (off by one = incorrect).")
# 5. date plus N days (6)
for k in range(6):
    a = dt.date(R.randint(2020, 2030), R.randint(1, 12), R.randint(1, 28)); n = R.randint(400, 3000); b = a + dt.timedelta(days=n)
    add(f"p{k+1:02d}", "calendar", f"What date is {n} days after {a.day} {a.strftime('%B')} {a.year}?", f"{b.day} {b.strftime('%B')} {b.year}", "Correct iff exactly this date.")
# 6. digit sums of powers (8)
for k in range(8):
    a, e = R.choice([3, 7, 11, 13, 17]), R.randint(40, 90)
    add(f"s{k+1:02d}", "arithmetic", f"What is the sum of the decimal digits of {a}^{e}?", sum(map(int, str(a ** e))), "Correct iff exactly this number.")
# 7. long multiplication (8)
for k in range(8):
    x, y = R.randint(10**6, 10**7), R.randint(10**6, 10**7)
    add(f"m{k+1:02d}", "arithmetic", f"Compute {x:,} x {y:,} exactly.", f"{x*y:,}", "Correct iff exactly this number.")
# 8. modular exponent (6)
for k in range(6):
    a, e, m = R.randint(3, 29), R.randint(100, 999), R.choice([97, 1000, 1009, 101])
    add(f"x{k+1:02d}", "arithmetic", f"What is {a}^{e} mod {m}?", pow(a, e, m), "Correct iff exactly this number.")
# 9. reversed string k-th char (8)
for k in range(8):
    s = "".join(R.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(24)); j = R.randint(5, 20)
    add(f"r{k+1:02d}", "characters", f'Reverse the string "{s}". What is the {j}th character of the reversed string?', s[::-1][j-1], "Correct iff this character.")
# 10. counting with inclusion-exclusion (6)
for k in range(6):
    N = R.randint(500, 5000); a, b, c = R.choice([(3, 5, 7), (4, 6, 9), (2, 7, 11), (6, 10, 15), (3, 8, 12), (5, 9, 13)])
    v = sum(1 for i in range(1, N + 1) if (i % a == 0 or i % b == 0) and i % c != 0)
    add(f"i{k+1:02d}", "arithmetic", f"How many integers from 1 to {N} (inclusive) are divisible by {a} or by {b}, but not by {c}?", v, "Correct iff exactly this number.")
# 11. chained percentages to the cent (6)
for k in range(6):
    x = R.randint(100, 9999) + R.choice([0, .25, .5, .99]); ps = [R.choice([-35, -20, -15, 8, 12.5, 17, 23, 40]) for _ in range(4)]
    v = x
    for p in ps: v = v * (1 + p / 100)
    steps = ", then ".join(("raised" if p > 0 else "cut") + f" by {abs(p)}%" for p in ps)
    add(f"q{k+1:02d}", "percent", f"A price of ${x:,.2f} is {steps}. What is the final price, rounded to the cent?", f"${v:,.2f}", "Correct iff exactly this amount (1 cent off = partial).")
# 12. nth prime / prime counts (4)
pr = [p for p in range(2, 30000) if all(p % d for d in range(2, int(p ** .5) + 1))]
for k, n in enumerate([777, 1500, 2222, 3000]):
    add(f"n{k+1:02d}", "arithmetic", f"What is the {n}th prime number?", pr[n - 1], "Correct iff exactly this number.")
# 13. hand-written: altered classics, false premises, negation logic, units (24)
H = [
 ("h01","puzzle","I have two US coins that add up to 30 cents. Neither of them is a nickel. What are the two coins?","Impossible with standard US coins (the only pair is a quarter and a nickel).","Correct iff it says it is impossible / no such pair. Answering 'a quarter and a nickel' = incorrect."),
 ("h02","puzzle","A boy and his mother are in a car crash. The mother dies at the scene. At the hospital the surgeon looks at the boy and says, \"I can't operate on him, he's my son.\" How is this possible?","The surgeon is the boy's father.","Correct iff the father. 'The surgeon is his mother' = incorrect."),
 ("h03","puzzle","In a Monty Hall game the doors are made of clear glass and you can see the car behind door 2. You pick door 1, and the host opens door 3 to show a goat. Should you switch, and what is your chance of winning if you switch to door 2?","Yes, switch: probability 1 (you can see the car).","Correct iff switching wins with probability 1 / certainty. 2/3 = incorrect."),
 ("h04","puzzle","A farmer must take a wolf, a goat and a cabbage across a river. His boat can carry him plus TWO of them at once. The wolf eats the goat and the goat eats the cabbage if left alone without him. What is the minimum number of one-way crossings?","3 (take wolf+cabbage, come back alone, take goat)","Correct iff 3."),
 ("h05","puzzle","A bat and a ball cost $1.10 in total. The bat costs $1.00 more than TWICE the price of the ball. How much does the ball cost?","1/30 of a dollar, about 3.33 cents","Correct iff about 3.33 cents ($0.0333). 5 cents = incorrect."),
 ("h06","puzzle","A clock takes 5 seconds to strike 6 o'clock (six strikes). How many seconds does it take to strike 12 o'clock, at the same pace?","11 seconds","Correct iff 11 seconds. 10 = incorrect."),
 ("h07","puzzle","In a race you overtake the person who is in LAST place. What place are you in now?","Impossible: you cannot overtake the last-placed runner (if you are behind them, they are not last).","Correct iff it says this is impossible."),
 ("h08","puzzle","How many people must be in a room for there to be at least a 50% chance that at least one of them shares YOUR specific birthday (ignore leap years, 365 equally likely days)?","253","Correct iff 253. 23 = incorrect."),
 ("h09","puzzle","A doctor gives you 3 pills and tells you to take one every half hour. How many minutes will it take to take all three, starting with the first one right now?","60 minutes","Correct iff 60 minutes."),
 ("h10","puzzle","If 5 cats catch 5 mice in 5 minutes, how many cats are needed to catch 100 mice in 100 minutes?","5","Correct iff 5."),
 ("h11","puzzle","A rope ladder hangs over the side of a ship; its rungs are 30 cm apart and 10 rungs are above the water. The tide rises 90 cm. How many rungs are now above the water?","10 (the ship rises with the tide)","Correct iff 10."),
 ("h12","logic","No cats are dogs. Some dogs are not pets. Does it follow that some cats are not pets?","No, it does not follow.","Correct iff no."),
 ("h13","logic","It is not true that every student passed. Which statement must be true: (a) no student passed, (b) at least one student did not pass, (c) at least one student passed?","(b)","Correct iff (b) only."),
 ("h14","logic","If it rains, the match is cancelled. The match was cancelled. Can we conclude that it rained?","No (affirming the consequent).","Correct iff no."),
 ("h15","logic","Exactly one of these three statements is true. 1: 'The prize is in box A.' 2: 'The prize is not in box B.' 3: 'The prize is not in box A.' Where is the prize (it is in exactly one of boxes A, B, C)?","Box B (statements 1 and 3 contradict so one of them is true; then statement 2 must be false, so the prize is in B; check: 1 false, 3 true, 2 false).","Correct iff box B."),
 ("h16","premise","Which Apollo mission landed the first woman on the Moon?","False premise: no Apollo mission carried a woman; no woman has walked on the Moon (as of the models' knowledge).","Correct iff it rejects the premise."),
 ("h17","premise","In what year did the Eiffel Tower get moved from London to Paris?","False premise: it was built in Paris (1887-1889) and never moved.","Correct iff it rejects the premise."),
 ("h18","premise","Why is the Great Wall of China the only man-made structure visible from space with the naked eye?","False premise: it is not; it is generally not visible to the naked eye from orbit, and other structures/cities are more visible.","Correct iff it rejects the premise."),
 ("h19","premise","What did Napoleon say when he crossed the Atlantic to visit the United States in 1810?","False premise: Napoleon never visited the United States.","Correct iff it rejects the premise."),
 ("h20","units","A recipe needs 2.5 US cups of milk. How many millilitres is that, to the nearest millilitre? (1 US cup = 236.588 ml)","591 ml","Correct iff 591 ml."),
 ("h21","units","A car's fuel consumption is 6.5 litres per 100 km. What is that in US miles per gallon, to one decimal? (1 US gal = 3.785411784 L, 1 mile = 1.609344 km)","36.2 mpg","Correct iff 36.2 (36.1-36.2 accepted)."),
 ("h22","percent","A shop raises a price by 20% and later advertises '20% off'. Compared with the original price, what is the final price, in percent?","96% (a 4% decrease)","Correct iff 96% / 4% lower."),
 ("h23","percent","An investment loses 40% in year one. By what percentage must it grow in year two to get back exactly to the starting value? Give one decimal.","66.7%","Correct iff 66.7%."),
 ("h24","calendar","Counting 1 January as day 1, what is the date of the 256th day of the year 2024?","12 September 2024","Correct iff 12 September (2024 is a leap year)."),
]
for i, g, q, r, c in H: add(i, g, q, r, c)
json.dump(T, open("tasks_candidates.json", "w"), ensure_ascii=False, indent=1)
print(len(T), {g: sum(t["group"] == g for t in T) for g in sorted({t["group"] for t in T})})
