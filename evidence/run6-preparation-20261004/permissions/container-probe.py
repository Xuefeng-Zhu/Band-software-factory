"""Named-profile SDK command/exec proof; no model turns or BAND messages."""
import asyncio
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import uuid

WORKSPACE = Path('/Users/frank/mygit/Tablekeeper')
FACTORY = WORKSPACE / 'factory'
sys.path.insert(0, str(FACTORY))
from factorykit.budgets import codex_argv
from factorykit.common import canonical, digest, load_config, redact, artifact_path
from factorykit.permissions import profile_arguments
from band.integrations.codex.stdio_client import CodexStdioClient

PHASE = sys.argv[1] if len(sys.argv)>1 else 'quick'
USE_ADAPTER = '--adapter' in sys.argv
RUN = Path(__file__).resolve().parent
CONFIG_PATH = Path(sys.argv[sys.argv.index('--config')+1]).resolve()
MODE = sys.argv[sys.argv.index('--mode')+1] if '--mode' in sys.argv else 'judged'
assert MODE in ('rehearsal','judged')
config = load_config(CONFIG_PATH)
profile = config['runtime']['permission_profile']
SCRATCH = RUN / 'scratch'
SCRATCH.mkdir(exist_ok=True)
CONTEXT = SCRATCH / 'harness-context'
CONTEXT.mkdir(exist_ok=True)
for file in ('Dockerfile','requirements.txt'):
    shutil.copyfile(WORKSPACE / 'challenge/harness' / file, CONTEXT/file)
TAG = 'factory-permission-probe:' + hashlib.sha256(str(RUN).encode()).hexdigest()[:10]
SOCKET = profile['unix_sockets'][0]
IMAGE_ID = SCRATCH/'image-id.txt'

