// Global variables
let trendsChart = null;
let versionChart = null;
let versionData = [];
let availableVersions = [];

// Chart.js default configuration
Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif';
Chart.defaults.responsive = true;
Chart.defaults.maintainAspectRatio = false;

// Utility functions
function parseDate(dateString) {
    return new Date(dateString);
}

function formatDate(date) {
    return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric' 
    });
}

// Load and parse CSV data
async function loadCsvData(filename) {
    try {
        const response = await fetch(filename);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const csvText = await response.text();
        
        const lines = csvText.trim().split('\n');
        const headers = lines[0].split(',');
        const data = [];
        
        for (let i = 1; i < lines.length; i++) {
            const values = lines[i].split(',');
            const row = {};
            headers.forEach((header, index) => {
                row[header.trim()] = values[index]?.trim();
            });
            data.push(row);
        }
        
        return data;
    } catch (error) {
        console.error('Error loading CSV data:', error);
        throw error;
    }
}

// Try to load the most recent CSV file
async function tryLoadRecentCsv(pattern) {
    // First try to load the "latest" symlink files
    let latestFilename;
    if (pattern === 'trends') {
        latestFilename = 'download_by_date_latest.csv';
    } else if (pattern === 'versions') {
        latestFilename = 'download_by_date_all_versions_latest.csv';
    }
    
    // Try the latest file first
    if (latestFilename) {
        try {
            const data = await loadCsvData(latestFilename);
            return data;
        } catch (error) {
            console.warn(`Failed to load latest file ${latestFilename}, trying timestamped files...`);
        }
    }
    
    // Fall back to timestamped files
    const files = window.availableCsvFiles || [];
    
    let relevantFiles = [];
    if (pattern === 'trends') {
        relevantFiles = files.filter(f => f.includes('download_by_date_') && !f.includes('all_versions') && !f.includes('latest'));
    } else if (pattern === 'versions') {
        relevantFiles = files.filter(f => f.includes('download_by_date_all_versions_') && !f.includes('latest'));
    }
    
    // Sort by filename (which includes timestamp) in descending order
    relevantFiles.sort((a, b) => b.localeCompare(a));
    
    for (const filename of relevantFiles) {
        try {
            const data = await loadCsvData(filename);
            return data;
        } catch (error) {
            console.warn(`Failed to load ${filename}, trying next...`);
        }
    }
    
    throw new Error(`No valid ${pattern} CSV files found`);
}

// Initialize download trends chart
async function initTrendsChart() {
    const loadingEl = document.getElementById('trendsLoading');
    const errorEl = document.getElementById('trendsError');
    const chartEl = document.getElementById('trendsChart');
    
    try {
        loadingEl.style.display = 'block';
        errorEl.style.display = 'none';
        
        const data = await tryLoadRecentCsv('trends');
        
        // Parse and prepare data
        const chartData = data.map(row => ({
            x: parseDate(row.download_date).getTime(),
            y: parseInt(row.daily_downloads)
        })).sort((a, b) => a.x - b.x);
        
        loadingEl.style.display = 'none';
        chartEl.style.display = 'block';
        
        const ctx = chartEl.getContext('2d');
        trendsChart = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: [{
                        label: 'Daily Downloads',
                        data: chartData,
                        borderColor: '#007bff',
                        backgroundColor: 'rgba(0, 123, 255, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.1,
                        pointRadius: 4,
                        pointHoverRadius: 8,
                        pointBackgroundColor: '#007bff',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2,
                        pointHoverBackgroundColor: '#0056b3',
                        pointHoverBorderColor: '#ffffff',
                        pointHoverBorderWidth: 3
                    }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                scales: {
                    x: {
                        type: 'linear',
                        title: {
                            display: true,
                            text: 'Date'
                        },
                        ticks: {
                            callback: function(value, index, values) {
                                // Convert back to date for display
                                const date = new Date(value);
                                return formatDate(date);
                            },
                            maxTicksLimit: 10
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Daily Downloads'
                        },
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        enabled: true,
                        mode: 'index',
                        intersect: false,
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: 'white',
                        bodyColor: 'white',
                        borderColor: '#007bff',
                        borderWidth: 1,
                        cornerRadius: 6,
                        displayColors: true,
                        callbacks: {
                            title: function(context) {
                                const timestamp = context[0].parsed.x;
                                const date = new Date(timestamp);
                                return date.toLocaleDateString('en-US', { 
                                    year: 'numeric',
                                    month: 'short', 
                                    day: 'numeric',
                                    weekday: 'short'
                                });
                            },
                            label: function(context) {
                                const downloads = context.parsed.y;
                                return `Daily Downloads: ${downloads.toLocaleString()}`;
                            },
                            afterLabel: function(context) {
                                // Add percentage change if there's previous data
                                const dataset = context.dataset.data;
                                const currentIndex = context.dataIndex;
                                if (currentIndex > 0) {
                                    const current = dataset[currentIndex].y;
                                    const previous = dataset[currentIndex - 1].y;
                                    const change = ((current - previous) / previous * 100).toFixed(1);
                                    const changeText = change >= 0 ? `+${change}%` : `${change}%`;
                                    const changeColor = change >= 0 ? '📈' : '📉';
                                    return `${changeColor} ${changeText} from previous day`;
                                }
                                return null;
                            }
                        }
                    }
                }
            }
        });
        
    } catch (error) {
        loadingEl.style.display = 'none';
        errorEl.style.display = 'block';
        errorEl.textContent = `Failed to load download trends: ${error.message}`;
        console.error('Error loading trends chart:', error);
    }
}

