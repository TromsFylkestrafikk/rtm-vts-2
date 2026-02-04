from django.shortcuts import render
from django.urls import path
from django.http import HttpResponse,JsonResponse
from django.template import loader
from .models import VtsSituation, BusRoute, DetectedCollision
from django.contrib.gis.measure import D
import ast  # Safe alternative to eval() for string-to-list conversion
from .utils import get_trip_geojson 
from django.contrib.gis.db.models.functions import AsGeoJSON
import os, json
from django.conf import settings
from django.contrib.gis.db.models.functions import Transform, Distance
from django.db.models import OuterRef, Exists
from django.db.models import Q
from django.db import connection

def serve_geojson(request):
    """Serve the pre-generated GeoJSON file instead of querying the database."""
    geojson_path = os.path.join(settings.BASE_DIR, 'output.geojson')
    if os.path.exists(geojson_path):
        with open(geojson_path, 'r') as file:
            geojson_data = json.load(file)
        return JsonResponse(geojson_data, safe=False)
    else:
        return JsonResponse({"error": "GeoJSON file not found"}, status=404)


def serve_bus(request):
    '''
    the updated bus list is served here
    '''
    buslist_path = os.path.join(settings.BASE_DIR,"bus_positions.json")
    print(f"bus list path: {buslist_path}")
    if os.path.exists(buslist_path):
        with open(buslist_path,'r') as file:
            buslist_data = json.load(file)
        return JsonResponse(buslist_data,safe=False)
    else:
        return JsonResponse({"error": "buslist file not found"},status = 404)
    
def busroute_json(request):
    '''
    busroute
    '''
    route_path = os.path.join(settings.BASE_DIR,"route_coordinates.geojson")
    print(f"bus list path: {route_path}")
    if os.path.exists(route_path):
        with open(route_path,'r') as file:
            route_data = json.load(file)
        return JsonResponse(route_data,safe=False)
    else:
        return JsonResponse({"error": "buslist file not found"},status = 404)

def busroute(request):
    """
    Serves BusRoute data from the database as a GeoJSON FeatureCollection.
    """
    try:
        # Query all BusRoute objects from the database
        # Use .iterator() for potentially large datasets to reduce memory usage
        routes = BusRoute.objects.all().iterator()

        # Prepare the list of GeoJSON features
        features = []
        for route in routes:
            # Ensure the path field is not null and actually contains geometry data
            if route.path and route.path.coords:
                # --- Method 1: Using the .geojson property (Recommended) ---
                # GeoDjango geometry fields have a .geojson property that returns
                # the geometry part as a GeoJSON string. We parse it back to a dict.
                try:
                    geometry_dict = json.loads(route.path.geojson)
                except json.JSONDecodeError:
                    print(f"Warning: Could not decode geojson geometry for route {route.pk}")
                    # Skip this feature if geometry is invalid
                    continue

                # Construct the GeoJSON Feature object
                feature = {
                    "type": "Feature",
                    "geometry": geometry_dict,
                    "properties": {
                        # Add any relevant non-geometry fields from your model here
                        "version": route.version,
                        # Format datetime to ISO 8601 string for standard JSON compatibility
                        "last_updated": route.last_updated.isoformat() if route.last_updated else None,
                        # You could add the primary key here if useful for the frontend
                        # "database_id": route.pk,
                    },
                    # Use the database primary key as the feature ID
                    "id": route.pk
                }
                features.append(feature)
            else:
                # Log or print a warning if a route has no path data
                print(f"Warning: Skipping route {route.pk} because its path is null or empty.")


        # Construct the final GeoJSON FeatureCollection dictionary
        geojson_data = {
            "type": "FeatureCollection",
            "features": features
        }

        # Return the GeoJSON data
        # safe=False is required because the top-level object is a dictionary, not a list
        return JsonResponse(geojson_data, safe=False)

    except Exception as e:
        # Log the error for debugging purposes
        # import logging
        # logger = logging.getLogger(__name__)
        # logger.error(f"Error generating bus route GeoJSON: {e}", exc_info=True)
        print(f"Error generating bus route GeoJSON: {e}") # Basic error logging
        # Return a generic error response
        return JsonResponse({"error": "An internal server error occurred while fetching route data."}, status=500)
    
    
