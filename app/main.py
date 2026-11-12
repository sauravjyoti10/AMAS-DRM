"""FastAPI Server and WebSocket Gateway for AMAS-DRM."""
import json
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.depots import DEPOTS
from app.graph import AgentState, apply_manual_location, dispatch, orchestrator, routing_node
from app.hazards import get_hazard_store
from app.routing import NoRouteError, OutOfCoverageError, RoadNetwork
from app.schemas import HazardCreate, RouteRequest, SOSRequest
from app.triage import TriageError, resolve_location, run_triage

app = FastAPI(
    title="AMAS-DRM API",
    description="Autonomous Multi-Agent System for Disaster & Resource Management",
    version="1.1.0",
)

# Enable CORS for local React development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    """WebSocket fan-out. A dead client must never break a broadcast."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        payload = json.dumps(message)
        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


class ProcessRequest(BaseModel):
    raw_sos: str = Field(min_length=3, max_length=2000)


class HITLApprovalRequest(BaseModel):
    state: Dict[str, Any]
    approved: bool
    # Optional: dispatcher-pinned location (required when the location could not be resolved).
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class RerouteRequest(BaseModel):
    state: Dict[str, Any]


def _hazards_payload() -> List[Dict[str, Any]]:
    return [h.model_dump() for h in get_hazard_store().list()]


@app.get("/")
def read_root():
    return {"system": "AMAS-DRM", "status": "operational", "phase": "3 & 4"}


@app.get("/health")
def health():
    settings = get_settings()
    try:
        net = RoadNetwork.from_graphml(settings.graph_path)
        s, w, n, e = net.bounds()
        road_map = {"loaded": True, "nodes": net.graph.number_of_nodes(),
                    "bounds": {"south": s, "west": w, "north": n, "east": e}}
    except FileNotFoundError as exc:
        road_map = {"loaded": False, "error": str(exc)}
    return {"status": "ok", "road_map": road_map, "hazards": len(get_hazard_store().list())}


@app.get("/api/depots")
def list_depots():
    return [d.model_dump() for d in DEPOTS]


# ---------------------------------------------------------------- hazards
@app.get("/api/hazards")
def list_hazards():
    return _hazards_payload()


@app.post("/api/hazards")
async def add_hazard(request: HazardCreate):
    zone = get_hazard_store().add(request)
    await manager.broadcast({"event": "HAZARDS_UPDATED", "data": _hazards_payload()})
    return zone


@app.delete("/api/hazards/{hazard_id}")
async def delete_hazard(hazard_id: str):
    if not get_hazard_store().remove(hazard_id):
        raise HTTPException(status_code=404, detail="Hazard not found")
    await manager.broadcast({"event": "HAZARDS_UPDATED", "data": _hazards_payload()})
    return {"status": "deleted", "id": hazard_id}


# ---------------------------------------------------------------- stand-alone triage / route (see api.http)
@app.post("/triage")
async def triage_only(request: SOSRequest):
    try:
        parsed = await run_in_threadpool(run_triage, request.sos_message)
    except TriageError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return await run_in_threadpool(resolve_location, parsed)


@app.post("/route")
async def route_only(request: RouteRequest):
    settings = get_settings()
    try:
        net = RoadNetwork.from_graphml(settings.graph_path)
        return await run_in_threadpool(
            net.route,
            request.origin.lat, request.origin.lon,
            request.destination.lat, request.destination.lon,
            request.hazards, settings.max_snap_m,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except OutOfCoverageError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except NoRouteError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


# ---------------------------------------------------------------- multi-agent pipeline
@app.post("/api/sos/process")
async def process_sos(request: ProcessRequest):
    """Trigger the multi-agent pipeline for an incoming SOS message."""
    initial_state: AgentState = {
        "raw_sos": request.raw_sos,
        "incident": None,
        "allocation": None,
        "route": None,
        "needs_human_verification": False,
        "status": "pending",
        "error": None,
        "warnings": [],
    }
    result_state = await run_in_threadpool(orchestrator.invoke, initial_state)
    await manager.broadcast({"event": "INCIDENT_PROCESSED", "data": result_state})
    return result_state


@app.post("/api/sos/approve")
async def approve_incident(request: HITLApprovalRequest):
    """Resume an incident paused at the Human-in-the-Loop checkpoint (optionally with a pinned location)."""
    if not request.approved:
        return {"status": "rejected", "message": "Dispatcher rejected allocation."}

    state = dict(request.state)
    if request.latitude is not None and request.longitude is not None:
        try:
            state = apply_manual_location(state, request.latitude, request.longitude)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    state = await run_in_threadpool(dispatch, state)
    await manager.broadcast({"event": "DISPATCH_APPROVED", "data": state})
    return state


@app.post("/api/sos/reroute")
async def reroute_incident(request: RerouteRequest):
    """Recompute the route for an already-dispatched incident (e.g. after hazards changed)."""
    state = dict(request.state)
    state.update(await run_in_threadpool(routing_node, state))
    await manager.broadcast({"event": "DISPATCH_APPROVED", "data": state})
    return state


@app.websocket("/ws/feed")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket feed for real-time situational dashboard updates."""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
