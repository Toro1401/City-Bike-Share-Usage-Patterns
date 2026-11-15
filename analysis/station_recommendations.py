# Historical exploration; superseded by ingest.py and build_portfolio.py. See README.md.
"""
station_recommendations.py — Identify optimal locations for new bike-share stations.

Uses demand analysis, geographic gap detection, and trip endpoint clustering
to recommend 5-10 new station locations with supporting rationale.
"""

import duckdb
import pandas as pd
import numpy as np
import json
import os
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '..', 'citibike.duckdb')
RESULTS_DIR = os.path.join(BASE_DIR, 'results')

os.makedirs(RESULTS_DIR, exist_ok=True)


def haversine_distance(lat1, lng1, lat2, lng2):
    """Calculate distance in meters between two points."""
    R = 6371000
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlam = np.radians(lng2 - lng1)
    a = np.sin(dphi/2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam/2)**2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))


def get_station_data(con):
    """Get all station locations with activity metrics."""
    return con.execute("""
        WITH dep AS (
            SELECT start_station_name AS name,
                   AVG(start_lat) AS lat, AVG(start_lng) AS lng,
                   COUNT(*) AS departures
            FROM trips
            WHERE duration_sec BETWEEN 60 AND 86400
              AND start_station_name IS NOT NULL
              AND start_lat BETWEEN 40.69 AND 40.77
              AND start_lng BETWEEN -74.10 AND -74.01
            GROUP BY start_station_name
        ), arr AS (
            SELECT end_station_name AS name, COUNT(*) AS arrivals
            FROM trips
            WHERE duration_sec BETWEEN 60 AND 86400
              AND end_station_name IS NOT NULL
            GROUP BY end_station_name
        )
        SELECT dep.name, dep.lat, dep.lng,
               dep.departures, COALESCE(arr.arrivals, 0) AS arrivals,
               dep.departures + COALESCE(arr.arrivals, 0) AS total_activity
        FROM dep LEFT JOIN arr ON dep.name = arr.name
        ORDER BY total_activity DESC
    """).fetchdf()


def find_coverage_gaps(stations_df, grid_resolution=0.002):
    """Find areas with low station coverage using a grid approach."""
    # Jersey City bounds
    lat_min, lat_max = 40.695, 40.770
    lng_min, lng_max = -74.085, -74.020

    gaps = []
    station_lats = stations_df['lat'].values
    station_lngs = stations_df['lng'].values
    station_activity = stations_df['total_activity'].values

    for lat in np.arange(lat_min, lat_max, grid_resolution):
        for lng in np.arange(lng_min, lng_max, grid_resolution):
            # Distance to nearest station
            distances = haversine_distance(lat, lng, station_lats, station_lngs)
            min_dist = np.min(distances)
            nearest_idx = np.argmin(distances)

            if min_dist > 300:  # > 300m from any station
                # Check if nearby stations are busy (high demand area)
                nearby_mask = distances < 1000  # within 1km
                nearby_activity = station_activity[nearby_mask].sum() if nearby_mask.any() else 0

                gaps.append({
                    'lat': round(lat, 6),
                    'lng': round(lng, 6),
                    'nearest_station_dist_m': round(min_dist, 0),
                    'nearest_station': stations_df.iloc[nearest_idx]['name'],
                    'nearby_station_count': int(nearby_mask.sum()),
                    'nearby_total_activity': int(nearby_activity),
                    'score': min_dist * np.log1p(nearby_activity)  # farther + busier = higher score
                })

    return pd.DataFrame(gaps).sort_values('score', ascending=False)


