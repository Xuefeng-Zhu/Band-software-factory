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
 a=boot(C,SHA);b=boot(C,SHA);old=boot(OLD,'4026ec71ac6cf5ae0ebe6e998d77fd4a475a8c4d')
 # Independently authored missing/range/fraction checks across ordinary fixture numerics.
 req(a,'POST','/_test/reset',fixture());before=state(a)
 for field in ['slot_minutes','reservation_duration_minutes','cancellation_cutoff_minutes','capacity']:
  for value in ['MISSING',-1,1.5]:
   f=fixture();target=f['restaurants'][0]['tables'][0] if field=='capacity' else f['restaurants'][0]
   if value=='MISSING':del target[field]
   else:target[field]=value
   check('numeric-value-'+field+'-'+str(value),[422,'validation_failed'],error(req(a,'POST','/_test/reset',f)));check('numeric-value-atomic-'+field+'-'+str(value),True,state(a)==before)
 token=login(a)
 for value in ['2',True,None,[],{}]:check('party-type-override-'+type(value).__name__,[422,'validation_failed'],error(req(a,'POST','/reservations',dict(createbody(),party_size=value),token,'bad-'+type(value).__name__)))
 # No product codec used: emit exact numbers via raw sentinel replacement, decode with stdlib Decimal.
 digits='9'*5000;expected=Decimal(digits)
 for field in ['capacity','reservation_duration_minutes','slot_minutes','cancellation_cutoff_minutes']:
  for form in [digits,digits+'.0']:
   f=fixture();target=f['restaurants'][0]['tables'][0] if field=='capacity' else f['restaurants'][0];target[field]='NUMBER';raw=json.dumps(f).replace('"NUMBER"',form);suffix=field+('-decimal' if form.endswith('.0') else '-integer')
   check('huge-reset-'+suffix,204,req(a,'POST','/_test/reset',raw=raw)[0]);r=req(a,'GET','/restaurants/r');decoded=json.loads(r[1],parse_int=Decimal,parse_float=Decimal);value=decoded['tables'][0][field] if field=='capacity' else decoded[field];check('huge-browse-'+suffix,True,r[0]==200 and value==expected and isinstance(value,Decimal))
   exported=req(a,'GET','/_test/export');check('huge-import-'+suffix,204,req(b,'POST','/_test/import',raw=exported[1])[0]);check('huge-state-roundtrip-'+suffix,True,json.loads(req(b,'GET','/_test/export')[1],parse_int=Decimal,parse_float=Decimal)==json.loads(exported[1],parse_int=Decimal,parse_float=Decimal))
   token=login(a);body=createbody();bookingraw=json.dumps(body)
   if field=='capacity':bookingraw=bookingraw.replace('"party_size": 2','"party_size": '+digits)
   booking=req(a,'POST','/reservations',raw=bookingraw,token=token,key='large');check('huge-booking-'+suffix,422 if field=='reservation_duration_minutes' else 201,booking[0])
   if booking[0]==201:
    parsed=json.loads(booking[1],parse_int=Decimal,parse_float=Decimal);ref=parsed['reference'];check('huge-replay-'+suffix,True,json.loads(req(a,'POST','/reservations',raw=bookingraw,token=token,key='large')[1],parse_int=Decimal,parse_float=Decimal)==parsed)
    if field=='capacity':check('huge-party-response-'+suffix,True,parsed['party_size']==expected)
    if field=='cancellation_cutoff_minutes':check('huge-cutoff-'+suffix,[409,'cutoff_passed'],error(req(a,'POST','/reservations/'+ref+'/cancel',{},token)))
    if field=='slot_minutes':check('huge-grid-offgrid-'+suffix,[422,'not_on_slot_grid'],error(req(a,'POST','/reservations',dict(body,table_id='z',starts_at_local='2096-09-24T18:30'),token,'offgrid')))
    snap=req(a,'GET','/_test/export');check('huge-booking-import-'+suffix,204,req(b,'POST','/_test/import',raw=snap[1])[0]);check('huge-imported-replay-'+suffix,True,json.loads(req(b,'POST','/reservations',raw=bookingraw,token=token,key='large')[1],parse_int=Decimal,parse_float=Decimal)==parsed)
 # Exact parsing equality of escaped strings, large/decimal numbers and bool distinctions.
 req(a,'POST','/_test/reset',fixture());token=login(a);base=json.dumps(createbody())[:-1]
 raw1=base+',"unknown":{"n":123456789012345678901234567890.000,"s":"\\u96ea\\n\\\"\\\\","x":[true,null]}}';raw2=base+',"unknown":{"x":[true,null],"s":"雪\\n\\\"\\\\","n":123456789012345678901234567890}}'
 r=req(a,'POST','/reservations',raw=raw1,token=token,key='exact');check('codec-first',201,r[0]);check('codec-equivalent',True,req(a,'POST','/reservations',raw=raw2,token=token,key='exact')==(200,r[1]))
 for label,raw in [('number',raw2.replace('567890','567891')),('boolean',raw2.replace('[true,null]','[1,null]'))]:check('codec-difference-'+label,[409,'idempotency_key_reuse'],error(req(a,'POST','/reservations',raw=raw,token=token,key='exact')))
 for raw in [base+',"ignored":NaN}',base+',"ignored":01}',base+',"ignored":Infinity}']:check('codec-malformed',[400,'malformed_request'],error(req(a,'POST','/reservations',raw=raw,token=token,key='invalid')))
 # Actual unchanged old-process export with create+batch originals, later mutation and cancellation.
 req(old,'POST','/_test/reset',fixture());token=login(old);create1=obj(req(old,'POST','/reservations',createbody(),token,'one'));create2=obj(req(old,'POST','/reservations',createbody('z'),token,'two'));moves={'moves':[{'reference':create1['reference'],'table_id':'z'},{'reference':create2['reference'],'table_id':'t'}]};batch=obj(req(old,'POST','/reservation-moves',moves,token,'batch'));req(old,'PATCH','/reservations/'+create1['reference'],{'party_size':3},token);req(old,'POST','/reservations/'+create2['reference']+'/cancel',{},token);snap=state(old);check('old-process-import',204,req(b,'POST','/_test/import',snap)[0]);check('old-process-state',True,state(b)==snap)
 for path,body,key,response in [('/reservations',createbody(),'one',create1),('/reservations',createbody('z'),'two',create2),('/reservation-moves',moves,'batch',batch)]:check('old-process-replay-'+key,True,obj(req(b,'POST',path,body,token,key))==response)
 check('old-process-password-login',200,req(b,'POST','/auth/login',{'email':'u@x','password':'synthetic-pass'})[0])
 # Independent receipt invalidity checks: full identities/order plus impossible request-response pairs.
 mutations=[]
 def mutate_response(index,field,value):
  def mutate(s):
   d=json.loads(s['state']['receipts'][index]['response']);d[field]=value;s['state']['receipts'][index]['response']=json.dumps(d)
  return mutate
 for field,value in [('reservation_id','missing'),('restaurant_id','other'),('party_size',True),('status','cancelled'),('starts_at','not-a-time'),('created_at','2000-01-01T00:00:00+00:00')]:mutations.append(('create-'+field,mutate_response(0,field,value)))
 def owner(s):s['state']['receipts'][0]['user_id']='v'
 mutations.append(('create-owner',owner))
 def reversed_batch(s):
  d=json.loads(s['state']['receipts'][2]['response']);d['reservations'].reverse();s['state']['receipts'][2]['response']=json.dumps(d)
 mutations.append(('batch-order',reversed_batch))
 def missing_batch(s):
  d=json.loads(s['state']['receipts'][2]['response']);del d['reservations'][0]['table_id'];s['state']['receipts'][2]['response']=json.dumps(d)
 mutations.append(('batch-member-shape',missing_batch))
 mutations += [('create-request-response-party',mutate_response(0,'party_size',3)),('create-local-instant-inconsistent',mutate_response(0,'starts_at_local','2096-09-24T20:00')),('create-elapsed-duration-inconsistent',mutate_response(0,'ends_at','2096-09-24T18:30:00+00:00'))]
 for name,mutation in mutations:
  req(b,'POST','/_test/import',snap);before=state(b);bad=copy.deepcopy(snap);mutation(bad);r=req(b,'POST','/_test/import',bad);check('invalid-receipt-'+name,[422,'validation_failed'],error(r));check('invalid-receipt-atomic-'+name,True,state(b)==before)
 # Unchanged independent HTTP suite exercises shared codec across baseline routes and races.
 argv=[P,str(C/'tests/qa_stage1_boundaries.py'),'--base-url',a,'--destination-url',b,'--revision',SHA,'--out',str(E.resolve()/'baseline.json')];t=now()
 with open(E/'baseline.log','w') as log:r=subprocess.run(argv,cwd=C,stdout=log,stderr=log,timeout=30,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
 commands.append({'argv':argv,'cwd':str(C),'start':t,'end':now(),'exit':r.returncode});check('baseline-process',0,r.returncode)
finally:
 cleanup=[]
 for p,log in procs:
  p.terminate()
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
  log.close();cleanup.append({'pid':p.pid,'exit':p.returncode,'utc':now()})
 record={'work_item':'GATE-S1-RECHECK','revision':SHA,'start':start,'end':now(),'python':sys.version,'commands':commands,'cleanup':cleanup,'results':results};(E/'extended-results.json').write_text(json.dumps(record,indent=2));print(json.dumps({'pass':sum(x['status']=='PASS' for x in results),'fail':[x for x in results if x['status']=='FAIL']}))
sys.exit(1 if any(x['status']=='FAIL' for x in results) else 0)
