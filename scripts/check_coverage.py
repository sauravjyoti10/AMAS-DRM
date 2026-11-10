"""Check how well the downloaded map covers key Guwahati places.

Run from the project root:  python -m scripts.check_coverage
(Coordinates below are approximate; this is only a rough sanity check.)
"""
from app.config import get_settings
from app.routing import RoadNetwork

PLACES = {
    "Zoo Road Tiniali": (26.1750, 91.7750),
    "Paltan Bazaar": (26.1830, 91.7500),
    "Dispur": (26.1433, 91.7898),
    "Beltola": (26.1280, 91.8000),
}


def main() -> None:
    net = RoadNetwork.from_graphml(get_settings().graph_path)
    s, w, n, e = net.bounds()
    print(f"Map: {net.graph.number_of_nodes()} nodes | lat {s:.4f}..{n:.4f} | lon {w:.4f}..{e:.4f}\n")
    for name, (lat, lon) in PLACES.items():
        _, dist = net.snap(lat, lon)
        verdict = "OK" if dist <= 500 else "FAR - map may be too small here"
        print(f"{name:<20} nearest road node: {dist:7.0f} m   {verdict}")


if __name__ == "__main__":
    main()