// Initialize version comparison chart
async function initVersionChart() {
    const loadingEl = document.getElementById('versionLoading');
    const errorEl = document.getElementById('versionError');
    const chartEl = document.getElementById('versionChart');
    const controlsEl = document.getElementById('versionControls');
    
    try {
        loadingEl.style.display = 'block';
        errorEl.style.display = 'none';
        
        versionData = await tryLoadRecentCsv('versions');
        
        // Get unique versions and sort them
        availableVersions = [...new Set(versionData.map(row => row.version))]
            .sort((a, b) => {
                // Try to sort versions semantically
                const parseVersion = (v) => v.split('.').map(n => parseInt(n) || 0);
                const aVer = parseVersion(a);
                const bVer = parseVersion(b);
                
                for (let i = 0; i < Math.max(aVer.length, bVer.length); i++) {
                    const aDiff = aVer[i] || 0;
                    const bDiff = bVer[i] || 0;
                    if (aDiff !== bDiff) {
                        return bDiff - aDiff; // Descending order (latest first)
                    }
                }
                return 0;
            });
        
        loadingEl.style.display = 'none';
        controlsEl.style.display = 'block';
        chartEl.style.display = 'block';
        
        // Create version checkboxes
        createVersionCheckboxes();
        
        // Initialize empty chart first
        initEmptyVersionChart();
        
        // Select latest 3 versions by default after chart is initialized
        selectLatestVersions();
        
    } catch (error) {
        loadingEl.style.display = 'none';
        errorEl.style.display = 'block';
        errorEl.textContent = `Failed to load version data: ${error.message}`;
        console.error('Error loading version chart:', error);
    }
}

function createVersionCheckboxes() {
    const container = document.getElementById('versionCheckboxes');
    container.innerHTML = '';
    
    availableVersions.forEach(version => {
        const div = document.createElement('div');
        div.className = 'version-checkbox';
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `version-${version}`;
        checkbox.value = version;
        
        const label = document.createElement('label');
        label.htmlFor = `version-${version}`;
        label.textContent = `v${version}`;
        
        div.appendChild(checkbox);
        div.appendChild(label);
        container.appendChild(div);
    });
}

