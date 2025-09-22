#!/usr/bin/python3

# assess.py

import networkx as nx
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping
import plotly.express as px
import plotly.graph_objects as go

class AssessPipeline:
    def __init__(self, G_proj, edges_gdf, nodes_gdf, pop_points, facilities, metric_crs=21037):
        """
        G_proj: projected road graph (from access.py)
        edges_gdf, nodes_gdf: edges and nodes GeoDataFrames
        pop_points: GeoDataFrame of population points
        facilities: GeoDataFrame of facilities
        """
        self.G = G_proj
        self.edges = edges_gdf
        self.nodes = nodes_gdf
        self.pop_points = pop_points
        self.facilities = facilities
        self.metric_crs = metric_crs

    # -------------------------------
    # Road network weights
    # -------------------------------
    def assign_speeds_and_travel_time(self, default_speeds=None):
        if default_speeds is None:
            default_speeds = {
                'motorway': 80, 'motorway_link': 60,
                'trunk': 60, 'trunk_link': 50,
                'primary': 50, 'primary_link': 40,
                'secondary': 40, 'secondary_link': 35,
                'tertiary': 35, 'tertiary_link': 30,
                'residential': 25, 'living_street': 20,
                'unclassified': 20, 'service': 15
            }

        # map speed to edges
        self.edges['highway_str'] = self.edges['highway'].apply(
            lambda x: ','.join(x) if isinstance(x, list) else x
        )
        self.edges['speed_kph'] = self.edges['highway_str'].map(default_speeds).fillna(30)

        # compute travel time in seconds
        self.edges['travel_time_sec'] = (self.edges['length'] / 1000) / self.edges['speed_kph'] * 3600

        # assign to graph
        nx.set_edge_attributes(self.G, self.edges['travel_time_sec'].to_dict(), 'travel_time_sec')

        return self.edges

    # -------------------------------
    # Multi-source Dijkstra
    # -------------------------------
    def compute_accessibility(self, cutoff=3600):
        """
        Compute shortest travel time (seconds) from every node to nearest facility.
        cutoff: maximum travel time in seconds (default 1 hour).
        """
        # snap facilities to nearest nodes
        facility_nodes = [
            nx.nearest_nodes(self.G, f.x, f.y) for f in self.facilities.to_crs(self.metric_crs).geometry
        ]
        facility_nodes = list(set(facility_nodes))

        # run multi-source Dijkstra
        lengths = nx.multi_source_dijkstra_path_length(
            self.G, facility_nodes, weight='travel_time_sec', cutoff=cutoff
        )
        return lengths

    # -------------------------------
    # Attach travel times to population
    # -------------------------------
    def attach_travel_times(self, lengths):
        """
        Add travel time (minutes) from population point to nearest facility.
        """
        # snap pop points to nearest nodes
        pop_nodes = [
            nx.nearest_nodes(self.G, p.x, p.y) for p in self.pop_points.to_crs(self.metric_crs).geometry
        ]

        travel_times = [lengths.get(n, np.nan) / 60 for n in pop_nodes]  # minutes
        self.pop_points['travel_time_min'] = travel_times
        return self.pop_points

    # -------------------------------
    # Summaries
    # -------------------------------
    def summarize_access(self, thresholds=[10, 20, 30, 60]):
        """
        Summarize percentage of population within travel time thresholds.
        """
        results = {}
        total_pop = self.pop_points['pop'].sum() if 'pop' in self.pop_points.columns else len(self.pop_points)

        for t in thresholds:
            within = self.pop_points.loc[self.pop_points['travel_time_min'] <= t, 'pop'].sum()
            results[t] = within / total_pop * 100

        return results


# -----------------------------
# RASTER FUNCTIONS
# -----------------------------
def summarize_raster(raster_path, polygon_gdf, polygon_col="COUNTY", region_name="NAIROBI"):
    """Summarize raster stats for a given region (polygon mask)."""
    region_gdf = polygon_gdf[polygon_gdf[polygon_col].str.upper().str.contains(region_name.upper())]
    region_geom = [mapping(region_gdf.iloc[0].geometry)]

    with rasterio.open(raster_path) as src:
        out_image, _ = mask(src, region_geom, crop=True)
        data = out_image[0]
        data = data[data > 0]  # remove no-data and zeros

    return {
        "total": float(data.sum()),
        "mean": float(data.mean()),
        "std_dev": float(data.std()),
        "min": float(data.min()),
        "max": float(data.max()),
        "cell_count": int(data.size),
    }, out_image[0]


def plot_raster_heatmap(data, title="Raster Heatmap", cmap="Viridis"):
    """Plot raster data as heatmap (array expected)."""
    fig = px.imshow(
        data,
        color_continuous_scale=cmap,
        title=title,
        labels={"color": "Value"}
    )
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10))
    return fig


def plot_raster_histogram(data, title="Raster Histogram", nbins=50):
    """Plot histogram of raster cell values."""
    flat_data = data.flatten()
    flat_data = flat_data[flat_data > 0]  # filter zeros/nodata
    fig = px.histogram(
        flat_data,
        nbins=nbins,
        title=title,
        labels={"value": "Value", "count": "Frequency"}
    )
    return fig


# -----------------------------
# VECTOR FUNCTIONS
# -----------------------------
def plot_choropleth(gdf, column, title="Choropleth Map", cmap="Viridis"):
    """Plot a choropleth from a GeoDataFrame."""
    gdf = gdf.to_crs(epsg=4326)  # ensure WGS84 for Plotly
    fig = px.choropleth_mapbox(
        gdf,
        geojson=gdf.geometry,
        locations=gdf.index,
        color=column,
        mapbox_style="carto-positron",
        center={"lat": gdf.geometry.centroid.y.mean(), "lon": gdf.geometry.centroid.x.mean()},
        zoom=8,
        color_continuous_scale=cmap,
        title=title
    )
    return fig


def plot_points_on_map(points_gdf, title="Points on Map"):
    """Plot points (e.g., facilities) on a basemap."""
    points_gdf = points_gdf.to_crs(epsg=4326)
    fig = px.scatter_mapbox(
        points_gdf,
        lat=points_gdf.geometry.y,
        lon=points_gdf.geometry.x,
        hover_name=points_gdf.index.astype(str),
        mapbox_style="carto-positron",
        zoom=9,
        title=title
    )
    return fig
