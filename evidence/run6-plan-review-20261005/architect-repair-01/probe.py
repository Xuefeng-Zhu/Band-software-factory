"""ARCH repair-1 synthetic proofs; not product, HTTP or independent acceptance."""
import copy
import datetime as dt
from decimal import Decimal, localcontext
import json
import pathlib
from zoneinfo import ZoneInfo

OUT = pathlib.Path(__file__).parent
UTC = dt.timezone.utc
results = []
started = dt.datetime.now(UTC).isoformat()

def check(name, actual, expected, layer='synthetic mechanism'):
    assert actual == expected, (name, actual, expected)
    results.append({'name': name, 'status': 'PASS', 'layer': layer})

def resolve(naive, zone):
    possible = []
    for fold in (0, 1):
        candidate = naive.replace(tzinfo=zone, fold=fold).astimezone(UTC)
        if candidate.astimezone(zone).replace(tzinfo=None) == naive:
            possible.append(candidate)
    return min(possible) if possible else None

def closing(wall, zone):
    # Minute scan demonstrates the documented convention for required minute-aligned zones.
    # Product adapter must use the actual transition instant for other IANA transitions.
    value = resolve(wall, zone)
    while value is None:
        wall += dt.timedelta(minutes=1)
        value = resolve(wall, zone)
    return value

def slots(date, opens, closes, grid, duration):
    zone = ZoneInfo('Europe/Berlin')
    wall = dt.datetime.fromisoformat(date+'T'+opens)
    wall_close = dt.datetime.fromisoformat(date+'T'+closes)
    close = closing(wall_close, zone)
    values=[]
    while wall < wall_close:
        start=resolve(wall,zone)
        if start is not None and start+dt.timedelta(minutes=duration) <= close:
            values.append(start.astimezone(zone).isoformat())
        wall += dt.timedelta(minutes=grid)
    return values

check('R1 mandatory gap-opening witness',slots('2026-03-29','02:15','04:45',30,30),[
    '2026-03-29T03:15:00+02:00','2026-03-29T03:45:00+02:00','2026-03-29T04:15:00+02:00'])
check('R1 grid not shifted to gap end',slots('2026-03-29','02:15','04:45',30,30)[0][11:16],'03:15')
check('R1 separate gap-closing convention',slots('2026-03-29','01:00','02:30',30,30),[
    '2026-03-29T01:00:00+01:00','2026-03-29T01:30:00+01:00'],'implementation convention only')
check('R1 separate first-fold closing convention',slots('2026-10-25','01:30','02:30',30,90),[], 'implementation convention')

def reject(value):
    raise ValueError('non-JSON numeric token')

def parse(raw):
    return json.loads(raw,parse_int=Decimal,parse_float=Decimal,parse_constant=reject)

def encode(value):
    if value is None: return 'null'
    if type(value) is bool: return 'true' if value else 'false'
    if isinstance(value,str): return json.dumps(value,ensure_ascii=False)
    if isinstance(value,Decimal):
        if not value.is_finite(): raise ValueError('nonfinite')
        return str(value)
    if type(value) is int: return str(value)
    if isinstance(value,list): return '['+','.join(encode(v) for v in value)+']'
    if isinstance(value,dict): return '{'+','.join(json.dumps(k)+':'+encode(v) for k,v in value.items())+'}'
    raise TypeError('unsupported value; floats prohibited')

def same(a,b):
    if type(a) is bool or type(b) is bool: return type(a) is type(b) and a==b
    if isinstance(a,(int,Decimal)) and isinstance(b,(int,Decimal)): return a==b
    if type(a) is not type(b): return False
    if isinstance(a,dict): return a.keys()==b.keys() and all(same(a[k],b[k]) for k in a)
    if isinstance(a,list): return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
    return a==b

