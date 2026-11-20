
"""Relief depots: single source of truth for the allocator, router and dashboard."""
from typing import List

from app.allocation import Depot

DEPOTS: List[Depot] = [
    Depot(
        id="Depot_ZooRoad",
        name="Zoo Road Central Depot",
        capacity=50,
        lat=26.1750,
        lon=91.7750,
        inventory={
            "Inflatable Rafts": 8,
            "First Aid Kits": 10,
            "Food Packets": 12,
            "Drinking Water": 12,
            "Emergency Medical Kits": 8,
        },
    ),
    Depot(
        id="Depot_Dispur",
        name="Dispur Emergency Depot",
        capacity=50,
        lat=26.1433,
        lon=91.7898,
        inventory={
            "Inflatable Rafts": 6,
            "First Aid Kits": 12,
            "Food Packets": 12,
            "Drinking Water": 12,
            "Emergency Medical Kits": 8,
        },
    ),
]
