"""Integration tests for the LangGraph multi-agent orchestrator."""
import pytest
from unittest.mock import patch, MagicMock
from app.graph import orchestrator


@patch("app.graph.run_triage")
@patch("app.graph.resolve_location")
@patch("app.graph.RoadNetwork.from_graphml")
def test_full_agent_pipeline_success(mock_from_graphml, mock_resolve, mock_triage):
    """Test full pipeline flow for a non-critical incident (auto-allocation & routing)."""
    # 1. Mock Triage Output
    mock_triage.return_value = MagicMock()
    mock_resolve.return_value = MagicMock(
        severity="HIGH",
        latitude=26.1750,
        longitude=91.7750,
        needed_resources=[{"resource_type": "water", "quantity": 10}],
        model_dump=lambda: {
            "severity": "HIGH",
            "latitude": 26.1750,
            "longitude": 91.7750,
            "needed_resources": [{"resource_type": "water", "quantity": 10}]
        }
    )

    # 2. Mock Routing Network
    mock_net = MagicMock()
    mock_route_res = MagicMock()
    mock_route_res.distance_m = 1200.0
    mock_route_res.travel_time_s = 180.0
    mock_route_res.node_count = 15
    mock_net.route.return_value = mock_route_res
    mock_from_graphml.return_value = mock_net

    # 3. Execute Graph
    initial_state = {
        "raw_sos": "Need 10 water bottles near Zoo Road. Moderate flooding.",
        "incident": None,
        "allocation": None,
        "route": None,
        "needs_human_verification": False,
        "status": "pending",
        "error": None
    }
    
    final_state = orchestrator.invoke(initial_state)

    # Assertions
    assert final_state["status"] == "completed"
    assert final_state["incident"]["severity"] == "HIGH"
    assert final_state["allocation"] is not None
    assert final_state["route"]["distance_m"] == 1200.0


@patch("app.graph.run_triage")
@patch("app.graph.resolve_location")
def test_human_in_the_loop_flag_for_critical_incident(mock_resolve, mock_triage):
    """Test that CRITICAL incidents halt at the Human-in-the-Loop checkpoint."""
    mock_triage.return_value = MagicMock()
    mock_resolve.return_value = MagicMock(
        severity="CRITICAL",
        latitude=26.1750,
        longitude=91.7750,
        needed_resources=[{"resource_type": "medical_kit", "quantity": 5}],
        model_dump=lambda: {
            "severity": "CRITICAL",
            "latitude": 26.1750,
            "longitude": 91.7750,
            "needed_resources": [{"resource_type": "medical_kit", "quantity": 5}]
        }
    )

    initial_state = {
        "raw_sos": "CRITICAL EMERGENCY: 5 casualties trapped in building collapse near Chandmari!",
        "incident": None,
        "allocation": None,
        "route": None,
        "needs_human_verification": False,
        "status": "pending",
        "error": None
    }

    final_state = orchestrator.invoke(initial_state)

    # Graph should halt after triage before allocation/routing
    assert final_state["status"] == "triaged"
    assert final_state["needs_human_verification"] is True
    assert final_state["allocation"] is None
    assert final_state["route"] is None