import os,socket,subprocess,time,json,datetime,pathlib,urllib.request
E=pathlib.Path('/Users/frank/mygit/Tablekeeper/result-run-5/.evidence/qa-s1-20261004T2218Z');C=pathlib.Path('/private/tmp/qa-s1-20261004T2218Z');P='/Users/frank/mygit/Tablekeeper/runs/harness-venv/bin/python'
procs=[];record={'candidate':'68afbf86127ae9b2b5dc8ecc56a0e9c78e6a69f1','start':datetime.datetime.now(datetime.timezone.utc).isoformat(),'layer':'host Python, no isolation/resource gate','services':[]}
try:
 for i in range(2):
  sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
  env=dict(os.environ,PYTHONPATH=str(C/'stage-1'),PORT=str(port),PYTHONDONTWRITEBYTECODE='1')
  log=open(E/f'server-{i}.log','w');p=subprocess.Popen([P,'-m','tablekeeper.server'],cwd=E,env=env,stdout=log,stderr=log);procs.append(p)
  record['services'].append({'pid':p.pid,'port':port,'command':[P,'-m','tablekeeper.server'],'PYTHONPATH':env['PYTHONPATH']})
  for _ in range(100):
   try:
    with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=1) as r: assert r.status==200
    break
   except Exception: time.sleep(.1)
  else: raise RuntimeError('host startup failed')
 urls=[f'http://127.0.0.1:{s["port"]}' for s in record['services']]
 (E/'endpoints.json').write_text(json.dumps(urls));(E/'processes.json').write_text(json.dumps(record,indent=2))
 cmd=[P,str(C/'tests/qa_stage1_boundaries.py'),'--base-url',urls[0],'--destination-url',urls[1],'--revision',record['candidate'],'--out',str(E/'baseline.json')]
 with open(E/'baseline.log','w') as log:r=subprocess.run(cmd,stdout=log,stderr=log,timeout=120)
 record['baseline']={'command':cmd,'exit_status':r.returncode};(E/'processes.json').write_text(json.dumps(record,indent=2));print('BASELINE',r.returncode,flush=True)
 end=time.monotonic()+420
 while time.monotonic()<end and not (E/'stop').exists():time.sleep(.2)
finally:
 for p in procs:
  p.terminate()
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
 record['end']=datetime.datetime.now(datetime.timezone.utc).isoformat();record['own_processes_stopped']=[p.poll() is not None for p in procs];(E/'processes.json').write_text(json.dumps(record,indent=2));print('CLEANUP',record['own_processes_stopped'])
