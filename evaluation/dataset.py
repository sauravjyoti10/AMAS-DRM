"""Labelled SOS messages for triage evaluation.

Each sample: (text, severity, casualties, place, resources, lat, lon)

severity   CRITICAL = people trapped / stranded / life at immediate risk
           HIGH     = serious damage or injuries, people not in immediate danger
           MODERATE = disruption (power, blocked road, knee-deep water), no one hurt
           LOW      = minor issue, information request, test message
casualties number of injured or trapped people the message states (0 if none stated)
place      a key of app/gazetteer.py  -> the sender names that locality
           "OTHER"   -> a real Guwahati place that is NOT in the built-in gazetteer (needs online geocoding)
           "COORDS"  -> coordinates are written in the text (lat, lon = gold point)
           "OUTSIDE" -> a place or coordinates outside Guwahati (must NOT be pinned)
           None      -> no place named (must NOT be pinned)
resources  items the sender asks for (First Aid Kits / Inflatable Rafts / Drinking Water / Food Packets)

IMPORTANT HONESTY NOTE
These messages were written by the project author, not collected from real victims, and the labels
are one annotator's judgement. For the thesis: (1) have a second person label the same messages
independently and report Cohen's kappa, (2) add 30-50 real or public-dataset messages, and
(3) fill GOLD_COORDS below from the OSM base map to measure real position error in metres.
"""
from typing import Dict, List, NamedTuple, Optional, Tuple

F, R, D, N = "First Aid Kits", "Inflatable Rafts", "Drinking Water", "Food Packets"
C, H, M, L = "CRITICAL", "HIGH", "MODERATE", "LOW"


class Sample(NamedTuple):
    id: int
    text: str
    severity: str
    casualties: int
    place: Optional[str]
    resources: Tuple[str, ...]
    lat: Optional[float]
    lon: Optional[float]


# id -> (lat, lon) true position for "OTHER" places; fill these in from OSM to get real metre errors.
GOLD_COORDS: Dict[int, Tuple[float, float]] = {}

