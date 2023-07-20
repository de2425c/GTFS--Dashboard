import pandas as pd
import geopandas as gpd
from datetime import datetime
import osmnx as ox
import zipfile
from io import BytesIO
import json
import requests
import pickle5 as pickle
import urllib.request

import dash
from dash import dcc
from dash import html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go

from shapely.geometry import Point
from shapely.geometry import LineString
from google.transit import gtfs_realtime_pb2

from joblib import load

subfiles = ['bus_bronx', 'bus_brooklyn', 'bus_manhattan', 'bus_queens', 'bus_staten_island', 'subway', 'LIRR', 'MNR', 'bus_new_jersy', 'NJ_rail']
dataframes = {}

# pickle.dumps(data, protocol=4)
for subdir in subfiles:
    pkl_url = f'https://github.com/ZzMinn/GTFS-Dashboard/raw/10cbd433fe290eca41aa14c133ddbc62139b4598/data/{subdir}.pkl'
    response = requests.get(pkl_url)
    if response.status_code == 200:
        pkl_data = response.content
        # pickle.dumps(pkl_data)
        df = load(BytesIO(pkl_data))
        # df = pickle.loads(pkl_data)
        dataframes[subdir] = df
    else:
        print(f'Failed to fetch pkl file: {pkl_url}')


dataframes['bus_new_jersy']['color'] = '#00FF00'
transportation = ['Bus','Subway', 'Citibike','LIRR','MNR','NJ rail']
boroughs = ["Bronx", "Brooklyn", "Manhattan", "Queens", "Staten_Island","New_Jersy"]
citibike_regions = ['NYC District', 'JC District', 'Hoboken District']
subway_id = dataframes['subway']['route_id'].unique()
bus_bronx_id = dataframes['bus_bronx']['route_id'].unique()
bus_brooklyn_id = dataframes['bus_brooklyn']['route_id'].unique()
bus_manhattan_id = dataframes['bus_manhattan']['route_id'].unique()
bus_queens_id = dataframes['bus_queens']['route_id'].unique()
bus_staten_island_id = dataframes['bus_staten_island']['route_id'].unique()
bus_new_jersy_id = dataframes['bus_new_jersy']['route_id'].unique()
LIRR_id = dataframes['LIRR']['route_id'].unique()
MNR_id = dataframes['MNR']['route_id'].unique()
NJ_rail_id = dataframes['NJ_rail']['route_id'].unique()

def citibike_station_data():
    station_info_url = "https://gbfs.citibikenyc.com/gbfs/en/station_information.json"
    info_response = urllib.request.urlopen(station_info_url)
    data_info = json.load(info_response)

    station_status_url = 'https://gbfs.citibikenyc.com/gbfs/en/station_status.json'
    status_response = urllib.request.urlopen(station_status_url)
    data_status = json.load(status_response)

    system_regions_url = 'https://gbfs.citibikenyc.com/gbfs/en/system_regions.json'
    regions_response = urllib.request.urlopen(system_regions_url)
    data_regions = json.load(regions_response)

    info_df = pd.DataFrame(data_info['data']['stations']).set_index('station_id')
    info_df = info_df[['name', 'lat', 'lon', 'capacity', 'legacy_id', 'region_id']]

    status_df = pd.DataFrame(data_status['data']['stations']).set_index('station_id')
    status_df = status_df[['num_docks_available', 'num_bikes_disabled', 'num_ebikes_available', 'num_bikes_available', 'num_docks_disabled', 'station_status', 'is_renting', 'is_returning', 'last_reported', 'is_installed']]

    regions_df = pd.DataFrame(data_regions['data']['regions'])
    regions_df.rename(columns={'name': 'region_name'}, inplace=True)

    citibike_df = info_df.merge(status_df, left_index=True, right_index=True)
    citibike_df = citibike_df.merge(regions_df[['region_id', 'region_name']], left_on='region_id', right_on='region_id')
    citibike_gdf = gpd.GeoDataFrame(citibike_df,
                                    geometry=gpd.points_from_xy(citibike_df['lon'], citibike_df['lat']),
                                    crs="EPSG:4326")
    return citibike_gdf

# with open("GTFS/subway_API_Key.txt", "r") as f:
#     subway_API_KEY = f.read().strip()

