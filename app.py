import streamlit as st
import folium
from streamlit_folium import st_folium
import geopandas as gpd
import pandas as pd
import os

from api_handlers import get_openweather_data, get_tomtom_traffic
from config import DRIVE_TIME_OPTIONS, TAMPA_LAT, TAMPA_LON
from scoring import apply_scoring
from routing import generate_loop_route
import map_utils

# Page Config
st.set_page_config(page_title="ADAS Routing Engine", layout="wide")

# Force early Streamlit Secrets initialization parsing (Python 3.13 fix)
try:
    _ = st.secrets
except Exception:
    pass

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
    weather = get_openweather_data(TAMPA_LAT, TAMPA_LON)
    traffic = get_tomtom_traffic(TAMPA_LAT, TAMPA_LON, radius=10000)
    return weather, traffic

weather_data, traffic_data = fetch_live_data()

# 3. Apply Complexity Scoring Engine
roads_gdf = apply_scoring(roads_gdf, weather_data)

# 4. Map Logic
if roads_gdf is not None:
    # Sidebar: Complexity Filter
    st.sidebar.markdown("### 🎛️ Live Metrics")
    
    # Debug: Surface exact API connection failures to the Streamlit UI
    if not weather_data:
        st.sidebar.error("⚠️ Weather API Offline. Check Streamlit Secrets.")
    if not traffic_data:
        st.sidebar.error("⚠️ Traffic API Offline. Check Streamlit Secrets.")
        
    st.sidebar.metric("Temp", f"{weather_data['temp']} °F" if weather_data else "N/A", weather_data['conditions'] if weather_data else "N/A")
    st.sidebar.metric("Solar Altitude", f"{weather_data['solar_altitude']}°" if weather_data else "N/A")
    st.sidebar.metric("Active Incidents", len(traffic_data) if traffic_data else 0)
    st.sidebar.markdown("---")
    
    max_score = int(roads_gdf['complexity'].max()) if not roads_gdf['complexity'].empty else 100
    max_score = max(1, max_score) # Prevent slider crash if max is 0
    risk_threshold = st.sidebar.slider("Minimum Complexity Score", 0, max_score, 0)
    filtered_gdf = roads_gdf[roads_gdf['complexity'] >= risk_threshold]
    
    # Dynamic Color Thresholds
    p75 = roads_gdf['complexity'].quantile(0.75) if not roads_gdf.empty else 40
    p90 = roads_gdf['complexity'].quantile(0.90) if not roads_gdf.empty else 60
    
    # Build Map
    m = map_utils.build_base_map()
    
    map_utils.add_scored_roads_layer(m, filtered_gdf, p75, p90)
    map_utils.add_roundabouts_layer(m, roundabouts_gdf)
    map_utils.add_disengagements_layer(m, fsd_df)
    map_utils.add_live_traffic_layer(m, traffic_data)

    # Add Layer Control to toggle Data Feeds
    folium.LayerControl(collapsed=False).add_to(m)

    st.sidebar.markdown("### DATA COLLECTION ROUTING")
    st.sidebar.markdown("<span style='color: #888; font-size: 0.9rem;'>Generate a high-yield loop from the Depot to capture ADAS Edge Cases.</span>", unsafe_allow_html=True)
    
    # Initialize session state for routing
    if 'route_coords' not in st.session_state:
        st.session_state.route_coords = None
        st.session_state.route_metrics = None
    
    selected_time_label = st.sidebar.selectbox("Target Collection Duration", list(DRIVE_TIME_OPTIONS.keys()))
    drive_time_mins = DRIVE_TIME_OPTIONS[selected_time_label]
    
    generate_route = st.sidebar.button("INITIALIZE ROUTE")

    if generate_route:
        with st.spinner("Initializing OSMNX Graph and Calculating Optimal Path..."):
            try:
                # Build route via extracted routing module
                route_result = generate_loop_route(drive_time_mins, filtered_gdf, traffic_data)
                st.session_state.route_coords = route_result['coords']
                st.session_state.route_metrics = route_result['metrics']
                
                st.sidebar.success("✅ ROUTE COMPILED.")
                
            except Exception as e:
                st.sidebar.error(f"ROUTING ERROR: {str(e)}")

    # ALWAYS check session state to draw route and show manifest
    if st.session_state.route_coords:
        route_coords = st.session_state.route_coords
        metrics = st.session_state.route_metrics
        
        map_utils.draw_route(m, route_coords, metrics)
        
        st.sidebar.markdown(f"""
        **DRIVER DISPATCH MANIFEST**
        * **Distance:** {metrics['dist']:.1f} miles
        * **Est. Duration:** {metrics['time']:.0f} mins
        * **Nodes Traversed:** {metrics['nodes']} Intersections
        * **Objective:** {metrics.get('explanation', 'Traverse mapped network geometry.')}
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
