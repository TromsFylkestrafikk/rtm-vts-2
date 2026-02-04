import requests
import logging
import json
import xml.etree.ElementTree as ET
from pyproj import CRS, Transformer
from dotenv import load_dotenv
import os

load_dotenv()

username = os.getenv("brukernavn")
password = os.getenv("passord")

# Initialize transformer from EPSG:25833 to EPSG:4326
transformer = Transformer.from_crs("EPSG:25833", "EPSG:4326", always_xy=True)

def is_epsg_4326(lon, lat):
    """Check if coordinates are already in EPSG:4326 (lon/lat or lat/lon format)."""
    # Assuming lon, lat are input as lon, lat
    if -180 <= lon <= 180 and -90 <= lat <= 90:
        return True
    # Swap the coordinates and check again if they were provided as lat, lon
    elif -90 <= lon <= 90 and -180 <= lat <= 180:
        return True
    return False


# Function to read credentials from a text file
def read_credentials(filename='credentials.txt'):
    try:
        with open(filename, 'r') as file:
            # Read username and password from the file (assuming it's stored in two lines)
            username = file.readline().strip()
            password = file.readline().strip()
            return username, password
    except FileNotFoundError:
        logging.error(f"Credentials file {filename} not found.")
        return None, None

# Configure logging
logging.basicConfig(level=logging.INFO)

# Define URL
url = "https://datex-server-get-v3-1.atlas.vegvesen.no/datexapi/GetSituation/pullsnapshotdata?srti=True"

# If credentials are not found, exit
if not username or not password:
    logging.error("No valid credentials found. Exiting...")
    exit(1)

# Fetch XML data from the API
def fetch_xml_data():
    logging.info("Fetching XML data from the API...")
    try:
        response = requests.get(url, auth=(username, password))
        response.raise_for_status()  # Raise an error for bad status codes
        logging.info("Successfully fetched data.")
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching XML data: {e}")
        return None
    
