"""Small, dependency-light geometry helpers (numpy + plain Python).

Polygons are lists of (lat, lon) tuples. Areas here are a few hundred metres across,
so treating lon/lat as a flat plane for intersection tests is accurate enough.
"""
import math
from typing import List, Sequence, Tuple

import numpy as np

EARTH_RADIUS_M = 6_371_008.8
Point = Tuple[float, float]  # (lat, lon)


def haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres. Works on scalars and numpy arrays."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlmb = np.radians(lon2) - np.radians(lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(np.minimum(1.0, a)))


def polygon_bbox(poly: Sequence[Point]) -> Tuple[float, float, float, float]:
    """(min_lat, min_lon, max_lat, max_lon)"""
    lats = [p[0] for p in poly]
    lons = [p[1] for p in poly]
    return min(lats), min(lons), max(lats), max(lons)


def point_in_polygon(lat: float, lon: float, poly: Sequence[Point]) -> bool:
    """Ray casting. Points exactly on the boundary may go either way."""
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        yi, xi = poly[i]
        yj, xj = poly[j]
        if (yi > lat) != (yj > lat):
            x_cross = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


def _orient(a: Point, b: Point, c: Point) -> float:
    return (b[1] - a[1]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[1] - a[1])


def _on_segment(a: Point, b: Point, p: Point) -> bool:
    return (min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))


def segments_intersect(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
    """True if segment p1-p2 touches or crosses segment p3-p4."""
    d1, d2 = _orient(p3, p4, p1), _orient(p3, p4, p2)
    d3, d4 = _orient(p1, p2, p3), _orient(p1, p2, p4)
    if d1 * d2 < 0 and d3 * d4 < 0:  # proper crossing
        return True
    if d1 == 0 and _on_segment(p3, p4, p1):
        return True
    if d2 == 0 and _on_segment(p3, p4, p2):
        return True
    if d3 == 0 and _on_segment(p1, p2, p3):
        return True
    if d4 == 0 and _on_segment(p1, p2, p4):
        return True
    return False


def polyline_intersects_polygon(coords: Sequence[Point], poly: Sequence[Point]) -> bool:
    """True if a polyline touches the polygon: any vertex inside, or any segment crossing its border."""
    if not coords:
        return False
    for lat, lon in coords:
        if point_in_polygon(lat, lon, poly):
            return True
    n = len(poly)
    for i in range(len(coords) - 1):
        a, b = coords[i], coords[i + 1]
        for j in range(n):
            if segments_intersect(a, b, poly[j], poly[(j + 1) % n]):
                return True
    return False


def circle_polygon(lat: float, lon: float, radius_m: float, sides: int = 32) -> List[Point]:
    """Approximate a circle with a regular polygon (used for 'flood radius' hazards)."""
    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * max(0.01, math.cos(math.radians(lat))))
    return [
        (lat + dlat * math.sin(2 * math.pi * k / sides),
         lon + dlon * math.cos(2 * math.pi * k / sides))
        for k in range(sides)
    ]
