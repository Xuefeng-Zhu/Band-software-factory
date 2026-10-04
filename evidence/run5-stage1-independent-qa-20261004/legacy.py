import sys,json,subprocess,tarfile,socket,os,time,datetime,urllib.request,traceback
from pathlib import Path
E=Path(__file__).parent;C=Path('/private/tmp/qa-s1-20261004T2218Z');P='/Users/frank/mygit/Tablekeeper/runs/harness-venv/bin/python';sys.path.insert(0,str(C/'tests'))
from qa_stage1_boundaries import Suite,http,fixture,PASSWORD
legacy=Path('/private/tmp/qa-s1-legacy-20261004T2218Z');legacy.mkdir()
archive=legacy/'source.tar';subprocess.run(['git','-C',str(C),'archive','--output',str(archive),'12e43a92dd6e037ac27dfb2189f18eed35a32fbc','stage-1/tablekeeper'],check=True)
with tarfile.open(archive) as tar:tar.extractall(legacy,filter='data')
sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close();log=open(E/'legacy-server.log','w')
cmd=[P,'-m','tablekeeper.server'];proc=subprocess.Popen(cmd,cwd=E,env=dict(os.environ,PYTHONPATH=str(legacy/'stage-1'),PORT=str(port),PYTHONDONTWRITEBYTECODE='1'),stdout=log,stderr=log)
record={'candidate':'68afbf86127ae9b2b5dc8ecc56a0e9c78e6a69f1','legacy_revision':'12e43a92dd6e037ac27dfb2189f18eed35a32fbc','legacy_source':str(legacy),'command':cmd,'port':port,'pid':proc.pid,'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'layer':'three separate real host processes; no Docker'}
try:
 base=f'http://127.0.0.1:{port}'
 for _ in range(100):
  try:
   with urllib.request.urlopen(base+'/health',timeout=1) as r:assert r.status==200
   break
  except Exception:time.sleep(.1)
 else:raise RuntimeError('legacy startup failed')
 destination=json.loads((E/'endpoints.json').read_text())[1];s=Suite(base,destination);s.reset()
 body=s.body(unknown={'nested':[1,True,'kept']});original=s.expect(s.create(body,key='legacy-original'),201)
 move={'moves':[{'reference':original['reference'],'party_size':1}]};moved=s.expect(s.request('POST','/reservation-moves',move,key='legacy-move'),201)
 s.expect(s.create(s.body(party_size=0),key='legacy-failed'),422,'validation_failed')
 saved=s.expect(http(base,'GET','/_test/export'),200)
 s.expect(s.request('POST','/reservations/'+original['reference']+'/cancel',{}),200)
 s.expect(http(destination,'POST','/_test/import',saved),204)
 assert s.expect(http(destination,'GET','/_test/export'),200)==saved
 assert s.expect(s.request('POST','/reservations',body,key='legacy-original',base=destination),200)==original
 assert s.expect(s.request('POST','/reservation-moves',move,key='legacy-move',base=destination),200)==moved
 s.expect(http(destination,'POST','/auth/login',{'email':'alice@example.test','password':PASSWORD}),200)
 s.expect(s.request('POST','/reservations',s.body(table_id='r-b'),key='legacy-failed',base=destination),201)
 assert s.expect(s.request('GET','/reservations/'+original['reference'],base=destination),200)['status']=='confirmed'
 record['status']='PASS'
except Exception as e:record.update(status='FAIL',detail=type(e).__name__+': '+str(e),trace=traceback.format_exc())
finally:
 proc.terminate()
 try:proc.wait(timeout=5)
 except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
 record.update(ended_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),own_process_stopped=proc.poll() is not None)
 (E/'legacy-results.json').write_text(json.dumps(record,indent=2));print(record['status'],flush=True)
sys.exit(record['status']!='PASS')
