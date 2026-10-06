"""An explicit human rehearsal exception never manufactures observed readiness."""
import copy
import json
from pathlib import Path
from unittest.mock import patch

from factorykit.common import canonical, digest, write_json, utc_now
from factorykit.operations import freeze, launch_prepare
from factorykit.runtime import judged_launch_errors
from factorykit.validation import (REHEARSAL_OBSERVATIONS, observations,
    operator_readiness_authorization, frozen_readiness_authorization, frozen_readiness_errors, doctor)
from tests import test_toolkit as fixtures
from tests import test_attempt_branches as branches


class OperatorReadinessTests(fixtures.Fixture):
    def setUp(self):
        super().setUp()
        self.config['launch']['practice_mode'] = True
        self.config['band']['judged_room_id'] = '00000000-0000-4000-8000-000000000002'
        self.path=Path(self.config['paths']['runs'])/'readiness/observations.json'
        self.proof=self.root/'proof.json';self.proof.write_text('{"stage":1,"passed":8,"collected":8}')

    def report(self, authorized=True):
        source=self.source_binding() if hasattr(self,'source_binding') else None
        report={'configuration_sha256':digest(canonical(self.config)),
                'source_lock_sha256':digest(Path(self.config['paths']['factory'])/'config/source-lock.json'),
                'observations':[{'id':name,'status':'NOT_TESTED','observed':False,'evidence':[]}
                                for name in REHEARSAL_OBSERVATIONS],
                'partial_rehearsal':{'stage_1':'PASS_8_OF_8','stage_2':'PENDING',
                    'evidence':{'path':str(self.proof),'sha256':digest(self.proof)}}}
        if source: report['factory_source_sha256']=source
        if authorized:
            report['operator_authorization']={'kind':'proceed_with_incomplete_rehearsal',
                'configuration_sha256':report['configuration_sha256'],'source_lock_sha256':report['source_lock_sha256'],
                'judged_room_id':self.config['band']['judged_room_id'],
                'user_request':'can you start Tablekeeper build as well, since we are running out of time',
                'authorized_at':utc_now(),'skipped_observations':sorted(REHEARSAL_OBSERVATIONS)}
        return report

    def write(self, report): write_json(self.path,report)

    def test_explicit_skip_preserves_pending_stage_two_and_never_adds_pass_records(self):
        report=self.report();self.write(report);before=self.path.read_bytes()
        records,blockers=observations(self.config)
        self.assertEqual(records,[])
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(json.loads(before)['partial_rehearsal']['stage_2'],'PENDING')
        self.assertEqual(len(blockers),6)
        for name in ['permissions_agent_write_git','permissions_docker_build','permissions_browser',
                     'permissions_development_network','band_registration_room_visibility','semantic_generic_instructions']:
            self.assertTrue(any(name in value for value in blockers),name)

    def test_absent_authorization_keeps_all_rehearsal_requirements(self):
        self.write(self.report(False));records,blockers=observations(self.config)
        self.assertEqual(records,[])
        self.assertTrue(any('toy_isolated_harness' in value for value in blockers))
        self.assertTrue(any('toy_offline_submission_check' in value for value in blockers))

    def test_critical_checks_cannot_be_skipped_and_wrong_binding_fails(self):
        good=self.report()
        variants=[]
        for name in ['permissions_browser','band_registration_room_visibility','semantic_generic_instructions','unknown']:
            report=copy.deepcopy(good);report['operator_authorization']['skipped_observations']=[name];variants.append(report)
        for key,value in [('configuration_sha256','0'*64),('source_lock_sha256','0'*64),
                          ('judged_room_id','another-room'),('user_request',''),('authorized_at','')]:
            report=copy.deepcopy(good);report['operator_authorization'][key]=value;variants.append(report)
        for report in variants:
            with self.subTest(authorization=report['operator_authorization']):
                self.write(report);records,blockers=observations(self.config)
                self.assertEqual(records,[]);self.assertTrue(any('authorization' in value for value in blockers))

    def test_actual_permission_proof_remains_required_and_recorded(self):
        report=self.report();row={'id':'permissions_browser','status':'PASS','observed':True,
            'observed_at':utc_now(),'observer':'offline fixture','evidence':[{'path':str(self.proof),'sha256':digest(self.proof)}]}
        if report.get('factory_source_sha256'):row['factory_source_sha256']=report['factory_source_sha256']
        report['observations'].append(row);self.write(report)
        records,blockers=observations(self.config);self.assertEqual([x['id'] for x in records],['permissions_browser'])
        self.proof.write_text('changed');records,blockers=observations(self.config)
        self.assertEqual(records,[]);self.assertTrue(any('permissions_browser' in x for x in blockers))

    def test_frozen_authorization_binds_pending_records_as_well_as_user_request(self):
        report=self.report();self.write(report)
        frozen={'operator_readiness_authorization':frozen_readiness_authorization(self.config)}
        self.assertEqual(frozen_readiness_errors(self.config,frozen),[])
        report['partial_rehearsal']['stage_2']='changed';self.write(report)
        self.assertTrue(frozen_readiness_errors(self.config,frozen))
        del report['operator_authorization'];self.write(report)
        self.assertTrue(frozen_readiness_errors(self.config,frozen))

    def test_freeze_launch_and_judged_start_share_the_authorization_binding(self):
        branches.ScopedArtifactTests.ready(self)
        self.write(self.report())
        frozen=freeze(self.config)
        self.assertEqual(frozen['status'],'READY_TO_LAUNCH',frozen['blockers'])
        self.assertEqual(frozen['operator_readiness_authorization'],frozen_readiness_authorization(self.config))
        with patch('factorykit.runtime.persisted_budget_blockers',return_value=[]),patch('factorykit.common.verify_sources',return_value=[]):
            self.assertEqual(judged_launch_errors(self.config),[])
            report=json.loads(self.path.read_text());report['operator_authorization']['user_request']+=' changed';self.write(report)
            prepared=launch_prepare(self.config,'all',None)
            self.assertEqual(prepared['status'],'BLOCKED_WITH_ACTIONS')
            self.assertTrue(any('authorization' in x for x in prepared['blockers']))
            self.assertTrue(any('authorization' in x for x in judged_launch_errors(self.config)))
        self.assertFalse((Path(self.config['paths']['runs'])/'launch/ledger.json').exists())

    def test_doctor_retains_authorized_failed_rehearsal_status(self):
        report=self.report();row=next(x for x in report['observations'] if x['id']=='toy_isolated_harness')
        row.update(status='FAIL',observed=True,observed_at=utc_now(),observer='offline fixture',
                   evidence=[{'path':str(self.proof),'sha256':digest(self.proof)}]);self.write(report)
        with patch('factorykit.validation.run_command',return_value={'exit_code':0,'stdout':'fixture','stderr':''}), \
             patch('factorykit.validation.docker_resource_check',return_value={'status':'PASS','errors':[]}), \
             patch('factorykit.validation.platform.system',return_value='Linux'):
            result=doctor(self.config)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(next(x for x in result['checks'] if x['id']=='toy_isolated_harness')['status'],'FAIL')
        self.assertEqual(result['operator_readiness_authorization'],report['operator_authorization'])
