"""Triage Module: SOS parsing and spatial resolution.

Two stages:
  1. run_triage()        text -> ParsedIncident   (Gemini; rule-based parser when no API key is set)
  2. resolve_location()  ParsedIncident -> TriageResult with a VALIDATED lat/lon, or no location at all.

Design rule: a wrong pin is worse than no pin. If the place cannot be resolved inside Guwahati the
result says "unknown" and a dispatcher pins it by hand; nothing is silently replaced by a default point.
"""
import json as _json
import math
import os
import re
import threading
import time
from typing import Callable, List, Optional, Tuple

from app import gazetteer
from app.config import Settings, get_settings
from app.geo import haversine_m
from app.schemas import ParsedIncident, ResourceRequirement, TriageResult

GEO_SUFFIX = ", Guwahati, Assam, India"
MAX_ATTEMPTS = 5          # upper limit; the time budget (settings.gemini_budget_s) usually stops retries sooner
RETRY_BASE_S = 1.0        # pauses of 1, 2, 4 ... seconds between attempts

SYSTEM_PROMPT = """You are the triage agent of a disaster-management system for Guwahati, Assam, India.
Read one raw SOS message and fill the schema.
- severity: CRITICAL = lives at immediate risk (trapped, stranded, rising water, collapse, landslide);
  HIGH = serious damage or injuries without immediate danger; MODERATE = disruption; LOW = minor.
- casualties: number of injured or trapped people (0 if not stated).
- location_text: the place EXACTLY as the sender wrote it, keeping landmark words
  (for example 'Khanapara bus stand', 'Zoo Road Tiniali'). Null if no place is mentioned.
- latitude / longitude: ONLY if numeric coordinates are written in the message. Never guess them.
- needed_resources: only items from the allowed list, with a sensible quantity."""


class TriageError(Exception):
    """Gemini could not produce a valid ParsedIncident."""


# --------------------------------------------------------------------------- stage 1: parsing
def _strip_fences(text: Optional[str]) -> str:
    if not text:
        raise ValueError("empty model response")
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    return re.sub(r"\s*```$", "", text)


def run_triage(raw_sos: str, client=None, settings: Optional[Settings] = None) -> ParsedIncident:
    """Gemini structured extraction, retried once. With no API key and no client it uses the rule-based parser."""
    settings = settings or get_settings()
    if client is None:
        if not settings.gemini_api_key:
            return rule_based_triage(raw_sos)
        from google import genai  # imported lazily so tests and offline runs do not need the SDK
        timeout_ms = int(settings.gemini_timeout_s * 1000)
        try:  # one attempt per request: our own loop does the retrying inside the time budget
            client = genai.Client(api_key=settings.gemini_api_key,
                                  http_options={"timeout": timeout_ms, "retry_options": {"attempts": 1}})
        except Exception:  # older SDK without retry_options
            client = genai.Client(api_key=settings.gemini_api_key, http_options={"timeout": timeout_ms})

    last_error: Optional[Exception] = None
    started = time.monotonic()
    for attempt in range(MAX_ATTEMPTS):
        try:
            resp = client.models.generate_content(
                model=settings.gemini_model,
                contents=raw_sos,
                config={
                    "system_instruction": SYSTEM_PROMPT,
                    "response_mime_type": "application/json",
                    "response_schema": ParsedIncident,
                    "temperature": 0,
                },
            )
            return ParsedIncident.model_validate_json(_strip_fences(resp.text))
        except Exception as exc:  # bad JSON, schema violation, API/network error
            last_error = exc
            msg = str(exc)
            if "PerDay" in msg or "NOT_FOUND" in msg or "API key" in msg or "INVALID_ARGUMENT" in msg:
                break  # daily quota, wrong model name, bad key or bad request: waiting will not help
            delay = RETRY_BASE_S * (2 ** attempt)
            if attempt == MAX_ATTEMPTS - 1 or time.monotonic() - started + delay + settings.gemini_timeout_s > settings.gemini_budget_s:
                break  # another attempt could not finish inside the time budget
            time.sleep(delay)
    raise TriageError(f"Triage failed: {last_error}")


# ---- rule-based fallback (works offline, no API key) ----
_NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
              "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_PEOPLE = (r"(?:casualt\w*|people|persons?|travell?ers|passengers|residents|villagers|victims|"
           r"children|kids|students|families|workers|injured)")
