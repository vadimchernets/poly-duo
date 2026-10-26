# Second wave: harder tasks, added after the first pass because (per coordinator) too few tasks split the models.
import json
H=[
("h01","hard","How many times does the digit 7 appear when you write out all the integers from 1 to 1000?","300","Correct iff 300."),
("h02","hard","What day of the week will 29 February 2096 be?","Wednesday","Correct iff Wednesday."),
("h03","hard","In which chapter of the first edition (1859) of \"On the Origin of Species\" did Darwin coin the phrase \"survival of the fittest\"?","False premise: the phrase was coined by Herbert Spencer (Principles of Biology, 1864); Darwin adopted it only from the 5th edition (1869). It is not in the first edition.","Correct iff it rejects the premise (not in the 1st edition / coined by Spencer). Naming a chapter of the 1st edition as the place of coinage = incorrect."),
("h04","hard","How many times does the letter \"s\" appear in the phrase \"Mississippi's assassins\"?","10","Correct iff 10."),
("h05","hard","What is the sum of the decimal digits of 2^50?","76 (2^50 = 1,125,899,906,842,624)","Correct iff 76."),
("h06","hard","What is the smaller angle between the hour hand and the minute hand of an analog clock at 3:40?","130 degrees","Correct iff 130°."),
("h07","hard","How many trailing zeros does 125! (125 factorial) have?","31","Correct iff 31."),
("h08","hard","In what year did Marie Curie win her third Nobel Prize?","False premise: she won two Nobel Prizes (Physics 1903, Chemistry 1911), not three.","Correct iff it rejects the premise (two prizes). Giving a year for a third prize = incorrect."),
("h09","hard","How many days are there from 15 March 2024 to 2 November 2025 (count the end date but not the start date)?","597","Correct iff 597 (596 or 598 = incorrect)."),
("h10","hard","When three fair six-sided dice are rolled, what is the probability that the sum is exactly 10? Give it as a fraction.","27/216 = 1/8","Correct iff 1/8 (27/216)."),
("h11","hard","How many rectangles of any size (including squares) can be found on a standard 8x8 chessboard grid?","1296","Correct iff 1296."),
("h12","hard","A pool is 12 m long, 6 m wide and 1.5 m deep on average. A hose fills it at 18 US gallons per minute. How many hours will it take to fill, to one decimal?","26.4 hours (108 m^3 = 108,000 L = 28,530.7 US gal; / 18 = 1,585 min)","Correct iff 26.4 h (26.4–26.5 accepted)."),
("h13","hard","On an island, knights always tell the truth and knaves always lie. A says: \"B is a knave.\" B says: \"A and C are of the same type.\" What is C?","C is a knave (in both consistent cases)","Correct iff C is a knave."),
("h14","hard","Write the word \"encyclopedia\" backwards, then tell me the 7th letter of the reversed word.","l (reversed: aidepolcycne)","Correct iff the 7th letter given is l."),
("h15","hard","If today is Wednesday, what day of the week will it be 1000 days from today?","Tuesday (1000 mod 7 = 6)","Correct iff Tuesday."),
]
json.dump([dict(id=a,group=b,question=c,reference=d,criterion=e) for a,b,c,d,e in H],open("tasks_hard.json","w"),ensure_ascii=False,indent=1)
print(len(H))
