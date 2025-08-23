import csv
import math
import os
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from google.cloud import bigquery


def load_and_process_sql(sql_file_path: str, variables: dict) -> str:
    """Load SQL file and replace template variables"""
    with open(sql_file_path, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Handle version filtering logic
    version_filter = variables.get("version_filter", "all")
    if version_filter and version_filter.lower() != "all":
        version_condition = f"AND file.version = '{version_filter}'"
    else:
        version_condition = ""
    
    # Add version condition to variables
    variables_with_condition = variables.copy()
    variables_with_condition["version_condition"] = version_condition

    # Replace template variables
    for var_name, var_value in variables_with_condition.items():
        placeholder = f"{{{{{var_name}}}}}"
        sql_content = sql_content.replace(placeholder, str(var_value))

    return sql_content


def save_results_to_csv(rows, schema, job_name: str, project_name: str = None, output_dir: str = "output") -> str:
    """Save BigQuery results to CSV file"""
    # Create project-specific directory
    if project_name:
        project_output_dir = os.path.join(output_dir, project_name)
    else:
        project_output_dir = output_dir
    
    os.makedirs(project_output_dir, exist_ok=True)
    
    # Extract job type from job_name (remove project prefix)
    job_type = job_name.split('.')[-1] if '.' in job_name else job_name
    
    # Generate filename with timestamp for historical records
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{job_type}_{timestamp}.csv"
    filepath = os.path.join(project_output_dir, filename)
    
    # Also create a "latest" symlink for easy access
    latest_filename = f"{job_type}_latest.csv"
    latest_filepath = os.path.join(project_output_dir, latest_filename)
    
    if not rows:
        print(f"No data to save for job: {job_name}")
        return filepath
    
    # Get field names from schema
    field_names = [field.name for field in schema]
    
    # Write to CSV
    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write header
        writer.writerow(field_names)
        
        # Write data rows
        for row in rows:
            # Convert row values to strings, handling dates properly
            row_data = []
            for field_name in field_names:
                value = getattr(row, field_name)
                if hasattr(value, 'strftime'):  # Date/datetime objects
                    row_data.append(value.strftime('%Y-%m-%d'))
                else:
                    row_data.append(str(value) if value is not None else '')
            writer.writerow(row_data)
    
    # Create or update the latest symlink
    if os.path.exists(latest_filepath) or os.path.islink(latest_filepath):
        os.unlink(latest_filepath)
    
    try:
        # Create relative symlink 
        os.symlink(filename, latest_filepath)
    except OSError:
        # On Windows or if symlinks aren't supported, copy the file
        import shutil
        shutil.copy2(filepath, latest_filepath)
    
    print(f"Results saved to: {filepath}")
    print(f"Latest link created: {latest_filepath}")
    return filepath


def generate_svg_chart(df, chart_type: str, project_name: str, job_name: str) -> str:
    """Generate SVG chart directly without matplotlib"""
    # Chart dimensions
    width = 800
    height = 400
    margin = 60
    
    # Colors matching the website theme
    colors = {
        'primary': '#007bff',
        'secondary': '#6c757d', 
        'success': '#28a745',
        'warning': '#ffc107',
        'danger': '#dc3545',
        'info': '#17a2b8',
        'light': '#f8f9fa',
        'dark': '#343a40',
        'white': '#ffffff',
        'border': '#e9ecef',
        'text': '#495057',
        'text_light': '#6c757d',
        'background': '#ffffff'
    }
    
    # Version colors for multi-line charts
    version_colors = ['#007bff', '#28a745', '#ffc107', '#dc3545', '#17a2b8', '#6f42c1', '#fd7e14', '#20c997']
    
    # Sort data by date
    df_sorted = df.sort_values('download_date')
    
    # Calculate data ranges
    dates = df_sorted['download_date'].tolist()
    downloads = df_sorted['daily_downloads'].tolist()
    
    # Convert dates to numeric values for plotting
    date_nums = [(d - dates[0]).days for d in dates]
    
    # Calculate chart area
    chart_width = width - 2 * margin
    chart_height = height - 2 * margin
    
    # Calculate scales
    x_min, x_max = min(date_nums), max(date_nums)
    y_min, y_max = 0, max(downloads) * 1.1
    
    def scale_x(x):
        return margin + (x - x_min) / (x_max - x_min) * chart_width
    
    def scale_y(y):
        return height - margin - (y - y_min) / (y_max - y_min) * chart_height
    
    # Start building SVG
    svg_parts = []
    
    # SVG header
    svg_parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background-color: {colors['background']}; border: 1px solid {colors['border']}; border-radius: 8px;">
    <defs>
        <linearGradient id="areaGradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" style="stop-color:{colors['primary']};stop-opacity:0.3" />
            <stop offset="100%" style="stop-color:{colors['primary']};stop-opacity:0.1" />
        </linearGradient>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="2" dy="2" stdDeviation="3" flood-color="#000000" flood-opacity="0.1"/>
        </filter>
    </defs>''')
    
    # Grid lines
    svg_parts.append('    <!-- Grid lines -->')
    # Horizontal grid lines
    for i in range(5):
        y_val = y_min + (y_max - y_min) * i / 4
        y_pos = scale_y(y_val)
        svg_parts.append(f'    <line x1="{margin}" y1="{y_pos}" x2="{width-margin}" y2="{y_pos}" stroke="{colors["border"]}" stroke-width="1" opacity="0.5"/>')
    
    # Vertical grid lines (fewer for readability)
    for i in range(6):
        x_val = x_min + (x_max - x_min) * i / 5
        x_pos = scale_x(x_val)
        svg_parts.append(f'    <line x1="{x_pos}" y1="{margin}" x2="{x_pos}" y2="{height-margin}" stroke="{colors["border"]}" stroke-width="1" opacity="0.5"/>')
    
    # Chart area
    if chart_type == 'simple':
        # Create area fill path
        area_path = f"M {scale_x(date_nums[0])} {scale_y(downloads[0])}"
        for i in range(1, len(date_nums)):
            area_path += f" L {scale_x(date_nums[i])} {scale_y(downloads[i])}"
        area_path += f" L {scale_x(date_nums[-1])} {scale_y(0)} L {scale_x(date_nums[0])} {scale_y(0)} Z"
        
        svg_parts.append(f'    <path d="{area_path}" fill="url(#areaGradient)" opacity="0.6"/>')
        
        # Line path
        line_path = f"M {scale_x(date_nums[0])} {scale_y(downloads[0])}"
        for i in range(1, len(date_nums)):
            line_path += f" L {scale_x(date_nums[i])} {scale_y(downloads[i])}"
        
        svg_parts.append(f'    <path d="{line_path}" stroke="{colors["primary"]}" stroke-width="3" fill="none" filter="url(#shadow)"/>')
        
        # Data points
        for i, (x, y) in enumerate(zip(date_nums, downloads)):
            svg_parts.append(f'    <circle cx="{scale_x(x)}" cy="{scale_y(y)}" r="4" fill="{colors["primary"]}" stroke="{colors["white"]}" stroke-width="2"/>')
    
    elif chart_type == 'version':
        # Multi-version chart
        versions = df['version'].unique()
        
        for v_idx, version in enumerate(sorted(versions)):
            version_data = df[df['version'] == version].sort_values('download_date')
            version_dates = [(d - dates[0]).days for d in version_data['download_date']]
            version_downloads = version_data['daily_downloads'].tolist()
            
            color = version_colors[v_idx % len(version_colors)]
            
            # Line path for this version
            if len(version_dates) > 1:
                line_path = f"M {scale_x(version_dates[0])} {scale_y(version_downloads[0])}"
                for i in range(1, len(version_dates)):
                    line_path += f" L {scale_x(version_dates[i])} {scale_y(version_downloads[i])}"
                
                svg_parts.append(f'    <path d="{line_path}" stroke="{color}" stroke-width="2" fill="none" filter="url(#shadow)"/>')
            
            # Data points for this version
            for x, y in zip(version_dates, version_downloads):
                svg_parts.append(f'    <circle cx="{scale_x(x)}" cy="{scale_y(y)}" r="3" fill="{color}" stroke="{colors["white"]}" stroke-width="1.5"/>')
    
    # Axis labels
    svg_parts.append('    <!-- Axis labels -->')
    
    # Y-axis labels
    for i in range(5):
        y_val = y_min + (y_max - y_min) * i / 4
        y_pos = scale_y(y_val)
        label = format_number(int(y_val))
        svg_parts.append(f'    <text x="{margin-10}" y="{y_pos+4}" text-anchor="end" font-family="system-ui, sans-serif" font-size="12" fill="{colors["text_light"]}">{label}</text>')
    
    # X-axis labels (date labels)
    for i in range(6):
        x_val = x_min + (x_max - x_min) * i / 5
        x_pos = scale_x(x_val)
        if i < len(dates):
            date_label = dates[int(x_val)] if int(x_val) < len(dates) else dates[-1]
            label = date_label.strftime('%m-%d')
            svg_parts.append(f'    <text x="{x_pos}" y="{height-margin+20}" text-anchor="middle" font-family="system-ui, sans-serif" font-size="12" fill="{colors["text_light"]}">{label}</text>')
    
    # Title
    title = f"{project_name} - Daily Downloads"
    if chart_type == 'version':
        title += " by Version"
    
    svg_parts.append(f'    <text x="{width//2}" y="30" text-anchor="middle" font-family="system-ui, sans-serif" font-size="18" font-weight="600" fill="{colors["text"]}">{title}</text>')
    
    # Axis titles
    svg_parts.append(f'    <text x="{width//2}" y="{height-15}" text-anchor="middle" font-family="system-ui, sans-serif" font-size="14" fill="{colors["text_light"]}">Date</text>')
    svg_parts.append(f'    <text x="15" y="{height//2}" text-anchor="middle" font-family="system-ui, sans-serif" font-size="14" fill="{colors["text_light"]}" transform="rotate(-90, 15, {height//2})">Daily Downloads</text>')
    
    # Legend for version chart
    if chart_type == 'version':
        legend_y = 60
        for v_idx, version in enumerate(sorted(versions)):
            color = version_colors[v_idx % len(version_colors)]
            legend_x = width - 150
            legend_y_pos = legend_y + v_idx * 20
            
            svg_parts.append(f'    <circle cx="{legend_x}" cy="{legend_y_pos}" r="6" fill="{color}"/>')
            svg_parts.append(f'    <text x="{legend_x+15}" y="{legend_y_pos+4}" font-family="system-ui, sans-serif" font-size="12" fill="{colors["text"]}">v{version}</text>')
    
    svg_parts.append('</svg>')
    
    return '\n'.join(svg_parts)


def generate_pie_chart_svg(df, project_name: str) -> str:
    """Generate SVG pie chart for installer statistics"""
    # Chart dimensions
    width = 800
    height = 500
    margin = 60
    
    # Colors for pie chart segments
    colors = [
        '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
        '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
        '#F8C471', '#82E0AA', '#F1948A', '#85C1E9', '#D7BDE2'
    ]
    
    # Calculate total downloads
    total_downloads = df['download_count'].sum()
    
    # Calculate pie chart parameters
    center_x = width // 2
    center_y = height // 2
    radius = min(width, height) // 3 - margin
    
    # Start building SVG
    svg_parts = []
    
    # SVG header
    svg_parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background-color: white; border: 1px solid #e9ecef; border-radius: 8px;">
    <defs>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="2" dy="2" stdDeviation="3" flood-color="#000000" flood-opacity="0.1"/>
        </filter>
    </defs>''')
    
    # Title
    svg_parts.append(f'    <text x="{width//2}" y="30" text-anchor="middle" font-family="system-ui, sans-serif" font-size="18" font-weight="bold" fill="#2c3e50">Recent 30 Days Installer Statistics - {project_name}</text>')
    
    # Calculate pie segments
    current_angle = 0
    for i, (_, row) in enumerate(df.iterrows()):
        installer_name = row['installer_name']
        download_count = row['download_count']
        percentage = row['percentage']
        
        # Calculate segment angle
        segment_angle = (download_count / total_downloads) * 360
        
        # Skip very small segments (less than 1%)
        if segment_angle < 3.6:  # 1% of 360 degrees
            continue
        
        # Calculate arc parameters
        start_angle_rad = math.radians(current_angle)
        end_angle_rad = math.radians(current_angle + segment_angle)
        
        # Calculate arc path
        x1 = center_x + radius * math.cos(start_angle_rad)
        y1 = center_y + radius * math.sin(start_angle_rad)
        x2 = center_x + radius * math.cos(end_angle_rad)
        y2 = center_y + radius * math.sin(end_angle_rad)
        
        # Determine if arc is large (more than 180 degrees)
        large_arc_flag = 1 if segment_angle > 180 else 0
        
        # Create arc path
        arc_path = f"M {center_x} {center_y} L {x1} {y1} A {radius} {radius} 0 {large_arc_flag} 1 {x2} {y2} Z"
        
        # Add pie segment
        color = colors[i % len(colors)]
        svg_parts.append(f'    <path d="{arc_path}" fill="{color}" filter="url(#shadow)"/>')
        
        # Add label if segment is large enough
        if segment_angle > 15:  # Only label segments larger than 15 degrees
            label_angle_rad = math.radians(current_angle + segment_angle / 2)
            label_radius = radius * 0.7
            label_x = center_x + label_radius * math.cos(label_angle_rad)
            label_y = center_y + label_radius * math.sin(label_angle_rad)
            
            # Add percentage text
            svg_parts.append(f'    <text x="{label_x}" y="{label_y}" text-anchor="middle" font-family="system-ui, sans-serif" font-size="12" font-weight="bold" fill="white">{percentage}%</text>')
        
        current_angle += segment_angle
    
    # Add legend
    legend_x = margin
    legend_y = height - margin - 20
    legend_item_height = 25
    
    svg_parts.append(f'    <text x="{legend_x}" y="{legend_y - 10}" font-family="system-ui, sans-serif" font-size="14" font-weight="bold" fill="#2c3e50">Installers:</text>')
    
    for i, (_, row) in enumerate(df.iterrows()):
        if i >= 10:  # Limit legend to first 10 items
            break
            
        installer_name = row['installer_name']
        download_count = row['download_count']
        percentage = row['percentage']
        
        color = colors[i % len(colors)]
        y_pos = legend_y + i * legend_item_height
        
        # Legend item
        svg_parts.append(f'    <rect x="{legend_x}" y="{y_pos - 8}" width="12" height="12" fill="{color}"/>')
        svg_parts.append(f'    <text x="{legend_x + 20}" y="{y_pos}" font-family="system-ui, sans-serif" font-size="11" fill="#2c3e50">{installer_name} ({percentage}% - {download_count:,})</text>')
    
    # Add total downloads info
    total_text = f"Total Downloads: {total_downloads:,}"
    svg_parts.append(f'    <text x="{width//2}" y="{height - 20}" text-anchor="middle" font-family="system-ui, sans-serif" font-size="14" font-weight="bold" fill="#2c3e50">{total_text}</text>')
    
    svg_parts.append('</svg>')
    
    return '\n'.join(svg_parts)


