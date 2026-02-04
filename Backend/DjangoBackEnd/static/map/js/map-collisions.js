
// --- State Variable ---
let collisionsLayerVisible = false; // Track visibility state
const COLLISION_POINTS_SOURCE_ID = 'collision-points-source'; // Choose a unique ID
const COLLISION_POINTS_LAYER_ID = 'collision-points-layer'; 
// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    // Wait for map object
    const checkMap = setInterval(() => {
        if (typeof map !== 'undefined' && map.loaded()) {
            clearInterval(checkMap);
            initializeCollisionButton();
        } else if (typeof map !== 'undefined' && !map.loaded()) {
            map.once('load', initializeCollisionButton);
            clearInterval(checkMap);
        }
    }, 100);
});

/**
 * Adds the event listener to the toggle button.
 */
function initializeCollisionButton() {
    const toggleButton = document.getElementById('toggle-collisions-btn');
    if (toggleButton) {
        toggleButton.addEventListener('click', toggleCollisionPointsLayer);
        console.log('Toggle collision points button listener added.');
    } else {
        console.warn('Toggle collision points button #toggle-collisions-btn not found.');
    }
}

/**
 * Toggles the dedicated collision points layer on/off.
 */
async function toggleCollisionPointsLayer() {
    const toggleButton = document.getElementById('toggle-collisions-btn');
    collisionsLayerVisible = !collisionsLayerVisible; // Flip state
    
    console.log(`Toggling collision points layer. Visible: ${collisionsLayerVisible}`);
    toggleButton.disabled = true; // Disable while working

    if (collisionsLayerVisible) {
        // --- Show Collision Points Layer ---
        toggleButton.textContent = 'Hide Collision Points';
        try {
            console.log("Fetching stored collision data for points...");
            const response = await fetch(API_STORED_COLLISIONS); // Use constant from map-config.js
            if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);

            const collisionApiResponse = await response.json();
            const collisionData = collisionApiResponse.stored_collisions || []; // Use correct key from your API response

            if (!Array.isArray(collisionData)) throw new Error("Invalid collision data format.");

            console.log(`Received ${collisionData.length} stored collision records.`);

            // Convert collision data to GeoJSON Points FeatureCollection
            const collisionFeatures = collisionData.map(collision => ({
                type: 'Feature',
                // Use transit_information_id as the unique ID for the point feature
                id: collision.transit_information_id,
                geometry: {
                    type: 'Point',
                    coordinates: [collision.transit_lon, collision.transit_lat]
                },
                properties: {
                    // Include relevant data for popups
                    transit_id: collision.transit_information_id,
                    route_id: collision.bus_route_id, // ID of ONE route it collided with
                    detection_time: collision.detection_timestamp,
                    tolerance: collision.tolerance_meters
                    // Add any other properties needed
                }
            }));

            const collisionGeoJSON = {
                type: 'FeatureCollection',
                features: collisionFeatures
            };

            // Add the source and layer (remove if existing first for refresh)
            addOrUpdateCollisionLayer(collisionGeoJSON);

        } catch (error) {
            console.error("❌ Error fetching or displaying collision points:", error);
            collisionsLayerVisible = false; // Revert state on error
            toggleButton.textContent = 'Show Collision Points';
        } finally {
            toggleButton.disabled = false; // Re-enable button
        }

    } else {
        // --- Hide Collision Points Layer ---
        toggleButton.textContent = 'Show Collision Points';
        removeCollisionLayer();
        toggleButton.disabled = false; // Re-enable immediately when hiding
    }
}

/**
 * Adds or updates the dedicated collision points source and layer.
 * @param {object} geojsonData - GeoJSON FeatureCollection of collision points.
 */
function addOrUpdateCollisionLayer(geojsonData) {
    if (!map.isStyleLoaded()) {
        console.warn("Map style not loaded, cannot add collision layer.");
        return;
    }

    // Use constants from map-config.js
    const sourceId = COLLISION_POINTS_SOURCE_ID;
    const layerId = COLLISION_POINTS_LAYER_ID;

    // Remove previous layer/source first to ensure clean update
    removeCollisionLayer();

    // Add new source
    map.addSource(sourceId, {
        type: 'geojson',
        data: geojsonData
    });
    console.log(`Collision points source '${sourceId}' added.`);

    // Add new layer with distinct styling
    map.addLayer({
        id: layerId,
        type: 'circle',
        source: sourceId,
        paint: {
            'circle-color': '#000000', // Bright red for collisions
            'circle-radius': 8,
            'circle-stroke-width': 1,
            'circle-stroke-color': '#FFFFFF' // White outline
        }
    });
    console.log(`Collision points layer '${layerId}' added.`);

    // Add popups specifically for this layer
    setupCollisionPopupOnClick(layerId);
}

/**
 * Removes the dedicated collision points layer and source.
 */
function removeCollisionLayer() {
    // Use constants from map-config.js
    const sourceId = COLLISION_POINTS_SOURCE_ID;
    const layerId = COLLISION_POINTS_LAYER_ID;

     // Clean up popups if attached
     cleanupCollisionPopupListeners(layerId);

    if (map.getLayer(layerId)) {
        map.removeLayer(layerId);
        console.log(`Collision points layer '${layerId}' removed.`);
    }
    if (map.getSource(sourceId)) {
        map.removeSource(sourceId);
        console.log(`Collision points source '${sourceId}' removed.`);
    }
}

/**
 * Attaches popup listeners specifically for the collision points layer.
 * @param {string} layerId
 */
let collisionPopupListenersAttached = false; // Prevent multiple attachments
let collisionClickHandler, collisionMouseEnterHandler, collisionMouseLeaveHandler; // Store handlers

function setupCollisionPopupOnClick(layerId) {
    if (!map || !layerId || collisionPopupListenersAttached) return; // Prevent duplicates

    collisionClickHandler = (e) => {
        if (e.features?.length > 0) {
            const feature = e.features[0];
            const props = feature.properties;
            const coordinates = feature.geometry.coordinates.slice();

            // Basic popup content from properties
            let popupHTML = `<strong>Collision Point</strong><br>
                             Transit ID: ${props.transit_id}<br>
                             Route ID: ${props.route_id}<br>
                             Coords: ${coordinates[1].toFixed(5)}, ${coordinates[0].toFixed(5)}<br>
                             Tolerance: ${props.tolerance}m<br>
                             Detected: ${new Date(props.detection_time).toLocaleString()}`;

            new maplibregl.Popup({ closeButton: true }) // Add close button
                .setLngLat(coordinates)
                .setHTML(popupHTML)
                .addTo(map);
        }
    };

    collisionMouseEnterHandler = () => map.getCanvas().style.cursor = 'pointer';
    collisionMouseLeaveHandler = () => map.getCanvas().style.cursor = '';

    map.on('click', layerId, collisionClickHandler);
    map.on('mouseenter', layerId, collisionMouseEnterHandler);
    map.on('mouseleave', layerId, collisionMouseLeaveHandler);

    collisionPopupListenersAttached = true;
    console.log(`Popup listener attached for collision layer ${layerId}`);
}

/**
 * Removes popup listeners specifically for the collision points layer.
 * @param {string} layerId
 */
function cleanupCollisionPopupListeners(layerId) {
     if (!map || !layerId || !collisionPopupListenersAttached) return;

     map.off('click', layerId, collisionClickHandler);
     map.off('mouseenter', layerId, collisionMouseEnterHandler);
     map.off('mouseleave', layerId, collisionMouseLeaveHandler);

     collisionPopupListenersAttached = false;
     console.log(`Popup listener removed for collision layer ${layerId}`);
}