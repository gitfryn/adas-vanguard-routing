# Vanguard ADAS Data Collection Router

An open-source intelligence dashboard designed for Advanced Driver Assistance Systems (ADAS) operations. This engine calculates dynamic pathing complexity using live APIs and open data to prioritize data-collection yields along spatial edge cases.

## Core Features

*   **Geospatial Complexity Scoring:** Dynamically weighs road segments based on historical High-Injury Networks.
*   **Live Weather & Solar Occlusion Modeling:** Integrates with OpenWeatherMap API to calculate current solar azimuth and altitude, applying massive occlusion penalties to optical sensors pointing directly into the sun.
*   **Dynamic Obstruction Mapping:** Connects to the TomTom Traffic API to pull real-time construction and collision events disrupting the grid.
*   **Historical Disengagement Layering:** Simulates spatial clustering of ADAS failures to highlight anomalous system behavior.
*   **Active Route Generation:** Utilizes `osmnx` and `networkx` to calculate high-yield autonomous driving loop routes through the most complex geometries available within a given timeframe.

## Local Installation

1.  Clone this repository.
2.  Install the required dependencies: `pip install -r requirements.txt`
3.  Set up your `.env` file with the necessary API keys (`OPENWEATHER_API_KEY` and `TOMTOM_API_KEY`). An example `.env.example` is provided.
4.  Run the Streamlit application: `streamlit run app.py`

## Streamlit Cloud Deployment

This repository is structured for immediate deployment on Streamlit Community Cloud:

1.  Push this code to your GitHub account.
2.  Log in to [Streamlit Community Cloud](https://streamlit.io/cloud).
3.  Click **New app** and authorize your GitHub account.
4.  Select your repository and branch.
5.  Set the Main file path to `app.py`.
6.  **Crucial:** Click **Advanced settings** and paste the contents of your `.env` file into the `Secrets` text box before deploying.
7.  Click **Deploy!**

## Tech Stack
*   **Frontend:** Streamlit, Folium
*   **Data Processing:** GeoPandas, Pandas, Numpy
*   **Routing:** OSMnx, NetworkX
*   **Live Data:** OpenWeatherMap API, TomTom Traffic API
