#!/usr/bin/env python3
"""Non-model smoke probes in a disposable repository, never in judged output."""
import argparse,datetime,json,os,socket,subprocess,sys,urllib.request,uuid
from pathlib import Path

def child(path):
 out={}
 try: (path/'write-probe.txt').write_text('synthetic setup probe\n');out['workspace_write']='PASS'
 except OSError as e:out['workspace_write']=type(e).__name__
 env=dict(os.environ,GIT_AUTHOR_NAME='Factory Probe',GIT_AUTHOR_EMAIL='probe@factory.invalid',GIT_COMMITTER_NAME='Factory Probe',GIT_COMMITTER_EMAIL='probe@factory.invalid')
 r=subprocess.run(['git','-C',str(path),'commit','--allow-empty','-m','Disposable permission probe'],env=env,capture_output=True,text=True)
 out['git_commit']={'status':'PASS' if r.returncode==0 else 'FAIL','exit_code':r.returncode,'evidence':r.stderr[:500]}
 try:
  with urllib.request.urlopen('https://pypi.org/simple/',timeout=5) as r:out['development_network']={'status':'PASS','http_status':r.status}
 except Exception as e:out['development_network']={'status':'FAIL','error_type':type(e).__name__}
 try:
  with socket.socket() as s:s.bind(('127.0.0.1',0));out['loopback_bind']='PASS'
 except Exception as e:out['loopback_bind']=type(e).__name__
 print(json.dumps(out));return 0

def main():
 p=argparse.ArgumentParser();p.add_argument('--child',type=Path);a=p.parse_args()
 if a.child:return child(a.child)
 f=Path(__file__).resolve().parents[1];w=f.parent;run=w/'runs'/('permissions-'+uuid.uuid4().hex[:10]); repo=run/'scratch';repo.mkdir(parents=True)
 subprocess.run(['git','-C',str(repo),'init','-b','main'],check=True,capture_output=True)
 command=[str(f/'scripts/codex-local'),'sandbox','macos','--permissions-profile',':workspace','-c','model_reasoning_effort="medium"','-c','sandbox_mode="workspace-write"','-c','approval_policy="never"','-C',str(repo),sys.executable,str(Path(__file__).resolve()),'--child',str(repo)]
 r=subprocess.run(command,capture_output=True,text=True,timeout=30)
 data={'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'command':command,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'scope':'Disposable setup probe only; no model turn or BAND activity'}
 (run/'evidence.json').write_text(json.dumps(data,indent=2)+'\n');print(json.dumps(data,indent=2));print('Evidence:',run/'evidence.json')
 return r.returncode
if __name__=='__main__':raise SystemExit(main())