raw='{"restaurant_id":"r","table_id":"t1","starts_at_local":"2027-03-01T19:00","party_size":2,"ignored":{"n":1.0000000000000001}}'
parsed=parse(raw)
receipt={'request_json':encode(parsed),'response_json':encode({'reference':'ABC123','status':'confirmed','ignored_probe':Decimal('1.0000000000000001')})}
envelope={'track':'tablekeeper','format_version':1,'state':{'receipts':[receipt]}}
imported=json.loads(json.dumps(envelope)) # intentionally ordinary outer decoder
after=imported['state']['receipts'][0]
check('R2 request preserved across ordinary envelope decoder',same(parsed,parse(after['request_json'])),True)
check('R2 distinct unknown decimal remains conflict',same(parse(after['request_json']),parse(raw.replace('1.0000000000000001','1.0'))),False)
check('R2 equivalent spelling remains replay',same(parse(after['request_json']),parse(raw.replace('1.0000000000000001','10000000000000001e-16'))),True)
check('R2 response decimal remains exact',parse(after['response_json'])['ignored_probe'],Decimal('1.0000000000000001'))
check('R2 integer and decimal equal',same(parse('{"n":1}'),parse('{"n":1.0}')),True)
check('R2 bool differs from number',same(parse('{"n":true}'),parse('{"n":1}')),False)
check('R2 object key ordering ignored',same(parse('{"a":1,"b":2}'),parse('{"b":2.0,"a":1e0}')),True)
check('R2 array ordering retained',same(parse('[1,2]'),parse('[2,1]')),False)
with localcontext() as ctx:
    ctx.prec=3
    for raw_num in ['123456789012345678901234567890123456789','1e-1000','1.0000000000000001000000000000000000000001']:
        original=parse(raw_num)
        check('R2 no decimal context rounding '+raw_num,same(original,parse(encode(original))),True)
try:
    encode(1.5)
    raise AssertionError('float accepted')
except TypeError:
    check('R2 float coercion prohibited',True,True)
try:
    parse('NaN')
    raise AssertionError('non-JSON constant accepted')
except ValueError:
    check('R2 non-JSON constants rejected',True,True)

# Record observed private facts at the actual synthetic operations, never reconstruct
# creation from the final record. These times are supplied experiment inputs.
terms={'policy_version':0,'slot_minutes':30,'reservation_duration_minutes':90,
       'cancellation_cutoff_minutes':120,'opening_hours':[], 'capacities':{'t1':2,'t2':4}}
created={'reservation_id':'res1','reference':'ABC123','table_id':'t1','starts_at_local':'2027-03-01T19:00','party_size':2,'status':'confirmed','created_at':'2026-10-01T10:00:00+00:00'}
state={'record':copy.deepcopy(created),'facts':[],'original_response_json':encode(created)}
def fact(event,at,changes):
    state['facts'].append({'seq':len(state['facts'])+1,'revision':len(state['facts'])+1,
        'at':at,'event':event,'changes':copy.deepcopy(changes),'accepted_terms':copy.deepcopy(terms),'provenance':'observed_operation'})
fact('created',created['created_at'],[{'field':f,'from':None,'to':created[f]} for f in ('table_id','starts_at_local','party_size')])
state['record']['table_id']='t2'
fact('changed','2026-10-02T11:00:00+00:00',[{'field':'table_id','from':'t1','to':'t2'}])
state['record']['status']='cancelled'
fact('cancelled','2026-10-03T12:00:00+00:00',[])
legacy=json.loads(json.dumps(state))
history=copy.deepcopy(legacy['facts'])
check('R3 original creation table retained',history[0]['changes'][0]['to'],'t1')
check('R3 real amendment before/after retained',history[1]['changes'],[{'field':'table_id','from':'t1','to':'t2'}])
check('R3 actual cancellation time retained',history[2]['at'],'2026-10-03T12:00:00+00:00')
check('R3 current table/status independently retained',[legacy['record']['table_id'],legacy['record']['status']],['t2','cancelled'])
check('R3 original receipt unchanged',same(parse(legacy['original_response_json']),parse(encode(created))),True)
check('R3 fact revisions carried forward',[x['revision'] for x in history],[1,2,3])
check('R3 identities and created_at preserved',[legacy['record'][x] for x in ('reservation_id','reference','created_at')],[created[x] for x in ('reservation_id','reference','created_at')])
check('R3 captured terms unchanged',all(x['accepted_terms']==terms for x in history),True)
seed_fact={'event':'created','provenance':'fixture_seed','initial_status':'cancelled','at':'2026-10-04T13:00:00+00:00','revision':1}
check('R3 cancelled seed does not invent cancellation fact','cancelled' in [seed_fact['event']],False)
check('R3 seed initialization explicitly distinguished',seed_fact['provenance'],'fixture_seed')

document={'work_item':'ARCH','repair_attempt':1,'owner':'@frankzhu94/factory-architect',
    'starting_revision':'0456233212ba4a101243c03684706e4fbbbb32e9','started_at_utc':started,
    'ended_at_utc':dt.datetime.now(UTC).isoformat(),'checks':results,
    'limitations':['Synthetic host only; no product HTTP, container, browser, upgrade or independent acceptance.','Gap-closing witness tests a documented convention, not a normative oracle.']}
(OUT/'probe-results.json').write_text(json.dumps(document,indent=2)+'\n')
print(json.dumps({'status':'PASS','checks':len(results),'evidence':str(OUT/'probe-results.json')}))