# with open("GTFS/bus_API_Key.txt", "r") as f:
#     bus_API_KEY = f.read().strip()

subway_API_KEY = os.getenv("SUBWAY_API_KEY")
bus_API_KEY = os.getenv("BUS_API_KEY")
       
def export_subway_schedule(api_key):
    urls = [
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs',
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace',
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm',
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-g',
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-jz',
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-l',
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw',
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-si'
    ]

    feed = gtfs_realtime_pb2.FeedMessage()

    for url in urls:
        response = requests.get(url, headers={'x-api-key': api_key})
        feed_message = gtfs_realtime_pb2.FeedMessage()
        feed_message.ParseFromString(response.content)
        feed.entity.extend(feed_message.entity)

    subway_schedule = []

    for entity in feed.entity:
        if entity.HasField('trip_update'):
            trip_update = entity.trip_update
            for stop_time_update in trip_update.stop_time_update:
                arrival_time = datetime.fromtimestamp(stop_time_update.arrival.time).strftime("%Y-%m-%d %H:%M:%S")
                departure_time = datetime.fromtimestamp(stop_time_update.departure.time).strftime("%Y-%m-%d %H:%M:%S")
                stop_id = stop_time_update.stop_id
                subway_schedule.append({
                    'route': trip_update.trip.route_id,
                    'arrival_time': arrival_time,
                    'departure_time': departure_time,
                    'stop_id': stop_id
                })

    return subway_schedule

subway_schedule = export_subway_schedule(subway_API_KEY)

def export_MNR_schedule(api_key):
    url = 'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/mnr%2Fgtfs-mnr'
    feed = gtfs_realtime_pb2.FeedMessage()
    response = requests.get(url, headers={'x-api-key': api_key})
    feed_message = gtfs_realtime_pb2.FeedMessage()
    feed_message.ParseFromString(response.content)
    feed.entity.extend(feed_message.entity)

    MNR_schedule = []

    for entity in feed.entity:
        if entity.HasField('trip_update'):
            trip_update = entity.trip_update
            for stop_time_update in trip_update.stop_time_update:
                arrival_time = datetime.fromtimestamp(stop_time_update.arrival.time).strftime("%Y-%m-%d %H:%M:%S")
                departure_time = datetime.fromtimestamp(stop_time_update.departure.time).strftime("%Y-%m-%d %H:%M:%S")
                stop_id = stop_time_update.stop_id
                MNR_schedule.append({
                    'route': trip_update.trip.route_id,
                    'arrival_time': arrival_time,
                    'departure_time': departure_time,
                    'stop_id': stop_id
                })

    return MNR_schedule

MNR_schedule = export_MNR_schedule(subway_API_KEY)

def export_bus_schedule(api_key):
    base_url = 'http://gtfsrt.prod.obanyc.com/tripUpdates'
    request_url = f'{base_url}?key={api_key}'

    response = requests.get(request_url)
    data = response.content

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(data)

    bus_schedule = []
    
    for entity in feed.entity:
        if entity.HasField('trip_update'):
            trip_update = entity.trip_update
            route_id = trip_update.trip.route_id
            for stop_time_update in trip_update.stop_time_update:
                arrival_time = datetime.fromtimestamp(stop_time_update.arrival.time).strftime("%Y-%m-%d %H:%M:%S")
                departure_time = datetime.fromtimestamp(stop_time_update.departure.time).strftime("%Y-%m-%d %H:%M:%S")
                stop_id = stop_time_update.stop_id
                bus_schedule.append({
                    'route': route_id,
                    'arrival_time': arrival_time,
                    'departure_time': departure_time,
                    'stop_id': stop_id
                })

    return bus_schedule

bus_schedule = export_bus_schedule(bus_API_KEY)

def export_bus_location(api_key):
    base_url = "http://gtfsrt.prod.obanyc.com/vehiclePositions"
    request_url = f'{base_url}?key={api_key}'

    response = requests.get(request_url)
    data = response.content

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(data)

    location = []
    
    for entity in feed.entity:
        if entity.HasField('vehicle'):
            vehicle = entity.vehicle
            vehicle_id = vehicle.vehicle.id
            route_id = vehicle.trip.route_id if vehicle.trip.HasField('route_id') else ""
            direction_id = vehicle.trip.direction_id if vehicle.trip.HasField('direction_id') else None
            latitude = vehicle.position.latitude
            longitude = vehicle.position.longitude
            location.append({
                'Vehicle ID': vehicle_id,
                'Route ID': route_id,
                'Direction ID': direction_id,
                'Latitude': latitude,
                'Longitude': longitude
            })

    return location

