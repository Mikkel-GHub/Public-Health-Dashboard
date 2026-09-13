// Wait for the page to load before initializing the map
document.addEventListener('DOMContentLoaded', function () {
  // Initialize the map centered on Greater Sydney
  const map = L.map('map').setView([-33.8688, 151.2093], 11);

  // Add the base map tiles (OpenStreetMap)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
  }).addTo(map);

  // Define color function
  function getColor(lgaName) {
    const colors = {
      'Blacktown': '#FF6B6B',
      'Parramatta': '#4ECDC4',
      'Sydney': '#45B7D1',
      'Liverpool': '#96CEB4',
      'Canterbury-Bankstown': '#FFEAA7',
      'Cumberland': '#DDA0DD',
      'Fairfield': '#98D8C8',
      // Add more LGAs as needed
    };
    return colors[lgaName] || '#B0B0B0'; // Grey for unknown LGAs
  }

  // Load and display the Greater Sydney LGAs
  fetch('Greater Sydney - LGAs.json')
    .then(response => {
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      return response.json();
    })
    .then(data => {
      // Log to see what properties are available
      console.log('Data loaded:', data);
      console.log('First feature properties:', data.features[0]?.properties);

      // Add colored GeoJSON layer
      L.geoJSON(data, {
        style: function(feature) {
          // Try different possible property names for LGA name
          const lgaName = feature.properties?.name || 
                          feature.properties?.LGA_NAME || 
                          feature.properties?.lga_name ||
                          feature.properties?.LGA || 
                          'Unknown';
          return {
            color: "#333333",          // Dark border
            weight: 1.5,
            opacity: 0.8,
            fillColor: getColor(lgaName),
            fillOpacity: 0.7
          };
        },
        onEachFeature: function(feature, layer) {
          const lgaName = feature.properties?.name || 
                          feature.properties?.LGA_NAME || 
                          feature.properties?.lga_name ||
                          feature.properties?.LGA || 
                          'Unknown';
          layer.bindPopup(`<strong>${lgaName}</strong>`);
        }
      }).addTo(map);

      // Fit the map to show all LGAs
      map.fitBounds(L.geoJSON(data).getBounds());

      // Create and add the legend
      var legend = L.control({ position: 'bottomright' });

      legend.onAdd = function(map) {
        var div = L.DomUtil.create('div', 'legend');
        div.style.backgroundColor = 'white';
        div.style.padding = '15px';
        div.style.borderRadius = '8px';
        div.style.boxShadow = '0 2px 8px rgba(0,0,0,0.2)';
        div.style.maxHeight = '300px';
        div.style.overflowY = 'auto';
        div.style.fontSize = '12px';
        
        div.innerHTML = '<h4 style="margin:0 0 10px 0; font-size:14px;">📊 LGAs</h4>';
        
        // Get unique LGAs from your data
        const lgaNames = new Set();
        data.features.forEach(f => {
          const name = f.properties?.name || 
                       f.properties?.LGA_NAME || 
                       f.properties?.lga_name ||
                       f.properties?.LGA || 
                       'Unknown';
          lgaNames.add(name);
        });
        
        // Add each LGA to the legend
        lgaNames.forEach(name => {
          const color = getColor(name);
          div.innerHTML += `
            <div style="margin:4px 0; display:flex; align-items:center;">
              <span style="
                display:inline-block;
                width:12px;
                height:12px;
                background:${color};
                border:1px solid #333;
                margin-right:8px;
                border-radius:2px;
              "></span>
              <span>${name}</span>
            </div>
          `;
        });
        
        return div;
      };

      legend.addTo(map);
      console.log('Boundary loaded and styled successfully!');
    })
    .catch(error => {
      console.error('Error loading the boundary:', error);
    });
});