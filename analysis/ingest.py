"""Strict, accounted CSV ingestion. Creates a NEW database; never overwrites an existing one."""
import argparse,csv
from contextlib import closing
from pathlib import Path
import duckdb

ROOT=Path(__file__).resolve().parent.parent

def ingest(source,output):
    files=sorted(Path(source).glob('*.csv'))
    if not files: raise ValueError('No CSV files found')
    output=Path(output)
    if output.exists(): raise FileExistsError('Refusing to overwrite '+str(output))
    stage=output.with_name(output.stem+'.building.duckdb')
    if stage.exists(): raise FileExistsError('Staging database already exists: '+str(stage))
    with closing(duckdb.connect(str(stage))) as con:
        con.execute("""CREATE TABLE trips(ride_id VARCHAR,bike_type VARCHAR,started_at TIMESTAMP,ended_at TIMESTAMP,
            duration_sec BIGINT,start_station_name VARCHAR,start_station_id VARCHAR,end_station_name VARCHAR,
            end_station_id VARCHAR,start_lat DOUBLE,start_lng DOUBLE,end_lat DOUBLE,end_lng DOUBLE,user_type VARCHAR)""")
        con.execute('CREATE TABLE ingestion_manifest(filename VARCHAR, schema_version VARCHAR, source_rows BIGINT, imported_rows BIGINT, invalid_times BIGINT, invalid_durations BIGINT, missing_coordinates BIGINT)')
        for path in files:
            con.execute('CREATE OR REPLACE TEMP TABLE input_csv AS SELECT * FROM read_csv(?,header=true,all_varchar=true,strict_mode=true,ignore_errors=false)',[str(path)])
            names=[r[0] for r in con.execute('DESCRIBE input_csv').fetchall()]
            normalized={n.strip().lower().replace(' ','_'):n for n in names}
            def col(*options):
                name=next((normalized[o] for o in options if o in normalized),None)
                if name is None: raise ValueError(f'{path.name}: missing column {options}')
                return '"'+name.replace('"','""')+'"'
            new='ride_id' in normalized
            if new:
                ident=col('ride_id');bike=col('rideable_type');start=col('started_at');end=col('ended_at')
                duration=f'date_diff(\'second\',TRY_CAST({start} AS TIMESTAMP),TRY_CAST({end} AS TIMESTAMP))'
                user=col('member_casual')
            else:
                safe=path.name.replace("'","''")
                ident=f"ROW_NUMBER() OVER () || '_{safe}'";bike="'classic_bike'"
                start=col('starttime','start_time');end=col('stoptime','stop_time');duration=f'TRY_CAST({col("tripduration","trip_duration")} AS BIGINT)'
                user=f"CASE WHEN lower({col('usertype','user_type')})='subscriber' THEN 'member' WHEN lower({col('usertype','user_type')})='customer' THEN 'casual' ELSE 'unknown' END"
            fields=[ident,bike,f'TRY_CAST({start} AS TIMESTAMP)',f'TRY_CAST({end} AS TIMESTAMP)',duration,
                col('start_station_name'),col('start_station_id'),col('end_station_name'),col('end_station_id'),
                f'TRY_CAST({col("start_lat","start_station_latitude")} AS DOUBLE)',
                f'TRY_CAST({col("start_lng","start_station_longitude")} AS DOUBLE)',
                f'TRY_CAST({col("end_lat","end_station_latitude")} AS DOUBLE)',
                f'TRY_CAST({col("end_lng","end_station_longitude")} AS DOUBLE)',user]
            aliases=['ride_id','bike_type','started_at','ended_at','duration_sec','start_station_name','start_station_id','end_station_name','end_station_id','start_lat','start_lng','end_lat','end_lng','user_type']
            con.execute('CREATE OR REPLACE TEMP TABLE batch AS SELECT '+','.join(f'{expression} AS {name}' for expression,name in zip(fields,aliases))+' FROM input_csv')
            con.execute('INSERT INTO trips SELECT * FROM batch')
            source_count=con.execute('SELECT COUNT(*) FROM input_csv').fetchone()[0]
            values=con.execute('SELECT COUNT(*),COUNT(*) FILTER(WHERE started_at IS NULL OR ended_at IS NULL OR ended_at<started_at),COUNT(*) FILTER(WHERE duration_sec IS NULL OR duration_sec NOT BETWEEN 60 AND 86400),COUNT(*) FILTER(WHERE start_lat IS NULL OR start_lng IS NULL OR end_lat IS NULL OR end_lng IS NULL) FROM batch').fetchone()
            if source_count!=values[0]: raise ValueError('Source/import mismatch: '+path.name)
            con.execute('INSERT INTO ingestion_manifest VALUES (?,?,?,?,?,?,?)',[path.name,'new' if new else 'old',source_count,*values])
            print(path.name,source_count)
        count=con.execute('SELECT COUNT(*) FROM trips').fetchone()[0]
        if count!=con.execute('SELECT SUM(imported_rows) FROM ingestion_manifest').fetchone()[0]:raise ValueError('Manifest does not reconcile')
    stage.rename(output)
    return count

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',default=str(ROOT/'Dataset'));p.add_argument('--output',default=str(ROOT/'citibike_rebuilt.duckdb'))
    a=p.parse_args();print('Imported rows:',ingest(a.source,a.output))
