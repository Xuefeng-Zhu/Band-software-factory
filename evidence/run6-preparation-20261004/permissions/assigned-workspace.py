"""Actual scoped adapter assigned-path check; zero model turns/messages."""
import asyncio,json,sys,os
from pathlib import Path
F=Path('/Users/frank/mygit/Tablekeeper/factory');sys.path.insert(0,str(F))
from factorykit.common import load_config,canonical,digest,write_json,utc_now,artifact_path,redact
from factorykit.runtime import adapter_config
from band.integrations.codex.stdio_client import CodexStdioClient
async def main():
 config_path=Path(sys.argv[sys.argv.index('--config')+1]).resolve();mode=sys.argv[sys.argv.index('--mode')+1] if '--mode' in sys.argv else 'judged';assert mode in ('judged','rehearsal')
 c=load_config(config_path);a=adapter_config(c,c['seats'][0],mode);cwd=a.workspace_for_room(c['band'][mode+'_room_id']);out=Path(__file__).parent
 r={'created_at':utc_now(),'cwd':cwd,'configuration_path':str(config_path),'mode':mode,'configuration_sha256':digest(canonical(c)),'source_lock_sha256':digest(artifact_path(c,'source_lock')),'runtime_source_sha256':digest(F/'factorykit/runtime.py'),'probe_sha256':digest(Path(__file__)),'model_turns':0,'room_messages':0,'scope':'Exact assigned checkout temporary workspace/Git metadata writes removed and git ls-remote of configured branch; no source, commits, fetched objects, Agent or turn'}
 body=r"""import json,uuid,subprocess,os
from pathlib import Path
p=Path.cwd();before=sorted(x.name for x in p.iterdir());objects_before=subprocess.run(['git','count-objects','-v'],capture_output=True,text=True,check=True).stdout;paths=[p/('factory-probe-'+uuid.uuid4().hex),p/'.git'/('factory-probe-'+uuid.uuid4().hex)]
try:
 for probe in paths:probe.write_text('neutral permission diagnostic\n');assert probe.read_text()=='neutral permission diagnostic\n'
finally:
 for probe in paths:probe.unlink(missing_ok=True)
after=sorted(x.name for x in p.iterdir());remote=subprocess.run(['git','remote','get-url','origin'],capture_output=True,text=True,check=True).stdout.strip();branch=subprocess.run(['git','symbolic-ref','--short','HEAD'],capture_output=True,text=True,check=True).stdout.strip();head=subprocess.run(['git','rev-parse','--verify','HEAD'],capture_output=True,text=True);r=subprocess.run(['git','ls-remote','origin','refs/heads/'+EXPECTED_BRANCH],env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='never'),capture_output=True,text=True,timeout=30);objects_after=subprocess.run(['git','count-objects','-v'],capture_output=True,text=True,check=True).stdout;print(json.dumps({'workspace_write':'PASS','git_metadata_write':'PASS','entries_before':before,'entries_after':after,'git_status':subprocess.run(['git','status','--porcelain'],capture_output=True,text=True,check=True).stdout,'branch_matches':branch==EXPECTED_BRANCH,'remote_matches':remote==EXPECTED_REMOTE,'local_HEAD_exists':head.returncode==0,'ls_remote_exit':r.returncode,'ls_remote_stdout':r.stdout,'ls_remote_stderr':r.stderr[-500:],'object_store_unchanged':objects_before==objects_after,'objects_before':objects_before,'objects_after':objects_after}))
"""
 body='EXPECTED_BRANCH='+repr(c['product']['branch'])+'\nEXPECTED_REMOTE='+repr(c['product']['repository_url'])+'\n'+body
 client=CodexStdioClient(command=list(a.codex_command),cwd=cwd,env=a.codex_env)
 try:
  async with asyncio.timeout(55):
   await client.connect();await client.initialize(client_name='factory_scoped_workspace',client_title='Scoped assigned-checkout permission verification',client_version='1.0')
   raw=await client.request('command/exec',{'command':[sys.executable,'-c',body],'cwd':cwd,'timeoutMs':40000,'outputBytesCap':2000});r['command_exec']=raw;r['command_exit']=raw.get('exitCode');r['checks']=json.loads(raw.get('stdout','{}'))
   r['status']='PASS' if r['command_exit']==0 and r['checks'].get('entries_before')==['.git'] and r['checks'].get('entries_after')==['.git'] and not r['checks'].get('git_status') and r['checks'].get('ls_remote_exit')==0 and r['checks'].get('branch_matches') and r['checks'].get('remote_matches') and r['checks'].get('object_store_unchanged') and not r['checks'].get('local_HEAD_exists') else 'FAIL'
 except Exception as e:r.update(status='FAIL',error_type=type(e).__name__)
 finally:await client.close()
 path=out/('assigned-'+r['created_at'].replace(':','')+'.json');write_json(path,json.loads(redact(json.dumps(r))));print(json.dumps({'status':r['status'],'evidence':str(path),'checks':r.get('checks'),'error_type':r.get('error_type')}))
asyncio.run(main())
