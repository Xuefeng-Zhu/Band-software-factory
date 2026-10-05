import os,sys,json,time,datetime,subprocess,urllib.parse
from pathlib import Path
ROOT=Path('/Users/frank/mygit/Tablekeeper/result-run-5')
E=ROOT/'.evidence/backend-s1-repair2-20261004T2234Z'
P='/Users/frank/mygit/Tablekeeper/runs/harness-venv/bin/python'
REV='7e82648b4f4feb1c74015f9c551626ba3a36851c'
sys.path.insert(0,str(ROOT/'tests'))
from qa_stage1_boundaries import http,fixture,PASSWORD
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
record=dict(work_item='BUILD-S1-REPAIR2',owner='@frankzhu94/factory-backend',revision=REV,layer='host Python 3.13; no container resource/isolation claims',start=now(),commands=[],services=[],adjacent=[])
env=dict(os.environ,PYTHONPATH=str(ROOT/'stage-1'),PYTHONDONTWRITEBYTECODE='1')
processes=[];handles=[]
def run(argv,log,timeout=40):
 item=dict(argv=argv,cwd=str(ROOT),start=now())
 with (E/log).open('w') as output:
  result=subprocess.run(argv,cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,timeout=timeout)
 item.update(end=now(),exit_status=result.returncode,log=str(E/log));record['commands'].append(item)
 assert result.returncode==0,log
try:
 for port in [18280,18281]:
  handle=(E/('server-'+str(port)+'.log')).open('w'); handles.append(handle)
  argv=[P,'-m','tablekeeper.server'];proc=subprocess.Popen(argv,cwd=ROOT,env=dict(env,PORT=str(port)),stdout=handle,stderr=subprocess.STDOUT);processes.append(proc)
  record['services'].append(dict(argv=argv,port=port,pid=proc.pid,start=now(),source=str(ROOT/'stage-1')))
  for _ in range(100):
   try:
    if http('http://127.0.0.1:'+str(port),'GET','/health')[0]==200: break
   except OSError: time.sleep(.03)
  else: raise RuntimeError('Service failed to become healthy')
 base='http://127.0.0.1:18280'
 run([P,str(E/'reproduce.py'),base,REV,str(E/'after.json')],'after.log')
 after=json.loads((E/'after.json').read_text())['results']
 assert all(x['observed_status']==200 and x['slot_count']==8 for x in after)
 assert all(x==['r-a','r-b'] for x in after[0]['tables'])
 assert all(x==[] for x in after[1]['tables'])
 def availability(day,party): return http(base,'GET','/availability?'+urllib.parse.urlencode(dict(restaurant_id='r',date=day,party_size=party)))
 for day in ['0001-01-01','2000-02-29','2400-02-29','9999-12-30','9999-12-31']:
  status,b=availability(day,'2');assert status==200 and len(b['slots'])==8
  record['adjacent'].append(dict(kind='date',date=day,status=status,slots=len(b['slots'])))
 for day in ['0000-01-01','1900-02-29','2100-02-29','2096-04-31']:
  status,b=availability(day,'2');assert (status,b['error']['code'])==(422,'validation_failed')
  record['adjacent'].append(dict(kind='invalid_date',date=day,status=status))
 for label,party,tables in [('long-positive','9'*5000,[]),('long-leading-zero','0'*5000+'2',['r-a','r-b']),('long-leading-zero-four','0'*5000+'4',['r-b']),('ordinary-four','4',['r-b']),('ordinary-five','5',[])]:
  status,b=availability('2096-09-24',party);assert status==200 and len(b['slots'])==8 and all(s['available_table_ids']==tables for s in b['slots'])
  record['adjacent'].append(dict(kind='query',label=label,digits=len(party),status=status,slots=len(b['slots']),expected_tables=tables))
 for label,party in [('zero','0'),('long-zero','0'*5000),('empty',''),('sign','+4'),('negative','-4'),('decimal','4.0'),('exponent','4e0'),('arabic','٤'),('fullwidth','４')]:
  status,b=availability('2096-09-24',party);assert (status,b['error']['code'])==(422,'validation_failed')
  record['adjacent'].append(dict(kind='invalid_query',label=label,status=status))
 token=http(base,'POST','/auth/login',dict(email='alice@example.test',password=PASSWORD))[1]['token']
 body=dict(restaurant_id='r',table_id='r-a',party_size=2,starts_at_local='9999-12-31T21:30')
 status,b=http(base,'POST','/reservations',body,token,'date-boundary');assert status==201 and b['ends_at']=='9999-12-31T23:00:00+00:00'
 status,b=http(base,'POST','/reservations',dict(body,starts_at_local='9999-12-31T22:30'),token,'date-too-late');assert (status,b['error']['code'])==(422,'outside_opening_hours')
 record['adjacent'].append(dict(kind='create-at-date-boundary',valid_status=201,overflow_status=422,overflow_code='outside_opening_hours'))
 run([P,'-m','unittest','discover','-s','stage-1/tests','-v'],'unit-committed.log')
 run([P,'tests/qa_stage1_boundaries.py','--base-url',base,'--destination-url','http://127.0.0.1:18281','--revision',REV,'--out',str(E/'http-results.json')],'http-run.log')
 record['outcome']='PASS'
finally:
 for proc,service in zip(processes,record['services']):
  proc.terminate()
  try: proc.wait(timeout=5)
  except subprocess.TimeoutExpired: proc.kill();proc.wait(timeout=2)
  service.update(stopped_at=now(),exit_status=proc.returncode)
 for handle in handles: handle.close()
 record['end']=now();(E/'verification.json').write_text(json.dumps(record,indent=2))
print(record.get('outcome','FAIL'))
