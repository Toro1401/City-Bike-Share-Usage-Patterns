# Methodology and KPI contract

## Grain and lineage

Raw trips contain source ride IDs in newer files; legacy IDs are generated as filename + row number. `ingest.py` accepts old/new schemas, parses CSV strictly and retains rows with invalid cast fields for visible quality exclusion later. Parsing errors fail the build. The manifest records input rows, imported rows, invalid times/durations and missing coordinates; diagnostic categories can overlap and must not be summed. Import rows reconcile exactly to the trips table. A source CSV missing entirely is detected through observed-month gaps, not fabricated as zero demand.

## Cleaning stages

1. Remove exact duplicate rows.
2. Quarantine all variants of a ride_id with conflicting rows, plus null ride IDs. No arbitrary survivor selection.
3. Keep duration 60–86,400 seconds, nonnull start/end and end >= start. Times remain as supplied; source timezone is not converted.
4. Reconcile monthly/yearly/hourly counts to clean trips.
5. Reconcile station endpoint counts to endpoints having both ID and name. Endpoints without identity stay in trip KPIs, but are not assigned to stations.

## Station identity

Station observation key: (year, station_id, station_name), using both departures and arrivals. This intentionally avoids automatically merging legacy IDs or renames. Coordinates use the latest observed record in the year, not an average across a decade. If within-year latitude or longitude span exceeds 0.005 degrees, flag the observation and omit it from the coordinate plot. The threshold is a review heuristic, not a verified relocation detector. Cross-year IDs can be reused; no physical-station lifetime count is claimed.

## Metrics

- Trips: clean record count.
- Member share: explicit member records / all clean records, including unknown user type in denominator.
- Median duration: median seconds / 60.
- Net flow: departures − arrivals per station observation; positive means net departures. Not stockout rate or bike availability.
- YoY: only if both adjacent years show all 12 months and observed date boundaries Jan 1–Dec 31. Missing periods suppress comparison.
- Year search: station filters do not alter year-wide KPIs. Coordinate plot is bounded and may omit out-of-area/invalid/flagged observations; table retains them with flags.

## Limits and decisions

Missing August 2017, partial first/last years, evolving membership/bike schemas, observation-based station identity and no capacity/availability/weather/rebalancing data. New-site demand and unmet demand cannot be inferred solely from historical trip endpoints. The verified output supports investigation of timing and directional imbalance, not automated expansion decisions.
