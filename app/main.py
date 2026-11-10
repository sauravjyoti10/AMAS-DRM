"""FastAPI Server and WebSocket Gateway for AMAS-DRM."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json

from app.graph import orchestrator, AgentState

app = FastAPI(
    title="AMAS-DRM API",
    description="Autonomous Multi-Agent System for Disaster & Resource Management",
    version="1.0.0"
)

# Enable CORS for local React development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Connection Manager for WebSockets
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in self.active_connections:
            await connection.send_text(json.dumps(message))

manager = ConnectionManager()


class SOSRequest(BaseModel):
    raw_sos: str


class HITLApprovalRequest(BaseModel):
    state: Dict[str, Any]
    approved: bool


@app.get("/")
def read_root():
    return {"system": "AMAS-DRM", "status": "operational", "phase": "3 & 4"}


@app.post("/api/sos/process")
async def process_sos(request: SOSRequest):
    """Trigger the multi-agent pipeline for an incoming SOS message."""
    initial_state: AgentState = {
        "raw_sos": request.raw_sos,
        "incident": None,
        "allocation": None,
        "route": None,
        "needs_human_verification": False,
        "status": "pending",
        "error": None
    }
    
    result_state = orchestrator.invoke(initial_state)
    
    # Broadcast status change to connected UI clients
    await manager.broadcast({
        "event": "INCIDENT_PROCESSED",
        "data": result_state
    })
    
    return result_state


@app.post("/api/sos/approve")
async def approve_incident(request: HITLApprovalRequest):
    """Resume execution for an incident paused at the Human-in-the-Loop checkpoint."""
    if not request.approved:
        return {"status": "rejected", "message": "Dispatcher rejected allocation."}
    
    # 1. Grab the current state from the frontend
    state = request.state
    
    # 2. Clear the human check flag so it doesn't pause again
    state["needs_human_verification"] = False
    
    from app.graph import allocation_node, routing_node
    
    # 3. Manually run Allocation and MERGE the result into the state
    alloc_res = allocation_node(state)
    state.update(alloc_res)
    
    # Check if allocation failed before routing
    if state.get("status") == "failed":
        await manager.broadcast({"event": "DISPATCH_APPROVED", "data": state})
        return state

    # 4. Manually run Routing and MERGE the result into the state
    route_res = routing_node(state)
    state.update(route_res)
    
    # 5. Broadcast the final completed state back to the UI
    await manager.broadcast({
        "event": "DISPATCH_APPROVED",
        "data": state
    })
    
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