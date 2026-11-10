"""Typed contracts shared by every agent (PPT Gap 1: typed information extraction)."""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

# Closed vocabulary so LLM output always matches depot inventory keys.
ItemName = Literal["First Aid Kits", "Inflatable Rafts", "Food Packets", "Drinking Water"]
Severity = Literal["CRITICAL", "HIGH", "MODERATE", "LOW"]


class SOSRequest(BaseModel):
    sos_message: str = Field(..., min_length=5, max_length=2000)


class ResourceRequirement(BaseModel):
    item_name: ItemName = Field(description="Relief item needed")
    quantity: int = Field(ge=1, description="Quantity required")


class ParsedIncident(BaseModel):
    summary: str = Field(description="One-sentence summary of the incident")
    severity: Severity = Field(description="Urgency level")
    casualties: int = Field(ge=0, description="Number of injured or trapped people")
    location_text: Optional[str] = Field(
        default=None, description="Place name exactly as written in the message"
    )
    latitude: Optional[float] = Field(
        default=None, description="Only if explicitly stated in the message, else null"
    )
    longitude: Optional[float] = Field(
        default=None, description="Only if explicitly stated in the message, else null"
    )
    needed_resources: List[ResourceRequirement] = Field(default_factory=list)


LocationSource = Literal["message", "geocoded", "unknown"]


class TriageResult(BaseModel):
    """Triage output: the parsed incident plus a validated location (or none)."""
    incident: ParsedIncident
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_source: LocationSource


# ---------- Routing (Step 3) ----------
class LatLon(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class HazardZone(BaseModel):
    """A blocked area (flood, landslide...) given as a polygon of lat/lon corners."""
    name: str = "hazard"
    polygon: List[LatLon] = Field(min_length=3)


class RouteRequest(BaseModel):
    origin: LatLon
    destination: LatLon
    hazards: List[HazardZone] = Field(default_factory=list)


class RouteResult(BaseModel):
    distance_m: float
    travel_time_s: float
    node_count: int
    origin_snap_m: float          # how far the origin was from the nearest road node
    destination_snap_m: float
    blocked_edges: int            # road segments removed because they touch a hazard
    hazard_safe: bool             # True when the final path intersects no hazard polygon
    path_coordinates: List[List[float]]  # [[lat, lon], ...] following real road geometry
