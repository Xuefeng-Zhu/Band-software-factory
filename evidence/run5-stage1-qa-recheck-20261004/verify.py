import os,socket,subprocess,time,json,datetime,pathlib,urllib.request,sys,hashlib
E=pathlib.Path(__file__).resolve().parent;C=pathlib.Path('/private/tmp/qa-s1-recheck-20261004T2244Z');P='/Users/frank/mygit/Tablekeeper/runs/harness-venv/bin/python';SHA='4026ec71ac6cf5ae0ebe6e998d77fd4a475a8c4d'
procs=[];record={'candidate':SHA,'start':datetime.datetime.now(datetime.timezone.utc).isoformat(),'layer':'host Python only','python_version':sys.version.split()[0],'services':[],'checks':[]};env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
def run(argv,name):
 start=datetime.datetime.now(datetime.timezone.utc).isoformat()
 with open(E/(name+'.log'),'w') as log:r=subprocess.run(argv,cwd=E,env=env,stdout=log,stderr=log,timeout=120)
 record['checks'].append({'command':argv,'cwd':str(E),'start':start,'end':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit_status':r.returncode});print(name,r.returncode,flush=True)
try:
 for i in range(2):
  sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
  service_env=dict(env,PYTHONPATH=str(C/'stage-1'),PORT=str(port));log=open(E/f'server-{i}.log','w')
  p=subprocess.Popen([P,'-m','tablekeeper.server'],cwd=E,env=service_env,stdout=log,stderr=log);procs.append(p)
  record['services'].append({'pid':p.pid,'port':port,'command':[P,'-m','tablekeeper.server'],'PYTHONPATH':service_env['PYTHONPATH']})
  for _ in range(100):
   try:
    with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=1) as r:assert r.status==200
    break
   except Exception:time.sleep(.1)
  else:raise RuntimeError('host startup failed')
 urls=[f'http://127.0.0.1:{s["port"]}' for s in record['services']];(E/'endpoints.json').write_text(json.dumps(urls))
 run([P,str(E/'focused.py')],'focused')
 run([P,str(C/'tests/qa_stage1_boundaries.py'),'--base-url',urls[0],'--destination-url',urls[1],'--revision',SHA,'--out',str(E/'baseline.json')],'baseline')
 # Retain original independent extra assertions; remap only clone and candidate metadata.
 source=pathlib.Path('/Users/frank/mygit/Tablekeeper/result-run-5/.evidence/qa-s1-20261004T2218Z/extra.py')
 text=source.read_text().replace('/private/tmp/qa-s1-20261004T2218Z',str(C)).replace('68afbf86127ae9b2b5dc8ecc56a0e9c78e6a69f1',SHA)
 (E/'prior-extra.py').write_text(text);record['prior_extra_original_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
 run([P,str(E/'prior-extra.py')],'prior-extra')
finally:
 for p in procs:
  p.terminate()
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
 record['end']=datetime.datetime.now(datetime.timezone.utc).isoformat();record['own_processes_stopped']=[p.poll() is not None for p in procs];(E/'execution.json').write_text(json.dumps(record,indent=2));print('cleanup',record['own_processes_stopped'],flush=True)
sys.exit(any(c['exit_status'] for c in record['checks']))