_LANDMARK_WORDS = (r"bus\s*stand|bus\s*stop|bus\s*terminus|bus\s*station|isbt|tiniali|chariali|chowk|"
                   r"junction|flyover|bridge|market|bazaar|bazar|station|gate|petrol\s*pump|hospital|"
                   r"school|college|temple|stadium|ground|park|colony|road|path|lane")
_CRITICAL = ("critical", "collapse", "trapped", "stranded", "submerged", "drown",
             "rising", "rooftop", "life-threatening", "immediately")
_HIGH = ("flood", "waterlogging", "injur", "overflow", "fire", "washed away")
_MODERATE = ("electricity", "power cut", "knee-deep", "blocked", "fallen tree", "tree fell")


def parse_coordinates(text: str) -> Optional[Tuple[float, float]]:
    """'26.1750 N, 91.7750 E' or '26.175, 91.775' -> (lat, lon)."""
    # The hemisphere letter must stand alone: "91.77 water" is not "91.77 W" (west).
    m = re.search(
        r"(?:\blat(?:itude)?\s*[:=]?\s*)?(-?\d{1,2}\.\d{2,})\s*°?\s*([NS](?![A-Za-z]))?"
        r"(?:\s*[,;/]\s*|\s+)"
        r"(?:\blon(?:g|gitude)?\s*[:=]?\s*)?(-?\d{2,3}\.\d{2,})\s*°?\s*([EW](?![A-Za-z]))?",
        text, re.I)
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(3))
    if (m.group(2) or "").upper() == "S":
        lat = -abs(lat)
    if (m.group(4) or "").upper() == "W":
        lon = -abs(lon)
    return lat, lon



