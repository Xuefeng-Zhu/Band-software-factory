import sys,json,copy,time,datetime,urllib.request,urllib.error,concurrent.futures,threading,traceback
from pathlib import Path
E=Path(__file__).parent; C=Path('/private/tmp/qa-s1-20261004T2218Z');sys.path.insert(0,str(C/'tests'))
from qa_stage1_boundaries import Suite,http,fixture,FUTURE,PASSWORD
urls=json.loads((E/'endpoints.json').read_text());s=Suite(*urls)
results=[]
def check(name,fn):
 start=time.monotonic()
 try:fn();r={'name':name,'status':'PASS'}
 except Exception as e:r={'name':name,'status':'FAIL','error':type(e).__name__+': '+str(e),'trace':traceback.format_exc()}
 r['elapsed_seconds']=round(time.monotonic()-start,4);results.append(r);print(name,r['status'],r.get('error',''),flush=True)
 (E/'extra-results.json').write_text(json.dumps({'candidate':'68afbf86127ae9b2b5dc8ecc56a0e9c78e6a69f1','layer':'two host HTTP services','owner':'@frankzhu94/factory-qa','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'results':results},indent=2))
def export(base=None):return s.expect(http(base or s.base,'GET','/_test/export'),200)
def ids_reset():
 s.reset();s.expect(s.create(),201);before=export()
 for location in ['users','restaurants','tables']:
  f=fixture();target=f['restaurants'][0]['tables'][0] if location=='tables' else f[location][0];target['id']='x'*65
  s.expect(http(s.base,'POST','/_test/reset',f),422,'validation_failed');assert export()==before
 for location in ['users','restaurants','tables']:
  f=fixture();target=f['restaurants'][0]['tables'][0] if location=='tables' else f[location][0];target['id']='x'*64;s.reset(f)
  assert ('x'*64) in json.dumps(export()['state'])
 old=s.tokens['alice'];s.expect(http(s.base,'POST','/_test/reset',fixture()),204);s.expect(http(s.base,'GET','/reservations',token=old),401,'unauthenticated')
def auth_boundaries():
 s.reset()
 for auth in ['Basic abc','Bearer','Bearer ','Bearer unknown','Bearer a b','bearer unknown']:
  req=urllib.request.Request(s.base+'/reservations',headers={'Authorization':auth})
  try:urllib.request.urlopen(req,timeout=5);raise AssertionError('malformed bearer succeeded')
  except urllib.error.HTTPError as e:assert e.code==401 and json.load(e)['error']['code']=='unauthenticated'
 valid={'email':'x@y','password':'12345678','display_name':'X'}
 for field in valid:
  b=dict(valid);del b[field];s.expect(http(s.base,'POST','/auth/signup',b),422,'validation_failed')
  for value in [None,True,1,[],{}]:
   b=dict(valid);b[field]=value;s.expect(http(s.base,'POST','/auth/signup',b),400,'malformed_request')
 for email in ['x','@y','x@','x@y@z','x y@z']:
  s.expect(http(s.base,'POST','/auth/signup',dict(valid,email=email)),422,'validation_failed')
 s.expect(http(s.base,'POST','/auth/signup',valid),201)
 # Inspect only synthetic export; persist no password value, hash or token.
 state=export()['state'];assert all(u['password']!=PASSWORD and isinstance(u['password'],dict) and u['password']['algorithm']=='scrypt' for u in state['users'])
def dates_slots():
 s.reset()
 for day in ['2000-02-29','2400-02-29','0001-01-01','9999-12-31']:
  slots=s.availability(day)['slots'];assert len(slots)==8
  s.expect(s.create(s.body(starts_at_local=day+'T18:00')),201)
 for day in ['1900-02-29','2100-02-29','0000-01-01','2026-04-31']:
  s.expect(http(s.base,'GET','/availability?restaurant_id=r&date='+day+'&party_size=2'),422,'validation_failed')
 s.reset();s.expect(s.create(),201);s.expect(s.create(s.body(table_id='r-b')),201)
 slots=s.availability()['slots'];assert slots[0]['available_table_ids']==[] and len(slots)==8
 assert s.expect(http(s.base,'GET','/availability?restaurant_id=r&date='+FUTURE+'&party_size=2&ignored=anything'),200)==s.availability()
 # Large valid decimal query count is not a malformed body or exponent representation.
 s.expect(http(s.base,'GET','/availability?restaurant_id=r&date='+FUTURE+'&party_size='+('9'*5000)),200)
def move_keys_equality():
 s.reset();a=s.expect(s.create(),201);body={'moves':[{'reference':a['reference']}],'unknown':{'values':[True,1,{'x':'a'}]}}
 for key,status,code in [(None,400,'missing_idempotency_key'),('',400,'missing_idempotency_key'),('x'*256,422,'validation_failed')]:
  s.expect(s.request('POST','/reservation-moves',body,key=key),status,code)
 for key in ['x','x'*255]:
  receipt=s.expect(s.request('POST','/reservation-moves',body,key=key),201)
  assert s.expect(s.request('POST','/reservation-moves',body,key=key),200)==receipt
  changed=copy.deepcopy(body);changed['unknown']['values'][0]=1
  s.expect(s.request('POST','/reservation-moves',changed,key=key),409,'idempotency_key_reuse')
  changed=copy.deepcopy(body);changed['unknown']['values'].reverse()
  s.expect(s.request('POST','/reservation-moves',changed,key=key),409,'idempotency_key_reuse')
 b=s.body(table_id='r-b',unknown={'a':[1,2],'b':True});original=s.expect(s.create(b,key='nested'),201)
 raw=json.dumps(dict(reversed(list(b.items()))),indent=4)
 assert s.expect(s.request('POST','/reservations',key='nested',raw=raw),200)==original
 changed=copy.deepcopy(b);changed['unknown']['b']=1;s.expect(s.create(changed,key='nested'),409,'idempotency_key_reuse')
def patch_batch_atomicity():
 s.reset();a=s.expect(s.create(),201);b=s.expect(s.create(s.body(table_id='r-b')),201);other=s.expect(s.create(s.body(restaurant_id='other',table_id='other-a')),201)
 bob=s.expect(s.create(s.body(starts_at_local=FUTURE+'T20:00'),user='bob'),201)
 before=export()
 for change,status,code in [({'party_size':0},422,'validation_failed'),({'party_size':3},422,'party_exceeds_capacity'),({'table_id':1},400,'malformed_request'),({'table_id':'missing'},404,'not_found'),({'starts_at_local':FUTURE+'T18:01'},422,'not_on_slot_grid'),({'starts_at_local':FUTURE+'T22:00'},422,'outside_opening_hours'),({'table_id':'r-b'},409,'table_unavailable')]:
  s.expect(s.request('PATCH','/reservations/'+a['reference'],change),status,code);assert export()==before
 variants=[([],422,'validation_failed'),([{}],422,'validation_failed'),([1],422,'validation_failed'),([{'reference':1}],422,'validation_failed'),([{'reference':a['reference']}]*9,422,'validation_failed'),([{'reference':a['reference']},{'reference':other['reference']}],422,'validation_failed'),([{'reference':bob['reference']}],404,'not_found'),([{'reference':a['reference'],'table_id':'r-b'},{'reference':b['reference']}],409,'table_unavailable'),([{'reference':a['reference'],'table_id':'r-b'},{'reference':b['reference'],'party_size':0}],422,'validation_failed')]
 for moves,status,code in variants:
  s.expect(s.request('POST','/reservation-moves',{'moves':moves},key='reuse'),status,code);assert export()==before
 s.expect(s.request('POST','/reservation-moves',{'moves':[{'reference':a['reference']}]},key='reuse'),201)
def import_invalid():
 s.reset();s.expect(s.create(),201);good=export();s.expect(http(s.destination,'POST','/_test/import',good),204)
 for raw in ['{','[]','null']:
  s.expect(http(s.destination,'POST','/_test/import',raw=raw),400,'malformed_request');assert export(s.destination)==good
 bads=[{},dict(good,format_version=True),dict(good,format_version=2),dict(good,state={}),dict(good,state=[]),dict(good,state=None)]
 for kind in ['duplicate_user','unknown_session','overlap','duplicate_receipt','missing_field']:
  bad=copy.deepcopy(good);state=bad['state']
  if kind=='duplicate_user':state['users'].append(copy.deepcopy(state['users'][0]))
  if kind=='unknown_session':state['sessions'][0]['user_id']='missing'
  if kind=='overlap':state['reservations'].append(copy.deepcopy(state['reservations'][0]))
  if kind=='duplicate_receipt':state['receipts'].append(copy.deepcopy(state['receipts'][0]))
  if kind=='missing_field':del state['restaurants']
  bads.append(bad)
 for bad in bads:
  s.expect(http(s.destination,'POST','/_test/import',bad),422,'validation_failed');assert export(s.destination)==good

def concurrent_snapshots():
 s.reset();a=s.expect(s.create(key='a'),201);b=s.expect(s.create(s.body(table_id='r-b'),key='b'),201)
 saved=export();barrier=threading.Barrier(12)
 def worker(i):
  barrier.wait(timeout=5)
  if i<4:
   target=['r-a','r-b'] if i%2 else ['r-b','r-a']
   moves={'moves':[{'reference':a['reference'],'table_id':target[0]},{'reference':b['reference'],'table_id':target[1]}]}
   return ('success',s.expect(s.request('POST','/reservation-moves',moves,key=f'swap{i}'),201))
  if i<8:
   moves={'moves':[{'reference':a['reference'],'table_id':'r-b'},{'reference':b['reference'],'party_size':0}]}
   s.expect(s.request('POST','/reservation-moves',moves,key=f'reject{i}'),422,'validation_failed');return ('reject',None)
  return ('snapshot',export())
 with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:results=list(pool.map(worker,range(12)))
 for kind,snapshot in results:
  if kind!='snapshot':continue
  state=snapshot['state'];bookings=state['reservations'];assert len(bookings)==2 and set(x['table_id'] for x in bookings)=={'r-a','r-b'}
  receipts=state['receipts'];assert len({(r['user_id'],r['method'],r['path'],r['key']) for r in receipts})==len(receipts)
  assert not any(r['key'].startswith('reject') for r in receipts)
  s.expect(http(s.destination,'POST','/_test/import',snapshot),204)
  assert export(s.destination)==snapshot
  for r in receipts:
   token=s.tokens['alice'];status,value=http(s.destination,r['method'],r['path'],token=token,key=r['key'],raw=r['request']);assert status==200 and value==json.loads(r['response'])
 assert saved['state']['reservations'][0]['table_id']=='r-a' and len(saved['state']['receipts'])==2
for name in ['ids_reset','auth_boundaries','dates_slots','move_keys_equality','patch_batch_atomicity','import_invalid','concurrent_snapshots']:check(name,globals()[name])
sys.exit(any(r['status']=='FAIL' for r in results))