def create_svg_chart(rows, schema, job_name: str, project_name: str, output_dir: str = "output") -> str:
    """Create SVG chart from BigQuery results"""
    # Create project-specific directory
    project_output_dir = os.path.join(output_dir, project_name)
    os.makedirs(project_output_dir, exist_ok=True)
    
    # Generate filename (no timestamp for GitHub Actions)
    # Map job names to descriptive chart names
    chart_name_mapping = {
        "download_by_date": "download-trends",
        "download_by_date_all_versions": "version-comparison", 
        "download_by_date_version": "version-specific",
        "installer_stats_30d": "installer-stats-pie",
        "download_by_country_30d": "country-stats-pie"
    }
    
    # Get chart name from mapping or use job name
    chart_name = chart_name_mapping.get(job_name, job_name.replace("_", "-"))
    
    # Create filename: {chart-type}.svg (inside project directory)
    filename = f"{chart_name}.svg"
    filepath = os.path.join(project_output_dir, filename)
    
    if not rows:
        print(f"No data to create chart for job: {job_name}")
        return filepath
    
    # Get field names from schema
    field_names = [field.name for field in schema]
    
    # Convert to pandas DataFrame for easier plotting
    data = []
    for row in rows:
        row_data = {}
        for field_name in field_names:
            value = getattr(row, field_name)
            row_data[field_name] = value
        data.append(row_data)
    
    df = pd.DataFrame(data)
    
    # Determine chart type
    chart_type = 'version' if 'version' in df.columns else 'simple'
    
    # Generate SVG content
    svg_content = generate_svg_chart(df, chart_type, project_name, job_name)
    
    # Save SVG to file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(svg_content)
    
    print(f"SVG chart saved to: {filepath}")
    return filepath


