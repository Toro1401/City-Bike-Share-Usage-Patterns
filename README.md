# Citi Bike Operations Analysis

This DuckDB project looks at when people ride in Jersey City and where departures and arrivals differ. It uses 127 Citi Bike CSVs from September 2015 through April 2026. The import manifest accounts for every parsed record, and the offline dashboard shows the resulting aggregates along with gaps in coverage and uncertainty about station identity.

## Explore

- Open the [interactive dashboard](dashboard/index.html) directly in your browser. It runs offline without an account, a server, or a map service.
- [Audit and source-file manifest](dashboard/audited/audit.json), [verified SQL](analysis/audited_queries.sql), [method and KPI definitions](docs/METHODOLOGY.md), [PRD](PRD.md).

![Dashboard preview](docs/dashboard-preview.svg)

## Verified snapshot

| Stage | Records |
| --- | --- |
| Source records imported | 6,449,990 |
| Conflicting ride IDs | 24 IDs / 48 rows quarantined |
| Duration/time exclusions after quarantine | 67,790 |
| Valid trips | 6,382,152 |
| Missing month inside the observed date range | August 2017 |

The conflicting ride IDs have different timestamps, so the import quarantines every row with a conflicting ID and keeps the original database and CSVs intact. The analysis groups station observations by ID, name, and year. It keeps old and new IDs separate unless there is evidence they refer to the same station. The counts describe those groups. They do not establish how many physical stations exist. The analysis also flags shifts in endpoint coordinates.

## Reproduce

Python 3.10+:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Place the original CSVs in Dataset/; creates a NEW DB, refuses overwrite.
.\.venv\Scripts\python.exe analysis/ingest.py --output citibike_verified.duckdb
.\.venv\Scripts\python.exe analysis/build_portfolio.py --db citibike_verified.duckdb
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Source: [Citi Bike system data](https://citibikenyc.com/system-data) and [download archive](https://s3.amazonaws.com/tripdata/index.html). Download the Jersey City files. The ledger and missing-month checks apply to the files you supply, so the coverage may differ from the snapshot above. Check the source terms before reuse. The repository excludes the CSVs and databases.

The importer writes to a separate staging database and logs source counts, imported counts, and invalid fields for each file. It stops on malformed CSV rows and leaves a `.building.duckdb` file for diagnosis. After fixing the problem, choose a fresh output path. You can also export from the legacy `citibike.duckdb`. The export reports that file-level lineage is unavailable.

## Dashboard and decisions

The year selector updates trip counts, membership, median duration, growth for comparable years, and station observations. The station search filters the station table and coordinate plot only. The plot uses longitude and latitude and omits flagged coordinate shifts. You can download the filtered table.

Use the difference between departures and arrivals to decide which sites to look into. Before moving bikes or changing capacity, check availability, capacity, rebalancing, and weather. Trip records alone cannot show stockouts or unmet demand. The dashboard omits the previous, unvalidated recommendations for new stations.

## Historical assets

`analysis/setup_database.py`, `run_analysis.py`, `export_dashboard_data.py`, `sql_queries.sql`, `station_recommendations.py` and old `dashboard/data/` files are historical exploration. Run `ingest.py` and then `build_portfolio.py` to produce `dashboard/audited/` and `dashboard/index.html`. Use those outputs for operational review. The older exports and station recommendations are exploratory.

The dashboard compares full years only when both have observations in all 12 months from January through December. That excludes 2015, 2017, and 2026. Even with observations in all 12 months, the source can still be incomplete.

## Repeatable verification

Review the commands in `ai-toolkit.json`, then run `python scripts/verify.py` in the project’s Python environment. The script checks local documentation links and runs those commands without a shell. It saves the results in `.verification/latest.json`, which Git ignores. Dashboard JavaScript and filter checks require Node.js on PATH. The local checks do not cover browser behavior, deployment, or live services. See AGENTS.md and CLAUDE.md for the project workflows.
