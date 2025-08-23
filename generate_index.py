#!/usr/bin/env python3
"""
生成根目录的项目索引页面
"""

import os
import tomllib
from datetime import datetime, timezone
from pathlib import Path


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


def read_total_downloads(project_path):
    """Read total downloads from project directory"""
    total_downloads_file = os.path.join(project_path, 'total_downloads.txt')
    if os.path.exists(total_downloads_file):
        try:
            with open(total_downloads_file, 'r') as f:
                return int(f.read().strip())
        except (ValueError, IOError):
            pass
    return None


def read_recent_30_days_downloads(project_path):
    """Read recent 30 days downloads from project directory"""
    recent_downloads_file = os.path.join(project_path, 'recent_30_days_downloads.txt')
    if os.path.exists(recent_downloads_file):
        try:
            with open(recent_downloads_file, 'r') as f:
                return int(f.read().strip())
        except (ValueError, IOError):
            pass
    return None


def generate_project_index(output_dir="output", pages_dir="output"):
    """Generate index page with project links"""
    
    # Find all project directories
    projects = []
    if os.path.exists(output_dir):
        for item in os.listdir(output_dir):
            project_path = os.path.join(output_dir, item)
            if os.path.isdir(project_path):
                # Check if directory has SVG files (indicating it's a project)
                svg_files = [f for f in os.listdir(project_path) if f.endswith('.svg')]
                if svg_files:
                    total_downloads = read_total_downloads(project_path)
                    recent_downloads = read_recent_30_days_downloads(project_path)
                    projects.append({
                        'name': item,
                        'chart_count': len(svg_files),
                        'has_html': os.path.exists(os.path.join(project_path, 'index.html')),
                        'total_downloads': total_downloads,
                        'recent_30_days_downloads': recent_downloads,
                        'has_badge': os.path.exists(os.path.join(project_path, 'pypi-downloads-badge.svg')),
                        'has_recent_badge': os.path.exists(os.path.join(project_path, 'downloads-(30d)-badge.svg'))
                    })
    
    # Also check jobs.toml for project info
    project_descriptions = {}
    try:
        with open("jobs.toml", "rb") as f:
            config = tomllib.load(f)
            jobs = config.get("jobs", {})
            
            # Parse nested structure: jobs.{package_name}.{job_type}
            for package_name, package_jobs in jobs.items():
                if isinstance(package_jobs, dict):
                    for job_type, job_config in package_jobs.items():
                        variables = job_config.get("vars", {})
                        project_name = variables.get("project_name")
                        if project_name and project_name not in project_descriptions:
                            project_descriptions[project_name] = {
                                'description': f'PyPI package analytics for {project_name}',
                                'time_range': variables.get('time_range', 45)
                            }
    except Exception as e:
        print(f"Warning: Could not read jobs.toml: {e}")
    
    # Generate HTML content
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PyPI Download Charts</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            color: #333;
            background: #f8f9fa;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 40px;
            padding: 40px 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        
        .header p {{
            margin: 10px 0 0 0;
            font-size: 1.2em;
            opacity: 0.9;
        }}
        
        .project-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 40px 0;
        }}
        
        .project-card {{
            background: white;
            border: 1px solid #e1e5e9;
            border-radius: 10px;
            padding: 25px;
            transition: transform 0.2s, box-shadow 0.2s;
            text-decoration: none;
            color: inherit;
        }}
        
        .project-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
            text-decoration: none;
            color: inherit;
        }}
        
        .project-name {{
            font-size: 1.4em;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        
        .project-description {{
            color: #666;
            margin-bottom: 15px;
            font-size: 0.95em;
        }}
        
        .project-stats {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.9em;
            color: #888;
            margin-bottom: 15px;
        }}
        
        .chart-count {{
            background: #e3f2fd;
            color: #1976d2;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: bold;
        }}
        
        .total-downloads {{
            background: #f3e5f5;
            color: #7b1fa2;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 0.95em;
            font-weight: bold;
            text-align: center;
            margin-bottom: 10px;
        }}
        
        .download-badge {{
            text-align: center;
            margin-bottom: 15px;
        }}
        
        .download-badge img {{
            max-height: 20px;
            border-radius: 3px;
        }}
        
        .update-time {{
            background: #e8f4f8;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            color: #2c3e50;
            margin-bottom: 30px;
        }}
        
        .footer {{
            text-align: center;
            margin-top: 50px;
            padding: 30px 0;
            color: #666;
            border-top: 1px solid #e1e5e9;
        }}
        
        .footer a {{
            color: #3498db;
            text-decoration: none;
        }}
        
        .footer a:hover {{
            text-decoration: underline;
        }}
        
        .empty-state {{
            text-align: center;
            padding: 60px 20px;
            color: #666;
        }}
        
        .empty-state h2 {{
            color: #999;
            font-weight: normal;
        }}
        
        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 2em;
            }}
            
            .project-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 PyPI Download Charts</h1>
        <p>Python package download analytics and trends</p>
    </div>

    <div class="update-time">
        <strong>Last Updated:</strong> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
    </div>
