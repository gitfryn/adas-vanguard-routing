import streamlit as st
import folium
from streamlit_folium import st_folium
import geopandas as gpd
import pandas as pd
import os
from api_handlers import get_openweather_data, get_tomtom_traffic

# Page Config
# Page Config
st.set_page_config(page_title="ADAS Routing Engine", layout="wide")

# Inject Custom Tesla-Inspired CSS
st.markdown("""
<style>
    /* Global Background and Fonts */
    .stApp {
        background-color: #111111;
        color: #f4f4f4;
        font-family: 'Helvetica Neue', Arial, sans-serif;
    }
    
    /* Headers */
    h1, h2, h3, h4 {
        font-weight: 500 !important;
        letter-spacing: 1.5px;
        color: #ffffff !important;
        text-transform: uppercase;
    }
    
    /* Primary buttons */
    .stButton>button {
        background-color: #e82127; /* Tesla Red */
        color: white;
        border-radius: 4px;
        border: none;
        padding: 10px 24px;
        font-weight: 600;
        letter-spacing: 1px;
        text-transform: uppercase;
        transition: all 0.3s ease;
        width: 100%;
    }
    
    .stButton>button:hover {
        background-color: #c01c21;
        box-shadow: 0 4px 12px rgba(232, 33, 39, 0.4);
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #000000;
        border-right: 1px solid #333333;
    }
    
    /* Sliders and Metrics */
    div[data-testid="stMetricValue"] {
        color: #e82127;
        font-weight: 700;
    }
    
    div[data-baseweb="slider"] {
        accent-color: #e82127 !important;
    }
    
    /* Metric label text */
    div[data-testid="stMetricLabel"] {
        color: #888888;
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
</style>
""", unsafe_allow_html=True)

st.title("ADAS Risk & Complexity Engine")
st.sidebar.markdown("### SYSTEM CONTROLS")

# 1. Load Data
@st.cache_data
def load_data():
    data_path = "data/vanguard_master_roads.geojson"
    roundabout_path = "data/median_type_roundabout.geojson"
    fsd_path = "data/mock_fsd_disengagements.csv"
    
    roads_gdf = None
    roundabouts_gdf = None
    fsd_df = None
    
    if os.path.exists(data_path):
        roads_gdf = gpd.read_file(data_path)
        if roads_gdf.crs != "EPSG:4326":
            roads_gdf = roads_gdf.to_crs("EPSG:4326")
            
    if os.path.exists(roundabout_path):
        roundabouts_gdf = gpd.read_file(roundabout_path)
        if roundabouts_gdf.crs != "EPSG:4326":
            roundabouts_gdf = roundabouts_gdf.to_crs("EPSG:4326")
        # Filter for codes 41 and 42 (Roundabouts)
        roundabouts_gdf = roundabouts_gdf[roundabouts_gdf['MEDIAN_TYP'].isin(['41', '42'])]
        
    if os.path.exists(fsd_path):
        fsd_df = pd.read_csv(fsd_path)
            
    return roads_gdf, roundabouts_gdf, fsd_df

roads_gdf, roundabouts_gdf, fsd_df = load_data()

# 2. Fetch Live APIs
@st.cache_data(ttl=300) # Cache for 5 minutes
def fetch_live_data():
    tampa_lat, tampa_lon = 27.9506, -82.4572
    weather = get_openweather_data(tampa_lat, tampa_lon)
    traffic = get_tomtom_traffic(tampa_lat, tampa_lon, radius=10000)
    return weather, traffic

weather_data, traffic_data = fetch_live_data()