QUICK = r'''
import json, os, socket, subprocess, urllib.request
from pathlib import Path
p=Path.cwd();out={}
(p/'generic-write.txt').write_text('Synthetic permission probe\n');out['workspace_write']='PASS'
env=dict(os.environ,GIT_AUTHOR_NAME='Factory Probe',GIT_AUTHOR_EMAIL='probe@factory.invalid',GIT_COMMITTER_NAME='Factory Probe',GIT_COMMITTER_EMAIL='probe@factory.invalid')
r=subprocess.run(['git','commit','--allow-empty','-m','Neutral SDK permission diagnostic'],env=env,capture_output=True,text=True,timeout=10)
out['git_commit']={'status':'PASS' if r.returncode==0 else 'FAIL','exit_code':r.returncode,'stderr':r.stderr[:400]}
for label,url in [('pypi','https://pypi.org/simple/'),('npm','https://registry.npmjs.org/react/latest'),('blocked_external','https://example.com/')]:
 try:
  with urllib.request.urlopen(url,timeout=8) as r:out[label]={'request_succeeded':True,'http_status':r.status}
 except Exception as e:out[label]={'request_succeeded':False,'error_type':type(e).__name__,'detail':str(e)[:250]}
try:
 import urllib.parse
 with urllib.request.urlopen('https://pypi.org/pypi/httpx/0.28.1/json',timeout=8) as r:package=json.load(r)
 package_url=next(item['url'] for item in package['urls'] if item['filename'].endswith('.whl'))
 assert urllib.parse.urlparse(package_url).hostname=='files.pythonhosted.org'
 with urllib.request.urlopen(urllib.request.Request(package_url,headers={'Range':'bytes=0-31'}),timeout=8) as r:out['files_pythonhosted_download']={'status':'PASS','http_status':r.status,'bytes_read':len(r.read(32))}
except Exception as e:out['files_pythonhosted_download']={'status':'FAIL','error_type':type(e).__name__,'detail':str(e)[:250]}
try:
 with socket.socket() as s:s.bind(('127.0.0.1',0));out['loopback_bind']='PASS'
except Exception as e:out['loopback_bind']=type(e).__name__
try:
 with socket.socket(socket.AF_UNIX) as s:s.connect(SOCKET);out['exact_docker_socket']='PASS'
except Exception as e:out['exact_docker_socket']={'error_type':type(e).__name__,'detail':str(e)[:250]}
try:
 (p.parent/'outside-write-sentinel').write_text('Should fail');out['outside_workspace_write']='UNEXPECTEDLY_ALLOWED'
except OSError as e:out['outside_workspace_write']={'status':'DENIED','error_type':type(e).__name__}
r=subprocess.run(['/usr/local/bin/docker','version','--format','{{json .Server}}'],capture_output=True,text=True,timeout=15)
out['docker_version']={'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr[:1000]}
print(json.dumps(out))
'''
BUILD = r'''
import hashlib, json, os, subprocess, tempfile, time
from pathlib import Path
p=Path.cwd();started=time.monotonic()
argv=['/usr/local/bin/docker','build','--label','factory.permission.probe=true','--tag',TAG,'--iidfile',str(p/'image-id.txt'),str(p/'harness-context')]
buildx=Path(os.environ.get('BUILDX_CONFIG') or str(Path(tempfile.gettempdir())/('factory-buildx-diagnostic-'+hashlib.sha256(str(p).encode()).hexdigest()[:12])));buildx.mkdir(exist_ok=True,mode=0o700)
env=dict(os.environ,BUILDX_CONFIG=str(buildx))
r=subprocess.run(argv,env=env,capture_output=True,text=True,timeout=510)
(p/'build.stdout.log').write_text(r.stdout);(p/'build.stderr.log').write_text(r.stderr)
print(json.dumps({'docker_build':{'exit_code':r.returncode,'elapsed_s':round(time.monotonic()-started,3),'buildx_config':str(buildx),'image_id':(p/'image-id.txt').read_text().strip() if (p/'image-id.txt').is_file() else None,'stdout_tail':r.stdout[-1200:],'stderr_tail':r.stderr[-4000:]}}))
'''
BROWSER_CODE = r'''
import json, urllib.request
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(headless=True)
 page=b.new_page()
 page.set_content('<title>Factory permission probe</title><button onclick="this.textContent=Number(this.textContent)+1">0</button>')
 page.get_by_role('button',name='0',exact=True).click()
 assert page.get_by_role('button',name='1',exact=True).count()==1
 info={'browser':'chromium','version':b.version,'title':page.title(),'click_result':page.get_by_role('button').inner_text(),'status':'PASS'}
 b.close()
 try:
  urllib.request.urlopen('https://example.com/',timeout=3)
  info['container_outbound']='UNEXPECTEDLY_ALLOWED'
 except Exception as e:info['container_outbound']={'status':'DENIED','error_type':type(e).__name__}
 print(json.dumps(info))
'''
BROWSER = r'''
import json, subprocess
from pathlib import Path
p=Path.cwd();image=(p/'image-id.txt').read_text().strip();name='factory-browser-permission-'+image[-10:]
argv=['/usr/local/bin/docker','run','--rm','--name',name,'--network','none','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256','--cpus','1','--memory','1g',image,'python','-c',BROWSER_CODE]
r=subprocess.run(argv,capture_output=True,text=True,timeout=90)
print(json.dumps({'docker_browser':{'exit_code':r.returncode,'image_id':image,'container_name':name,'stdout':r.stdout,'stderr':r.stderr[-3000:]}}))
'''
CLEAN = r'''
import json, subprocess
from pathlib import Path
p=Path.cwd();image=(p/'image-id.txt').read_text().strip();name='factory-browser-permission-'+image[-10:]
out={}
for key,argv in [('container_check',['container','inspect','--format','{{.Id}}',name]),('image_remove',['image','rm',TAG])]:
 r=subprocess.run(['/usr/local/bin/docker',*argv],capture_output=True,text=True,timeout=30)
 out[key]={'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr[:500]}
print(json.dumps(out))
'''
async def main():
    if not (SCRATCH/'.git').exists():subprocess.run(['git','-C',str(SCRATCH),'init','-b','main'],check=True,capture_output=True)
    command=codex_argv(config,*profile_arguments(profile['name'],profile['domains'],allow_local_binding=profile['allow_local_binding'],unix_sockets=profile['unix_sockets']),'app-server','--listen','stdio://')
    adapter=None
    if USE_ADAPTER:
        from factorykit.runtime import adapter_config
        adapter=adapter_config(config,config['seats'][0],MODE)
        command=list(adapter.codex_command)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output=RUN/(PHASE+('-adapter' if USE_ADAPTER else '')+'-'+stamp+'.json')
    evidence={'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Actual BAND SDK CodexStdioClient transport; command/exec only, no model turn or BAND room message','configuration_path':str(CONFIG_PATH),'configuration_sha256':digest(canonical(config)),'source_lock_sha256':digest(artifact_path(config,'source_lock')),'profile':profile,'profile_sha256':digest(canonical(profile)),'docker_host':config['runtime']['docker_host'],'probe_sha256':digest(Path(__file__)),'cwd':str(SCRATCH),'command':command,'official_harness_files':{file:digest(CONTEXT/file) for file in ('Dockerfile','requirements.txt')},'phase':PHASE,'inference_started':False,'room_messages_sent':False,'legacy_sandbox_fields_omitted':True}
    if adapter:
        evidence['adapter_route']={'seat_id':config['seats'][0]['id'],'mode':MODE,'source':'factorykit.runtime.adapter_config','registered_room_connected':False,'neutral_command_cwd_override':str(SCRATCH),'configured_seat_cwd':adapter.workspace_for_room(config['band'][MODE+'_room_id']),'model':adapter.model,'sandbox':adapter.sandbox,'sandbox_policy':adapter.sandbox_policy,'docker_env':{key:adapter.codex_env[key] for key in ('BUILDX_CONFIG','DOCKER_HOST','DOCKER_CONTEXT')},'runtime_source_sha256':digest(FACTORY/'factorykit/runtime.py')}
    client=CodexStdioClient(command=command,cwd=str(SCRATCH),env=adapter.codex_env if adapter else None)
    body={'quick':QUICK,'build':BUILD,'browser':BROWSER,'cleanup':CLEAN}[PHASE]
    body='import os\nos.environ["DOCKER_CONTEXT"]=""\nos.environ["DOCKER_HOST"]='+repr(config['runtime']['docker_host'])+'\nSOCKET='+repr(SOCKET)+'\nTAG='+repr(TAG)+'\nBROWSER_CODE='+repr(BROWSER_CODE)+'\n'+body
    timeout=540 if PHASE=='build' else 115
    try:
      async with asyncio.timeout(timeout+20):
        await client.connect();await client.initialize(client_name='factory_container_permissions',client_title='Factory neutral Docker browser proof',client_version='1.0')
        result=await client.request('command/exec',{'command':[sys.executable,'-c',body],'cwd':str(SCRATCH),'timeoutMs':timeout*1000,'outputBytesCap':12000})
        evidence['command_exec']=result
        try:evidence['checks']=json.loads(result.get('stdout',''))
        except ValueError:pass
        if PHASE=='quick':
          response=await client.request('thread/start',{'cwd':str(SCRATCH),'model':config['runtime']['model'],'approvalPolicy':'never','ephemeral':True,'allowProviderModelFallback':False})
          evidence['thread_start']={key:response.get(key) for key in ('activePermissionProfile','sandbox','approvalPolicy','model','modelProvider','cwd','runtimeWorkspaceRoots')}
          evidence['thread_turn_count']=len((response.get('thread') or {}).get('turns') or [])
    except Exception as e:evidence['error']={'type':type(e).__name__,'message':redact(str(e))[:1000]}
    finally:
      await client.close();output.write_text(redact(json.dumps(evidence,indent=2))+'\n')
    print(json.dumps({'evidence':str(output),'checks':evidence.get('checks'),'error':evidence.get('error'),'command_exec_exit':evidence.get('command_exec',{}).get('exitCode')},indent=2))
asyncio.run(main())
