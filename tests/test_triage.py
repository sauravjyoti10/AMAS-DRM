import json
import pytest

from app.config import Settings
from app.schemas import ParsedIncident
from app.triage import TriageError, resolve_location, run_triage

VALID = {
    "summary": "Flooding near Zoo Road Tiniali",
    "severity": "CRITICAL",
    "casualties": 4,
    "location_text": "Zoo Road Tiniali",
    "latitude": 26.175,
    "longitude": 91.775,
    "needed_resources": [
        {"item_name": "First Aid Kits", "quantity": 10},
        {"item_name": "Inflatable Rafts", "quantity": 2},
    ],
}


class _Resp:
    def __init__(self, text):
        self.text = text


class _Models:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return _Resp(out)


class FakeClient:
    """Stands in for the Gemini client so tests cost no API calls."""
    def __init__(self, *outputs):
        self.models = _Models(outputs)


def incident(**overrides) -> ParsedIncident:
    return ParsedIncident(**{**VALID, **overrides})


# ---------- run_triage ----------
def test_run_triage_parses_valid_json():
    client = FakeClient(json.dumps(VALID))
    result = run_triage("sos", client=client, settings=Settings())
    assert result.casualties == 4
    assert result.needed_resources[0].item_name == "First Aid Kits"


def test_run_triage_retries_then_succeeds():
    client = FakeClient("not json", json.dumps(VALID))
    result = run_triage("sos", client=client, settings=Settings())
    assert result.severity == "CRITICAL"
    assert client.models.calls == 2


def test_run_triage_raises_after_retries():
    client = FakeClient("bad", RuntimeError("API down"))
    with pytest.raises(TriageError):
        run_triage("sos", client=client, settings=Settings())


def test_run_triage_rejects_unknown_item():
    bad = {**VALID, "needed_resources": [{"item_name": "Spaceship", "quantity": 1}]}
    client = FakeClient(json.dumps(bad), json.dumps(bad))
    with pytest.raises(TriageError):
        run_triage("sos", client=client, settings=Settings())


# ---------- resolve_location ----------
def test_coordinates_inside_guwahati_are_kept():
    res = resolve_location(incident(), settings=Settings())
    assert res.location_source == "message"
    assert (res.latitude, res.longitude) == (26.175, 91.775)


def test_out_of_area_coordinates_fall_back_to_geocoder():
    res = resolve_location(
        incident(latitude=28.6, longitude=77.2),  # Delhi: hallucinated
        settings=Settings(),
        geocoder=lambda q: (26.18, 91.78),
    )
    assert res.location_source == "geocoded"
    assert res.latitude == 26.18


def test_missing_coordinates_use_geocoder():
    res = resolve_location(
        incident(latitude=None, longitude=None),
        settings=Settings(),
        geocoder=lambda q: (26.18, 91.78),
    )
    assert res.location_source == "geocoded"


def test_geocoder_failure_gives_unknown():
    def boom(q):
        raise RuntimeError("no internet")

    res = resolve_location(
        incident(latitude=None, longitude=None), settings=Settings(), geocoder=boom
    )
    assert res.location_source == "unknown"
    assert res.latitude is None


def test_geocoded_point_outside_city_gives_unknown():
    res = resolve_location(
        incident(latitude=None, longitude=None),
        settings=Settings(),
        geocoder=lambda q: (10.0, 10.0),
    )
    assert res.location_source == "unknown"


# ---------- rule-based parser (no Gemini key) ----------
from app import triage as triage_mod
from app.triage import parse_coordinates, rule_based_triage

KHANAPARA_SOS = (
    '"We are stuck near the Khanapara bus stand. Flash floods have completely submerged the main road '
    'and water is rising fast. About 15 travelers are stranded on top of a bus stop roof. '
    'Please send inflatable rafts and drinking water immediately."'
)


def test_rule_based_keeps_the_place_named_in_the_sos():
    p = rule_based_triage(KHANAPARA_SOS)
    assert p.location_text == "Khanapara bus stand"      # was silently lost before, so the pin fell back to 'Guwahati'
    assert p.severity == "CRITICAL"
    assert p.casualties == 15
    items = {r.item_name: r.quantity for r in p.needed_resources}
    assert items["Inflatable Rafts"] == 2 and items["Drinking Water"] == 15


def test_run_triage_without_key_uses_rule_based():
    p = run_triage(KHANAPARA_SOS, settings=Settings(gemini_api_key=""))
    assert p.location_text == "Khanapara bus stand"


def test_parse_coordinates():
    assert parse_coordinates("Coordinates: 26.1750 N, 91.7750 E.") == (26.175, 91.775)
    assert parse_coordinates("no numbers here") is None


def test_rule_based_reads_coordinates_from_message():
    p = rule_based_triage("Flooding at 26.1750 N, 91.7750 E, 4 people injured")
    assert (p.latitude, p.longitude) == (26.175, 91.775)


# ---------- geocoding: no silent defaults, sanity guard on OSM answers ----------
OFFLINE = Settings(geocode_online=False)


def test_khanapara_resolves_to_khanapara_not_city_centre():
    res = resolve_location(rule_based_triage(KHANAPARA_SOS), settings=OFFLINE)
    assert res.location_source == "geocoded"
    assert (res.latitude, res.longitude) == pytest.approx((26.125, 91.8108), abs=0.001)
    assert res.uncertainty_m == 700           # honest: locality-level, drawn as a circle on the map
    assert res.location_label == "Khanapara bus stand"


