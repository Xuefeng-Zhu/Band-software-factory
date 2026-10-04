import sys,json,datetime
from pathlib import Path
E=Path(__file__).parent;sys.path.insert(0,'/private/tmp/qa-s1-20261004T2218Z/tests')
from qa_stage1_boundaries import Suite,http,fixture
s=Suite(*json.loads((E/'endpoints.json').read_text()));s.reset();out=[]
for day in ['2000-02-29','2400-02-29','0001-01-01','9999-12-31','1900-02-29','2100-02-29','0000-01-01','2026-04-31']:
 status,body=http(s.base,'GET','/availability?restaurant_id=r&date='+day+'&party_size=2');out.append({'date':day,'status':status,'code':body.get('error',{}).get('code'),'slots':len(body.get('slots',[]))})
status,body=http(s.base,'GET','/availability?restaurant_id=r&date=2096-09-24&party_size='+('9'*5000));out.append({'case':'5000 decimal digits','status':status,'code':body.get('error',{}).get('code')})
(E/'calendar-diagnosis.json').write_text(json.dumps({'candidate':'68afbf86127ae9b2b5dc8ecc56a0e9c78e6a69f1','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'results':out},indent=2));print(json.dumps(out))
