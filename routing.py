# routing.py
import osmnx as ox
import networkx as nx
import random
from config import DEPOT_LAT, DEPOT_LON, AVERAGE_SPEED_MPS
import math
from shapely.geometry import Point
import geopandas as gpd
import pandas as pd

import streamlit as st

@st.cache_data(show_spinner=False)
def get_cached_graph(radius):
    """
    Downloads and caches the OSMnx street graph for the given radius around the depot.
    Projects the graph to UTM to prevent scikit-learn dependency errors.
    """
    # Configure osmnx to quiet mode and use cache
    ox.settings.log_console = False
    ox.settings.use_cache = True
    
    G = ox.graph_from_point((DEPOT_LAT, DEPOT_LON), dist=radius, network_type='drive')
    G_proj = ox.project_graph(G)
    return G_proj

def generate_loop_route(drive_time_mins, roads_gdf, traffic_data):
    """
    Calculates a continuous multi-waypoint route loop from the depot
    to cover the target distance. Maps live complexity and traffic incidents
    to graph edges to actively seek out high-complexity environments and avoid closures.
    Returns a dictionary with 'route_coords', 'route_metrics', and 'radius'.
    """
    # Expand radius slightly based on requested time (POC approximation)
    radius = 3000 if drive_time_mins <= 60 else 6000
    
    # Retrieve the cached street network
    G_proj = get_cached_graph(radius)
    
    # Project the depot coordinates to match the graph's generated UTM CRS
    depot_point = Point(DEPOT_LON, DEPOT_LAT)
    depot_proj, _ = ox.projection.project_geometry(depot_point, to_crs=G_proj.graph['crs'])
    orig = ox.distance.nearest_nodes(G_proj, X=depot_proj.x, Y=depot_proj.y)
    
    # -------------------------------------------------------------
    # SPRINT 6: COMPLEXITY-AWARE GRAPH EDGE WEIGHTING
    # -------------------------------------------------------------
    
    # Extract edges to a GeoDataFrame to perform spatial operations
    _, edges_gdf = ox.graph_to_gdfs(G_proj)
    
    # Create the base 'risk_weight' (Inverted formula to make complex roads 'cheaper' for Dijkstra)
    for u, v, k, data in G_proj.edges(keys=True, data=True):
        length = data.get('length', 1.0)
        data['risk_weight'] = length / 1.0 # Default un-scored weight
        data['is_incident'] = False
        
    # 1. Map Complexity Scores from roads_gdf onto the graph edges
    if roads_gdf is not None and not roads_gdf.empty:
        # We must reproject roads_gdf to match the UTM zone of the graph for spatial joining
        roads_proj = roads_gdf.to_crs(G_proj.graph['crs'])
        
        # We use a spatial join (nearest) to quickly link OSMnx graph edges to our scored roads
        # Use a 50 meter tolerance to map adjacent parallel lanes
        edges_scored = gpd.sjoin_nearest(edges_gdf, roads_proj[['geometry', 'complexity']], how='left', max_distance=50)
        
        # Overwrite the base risk_weight in the internal NetworkX Graph
        for idx, row in edges_scored.iterrows():
            if pd.notna(row.get('complexity')):
                # Grab the graph edge keys
                u, v, k = idx[0], idx[1], idx[2]
                if G_proj.has_edge(u, v, k):
                    length = G_proj[u][v][k].get('length', 1.0)
                    score = max(row['complexity'], 1) # Prevent division by zero
                    
                    # Core Autonomous Optimization Math:
                    # By dividing physical length by the hazard complexity, the routing 
                    # algorithm is mathematically tricked into viewing highly dangerous 
                    # intersections as "shortcuts".
                    G_proj[u][v][k]['risk_weight'] = length / score

    # 2. Map Traffic Incidents (Avoidance Penalty)
    if traffic_data:
        # Build Point geometries for active incidents
        incident_points = [Point(inc['geometry'][0][0], inc['geometry'][0][1]) for inc in traffic_data if inc.get('geometry')]
        if incident_points:
            incidents_gdf = gpd.GeoDataFrame(geometry=incident_points, crs="EPSG:4326")
            incidents_proj = incidents_gdf.to_crs(G_proj.graph['crs'])
            
            # Find any street edge within 100 meters of a major incident
            edges_with_incidents = gpd.sjoin_nearest(edges_gdf, incidents_proj, how='inner', max_distance=100)
            
            for idx, _ in edges_with_incidents.iterrows():
                u, v, k = idx[0], idx[1], idx[2]
                if G_proj.has_edge(u, v, k):
                    length = G_proj[u][v][k].get('length', 1.0)
                    # Apply an astronomical mathematical penalty so Dijkstra actively routes around the blockage
                    G_proj[u][v][k]['risk_weight'] = length * 1000.0 
                    G_proj[u][v][k]['is_incident'] = True
                    
    # -------------------------------------------------------------
    
    nodes = list(G_proj.nodes())
    
    # Calculate target network distance
    target_distance_m = drive_time_mins * 60 * AVERAGE_SPEED_MPS
    
    # Build Continuous Multi-Waypoint Route Loop
    path = [orig]
    current_node = orig
    accumulated_length = 0
    waypoints = 0
    max_waypoints = 15 # Safeguard against infinite loops in small grids
    
    while accumulated_length < (target_distance_m * 0.8) and waypoints < max_waypoints:
        # Sample 50 random nodes and pick one that is geometrically far from our current location to force a sweeping route
        sample = random.sample(nodes, min(50, len(nodes)))
        next_dest = max(sample, key=lambda n: math.hypot(
            G_proj.nodes[current_node]['x'] - G_proj.nodes[n]['x'], 
            G_proj.nodes[current_node]['y'] - G_proj.nodes[n]['y']
        ))
        
        try:
            # We now route using our custom 'risk_weight' instead of pure 'length'
            sub_path = nx.shortest_path(G_proj, current_node, next_dest, weight='risk_weight')
            
            # We calculate actual physical attributes using real length to keep manifest accurate
            sub_gdf = ox.routing.route_to_gdf(G_proj, sub_path, weight='length')
            sub_len = sub_gdf['length'].sum()
            
            # Extend master path (skip the first node to avoid duplicate coordinates linking segments)
            path.extend(sub_path[1:])
            accumulated_length += sub_len
            current_node = next_dest
            waypoints += 1
            
        except Exception:
            pass
    
    # Final Leg: Route back to the starting Depot to close the loop
    try:
        home_path = nx.shortest_path(G_proj, current_node, orig, weight='risk_weight')
        path.extend(home_path[1:])
    except Exception:
        pass
    
    # Convert path to coordinate pairs [lat, lon] for Folium
    route_coords = [(G_proj.nodes[n]['y'], G_proj.nodes[n]['x']) for n in path]
    
    # Calculate Final Mathematical Route Attributes
    route_gdf = ox.routing.route_to_gdf(G_proj, path, weight='length')
    total_length_m = route_gdf['length'].sum()
    total_length_mi = total_length_m * 0.000621371
    
    est_time_mins = total_length_m / AVERAGE_SPEED_MPS / 60
    
    return {
        'coords': route_coords,
        'metrics': {
            'dist': total_length_mi,
            'time': est_time_mins,
            'nodes': len(path)
        },
        'radius': radius
    }
