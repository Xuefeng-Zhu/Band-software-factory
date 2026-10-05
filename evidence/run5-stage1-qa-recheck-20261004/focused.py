"""Requirement-derived black-box boundary assertions; no product source imports."""
import sys,json,datetime,urllib.parse,time,traceback
from pathlib import Path
E=Path(__file__).parent;C=Path('/private/tmp/qa-s1-recheck-20261004T2244Z');sys.path.insert(0,str(C/'tests'))
from qa_stage1_boundaries import Suite,http,fixture,FUTURE
s=Suite(*json.loads((E/'endpoints.json').read_text()));results=[]
TIMES=['18:00','18:30','19:00','19:30','20:00','20:30','21:00','21:30']

def assert_slots(value,day,times,tables,offset='+00:00'):
 assert value['restaurant_id']=='r' and value['date']==day
 slots=value['slots'];assert len(slots)==len(times)
 assert [v['starts_at_local'] for v in slots]==[day+'T'+t for t in times]
 assert [v['available_table_ids'] for v in slots]==[tables]*len(times)
 if offset:
  assert [v['starts_at'] for v in slots]==[day+'T'+t+':00'+offset for t in times]

def date_max():
 original=json.loads(Path('/Users/frank/mygit/Tablekeeper/result-run-5/.evidence/qa-s1-20261004T2218Z/repro-fixture.json').read_text());s.reset(original)
 value=s.availability('9999-12-31');assert_slots(value,'9999-12-31',TIMES,['r-a','r-b'])
 r=s.expect(s.create(s.body(starts_at_local='9999-12-31T21:30')),201)
 assert r['starts_at']=='9999-12-31T21:30:00+00:00' and r['ends_at']=='9999-12-31T23:00:00+00:00'
 s.expect(s.create(s.body(starts_at_local='9999-12-31T22:30')),422,'outside_opening_hours')
 return {'defect':'QA-S1-DATE-MAX','disposition':'CLOSED','query_status':200,'times':TIMES,'available_table_ids':['r-a','r-b'],'last_fit_status':201,'last_fit_end':'9999-12-31T23:00:00+00:00','late_status':422,'late_code':'outside_opening_hours'}

def decimal_queries():
 s.reset()
 for raw,tables in [('9'*5000,[]),('0'*5000+'2',['r-a','r-b']),('0'*5000+'4',['r-b']),('0'*5000+'5',[]),('1',['r-a','r-b']),('2',['r-a','r-b']),('3',['r-b']),('4',['r-b']),('5',[])]:
  q=urllib.parse.urlencode({'restaurant_id':'r','date':FUTURE,'party_size':raw})
  value=s.expect(http(s.base,'GET','/availability?'+q),200);assert_slots(value,FUTURE,TIMES,tables)
 for raw in ['0','0'*5000,'-1','+4','4.0','1e9','',' 4','4 ','٤','４']:
  q=urllib.parse.urlencode({'restaurant_id':'r','date':FUTURE,'party_size':raw})
  s.expect(http(s.base,'GET','/availability?'+q),422,'validation_failed')
 return {'defect':'QA-S1-QUERY-DIGITS','disposition':'CLOSED','digits':5000,'status':200,'slots':8,'all_available_table_ids_empty':True,'leading_zeros_and_capacity_cases':8,'invalid_format_cases':11}

def calendar_neighbors():
 s.reset()
 for day in ['0001-01-01','0001-01-02','9999-12-30','9999-12-31','2000-02-29','2400-02-29']:
  assert_slots(s.availability(day),day,TIMES,['r-a','r-b'])
 for day in ['0000-01-01','10000-01-01','1900-02-29','2100-02-29','2026-04-31','2026-02-30']:
  q=urllib.parse.urlencode({'restaurant_id':'r','date':day,'party_size':'2'});s.expect(http(s.base,'GET','/availability?'+q),422,'validation_failed')
 return {'valid_neighbors':6,'invalid_neighbors':6}

def grid_and_duration():
 s.reset(fixture(opens='18:10',closes='22:10',grid=30,duration=90));expected=['18:10','18:40','19:10','19:40','20:10','20:40']
 assert_slots(s.availability(),FUTURE,expected,['r-a','r-b'])
 s.expect(s.create(s.body(starts_at_local=FUTURE+'T18:11')),422,'not_on_slot_grid')
 r=s.expect(s.create(s.body(starts_at_local=FUTURE+'T20:40')),201);assert r['ends_at']==FUTURE+'T22:10:00+00:00'
 for duration in [301,10**30]:
  s.reset(fixture(duration=duration));assert s.availability()['slots']==[]
  s.expect(s.create(),422,'outside_opening_hours')
 return {'offset_grid_slots':expected,'duration_beyond_opening_and_timedelta':'PASS'}

def dst_closing():
 data=[]
 for zone,day,clock,start_offset,end_clock,end_offset,times in [
  ('Europe/Berlin','2026-03-29','01:30','+01:00','04:00','+02:00',['00:00','00:30','01:00','01:30']),
  ('America/New_York','2026-03-08','01:30','-05:00','04:00','-04:00',['00:00','00:30','01:00','01:30']),
  ('Europe/Berlin','2026-10-25','02:30','+02:00','03:00','+01:00',['00:00','00:30','01:00','01:30','02:00','02:30']),
  ('America/New_York','2026-11-01','02:30','-05:00','04:00','-05:00',['00:00','00:30','01:00','01:30','02:00','02:30'])]:
  s.reset(fixture(zone=zone,opens='00:00',closes='04:00',duration=90));value=s.availability(day);assert_slots(value,day,times,['r-a','r-b'],offset=None)
  r=s.expect(s.create(s.body(starts_at_local=day+'T'+clock)),201)
  assert r['starts_at']==day+'T'+clock+':00'+start_offset and r['ends_at']==day+'T'+end_clock+':00'+end_offset
  start=datetime.datetime.fromisoformat(r['starts_at']);end=datetime.datetime.fromisoformat(r['ends_at']);assert (end-start).total_seconds()==5400
  s.expect(s.create(s.body(starts_at_local=day+'T03:00',table_id='r-b')),422,'outside_opening_hours')
  if '03-' in day:
   s.expect(s.create(s.body(starts_at_local=day+'T02:30',table_id='r-b')),422,'invalid_local_time')
  data.append({'zone':zone,'date':day,'expected_slots':times,'observed_slots':[v['starts_at_local'][-5:] for v in value['slots']],'elapsed_seconds':5400})
 return data

for name in ['date_max','decimal_queries','calendar_neighbors','grid_and_duration','dst_closing']:
 start=time.monotonic()
 try:r={'name':name,'status':'PASS','observed':globals()[name]()}
 except Exception as e:r={'name':name,'status':'FAIL','detail':type(e).__name__+': '+str(e),'trace':traceback.format_exc()}
 r['elapsed_seconds']=time.monotonic()-start;results.append(r);print(name,r['status'],flush=True)
 (E/'focused-results.json').write_text(json.dumps({'work_item':'QA-S1-RECHECK','candidate':'4026ec71ac6cf5ae0ebe6e998d77fd4a475a8c4d','layer':'real host HTTP','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'results':results},indent=2))
sys.exit(any(r['status']!='PASS' for r in results))
