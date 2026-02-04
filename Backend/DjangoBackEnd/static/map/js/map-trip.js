
document.addEventListener('DOMContentLoaded', function() {
    const tripSearchForm = document.getElementById('trip-search-form');
    if (tripSearchForm) {
        console.log("Trip search form found!");
    } else {
        console.error("Trip search form NOT found!");
        return; // Exit if form not found
    }

    tripSearchForm.addEventListener('submit', function(e) {
        e.preventDefault();

        const fromLocation = document.getElementById('from').value;
        const toLocation = document.getElementById('to').value;

        console.log("Submitting trip search:", fromLocation, toLocation);

        // Use the current URL instead of Django template tag
        fetch(window.location.href, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            },
            body: new URLSearchParams({
                'from': fromLocation,
                'to': toLocation
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok: ' + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            console.log("Trip response:", data);
            if (data.trip_data) {
                renderTripMap(data.trip_data);
            } else {
                alert("Could not find a route");
            }
        })
        .catch(error => {
            console.error("Error fetching trip:", error);
            alert("An error occurred while fetching the trip: " + error.message);
        });
    });
});
function renderTripMap(trip_data) {
    console.log("Rendering trip with:", trip_data);
    if (!trip_data || !trip_data.features || trip_data.features.length === 0) {
        console.error("No valid GeoJSON data to render");
        return;
    }
    if (!trip_data || !trip_data.features || trip_data.features.length === 60) {
        console.error("No valid GeoJSON data to render");
        return;
    }
    // Check if map is initialized
    if (!map) {
        console.error("Map is not initialized!");
        return;
    }
    
    // Separate into lines and points
    const allLines = [];
    const tripPoints = [];
    
    // Possible transport modes from Entur API
    const transportModes = ['WALK', 'BUS', 'TRAM', 'SUBWAY', 'RAIL', 'FERRY', 'METRO', 'AIR'];
    
    // Process all features
    trip_data.features.forEach(feature => {
        if (feature.geometry.type === "LineString") {
            allLines.push(feature);
            
            // Extract start and end points
            if (feature.geometry.coordinates.length > 0) {
                // Start point
                tripPoints.push({
                    type: "Feature",
                    properties: {
                        name: "Waypoint",
                        isWaypoint: true
                    },
                    geometry: {
                        type: "Point",
                        coordinates: feature.geometry.coordinates[0]
                    }
                });
                
                // End point
                tripPoints.push({
                    type: "Feature",
                    properties: {
                        name: "Waypoint",
                        isWaypoint: true
                    },
                    geometry: {
                        type: "Point",
                        coordinates: feature.geometry.coordinates[feature.geometry.coordinates.length - 1]
                    }
                });
            }
        }
    });
    
    console.log(`Found ${allLines.length} line features and ${tripPoints.length} points`);
    
    // 1. Use unique layer IDs that won't conflict with VTS message layers
    const tripLinesLayerId = 'trip-route-lines';
    const tripPointsLayerId = 'trip-route-waypoints';
    
    // 2. Clean up existing trip layers if they exist (but don't affect other layers)
    if (map.getLayer(tripLinesLayerId)) {
        map.removeLayer(tripLinesLayerId);
        }
    if (map.getSource(tripLinesLayerId)) {
        map.removeSource(tripLinesLayerId);
        }
    
    if (map.getLayer(tripPointsLayerId)) {
        map.removeLayer(tripPointsLayerId);
    }
    if (map.getSource(tripPointsLayerId)) {
        map.removeSource(tripPointsLayerId);
    }
    
    // 3. Add trip lines
    if (allLines.length > 0) {
        try {
            map.addSource(tripLinesLayerId, {
                type: 'geojson',
                data: {
                    type: 'FeatureCollection',
                    features: allLines
                }
            });
            
            map.addLayer({
                id: tripLinesLayerId,
                type: 'line',
                source: tripLinesLayerId,
                layout: {
                    'line-join': 'round',
                    'line-cap': 'round'
                },
                paint: {
                    'line-color': '#007bff',
                    'line-width': 4,
                    'line-opacity': 0.8
                }
            });
            
            console.log('Successfully added trip lines layer');
        } catch (error) {
            console.error('Error adding trip lines layer:', error);
        }
    }
    
    // 4. Add waypoints if there are any
    if (tripPoints.length > 0) {
        map.addSource(tripPointsLayerId, {
            type: 'geojson',
            data: {
                type: 'FeatureCollection',
                features: tripPoints
            }
        });
        
        map.addLayer({
            id: tripPointsLayerId,
            type: 'circle',
            source: tripPointsLayerId,
            paint: {
                'circle-radius': 6,
                'circle-color': '#FFFFFF',
                'circle-stroke-width': 2,
                'circle-stroke-color': '#000000'
            }
        });
        
        // 5. Use namespaced event handling to avoid conflicts
        // First remove any existing handlers to prevent duplicates
        map.off('click', tripPointsLayerId);
        
        // Then add the new click handler
        map.on('click', tripPointsLayerId, function(e) {
            if (!e.features || !e.features[0]) return;
            
            const props = e.features[0].properties;
            const name = props.name || 'Waypoint';
            
            new maplibregl.Popup()
                .setLngLat(e.features[0].geometry.coordinates)
                .setHTML(`<h3>${name}</h3>`)
                .addTo(map);
        });
    }
    
    // 6. Fit bounds but with a flag to make it optional
    const shouldFitBounds = true; // You could make this a parameter
    if (shouldFitBounds && trip_data.features.length > 0) {
        const bounds = new maplibregl.LngLatBounds();
        
        trip_data.features.forEach(feature => {
            if (feature.geometry && feature.geometry.coordinates) {
                if (feature.geometry.type === 'LineString') {
                    feature.geometry.coordinates.forEach(coord => {
                        bounds.extend(coord);
                    });
                }
            }
        });
        
        if (!bounds.isEmpty()) {
            map.fitBounds(bounds, {
                padding: 50,
                duration: 1000
            });
        }
    }
}
function waitForMap() {
    if (!map) {
        console.log("Waiting for map to initialize...");
        setTimeout(waitForMap, 100);
        return;
    }
    
    if (!map.loaded()) {
        console.log("Map loading...");
        map.once('load', function() {
            console.log("Map loaded and ready for trip rendering");
        });
    }
}

// Call this function when the document is loaded
document.addEventListener('DOMContentLoaded', function() {
    waitForMap();
});