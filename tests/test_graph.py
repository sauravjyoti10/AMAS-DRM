"""Integration tests for the LangGraph multi-agent orchestrator."""
import pytest
from unittest.mock import MagicMock, patch

from app.graph import apply_manual_location, dispatch, orchestrator, routing_node
from app.hazards import HazardStore
from app.routing import NoRouteError
from app.schemas import HazardCreate, ParsedIncident, TriageResult


def triaged(severity="HIGH", lat=26.1750, lon=91.7750, source="geocoded", qty=10) -> TriageResult:
    inc = ParsedIncident(
        summary="test", severity=severity, casualties=0, location_text="Zoo Road",
        needed_resources=[{"item_name": "Drinking Water", "quantity": qty}],
    )
    return TriageResult(incident=inc, latitude=lat, longitude=lon, location_source=source, uncertainty_m=100.0)


def fake_route(distance=1200.0):
    r = MagicMock()
    r.distance_m, r.travel_time_s, r.node_count = distance, 180.0, 15
    return r


def start_state(text="Need 10 water bottles near Zoo Road. Moderate flooding."):
    return {"raw_sos": text, "incident": None, "allocation": None, "route": None,
            "needs_human_verification": False, "status": "pending", "error": None, "warnings": []}


@pytest.fixture
def no_hazards():
    with patch("app.graph.get_hazard_store", return_value=HazardStore()) as p:
        yield p.return_value


@patch("app.graph.run_triage")
@patch("app.graph.resolve_location")
@patch("app.graph.RoadNetwork.from_graphml")
def test_full_agent_pipeline_success(mock_from_graphml, mock_resolve, mock_triage, no_hazards):
    """Non-critical incident: automatic allocation and routing."""
    mock_triage.return_value = MagicMock()
    mock_resolve.return_value = triaged("HIGH")
    mock_net = MagicMock()
    mock_net.route.return_value = fake_route()
    mock_from_graphml.return_value = mock_net

    final = orchestrator.invoke(start_state())

    assert final["status"] == "completed"
    assert final["incident"]["severity"] == "HIGH"
    assert final["incident"]["latitude"] == 26.1750 and final["incident"]["location_source"] == "geocoded"
    assert final["allocation"] is not None
    assert final["route"]["distance_m"] == 1200.0
    assert final["route"]["depot_id"] in {"Depot_ZooRoad", "Depot_Dispur"}


@patch("app.graph.run_triage")
@patch("app.graph.resolve_location")
def test_human_in_the_loop_flag_for_critical_incident(mock_resolve, mock_triage):
    """CRITICAL incidents halt at the Human-in-the-Loop checkpoint."""
    mock_triage.return_value = MagicMock()
    mock_resolve.return_value = triaged("CRITICAL", qty=5)

    final = orchestrator.invoke(start_state("CRITICAL EMERGENCY: 5 casualties trapped near Chandmari!"))

    assert final["status"] == "triaged"
    assert final["needs_human_verification"] is True
    assert final["allocation"] is None
    assert final["route"] is None


@patch("app.graph.run_triage")
@patch("app.graph.resolve_location")
def test_unknown_location_stops_for_a_human_pin(mock_resolve, mock_triage):
    """No trustworthy coordinates: never invent a point, ask the dispatcher to pin it."""
    mock_triage.return_value = MagicMock()
    mock_resolve.return_value = triaged("HIGH", lat=None, lon=None, source="unknown")

    final = orchestrator.invoke(start_state("Help, flooding somewhere"))

    assert final["status"] == "triaged"
    assert final["needs_human_verification"] is True
    assert final["incident"]["latitude"] is None
    assert any("Pin it on the map" in w for w in final["warnings"])


@patch("app.graph.RoadNetwork.from_graphml")
def test_manual_pin_then_dispatch_routes_the_incident(mock_from_graphml, no_hazards):
    net = MagicMock()
    net.route.return_value = fake_route(2500.0)
    mock_from_graphml.return_value = net
    state = {"raw_sos": "x", "status": "triaged", "needs_human_verification": True,
             "incident": {"severity": "HIGH", "latitude": None, "longitude": None, "needed_resources": []}}

    state = apply_manual_location(state, 26.125, 91.8108)
    assert state["incident"]["location_source"] == "manual"
    out = dispatch(state)

    assert out["status"] == "completed" and out["needs_human_verification"] is False
    assert out["route"]["distance_m"] == 2500.0


def test_manual_pin_outside_guwahati_is_rejected():
    with pytest.raises(ValueError):
        apply_manual_location({"incident": {}}, 28.6, 77.2)


@patch("app.graph.RoadNetwork.from_graphml")
def test_hazards_are_passed_to_the_router_except_the_one_around_the_incident(mock_from_graphml):
    store = HazardStore()
    store.add(HazardCreate(name="at incident", center={"lat": 26.1750, "lon": 91.7750}, radius_m=200))
    store.add(HazardCreate(name="underpass", center={"lat": 26.1600, "lon": 91.7800}, radius_m=200))
    net = MagicMock()
    net.route.return_value = fake_route()
    mock_from_graphml.return_value = net
    state = {"incident": {"latitude": 26.1750, "longitude": 91.7750}, "allocation": {"INC_1": {"Depot_Dispur": 5}}}

    with patch("app.graph.get_hazard_store", return_value=store):
        out = routing_node(state)

    assert out["status"] == "completed"
    assert out["route"]["depot_id"] == "Depot_Dispur"            # allocated depot goes first
    assert out["route"]["hazards_avoided"] == ["underpass"]
    assert out["route"]["hazards_ignored"] == ["at incident"]
    first_call = net.route.call_args_list[0]
    assert [h.name for h in first_call.kwargs["hazards"]] == ["underpass"]


@patch("app.graph.RoadNetwork.from_graphml")
def test_routing_fails_cleanly_when_hazards_cut_off_every_depot(mock_from_graphml, no_hazards):
    net = MagicMock()
    net.route.side_effect = NoRouteError("hazard zones block every road")
    mock_from_graphml.return_value = net
    state = {"incident": {"latitude": 26.125, "longitude": 91.8108}, "allocation": {"INC_1": {}}}

    out = routing_node(state)

    assert out["status"] == "failed" and "No safe route" in out["error"]


@patch("app.graph.RoadNetwork.from_graphml", side_effect=FileNotFoundError("Road map 'x' not found. Run: python -m scripts.download_map"))
def test_missing_map_file_gives_a_clear_error(_):
    out = routing_node({"incident": {"latitude": 26.125, "longitude": 91.8108}, "allocation": {"INC_1": {}}})
    assert out["status"] == "failed" and "download_map" in out["error"]