def create_installer_pie_chart(rows, schema, project_name: str, output_dir: str = "output") -> str:
    """Create pie chart for installer statistics"""
    # Create project-specific directory
    project_output_dir = os.path.join(output_dir, project_name)
    os.makedirs(project_output_dir, exist_ok=True)
    
    # Create filename
    filename = "installer-stats-pie.svg"
    filepath = os.path.join(project_output_dir, filename)
    
    if not rows:
        print(f"No installer data to create pie chart for project: {project_name}")
        return filepath
    
    # Get field names from schema
    field_names = [field.name for field in schema]
    
    # Convert to pandas DataFrame for easier plotting
    data = []
    for row in rows:
        row_data = {}
        for field_name in field_names:
            value = getattr(row, field_name)
            row_data[field_name] = value
        data.append(row_data)
    
    df = pd.DataFrame(data)
    
    # Generate SVG pie chart
    svg_content = generate_pie_chart_svg(df, project_name)
    
    # Save SVG to file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(svg_content)
    
    print(f"Installer pie chart saved to: {filepath}")
    return filepath


def generate_country_pie_chart_svg(df, project_name: str) -> str:
    """Generate SVG pie chart for country statistics"""
    # Chart dimensions
    width = 800
    height = 500
    margin = 60
    
    # Colors for pie chart segments
    colors = [
        '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
        '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
        '#F8C471', '#82E0AA', '#F1948A', '#85C1E9', '#D7BDE2'
    ]
    
    # Calculate total downloads
    total_downloads = df['download_count'].sum()
    
    # Calculate pie chart parameters
    center_x = width // 2
    center_y = height // 2
    radius = min(width, height) // 3 - margin
    
    # Start building SVG
    svg_parts = []
    
    # SVG header
    svg_parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background-color: white; border: 1px solid #e9ecef; border-radius: 8px;">
    <defs>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="2" dy="2" stdDeviation="3" flood-color="#000000" flood-opacity="0.1"/>
        </filter>
    </defs>''')
    
    # Title
    svg_parts.append(f'    <text x="{width//2}" y="30" text-anchor="middle" font-family="system-ui, sans-serif" font-size="18" font-weight="bold" fill="#2c3e50">Recent 30 Days Download by Country - {project_name}</text>')
    
    # Calculate pie segments
    current_angle = 0
    for i, (_, row) in enumerate(df.iterrows()):
        country_code = row['country_code']
        download_count = row['download_count']
        percentage = row['percentage']
        
        # Calculate segment angle
        segment_angle = (download_count / total_downloads) * 360
        
        # Skip very small segments (less than 1%)
        if segment_angle < 3.6:  # 1% of 360 degrees
            continue
        
        # Calculate arc parameters
        start_angle_rad = math.radians(current_angle)
        end_angle_rad = math.radians(current_angle + segment_angle)
        
        # Calculate arc path
        x1 = center_x + radius * math.cos(start_angle_rad)
        y1 = center_y + radius * math.sin(start_angle_rad)
        x2 = center_x + radius * math.cos(end_angle_rad)
        y2 = center_y + radius * math.sin(end_angle_rad)
        
        # Determine if arc is large (more than 180 degrees)
        large_arc_flag = 1 if segment_angle > 180 else 0
        
        # Create arc path
        arc_path = f"M {center_x} {center_y} L {x1} {y1} A {radius} {radius} 0 {large_arc_flag} 1 {x2} {y2} Z"
        
        # Add pie segment
        color = colors[i % len(colors)]
        svg_parts.append(f'    <path d="{arc_path}" fill="{color}" filter="url(#shadow)"/>')
        
        # Add label if segment is large enough
        if segment_angle > 15:  # Only label segments larger than 15 degrees
            label_angle_rad = math.radians(current_angle + segment_angle / 2)
            label_radius = radius * 0.7
            label_x = center_x + label_radius * math.cos(label_angle_rad)
            label_y = center_y + label_radius * math.sin(label_angle_rad)
            
            # Add percentage text
            svg_parts.append(f'    <text x="{label_x}" y="{label_y}" text-anchor="middle" font-family="system-ui, sans-serif" font-size="12" font-weight="bold" fill="white">{percentage}%</text>')
        
        current_angle += segment_angle
    
    # Add legend
    legend_x = margin
    legend_y = height - margin - 20
    legend_item_height = 25
    
    svg_parts.append(f'    <text x="{legend_x}" y="{legend_y - 10}" font-family="system-ui, sans-serif" font-size="14" font-weight="bold" fill="#2c3e50">Countries:</text>')
    
    for i, (_, row) in enumerate(df.iterrows()):
        if i >= 10:  # Limit legend to first 10 items
            break
            
        country_code = row['country_code']
        download_count = row['download_count']
        percentage = row['percentage']
        
        color = colors[i % len(colors)]
        y_pos = legend_y + i * legend_item_height
        
        # Legend item
        svg_parts.append(f'    <rect x="{legend_x}" y="{y_pos - 8}" width="12" height="12" fill="{color}"/>')
        svg_parts.append(f'    <text x="{legend_x + 20}" y="{y_pos}" font-family="system-ui, sans-serif" font-size="11" fill="#2c3e50">{country_code} ({percentage}% - {download_count:,})</text>')
    
    # Add total downloads info
    total_text = f"Total Downloads: {total_downloads:,}"
    svg_parts.append(f'    <text x="{width//2}" y="{height - 20}" text-anchor="middle" font-family="system-ui, sans-serif" font-size="14" font-weight="bold" fill="#2c3e50">{total_text}</text>')
    
    svg_parts.append('</svg>')
    
    return '\n'.join(svg_parts)


def create_country_pie_chart(rows, schema, project_name: str, output_dir: str = "output") -> str:
    """Create pie chart for country statistics"""
    # Create project-specific directory
    project_output_dir = os.path.join(output_dir, project_name)
    os.makedirs(project_output_dir, exist_ok=True)
    
    # Create filename
    filename = "country-stats-pie.svg"
    filepath = os.path.join(project_output_dir, filename)
    
    if not rows:
        print(f"No country data to create pie chart for project: {project_name}")
        return filepath
    
    # Get field names from schema
    field_names = [field.name for field in schema]
    
    # Convert to pandas DataFrame for easier plotting
    data = []
    for row in rows:
        row_data = {}
        for field_name in field_names:
            value = getattr(row, field_name)
            row_data[field_name] = value
        data.append(row_data)
    
    df = pd.DataFrame(data)
    
    # Generate SVG pie chart
    svg_content = generate_country_pie_chart_svg(df, project_name)
    
    # Save SVG to file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(svg_content)
    
    print(f"Country pie chart saved to: {filepath}")
    return filepath


# Removed matplotlib-based chart functions - replaced with generate_svg_chart function above


def format_number(num):
    """Format number with appropriate suffixes (K, M, B)"""
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.1f}B"
    elif num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    else:
        return str(num)


def create_badge_svg(label: str, value: str, color: str = "#4c72b0", output_dir: str = "output", project_name: str = None) -> str:
    """Create SVG badge for download statistics"""
    # Create project-specific directory
    if project_name:
        project_output_dir = os.path.join(output_dir, project_name)
    else:
        project_output_dir = output_dir
    
    os.makedirs(project_output_dir, exist_ok=True)
    
    # Calculate text widths (approximate)
    label_width = len(label) * 6 + 10
    value_width = len(value) * 6 + 10
    total_width = label_width + value_width
    
    # Create SVG content
    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20">
    <defs>
        <linearGradient id="smooth" x2="0" y2="100%">
            <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
            <stop offset="1" stop-opacity=".1"/>
        </linearGradient>
        <clipPath id="round">
            <rect width="{total_width}" height="20" rx="3" fill="#fff"/>
        </clipPath>
    </defs>
    <g clip-path="url(#round)">
        <rect width="{label_width}" height="20" fill="#555"/>
        <rect x="{label_width}" width="{value_width}" height="20" fill="{color}"/>
        <rect width="{total_width}" height="20" fill="url(#smooth)"/>
    </g>
    <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
        <text x="{label_width//2}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
        <text x="{label_width//2}" y="14">{label}</text>
        <text x="{label_width + value_width//2}" y="15" fill="#010101" fill-opacity=".3">{value}</text>
        <text x="{label_width + value_width//2}" y="14">{value}</text>
    </g>
</svg>'''
    
    # Save badge
    badge_filename = f"{label.lower().replace(' ', '-')}-badge.svg"
    badge_filepath = os.path.join(project_output_dir, badge_filename)
    
    with open(badge_filepath, 'w', encoding='utf-8') as f:
        f.write(svg_content)
    
    print(f"Badge saved: {badge_filepath}")
    return badge_filepath


