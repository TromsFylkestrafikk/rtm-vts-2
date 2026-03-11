import json
import polyline
import re
import os
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from django.core.management.base import BaseCommand
from django.conf import settings

OUTPUT_DIRECTORY = settings.BASE_DIR / "data"
JSON_FILE_PATH = OUTPUT_DIRECTORY / "route_coordinates.geojson"

class Command(BaseCommand):
    help = "Fetch static bus route coordinates for all bus lines in Troms"

    def fetch_route_coordinates(self):
        uri = "https://api.entur.io/journey-planner/v3/graphql"

        headers = {
            "ET-Client-Name": "troms-fylkeskommune-studenter",
        }
        
        #graphQL query for all traffic lines in Troms
        route_query = gql("""
        query {
            lines(authorities: "TRO:Authority:1") {
                id
                journeyPatterns {
                pointsOnLink {
                    points
                }
            }
        }
    }
        """)

        transport = RequestsHTTPTransport(url=uri, headers=headers)
        client = Client(transport=transport, fetch_schema_from_transport=True)

        result = client.execute(route_query)
        
        geojson_data = {
            "type": "FeatureCollection",
            "features": []
        }
        
        if "lines" in result and result["lines"] :
            for route_data in result["lines"]:
                
                points_on_link = route_data["journeyPatterns"][0].get("pointsOnLink", None)

                # Check if pointsOnLink is None or doesn't contain points
                if points_on_link and points_on_link.get("points"):
                    encoded_points = points_on_link["points"]
                    decoded_coordinates = polyline.decode(encoded_points)
                    
                    # Extract the desired part of the ID using regex
                    match = re.search(r"_(\d+)", route_data.get("id", ""))
                    
                    if match:
                        trimmed_id = match.group(0)[1:]  # Get the part after ':' and '_' (e.g 1_263)
                        
                        # Create a feature for the bus route
                        feature = {
                            "type": "Feature",
                            "geometry": {
                                "type": "LineString",
                                "coordinates": [[lon, lat] for lat, lon in decoded_coordinates]  # Ensure [longitude, latitude] order
                            },
                            "properties": {
                                # Add the trimmed ID to the properties
                                # These are the bus lines 
                                "route_id": trimmed_id  
                            }
                        }

                        geojson_data["features"].append(feature)
                    else:
                        self.stdout.write(self.style.WARNING(f"Could not extract route ID for journey {route_data.get('id')}"))
                else:
                    # Handle the case where no points are available for this route
                    self.stdout.write(self.style.WARNING(f"No points data found for journey ID {route_data.get('id')}"))

            # Save all routes to a GeoJSON file
            with open(JSON_FILE_PATH, "w") as f:
                json.dump(geojson_data, f, indent=4)
            
            self.stdout.write(self.style.SUCCESS("Successfully fetched and saved all route coordinates as GeoJSON"))
        else:
            self.stdout.write(self.style.ERROR("No route data found for any bus line in Troms"))

    def handle(self, *args, **kwargs):
        self.fetch_route_coordinates()
