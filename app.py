import os
from google.transit import gtfs_realtime_pb2
from datetime import datetime, date
import dash
from dash import dcc
from dash import html
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
import geopandas as gpd
import pandas as pd
import dash_bootstrap_components as dbc
import geopandas as gpd
import json
import requests
import urllib.request

subfile = ['bus_bronx','bus_brooklyn','bus_manhattan','bus_queens',
           'bus_staten_island','subway','LIRR','MNR','bus_new_jersy','NJ_rail']

dataframes = {} 

for subdir in subfile:
    folder_path = os.path.join('GTFS', subdir)

    routes = pd.read_csv(os.path.join(folder_path, 'routes.txt'))
    stop_times = pd.read_csv(os.path.join(folder_path, 'stop_times.txt'))
    stops = pd.read_csv(os.path.join(folder_path, 'stops.txt'))
    trips = pd.read_csv(os.path.join(folder_path, 'trips.txt'))

    df = trips[['route_id', 'service_id', 'trip_id']]
    df = df.merge(stop_times[['trip_id', 'arrival_time', 'departure_time', 'stop_sequence', 'stop_id']],
                  left_on='trip_id', right_on='trip_id', how='left')
    df = df.merge(stops[['stop_id', 'stop_name', 'stop_lat', 'stop_lon']],
                  left_on='stop_id', right_on='stop_id', how='left')
    df = df.merge(routes[['route_id', 'route_long_name', 'route_color']],
                  left_on='route_id', right_on='route_id', how='left')

    route_color_mapping = df.set_index('route_id')['route_color'].fillna('000000').astype(str).apply(lambda x: "#" + x).to_dict()
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df['stop_lon'], df['stop_lat']))
    gdf.crs = "EPSG:4326"
    gdf['color'] = gdf['route_id'].map(route_color_mapping)
    dataframes[subdir] = gdf

dataframes['bus_new_jersy']['color'] = '#00FF00'
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
    info_df = info_df[['name', 'lat', 'lon', 'capacity', 'region_id']]

    status_df = pd.DataFrame(data_status['data']['stations']).set_index('station_id')
    status_df = status_df[['num_docks_available', 'num_bikes_disabled', 'num_ebikes_available', 'num_bikes_available', 'num_docks_disabled', 'is_renting', 'is_returning', 'last_reported', 'is_installed']]

    regions_df = pd.DataFrame(data_regions['data']['regions'])
    regions_df.rename(columns={'name': 'region_name'}, inplace=True)

    citibike_df = info_df.merge(status_df, left_index=True, right_index=True)
    citibike_df = citibike_df.merge(regions_df[['region_id', 'region_name']], left_on='region_id', right_on='region_id')
    citibike_gdf = gpd.GeoDataFrame(citibike_df,
                                    geometry=gpd.points_from_xy(citibike_df['lon'], citibike_df['lat']),
                                    crs="EPSG:4326")
    return citibike_gdf

with open("GTFS/subway_API_Key.txt", "r") as f:
    subway_API_KEY = f.read().strip()

with open("GTFS/bus_API_Key.txt", "r") as f:
    bus_API_KEY = f.read().strip()
       
