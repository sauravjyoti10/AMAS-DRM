"""Stateful Multi-Agent Orchestrator for Disaster & Resource Management.

Pipeline:  triage -> (human check for CRITICAL / unknown location) -> allocation -> routing
"""
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.allocation import IncidentDemand, optimize_allocation
from app.config import get_settings
from app.depots import DEPOTS
from app.geo import haversine_m
from app.hazards import get_hazard_store, split_by_destination
from app.routing import NoRouteError, OutOfCoverageError, RoadNetwork
from app.schemas import TriageResult
from app.triage import TriageError, resolve_location, rule_based_triage, run_triage

UNREACHABLE_KM = 9999.0  # a depot cut off by hazards gets a prohibitive distance, so it receives no stock
SEVERITY_WEIGHTS = {"LOW": 1.0, "MODERATE": 2.5, "HIGH": 5.0, "CRITICAL": 10.0}


class AgentState(TypedDict, total=False):
    raw_sos: str
    incident: Optional[Dict[str, Any]]
    allocation: Optional[Dict[str, Dict[str, int]]]
    route: Optional[Dict[str, Any]]
    needs_human_verification: bool
    status: str
    error: Optional[str]
    warnings: List[str]


# --------------------------------------------------------------------------- helpers
def _incident_dict(result: TriageResult) -> Dict[str, Any]:
    inc = result.incident.model_dump()
    inc.update(
        latitude=result.latitude,
        longitude=result.longitude,
        location_source=result.location_source,
        uncertainty_m=result.uncertainty_m,
        location_label=result.location_label,
    )
    return inc


def _load_network():
    """(network | None, warning | None)."""
    try:
        return RoadNetwork.from_graphml(get_settings().graph_path), None
    except FileNotFoundError as exc:
        return None, str(exc)


def apply_manual_location(state: Dict[str, Any], lat: float, lon: float) -> Dict[str, Any]:
    """Dispatcher pinned the incident on the map. Raises ValueError when the pin is outside Guwahati."""
    if not get_settings().in_bbox(lat, lon):
        raise ValueError("Pinned location is outside the Guwahati service area.")
    inc = dict(state.get("incident") or {})
    inc.update(latitude=lat, longitude=lon, location_source="manual",
               uncertainty_m=0.0, location_label="Pinned by dispatcher")
    state["incident"] = inc
    return state


# --------------------------------------------------------------------------- nodes
def triage_node(state: AgentState) -> Dict[str, Any]:
    warnings: List[str] = list(state.get("warnings") or [])
    try:
        try:
            parsed = run_triage(state["raw_sos"])
        except TriageError as exc:
            warnings.append(f"Gemini triage failed, used the rule-based parser instead ({exc}).")
            parsed = rule_based_triage(state["raw_sos"])

        result = resolve_location(parsed)
        incident = _incident_dict(result)
        if result.location_source == "unknown":
            warnings.append("Location could not be resolved. Pin it on the map to continue.")

        needs_human = incident["severity"] == "CRITICAL" or result.location_source == "unknown"
        return {
            "incident": incident,
            "needs_human_verification": needs_human,
            "status": "triaged",
            "error": None,
            "warnings": warnings,
        }
    except Exception as e:
        return {"status": "failed", "error": f"Triage failed: {str(e)}", "warnings": warnings}


def _depot_distances_km(net, lat: float, lon: float, avoid) -> Dict[str, float]:
    """Road distance (km) from each depot to the incident, honouring hazards."""
    settings = get_settings()
    out: Dict[str, float] = {}
    for depot in DEPOTS:
        if net is None:
            out[depot.id] = float(haversine_m(depot.lat, depot.lon, lat, lon)) * 1.35 / 1000.0
            continue
        try:
            res = net.route(depot.lat, depot.lon, lat, lon, hazards=avoid, max_snap_m=settings.max_snap_m)
            out[depot.id] = res.distance_m / 1000.0
        except (NoRouteError, OutOfCoverageError):
            out[depot.id] = UNREACHABLE_KM
    return out


