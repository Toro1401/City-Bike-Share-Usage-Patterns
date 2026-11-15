# Historical exploration; superseded by ingest.py and build_portfolio.py. See README.md.
"""
setup_database.py — Load all 127 Citi Bike CSV files into a unified DuckDB database.

Handles two schema versions:
  - Old (2015-09 to 2021-01): tripduration, starttime, stoptime, station IDs/names, lat/lng, bikeid, usertype, birth year, gender
  - New (2021-02 to 2026-04): ride_id, rideable_type, started_at, ended_at, station names/IDs, lat/lng, member_casual

Output: citibike.duckdb with a single 'trips' table containing unified schema.
"""

import duckdb
import glob
import os
import time

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'citibike.duckdb')
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'Dataset')


def get_schema_version(filepath: str) -> str:
    """Detect schema version by reading header line."""
    with open(filepath, 'r', encoding='utf-8') as f:
        header = f.readline().strip().lower()
    if 'ride_id' in header:
        return 'new'
    elif 'tripduration' in header or 'trip duration' in header:
        return 'old'
    else:
        raise ValueError(f"Unknown schema in {filepath}: {header[:100]}")


def setup_database():
    """Create unified DuckDB database from all CSV files."""
    start = time.time()

    # Remove existing DB
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    con = duckdb.connect(DB_PATH)

    # Create unified trips table
    con.execute("""
        CREATE TABLE trips (
            ride_id VARCHAR,
            bike_type VARCHAR,
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
            duration_sec INTEGER,
            start_station_name VARCHAR,
            start_station_id VARCHAR,
            end_station_name VARCHAR,
            end_station_id VARCHAR,
            start_lat DOUBLE,
            start_lng DOUBLE,
            end_lat DOUBLE,
            end_lng DOUBLE,
            user_type VARCHAR
        )
    """)

    # Get all CSV files
    csv_files = sorted(glob.glob(os.path.join(DATA_DIR, '*.csv')))
    total_files = len(csv_files)
    total_rows = 0
    prev_count = 0

    print(f"Found {total_files} CSV files in {DATA_DIR}")
    print(f"Database: {DB_PATH}")
    print("-" * 60)

    for i, filepath in enumerate(csv_files, 1):
        filename = os.path.basename(filepath)
        schema = get_schema_version(filepath)
        count_before = con.execute("SELECT COUNT(*) FROM trips").fetchone()[0]

        try:
            if schema == 'new':
                # New schema (2021-02+): ride_id, rideable_type, started_at, ended_at,
                # start_station_name, start_station_id, end_station_name, end_station_id,
                # start_lat, start_lng, end_lat, end_lng, member_casual
                query = f"""
                    INSERT INTO trips
                    SELECT
                        ride_id,
                        rideable_type AS bike_type,
                        started_at::TIMESTAMP AS started_at,
                        ended_at::TIMESTAMP AS ended_at,
                        EXTRACT(EPOCH FROM (ended_at::TIMESTAMP - started_at::TIMESTAMP))::INTEGER AS duration_sec,
                        start_station_name,
                        start_station_id::VARCHAR AS start_station_id,
                        end_station_name,
                        end_station_id::VARCHAR AS end_station_id,
                        start_lat,
                        start_lng,
                        end_lat,
                        end_lng,
                        member_casual AS user_type
                    FROM read_csv_auto('{filepath.replace(os.sep, "/")}',
                         header=true, ignore_errors=true)
                """
            else:
                # Old schema: varies in column name casing/spacing
                query = f"""
                    INSERT INTO trips
                    SELECT
                        ROW_NUMBER() OVER () || '_{filename}' AS ride_id,
                        'classic_bike' AS bike_type,
                        columns('^(starttime|Start Time)$')::TIMESTAMP AS started_at,
                        columns('^(stoptime|Stop Time)$')::TIMESTAMP AS ended_at,
                        columns('^(tripduration|Trip Duration)$')::INTEGER AS duration_sec,
                        columns('^(start station name|Start Station Name)$') AS start_station_name,
                        columns('^(start station id|Start Station ID)$')::VARCHAR AS start_station_id,
                        columns('^(end station name|End Station Name)$') AS end_station_name,
                        columns('^(end station id|End Station ID)$')::VARCHAR AS end_station_id,
                        columns('^(start station latitude|Start Station Latitude)$')::DOUBLE AS start_lat,
                        columns('^(start station longitude|Start Station Longitude)$')::DOUBLE AS start_lng,
                        columns('^(end station latitude|End Station Latitude)$')::DOUBLE AS end_lat,
                        columns('^(end station longitude|End Station Longitude)$')::DOUBLE AS end_lng,
                        CASE
                            WHEN columns('^(usertype|User Type)$') IN ('Subscriber', 'subscriber') THEN 'member'
                            ELSE 'casual'
                        END AS user_type
                    FROM read_csv_auto('{filepath.replace(os.sep, "/")}',
                         header=true, ignore_errors=true)
                """

            con.execute(query)
            count_after = con.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
            rows = count_after - count_before
            total_rows += rows
            print(f"  [{i:3d}/{total_files}] {filename} -- {rows:,} rows ({schema} schema)")

        except Exception as e:
            print(f"  [{i:3d}/{total_files}] {filename} -- ERROR: {e}")
            # Try simpler approach for problematic files
            try:
                count_fb_before = con.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
                _load_with_pandas_fallback(con, filepath, filename, schema)
                count_fb_after = con.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
                rows = count_fb_after - count_fb_before
                total_rows += rows
                print(f"           -> Fallback succeeded: {rows:,} rows")
            except Exception as e2:
                print(f"           -> Fallback also failed: {e2}")

    # Create indexes for common query patterns
    print("\nCreating indexes...")
    con.execute("CREATE INDEX idx_started_at ON trips(started_at)")
    con.execute("CREATE INDEX idx_start_station ON trips(start_station_name)")
    con.execute("CREATE INDEX idx_end_station ON trips(end_station_name)")
    con.execute("CREATE INDEX idx_user_type ON trips(user_type)")

    # Summary stats
    final_count = con.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
    elapsed = time.time() - start

    print("-" * 60)
    print(f"DONE in {elapsed:.1f}s")
    print(f"Total rows: {final_count:,}")
    print(f"DB size: {os.path.getsize(DB_PATH) / (1024*1024):.1f} MB")

    # Quick data quality check
    print("\nData quality snapshot:")
    result = con.execute("""
        SELECT
            COUNT(*) AS total_trips,
            COUNT(DISTINCT start_station_name) AS unique_start_stations,
            COUNT(DISTINCT end_station_name) AS unique_end_stations,
            MIN(started_at) AS earliest_trip,
            MAX(started_at) AS latest_trip,
            SUM(CASE WHEN start_lat IS NULL THEN 1 ELSE 0 END) AS null_lat_count,
            SUM(CASE WHEN duration_sec < 60 THEN 1 ELSE 0 END) AS short_trips,
            SUM(CASE WHEN duration_sec > 86400 THEN 1 ELSE 0 END) AS very_long_trips
        FROM trips
    """).fetchone()

    print(f"  Total trips: {result[0]:,}")
    print(f"  Unique start stations: {result[1]}")
    print(f"  Unique end stations: {result[2]}")
    print(f"  Date range: {result[3]} to {result[4]}")
    print(f"  Null coordinates: {result[5]:,}")
    print(f"  Short trips (<60s): {result[6]:,}")
    print(f"  Very long trips (>24h): {result[7]:,}")

    con.close()
    return DB_PATH