def _count_people(raw: str) -> int:
    """Extract an explicitly stated number of people from an SOS message."""

    number_pattern = (
        r"(?:\d{1,4}|"
        + "|".join(_NUM_WORDS.keys())
        + r")"
    )

    people_words = (
        r"people|persons?|travell?ers|passengers|residents|villagers|"
        r"victims|children|kids|students|families|workers|adults?|"
        r"men|women|casualt\w*"
    )

    patterns = [
        # Examples: 4 people, two children, 3 injured people
        rf"\b({number_pattern})\s+(?:more\s+|injured\s+|trapped\s+|stranded\s+|elderly\s+)?(?:{people_words})\b",

        # Examples: 4 injured, two trapped
        rf"\b({number_pattern})\s+(?:injured|trapped|stranded|unconscious)\b",

        # Examples: with 4 inside, 2 trapped inside
        rf"\b(?:with|and|of)\s+({number_pattern})\s+(?:people\s+)?inside\b",

        # Example: car with 4 inside
        rf"\b({number_pattern})\s+inside\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, raw, re.I)
        if match:
            value = match.group(1).lower()
            if value.isdigit():
                return int(value)
            return _NUM_WORDS.get(value, 0)

    return 0



def _extract_location_text(raw: str) -> Optional[str]:
    """Known locality (plus a following landmark such as 'bus stand') first, then 'near/at <words>'."""
    names = sorted(set(gazetteer.GAZETTEER) | set(gazetteer.ALIASES), key=len, reverse=True)
    pattern = rf"\b(?:{'|'.join(re.escape(n) for n in names)})\b(?:\s+(?:{_LANDMARK_WORDS})){{0,2}}"
    m = re.search(pattern, raw, re.I)
    if m:
        return m.group(0).strip()
    m = re.search(r"\b(?:near|at|opposite|opp|behind|beside|around|outside)\s+(?:the\s+)?([A-Za-z0-9'\- ]{3,40})",
                  raw, re.I)
    return m.group(1).strip() if m else None

def _normalize_sos(text: str) -> str:
    """Normalize common informal SOS spelling and abbreviations."""
    text = text.lower()

    replacements = {
        "flud": "flood",
        "pani": "water",
        "bijli": "electricity",
        "ppl": "people",
        "strnded": "stranded",
        "plz": "please",
        "fase hai": "trapped",
        "fase hain": "trapped",
        "fase": "trapped",
    }

    for old, new in replacements.items():
        text = re.sub(rf"\b{re.escape(old)}\b", new, text)

    return text

def rule_based_triage(raw_sos: str) -> ParsedIncident:
    """Keyword/regex triage used when Gemini is not configured or fails."""
    raw = _normalize_sos(raw_sos)
    casualties = _count_people(raw_sos)

    
    # Immediate life-threatening situations
    critical_patterns = [
        # Landslide emergencies involving buried, missing, or trapped people
        r"\blandslide\b.*\b(?:people|persons|passengers|students|workers)\b.*\b(?:buried|missing|trapped)\b",
        r"\blandslide\b.*\b(?:bus|vehicle)\b.*\bpartially buried\b",
        r"\bpartially buried\b.*\b(?:passengers|people)\b",
        r"\blandslide\b.*\b(?:students|people|persons)\b.*\bunder the mud\b",
        r"\blandslide\b.*\b(?:people|persons)\b.*\b(?:hurt|injured)\b",
        r"\blandslide\b.*\b\d+\s+(?:people|persons)\s+(?:hurt|injured)\b",

        # Additional wording variations
        r"\b\d+\s+(?:people|persons)\s+buried\b.*\blandslide\b",
        r"\b(?:people|persons|passengers|students)\b.*\b(?:buried|trapped|missing)\b.*\b(?:landslide|mud|debris)\b",
        r"\b(?:landslide|mudslide)\b.*\b(?:crushed|buried)\b.*\b(?:people|persons|passengers|shops|houses)\b", 

        # Restore general life-threatening emergency rules
        r"\bswept away\b",
        r"\bdrowning\b|\bdrown(?:ed|ing)?\b",
        r"\bsubmerged\b",
        r"\btrapped\b",
        r"\bunconscious\b",
        r"\bnot breathing\b",
        r"\blife[- ]threatening\b",
        r"\bpeople inside\b.*\bfire\b",
        r"\bfire\b.*\bpeople inside\b",
        r"\bpregnant\b.*\bin labour\b.*\bambulance\b",
        r"\bdiabetic\b.*\binsulin\b.*\b(?:cannot|can't|unable)\b",   

        # Structural collapse with people trapped
        r"\b(?:wall|roof|house|building|scaffolding)\b.*\bcollapsed?\b.*\b(?:trapped|buried|bleeding)\b",
        r"\bcollapse\b.*\b\d+\s+(?:workers|people|persons)\b.*\btrapped\b",
        r"\b(?:workers|people|persons)\b.*\btrapped\b.*\b(?:collapse|debris|rubble)\b",

        # People swept away by water
        r"\bswept away\b.*\b(?:car|vehicle|people|person|man|woman|river)\b",
        r"\b(?:man|woman|person|people)\b.*\bswept away\b",

        # Medical emergencies
        r"\bnot breathing\b",
        r"\bunconscious\b",
        r"\b(?:gas leak|gas leakage)\b.*\b\d*\s*(?:people|persons)\b.*\bunconscious\b",

        # Fire with people inside
        r"\bfire\b.*\b(?:people|persons|workers)\b.*\binside\b",
        r"\b(?:people|persons|workers)\b.*\binside\b.*\bfire\b",

        # Pregnancy emergency with blocked ambulance access
        r"\bpregnant\b.*\bin labour\b.*\bambulance\b.*\b(?:stuck|blocked)\b",      

        # People in immediate danger from floodwater
        r"\bboat\s+capsized\b",
        r"\bpeople\s+in\s+the\s+water\b",
        r"\bin\s+the\s+water\b.*\b(?:help|rescue|boat)\b",
        r"\bwater\s+entering\s+(?:the\s+)?car\b",
        r"\bwater\s+inside\s+(?:the\s+)?car\b",
        r"\bwater\s+rising\s+(?:inside|around)\b",
        r"\bon\s+(?:the\s+)?roof\b",
        r"\b(?:people|persons|families)\s+on\s+(?:the\s+)?(?:roof|rooftop)\b",
        r"\bstranded\b.*\b(?:roof|rooftop|water|flood)\b",

        # Fire with people escaping
        r"\bpeople\s+jumping\s+out\b",

        # Flood-related medical emergency
        r"\bdiabet\w*\b.*\binsulin\b.*\b(?:flood|trapped|cannot|can't|unable)\b",
        r"\binsulin\b.*\b(?:cannot|can't|unable)\b.*\b(?:leave|get out|reach)\b",

        # People trapped inside a building or vehicle
        r"\b(?:first floor|ground floor)\b.*\b(?:cannot|can't|unable)\b.*\b(?:leave|escape|get out)\b",
        r"\bwater\b.*\b(?:trapped|stuck)\b.*\b(?:car|vehicle)\b",
                # Multiple people trapped in a vehicle with communication failure
        r"\bno signal\b.*\b(?:stuck|trapped)\b.*\b(?:car|vehicle)\b",
        r"\b(?:stuck|trapped)\b.*\b(?:car|vehicle)\b.*\bno signal\b",

        # Multiple people stranded and requesting rescue during flooding
        r"\bflood\b.*\b(?:people|persons|families)\b.*\bstranded\b",
        r"\bstranded\b.*\b(?:send|need|please send)\b.*\b(?:boat|raft|rescue)\b",

        # House surrounded by water with people trapped
        r"\bhouse\b.*\bsurrounded by water\b",
        r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve)\b.*\btrapped\b.*\b(?:water|flood)\b",

    ]

    # Serious injuries or significant property damage
    high_patterns = [
    # Injuries and medical emergencies
    r"\b(?:deep cut|bleeding|broken arm|fracture|fractures)\b",
    r"\b(?:burns|burn injuries|serious injur\w*)\b",
    r"(?<!no )(?<!nobody )(?<!no one )(?<!none )\b(?:injured|injuries|casualties|hurt)\b",
    r"\b(?:first aid|medical help)\b",

    # Serious incidents involving electricity
    r"\b(?:electricity|power)\b.*\b(?:pole|wire|wires)\b.*\b(?:fell|fallen|down|live|sparking|fire)\b",
    r"\b(?:pole|wire|wires)\b.*\b(?:fell|fallen|down|live)\b",
    r"\blive wires?\b",

    # Floodwater entering buildings or trapping vehicles
    r"\bwater\b.*\bentering\b.*\b(?:house|home|building)\b",
    r"\bdrain overflow\b.*\bflood(?:ing)?\s+(?:the\s+)?houses?\b",
    r"\b(?:car|vehicle)\b.*\bstuck\b.*\bwater\b",
    r"\bwater\b.*\b(?:car|vehicle)\b.*\bstuck\b",
    r"\bunderpass\b.*\b(?:full of water|flooded)\b",

    # Property damage and serious disruption
    r"\b(?:exploded|explosion)\b",
    r"\b(?:houses?|homes?) damaged\b",
    r"\b(?:families|people)\b.*\b(?:cut off|moved to|without food|without water)\b",
    r"\b(?:landslide|collapse|collapsed)\b.*\b(?:house|houses|home|homes|damage|damaged|cracks)\b",
    r"\b(?:wall|building|roof)\b.*\bcollapsed\b",
]

    # General disruption without an immediate threat to life
    moderate_patterns = [
    r"\bwaterlogging\b|\bwater logging\b",
    r"\bwaterlogged\b",
    r"\b(?:road|roads|lane)\b.*\bblocked\b",
    r"\bdebris\b.*\bblocking\b",
    r"\bdrain overflow\b",
    r"\bmobile network\b.*\bdown\b",
    r"\b(?:electricity|power)\b.*\b(?:outage|cut|down)\b",
    r"\b(?:water supply|streetlights?)\b.*\b(?:stopped|not working|down)\b",
    r"\bbuses?\b.*\b(?:late|delayed)\b",
    r"\b(?:vehicles?|two-wheelers?)\b.*\b(?:cannot|can't|unable)\b.*\bpass\b",
    r"\bvehicles?\b.*\bstuck\b",
    r"\btraffic\b.*\b(?:jammed|blocked|stuck)\b",
    r"\bshops?\b.*\bflooded\b",
    r"\b(?:children|kids)\b.*\b(?:fever|cough)\b",
]

    if any(re.search(pattern, raw) for pattern in critical_patterns):
        severity = "CRITICAL"
    elif any(re.search(pattern, raw) for pattern in high_patterns):
        severity = "HIGH"
    elif any(re.search(pattern, raw) for pattern in moderate_patterns):
        severity = "MODERATE"
    elif any(w in raw for w in _CRITICAL):
        # Retain existing emergency keywords as a fallback.
        severity = "CRITICAL"
    elif any(w in raw for w in _HIGH):
        severity = "HIGH"
    elif any(w in raw for w in _MODERATE):
        severity = "MODERATE"
    else:
        severity = "LOW"


    resources: List[ResourceRequirement] = []
    people = max(casualties, 0)
    if re.search(r"injur|casualt|hurt|medical|first aid|medic|ambulance|bleed", raw):
        resources.append(ResourceRequirement(item_name="First Aid Kits", quantity=max(1, people or 2)))
    flood_rescue = "flood" in raw and re.search(r"stranded|submerged|rooftop|rising|trapped", raw)
    if flood_rescue or re.search(r"raft|boat", raw):
        resources.append(ResourceRequirement(item_name="Inflatable Rafts", quantity=max(1, math.ceil(people / 8))))
    if re.search(r"water bottle|drinking water|thirst|water\b.*\bsend|send.*\bwater", raw):
        resources.append(ResourceRequirement(item_name="Drinking Water", quantity=max(1, people or 10)))
    if re.search(r"food|hungry|ration|meal", raw):
        resources.append(ResourceRequirement(item_name="Food Packets", quantity=max(1, people or 10)))
    
    if re.search(r"emergency medical kit|medical kits?", raw):
        match = re.search(
            r"\b(\d+)\s+emergency medical kits?\b",
            raw
        )
        quantity = int(match.group(1)) if match else 1

        resources.append(
            ResourceRequirement(
                item_name="Emergency Medical Kits",
                quantity=quantity
            )
        )
    

    kind = next((k for k in ("flood", "landslide", "collapse", "fire") if k in raw), "emergency")
    location = _extract_location_text(raw_sos)
    coords = parse_coordinates(raw_sos)
    return ParsedIncident(
        summary=f"{severity.title()} {kind} reported" + (f" near {location}" if location else ""),
        severity=severity,
        casualties=casualties,
        location_text=location,
        latitude=coords[0] if coords else None,
        longitude=coords[1] if coords else None,
        needed_resources=resources,
    )


