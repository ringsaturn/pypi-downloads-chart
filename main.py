import csv
import os
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
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
    
    # Generate filename with timestamp for historical records
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{job_name}_{timestamp}.csv"
    filepath = os.path.join(project_output_dir, filename)
    
    # Also create a "latest" symlink for easy access
    latest_filename = f"{job_name}_latest.csv"
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
        "download_by_date_version": "version-specific"
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
    
    # Set up matplotlib for SVG output
    plt.style.use('default')
    fig, ax = plt.subplots(figsize=(12, 6), dpi=100)
    
    # Configure matplotlib to use Agg backend for SVG
    plt.switch_backend('Agg')
    
    # Check what type of chart to create based on available columns
    if 'version' in df.columns:
        # Multi-version chart
        create_version_chart(df, ax, job_name, project_name)
    else:
        # Simple download chart
        create_simple_chart(df, ax, job_name, project_name)
    
    # Save as SVG
    plt.tight_layout()
    plt.savefig(filepath, format='svg', bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close(fig)
    
    print(f"SVG chart saved to: {filepath}")
    return filepath


def create_version_chart(df, ax, job_name: str, project_name: str):
    """Create chart for version-specific data"""
    # Group by version and plot separate lines
    versions = df['version'].unique()
    colors = plt.cm.Set1(range(len(versions)))
    
    for i, version in enumerate(sorted(versions)):
        version_data = df[df['version'] == version].copy()
        version_data = version_data.sort_values('download_date')
        
        ax.plot(version_data['download_date'], version_data['daily_downloads'], 
                marker='o', linewidth=2, markersize=4, 
                label=f'v{version}', color=colors[i])
    
    ax.set_title(f'{project_name} - Daily Downloads by Version', fontsize=14, fontweight='bold')
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Daily Downloads', fontsize=12)
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.grid(True, alpha=0.3)
    
    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(df['download_date'].unique()) // 10)))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)



def create_simple_chart(df, ax, job_name: str, project_name: str):
    """Create simple download chart"""
    df_sorted = df.sort_values('download_date')
    
    ax.plot(df_sorted['download_date'], df_sorted['daily_downloads'], 
            marker='o', linewidth=2, markersize=4, color='blue')
    ax.fill_between(df_sorted['download_date'], df_sorted['daily_downloads'], 
                    alpha=0.3, color='lightblue')
    
    ax.set_title(f'{project_name} - Daily Downloads', fontsize=14, fontweight='bold')
    ax.set_xlabel('Date', fontsize=12)
    ax.set_ylabel('Daily Downloads', fontsize=12)
    ax.grid(True, alpha=0.3)
    
    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(df['download_date'].unique()) // 10)))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)


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


def generate_project_html(project_name: str, output_dir: str = "output", template_path: str = "templates/index.html") -> str:
    """Generate HTML page for a project using new CSV-based template"""
    project_output_dir = os.path.join(output_dir, project_name)
    
    # Check if project directory exists
    if not os.path.exists(project_output_dir):
        print(f"Project directory does not exist: {project_output_dir}")
        return ""
    
    # Find CSV files in project directory
    csv_files = []
    if os.path.exists(project_output_dir):
        for file in os.listdir(project_output_dir):
            if file.endswith('.csv'):
                csv_files.append(file)
    
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
    
    html_content = html_content.replace('{{CSV_FILES_SCRIPT}}', csv_files_script)
    html_content = html_content.replace('{{JAVASCRIPT_CODE}}', javascript_code)
    
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
    </style>
</head>
<body>
    <div class="header">
        <h1>📦 {{PROJECT_NAME}}</h1>
        <p>PyPI Download Statistics</p>
    </div>
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
        "download-trends.svg": "📈 Download Trends",
        "version-comparison.svg": "📊 Version Comparison", 
        "version-specific.svg": "🎯 Version Specific"
    }
    
    # Define priority order for charts - Download Trends first
    priority_order = [
        "download-trends.svg",
        "version-comparison.svg", 
        "version-specific.svg"
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
        <img src="{svg_file}" alt="{title} for {project_name}">
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
        else:
            # Create and save SVG chart (fixed filename for GitHub Actions)
            create_svg_chart(rows, results.schema, job_type, project_name)
        
        # Display results based on job type and schema
        if job_type == "total_downloads":
            print("Total Downloads Result:")
            total_downloads = getattr(rows[0], 'total_downloads', 0)
            formatted_total = format_number(total_downloads)
            print(f"Total Downloads: {total_downloads:,} ({formatted_total})")
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
