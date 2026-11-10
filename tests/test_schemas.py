import json
import pytest
from pydantic import ValidationError
from app.schemas import ParsedIncident, ResourceRequirement


def test_valid_incident():
    inc = ParsedIncident(
        summary="Flooding at Zoo Road", severity="CRITICAL", casualties=4,
        needed_resources=[ResourceRequirement(item_name="First Aid Kits", quantity=10)],
    )
    assert inc.latitude is None  # coordinates optional, never invented


def test_unknown_item_rejected():
    with pytest.raises(ValidationError):
        ResourceRequirement(item_name="Spaceship", quantity=1)


def test_negative_casualties_rejected():
    with pytest.raises(ValidationError):
        ParsedIncident(summary="x", severity="LOW", casualties=-1)


def test_bad_severity_rejected():
    with pytest.raises(ValidationError):
        ParsedIncident(summary="x", severity="MEH", casualties=0)


def test_schema_has_no_gemini_unsupported_keywords():
    schema = json.dumps(ParsedIncident.model_json_schema())
    assert "exclusiveMinimum" not in schema
    assert "exclusiveMaximum" not in schema
