# Vanguard ADAS Data Collection Router

An open-source intelligence dashboard designed for Advanced Driver Assistance Systems (ADAS) operations. This engine calculates dynamic pathing complexity using live APIs and open data to prioritize data-collection yields along spatial edge cases.

## Currently Implemented Features

*   **Geospatial Complexity Scoring:** Dynamically weighs road segments based on High-Injury Networks and FDOT flood zones.
*   **Live Weather & Solar Occlusion Modeling:** Integrates with OpenWeatherMap API to calculate current solar azimuth and altitude, flagging optical occlusion for vehicles driving directly into low-horizon glare.
*   **Dynamic Obstruction Avoidance:** Connects to the TomTom API to pull real-time construction and collision events.
*   **Complexity-Aware Routing Engine:** Utilizes `osmnx` and `networkx` to calculate high-yield autonomous driving loop routes. The algorithm mathematically optimizes for complex geometry, automatically deviating from the fastest path to prioritize hazardous intersections and avoid live traffic blockages.

## Product Roadmap (Future Work)

*   **Spatial Clustering Analytics:** Apply DBSCAN algorithms to automatically identify statistically significant groupings of historical ADAS failures.
*   **Dynamic Radius Adjustment:** Scale the grid download radius algorithmically based on real-time traffic density rather than static time thresholds.
*   **GPX / GeoJSON Download:** Add export functionality for the generated Driver Manifest to be loaded directly into fleet management software.
*   **Asynchronous API Fetches:** Utilize `asyncio` to pull weather and traffic layers simultaneously to drop initial map-render latencies.

## Local Setup & Reproducibility

1.  Clone this repository.
2.  Install the required dependencies inside your virtual environment. The app was built using **Python 3.11**.
    *   *Note: For strict reproducibility, we recommend using `uv` or `Poetry` to lock versions.*
    *   `pip install -r requirements.txt`
3.  Set up your `.env` file with the necessary API keys (`OPENWEATHER_API_KEY` and `TOMTOM_API_KEY`). An example `.env.example` is provided in the repository root.
    *   *Note: If no API keys are provided, the map will still render local datasets but live layers will be hidden gracefully.*
4.  Run the Streamlit application: `streamlit run app.py`

## Streamlit Cloud Deployment

This repository is structured for immediate deployment on Streamlit Community Cloud:

1.  Push this code to your GitHub account.
2.  Log in to [Streamlit Community Cloud](https://streamlit.io/cloud).
3.  Click **New app** and authorize your GitHub account.
4.  Select your repository and branch.
5.  Set the Main file path to `app.py`.
6.  **Crucial TOML Formatting:** Click **Advanced settings** -> **Secrets**. Do NOT just paste the `.env` text. You MUST wrap your keys in double-quotes (`"`) to satisfy the Streamlit TOML parser, or the app will immediately crash.
    ```toml
    OPENWEATHER_API_KEY="your_api_key_here"
    TOMTOM_API_KEY="your_api_key_here"
    ```
7.  Click **Deploy!**

*(Note: Streamlit Community Cloud puts apps to "sleep" after 7 days of inactivity. Simply visit the URL to wake the app back up; it may take ~60 seconds to boot the first time.)*

## Tech Stack & Architecture
*   **Frontend UI:** Streamlit
*   **Web Mapping:** Folium (`map_utils.py`)
*   **Data Processing Pipeline:** GeoPandas, Pandas, Numpy
*   **Graph Routing & Cost Matrix:** OSMnx, NetworkX (`routing.py`)
*   **Complexity Heuristics:** Custom Python Math (`scoring.py`)
*   **Live Data Fetching:** OpenWeatherMap API, TomTom Traffic API (`api_handlers.py`)
