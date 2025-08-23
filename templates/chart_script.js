// Global variables
let trendsChart = null;
let versionChart = null;
let versionData = [];
let availableVersions = [];
let allTrendsData = []; // Store original data for time range filtering
let originalTimeRange = null; // Store original time range

// Chart.js default configuration
Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif';
Chart.defaults.responsive = true;
Chart.defaults.maintainAspectRatio = false;

// Utility functions
function parseDate(dateString) {
    return new Date(dateString);
}

function formatDate(date, dataRange = null) {
    // If we know the data range, format accordingly
    if (dataRange) {
        const rangeDays = (dataRange.max - dataRange.min) / (1000 * 60 * 60 * 24);
        
        // For data spanning more than 6 months, show month/year for clarity
        if (rangeDays > 180) {
            return date.toLocaleDateString('en-US', { 
                year: 'numeric',
                month: 'short'
            });
        }
        // For shorter ranges, show month/day
        else if (rangeDays > 30) {
            return date.toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric' 
            });
        }
    }
    
    // Default format with year
    return date.toLocaleDateString('en-US', { 
        year: 'numeric',
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
            const line = lines[i].trim();
            if (!line) continue; // Skip empty lines
            
            const values = line.split(',');
            if (values.length !== headers.length) continue; // Skip malformed lines
            
            const row = {};
            headers.forEach((header, index) => {
                row[header.trim()] = values[index]?.trim();
            });
            
            // Check if this is installer data, country data, or download trend data
            if (row.installer_name && row.download_count) {
                // Installer statistics data
                data.push(row);
            } else if (row.country_code && row.download_count) {
                // Country statistics data
                data.push(row);
            } else if (row.download_date && row.daily_downloads) {
                // Download trend data
                data.push(row);
            }
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
    } else if (pattern === 'installer') {
        latestFilename = 'installer_stats_30d_latest.csv';
    } else if (pattern === 'country') {
        latestFilename = 'download_by_country_30d_latest.csv';
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
    } else if (pattern === 'installer') {
        relevantFiles = files.filter(f => f.includes('installer_stats_30d_') && !f.includes('latest'));
    } else if (pattern === 'country') {
        relevantFiles = files.filter(f => f.includes('download_by_country_30d_') && !f.includes('latest'));
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
        allTrendsData = data
            .filter(row => row.download_date && row.daily_downloads) // Filter valid data
            .map(row => {
                const date = parseDate(row.download_date);
                const downloads = parseInt(row.daily_downloads);
                
                // Skip invalid dates or downloads
                if (isNaN(date.getTime()) || isNaN(downloads)) return null;
                
                return {
                    x: date.getTime(),
                    y: downloads
                };
            })
            .filter(point => point !== null) // Remove null entries
            .sort((a, b) => a.x - b.x);
        
        // Store original time range
        if (allTrendsData.length > 0) {
            originalTimeRange = {
                min: Math.min(...allTrendsData.map(d => d.x)),
                max: Math.max(...allTrendsData.map(d => d.x))
            };
            
                    // Initialize time range controls
        initTimeRangeControls();
        

    }
    
    const chartData = allTrendsData;
    
    loadingEl.style.display = 'none';
    chartEl.style.display = 'block';
    document.getElementById('timeRangeControls').style.display = 'block';
    
    // Show chart actions
    const chartActions = document.getElementById('trendsChartActions');
    if (chartActions) {
        chartActions.style.display = 'flex';
        // Update data count
        const dataCountEl = document.getElementById('trendsDataCount');
        if (dataCountEl) {
            dataCountEl.textContent = allTrendsData.length;
        }
    }
        
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
                        min: Math.min(...chartData.map(d => d.x)),
                        max: Math.max(...chartData.map(d => d.x)),
                        ticks: {
                            callback: function(value, index, values) {
                                // Convert back to date for display
                                const date = new Date(value);
                                const dataRange = {
                                    min: Math.min(...chartData.map(d => d.x)),
                                    max: Math.max(...chartData.map(d => d.x))
                                };
                                return formatDate(date, dataRange);
                            },
                            maxTicksLimit: 12
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
    // Find the version chart section by traversing up from the version chart element
    const versionSection = document.getElementById('versionChart').closest('.chart-section');
    
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
        
        // Check if we have enough versions for comparison (need at least 2 versions)
        if (availableVersions.length < 2) {
            console.log('Not enough versions for comparison, hiding version chart section');
            if (versionSection) {
                versionSection.style.display = 'none';
            }
            return;
        }
        
        loadingEl.style.display = 'none';
        controlsEl.style.display = 'block';
        chartEl.style.display = 'block';
        
        // Show version chart actions
        const versionChartActions = document.getElementById('versionChartActions');
        if (versionChartActions) {
            versionChartActions.style.display = 'flex';
            // Update data count
            const versionDataCountEl = document.getElementById('versionDataCount');
            if (versionDataCountEl) {
                versionDataCountEl.textContent = versionData.length;
            }
        }
        
        // Create version checkboxes
        createVersionCheckboxes();
        
        // Initialize empty chart first
        initEmptyVersionChart();
        
        // Select latest 3 versions by default after chart is initialized
        selectLatestVersions();
        
    } catch (error) {
        loadingEl.style.display = 'none';
        console.log('Failed to load version data, hiding version chart section');
        
        // Hide the entire version section if there's an error loading data
        if (versionSection) {
            versionSection.style.display = 'none';
        }
        
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
                        maxTicksLimit: 12
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
        const chartData = versionRows
            .filter(row => row.download_date && row.daily_downloads) // Filter valid data
            .map(row => {
                const date = parseDate(row.download_date);
                const downloads = parseInt(row.daily_downloads);
                
                // Skip invalid dates or downloads
                if (isNaN(date.getTime()) || isNaN(downloads)) return null;
                
                return {
                    x: date.getTime(),
                    y: downloads
                };
            })
            .filter(point => point !== null) // Remove null entries
            .sort((a, b) => a.x - b.x);
        
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
    
    // Auto-adapt time range based on actual data
    if (datasets.length > 0) {
        const allDataPoints = datasets.flatMap(dataset => dataset.data);
        if (allDataPoints.length > 0) {
            const minTime = Math.min(...allDataPoints.map(d => d.x));
            const maxTime = Math.max(...allDataPoints.map(d => d.x));
            
            versionChart.options.scales.x.min = minTime;
            versionChart.options.scales.x.max = maxTime;
        }
    }
    
    versionChart.update();
}

// Time range control functions
function initTimeRangeControls() {
    if (!originalTimeRange) return;
    
    const startDate = document.getElementById('startDate');
    const endDate = document.getElementById('endDate');
    
    // Set initial values to full range
    startDate.value = new Date(originalTimeRange.min).toISOString().split('T')[0];
    endDate.value = new Date(originalTimeRange.max).toISOString().split('T')[0];
    
    // Set min/max attributes
    const minDateStr = new Date(originalTimeRange.min).toISOString().split('T')[0];
    const maxDateStr = new Date(originalTimeRange.max).toISOString().split('T')[0];
    
    startDate.min = minDateStr;
    startDate.max = maxDateStr;
    endDate.min = minDateStr;
    endDate.max = maxDateStr;
}

function updateTimeRange() {
    const startDate = document.getElementById('startDate').value;
    const endDate = document.getElementById('endDate').value;
    
    if (!startDate || !endDate) {
        alert('Please select both start and end dates');
        return;
    }
    
    const startTime = new Date(startDate).getTime();
    const endTime = new Date(endDate + 'T23:59:59').getTime(); // Include the full end day
    
    if (startTime >= endTime) {
        alert('Start date must be before end date');
        return;
    }
    
    // Filter data for the selected range
    const filteredData = allTrendsData.filter(point => 
        point.x >= startTime && point.x <= endTime
    );
    
    if (filteredData.length === 0) {
        alert('No data available for the selected time range');
        return;
    }
    
    // Update chart
    updateTrendsChart(filteredData);
}

function resetTimeRange() {
    if (!originalTimeRange) return;
    
    // Reset input values
    document.getElementById('startDate').value = new Date(originalTimeRange.min).toISOString().split('T')[0];
    document.getElementById('endDate').value = new Date(originalTimeRange.max).toISOString().split('T')[0];
    
    // Update chart with full data
    updateTrendsChart(allTrendsData);
}

function setPresetRange(preset) {
    if (!originalTimeRange) return;
    
    const endTime = originalTimeRange.max;
    let startTime;
    
    const now = new Date(endTime);
    
    switch(preset) {
        case '1month':
            startTime = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000).getTime();
            break;
        case '3months':
            startTime = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000).getTime();
            break;
        case '6months':
            startTime = new Date(now.getTime() - 180 * 24 * 60 * 60 * 1000).getTime();
            break;
        case '1year':
            startTime = new Date(now.getTime() - 365 * 24 * 60 * 60 * 1000).getTime();
            break;
        default:
            return;
    }
    
    // Ensure start time doesn't go before data start
    startTime = Math.max(startTime, originalTimeRange.min);
    
    // Update input values
    document.getElementById('startDate').value = new Date(startTime).toISOString().split('T')[0];
    document.getElementById('endDate').value = new Date(endTime).toISOString().split('T')[0];
    
    // Apply the range
    updateTimeRange();
}