bus_location = export_bus_location(bus_API_KEY)

osm = ox.graph_from_place("New York City, United States", network_type="drive", simplify=False)
nodes, osm = ox.graph_to_gdfs(osm)
osm = osm.reset_index()[["osmid", "name", "geometry"]]

styles = {'background': '#262729', 'textColor': '#ffffff', 'marginColor': '#0e1012'}

app = dash.Dash(__name__)
server = app.server

app.layout = html.Div(
    children=[
        html.Br(),
        html.H1(children='TRAFFIC DATA DASHBOARD', style={'textAlign': 'center'}),
        html.Br(),
        html.Div(
            style={"margin": "0 10%"},  # Added margin on both sides
            children=[
                html.Table(
                    style={"margin": "auto", 'width': '100%'},
                    children=[
                        html.Tr([
                            html.Td([
                                html.P("Transportation:", style={"font-weight": "bold", "font-size": "20px"}),
                                dcc.Checklist(
                                    id='transport-selector',
                                    options=[{'label': method, 'value': method} for method in transportation],
                                    value=[transportation[1]],
                                    className='form-check',
                                    inputClassName='form-check-input',
                                    labelClassName='form-check-label')
                            ], style={'vertical-align': 'top', 'padding': '10px'}),

                            html.Td([
                                html.P("Bus Region:", style={"font-weight": "bold", "font-size": "20px"}),
                                dcc.Checklist(
                                    id='boroughs_chosen',
                                    options=[{'label': str(b), 'value': b} for b in boroughs],
                                    value=[],
                                    className='form-check',
                                    inputClassName='form-check-input',
                                    labelClassName='form-check-label')
                            ], style={'vertical-align': 'top', 'padding': '10px'}),  # First row, second column for bus region

                            html.Td([
                                html.P("Bus Route:", style={"font-weight": "bold", "font-size": "20px"}),
                                dcc.Dropdown(
                                    id='bus-routes-dropdown',
                                    multi=True,
                                    clearable=False,
                                    options=[{'label': str(route_id), 'value': route_id} for route_id in subway_id],
                                    value=[],
                                    style={'display': 'block', 'color': '#000000'}
                                ),
                                html.P("Subway Route:", style={"font-weight": "bold", "font-size": "20px"}),
                                dcc.Dropdown(
                                    id='route-selector',
                                    options=[{'label': str(route_id), 'value': route_id} for route_id in subway_id],
                                    multi=True,
                                    value=[subway_id[0]],
                                    style={'display': 'block', 'color': '#000000'}
                                ),
                                html.P("Citibike Region:", style={"font-weight": "bold", "font-size": "20px"}),
                                dcc.Dropdown(
                                    id='citibike-region-dropdown',
                                    options=[{'label': region, 'value': region} for region in citibike_regions],
                                    multi=True,
                                    style={'display': 'block', 'color': '#000000'}
                                )
                            ], style={'vertical-align': 'top', 'padding': '5px'}),  # First row, third column for bus route, subway route, and Citibike region

                            html.Td([
                                html.P("LIRR Route:", style={"font-weight": "bold", "font-size": "20px"}),
                                dcc.Dropdown(
                                    id='lirr-route-selector',
                                    options=[{'label': str(route_id), 'value': route_id} for route_id in LIRR_id],
                                    multi=True,
                                    value=[],
                                    style={'display': 'block', 'color': '#000000'}
                                ),
                                html.P("MNR Route:", style={"font-weight": "bold", "font-size": "20px"}),
                                dcc.Dropdown(
                                    id='mnr-route-selector',
                                    options=[{'label': str(route_id), 'value': route_id} for route_id in MNR_id],
                                    multi=True,
                                    value=[],
                                    style={'display': 'block', 'color': '#000000'}
                                ),
                                html.P("NJ Rail Route:", style={"font-weight": "bold", "font-size": "20px"}),
                                dcc.Dropdown(
                                    id='nj-transit-route-selector',
                                    options=[{'label': str(route_id), 'value': route_id} for route_id in NJ_rail_id],
                                    multi=True,
                                    style={'display': 'block', 'color': '#000000'}
                                )
                            ], style={'vertical-align': 'top', 'padding': '10px'}),
                        ]),  # Close for html.Tr
                    ]),  # Close for html.Table
            ]
        ),  # Close for html.Div

        dbc.Card([
            dbc.CardBody([
                dcc.Graph(id='map', style={'width': '100%', 'height': '100%'}),
                html.Div(id='info-box', style={'display': 'none'}),
                html.Div(id='info-content'),
                html.Div(id='real-time-data', style={'display': 'none'}),  # Container for real-time data
                dcc.Interval(
                    id='interval-component',
                    interval=60 * 1000,  # in milliseconds
                    n_intervals=0
                )
            ])
        ], style={"margin": "10px", "background-color": styles['background'], "color": styles['textColor']}),
    ],
    style={"margin": "auto", "background-color": styles['background'], "color": styles['textColor'], "border-color": styles['background']}
)

