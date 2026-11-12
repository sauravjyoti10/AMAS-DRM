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
MAX_ATTEMPTS = 2

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
        client = genai.Client(api_key=settings.gemini_api_key)

    last_error: Optional[Exception] = None
    for _ in range(MAX_ATTEMPTS):
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
    raise TriageError(f"Triage failed after {MAX_ATTEMPTS} attempts: {last_error}")


# ---- rule-based fallback (works offline, no API key) ----
_NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
              "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_PEOPLE = (r"(?:casualt\w*|people|persons?|travell?ers|passengers|residents|villagers|victims|"
           r"children|kids|students|families|workers|injured)")
_LANDMARK_WORDS = (r"bus\s*stand|bus\s*stop|bus\s*terminus|bus\s*station|isbt|tiniali|chariali|chowk|"
                   r"junction|flyover|bridge|market|bazaar|bazar|station|gate|petrol\s*pump|hospital|"
                   r"school|college|temple|stadium|ground|park|colony|road|path|lane")
_CRITICAL = ("critical", "collapse", "landslide", "trapped", "stranded", "submerged", "drown",
             "rising", "rooftop", "life-threatening", "immediately")
_HIGH = ("flood", "waterlogging", "injur", "overflow", "fire", "washed away")
_MODERATE = ("electricity", "power cut", "knee-deep", "blocked", "fallen tree", "tree fell")


def parse_coordinates(text: str) -> Optional[Tuple[float, float]]:
    """'26.1750 N, 91.7750 E' or '26.175, 91.775' -> (lat, lon)."""
    m = re.search(r"(-?\d{1,2}\.\d{2,})\s*°?\s*([NS])?\s*[,;/ ]\s*(-?\d{2,3}\.\d{2,})\s*°?\s*([EW])?", text, re.I)
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(3))
    if (m.group(2) or "").upper() == "S":
        lat = -abs(lat)
    if (m.group(4) or "").upper() == "W":
        lon = -abs(lon)
    return lat, lon


def _count_people(raw: str) -> int:
    m = re.search(rf"\b(\d{{1,4}})\s+(?:more\s+|injured\s+|trapped\s+|stranded\s+|elderly\s+)?{_PEOPLE}", raw, re.I)
    if m:
        return int(m.group(1))
    m = re.search(rf"\b({'|'.join(_NUM_WORDS)})\s+(?:more\s+|injured\s+|trapped\s+)?{_PEOPLE}", raw, re.I)
    return _NUM_WORDS[m.group(1).lower()] if m else 0


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


def rule_based_triage(raw_sos: str) -> ParsedIncident:
    """Keyword/regex triage used when Gemini is not configured or fails."""
    raw = raw_sos.lower()
    casualties = _count_people(raw_sos)

    if any(w in raw for w in _CRITICAL) or casualties >= 3:
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


def _nominatim(phrase: str, settings: Settings) -> Optional[Tuple[float, float, float]]:
    """OpenStreetMap lookup restricted to the Guwahati bounding box. Cached on disk. -> (lat, lon, uncertainty_m)"""
    global _last_nominatim_call
    key = gazetteer.normalize(phrase)
    with _geo_lock:
        cache = _cache_load(settings.geocode_cache_path)
        if key in cache:
            hit = cache[key]
            return tuple(hit) if hit else None
        try:
            from geopy.geocoders import Nominatim
            wait = 1.1 - (time.time() - _last_nominatim_call)  # Nominatim usage policy: max 1 request/second
            if wait > 0:
                time.sleep(wait)
            _last_nominatim_call = time.time()
            geo = Nominatim(user_agent=settings.geocode_user_agent, timeout=settings.geocode_timeout_s)
            loc = geo.geocode(
                f"{phrase}{GEO_SUFFIX}",
                viewbox=[(settings.bbox_south, settings.bbox_west), (settings.bbox_north, settings.bbox_east)],
                bounded=True, country_codes="in", exactly_one=True,
            )
        except Exception:
            return None  # offline / rate limited: do NOT cache, try again next time
        if loc is None:
            cache[key] = None
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
    def geocode(query: str):
        phrase = query[: -len(GEO_SUFFIX)] if query.endswith(GEO_SUFFIX) else query
        anchors = [a for a in (gazetteer.lookup(n) for n, _, _ in gazetteer.find_places(phrase)) if a]
        anchors = [a for a in anchors if a[0] != "guwahati"]

        live = _nominatim(phrase, settings) if settings.geocode_online else None
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
