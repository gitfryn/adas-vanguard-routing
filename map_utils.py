# map_utils.py
import folium
import streamlit as st
from config import TAMPA_LAT, TAMPA_LON, DEPOT_LAT, DEPOT_LON

# Removed global get_color in favor of dynamic scoping

def build_base_map():
    # Center on Tampa per Blueprint
    m = folium.Map(location=[TAMPA_LAT, TAMPA_LON], zoom_start=12, tiles=None, control_scale=True)
    # Rename the base tile layer so 'cartodbpositron' doesn't show in the LayerControl
    folium.TileLayer('cartodbpositron', name='Base Map (Light)', control=True).add_to(m)
    
    # Add ADAS Data Collection Depot
    folium.Marker(
        location=[DEPOT_LAT, DEPOT_LON],
        icon=folium.Icon(color="black", icon="flag", prefix='fa'),
        tooltip=folium.Tooltip(
            "ADAS Data Collection Depot<br>11945 N Florida Ave", 
            style="font-weight: bold; color: #fff; background-color: #000;"
        ),
    ).add_to(m)
    return m

def add_scored_roads_layer(m, filtered_gdf, p75=40, p90=60):
    if not filtered_gdf.empty:
        def dynamic_color(score_val):
            # Ensure score_val is safely comparable as a float
            try:
                score = float(score_val)
            except:
                score = 0.0
                
            if score < p75: return '#10b981' # Emerald Green
            if score < p90: return '#f59e0b' # Amber Orange
            return '#ef4444' # Rose Red
            
        fg_roads = folium.FeatureGroup(name="🛣️ Roadway Complexity (Live)")
        folium.GeoJson(
            filtered_gdf,
            name="Hillsborough Road Network",
            style_function=lambda x: {
                'color': dynamic_color(x['properties'].get('complexity', 0)),
                'weight': 3 if float(x['properties'].get('complexity', 0)) < p90 else 5,
                'opacity': 0.8
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['NAME', 'complexity', 'bearing', 'occlusion_risk', 'hinHIN_Status', 'fld_FLD'], 
                aliases=['Road Name:', 'Complexity Score:', 'Bearing:', 'Solar Occlusion Risk:', 'HIN Status:', 'Flood Zone:']
            )
        ).add_to(fg_roads)
        fg_roads.add_to(m)

def add_roundabouts_layer(m, roundabouts_gdf):
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

def add_disengagements_layer(m, fsd_df):
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
                tooltip=f"<b>ADAS Disengagement</b><br><b>Time:</b> {row['timestamp']}<br><b>Trigger:</b> {row['type']} ({row['severity']})<br><i>{row['notes']}</i>"
            ).add_to(fg_fsd)
        fg_fsd.add_to(m)

def add_live_traffic_layer(m, traffic_data):
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

def draw_route(m, route_coords, metrics):
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
