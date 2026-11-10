"""Stateful Multi-Agent Orchestrator for Disaster & Resource Management."""
from typing import TypedDict, Dict, Any, Optional
from langgraph.graph import StateGraph, END

from app.triage import run_triage, resolve_location
from app.allocation import optimize_allocation, Depot, IncidentDemand
from app.routing import RoadNetwork, get_nearest_depot
from app.config import get_settings


class AgentState(TypedDict):
    raw_sos: str
    incident: Optional[Dict[str, Any]]
    allocation: Optional[Dict[str, Dict[str, int]]]
    route: Optional[Dict[str, Any]]
    needs_human_verification: bool
    status: str
    error: Optional[str]


def triage_node(state: AgentState) -> Dict[str, Any]:
    try:
        parsed = run_triage(state["raw_sos"])
        resolved = resolve_location(parsed)
        is_critical = resolved.severity == "CRITICAL"
        
        return {
            "incident": resolved.model_dump(),
            "needs_human_verification": is_critical,
            "status": "triaged",
            "error": None
        }
    except Exception as e:
        return {"status": "failed", "error": f"Triage failed: {str(e)}"}


def allocation_node(state: AgentState) -> Dict[str, Any]:
    incident_data = state.get("incident")
    if not incident_data:
        return {"status": "failed", "error": "No incident data found for allocation"}

    depots = [
        Depot(id="Depot_ZooRoad", capacity=50, lat=26.1750, lon=91.7750),
        Depot(id="Depot_Dispur", capacity=50, lat=26.1433, lon=91.7898),
    ]

    severity_weights = {"LOW": 1.0, "MEDIUM": 2.5, "HIGH": 5.0, "CRITICAL": 10.0}
    severity_score = severity_weights.get(incident_data.get("severity", "MEDIUM"), 2.5)

    # Ensure coordinates exist
    lat = incident_data.get("latitude")
    lon = incident_data.get("longitude")
    if not lat or not lon:
        return {"status": "failed", "error": "Coordinates missing for allocation"}

    inc_demand = IncidentDemand(
        id="INC_1",
        severity_score=severity_score,
        demand=max(1, sum(item.get("quantity", 1) for item in incident_data.get("needed_resources", []))),
        lat=lat,
        lon=lon,
    )

    distances = {("INC_1", d.id): 5.0 for d in depots}
    plan = optimize_allocation([inc_demand], depots, distances)

    return {"allocation": plan, "status": "allocated", "error": None}


def routing_node(state: AgentState) -> Dict[str, Any]:
    incident_data = state.get("incident")
    allocation = state.get("allocation")

    if not incident_data or not allocation:
        return {"status": "failed", "error": "Missing allocation or incident data for routing"}

    dest_lat = incident_data.get("latitude")
    dest_lon = incident_data.get("longitude")

    if not dest_lat or not dest_lon:
        return {"status": "failed", "error": "Unresolved target location coordinates"}

    try:
        net = RoadNetwork.from_graphml(get_settings().graph_path)
        
        # 🧠 Automatically picks the closest depot (Dispur vs. Zoo Road)
        depot_lat, depot_lon = get_nearest_depot(dest_lat, dest_lon)
        
        route_res = net.route(depot_lat, depot_lon, dest_lat, dest_lon)

        return {
            "route": {
                "distance_m": route_res.distance_m,
                "travel_time_s": route_res.travel_time_s,
                "node_count": route_res.node_count,
                "path_coordinates": route_res.path_coordinates,
            },
            "status": "completed",
            "error": None
        }
    except Exception as e:
        return {"status": "failed", "error": f"Routing failed: {str(e)}"}


def route_after_triage(state: AgentState) -> str:
    # 1. Stop immediately if Triage crashed (e.g., Gemini API error)
    if state.get("status") == "failed":
        return "end_graph"
    # 2. Pause if it's a critical incident
    if state.get("needs_human_verification"):
        return "pause_for_human"
    # 3. Otherwise, proceed normally
    return "proceed_to_allocation"

def route_after_allocation(state: AgentState) -> str:
    # Stop if Allocation failed (e.g., missing coordinates)
    if state.get("status") == "failed":
        return "end_graph"
    return "proceed_to_routing"

workflow = StateGraph(AgentState)

workflow.add_node("triage", triage_node)
workflow.add_node("allocation", allocation_node)
workflow.add_node("routing", routing_node)

workflow.set_entry_point("triage")

# Strict routing after Triage
workflow.add_conditional_edges(
    "triage",
    route_after_triage,
    {
        "end_graph": END,
        "pause_for_human": END,
        "proceed_to_allocation": "allocation",
    },
)

# Strict routing after Allocation (Replaces the old standard edge)
workflow.add_conditional_edges(
    "allocation",
    route_after_allocation,
    {
        "end_graph": END,
        "proceed_to_routing": "routing",
    }
)

workflow.add_edge("routing", END)

orchestrator = workflow.compile()