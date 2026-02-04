/**
 * Toggle a section's visibility
 * @param {string} sectionId - The ID of the section content to toggle
 */
function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    const header = section.previousElementSibling;
    const icon = header.querySelector('.toggle-icon');
    
    if (section.style.display === 'none' || section.style.display === '') {
        section.style.display = 'block';
        icon.textContent = '▼';
    } else {
        section.style.display = 'none';
        icon.textContent = '►';
    }
}

/**
 * Initialize the sidebar sections based on the current page
 */
function initializeSidebar() {
    // Show transit section by default
    const transitContent = document.getElementById('transit-content');
    transitContent.style.display = 'block';
    
    const tripContent = document.getElementById('trip-content');
    const tripIcon = document.querySelector('.trip-header .toggle-icon');
    
    // Use the window variable set in the main HTML
    if (window.isOnTripPage) {
        // If on trip page, show the trip section too
        tripContent.style.display = 'block';
    } else {
        // Otherwise hide it by default
        tripContent.style.display = 'none';
        tripIcon.textContent = '►';
    }
}