def test_unresolvable_place_is_unknown_not_a_default_point():
    res = resolve_location(incident(latitude=None, longitude=None, location_text="Atlantis Tower"),
                           settings=OFFLINE)
    assert res.location_source == "unknown"
    assert res.latitude is None and res.longitude is None


def test_no_location_text_is_unknown():
    res = resolve_location(incident(latitude=None, longitude=None, location_text=None), settings=OFFLINE)
    assert res.location_source == "unknown"


def test_longitude_outside_bbox_is_rejected_too():
    # The old code only checked latitude, so (26.175, 77.2) was accepted.
    res = resolve_location(incident(latitude=26.175, longitude=77.2), settings=OFFLINE)
    assert res.location_source != "message"


def test_osm_hit_far_from_the_named_locality_is_rejected(monkeypatch):
    # A same-name place 10 km away must not beat the gazetteer.
    monkeypatch.setattr(triage_mod, "_nominatim", lambda phrase, s: (26.20, 91.66, 150.0))
    res = resolve_location(incident(latitude=None, longitude=None, location_text="Khanapara bus stand"),
                           settings=Settings(geocode_online=True))
    assert (res.latitude, res.longitude) == pytest.approx((26.125, 91.8108), abs=0.001)


def test_precise_osm_hit_near_the_locality_is_kept(monkeypatch):
    monkeypatch.setattr(triage_mod, "_nominatim", lambda phrase, s: (26.1187, 91.8059, 150.0))
    res = resolve_location(incident(latitude=None, longitude=None, location_text="Khanapara bus stand"),
                           settings=Settings(geocode_online=True))
    assert (res.latitude, res.longitude) == (26.1187, 91.8059)
    assert res.uncertainty_m == 150.0


def test_parse_coordinates_does_not_mistake_the_next_word_for_a_hemisphere():
    # Found by the evaluation: "91.7712 water" was read as 91.7712 W (west), giving a negative longitude.
    assert parse_coordinates("Location 26.1595, 91.7712 water rising") == (26.1595, 91.7712)
    assert parse_coordinates("at 26.14 South 91.80 East") is None or parse_coordinates("at 26.14 South 91.80 East")[1] > 0


def test_parse_coordinates_accepts_lat_lon_labels():
    assert parse_coordinates("Lat 26.1730 Lon 91.7730 flooded road") == (26.173, 91.773)
    assert parse_coordinates("latitude: 26.1730, longitude: 91.7730") == (26.173, 91.773)
    assert parse_coordinates("26.1450 N, 91.8020 E") == (26.145, 91.802)


# ---------- OpenStreetMap lookup wiring (geopy is faked, no internet) ----------
import sys
import types


class _FakeLoc:
    latitude, longitude, raw = 26.1186, 91.8149, {"class": "highway", "addresstype": "bus_stop"}


def _fake_geopy(monkeypatch, answers):
    queries = []

    class FakeNominatim:
        def __init__(self, **kw): pass
        def geocode(self, q, **kw):
            queries.append((q, kw))
            return answers.pop(0)

    mod = types.ModuleType("geopy.geocoders"); mod.Nominatim = FakeNominatim
    monkeypatch.setitem(sys.modules, "geopy", types.ModuleType("geopy"))
    monkeypatch.setitem(sys.modules, "geopy.geocoders", mod)
    monkeypatch.setattr(triage_mod.time, "sleep", lambda s: None)
    return queries


def test_nominatim_tries_the_bare_phrase_first_inside_the_guwahati_box(monkeypatch, tmp_path):
    queries = _fake_geopy(monkeypatch, [_FakeLoc()])
    s = Settings(geocode_cache_path=str(tmp_path / "c.json"))
    assert triage_mod._nominatim("Khanapara bus stand", s) == (26.1186, 91.8149, 150.0)
    assert queries[0][0] == "Khanapara bus stand"                 # no ", Guwahati, Assam, India" suffix
    assert queries[0][1]["bounded"] is True and queries[0][1]["country_codes"] == "in"


def test_nominatim_retries_with_city_name_and_remembers_misses_only_for_a_day(monkeypatch, tmp_path):
    queries = _fake_geopy(monkeypatch, [None, None, _FakeLoc()])
    s = Settings(geocode_cache_path=str(tmp_path / "c.json"))
    assert triage_mod._nominatim("Ganeshguri", s) is None
    assert [q for q, _ in queries] == ["Ganeshguri", "Ganeshguri, Guwahati"]
    assert triage_mod._nominatim("Ganeshguri", s) is None         # recent miss: no new request
    assert len(queries) == 2
    cache = triage_mod._cache_load(s.geocode_cache_path)
    cache["ganeshguri"]["miss_at"] -= 2 * 24 * 3600               # a miss older than the TTL is retried
    triage_mod._cache_save(s.geocode_cache_path, cache)
    assert triage_mod._nominatim("Ganeshguri", s) == (26.1186, 91.8149, 150.0)


def test_legacy_null_cache_entries_are_retried(monkeypatch, tmp_path):
    path = tmp_path / "c.json"
    path.write_text('{"khanapara bus stand": null}')
    _fake_geopy(monkeypatch, [_FakeLoc()])
    assert triage_mod._nominatim("Khanapara bus stand", Settings(geocode_cache_path=str(path))) is not None
