import sys,json,datetime,urllib.parse
from pathlib import Path
sys.path.insert(0,'tests')
from qa_stage1_boundaries import http,fixture
base=sys.argv[1]; revision=sys.argv[2]; output=Path(sys.argv[3]);start=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert not output.exists()
assert http(base,'POST','/_test/reset',fixture())[0]==204
results=[]
for label,day,party in [('QA-S1-DATE-MAX','9999-12-31','2'),('QA-S1-QUERY-DIGITS','2096-09-24','9'*5000)]:
 status,body=http(base,'GET','/availability?'+urllib.parse.urlencode(dict(restaurant_id='r',date=day,party_size=party)))
 results.append(dict(defect=label,observed_status=status,error=body.get('error',{}).get('code'),slot_count=len(body.get('slots',[])),local_labels=[s['starts_at_local'] for s in body.get('slots',[])],tables=[s['available_table_ids'] for s in body.get('slots',[])],expected_status=200))
output.write_text(json.dumps(dict(work_item='BUILD-S1-REPAIR2',owner='@frankzhu94/factory-backend',revision=revision,start=start,end=datetime.datetime.now(datetime.timezone.utc).isoformat(),results=results),indent=2))
print([(x['defect'],x['observed_status'],x['slot_count']) for x in results])