# --------------------------------------------------------------------------- stage 2: location
_LEAD = re.compile(
    r"^(?:(?:stuck\s+)?(?:near|nr|opp|opposite|behind|beside|next to|close to|around|at|in|inside|outside|by)\b"
    r"[\s,.:\-]*)+", re.I)
_TAIL = re.compile(r"\s*(?:[,.;!?]|\b(?:and|but|where|with|please|pls|we|they|need|needs|send|help)\b).*$", re.I | re.S)
_INNER = re.compile(r"\b(?:near|opp|opposite|behind|beside|next to|close to)\b", re.I)
_LANDMARK_TAIL = re.compile(rf"\s+(?:{_LANDMARK_WORDS})$", re.I)


def place_queries(location_text: Optional[str]) -> List[str]:
    """Ordered geocoding candidates, most specific first.

    'near the Khanapara bus stand' -> ['Khanapara bus stand', 'Khanapara']
    'Zoo Road Tiniali'            -> ['Zoo Road Tiniali', 'Zoo Road']
    'Ganeshguri flyover opp SBI'  -> ['Ganeshguri flyover', 'Ganeshguri', 'SBI']
    """
    if not location_text:
        return []
    text = _LEAD.sub("", _TAIL.sub("", location_text.strip())).strip(" ,.-")
    out: List[str] = []
    for part in _INNER.split(text):
        cand = re.sub(r"^the\s+", "", part.strip(" ,.-"), flags=re.I)
        while len(cand) >= 3:
            if cand not in out:
                out.append(cand)
            shorter = _LANDMARK_TAIL.sub("", cand).strip()
            if shorter == cand or len(shorter) < 4:
                break
            cand = shorter
    return out


