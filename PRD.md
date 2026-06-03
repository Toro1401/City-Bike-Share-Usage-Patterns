# Product Requirements Document (PRD)
## City Bike-Share Usage Patterns Analysis

**Version:** 1.0  
**Date:** June 2026  
**Author:** Data Analytics Team  
**Status:** Active

---

## 1. Executive Summary

This project analyzes Citi Bike trip data for Jersey City, NJ to identify temporal and geographic usage patterns, evaluate station performance, and recommend optimal locations for new bike-share stations. The analysis spans **10+ years** of trip records (September 2015 – April 2026), comprising **127 monthly datasets totaling ~1.2 GB** of trip-level data.

The deliverables include SQL-based analytical queries, static and interactive geographic visualizations, and data-driven recommendations for infrastructure expansion.

---

## 2. Business Context & Problem Statement

### 2.1 Background

Citi Bike operates the largest bike-share system in the United States. Jersey City's system has grown significantly since its 2015 launch, yet station placement decisions have historically relied on limited data analysis. As urban mobility demand shifts post-pandemic with the introduction of electric bikes and changing commuter patterns, the city needs a data-driven framework to:

- Understand **when** demand peaks occur (hourly, daily, seasonal)
- Identify **where** trip activity concentrates geographically
- Detect **underserved areas** that would benefit from new stations
- Optimize **rebalancing operations** by understanding station flow imbalances

### 2.2 Business Questions

| # | Question | Stakeholder |
|---|----------|-------------|
| 1 | When are bike-share trips most concentrated? | City Planners, Citi Bike Operations |
| 2 | Which stations handle the most traffic? | Citi Bike Operations, Maintenance |
| 3 | What are the most popular routes? | Urban Transit Planning |
| 4 | Where should the city add new stations? | City Council, Capital Planning |
| 5 | How has usage evolved over the years? | Executive Leadership, Budget Teams |
| 6 | How do member vs. casual riders differ in behavior? | Marketing, Membership Strategy |

---

## 3. Stakeholders

| Stakeholder | Role | Interest |
|-------------|------|----------|
| City of Jersey City — Transportation Dept. | Primary consumer | Station placement, infrastructure planning |
| Citi Bike / Lyft Operations | System operator | Rebalancing, maintenance scheduling, capacity planning |
| Urban Transit Authority | Policy maker | Multi-modal transit integration |
| City Council | Decision authority | Budget allocation for new stations |
| Community Residents | End users | Access to bike-share near homes/workplaces |

---

## 4. Goals & Success Metrics

### 4.1 Project Goals

1. **Quantify temporal demand patterns** — identify peak hours, days, and months with statistical rigor
2. **Map geographic trip density** — visualize station-level activity on an interactive map
3. **Identify high-demand corridors** — discover the most-traveled routes
4. **Detect station imbalances** — find stations that consistently gain or lose bikes
5. **Recommend 5–10 new station locations** — backed by demand data and gap analysis
6. **Demonstrate large-scale data handling** — process 1.2GB across 127 files efficiently

### 4.2 Success Metrics

| Metric | Target |
|--------|--------|
| Total trip records processed | 100% of available data (all 127 files) |
| SQL queries covering business questions | ≥ 10 distinct analytical queries |
| Geographic visualization completeness | All stations with lat/lng mapped |
| Recommendation confidence | Each recommendation backed by ≥ 2 data signals |
| Dashboard load time | < 3 seconds on modern browser |
| Analysis reproducibility | Single-command pipeline execution |

---

## 5. Scope

### 5.1 In Scope

| Area | Details |
|------|---------|
| **Data** | All 127 JC Citi Bike CSV files (Sep 2015 – Apr 2026) |
| **Schema Unification** | Merge old format (2015–2021-01) and new format (2021-02+) into unified schema |
| **SQL Analysis** | Peak usage, popular routes, station utilization, user type breakdown, year-over-year trends |
| **Static Visualizations** | Matplotlib/Seaborn charts (heatmaps, bar charts, line charts, distributions) |
| **Interactive Dashboard** | Leaflet.js map with station bubbles, route flows, filters, KPI cards |
| **Station Recommendations** | Data-driven suggestions for 5–10 new station locations |
| **PRD** | This document |

### 5.2 Out of Scope

| Area | Reason |
|------|--------|
| Full NYC (Manhattan, Brooklyn, etc.) data | Not in dataset — JC only |
| Real-time data feeds | Project uses historical batch data |
| Predictive forecasting models | Focus is descriptive/diagnostic analytics |
| Mobile app development | Dashboard is web-only |
| Tableau/Power BI files | Using open-source web stack instead |
| Revenue/financial analysis | Trip data doesn't include pricing |

---

## 6. Data Requirements

### 6.1 Data Source

**Citi Bike System Data** — publicly available at `s3.amazonaws.com/tripdata`

### 6.2 Schema (Unified)

| Column | Type | Source (Old) | Source (New) |
|--------|------|-------------|-------------|
| `ride_id` | VARCHAR | Generated from row index | `ride_id` |
| `bike_type` | VARCHAR | "classic_bike" (default) | `rideable_type` |
| `started_at` | TIMESTAMP | `starttime` | `started_at` |
| `ended_at` | TIMESTAMP | `stoptime` | `ended_at` |
| `duration_sec` | INTEGER | `tripduration` | Computed: `ended_at - started_at` |
| `start_station_name` | VARCHAR | `Start Station Name` | `start_station_name` |
| `start_station_id` | VARCHAR | `Start Station ID` | `start_station_id` |
| `end_station_name` | VARCHAR | `End Station Name` | `end_station_name` |
| `end_station_id` | VARCHAR | `End Station ID` | `end_station_id` |
| `start_lat` | DOUBLE | `Start Station Latitude` | `start_lat` |
| `start_lng` | DOUBLE | `Start Station Longitude` | `start_lng` |
| `end_lat` | DOUBLE | `End Station Latitude` | `end_lat` |
| `end_lng` | DOUBLE | `End Station Longitude` | `end_lng` |
| `user_type` | VARCHAR | `usertype` → mapped | `member_casual` |

