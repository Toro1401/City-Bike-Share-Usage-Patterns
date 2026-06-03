"""
run_analysis.py — Execute SQL queries against DuckDB and generate charts.

Reads from citibike.duckdb, runs all analytical queries,
exports results as CSVs and generates publication-quality charts.
"""

import duckdb
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import seaborn as sns
import numpy as np
import os
import time

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '..', 'citibike.duckdb')
RESULTS_DIR = os.path.join(BASE_DIR, 'results')
CHARTS_DIR = os.path.join(BASE_DIR, 'charts')

# Ensure output dirs
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)

# ── Chart Style ──────────────────────────────────────────────────────────────
DARK_BG = '#0f172a'
DARK_CARD = '#1e293b'
DARK_TEXT = '#e2e8f0'
DARK_GRID = '#1e293b'
ACCENT_BLUE = '#3b82f6'
ACCENT_PURPLE = '#8b5cf6'
ACCENT_GREEN = '#10b981'
ACCENT_ORANGE = '#f59e0b'
ACCENT_RED = '#ef4444'
ACCENT_CYAN = '#06b6d4'
GREY_BARS = '#334155'
GREY_TEXT = '#94a3b8'

CATEGORICAL_COLORS = [ACCENT_BLUE, ACCENT_ORANGE, ACCENT_GREEN, ACCENT_PURPLE, ACCENT_RED, ACCENT_CYAN]

plt.rcParams.update({
    'figure.facecolor': DARK_BG,
    'axes.facecolor': DARK_BG,
    'axes.edgecolor': '#334155',
    'axes.labelcolor': DARK_TEXT,
    'text.color': DARK_TEXT,
    'xtick.color': GREY_TEXT,
    'ytick.color': GREY_TEXT,
    'grid.color': DARK_GRID,
    'font.family': 'sans-serif',
    'font.size': 12,
    'axes.titlesize': 15,
    'axes.labelsize': 12,
})


def save_chart(fig, name):
    path = os.path.join(CHARTS_DIR, f"{name}.png")
    fig.savefig(path, dpi=150, facecolor=DARK_BG, bbox_inches='tight', pad_inches=0.3)
    plt.close(fig)
    print(f"  Chart saved: {name}.png")


def run_query(con, name, sql):
    """Run SQL query, save as CSV, return DataFrame."""
    df = con.execute(sql).fetchdf()
    csv_path = os.path.join(RESULTS_DIR, f"{name}.csv")
    df.to_csv(csv_path, index=False)
    print(f"  Result saved: {name}.csv ({len(df)} rows)")
    return df


