"""Run6 non-inference probes only; never starts BAND or inference turns."""
import asyncio,hashlib,json,logging,re,subprocess,sys
from pathlib import Path
F=Path('/Users/frank/mygit/Tablekeeper/factory');sys.path.insert(0,str(F))
from factorykit.common import load_config,canonical,digest,write_json,utc_now,redact,artifact_path
from factorykit.runtime import discover_models
R=F.parent/'runs/run6-preparation-20261004';P=R/'permissions';C=R/'factory.yaml';config=load_config(C);global_path=Path.home()/'.codex/config.toml';global_before=global_path.read_text();observed_at=utc_now()
watched={'scoped_config':C,'scoped_source_lock':artifact_path(config,'source_lock'),'default_config':F/'config/factory.yaml','default_source_lock':F/'config/source-lock.json','default_ledger':F.parent/'runs/runtime/budget-subscription.json','scoped_ledger':R/'runtime/budget-subscription.json'}
before={k:digest(v) for k,v in watched.items() if v.exists()};steps=[]
logging.disable(logging.CRITICAL)
try:
 catalog=asyncio.run(discover_models(config));write_json(R/'runtime/models.json',catalog)
 models=[m.get('model',m.get('id')) for m in catalog['models']]
 write_json(P/'model-discovery.json',{'observed_at':utc_now(),'configuration_sha256':digest(canonical(config)),'catalog':{'path':str(R/'runtime/models.json'),'sha256':digest(R/'runtime/models.json')},'inference_started':False,'configured_model':config['runtime']['model'],'configured_model_advertised':config['runtime']['model'] in models,'model_ids':models,'model_changed':False})
 print(json.dumps({'phase':'model-discovery','configured_model_advertised':config['runtime']['model'] in models,'model_ids':models}),flush=True)
 for phase in ('assigned','quick','build','browser','cleanup'):
  argv=[sys.executable,'-B',str(P/('assigned-workspace.py' if phase=='assigned' else 'container-probe.py'))]
  if phase!='assigned':argv.extend([phase,'--adapter'])
  argv.extend(['--config',str(C),'--mode','judged'])
  started=utc_now();r=subprocess.run(argv,capture_output=True,text=True,timeout=600 if phase=='build' else 150)
  record={'started_at':started,'finished_at':utc_now(),'argv':argv,'exit_code':r.returncode,'stdout':redact(r.stdout),'stderr':redact(r.stderr)};write_json(P/(phase+'-invocation.json'),record)
  try:response=json.loads(r.stdout)
  except ValueError:response={}
  steps.append({'phase':phase,'process_exit_code':r.returncode,'status':response.get('status'),'command_exec_exit':response.get('command_exec_exit'),'error':response.get('error') or response.get('error_type'),'evidence':response.get('evidence')})
  print(json.dumps(steps[-1]),flush=True)
finally:
 global_after=global_path.read_text();new_sections=[];reconstructed=global_after
 for target in (str(P/'scratch'),config['paths']['result']):
  pattern=r'\n?\[projects\."'+re.escape(target)+r'"\]\ntrust_level = "trusted"\n'
  m=re.search(pattern,reconstructed)
  if m and not re.search(pattern,global_before):new_sections.append('projects.'+target+'.trust_level');reconstructed=reconstructed[:m.start()]+reconstructed[m.end():]
 audit={'observed_at':utc_now(),'global_before_sha256':digest(global_before),'global_after_sha256':digest(global_after),'exact_previous_reconstructed_after_removing_only_new_trust_sections':digest(reconstructed)==digest(global_before),'new_trust_key_paths':new_sections,'global_file_manually_written':False,'source_lock_manually_written':False,'watched_before_sha256':before,'watched_after_sha256':{k:digest(v) for k,v in watched.items() if v.exists()},'steps':steps,'scope':'Preparation-only probes. No model turns, room messages, Agent creation or model/config/budget/source-lock changes. SDK may auto-add exact probed-directory trust metadata.'}
 write_json(P/'probe-input-audit.json',audit)
 print(json.dumps({'audit':str(P/'probe-input-audit.json'),'only_expected_trust_delta':audit['exact_previous_reconstructed_after_removing_only_new_trust_sections'],'new_trust_key_paths':new_sections,'watched_changed':[k for k in before if before[k]!=audit['watched_after_sha256'].get(k)]}),flush=True)