### 6.3 Data Quality Considerations

- **Missing coordinates**: Some trips may have null lat/lng — exclude from geo analysis
- **Outlier durations**: Trips < 60s (likely false starts) or > 24h (likely unreturned bikes) — filter
- **Station ID inconsistency**: Old format uses numeric IDs, new format uses alphanumeric — use station name + coordinates as primary key
- **Schema break**: Column names/types change at Feb 2021 boundary — handle in ETL

---

## 7. Deliverable Specifications

### 7.1 SQL Analysis (`analysis/`)

| File | Purpose |
|------|---------|
| `setup_database.py` | Load all CSVs into DuckDB with unified schema |
| `sql_queries.sql` | All analytical SQL queries with comments |
| `run_analysis.py` | Execute queries, export results as CSV + charts |
| `results/*.csv` | Query output tables |
| `charts/*.png` | Static visualizations |

**Query Categories:**
1. Temporal patterns (hourly, daily, monthly, yearly)
2. Route analysis (top routes, avg duration, user type split)
3. Station performance (busiest, net flow, utilization trends)
4. User segmentation (member vs casual, bike type preferences)

### 7.2 Geographic Visualization (`dashboard/`)

| File | Purpose |
|------|---------|
| `index.html` | Main dashboard page |
| `index.css` | Styling (dark mode, glassmorphism) |
| `app.js` | Map logic, chart rendering, interactivity |
| `data/*.json` | Pre-aggregated data from Python analysis |

**Map Layers:**
1. **Station Bubbles** — sized by total trips, colored by utilization intensity
2. **Route Flows** — animated lines for top station-to-station pairs
3. **Recommendation Markers** — proposed new station locations

**Dashboard Components:**
- KPI summary cards (total trips, stations, avg duration, growth)
- Year/month filter controls
- Hourly usage heatmap
- Top stations ranked list
- Member vs casual breakdown

### 7.3 Station Recommendations

**Methodology:**
1. High-demand corridor detection (frequent long-distance routes)
2. Geographic gap analysis (Voronoi-style coverage gaps)
3. Trip endpoint clustering (K-means on trip start/end coordinates not near stations)
4. Multi-signal scoring: demand density × distance-to-nearest-station × flow imbalance

**Output:** 5–10 ranked locations with:
- Lat/lng coordinates
- Estimated daily trip potential
- Supporting data signals
- Narrative rationale

---

## 8. Technical Architecture

```
Dataset/ (127 CSVs, 1.2 GB)
    │
    ▼
setup_database.py ──► citibike.duckdb (unified schema)
    │
    ▼
sql_queries.sql ◄── run_analysis.py ──► results/*.csv + charts/*.png
    │
    ▼
station_recommendations.py ──► recommendations data
    │
    ▼
export_dashboard_data.py ──► dashboard/data/*.json
    │
    ▼
dashboard/ (index.html + index.css + app.js)
    └──► Interactive web dashboard (open in browser)
```

**Technology Stack:**

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| SQL Engine | DuckDB | Columnar, reads CSVs directly, fast on 1.2GB |
| Data Processing | Python 3.14 + pandas | Schema unification, data transformation |
| Static Charts | matplotlib + seaborn | Publication-quality charts |
| Interactive Maps | Leaflet.js + OpenStreetMap | Open-source, no API key needed |
| Dashboard UI | HTML5 + CSS3 + vanilla JS | No build step, premium design |
| Charts in Dashboard | Chart.js | Lightweight, responsive charts |

---

## 9. Timeline

| Phase | Deliverable | Duration |
|-------|-------------|----------|
| 1 | PRD | ✅ Complete |
| 2 | Data Pipeline + SQL Analysis | ~30 min |
| 3 | Interactive Dashboard | ~30 min |
| 4 | Station Recommendations | ~15 min |
| — | Verification & Polish | ~15 min |

---

## 10. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Schema inconsistency across years | Data loss in union | Medium | Explicit column mapping with fallbacks |
| Missing lat/lng on some trips | Gaps in geo viz | Low | Exclude from geo analysis, note in findings |
| DuckDB memory on 1.2GB | Slow queries | Low | DuckDB handles this natively; can sample if needed |
| Station ID changes over time | Duplicate stations | Medium | Use name + coordinates as composite key |
| Browser performance with many map markers | Slow dashboard | Medium | Pre-aggregate to station level, use clustering |

---

## 11. Appendix

### A. Data File Naming Convention

- **Old format**: `JC-YYYYMM-citibike-tripdata.csv`
- **New format**: Same pattern, one typo file (`JC-202207-citbike-tripdata.csv` — missing 'i')

### B. Geographic Bounds (Jersey City)

- Latitude: ~40.69 to ~40.77
- Longitude: ~-74.10 to ~-74.02
- Neighboring coverage: Hoboken stations included in JC data

### C. Glossary

| Term | Definition |
|------|-----------|
| **Member** | Annual Citi Bike subscriber |
| **Casual** | Single-ride or day-pass user |
| **Net flow** | Departures minus arrivals at a station (positive = net exporter) |
| **Rebalancing** | Physical redistribution of bikes between stations |
| **Docking station** | Physical bike rack with fixed number of docks |