_geo_lock = threading.Lock()
_last_nominatim_call = 0.0
_PRECISE_CLASSES = {"amenity", "highway", "building", "shop", "railway", "tourism", "leisure",
                    "public_transport", "man_made", "office", "healthcare"}


def _cache_load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return _json.load(f)
    except (OSError, ValueError):
        return {}


def _cache_save(path: str, cache: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            _json.dump(cache, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


MISS_TTL_S = 24 * 3600   # "not found" answers are re-checked after a day (OSM data and our query wording both improve)


def _nominatim(phrase: str, settings: Settings, deadline: Optional[float] = None) -> Optional[Tuple[float, float, float]]:
    """OpenStreetMap lookup restricted to the Guwahati bounding box. Cached on disk. -> (lat, lon, uncertainty_m)

    The bounding box already limits results to Guwahati, so the bare phrase is tried first: adding
    ', Guwahati, Assam, India' to a bounded query made Nominatim return nothing for well-known localities.
    """
    global _last_nominatim_call
    key = gazetteer.normalize(phrase)
    with _geo_lock:
        cache = _cache_load(settings.geocode_cache_path)
        hit = cache.get(key)
        if isinstance(hit, list):
            return tuple(hit)
        if isinstance(hit, dict) and time.time() - hit.get("miss_at", 0) < MISS_TTL_S:
            return None  # recent confirmed miss (legacy `null` entries are treated as expired)
        loc = None
        try:
            from geopy.geocoders import Nominatim
            for query in (phrase, f"{phrase}, Guwahati"):
                wait = 1.1 - (time.time() - _last_nominatim_call)  # Nominatim usage policy: max 1 request/second
                if wait > 0:
                    time.sleep(wait)
                left = None if deadline is None else deadline - time.monotonic()
                if left is not None and left < 1.0:
                    return None  # time budget used up: not a real miss, so nothing is cached
                geo = Nominatim(user_agent=settings.geocode_user_agent,
                                timeout=settings.geocode_timeout_s if left is None else min(settings.geocode_timeout_s, left))
                _last_nominatim_call = time.time()
                loc = geo.geocode(
                    query,
                    viewbox=[(settings.bbox_south, settings.bbox_west), (settings.bbox_north, settings.bbox_east)],
                    bounded=True, country_codes="in", exactly_one=True,
                )
                if loc is not None:
                    break
        except Exception:
            return None  # offline / rate limited: do NOT cache, try again next time
        if loc is None:
            cache[key] = {"miss_at": time.time()}
            _cache_save(settings.geocode_cache_path, cache)
            return None
        raw = getattr(loc, "raw", {}) or {}
        precise = raw.get("class") in _PRECISE_CLASSES or raw.get("addresstype") in _PRECISE_CLASSES
        result = (float(loc.latitude), float(loc.longitude), 150.0 if precise else 700.0)
        cache[key] = list(result)
        _cache_save(settings.geocode_cache_path, cache)
        return result


def make_default_geocoder(settings: Settings) -> Callable[[str], Optional[Tuple[float, float, float]]]:
    """OSM first (precise landmarks), gazetteer as fallback and as a sanity check on OSM answers."""
    deadline = time.monotonic() + settings.geocode_budget_s   # one message: online lookups share this budget

    def geocode(query: str):
        phrase = query[: -len(GEO_SUFFIX)] if query.endswith(GEO_SUFFIX) else query
        anchors = [a for a in (gazetteer.lookup(n) for n, _, _ in gazetteer.find_places(phrase)) if a]
        anchors = [a for a in anchors if a[0] != "guwahati"]

        live = _nominatim(phrase, settings, deadline) if settings.geocode_online and time.monotonic() < deadline else None
        if live:
            # A result far from a locality named in the same sentence is a mis-hit (same-name place elsewhere).
            if not anchors or min(haversine_m(live[0], live[1], a[1], a[2]) - a[3] for a in anchors) <= 2500:
                return live

        known = gazetteer.lookup(phrase)
        if known:
            return known[1], known[2], known[3]
        return None
    return geocode


def resolve_location(
    incident: ParsedIncident,
    settings: Optional[Settings] = None,
    geocoder: Optional[Callable[[str], Optional[Tuple]]] = None,
) -> TriageResult:
    """Validated location for an incident.

    1. Coordinates written in the SOS (both inside the Guwahati bounding box) are trusted.
    2. Otherwise the place name is geocoded, trying the most specific phrase first.
    3. Otherwise the location is 'unknown'. No default point is ever invented.

    `geocoder(query) -> (lat, lon[, uncertainty_m]) | None` can be injected (tests, other providers).
    """
    settings = settings or get_settings()
    lat, lon = incident.latitude, incident.longitude
    if lat is not None and lon is not None and settings.in_bbox(lat, lon):
        return TriageResult(incident=incident, latitude=lat, longitude=lon, location_source="message",
                            uncertainty_m=0.0, location_label=incident.location_text)

    geocode = geocoder or make_default_geocoder(settings)
    for phrase in place_queries(incident.location_text):
        try:
            hit = geocode(f"{phrase}{GEO_SUFFIX}")
        except Exception:
            continue
        if not hit:
            continue
        glat, glon = float(hit[0]), float(hit[1])
        if not settings.in_bbox(glat, glon):
            continue
        unc = float(hit[2]) if len(hit) > 2 and hit[2] is not None else 300.0
        return TriageResult(incident=incident, latitude=glat, longitude=glon, location_source="geocoded",
                            uncertainty_m=unc, location_label=phrase)

    return TriageResult(incident=incident, latitude=None, longitude=None, location_source="unknown")
