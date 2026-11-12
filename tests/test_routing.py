"""Routing tests on a small synthetic grid: no internet, no big map file needed.

Grid layout (rows go north, columns go east), 4 x 4 nodes, ~100 m apart:
    node id = row * 4 + col
"""
import networkx as nx
import pytest

from app.routing import (NoRouteError, OutOfCoverageError, RoadNetwork,
                         haversine_m)
from app.schemas import HazardZone

BASE_LAT, BASE_LON, STEP, N = 26.170, 91.770, 0.001, 4


def make_grid() -> RoadNetwork:
    G = nx.MultiDiGraph()
    G.graph["crs"] = "EPSG:4326"
    for r in range(N):
        for c in range(N):
            G.add_node(r * N + c, y=BASE_LAT + r * STEP, x=BASE_LON + c * STEP)

    def link(a, b):
        length = float(haversine_m(G.nodes[a]["y"], G.nodes[a]["x"], G.nodes[b]["y"], G.nodes[b]["x"]))
        G.add_edge(a, b, length=length, travel_time=length / 10)
        G.add_edge(b, a, length=length, travel_time=length / 10)

    for r in range(N):
        for c in range(N):
            if c + 1 < N:
                link(r * N + c, r * N + c + 1)
            if r + 1 < N:
                link(r * N + c, (r + 1) * N + c)
    return RoadNetwork(G)


def node_ll(r, c):
    return BASE_LAT + r * STEP, BASE_LON + c * STEP


def rect(lat_min, lon_min, lat_max, lon_max, name="hazard") -> HazardZone:
    return HazardZone(name=name, polygon=[
        {"lat": lat_min, "lon": lon_min}, {"lat": lat_min, "lon": lon_max},
        {"lat": lat_max, "lon": lon_max}, {"lat": lat_max, "lon": lon_min},
    ])


@pytest.fixture
def net():
    return make_grid()


def test_snap_exact_node(net):
    node, dist = net.snap(*node_ll(2, 1))
    assert node == 2 * N + 1
    assert dist < 1.0


def test_route_without_hazards(net):
    res = net.route(*node_ll(0, 0), *node_ll(3, 3))
    assert res.node_count == 7              # 3 north + 3 east + start
    assert res.blocked_edges == 0
    assert res.hazard_safe is True
    assert len(res.path_coordinates) == res.node_count


def test_hazard_forces_detour(net):
    direct = net.route(*node_ll(0, 0), *node_ll(0, 3))
    assert direct.node_count == 4           # straight along row 0

    # Blocks every east-west link in rows 0-2 between columns 0 and 3.
    hz = rect(BASE_LAT - 0.0005, BASE_LON + 0.5 * STEP, BASE_LAT + 2.5 * STEP, BASE_LON + 2.5 * STEP)
    detour = net.route(*node_ll(0, 0), *node_ll(0, 3), hazards=[hz])

    assert detour.node_count == 10          # 3 north + 3 east + 3 south + start
    assert detour.distance_m > direct.distance_m
    assert detour.travel_time_s > direct.travel_time_s
    assert detour.blocked_edges > 0
    assert detour.hazard_safe is True       # PPT metric: geom(P*) ∩ H = ∅


def test_fully_blocked_raises_no_route(net):
    wall = rect(BASE_LAT - 0.0005, BASE_LON + 0.8 * STEP, BASE_LAT + 3.5 * STEP, BASE_LON + 1.2 * STEP)
    with pytest.raises(NoRouteError):
        net.route(*node_ll(0, 0), *node_ll(0, 3), hazards=[wall])


def test_origin_inside_hazard_raises_no_route(net):
    lat, lon = node_ll(0, 0)
    around_origin = rect(lat - 0.0001, lon - 0.0001, lat + 0.0001, lon + 0.0001)
    with pytest.raises(NoRouteError):
        net.route(*node_ll(0, 0), *node_ll(3, 3), hazards=[around_origin])


def test_far_away_point_is_out_of_coverage(net):
    with pytest.raises(OutOfCoverageError):
        net.route(*node_ll(0, 0), 28.6, 77.2, max_snap_m=1000)   # Delhi


def test_graph_is_not_mutated_by_hazards(net):
    before_edges = net.graph.number_of_edges()
    before = net.route(*node_ll(0, 0), *node_ll(0, 3))

    hz = rect(BASE_LAT - 0.0005, BASE_LON + 0.5 * STEP, BASE_LAT + 2.5 * STEP, BASE_LON + 2.5 * STEP)
    net.route(*node_ll(0, 0), *node_ll(0, 3), hazards=[hz])

    assert net.graph.number_of_edges() == before_edges
    after = net.route(*node_ll(0, 0), *node_ll(0, 3))
    assert after.distance_m == before.distance_m   # earlier hazard did not leak


def test_hazard_zone_needs_three_points():
    with pytest.raises(Exception):
        HazardZone(name="bad", polygon=[{"lat": 26.1, "lon": 91.7}, {"lat": 26.2, "lon": 91.8}])


# ---------- real road geometry, hazard geometry, last-metre legs ----------
def test_route_follows_edge_geometry_not_straight_lines():
    G = nx.MultiDiGraph()
    G.graph["crs"] = "EPSG:4326"
    G.add_node(1, y=26.170, x=91.770)
    G.add_node(2, y=26.170, x=91.772)
    bend = f"LINESTRING (91.770 26.170, 91.771 26.1715, 91.772 26.170)"   # road bows north between the nodes
    G.add_edge(1, 2, length=300.0, travel_time=30.0, geometry=bend)
    res = RoadNetwork(G).route(26.170, 91.770, 26.170, 91.772)
    assert res.node_count == 2
    assert len(res.path_coordinates) == 3                       # the bend is kept
    assert res.path_coordinates[1] == [26.1715, 91.771]
    assert res.distance_m == 300.0 and res.travel_time_s == 30.0


def test_hazard_over_a_curved_road_with_no_node_inside_blocks_it():
    G = nx.MultiDiGraph()
    G.graph["crs"] = "EPSG:4326"
    for n, (la, lo) in {1: (26.170, 91.770), 2: (26.170, 91.772), 3: (26.168, 91.771)}.items():
        G.add_node(n, y=la, x=lo)
    bend = "LINESTRING (91.770 26.170, 91.771 26.1715, 91.772 26.170)"
    G.add_edge(1, 2, length=300.0, travel_time=30.0, geometry=bend)
    for a, b in ((1, 3), (3, 2)):
        G.add_edge(a, b, length=400.0, travel_time=80.0)
    net = RoadNetwork(G)
    flood = rect(26.1712, 91.7708, 26.1718, 91.7712)            # sits on the bend only
    res = net.route(26.170, 91.770, 26.170, 91.772, hazards=[flood])
    assert res.node_count == 3 and res.hazard_safe              # took the southern road
    assert res.blocked_edges == 1


def test_route_connects_exact_points_to_the_road():
    net = make_grid()
    lat, lon = node_ll(0, 0)
    res = net.route(lat + 0.0002, lon, *node_ll(0, 3))          # ~22 m from the nearest node
    assert res.origin_snap_m > 1
    assert res.path_coordinates[0] == [lat + 0.0002, lon]


def test_snap_limit_protects_against_wrong_locations():
    net = make_grid()
    with pytest.raises(OutOfCoverageError):
        net.route(*node_ll(0, 0), 26.30, 91.77, max_snap_m=500)
