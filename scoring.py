# scoring.py
import pandas as pd
from config import BASE_COMPLEXITY

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

def calculate_complexity(row, weather):
    score = BASE_COMPLEXITY
    
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

def apply_scoring(roads_gdf, weather_data):
    """
    Applies complexity and occlusion risk scoring to the roads GeoDataFrame.
    """
    if roads_gdf is not None and not roads_gdf.empty:
        roads_gdf['complexity'] = roads_gdf.apply(lambda row: calculate_complexity(row, weather_data), axis=1)
        roads_gdf['occlusion_risk'] = roads_gdf['bearing'].apply(get_solar_occlusion_hours)
    return roads_gdf
