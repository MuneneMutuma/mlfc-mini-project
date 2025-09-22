#!/usr/bin/python3

# Access pipeline utilities (drop into a cell)
import os
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Union, Tuple

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
import rasterio.mask
from rasterio.transform import xy
from shapely.geometry import Point, mapping
import plotly.express as px
import plotly.graph_objects as go
import osmnx as ox

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("access.pipeline")

# Default CRSes
WGS84 = "EPSG:4326"
METRIC_CRS = 32737  # UTM zone 37S (Kenya). Make configurable if needed.


@dataclass
class AccessPipeline:
    processed_dir: str = "../data/processed"
    metric_crs: int = METRIC_CRS
    wgs84: str = WGS84
    make_dirs: bool = True

    def __post_init__(self):
        if self.make_dirs:
            os.makedirs(self.processed_dir, exist_ok=True)
            os.makedirs(os.path.join(self.processed_dir, "rasters"), exist_ok=True)
            os.makedirs(os.path.join(self.processed_dir, "vectors"), exist_ok=True)

    # -------------------------
    # Loading helpers
    # -------------------------
    def load_boundary(self, boundary_source: Union[str, gpd.GeoDataFrame], county_name: Optional[str] = None) -> gpd.GeoDataFrame:
        """
        Load a region boundary. boundary_source can be:
         - path to shapefile / geojson (string), or
         - a GeoDataFrame already loaded.
        If county_name is provided, subset to that county (case-insensitive match on 'COUNTY' column).
        """
        if isinstance(boundary_source, gpd.GeoDataFrame):
            gdf = boundary_source.copy()
        else:
            gdf = gpd.read_file(boundary_source)
        gdf = gdf.to_crs(self.wgs84)
        if county_name:
            # try common column names
            if "COUNTY" in gdf.columns:
                mask = gdf["COUNTY"].str.upper().str.contains(county_name.upper(), na=False)
            elif "NAME" in gdf.columns:
                mask = gdf["NAME"].str.upper().str.contains(county_name.upper(), na=False)
            else:
                raise ValueError("Boundary has no COUNTY or NAME column to filter by county_name")
            gdf = gdf.loc[mask].copy()
            if gdf.empty:
                raise ValueError(f"No boundary matched county_name={county_name}")
        gdf = gdf.reset_index(drop=True)
        logger.info(f"Boundary loaded: {len(gdf)} features. CRS={gdf.crs}")
        return gdf

    def load_facilities(self, facility_source: Union[str, gpd.GeoDataFrame], lon_col: Optional[str] = None, lat_col: Optional[str] = None) -> gpd.GeoDataFrame:
        """
        Load facility data. Accepts:
         - geojson / shapefile path
         - CSV path with lat/lon columns (specify lon_col, lat_col)
         - GeoDataFrame already loaded
        Returns GeoDataFrame in WGS84.
        """
        if isinstance(facility_source, gpd.GeoDataFrame):
            gdf = facility_source.copy()
        else:
            # inference by extension
            ext = os.path.splitext(str(facility_source))[-1].lower()
            if ext in (".geojson", ".json", ".shp", ".gpkg"):
                gdf = gpd.read_file(facility_source)
            elif ext in (".csv", ".txt"):
                df = pd.read_csv(facility_source)
                if lon_col is None or lat_col is None:
                    # try common names
                    possible_lon = [c for c in df.columns if c.lower() in ("lon","longitude","lng","x")]
                    possible_lat = [c for c in df.columns if c.lower() in ("lat","latitude","y")]
                    if not possible_lon or not possible_lat:
                        raise ValueError("Provide lon_col and lat_col for CSV with coordinates")
                    lon_col = possible_lon[0]
                    lat_col = possible_lat[0]
                gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon_col], df[lat_col]), crs=self.wgs84)
            else:
                raise ValueError("Unknown facility_source extension")
        # ensure geometry present and valid
        if "geometry" not in gdf.columns:
            raise ValueError("Facilities data has no geometry column")
        gdf = gdf.to_crs(self.wgs84)
        # standardize columns minimally
        if "NAME" not in gdf.columns and "name" in gdf.columns:
            gdf = gdf.rename(columns={"name": "NAME"})
        logger.info(f"Facilities loaded: {len(gdf)} rows")
        return gdf

    def load_population_raster(self, raster_path: str):
        """Open raster (return rasterio dataset handle). Caller should close when done."""
        src = rasterio.open(raster_path)
        logger.info(f"Raster loaded: {raster_path} | CRS={src.crs} | width={src.width} height={src.height}")
        return src

    # -------------------------
    # Preprocess utilities
    # -------------------------
    def clip_raster_to_boundary(self, raster_path: str, boundary_gdf: gpd.GeoDataFrame, out_name: Optional[str] = None) -> Tuple[str, np.ndarray, dict]:
        """
        Clip the raster to the study boundary. Returns (out_raster_path, raster_array, meta)
        - Writes a cropped GeoTIFF into processed_dir/rasters/ by default.
        """
        if out_name is None:
            out_name = os.path.basename(raster_path).replace(".tif", f".{boundary_gdf.index[0]}.clip.tif")
        out_path = os.path.join(self.processed_dir, "rasters", out_name)

        geom = [mapping(boundary_gdf.geometry.unary_union)]
        with rasterio.open(raster_path) as src:
            out_image, out_transform = rasterio.mask.mask(src, geom, crop=True)
            out_meta = src.meta.copy()
            out_meta.update({
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform
            })
        # write output
        with rasterio.open(out_path, "w", **out_meta) as dst:
            dst.write(out_image)
        arr = out_image[0].astype(float)
        arr[arr < 0] = 0
        logger.info(f"Raster clipped and saved to {out_path} | shape={arr.shape}")
        return out_path, arr, {"transform": out_transform, "meta": out_meta}

    def raster_to_points(self, raster_array: np.ndarray, transform, threshold: float = 0, max_points: int = 200000) -> gpd.GeoDataFrame:
        """
        Convert raster cells > threshold into a point GeoDataFrame (cell centroids).
        Downsamples if > max_points (uniformly).
        Returns GeoDataFrame in WGS84 (lon/lat).
        """
        rows, cols = np.where(raster_array > threshold)
        logger.info(f"Non-zero cells: {len(rows)}")

        # optionally downsample uniformly
        if len(rows) > max_points:
            step = int(np.ceil(len(rows) / max_points))
            rows = rows[::step]
            cols = cols[::step]
            logger.info(f"Downsampled population points by step {step} -> {len(rows)} points")

        coords = [xy(transform, int(r), int(c)) for r, c in zip(rows, cols)]
        xs, ys = zip(*coords)
        pop_values = raster_array[rows, cols]

        gdf = gpd.GeoDataFrame({"pop": pop_values}, geometry=gpd.points_from_xy(xs, ys), crs=self.wgs84)
        logger.info(f"Constructed {len(gdf)} population points (WGS84).")
        return gdf

    def save_vector(self, gdf: gpd.GeoDataFrame, name: str) -> str:
        """Save GeoDataFrame as GeoParquet and GeoJSON for quick reuse and web use."""
        out_parq = os.path.join(self.processed_dir, "vectors", f"{name}.parquet")
        out_geojson = os.path.join(self.processed_dir, "vectors", f"{name}.geojson")
        gdf.to_parquet(out_parq, index=False)
        gdf.to_file(out_geojson, driver="GeoJSON")
        logger.info(f"Wrote {name} to {out_parq} and {out_geojson}")
        return out_parq

    # -------------------------
    # OSM / Road network
    # -------------------------
    def get_osm_graph(self, boundary_gdf: gpd.GeoDataFrame, network_type: str = "drive", buffer_m: int = 2000) -> Tuple[ox.Graph, gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """
        Download (or reuse cached) OSM road graph around the study polygon:
        - boundary_gdf must be in WGS84
        - buffer_m: expand the polygon by meters before fetching OSM
        Returns (graph_proj, edges_gdf, nodes_gdf) where projection is SELF.metric_crs.
        """
        # buffer in metric CRS
        poly_m = boundary_gdf.to_crs(epsg=self.metric_crs)
        poly_buffered = poly_m.buffer(buffer_m).to_crs(self.wgs84).geometry.unary_union
        logger.info("Fetching OSM graph (this may take 10-60s depending on area).")
        G = ox.graph_from_polygon(poly_buffered, network_type=network_type, simplify=True)
        # project graph to metric for later distance math
        G_proj = ox.project_graph(G, to_crs=f"EPSG:{self.metric_crs}")
        nodes, edges = ox.graph_to_gdfs(G_proj, nodes=True, edges=True)
        logger.info(f"OSM graph: nodes={len(nodes):,} edges={len(edges):,}")
        # cache
        edges.to_file(os.path.join(self.processed_dir, "vectors", "osm_edges.geojson"), driver="GeoJSON")
        nodes.to_file(os.path.join(self.processed_dir, "vectors", "osm_nodes.geojson"), driver="GeoJSON")
        return G_proj, edges, nodes

    # -------------------------
    # Quick baseline Plotly (lightweight)
    # -------------------------
    def plot_baseline(self,
                      boundary_gdf: gpd.GeoDataFrame,
                      facilities_gdf: gpd.GeoDataFrame,
                      pop_points_gdf: gpd.GeoDataFrame,
                      edges_gdf: Optional[gpd.GeoDataFrame] = None,
                      pop_sample: int = 5000):
        """
        Fast baseline interactive map (Plotly)
        - pop_points_gdf expected in WGS84
        - facilities_gdf expected in WGS84
        - edges_gdf (optional): projected or WGS84; if present it will be clipped and drawn as 1 trace
        This function uses density_mapbox for population heat and single-line trace for roads to remain fast.
        """
        # ensure WGS84
        b = boundary_gdf.to_crs(self.wgs84)
        fac = facilities_gdf.to_crs(self.wgs84).copy()
        pop = pop_points_gdf.to_crs(self.wgs84).copy()

        # population density layer (density_mapbox handles many points without plotting each)
        pop_sample_df = pop.sample(min(len(pop), pop_sample), random_state=1)
        pop_sample_df["lon"] = pop_sample_df.geometry.x
        pop_sample_df["lat"] = pop_sample_df.geometry.y

        # base density map
        fig = px.density_mapbox(pop_sample_df, lat="lat", lon="lon", z="pop",
                                radius=8, center={"lat": b.geometry.centroid.y.mean(), "lon": b.geometry.centroid.x.mean()},
                                zoom=11, mapbox_style="carto-positron",
                                title="Population density (sampled)")

        # add roads as 1 line trace if provided (clip edges to boundary)
        if edges_gdf is not None:
            edges_clip = gpd.overlay(edges_gdf.to_crs(self.wgs84), b, how="intersection")
            # concatenate all edge coords with None separators
            lon_all, lat_all = [], []
            for geom in edges_clip.geometry:
                if geom is None:
                    continue
                try:
                    xs, ys = geom.xy
                    lon_all.extend(xs.tolist() + [None])
                    lat_all.extend(ys.tolist() + [None])
                except Exception:
                    # handle multilines/polygons robustly by iterating components
                    for part in getattr(geom, "geoms", [geom]):
                        xs, ys = part.xy
                        lon_all.extend(xs.tolist() + [None])
                        lat_all.extend(ys.tolist() + [None])
            fig.add_trace(go.Scattermapbox(lon=lon_all, lat=lat_all, mode="lines",
                                           line=dict(width=1, color="black"), opacity=0.4, name="roads"))

        # add facilities as a single scatter trace
        fac["lon"] = fac.geometry.x
        fac["lat"] = fac.geometry.y
        fig.add_trace(go.Scattermapbox(lat=fac["lat"], lon=fac["lon"],
                                       mode="markers", marker=dict(size=7, color="red"),
                                       name="facilities", hovertext=fac.get("NAME").astype(str)))
        fig.update_layout(margin=dict(t=40, b=0, l=0, r=0))
        fig.show()

