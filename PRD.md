# Product Requirements — Citi Bike Operations Analysis

Updated 2026-11-15. Status: strict import, verified aggregates and offline operations dashboard implemented.

## Problem and user

An operations analyst needs consistent trip trends and station-observation imbalance without misleading partial-year comparisons, silent CSV loss or unverified station merging.

## Requirements and acceptance

| Requirement | Acceptance criterion |
| --- | --- |
| Strict accounted ingestion | Every parsed source row imported and counted by file; malformed CSV fails; original DB never overwritten |
| Explicit duplicate treatment | Exact duplicates removed; all conflicting/null ID rows quarantined with counts |
| Stable endpoint grain | ID + name + year; latest annual coordinates and displacement flag; missing identities reported |
| Time-aware metrics | Gaps visible; no YoY unless both years have observed Jan–Dec coverage |
| Reconciled exports | Year/month/hour totals equal clean trips; station endpoints reconcile |
| Working dashboard | Year filter, station search, trip trends, coordinate plot, imbalance table, CSV download, offline embedded data |
| Portfolio clarity | README, PRD, methodology, audit manifest, preview image and GitHub About |
| Meaningful verification | Small fixtures test conflicting IDs, missing months, station identity and importer schemas; real-data reconciliation run |

## Verified snapshot

127 CSV files; 6,449,990 raw rows; 48 rows quarantined across 24 conflicting IDs; 67,790 duration/time exclusions; 6,382,152 valid trips. Missing August 2017. Per-file diagnostics are in dashboard/audited/audit.json. Original CSVs and source database remain local and unchanged.

## Constraints and exclusions

No raw trip exports in Git. No live bike-availability feed, station capacity or counterfactual demand model. No validated new-station location claims. Coordinate scatter is not a street map. Historical scripts/data retained but superseded by the verified pipeline. Full observed months do not prove upstream source completeness.

## Next steps

Review flagged station observations against official station metadata; obtain capacity, availability, service-area polygons and rebalancing logs before making deployment/expansion recommendations. Restore missing source periods when available and rebuild, preserving provenance.
