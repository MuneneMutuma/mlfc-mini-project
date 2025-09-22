# src/assess.py
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
from scipy.spatial import cKDTree


class AssessPipeline:
    def __init__(self, G_proj, edges_gdf, nodes_gdf, pop_points, facilities, metric_crs=21037):
        """
        G_proj: projected road graph (NetworkX MultiDiGraph)
        edges_gdf, nodes_gdf: edges and nodes GeoDataFrames (preferably in projected CRS)
        pop_points: GeoDataFrame of population points
        facilities: GeoDataFrame of facilities
        metric_crs: EPSG code for metric CRS used for distance math / snapping
        """
        self.G = G_proj
        self.edges = edges_gdf
        self.nodes = nodes_gdf
        self.pop_points = pop_points
        self.facilities = facilities
        self.metric_crs = metric_crs

        # cached KDTree for snapping nodes (built on demand)
        self._node_kdtree = None
        self._node_index_list = None

    # -------------------------------
    # Internal helpers
    # -------------------------------
    def _build_node_kdtree(self):
        """Build (or rebuild) KDTree of graph nodes in metric CRS."""
        nodes_proj = self.nodes.to_crs(epsg=self.metric_crs)
        coords = np.vstack([nodes_proj.geometry.x.values, nodes_proj.geometry.y.values]).T
        self._node_kdtree = cKDTree(coords)
        self._node_index_list = nodes_proj.index.to_list()

    def _snap_to_nearest_nodes(self, points_gdf):
        """
        Snap a GeoDataFrame of points to the nearest graph node.
        Returns a list of node ids (matching nodes_gdf.index).
        """
        if self._node_kdtree is None or self._node_index_list is None:
            self._build_node_kdtree()

        pts_proj = points_gdf.to_crs(epsg=self.metric_crs)
        pts_coords = np.vstack([pts_proj.geometry.x.values, pts_proj.geometry.y.values]).T
        # handle empty
        if pts_coords.size == 0:
            return []
        _, idxs = self._node_kdtree.query(pts_coords, k=1)
        node_ids = [self._node_index_list[i] for i in idxs]
        return node_ids

    # -------------------------------
    # Road network weights
    # -------------------------------
    def assign_speeds_and_travel_time(self, default_speeds=None):
        """
        Assign default speeds to edges (based on highway tag) and compute travel_time_sec.
        Also write travel_time_sec into graph edge attributes (u, v, key) -> travel_time_sec
        """
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

        # Normalize highway column: if list, take first element
        def _highway_str(x):
            if isinstance(x, list) and len(x) > 0:
                return x[0]
            return x

        self.edges['highway_str'] = self.edges['highway'].apply(_highway_str)
        self.edges['speed_kph'] = self.edges['highway_str'].map(default_speeds).fillna(30)

        # compute travel time in seconds
        self.edges['travel_time_sec'] = (self.edges['length'] / 1000.0) / self.edges['speed_kph'] * 3600.0

        # Assign travel_time_sec back into the graph edges.
        # Edges GeoDataFrame may have MultiIndex (u,v,key) or columns u,v,key.
        edge_time_dict = {}
        if {'u', 'v', 'key'}.issubset(self.edges.columns):
            # explicit columns present
            for _, row in self.edges.iterrows():
                u = int(row['u'])
                v = int(row['v'])
                k = int(row['key'])
                edge_time_dict[(u, v, k)] = float(row['travel_time_sec'])
        else:
            # assume index holds (u,v,key)
            for idx, row in self.edges.iterrows():
                if isinstance(idx, tuple) and len(idx) >= 3:
                    u, v, k = idx[0], idx[1], idx[2]
                elif isinstance(idx, tuple) and len(idx) == 2:
                    u, v = idx
                    # MultiGraph without key -> assign 0 or find any key below
                    k = 0
                else:
                    # fallback: try to extract attributes
                    u = int(row.get('u', None)) if row.get('u', None) is not None else None
                    v = int(row.get('v', None)) if row.get('v', None) is not None else None
                    k = int(row.get('key', 0)) if row.get('key', None) is not None else 0
                if u is not None and v is not None:
                    edge_time_dict[(u, v, k)] = float(row['travel_time_sec'])

        # set attributes: networkx expects (u,v,k) keys for MultiDiGraph when using keyed edges
        # We'll set attributes where possible by iterating the dict and writing into G
        for (u, v, k), tt in edge_time_dict.items():
            try:
                if self.G.has_edge(u, v, key=k):
                    self.G[u][v][k]['travel_time_sec'] = tt
                else:
                    # fallback: if graph has edge but different keys, assign to the first matching key
                    if self.G.has_edge(u, v):
                        for key in self.G[u][v]:
                            self.G[u][v][key]['travel_time_sec'] = tt
                            break
            except Exception:
                # safe guard (skip problematic edges)
                continue

        return self.edges

    # -------------------------------
    # Multi-source Dijkstra
    # -------------------------------
    def compute_accessibility(self, cutoff=3600):
        """
        Compute shortest travel time (seconds) from every node to nearest facility.
        Uses multi-source Dijkstra starting from snapped facility nodes.

        Returns:
            lengths: dict(node_id -> travel_time_seconds)
        """
        # snap facilities to nearest nodes
        facility_nodes = list(set(self._snap_to_nearest_nodes(self.facilities)))
        if len(facility_nodes) == 0:
            return {}

        # run multi-source Dijkstra (returns node -> distance)
        lengths = nx.multi_source_dijkstra_path_length(
            self.G, facility_nodes, cutoff=cutoff, weight='travel_time_sec'
        )
        return lengths

    # -------------------------------
    # Attach travel times to population
    # -------------------------------
    def attach_travel_times(self, lengths):
        """
        Add travel time (minutes) from population point to nearest facility.

        lengths: dict from compute_accessibility (node -> travel_time_sec)
        """
        pop_nodes = self._snap_to_nearest_nodes(self.pop_points)
        # Map node -> seconds, fallback to np.nan
        travel_times_min = []
        for n in pop_nodes:
            sec = lengths.get(n, np.nan)
            if np.isfinite(sec):
                travel_times_min.append(sec / 60.0)
            else:
                travel_times_min.append(np.nan)
        # attach a copy to avoid modifying original unintentionally
        self.pop_points = self.pop_points.copy()
        self.pop_points['travel_time_min'] = travel_times_min
        return self.pop_points

    # -------------------------------
    # Summaries
    # -------------------------------
    def summarize_access(self, thresholds=[10, 20, 30, 60]):
        """
        Summarize percentage (or count) of population within travel time thresholds.
        Returns a dict mapping threshold -> percentage (0-100).
        """
        results = {}
        # Decide denominator: total population (if 'pop' column) else number of points
        if 'pop' in self.pop_points.columns:
            total_pop = float(self.pop_points['pop'].sum())
            for t in thresholds:
                within_pop = float(self.pop_points.loc[self.pop_points['travel_time_min'] <= t, 'pop'].sum())
                results[t] = (within_pop / total_pop * 100.0) if total_pop > 0 else 0.0
        else:
            total_pts = float(len(self.pop_points))
            for t in thresholds:
                within_pts = float((self.pop_points['travel_time_min'] <= t).sum())
                results[t] = (within_pts / total_pts * 100.0) if total_pts > 0 else 0.0
        return results


# -----------------------------
# RASTER FUNCTIONS (module-level, generic)
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
# VECTOR FUNCTIONS (module-level, generic)
# -----------------------------
def plot_choropleth(gdf, column, title="Choropleth Map", cmap="Viridis"):
    """Plot a choropleth from a GeoDataFrame."""
    gdf = gdf.to_crs(epsg=4326)  # ensure WGS84 for Plotly
    # GeoJSON expects features; use gdf.geometry directly with locations=index
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
