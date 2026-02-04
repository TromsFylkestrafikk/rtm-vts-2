import requests
import os
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

load_dotenv()
#accidents
url = "https://datex-server-get-v3-1.atlas.vegvesen.no/datexapi/GetSituation/pullsnapshotdata?srti=True"
#ferry information
url2 = "https://datex-server-get-v3-1.atlas.vegvesen.no/datexapi/GetSituation/pullsnapshotdata/filter/AbnormalTraffic"
"""
Filters:
• AbnormalTraffic
• Accident
• Activity
• AnimalPresenceObstruction
• AuthorityOperation
• Conditions
• ConstructionWorks
• DisturbanceActivity
• EnvironmentalObstruction
• EquipmentOrSystemFault
• GeneralInstructionOrMessageToRoadUsers
• GeneralNetworkManagement
• GeneralObstruction
• GenericSituationRecord
• InfrastructureDamageObstruction
• MaintenanceWorks
• NetworkManagement
• NonWeatherRelatedRoadConditions
"""
auth = ("brukernavn", "passord") # i .env fil

API_USERNAME = os.getenv("brukernavn")
API_PASSWORD = os.getenv("passord")
response = requests.get(url, auth=(API_USERNAME, API_PASSWORD))
# Check if response is successful
if response.status_code == 200:
    # Parse XML response
    root = ET.fromstring(response.text)

    # Example: Print all tag names and values
    for elem in root.iter():
        print(f"{elem.tag}: {elem.text}")

else:
    print(f"Error: {response.status_code}")