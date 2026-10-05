import json, subprocess, sys
from pathlib import Path
F=Path('/Users/frank/mygit/Tablekeeper/factory');sys.path.insert(0,str(F))
from factorykit.common import load_config,digest,write_json,utc_now
O=Path(__file__).resolve().parent.parent;C=load_config(O/'factory.yaml')
ROOM=C['band']['judged_room_id'];PM=next(s for s in C['seats'] if s['id']=='pm');HUMAN='7f9319c7-ef4f-4c9b-88aa-97e1edb15c60'
assert O.resolve()==Path(C['paths']['runs']).resolve()
assert PM['agent_id']=='7d26ccf7-2921-4b38-9e16-ca8ebfa2a448'
assert ROOM=='d98df99d-77ad-441d-875c-6e38cdbef39d' and (O/'launch/send-attempt.json').exists()
r=subprocess.run(['/Applications/Band.app/Contents/MacOS/band','room','messages',ROOM,'--type','text','--json','--profile','default'],capture_output=True,text=True,timeout=30);assert r.returncode==0
d=json.loads(r.stdout);write_json(O/'launch/room-text-after-dispatch.json',d);assert not d['has_more']
human=[x for x in d['messages'] if x['message_type']=='text' and x['sender_type']=='User'];assert len(human)==1
m=human[0];assert m['sender_id']==HUMAN and m['chat_id']==ROOM
entry=json.loads((O/'launch/ledger.json').read_text())['entries'][0];submitted=Path(entry['task']).read_text();assert digest(submitted)==entry['task_sha256']
mention='@'+PM['handle'];replacement='@[['+PM['agent_id']+']]'
assert submitted.count(mention)==1
assert m['content']==submitted.replace(mention,replacement)
record={'at':utc_now(),'status':'PASS_WITH_BAND_MENTION_NORMALIZATION','event_id':m['id'],'inserted_at':m['inserted_at'],'room_id':ROOM,'sender_id':HUMAN,'recipient_pm_id':PM['agent_id'],'human_text_count':1,'readback_scope':'Complete text-filtered page, has_more=false; not a full-session export','submitted_sha256':digest(submitted),'actual_sha256':digest(m['content']),'text_readback_sha256':digest(O/'launch/room-text-after-dispatch.json'),'raw_exact_match':m['content']==submitted,'exact_after_only_pm_mention_normalization':True,'normalization':{'from':mention,'to':replacement,'count':1},'retries_by_operator':0}
write_json(O/'launch/dispatch-verification.json',record);print(json.dumps(record))
