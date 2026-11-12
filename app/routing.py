"""Routing Module: hazard-aware shortest path over the real OpenStreetMap road network.

What it does (this is the "Google-Maps-like" part):
  * snaps the origin and destination to the nearest road node and REFUSES points that are
    too far from any mapped road (so a wrong location can never silently become a wrong route);
  * removes every road segment that touches a hazard polygon (flood, landslide, ...) for the
    duration of one query, without modifying the stored graph;
  * minimises travel TIME (not distance) with Dijkstra;
  * returns the path along the true road geometry (curves included), not straight lines
    between junctions;
  * double-checks that the final path intersects no hazard (the PPT safety metric).
"""
import os
import re
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import networkx as nx
import numpy as np

from app.geo import Point, haversine_m, polygon_bbox, polyline_intersects_polygon
from app.schemas import HazardZone, RouteResult

__all__ = ["RoadNetwork", "NoRouteError", "OutOfCoverageError", "haversine_m"]

DEFAULT_SPEED_M_S = 30 / 3.6   # 30 km/h when an edge has no travel_time (disaster-conditions average)
_NETWORK_CACHE: Dict[Tuple[str, float], "RoadNetwork"] = {}


class NoRouteError(Exception):
    """No path exists once hazard zones are removed (or the graph is disconnected)."""


class OutOfCoverageError(Exception):
    """A point is farther than max_snap_m from every mapped road."""


def _edge_cost(attrs: dict) -> float:
    """Seconds to traverse an edge."""
    tt = attrs.get("travel_time")
    if tt is not None:
        return float(tt)
    return float(attrs.get("length", 100.0)) / DEFAULT_SPEED_M_S


def _geometry_coords(geom) -> Optional[List[Point]]:
    """Return [(lat, lon), ...] from a shapely LineString or a WKT string, else None."""
    if geom is None:
        return None
    if isinstance(geom, str):
        m = re.match(r"\s*LINESTRING\s*\((.*)\)\s*$", geom, re.I | re.S)
        if not m:
            return None
        pts = [tuple(map(float, p.split()[:2])) for p in m.group(1).split(",")]
        return [(y, x) for x, y in pts]
    try:
        return [(y, x) for x, y in geom.coords]
    except Exception:
        return None


