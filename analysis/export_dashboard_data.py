"""
export_dashboard_data.py — Export aggregated analysis data as JSON for the web dashboard.

Reads from citibike.duckdb and analysis results, generates JSON files
that the static dashboard can load without a backend.
"""

import duckdb
import pandas as pd
import json
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '..', 'citibike.duckdb')
RESULTS_DIR = os.path.join(BASE_DIR, 'results')
DASHBOARD_DATA_DIR = os.path.join(BASE_DIR, '..', 'dashboard', 'data')

os.makedirs(DASHBOARD_DATA_DIR, exist_ok=True)


def save_json(data, filename):
    path = os.path.join(DASHBOARD_DATA_DIR, filename)
    with open(path, 'w') as f:
        json.dump(data, f, indent=None, default=str)  # compact JSON
    size_kb = os.path.getsize(path) / 1024
    print(f"  {filename} ({size_kb:.1f} KB)")


def export_all():
    start = time.time()
    print("=" * 60)
    print("Exporting Dashboard Data")
    print("=" * 60)

    con = duckdb.connect(DB_PATH, read_only=True)

    # ── 1. KPI Summary ─────────────────────────────────────────────────
    print("\n1. KPI metrics...")
    kpi = con.execute("""
        SELECT
            COUNT(*) AS total_trips,
            COUNT(DISTINCT start_station_name) AS total_stations,
            ROUND(AVG(duration_sec) / 60.0, 1) AS avg_duration_min,
            ROUND(MEDIAN(duration_sec) / 60.0, 1) AS median_duration_min,
            MIN(started_at)::VARCHAR AS first_trip,
            MAX(started_at)::VARCHAR AS last_trip,
            ROUND(SUM(CASE WHEN user_type = 'member' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS member_pct,
            SUM(CASE WHEN bike_type = 'electric_bike' THEN 1 ELSE 0 END) AS electric_trips,
            SUM(CASE WHEN bike_type = 'classic_bike' THEN 1 ELSE 0 END) AS classic_trips
        FROM trips
        WHERE duration_sec BETWEEN 60 AND 86400
    """).fetchdf().iloc[0].to_dict()

    # Year-over-year for growth calc
    yoy = con.execute("""
        SELECT EXTRACT(YEAR FROM started_at) AS year, COUNT(*) AS trips
        FROM trips WHERE duration_sec BETWEEN 60 AND 86400
        GROUP BY year ORDER BY year
    """).fetchdf()

    if len(yoy) >= 2:
        latest_full = yoy.iloc[-2]
        prev_full = yoy.iloc[-3] if len(yoy) >= 3 else yoy.iloc[-2]
        kpi['yoy_growth_pct'] = round(
            (latest_full['trips'] - prev_full['trips']) / prev_full['trips'] * 100, 1
        ) if prev_full['trips'] > 0 else 0

    save_json(kpi, 'kpi.json')

    # ── 2. Stations (with coordinates + metrics) ────────────────────────
    print("\n2. Station data...")
    stations = con.execute("""
        WITH dep AS (
            SELECT start_station_name AS name,
                   MAX(start_station_id) AS id,
                   ROUND(AVG(start_lat), 6) AS lat, ROUND(AVG(start_lng), 6) AS lng,
                   COUNT(*) AS departures,
                   ROUND(AVG(duration_sec) / 60.0, 1) AS avg_dur,
                   SUM(CASE WHEN user_type = 'member' THEN 1 ELSE 0 END) AS member_dep,
                   SUM(CASE WHEN user_type = 'casual' THEN 1 ELSE 0 END) AS casual_dep,
                   MODE(EXTRACT(HOUR FROM started_at))::INT AS peak_hour
            FROM trips
            WHERE duration_sec BETWEEN 60 AND 86400
              AND start_station_name IS NOT NULL AND start_lat IS NOT NULL
              AND start_lat BETWEEN 40.69 AND 40.77
              AND start_lng BETWEEN -74.10 AND -74.01
            GROUP BY start_station_name
        ), arr AS (
            SELECT end_station_name AS name, COUNT(*) AS arrivals
            FROM trips
            WHERE duration_sec BETWEEN 60 AND 86400 AND end_station_name IS NOT NULL
            GROUP BY end_station_name
        )
        SELECT dep.name, dep.id, dep.lat, dep.lng,
               dep.departures, COALESCE(arr.arrivals, 0) AS arrivals,
               dep.departures + COALESCE(arr.arrivals, 0) AS total,
               dep.departures - COALESCE(arr.arrivals, 0) AS net_flow,
               dep.avg_dur, dep.member_dep, dep.casual_dep, dep.peak_hour
        FROM dep LEFT JOIN arr ON dep.name = arr.name
        WHERE dep.lat IS NOT NULL
        ORDER BY total DESC
    """).fetchdf()

    stations_list = stations.to_dict('records')
    save_json(stations_list, 'stations.json')

    # ── 3. Top Routes (for flow lines) ──────────────────────────────────
    print("\n3. Top routes...")
    routes = con.execute("""
        SELECT
            start_station_name AS start_name,
            end_station_name AS end_name,
            ROUND(AVG(start_lat), 6) AS start_lat,
            ROUND(AVG(start_lng), 6) AS start_lng,
            ROUND(AVG(end_lat), 6) AS end_lat,
            ROUND(AVG(end_lng), 6) AS end_lng,
            COUNT(*) AS trips,
            ROUND(AVG(duration_sec) / 60.0, 1) AS avg_dur
        FROM trips
        WHERE duration_sec BETWEEN 60 AND 86400
          AND start_station_name IS NOT NULL AND end_station_name IS NOT NULL
          AND start_station_name != end_station_name
          AND start_lat IS NOT NULL AND end_lat IS NOT NULL
          AND start_lat BETWEEN 40.5 AND 41.0
        GROUP BY start_station_name, end_station_name
        HAVING COUNT(*) > 200
        ORDER BY trips DESC
        LIMIT 50
    """).fetchdf()

    save_json(routes.to_dict('records'), 'routes.json')

    # ── 4. Hourly Heatmap ───────────────────────────────────────────────
    print("\n4. Hourly heatmap...")
    heatmap = con.execute("""
        SELECT
            EXTRACT(DOW FROM started_at)::INT AS dow,
            EXTRACT(HOUR FROM started_at)::INT AS hour,
            COUNT(*) AS trips
        FROM trips WHERE duration_sec BETWEEN 60 AND 86400
        GROUP BY dow, hour ORDER BY dow, hour
    """).fetchdf()

    # Convert to 7×24 matrix
    matrix = [[0]*24 for _ in range(7)]
    for _, row in heatmap.iterrows():
        matrix[int(row['dow'])][int(row['hour'])] = int(row['trips'])

    save_json({
        'days': ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
        'hours': list(range(24)),
        'matrix': matrix
    }, 'hourly_heatmap.json')

    # ── 5. Monthly Trends ──────────────────────────────────────────────
    print("\n5. Monthly trends...")
    monthly = con.execute("""
        SELECT
            EXTRACT(YEAR FROM started_at)::INT AS year,
            EXTRACT(MONTH FROM started_at)::INT AS month,
            COUNT(*) AS total,
            SUM(CASE WHEN user_type = 'member' THEN 1 ELSE 0 END)::INT AS members,
            SUM(CASE WHEN user_type = 'casual' THEN 1 ELSE 0 END)::INT AS casuals,
            SUM(CASE WHEN bike_type = 'electric_bike' THEN 1 ELSE 0 END)::INT AS electric,
            ROUND(AVG(duration_sec) / 60.0, 1) AS avg_dur
        FROM trips WHERE duration_sec BETWEEN 60 AND 86400
        GROUP BY year, month ORDER BY year, month
    """).fetchdf()

    save_json(monthly.to_dict('records'), 'monthly_trends.json')

    # ── 6. Recommendations ─────────────────────────────────────────────
    print("\n6. Recommendations...")
    rec_path = os.path.join(RESULTS_DIR, 'station_recommendations.json')
    if os.path.exists(rec_path):
        with open(rec_path, 'r') as f:
            recs = json.load(f)
        save_json(recs, 'recommendations.json')
    else:
        print("   ⚠ No recommendations file found — run station_recommendations.py first")
        save_json({'recommendations': [], 'metadata': {}}, 'recommendations.json')

    # ── 7. Yearly summary ──────────────────────────────────────────────
    print("\n7. Yearly summary...")
    yearly = con.execute("""
        SELECT
            EXTRACT(YEAR FROM started_at)::INT AS year,
            COUNT(*) AS trips,
            COUNT(DISTINCT start_station_name) AS stations,
            ROUND(AVG(duration_sec) / 60.0, 1) AS avg_dur,
            ROUND(SUM(CASE WHEN user_type = 'member' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS member_pct,
            ROUND(SUM(CASE WHEN bike_type = 'electric_bike' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*), 0), 1) AS electric_pct
        FROM trips WHERE duration_sec BETWEEN 60 AND 86400
        GROUP BY year ORDER BY year
    """).fetchdf()

    save_json(yearly.to_dict('records'), 'yearly_summary.json')

    # ── Done ───────────────────────────────────────────────────────────
    elapsed = time.time() - start
    print(f"\nExport complete in {elapsed:.1f}s")
    print(f"Dashboard data dir: {DASHBOARD_DATA_DIR}")

    con.close()


if __name__ == '__main__':
    export_all()
