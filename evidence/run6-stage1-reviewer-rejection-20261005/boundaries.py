import datetime as dt
import json
import time
import urllib.request
import urllib.error

results=[]
start=dt.datetime.now(dt.timezone.utc).isoformat()
token=None
def call(method,path,body=None,key=None):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    if key:headers['Idempotency-Key']=key
    req=urllib.request.Request('http://127.0.0.1:8080'+path,data=None if body is None else json.dumps(body).encode(),headers=headers,method=method)
    try:r=urllib.request.urlopen(req,timeout=10 if path.startswith('/_test/') else 5)
    except urllib.error.HTTPError as e:r=e
    with r:
        raw=r.read();return r.status,json.loads(raw) if raw else None
def fixture(zone='UTC',opening='18:00',closing='20:00',grid=30,duration=60):
    return {'users':[{'id':'u','email':'review@example.invalid','password':'synthetic-review-only','display_name':'Review'}],
        'restaurants':[{'id':'r','name':'Room','timezone':zone,'slot_minutes':grid,'reservation_duration_minutes':duration,'cancellation_cutoff_minutes':0,
        'opening_hours':[{'weekday':day,'opens':opening,'closes':closing} for day in ['mon','tue','wed','thu','fri','sat','sun']],
        'tables':[{'id':'t','label':'Window','capacity':4}]}],'reservations':[]}
def reset(f):
    global token
    token=None;assert call('POST','/_test/reset',f)[0]==204
    status,response=call('POST','/auth/login',{'email':'review@example.invalid','password':'synthetic-review-only'});assert status==200;token=response['token']
def booking(date,clock='18:00'):
    return {'restaurant_id':'r','table_id':'t','starts_at_local':date+'T'+clock,'party_size':2}
def emit(name,ok,detail):results.append({'name':name,'status':'PASS' if ok else 'FAIL','detail':detail})

for year in ['2030','1000','0999','0001']:
    reset(fixture())
    date=year+'-06-01'
    status,response=call('GET','/availability?restaurant_id=r&date='+date+'&party_size=2')
    got=[s['starts_at_local'] for s in response.get('slots',[])]
    expected=[date+'T'+t for t in ['18:00','18:30','19:00']]
    create_status,record=call('POST','/reservations',booking(date),'year-'+year)
    emit('calendar_year_'+year,status==200 and got==expected and create_status==201,{'expected_starts':expected,'observed_starts':got,'availability_status':status,'create_status':create_status,'created_local':record.get('starts_at_local'),'scope':'real HTTP in constrained network-none Python3.12 container'})

reset(fixture('Europe/Berlin','02:10','04:10',20,40))
status,response=call('GET','/availability?restaurant_id=r&date=2026-03-29&party_size=2')
observed=[s['starts_at_local'] for s in response['slots']]
expected=['2026-03-29T03:10','2026-03-29T03:30']
emit('new_gap_grid_duration',status==200 and observed==expected,{'expected':expected,'observed':observed})

reset(fixture())
created=[]
for day in range(1,9):
    status,res=call('POST','/reservations',booking('2030-06-'+str(day).zfill(2)),'batch'+str(day));assert status==201;created.append(res)
move_body={'moves':[{'reference':r['reference']} for r in reversed(created)]}
status,response=call('POST','/reservation-moves',move_body,'eight')
replay_status,replay=call('POST','/reservation-moves',move_body,'eight')
emit('eight_item_noop_batch',status==201 and replay_status==200 and response==replay and response['reservations']==list(reversed(created)),{'count':len(response.get('reservations',[])),'first_status':status,'replay_status':replay_status})

record={'work_item':'S1-GATE','candidate_commit':'7960081554f92cbe1a61d377b8dfd651ae90487b','reviewer':'@frankzhu94/factory-reviewer','started_at_utc':start,'finished_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'layer':'actual HTTP inside network-none2CPU2GiB container','results':results}
with open('/tmp/reviewer-boundaries.json','x') as f:json.dump(record,f,indent=2)
print(json.dumps({'checks':len(results),'failures':[r['name'] for r in results if r['status']=='FAIL']}))
raise SystemExit(int(any(r['status']=='FAIL' for r in results)))