def test_view(request):
    return JsonResponse({'message': 'Test path is working!'})

def map(request):
    template = loader.get_template('map.html')
    return HttpResponse(template.render())


def is_epsg_4326(lon, lat):
    """ Check if coordinates are already in EPSG:4326 (lat/lon) format. """
    return -180 <= lon <= 180 and -90 <= lat <= 90


def get_filter_options_from_db(request):
    '''
    Retrieve unique filter options for transit information.

    This function queries the database to retrieve unique values for **counties** and 
    **situation types** from the `VtsSituation` model. The results are returned 
    as a JSON response, making them useful for populating dropdown filters in a frontend UI.

    Parameters
    ----------
    request : HttpRequest
        The HTTP request object (not used in filtering, but required for Django views).

    Returns
    -------
    JsonResponse
        A JSON response containing two lists:
        - `counties` (list of str): Unique county names.
        - `situation_types` (list of str): Unique situation types.

    Notes
    -----
    - The function removes `None` or empty values from the lists before returning them.
    - Uses `distinct()` to ensure uniqueness in both `counties` and `situation_types`.

    Example
    -------
    Response:
    ```json
    {
        "counties": ["Oslo", "Bergen", "Trondheim"],
        "situation_types": ["roadwork", "accident", "closure"]
    }
    ```
    '''
    try:
        counties = VtsSituation.objects.values_list('area_name', flat=True).distinct()
        counties = [county for county in counties if county]
        
        situation_types = VtsSituation.objects.values_list('filter_used', flat=True).distinct()
        situation_types = [type for type in situation_types if type]
        
        severities = VtsSituation.objects.values_list('severity', flat=True).distinct()
        severities = [severity for severity in severities if severity]
        
        return JsonResponse({
            'counties': list(counties),
            'situation_types': list(situation_types),
            'severities': list(severities)
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
def get_filter_options(request):
    """
    Retrieve unique filter options directly from the VtsSituation model.
    """
    try:
        # Use distinct() on the database fields
        counties_qs = VtsSituation.objects.values_list('area_name', flat=True).distinct().order_by('area_name')
        counties = [county for county in counties_qs if county] # Remove None/empty

        situation_types_qs = VtsSituation.objects.values_list('filter_used', flat=True).distinct().order_by('filter_used')
        situation_types = [stype for stype in situation_types_qs if stype] # Remove None/empty

        severities_qs = VtsSituation.objects.values_list('severity', flat=True).distinct().order_by('severity')
        severities = [sev for sev in severities_qs if sev] # Remove None/empty

        return JsonResponse({
            'counties': list(counties),
            'situation_types': list(situation_types),
            'severities': list(severities)
        })
    except Exception as e:
        # Log the exception for debugging
        print(f"Error fetching filter options: {e}") # Or use logging
        return JsonResponse({'error': 'Could not retrieve filter options.'}, status=500)
def get_filter_options_geojson(request):
    try:
        # Read the geojson file
        with open('output.geojson', 'r') as file:
            geojson_data = json.load(file)

        counties = set()
        situation_types = set()
        severities = set()

        # Iterate over features in geojson
        for feature in geojson_data.get('features', []):
            properties = feature.get('properties', {})

            # Collect unique values for counties, situation types, and severities
            county = properties.get('county')
            if county:
                counties.add(county)

            situation_type = properties.get('situation_type')
            if situation_type:
                situation_types.add(situation_type)

            severity = properties.get('severity')
            if severity:
                severities.add(severity)

        # Convert sets to lists and return as JSON
        return JsonResponse({
            'counties': list(counties),
            'situation_types': list(situation_types),
            'severities': list(severities)
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
def location_geojson(request):
    '''
    Generate a GeoJSON FeatureCollection containing transit location data
    using GeoDjango model fields and functions.

    Retrieves transit data from VtsSituation, filters based on query
    parameters (county, situation_type, severity), and formats Points
    (from 'location' field) and LineStrings (from 'path' field) directly
    into GeoJSON features. Assumes geometries are stored in SRID 4326 (WGS84).

    Query Parameters:
        county (str, optional): Filter by area_name.
        situation_type (str, optional): Filter by filter_used.
        severity (str, optional): Filter by severity.

    Returns:
        JsonResponse: A GeoJSON FeatureCollection.
    '''
    # Get filter parameters from request
    county = request.GET.get('county', None)
    situation_type = request.GET.get('situation_type', None)
    severity = request.GET.get('severity', None)

    # Start with base queryset
    locations_qs = VtsSituation.objects.all()

    # Apply filters if parameters are provided
    if county:
        locations_qs = locations_qs.filter(area_name=county)
    if situation_type:
        locations_qs = locations_qs.filter(filter_used=situation_type)
    if severity:
        locations_qs = locations_qs.filter(severity=severity)

    # Annotate the queryset to include geometry fields as GeoJSON strings
    # Select only necessary fields + the generated GeoJSON geometry strings
    # The database needs to support AsGeoJSON (PostGIS, SpatiaLite do)
    locations_data = locations_qs.annotate(
        location_geojson=AsGeoJSON('location'), # Get Point geometry as GeoJSON string
        path_geojson=AsGeoJSON('path')          # Get LineString geometry as GeoJSON string
    ).values(
        # --- Select the fields needed for properties ---
        'id', # Keep ID if needed by frontend popups etc.
        'road_number',
        'location_description',
        'severity',
        'comment',
        'area_name',
        'filter_used',
        # --- Include the generated GeoJSON strings ---
        'location_geojson',
        'path_geojson'
    )

    features = []
    # Process each record returned by the optimized query
    for loc_data in locations_data:
        # Define base properties (common to point/line from same record)
        properties = {
            # Use .get() for safer access, though .values() should include them
            "id": loc_data.get('id'),
            "name": loc_data.get('road_number', 'N/A'), # Provide default
            "description": loc_data.get('location_description', 'No description'),
            "severity": loc_data.get('severity', 'unknown'),
            "comment": loc_data.get('comment', ''),
            "county": loc_data.get('area_name', 'N/A'),
            "situation_type": loc_data.get('filter_used', 'Unknown')
        }

        # Attempt to create a Point feature if location_geojson exists
        location_geojson_str = loc_data.get('location_geojson')
        if location_geojson_str:
            try:
                # Parse the GeoJSON string from the DB into a Python dict
                geometry = json.loads(location_geojson_str)
                # Basic validation: Ensure it's a Point with coordinates
                if geometry and geometry.get('type') == 'Point' and geometry.get('coordinates'):
                     features.append({
                        "type": "Feature",
                        "geometry": geometry, # Use the parsed geometry dict
                        "properties": properties.copy() # Use a copy of properties
                    })
                else:
                    # Log if parsing gives unexpected structure but no error
                    print(f"Warning: Parsed location GeoJSON invalid/incomplete for ID {loc_data.get('id')}")
            except (json.JSONDecodeError, TypeError) as e:
                 # Log if the string itself is invalid JSON
                 print(f"Error decoding location GeoJSON for ID {loc_data.get('id')}: {e}")


        # Attempt to create a LineString feature if path_geojson exists
        path_geojson_str = loc_data.get('path_geojson')
        if path_geojson_str:
             try:
                # Parse the GeoJSON string from the DB into a Python dict
                geometry = json.loads(path_geojson_str)
                # Basic validation: Ensure it's a LineString with coordinates
                if geometry and geometry.get('type') == 'LineString' and geometry.get('coordinates'):
                    features.append({
                        "type": "Feature",
                        "geometry": geometry, # Use the parsed geometry dict
                        "properties": properties.copy() # Use a copy of properties
                    })
                else:
                    # Log if parsing gives unexpected structure but no error
                    print(f"Warning: Parsed path GeoJSON invalid/incomplete for ID {loc_data.get('id')}")
             except (json.JSONDecodeError, TypeError) as e:
                 # Log if the string itself is invalid JSON
                 print(f"Error decoding path GeoJSON for ID {loc_data.get('id')}: {e}")


    # Construct the final GeoJSON FeatureCollection structure
    geojson_data = {
        "type": "FeatureCollection",
        "features": features
        # Removed the separate "transit_list" as it's redundant
    }

    # Return the FeatureCollection as a JSON response
    # safe=False is required because the top-level structure is a dictionary
    return JsonResponse(geojson_data, safe=False)

def trip(request):
    if request.method == 'POST':
        from_place = request.POST.get('from')
        to_place = request.POST.get('to')

        # Example GeoJSON generation (replace with your actual logic)
        trip_data = get_trip_geojson(from_place,to_place,num_trips=1)

        return JsonResponse({
            'trip_data': trip_data,
        })
    
    # Render the trip planning page for GET requests
    return render(request, 'trip.html')

def find_all_collisions(distance_meters=20):
    """
    Finds collision pairs using Raw SQL with SpatiaLite functions.
    Requires SpatiaLite + PROJ library correctly configured.

    Args:
        distance_meters (int): The tolerance distance in meters.

    Returns:
        list: List of (transit_info_id, bus_route_id) tuples.
    """
    all_collisions = []
    print("Attempting collision check using Raw SQL (SpatiaLite syntax)...")
    try:
        # --- Use Raw SQL for Collision Detection ---

        # !!! IMPORTANT: Choose the projected SRID correct for your area !!!
        # !!! AND Ensure PROJ library is configured for SpatiaLite !!!
        projected_srid = 32633 # Example: UTM Zone 33N

        # Get the actual database table names from the models' metadata
        transit_table = transit_table = VtsSituation._meta.db_table
        route_table = BusRoute._meta.db_table

        # Use Django's connection cursor for safe parameterization
        with connection.cursor() as cursor:
            # SpatiaLite SQL using ST_Distance and ST_Transform
            # Uses INNER JOIN and calculates distance in WHERE clause
            sql = f"""
                SELECT
                    t.id AS transit_id,
                    r.id AS route_id
                FROM
                    "{transit_table}" AS t
                INNER JOIN
                    "{route_table}" AS r ON t.location IS NOT NULL AND r.path IS NOT NULL
                WHERE
                    -- Calculate distance between transformed geometries
                    -- Returns NULL if transformation fails (e.g., PROJ issue)
                    ST_Distance(
                        ST_Transform(t.location, %s), -- Transform VTS point
                        ST_Transform(r.path, %s)      -- Transform route path
                    ) <= %s                           -- Compare distance (in meters)
            """
            # Parameters: [proj_srid, proj_srid, distance]
            # Using float() for distance is safer for DB driver compatibility
            cursor.execute(sql, [projected_srid, projected_srid, float(distance_meters)])

            # fetchall() returns a list of tuples, matching the SELECT columns
            all_collisions = cursor.fetchall()

        print(f"Found {len(all_collisions)} collision pairs using Raw SQL (SpatiaLite).")
        return all_collisions

    except Exception as e:
        # Check the error message carefully. It might indicate:
        # - Missing SpatiaLite functions (ST_Distance, ST_Transform) -> SpatiaLite extension issue
        # - Errors related to transformation -> PROJ library configuration issue
        print(f"An error occurred during Raw SQL collision detection (SpatiaLite): {e}")
        # import traceback
        # traceback.print_exc() # Very useful for debugging setup issues
        return [] # Return empty list on error

def find_all_collisions_details(distance_meters=20):
    """
    Finds collision pairs using Raw SQL with SpatiaLite ST_Distance function.
    Returns details including IDs, transit point coordinates, and route GeoJSON.
    Requires SpatiaLite + PROJ library correctly configured.

    Args:
        distance_meters (int): The tolerance distance in meters.

    Returns:
        list: A list of dictionaries, each containing:
              {
                  'transit_id': int,
                  'route_id': int,
                  'transit_lon': float,
                  'transit_lat': float,
                  'route_geojson': dict | None # Parsed GeoJSON geometry or None on error
              }
              Returns an empty list if no collisions are found or on error.
    """
    detailed_collisions = []
    print(f"Attempting collision check using Raw SQL (SpatiaLite ST_Distance - With Details)...")
    try:
        # --- Use Raw SQL for Collision Detection ---

        # !!! IMPORTANT: Choose the projected SRID correct for your area !!!
        # !!! AND Ensure PROJ library is configured for SpatiaLite !!!
        projected_srid = 32633 # Example: UTM Zone 33N

        # --- Get table names ---
        try:
            transit_table = VtsSituation._meta.db_table
            route_table = BusRoute._meta.db_table
        except AttributeError as meta_err:
            print(f"Error getting table names from model metadata: {meta_err}")
            return []
        # --- End table name retrieval ---

        # Use Django's connection cursor for safe parameterization
        with connection.cursor() as cursor:
            # SELECT IDs and geometry details
            sql = f"""
                SELECT
                    t.id AS transit_id,
                    r.id AS route_id,
                    ST_X(t.location) AS transit_lon,
                    ST_Y(t.location) AS transit_lat,
                    -- Use AsGeoJSON for SpatiaLite
                    AsGeoJSON(r.path) AS route_geojson_str
                FROM
                    "{transit_table}" AS t
                INNER JOIN
                    "{route_table}" AS r ON t.location IS NOT NULL AND r.path IS NOT NULL
                WHERE
                    -- Calculate distance between transformed geometries
                    ST_Distance(
                        ST_Transform(t.location, %s), -- Transform VTS point
                        ST_Transform(r.path, %s)      -- Transform route path
                    ) <= %s                           -- Compare distance (in meters)
            """
            # Parameters: [proj_srid, proj_srid, distance]
            cursor.execute(sql, [projected_srid, projected_srid, float(distance_meters)])

            # --- Process results into dictionaries ---
            columns = [col[0] for col in cursor.description]
            for row in cursor.fetchall():
                result_dict = dict(zip(columns, row))
                route_geojson = None
                geojson_str = result_dict.pop('route_geojson_str', None)
                if geojson_str:
                    try:
                        route_geojson = json.loads(geojson_str)
                    except json.JSONDecodeError as json_err:
                        print(f"Warning: Could not parse route GeoJSON for route_id {result_dict.get('route_id')}: {json_err}")
                result_dict['route_geojson'] = route_geojson
                detailed_collisions.append(result_dict)
            # --- End result processing ---

        print(f"Found {len(detailed_collisions)} collision pairs with details using Raw SQL (SpatiaLite ST_Distance).")
        return detailed_collisions

    except Exception as e:
        print(f"An error occurred during Raw SQL collision detection (With Details): {e}")
        # import traceback
        # traceback.print_exc()
        return [] # Return empty list on error
def get_stored_collisions_view(request):
    """
    API endpoint to retrieve pre-calculated and stored collision data
    from the DetectedCollision table.
    Supports optional filtering by detection timestamp.
    """
    # Optional: Filter by tolerance if multiple tolerances are stored
    # tolerance_filter = request.GET.get('tolerance', None)

    # Start querying the storage model
    queryset = DetectedCollision.objects.all()


    # Select only the fields needed for the API response using values() for efficiency
    # Note: Django automatically gives you the foreign key ID when you access
    # the ForeignKey field name in .values()
    collision_data = list(queryset.values(
        'transit_information_id', # Gets the ID of the related VtsSituation object
        'bus_route_id',           # Gets the ID of the related BusRoute object
        'transit_lon',
        'transit_lat',
        'detection_timestamp',
        'tolerance_meters'
    ))

    # Return the data. The key "stored_collisions" clearly indicates the source.
    return JsonResponse({"stored_collisions": collision_data})