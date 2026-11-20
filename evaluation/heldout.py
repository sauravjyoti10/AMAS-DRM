"""Held-out triage test: 43 messages the rule parser was NOT tuned on.

The 117-message set in dataset.py was used to develop the rules, so its score (98.3 percent) measures how well
the rules fit that set, not how well they work on new messages. These 43 messages were written afterwards, with
new places and new wording (two in Hindi-English), and labelled with the written tie-break rules before any
parser was run on them. Severity labels follow evaluation/annotation/severity_adjudication.json.

    python -m evaluation.heldout

Small set, one author: read the result as an indication, not a precise accuracy.
"""
import os

from evaluation.metrics import pct
from app.triage import rule_based_triage

C, H, M, L = "CRITICAL", "HIGH", "MODERATE", "LOW"
DATA = [

("Our neighbour's house is sinking into the water at Bamunimaidan, family of 4 cannot get out.",C,4),
("Water has reached the roof of our single-storey house in Hengrabari, 6 of us are standing on the terrace.",C,6),
("A school bus is stuck in deep water near Kahilipara, 25 children inside, water is climbing.",C,25),
("Two men were hit by a falling tree at Lachit Nagar, both are awake, one has a bleeding head.",H,2),
("Streetlight pole fell on a rickshaw near Ulubari, driver has a broken leg but is conscious.",H,1),
("Large crack in the wall of our building at Bhangagarh after the rain, we have all moved out.",H,0),
("Transformer is sparking in the flooded lane at Maligaon, no one is near it.",H,0),
("No power since evening in Hatigaon, the whole locality is dark.",M,0),
("A lorry broke down and is blocking the road at Beltola Tiniali.",M,0),
("Please confirm if schools in Dispur are open tomorrow.",L,0),
("Mud and stones fell on the road near Narengi, bikes cannot go, nobody was under it.",M,0),
("Elderly woman fainted in the flood water at Silpukhuri and is not responding, need ambulance now.",C,1),
("Boat engine failed in the river at Pandu, 7 fishermen drifting, current is strong.",C,7),
("Water level at Bharalu is rising but our street is dry for now, just warning others.",L,0),
("My father has chest pain and our road to the hospital is waterlogged, ambulance cannot reach.",C,1),
("Fire in the electric shop at Fancy Bazar, shutters closed, nobody inside.",H,0),
("Ganeshguri flyover lights are off, drivers are confused.",M,0),
("Open manhole near Chandmari bus stop, someone could fall in.",H,0),
("Three labourers are buried under a collapsed wall at Jalukbari, we can hear them shouting.",C,3),
("Knee-deep water at Basistha chariali, auto-rickshaws not running.",M,0),
("Girl slipped on the wet stairs at Paltan Bazaar, ankle swollen, she can sit and talk, need first aid.",H,1),
("Test message from control room, ignore.",L,0),
("20 villagers marooned on a small island in the river near Sonapur, need boats urgently.",C,20),
("Gas cylinder blast in a flooded kitchen at Rupnagar, two people have burns and are being treated by neighbours.",H,2),
("Lift stuck with 3 people inside at Christian Basti, power cut, they are scared.",C,3),
("Landslide on the hill road above Sarania, boulders on the road, no vehicles, no injuries.",M,0),
("Our house in Kahilipara is full of water up to the waist, we are 5 people standing on the bed.",C,5),
("Potholes everywhere on Lal Ganesh road after rain.",L,0),
("Pregnant lady in pain and no taxi can come through the flood at Kamakhya.",C,1),
("Cattle shed collapsed at Azara, animals hurt, no people near.",H,0),
("Where can we collect relief food in Ulubari?",L,0),
("Mobile towers down in Noonmati after the storm, no calls going through.",M,0),
("Three kids trapped on the first floor of a flooded coaching centre at Six Mile, water at the stairs.",C,3),
("Crowd gathering at the river ghat at Uzanbazar, nothing wrong.",L,0),
("Car swept off the road by the current at Garchuk, two people inside shouting for help.",C,2),
("A man has a deep cut on his hand from broken glass in the flood at Chandmari, he is stable, needs a doctor.",H,1),
("Drainage water entering shops at Pan Bazar, goods damaged, no injuries.",H,0),
("Road to Guwahati airport partially flooded, taxis moving slowly.",M,0),
("Rooftop of a tin shed lifted by wind at Beltola, nobody injured, family sheltering with neighbours.",H,0),
("Eight people on a bus roof as the Bharalu overflows near Jalukbari, help!",C,8),
("paani bhar gaya hai ghar me, 4 log phase hue hain, nao chahiye",C,4),
("pls help bamunimaidan 2 ppl hurt tree fell",H,2),
("Overflowing drain at Sixmile, water on the road, buses slow.",M,0),
]


def main() -> None:
    gold, pred, cas_ok = [], [], 0
    for text, sev, cas in DATA:
        p = rule_based_triage(text)
        gold.append(sev)
        pred.append(p.severity)
        cas_ok += p.casualties == cas
    n = len(DATA)
    acc = sum(g == p for g, p in zip(gold, pred)) / n
    crit = [p for g, p in zip(gold, pred) if g == C]
    lines = [f"## Held-out triage test, rule parser ({n} messages not used to develop the rules)",
             f"Severity accuracy **{pct(acc)}** ({sum(g == p for g, p in zip(gold, pred))} of {n}); "
             f"CRITICAL recall {sum(p == C for p in crit)} of {len(crit)}; casualty count exact {pct(cas_ok / n)}.", ""]
    for (text, sev, cas), p in zip(DATA, pred):
        if sev != p:
            lines.append(f"- gold {sev} / predicted {p}: {text}")
    out = "\n".join(lines)
    print(out)
    os.makedirs(os.path.join(os.path.dirname(__file__), "results"), exist_ok=True)
    with open(os.path.join(os.path.dirname(__file__), "results", "heldout_rules.md"), "w", encoding="utf-8") as f:
        f.write(out + "\n")


if __name__ == "__main__":
    main()