function initEmptyVersionChart() {
    const ctx = document.getElementById('versionChart').getContext('2d');
    versionChart = new Chart(ctx, {
        type: 'line',
        data: {
            datasets: []
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            scales: {
                x: {
                    type: 'linear',
                    title: {
                        display: true,
                        text: 'Date'
                    },
                    ticks: {
                        callback: function(value, index, values) {
                            // Convert back to date for display
                            const date = new Date(value);
                            return formatDate(date);
                        },
                        maxTicksLimit: 10
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Daily Downloads'
                    },
                    beginAtZero: true
                }
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        padding: 15
                    }
                },
                tooltip: {
                    enabled: true,
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: 'white',
                    bodyColor: 'white',
                    borderColor: '#6c757d',
                    borderWidth: 1,
                    cornerRadius: 6,
                    displayColors: true,
                    callbacks: {
                        title: function(context) {
                            const timestamp = context[0].parsed.x;
                            const date = new Date(timestamp);
                            return date.toLocaleDateString('en-US', { 
                                year: 'numeric',
                                month: 'short', 
                                day: 'numeric',
                                weekday: 'short'
                            });
                        },
                        label: function(context) {
                            const version = context.dataset.label;
                            const downloads = context.parsed.y;
                            return `${version}: ${downloads.toLocaleString()} downloads`;
                        },
                        afterBody: function(context) {
                            // Show total downloads for all versions on this date
                            let total = 0;
                            context.forEach(item => {
                                total += item.parsed.y;
                            });
                            return `Total: ${total.toLocaleString()} downloads`;
                        },
                        footer: function(context) {
                            // Show version percentage for this date
                            if (context.length > 1) {
                                const totalDownloads = context.reduce((sum, item) => sum + item.parsed.y, 0);
                                return context.map(item => {
                                    const percentage = ((item.parsed.y / totalDownloads) * 100).toFixed(1);
                                    return `${item.dataset.label}: ${percentage}%`;
                                });
                            }
                            return null;
                        }
                    }
                }
            }
        }
    });
}

function getSelectedVersions() {
    const checkboxes = document.querySelectorAll('#versionCheckboxes input[type="checkbox"]:checked');
    return Array.from(checkboxes).map(cb => cb.value);
}

function selectLatestVersions() {
    // Deselect all first
    deselectAllVersions();
    
    // Select latest 3 versions
    const checkboxes = document.querySelectorAll('#versionCheckboxes input[type="checkbox"]');
    for (let i = 0; i < Math.min(3, checkboxes.length); i++) {
        checkboxes[i].checked = true;
    }
    
    // Only update chart if it's initialized and we have data
    if (versionChart && versionData.length > 0) {
        updateVersionChart();
    }
}

function selectAllVersions() {
    const checkboxes = document.querySelectorAll('#versionCheckboxes input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = true);
    if (versionChart) {
        updateVersionChart();
    }
}

function deselectAllVersions() {
    const checkboxes = document.querySelectorAll('#versionCheckboxes input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = false);
    if (versionChart) {
        updateVersionChart();
    }
}

function updateVersionChart() {
    const selectedVersions = getSelectedVersions();
    
    // Check if chart is initialized
    if (!versionChart) {
        console.warn('Version chart not initialized yet');
        return;
    }
    
    if (selectedVersions.length === 0) {
        versionChart.data.datasets = [];
        versionChart.update();
        return;
    }
    
    // Generate colors for selected versions
    const colors = [
        '#007bff', '#28a745', '#dc3545', '#ffc107', '#17a2b8',
        '#6f42c1', '#e83e8c', '#fd7e14', '#20c997', '#6c757d'
    ];
    
    const datasets = selectedVersions.map((version, index) => {
        const versionRows = versionData.filter(row => row.version === version);
        const chartData = versionRows.map(row => ({
            x: parseDate(row.download_date).getTime(),
            y: parseInt(row.daily_downloads)
        })).sort((a, b) => a.x - b.x);
        
        return {
            label: `v${version}`,
            data: chartData,
            borderColor: colors[index % colors.length],
            backgroundColor: colors[index % colors.length] + '20',
            borderWidth: 2,
            fill: false,
            tension: 0.1,
            pointRadius: 3,
            pointHoverRadius: 6,
            pointBackgroundColor: colors[index % colors.length],
            pointBorderColor: '#ffffff',
            pointBorderWidth: 1,
            pointHoverBackgroundColor: colors[index % colors.length],
            pointHoverBorderColor: '#ffffff',
            pointHoverBorderWidth: 2
        };
    });
    
    versionChart.data.datasets = datasets;
    versionChart.update();
}

// Initialize charts when page loads
document.addEventListener('DOMContentLoaded', function() {
    initTrendsChart();
    initVersionChart();
});
