import os
import requests
import zipfile

def download_file(url, dest_path):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    if os.path.exists(dest_path):
        print(f"Already exists: {dest_path}")
        return
    print(f"Downloading {url} ...")
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(dest_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"Saved to {dest_path}")

def unzip_file(zip_path, extract_to):
    print(f"Unzipping {zip_path} ...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    print(f"Extracted to {extract_to}")

# List of datasets: (filename, url, unzip_dir or None)
datasets = [
    # Kenya Master Health Facility List (CSV)
    ("data/raw/kmhfl_hospitals_2020.csv", "https://open.africa/dataset/bb87c99a-78f8-4b8c-8186-4b0f4d935bcd/resource/6d13d7ff-ce54-4c8e-8879-da24fd3b456d/download/cfafrica-_-data-team-_-outbreak-_-covid19-_-data-_-openafrica-uploads-_-kenya-hospital-ke.csv", None),
    # WorldPop Kenya 2020 Population Raster (GeoTIFF)
    ("data/raw/worldpop_kenya_2020.tif", "https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/KEN/ken_ppp_2020.tif", None),
    # Facebook HRSL Kenya 2020 (CSV ZIP)
    ("data/raw/hrsl_kenya_2020.zip", "https://data.humdata.org/dataset/2964b369-c10c-4b55-94a8-495de3fc9858/resource/728e9fe2-0707-491f-91d8-3dc8379d7a32/download/ken_general_2020_csv.zip", "data/raw/hrsl_kenya_2020"),
    # Kenya Counties Shapefile (ZIP)
    ("data/raw/kenya_counties_shapefile.zip", "https://open.africa/dataset/194132e2-d3b8-4c76-9eac-1bd91ebaa9ad/resource/0b78f25e-494e-4258-96b8-a3ab2b35b121/download/kenyan-counties.zip", "data/raw/kenya_counties_shapefile"),
    # Kenya Wards Shapefile (ZIP)
    ("data/raw/kenya_wards_shapefile.zip", "https://data.humdata.org/dataset/e8d06ae7-740b-4491-8749-43f81700cf41/resource/858129b2-7197-4ffe-b34f-c2091b307b2c/download/kenya_wards.zip", "data/raw/kenya_wards_shapefile"),
    # Kenya Schools Shapefile (ZIP)
    ("data/raw/kenya_schools_shapefile.zip", "https://energydata.info/dataset/2fda191d-c3c6-4002-8c82-daa02008a9e3/resource/849830e2-fcb5-4b42-8d33-e42c7c1e90b4/download/schools.zip", "data/raw/kenya_schools_shapefile"),
    # Kenya Schools JSON
    ("data/raw/kenya_schools.json", "https://energydata.info/dataset/2fda191d-c3c6-4002-8c82-daa02008a9e3/resource/129b8c79-de8b-4b7b-8310-cdd207e46863/download/schools.json", None),
    # Kenya Health Facilities Shapefile (ZIP)
    ("data/raw/kenya_health_facilities_shapefile.zip", "https://energydata.info/dataset/7e456b65-1c58-4031-9a91-397787c1334c/resource/eeec12d8-d4c6-4112-8c0f-676f88f90f1b/download/healthcare-facilities.zip", "data/raw/kenya_health_facilities_shapefile"),
    # Kenya Health Facilities JSON
    ("data/raw/kenya_health_facilities.json", "https://energydata.info/dataset/7e456b65-1c58-4031-9a91-397787c1334c/resource/cca57586-9600-4736-8287-35f32d59071f/download/healthcare_facilities.json", None),
    # Kenya Health Facilities CSV
    ("data/raw/kenya_health_facilities.csv", "https://energydata.info/dataset/7e456b65-1c58-4031-9a91-397787c1334c/resource/841097c2-9424-4c90-b1e7-8e942a817c3c/download/healthcare_facilities.csv", None),
    # HRSL Kenya Population Raster (GeoTIFF ZIP)
    ("data/raw/hrslkenpop.zip", "https://us-iad-1.linodeobjects.com/edi-prod-public/edi-prod/resources/1473018a-3912-4b2f-873f-010d5f4b4df1/hrslkenpop.zip", "data/raw/hrslkenpop"),
]

for dest, url, unzip_dir in datasets:
    download_file(url, dest)
    if unzip_dir is not None:
        unzip_file(dest, unzip_dir)