def find_high_demand_corridors(con):
    """Find routes with high demand but long average distances — gap indicators."""
    return con.execute("""
        SELECT
            start_station_name, end_station_name,
            AVG(start_lat) AS start_lat, AVG(start_lng) AS start_lng,
            AVG(end_lat) AS end_lat, AVG(end_lng) AS end_lng,
            COUNT(*) AS trip_count,
            ROUND(AVG(duration_sec) / 60.0, 1) AS avg_duration_min,
            ROUND(AVG(
                6371000 * ACOS(
                    LEAST(1.0, GREATEST(-1.0,
                        COS(RADIANS(start_lat)) * COS(RADIANS(end_lat)) *
                        COS(RADIANS(end_lng) - RADIANS(start_lng)) +
                        SIN(RADIANS(start_lat)) * SIN(RADIANS(end_lat))
                    ))
                )
            ), 0) AS avg_distance_m
        FROM trips
        WHERE duration_sec BETWEEN 60 AND 86400
          AND start_station_name IS NOT NULL AND end_station_name IS NOT NULL
          AND start_station_name != end_station_name
          AND start_lat IS NOT NULL AND end_lat IS NOT NULL
          AND start_lat BETWEEN 40.5 AND 41.0
        GROUP BY start_station_name, end_station_name
        HAVING COUNT(*) > 500 AND avg_distance_m > 1000
        ORDER BY trip_count DESC
        LIMIT 20
    """).fetchdf()


def find_endpoint_clusters(con, stations_df):
    """Find clusters of trip endpoints that are far from any station.
    These indicate where people want to go but no station exists nearby."""
    # Get trip end coordinates that are far from the nearest end station
    df_ends = con.execute("""
        SELECT end_lat AS lat, end_lng AS lng, COUNT(*) AS trip_count
        FROM trips
        WHERE duration_sec BETWEEN 60 AND 86400
          AND end_lat IS NOT NULL
          AND end_lat BETWEEN 40.69 AND 41.0
          AND end_lng BETWEEN -74.1 AND -73.9
          AND end_station_name IS NULL  -- trips ending without docking = potential demand
        GROUP BY ROUND(end_lat, 3), ROUND(end_lng, 3), end_lat, end_lng
        HAVING COUNT(*) > 50
        ORDER BY trip_count DESC
        LIMIT 100
    """).fetchdf()

    if df_ends.empty:
        # Fallback: look at high-volume endpoint clusters
        df_ends = con.execute("""
            SELECT ROUND(end_lat, 3) AS lat, ROUND(end_lng, 3) AS lng,
                   COUNT(*) AS trip_count
            FROM trips
            WHERE duration_sec BETWEEN 60 AND 86400
              AND end_lat IS NOT NULL
              AND end_lat BETWEEN 40.69 AND 41.0
              AND end_lng BETWEEN -74.1 AND -73.9
            GROUP BY ROUND(end_lat, 3), ROUND(end_lng, 3)
            HAVING COUNT(*) > 200
            ORDER BY trip_count DESC
            LIMIT 50
        """).fetchdf()

    return df_ends


def score_and_rank_candidates(gaps_df, corridors_df, stations_df):
    """Score candidate locations and produce final recommendations."""
    recommendations = []

    # Signal 1: Coverage gaps near high-activity zones
    if not gaps_df.empty:
        top_gaps = gaps_df.head(20)
        for _, gap in top_gaps.iterrows():
            # Check if this gap is along a high-demand corridor
            corridor_bonus = 0
            for _, corr in corridors_df.iterrows():
                mid_lat = (corr['start_lat'] + corr['end_lat']) / 2
                mid_lng = (corr['start_lng'] + corr['end_lng']) / 2
                dist_to_mid = haversine_distance(gap['lat'], gap['lng'], mid_lat, mid_lng)
                if dist_to_mid < 500:
                    corridor_bonus += corr['trip_count']

            final_score = gap['score'] + corridor_bonus * 0.1

            recommendations.append({
                'lat': gap['lat'],
                'lng': gap['lng'],
                'score': round(final_score, 1),
                'nearest_station': gap['nearest_station'],
                'nearest_station_dist_m': gap['nearest_station_dist_m'],
                'nearby_stations': gap['nearby_station_count'],
                'nearby_activity': gap['nearby_total_activity'],
                'corridor_demand': int(corridor_bonus),
                'signals': []
            })

    # Sort and deduplicate (merge nearby candidates)
    recommendations.sort(key=lambda x: x['score'], reverse=True)

    # Merge candidates within 200m of each other
    merged = []
    used = set()
    for i, rec in enumerate(recommendations):
        if i in used:
            continue
        cluster = [rec]
        for j, other in enumerate(recommendations):
            if j <= i or j in used:
                continue
            dist = haversine_distance(rec['lat'], rec['lng'], other['lat'], other['lng'])
            if dist < 200:
                cluster.append(other)
                used.add(j)

        # Average coordinates of cluster
        avg_lat = np.mean([c['lat'] for c in cluster])
        avg_lng = np.mean([c['lng'] for c in cluster])
        max_score = max(c['score'] for c in cluster)

        best = cluster[0]
        best['lat'] = round(avg_lat, 6)
        best['lng'] = round(avg_lng, 6)
        best['score'] = round(max_score, 1)

        # Build rationale
        signals = []
        if best['nearest_station_dist_m'] > 400:
            signals.append(f"Coverage gap: {int(best['nearest_station_dist_m'])}m from nearest station ({best['nearest_station']})")
        if best['nearby_activity'] > 50000:
            signals.append(f"High surrounding demand: {best['nearby_activity']:,} trips at nearby stations")
        if best['corridor_demand'] > 0:
            signals.append(f"On high-demand corridor: {best['corridor_demand']:,} corridor trips")
        if best['nearby_stations'] < 3:
            signals.append(f"Low station density: only {best['nearby_stations']} stations within 1km")

        if not signals:
            signals.append(f"Moderate coverage gap: {int(best['nearest_station_dist_m'])}m from nearest station")

        best['signals'] = signals
        best['rationale'] = '. '.join(signals)
        merged.append(best)

    return merged[:10]  # Top 10


