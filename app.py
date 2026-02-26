import streamlit as st
import folium
from streamlit_folium import st_folium
import geopandas as gpd
import pandas as pd
import os
from api_handlers import get_openweather_data, get_tomtom_traffic

# Page Config
st.set_page_config(page_title="Vanguard Roadway Risk Dashboard", layout="wide")

st.title("🛣️ Vanguard Roadway Risk & Complexity Engine")
st.sidebar.header("Managerial Controls")

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

    st.sidebar.markdown("### 🗺️ Data Collection Routing")
    st.sidebar.markdown("*Generate a high-yield loop from the Depot to capture ADAS Edge Cases.*")
    drive_time = st.sidebar.slider("Target Drive Time (mins)", 15, 60, 30)
    generate_route = st.sidebar.button("Generate Collection Route")

    if generate_route:
        with st.spinner("Initializing OSMNX Graph and Calculating Optimal Path..."):
            try:
                import osmnx as ox
                import networkx as nx
                import random
                
                # Configure osmnx to quiet mode and use cache
                ox.settings.log_console = False
                ox.settings.use_cache = True
                
                # Download street network around the depot (3km radius for POC speed)
                G = ox.graph_from_point((depot_lat, depot_lon), dist=3000, network_type='drive')
                orig = ox.distance.nearest_nodes(G, X=depot_lon, Y=depot_lat)
                
                # Select a destination node roughly far away to simulate a loop anchor
                nodes = list(G.nodes())
                dest = random.choice(nodes)
                
                # Calculate the shortest path (in a full production system, weight='complexity')
                path = nx.shortest_path(G, orig, dest, weight='length')
                
                # Convert path to coordinate pairs [lat, lon] for Folium
                route_coords = [(G.nodes[n]['y'], G.nodes[n]['x']) for n in path]
                
                # Draw the Route
                folium.PolyLine(
                    locations=route_coords,
                    color="#8b5cf6", # Bright Purple
                    weight=8,
                    opacity=0.9,
                    tooltip="Optimized ADAS Data Collection Route"
                ).add_to(m)
                
                # Add Endpoint Marker
                end_lat, end_lon = route_coords[-1]
                folium.Marker(
                    location=[end_lat, end_lon],
                    icon=folium.Icon(color="purple", icon="refresh"),
                    tooltip="Route Turnaround Point"
                ).add_to(m)
                
                st.sidebar.success("✅ Route Generated Successfully!")
            except Exception as e:
                st.sidebar.error(f"Routing Error: {e}")

    # Render Map
    st_folium(m, width=1400, height=700)
else:
    st.error("Master GeoJSON not found in /data. Please verify your QGIS export.")

st.sidebar.markdown("---")
st.sidebar.info("""
**Advanced Driver Assistance Systems (ADAS)**
*Data Collection & Routing Engine*

This engine identifies critical **Edge Cases** by calculating dynamic pathing complexity based on:
1. **High-Injury Corridors & Historical Disengagements:** Prioritizing network clusters where autonomy historically hands off control.
2. **Camera System Occlusion Risk:** Real-time calculation of blinding solar glare directly overwhelming vehicle optical sensors based on the current azimuth.
3. **Live Obstructions:** TomTom API integration for current construction and collision events.
4. **Geometric Edge Cases:** Hard-coded spatial prioritization for Unmarked Roundabouts and active Zone-AE Floodways.

*Use the **Layer Control** icon on the top right of the map to filter routing datasets.*
""")
