"""The evaluation code itself must be right, or its numbers mean nothing."""
import pytest

from app import gazetteer
from app.allocation import Depot, IncidentDemand
from app.schemas import ParsedIncident, TriageResult
from evaluation import dataset
from evaluation.eval_allocation import fcfs, score
from evaluation.eval_routing import densify, touches
from evaluation.eval_triage import score_location
from evaluation.metrics import confusion, per_class, percentile, prf, set_micro_prf


def test_prf_and_confusion():
    assert prf(8, 2, 2) == pytest.approx((0.8, 0.8, 0.8))
    cm = confusion(["CRITICAL", "CRITICAL", "LOW"], ["CRITICAL", "LOW", "LOW"])
    pc = per_class(cm)
    assert pc["CRITICAL"]["recall"] == 0.5 and pc["CRITICAL"]["precision"] == 1.0
    assert pc["LOW"]["precision"] == 0.5 and pc["LOW"]["recall"] == 1.0


def test_set_micro_prf_and_percentile():
    p, r, f = set_micro_prf([["a", "b"], ["c"]], [["a"], ["c", "d"]])
    assert (p, r) == pytest.approx((2 / 3, 2 / 3))
    assert percentile([1, 2, 3, 4, 5], 50) == 3 and percentile([1, 2, 3, 4, 5], 100) == 5


def test_dataset_is_large_enough_and_consistent():
    data = dataset.load()
    assert len(data) >= 100
    assert {s.severity for s in data} == {"CRITICAL", "HIGH", "MODERATE", "LOW"}
    for s in data:
        if s.place not in (None, "OTHER", "COORDS", "OUTSIDE"):
            assert gazetteer.lookup(s.place), f"#{s.id}: unknown gold place {s.place}"
        if s.place == "COORDS":
            assert s.lat is not None and s.lon is not None


def _res(lat, lon, source):
    inc = ParsedIncident(summary="x", severity="LOW", casualties=0)
    return TriageResult(incident=inc, latitude=lat, longitude=lon, location_source=source, uncertainty_m=100.0)


def _sample(place, lat=None, lon=None):
    return dataset.Sample(1, "t", "LOW", 0, place, (), lat, lon)


def test_score_location_outcomes():
    key, glat, glon, _ = gazetteer.lookup("khanapara")
    assert score_location(_sample("khanapara"), _res(glat, glon, "geocoded"))["outcome"] == "correct"
    assert score_location(_sample("khanapara"), _res(26.18, 91.75, "geocoded"))["outcome"] == "wrong_pin"
    assert score_location(_sample("khanapara"), _res(None, None, "unknown"))["outcome"] == "missed"
    assert score_location(_sample(None), _res(26.17, 91.75, "geocoded"))["outcome"] == "false_pin"
    assert score_location(_sample("OUTSIDE"), _res(None, None, "unknown"))["outcome"] == "correct_unresolved"
    assert score_location(_sample("COORDS", 26.145, 91.802), _res(26.145, 91.802, "message"))["outcome"] == "coords_ok"


def _scenario():
    depots = [Depot(id="D", capacity=10, lat=26.1, lon=91.7)]
    low = IncidentDemand(id="low", severity_score=1.0, demand=10, lat=26.1, lon=91.7)
    crit = IncidentDemand(id="crit", severity_score=10.0, demand=10, lat=26.1, lon=91.7)
    incs = [("LOW", low), ("CRITICAL", crit)]                    # the low-priority call arrived first
    return depots, incs, {("low", "D"): 1.0, ("crit", "D"): 1.0}


def test_fcfs_serves_in_arrival_order_even_when_a_critical_call_waits():
    depots, incs, dist = _scenario()
    plan = fcfs(depots, incs, dist)
    assert plan["low"] == {"D": 10} and plan["crit"] == {}
    s = score(plan, depots, incs, dist)
    assert s["critical_fill"] == 0.0 and s["fill_rate"] == 0.5


def test_densify_and_independent_hazard_check():
    pts = densify([[26.1700, 91.7700], [26.1700, 91.7720]], step_m=10)
    assert len(pts) > 15                                          # ~214 m sampled every ~10 m
    square = [(26.1695, 91.7705), (26.1695, 91.7715), (26.1705, 91.7715), (26.1705, 91.7705)]
    assert touches([[26.1700, 91.7700], [26.1700, 91.7720]], [square])
    assert not touches([[26.1800, 91.7700], [26.1800, 91.7720]], [square])