def main():
    start = time.time()
    print("=" * 60)
    print("City Bike-Share Usage Patterns — Analysis")
    print("=" * 60)

    con = duckdb.connect(DB_PATH, read_only=True)

    # ── 1. PEAK USAGE TIMES ──────────────────────────────────────────────
    print("\n1. Peak Usage Times")
    print("-" * 40)

    # 1a. Trips by hour
    df_hourly = run_query(con, '1a_trips_by_hour', """
        SELECT
            EXTRACT(HOUR FROM started_at) AS hour_of_day,
            COUNT(*) AS trip_count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_total
        FROM trips
        WHERE duration_sec BETWEEN 60 AND 86400
        GROUP BY hour_of_day
        ORDER BY hour_of_day
    """)

    # Chart: Hourly distribution
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Highlight peak morning and evening commute hours
    colors = [GREY_BARS] * 24
    colors[8] = ACCENT_BLUE      # 8 AM Peak
    colors[18] = ACCENT_ORANGE   # 6 PM Peak
    
    bars = ax.bar(df_hourly['hour_of_day'], df_hourly['trip_count'],
                  color=colors, width=0.7, alpha=0.9)

    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Total Trips')
    ax.set_title('Commuter demand peaks twice daily: 8 AM morning commute and 6 PM evening rush',
                 fontweight='bold')
    ax.set_xticks(range(24))
    ax.set_xticklabels([f'{h}:00' for h in range(24)], rotation=45, ha='right', fontsize=9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.1, linestyle=':')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000:.0f}K'))
    ax.set_ylim(0, max(df_hourly['trip_count']) * 1.15)
    
    # Annotate peak values
    val_8am = df_hourly.loc[df_hourly['hour_of_day'] == 8, 'trip_count'].values[0]
    val_6pm = df_hourly.loc[df_hourly['hour_of_day'] == 18, 'trip_count'].values[0]
    ax.text(8, val_8am + 15000, f'Morning Peak\n{val_8am/1000:.0f}K', ha='center', va='bottom', fontsize=10, color=ACCENT_BLUE, fontweight='bold')
    ax.text(18, val_6pm + 15000, f'Evening Peak\n{val_6pm/1000:.0f}K', ha='center', va='bottom', fontsize=10, color=ACCENT_ORANGE, fontweight='bold')
    
    save_chart(fig, '1a_hourly_distribution')

    # 1b. Weekday vs Weekend by hour
    df_daytype = run_query(con, '1b_weekday_vs_weekend', """
        SELECT
            EXTRACT(HOUR FROM started_at) AS hour_of_day,
            CASE WHEN EXTRACT(DOW FROM started_at) IN (0, 6) THEN 'weekend' ELSE 'weekday' END AS day_type,
            COUNT(*) AS trip_count
        FROM trips
        WHERE duration_sec BETWEEN 60 AND 86400
        GROUP BY hour_of_day, day_type
        ORDER BY day_type, hour_of_day
    """)

    fig, ax = plt.subplots(figsize=(14, 6))
    for dtype, color, ls, lw in [('weekday', ACCENT_BLUE, '-', 3.0), ('weekend', GREY_TEXT, '--', 2.0)]:
        mask = df_daytype['day_type'] == dtype
        ax.plot(df_daytype.loc[mask, 'hour_of_day'], df_daytype.loc[mask, 'trip_count'],
                color=color, linewidth=lw, linestyle=ls, marker='o', markersize=4)
    ax.fill_between(df_daytype.loc[df_daytype['day_type'] == 'weekday', 'hour_of_day'],
                    df_daytype.loc[df_daytype['day_type'] == 'weekday', 'trip_count'],
                    alpha=0.12, color=ACCENT_BLUE)
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Total Trips')
    ax.set_title('Weekday commute peaks vs. flat weekend midday leisure rides', fontweight='bold')
    ax.set_xticks(range(24))
    ax.set_xticklabels([f'{h}:00' for h in range(24)], rotation=45, ha='right', fontsize=9)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.1, linestyle=':')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000:.0f}K'))
    
    # Direct labels next to lines at the end
    ax.set_xlim(-0.5, 25.5)
    y_wd = df_daytype.loc[(df_daytype['day_type'] == 'weekday') & (df_daytype['hour_of_day'] == 23), 'trip_count'].values[0]
    y_we = df_daytype.loc[(df_daytype['day_type'] == 'weekend') & (df_daytype['hour_of_day'] == 23), 'trip_count'].values[0]
    ax.text(23.2, y_wd, ' Weekday', color=ACCENT_BLUE, fontweight='bold', va='center', fontsize=11)
    ax.text(23.2, y_we, ' Weekend', color=GREY_TEXT, fontweight='bold', va='center', fontsize=11)
    

                
    save_chart(fig, '1b_weekday_vs_weekend')

    # 1c. Day of week
    df_dow = run_query(con, '1c_trips_by_day', """
        SELECT
            EXTRACT(DOW FROM started_at) AS day_of_week,
            CASE EXTRACT(DOW FROM started_at)
                WHEN 0 THEN 'Sun' WHEN 1 THEN 'Mon' WHEN 2 THEN 'Tue'
                WHEN 3 THEN 'Wed' WHEN 4 THEN 'Thu' WHEN 5 THEN 'Fri' WHEN 6 THEN 'Sat'
            END AS day_name,
            COUNT(*) AS trip_count
        FROM trips WHERE duration_sec BETWEEN 60 AND 86400
        GROUP BY day_of_week, day_name ORDER BY day_of_week
    """)

    fig, ax = plt.subplots(figsize=(10, 6))
    # Highlight Wednesday peak, weekdays in blue, weekends in grey
    colors = [GREY_BARS] * 7
    for d in df_dow['day_of_week']:
        if d == 3: # Wednesday
            colors[d] = ACCENT_ORANGE
        elif d not in (0, 6): # Weekdays
            colors[d] = ACCENT_BLUE
            
    ax.bar(df_dow['day_name'], df_dow['trip_count'], color=colors, width=0.6)
    ax.set_ylabel('Total Trips')
    ax.set_title('Midweek days (Wed–Fri) drive maximum weekly ridership', fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.1, linestyle=':')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000:.0f}K'))
    ax.set_ylim(0, max(df_dow['trip_count']) * 1.15)
    # Add value labels
    for bar, val, day in zip(ax.patches, df_dow['trip_count'], df_dow['day_of_week']):
        text_color = ACCENT_ORANGE if day == 3 else (ACCENT_BLUE if day not in (0,6) else GREY_TEXT)
        font_wt = 'bold' if day == 3 else 'normal'
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 15000,
                f'{val/1000:.0f}K', ha='center', va='bottom', fontsize=9.5, fontweight=font_wt, color=text_color)
    save_chart(fig, '1c_day_of_week')

    # 1d. Monthly seasonal
    df_monthly = run_query(con, '1d_trips_by_month', """
        SELECT
            EXTRACT(MONTH FROM started_at) AS month_num,
            CASE EXTRACT(MONTH FROM started_at)
                WHEN 1 THEN 'Jan' WHEN 2 THEN 'Feb' WHEN 3 THEN 'Mar'
                WHEN 4 THEN 'Apr' WHEN 5 THEN 'May' WHEN 6 THEN 'Jun'
                WHEN 7 THEN 'Jul' WHEN 8 THEN 'Aug' WHEN 9 THEN 'Sep'
                WHEN 10 THEN 'Oct' WHEN 11 THEN 'Nov' WHEN 12 THEN 'Dec'
            END AS month_name,
            COUNT(*) AS trip_count,
            ROUND(AVG(duration_sec) / 60.0, 1) AS avg_duration_min
        FROM trips WHERE duration_sec BETWEEN 60 AND 86400
        GROUP BY month_num, month_name ORDER BY month_num
    """)

    # Two-panel subplot (1 column, 2 rows) to avoid dual Y-axis
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    # Panel 1: Trips by Month
    # Highlight Jun-Sep in blue, others grey
    trip_colors = [ACCENT_BLUE if m in (6, 7, 8, 9) else GREY_BARS for m in df_monthly['month_num']]
    ax1.bar(df_monthly['month_name'], df_monthly['trip_count'], color=trip_colors, width=0.6)
    ax1.set_ylabel('Total Trips')
    ax1.set_title('Summer ridership surges, but average trip duration peaks in spring', fontweight='bold', pad=15)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.grid(axis='y', alpha=0.1, linestyle=':')
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000:.0f}K'))
    
    # Annotate peak trips in September
    val_sep = df_monthly.loc[df_monthly['month_num'] == 9, 'trip_count'].values[0]
    ax1.text(8, val_sep + 15000, f'September Peak\n{val_sep/1000:.0f}K', ha='center', va='bottom', fontsize=10, color=ACCENT_BLUE, fontweight='bold')
    
    # Panel 2: Duration by Month
    ax2.plot(df_monthly['month_name'], df_monthly['avg_duration_min'],
             color=ACCENT_ORANGE, linewidth=2.5, marker='s', markersize=6)
    ax2.set_ylabel('Avg Duration (min)')
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.grid(axis='y', alpha=0.1, linestyle=':')
    

                
    plt.tight_layout()
    save_chart(fig, '1d_seasonal_pattern')

    # 1e. Year-over-year
    df_yoy = run_query(con, '1e_year_over_year', """
        SELECT
            EXTRACT(YEAR FROM started_at) AS year,
            COUNT(*) AS trip_count,
            ROUND(AVG(duration_sec) / 60.0, 1) AS avg_duration_min,
            COUNT(DISTINCT start_station_name) AS active_stations,
            ROUND(SUM(CASE WHEN user_type = 'member' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS member_pct
        FROM trips WHERE duration_sec BETWEEN 60 AND 86400
        GROUP BY year ORDER BY year
    """)

    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Generate sequential color gradient for growth
    import matplotlib.cm as cm
    bar_colors = cm.Blues(np.linspace(0.4, 0.95, len(df_yoy)))
    # Highlight 2026 as partial/grey
    for idx, r in enumerate(df_yoy.itertuples()):
        if r.year == 2026:
            bar_colors[idx] = [0.2, 0.25, 0.35, 1.0] # Slate grey
            
    ax.bar(df_yoy['year'].astype(int).astype(str), df_yoy['trip_count'],
           color=bar_colors, width=0.6, alpha=0.9)
    ax.set_ylabel('Total Trips')
    ax.set_title('System ridership more than doubled between 2020 and 2024', fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.1, linestyle=':')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000:.0f}K'))
    ax.set_ylim(0, max(df_yoy['trip_count']) * 1.15)
    for idx, (bar, val, yr) in enumerate(zip(ax.patches, df_yoy['trip_count'], df_yoy['year'])):
        if yr == 2026:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 15000,
                    '210K\n(Jan-Apr)', ha='center', va='bottom', fontsize=8.5, color=GREY_TEXT)
        else:
            text_color = ACCENT_BLUE if yr == 2024 else DARK_TEXT
            font_wt = 'bold' if yr == 2024 else 'normal'
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 15000,
                    f'{val/1000:.0f}K', ha='center', va='bottom', fontsize=9, fontweight=font_wt, color=text_color)
            

                
    save_chart(fig, '1e_year_over_year')

    # 1f. Heatmap (Day × Hour)
    df_heatmap = run_query(con, '1f_hourly_heatmap', """
        SELECT
            EXTRACT(DOW FROM started_at) AS day_of_week,
            EXTRACT(HOUR FROM started_at) AS hour_of_day,
            COUNT(*) AS trip_count
        FROM trips WHERE duration_sec BETWEEN 60 AND 86400
        GROUP BY day_of_week, hour_of_day
        ORDER BY day_of_week, hour_of_day
    """)

    pivot = df_heatmap.pivot(index='day_of_week', columns='hour_of_day', values='trip_count').fillna(0)
    day_labels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    hour_labels = [f'{h}:00' for h in range(24)]

    fig, ax = plt.subplots(figsize=(16, 6))
    # Use mako colormap which starts dark and goes bright (perfect for dark background)
    sns.heatmap(pivot, annot=False, fmt='.0f', cmap='mako',
                xticklabels=hour_labels, yticklabels=day_labels,
                linewidths=0.5, linecolor=DARK_BG, ax=ax,
                cbar_kws={'label': 'Trip Count'})
    ax.set_title('Weekday evening commute (5:00-6:00 PM) is the busiest period', fontweight='bold', pad=15)
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('')
    plt.xticks(rotation=45, ha='right', fontsize=9)
    plt.yticks(rotation=0) # Make day names horizontal
    # Remove outer spines around heatmap
    for spine in ax.spines.values():
        spine.set_visible(False)
    save_chart(fig, '1f_heatmap')

    # ── 2. POPULAR ROUTES ────────────────────────────────────────────────
    print("\n2. Popular Routes")
    print("-" * 40)

    df_routes = run_query(con, '2a_top_routes', """
        SELECT
            start_station_name,
            end_station_name,
            COUNT(*) AS trip_count,
            ROUND(AVG(duration_sec) / 60.0, 1) AS avg_duration_min
        FROM trips
        WHERE duration_sec BETWEEN 60 AND 86400
          AND start_station_name IS NOT NULL AND end_station_name IS NOT NULL
        GROUP BY start_station_name, end_station_name
        ORDER BY trip_count DESC
        LIMIT 20
    """)

    fig, ax = plt.subplots(figsize=(14, 8))
    labels = [f"{r['start_station_name'][:20]} → {r['end_station_name'][:20]}" for _, r in df_routes.iterrows()]
    labels.reverse()
    values = df_routes['trip_count'].values[::-1]
    
    # Highlight top route only
    colors = [GREY_BARS] * len(values)
    colors[-1] = ACCENT_BLUE  # #1 route Hamilton Park to Grove St PATH
    
    ax.barh(range(len(labels)), values, color=colors, height=0.6)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9.5)
    ax.set_xlabel('Total Trips')
    ax.set_title('Hamilton Park to Grove St PATH is the highest-demand commute corridor', fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='x', alpha=0.1, linestyle=':')
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000:.0f}K'))
    for i, v in enumerate(values):
        is_top = (i == len(values) - 1)
        text_color = ACCENT_BLUE if is_top else GREY_TEXT
        font_wt = 'bold' if is_top else 'normal'
        ax.text(v + max(values)*0.01, i, f'{v:,}', va='center', fontsize=8.5, color=text_color, fontweight=font_wt)
        
    save_chart(fig, '2a_top_routes')

    df_routes_user = run_query(con, '2b_routes_by_user_type', """
        SELECT user_type, start_station_name, end_station_name,
               COUNT(*) AS trip_count, ROUND(AVG(duration_sec) / 60.0, 1) AS avg_duration_min
        FROM trips
        WHERE duration_sec BETWEEN 60 AND 86400
          AND start_station_name IS NOT NULL AND end_station_name IS NOT NULL
        GROUP BY user_type, start_station_name, end_station_name
        QUALIFY ROW_NUMBER() OVER (PARTITION BY user_type ORDER BY COUNT(*) DESC) <= 10
        ORDER BY user_type, trip_count DESC
    """)

    df_roundtrip = run_query(con, '2c_roundtrip_vs_oneway', """
        SELECT
            CASE WHEN start_station_name = end_station_name THEN 'Round Trip' ELSE 'One Way' END AS trip_type,
            COUNT(*) AS trip_count,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct,
            ROUND(AVG(duration_sec) / 60.0, 1) AS avg_duration_min
        FROM trips
        WHERE duration_sec BETWEEN 60 AND 86400 AND start_station_name IS NOT NULL
        GROUP BY trip_type
    """)

    # ── 3. STATION UTILIZATION ───────────────────────────────────────────
    print("\n3. Station Utilization")
    print("-" * 40)

    df_top_start = run_query(con, '3a_top_start_stations', """
        SELECT start_station_name,
               ROUND(AVG(start_lat), 6) AS lat, ROUND(AVG(start_lng), 6) AS lng,
               COUNT(*) AS departure_count,
               ROUND(AVG(duration_sec) / 60.0, 1) AS avg_trip_duration_min
        FROM trips
        WHERE duration_sec BETWEEN 60 AND 86400 AND start_station_name IS NOT NULL AND start_lat IS NOT NULL
        GROUP BY start_station_name
        ORDER BY departure_count DESC LIMIT 20
    """)

    fig, ax = plt.subplots(figsize=(14, 8))
    names = df_top_start['start_station_name'].values[::-1]
    counts = df_top_start['departure_count'].values[::-1]
    colors_bar = [GREY_BARS] * len(counts)
    colors_bar[-1] = ACCENT_BLUE
    colors_bar[-2] = ACCENT_BLUE
    colors_bar[-3] = ACCENT_BLUE
    
    ax.barh(range(len(names)), counts, color=colors_bar, height=0.6)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels([n[:30] for n in names], fontsize=9.5)
    ax.set_xlabel('Total Departures')
    ax.set_title('Grove St PATH and Hoboken Terminal dominate system departures', fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='x', alpha=0.1, linestyle=':')
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000:.0f}K'))
    for i, v in enumerate(counts):
        text_color = ACCENT_BLUE if i >= len(counts)-3 else GREY_TEXT
        font_wt = 'bold' if i >= len(counts)-3 else 'normal'
        ax.text(v + max(counts)*0.01, i, f'{v:,}', va='center', fontsize=8.5, color=text_color, fontweight=font_wt)
    save_chart(fig, '3a_top_stations')

    df_top_end = run_query(con, '3b_top_end_stations', """
        SELECT end_station_name,
               ROUND(AVG(end_lat), 6) AS lat, ROUND(AVG(end_lng), 6) AS lng,
               COUNT(*) AS arrival_count
        FROM trips
        WHERE duration_sec BETWEEN 60 AND 86400 AND end_station_name IS NOT NULL AND end_lat IS NOT NULL
        GROUP BY end_station_name
        ORDER BY arrival_count DESC LIMIT 20
    """)

    # Net flow chart
    df_netflow = run_query(con, '3c_station_net_flow', """
        WITH departures AS (
            SELECT start_station_name AS station_name, COUNT(*) AS dep_count
            FROM trips WHERE duration_sec BETWEEN 60 AND 86400 AND start_station_name IS NOT NULL
            GROUP BY start_station_name
        ), arrivals AS (
            SELECT end_station_name AS station_name, COUNT(*) AS arr_count
            FROM trips WHERE duration_sec BETWEEN 60 AND 86400 AND end_station_name IS NOT NULL
            GROUP BY end_station_name
        )
        SELECT COALESCE(d.station_name, a.station_name) AS station_name,
               COALESCE(d.dep_count, 0) AS departures,
               COALESCE(a.arr_count, 0) AS arrivals,
               COALESCE(d.dep_count, 0) - COALESCE(a.arr_count, 0) AS net_flow,
               COALESCE(d.dep_count, 0) + COALESCE(a.arr_count, 0) AS total_activity
        FROM departures d FULL OUTER JOIN arrivals a ON d.station_name = a.station_name
        ORDER BY ABS(COALESCE(d.dep_count, 0) - COALESCE(a.arr_count, 0)) DESC
        LIMIT 30
    """)

    fig, ax = plt.subplots(figsize=(14, 8))
    top_imbalanced = df_netflow.head(20).sort_values('net_flow')
    
    # Modern exporter (emerald) vs importer (rose red) palette
    colors_flow = ['#10b981' if x > 0 else '#f43f5e' for x in top_imbalanced['net_flow']]
    ax.barh(range(len(top_imbalanced)), top_imbalanced['net_flow'], color=colors_flow, height=0.6)
    ax.set_yticks(range(len(top_imbalanced)))
    ax.set_yticklabels([n[:30] for n in top_imbalanced['station_name']], fontsize=9.5)
    ax.set_xlabel('Net Flow (Departures − Arrivals)')
    ax.set_title('Station flow imbalance: PATH stations import riders, residential zones export', fontweight='bold')
    ax.axvline(x=0, color=GREY_TEXT, linewidth=0.8, alpha=0.5, linestyle='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='x', alpha=0.1, linestyle=':')
    
    # Dynamic labels to highlight the most imbalanced stations
    for idx, row in enumerate(top_imbalanced.itertuples()):
        if row.station_name == 'Grove St PATH':
            # Place inside the bar to avoid overlapping the y-axis labels
            ax.text(row.net_flow + 2000, idx, f'Grove St PATH (Importer: {row.net_flow/1000:.1f}K)', ha='left', va='center', color='white', fontweight='bold', fontsize=9.5)
        elif row.station_name == 'McGinley Square':
            # Place inside the bar
            ax.text(row.net_flow - 2000, idx, f'McGinley Square (Exporter: +{row.net_flow/1000:.1f}K)', ha='right', va='center', color='white', fontweight='bold', fontsize=9.5)
            
    save_chart(fig, '3c_net_flow')

    df_trend = run_query(con, '3d_station_trend', """
        WITH top_stations AS (
            SELECT start_station_name AS station_name
            FROM trips WHERE duration_sec BETWEEN 60 AND 86400 AND start_station_name IS NOT NULL
            GROUP BY start_station_name ORDER BY COUNT(*) DESC LIMIT 10
        )
        SELECT EXTRACT(YEAR FROM t.started_at) AS year,
               t.start_station_name AS station_name, COUNT(*) AS trip_count
        FROM trips t JOIN top_stations ts ON t.start_station_name = ts.station_name
        WHERE t.duration_sec BETWEEN 60 AND 86400
        GROUP BY EXTRACT(YEAR FROM t.started_at), t.start_station_name ORDER BY t.start_station_name, year
    """)

    # All stations summary
    df_all_stations = run_query(con, '3e_all_stations', """
        SELECT start_station_name AS station_name, start_station_id AS station_id,
               ROUND(AVG(start_lat), 6) AS lat, ROUND(AVG(start_lng), 6) AS lng,
               COUNT(*) AS total_departures,
               ROUND(AVG(duration_sec) / 60.0, 1) AS avg_duration_min,
               SUM(CASE WHEN user_type = 'member' THEN 1 ELSE 0 END) AS member_trips,
               SUM(CASE WHEN user_type = 'casual' THEN 1 ELSE 0 END) AS casual_trips,
               MIN(started_at) AS first_trip, MAX(started_at) AS last_trip
        FROM trips
        WHERE duration_sec BETWEEN 60 AND 86400
          AND start_station_name IS NOT NULL AND start_lat IS NOT NULL
          AND start_lat BETWEEN 40.5 AND 41.0 AND start_lng BETWEEN -74.2 AND -73.9
        GROUP BY start_station_name, start_station_id
        ORDER BY total_departures DESC
    """)

    # ── 4. USER TYPE ANALYSIS ────────────────────────────────────────────
    print("\n4. User Type Analysis")
    print("-" * 40)

    df_user_monthly = run_query(con, '4a_member_vs_casual', """
        SELECT EXTRACT(YEAR FROM started_at) AS year,
               EXTRACT(MONTH FROM started_at) AS month,
               user_type, COUNT(*) AS trip_count
        FROM trips WHERE duration_sec BETWEEN 60 AND 86400
        GROUP BY year, month, user_type
        ORDER BY year, month, user_type
    """)

    # Stacked area chart with direct annotations
    fig, ax = plt.subplots(figsize=(16, 6))
    df_pivot_user = df_user_monthly.pivot_table(
        index=['year', 'month'], columns='user_type', values='trip_count', fill_value=0
    ).reset_index()
    df_pivot_user['date'] = pd.to_datetime(
        df_pivot_user['year'].astype(int).astype(str) + '-' +
        df_pivot_user['month'].astype(int).astype(str) + '-01'
    )
    df_pivot_user = df_pivot_user.sort_values('date')

    member_vals = df_pivot_user.get('member', pd.Series([0]*len(df_pivot_user))).values
    casual_vals = df_pivot_user.get('casual', pd.Series([0]*len(df_pivot_user))).values

    ax.fill_between(df_pivot_user['date'], 0, member_vals, alpha=0.8, color=ACCENT_BLUE)
    ax.fill_between(df_pivot_user['date'], member_vals, member_vals + casual_vals,
                    alpha=0.75, color=ACCENT_ORANGE)
    ax.set_ylabel('Monthly Trips')
    ax.set_title('Members provide stable baseline; casual riders drive summer demand surges', fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.1, linestyle=':')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000:.0f}K'))
    
    # Direct text annotations in the middle of 2024 to skip legend
    df_2024 = df_pivot_user[df_pivot_user['year'] == 2024]
    if not df_2024.empty:
        mid_row = df_2024.iloc[len(df_2024)//2]
        mid_date = mid_row['date']
        y_member = mid_row['member'] / 2
        y_casual = mid_row['member'] + (mid_row['casual'] / 2)
        ax.text(mid_date, y_member, 'Members', color='white', fontweight='bold', fontsize=12, ha='center')
        ax.text(mid_date, y_casual, 'Casual Riders', color='white', fontweight='bold', fontsize=12, ha='center')
        
    save_chart(fig, '4a_member_vs_casual')

    df_bike_type = run_query(con, '4b_bike_type', """
        SELECT bike_type, COUNT(*) AS trip_count,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct,
               ROUND(AVG(duration_sec) / 60.0, 1) AS avg_duration_min
        FROM trips WHERE duration_sec BETWEEN 60 AND 86400
        GROUP BY bike_type ORDER BY trip_count DESC
    """)

    df_user_bike = run_query(con, '4c_user_bike_duration', """
        SELECT user_type, bike_type, COUNT(*) AS trip_count,
               ROUND(AVG(duration_sec) / 60.0, 1) AS avg_duration_min,
               ROUND(MEDIAN(duration_sec) / 60.0, 1) AS median_duration_min
        FROM trips WHERE duration_sec BETWEEN 60 AND 86400
        GROUP BY user_type, bike_type ORDER BY user_type, bike_type
    """)

    df_ebike = run_query(con, '4d_ebike_adoption', """
        SELECT EXTRACT(YEAR FROM started_at) AS year, bike_type,
               COUNT(*) AS trip_count,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY EXTRACT(YEAR FROM started_at)), 1) AS pct
        FROM trips WHERE duration_sec BETWEEN 60 AND 86400
        GROUP BY year, bike_type ORDER BY year, bike_type
    """)

    # E-bike adoption chart with direct label
    fig, ax = plt.subplots(figsize=(14, 6))
    unique_years = sorted(df_ebike['year'].unique())
    
    for btype, color in [('classic_bike', ACCENT_BLUE), ('electric_bike', ACCENT_GREEN), ('docked_bike', ACCENT_PURPLE)]:
        mask = df_ebike['bike_type'] == btype
        if mask.any():
            df_sub = df_ebike[mask].sort_values('year')
            ax.plot(df_sub['year'].astype(int).astype(str),
                    df_sub['pct'], color=color, linewidth=2.5,
                    marker='o', markersize=5)
            
            # Direct labeling at endpoint (2026)
            last_val = df_sub['pct'].values[-1]
            label_name = btype.replace('_', ' ').title()
            ax.text(len(unique_years) - 0.8, last_val, f' {label_name} ({last_val:.0f}%)', color=color, fontweight='bold', va='center')

    ax.set_xlim(-0.3, len(unique_years) + 0.8)
    ax.set_ylabel('% of Trips')
    ax.set_title('Electric bikes now account for 66% of all bike-share trips', fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.1, linestyle=':')
    save_chart(fig, '4d_ebike_adoption')

    # ── TRIP DURATION DISTRIBUTION ───────────────────────────────────────
    print("\n5. Trip Duration Distribution")
    print("-" * 40)

    df_duration = run_query(con, '5_duration_distribution', """
        SELECT
            CASE
                WHEN duration_sec < 300 THEN '1-5 min'
                WHEN duration_sec < 600 THEN '5-10 min'
                WHEN duration_sec < 900 THEN '10-15 min'
                WHEN duration_sec < 1200 THEN '15-20 min'
                WHEN duration_sec < 1800 THEN '20-30 min'
                WHEN duration_sec < 2700 THEN '30-45 min'
                WHEN duration_sec < 3600 THEN '45-60 min'
                ELSE '60+ min'
            END AS duration_bucket,
            COUNT(*) AS trip_count
        FROM trips
        WHERE duration_sec BETWEEN 60 AND 86400
        GROUP BY duration_bucket
        ORDER BY MIN(duration_sec)
    """)

    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Highlight short trip buckets (1-5, 5-10, 10-15 min) in blue, others in slate
    colors = [GREY_BARS] * len(df_duration)
    for idx, r in enumerate(df_duration.itertuples()):
        if r.duration_bucket in ('1-5 min', '5-10 min', '10-15 min'):
            colors[idx] = ACCENT_BLUE
            
    ax.bar(df_duration['duration_bucket'], df_duration['trip_count'],
           color=colors, width=0.6, alpha=0.9)
    ax.set_xlabel('Trip Duration')
    ax.set_ylabel('Number of Trips')
    ax.set_title('Short utility rides (under 15 min) dominate the system', fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.1, linestyle=':')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000:.0f}K'))
    ax.set_ylim(0, max(df_duration['trip_count']) * 1.15)
    plt.xticks(rotation=30, ha='right')
    

                
    save_chart(fig, '5_duration_distribution')

    # ── MONTHLY TRIPS LINE (multi-year timeline) ─────────────────────────
    print("\n6. Monthly Timeline")
    print("-" * 40)

    df_timeline = run_query(con, '6_monthly_timeline', """
        SELECT
            EXTRACT(YEAR FROM started_at) AS year,
            EXTRACT(MONTH FROM started_at) AS month,
            COUNT(*) AS trip_count
        FROM trips WHERE duration_sec BETWEEN 60 AND 86400
        GROUP BY year, month ORDER BY year, month
    """)

    fig, ax = plt.subplots(figsize=(18, 6))
    df_timeline['date'] = pd.to_datetime(
        df_timeline['year'].astype(int).astype(str) + '-' +
        df_timeline['month'].astype(int).astype(str) + '-01'
    )
    ax.plot(df_timeline['date'], df_timeline['trip_count'],
            color=ACCENT_BLUE, linewidth=2.5, alpha=0.9)
    ax.fill_between(df_timeline['date'], df_timeline['trip_count'],
                    alpha=0.12, color=ACCENT_BLUE)
    
    # Milestones lines
    # 1. COVID Dip
    covid_date = pd.Timestamp('2020-04-01')
    ax.axvline(x=covid_date, color=ACCENT_RED, linewidth=1, linestyle='--', alpha=0.6)
                
    # 2. Electrification Rebound
    rebound_date = pd.Timestamp('2021-09-01')
    ax.axvline(x=rebound_date, color=ACCENT_GREEN, linewidth=1, linestyle='--', alpha=0.6)
                
    # 3. All-time peak
    peak_date = pd.Timestamp('2024-10-01')
    ax.axvline(x=peak_date, color=ACCENT_ORANGE, linewidth=1, linestyle='--', alpha=0.6)

    ax.set_ylabel('Monthly Trips')
    ax.set_title('10-year ridership timeline shows strong post-pandemic expansion', fontweight='bold')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='y', alpha=0.1, linestyle=':')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000:.0f}K'))
    save_chart(fig, '6_monthly_timeline')

    # ── SUMMARY ──────────────────────────────────────────────────────────
    elapsed = time.time() - start
    print("\n" + "=" * 60)
    print(f"Analysis complete in {elapsed:.1f}s")
    print(f"Results: {RESULTS_DIR}")
    print(f"Charts: {CHARTS_DIR}")

    result_files = os.listdir(RESULTS_DIR)
    chart_files = os.listdir(CHARTS_DIR)
    print(f"  {len(result_files)} CSV files, {len(chart_files)} chart files")

    con.close()


if __name__ == '__main__':
    main()
