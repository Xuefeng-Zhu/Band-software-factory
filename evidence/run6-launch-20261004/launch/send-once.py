"""Approved one-shot human dispatch; an existing attempt record permanently prevents rerun."""
import json, os, subprocess, sys
from pathlib import Path
F=Path('/Users/frank/mygit/Tablekeeper/factory');sys.path.insert(0,str(F))
from factorykit.common import load_config, canonical, digest, write_json, utc_now, redact
from factorykit.runtime import judged_launch_errors
O=Path(__file__).resolve().parent.parent
C=load_config(O/'factory.yaml');BAND='/Applications/Band.app/Contents/MacOS/band'
ROOM=C['band']['judged_room_id'];PM=next(s for s in C['seats'] if s['id']=='pm')
assert O.resolve()==Path(C['paths']['runs']).resolve()
assert PM['agent_id']=='7d26ccf7-2921-4b38-9e16-ca8ebfa2a448'
assert ROOM=='d98df99d-77ad-441d-875c-6e38cdbef39d'
assert C['budgets']['approved'] and not judged_launch_errors(C)
approval=json.loads((O/'authorization/approval.json').read_text())
assert approval['authorized_attempt']=='Run6' and approval['authorized_dispatches']==1 and approval['mode']=='all'
assert approval['room_id']==ROOM and approval['result']==C['paths']['result']
assert approval['user_reply']=='approve' and approval['retry_or_additional_attempt_authorized'] is False
ledger=json.loads((O/'launch/ledger.json').read_text());assert len(ledger['entries'])==1
entry=ledger['entries'][0];assert entry['state']=='PREPARED'
freeze=O/'freeze/latest.json';assert digest(freeze)==entry['freeze_sha256']
frozen=json.loads(freeze.read_text());assert frozen['status']=='READY_TO_LAUNCH' and frozen['configuration_sha256']==digest(canonical(C))
task=Path(entry['task']);raw=task.read_bytes();assert digest(raw)==entry['task_sha256']
assert digest(raw)=='c0799fc072bcf6979c4992632e93ada4a20618529acf0dcfff86d20819bcf75b'
assert digest(freeze)=='5e8832e8790b098bd70812754e8a2fbe6c0a0375857c6814a5057cd733ada367'
body=raw.decode('utf-8')
assert 'git push origin HEAD:refs/heads/run-6' in body
who=subprocess.run([BAND,'whoami','--json','--profile','default'],capture_output=True,text=True,timeout=25)
assert who.returncode==0
person=json.loads(who.stdout);assert person['id']=='7f9319c7-ef4f-4c9b-88aa-97e1edb15c60' and person['handle']=='frankzhu94'
read=subprocess.run([BAND,'room','messages',ROOM,'--json','--profile','default'],capture_output=True,text=True,timeout=25)
assert read.returncode==0
before=json.loads(read.stdout)
write_json(O/'launch/room-immediately-before.json',before)
assert len(before['messages'])==7 and not before['has_more']
assert all(m['chat_id']==ROOM and m['message_type']=='participant' for m in before['messages'])
assert not judged_launch_errors(C)
path=O/'launch/send-attempt.json'
record={'status':'ATTEMPTING_ONCE','at':utc_now(),'room_id':ROOM,'operator_id':person['id'],'pm_id':PM['agent_id'],'preparation_id':entry['id'],'task_sha256':digest(raw),'freeze_sha256':digest(freeze),'body_bytes':len(raw),'retries_by_operator':0,'transport':'Installed BAND native human CLI; body passed directly as one argv, no shell interpolation','internal_transport_retry_policy':'Not verified; one CLI invocation only. Read actual room before any conclusion.'}
fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
with os.fdopen(fd,'w') as stream:
    json.dump(record,stream,indent=2);stream.flush();os.fsync(stream.fileno())
try:
    sent=subprocess.run([BAND,'room','send',ROOM,body,'--mention',PM['agent_id'],'--profile','default'],capture_output=True,text=True,timeout=35)
    (O/'launch/send-stdout.log').write_text(redact(sent.stdout))
    (O/'launch/send-stderr.log').write_text(redact(sent.stderr))
    record.update(status='CLI_RETURNED_INSPECT_ROOM',returncode=sent.returncode,completed_at=utc_now())
except Exception as exc:
    record.update(status='UNKNOWN_INSPECT_ROOM_DO_NOT_RESEND',error_type=type(exc).__name__,completed_at=utc_now())
write_json(path,record)
print(json.dumps(record))
