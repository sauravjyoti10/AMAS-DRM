from app.hazards import HazardStore, split_by_destination
from app.schemas import HazardCreate


def test_add_circle_list_remove(tmp_path):
    store = HazardStore(str(tmp_path / "h.json"))
    z = store.add(HazardCreate(name="Flooded underpass", center={"lat": 26.17, "lon": 91.77}, radius_m=300))
    assert z.id and len(z.polygon) >= 8
    assert [h.name for h in store.list()] == ["Flooded underpass"]

    reloaded = HazardStore(str(tmp_path / "h.json"))          # survives a restart
    assert len(reloaded.list()) == 1
    assert reloaded.remove(z.id) is True
    assert reloaded.remove(z.id) is False
    assert reloaded.list() == []


def test_hazard_needs_a_shape():
    import pytest
    with pytest.raises(Exception):
        HazardCreate(name="nothing")


def test_hazard_containing_the_incident_is_not_avoided():
    store = HazardStore()
    store.add(HazardCreate(name="at incident", center={"lat": 26.1250, "lon": 91.8108}, radius_m=300))
    store.add(HazardCreate(name="elsewhere", center={"lat": 26.1750, "lon": 91.7750}, radius_m=300))
    avoid, ignored = split_by_destination(store.list(), 26.1250, 91.8108)
    assert [h.name for h in avoid] == ["elsewhere"]
    assert [h.name for h in ignored] == ["at incident"]