def allocation_node(state: AgentState) -> Dict[str, Any]:
    incident_data = state.get("incident")
    if not incident_data:
        return {"status": "failed", "error": "No incident data found for allocation"}

    lat, lon = incident_data.get("latitude"), incident_data.get("longitude")
    if lat is None or lon is None:
        return {"status": "failed", "error": "Coordinates missing for allocation"}

    net, warning = _load_network()
    warnings = list(state.get("warnings") or [])
    if warning and warning not in warnings:
        warnings.append(warning + " (depot distances are straight-line estimates)")
    avoid, _ = split_by_destination(get_hazard_store().list(), lat, lon)

    inc_demand = IncidentDemand(
        id="INC_1",
        severity_score=SEVERITY_WEIGHTS.get(incident_data.get("severity", "MODERATE"), 2.5),
        demand=max(1, sum(item.get("quantity", 1) for item in incident_data.get("needed_resources", []))),
        lat=lat,
        lon=lon,
    )
    km = _depot_distances_km(net, lat, lon, avoid)
    plan = optimize_allocation([inc_demand], DEPOTS, {("INC_1", d.id): km[d.id] for d in DEPOTS})

    return {"allocation": plan, "status": "allocated", "error": None, "warnings": warnings}


def routing_node(state: AgentState) -> Dict[str, Any]:
    incident_data = state.get("incident")
    allocation = state.get("allocation")
    if not incident_data or allocation is None:
        return {"status": "failed", "error": "Missing allocation or incident data for routing"}

    dest_lat, dest_lon = incident_data.get("latitude"), incident_data.get("longitude")
    if dest_lat is None or dest_lon is None:
        return {"status": "failed", "error": "Unresolved target location coordinates"}

    net, warning = _load_network()
    if net is None:
        return {"status": "failed", "error": f"Routing failed: {warning}"}

    settings = get_settings()
    avoid, ignored = split_by_destination(get_hazard_store().list(), dest_lat, dest_lon)
    plan = allocation.get("INC_1", {})
    # Depots that were allocated stock come first (largest share first), then nearest as the tie-break.
    depots = sorted(DEPOTS, key=lambda d: (-plan.get(d.id, 0), haversine_m(d.lat, d.lon, dest_lat, dest_lon)))

    last_error: Optional[Exception] = None
    for depot in depots:
        try:
            res = net.route(depot.lat, depot.lon, dest_lat, dest_lon,
                            hazards=avoid, max_snap_m=settings.max_snap_m)
        except (NoRouteError, OutOfCoverageError) as exc:
            last_error = exc
            continue

        route: Dict[str, Any] = {
            "depot_id": depot.id,
            "depot_name": depot.name or depot.id,
            "origin": {"lat": depot.lat, "lon": depot.lon},
            "distance_m": res.distance_m,
            "travel_time_s": res.travel_time_s,
            "node_count": res.node_count,
            "origin_snap_m": res.origin_snap_m,
            "destination_snap_m": res.destination_snap_m,
            "blocked_edges": res.blocked_edges,
            "hazard_safe": res.hazard_safe,
            "path_coordinates": res.path_coordinates,
            "hazards_avoided": [h.name for h in avoid],
            "hazards_ignored": [h.name for h in ignored],
        }
        if avoid:  # also show what the route would have been without hazards, so the detour is visible
            try:
                base = net.route(depot.lat, depot.lon, dest_lat, dest_lon, max_snap_m=settings.max_snap_m)
                route.update(baseline_distance_m=base.distance_m,
                             baseline_travel_time_s=base.travel_time_s,
                             baseline_path_coordinates=base.path_coordinates)
            except (NoRouteError, OutOfCoverageError):
                pass
        return {"route": route, "status": "completed", "error": None}

    return {"status": "failed", "route": None,
            "error": f"No safe route from any depot: {last_error}"}


def dispatch(state: Dict[str, Any]) -> Dict[str, Any]:
    """Run allocation then routing for an incident released from the human checkpoint."""
    state = dict(state)
    state["needs_human_verification"] = False
    for node in (allocation_node, routing_node):
        state.update(node(state))
        if state.get("status") == "failed":
            break
    return state


# --------------------------------------------------------------------------- graph wiring
def route_after_triage(state: AgentState) -> str:
    if state.get("status") == "failed":
        return "end_graph"
    if state.get("needs_human_verification"):
        return "pause_for_human"
    return "proceed_to_allocation"


def route_after_allocation(state: AgentState) -> str:
    if state.get("status") == "failed":
        return "end_graph"
    return "proceed_to_routing"


workflow = StateGraph(AgentState)
workflow.add_node("triage", triage_node)
workflow.add_node("allocation", allocation_node)
workflow.add_node("routing", routing_node)
workflow.set_entry_point("triage")

workflow.add_conditional_edges(
    "triage",
    route_after_triage,
    {"end_graph": END, "pause_for_human": END, "proceed_to_allocation": "allocation"},
)
workflow.add_conditional_edges(
    "allocation",
    route_after_allocation,
    {"end_graph": END, "proceed_to_routing": "routing"},
)
workflow.add_edge("routing", END)

orchestrator = workflow.compile()
