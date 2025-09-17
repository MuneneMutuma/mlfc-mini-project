# Project Roadmap: Urban Accessibility and Service Deserts in Kenya

## 1. Project Goals

**Main Goal:** Map and quantify accessibility to essential services (clinics, schools, markets, transport) in Nairobi to identify underserved “service deserts.”

**Specific Objectives:**
- Build an integrated geospatial dataset combining roads, facilities, and population.
- Assess accessibility via travel-time modeling and service catchments.
- Identify underserved zones and produce visual + quantitative outputs.
- Deliver actionable insights for urban planning and equitable service provision.

## 2. Framework Overview (Access – Assess – Address)

### Access – Data Collection & Integration

**Datasets & Sources:**
- **Roads & Facilities:** OpenStreetMap (download programmatically via OSMnx).
- **Health Facilities:** Kenya Master Health Facility List (KMHFL).
- **Education Facilities:** Ministry of Education Kenya databases (school listings; can be cross-checked with OSM Points of Interest).
- **Population:**
  - Kenya Population & Housing Census 2019 – KNBS (aggregated ward/sub-county level).
  - WorldPop – high-resolution (100m) gridded population datasets.
  - Facebook High Resolution Settlement Layer (HRSL) – Kenya.
- **Administrative Boundaries:** Kenya AfriGeoPortal (ward/sub-county shapefiles, boundaries, and socio-economic layers).

**Data Readiness Levels (DRLs):**
- OSM: High DRL (easy access, needs validation).
- Census (KNBS): Medium DRL (aggregated, requires geocoding & harmonization).
- WorldPop / HRSL: Medium DRL (fine-scale, requires resampling and merging with census).
- KMHFL / Ministry of Education: Low–Medium DRL (structured but geocoding and deduplication needed).

**Work Required:**
- Harmonize datasets by administrative boundaries (wards/sub-counties).
- Standardize facility locations (geocoding for KMHFL/education).
- Merge raster-based (WorldPop, HRSL) and tabular (census) population data.

### Assess – Exploratory & Analytical Work

**Exploratory Analysis:**
- Plot service distributions (hospitals, schools, markets) as density/heatmaps.
- Visualize road networks from OSMnx.
- Compare facility clusters with population density (KNBS, WorldPop, HRSL).

**Accessibility Modeling:**
- Compute isochrones (10, 20, 30 min walking/driving catchments) using OSMnx + NetworkX.
- Overlay population rasters (WorldPop, HRSL) to estimate % of population covered.
- Perform equity analysis using poverty and housing indicators from KNBS Census.

**Identification of Service Deserts:**
- Define underserved zones (e.g., >30 min from nearest clinic or school).
- Identify high-population but low-service coverage wards.
- Cross-sectoral gaps (health vs. education vs. markets).

### Address – Outputs & Insights

**Deliverables:**
- Harmonized Dataset: Integrated road networks, facilities, and population layers.
- Accessibility Index: Proportion of population within 15 min walk/drive of services.
- Maps:
  - Isochrone maps (folium, matplotlib).
  - Choropleth maps of accessibility scores.
  - Service desert hotspot maps.
- Policy Brief: Highlight wards requiring urgent service expansion.
- Notebook Story: Interactive Jupyter notebook structured via the Fynesse template.

## 3. Technical Steps (Detailed Workflow)

### Setup & Repo Structure
- Start with the Fynesse template repository.
- Install dependencies:
  - OSMnx
  - GeoPandas
  - NetworkX
  - Rasterio
  - Folium
  - Shapely
  - Matplotlib

### Access Phase
- Extract Nairobi road graphs via OSMnx.
- Download OSM Points of Interest (POIs): "amenity"="hospital", "amenity"="school", "amenity"="marketplace", "highway"="bus_stop".
- Collect KNBS census shapefiles (KNBS portal, AfriGeoPortal).
- Download and preprocess WorldPop and HRSL rasters.
- Geocode KMHFL facilities (KMHFL database).

### Assess Phase
- Create service density maps with GeoPandas and Matplotlib.
- Run isochrone analysis using OSMnx + NetworkX.
- Overlay population coverage with service catchments.
- Compute accessibility scores at ward level.
- Compare scores across socio-economic indicators (poverty, housing).

### Address Phase
- Build accessibility index at ward/sub-county level.
- Create final visualizations: service desert maps, accessibility choropleths, and isochrone overlays.
- Summarize findings in notebook + policy brief.
- Package harmonized dataset for reproducibility (GeoPackage/CSV + documentation).

## 4. Expected Outcomes

**Data Products:**
- Harmonized geospatial dataset (roads, facilities, population).
- Accessibility index per ward.

**Analytical Insights:**
- Quantification of underserved populations.
- Identification of priority wards for new clinics/schools/markets/transport nodes.

**Visual Outputs:**
- Interactive maps (via folium).
- Isochrone and density visualizations.
- Choropleths highlighting inequality.

**Final Deliverables:**
- Jupyter Notebook “story” (structured with Fynesse template).
- GitHub repo with Access–Assess–Address modules.
- Policy-oriented summary brief.