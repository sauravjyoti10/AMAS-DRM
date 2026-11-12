"""Typed contracts shared by every agent (PPT Gap 1: typed information extraction)."""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, model_validator

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
        default=None,
        description="Place name exactly as written in the message, including the landmark "
                    "(for example 'Khanapara bus stand'). Null if no place is mentioned.",
    )
    latitude: Optional[float] = Field(
        default=None, description="Only if explicitly stated in the message, else null"
    )
    longitude: Optional[float] = Field(
        default=None, description="Only if explicitly stated in the message, else null"
    )
    needed_resources: List[ResourceRequirement] = Field(default_factory=list)


# message  = coordinates were written in the SOS text
# geocoded = looked up from the place name (OpenStreetMap or the built-in gazetteer)
# manual   = a dispatcher pinned the location on the map
# unknown  = nothing trustworthy found; a human must place the pin
LocationSource = Literal["message", "geocoded", "manual", "unknown"]


class TriageResult(BaseModel):
    """Triage output: the parsed incident plus a validated location (or none)."""
    incident: ParsedIncident
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_source: LocationSource
    # How far off the pin might be, in metres (0 = exact). None when the location is unknown.
    uncertainty_m: Optional[float] = None
    # The place name that was actually matched (e.g. "Khanapara"), for display and auditing.
    location_label: Optional[str] = None


# ---------- Routing (Step 3) ----------
class LatLon(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class HazardZone(BaseModel):
    """A blocked area (flood, landslide...) given as a polygon of lat/lon corners."""
    id: Optional[str] = None
    name: str = "hazard"
    polygon: List[LatLon] = Field(min_length=3)


class HazardCreate(BaseModel):
    """Create a hazard from either an explicit polygon or a centre point + radius."""
    name: str = "hazard"
    polygon: Optional[List[LatLon]] = Field(default=None, min_length=3)
    center: Optional[LatLon] = None
    radius_m: Optional[float] = Field(default=None, gt=0, le=10000)

    @model_validator(mode="after")
    def _needs_shape(self):
        if self.polygon is None and (self.center is None or self.radius_m is None):
            raise ValueError("give either 'polygon' or both 'center' and 'radius_m'")
        return self


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
