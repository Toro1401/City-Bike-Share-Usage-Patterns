-- HISTORICAL EXPLORATION. Verified dashboard uses audited_queries.sql and explicit ID quarantine.
-- ============================================================================
-- City Bike-Share Usage Patterns — SQL Analysis Queries
-- Dataset: Citi Bike Jersey City, Sep 2015 – Apr 2026
-- Engine: DuckDB
-- ============================================================================

-- ============================================================================
-- 1. PEAK USAGE TIMES
-- ============================================================================

-- 1a. Trips by Hour of Day (overall)
-- Insight: Identifies morning/evening commute peaks vs midday/night lulls
SELECT
    EXTRACT(HOUR FROM started_at) AS hour_of_day,
    COUNT(*) AS trip_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_total
FROM trips
WHERE duration_sec BETWEEN 60 AND 86400
GROUP BY hour_of_day
ORDER BY hour_of_day;

-- 1b. Trips by Hour — Weekday vs Weekend
-- Insight: Commute pattern (weekday) vs leisure pattern (weekend)
SELECT
    EXTRACT(HOUR FROM started_at) AS hour_of_day,
    CASE WHEN EXTRACT(DOW FROM started_at) IN (0, 6) THEN 'weekend' ELSE 'weekday' END AS day_type,
    COUNT(*) AS trip_count
FROM trips
WHERE duration_sec BETWEEN 60 AND 86400
GROUP BY hour_of_day, day_type
ORDER BY day_type, hour_of_day;

-- 1c. Trips by Day of Week
SELECT
    EXTRACT(DOW FROM started_at) AS day_of_week,
    CASE EXTRACT(DOW FROM started_at)
        WHEN 0 THEN 'Sunday'
        WHEN 1 THEN 'Monday'
        WHEN 2 THEN 'Tuesday'
        WHEN 3 THEN 'Wednesday'
        WHEN 4 THEN 'Thursday'
        WHEN 5 THEN 'Friday'
        WHEN 6 THEN 'Saturday'
    END AS day_name,
    COUNT(*) AS trip_count
FROM trips
WHERE duration_sec BETWEEN 60 AND 86400
GROUP BY day_of_week, day_name
ORDER BY day_of_week;

-- 1d. Trips by Month (seasonal patterns)
SELECT
    EXTRACT(MONTH FROM started_at) AS month_num,
    CASE EXTRACT(MONTH FROM started_at)
        WHEN 1 THEN 'January' WHEN 2 THEN 'February' WHEN 3 THEN 'March'
        WHEN 4 THEN 'April' WHEN 5 THEN 'May' WHEN 6 THEN 'June'
        WHEN 7 THEN 'July' WHEN 8 THEN 'August' WHEN 9 THEN 'September'
        WHEN 10 THEN 'October' WHEN 11 THEN 'November' WHEN 12 THEN 'December'
    END AS month_name,
    COUNT(*) AS trip_count,
    ROUND(AVG(duration_sec) / 60.0, 1) AS avg_duration_min
FROM trips
WHERE duration_sec BETWEEN 60 AND 86400
GROUP BY month_num, month_name
ORDER BY month_num;

