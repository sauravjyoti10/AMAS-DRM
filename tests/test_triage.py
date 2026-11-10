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