function updateTrendsChart(chartData) {
    if (!trendsChart || !chartData.length) return;
    
    // Update chart data
    trendsChart.data.datasets[0].data = chartData;
    
    // Update axis range
    const minTime = Math.min(...chartData.map(d => d.x));
    const maxTime = Math.max(...chartData.map(d => d.x));
    
    trendsChart.options.scales.x.min = minTime;
    trendsChart.options.scales.x.max = maxTime;
    
    // Update the callback to use current data range
    const dataRange = { min: minTime, max: maxTime };
    trendsChart.options.scales.x.ticks.callback = function(value, index, values) {
        const date = new Date(value);
        return formatDate(date, dataRange);
    };
    
    trendsChart.update();
}

// Data download functionality

function downloadTrendsData() {
    if (!allTrendsData || allTrendsData.length === 0) {
        alert('No trends data available for download');
        return;
    }
    
    // Convert data to CSV format
    const csvContent = convertTrendsDataToCSV(allTrendsData);
    const filename = `${window.location.pathname.split('/').slice(-2, -1)[0]}_download_trends_${getCurrentDateString()}.csv`;
    
    downloadCSV(csvContent, filename);
}

function downloadVersionData() {
    if (!versionData || versionData.length === 0) {
        alert('No version data available for download');
        return;
    }
    
    // Load version data from CSV and convert
    tryLoadRecentCsv('versions').then(data => {
        const csvContent = convertVersionDataToCSV(data);
        const filename = `${window.location.pathname.split('/').slice(-2, -1)[0]}_version_comparison_${getCurrentDateString()}.csv`;
        downloadCSV(csvContent, filename);
    }).catch(error => {
        console.error('Error downloading version data:', error);
        alert('Failed to download version data');
    });
}