-- 1e. Year-over-Year Growth
SELECT
    EXTRACT(YEAR FROM started_at) AS year,
    COUNT(*) AS trip_count,
    ROUND(AVG(duration_sec) / 60.0, 1) AS avg_duration_min,
    COUNT(DISTINCT start_station_name) AS active_stations,
    ROUND(SUM(CASE WHEN user_type = 'member' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS member_pct
FROM trips
WHERE duration_sec BETWEEN 60 AND 86400
GROUP BY year
ORDER BY year;

-- 1f. Hourly Heatmap — Day of Week × Hour of Day
-- For heatmap visualization
SELECT
    EXTRACT(DOW FROM started_at) AS day_of_week,
    EXTRACT(HOUR FROM started_at) AS hour_of_day,
    COUNT(*) AS trip_count
FROM trips
WHERE duration_sec BETWEEN 60 AND 86400
GROUP BY day_of_week, hour_of_day
ORDER BY day_of_week, hour_of_day;


-- ============================================================================
-- 2. POPULAR ROUTES
-- ============================================================================

-- 2a. Top 20 Station-to-Station Routes
SELECT
    start_station_name,
    end_station_name,
    COUNT(*) AS trip_count,
    ROUND(AVG(duration_sec) / 60.0, 1) AS avg_duration_min,
    ROUND(AVG(
        6371000 * ACOS(
            COS(RADIANS(start_lat)) * COS(RADIANS(end_lat)) *
            COS(RADIANS(end_lng) - RADIANS(start_lng)) +
            SIN(RADIANS(start_lat)) * SIN(RADIANS(end_lat))
        )
    ), 0) AS avg_distance_m
FROM trips
WHERE duration_sec BETWEEN 60 AND 86400
  AND start_station_name IS NOT NULL
  AND end_station_name IS NOT NULL
  AND start_lat IS NOT NULL AND end_lat IS NOT NULL
GROUP BY start_station_name, end_station_name
ORDER BY trip_count DESC
LIMIT 20;

-- 2b. Top Routes by User Type
SELECT
    user_type,
    start_station_name,
    end_station_name,
    COUNT(*) AS trip_count,
    ROUND(AVG(duration_sec) / 60.0, 1) AS avg_duration_min
FROM trips
WHERE duration_sec BETWEEN 60 AND 86400
  AND start_station_name IS NOT NULL
  AND end_station_name IS NOT NULL
GROUP BY user_type, start_station_name, end_station_name
QUALIFY ROW_NUMBER() OVER (PARTITION BY user_type ORDER BY COUNT(*) DESC) <= 10
ORDER BY user_type, trip_count DESC;

-- 2c. Round-trip vs One-way Analysis
SELECT
    CASE WHEN start_station_name = end_station_name THEN 'Round Trip' ELSE 'One Way' END AS trip_type,
    COUNT(*) AS trip_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct,
    ROUND(AVG(duration_sec) / 60.0, 1) AS avg_duration_min
FROM trips
WHERE duration_sec BETWEEN 60 AND 86400
  AND start_station_name IS NOT NULL
GROUP BY trip_type;


-- ============================================================================
-- 3. STATION UTILIZATION
-- ============================================================================

-- 3a. Top 20 Busiest Start Stations
SELECT
    start_station_name,
    start_station_id,
    ROUND(AVG(start_lat), 6) AS lat,
    ROUND(AVG(start_lng), 6) AS lng,
    COUNT(*) AS departure_count,
    ROUND(AVG(duration_sec) / 60.0, 1) AS avg_trip_duration_min
FROM trips
WHERE duration_sec BETWEEN 60 AND 86400
  AND start_station_name IS NOT NULL
  AND start_lat IS NOT NULL
GROUP BY start_station_name, start_station_id
ORDER BY departure_count DESC
LIMIT 20;

-- 3b. Top 20 Busiest End Stations
SELECT
    end_station_name,
    end_station_id,
    ROUND(AVG(end_lat), 6) AS lat,
    ROUND(AVG(end_lng), 6) AS lng,
    COUNT(*) AS arrival_count
FROM trips
WHERE duration_sec BETWEEN 60 AND 86400
  AND end_station_name IS NOT NULL
  AND end_lat IS NOT NULL
GROUP BY end_station_name, end_station_id
ORDER BY arrival_count DESC
LIMIT 20;

-- 3c. Station Net Flow (departures − arrivals)
-- Positive = net exporter (more bikes leave), Negative = net importer
WITH departures AS (
    SELECT start_station_name AS station_name, COUNT(*) AS dep_count
    FROM trips
    WHERE duration_sec BETWEEN 60 AND 86400 AND start_station_name IS NOT NULL
    GROUP BY start_station_name
),
arrivals AS (
    SELECT end_station_name AS station_name, COUNT(*) AS arr_count
    FROM trips
    WHERE duration_sec BETWEEN 60 AND 86400 AND end_station_name IS NOT NULL
    GROUP BY end_station_name
)
SELECT
    COALESCE(d.station_name, a.station_name) AS station_name,
    COALESCE(d.dep_count, 0) AS departures,
    COALESCE(a.arr_count, 0) AS arrivals,
    COALESCE(d.dep_count, 0) - COALESCE(a.arr_count, 0) AS net_flow,
    COALESCE(d.dep_count, 0) + COALESCE(a.arr_count, 0) AS total_activity
FROM departures d
FULL OUTER JOIN arrivals a ON d.station_name = a.station_name
ORDER BY ABS(COALESCE(d.dep_count, 0) - COALESCE(a.arr_count, 0)) DESC
LIMIT 30;

-- 3d. Station Utilization Trend (yearly, top 10 stations)
WITH top_stations AS (
    SELECT start_station_name AS station_name
    FROM trips
    WHERE duration_sec BETWEEN 60 AND 86400 AND start_station_name IS NOT NULL
    GROUP BY start_station_name
    ORDER BY COUNT(*) DESC
    LIMIT 10
)
SELECT
    EXTRACT(YEAR FROM t.started_at) AS year,
    t.start_station_name AS station_name,
    COUNT(*) AS trip_count
FROM trips t
JOIN top_stations ts ON t.start_station_name = ts.station_name
WHERE t.duration_sec BETWEEN 60 AND 86400
GROUP BY year, station_name
ORDER BY station_name, year;

-- 3e. Full Station Summary (all stations with coordinates)
SELECT
    start_station_name AS station_name,
    start_station_id AS station_id,
    ROUND(AVG(start_lat), 6) AS lat,
    ROUND(AVG(start_lng), 6) AS lng,
    COUNT(*) AS total_departures,
    ROUND(AVG(duration_sec) / 60.0, 1) AS avg_duration_min,
    SUM(CASE WHEN user_type = 'member' THEN 1 ELSE 0 END) AS member_trips,
    SUM(CASE WHEN user_type = 'casual' THEN 1 ELSE 0 END) AS casual_trips,
    MIN(started_at) AS first_trip,
    MAX(started_at) AS last_trip
FROM trips
WHERE duration_sec BETWEEN 60 AND 86400
  AND start_station_name IS NOT NULL
  AND start_lat IS NOT NULL
  AND start_lat BETWEEN 40.5 AND 41.0
  AND start_lng BETWEEN -74.2 AND -73.9
GROUP BY start_station_name, start_station_id
ORDER BY total_departures DESC;


-- ============================================================================
-- 4. USER TYPE ANALYSIS
-- ============================================================================

-- 4a. Member vs Casual Split Over Time
SELECT
    EXTRACT(YEAR FROM started_at) AS year,
    EXTRACT(MONTH FROM started_at) AS month,
    user_type,
    COUNT(*) AS trip_count
FROM trips
WHERE duration_sec BETWEEN 60 AND 86400
GROUP BY year, month, user_type
ORDER BY year, month, user_type;

-- 4b. Ride Type Distribution (classic vs electric bike)
SELECT
    bike_type,
    COUNT(*) AS trip_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct,
    ROUND(AVG(duration_sec) / 60.0, 1) AS avg_duration_min
FROM trips
WHERE duration_sec BETWEEN 60 AND 86400
GROUP BY bike_type
ORDER BY trip_count DESC;

-- 4c. Average Duration by User Type and Bike Type
SELECT
    user_type,
    bike_type,
    COUNT(*) AS trip_count,
    ROUND(AVG(duration_sec) / 60.0, 1) AS avg_duration_min,
    ROUND(MEDIAN(duration_sec) / 60.0, 1) AS median_duration_min,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_sec) / 60.0, 1) AS p95_duration_min
FROM trips
WHERE duration_sec BETWEEN 60 AND 86400
GROUP BY user_type, bike_type
ORDER BY user_type, bike_type;

-- 4d. Electric Bike Adoption Over Time
SELECT
    EXTRACT(YEAR FROM started_at) AS year,
    bike_type,
    COUNT(*) AS trip_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY EXTRACT(YEAR FROM started_at)), 1) AS pct
FROM trips
WHERE duration_sec BETWEEN 60 AND 86400
GROUP BY year, bike_type
ORDER BY year, bike_type;
