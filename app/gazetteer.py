"""Built-in gazetteer of Guwahati localities: the offline fallback and the sanity check for geocoding.

Each entry is (lat, lon, uncertainty_m). The uncertainty is how far the real spot named in an SOS
could be from the point stored here; the dashboard draws it as a circle so nobody mistakes a
locality centre for an exact address.

  VERIFIED  = coordinates read from Wikipedia (locality centroid).
  APPROX    = project-supplied or estimated; treat as +-1 km until checked against the OSM base map.

The live OpenStreetMap geocoder (app/triage.py) is tried first for precise landmarks;
these entries are used when it is offline, finds nothing, or returns a point far from the named locality.
"""
import re
from typing import Dict, List, Optional, Tuple

GAZETTEER: Dict[str, Tuple[float, float, float]] = {
    "khanapara":        (26.1250, 91.8108, 700),   # VERIFIED (Wikipedia: 26.125 N, 91.81083 E)
    "guwahati":         (26.1722, 91.7458, 5000),  # VERIFIED city centre (Wikipedia)
    "paltan bazaar":    (26.1830, 91.7500, 600),   # APPROX
    "zoo road tiniali": (26.1750, 91.7750, 400),   # APPROX (project depot location)
    "zoo road":         (26.1740, 91.7740, 800),   # APPROX
    "rajgarh":          (26.1730, 91.7730, 900),   # APPROX
    "chandmari":        (26.1715, 91.7640, 900),   # APPROX
    "ganeshguri":       (26.1495, 91.7860, 600),   # APPROX
    "dispur":           (26.1433, 91.7898, 800),   # APPROX (project depot location)
    "beltola":          (26.1280, 91.8000, 800),   # APPROX
    "six mile":         (26.1330, 91.8030, 800),   # APPROX
    "maligaon":         (26.1520, 91.6970, 900),   # APPROX
    "jalukbari":        (26.1550, 91.6640, 900),   # APPROX
}

ALIASES: Dict[str, str] = {
    "paltan bazar": "paltan bazaar",
    "paltanbazar": "paltan bazaar",
    "zoo tiniali": "zoo road tiniali",
    "zoo road tiniali": "zoo road tiniali",
    "ganesh guri": "ganeshguri",
    "khanapara bus stand": "khanapara",
    "khanapara isbt": "khanapara",
    "6 mile": "six mile",
    "sixmile": "six mile",
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


def lookup(name: str) -> Optional[Tuple[str, float, float, float]]:
    """Exact (normalised) match -> (canonical_name, lat, lon, uncertainty_m)."""
    key = normalize(name)
    key = ALIASES.get(key, key)
    if key in GAZETTEER:
        lat, lon, unc = GAZETTEER[key]
        return key, lat, lon, unc
    return None


def find_places(text: str) -> List[Tuple[str, int, int]]:
    """Every gazetteer name or alias mentioned in free text, longest first: [(canonical, start, end)]."""
    norm = normalize(text)
    names = sorted(set(GAZETTEER) | set(ALIASES), key=len, reverse=True)
    found: List[Tuple[str, int, int]] = []
    taken: List[Tuple[int, int]] = []
    for name in names:
        for m in re.finditer(rf"\b{re.escape(name)}\b", norm):
            span = (m.start(), m.end())
            if any(s < span[1] and span[0] < e for s, e in taken):
                continue  # already covered by a longer match
            taken.append(span)
            found.append((ALIASES.get(name, name), span[0], span[1]))
    return sorted(found, key=lambda f: f[1])
