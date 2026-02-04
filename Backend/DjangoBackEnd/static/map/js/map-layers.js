// map-layers.js - Layer definitions and functions
// Fetch GeoJSON data and load it into the map



// Add custom vector tile source
map.on('load', () => {
    // Define vector tile source - the same source as in map-config.js
    map.addSource('custom-tiles', {
        type: 'vector',
        tiles: ['https://victor.tftservice.no/data/norway-vector/{z}/{x}/{y}.pbf'],
        minzoom: 0,
        maxzoom: 14
    });

    let layers = [];

    // Add layers to map
    layers.forEach(layer => {
        map.addLayer({
            id: layer.id,
            type: layer.type,
            source: "custom-tiles", // Reference the correct source
            "source-layer": layer.sourceLayer, // The layer from the vector tile
            paint: layer.paint
        });
    });
    
});

function updateLayer(id, type, data, paint) {
    // Remove existing layer and source if they exist
    if (map.getSource(id)) {
        console.log('Removing existing layer and source');
        map.removeLayer(id);
        map.removeSource(id);
    }

    // Add new source with the filtered data
    map.addSource(id, {
        type: "geojson",
        data: {
            type: "FeatureCollection",
            features: data
        }
    });

    // Add the layer with the specified paint properties
    map.addLayer({
        id: id,
        type: type,
        source: id,
        paint: paint,
        layout: {
            visibility: data.length > 0 ? "visible" : "none"
        }
    });

    console.log('Layer added:', id);  // Log when a layer is added
}

// Function to add all data layers to the map
function addAllLayers(data) {
    const points = [];
    const lines = [];

    data.features.forEach(feature => {
        if (feature.geometry.type === "Point") {
            points.push(feature);
        } else if (feature.geometry.type === "LineString") {
            lines.push(feature);
        } else if (feature.geometry.type === "GeometryCollection") {
            feature.geometry.geometries.forEach(geometry => {
                if (geometry.type === "Point") {
                    points.push({
                        type: "Feature",
                        properties: feature.properties,  // Keep original properties
                        geometry: geometry
                    });
                } else if (geometry.type === "LineString") {
                    lines.push({
                        type: "Feature",
                        properties: feature.properties,  // Keep original properties
                        geometry: geometry
                    });
                }
            });
        }
    });

    // Update the layers
    updateLayer("locations-layer", "circle", points, { 
        "circle-radius": 6, 
        "circle-color": ['match', ['get', 'severity'], 
            'none', '#7e4da3', 
            'low', '#FFFF00', 
            'high', '#FFA500', 
            'highest', '#FF0000', 
            'unknown', '#808080', 
            '#0000FF'
        ] 
    });

    updateLayer("line-layer", "line", lines, { 
        "line-color": ['match', ['get', 'severity'], 
            'none', '#7e4da3', 
            'low', '#FFFF00', 
            'high', '#FFA500', 
            'highest', '#FF0000', 
            'unknown', '#808080', 
            '#0000FF'
        ], 
        "line-width": 4 
    });

    // Add click handlers for popups
    map.on('click', 'locations-layer', function (e) {
        const { name, description = "No description", comment, severity, situation_type } = e.features[0].properties;
        new maplibregl.Popup()
            .setLngLat(e.features[0].geometry.coordinates)
            .setHTML(`<h3>${name}</h3>
                    <p>${description}</p>
                    <hr>
                    <p><strong>Comments:</strong> ${comment}</p>
                    <p><strong>Situation Type:</strong> ${situation_type}</p>
                    <p><strong>Severity:</strong> ${severity}</p>`)
            .addTo(map);
    });
}

// Function to toggle visibility of the points layer
function togglePointVisibility(isVisible) {
    map.setLayoutProperty('locations-layer', 'visibility', isVisible ? 'visible' : 'none');
}
