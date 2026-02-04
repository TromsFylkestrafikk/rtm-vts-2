import requests
import json
import polyline
from map.models import BusRoute, VtsSituation
from django.db import connection
from django.contrib.gis.geos import Polygon
import time
def get_trip_geojson(from_place, to_place, num_trips=2):
    url = "https://api.entur.io/journey-planner/v3/graphql"
    headers = {
        'ET-Client-Name': 'TromsøFylkeskommune-svipper-Studenter',
        'Content-Type': 'application/json'
    }

    query = """
    {
    trip(
      from: {
        place: "%s"
      },
      to: {
        place: "%s"
      },
      numTripPatterns: %d,
    ) {
      tripPatterns {
        legs {
          mode
          distance
          line {
            id
            name
          }
          fromPlace {
            name
            quay {
              name
            }
            latitude
            longitude
          }
          toPlace {
            name
            quay {
              name
            }
            latitude
            longitude
          }
          pointsOnLink {
            points
          }
        }
      }
    }
  }
    """ % (from_place, to_place, num_trips)

    payload = {"query": query}

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        geojson_features = []
        for trip_pattern in data['data']['trip']['tripPatterns']:
            for leg in trip_pattern['legs']:
                if 'pointsOnLink' in leg and leg['pointsOnLink']:
                    # Decode polyline points
                    points = polyline.decode(leg['pointsOnLink']['points'])
                    # Swap lat/lng to lng/lat for GeoJSON compliance
                    points = [(lng, lat) for lat, lng in points]
                    
                    line_name = leg['line'].get('name') if leg.get('line') else None
                    geojson_feature = {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": points
                        },
                        "properties": {
                            "mode": leg['mode'].lower(),  # Lowercase for consistency
                            "lineName": line_name,
                            "distance": leg['distance']
                        }
                    }
                    geojson_features.append(geojson_feature)

        geojson = {
            "type": "FeatureCollection",
            "features": geojson_features
        }
        return geojson

    except (requests.exceptions.RequestException, json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"Error in get_trip_geojson: {e}")
        return None
# --- Define your Area of Interest (AOI) ---
# Replace with actual accurate coordinates for Troms
TROMS_BBOX_COORDS = (14.0, 68.2, 22.0, 70.5) # (min_lon, min_lat, max_lon, max_lat)
TROMS_BBOX_POLYGON = Polygon.from_bbox(TROMS_BBOX_COORDS)
TROMS_BBOX_POLYGON.srid = 4326
PROJECTED_SRID = 32633

def calculate_collisions_for_storage(distance_meters: int = 50) -> list:
    """
    Calculates collisions using Raw SQL (optimized with BBOX filter, using ST_Distance
    and GeomFromText for SpatiaLite compatibility).
    Returns details needed for storing in the DetectedCollision model.
    Requires SpatiaLite + PROJ library correctly configured.

    Args:
        distance_meters (int): The tolerance distance in meters.

    Returns:
        list: A list of dictionaries, each containing:
              {'transit_id': int, 'route_id': int, 'transit_lon': float, 'transit_lat': float}
              Returns an empty list if no collisions are found or on error.
    """
    collision_data_for_storage = []
    start_calc_time = time.time()
    print(f"Calculating collisions for storage (Tolerance: {distance_meters}m, Area: Troms BBOX)...")

    try:
        transit_table = VtsSituation._meta.db_table
        route_table = BusRoute._meta.db_table
        bbox_wkt = TROMS_BBOX_POLYGON.wkt
        bbox_srid = TROMS_BBOX_POLYGON.srid # Should be 4326

        with connection.cursor() as cursor:
            # Use GeomFromText(wkt, srid) instead of ST_SetSRID(ST_GeomFromText(wkt), srid)
            sql = f"""
                SELECT
                    t.id AS transit_id,
                    r.id AS route_id,
                    ST_X(t.location) AS transit_lon,
                    ST_Y(t.location) AS transit_lat
                FROM
                    "{transit_table}" AS t
                INNER JOIN
                    "{route_table}" AS r ON t.location IS NOT NULL AND r.path IS NOT NULL
                WHERE
                    -- Filter 1: Transit location must be within the BBOX
                    ST_Intersects(
                        t.location,
                        GeomFromText(%s, %s) -- Use GeomFromText with SRID parameter
                    )
                    AND
                    -- Filter 2: Bus route path must intersect the BBOX
                    ST_Intersects(
                        r.path,
                        GeomFromText(%s, %s) -- Use GeomFromText with SRID parameter
                    )
                    AND
                    -- Proximity Check: Using ST_Distance on transformed geometries
                    ST_Distance(
                        ST_Transform(t.location, %s), -- Transform point to projected SRID
                        ST_Transform(r.path, %s)      -- Transform path to projected SRID
                    ) <= %s                           -- Distance tolerance in meters
            """
            # Parameters order must match the %s placeholders
            params = [
                bbox_wkt, bbox_srid,           # Parameters for first GeomFromText
                bbox_wkt, bbox_srid,           # Parameters for second GeomFromText
                PROJECTED_SRID, PROJECTED_SRID, # Parameters for ST_Transform
                float(distance_meters)         # Parameter for ST_Distance comparison
            ]
            cursor.execute(sql, params)

            # --- Process results (same as before) ---
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            for row in rows:
                result_dict = dict(zip(columns, row))
                collision_data_for_storage.append(result_dict)
            # --- End result processing ---

        end_calc_time = time.time()
        print(f"Raw SQL calculation finished in {end_calc_time - start_calc_time:.2f} seconds. Found {len(collision_data_for_storage)} potential collisions.")
        return collision_data_for_storage

    except Exception as e:
        print(f"An error occurred during collision calculation for storage: {e}")
        # import traceback
        # traceback.print_exc() # Uncomment for full details if it fails again
        return []