import streamlit as st
import pandas as pd
import numpy as np
import networkx as nx
import folium
from folium.plugins import MarkerCluster, AntPath
import requests
from datetime import datetime

# Set the page configuration first (before any Streamlit command)
st.set_page_config(page_title="Flight Services Hub", layout="wide")

# Function for Flight Network Visualizer
def flight_network_visualizer():
    # Load datasets
    airlines = pd.read_csv(r"C:\Users\vinith\OneDrive\Desktop\flight.py\data\airlines.csv")
    routes = pd.read_csv(r"C:\Users\vinith\OneDrive\Desktop\flight.py\data\routes.csv")
    airports = pd.read_csv(r"C:\Users\vinith\OneDrive\Desktop\flight.py\data\airports-extended.csv")

    # Data Cleaning and Preprocessing
    routes.replace('\\N', np.nan, inplace=True)
    routes.dropna(axis=0, how='any', inplace=True)
    routes['airline ID'] = routes['airline ID'].astype(int)

    # Rename airport columns for consistency
    new_column_names = [
        'id', 'airport.name', 'city.name', 'country.name', 'IATA', 'ICAO',
        'lat', 'long', 'altitude', 'tz.offset', 'DST', 'tz.name',
        'airport.type', 'source.data'
    ]
    airports.columns = new_column_names

    # Merge datasets
    merged_df = pd.merge(routes, airlines, left_on='airline ID', right_on='Airline ID', how='left')
    keep_col = ['airline', 'airline ID', 'Name', 'Country',
                ' source airport', ' source airport id',
                ' destination apirport', ' destination airport id',
                ' codeshare', ' stops', ' equipment', 'Active']
    merged_df = merged_df[keep_col]

    # Merge with airports data for source and destination airports
    merged_df = pd.merge(merged_df, airports, left_on=' source airport', right_on='IATA', how='left')
    merged_df = pd.merge(merged_df, airports, left_on=' destination apirport', right_on='IATA', how='left')

    # Select relevant columns for analysis
    routes_df = merged_df[['Name', 'Country',
                           'airport.name_x', 'city.name_x', 'country.name_x',
                           'lat_x', 'long_x',
                           'airport.name_y', 'city.name_y', 'country.name_y',
                           'lat_y', 'long_y', 'IATA_x', 'IATA_y']]

    # Create a directed graph
    G = nx.DiGraph()
    for _, row in routes_df.iterrows():
        source = row['IATA_x']
        destination = row['IATA_y']
        source_lat, source_long = row['lat_x'], row['long_x']
        dest_lat, dest_long = row['lat_y'], row['long_y']
        distance = np.sqrt((dest_lat - source_lat)**2 + (dest_long - source_long)**2)
        G.add_edge(source, destination, weight=distance)

    # Streamlit UI
    st.title("✈️ Real-Time Animated Flight Route Visualizer")

    # Sidebar for inputs
    st.sidebar.header("Flight Route Finder")
    source_airport = st.sidebar.selectbox(
        "Select Source Airport",
        sorted(airports['IATA'].dropna().unique()),
        help="Choose the source airport IATA code"
    )
    destination_airport = st.sidebar.selectbox(
        "Select Destination Airport",
        sorted(airports['IATA'].dropna().unique()),
        help="Choose the destination airport IATA code"
    )

    if st.sidebar.button('Show Animated Flight Path 🚀'):
        if source_airport not in G or destination_airport not in G:
            st.error("Invalid IATA code. Please select valid source and destination airports.")
        else:
            try:
                # Find the shortest path
                shortest_path = nx.dijkstra_path(G, source_airport, destination_airport, weight='weight')
                st.success(f"Shortest Path from **{source_airport}** to **{destination_airport}**")

                # Display connections on the flight path
                st.subheader("Airport Connections on the Flight Path")
                for i in range(len(shortest_path) - 1):
                    start = shortest_path[i]
                    end = shortest_path[i + 1]
                    start_row = routes_df[routes_df['IATA_x'] == start].iloc[0]
                    end_row = routes_df[routes_df['IATA_y'] == end].iloc[0]
                    st.write(f"{start_row['airport.name_x']} → {end_row['airport.name_y']}")

                # Create Folium map
                start_row = routes_df[routes_df['IATA_x'] == source_airport].iloc[0]
                folium_map = folium.Map(location=[start_row['lat_x'], start_row['long_x']], zoom_start=4)
                marker_cluster = MarkerCluster().add_to(folium_map)

                # Add start and end markers
                folium.Marker(
                    [start_row['lat_x'], start_row['long_x']],
                    popup=f"Start: {start_row['airport.name_x']} ({source_airport})",
                    icon=folium.Icon(color='green')
                ).add_to(marker_cluster)

                end_marker = routes_df[routes_df['IATA_y'] == destination_airport].iloc[0]
                folium.Marker(
                    [end_marker['lat_y'], end_marker['long_y']],
                    popup=f"End: {end_marker['airport.name_y']} ({destination_airport})",
                    icon=folium.Icon(color='red')
                ).add_to(marker_cluster)

                # Add markers for all airports in the path
                for airport_code in shortest_path:
                    airport_row = routes_df[routes_df['IATA_x'] == airport_code].iloc[0]
                    folium.Marker(
                        location=(airport_row['lat_x'], airport_row['long_x']),
                        tooltip=f"{airport_row['airport.name_x']} ({airport_row['IATA_x']})",
                        icon=folium.Icon(color="blue", icon="plane", prefix="fa")
                    ).add_to(marker_cluster)

                # Add animated paths
                for i in range(len(shortest_path) - 1):
                    start = shortest_path[i]
                    end = shortest_path[i + 1]
                    start_row = routes_df[routes_df['IATA_x'] == start].iloc[0]
                    end_row = routes_df[routes_df['IATA_y'] == end].iloc[0]
                    AntPath(
                        locations=[(start_row['lat_x'], start_row['long_x']),
                                   (end_row['lat_y'], end_row['long_y'])],
                        color='blue', weight=5, dash_array=[10, 20], delay=500
                    ).add_to(folium_map)

                # Display map
                st.components.v1.html(folium_map._repr_html_(), height=500)
            except nx.NetworkXNoPath:
                st.error(f"No path found between {source_airport} and {destination_airport}.")