function convertTrendsDataToCSV(data) {
    const headers = ['download_date', 'daily_downloads'];
    const csvRows = [headers.join(',')];
    
    data.forEach(point => {
        const date = new Date(point.x).toISOString().split('T')[0];
        const downloads = point.y;
        csvRows.push(`${date},${downloads}`);
    });
    
    return csvRows.join('\n');
}

function convertVersionDataToCSV(data) {
    if (!data || data.length === 0) return '';
    
    // Get headers from first row
    const headers = Object.keys(data[0]);
    const csvRows = [headers.join(',')];
    
    data.forEach(row => {
        const values = headers.map(header => {
            const value = row[header];
            // Escape commas and quotes in values
            if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
                return `"${value.replace(/"/g, '""')}"`;
            }
            return value;
        });
        csvRows.push(values.join(','));
    });
    
    return csvRows.join('\n');
}

function downloadCSV(csvContent, filename) {
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    
    if (link.download !== undefined) {
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    } else {
        // Fallback for older browsers
        alert('Your browser does not support automatic downloads. Please copy the data from the preview.');
    }
}

function previewTrendsData() {
    if (!allTrendsData || allTrendsData.length === 0) {
        alert('No trends data available for preview');
        return;
    }
    
    const csvContent = convertTrendsDataToCSV(allTrendsData);
    showDataPreview('Download Trends Data Preview', csvContent, () => downloadTrendsData());
}

function previewVersionData() {
    if (!versionData || versionData.length === 0) {
        alert('No version data available for preview');
        return;
    }
    
    tryLoadRecentCsv('versions').then(data => {
        const csvContent = convertVersionDataToCSV(data);
        showDataPreview('Version Comparison Data Preview', csvContent, () => downloadVersionData());
    }).catch(error => {
        console.error('Error previewing version data:', error);
        alert('Failed to preview version data');
    });
}

