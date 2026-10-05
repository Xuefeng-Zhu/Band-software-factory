import copy,datetime as dt,json,pathlib,sys,threading
from unittest.mock import patch
sys.path.insert(0,'/private/tmp/gate-s1-20261004T2254Z/stage-1')
import tablekeeper.service as mod
from tablekeeper.core import parse,Error
E=pathlib.Path(__file__).parent;results=[];start=dt.datetime.now(dt.timezone.utc).isoformat()
def f():return {'users':[{'id':'u','email':'u@x','display_name':'U','password':'synthetic-pass'}],'restaurants':[{'id':'r','name':'R','timezone':'UTC','slot_minutes':30,'reservation_duration_minutes':90,'cancellation_cutoff_minutes':0,'opening_hours':[{'weekday':x,'opens':'18:00','closes':'23:00'} for x in ['mon','tue','wed','thu','fri','sat','sun']],'tables':[{'id':'t','label':'T','capacity':4}]}],'reservations':[]}
def run(name,fn):
 try:fn();results.append({'name':name,'status':'PASS'})
 except Exception as e:results.append({'name':name,'status':'FAIL','error_type':type(e).__name__});raise

def generation():
 for replacement in ['reset','import']:
  s=mod.Service();s.reset(f());candidate=s.store.export();entered=threading.Event();release=threading.Event();original=mod.password;out=[]
  def delayed(p,record=None):
   if record:entered.set();assert release.wait(3)
   return original(p,record)
  def login():
   try:s.login({'email':'u@x','password':'synthetic-pass'},False);out.append('stale-session')
   except Error as e:out.append(e.status)
  with patch.object(mod,'password',delayed):
   t=threading.Thread(target=login);t.start();assert entered.wait(3)
   if replacement=='reset':s.reset({'users':[],'restaurants':[],'reservations':[]})
   else:s.store.replace(candidate)
   release.set();t.join(3);assert not t.is_alive();assert out==[401];assert s.store.export()['sessions']==[]
run('login-reset-and-identical-import-generation-races',generation)

def transaction_checks():
 s=mod.Service();s.reset(f());token=s.login({'email':'u@x','password':'synthetic-pass'},False)['token'];body={'restaurant_id':'r','table_id':'t','starts_at_local':'2096-09-24T18:00','party_size':2}
 def route(method,path,b,key=None):
  raw=json.dumps(b);return s.route(method,path,{},parse(raw),raw,'Bearer '+token,key)
 before=s.store.export()
 with patch.object(s.store,'insert_receipt',side_effect=RuntimeError('injected')):
  try:route('POST','/reservations',body,'key');raise AssertionError('did not fail')
  except RuntimeError:pass
 assert s.store.export()==before
 status,original=route('POST','/reservations',body,'key');assert status==201;ref=original['reference']
 for name,action in [('replay',lambda:route('POST','/reservations',body,'key')),('noop-patch',lambda:route('PATCH','/reservations/'+ref,{'party_size':2}))]:
  before=s.store.export();sql=[];s.store.db.set_trace_callback(sql.append);action();s.store.db.set_trace_callback(None);assert s.store.export()==before;assert not any(x.startswith(('UPDATE','INSERT','DELETE')) for x in sql)
 route('POST','/reservations/'+ref+'/cancel',{});before=s.store.export();sql=[];s.store.db.set_trace_callback(sql.append);route('POST','/reservations/'+ref+'/cancel',{});s.store.db.set_trace_callback(None);assert s.store.export()==before;assert not any(x.startswith(('UPDATE','INSERT','DELETE')) for x in sql)
 # Force replacement failure after core/delete work; complete previous state must return.
 with patch.object(s.store,'insert_receipt',side_effect=RuntimeError('injected')):
  try:s.store.replace(before);raise AssertionError('did not fail')
  except RuntimeError:pass
 assert s.store.export()==before
run('receipt-insert-and-replacement-rollback-plus-noop-sql',transaction_checks)
(E/'mechanisms-results.json').write_text(json.dumps({'work_item':'GATE-S1','revision':'4026ec71ac6cf5ae0ebe6e998d77fd4a475a8c4d','layer':'host in-process with deliberate failure/scheduling injection; not HTTP or container','start':start,'end':dt.datetime.now(dt.timezone.utc).isoformat(),'results':results},indent=2));print(json.dumps(results))
