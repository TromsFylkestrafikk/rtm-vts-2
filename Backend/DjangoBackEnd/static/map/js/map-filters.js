// Reference to the HTML element that displays coordinates
const coordinates = document.createElement('div');
coordinates.id = 'coordinates';
document.body.appendChild(coordinates);

// Event listener for drawing completion
map.on('draw.create', (e) => {
    const feature = e.features[0];
    if (!feature) return;

    // Extract coordinates from the drawn feature
    const coords = feature.geometry.type === 'Polygon' ? 
        feature.geometry.coordinates[0] : 
        feature.geometry.coordinates;

    // Display coordinates in the HTML element
    coordinates.innerHTML = `Coordinates:<br />${coords.map(coord => 
        `Lng: ${coord[0].toFixed(5)}, Lat: ${coord[1].toFixed(5)}`).join('<br />')}`;

    // Show coordinates in a popup on the map
    new maplibregl.Popup()
        .setLngLat(coords[0])
        .setHTML(`<strong>Coordinates:</strong><br>Lng: ${coords[0][0].toFixed(5)}<br>Lat: ${coords[0][1].toFixed(5)}`)
        .addTo(map);
});

// Function to populate dropdowns with filter options
async function populateDropdowns() {
    try {
        const response = await fetch('/api/filter-options/');
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Populate county dropdown
        const countyDropdown = document.getElementById("county-dropdown");
        data.counties.forEach(county => {
            const option = document.createElement("option");
            option.value = county;
            option.textContent = county;
            countyDropdown.appendChild(option);
        });
        
        // Populate situation dropdown
        const situationDropdown = document.getElementById("situation-dropdown");
        data.situation_types.forEach(type => {
            const option = document.createElement("option");
            option.value = type;
            option.textContent = type;
            situationDropdown.appendChild(option);
        });

        // Populate severity dropdown
        const severityDropdown = document.getElementById("severity-dropdown");
        data.severities.forEach(severity => {
            const option = document.createElement("option");
            option.value = severity;
            option.textContent = severity.charAt(0).toUpperCase() + severity.slice(1);
            severityDropdown.appendChild(option);
        });
    } catch (error) {
        console.error("❌ Error populating dropdowns:", error);
    }
}

let busMarkers = {};  // Store markers by vehicleId

// Function to fetch and update bus positions
async function fetchAndUpdateBuses() {
    try {
        const response = await fetch(API_BUS);
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const busData = await response.json();

        if (!Array.isArray(busData)) {
            throw new Error("❌ Invalid bus data format!");
        }

        console.log("📡 Live Bus Data Fetched:", busData);

        // Update bus positions on the map
        updateBusMarkers(busData);

    } catch (error) {
        console.error("❌ Error fetching bus locations:", error);
    }
}

// Function to update bus markers on the map
function updateBusMarkers(busData) {
    busData.forEach(bus => {
        const { vehicleId, latitude, longitude } = bus;

        if (!vehicleId || !latitude || !longitude) {
            console.warn("⚠️ Missing data for a bus:", bus);
            return;
        }

        // If the marker exists, move it
        if (busMarkers[vehicleId]) {
            busMarkers[vehicleId].setLngLat([longitude, latitude]);
        } else {
            // Create a new marker
            const marker = new maplibregl.Marker({ color: "red" })
                .setLngLat([longitude, latitude])
                .setPopup(new maplibregl.Popup().setHTML(`<strong>Bus ${vehicleId}</strong><br>Lat: ${latitude.toFixed(5)}<br>Lng: ${longitude.toFixed(5)}`))
                .addTo(map);

            busMarkers[vehicleId] = marker;
        }
    });
}

// function checkForIntersection(routeFeature, incidentFeature) {
//     console.log('Route feature geometry:', routeFeature.geometry.type);
//     console.log('Incident feature geometry:', incidentFeature.geometry.type);

//     // Ensure the route is a LineString
//     if (routeFeature.geometry.type !== "LineString") {
//         console.error("Route feature is not a LineString");
//         return false;
//     }

//     let incidentCoordinates = null;

//     // Handle GeometryCollection, which can contain both Point and LineString
//     if (incidentFeature.geometry.type === "GeometryCollection") {
//         const pointGeometry = incidentFeature.geometry.geometries.find(g => g.type === "Point");
//         const lineGeometry = incidentFeature.geometry.geometries.find(g => g.type === "LineString");

//         // If a Point geometry is found in the GeometryCollection
//         if (pointGeometry) {
//             incidentCoordinates = pointGeometry.coordinates;
//         }
//         // If a LineString geometry is found in the GeometryCollection
//         if (lineGeometry) {
//             console.log("Incident GeometryCollection contains a LineString, which may require different handling.");
//             return false; // You can handle this separately if needed
//         }

//         if (!incidentCoordinates) {
//             console.error("No valid Point geometry found in GeometryCollection");
//             return false;
//         }
//     } else if (incidentFeature.geometry.type === "Point") {
//         incidentCoordinates = incidentFeature.geometry.coordinates;
//     } else {
//         console.error("Incident feature is neither Point nor GeometryCollection");
//         return false;
//     }