# 3. Complexity Scoring Engine
def calculate_complexity(row, weather):
    score = 20 # Base line complexity
    
    # 1. HIN Network (30 pts)
    if pd.notna(row.get('hinHIN_Status')):
        rank = row.get('hinRank', 0)
        rank_score = min(20, (rank / 1000) * 20) if pd.notna(rank) else 0
        score += 10 + rank_score
        
    # 2. Flood Risk (25 pts)
    if str(row.get('fld_FLD')) == 'FLOOD_AE/A':
        if weather and weather.get('conditions') in ['Rain', 'Thunderstorm', 'Drizzle']:
            score += 25 # High risk if actively raining in a flood zone
        else:
            score += 10 # Base risk for simply being in a flood zone
            
    # 3. Solar Glare (20 pts)
    bearing = row.get('bearing')
    if pd.notna(bearing) and weather:
        alt = weather.get('solar_altitude', 90)
        azi = weather.get('solar_azimuth', 0)
        
        # If sun is low on the horizon (0 to 15 degrees)
        if 0 <= alt <= 15:
            # Check if road bearing points directly into the sun (within 15 degrees)
            diff = abs(bearing - azi)
            if diff <= 15 or diff >= 345:
                score += 20
                
    # 4. Traffic Penalty (Base hook - currently active incidents are visualized on map)
    # TODO: Spatial join with traffic_data to apply localized penalty
    # score += 20 if incident nearby
    
    return min(100, score)

def get_solar_occlusion_hours(bearing):
    if pd.isna(bearing):
        return "Unknown"
    # East-facing roads face sunrise glare
    if 60 <= bearing <= 120:
        return "Sunrise (approx 6:30 AM - 8:30 AM)"
    # West-facing roads face sunset glare
    elif 240 <= bearing <= 300:
        return "Sunset (approx 5:30 PM - 7:30 PM)"
    else:
        return "No Issue (North/South)"

# Apply Scoring and Attributes
if roads_gdf is not None:
    roads_gdf['complexity'] = roads_gdf.apply(lambda row: calculate_complexity(row, weather_data), axis=1)
    roads_gdf['occlusion_risk'] = roads_gdf['bearing'].apply(get_solar_occlusion_hours)

