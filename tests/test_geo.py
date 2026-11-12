"""Geometry helpers, gazetteer and place-name cleaning (no internet needed)."""
import pytest

from app import gazetteer
from app.geo import (circle_polygon, haversine_m, point_in_polygon,
                     polyline_intersects_polygon, segments_intersect)
from app.triage import place_queries

SQUARE = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]   # (lat, lon) corners


def test_haversine_one_degree_of_latitude():
    assert haversine_m(26.0, 91.0, 27.0, 91.0) == pytest.approx(111_195, rel=1e-3)


def test_point_in_polygon():
    assert point_in_polygon(0.5, 0.5, SQUARE)
    assert not point_in_polygon(1.5, 0.5, SQUARE)


def test_segments_crossing_and_touching():
    assert segments_intersect((0, 0), (1, 1), (0, 1), (1, 0))        # X shape
    assert segments_intersect((0, 0), (1, 0), (1, 0), (1, 1))        # touch at an end
    assert not segments_intersect((0, 0), (1, 0), (0, 1), (1, 1))    # parallel


def test_polyline_crossing_polygon_with_no_vertex_inside():
    # Both ends are outside, the line cuts straight through the square.
    assert polyline_intersects_polygon([(0.5, -1.0), (0.5, 2.0)], SQUARE)
    assert not polyline_intersects_polygon([(2.0, -1.0), (2.0, 2.0)], SQUARE)


def test_circle_polygon_radius():
    ring = circle_polygon(26.17, 91.77, 400.0)
    dists = [float(haversine_m(26.17, 91.77, la, lo)) for la, lo in ring]
    assert all(390 < d < 410 for d in dists)
    assert point_in_polygon(26.17, 91.77, ring)


# ---------- gazetteer ----------
def test_gazetteer_alias_and_lookup():
    assert gazetteer.lookup("Paltan Bazar")[0] == "paltan bazaar"
    assert gazetteer.lookup("nowhere land") is None


def test_find_places_prefers_longest_match():
    names = [n for n, _, _ in gazetteer.find_places("Water on Zoo Road Tiniali near Chandmari")]
    assert names == ["zoo road tiniali", "chandmari"]


# ---------- place_queries ----------
@pytest.mark.parametrize("text, expected", [
    ("Khanapara bus stand", ["Khanapara bus stand", "Khanapara"]),
    ("near the Khanapara bus stand.", ["Khanapara bus stand", "Khanapara"]),
    ("Zoo Road Tiniali", ["Zoo Road Tiniali", "Zoo Road"]),
    ("Ganeshguri flyover opp SBI ATM", ["Ganeshguri flyover", "Ganeshguri", "SBI ATM"]),
    ("Beltola, where water is rising", ["Beltola"]),
    ("", []),
    (None, []),
])
def test_place_queries(text, expected):
    assert place_queries(text) == expected