@app.callback(
    [Output('bus-routes-dropdown', 'style'),
     Output('route-selector', 'style'),
     Output('citibike-region-dropdown', 'style'),
     Output('lirr-route-selector', 'style'),
     Output('mnr-route-selector', 'style'),
     Output('nj-transit-route-selector', 'style')],
    [Input('transport-selector', 'value')]
)
def update_dropdown_styles(value):
    bus_routes_style = {'display': 'block', 'color': '#000000'} if 'Bus' in value else {'display': 'block', 'color': '#000000'}
    route_selector_style = {'display': 'block', 'color': '#000000'} if 'Subway' in value else {'display': 'block', 'color': '#000000'}
    citibike_region_style = {'display': 'block', 'color': '#000000'} if 'Citibike' in value else {'display': 'block', 'color': '#000000'}
    lirr_route_selector_style = {'display': 'block', 'color': '#000000'} if 'LIRR' in value else {'display': 'block', 'color': '#000000'}
    mnr_route_selector_style = {'display': 'block', 'color': '#000000'} if 'MNR' in value else {'display': 'block', 'color': '#000000'}
    nj_transit_route_selector_style = {'display': 'block', 'color': '#000000'} if 'NJ Transit' in value else {'display': 'block', 'color': '#000000'}

    return (
        bus_routes_style,
        route_selector_style,
        citibike_region_style,
        lirr_route_selector_style,
        mnr_route_selector_style,
        nj_transit_route_selector_style
    )

@app.callback(
    Output('bus-routes-dropdown', 'options'),
    [Input('boroughs_chosen', 'value')]
)
def update_bus_route_options(boroughs):
    options = []
    if boroughs is not None:
        for borough in boroughs:
            if borough == 'Bronx':
                options.extend([{'label': str(route_id), 'value': route_id} for route_id in bus_bronx_id])
            elif borough == 'Brooklyn':
                options.extend([{'label': str(route_id), 'value': route_id} for route_id in bus_brooklyn_id])
            elif borough == 'Manhattan':
                options.extend([{'label': str(route_id), 'value': route_id} for route_id in bus_manhattan_id])
            elif borough == 'Queens':
                options.extend([{'label': str(route_id), 'value': route_id} for route_id in bus_queens_id])
            elif borough == 'Staten_Island':
                options.extend([{'label': str(route_id), 'value': route_id} for route_id in bus_staten_island_id])
            elif borough == 'New_Jersy':
                options.extend([{'label': str(route_id), 'value': route_id} for route_id in bus_new_jersy_id])
    return options
    
def add_bus_location(fig, route_id):
    bus_data = export_bus_location(bus_API_KEY)
    bus_df = pd.DataFrame(bus_data)
    bus_df_route = bus_df[bus_df['Route ID'] == route_id]

    fig.add_trace(go.Scattermapbox(
        name=f"Bus Location",
        lon=bus_df_route['Longitude'],
        lat=bus_df_route['Latitude'],
        mode='markers',
        marker=dict(
            size=10, 
            color='red'
            # symbol='bus' 
        ),
        text=bus_df_route.apply(lambda x: f"Vehicle ID: {x['Vehicle ID']} <br> Route ID: {x['Route ID']} <br> Direction ID: {x['Direction ID']}", axis=1),
        hoverinfo='text'
    ))
    return fig

