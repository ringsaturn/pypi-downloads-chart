import csv
import os
import tomllib
from datetime import datetime
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
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate filename with timestamp for historical records
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if project_name:
        filename = f"{project_name}-{job_name}_{timestamp}.csv"
    else:
        filename = f"{job_name}_{timestamp}.csv"
    filepath = os.path.join(output_dir, filename)
    
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
    
    print(f"Results saved to: {filepath}")
    return filepath


def create_svg_chart(rows, schema, job_name: str, project_name: str, output_dir: str = "output") -> str:
    """Create SVG chart from BigQuery results"""
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate filename with project name (no timestamp for GitHub Actions)
    # Map job names to descriptive chart names
    chart_name_mapping = {
        "download_by_date": "download-trends",
        "download_by_date_all_versions": "version-comparison", 
        "download_by_date_summary": "download-summary",
        "download_by_date_version": "version-specific"
    }
    
    # Get chart name from mapping or use job name
    chart_name = chart_name_mapping.get(job_name, job_name.replace("_", "-"))
    
    # Create filename: {project-name}-{chart-type}.svg
    filename = f"{project_name}-{chart_name}.svg"
    filepath = os.path.join(output_dir, filename)
    
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
    elif 'versions_count' in df.columns:
        # Summary chart with version count
        create_summary_chart(df, ax, job_name, project_name)
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


def create_summary_chart(df, ax, job_name: str, project_name: str):
    """Create chart for summary data with version count"""
    df_sorted = df.sort_values('download_date')
    
    # Create primary y-axis for downloads
    ax.bar(df_sorted['download_date'], df_sorted['daily_downloads'], 
           alpha=0.7, color='skyblue', label='Daily Downloads')
    ax.set_ylabel('Daily Downloads', fontsize=12, color='blue')
    ax.tick_params(axis='y', labelcolor='blue')
    
    # Create secondary y-axis for version count
    ax2 = ax.twinx()
    ax2.plot(df_sorted['download_date'], df_sorted['versions_count'], 
             color='red', marker='o', linewidth=2, markersize=4, label='Version Count')
    ax2.set_ylabel('Number of Versions', fontsize=12, color='red')
    ax2.tick_params(axis='y', labelcolor='red')
    
    ax.set_title(f'{project_name} - Daily Downloads & Version Count', fontsize=14, fontweight='bold')
    ax.set_xlabel('Date', fontsize=12)
    ax.grid(True, alpha=0.3)
    
    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(df['download_date'].unique()) // 10)))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    
    # Add legends
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left')


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
        
        # Create and save SVG chart (fixed filename for GitHub Actions)
        create_svg_chart(rows, results.schema, job_name, project_name)
        
        # Display results based on whether version info is included
        if rows and 'version' in [field.name for field in results.schema]:
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
            # Check if this is the summary query with version count
            if rows and hasattr(rows[0], 'versions_count'):
                print(f"{'Date':<12} {'Downloads':<10} {'Versions':<10}")
                print("-" * 35)
                for i, row in enumerate(rows):
                    if i >= 20:  # Show first 20 rows
                        break
                    print(f"{row.download_date.strftime('%Y-%m-%d'):<12} {row.daily_downloads:<10} {row.versions_count:<10}")
            else:
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
    print(f"Found {len(jobs)} jobs:")
    for job_name in jobs.keys():
        print(f"  - {job_name}")

    print("=" * 50)

    # Execute all jobs
    for job_name, job_config in jobs.items():
        execute_bigquery_job(job_name, job_config)
        print("=" * 50)


if __name__ == "__main__":
    main()