def save_total_downloads_badge(rows, schema, project_name: str, output_dir: str = "output") -> str:
    """Save total downloads count as a badge"""
    if not rows:
        print("No total downloads data to create badge")
        return ""
    
    # Get total downloads from first row (should only be one row)
    total_downloads = getattr(rows[0], 'total_downloads', 0)
    formatted_total = format_number(total_downloads)
    
    # Create badge
    badge_path = create_badge_svg(
        label="PyPI Downloads", 
        value=formatted_total, 
        color="#306998",  # Python blue
        output_dir=output_dir, 
        project_name=project_name
    )
    
    # Also save raw number for later use
    project_output_dir = os.path.join(output_dir, project_name) if project_name else output_dir
    total_downloads_file = os.path.join(project_output_dir, "total_downloads.txt")
    with open(total_downloads_file, 'w', encoding='utf-8') as f:
        f.write(str(total_downloads))
    
    return badge_path


def save_recent_30_days_badge(rows, schema, project_name: str, output_dir: str = "output") -> str:
    """Save recent 30 days downloads count as a badge"""
    if not rows:
        print("No recent 30 days downloads data to create badge")
        return ""
    
    # Get recent downloads from first row (should only be one row)
    recent_downloads = getattr(rows[0], 'recent_30_days_downloads', 0)
    formatted_recent = format_number(recent_downloads)
    
    # Create badge
    badge_path = create_badge_svg(
        label="Downloads (30d)", 
        value=formatted_recent, 
        color="#28a745",  # Green color for recent activity
        output_dir=output_dir, 
        project_name=project_name
    )
    
    # Also save raw number for later use
    project_output_dir = os.path.join(output_dir, project_name) if project_name else output_dir
    recent_downloads_file = os.path.join(project_output_dir, "recent_30_days_downloads.txt")
    with open(recent_downloads_file, 'w', encoding='utf-8') as f:
        f.write(str(recent_downloads))
    
    return badge_path