'''

    if projects:
        html_content += '    <div class="project-grid">\n'
        
        for project in sorted(projects, key=lambda x: x['name']):
            name = project['name']
            chart_count = project['chart_count']
            total_downloads = project['total_downloads']
            recent_downloads = project['recent_30_days_downloads']
            has_badge = project['has_badge']
            has_recent_badge = project['has_recent_badge']
            description = project_descriptions.get(name, {}).get('description', f'Download statistics for {name}')
            time_range = project_descriptions.get(name, {}).get('time_range', 45)
            
            # Generate downloads display
            downloads_display = ""
            badge_display = ""
            
            if total_downloads is not None:
                formatted_downloads = format_number(total_downloads)
                downloads_display += f'''
            <div class="total-downloads">
                📥 Total Downloads: {total_downloads:,} ({formatted_downloads})
            </div>'''
            
            if recent_downloads is not None:
                formatted_recent = format_number(recent_downloads)
                downloads_display += f'''
            <div class="total-downloads" style="background: #e8f5e8; color: #2e7d32;">
                📊 Recent 30 Days: {recent_downloads:,} ({formatted_recent})
            </div>'''
            
            if has_badge:
                badge_display += f'''
            <div class="download-badge">
                <img src="{name}/pypi-downloads-badge.svg" alt="Total Download Badge for {name}">
            </div>'''
            
            if has_recent_badge:
                badge_display += f'''
            <div class="download-badge">
                <img src="{name}/downloads-(30d)-badge.svg" alt="30-Day Download Badge for {name}">
            </div>'''
            
            html_content += f'''        <a href="{name}/index.html" class="project-card">
            <div class="project-name">📦 {name}</div>
            <div class="project-description">{description}</div>{downloads_display}{badge_display}
            <div class="project-stats">
                <span>Last {time_range} days</span>
                <span class="chart-count">{chart_count} charts</span>
            </div>
        </a>
'''
        
        html_content += '    </div>\n'
    else:
        html_content += '''    <div class="empty-state">
        <h2>🔍 No projects found</h2>
        <p>Run the chart generation script to create project statistics.</p>
        <p>Make sure you have configured <code>jobs.toml</code> with your package information.</p>
    </div>
'''

    html_content += f'''
    <div class="footer">
        <p>
            📊 Generated by 
            <a href="https://github.com/ringsaturn/pypi-downloads-chart" target="_blank">
                pypi-downloads-chart
            </a>
        </p>
        <p>
            📦 Data source: 
            <a href="https://console.cloud.google.com/bigquery?p=bigquery-public-data&d=pypi&page=dataset" target="_blank">
                PyPI BigQuery Dataset
            </a>
        </p>
        <p><small>Found {len(projects)} project(s) • Updates automatically via GitHub Actions</small></p>
    </div>
</body>
</html>'''

    # Ensure pages directory exists
    os.makedirs(pages_dir, exist_ok=True)
    
    # Write index.html
    index_path = os.path.join(pages_dir, 'index.html')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"📝 Generated project index: {index_path}")
    print(f"📊 Found {len(projects)} projects: {', '.join([p['name'] for p in projects])}")
    
    return index_path


def main():
    """Main function"""
    print("🚀 Generating project index page...")
    generate_project_index()
    print("✅ Index generation completed!")


if __name__ == "__main__":
    main()
