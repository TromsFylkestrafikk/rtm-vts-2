import os
import logging
import requests
import django
from dateutil.parser import isoparse
from datetime import timezone as dt_timezone
import xml.etree.ElementTree as ET
from django.core.management.base import BaseCommand
# --- GeoDjango Imports ---
from django.contrib.gis.geos import Point, LineString
from django.core.exceptions import ValidationError
# --- End GeoDjango Imports ---
from map.models import VtsSituation, ApiMetadata
from config import UserName_DATEX, Password_DATEX
from email.utils import format_datetime

# Set up Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings")
django.setup()

BaseURL = "https://datex-server-get-v3-1.atlas.vegvesen.no/datexapi/GetSituation/pullsnapshotdata/"
logger = logging.getLogger(__name__)

# Define namespaces (assuming these remain correct)
namespaces = {
    'ns0': 'http://datex2.eu/schema/3/messageContainer',
    'ns2': 'http://datex2.eu/schema/3/messageContainer',
    'ns12': 'http://datex2.eu/schema/3/situation',
    'ns8': 'http://datex2.eu/schema/3/locationReferencing',
    'common': 'http://datex2.eu/schema/3/common',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    'def': 'http://datex2.eu/schema/3/common',
}

# Docstring remains largely the same, but mention GeoDjango usage
"""
This script is a Django management command that fetches transit situation data from the VTS (Vegtrafikksentralen) API,
processes the XML response, and stores the relevant information in the database using GeoDjango fields for spatial data.

Key functionalities:
- ... (existing functionalities) ...
- Parses XML and extracts data including location details.
- Creates GeoDjango Point objects from latitude/longitude.
- Creates GeoDjango LineString objects from 'posList' data.
- Stores extracted information in the 'VtsSituation' model, using spatial fields.

Usage: ...
Requirements: ...
- GeoDjango and SpatiaLite backend must be configured in settings.py.
- SpatiaLite library must be installed on the system.
- Necessary Python packages (requests, python-dateutil, Django, GDAL bindings if needed) must be installed.
"""

