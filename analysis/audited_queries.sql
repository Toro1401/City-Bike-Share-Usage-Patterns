-- Canonical relations are temporary views; raw database is read-only.
-- name: yearly
SELECT year(started_at) AS yr,COUNT(*) AS trips,AVG(duration_sec)/60 AS avg_minutes,
 MEDIAN(duration_sec)/60 AS median_minutes,SUM(CASE WHEN user_type='member' THEN 1 ELSE 0 END) AS members,
 COUNT(DISTINCT month(started_at)) AS observed_months,
 MIN(started_at)::VARCHAR AS first_observed,MAX(started_at)::VARCHAR AS last_observed
FROM clean_trips GROUP BY 1 ORDER BY 1;

-- name: monthly
SELECT year(started_at) AS yr,month(started_at) AS mon,COUNT(*) AS trips
FROM clean_trips GROUP BY 1,2 ORDER BY 1,2;

-- name: hourly
SELECT year(started_at) AS yr,dayofweek(started_at) AS dow,hour(started_at) AS hr,COUNT(*) AS trips
FROM clean_trips GROUP BY 1,2,3 ORDER BY 1,2,3;

-- name: stations
-- Station ID AND name remain separate observations; latest observed coordinates per year.
-- No implicit merge of legacy IDs, renamed sites or relocated stations.
SELECT yr,station_id,name,SUM(dep) AS departures,SUM(arr) AS arrivals,
 arg_max(lat,observed_at) AS lat,arg_max(lng,observed_at) AS lng,
 MAX(lat)-MIN(lat) AS lat_span,MAX(lng)-MIN(lng) AS lng_span
FROM endpoints WHERE station_id IS NOT NULL AND name IS NOT NULL
GROUP BY 1,2,3 ORDER BY 1,departures DESC;
