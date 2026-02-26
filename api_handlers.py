import os
import requests
import streamlit as st
from dotenv import load_dotenv

# Load environment variables from the .env file (for local development)
load_dotenv()

# Globals are removed to prevent Streamlit Cloud from caching empty API keys on initial module import.

def get_tomtom_traffic(lat, lon, radius=5000):
    """
    Fetch live traffic incidents from TomTom API for a given location.
    Requires TOMTOM_API_KEY to be set in the .env file.
    Radius is in meters (max 10,000). Returns list of significant incidents.
    """
    api_key = os.getenv("TOMTOM_API_KEY")
    if not api_key:
        try:
            import streamlit as st
            # Avoid strict .get() or dictionary lookup on uninitialized st.secrets to prevent KeyError
            if "TOMTOM_API_KEY" in st.secrets:
                api_key = st.secrets["TOMTOM_API_KEY"]
        except Exception as e:
            import streamlit as st
            st.error(f"TomTom Secret Extraction Failed: {e}")
            pass

    if not api_key:
        import streamlit as st
        st.error("Warning: TOMTOM_API_KEY is missing/empty. Returning empty traffic data.")
        return []
        
    # Bounding box is required for the Incident Details API. 
    # For a simple radius, we approximate the bbox based on lat/lon
    # 1 degree lat is ~111km. 5km is ~0.045 degrees.
    offset = (radius / 111000)
    min_lat, max_lat = lat - offset, lat + offset
    min_lon, max_lon = lon - offset, lon + offset
    bbox = f"{min_lon},{min_lat},{max_lon},{max_lat}"

    url = f"https://api.tomtom.com/traffic/services/5/incidentDetails?key={api_key}&bbox={bbox}&fields={'{'}incidents{'{'}type,geometry{'{'}type,coordinates{'}'},properties{'{'}iconCategory,magnitudeOfDelay{'}'}{'}'}{'}'}&language=en-GB&categoryFilter=0,1,2,3,4,5,6,7,8,9,10,11,14"

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
            import streamlit as st
            st.error(f"TomTom HTTP Error {response.status_code}: {response.text}")
            return []
    except Exception as e:
        import streamlit as st
        st.error(f"TomTom Connect Exception: {e}")
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
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        try:
            import streamlit as st
            if "OPENWEATHER_API_KEY" in st.secrets:
                api_key = st.secrets["OPENWEATHER_API_KEY"]
        except Exception as e:
            import streamlit as st
            st.error(f"OpenWeather Secret Extraction Failed: {e}")
            pass

    if not api_key:
        import streamlit as st
        st.error("Warning: OPENWEATHER_API_KEY is missing/empty. Returning empty weather data.")
        return None
        
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=imperial"
    
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
            import streamlit as st
            st.error(f"OpenWeather HTTP Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        import streamlit as st
        st.error(f"OpenWeather Connect Exception: {e}")
        return None