function showDataPreview(title, csvContent, downloadCallback) {
    const modal = document.getElementById('dataPreviewModal');
    const titleEl = document.getElementById('previewTitle');
    const contentEl = document.getElementById('previewContent');
    const downloadBtn = document.getElementById('downloadFromPreview');
    
    titleEl.textContent = title;
    
    // Show first 20 lines of CSV for preview
    const lines = csvContent.split('\n');
    const previewLines = lines.slice(0, 21); // Header + 20 data rows
    const previewContent = previewLines.join('\n');
    
    if (lines.length > 21) {
        contentEl.textContent = previewContent + '\n... (' + (lines.length - 21) + ' more rows)';
    } else {
        contentEl.textContent = previewContent;
    }
    
    // Set download callback
    downloadBtn.onclick = () => {
        downloadCallback();
        closeDataPreview();
    };
    
    modal.style.display = 'flex';
}

function closeDataPreview() {
    document.getElementById('dataPreviewModal').style.display = 'none';
}

function getCurrentDateString() {
    const now = new Date();
    return now.toISOString().split('T')[0].replace(/-/g, '');
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('dataPreviewModal');
    if (event.target === modal) {
        closeDataPreview();
    }
}

// Clipboard copy functionality
async function copyToClipboard(textareaId, buttonElement) {
    const textarea = document.getElementById(textareaId);
    const text = textarea.value;
    
    try {
        // Modern clipboard API
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
        } else {
            // Fallback for older browsers
            textarea.select();
            textarea.setSelectionRange(0, 99999); // For mobile devices
            document.execCommand('copy');
        }
        
        // Visual feedback
        const originalText = buttonElement.textContent;
        buttonElement.classList.add('copied');
        buttonElement.textContent = 'Copied!';
        
        // Reset button after 2 seconds
        setTimeout(() => {
            buttonElement.classList.remove('copied');
            buttonElement.textContent = originalText;
        }, 2000);
        
    } catch (err) {
        console.error('Failed to copy to clipboard:', err);
        
        // Fallback: select the text for manual copying
        textarea.select();
        textarea.setSelectionRange(0, 99999);
        
        // Show alert with fallback instruction
        alert('Copy failed. The text has been selected - please use Ctrl+C (or Cmd+C on Mac) to copy.');
    }
}

// Initialize charts when page loads
document.addEventListener('DOMContentLoaded', function() {
    initTrendsChart();
    initVersionChart();
    initInstallerChart();
    initCountryChart();
});

// Installer statistics functions
let installerChart = null;

async function initInstallerChart() {
    const loadingEl = document.getElementById('installerLoading');
    const errorEl = document.getElementById('installerError');
    const chartEl = document.getElementById('installerChart');
    const actionsEl = document.getElementById('installerChartActions');
    const dataCountEl = document.getElementById('installerDataCount');
    
    try {
        // Try to load installer statistics CSV
        const data = await tryLoadRecentCsv('installer');
        
        if (data && data.length > 0) {
            // Prepare chart data
            const chartData = {
                labels: data.map(row => row.installer_name),
                datasets: [{
                    data: data.map(row => parseInt(row.download_count)),
                    backgroundColor: [
                        '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
                        '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
                        '#F8C471', '#82E0AA', '#F1948A', '#85C1E9', '#D7BDE2'
                    ],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            };
            
            // Create pie chart
            const ctx = chartEl.getContext('2d');
            installerChart = new Chart(ctx, {
                type: 'pie',
                data: chartData,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                padding: 20,
                                usePointStyle: true,
                                font: {
                                    size: 12
                                }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.parsed;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = ((value / total) * 100).toFixed(2);
                                    return `${label}: ${value.toLocaleString()} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
            
            // Show chart
            chartEl.style.display = 'block';
            actionsEl.style.display = 'flex';
            dataCountEl.textContent = data.length;
            
            // Hide loading
            loadingEl.style.display = 'none';
        } else {
            throw new Error('No installer data available');
        }
    } catch (error) {
        console.error('Error loading installer chart:', error);
        errorEl.textContent = 'Failed to load installer statistics data. Please try again later.';
        errorEl.style.display = 'block';
        loadingEl.style.display = 'none';
    }
}

function previewInstallerData() {
    tryLoadRecentCsv('installer').then(data => {
        const csvContent = convertInstallerDataToCSV(data);
        showDataPreview('Installer Statistics Data Preview', csvContent, () => downloadInstallerData());
    }).catch(error => {
        console.error('Error previewing installer data:', error);
        alert('Failed to preview installer data');
    });
}

function downloadInstallerData() {
    tryLoadRecentCsv('installer').then(data => {
        const csvContent = convertInstallerDataToCSV(data);
        const filename = `installer-statistics-${getCurrentDateString()}.csv`;
        downloadCSV(csvContent, filename);
    }).catch(error => {
        console.error('Error downloading installer data:', error);
        alert('Failed to download installer data');
    });
}

function convertInstallerDataToCSV(data) {
    if (!data || data.length === 0) {
        return 'installer_name,download_count,percentage\n';
    }
    
    const headers = ['installer_name', 'download_count', 'percentage'];
    const csvRows = [headers.join(',')];
    
    data.forEach(row => {
        const values = headers.map(header => {
            const value = row[header] || '';
            // Escape commas and quotes in values
            if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
                return `"${value.replace(/"/g, '""')}"`;
            }
            return value;
        });
        csvRows.push(values.join(','));
    });
    
    return csvRows.join('\n');
}

