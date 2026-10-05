import copy,datetime as dt,json,os,pathlib,socket,subprocess,sys,time,urllib.request,urllib.error
from decimal import Decimal
E=pathlib.Path(__file__).parent;C=pathlib.Path('/private/tmp/gate-s1-recheck-20261004T2318Z'); OLD=pathlib.Path('/private/tmp/gate-s1-20261004T2254Z');SHA='3329a8238ece53e06812cce4b5c6222476dd33ab'; P=sys.executable;results=[];procs=[];commands=[];now=lambda:dt.datetime.now(dt.timezone.utc).isoformat();start=now()
def check(name,expected,actual):results.append({'name':name,'status':'PASS' if expected==actual else 'FAIL','expected':expected,'actual':actual,'utc':now()})
def req(base,method,path,b=None,token=None,key=None,raw=None):
 h={'Content-Type':'application/json; charset=utf-8'}
 if token:h['Authorization']='Bearer '+token
 if key:h['Idempotency-Key']=key
 data=raw.encode() if raw is not None else json.dumps(b).encode() if b is not None else None
 try:r=urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=h,method=method),timeout=10 if path.startswith('/_test/') else 5)
 except urllib.error.HTTPError as e:r=e
 with r:return r.status,r.read().decode()
def obj(r):return json.loads(r[1]) if r[1] else None
def error(r):return [r[0],obj(r).get('error',{}).get('code') if r[1] else None]
def fixture():return {'users':[{'id':u,'email':u+'@x','display_name':u,'password':'synthetic-pass'} for u in ['u','v']],'restaurants':[{'id':'r','name':'R','timezone':'UTC','slot_minutes':30,'reservation_duration_minutes':90,'cancellation_cutoff_minutes':0,'opening_hours':[{'weekday':x,'opens':'18:00','closes':'23:00'} for x in ['mon','tue','wed','thu','fri','sat','sun']],'tables':[{'id':'t','label':'T','capacity':4},{'id':'z','label':'Z','capacity':4}]}],'reservations':[]}
def login(base,u='u'):return obj(req(base,'POST','/auth/login',{'email':u+'@x','password':'synthetic-pass'}))['token']
def createbody(table='t'):return {'restaurant_id':'r','table_id':table,'starts_at_local':'2096-09-24T18:00','party_size':2}
def boot(path,sha):
 assert subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()==sha
 assert subprocess.check_output(['git','-C',str(path),'status','--porcelain'],text=True).strip()==''
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 log=open(E/f'extended-server-{len(procs)}.log','w');cmd=[P,'-m','tablekeeper.server'];p=subprocess.Popen(cmd,cwd=path,env=dict(os.environ,PYTHONPATH=str(path/'stage-1'),PORT=str(port),PYTHONDONTWRITEBYTECODE='1'),stdout=log,stderr=log);procs.append((p,log));commands.append({'argv':cmd,'cwd':str(path),'revision':sha,'pid':p.pid,'port':port,'start':now()});base=f'http://127.0.0.1:{port}'
 for _ in range(100):
  try:
   if req(base,'GET','/health')[0]==200:return base
  except OSError:pass
  time.sleep(.02)
 raise AssertionError('startup')
def state(base):return obj(req(base,'GET','/_test/export'))
try:
 a=boot(C,SHA);b=boot(C,SHA);req(a,'POST','/_test/reset',fixture());token=login(a);body=createbody();original=obj(req(a,'POST','/reservations',body,token,'one'));ref=original['reference'];moves={'moves':[{'reference':ref,'table_id':'z','party_size':3}]};batch=obj(req(a,'POST','/reservation-moves',moves,token,'batch'));req(a,'POST','/reservations/'+ref+'/cancel',{},token);snap=state(a)
 for name,index,field,value,path,replaybody,key in [('party-pair',0,'party_size',3,'/reservations',body,'one'),('batch-table-pair',1,'table_id','t','/reservation-moves',moves,'batch')]:
  req(b,'POST','/_test/import',snap);bad=copy.deepcopy(snap);response=json.loads(bad['state']['receipts'][index]['response']);historical=response if index==0 else response['reservations'][0];historical[field]=value;bad['state']['receipts'][index]['response']=json.dumps(response);r=req(b,'POST','/_test/import',bad);replayed=req(b,'POST',path,replaybody,token,key);observed=obj(replayed);historical_actual=observed if index==0 else observed['reservations'][0]
  check(name+'-import',[422,'validation_failed'],error(r));check(name+'-replay-original-value',body['party_size'] if index==0 else moves['moves'][0]['table_id'],historical_actual[field]);check(name+'-replay-status',200,replayed[0])
finally:
 cleanup=[]
 for p,log in procs:
  p.terminate();p.wait(timeout=5);log.close();cleanup.append({'pid':p.pid,'exit':p.returncode,'utc':now()})
 (E/'receipt-pairs-results.json').write_text(json.dumps({'work_item':'GATE-S1-RECHECK','revision':SHA,'start':start,'end':now(),'commands':commands,'cleanup':cleanup,'results':results},indent=2));print(json.dumps(results))
sys.exit(1 if any(x['status']=='FAIL' for x in results) else 0)