# Function for Enhanced Flight Connection Path Finder
def flight_connection_path_finder():
    # Function to fetch flight data from AviationStack API
    def get_flights_from_aviationstack(source, destination):
        url = "https://api.aviationstack.com/v1/flights"
        params = {
            'access_key': '8924ace71edd2550178355fa80b0bded',  # Replace with your API key
            'dep_iata': source,           # Source airport IATA
            'arr_iata': destination       # Destination airport IATA
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Failed to fetch flights. Error: {response.status_code}")
            return None

    # Main function for Streamlit application
    st.title("✈️ Enhanced Flight Connection Path Finder ✈️")
    st.markdown("""This enhanced app allows you to search for available flights between any two airports by providing their **IATA codes**. You can also filter flights by **airline**, **date**, and view detailed flight information!""")
    
    # Input fields for source and destination airport IATA codes
    source = st.text_input("Source Airport IATA Code", "", placeholder="e.g., JFK").strip().upper()
    destination = st.text_input("Destination Airport IATA Code", "", placeholder="e.g., LHR").strip().upper()
    
    # Add date filtering option
    st.markdown("### Filter Options")
    airline_filter = st.text_input("Filter by Airline (Optional)", "", placeholder="e.g., Delta Air Lines").strip().title()
    date_filter = st.date_input("Filter by Date", key="date_filter")

    # Button to trigger flight search
    if st.button("Search Flights"):
        if source and destination:
            st.info(f"Searching for flights from **{source}** to **{destination}** ...")
            flight_data = get_flights_from_aviationstack(source, destination)
            if flight_data:
                flights = flight_data.get("data", [])
                if flights:
                    st.success(f"Found {len(flights)} flight(s).")
                    for flight in flights:
                        st.subheader(f"Flight {flight['flight']['iata']} ({flight['airline']['name']})")
                        st.write(f"Departure: {flight['departure']['estimated']} - {flight['departure']['airport']}")
                        st.write(f"Arrival: {flight['arrival']['estimated']} - {flight['arrival']['airport']}")
                        st.write(f"Aircraft: {flight['aircraft']['model']}")
                        st.write(f"Status: {flight['flight_status']}")
                        st.write("---")
                else:
                    st.warning("No flights found for the specified route.")
            else:
                st.error("Failed to retrieve flight data.")
        else:
            st.error("Please enter both source and destination airport codes.")

# Main function to select which project to run
def main():
    project = st.radio("Choose the project to run:", ("Flight Network Visualizer", "Enhanced Flight Connection Path Finder"))
    
    if project == "Flight Network Visualizer":
        flight_network_visualizer()
    elif project == "Enhanced Flight Connection Path Finder":
        flight_connection_path_finder()

if __name__ == "__main__":
    main()