//     // Log coordinates for debugging
//     console.log('Route Coordinates:', routeFeature.geometry.coordinates);
//     console.log('Incident Coordinates:', incidentCoordinates);

//     // Ensure coordinates are valid and numeric
//     if (!Array.isArray(routeFeature.geometry.coordinates) || !Array.isArray(incidentCoordinates)) {
//         console.error("❌ Coordinates must be arrays");
//         return false;
//     }

//     // Validate coordinates: All coordinates must be numbers
//     const validRoute = routeFeature.geometry.coordinates.every(coord => 
//         Array.isArray(coord) && coord.length === 2 && typeof coord[0] === 'number' && typeof coord[1] === 'number'
//     );
//     const validIncident = Array.isArray(incidentCoordinates) && incidentCoordinates.length === 2 
//         && typeof incidentCoordinates[0] === 'number' && typeof incidentCoordinates[1] === 'number';

//     if (!validRoute || !validIncident) {
//         console.error("❌ Coordinates must be valid numbers");
//         return false;
//     }

//     // Create turf features
//     try {
//         const route = turf.lineString(routeFeature.geometry.coordinates);
//         const incident = turf.point(incidentCoordinates);

//         // Use turf.nearestPointOnLine to find the nearest point on the line
//         const nearestPoint = turf.nearestPointOnLine(route, incident);

//         // Log the nearest point for debugging
//         console.log('Nearest Point on Route:', nearestPoint);

//         // Check if the incident is near the route (within a threshold)
//         const distance = turf.distance(incident, nearestPoint);
//         const threshold = 0.01;  // Define a threshold distance in kilometers for considering a point near the route

//         return distance <= threshold;
//     } catch (error) {
//         console.error("❌ Error during turf operation:", error);
//         return false;
//     }
// }




// Function to highlight intersecting routes
function highlightRoute(routeFeature) {
    const highlightedLayerId = "highlighted-routes";
    
    if (map.getLayer(highlightedLayerId)) {
        map.removeLayer(highlightedLayerId);
        map.removeSource(highlightedLayerId);
    }

    // Add a new layer to highlight the intersected route
    map.addLayer({
        id: highlightedLayerId,
        type: "line",
        source: {
            type: "geojson",
            data: {
                type: "FeatureCollection",
                features: [routeFeature]
            }
        },
        paint: {
            "line-color": "#FF0000",  // Red color for intersection
            "line-width": 6
        }
    });
}

// Function to check for overlaps between bus routes and incidents
async function fetchAndCheckForOverlaps() {
    try {
        // Fetch bus route and incident data
        const [routeResponse, incidentResponse] = await Promise.all([
            fetch(API_ROUTE),
            fetch(API_BASE_URL)
        ]);

        const routesGeoJSON = await routeResponse.json();
        const incidentsGeoJSON = await incidentResponse.json();

        if (!Array.isArray(routesGeoJSON.features) || !Array.isArray(incidentsGeoJSON.features)) {
            throw new Error("❌ Invalid GeoJSON data format!");
        }

        // Check intersections
        routesGeoJSON.features.forEach(route => {
            incidentsGeoJSON.features.forEach(incident => {
                if (checkForIntersection(route, incident)) {
                    // Show popup for intersection
                    new maplibregl.Popup()
                        .setLngLat(route.geometry.coordinates[0])  // Show on the bus route
                        .setHTML(`<strong>Route intersects with an incident:</strong><br>Severity: ${incident.properties.severity}`)
                        .addTo(map);

                    // Optionally highlight the route
                    highlightRoute(route);
                }
            });
        });
    } catch (error) {
        console.error("❌ Error checking for overlaps:", error);
    }
}

// Function to fetch and add bus routes to the map
async function fetchAndAddRoutes() {
    try {
        const response = await fetch(API_ROUTE);
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const geojson = await response.json();

        if (!geojson?.features) {
            throw new Error("Invalid route GeoJSON data!");
        }

        updateLayer("bus-routes", "line", geojson.features, {
            "line-color": "#33FFFF",
            "line-width": 4
        });

        console.log("✅ Routes added to map.");
    } catch (error) {
        console.error("❌ Error fetching route data:", error);
    }
}

// Initial data load when the DOM is ready
document.addEventListener('DOMContentLoaded', async function () {
    try {
        const response = await fetch(API_BASE_URL);
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const geojsonData = await response.json();

        // Validate fetched data
        if (!geojsonData?.features) {
            throw new Error("❌ Invalid GeoJSON data format!");
        }

        console.log("📡 API Data Fetched:", geojsonData);
        
        // Populate dropdowns
        populateDropdowns();
        
        // Add map layers
        addAllLayers(geojsonData);
        
        // Fetch routes and add to map
        fetchAndAddRoutes();
        fetchAndCheckForOverlaps();

        // Optionally set up regular updates for bus positions
        setInterval(fetchAndUpdateBuses, updateInterval);

        // Populate transit list with buttons (if needed)
        populateTransitList(geojsonData);
        
    } catch (error) {
        console.error("❌ Error fetching locations:", error);
    }
});
