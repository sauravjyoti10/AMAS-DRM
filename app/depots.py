"""Relief depots: single source of truth for the allocator, the router and the dashboard."""
from typing import List

from app.allocation import Depot

DEPOTS: List[Depot] = [
    Depot(id="Depot_ZooRoad", name="Zoo Road Central Depot", capacity=50, lat=26.1750, lon=91.7750),
    Depot(id="Depot_Dispur", name="Dispur Emergency Depot", capacity=50, lat=26.1433, lon=91.7898),
]
