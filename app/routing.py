"""Routing Module: Dynamic graph traversal and obstacle avoidance."""
import os  # 👈 Add this import here
import networkx as nx
from shapely.geometry import LineString, Point, Polygon
from typing import List, Dict, Any, Tuple
import osmnx as ox
from pydantic import BaseModel

class RouteResult(BaseModel):
    distance_m: float
    travel_time_s: float
    node_count: int
    path_coordinates: List[Tuple[float, float]]  # 👈 Must return actual lat/lon steps!

# Define your available supply depots
DEPOTS = {
    "Dispur Depot": {"lat": 26.1433, "lon": 91.7898},
    "Zoo Road Depot": {"lat": 26.1850, "lon": 91.7820} 
}

def get_nearest_depot(dest_lat: float, dest_lon: float) -> tuple[float, float]:
    """Mathematically select the closest warehouse to minimize response distance."""
    import math
    
    closest_lat, closest_lon = DEPOTS["Dispur Depot"]["lat"], DEPOTS["Dispur Depot"]["lon"]
    min_dist = float('inf')
    
    for name, coords in DEPOTS.items():
        dist = math.sqrt((coords["lat"] - dest_lat)**2 + (coords["lon"] - dest_lon)**2)
        if dist < min_dist:
            min_dist = dist
            closest_lat, closest_lon = coords["lat"], coords["lon"]
            
    return closest_lat, closest_lon

class RoadNetwork:
    def __init__(self, G: nx.MultiDiGraph):
        self.G = G

    @classmethod
    def from_graphml(cls, filepath: str) -> "RoadNetwork":
        if not os.path.exists(filepath):
            # Fallback for local dev if graphml is missing
            G = ox.graph_from_point((26.1550, 91.7650), dist=5000, network_type="drive")
            return cls(G)
        G = ox.load_graphml(filepath)
        return cls(G)

    def route(self, orig_lat: float, orig_lon: float, dest_lat: float, dest_lon: float) -> RouteResult:
        """Calculate shortest path along graph nodes and return precise road coordinates."""
        # Find nearest graph nodes to origin and destination coordinates
        orig_node = ox.distance.nearest_nodes(self.G, X=orig_lon, Y=orig_lat)
        dest_node = ox.distance.nearest_nodes(self.G, X=dest_lon, Y=dest_lat)

        try:
            # Calculate shortest path using NetworkX
            path_nodes = nx.shortest_path(self.G, orig_node, dest_node, weight="length")
        except nx.NetworkXNoPath:
            # Fallback straight-line if graph has disconnected components
            path_nodes = [orig_node, dest_node]

        # Extract actual latitude and longitude coordinates for every node in the path
        path_coords = []
        total_distance = 0.0

        for i in range(len(path_nodes)):
            node_data = self.G.nodes[path_nodes[i]]
            lat = node_data.get("y")
            lon = node_data.get("x")
            path_coords.append([lat, lon])

            if i > 0:
                prev_node = path_nodes[i-1]
                edge_data = self.G.get_edge_data(prev_node, path_nodes[i])
                if edge_data:
                    # Get length of the edge (handling multi-edges)
                    first_edge = list(edge_data.values())[0]
                    total_distance += first_edge.get("length", 100.0)

        # Estimate travel time (assuming average speed of 30 km/h in disaster conditions)
        travel_time = (total_distance / 1000.0) / 30.0 * 3600.0

        return RouteResult(
            distance_m=total_distance,
            travel_time_s=travel_time,
            node_count=len(path_nodes),
            path_coordinates=path_coords
        )