def generate_recommendations():
    """Main function: generate and save station recommendations."""
    print("=" * 60)
    print("Station Recommendation Analysis")
    print("=" * 60)

    con = duckdb.connect(DB_PATH, read_only=True)

    # Step 1: Get station data
    print("\n1. Loading station data...")
    stations_df = get_station_data(con)
    print(f"   {len(stations_df)} stations with activity data")

    # Step 2: Find coverage gaps
    print("\n2. Analyzing coverage gaps...")
    gaps_df = find_coverage_gaps(stations_df)
    print(f"   {len(gaps_df)} grid cells with coverage gaps (>300m from station)")

    # Step 3: Find high-demand corridors
    print("\n3. Identifying high-demand corridors...")
    corridors_df = find_high_demand_corridors(con)
    print(f"   {len(corridors_df)} high-demand corridors (>500 trips, >1km)")

    # Step 4: Find endpoint clusters
    print("\n4. Clustering trip endpoints...")
    endpoints_df = find_endpoint_clusters(con, stations_df)
    print(f"   {len(endpoints_df)} endpoint clusters found")

    # Step 5: Score and rank
    print("\n5. Scoring candidates...")
    recommendations = score_and_rank_candidates(gaps_df, corridors_df, stations_df)
    print(f"   {len(recommendations)} final recommendations")

    # Save results
    output = {
        'recommendations': recommendations,
        'metadata': {
            'total_stations': len(stations_df),
            'coverage_gaps_analyzed': len(gaps_df),
            'corridors_analyzed': len(corridors_df),
            'method': 'Coverage gap analysis + corridor demand + endpoint clustering'
        }
    }

    json_path = os.path.join(RESULTS_DIR, 'station_recommendations.json')
    with open(json_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n   Saved to {json_path}")

    # Save corridors
    corridors_path = os.path.join(RESULTS_DIR, 'high_demand_corridors.csv')
    corridors_df.to_csv(corridors_path, index=False)
    print(f"   Corridors saved to {corridors_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("TOP STATION RECOMMENDATIONS")
    print("=" * 60)
    for i, rec in enumerate(recommendations, 1):
        print(f"\n  #{i}: ({rec['lat']:.4f}, {rec['lng']:.4f})")
        print(f"      Score: {rec['score']}")
        print(f"      Nearest station: {rec['nearest_station']} ({int(rec['nearest_station_dist_m'])}m)")
        for signal in rec['signals']:
            print(f"      -> {signal}")

    con.close()
    return recommendations


if __name__ == '__main__':
    generate_recommendations()
