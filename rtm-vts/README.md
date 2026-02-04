# RTM-VTS: pub-sub system/map for VTS Situations and Bus/Ferry Collisions

## Overview

This Django web application provides a real-time map visualization integrating traffic situation data from the Norwegian Public Roads Administration (Statens vegvesen - VTS) DATEX II API with static bus route information.

The core functionalities include:

*   **Fetching VTS Data:** Regularly retrieves current road situation data (road work, accidents, closures, etc.) from the VTS DATEX II API.
*   **Bus Route Management:** Imports bus route geometries from external sources (e.g., GeoJSON).
*   **Collision Detection:** Calculates potential proximity conflicts (collisions within a tolerance) between VTS situation points/paths and bus route paths.
*   **Real-time Publishing:** Publishes newly detected collisions via MQTT for consumption by external clients or dashboards.
*   **Interactive Map Display:** Visualizes VTS situations and bus routes on an interactive map.

## Requirements

### 1. System Dependencies

These must be installed on your system **before** installing Python packages. Installation methods vary by OS:

*   **Python:** Version 3.10+ recommended (check compatibility with Django 5.1).
*   **GDAL (Geospatial Data Abstraction Library):** Essential for GeoDjango.
    *   **Linux (Debian/Ubuntu):** `sudo apt update && sudo apt install gdal-bin libgdal-dev`
    *   **macOS (Homebrew):** `brew update && brew install gdal`
    *   **Windows(not tested):** Use pre-compiled binaries (e.g., [OSGeo4W](https://trac.osgeo.org/osgeo4w/)) or Conda (`conda install -c conda-forge gdal`).
*   **SpatiaLite Library (mod_spatialite):** Required for the SpatiaLite database backend.
    *   **Linux (Debian/Ubuntu):** `sudo apt install libsqlite3-mod-spatialite`
    *   **macOS (Homebrew):** `brew install libspatialite`
    *   **Windows(not tested):** Download `mod_spatialite.dll` ([gaia-gis.it](https://www.gaia-gis.it/fossil/libspatialite/)), install via OSGeo4W/Conda, or ensure its location is set via the `SPATIALITE_LIBRARY_PATH` environment variable.
*   **MQTT Broker:** A running MQTT broker is needed for the real-time publishing feature.
    *   **Recommendation:** [Mosquitto](https://mosquitto.org/download/) for local development. Install via package manager (`apt`, `brew`) or download the installer for Windows.
* Password from "Statens vegvesen" for datex II API access, you should have gotten an email from Kåre.
### 2. Python Environment & Packages

*   **Virtual Environment:** Strongly recommended.
    ```bash
    # Create environment (use python or python3 as appropriate)
    python -m venv .venv

    # Activate:
    # Linux/macOS (bash/zsh)
    source .venv/bin/activate
    # Windows (cmd.exe)
    # .\.venv\Scripts\activate.bat
    # Windows (PowerShell)
    # .\.venv\Scripts\Activate.ps1
    ```
*   **Python Packages:** Install using the provided `requirement.txt`:
    ```bash
    pip install -r requirement.txt
    ```

### 3 Clone the Repository

```bash
# Using SSH (Recommended if you have keys setup)
git clone git@github.com:TromsFylkestrafikk/rtm-vts.git
# Or using HTTPS
# git clone https://github.com/TromsFylkestrafikk/rtm-vts.git

cd rtm-vts
```
### 2. Configure Environment Variables
This project uses a .env file in the project root directory to manage configuration.

Install python-dotenv: (Should be in requirements.txt)
```Bash
pip install python-dotenv
```

Edit .env and add your values:
```Bash
# Django Core
SECRET_KEY='your_strong_random_secret_key' # Generate a real one for production!
DEBUG=True # Set to False in production
ALLOWED_HOSTS=127.0.0.1,localhost # Comma-separated, add production domain(s)

# Database (SpatiaLite)
DATABASE_NAME=db.sqlite3 # Or your preferred filename
# CRITICAL FOR SPATIALITE (especially Windows/macOS):
# Uncomment and set the *full path* to your mod_spatialite library file if needed
# SPATIALITE_LIBRARY_PATH=/path/to/your/mod_spatialite.dll_or_dylib_or_so

# VTS DATEX II API Credentials (Rename if needed for consistency)
UserName_DATEX="your_vts_username"
Password_DATEX="your_vts_password"

# MQTT Broker Configuration
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_USERNAME= # Leave blank if no auth
MQTT_PASSWORD= # Leave blank if no auth
MQTT_BASE_COLLISION_TOPIC=vts/collisions # Base topic for publications

# Entur API (If fetch_entur_trips.py is used)
# ET_CLIENT_NAME="your_entur_client_name"
```
### 5. Set up MQTT Broker
Ensure your chosen MQTT broker (e.g., Mosquitto) is installed and running according to its documentation. Check that it's listening on the configured host and port (e.g., localhost:1883).
# Database Setup
Create Migrations (if models changed):
```Bash
python manage.py makemigrations map
```
Apply Migrations: This creates the database tables, including the necessary spatial metadata tables for SpatiaLite.
```Bash
python manage.py migrate
```
Initial Data Population
Run these commands to populate the database with initial data:
Import Bus Routes: (Requires the source GeoJSON file)

```Bash
python manage.py fetch-coordinates
```

```Bash
python manage.py import_bus_routes --file data/route_coordinates.geojson
```
(Adjust the command and file path as necessary)

Fetch Initial VTS Situations:
```Bash
python manage.py fetch_vts_situations
```
Calculate Initial Collisions:
```Bash
python manage.py update_collisions
```

## Running the Application
### 1. Run the Development Server
```Bash
python manage.py runserver
```
Access the web interface at http://127.0.0.1:8000/.

### 2. Run the Periodic Publisher (Crucial for MQTT Updates)
The publish_new_collisions command needs to run periodically (e.g., every 5 minutes) to send updates via MQTT. This does not run automatically with runserver.

For Development: You can run it manually in a separate terminal (ensure your virtual environment is activated):
```Bash
python manage.py run_cron
```
For Production/Continuous Operation: Schedule this command using cron (Linux/macOS), systemd timers (Linux).

Example Cron Job (Linux/macOS):

Edit crontab: crontab -e
Run publish command every 5 minutes, log output
*/5 * * * * /path/to/your/project/.venv/bin/python /path/to/your/project/manage.py run_cron >> /path/to/your/project/logs/publish_collisions.log 2>&1

### Key Components Models (map/models.py)
* **VtsSituation:** Stores road situation data fetched from the VTS DATEX II API.
* **BusRoute:** Stores static bus route geometry and metadata.
* **DetectedCollision:** Stores calculated collision instances between VtsSituation and BusRoute, including MQTT publishing status.
* **ApiMetadata:** Stores general metadata (e.g., last VTS fetch time).
### Management Commands (map/management/commands/)
* **fetch_vts_situations.py:** Fetches data from VTS API and saves to VtsSituation.
* **import_bus_routes.py:** Imports routes from GeoJSON into BusRoute.
* **calculate_and_store_collisions.py:** Calculates and saves/updates DetectedCollision records. Use --no-clear to avoid deleting existing collisions.
* **publish_new_collisions.py:** Checks for unpublished collisions and sends them via MQTT. Needs to be run periodically.
* **purge_transitinformation.py** (or similar name): Deletes data from VtsSituation.
* **fetch_entur_trips.py:** Fetches trip data from Entur.
* **fetch_coordinates.py:** Fetches bus route coordinates.

### MQTT Publishing
* Broker: Connects to the broker defined in .env.

* Topics: Publishes new collisions to topics structured like:

{MQTT_BASE_COLLISION_TOPIC}/route/{bus_route_id}/severity/{severity}/filter/{filter_used}

(e.g., vts/collisions/route/123/severity/high/filter/accident) OR 
(e.g., vts/collisions/+/123/severity/+/filter/+)
* Payload: JSON containing details of the collision (IDs, location, timestamp, etc.).

### Usage Notes
Data Accuracy: The application displays data sourced from VTS and Entur. Accuracy depends on the source providers.
Check out: https://datex-server-get-v3-1.atlas.vegvesen.no/datexapi/

### Credits
* Data Source: Norwegian Public Roads Administration (Statens vegvesen), Entur.
* Map Tiles: https://victor.tftservice.no
* Developers: Lga239, agu078
* Input for progression from: tfk-kaare, Troms Fylkeskommune developer team