// Country statistics functions
let countryChart = null;

async function initCountryChart() {
    const loadingEl = document.getElementById('countryLoading');
    const errorEl = document.getElementById('countryError');
    const chartEl = document.getElementById('countryChart');
    const actionsEl = document.getElementById('countryChartActions');
    const dataCountEl = document.getElementById('countryDataCount');
    
    try {
        // Try to load country statistics CSV
        const data = await tryLoadRecentCsv('country');
        
        if (data && data.length > 0) {
            // Prepare chart data
            const chartData = {
                labels: data.map(row => row.country_code),
                datasets: [{
                    data: data.map(row => parseInt(row.download_count)),
                    backgroundColor: [
                        '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
                        '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
                        '#F8C471', '#82E0AA', '#F1948A', '#85C1E9', '#D7BDE2'
                    ],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            };
            
            // Create pie chart
            const ctx = chartEl.getContext('2d');
            countryChart = new Chart(ctx, {
                type: 'pie',
                data: chartData,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                padding: 20,
                                usePointStyle: true,
                                font: {
                                    size: 12
                                }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.parsed;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = ((value / total) * 100).toFixed(2);
                                    return `${label}: ${value.toLocaleString()} (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
            
            // Show chart
            chartEl.style.display = 'block';
            actionsEl.style.display = 'flex';
            dataCountEl.textContent = data.length;
            
            // Hide loading
            loadingEl.style.display = 'none';
        } else {
            throw new Error('No country data available');
        }
    } catch (error) {
        console.error('Error loading country chart:', error);
        errorEl.textContent = 'Failed to load country statistics data. Please try again later.';
        errorEl.style.display = 'block';
        loadingEl.style.display = 'none';
    }
}

function previewCountryData() {
    tryLoadRecentCsv('country').then(data => {
        const csvContent = convertCountryDataToCSV(data);
        showDataPreview('Country Statistics Data Preview', csvContent, () => downloadCountryData());
    }).catch(error => {
        console.error('Error previewing country data:', error);
        alert('Failed to preview country data');
    });
}

function downloadCountryData() {
    tryLoadRecentCsv('country').then(data => {
        const csvContent = convertCountryDataToCSV(data);
        const filename = `country-statistics-${getCurrentDateString()}.csv`;
        downloadCSV(csvContent, filename);
    }).catch(error => {
        console.error('Error downloading country data:', error);
        alert('Failed to download country data');
    });
}

function convertCountryDataToCSV(data) {
    if (!data || data.length === 0) {
        return 'country_code,download_count,percentage\n';
    }
    
    const headers = ['country_code', 'download_count', 'percentage'];
    const csvRows = [headers.join(',')];
    
    data.forEach(row => {
        const values = headers.map(header => {
            const value = row[header] || '';
            // Escape commas and quotes in values
            if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
                return `"${value.replace(/"/g, '""')}"`;
            }
            return value;
        });
        csvRows.push(values.join(','));
    });
    
    return csvRows.join('\n');
}