def update_gtfs_map(gdf, feeds):
    fig = go.Figure()

    all_route_ids = gdf['route_id'].unique()

    for route_id in all_route_ids:
        route = gdf[gdf['route_id'] == route_id]
        
        entity_dict = {}
        for feed in feeds:
            if feed['route'] == route_id:
                arrival_time_str = feed['arrival_time']  
                arrival_time_datetime = datetime.strptime(arrival_time_str, "%Y-%m-%d %H:%M:%S")  

                departure_time_str = feed['departure_time']  
                departure_time_datetime = datetime.strptime(departure_time_str, "%Y-%m-%d %H:%M:%S") 

                entity_dict[str(feed['stop_id'])] = (arrival_time_datetime, departure_time_datetime)  
                
        color = route['color'].iloc[0]
        if color == '#000000':
            color = 'blue'


        fig.add_trace(go.Scattermapbox(
            name=f"Route {route_id}",
            lon=route.geometry.x,
            lat=route.geometry.y,
            mode='markers+lines',
            marker=dict(symbol='circle', color="white", size=4),
            text=route.apply(lambda x: f"Route: {x['route_id']} <br> Stop Name: {x['stop_name']} <br> Arrival Time: {entity_dict.get(str(x['stop_id']), ('N/A', 'N/A'))[0]} <br> Departure Time: {entity_dict.get(str(x['stop_id']), ('N/A', 'N/A'))[1]}", axis=1),
            hoverinfo='text',
            line=dict(width=3, color=color)
        ))
        
        fig = add_bus_location(fig, route_id)
        
    return fig

def update_map(gdf):
    fig = go.Figure()

    all_route_ids = gdf['route_id'].unique()

    for route_id in all_route_ids:
        route = gdf[gdf['route_id'] == route_id]

        fig.add_trace(go.Scattermapbox(
            name=f"Route {route_id}",
            lon=route.geometry.x,
            lat=route.geometry.y,
            mode='markers+lines',
            marker=dict(symbol='circle', color="white", size=4),
            text=route.apply(lambda x: f"Route: {x['route_id']} <br> Stop Name: {x['stop_name']} ", axis=1),
            hoverinfo='text',
            line=dict(width=3, color=route['color'].iloc[0])
        ))
        
    return fig

def update_MNR_map(gdf, feeds):
    fig = go.Figure()

    all_route_ids = gdf['route_id'].unique()
    for route_id in all_route_ids:
        route = gdf[gdf['route_id'] == route_id]
        route_long_name = route['route_long_name'].unique()[0]
        grouped = route.groupby('trip_id')
        longest_group = grouped.apply(lambda x: x['route_id'].count()).idxmax()
        selected_group = grouped.get_group(longest_group)

        # Convert 'stop_id' to string
        selected_group['stop_id'] = selected_group['stop_id'].astype(str)

        entity_dict = {}
        for feed in feeds:
            if feed['route'] == route_id:
                arrival_time_str = feed['arrival_time']
                arrival_time_datetime = datetime.strptime(arrival_time_str, "%Y-%m-%d %H:%M:%S")

                departure_time_str = feed['departure_time']
                departure_time_datetime = datetime.strptime(departure_time_str, "%Y-%m-%d %H:%M:%S")

                entity_dict[feed['stop_id']] = (arrival_time_datetime, departure_time_datetime)
        
        fig.add_trace(go.Scattermapbox(
            name=f"Route {route_long_name}",
            lon=selected_group.geometry.x,
            lat=selected_group.geometry.y,
            mode='markers+lines',
            marker=dict(symbol='circle', color="white", size=4),
            text=selected_group.apply(
                lambda x: f"Route: {x['route_id'], x['route_long_name']} <br> Stop Name: {x['stop_name']}", axis=1),
            hoverinfo='text',
            line=dict(width=3, color=selected_group['color'].iloc[0])  
        ))

    return fig


