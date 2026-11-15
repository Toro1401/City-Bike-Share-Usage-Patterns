"""Audit the source database and build an aggregate-only operations dashboard."""
import argparse
from contextlib import closing
import csv,json
from decimal import Decimal
from pathlib import Path
import duckdb
from dashboard_template import render

ROOT=Path(__file__).resolve().parent.parent

def export(db,output):
    with closing(duckdb.connect(str(db),read_only=True)) as con:
        def rows(sql):
            cur=con.execute(sql);names=[d[0] for d in cur.description]
            return [dict(zip(names,(float(v) if isinstance(v,Decimal) else v for v in row))) for row in cur.fetchall()]
        raw_count=con.execute('SELECT COUNT(*) FROM trips').fetchone()[0]
        con.execute('CREATE TEMP VIEW distinct_trips AS SELECT DISTINCT * FROM trips')
        unique_count=con.execute('SELECT COUNT(*) FROM distinct_trips').fetchone()[0]
        conflicts=con.execute('SELECT COUNT(*) FROM (SELECT ride_id FROM distinct_trips WHERE ride_id IS NOT NULL GROUP BY ride_id HAVING COUNT(*)>1)').fetchone()[0]
        con.execute('CREATE TEMP VIEW unambiguous_trips AS SELECT * FROM distinct_trips WHERE ride_id IS NOT NULL AND ride_id NOT IN (SELECT ride_id FROM distinct_trips WHERE ride_id IS NOT NULL GROUP BY ride_id HAVING COUNT(*)>1)')
        unambiguous_count=con.execute('SELECT COUNT(*) FROM unambiguous_trips').fetchone()[0]
        con.execute("CREATE TEMP VIEW clean_trips AS SELECT * FROM unambiguous_trips WHERE duration_sec BETWEEN 60 AND 86400 AND started_at IS NOT NULL AND ended_at>=started_at")
        valid=con.execute('SELECT COUNT(*) FROM clean_trips').fetchone()[0]
        if not valid: raise ValueError('No valid trips remain after quality exclusions')
        con.execute("""CREATE TEMP VIEW endpoints AS
            SELECT year(started_at) AS yr,start_station_id station_id,start_station_name name,start_lat lat,start_lng lng,started_at observed_at,1 dep,0 arr FROM clean_trips
            UNION ALL SELECT year(started_at),end_station_id,end_station_name,end_lat,end_lng,ended_at,0,1 FROM clean_trips""")
        text=(ROOT/'analysis/audited_queries.sql').read_text(encoding='utf-8')
        queries={part.splitlines()[0].strip():'\n'.join(part.splitlines()[1:]).strip() for part in text.split('-- name: ')[1:]}
        data={name:rows(sql) for name,sql in queries.items()}
        missing=[]
        observed={(r['yr'],r['mon']) for r in data['monthly']}
        first=min(observed);last=max(observed)
        for yr in range(first[0],last[0]+1):
            for mon in range(1,13):
                if first<=(yr,mon)<=last and (yr,mon) not in observed:missing.append(f'{yr}-{mon:02}')
        endpoint_count=con.execute('SELECT COUNT(*) FROM endpoints WHERE station_id IS NOT NULL AND name IS NOT NULL').fetchone()[0]
        station_sum=sum(r['departures']+r['arrivals'] for r in data['stations'])
        if sum(r['trips'] for r in data['yearly'])!=valid or sum(r['trips'] for r in data['monthly'])!=valid or sum(r['trips'] for r in data['hourly'])!=valid or endpoint_count!=station_sum:
            raise ValueError('Aggregate reconciliation failed')
        missing_endpoints=2*valid-endpoint_count
        moved=sum(1 for r in data['stations'] if (r['lat_span'] or 0)>.005 or (r['lng_span'] or 0)>.005)
        audit=dict(raw_rows=raw_count,exact_duplicates_removed=raw_count-unique_count,
            quarantined_ambiguous_or_null_id_rows=unique_count-unambiguous_count,excluded_duration_or_time=unambiguous_count-valid,valid_trips=valid,
            conflicting_ride_ids=conflicts,missing_months=missing,
            missing_id_or_name_endpoints=missing_endpoints,station_year_coordinate_flags=moved,
            historical_station_observations=len(data['stations']),
            provenance='Existing database: per-file import lineage is unavailable. Rebuild with ingest.py for strict per-file accounting.',
            checks='Year/month/hour counts reconcile to valid trips; station endpoint counts reconcile to nonmissing IDs and names.')
        tables={r[0] for r in con.execute('SHOW TABLES').fetchall()}
        if 'ingestion_manifest' in tables:
            audit['ingestion_manifest']=rows('SELECT * FROM ingestion_manifest ORDER BY filename')
            audit['provenance']='Strict CSV import: all source records accounted for in ingestion_manifest; no malformed CSV records silently skipped.'
        data['audit']=audit
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    for name,records in data.items():
        (output/(name+'.json')).write_text(json.dumps(records,indent=2),encoding='utf-8')
        if isinstance(records,list) and records:
            with (output/(name+'.csv')).open('w',encoding='utf-8',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    render('bike',data,output.parent/'index.html')
    return audit

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--db',default=str(ROOT/'citibike.duckdb'));p.add_argument('--output',default=str(ROOT/'dashboard/audited'))
    args=p.parse_args();print(json.dumps(export(args.db,args.output),indent=2))
