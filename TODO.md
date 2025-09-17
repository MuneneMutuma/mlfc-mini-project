# Project TODO: Urban Accessibility and Service Deserts in Kenya

## 1. Environment Setup
- [x] Create and activate a Python virtual environment
- [x] Install dependencies from requirements.txt

## 2. Data Acquisition
- [x] Download OSM road and facility data for Nairobi using OSMnx
- [x] Download Kenya Master Health Facility List (KMHFL) from https://kmhfl.health.go.ke/
- [x] Download Ministry of Education school listings (from official site or OSM POIs)
- [x] Download Kenya Population & Housing Census 2019 (KNBS) shapefiles/tabular data from https://www.knbs.or.ke/ or https://afrigis.co.ke/afrigis-geoportal/
- [x] Download WorldPop gridded population data for Kenya from https://www.worldpop.org/
- [x] Download Facebook HRSL data for Kenya from https://data.humdata.org/dataset/highresolutionpopulationdensitymaps-ken
- [x] Download administrative boundaries (wards/sub-counties) from AfriGeoPortal
- [x] Unzip all downloaded archives (ZIP files) directly into their own folders under data/raw/
- [x] Organize all raw and unzipped datasets in data/raw/

## 3. Data Harmonization & Preprocessing
- [ ] Harmonize datasets by administrative boundaries
- [ ] Geocode and standardize facility locations (KMHFL, education)
- [ ] Merge raster (WorldPop, HRSL) and tabular (census) population data
- [ ] Document data sources and processing steps in docs/

## 4. Exploratory Analysis
- [ ] Plot service distributions (hospitals, schools, markets) as density/heatmaps
- [ ] Visualize road networks from OSMnx
- [ ] Compare facility clusters with population density

## 5. Accessibility Modeling
- [ ] Compute isochrones (10, 20, 30 min walking/driving) using OSMnx + NetworkX
- [ ] Overlay population rasters to estimate % of population covered
- [ ] Perform equity analysis using poverty/housing indicators

## 6. Identification of Service Deserts
- [ ] Define underserved zones (>30 min from nearest clinic/school)
- [ ] Identify high-population, low-service coverage wards
- [ ] Analyze cross-sectoral gaps (health, education, markets)

## 7. Outputs & Reporting
- [ ] Build accessibility index at ward/sub-county level
- [ ] Create final maps: isochrone, choropleth, service desert hotspots
- [ ] Summarize findings in a Jupyter notebook (notebooks/fynesse_template.ipynb)
- [ ] Write a policy brief (docs/)
- [ ] Package harmonized dataset (GeoPackage/CSV + documentation)

## 8. Documentation & Reproducibility
- [ ] Update README.md with progress and instructions
- [ ] Ensure all scripts and notebooks are reproducible
- [ ] Version control all code and documentation
