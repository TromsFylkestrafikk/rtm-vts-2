import os
import json
import logging
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.contrib.gis.geos import LineString, GEOSException
from django.core.exceptions import ValidationError
from django.utils import timezone
from dateutil.parser import isoparse # For parsing ISO 8601 timestamps
from django.db import transaction, IntegrityError

# Adjust the import path if your model is elsewhere
from map.models import BusRoute

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = (
        "Imports bus route shapes from a GeoJSON FeatureCollection file. "
        "Each feature creates a *new* BusRoute record."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'geojson_file_path',
            type=str,
            help='Path to the GeoJSON file containing bus route features (e.g., bus_coordinates.geojson)',
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Delete all existing BusRoute entries before importing.',
        )
        # Optional: Add arguments for default version if not in GeoJSON
        # parser.add_argument('--default-version', type=str, help='Default version if not in properties')

    @transaction.atomic # Process the import within a single database transaction
    def handle(self, *args, **options):
        geojson_file_path = options['geojson_file_path']
        clear_existing = options['clear_existing']
        # default_version = options.get('default_version') # Example if you add the argument

        # --- Validate File Path ---
        if not os.path.exists(geojson_file_path):
            raise CommandError(f"Error: GeoJSON file not found at '{geojson_file_path}'")

        self.stdout.write(f"Starting import from '{geojson_file_path}'...")

        # --- Clear Existing Data (Optional) ---
        if clear_existing:
            self.stdout.write(self.style.WARNING("Deleting existing bus routes..."))
            deleted_count, _ = BusRoute.objects.all().delete()
            self.stdout.write(f"Deleted {deleted_count} existing routes.")

        # --- Read and Parse GeoJSON ---
        try:
            with open(geojson_file_path, 'r', encoding='utf-8') as f:
                geojson_data = json.load(f)

            # Validate basic GeoJSON structure
            if not isinstance(geojson_data, dict) or geojson_data.get('type') != 'FeatureCollection':
                raise ValueError("JSON root must be a GeoJSON FeatureCollection object.")
            if 'features' not in geojson_data or not isinstance(geojson_data['features'], list):
                 raise ValueError("FeatureCollection must contain a 'features' list.")

            features = geojson_data['features'] # Get the list of features

        except json.JSONDecodeError as e:
            raise CommandError(f"Error parsing GeoJSON file: {e}")
        except ValueError as e:
             raise CommandError(f"Invalid GeoJSON structure: {e}")
        except Exception as e:
            raise CommandError(f"Error reading file: {e}")

        self.stdout.write(f"Found {len(features)} features in the GeoJSON file.")

        # --- Process Each Feature and Save to DB ---
        created_count = 0
        skipped_count = 0
        feature_index = 0 # For better logging

        self.stdout.write("Processing features and creating new routes...")
        for feature in features:
            feature_index += 1
            if not isinstance(feature, dict) or feature.get('type') != 'Feature':
                logger.warning(f"Skipping invalid item at index {feature_index} (not a Feature object): {feature}")
                skipped_count += 1
                continue

            properties = feature.get('properties', {}) or {} # Ensure properties is a dict
            geometry = feature.get('geometry', {}) or {} # Ensure geometry is a dict

            # --- Extract Geometry ---
            geom_type = geometry.get('type')
            coords = geometry.get('coordinates')

            if geom_type != 'LineString':
                 logger.warning(f"Skipping feature {feature_index}: Geometry type is '{geom_type}', expected 'LineString'.")
                 skipped_count += 1
                 continue

            if not coords or not isinstance(coords, list) or len(coords) < 2:
                 logger.warning(f"Skipping feature {feature_index}: Invalid or insufficient coordinates for LineString. Coords: {coords}")
                 skipped_count += 1
                 continue
            route_id_str = properties.get('route_id')
            # Check if route_id is present (since we made it required in the model)
            if not route_id_str:
                logger.warning(f"Skipping feature {feature_index}: Missing required 'route_id' in properties.")
                skipped_count += 1
                continue
            # Convert to string explicitly in case it's a number in JSON
            route_id_str = str(route_id_str)
            # --- Extract Properties ---
            # Use properties.get('key', default_value)
            route_version = properties.get('version') # Or use default_version if provided via args
            last_updated_str = properties.get('last_updated') # Timestamp for the data point

            # --- Create Geometry and Prepare Data ---
            try:
                # Create the LineString geometry object
                # Assumes coordinates are [lon, lat] as is standard in GeoJSON
                route_path = LineString(coords, srid=4326) # GeoJSON uses WGS84

                # Parse the last_updated timestamp if available, otherwise use current time
                update_time = timezone.now() # Default to now
                if last_updated_str:
                    try:
                        parsed_time = isoparse(last_updated_str)
                        # Ensure it's timezone-aware (assume UTC if not specified, make it aware using Django settings)
                        if timezone.is_naive(parsed_time):
                             # Use settings.TIME_ZONE if needed, but UTC is often safer for backend storage
                             update_time = timezone.make_aware(parsed_time, timezone.utc)
                        else:
                            update_time = parsed_time # Already aware
                    except (ValueError, TypeError) as ts_err:
                         logger.warning(f"Feature {feature_index}: Could not parse timestamp '{last_updated_str}'. Using current time. Error: {ts_err}")
                         # Keep update_time as timezone.now()

                # --- Create new BusRoute instance ---
                # Since we don't have a unique key other than PK, we create a new entry for each feature.
                new_route = BusRoute(
                    route_id=route_id_str,
                    path=route_path,
                    version=route_version, # Will be None if not in properties or defaulted
                    last_updated=update_time,
                )
                new_route.full_clean() # Run model validation
                new_route.save() # Save to database

                created_count += 1
                # self.stdout.write(f"Created route: {new_route.pk}") # Can be noisy

            except (ValidationError, GEOSException) as e:
                logger.error(f"Skipping feature {feature_index}: Validation or Geometry error - {e}. Coordinates start: {str(coords)[:100]}...")
                skipped_count += 1
            except IntegrityError as e:
                 # Specifically catch IntegrityError, likely due to duplicate unique route_id
                 logger.error(f"Skipping feature {feature_index} (Route ID: {route_id_str}): Database integrity error (likely duplicate route_id) - {e}")
                 skipped_count += 1
            except Exception as e:
                # Catch other unexpected errors during processing/saving a single feature
                logger.exception(f"Skipping feature {feature_index}: Unexpected error - {e}") # Use logger.exception to include traceback
                skipped_count += 1

        # --- Final Report ---
        self.stdout.write(self.style.SUCCESS(
            f"Import finished. Created: {created_count}, Skipped: {skipped_count}"
        ))