# 4. Map Logic
if roads_gdf is not None:
    # Sidebar: Complexity Filter
    st.sidebar.markdown("### 🎛️ Live Metrics")
    st.sidebar.metric("Temp", f"{weather_data['temp']} °F" if weather_data else "N/A", weather_data['conditions'] if weather_data else "N/A")
    st.sidebar.metric("Solar Altitude", f"{weather_data['solar_altitude']}°" if weather_data else "N/A")
    st.sidebar.metric("Active Incidents", len(traffic_data) if traffic_data else 0)
    st.sidebar.markdown("---")
    
    risk_threshold = st.sidebar.slider("Minimum Complexity Score", 0, 100, 0)
    
    filtered_gdf = roads_gdf[roads_gdf['complexity'] >= risk_threshold]
    
    # Center on Tampa per Blueprint
    m = folium.Map(location=[27.9506, -82.4572], zoom_start=12, tiles=None, control_scale=True)
    
    # Rename the base tile layer so 'cartodbpositron' doesn't show in the LayerControl
    folium.TileLayer('cartodbpositron', name='Base Map (Light)', control=True).add_to(m)

    def get_color(score):
        if score < 40: return 'green'
        if score < 70: return 'orange'
        return 'red'

    # Add ADAS Data Collection Depot
    depot_lat, depot_lon = 28.0543, -82.4597
    folium.Marker(
        location=[depot_lat, depot_lon],
        icon=folium.Icon(color="black", icon="flag", prefix='fa'),
        tooltip=folium.Tooltip("ADAS Data Collection Depot<br>11945 N Florida Ave", style="font-weight: bold; color: #fff; background-color: #000;"),
    ).add_to(m)

    # Add Road Segments IF any satisfy the minimum threshold
    if not filtered_gdf.empty:
        fg_roads = folium.FeatureGroup(name="🛣️ Roadway Complexity (Live)")
        folium.GeoJson(
            filtered_gdf,
            name="Hillsborough Road Network",
            style_function=lambda x: {
                'color': get_color(x['properties'].get('complexity', 0)),
                'weight': 3 if x['properties'].get('complexity', 0) < 70 else 5,
                'opacity': 0.8
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['NAME', 'complexity', 'bearing', 'occlusion_risk', 'hinHIN_Status', 'fld_FLD'], 
                aliases=['Road Name:', 'Complexity Score:', 'Bearing:', 'Solar Occlusion Risk:', 'HIN Status:', 'Flood Zone:']
            )
        ).add_to(fg_roads)
        fg_roads.add_to(m)
    else:
        st.warning(f"No roads found with a complexity score matching or exceeding {risk_threshold}.")

    # Add Roundabouts Layer
    if roundabouts_gdf is not None and not roundabouts_gdf.empty:
        fg_roundabouts = folium.FeatureGroup(name="🔄 Roundabouts (Edge Cases)", show=True)
        folium.GeoJson(
            roundabouts_gdf,
            style_function=lambda x: {
                'color': '#3b82f6', # Bright Blue
                'weight': 6,
                'opacity': 0.9,
                'dashArray': '4, 4'
            },
            tooltip="FSD Edge Case: Roundabout Intersection"
        ).add_to(fg_roundabouts)
        fg_roundabouts.add_to(m)

    # Add Historical ADAS Disengagements Layer
    if fsd_df is not None and not fsd_df.empty:
        fg_fsd = folium.FeatureGroup(name="🛑 Autonomy Disengagements (Historical)", show=True)
        for _, row in fsd_df.iterrows():
            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=6,
                color='purple',
                fill=True,
                fillColor='purple',
                fillOpacity=0.7,
                tooltip=f"ADAS Disengagement<br>Event Trigger: {row['reason']}<br>Severity: {row['severity']}"
            ).add_to(fg_fsd)
        fg_fsd.add_to(m)

    # Add Live Traffic Incidents Layer
    if traffic_data:
        fg_traffic = folium.FeatureGroup(name="🚧 Live Traffic Obstructions", show=True)
        for inc in traffic_data:
            geom = inc.get('geometry', [])
            if geom and len(geom) > 0:
                first_coord = geom[0]
                lat, lon = first_coord[1], first_coord[0]
                severity = inc.get('magnitude', 0)
                folium.Marker(
                    location=[lat, lon],
                    icon=folium.Icon(color="red" if severity >= 3 else "orange", icon="info-sign"),
                    tooltip=folium.Tooltip(f"Active TomTom Incident (Severity: {severity})")
                ).add_to(fg_traffic)
        fg_traffic.add_to(m)

    # Add Layer Control to toggle Data Feeds
    folium.LayerControl(collapsed=False).add_to(m)

    st.sidebar.markdown("### DATA COLLECTION ROUTING")
    st.sidebar.markdown("<span style='color: #888; font-size: 0.9rem;'>Generate a high-yield loop from the Depot to capture ADAS Edge Cases.</span>", unsafe_allow_html=True)
    
    # Initialize session state for routing
    if 'route_coords' not in st.session_state:
        st.session_state.route_coords = None
        st.session_state.route_metrics = None
    
    # Locked intervals for drive time
    drive_time_options = {
        "30 Minutes": 30,
        "1 Hour": 60,
        "2 Hours": 120,
        "4 Hours": 240
    }
    selected_time_label = st.sidebar.selectbox("Target Collection Duration", list(drive_time_options.keys()))
    drive_time_mins = drive_time_options[selected_time_label]
    
    generate_route = st.sidebar.button("INITIALIZE ROUTE")

    if generate_route:
        with st.spinner("Initializing OSMNX Graph and Calculating Optimal Path..."):
            try:
                import osmnx as ox
                import networkx as nx
                import random
                
                # Configure osmnx to quiet mode and use cache
                ox.settings.log_console = False
                ox.settings.use_cache = True
                
                # Expand radius slightly based on requested time (POC approximation)
                radius = 3000 if drive_time_mins <= 60 else 6000
                st.sidebar.info(f"Downloading {radius}m network grid...")
                
                from shapely.geometry import Point
                
                # Download street network around the depot
                G = ox.graph_from_point((depot_lat, depot_lon), dist=radius, network_type='drive')
                
                # Project graph to avoid the scikit-learn unprojected error
                G_proj = ox.project_graph(G)
                
                import math
                
                # Project the depot coordinates to match the graph's generated UTM CRS
                depot_point = Point(depot_lon, depot_lat)
                depot_proj, _ = ox.projection.project_geometry(depot_point, to_crs=G_proj.graph['crs'])
                orig = ox.distance.nearest_nodes(G_proj, X=depot_proj.x, Y=depot_proj.y)
                
                nodes = list(G_proj.nodes())
                
                # Calculate target network distance (Average collection speed: 30mph or 13.4 m/s)
                target_distance_m = drive_time_mins * 60 * 13.4
                
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
                        sub_path = nx.shortest_path(G_proj, current_node, next_dest, weight='length')
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
                    home_path = nx.shortest_path(G_proj, current_node, orig, weight='length')
                    path.extend(home_path[1:])
                except Exception:
                    pass
                
                # Convert path to coordinate pairs [lat, lon] for Folium
                route_coords = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in path]
                
                # Calculate Final Mathematical Route Attributes
                route_gdf = ox.routing.route_to_gdf(G_proj, path, weight='length')
                total_length_m = route_gdf['length'].sum()
                total_length_mi = total_length_m * 0.000621371
                
                # Assuming 30mph (13.4 m/s) average ADAS collection speed in Tampa
                est_time_mins = total_length_m / 13.4 / 60
                
                # Save to session state
                st.session_state.route_coords = route_coords
                st.session_state.route_metrics = {
                    'dist': total_length_mi,
                    'time': est_time_mins,
                    'nodes': len(path)
                }
                
                st.sidebar.success("✅ ROUTE COMPILED.")
                
            except Exception as e:
                st.sidebar.error(f"ROUTING ERROR: {str(e)}")

    # ALWAYS check session state to draw route and show manifest
    if st.session_state.route_coords:
        route_coords = st.session_state.route_coords
        metrics = st.session_state.route_metrics
        
        # Draw the Route
        folium.PolyLine(
            locations=route_coords,
            color="#e82127", # Tesla Red
            weight=6,
            opacity=0.9,
            tooltip=f"Optimized Collection Route ({metrics['dist']:.1f} mi)"
        ).add_to(m)
        
        # Add Endpoint Marker
        end_lat, end_lon = route_coords[-1]
        folium.Marker(
            location=[end_lat, end_lon],
            icon=folium.Icon(color="red", icon="refresh"),
            tooltip="Route Turnaround Point"
        ).add_to(m)
        
        # Force Map to Zoom to the Route
        m.fit_bounds(route_coords)
        
        st.sidebar.markdown(f"""
        **DRIVER DISPATCH MANIFEST**
        * **Distance:** {metrics['dist']:.1f} miles
        * **Est. Duration:** {metrics['time']:.0f} mins
        * **Nodes Traversed:** {metrics['nodes']} Intersections
        * **Objective:** Prioritize system engagement through generated high-complexity grid.
        """)
        
        if st.sidebar.button("CLEAR ROUTE"):
            st.session_state.route_coords = None
            st.session_state.route_metrics = None
            st.rerun()

    # Render Map - Pass returned_objects=[] to completely decouple map interactions from triggering a Python backend refresh
    st_folium(m, width=1400, height=700, returned_objects=[], use_container_width=True)
else:
    st.error("Master GeoJSON not found in /data. Please verify your QGIS export.")

st.sidebar.markdown("---")
st.sidebar.info("""
**Advanced Driver Assistance Systems (ADAS)**
*Data Collection & Routing Engine*

This engine identifies critical **Edge Cases** by calculating dynamic pathing complexity based on:
1. **High-Injury Corridors & Historical Disengagements:** Prioritizing network clusters where autonomy historically hands off control.
2. **Camera System Occlusion Risk:** Real-time calculation of blinding solar glare directly overwhelming vehicle optical sensors.
3. **Live Obstructions:** TomTom API integration for current construction and collision events.
4. **Geometric Edge Cases:** Hard-coded spatial prioritization for Unmarked Roundabouts and active Zone-AE Floodways.
""")