def generate_project_html(project_name: str, output_dir: str = "output", template_path: str = "templates/index.html") -> str:
    """Generate HTML page for a project with both CSV and SVG charts"""
    project_output_dir = os.path.join(output_dir, project_name)
    
    # Check if project directory exists
    if not os.path.exists(project_output_dir):
        print(f"Project directory does not exist: {project_output_dir}")
        return ""
    
    # Find CSV files in project directory
    csv_files = []
    svg_files = []
    if os.path.exists(project_output_dir):
        for file in os.listdir(project_output_dir):
            if file.endswith('.csv'):
                csv_files.append(file)
            elif file.endswith('.svg'):
                svg_files.append(file)
    
    # Read template
    template_content = ""
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
    else:
        # Create a simple default template
        template_content = create_default_csv_template()
    
    # Read JavaScript file
    js_script_path = "templates/chart_script.js"
    js_content = ""
    if os.path.exists(js_script_path):
        with open(js_script_path, 'r', encoding='utf-8') as f:
            js_content = f.read()
    
    # Replace template variables
    html_content = template_content.replace('{{PROJECT_NAME}}', project_name)
    html_content = html_content.replace('{{LAST_UPDATE}}', datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'))
    
    # Generate CSV files list for JavaScript
    csv_files_script = f"""
    <script>
        // Available CSV files for this project
        window.availableCsvFiles = {csv_files};
    </script>"""
    
    # Generate JavaScript code
    javascript_code = f"""
    <script>
        {js_content}
    </script>"""
    
    # Generate SVG chart sections
    svg_sections = generate_chart_sections(svg_files, project_name)
    
    html_content = html_content.replace('{{CSV_FILES_SCRIPT}}', csv_files_script)
    html_content = html_content.replace('{{JAVASCRIPT_CODE}}', javascript_code)
    html_content = html_content.replace('{{SVG_SECTIONS}}', svg_sections)
    
    # Save HTML file
    html_filepath = os.path.join(project_output_dir, 'index.html')
    with open(html_filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Generated HTML page: {html_filepath}")
    return html_filepath


def create_default_csv_template() -> str:
    """Create a default HTML template for CSV-based charts if none exists"""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{PROJECT_NAME}} - PyPI Download Statistics</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            color: #333;
        }
        .header {
            text-align: center;
            margin-bottom: 40px;
            padding: 40px 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
        }
        .chart-section {
            margin: 40px 0;
            padding: 30px;
            border: 1px solid #e1e5e9;
            border-radius: 10px;
            background: #f8f9fa;
            text-align: center;
        }
        .chart-container {
            position: relative;
            height: 400px;
            margin: 20px 0;
        }
        .svg-chart {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .chart-title {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 20px;
            color: #2c3e50;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📦 {{PROJECT_NAME}}</h1>
        <p>PyPI Download Statistics</p>
    </div>
    
    <!-- SVG Charts Section -->
    {{SVG_SECTIONS}}
    
    <!-- CSV-based Charts Section -->
    <div class="chart-section">
        <div class="chart-container">
            <canvas id="trendsChart"></canvas>
        </div>
    </div>
    {{CSV_FILES_SCRIPT}}
    {{JAVASCRIPT_CODE}}
</body>
</html>'''


def create_default_template() -> str:
    """Create a default HTML template if none exists"""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{PROJECT_NAME}} - PyPI Download Statistics</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            color: #333;
        }
        .header {
            text-align: center;
            margin-bottom: 40px;
            padding: 40px 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
        }
        .chart-section {
            margin: 40px 0;
            padding: 30px;
            border: 1px solid #e1e5e9;
            border-radius: 10px;
            background: #f8f9fa;
            text-align: center;
        }
        .chart-section img {
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 5px;
            background: white;
        }
        .chart-title {
            font-size: 1.5em;
            color: #2c3e50;
            margin-bottom: 20px;
        }
        .update-time {
            background: #e8f4f8;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 20px;
            text-align: center;
            color: #2c3e50;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📦 {{PROJECT_NAME}}</h1>
        <p>PyPI Download Statistics</p>
    </div>

    <div class="update-time">
        <strong>Last Updated:</strong> {{LAST_UPDATE}}
    </div>

    {{CHART_SECTIONS}}

    <div style="text-align: center; margin-top: 40px; color: #666;">
        <p>Generated by <a href="https://github.com/ringsaturn/pypi-downloads-chart">pypi-downloads-chart</a></p>
    </div>
</body>
</html>'''


def generate_chart_sections(svg_files: list, project_name: str) -> str:
    """Generate HTML sections for charts"""
    chart_descriptions = {
        "version-comparison.svg": "📊 Version Comparison", 
        "version-specific.svg": "🎯 Version Specific",
        "installer-stats-pie.svg": "🔧 Installer Statistics",
        "country-stats-pie.svg": "🌍 Download by Country"
    }
    
    # Define priority order for charts - Download Trends removed
    priority_order = [
        "version-comparison.svg", 
        "version-specific.svg",
        "installer-stats-pie.svg",
        "country-stats-pie.svg"
    ]
    
    # Sort files by priority, then alphabetically
    def sort_key(filename):
        if filename in priority_order:
            return (priority_order.index(filename), filename)
        return (len(priority_order), filename)
    
    sorted_files = sorted(svg_files, key=sort_key)
    
    sections = ""
    for svg_file in sorted_files:
        title = chart_descriptions.get(svg_file, svg_file.replace('.svg', '').replace('-', ' ').title())
        sections += f'''
    <div class="chart-section">
        <div class="chart-title">{title}</div>
        <img src="{svg_file}" alt="{title} for {project_name}" class="svg-chart">
    </div>'''
    
    return sections


def execute_bigquery_job(job_name: str, job_config: dict):
    """Execute BigQuery job"""
    print(f"Executing job: {job_name}")

    # Get SQL file path and variables
    sql_file = job_config["sql"]
    variables = job_config.get("vars", {})

    # Check if SQL file exists
    if not Path(sql_file).exists():
        print(f"Error: SQL file does not exist: {sql_file}")
        return

    # Load and process SQL
    processed_sql = load_and_process_sql(sql_file, variables)
    print("Processed SQL:")
    print(processed_sql)
    print("-" * 50)

    # Initialize BigQuery client
    try:
        client = bigquery.Client()
        print("BigQuery client connected successfully")

        # Execute query
        print("Starting query execution...")
        query_job = client.query(processed_sql)
        results = query_job.result()

        print(f"Query completed, total {results.total_rows} rows:")
        
        # Convert results to list for both display and CSV saving
        rows = list(results)
        
        # Get project name from variables
        project_name = variables.get("project_name", "unknown-package")
        
        # Save results to CSV (with timestamp for historical records)
        save_results_to_csv(rows, results.schema, job_name, project_name)
        
        # Handle different job types (extract job type from package_name.job_type format)
        job_type = job_name.split('.')[-1] if '.' in job_name else job_name
        if job_type == "total_downloads":
            # Create badge for total downloads
            save_total_downloads_badge(rows, results.schema, project_name)
        elif job_type == "recent_30_days_downloads":
            # Create badge for recent 30 days downloads
            save_recent_30_days_badge(rows, results.schema, project_name)
        elif job_type == "installer_stats_30d":
            # Create installer statistics pie chart
            create_installer_pie_chart(rows, results.schema, project_name)
        elif job_type == "download_by_country_30d":
            # Create country statistics pie chart
            create_country_pie_chart(rows, results.schema, project_name)
        else:
            # Create and save SVG chart (fixed filename for GitHub Actions)
            create_svg_chart(rows, results.schema, job_type, project_name)
        
        # Display results based on job type and schema
        if job_type == "total_downloads":
            print("Total Downloads Result:")
            total_downloads = getattr(rows[0], 'total_downloads', 0)
            formatted_total = format_number(total_downloads)
            print(f"Total Downloads: {total_downloads:,} ({formatted_total})")
        elif job_type == "recent_30_days_downloads":
            print("Recent 30 Days Downloads Result:")
            recent_downloads = getattr(rows[0], 'recent_30_days_downloads', 0)
            formatted_recent = format_number(recent_downloads)
            print(f"Recent 30 Days Downloads: {recent_downloads:,} ({formatted_recent})")
        elif job_type == "installer_stats_30d":
            print("Installer Statistics Result:")
            print(f"{'Installer':<20} {'Downloads':<12} {'Percentage':<10}")
            print("-" * 45)
            for row in rows:
                installer_name = getattr(row, 'installer_name', 'Unknown')
                download_count = getattr(row, 'download_count', 0)
                percentage = getattr(row, 'percentage', 0)
                print(f"{installer_name:<20} {download_count:<12,} {percentage:<10.2f}%")
        elif job_type == "download_by_country_30d":
            print("Country Statistics Result:")
            print(f"{'Country Code':<15} {'Downloads':<12} {'Percentage':<10}")
            print("-" * 40)
            for row in rows:
                country_code = getattr(row, 'country_code', 'Unknown')
                download_count = getattr(row, 'download_count', 0)
                percentage = getattr(row, 'percentage', 0)
                print(f"{country_code:<15} {download_count:<12,} {percentage:<10.2f}%")
        elif rows and 'version' in [field.name for field in results.schema]:
            print("Results (showing first 20 rows):")
            print(f"{'Date':<12} {'Version':<15} {'Downloads':<10}")
            print("-" * 40)
            for i, row in enumerate(rows):
                if i >= 20:  # Show first 20 rows
                    break
                print(f"{row.download_date.strftime('%Y-%m-%d'):<12} {row.version:<15} {row.daily_downloads:<10}")
            
            # Show summary by version if applicable
            if len(rows) > 1:
                version_totals = {}
                for row in rows:
                    version = row.version
                    downloads = row.daily_downloads
                    version_totals[version] = version_totals.get(version, 0) + downloads
                
                print("\nVersion Summary:")
                print(f"{'Version':<15} {'Total Downloads':<15}")
                print("-" * 30)
                for version, total in sorted(version_totals.items(), key=lambda x: x[1], reverse=True):
                    print(f"{version:<15} {total:<15}")
        else:
            print("Results (showing first 20 rows):")
            print(f"{'Date':<12} {'Downloads':<10}")
            print("-" * 25)
            for i, row in enumerate(rows):
                if i >= 20:  # Show first 20 rows
                    break
                print(f"{row.download_date.strftime('%Y-%m-%d'):<12} {row.daily_downloads:<10}")

        return results

    except Exception as e:
        print(f"BigQuery query failed: {e}")
        print("Please ensure:")
        print("1. Google Cloud SDK is installed and configured")
        print("2. Proper authentication is set up")
        print("3. You have access permissions to BigQuery")
        return None


def main():
    """Main function"""
    # Load job configuration
    with open("jobs.toml", "rb") as f:
        config = tomllib.load(f)

    jobs = config.get("jobs", {})
    
    # Parse nested structure: jobs.{package_name}.{job_type}
    flat_jobs = {}
    for package_name, package_jobs in jobs.items():
        if isinstance(package_jobs, dict):
            for job_type, job_config in package_jobs.items():
                # Create unique job name: package_name.job_type
                job_name = f"{package_name}.{job_type}"
                flat_jobs[job_name] = job_config
    
    print(f"Found {len(flat_jobs)} jobs:")
    for job_name in flat_jobs.keys():
        print(f"  - {job_name}")

    print("=" * 50)

    # Execute all jobs
    processed_projects = set()
    for job_name, job_config in flat_jobs.items():
        execute_bigquery_job(job_name, job_config)
        
        # Track projects for HTML generation
        variables = job_config.get("vars", {})
        project_name = variables.get("project_name", "unknown-package")
        processed_projects.add(project_name)
        
        print("=" * 50)
    
    # Generate HTML pages for each project
    print("🌐 Generating HTML pages...")
    for project_name in processed_projects:
        generate_project_html(project_name)
    
    # Generate project index page
    print("📝 Generating project index page...")
    from generate_index import generate_project_index
    generate_project_index()
    
    print("✅ HTML generation completed!")


if __name__ == "__main__":
    main()
