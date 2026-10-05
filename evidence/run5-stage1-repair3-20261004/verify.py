import os,sys,json,time,subprocess,datetime,socket,hashlib
from pathlib import Path
ROOT=Path('/Users/frank/mygit/Tablekeeper/result-run-5');E=ROOT/'.evidence/backend-s1-repair3-20261004T2307Z';P=sys.executable;REV='513db15d7b3a1b9a86d4e0fa15366c587c6c4e67'
sys.path.insert(0,str(ROOT/'tests'));from qa_stage1_boundaries import http,fixture,PASSWORD
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
record=dict(work_item='BUILD-S1-REPAIR3',owner='@frankzhu94/factory-backend',revision=REV,start=now(),layer='host Python3.13; no Docker claims',commands=[],services=[])
env=dict(os.environ,PYTHONPATH=str(ROOT/'stage-1'),PYTHONDONTWRITEBYTECODE='1');children=[];logs=[]
def run(argv,name,timeout=45):
 item=dict(argv=argv,cwd=str(ROOT),start=now())
 with (E/name).open('w') as out:r=subprocess.run(argv,cwd=ROOT,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=timeout)
 item.update(end=now(),exit_status=r.returncode,log=str(E/name));record['commands'].append(item)
 assert r.returncode==0,name

def start(source):
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 log=(E/('server-'+str(port)+'.log')).open('w');logs.append(log);argv=[P,'-m','tablekeeper.server'];proc=subprocess.Popen(argv,cwd=ROOT,env=dict(env,PYTHONPATH=str(source),PORT=str(port)),stdout=log,stderr=log);children.append(proc);record['services'].append(dict(argv=argv,source=str(source),port=port,pid=proc.pid,start=now()));base='http://127.0.0.1:'+str(port)
 for _ in range(100):
  try:
   if http(base,'GET','/health')[0]==200:return base
  except OSError:time.sleep(.02)
 raise RuntimeError('startup')
try:
 run([P,'-m','unittest','discover','-s','stage-1/tests','-v'],'unit-committed.log')
 run([P,str(E/'reviewer-repro/check.py')],'reviewer-repro.log')
 a=start(ROOT/'stage-1');b=start(ROOT/'stage-1')
 run([P,'stage-1/tests/http_repair3.py','--base-url',a,'--destination-url',b,'--revision',REV,'--out',str(E/'http-repair3.json')],'http-repair3.log')
 run([P,'tests/qa_stage1_boundaries.py','--base-url',a,'--destination-url',b,'--revision',REV,'--out',str(E/'http-baseline.json')],'http-baseline.log')
 legacy=E/'legacy';legacy.mkdir()
 archive=subprocess.check_output(['git','archive','4026ec71ac6cf5ae0ebe6e998d77fd4a475a8c4d','stage-1/tablekeeper'],cwd=ROOT)
 subprocess.run(['tar','-x','-C',str(legacy)],input=archive,check=True)
 old=start(legacy/'stage-1');assert http(old,'POST','/_test/reset',fixture())[0]==204
 token=http(old,'POST','/auth/login',dict(email='alice@example.test',password=PASSWORD))[1]['token'];body=dict(restaurant_id='r',table_id='r-a',party_size=2,starts_at_local='2096-09-24T18:00')
 original=http(old,'POST','/reservations',body,token,'legacy-create')[1]
 moves={'moves':[{'reference':original['reference'],'party_size':1}]};batch=http(old,'POST','/reservation-moves',moves,token,'legacy-batch')[1]
 assert http(old,'POST','/reservations/'+original['reference']+'/cancel',{},token)[0]==200
 snapshot=http(old,'GET','/_test/export')[1];assert http(b,'POST','/_test/import',snapshot)[0]==204;assert http(b,'GET','/_test/export')[1]==snapshot
 assert http(b,'POST','/reservations',body,token,'legacy-create')==(200,original)
 assert http(b,'POST','/reservation-moves',moves,token,'legacy-batch')==(200,batch)
 assert http(b,'POST','/auth/login',dict(email='alice@example.test',password=PASSWORD))[0]==200
 record['legacy_portability']='PASS: unchanged actual old export, cancelled current booking, original create/batch responses, retained token/password'
 record['outcome']='PASS'
finally:
 for child,info in zip(children,record['services']):
  child.terminate()
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:child.kill();child.wait(timeout=2)
  info.update(stopped=now(),exit_status=child.returncode)
 for log in logs:log.close()
 record['end']=now();(E/'verification.json').write_text(json.dumps(record,indent=2))
 print(record.get('outcome','FAIL'))
