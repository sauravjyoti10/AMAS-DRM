"""See exactly what OpenStreetMap (Nominatim) answers for place names, and compare it with our built-in gazetteer.

    python -m scripts.check_geocoding "Khanapara bus stand" "Ganeshguri"   # raw answers for these phrases
    python -m scripts.check_geocoding                                      # compare EVERY gazetteer place with OSM

For each phrase it tries the same query wordings the app uses and prints the match, its OSM type and the distance to
our gazetteer point. Update app/gazetteer.py with any place that is more than ~500 m off: OSM is the base map the
routes are drawn on, so it is the better reference.
"""
import sys
import time

from geopy.geocoders import Nominatim

from app import gazetteer
from app.config import get_settings
from app.geo import haversine_m


def ask(geo, settings, query):
    time.sleep(1.1)  # Nominatim usage policy: max 1 request per second
    return geo.geocode(
        query,
        viewbox=[(settings.bbox_south, settings.bbox_west), (settings.bbox_north, settings.bbox_east)],
        bounded=True, country_codes="in", exactly_one=True,
    )


def check(geo, settings, phrase):
    ref = gazetteer.lookup(phrase)
    print(f"\n{phrase}")
    found = None
    for query in (phrase, f"{phrase}, Guwahati"):
        try:
            loc = ask(geo, settings, query)
        except Exception as exc:
            print(f"   {query!r:40} ERROR {type(exc).__name__}: {exc}")
            continue
        if loc is None:
            print(f"   {query!r:40} no result")
            continue
        raw = loc.raw or {}
        extra = ""
        if ref:
            d = float(haversine_m(loc.latitude, loc.longitude, ref[1], ref[2]))
            extra = f"  | {d:.0f} m from gazetteer" + ("  <-- UPDATE" if d > 500 else "")
        print(f"   {query!r:40} {loc.latitude:.5f}, {loc.longitude:.5f}  [{raw.get('class')}/{raw.get('type')}]  {loc.address[:70]}{extra}")
        found = found or loc
    if found and ref:
        print(f"   suggested gazetteer line:  \"{ref[0]}\": ({found.latitude:.4f}, {found.longitude:.4f}, {ref[3]:.0f}),")


def main() -> None:
    settings = get_settings()
    geo = Nominatim(user_agent=settings.geocode_user_agent, timeout=settings.geocode_timeout_s)
    phrases = sys.argv[1:] or sorted(k for k in gazetteer.GAZETTEER if k != "guwahati")
    for p in phrases:
        check(geo, settings, p)


if __name__ == "__main__":
    main()
