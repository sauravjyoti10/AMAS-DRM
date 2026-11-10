"""One-time download of the Guwahati drivable road network, prepared for routing.

Why this is more elaborate than one call:
  * The area is downloaded in small tiles, because big single requests are the
    ones free Overpass servers most often drop (ConnectionResetError 10054).
  * Each tile is retried, then retried on backup Overpass servers.
  * osmnx caches every response, so if the script stops, running it again
    resumes instead of starting over.

Run from the project root:  python -m scripts.download_map
"""
import os
import time

import networkx as nx
import osmnx as ox

from app.config import get_settings

# (west, south, east, north): Jalukbari to Beltola, Khanapara to Paltan Bazaar
WEST, SOUTH, EAST, NORTH = 91.62, 26.09, 91.88, 26.23
GRID = 2                 # GRID x GRID tiles
OVERLAP = 0.004          # degrees (~400 m) so roads crossing tile borders are kept
RETRIES_PER_SERVER = 2

SERVERS = [              # tried in order
    "https://overpass-api.de/api",
    "https://overpass.private.coffee/api",
    "https://overpass.kumi.systems/api",
]

ox.settings.use_cache = True
ox.settings.log_console = False
ox.settings.requests_timeout = 180


def _server_setting():
    """osmnx versions differ on the setting name and whether it ends in /interpreter."""
    attr = "overpass_url" if hasattr(ox.settings, "overpass_url") else "overpass_endpoint"
    current = str(getattr(ox.settings, attr)).rstrip("/")
    return attr, ("/interpreter" if current.endswith("/interpreter") else "")


def tiles():
    dx, dy = (EAST - WEST) / GRID, (NORTH - SOUTH) / GRID
    for i in range(GRID):
        for j in range(GRID):
            yield (
                WEST + i * dx - OVERLAP, SOUTH + j * dy - OVERLAP,
                WEST + (i + 1) * dx + OVERLAP, SOUTH + (j + 1) * dy + OVERLAP,
            )


def download_tile(bbox):
    attr, suffix = _server_setting()
    last_error = None
    for base in SERVERS:
        setattr(ox.settings, attr, base + suffix)
        for attempt in range(1, RETRIES_PER_SERVER + 1):
            try:
                return ox.graph_from_bbox(
                    bbox, network_type="drive", retain_all=True, truncate_by_edge=True
                )
            except Exception as e:
                last_error = e
                print(f"   failed on {base} (try {attempt}): {type(e).__name__}")
                time.sleep(5 * attempt)
    raise RuntimeError(f"All Overpass servers failed for this tile. Last error: {last_error}")


def main() -> None:
    path = get_settings().graph_path
    os.makedirs(os.path.dirname(path), exist_ok=True)

    graphs = []
    total = GRID * GRID
    for n, bbox in enumerate(tiles(), start=1):
        print(f"Tile {n}/{total}: downloading ...")
        G_tile = download_tile(bbox)
        print(f"   ok: {G_tile.number_of_nodes()} nodes")
        graphs.append(G_tile)

    G = nx.compose_all(graphs)
    print(f"Combined: {G.number_of_nodes()} nodes / {G.number_of_edges()} edges")

    # Keep only the largest strongly connected piece so every node can reach every other.
    G = ox.truncate.largest_component(G, strongly=True)

    # Add speed + travel time per edge: emergency routing should minimise ETA, not distance.
    G = ox.routing.add_edge_speeds(G)
    G = ox.routing.add_edge_travel_times(G)

    ox.save_graphml(G, filepath=path)
    print(f"Saved {G.number_of_nodes()} nodes / {G.number_of_edges()} edges to {path}")


if __name__ == "__main__":
    main()
