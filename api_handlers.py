import os
import requests
import streamlit as st
from dotenv import load_dotenv

# Load environment variables from the .env file (for local development)
load_dotenv()

# Fallback checking: first check local OS environment (from .env), then check Streamlit Cloud secrets
# Safely load API Keys handling both local (.env) and Streamlit Cloud (st.secrets)
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# If local variables are missing, carefully attempt to load from Streamlit Cloud Secrets Manager.
# We use a broad Exception catch here because Streamlit throws a specific `StreamlitSecretNotFoundError`
# if the TOML file isn't perfectly parsed yet (common in Python 3.13 fast-boots).
if not TOMTOM_API_KEY:
    try:
        from streamlit import secrets
        if "TOMTOM_API_KEY" in secrets:
            TOMTOM_API_KEY = secrets["TOMTOM_API_KEY"]
    except Exception as e:
        print(f"Skipping Streamlit Secrets for TomTom: {e}")

if not OPENWEATHER_API_KEY:
    try:
        from streamlit import secrets
        if "OPENWEATHER_API_KEY" in secrets:
            OPENWEATHER_API_KEY = secrets["OPENWEATHER_API_KEY"]
    except Exception as e:
        print(f"Skipping Streamlit Secrets for OpenWeather: {e}")

def get_tomtom_traffic(lat, lon, radius=5000):
    """
    Fetch live traffic incidents from TomTom API for a given location.
    Requires TOMTOM_API_KEY to be set in the .env file.
    Radius is in meters (max 10,000). Returns list of significant incidents.
    """
    if not TOMTOM_API_KEY:
        print("Warning: TOMTOM_API_KEY is missing. Returning empty traffic data.")
        return []
        
    # Bounding box is required for the Incident Details API. 
    # For a simple radius, we approximate the bbox based on lat/lon
    # 1 degree lat is ~111km. 5km is ~0.045 degrees.
    offset = (radius / 111000)
    min_lat, max_lat = lat - offset, lat + offset
    min_lon, max_lon = lon - offset, lon + offset
    bbox = f"{min_lon},{min_lat},{max_lon},{max_lat}"

    url = f"https://api.tomtom.com/traffic/services/5/incidentDetails?key={TOMTOM_API_KEY}&bbox={bbox}&fields={'{'}incidents{'{'}type,geometry{'{'}type,coordinates{'}'},properties{'{'}iconCategory,magnitudeOfDelay{'}'}{'}'}{'}'}&language=en-GB&categoryFilter=0,1,2,3,4,5,6,7,8,9,10,11,14"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            incidents = data.get('incidents', [])
            
            # Filter for meaningful delays or closures (magnitude 2, 3, or 4)
            # 1: Minor, 2: Moderate, 3: Major, 4: Unknown (often closures)
            significant_incidents = []
            for inc in incidents:
                mag = inc.get('properties', {}).get('magnitudeOfDelay', 0)
                if mag >= 2:
                    significant_incidents.append({
                        "type": inc.get('properties', {}).get('iconCategory', 'Unknown'),
                        "magnitude": mag,
                        "geometry": inc.get('geometry', {}).get('coordinates', [])
                    })
            
            return significant_incidents
        else:
            print(f"TomTom Error {response.status_code}: {response.text}")
            return []
    except Exception as e:
        print(f"TomTom Connect Error: {e}")
        return []

import datetime
import pytz
from pysolar.solar import get_altitude, get_azimuth

def get_openweather_data(lat, lon):
    """
    Fetch current weather conditions from OpenWeatherMap API for a given location.
    Requires OPENWEATHER_API_KEY to be set in the .env file.
    Returns weather details and calculates solar position.
    """
    if not OPENWEATHER_API_KEY:
        print("Warning: OPENWEATHER_API_KEY is missing. Returning empty weather data.")
        return None
        
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=imperial"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            # Calculate Solar Position
            tz = pytz.timezone('America/New_York')
            now = datetime.datetime.now(tz)
            altitude = get_altitude(lat, lon, now)
            azimuth = get_azimuth(lat, lon, now)
            
            return {
                "temp": data['main']['temp'],
                "conditions": data['weather'][0]['main'],
                "visibility_meters": data.get('visibility', 10000),
                "solar_altitude": round(altitude, 2),
                "solar_azimuth": round(azimuth, 2)
            }
        else:
            print(f"OpenWeather Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"OpenWeather Connect Error: {e}")
        return None
