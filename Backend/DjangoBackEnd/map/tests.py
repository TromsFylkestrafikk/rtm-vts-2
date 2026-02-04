from django.test import TestCase, Client
from unittest.mock import patch, MagicMock
from django.core.management import call_command
from map.models import VtsSituation, ApiMetadata, BusRoute
from .utils import get_trip_geojson
from .views import trip, find_all_collisions
from django.contrib.gis.geos import Point, LineString

class FetchVtsSituationTest(TestCase):

    @patch("requests.get")
    def test_fetch_transit_information_api_failure(self, mock_get):
        """Test API failure handling."""
        # Mock the API response to simulate a failure (HTTP 500)
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        # Capture the logs during the execution of the management command
        with self.assertLogs("map.management.commands.get_transit_info", level="ERROR") as log:
            call_command("get_transit_info")
            # Adjusted assertion to match the actual log message
            self.assertIn("Error fetching data: HTTP 500", log.output[0])

        # Ensure no data has been saved to the database
        self.assertEqual(VtsSituation.objects.count(), 0)
    @patch("requests.get")
    def test_fetch_and_store_transit_information(self, mock_get):
        # Prepare the mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <d2LogicalModel xmlns="http://datex2.eu/schema/3/messageContainer"
                        xmlns:ns12="http://datex2.eu/schema/3/situation"
                        xmlns:common="http://datex2.eu/schema/3/common"
                        xmlns:ns8="http://datex2.eu/schema/3/locationReferencing">
            <payloadPublication>
                <ns12:situation>
                    <ns12:situationRecord id="FERRY1" version="1">
                        <ns12:situationRecordCreationTime>2023-01-01T12:00:00Z</ns12:situationRecordCreationTime>
                        <ns12:transitServiceType>ferry</ns12:transitServiceType>
                        <!-- Additional necessary fields -->
                    </ns12:situationRecord>
                </ns12:situation>
            </payloadPublication>
        </d2LogicalModel>
        """  # Your test XML data
        mock_response.headers = {'Last-Modified': 'Wed, 21 Oct 2020 07:28:00 GMT'}
        mock_get.return_value = mock_response
        # Run your management command
        call_command('get_transit_info')
        self.assertEqual(VtsSituation.objects.count(), 1)
        transit_info = VtsSituation.objects.first()
        self.assertEqual(transit_info.transit_service_type, 'ferry')
    @patch("requests.get")
    def test_no_action_on_304_response(self, mock_get):
        """Test that when the server responds with 304 Not Modified, no data is updated or saved."""
        # Setup the last_modified_date in ApiMetadata
        last_modified_value = 'Wed, 21 Oct 2020 07:28:00 GMT'
        ApiMetadata.objects.create(key='last_modified_date', value=last_modified_value)

        # Prepare the mock response
        mock_response = MagicMock()
        mock_response.status_code = 304  # Not Modified
        mock_response.headers = {}
        mock_get.return_value = mock_response

        # Run the management command
        with patch('map.management.commands.get_transit_info.logger') as mock_logger:
            call_command('get_transit_info')

            # Ensure that appropriate log message was made
            mock_logger.info.assert_any_call("data not modified!")

        # Ensure no new data was saved to the database
        self.assertEqual(VtsSituation.objects.count(), 0)
    @patch("requests.get")
    def test_if_modified_since_header_absent_when_no_last_modified_date(self, mock_get):
        """Test that the If-Modified-Since header is not set when there is no last_modified_date in the database."""
        # Ensure that there is no last_modified_date in the database
        self.assertFalse(ApiMetadata.objects.filter(key='last_modified_date').exists())

        # Prepare the mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <ns2:messageContainer xmlns:ns2="http://datex2.eu/schema/3/messageContainer"
            xmlns:ns3="http://datex2.eu/schema/3/situation"
            xmlns:ns4="http://datex2.eu/schema/3/common">
            <ns2:payload>
                <ns4:publicationTime>2020-10-22T07:28:00Z</ns4:publicationTime>
                <ns3:situation>
                    <ns3:situationRecord id="FERRY1" version="1">
                        <ns3:situationRecordCreationTime>2023-01-01T12:00:00Z</ns3:situationRecordCreationTime>
                        <ns3:transitServiceType>ferry</ns3:transitServiceType>
                        <!-- Additional necessary fields -->
                    </ns3:situationRecord>
                </ns3:situation>
            </ns2:payload>
        </ns2:messageContainer>
        """
        mock_response.headers = {}
        mock_get.return_value = mock_response

        # Run the management command
        call_command('get_transit_info')

        # Ensure that 'If-Modified-Since' header was not used in request
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(kwargs['headers'], {})

        # Ensure that data was saved to the database
        self.assertEqual(VtsSituation.objects.count(), 1)
    # @patch("requests.get")
    # def test_no_last_modified_and_no_publication_time(self, mock_get):
    #     """Test that when neither Last-Modified header nor publicationTime is available, last_modified_date is not updated."""
    #     # Prepare the mock response
    #     mock_response = MagicMock()
    #     mock_response.status_code = 200
    #     mock_response.content = b"""<?xml version="1.0" encoding="UTF-8"?>
    #     <ns2:messageContainer xmlns:ns2="http://datex2.eu/schema/3/messageContainer"
    #         xmlns:ns3="http://datex2.eu/schema/3/situation">
    #         <ns2:payload>
    #             <ns3:situation>
    #                 <ns3:situationRecord id="FERRY1" version="1">
    #                     <ns3:situationRecordCreationTime>2023-01-01T12:00:00Z</ns3:situationRecordCreationTime>
    #                     <ns3:transitServiceType>ferry</ns3:transitServiceType>
    #                 </ns3:situationRecord>
    #             </ns3:situation>
    #         </ns2:payload>
    #     </ns2:messageContainer>
    #     """
    #     # No Last-Modified header and no publicationTime in XML
    #     mock_response.headers = {}
    #     mock_get.return_value = mock_response

    #     # Run the management command
    #     with patch('map.management.commands.get_transit_info.logger') as mock_logger:
    #         call_command('get_transit_info')

    #         # Ensure that appropriate warning was logged
    #         mock_logger.warning.assert_any_call("No Last-Modified header or publicationTime found in the response.")

    #     # Ensure that the VtsSituation was saved
    #     self.assertEqual(VtsSituation.objects.count(), 1)

    #     # Ensure that last_modified_date was not updated
    #     self.assertFalse(ApiMetadata.objects.filter(key='last_modified_date').exists())

# class TripPlanningTests(TestCase):
#     def test_get_trip_geojson(self):
#         # Test with valid from/to places
#         geojson = get_trip_geojson("NSR:StopPlace:58777", "NSR:StopPlace:58707")  # Example place IDs
#         self.assertIsNotNone(geojson)  # Check that the function returns something
#         self.assertEqual(geojson['type'], "FeatureCollection")  # Check GeoJSON structure

#         # Test with invalid or missing place IDs (expecting None or error handling)
#         geojson = get_trip_geojson(None, "NSR:StopPlace:58707")
#         self.assertIsNone(geojson)  # Or check for specific error handling

#     def test_plan_trip_view(self):
#         client = Client()
#         # Test POST request with valid data
#         response = client.post('/trip/', {'from': "NSR:StopPlace:58777", 'to': "NSR:StopPlace:58707"})
#         self.assertEqual(response.status_code, 200)  # Check for successful response
#         self.assertIn('geojson', response.context)  # Check that geojson is in the context

#         # Test POST request with invalid data
#         response = client.post('/trip/', {'from': "", 'to': ""})  # Empty values
#         self.assertEqual(response.status_code, 200)  # Or appropriate error code
#         self.assertIn('error', response.context)  # Check for error message in context
