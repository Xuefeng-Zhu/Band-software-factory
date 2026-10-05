import copy,datetime as dt,json,os,pathlib,socket,subprocess,sys,time,urllib.request,urllib.error
E=pathlib.Path(__file__).parent; C=pathlib.Path('/private/tmp/gate-s1-recheck-20261004T2318Z'); SHA='3329a8238ece53e06812cce4b5c6222476dd33ab'; results=[]; processes=[]
now=lambda:dt.datetime.now(dt.timezone.utc).isoformat()
def git(p,*a):return subprocess.check_output(['git','-C',str(p),*a],text=True).strip()
def check(name,expected,actual,details=None):
 results.append(dict(name=name,expected=expected,actual=actual,status='PASS' if expected==actual else 'FAIL',details=details,utc=now()))
def req(base,method,path,body=None,token=None,key=None,raw=None):
 headers={'Content-Type':'application/json'}
 if token:headers['Authorization']='Bearer '+token
 if key:headers['Idempotency-Key']=key
 data=raw.encode() if raw is not None else None if body is None else json.dumps(body).encode()
 try:r=urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers,method=method),timeout=10)
 except urllib.error.HTTPError as e:r=e
 with r:
  data=r.read();return r.status,json.loads(data) if data else None

def fixture():return {'users':[{'id':'u','email':'u@x','display_name':'U','password':'synthetic-pass'}],'restaurants':[{'id':'r','name':'R','timezone':'UTC','slot_minutes':30,'reservation_duration_minutes':90,'cancellation_cutoff_minutes':0,'opening_hours':[{'weekday':x,'opens':'18:00','closes':'23:00'} for x in ['mon','tue','wed','thu','fri','sat','sun']],'tables':[{'id':'t','label':'T','capacity':4}]}],'reservations':[]}
def err(r):return [r[0],r[1].get('error',{}).get('code') if r[1] else None]
execution={'work_item':'GATE-S1-RECHECK','revision':SHA,'reviewer':'@frankzhu94/factory-reviewer','start':now(),'python':sys.version,'commands':[]}
try:
 for p in [C,pathlib.Path('/Users/frank/mygit/Tablekeeper/result-run-5')]:
  assert git(p,'rev-parse','HEAD')==SHA and git(p,'status','--porcelain')==''
 execution['clean_before']=True
 bases=[]
 for i in range(2):
  with socket.socket() as s:s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
  env=dict(os.environ,PYTHONPATH=str(C/'stage-1'),PYTHONDONTWRITEBYTECODE='1',PORT=str(port)); cmd=[sys.executable,'-m','tablekeeper.server']; log=open(E/f'server-{i}.log','w');p=subprocess.Popen(cmd,cwd=C,env=env,stdout=log,stderr=log);processes.append((p,log));base=f'http://127.0.0.1:{port}';bases.append(base)
  execution['commands'].append({'argv':cmd,'cwd':str(C),'port':port,'pid':p.pid,'start':now()})
  for _ in range(100):
   try:
    if req(base,'GET','/health')==(200,{'status':'ok'}):break
   except OSError:pass
   time.sleep(.03)
  else:raise AssertionError('startup')
 a,b=bases; f=fixture();check('reset-valid',204,req(a,'POST','/_test/reset',f)[0]); token=req(a,'POST','/auth/login',{'email':'u@x','password':'synthetic-pass'})[1]['token']
 before=req(a,'GET','/_test/export')[1]
 for field in ['slot_minutes','reservation_duration_minutes','cancellation_cutoff_minutes','capacity']:
  for value in ['30',True,None,[],{}]:
   bad=copy.deepcopy(f); target=bad['restaurants'][0]['tables'][0] if field=='capacity' else bad['restaurants'][0];target[field]=value
   r=req(a,'POST','/_test/reset',bad);check('reset-wrong-type-'+field+'-'+type(value).__name__,[400,'malformed_request'],err(r));check('reset-invalid-atomic-'+field+'-'+type(value).__name__,before,req(a,'GET','/_test/export')[1])
 body={'restaurant_id':'r','table_id':'t','starts_at_local':'2096-09-24T18:00','party_size':2}; r=req(a,'POST','/reservations',body,token,'create');check('create',201,r[0]); original=r[1];ref=original['reference']
 check('amend',200,req(a,'PATCH','/reservations/'+ref,{'party_size':3},token)[0]);check('cancel',200,req(a,'POST','/reservations/'+ref+'/cancel',{},token)[0])
 snap=req(a,'GET','/_test/export')[1];check('unchanged-export-import',204,req(b,'POST','/_test/import',snap)[0]);check('historical-create-replay',[200,original],list(req(b,'POST','/reservations',body,token,'create')));check('password-after-import',200,req(b,'POST','/auth/login',{'email':'u@x','password':'synthetic-pass'})[0])
 # Incomplete completed response is invalid schema1 state, not a stale current booking.
 for name,response in [('missing-fields',{'reference':ref}),('unknown-reference',dict(original,reference='ORPHAN01')),('wrong-owner-id',dict(original,reservation_id='missing'))]:
  req(b,'POST','/_test/import',snap);previous=req(b,'GET','/_test/export')[1];bad=copy.deepcopy(snap);bad['state']['receipts'][0]['response']=json.dumps(response);r=req(b,'POST','/_test/import',bad)
  check('import-receipt-'+name,[422,'validation_failed'],err(r));check('import-receipt-'+name+'-unchanged',True,req(b,'GET','/_test/export')[1]==previous)
  if r[0]==204:
   replay=req(b,'POST','/reservations',body,token,'create');check('import-receipt-'+name+'-replay-retains-original',True,replay==(200,original),{'status':replay[0],'response_keys':sorted(replay[1]),'reference_matches':replay[1].get('reference')==ref})
 # History identity alone is insufficient: verify invalid ordering/time is rejected.
 req(b,'POST','/_test/import',snap);bad=copy.deepcopy(snap);bad['state']['reservations'][0]['_history'][0]['at']='not-a-date';check('import-invalid-history-time',[422,'validation_failed'],err(req(b,'POST','/_test/import',bad)))
 # Independently recheck prior failures, full eight slots and capacity values.
 req(a,'POST','/_test/reset',f)
 for date,party,tables in [('9999-12-31','2',['t']),('2096-09-24','9'*5000,[])]:
  r=req(a,'GET',f'/availability?restaurant_id=r&date={date}&party_size={party}');expected=[{'starts_at_local':date+'T'+x,'starts_at':date+'T'+x+':00+00:00','available_table_ids':tables} for x in ['18:00','18:30','19:00','19:30','20:00','20:30','21:00','21:30']];check('prior-date-max' if date.startswith('9999') else 'prior-query-digits',[200,expected],[r[0],r[1].get('slots')])
 f['restaurants'][0]['timezone']='Europe/Berlin';req(a,'POST','/_test/reset',f);r=req(a,'GET','/availability?restaurant_id=r&date=1890-01-01&party_size=2');check('historical-second-offset-rfc3339','1890-01-01T17:06:32+00:00',r[1]['slots'][0]['starts_at'])
 # Huge but short JSON fixture integer: 5000 digits, no memory/resource stress.
 f=fixture();f['restaurants'][0]['tables'][0]['capacity']='CAPACITY_SENTINEL';raw=json.dumps(f).replace('"CAPACITY_SENTINEL"','9'*5000);r=req(a,'POST','/_test/reset',raw=raw);check('valid-5000-digit-capacity-reset',204,r[0],{'error_code':r[1].get('error',{}).get('code') if r[1] else None})
finally:
 for p,log in processes:
  p.terminate()
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
  log.close();execution.setdefault('cleanup',[]).append({'pid':p.pid,'returncode':p.returncode,'end':now()})
 execution['end']=now();execution['clean_after']=all(git(p,'rev-parse','HEAD')==SHA and git(p,'status','--porcelain')=='' for p in [C,pathlib.Path('/Users/frank/mygit/Tablekeeper/result-run-5')]);execution['pass']=sum(r['status']=='PASS' for r in results);execution['fail']=sum(r['status']=='FAIL' for r in results)
 # Never persist private export/credential values, including assertion expected/actual snapshots.
 for x in results:
  if x['name'].startswith('reset-invalid-atomic'):
   x['expected']='unchanged';x['actual']='unchanged' if x['status']=='PASS' else 'changed'
 (E/'results.json').write_text(json.dumps(results,indent=2));(E/'execution.json').write_text(json.dumps(execution,indent=2));print(json.dumps({'pass':execution['pass'],'fail':execution['fail'],'cleanup':execution['cleanup']}))
sys.exit(1 if execution['fail'] else 0)
