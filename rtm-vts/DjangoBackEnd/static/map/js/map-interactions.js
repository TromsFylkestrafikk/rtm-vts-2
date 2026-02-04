// Update the map with filtered data
function updateMapWithFilteredData(filteredFeatures) {
    updateLayer("locations-layer", "circle", 
        filteredFeatures.filter(f => f.geometry.type === "Point"), 
        {
            "circle-radius": 6, 
            "circle-color": ['match', ['get', 'severity'], 
                'none', '#7e4da3', 
                'low', '#FFFF00', 
                'high', '#FFA500', 
                'highest', '#FF0000', 
                'unknown', '#808080', 
                '#0000FF'
            ]
        }
    );

    updateLayer("line-layer", "line", 
        filteredFeatures.filter(f => f.geometry.type === "LineString"), 
        {
            "line-color": ['match', ['get', 'severity'], 
                'none', '#7e4da3', 
                'low', '#FFFF00', 
                'high', '#FFA500', 
                'highest', '#FF0000', 
                'unknown', '#808080', 
                '#0000FF'
            ],
            "line-width": 4
        }
    );
}

// Combined filter function for both county and situation type
function updateFilters() {
    if (!geojsonData) return;
    
    const selectedCounty = document.getElementById("county-dropdown").value.trim().toLowerCase();
    const selectedSituation = document.getElementById("situation-dropdown").value.trim().toLowerCase();
    const selectedSeverity = document.getElementById("severity-dropdown").value.trim().toLowerCase();
    
    const filteredFeatures = geojsonData.features.filter(f => {
        const countyMatch = !selectedCounty || 
            f.properties?.county?.trim().toLowerCase() === selectedCounty;
        const situationMatch = !selectedSituation || 
            f.properties?.situation_type?.trim().toLowerCase() === selectedSituation;
        const severityMatch = !selectedSeverity || 
            f.properties?.severity?.trim().toLowerCase() === selectedSeverity;
        
        return countyMatch && situationMatch && severityMatch;
    });
    
    updateMapWithFilteredData(filteredFeatures);
}

// Function to fetch data with filters from the API

async function fetchFilteredData() {
    const countyValue = document.getElementById("county-dropdown").value;
    const situationValue = document.getElementById("situation-dropdown").value;
    const severityValue = document.getElementById("severity-dropdown").value;
    
    let url = API_BASE_URL;
    const params = new URLSearchParams();
    
    if (countyValue) params.append('county', encodeURIComponent(countyValue));
    if (situationValue) params.append('situation_type', encodeURIComponent(situationValue));
    if (severityValue) params.append('severity', encodeURIComponent(severityValue));
        
    if (params.toString()) {
        url += "?" + params.toString();
    }
    
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        geojsonData = await response.json();
        
        // Update the map with the filtered data
        addAllLayers(geojsonData);
        populateTransitList(geojsonData);
    } catch (error) {
        console.error("❌ Error fetching filtered data:", error);
    }
}

// Populates the transit list with checkboxes for each point feature
function populateTransitList(data) {
    const transitList = document.getElementById("transit-list");
    if (!transitList) return console.error("❌ 'transit-list' element not found!");
    
    transitList.innerHTML = "";
    const pointFeatures = data.features.filter(f => f.geometry.type === "Point");
    console.log(`Found ${pointFeatures.length} point features`);
    data.features
        .filter(f => f.geometry.type === "Point")
        .forEach(item => {
            // console.log("Creating list item for:", item.properties.name);
            const listItem = document.createElement("li");
            listItem.classList.add("transit-item");
            // Create container for the item info
            const itemInfo = document.createElement("div");
            itemInfo.classList.add("item-info");
            
            const label = document.createElement("label");
            label.textContent = item.properties.name || "Unnamed Location";
            
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.checked = true;
            checkbox.dataset.id = item.properties.id;
            
            checkbox.addEventListener("change", () => {
                // Toggle visibility of this specific point if possible
                // As a fallback, toggle all points
                togglePointVisibility(checkbox.checked);
            });
            
            // Create a "Go to" button
            const goToButton = document.createElement("button");
            goToButton.textContent = "Go to";
            goToButton.classList.add("go-to-btn");
            goToButton.addEventListener("click", () => {
                // Get coordinates from the feature
                const coordinates = item.geometry.coordinates;
                
                // Fly to the location
                map.flyTo({
                    center: coordinates,
                    zoom: 14,
                    essential: true
                });
                
                // Optionally, add a temporary highlight effect
                highlightLocation(item.properties.id);
            });
            
            // Add elements to the list item
            itemInfo.appendChild(checkbox);
            itemInfo.appendChild(label);
            listItem.appendChild(itemInfo);
            listItem.appendChild(goToButton);
            transitList.appendChild(listItem);
        });
}

// Function to highlight a location temporarily
function highlightLocation(id) {
    // Check if we already have a highlight layer and remove it
    if (map.getLayer('highlight-point')) {
        map.removeLayer('highlight-point');
    }
    
    if (map.getSource('highlight-source')) {
        map.removeSource('highlight-source');
    }
    
    // Find the feature with the given ID
    const feature = geojsonData.features.find(f => f.properties.id === id);
    
    if (feature && feature.geometry.type === "Point") {
        // Add a new source and layer for the highlight
        map.addSource('highlight-source', {
            type: 'geojson',
            data: {
                type: 'FeatureCollection',
                features: [feature]
            }
        });
        
        map.addLayer({
            id: 'highlight-point',
            type: 'circle',
            source: 'highlight-source',
            paint: {
                'circle-radius': 15,
                'circle-color': '#ffff00',
                'circle-opacity': 0.8,
                'circle-stroke-width': 2,
                'circle-stroke-color': '#000000'
            }
        });
        
        // Remove the highlight after 2 seconds
        setTimeout(() => {
            if (map.getLayer('highlight-point')) {
                map.removeLayer('highlight-point');
            }
            if (map.getSource('highlight-source')) {
                map.removeSource('highlight-source');
            }
        }, 2000);
    }
}
// Event listeners for dropdowns
document.getElementById("county-dropdown").addEventListener("change", fetchFilteredData);
document.getElementById("situation-dropdown").addEventListener("change", fetchFilteredData);
document.getElementById("severity-dropdown").addEventListener("change", fetchFilteredData);