def update_citibike_map():
    # Load the Citibike station data
    citibike_gdf = citibike_station_data()
    citibike_gdf = citibike_gdf[citibike_gdf['station_status'] == 'active']
    citibike_gdf['last_reported'] = citibike_gdf['last_reported'].apply(lambda x: datetime.fromtimestamp(int(x)))

    fig = go.Figure()

    fig.add_trace(go.Scattermapbox(
        lon=citibike_gdf.geometry.x,
        lat=citibike_gdf.geometry.y,
        mode='markers',
        marker=dict(
            size=4,
            color='blue'
        ),
        text=citibike_gdf.apply(lambda x: f"Name: {x['name']} <br> Available Docks: {x['num_docks_available']} <br> Available eBikes: {x['num_ebikes_available']} <br> Available Bikes: {x['num_bikes_available']} <br> Last Reported: {x['last_reported']}", axis=1),
        hoverinfo='text'
    ))

    return fig

@app.callback(
    [Output('map', 'figure'),
     Output('real-time-data', 'children')],
    [Input('transport-selector', 'value'),
     Input('route-selector', 'value'),
     Input('boroughs_chosen', 'value'),
     Input('bus-routes-dropdown', 'value'),
     Input('lirr-route-selector', 'value'),
     Input('mnr-route-selector', 'value'),
     Input('nj-transit-route-selector', 'value'),
     Input('interval-component', 'n_intervals')]
)

def update_map_and_real_time_data(transportation, subway_routes, boroughs, bus_routes, LIRR_routes, MNR_routes, NJrail_routes, n):
    fig = go.Figure()
    subway_schedule = None
    bus_schedule = None
    MNR_schedule = None
    schedule_json = None
    
    if 'Subway' in transportation and subway_routes is not None:
        subway_schedule = export_subway_schedule(subway_API_KEY)
        subway_gdf = dataframes['subway'][dataframes['subway']['route_id'].isin(subway_routes)]
        subway_fig = update_gtfs_map(subway_gdf, subway_schedule)
        for trace in subway_fig.data:
            fig.add_trace(trace)
        
    if 'Bus' in transportation and boroughs is not None and bus_routes is not None:
        bus_schedule = export_bus_schedule(bus_API_KEY)
        for borough in boroughs:
            bus_gdf = dataframes[f'bus_{borough.lower()}'][dataframes[f'bus_{borough.lower()}']['route_id'].isin(bus_routes)]
            bus_fig = update_gtfs_map(bus_gdf, bus_schedule)
            for trace in bus_fig.data:
                fig.add_trace(trace)
    
    if 'Citibike' in transportation:
        citibike_fig = update_citibike_map()
        for trace in citibike_fig.data:
            fig.add_trace(trace)
            
    if 'LIRR' in transportation and LIRR_routes is not None:
        LIRR_gdf = dataframes['LIRR'][dataframes['LIRR']['route_id'].isin(LIRR_routes)]
        LIRR_fig = update_map(LIRR_gdf)
        for trace in LIRR_fig.data:
            fig.add_trace(trace)
            
    if 'MNR' in transportation and MNR_routes is not None:
        MNR_schedule = export_MNR_schedule(subway_API_KEY)
        MNR_gdf = dataframes['MNR'][dataframes['MNR']['route_id'].isin(MNR_routes)]
        MNR_fig = update_MNR_map(MNR_gdf, MNR_schedule)
        for trace in MNR_fig.data:
            fig.add_trace(trace)
            
    if 'NJ rail' in transportation and NJrail_routes is not None:
        NJ_gdf = dataframes['NJ_rail'][dataframes['NJ_rail']['route_id'].isin(NJrail_routes)]
        NJ_fig = update_map(NJ_gdf)
        for trace in NJ_fig.data:
            fig.add_trace(trace)

    fig.update_layout(
        mapbox = {
            'center': {"lat": 40.8, "lon": -74},
            'style': "carto-darkmatter",
            'zoom': 10
        },
        height = 1400,
        paper_bgcolor = "#e4ebf5",
        legend = dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(
                size=20,
                color="#0e1012"
            ),
            bgcolor= "#e4ebf5",
            bordercolor="#0e1012",
            borderwidth=2
        )    
    )
    
    if subway_schedule :
        schedule_json = json.dumps(subway_schedule)
    if bus_schedule:
        schedule_json = json.dumps(bus_schedule)
    if MNR_schedule:
        schedule_json = json.dumps(MNR_schedule)
        
    return fig, schedule_json


if __name__ == '__main__':
    app.run_server(debug=True)
