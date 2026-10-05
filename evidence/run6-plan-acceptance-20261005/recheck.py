import ast
import copy
import csv
import datetime as dt
from decimal import Decimal, localcontext
import hashlib
import json
import pathlib
import platform
import subprocess
import sys
from zoneinfo import ZoneInfo

E=pathlib.Path(__file__).parent
C=pathlib.Path(json.loads((E/'setup.json').read_text())['clone'])
SHA='c4dcae6f1dc8eb31e2634b6593c05fdcaaa91238'
sys.dont_write_bytecode=True
sys.path.insert(0,str(C/'qa'))
from stage1_http import exact_loads,same,numeric_body
from legacy_upgrade import check_history
started=dt.datetime.now(dt.timezone.utc).isoformat()
results=[]
def check(name,passed,detail):
    results.append({'name':name,'status':'PASS' if passed else 'FAIL','detail':detail})
def git(*args): return subprocess.check_output(['git','-C',str(C),*args],text=True).strip()
check('exact_clean_clone',git('rev-parse','HEAD')==SHA and not git('status','--porcelain'),SHA)
for ancestor in ['96e2fa1b0a61ee9f917f5ce76b94726ba8e7cd10','5e12fe7413e3521870aa2ad34f335798d7e910d7']:
    rc=subprocess.run(['git','-C',str(C),'merge-base','--is-ancestor',ancestor,SHA]).returncode
    check('repair_ancestry',rc==0,ancestor)
rows=list(csv.DictReader((C/'planning/requirements-coverage.csv').open()))
cases=json.loads((C/'qa/boundary-cases.json').read_text())
for n in range(1,5):
    rs=[r for r in rows if r['requirement_id'].startswith(f'S{n}-')]
    raw=pathlib.Path(rs[0]['source_path']).read_bytes()
    check(f'S{n}_requirements_unchanged',hashlib.sha256(raw).hexdigest()==rs[0]['source_sha256'] and '\n\n'.join(r['acceptance_condition'] for r in rs).strip()==raw.decode().strip(),rs[0]['source_sha256'])
check('product_not_tested_status',len(rows)==37 and len(cases)==42 and all(r['verification_status']=='NOT_TESTED' for r in rows) and all(r['status']=='NOT_TESTED' for r in cases),'37 source rows,42 classes,all product NOT_TESTED')
check('original_R2_witness_fixed',not same(exact_loads('{"n":1.0000000000000001}'),exact_loads('{"n":1.0}')),'Prior failed case now distinguishes exact numeric values.')
with localcontext() as ctx:
    ctx.prec=1
    a=exact_loads('{"z":[-0,123456789012345678901e-20,1e-5000],"b":true}')
    b=exact_loads('{"b":true,"z":[0.0,1.23456789012345678901,10e-5001]}')
    c=exact_loads('{"b":1,"z":[0,1.23456789012345678901,1e-5000]}')
    d=exact_loads('{"b":true,"z":[0,1.23456789012345678902,1e-5000]}')
    check('new_nested_exact_controls',same(a,b) and not same(a,c) and not same(a,d),'Object order and signed zero/equivalent exponent pass; nested bool and adjacent precise decimals fail under precision1.')
token='123456789012345678901e-20'
wire=numeric_body(token)
check('new_raw_token_preserved',token.encode() in wire and exact_loads(wire)['meta']['n']==Decimal('1.23456789012345678901'),'Wire bytes never pass through float.')

# Run only declared mechanism functions from the owner's non-product probe, with
# independently chosen inputs/expectations. Do not execute its result-writing body.
probe=pathlib.Path('/Users/frank/mygit/Tablekeeper/result-run-6/.evidence/architect-ARCH-repair1-20261005/probe.py')
tree=ast.parse(probe.read_text())
functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'resolve','closing','slots','parse','reject','encode'}]
ns={'dt':dt,'UTC':dt.timezone.utc,'ZoneInfo':ZoneInfo,'Decimal':Decimal,'json':json}
exec(compile(ast.Module(body=functions,type_ignores=[]),str(probe),'exec'),ns)
check('R1_exact_witness',ns['slots']('2026-03-29','02:15','04:45',30,30)==['2026-03-29T03:15:00+02:00','2026-03-29T03:45:00+02:00','2026-03-29T04:15:00+02:00'],'Owner mechanism tested independently; no service exists.')
check('R1_new_grid_duration_witness',ns['slots']('2026-03-29','02:10','04:10',20,40)==['2026-03-29T03:10:00+02:00','2026-03-29T03:30:00+02:00'],'New input:20-minute wall grid from02:10,40-minute duration; must not shift to03:00.')
original=exact_loads('{"n":[123456789012345678901e-20,1e-5000],"s":"é","b":true}')
outer={'track':'tablekeeper','format_version':1,'state':{'request_json':ns['encode'](original)}}
roundtrip=json.loads(json.dumps(outer))
check('R2_new_outer_transport_witness',same(original,exact_loads(roundtrip['state']['request_json'])),'Ordinary outer JSON parser preserves escaped receipt document,including precise exponents/unicode/bool.')

# New corruption controls beyond owner's current-table/cancellation-time examples.
from test_oracles import LegacyOracleControls
entries,created,windows=LegacyOracleControls().sample()
check_history(entries,created,windows)
bad=copy.deepcopy(entries);bad[1]['changes'][0]['from']='t2'
try: check_history(bad,created,windows);rejected=False
except AssertionError: rejected=True
check('R3_new_wrong_before_value_rejected',rejected,'Corrupt amendment origin t2 instead of observed t1.')
bad=copy.deepcopy(entries);bad[1]['accepted_terms']['capacities']['t1']=3
try: check_history(bad,created,windows);rejected=False
except AssertionError: rejected=True
check('R3_new_changed_terms_rejected',rejected,'Corrupt policy0 snapshot; should fail even with correct current table.')
check('clone_still_clean',git('rev-parse','HEAD')==SHA and not git('status','--porcelain'),SHA)
record={'id':'REVIEW-PLAN','candidate_commit':SHA,'reviewer':'@frankzhu94/factory-reviewer','started_at_utc':started,'finished_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'environment':{'platform':platform.platform(),'python':platform.python_version(),'layer':'host planning/oracle review only'},'results':results,'owner_suite_independently_run':{'command':'python3 -B qa/test_oracles.py','exit':0,'passed':14},'help_checks':{'commands':['python3 -B qa/legacy_upgrade.py --help','python3 -B qa/stage1_http.py --help'],'exit':0},'limitations':['No product HTTP/container/browser/upgrade/performance execution.','Probe helpers come from supplied owner evidence, not committed product; tests use new independently specified inputs.','Private ledger timestamp adapter remains a first-runnable obligation.'],'room_event':'08141cfb-0413-4ff7-a168-b4a484d00d01','measured_consumption':'UNAVAILABLE'}
(E/'results.json').write_text(json.dumps(record,indent=2))
print(json.dumps({'checks':len(results),'failures':[r['name'] for r in results if r['status']=='FAIL'],'evidence':str(E/'results.json')}))
sys.exit(int(any(r['status']=='FAIL' for r in results)))
