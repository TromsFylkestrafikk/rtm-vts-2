import requests
import json
from django.core.management.base import BaseCommand
from django.conf import settings
import polyline

class Command(BaseCommand):
    help = "Fetch trip information from Entur API"

    def add_arguments(self, parser):
        parser.add_argument('--from', dest='from_place', required=True, help='Origin place ID')
        parser.add_argument('--to', dest='to_place', required=True, help='Destination place ID')
        parser.add_argument('--num', type=int, default=1, help='Number of trip patterns to fetch')

    def handle(self, *args, **options):
        from_place = options['from_place']
        to_place = options['to_place']
        num_trips = options['num']
        
        # Entur GraphQL API endpoint
        url = "https://api.entur.io/journey-planner/v3/graphql"
        
        # Headers with client identifier
        headers = {
            'ET-Client-Name': 'your-app-name',
            'Content-Type': 'application/json'
        }
        
        # GraphQL query for trip information
        query = """
        {
          trip(
            from: {
              place: "%s"
            },
            to: {
              place: "%s"
            },
            numTripPatterns: %d
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
                  latitude
                  longitude
                }
                toPlace {
                  name
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
        
        # Prepare the request payload
        payload = {
            "query": query
        }
        
        try:
            # Make the API call
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()  # Raise exception for HTTP errors
            
            # Process the response
            data = response.json()
            
            # You can save to database, print results, or return data
            self.stdout.write(self.style.SUCCESS(json.dumps(data, indent=2)))
            
        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f"API request failed: {e}"))
        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR("Failed to decode JSON response"))