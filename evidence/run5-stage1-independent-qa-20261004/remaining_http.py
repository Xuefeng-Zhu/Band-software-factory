import sys,json,datetime
from pathlib import Path
E=Path(__file__).parent;sys.path.insert(0,'/private/tmp/qa-s1-20261004T2218Z/tests')
from qa_stage1_boundaries import Suite,http,FUTURE
s=Suite(*json.loads((E/'endpoints.json').read_text()));s.reset();out=[]
def record(name,actual,expected):out.append({'case':name,'actual':actual,'expected':expected,'status':'PASS' if actual==expected else 'FAIL'})
for day in ['2000-02-29','2400-02-29','0001-01-01','9999-12-31']:
 status,_=s.create(s.body(starts_at_local=day+'T18:00'));record('create '+day,status,201)
s.reset();s.expect(s.create(),201);s.expect(s.create(s.body(table_id='r-b')),201);slots=s.availability()['slots'];record('fully occupied slots retained',(len(slots),slots[0]['available_table_ids']),(8,[]))
q='/availability?restaurant_id=r&date='+FUTURE+'&party_size=2&ignore=true';record('unknown query ignored',s.expect(http(s.base,'GET',q),200)==s.availability(),True)
(E/'remaining-http-results.json').write_text(json.dumps({'candidate':'68afbf86127ae9b2b5dc8ecc56a0e9c78e6a69f1','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'results':out},indent=2));print([(r['case'],r['status']) for r in out])
sys.exit(any(r['status']=='FAIL' for r in out))
