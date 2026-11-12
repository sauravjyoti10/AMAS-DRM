"""Active hazard zones (flooded streets, landslides ...) that routes must stay out of."""
import json
import os
import threading
import uuid
from functools import lru_cache
from typing import List, Optional, Tuple

from app.config import get_settings
from app.geo import circle_polygon, point_in_polygon
from app.schemas import HazardCreate, HazardZone, LatLon


class HazardStore:
    """Thread-safe list of hazards, saved to a JSON file so they survive a server restart."""

    def __init__(self, path: Optional[str] = None):
        self._path = path
        self._lock = threading.Lock()
        self._items: List[HazardZone] = []
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self._items = [HazardZone(**h) for h in json.load(f)]
            except (OSError, ValueError, TypeError):
                self._items = []

    def _save(self) -> None:
        if not self._path:
            return
        try:
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump([h.model_dump() for h in self._items], f, indent=1)
        except OSError:
            pass

    def list(self) -> List[HazardZone]:
        with self._lock:
            return list(self._items)

    def add(self, req: HazardCreate) -> HazardZone:
        if req.polygon is not None:
            polygon = req.polygon
        else:
            ring = circle_polygon(req.center.lat, req.center.lon, req.radius_m)
            polygon = [LatLon(lat=la, lon=lo) for la, lo in ring]
        zone = HazardZone(id=uuid.uuid4().hex[:8], name=req.name, polygon=polygon)
        with self._lock:
            self._items.append(zone)
            self._save()
        return zone

    def remove(self, hazard_id: str) -> bool:
        with self._lock:
            before = len(self._items)
            self._items = [h for h in self._items if h.id != hazard_id]
            changed = len(self._items) != before
            if changed:
                self._save()
            return changed

    def clear(self) -> None:
        with self._lock:
            self._items = []
            self._save()


@lru_cache
def get_hazard_store() -> HazardStore:
    return HazardStore(get_settings().hazards_path)


def split_by_destination(hazards: List[HazardZone], lat: float, lon: float) -> Tuple[List[HazardZone], List[HazardZone]]:
    """(to_avoid, ignored). A hazard that contains the incident itself cannot be avoided,
    because rescuers must still reach the people inside it."""
    avoid, ignored = [], []
    for hz in hazards:
        poly = [(p.lat, p.lon) for p in hz.polygon]
        (ignored if point_in_polygon(lat, lon, poly) else avoid).append(hz)
    return avoid, ignored