class Command(BaseCommand):
    help = "Fetch transit information and store it in the database using GeoDjango"

    def handle(self, *args, **kwargs):
        # Retrieve the last modified date (same as before)
        last_modified_entry = ApiMetadata.objects.filter(key='last_modified_date').first()
        headers = {}
        if last_modified_entry:
            last_modified_date = last_modified_entry.value
            headers['If-Modified-Since'] = last_modified_date
            logger.info(f"Using If-Modified-Since header: {last_modified_date}")

        url = BaseURL # Removed f-string as no variable is used here
        try:
            response = requests.get(url, auth=(UserName_DATEX, Password_DATEX), headers=headers)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        except requests.RequestException as e:
            logger.error(f"HTTP request failed: {e}")
            return

        # Only process if status code was 200
        if response.status_code == 200:
             logger.info("Received new data (HTTP 200). Processing...")
             self.process_response(response)
             self.update_last_modified_date(response) # Update last modified only on successful fetch
        # The 304 case is handled by the HTTPError exception check above.

    # Removed to_float as direct conversion happens during Point creation

    def safe_parse_datetime(self, datetime_str):
        # (same as before)
        if datetime_str is None:
            return None
        try:
            parsed_datetime = isoparse(datetime_str)
            parsed_datetime = parsed_datetime.astimezone(dt_timezone.utc)
            return parsed_datetime
        except (ValueError, TypeError) as e:
            logger.error(f"Could not parse datetime '{datetime_str}': {e}")
            return None

    def process_response(self, response):
        """Parse the XML response, process situation records, create geometry objects, and update the database."""
        # Optional: Save debug response (same as before)
        with open("debug_response.xml", "w", encoding="utf-8") as f:
            f.write(response.content.decode('utf-8'))
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            logger.error(f"Error parsing XML: {e}")
            return

        processed_count = 0
        skipped_count = 0

        # Iterate over each situation record
        for situation in root.findall(".//ns12:situationRecord", namespaces):
            situation_id = situation.get("id") # Get ID early for logging errors
            try:
                # Extract comment (same as before)
                comment = None
                general_public_comment = situation.find("ns12:generalPublicComment", namespaces=namespaces)
                if general_public_comment is not None:
                    comment_values = general_public_comment.findall(".//common:value", namespaces=namespaces)
                    comments = [cv.text for cv in comment_values if cv.text]
                    comment = ' '.join(comments) if comments else None

                # Extract xsi:type (same as before)
                xsi_type = situation.attrib.get('{http://www.w3.org/2001/XMLSchema-instance}type')
                situation_type = xsi_type.split(':')[-1] if xsi_type else 'Unknown'

                # Extract basic information (same as before)
                version = situation.get("version")
                creation_time = self.safe_parse_datetime(situation.findtext("ns12:situationRecordCreationTime", namespaces=namespaces))
                version_time = self.safe_parse_datetime(situation.findtext("ns12:situationRecordVersionTime", namespaces=namespaces))
                probability_of_occurrence = situation.findtext("ns12:probabilityOfOccurrence", namespaces=namespaces)
                severity = situation.findtext("ns12:severity", namespaces=namespaces)

                # Extract source information (same as before)
                source = situation.find("ns12:source", namespaces=namespaces)
                source_country = source.findtext("common:sourceCountry", namespaces=namespaces) if source is not None else None
                source_identification = source.findtext("common:sourceIdentification", namespaces=namespaces) if source is not None else None
                source_name = source.findtext("common:sourceName/common:values/common:value", namespaces=namespaces) if source is not None else None
                source_type = source.findtext("common:sourceType", namespaces=namespaces) if source is not None else None

                # Extract validity information (same as before)
                validity = situation.find("ns12:validity", namespaces=namespaces)
                validity_status = validity.findtext("common:validityStatus", namespaces=namespaces) if validity is not None else None
                overall_start_time = self.safe_parse_datetime(validity.findtext("common:validityTimeSpecification/common:overallStartTime", namespaces=namespaces)) if validity is not None else None
                overall_end_time = self.safe_parse_datetime(validity.findtext("common:validityTimeSpecification/common:overallEndTime", namespaces=namespaces)) if validity is not None else None

                # --- Process Location and Geometry ---
                point_location = None
                line_path = None
                location_description = None
                road_number = None
                area_name = None
                pos_list_raw = None # Keep for reference

                location_reference = situation.find("ns12:locationReference", namespaces=namespaces)
                if location_reference is not None:
                    # Extract Lat/Lon for Point
                    latitude_str = location_reference.findtext(".//ns8:latitude", namespaces=namespaces)
                    longitude_str = location_reference.findtext(".//ns8:longitude", namespaces=namespaces)
                    if latitude_str and longitude_str:
                        try:
                            lat = float(latitude_str)
                            lon = float(longitude_str)
                            # Create Point(x, y) -> Point(longitude, latitude) with SRID 4326
                            point_location = Point(lon, lat, srid=4326)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Invalid coordinates for situation {situation_id}: lat='{latitude_str}', lon='{longitude_str}'. Error: {e}")
                            point_location = None # Ensure it's None if conversion fails

                    # Extract other location info
                    location_description = location_reference.findtext(".//ns8:locationDescription/common:values/common:value", namespaces=namespaces)
                    road_number = location_reference.findtext(".//ns8:roadInformation/ns8:roadNumber", namespaces=namespaces)
                    area_name_element = location_reference.find(".//ns8:areaName", namespaces=namespaces)
                    area_name = None
                    if area_name_element is not None:
                        area_name_values = area_name_element.findall("common:values/common:value", namespaces=namespaces)
                        area_name_texts = [v.text for v in area_name_values if v.text]
                        area_name = ' '.join(area_name_texts) if area_name_texts else None

                    # Extract posList data for LineString
                    gml_line_string = location_reference.find(".//ns8:gmlLineString", namespaces=namespaces)
                    if gml_line_string is not None:
                        pos_list_raw = gml_line_string.findtext("ns8:posList", namespaces=namespaces)
                        if pos_list_raw:
                            try:
                                # Parse the posList into coordinate pairs (lat lon lat lon...)
                                coords_flat = list(map(float, pos_list_raw.strip().split()))
                                # Ensure even number of coordinates
                                if len(coords_flat) % 2 == 0 and len(coords_flat) >= 4: # Need at least 2 points for a line
                                    # Create list of (lon, lat) tuples for LineString
                                    positions_lon_lat = list(zip(coords_flat[1::2], coords_flat[::2])) # lon is second, lat is first in each pair
                                    # Create LineString object with SRID 4326
                                    line_path = LineString(positions_lon_lat, srid=4326)
                                else:
                                     logger.warning(f"Invalid number of coordinates ({len(coords_flat)}) in posList for situation {situation_id}. Minimum 4 required.")
                                     line_path = None
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Could not parse posList '{pos_list_raw[:50]}...' for situation {situation_id}: {e}")
                                line_path = None
                            except ValidationError as e: # Catch potential LineString validation errors
                                logger.warning(f"Could not create LineString for situation {situation_id} from posList '{pos_list_raw[:50]}...': {e}")
                                line_path = None

                # Extract transit service information (same as before)
                transit_service_information = situation.findtext("ns12:transitServiceInformation", namespaces=namespaces)
                transit_service_type = situation.findtext("ns12:transitServiceType", namespaces=namespaces)

                # --- Create and save the VtsSituation object ---
                VtsSituation.objects.update_or_create(
                    situation_id=situation_id,
                    defaults={
                        'version': version,
                        'creation_time': creation_time,
                        'version_time': version_time,
                        'probability_of_occurrence': probability_of_occurrence,
                        'severity': severity,
                        'source_country': source_country,
                        'source_identification': source_identification,
                        'source_name': source_name,
                        'source_type': source_type,
                        'validity_status': validity_status,
                        'overall_start_time': overall_start_time,
                        'overall_end_time': overall_end_time,
                        'location': point_location,
                        'path': line_path,
                        'location_description': location_description,
                        'road_number': road_number,
                        'area_name': area_name,
                        'transit_service_information': transit_service_information,
                        'transit_service_type': transit_service_type,
                        'pos_list_raw': pos_list_raw, # Store raw string for reference
                        'comment': comment,
                        'filter_used': situation_type,
                    }
                )
                processed_count += 1
                # Update log message
                log_msg = f"Processed: {situation_id}"
                if point_location:
                    log_msg += f" (Loc: Point({point_location.x:.4f}, {point_location.y:.4f})"
                else:
                     log_msg += f" (Loc: None"
                if line_path:
                     log_msg += f", Path: {len(line_path.coords)} pts)"
                else:
                     log_msg += f", Path: None)"

                logger.info(log_msg)

            except Exception as e:
                logger.exception(f"FATAL Error processing situation record ID {situation_id}: {e}")
                skipped_count += 1

        logger.info(f"Finished processing. Processed: {processed_count}, Skipped due to errors: {skipped_count}")


    def update_last_modified_date(self, response):
        """Update the last modified date in the database (same logic as before)."""
        try:
            # Get the Last-Modified header from the response
            last_modified = response.headers.get('Last-Modified')
            last_modified_date_to_save = None # Initialize

            if last_modified:
                # Use Last-Modified header as is
                logger.info(f"Using Last-Modified header: {last_modified}")
                last_modified_date_to_save = last_modified
            else:
                logger.warning("No Last-Modified header found. Attempting to use publicationTime from XML.")
                # Attempt to extract publicationTime from the XML
                try:
                    root = ET.fromstring(response.content)
                    publication_time_str = root.findtext('.//def:publicationTime', namespaces=namespaces) # Simplified path might work
                    if not publication_time_str: # Try original path if simplified fails
                         publication_time_str = root.findtext('./ns2:payload/def:publicationTime', namespaces=namespaces)

                    if publication_time_str:
                        logger.debug(f"Extracted publicationTime: {publication_time_str}")
                        parsed_publication_time = self.safe_parse_datetime(publication_time_str)
                        if parsed_publication_time:
                            # Format datetime into HTTP-date format
                            last_modified_fallback = format_datetime(parsed_publication_time, usegmt=True)
                            last_modified_date_to_save = last_modified_fallback
                            logger.info(f"Using formatted publicationTime as fallback last modified date: {last_modified_fallback}")
                        else:
                            logger.warning("Could not parse publicationTime from XML.")
                    else:
                        logger.warning("publicationTime not found in XML.")
                except ET.ParseError as e:
                     logger.error(f"Error parsing XML while looking for publicationTime: {e}")
                except Exception as e: # Catch other potential errors during fallback
                     logger.error(f"Error processing publicationTime fallback: {e}")


            # Save the last modified date if we found one
            if last_modified_date_to_save:
                ApiMetadata.objects.update_or_create(
                    key='last_modified_date',
                    defaults={'value': last_modified_date_to_save}
                )
                logger.info(f"Last modified date updated in database: {last_modified_date_to_save}")
            else:
                logger.error("Could not determine Last-Modified date from headers or XML. Database record not updated.")

        except Exception as e:
            logger.exception(f"Critical error updating last modified date: {e}")