# Function to parse XML and convert to GeoJSON
def parse_xml_to_geojson(xml_data):
    logging.info("Parsing XML data...")
    try:
        # Define namespaces
        namespaces = {
            'ns2': 'http://datex2.eu/schema/3/messageContainer',
            'ns3': 'http://datex2.eu/schema/3/cisInformation',
            'ns4': 'http://datex2.eu/schema/3/exchangeInformation',
            'ns5': 'http://datex2.eu/schema/3/informationManagement',
            'ns6': 'http://datex2.eu/schema/3/dataDictionaryExtension',
            'ns7': 'http://datex2.eu/schema/3/cctvExtension',
            'ns8': 'http://datex2.eu/schema/3/locationReferencing',
            'ns9': 'http://datex2.eu/schema/3/alertCLocationCodeTableExtension',
            'ns10': 'http://datex2.eu/schema/3/roadTrafficData',
            'ns11': 'http://datex2.eu/schema/3/vms',
            'ns12': 'http://datex2.eu/schema/3/situation',
            'ns0': 'http://datex2.eu/schema/3/common'
        }

        # Parse the XML data
        root = ET.fromstring(xml_data)

        # Find all situations
        situations = root.findall('.//ns12:situation', namespaces)

        if not situations:
            logging.warning("No situations found in the XML data.")
            return None

        geojson_features = []

        for situation in situations:
            situation_id = situation.attrib.get('id', 'Unknown')
            logging.info(f"Processing situation with ID: {situation_id}")

            # Extracting additional properties
            severity = situation.find('.//ns12:severity', namespaces)
            comments = situation.findall('.//ns12:generalPublicComment/ns12:comment', namespaces)
            county = situation.find('.//ns8:namedArea/ns8:areaName/ns0:values/ns0:value', namespaces)
            situation_type = situation.find('.//ns12:situationRecord/ns12:probabilityOfOccurrence', namespaces)
            # Extract Road Name & Road Number
            road_name_element = situation.find('.//ns8:roadInformation/ns8:roadName', namespaces)
            road_number_element = situation.find('.//ns8:roadInformation/ns8:roadNumber', namespaces)
            roadclose = situation.find('.//ns12:roadOrCarriagewayOrLaneManagementType', namespaces)

            # Convert to text if element exists, otherwise use default
            severity_text = severity.text if severity is not None else "Unknown"
            roadclose_text = roadclose.text if roadclose is not None else "unknown"
            county_text = county.text if county is not None else "Unknown"
            situation_type_text = situation_type.text if situation_type is not None else "Unknown"
            road_name_text = road_name_element.text if road_name_element is not None else "Unknown Road Name"
            road_number_text = road_number_element.text if road_number_element is not None else "Unknown Road Number"

            # Collect all location descriptions
            location_description_text = []

            # Extract locationDescriptions
            location_descriptions = situation.findall('.//ns8:locationDescription', namespaces)

            for location_description in location_descriptions:
                values = location_description.find('.//ns0:values', namespaces)  # Ensure correct namespace
                if values is not None:
                    value = values.find('.//ns0:value', namespaces)
                    if value is not None:
                        location_description_text.append(value.text.strip())  # Strip leading/trailing spaces
                    else:
                        location_description_text.append("No value element found in values")
                else:
                    location_description_text.append("No values element found for location description.")

            # Remove duplicates while maintaining order
            location_description_text = list(dict.fromkeys(location_description_text))
            # Collect all comments
            comment_text = []

            for comment in comments:
                values = comment.find('.//ns0:values', namespaces)
                if values is not None:
                    value = values.find('.//ns0:value', namespaces)
                    if value is not None:
                        comment_text.append(value.text.strip())
                    else:
                        comment_text.append("no value found")
                else:
                    comment_text.append("no values found")
                    
            comment_text = list(dict.fromkeys(comment_text))
                    
            # Extract LineString coordinates (if available)
            gml_line_elements = situation.findall('.//ns8:gmlLineString', namespaces)
            coordinates = []

            if gml_line_elements:
                first_gml_line = gml_line_elements[0]  # Only process the first gmlLineString
                pos_list = first_gml_line.find('.//ns8:posList', namespaces)
                if pos_list is not None and pos_list.text:
                    coord_list = list(map(float, pos_list.text.split()))
                    extracted_coords = [(coord_list[i], coord_list[i+1]) for i in range(0, len(coord_list), 2)]

                    transformed_coords = []
                    for lat, lon in extracted_coords:
                        if is_epsg_4326(lat, lon):
                            transformed_coords.append((lon, lat))  # Already in EPSG:4326
                        else:
                            # Transform from EPSG:25833 to EPSG:4326
                            new_lat, new_lon = transformer.transform(lat, lon)
                            transformed_coords.append((new_lat, new_lon))
            
                    coordinates = transformed_coords
                    logging.info(f"Extracted {len(coordinates)} coordinate pairs for situation {situation_id}.")
    
            # Extract Point
            lat_element = situation.find('.//ns8:coordinatesForDisplay/ns8:latitude', namespaces)
            lon_element = situation.find('.//ns8:coordinatesForDisplay/ns8:longitude', namespaces)
            point_coordinates = [float(lon_element.text), float(lat_element.text)] if lat_element is not None and lon_element is not None else None

            # Create GeoJSON feature
            feature = {
                "type": "Feature",
                "properties": {
                    "id": situation_id,
                    "name": road_name_text, 
                    "road_number" : road_number_text,
                    "description": " | ".join(location_description_text),  # Concatenate descriptions
                    "severity": severity_text,
                    "comment": "".join(comment_text),
                    "county": county_text,
                    "situation_type": situation_type_text,
                    "road close" : roadclose_text
                },
                "geometry": {}
            }

            # Add geometry type based on available coordinates
            if coordinates and point_coordinates:
                feature["geometry"]["type"] = "GeometryCollection"
                feature["geometry"]["geometries"] = [
                    {
                        "type": "LineString",
                        "coordinates": coordinates
                    },
                    {
                        "type": "Point",
                        "coordinates": point_coordinates
                    }
                ]
            elif coordinates:
                feature["geometry"]["type"] = "LineString"
                feature["geometry"]["coordinates"] = coordinates
            elif point_coordinates:
                feature["geometry"]["type"] = "Point"
                feature["geometry"]["coordinates"] = point_coordinates
            else:
                logging.warning(f"No valid geometry found for situation {situation_id}. Skipping.")

            # Add feature only if it has valid geometry
            if "type" in feature["geometry"]:
                geojson_features.append(feature)

        # Create the GeoJSON feature collection
        geojson = {
            "type": "FeatureCollection",
            "features": geojson_features
        }

        return geojson

    except Exception as e:
        logging.error(f"Error parsing XML data: {e}")
        return None


# Save GeoJSON data to a file
def save_geojson(geojson, filename='output.geojson'):
    logging.info(f"Saving GeoJSON data to {filename}...")
    try:
        with open(filename, 'w') as geojson_file:
            json.dump(geojson, geojson_file, indent=4)
        logging.info(f"GeoJSON data successfully saved to {filename}")
    except Exception as e:
        logging.error(f"Error saving GeoJSON data: {e}")

# Main function to orchestrate fetching, parsing, and saving data
def main():
    # Fetch the XML data
    xml_data = fetch_xml_data()
    
    if xml_data:
        # Parse XML to GeoJSON
        geojson = parse_xml_to_geojson(xml_data)
        
        if geojson:
            # Save GeoJSON to file
            save_geojson(geojson)

if __name__ == "__main__":
    main()