_RAW = [
    # ---------------- CRITICAL, locality in the gazetteer ----------------
    ("Building collapsed near Paltan Bazaar, 6 people trapped under debris. Need first aid kits urgently.", C, 6, "paltan bazaar", [F]),
    ("Flash flood at Zoo Road Tiniali. 12 residents stranded on rooftops, water rising. Send rafts and drinking water!", C, 12, "zoo road tiniali", [R, D]),
    ("5 people buried under the landslide at Jalukbari, need first aid kits.", C, 5, "jalukbari", [F]),
    ("Water has entered the ground floor in Rajgarh, an elderly couple is trapped upstairs and cannot move. Please send a boat.", C, 2, "rajgarh", [R]),
    ("Boat capsized near Ganeshguri, 8 people in the water, urgent!", C, 8, "ganeshguri", [R]),
    ("SOS! Khanapara overbridge area completely under water, 20 passengers stuck inside a bus, water level rising.", C, 20, "khanapara", [R]),
    ("Wall collapse at Chandmari market, 4 workers trapped, one is bleeding badly. Ambulance and first aid kits please.", C, 4, "chandmari", [F]),
    ("Six Mile flyover side: a house caved in, 3 children trapped inside. Help immediately.", C, 3, "six mile", [F]),
    ("Maligaon railway colony flooded, water above waist level, 10 families stranded. Need boats and food.", C, 10, "maligaon", [R, N]),
    ("Dispur: flash flood swept away a car with 3 people, we are trying to pull them out. Need rope and ambulance now.", C, 3, "dispur", [F]),
    ("Beltola Tiniali under 5 feet of water. 15 people are on the first floor of a shop and cannot get out. Boats needed.", C, 15, "beltola", [R]),
    ("Landslide near Zoo Road, a bus is partially buried, passengers shouting for help.", C, 0, "zoo road", [F]),
    ("Trapped in a lift in Paltan Bazaar after power surge and flooding, 5 of us, oxygen is low.", C, 5, "paltan bazaar", []),
    ("Rajgarh Road: three people have collapsed from electric shock in the water, please send an ambulance.", C, 3, "rajgarh", [F]),
    ("House collapsed at Ganeshguri Chariali. Two people under the rubble.", C, 2, "ganeshguri", [F]),
    ("My mother is having a heart attack and the road to the hospital at Chandmari is submerged. Need rescue boat.", C, 1, "chandmari", [R, F]),
    ("Khanapara ISBT: flood water is chest deep, many passengers stranded on the roof of the terminal. About 40 people.", C, 40, "khanapara", [R, D]),
    ("URGENT: embankment breach near Beltola, water entering homes fast, 25 people trapped.", C, 25, "beltola", [R]),
    ("Six Mile area landslide has crushed two shops. Four people missing.", C, 4, "six mile", [F]),
    ("SOS Jalukbari ghat: ferry stuck mid river, 30 passengers panicking, water rising.", C, 30, "jalukbari", [R]),
    ("Flooded basement at Dispur secretariat road, two guards trapped and water rising fast.", C, 2, "dispur", [R]),
    ("Flash flood trapped 7 hikers near Zoo Road forest area, we have no signal. Send rescue.", C, 7, "zoo road", [R, F]),
    ("Building on fire and flooding combined at Paltan Bazaar market, people jumping out, 9 injured.", C, 9, "paltan bazaar", [F]),
    ("Chandmari: roof of an old house collapsed, 2 trapped, calling from under the debris.", C, 2, "chandmari", [F]),
    ("Stuck in car near Maligaon, water entering the car, 4 inside. HELP", C, 4, "maligaon", [R]),
    ("Rajgarh: gas leak and flooded street, 3 unconscious people on the floor.", C, 3, "rajgarh", [F]),
    ("Landslide hit the hostel wall at Khanapara, 6 students under the mud, rescue needed now.", C, 6, "khanapara", [F]),
    ("Dispur: collapsed scaffolding, a worker is trapped and bleeding heavily.", C, 1, "dispur", [F]),

    # ---------------- HIGH, locality in the gazetteer ----------------
    ("Heavy flooding in Beltola, water inside houses but everyone is safe on upper floors. Need drinking water and food packets.", H, 0, "beltola", [D, N]),
    ("Two people injured after a tree fell on a scooter near Dispur. They are conscious. Need first aid.", H, 2, "dispur", [F]),
    ("Fire in a godown near Paltan Bazaar, firefighters have not arrived, no one inside as far as we know.", H, 0, "paltan bazaar", []),
    ("Flood water entered our house in Rajgarh, we moved upstairs with the kids, we need food and drinking water for 2 days.", H, 0, "rajgarh", [N, D]),
    ("A boy has a deep cut on his leg after falling in Khanapara market, bleeding but stable. Need first aid.", H, 1, "khanapara", [F]),
    ("Three people with minor injuries from a wall collapse at Chandmari, others are safe. Please send first aid kits.", H, 3, "chandmari", [F]),
    ("Flooded colony at Maligaon, 50 houses affected, no food since yesterday.", H, 0, "maligaon", [N]),
    ("Water supply contaminated by floodwater at Jalukbari, people falling sick, need drinking water.", H, 0, "jalukbari", [D]),
    ("Five injured in a bus collision on the flooded road at Dispur, all awake and talking.", H, 5, "dispur", [F]),
    ("Elderly man with diabetes needs insulin, cannot leave the house because of flood near Zoo Road. Need medical help.", H, 1, "zoo road", [F]),
    ("River bank erosion is damaging houses near Jalukbari, families moved to the school, need food.", H, 0, "jalukbari", [N]),
    ("Heavy rain flooding Khanapara petrol pump, fuel leaking into the water.", H, 0, "khanapara", []),
    ("Boundary wall collapsed at Rajgarh school, 2 students have fractures, teachers are with them.", H, 2, "rajgarh", [F]),
    ("Floodwater has cut off our lane at Six Mile, 30 families have no food or clean water.", H, 0, "six mile", [N, D]),
    ("Pregnant woman in labour at Ganeshguri, ambulance stuck in the flood, we need help reaching hospital.", H, 1, "ganeshguri", [F]),
    ("Electric transformer exploded near Paltan Bazaar, area dark, two people got burns.", H, 2, "paltan bazaar", [F]),
    ("Our hostel at Khanapara has no power and the lower floor is flooded, we are safe but need drinking water.", H, 0, "khanapara", [D]),
    ("Flash flood washed away the culvert at Maligaon, road cut off completely.", H, 0, "maligaon", []),
    ("Dog bite victim bleeding at Chandmari, no vehicle available because of flooding.", H, 1, "chandmari", [F]),
    ("Landslide near Zoo Road narrowly missed a house, cracks in the walls, family is staying outside.", H, 0, "zoo road", []),
    ("Flooded street in Dispur, two children have fever and cough, need medicine.", H, 2, "dispur", [F]),
    ("Smoke from a short circuit in a flooded shop at Ganeshguri, one person coughing badly.", H, 1, "ganeshguri", [F]),
    ("Heavy flooding on Jalukbari bypass, trucks stuck, drivers have no food or water for 12 hours.", H, 0, "jalukbari", [N, D]),
    ("Wall of the drain collapsed near Rajgarh Road, water entering shops, no one hurt.", H, 0, "rajgarh", []),
    ("Need first aid kits at the relief camp in Khanapara, one person has a broken arm.", H, 1, "khanapara", [F]),
    ("Floodwater entering the ground floor of the hospital at Six Mile, patients being shifted.", H, 0, "six mile", []),
    ("Child cut by broken glass while wading through flood at Paltan Bazaar.", H, 1, "paltan bazaar", [F]),

    # ---------------- MODERATE ----------------
    ("Waterlogging at Ganeshguri since morning, shops flooded, traffic completely jammed.", M, 0, "ganeshguri", []),
    ("Knee-deep water on the road at Beltola, two-wheelers are struggling.", M, 0, "beltola", []),
    ("Electricity pole fell across the road at Chandmari, wires are live, people avoiding the area.", M, 0, "chandmari", []),
    ("No electricity in Dispur since last night, transformer damaged.", M, 0, "dispur", []),
    ("Landslide debris blocking the Six Mile road, vehicles cannot pass, no injuries reported.", M, 0, "six mile", []),
    ("A big tree fell on the road near Rajgarh and blocked traffic.", M, 0, "rajgarh", []),
    ("Drain overflow near Paltan Bazaar, dirty water on the road.", M, 0, "paltan bazaar", []),
    ("Streetlights are not working on Zoo Road after the storm.", M, 0, "zoo road", []),
    ("Road caved in a little at Jalukbari, one lane is blocked, please inspect.", M, 0, "jalukbari", []),
    ("Mobile network is down in Khanapara after the floods, people cannot call for help.", M, 0, "khanapara", []),
    ("Water supply has stopped in Maligaon for two days.", M, 0, "maligaon", []),
    ("Power cut and knee-deep water around Zoo Road Tiniali, shops closed.", M, 0, "zoo road tiniali", []),
    ("Traffic signal not working at Ganeshguri Chariali and the junction has knee-deep water.", M, 0, "ganeshguri", []),
    ("Fallen tree branches blocking the lane at Beltola.", M, 0, "beltola", []),
    ("Electricity wires hanging low near Chandmari, nobody hurt yet, please fix.", M, 0, "chandmari", []),
    ("Waterlogging near Six Mile bus stop, buses running late.", M, 0, "six mile", []),

    # ---------------- LOW ----------------
    ("Light drizzle and small puddles near Dispur, just letting you know.", L, 0, "dispur", []),
    ("Is the Khanapara road open for travel tomorrow?", L, 0, "khanapara", []),
    ("Please tell me the nearest relief camp near Zoo Road.", L, 0, "zoo road", []),
    ("Stray dogs gathering near the Beltola relief point, no one hurt.", L, 0, "beltola", []),
    ("Pothole filled with water at Rajgarh, will be a problem later.", L, 0, "rajgarh", []),
    ("Minor leak in a water pipe near Chandmari.", L, 0, "chandmari", []),
    ("Crowd watching the river at Jalukbari bridge, police not present, nothing wrong right now.", L, 0, "jalukbari", []),
    ("Ankle deep water at Ganeshguri Chariali, shops opening late.", L, 0, "ganeshguri", []),
    ("Test message, please ignore.", L, 0, None, []),
    ("Can volunteers register at Paltan Bazaar tomorrow morning?", L, 0, "paltan bazaar", []),

    # ---------------- real Guwahati places NOT in the gazetteer (need online geocoding) ----------------
    ("Flooding near Fancy Bazar, 3 people trapped in a shop.", C, 3, "OTHER", [R]),
    ("Landslide at Narengi, 2 houses damaged, no one hurt.", H, 0, "OTHER", []),
    ("Water logging at Bhangagarh since morning.", M, 0, "OTHER", []),
    ("Tree fell on a car near Lokhra Chariali, driver injured.", H, 1, "OTHER", [F]),
    ("Hatigaon main road flooded, two-wheelers cannot pass.", M, 0, "OTHER", []),
    ("Uzanbazar ghat: man swept away by the river, search needed.", C, 1, "OTHER", [R]),
    ("Fire at a warehouse in Garchuk, people inside, send help.", C, 0, "OTHER", [F]),
    ("Noonmati refinery road waterlogged.", M, 0, "OTHER", []),
    ("Adabari bus stand flooded, passengers stranded.", C, 0, "OTHER", [R]),
    ("Ulubari underpass is full of water, a car is stuck.", H, 0, "OTHER", []),
    ("Silpukhuri: drain overflow flooding houses.", H, 0, "OTHER", []),
    ("Basistha hill road landslide, vehicles stuck.", M, 0, "OTHER", []),

    # ---------------- coordinates in the message ----------------
    ("SOS! Landslide at 26.1450 N, 91.8020 E. 6 people trapped. Need first aid kits.", C, 6, "COORDS", [F], 26.1450, 91.8020),
    ("Flood at 26.1280 N, 91.8000 E. Water inside houses. We need food packets.", H, 0, "COORDS", [N], 26.1280, 91.8000),
    ("Location 26.1595, 91.7712 water rising, 3 people on the roof.", C, 3, "COORDS", [R], 26.1595, 91.7712),
    ("At 26.1830, 91.7500 a boy fell into the open drain and is being swept away, please send help immediately.", C, 1, "COORDS", [], 26.1830, 91.7500),
    ("Car stuck in water at 26.1832 91.7390, two adults inside, safe for now.", H, 2, "COORDS", [R], 26.1832, 91.7390),
    ("Lat 26.1730 Lon 91.7730 flooded road, shops damaged.", H, 0, "COORDS", [], 26.1730, 91.7730),

    # ---------------- no place named ----------------
    ("Help! Water is entering our house and the children are scared.", H, 0, None, []),
    ("Someone please send a boat, we are on the roof.", C, 0, None, [R]),
    ("I need first aid kits urgently, my brother is hurt.", H, 1, None, [F]),
    ("Flood flood flood please help", H, 0, None, []),
    ("Medical emergency, patient not breathing.", C, 1, None, [F]),
    ("Road blocked by a landslide, no signal, 6 of us are stuck in the car.", C, 6, None, []),

    # ---------------- outside Guwahati / outside the service area ----------------
    ("SOS flooding near Connaught Place, Delhi. 5 people trapped.", C, 5, "OUTSIDE", [R]),
    ("Landslide on Police Bazar road, Shillong, 4 people trapped.", C, 4, "OUTSIDE", [F]),
    ("Flood at Silchar town, 20 people stranded on a roof.", C, 20, "OUTSIDE", [R]),
    ("Coordinates 28.6139 N, 77.2090 E, flood, 4 people trapped.", C, 4, "OUTSIDE", [R]),

    # ---------------- messy: typos, ALL CAPS, Hinglish ----------------
    ("pls help khanapra me pani aa gaya 10 log fase hai", C, 10, "khanapara", [R]),
    ("SOS SOS ZOO ROAD TINIALI FLOOD 5 PEOPLE ON ROOF!!!", C, 5, "zoo road tiniali", [R]),
    ("flud at beltola 3 ppl strnded plz send boat", C, 3, "beltola", [R]),
    ("Chandmari water rising fast!! trapped in shop", C, 0, "chandmari", [R]),
    ("Need rafts n food at Maligaon, 12 stuck, house surrounded by water", C, 12, "maligaon", [R, N]),
    ("ganeshguri flood help", H, 0, "ganeshguri", []),
    ("Urgent!!! JALUKBARI landslide!!! 2 ppl hurt", C, 2, "jalukbari", [F]),
    ("dispur me bijli nahi hai kal se", M, 0, "dispur", []),
]


def load() -> List[Sample]:
    out: List[Sample] = []
    for i, row in enumerate(_RAW, start=1):
        text, sev, cas, place, res = row[:5]
        lat, lon = (row[5], row[6]) if len(row) > 5 else (None, None)
        if place == "OTHER" and i in GOLD_COORDS:
            lat, lon = GOLD_COORDS[i]
        out.append(Sample(i, text, sev, cas, place, tuple(res), lat, lon))
    return out


if __name__ == "__main__":
    import collections
    data = load()
    print(len(data), "messages")
    print("severity:", dict(collections.Counter(s.severity for s in data)))
    print("place   :", dict(collections.Counter(("gazetteer" if s.place not in (None, "OTHER", "COORDS", "OUTSIDE") else s.place) for s in data)))
