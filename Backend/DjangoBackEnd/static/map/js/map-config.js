
// --- API Endpoints ---
const API_BASE_URL = "http://127.0.0.1:8000/api/location_geojson/"; // Incidents/VTS
const API_BUS = "http://127.0.0.1:8000/api/serve_bus/"; // Live Bus Positions
const API_ROUTE = "http://127.0.0.1:8000/api/busroute/"; // Bus Routes GeoJSON
const API_STORED_COLLISIONS = "/api/stored_collisions/"; // Stored Collisions
const API_FILTER_OPTIONS = '/api/filter-options/'; // Filter options

// --- MapLibre Source and Layer IDs ---
const ROUTE_SOURCE_ID = 'bus-routes-source';
const ROUTE_LAYER_ID = 'bus-routes-layer';
const INCIDENT_SOURCE_ID = 'incidents-source';
const INCIDENT_LAYER_ID = 'incidents-layer'; // Standardize on this
const TRIP_LINES_LAYER_ID = 'trip-route-lines'; // From trip.js
const TRIP_POINTS_LAYER_ID = 'trip-route-waypoints'; // From trip.js
const VECTOR_TILE_SOURCE_ID = 'custom-tiles'; // From map-layers.js

// --- Initialize Map ---
const map = new maplibregl.Map({
    container: 'map',
    style: 'https://victor2.tftservice.no/styles/osm-bright/style.json',
    center: [18.9553, 69.6496],
    zoom: 5
});

// Global map object (ensure it's accessible)
window.map = map;
// Initialize Mapbox Draw control
const draw = new MapboxDraw({
    displayControlsDefault: false,
    styles: [
        { "id": "gl-draw-point", "type": "circle", "filter": ["==", "$type", "Point"] },
        { "id": "gl-draw-line", "type": "line", "filter": ["==", "$type", "LineString"], "paint": { "line-color": "#FF0000", "line-width": 3, "line-dasharray": [0.2, 2] } },
        { "id": "gl-draw-polygon-fill", "type": "fill", "filter": ["==", "$type", "Polygon"], "paint": { "fill-color": "#FF0000", "fill-opacity": 0.3 } },
        { "id": "gl-draw-polygon-stroke", "type": "line", "filter": ["==", "$type", "Polygon"], "paint": { "line-color": "#FF0000", "line-width": 2 } }
    ]
});

// Add the drawing control to the map
map.addControl(draw);
// --- Add Navigation Control --- (Moved from map-interactions.js)
const navigationControl = new maplibregl.NavigationControl({
    showCompass: true,
    showZoom: true
});
map.addControl(navigationControl, 'bottom-right');
// Global variables
let geojsonData = null;