class RoadNetwork:
    def __init__(self, G: nx.MultiDiGraph):
        self.G = G
        ids = list(G.nodes)
        self._ids = np.array(ids, dtype=object)
        self._lat = np.array([G.nodes[n]["y"] for n in ids], dtype=float)
        self._lon = np.array([G.nodes[n]["x"] for n in ids], dtype=float)
        self._edge_index = None  # built lazily, only when hazards are used

    # ------------------------------------------------------------------ loading
    @property
    def graph(self) -> nx.MultiDiGraph:
        return self.G

    @classmethod
    def from_graphml(cls, filepath: str) -> "RoadNetwork":
        """Load (and cache per process) the road graph produced by `python -m scripts.download_map`."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(
                f"Road map '{filepath}' not found. Run:  python -m scripts.download_map"
            )
        key = (os.path.abspath(filepath), os.path.getmtime(filepath))
        if key not in _NETWORK_CACHE:
            import osmnx as ox  # imported lazily: only needed to read the real map file
            _NETWORK_CACHE.clear()
            _NETWORK_CACHE[key] = cls(ox.load_graphml(filepath))
        return _NETWORK_CACHE[key]

    def bounds(self) -> Tuple[float, float, float, float]:
        """(south, west, north, east) of the loaded map."""
        return (float(self._lat.min()), float(self._lon.min()),
                float(self._lat.max()), float(self._lon.max()))

    # ------------------------------------------------------------------ snapping
    def snap(self, lat: float, lon: float) -> Tuple[object, float]:
        """Nearest road node and its distance in metres."""
        d = haversine_m(lat, lon, self._lat, self._lon)
        i = int(np.argmin(d))
        return self._ids[i], float(d[i])

    # ------------------------------------------------------------------ hazards
    def _build_edge_index(self) -> None:
        keys, coords, boxes = [], [], []
        for u, v, k, data in self.G.edges(keys=True, data=True):
            pts = _geometry_coords(data.get("geometry"))
            if not pts:
                pts = [(self.G.nodes[u]["y"], self.G.nodes[u]["x"]),
                       (self.G.nodes[v]["y"], self.G.nodes[v]["x"])]
            keys.append((u, v, k))
            coords.append(pts)
            la = [p[0] for p in pts]
            lo = [p[1] for p in pts]
            boxes.append((min(la), min(lo), max(la), max(lo)))
        self._edge_index = (keys, coords, np.array(boxes, dtype=float).reshape(-1, 4))

    def _blocked_edges(self, polys: Sequence[Sequence[Point]]) -> Set[Tuple]:
        """Edge keys (u, v, k) whose geometry touches any hazard polygon."""
        if not polys:
            return set()
        if self._edge_index is None:
            self._build_edge_index()
        keys, coords, boxes = self._edge_index
        blocked: Set[Tuple] = set()
        for poly in polys:
            a, b, c, d = polygon_bbox(poly)
            overlap = ((boxes[:, 2] >= a) & (boxes[:, 0] <= c)
                       & (boxes[:, 3] >= b) & (boxes[:, 1] <= d))
            for i in np.nonzero(overlap)[0]:
                if polyline_intersects_polygon(coords[i], poly):
                    blocked.add(keys[i])
        return blocked

    @staticmethod
    def _as_polys(hazards: Optional[Iterable[HazardZone]]) -> List[List[Point]]:
        return [[(p.lat, p.lon) for p in hz.polygon] for hz in (hazards or [])]

    # ------------------------------------------------------------------ routing
    def route(
        self,
        orig_lat: float,
        orig_lon: float,
        dest_lat: float,
        dest_lon: float,
        hazards: Optional[Iterable[HazardZone]] = None,
        max_snap_m: float = 1000.0,
    ) -> RouteResult:
        """Fastest road route that stays out of every hazard polygon."""
        orig_node, orig_snap = self.snap(orig_lat, orig_lon)
        dest_node, dest_snap = self.snap(dest_lat, dest_lon)
        if orig_snap > max_snap_m:
            raise OutOfCoverageError(
                f"Origin is {orig_snap:.0f} m from the nearest mapped road (limit {max_snap_m:.0f} m)")
        if dest_snap > max_snap_m:
            raise OutOfCoverageError(
                f"Destination is {dest_snap:.0f} m from the nearest mapped road (limit {max_snap_m:.0f} m)")

        polys = self._as_polys(hazards)
        blocked = self._blocked_edges(polys)

        def weight(u, v, multi):  # multi = {key: attrs}; None hides the edge from Dijkstra
            best = None
            for k, attrs in multi.items():
                if (u, v, k) in blocked:
                    continue
                c = _edge_cost(attrs)
                if best is None or c < best:
                    best = c
            return best

        try:
            nodes = nx.shortest_path(self.G, orig_node, dest_node, weight=weight)
        except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
            reason = "hazard zones block every road" if polys else "the road graph is disconnected"
            raise NoRouteError(f"No route found: {reason}.") from exc

        coords, distance, seconds = self._assemble(nodes, blocked)

        # PPT safety metric: geom(P*) ∩ H = ∅, checked on the road path itself.
        safe = not any(polyline_intersects_polygon(coords, p) for p in polys)

        # Connect the exact requested points to the road (short "last-metre" legs), when they differ.
        if orig_snap > 1.0:
            coords.insert(0, (orig_lat, orig_lon))
        if dest_snap > 1.0:
            coords.append((dest_lat, dest_lon))

        return RouteResult(
            distance_m=distance,
            travel_time_s=seconds,
            node_count=len(nodes),
            origin_snap_m=orig_snap,
            destination_snap_m=dest_snap,
            blocked_edges=len(blocked),
            hazard_safe=safe,
            path_coordinates=[[float(la), float(lo)] for la, lo in coords],
        )

    def _assemble(self, nodes: List, blocked: Set[Tuple]) -> Tuple[List[Point], float, float]:
        """Follow the cheapest usable parallel edge between consecutive nodes and keep its true shape."""
        n0 = self.G.nodes[nodes[0]]
        coords: List[Point] = [(n0["y"], n0["x"])]
        distance = seconds = 0.0
        for u, v in zip(nodes, nodes[1:]):
            best_k, best_c = None, None
            for k, attrs in self.G[u][v].items():
                if (u, v, k) in blocked:
                    continue
                c = _edge_cost(attrs)
                if best_c is None or c < best_c:
                    best_k, best_c = k, c
            attrs = self.G[u][v][best_k]
            nu, nv = self.G.nodes[u], self.G.nodes[v]
            pts = _geometry_coords(attrs.get("geometry")) or [(nu["y"], nu["x"]), (nv["y"], nv["x"])]
            # make sure the stored geometry runs u -> v
            if (haversine_m(pts[0][0], pts[0][1], nu["y"], nu["x"])
                    > haversine_m(pts[-1][0], pts[-1][1], nu["y"], nu["x"])):
                pts = pts[::-1]
            coords.extend(pts[1:] if len(pts) > 1 else pts)
            length = attrs.get("length")
            if length is None:
                length = float(sum(haversine_m(a[0], a[1], b[0], b[1]) for a, b in zip(pts, pts[1:])))
            distance += float(length)
            seconds += best_c
        return coords, distance, seconds
