import ast
import csv
import datetime as dt
from decimal import Decimal
import hashlib
import itertools
import json
import pathlib
import platform
import runpy
import subprocess
import sys

E = pathlib.Path(__file__).parent
C = pathlib.Path(json.loads((E / 'setup.json').read_text())['clone'])
SHA = '0456233212ba4a101243c03684706e4fbbbb32e9'
results = []
started = dt.datetime.now(dt.timezone.utc).isoformat()

def check(name, ok, detail):
    results.append({'check': name, 'status': 'PASS' if ok else 'FAIL', 'detail': detail})

def git(*args):
    return subprocess.check_output(['git', '-C', str(C), *args], text=True).strip()

check('exact_clean_candidate_before', git('rev-parse', 'HEAD') == SHA and not git('status', '--porcelain'), SHA)
rows = list(csv.DictReader((C / 'planning/requirements-coverage.csv').open()))
cases = json.loads((C / 'qa/boundary-cases.json').read_text())
check('map_cardinality', len(rows) == 37 and len(cases) == 42, {'requirements': len(rows), 'classes': len(cases)})
for n in range(1, 5):
    selected = [r for r in rows if r['requirement_id'].startswith(f'S{n}-')]
    original = pathlib.Path(selected[0]['source_path']).read_bytes()
    reconstructed = '\n\n'.join(r['acceptance_condition'] for r in selected) + '\n'
    check(f'S{n}_source_fidelity', hashlib.sha256(original).hexdigest() == selected[0]['source_sha256'] and reconstructed.strip() == original.decode().strip(), selected[0]['source_sha256'])
check('all_product_statuses_truthful', all(r['verification_status'] == 'NOT_TESTED' for r in rows) and all(c['status'] == 'NOT_TESTED' for c in cases), 'No product behavior executed or accepted.')
ids = {r['requirement_id'] for r in rows}
check('case_requirement_links', all(set(c['requirements']) <= ids for c in cases), 'All 42 classes link to existing source rows.')
source = (C / 'qa/stage1_http.py').read_text()
ast.parse(source)
check('driver_syntax', True, 'ast.parse; no service execution')
help_run = subprocess.run([sys.executable, str(C / 'qa/stage1_http.py'), '--help'], capture_output=True, text=True)
check('driver_help', help_run.returncode == 0, {'exit': help_run.returncode})
qa = runpy.run_path(str(C / 'qa/stage1_http.py'))
same = qa['same']
check('typed_numeric_controls', same({'n': 1}, {'n': 1.0}) and not same({'n': 1}, {'n': True}) and not same([1, 2], [2, 1]), 'Existing QA comparator distinguishes bool and array ordering.')
left, right = '{"n":1.0000000000000001}', '{"n":1.0}'
qa_equal = same(json.loads(left), json.loads(right))
exact_equal = json.loads(left, parse_float=Decimal) == json.loads(right, parse_float=Decimal)
check('fractional_identity_oracle_challenge', not qa_equal and not exact_equal, {'qa_default_parse_reports_equal': qa_equal, 'exact_decimal_reports_equal': exact_equal, 'left': left, 'right': right, 'scope': 'oracle limitation, not product result'})

# Independent opening-gap witness uses explicit transition offsets from supplied spec.
# New case beyond submitted 02:00 opening: preserve a non-hour grid origin at 02:15.
grid = ['02:15', '02:45', '03:15', '03:45', '04:15', '04:45']
valid = [v for v in grid if v >= '03:00' and v <= '04:15']
start = dt.datetime.fromisoformat('2026-03-29T03:15:00+02:00')
end = start + dt.timedelta(minutes=30)
close = dt.datetime.fromisoformat('2026-03-29T04:45:00+02:00')
check('gap_opening_counterexample', valid == ['03:15', '03:45', '04:15'] and end <= close, {'zone': 'Europe/Berlin', 'date': '2026-03-29', 'opening': '02:15', 'closing': '04:45', 'grid_minutes': 30, 'duration_minutes': 30, 'required_valid_starts': valid, 'architecture_line_52_predicts': [], 'scope': 'contradiction in proposed rule; no product exists'})

# Exhaustive tiny planner with two overlapping bookings, independent of product helpers.
# Close t0. Moving B to free t1 for A is lexically tempting but costs two moves.
tables = [frozenset([i]) for i in range(3)]
capacities = [2, 2, 4]
original = [tables[0], tables[1]]
scores = []
for assignment in itertools.product(range(3), repeat=2):
    if 0 in assignment or tables[assignment[0]] & tables[assignment[1]]:
        continue
    changed = sum(tables[rank] != original[i] for i, rank in enumerate(assignment))
    unused = sum(capacities[rank] - 2 for rank in assignment)
    scores.append((changed, unused, assignment))
optimum = min(scores)
check('global_planner_independent_witness', optimum == (1, 2, (2, 1)), {'all_feasible_objectives': scores, 'expected': optimum, 'references_in_order': ['AAA001', 'BBB001'], 'scope': 'independent future product oracle only'})
check('exact_clean_candidate_after', git('rev-parse', 'HEAD') == SHA and not git('status', '--porcelain'), SHA)
record = {'work_item': 'REVIEW-PLAN', 'responsible_handle': '@frankzhu94/factory-reviewer', 'candidate_commit': SHA, 'starting_revision': SHA, 'clone': str(C), 'started_at_utc': started, 'finished_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'environment': {'platform': platform.platform(), 'python': sys.version.split()[0], 'layer': 'host planning/oracle checks; not isolated product checks'}, 'room_references': ['f72d9e6d-8ecf-41d7-b28f-01fd1dac8810', 'ddaec528-b2ea-44c4-bb59-bc1760208514'], 'results': results, 'measured_consumption': 'UNAVAILABLE'}
(E / 'independent-results.json').write_text(json.dumps(record, indent=2))
print(json.dumps({'checks': len(results), 'failed': [r['check'] for r in results if r['status'] == 'FAIL'], 'evidence': str(E / 'independent-results.json')}))
sys.exit(int(any(r['status'] == 'FAIL' for r in results)))
