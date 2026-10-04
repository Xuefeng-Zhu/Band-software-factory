import sys,json,datetime,sqlite3,copy,hashlib,time,traceback
from pathlib import Path
E=Path(__file__).parent;C=Path('/private/tmp/qa-s1-20261004T2218Z');sys.path[:0]=[str(C/'tests'),str(C/'stage-1')]
from qa_stage1_boundaries import fixture,PASSWORD
from tablekeeper.service import Service
from tablekeeper.core import parse,Error
out=[]
def run(name,fn):
 try: fn();r={'name':name,'status':'PASS'}
 except Exception as e:r={'name':name,'status':'FAIL','detail':type(e).__name__+': '+str(e),'trace':traceback.format_exc()}
 out.append(r);print(name,r['status'],flush=True)
 (E/'storage-results.json').write_text(json.dumps({'candidate':'68afbf86127ae9b2b5dc8ecc56a0e9c78e6a69f1','layer':'in-process source seam, independent assertions, no HTTP/container claim','owner':'@frankzhu94/factory-qa','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'results':out},indent=2))
def setup():
 service=Service(now=lambda:datetime.datetime(2096,9,24,15,59,59,tzinfo=datetime.timezone.utc))
 def request(method,path,body=None,key=None):
  raw=json.dumps(body or {});return service.route(method,path,{},parse(raw),raw,getattr(service,'qa_auth',None),key)
 request('POST','/_test/reset',fixture());_,auth=request('POST','/auth/login',{'email':'alice@example.test','password':PASSWORD});service.qa_auth='Bearer '+auth['token']
 service.qa_request=request;return service
BODY={'restaurant_id':'r','table_id':'r-a','starts_at_local':'2096-09-24T18:00','party_size':2}
def storage_trace():
 v=setup();q=v.qa_request;_,a=q('POST','/reservations',BODY,'original')
 _,b=q('POST','/reservations',dict(BODY,table_id='r-b',padding='x'*8192),'unrelated')
 for i in range(4):q('PATCH','/reservations/'+b['reference'],{'party_size':1 if i%2==0 else 2})
 db=v.store.db
 indexes=db.execute('PRAGMA index_list(receipts)').fetchall();assert any(row[2] for row in indexes)
 plan=db.execute('EXPLAIN QUERY PLAN SELECT request,response FROM receipts WHERE user_id=? AND method=? AND path=? AND key=?',('u','POST','/reservations','k')).fetchall();assert any('SEARCH' in row[-1] and 'INDEX' in row[-1] for row in plan)
 for name,operation in [('replay',lambda:q('POST','/reservations',BODY,'original')),('noop_patch',lambda:q('PATCH','/reservations/'+a['reference'],{})),('browse',lambda:q('GET','/restaurants')),('health',lambda:q('GET','/health'))]:
  trace=[];db.set_trace_callback(trace.append);operation();db.set_trace_callback(None)
  assert not any(t.lstrip().upper().startswith(('INSERT','UPDATE','DELETE','REPLACE')) for t in trace),name
  assert not any('histories' in t.lower() for t in trace),name
  reads=[t for t in trace if 'from receipts' in t.lower()]
  assert len(reads)==(1 if name=='replay' else 0),name
  if reads:assert 'where user_id=' in reads[0].lower() and 'key=' in reads[0].lower()
 before=db.execute('SELECT reservation_id,sequence,event FROM histories ORDER BY reservation_id,sequence').fetchall()
 q('PATCH','/reservations/'+a['reference'],{'party_size':1})
 after=db.execute('SELECT reservation_id,sequence,event FROM histories ORDER BY reservation_id,sequence').fetchall();assert set(before).issubset(set(after)) and len(after)==len(before)+1
 q('POST','/reservations/'+a['reference']+'/cancel',{})
 trace=[];db.set_trace_callback(trace.append);q('POST','/reservations/'+a['reference']+'/cancel',{});db.set_trace_callback(None)
 assert not any(t.lstrip().upper().startswith(('INSERT','UPDATE','DELETE','REPLACE')) for t in trace)
 trace=[];db.set_trace_callback(trace.append);q('POST','/reservation-moves',{'moves':[{'reference':b['reference']}]},'noop_batch');db.set_trace_callback(None)
 mutations=[t.lstrip().lower() for t in trace if t.lstrip().upper().startswith(('INSERT','UPDATE','DELETE','REPLACE'))];assert len(mutations)==1 and mutations[0].startswith('insert into receipts')
 # Independently verify synthetic scrypt hashes, never log hash material.
 for user in v.store.export()['users']:
  p=user['password'];digest=hashlib.scrypt(PASSWORD.encode(),salt=bytes.fromhex(p['salt']),n=16384,r=8,p=1,dklen=64,maxmem=67108864).hex();assert digest==p['digest']
def rollback_injection():
 for table,verb in [('receipts','INSERT'),('histories','INSERT'),('state','UPDATE')]:
  v=setup();q=v.qa_request;before=v.store.export()
  v.store.db.execute(f"CREATE TEMP TRIGGER qa_fault BEFORE {verb} ON {table} BEGIN SELECT RAISE(ABORT,'qa-injected'); END")
  try:q('POST','/reservations',BODY,'rollback');raise AssertionError('fault not raised')
  except sqlite3.DatabaseError:pass
  assert v.store.export()==before
  v.store.db.execute('DROP TRIGGER qa_fault');assert q('POST','/reservations',BODY,'rollback')[0]==201
 v=setup();q=v.qa_request;q('POST','/reservations',BODY,'initial');before=v.store.export();candidate=copy.deepcopy(before);candidate['users'][0]['display_name']='Replacement'
 v.store.db.execute("CREATE TEMP TRIGGER qa_fault BEFORE INSERT ON receipts BEGIN SELECT RAISE(ABORT,'qa-injected'); END")
 try:v.store.replace(candidate);raise AssertionError('fault not raised')
 except sqlite3.DatabaseError:pass
 assert v.store.export()==before
 v.store.db.execute('DROP TRIGGER qa_fault')
def cutoff_equality():
 for now,status in [(datetime.datetime(2096,9,24,15,59,59,tzinfo=datetime.timezone.utc),200),(datetime.datetime(2096,9,24,16,0,tzinfo=datetime.timezone.utc),409),(datetime.datetime(2096,9,24,16,0,1,tzinfo=datetime.timezone.utc),409)]:
  v=setup();q=v.qa_request;_,r=q('POST','/reservations',BODY,'cutoff');v.now=lambda:now
  try:actual,_=q('POST','/reservations/'+r['reference']+'/cancel',{})
  except Error as e:actual=e.status;assert e.code=='cutoff_passed'
  assert actual==status
for name in ['storage_trace','rollback_injection','cutoff_equality']:run(name,globals()[name])
sys.exit(any(x['status']=='FAIL' for x in out))