def export_subway_schedule(api_key):
    urls = [
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs',
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace',
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-bdfm',
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-g',
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-jz',
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-l',
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-nqrw',
        'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-si',
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

def export_LIRR_schedule(api_key):
    url = 'https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/lirr%2Fgtfs-lirr'
    feed = gtfs_realtime_pb2.FeedMessage()
    response = requests.get(url, headers={'x-api-key': api_key})
    feed_message = gtfs_realtime_pb2.FeedMessage()
    feed_message.ParseFromString(response.content)
    feed.entity.extend(feed_message.entity)

    LIRR_schedule = []

    for entity in feed.entity:
        if entity.HasField('trip_update'):
            trip_update = entity.trip_update
            for stop_time_update in trip_update.stop_time_update:
                arrival_time = datetime.fromtimestamp(stop_time_update.arrival.time).strftime("%Y-%m-%d %H:%M:%S")
                departure_time = datetime.fromtimestamp(stop_time_update.departure.time).strftime("%Y-%m-%d %H:%M:%S")
                stop_id = stop_time_update.stop_id
                LIRR_schedule.append({
                    'route': trip_update.trip.route_id,
                    'arrival_time': arrival_time,
                    'departure_time': departure_time,
                    'stop_id': stop_id
                })

    return LIRR_schedule

LIRR_schedule = export_LIRR_schedule(subway_API_KEY)

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

styles = {'background': '#262729', 'textColor': '#ffffff', 'marginColor': '#0e1012'}

app = dash.Dash(__name__)
app.layout = html.Div(
    children=[
        html.Br(),
        html.H1(children='Real Time Transportation Dashboard', style={'textAlign': 'center'}),
        html.Br(),
        html.Div(
            style={"margin": "2%", "display": "flex", 'margin-top': '20px'},
            children=[
                html.Div(
                    style={"width": "25%", 'vertical-align': 'top'}, 
                    children=[
                        html.P("Bus Region:", style={"font-weight": "bold", "font-size": "18px", "margin-bottom": "0px"}),
                        dcc.Checklist(
                            id='select-all-bus-regions',
                            options=[{'label': 'Select All', 'value': 'ALL'}],
                            value=[],
                            inline=True,
                            style={"margin-top": "0px", 'color': '#ffffff'}
                        ),
                        dcc.Dropdown(
                            id='boroughs_chosen',
                            multi = True, searchable=True,
                            options=[{'label': str(b), 'value': b} for b in boroughs],
                            value=[],
                            placeholder="Select a bus region",
                            style={"margin-top": "0px", 'color': '#000000', "margin-bottom": "5px"}
                        ),
                        html.P("Bus Route:", style={"font-weight": "bold", "font-size": "18px", "margin-bottom": "0px"}),
                        dcc.Checklist(
                            id='select-all-bus-route',
                            options=[{'label': 'Select All', 'value': 'ALL'}],
                            value=[],
                            inline=True,
                            style={"margin-top": "0px", 'color': '#ffffff'}
                        ),
                        dcc.Dropdown(
                            id='bus-routes-dropdown',
                            multi=True, searchable=True,
                            clearable=False,
                            options=[{'label': str(route_id), 'value': route_id} for route_id in subway_id],
                            value=[],
                            placeholder="Select a bus route",
                            style={'display': 'block', 'color': '#000000', "margin-bottom": "5px"}
                        ),
                        html.P("Subway Route:", style={"font-weight": "bold", "font-size": "18px", "margin-bottom": "0px"}),
                        dcc.Checklist(
                            id='select-all-subway-route',
                            options=[{'label': 'Select All', 'value': 'ALL'}],
                            value=[],
                            inline=True,
                            style={"margin-top": "0px", 'color': '#ffffff'}
                        ),
                        dcc.Dropdown(
                            id='route-selector',
                            options=[{'label': str(route_id), 'value': route_id} for route_id in subway_id],
                            multi=True, searchable=True,
                            value=[subway_id[0]],
                            placeholder="Select a Subway route",
                            style={'display': 'block', 'color': '#000000', "margin-bottom": "5px"}
                        ),
                        
                        html.P("Citibike Region:", style={"font-weight": "bold", "font-size": "18px", "margin-bottom": "0px"}),
                        dcc.Checklist(
                            id='select-all-citibike-region',
                            options=[{'label': 'Select All', 'value': 'ALL'}],
                            value=[],
                            inline=True,
                            style={"margin-top": "0px", 'color': '#ffffff'}
                        ),
                        dcc.Dropdown(
                            id='citibike-region-dropdown',
                            options=[{'label': region, 'value': region} for region in citibike_regions],
                            multi=True, searchable=True,
                            placeholder="Select a Citibike region",
                            style={'display': 'block', 'color': '#000000', "margin-bottom": "5px"}
                        ),
                        
                        html.P("LIRR Route:", style={"font-weight": "bold", "font-size": "18px", "margin-bottom": "0px"}),
                        dcc.Checklist(
                            id='select-all-lirr-route',
                            options=[{'label': 'Select All', 'value': 'ALL'}],
                            value=[],
                            inline=True,
                            style={"margin-top": "0px", 'color': '#ffffff'}
                        ),
                        dcc.Dropdown(
                            id='lirr-route-selector',
                            options=[{'label': str(route_id), 'value': route_id} for route_id in LIRR_id],
                            multi=True, searchable=True,
                            value=[],
                            placeholder="Select a LIRR route",
                            style={'display': 'block', 'color': '#000000', "margin-bottom": "5px"}
                        ),
                        html.P("MNR Route:", style={"font-weight": "bold", "font-size": "18px", "margin-bottom": "0px"}),
                        dcc.Checklist(
                            id='select-all-mnr-route',
                            options=[{'label': 'Select All', 'value': 'ALL'}],
                            value=[],
                            inline=True,
                            style={"margin-top": "0px", 'color': '#ffffff'}
                        ),
                        dcc.Dropdown(
                            id='mnr-route-selector',
                            options=[{'label': str(route_id), 'value': route_id} for route_id in MNR_id],
                            multi=True,
                            value=[],
                            placeholder="Select a MNR route",
                            style={'display': 'block', 'color': '#000000', "margin-bottom": "5px"}
                        ),
                        html.P("NJ Rail Route:", style={"font-weight": "bold", "font-size": "18px", "margin-bottom": "0px"}),
                        dcc.Checklist(
                            id='select-all-nj-route',
                            options=[{'label': 'Select All', 'value': 'ALL'}],
                            value=[],
                            inline=True,
                            style={"margin-top": "0px", 'color': '#ffffff'}
                        ),
                        dcc.Dropdown(
                            id='nj-transit-route-selector',
                            options=[{'label': str(route_id), 'value': route_id} for route_id in NJ_rail_id],
                            multi=True,
                            placeholder="Select a NJ Rail route",
                            style={'display': 'block', 'color': '#000000', "margin-bottom": "15px"}
                        ),
                        html.Button('Reset', id='reset-button', n_clicks=0)
                    ]
                ),
                html.Div(
                    style={"width": "75%","margin-left": "20px"},
                    children=[
                        dbc.Card([
                            dbc.CardBody([
                                dcc.Graph(id='map'),
                                html.Div(id='real-time-data', style={'display': 'none'}),
                                dcc.Interval(
                                    id='interval-component',
                                    interval=60 * 1000,
                                    n_intervals=0
                                )
                            ])
                        ],style={"border": "none", "background-color": "transparent"})
                    ]
                )
            ]
        )
    ],
)

@app.callback(
    Output('boroughs_chosen', 'value'),
    Input('select-all-bus-regions', 'value')
)
def select_all_boroughs(select_all):
    if 'ALL' in select_all:
        return boroughs
    return []

@app.callback(
    Output('route-selector', 'value'),
    Input('select-all-subway-route', 'value')
)
def select_all_subway_routes(select_all):
    if 'ALL' in select_all:
        return subway_id
    return [subway_id[0]]

@app.callback(
    Output('citibike-region-dropdown', 'value'),
    Input('select-all-citibike-region', 'value')
)
def select_all_citibike_region(select_all):
    if 'ALL' in select_all:
        return citibike_regions
    return []

@app.callback(
    Output('lirr-route-selector', 'value'),
    Input('select-all-lirr-route', 'value')
)
def select_all_lirr_routes(select_all):
    if 'ALL' in select_all:
        return LIRR_id
    return []

@app.callback(
    Output('mnr-route-selector', 'value'),
    Input('select-all-mnr-route', 'value')
)
def select_all_mnr_route(select_all):
    if 'ALL' in select_all:
        return MNR_id
    return []

@app.callback(
    Output('nj-transit-route-selector', 'value'),
    Input('select-all-nj-route', 'value')
)
def select_all_nj_routes(select_all):
    if 'ALL' in select_all:
        return NJ_rail_id
    return []

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

@app.callback(
    Output('bus-routes-dropdown', 'value'),
    [Input('boroughs_chosen', 'value'),
     Input('select-all-bus-route', 'value')]
)

def update_bus_route_options(boroughs, select_all):
    values = []
    if boroughs is not None:
        if 'ALL' in select_all:
            for borough in boroughs:
                if borough == 'Bronx':
                    values.extend(bus_bronx_id)
                elif borough == 'Brooklyn':
                    values.extend(bus_brooklyn_id)
                elif borough == 'Manhattan':
                    values.extend(bus_manhattan_id)
                elif borough == 'Queens':
                    values.extend(bus_queens_id)
                elif borough == 'Staten_Island':
                    values.extend(bus_staten_island_id)
                elif borough == 'New_Jersy':
                    values.extend(bus_new_jersy_id)
    return values

@app.callback(
    [Output('boroughs_chosen', 'value', allow_duplicate=True),
     Output('bus-routes-dropdown', 'value', allow_duplicate=True),
     Output('route-selector', 'value', allow_duplicate=True),
     Output('citibike-region-dropdown', 'value', allow_duplicate=True),
     Output('lirr-route-selector', 'value', allow_duplicate=True),
     Output('mnr-route-selector', 'value', allow_duplicate=True),
     Output('nj-transit-route-selector', 'value', allow_duplicate=True)],
    [Input('reset-button', 'n_clicks')],
    prevent_initial_call=True
)

def reset_selections(n_clicks):
    if n_clicks is None:
        return dash.no_update
    return [], [], [subway_id[0]], [], [], [], []
    
def add_bus_location(fig, route_id):
    bus_data = export_bus_location(bus_API_KEY)
    bus_df = pd.DataFrame(bus_data)
    bus_df_route = bus_df[bus_df['Route ID'] == route_id]

    fig.add_trace(go.Scattermapbox(
        name=f"{route_id} Bus Location",
        lon=bus_df_route['Longitude'],
        lat=bus_df_route['Latitude'],
        mode='markers',
        marker=dict(
            size=8, 
            color='red'
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
        max_sequence = route['stop_sequence'].max()
        max_sequence_index = route[route['stop_sequence'] == max_sequence].index[0]
        longest_sequence = route.loc[max_sequence_index - max_sequence + 1:max_sequence_index]
        
        entity_dict = {}
        for feed in feeds:
            if feed['route'] == route_id:
                arrival_time_str = feed['arrival_time']  
                arrival_time_datetime = datetime.strptime(arrival_time_str, "%Y-%m-%d %H:%M:%S")  

                departure_time_str = feed['departure_time']  
                departure_time_datetime = datetime.strptime(departure_time_str, "%Y-%m-%d %H:%M:%S") 
                
                if arrival_time_datetime.date() < date.today():
                    arrival_time_datetime = 'N/A'
                elif departure_time_datetime.date() < date.today():
                    departure_time_datetime = 'N/A'

                entity_dict[str(feed['stop_id'])] = (arrival_time_datetime, departure_time_datetime)  
                
        color = longest_sequence['color'].iloc[0]
        if color == '#000000':
            color = 'blue'
            
        if route_id in subway_id:
            route_name = f"Subway Route {route_id}"
        else:
            route_name = f"Bus Route {route_id}"

        fig.add_trace(go.Scattermapbox(
            name = route_name,
            lon = longest_sequence.geometry.x,
            lat = longest_sequence.geometry.y,
            mode = 'markers+lines',
            marker = dict(symbol='circle', color="white", size=4),
            text = longest_sequence.apply(lambda x: f"Route: {x['route_id']} <br> Stop Name: {x['stop_name']} <br> Arrival Time: {entity_dict.get(str(x['stop_id']), ('N/A', 'N/A'))[0]} <br> Departure Time: {entity_dict.get(str(x['stop_id']), ('N/A', 'N/A'))[1]}", axis=1),
            hoverinfo = 'text',
            line=dict(width=3, color=color)
        ))
        
        fig = add_bus_location(fig, route_id)
        
    return fig

def update_map(gdf, gdf_name):
    fig = go.Figure()
    all_route_ids = gdf['route_id'].unique()

    for route_id in all_route_ids:
        route = gdf[gdf['route_id'] == route_id]
        max_sequence = route['stop_sequence'].max()
        max_sequence_index = route[route['stop_sequence'] == max_sequence].index[0]
        longest_sequence = route.loc[max_sequence_index - max_sequence + 1:max_sequence_index]

        if gdf_name in 'NJ_gdf':
            route_name = f"NJ Rail Route {route_id}"
        else:
            route_name = f"Route {route_id}"

        fig.add_trace(go.Scattermapbox(
            name= route_name,
            lon=longest_sequence.geometry.x,
            lat=longest_sequence.geometry.y,
            mode='markers+lines',
            marker=dict(symbol='circle', color="white", size=4),
            text=longest_sequence.apply(lambda x: f"Route: {x['route_id']} <br> Stop Name: {x['stop_name']} ", axis=1),
            hoverinfo='text',
            line=dict(width=3, color=longest_sequence['color'].iloc[0])
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
        selected_group['stop_id'] = selected_group['stop_id'].astype(str)
        
        entity_dict = {}
        for feed in feeds:
            if str(feed['route']) == str(route_id):
                arrival_time_str = feed['arrival_time']
                arrival_time_datetime = datetime.strptime(arrival_time_str, "%Y-%m-%d %H:%M:%S")

                departure_time_str = feed['departure_time']
                departure_time_datetime = datetime.strptime(departure_time_str, "%Y-%m-%d %H:%M:%S")

                if arrival_time_datetime.date() < date.today():
                    arrival_time_datetime = 'N/A'
                elif departure_time_datetime.date() < date.today():
                    departure_time_datetime = 'N/A'

                entity_dict[str(feed['stop_id'])] = (arrival_time_datetime, departure_time_datetime)  
        
        fig.add_trace(go.Scattermapbox(
            name=f"MNR Route {route_id}",
            lon=selected_group.geometry.x,
            lat=selected_group.geometry.y,
            mode='markers+lines',
            marker=dict(symbol='circle', color="white", size=4),
            text=selected_group.apply(
                lambda x: f"Route: {x['route_id'], x['route_long_name']} <br> Stop Name: {x['stop_name']} <br> Arrival Time: {entity_dict.get(str(x['stop_id']), ('N/A', 'N/A'))[0]} <br> Departure Time: {entity_dict.get(str(x['stop_id']), ('N/A', 'N/A'))[1]}", axis=1),
            hoverinfo = 'text',
            line=dict(width=3, color=selected_group['color'].iloc[0])  
        ))

    return fig

def update_LIRR_map(gdf, feeds):
    fig = go.Figure()
    all_route_ids = gdf['route_id'].unique()

    for route_id in all_route_ids:
        route = gdf[gdf['route_id'] == route_id]
        max_sequence = route['stop_sequence'].max()
        max_sequence_index = route[route['stop_sequence'] == max_sequence].index[0]
        longest_sequence = route.loc[max_sequence_index - max_sequence + 1 : max_sequence_index]

        entity_dict = {}
        for feed in feeds:
            if str(feed['route']) == str(route_id):
                arrival_time_str = feed['arrival_time']
                arrival_time_datetime = datetime.strptime(arrival_time_str, "%Y-%m-%d %H:%M:%S")

                departure_time_str = feed['departure_time']
                departure_time_datetime = datetime.strptime(departure_time_str, "%Y-%m-%d %H:%M:%S")

                if arrival_time_datetime.date() < date.today():
                    arrival_time_datetime = 'N/A'
                elif departure_time_datetime.date() < date.today():
                    departure_time_datetime = 'N/A'

                entity_dict[str(feed['stop_id'])] = (arrival_time_datetime, departure_time_datetime)   
        
        fig.add_trace(go.Scattermapbox(
            name=f"LIRR Route {route_id}",
            lon=longest_sequence.geometry.x,
            lat=longest_sequence.geometry.y,
            mode='markers+lines',
            marker=dict(symbol='circle', color="white", size=4),
            text=longest_sequence.apply(
                lambda x: f"Route: {x['route_id'], x['route_long_name']} <br> Stop Name: {x['stop_name']} <br> Arrival Time: {entity_dict.get(str(x['stop_id']), ('N/A', 'N/A'))[0]} <br> Departure Time: {entity_dict.get(str(x['stop_id']), ('N/A', 'N/A'))[1]}", axis=1),
            hoverinfo = 'text',
            line=dict(width=3, color=longest_sequence['color'].iloc[0])  
        ))
        
    return fig

def update_citibike_map(citibike_gdf):
    fig = go.Figure()
    
    citibike_gdf['last_reported'] = citibike_gdf['last_reported'].apply(lambda x: datetime.fromtimestamp(int(x)))
    citibike_regions = citibike_gdf['region_name'].unique()
    region_color_mapping = {'NYC District': 'blue', 'JC District': 'green','Hoboken District': 'red'}
    
    for region in citibike_regions:
        citibike = citibike_gdf[citibike_gdf['region_name'] == region]
        region_color = region_color_mapping.get(region, 'blue')

        fig.add_trace(go.Scattermapbox(
            name=f" Citibike - {region}",
            lon=citibike.geometry.x,
            lat=citibike.geometry.y,
            mode='markers',
            marker=dict(
                size=4,
                color= region_color
            ),
            text=citibike.apply(lambda x: f"Name: {x['name']} <br> Available Docks: {x['num_docks_available']} <br> Available eBikes: {x['num_ebikes_available']} <br> Available Bikes: {x['num_bikes_available']} <br> Last Reported: {x['last_reported']}", axis=1),
            hoverinfo='text'
        ))

    return fig

@app.callback(
    [Output('map', 'figure'),
     Output('real-time-data', 'children')],
    [Input('route-selector', 'value'),
     Input('boroughs_chosen', 'value'),
     Input('bus-routes-dropdown', 'value'),
     Input('citibike-region-dropdown', 'value'),
     Input('lirr-route-selector', 'value'),
     Input('mnr-route-selector', 'value'),
     Input('nj-transit-route-selector', 'value'),
     Input('interval-component', 'n_intervals')]
)

def update_map_and_real_time_data(subway_routes, boroughs, bus_routes, citibike_region, LIRR_routes, MNR_routes, NJrail_routes, n):
    fig = go.Figure()
    subway_schedule = None
    bus_schedule = None
    schedule_json = None
    MNR_schedule = None
    LIRR_schedule = None
    
    if subway_routes is not None:
        subway_schedule = export_subway_schedule(subway_API_KEY)
        subway_gdf = dataframes['subway'][dataframes['subway']['route_id'].isin(subway_routes)]
        subway_fig = update_gtfs_map(subway_gdf, subway_schedule)
        for trace in subway_fig.data:
            fig.add_trace(trace)
        
    if boroughs is not None and bus_routes is not None:
        bus_schedule = export_bus_schedule(bus_API_KEY)
        for borough in boroughs:
            bus_gdf = dataframes[f'bus_{borough.lower()}'][dataframes[f'bus_{borough.lower()}']['route_id'].isin(bus_routes)]
            bus_fig = update_gtfs_map(bus_gdf, bus_schedule)
            for trace in bus_fig.data:
                fig.add_trace(trace)
    
    if citibike_region is not None:
        citibike_gdf = citibike_station_data()
        citibike_gdf = citibike_gdf[citibike_gdf['region_name'].isin(citibike_region)]
        citibike_fig = update_citibike_map(citibike_gdf)
        for trace in citibike_fig.data:
            fig.add_trace(trace)
            
    if LIRR_routes is not None:
        LIRR_schedule = export_LIRR_schedule(subway_API_KEY)
        LIRR_gdf = dataframes['LIRR'][dataframes['LIRR']['route_id'].isin(LIRR_routes)]
        LIRR_fig = update_LIRR_map(LIRR_gdf, LIRR_schedule)
        for trace in LIRR_fig.data:
            fig.add_trace(trace)
            
    if MNR_routes is not None:
        MNR_schedule = export_MNR_schedule(subway_API_KEY)
        MNR_gdf = dataframes['MNR'][dataframes['MNR']['route_id'].isin(MNR_routes)]
        MNR_fig = update_MNR_map(MNR_gdf, MNR_schedule)
        for trace in MNR_fig.data:
            fig.add_trace(trace)
            
    if NJrail_routes is not None:
        NJ_gdf = dataframes['NJ_rail'][dataframes['NJ_rail']['route_id'].isin(NJrail_routes)]
        NJ_fig = update_map(NJ_gdf, 'NJ_gdf')
        for trace in NJ_fig.data:
            fig.add_trace(trace)

    fig.update_layout(
        mapbox = {
            'center': {"lat": 40.8, "lon": -74},
            'style': "carto-darkmatter",
            'zoom': 10
        },
        margin=dict(l=0, r=0, b=0, t=0),
        hovermode="closest",
        plot_bgcolor="#e4ebf5",
        paper_bgcolor="#e4ebf5",
        height = 700,
        legend = dict(
            orientation="v",
            # yanchor="bottom",
            # y=1.02,
            xanchor="right",
            x=1,
            font=dict(
                size=10,
                color="#0e1012"
            ),
            bordercolor= "#e4ebf5",
            borderwidth=2
        )    
    )
    
    if subway_schedule :
        schedule_json = json.dumps(subway_schedule)
    if bus_schedule:
        schedule_json = json.dumps(bus_schedule)
    if MNR_schedule:
        schedule_json = json.dumps(MNR_schedule)
    if LIRR_schedule:
        schedule_json = json.dumps(LIRR_schedule)
        
    return fig, schedule_json


if __name__ == '__main__':
    app.run_server(debug=True)