def _load_with_pandas_fallback(con, filepath, filename, schema):
    """Fallback: use pandas to read CSV then insert into DuckDB."""
    import pandas as pd

    df = pd.read_csv(filepath, low_memory=False)
    # Normalize column names
    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]

    if schema == 'old':
        col_map = {}
        for c in df.columns:
            if 'tripduration' in c or 'trip_duration' in c:
                col_map[c] = 'duration_sec'
            elif 'starttime' in c or 'start_time' in c:
                col_map[c] = 'started_at'
            elif 'stoptime' in c or 'stop_time' in c:
                col_map[c] = 'ended_at'
            elif 'start_station_name' in c:
                col_map[c] = 'start_station_name'
            elif 'start_station_id' in c:
                col_map[c] = 'start_station_id'
            elif 'end_station_name' in c:
                col_map[c] = 'end_station_name'
            elif 'end_station_id' in c:
                col_map[c] = 'end_station_id'
            elif 'start_station_lat' in c:
                col_map[c] = 'start_lat'
            elif 'start_station_long' in c:
                col_map[c] = 'start_lng'
            elif 'end_station_lat' in c:
                col_map[c] = 'end_lat'
            elif 'end_station_long' in c:
                col_map[c] = 'end_lng'
            elif c == 'usertype' or c == 'user_type':
                col_map[c] = 'user_type'

        df = df.rename(columns=col_map)
        df['ride_id'] = [f"{i}_{filename}" for i in range(len(df))]
        df['bike_type'] = 'classic_bike'
        df['user_type'] = df['user_type'].map(
            lambda x: 'member' if str(x).lower() in ('subscriber',) else 'casual'
        )
    else:
        df = df.rename(columns={
            'rideable_type': 'bike_type',
            'member_casual': 'user_type'
        })
        df['duration_sec'] = (
            pd.to_datetime(df['ended_at']) - pd.to_datetime(df['started_at'])
        ).dt.total_seconds().astype(int)

    # Keep only unified columns
    cols = ['ride_id', 'bike_type', 'started_at', 'ended_at', 'duration_sec',
            'start_station_name', 'start_station_id', 'end_station_name',
            'end_station_id', 'start_lat', 'start_lng', 'end_lat', 'end_lng',
            'user_type']

    for c in cols:
        if c not in df.columns:
            df[c] = None

    df = df[cols]
    df['start_station_id'] = df['start_station_id'].astype(str)
    df['end_station_id'] = df['end_station_id'].astype(str)

    con.execute("INSERT INTO trips SELECT * FROM df")


if __name__ == '__main__':
    setup_database()
