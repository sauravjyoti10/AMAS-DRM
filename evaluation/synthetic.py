"""A synthetic street grid over Guwahati's coordinates, for running the evaluations without the OSM download.

Numbers from this grid prove the code paths work; the thesis numbers must come from the real OSM graph
(run without --synthetic after `python -m scripts.download_map`).
"""
import random

import networkx as nx

from app.geo import haversine_m
from app.routing import RoadNetwork


def build_grid(south=26.06, west=91.62, n=140, step=0.0015, seed=1, drop_fraction=0.08) -> RoadNetwork:
    """n x n grid (~220 m blocks). A few random streets are removed so the network is not perfectly regular."""
    rng = random.Random(seed)
    G = nx.MultiDiGraph()
    G.graph["crs"] = "EPSG:4326"
    for r in range(n):
        for c in range(n):
            G.add_node(r * n + c, y=south + r * step, x=west + c * step)

    def link(a, b):
        length = float(haversine_m(G.nodes[a]["y"], G.nodes[a]["x"], G.nodes[b]["y"], G.nodes[b]["x"]))
        speed = rng.choice([6.9, 8.3, 11.1])             # 25, 30, 40 km/h
        for u, v in ((a, b), (b, a)):
            G.add_edge(u, v, length=length, travel_time=length / speed)

    for r in range(n):
        for c in range(n):
            if c + 1 < n and rng.random() > drop_fraction:
                link(r * n + c, r * n + c + 1)
            if r + 1 < n and rng.random() > drop_fraction:
                link(r * n + c, (r + 1) * n + c)
    # keep one connected piece, like scripts/download_map.py does
    biggest = max(nx.strongly_connected_components(G), key=len)
    return RoadNetwork(G.subgraph(biggest).copy())
