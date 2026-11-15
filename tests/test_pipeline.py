from pathlib import Path
import sys,tempfile,unittest,json
from contextlib import closing
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'analysis'))
import duckdb
from build_portfolio import export
from ingest import ingest

class BikeTests(unittest.TestCase):
    def test_old_new_schema_import_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source';source.mkdir();db=root/'test.duckdb'
            (source/'old.csv').write_text('tripduration,starttime,stoptime,start station name,start station id,end station name,end station id,start station latitude,start station longitude,end station latitude,end station longitude,usertype\n120,2017-01-01 12:00:00,2017-01-01 12:02:00,A,1,B,2,40.7,-74.0,40.71,-74.01,Subscriber\n')
            (source/'new.csv').write_text('ride_id,rideable_type,started_at,ended_at,start_station_name,start_station_id,end_station_name,end_station_id,start_lat,start_lng,end_lat,end_lng,member_casual\nr1,classic_bike,2017-03-01 12:00:00,2017-03-01 12:02:00,A,NEW,B,2,40.7,-74.0,40.71,-74.01,member\n')
            self.assertEqual(ingest(source,db),2)
            with self.assertRaises(FileExistsError):ingest(source,db)
            audit=export(db,root/'dashboard/audited')
            self.assertEqual(audit['valid_trips'],2)
            self.assertEqual(audit['missing_months'],['2017-02'])
            self.assertEqual(sum(r['source_rows'] for r in audit['ingestion_manifest']),2)
            stations=json.loads((root/'dashboard/audited/stations.json').read_text())
            self.assertEqual(len([r for r in stations if r['name']=='A']),2)

    def test_conflicting_ids_quarantined_not_arbitrarily_deduplicated(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);db=root/'test.duckdb'
            with closing(duckdb.connect(str(db))) as c:
                c.execute("""CREATE TABLE trips AS SELECT 'x' ride_id,'classic' bike_type,TIMESTAMP '2025-01-01 12:00:00' started_at,TIMESTAMP '2025-01-01 12:02:00' ended_at,120 duration_sec,'A' start_station_name,'1' start_station_id,'B' end_station_name,'2' end_station_id,40.7 start_lat,-74.0 start_lng,40.71 end_lat,-74.01 end_lng,'member' user_type""")
                c.execute("INSERT INTO trips SELECT * REPLACE (TIMESTAMP '2025-01-02 12:00:00' AS started_at,TIMESTAMP '2025-01-02 12:02:00' AS ended_at) FROM trips")
                c.execute("INSERT INTO trips SELECT * REPLACE ('good' AS ride_id) FROM trips LIMIT 1")
                c.execute("INSERT INTO trips SELECT * FROM trips WHERE ride_id='good'")
            audit=export(db,root/'dashboard/audited')
            self.assertEqual(audit['conflicting_ride_ids'],1)
            self.assertEqual(audit['quarantined_ambiguous_or_null_id_rows'],2)
            self.assertEqual(audit['exact_duplicates_removed'],1)
            self.assertEqual(audit['valid_trips'],1)

if __name__=='__main__':unittest.main()
