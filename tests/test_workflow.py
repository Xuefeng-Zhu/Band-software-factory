"""Watchdog regressions are entirely offline and use temporary operational state."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from factorykit.workflow import WorkflowError, WorkflowWatchdog, parse_header

ROOM='00000000-0000-4000-8000-000000000001'
PM='00000000-0000-4000-8000-000000000002'
BACKEND='00000000-0000-4000-8000-000000000003'
QA='00000000-0000-4000-8000-000000000004'
DIGEST='a'*64


def eid(n):return f'00000000-0000-4000-8000-{n:012d}'

def part(index,total=5,recipient=PM,digest=DIGEST,delivery='S1-BACKEND-RESULT-001',body=None):
    body=body if body is not None else f'Original payload part {index}.'
    return f'S1-IMPLEMENTATION delivery {delivery} part {index}/{total}; SHA-256 {digest}; recipient @[[{recipient}]]\n{body}' + ('\nEND OF HANDOFF' if index==total else '')

def ack(delivery='S1-BACKEND-RESULT-001',digest=DIGEST,sender=BACKEND):
    return f'HANDOFF-ACK delivery {delivery}; SHA-256 {digest}; sender @[[{sender}]]'


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'workflow.json';self.now=1000.0
        self.kwargs=dict(path=self.path,room_id=ROOM,pm_id=PM,participant_ids=[PM,BACKEND,QA],ack_timeout_seconds=120,max_notices=2,clock=lambda:self.now)
        self.w=WorkflowWatchdog(**self.kwargs)
        self.w.begin_turn(BACKEND,'backend-turn',1600.0)

    def send(self,index,total=5,**kwargs):
        return self.w.observe_outbound(eid(100+index),BACKEND,[PM],part(index,total,**kwargs),'backend-turn')

    def claim(self):
        p=self.w.due_notice(can_notify=True);self.assertIsNotNone(p)
        claimed=self.w.claim_notice(p['notice_id'],can_notify=True);self.assertEqual(claimed,p)
        return p

    def test_outbound_preview_is_read_only_and_reuses_post_validation(self):
        before=self.path.read_bytes()
        self.w.preview_outbound(BACKEND,[PM],part(1),'backend-turn')
        self.assertEqual(self.path.read_bytes(),before)
        self.assertTrue(self.send(1)['multipart'])
        before=self.path.read_bytes()
        with self.assertRaises(WorkflowError):
            self.w.preview_outbound(BACKEND,[PM],part(1,body='changed'),'backend-turn')
        self.assertEqual(self.path.read_bytes(),before)
        # A real already-posted conflict still fails closed and retains evidence.
        result=self.w.observe_outbound(eid(999),BACKEND,[PM],part(1,body='changed'),'backend-turn')
        self.assertTrue(result['blocked'])
        self.assertEqual(self.w.health()['state'],'blocked')

    def test_four_of_five_timeout_produces_pm_only_notice_with_original_ids(self):
        for i in range(1,5):self.send(i)
        self.now=1600.26
        self.w.end_turn('backend-turn','failed','timeout')
        self.assertEqual(self.w.health()['state'],'stalled')
        p=self.claim()
        self.assertEqual(p['sender_id'],BACKEND);self.assertEqual(p['recipient_ids'],[PM])
        self.assertIn('missing 5',p['content']);self.assertIn('S1-BACKEND-RESULT-001',p['content'])
        self.assertNotIn('Original payload',p['content']);self.assertIn('not a complete handoff or acceptance',p['content'])
        persisted=json.loads(self.path.read_text())
        self.assertEqual(persisted['notices'][p['notice_id']]['status'],'claimed')
        self.assertEqual(persisted['incidents'][p['incident_id']]['attempts'],1)
        self.assertIsNone(self.w.claim_notice(p['notice_id'],can_notify=True))
        self.w.complete_notice(p['notice_id'],eid(501))

    def test_full_delivery_and_exact_recipient_ack_never_emit_notice(self):
        for i in range(1,6):self.send(i)
        self.w.observe_outbound(eid(200),PM,[BACKEND],ack())
        self.w.end_turn('backend-turn','completed')
        self.now=2000
        self.assertIsNone(self.w.due_notice(can_notify=True));self.assertEqual(self.w.health()['state'],'idle')
        self.assertTrue(json.loads(self.path.read_text())['deliveries']['S1-BACKEND-RESULT-001']['acknowledged'])

    def test_transport_complete_is_not_ack_and_ack_timeout_is_executable(self):
        for i in range(1,6):self.send(i)
        self.w.end_turn('backend-turn','completed')
        self.now=1119.999;self.assertIsNone(self.w.due_notice(can_notify=True));self.assertEqual(self.w.health()['state'],'waiting')
        self.now=1120;p=self.claim();self.assertIn('canonical recipient acknowledgment is still missing',p['content'])
        self.assertNotIn('missing 5',p['content'])

    def test_partial_before_ack_deadline_waits_even_when_process_is_alive(self):
        self.send(1);self.w.end_turn('backend-turn','completed')
        self.assertEqual(self.w.health()['state'],'waiting');self.assertIsNone(self.w.due_notice(can_notify=True))
        self.now=1120;self.assertEqual(self.w.health()['state'],'stalled')

    def test_failed_turn_without_handoff_is_reported_and_limits_are_not_raised(self):
        self.w.end_turn('backend-turn','failed','provider_failure')
        p=self.claim();self.assertEqual(p['sender_id'],BACKEND);self.assertIn('original turn failed',p['content'])
        self.assertEqual(json.loads(self.path.read_text())['turns']['backend-turn']['deadline_at'],1600)
        with self.assertRaises(WorkflowError):self.w.end_turn('backend-turn','failed','secret raw exception')

    def test_unknown_outcome_deadline_has_status_and_can_be_refined_by_real_lifecycle(self):
        self.assertEqual(self.w.health()['state'],'busy');self.assertEqual(self.w.health()['seconds_to_next_deadline'],600)
        self.now=1600;self.assertEqual(self.w.queue_timeout_notices()['state'],'stalled')
        self.w.end_turn('backend-turn','failed','timeout')
        self.assertEqual(self.w.health()['state'],'stalled')

    def test_late_confirmed_completion_closes_unclaimed_unknown_turn(self):
        self.now=1600;self.w.queue_timeout_notices();self.w.end_turn('backend-turn','completed')
        self.assertEqual(self.w.health()['state'],'idle');self.assertIsNone(self.w.due_notice(can_notify=True))

    def test_notice_requires_explicit_budget_permission_both_at_due_and_claim(self):
        self.w.end_turn('backend-turn','failed','timeout')
        self.assertIsNone(self.w.due_notice());p=self.w.due_notice(can_notify=True)
        self.assertIsNone(self.w.claim_notice(p['notice_id']));self.assertEqual(self.w.health()['notice_attempts'],0)

    def test_unknown_send_never_retries_and_blocks_health(self):
        self.w.end_turn('backend-turn','failed','timeout');p=self.claim();self.w.unknown_notice(p['notice_id'])
        self.now=5000
        self.assertEqual(self.w.health()['state'],'blocked');self.assertIsNone(self.w.due_notice(can_notify=True))
        self.w=WorkflowWatchdog(**self.kwargs)
        self.assertEqual(self.w.health()['notice_attempts'],1);self.assertIsNone(self.w.due_notice(can_notify=True))
        with self.assertRaises(WorkflowError):self.w.complete_notice(p['notice_id'],eid(600))

    def test_restart_after_claim_is_unknown_before_any_send_is_retried(self):
        self.w.end_turn('backend-turn','failed','timeout');p=self.claim()
        self.w=WorkflowWatchdog(**self.kwargs)
        self.assertEqual(self.w.health()['unknown_notices'],[p['notice_id']]);self.assertIsNone(self.w.due_notice(can_notify=True))

    def test_restart_after_confirmed_notice_preserves_two_attempt_bound(self):
        self.send(1);self.w.end_turn('backend-turn','failed','timeout')
        p=self.claim();self.w.complete_notice(p['notice_id'],eid(601));self.w=WorkflowWatchdog(**self.kwargs)
        self.assertIsNone(self.w.due_notice(can_notify=True));self.now+=120
        second=self.claim();self.assertEqual(second['attempt'],2);self.w.complete_notice(second['notice_id'],eid(602))
        self.now+=120;self.w=WorkflowWatchdog(**self.kwargs)
        self.assertIsNone(self.w.due_notice(can_notify=True));self.assertEqual(self.w.health()['state'],'blocked')

    def test_configured_one_notice_cap_is_lower_than_default(self):
        other=Path(self.temp.name)/'one.json';w=WorkflowWatchdog(**dict(self.kwargs,path=other,max_notices=1))
        w.begin_turn(PM,'pm-turn',1600);w.end_turn('pm-turn','failed','timeout')
        p=w.due_notice(can_notify=True);p=w.claim_notice(p['notice_id'],can_notify=True)
        self.assertEqual(p['sender_id'],PM);self.assertEqual(p['recipient_ids'],[PM])
        w.complete_notice(p['notice_id'],eid(603));self.now+=120
        self.assertIsNone(w.due_notice(can_notify=True));self.assertEqual(w.health()['notice_attempts'],1)

    def test_duplicate_parts_receipts_lifecycle_and_completion_are_idempotent(self):
        self.w.begin_turn(BACKEND,'backend-turn',1600)
        for i in range(1,6):self.send(i)
        self.assertTrue(self.send(5)['duplicate'])
        self.w.observe_outbound(eid(205),BACKEND,[PM],part(5),'backend-turn')
        self.w.observe_outbound(eid(210),PM,[BACKEND],ack());self.w.observe_outbound(eid(210),PM,[BACKEND],ack())
        self.w.end_turn('backend-turn','completed');self.w.end_turn('backend-turn','completed')
        self.assertEqual(self.w.health()['notice_attempts'],0)

    def test_binding_conflicts_and_malformed_final_fail_closed_without_payload_storage(self):
        cases=[part(2,digest='b'*64),part(2,recipient=QA),part(5).removesuffix('\nEND OF HANDOFF'),part(1,body='different bytes')]
        for n,content in enumerate(cases):
            w=WorkflowWatchdog(**dict(self.kwargs,path=Path(self.temp.name)/f'bad{n}.json'))
            w.begin_turn(BACKEND,'t',1600);w.observe_outbound(eid(300),BACKEND,[PM],part(1),'t')
            self.assertTrue(w.observe_outbound(eid(301),BACKEND,[PM],content,'t')['blocked'])
            self.assertEqual(w.health()['state'],'blocked');self.assertIsNone(w.due_notice(can_notify=True))
            self.assertNotIn('different bytes',w.path.read_text())

    def test_ack_before_full_receipt_or_wrong_binding_is_blocked(self):
        for n,(sender,recipients,text) in enumerate([(PM,[BACKEND],ack()),(QA,[BACKEND],ack()),(PM,[QA],ack()),(PM,[BACKEND],ack(digest='b'*64))]):
            w=WorkflowWatchdog(**dict(self.kwargs,path=Path(self.temp.name)/f'ack{n}.json'))
            w.begin_turn(BACKEND,'t',1600)
            for i in range(1,5 if n==0 else 6):w.observe_outbound(eid(310+i),BACKEND,[PM],part(i),'t')
            self.assertTrue(w.observe_outbound(eid(320),sender,recipients,text)['blocked']);self.assertEqual(w.health()['state'],'blocked')

    def test_retry_turn_links_to_existing_delivery_incident_not_new_attempt_budget(self):
        self.send(1);self.w.end_turn('backend-turn','failed','timeout');first=self.claim();self.w.complete_notice(first['notice_id'],eid(650))
        self.now+=120;self.w.begin_turn(BACKEND,'retry-turn',2000)
        self.w.observe_outbound(eid(401),BACKEND,[PM],part(2),'retry-turn');self.w.end_turn('retry-turn','failed','timeout')
        second=self.claim();self.assertEqual(second['incident_id'],first['incident_id']);self.assertEqual(second['attempt'],2)
        self.w.complete_notice(second['notice_id'],eid(651));self.now+=120
        self.assertIsNone(self.w.due_notice(can_notify=True));self.assertEqual(len(json.loads(self.path.read_text())['incidents']),1)

    def test_unknown_roster_scope_change_missing_state_and_invalid_json_never_reset(self):
        before=self.path.read_bytes()
        with self.assertRaises(WorkflowError):WorkflowWatchdog(**dict(self.kwargs,room_id=eid(999)))
        self.assertEqual(self.path.read_bytes(),before)
        with self.assertRaises(WorkflowError):self.w.begin_turn(eid(998),'x',1600)
        self.path.unlink()
        with self.assertRaises(WorkflowError):WorkflowWatchdog(**self.kwargs)
        self.assertFalse(self.path.exists())
        self.path.write_text('{bad')
        with self.assertRaises(WorkflowError):WorkflowWatchdog(**self.kwargs)
        self.assertEqual(self.path.read_text(),'{bad')

    def test_parser_rejects_invalid_numbering_and_partial_headers(self):
        for content in [part(1).replace('1/5','0/5'),part(1).replace('1/5','6/5'),part(1).replace('1/5','1/129'),part(1).replace(DIGEST,'aaa'), 'delivery x part 1/5']:
            with self.subTest(content=content[:90]),self.assertRaises(WorkflowError):parse_header(content)
        self.assertIsNone(parse_header('Ordinary progress text.'))

    def test_failed_notice_handler_keeps_original_sender_incident_and_cap(self):
        self.w.end_turn('backend-turn','failed','timeout');first=self.claim();self.w.complete_notice(first['notice_id'],eid(800))
        self.w.begin_turn(PM,'pm-notice',1600,trigger_event_id=eid(800))
        self.w.end_turn('pm-notice','failed','timeout')
        second=self.claim();self.assertEqual(second['sender_id'],BACKEND);self.assertEqual(second['incident_id'],first['incident_id']);self.assertEqual(second['attempt'],2)
        self.w.complete_notice(second['notice_id'],eid(801))
        self.w.begin_turn(PM,'pm-notice2',1600,trigger_event_id=eid(801));self.w.end_turn('pm-notice2','failed','timeout')
        self.assertIsNone(self.w.due_notice(can_notify=True));self.assertEqual(self.w.health()['state'],'blocked')
        self.assertEqual(len(json.loads(self.path.read_text())['incidents']),1)

    def test_completed_pm_notice_handling_closes_only_no_delivery_incident(self):
        self.w.end_turn('backend-turn','failed','timeout');notice=self.claim();self.w.complete_notice(notice['notice_id'],eid(810))
        self.w.begin_turn(PM,'pm-notice',1600,trigger_event_id=eid(810));self.w.end_turn('pm-notice','completed')
        self.assertEqual(self.w.health()['state'],'waiting')
        self.assertTrue(self.w.observe_notice_handled(eid(810),PM));self.assertEqual(self.w.health()['state'],'idle')
        self.assertTrue(self.w.observe_notice_handled(eid(810),PM))
        with self.assertRaises(WorkflowError):self.w.observe_notice_handled(eid(810),BACKEND)
        self.assertFalse(self.w.observe_notice_handled(eid(811),PM))

    def test_notice_handled_does_not_acknowledge_partial_delivery(self):
        self.send(1);self.w.end_turn('backend-turn','failed','timeout');notice=self.claim();self.w.complete_notice(notice['notice_id'],eid(820))
        self.w.observe_notice_handled(eid(820),PM);self.now+=120
        self.assertIsNotNone(self.w.due_notice(can_notify=True))
        self.assertFalse(json.loads(self.path.read_text())['deliveries']['S1-BACKEND-RESULT-001']['acknowledged'])

    def test_unknown_protocol_delivery_stays_blocked_after_turn_completes(self):
        self.w.block_turn_delivery('backend-turn');self.assertEqual(self.w.health()['state'],'blocked')
        self.assertEqual(json.loads(self.path.read_text())['turns']['backend-turn']['status'],'running')
        self.w.end_turn('backend-turn','completed');self.w=WorkflowWatchdog(**self.kwargs)
        self.assertEqual(self.w.health()['state'],'blocked');self.assertIsNone(self.w.due_notice(can_notify=True))
        with self.assertRaises(WorkflowError):self.w.block_turn_delivery('backend-turn','raw error')

    def test_canonical_ack_rejects_trailing_contradictory_payload(self):
        for i in range(1,6):self.send(i)
        self.assertTrue(self.w.observe_outbound(eid(850),PM,[BACKEND],ack()+'\nINCOMPLETE: not received.')['blocked'])
        self.assertEqual(self.w.health()['state'],'blocked')

    def test_giant_number_is_recorded_as_blocked_not_integer_conversion_failure(self):
        content=part(1).replace('part 1/5','part '+('9'*5000)+'/5')
        self.assertTrue(self.w.observe_outbound(eid(851),BACKEND,[PM],content,'backend-turn')['blocked'])
        self.assertEqual(self.w.health()['state'],'blocked')

    def test_malformed_nested_counters_and_references_fail_closed_before_claim(self):
        self.w.end_turn('backend-turn','failed','timeout')
        original=json.loads(self.path.read_text())
        for change in [lambda d:d['incidents']['turn:backend-turn'].update(attempts=-1),
                       lambda d:d['incidents']['turn:backend-turn'].update(attempts=True),
                       lambda d:d['incidents']['turn:backend-turn'].update(attempts=1),
                       lambda d:d['turns']['backend-turn'].update(incident_ids=['missing']),
                       lambda d:d['turns']['backend-turn'].update(deadline_at='never')]:
            data=copy.deepcopy(original);change(data);self.path.write_text(json.dumps(data));before=self.path.read_bytes()
            with self.assertRaises(WorkflowError):WorkflowWatchdog(**self.kwargs)
            self.assertEqual(self.path.read_bytes(),before)
        self.path.write_text(json.dumps(original))

    def test_ordinary_non_pm_callback_is_not_a_notice(self):
        self.assertFalse(self.w.observe_notice_handled(eid(852),BACKEND))

    def test_websocket_turn_arriving_before_post_confirmation_keeps_original_cap(self):
        self.w.end_turn('backend-turn','failed','timeout');notice=self.claim()
        self.w.begin_turn(PM,'early-pm',1600,trigger_event_id=eid(860))
        self.w.complete_notice(notice['notice_id'],eid(860));self.w.end_turn('early-pm','failed','timeout')
        second=self.claim();self.assertEqual(second['incident_id'],notice['incident_id']);self.assertEqual(second['attempt'],2)
        self.w.complete_notice(second['notice_id'],eid(861));self.now+=120
        self.assertIsNone(self.w.due_notice(can_notify=True));self.assertEqual(len(json.loads(self.path.read_text())['incidents']),1)

    def test_early_pm_failure_before_post_confirmation_fails_closed_without_new_chain(self):
        self.w.end_turn('backend-turn','failed','timeout');notice=self.claim()
        self.w.begin_turn(PM,'early-pm',1600,trigger_event_id=eid(862));self.w.end_turn('early-pm','failed','timeout')
        self.assertIsNone(self.w.due_notice(can_notify=True))
        self.w.complete_notice(notice['notice_id'],eid(862))
        self.assertEqual(self.w.health()['state'],'blocked');self.assertIsNone(self.w.due_notice(can_notify=True))
        self.assertEqual(self.w.health()['notice_attempts'],1)

    def test_early_completed_pm_callback_is_bound_as_handled_after_confirmation(self):
        self.w.end_turn('backend-turn','failed','timeout');notice=self.claim()
        self.w.begin_turn(PM,'early-pm',1600,trigger_event_id=eid(863));self.w.end_turn('early-pm','completed')
        self.w.complete_notice(notice['notice_id'],eid(863))
        self.assertEqual(self.w.health()['state'],'idle')

    def test_exhausted_notice_wait_does_not_cut_short_pm_or_other_active_turn(self):
        for n,agent in enumerate((PM,QA)):
            self.now=1000
            w=WorkflowWatchdog(**dict(self.kwargs,path=Path(self.temp.name)/f'active{n}.json'))
            w.begin_turn(BACKEND,'b',1600)
            w.observe_outbound(eid(900),BACKEND,[PM],part(1),'b');w.end_turn('b','failed','timeout')
            first=w.due_notice(can_notify=True);w.claim_notice(first['notice_id'],can_notify=True);w.complete_notice(first['notice_id'],eid(901))
            self.now+=120
            second=w.due_notice(can_notify=True);w.claim_notice(second['notice_id'],can_notify=True);w.complete_notice(second['notice_id'],eid(902))
            w.begin_turn(agent,'active',self.now+600,trigger_event_id=eid(902) if agent==PM else None)
            self.now+=121
            self.assertEqual(w.health()['state'],'busy')
            self.assertEqual(w.health()['seconds_to_next_deadline'],479)
            self.assertIsNone(w.due_notice(can_notify=True))
            w.end_turn('active','completed')
            if agent==PM:w.observe_notice_handled(eid(902),PM)
            self.assertEqual(w.health()['state'],'blocked')
            self.assertEqual(w.health()['notice_attempts'],2)

    def test_explicit_unknown_delivery_blocks_even_during_active_recovery(self):
        self.w.end_turn('backend-turn','failed','timeout');notice=self.claim();self.w.complete_notice(notice['notice_id'],eid(910))
        self.w.begin_turn(PM,'active',1600,trigger_event_id=eid(910))
        self.w.block_turn_delivery('active')
        self.assertEqual(self.w.health()['state'],'blocked')
        self.assertEqual(self.w.health()['active_turn_ids'],['active'])

    def test_confirmed_notice_completion_is_idempotent_but_other_identity_is_not(self):
        self.w.end_turn('backend-turn','failed','timeout');p=self.claim();self.w.complete_notice(p['notice_id'],eid(700));before=self.path.read_bytes()
        self.w.complete_notice(p['notice_id'],eid(700));self.assertEqual(self.path.read_bytes(),before)
        with self.assertRaises(WorkflowError):self.w.complete_notice(p['notice_id'],eid(701))


    def pm_delivery(self, recipients=(BACKEND,), total=12):
        self.w.end_turn('backend-turn','completed')
        self.w.begin_turn(PM,'pm-original',1600)
        target=', '.join('@[['+a+']]' for a in recipients)
        for n in range(1,total+1):
            text=(f'WORK delivery PM-ORIGINAL part {n}/{total}; SHA-256 {DIGEST}; recipient {target}\nOriginal {n}.'
                  + ('\nEND OF HANDOFF' if n==total else ''))
            self.w.observe_outbound(eid(1000+n),PM,list(recipients),text,'pm-original')
        self.w.end_turn('pm-original','completed')
        self.now+=120

    def test_pm_origin_receipt_notice_targets_original_peer_and_keeps_shared_retry_cap(self):
        self.pm_delivery()
        first=self.claim()
        self.assertEqual(first['sender_id'],PM)
        self.assertEqual(first['recipient_ids'],[BACKEND])
        self.assertIn('bounded receipt/reassembly only',first['content'])
        self.assertIn('exact original payload, digest and part identities',first['content'])
        self.assertIn('Do not start, repeat or reassign implementation',first['content'])
        self.assertIn(DIGEST,first['content'])
        self.w.complete_notice(first['notice_id'],eid(1100))
        self.w.begin_turn(BACKEND,'peer-notice',self.now+600,trigger_event_id=eid(1100))
        self.w.end_turn('peer-notice','failed','timeout')
        second=self.claim()
        self.assertEqual(second['incident_id'],first['incident_id'])
        self.assertEqual(second['attempt'],2)
        self.assertEqual(second['sender_id'],PM)
        self.w.complete_notice(second['notice_id'],eid(1101))
        self.now+=120
        self.w=WorkflowWatchdog(**self.kwargs)
        self.assertIsNone(self.w.due_notice(can_notify=True))
        state=json.loads(self.path.read_text())
        self.assertEqual(len(state['incidents']),1)
        self.assertEqual(state['turns']['pm-original']['deadline_at'],1600)
        self.assertEqual(self.w.health()['state'],'blocked')

    def test_pm_notice_targets_only_unacknowledged_original_recipients(self):
        self.pm_delivery((BACKEND,QA))
        self.w.observe_outbound(eid(1110),QA,[PM],ack('PM-ORIGINAL',sender=PM))
        self.assertEqual(self.claim()['recipient_ids'],[BACKEND])

    def test_multirecipient_notice_handling_requires_every_exact_recipient_and_is_not_ack(self):
        self.pm_delivery((BACKEND,QA))
        notice=self.claim();self.w.complete_notice(notice['notice_id'],eid(1120))
        with self.assertRaises(WorkflowError):self.w.observe_notice_handled(eid(1120),PM)
        self.assertTrue(self.w.observe_notice_handled(eid(1120),BACKEND))
        state=json.loads(self.path.read_text());stored=state['notices'][notice['notice_id']]
        self.assertEqual(stored['handled_by'],[BACKEND]);self.assertNotIn('handled_at',stored)
        self.assertFalse(state['deliveries']['PM-ORIGINAL']['acknowledged'])
        self.assertTrue(self.w.observe_notice_handled(eid(1120),QA))
        before=self.path.read_bytes();self.w.observe_notice_handled(eid(1120),QA)
        self.assertEqual(self.path.read_bytes(),before)
        state=json.loads(self.path.read_text());stored=state['notices'][notice['notice_id']]
        self.assertEqual(stored['handled_by'],[BACKEND,QA]);self.assertIn('handled_at',stored)
        self.assertFalse(state['deliveries']['PM-ORIGINAL']['acknowledged'])
        self.now+=120;self.assertEqual(self.w.due_notice(can_notify=True)['attempt'],2)

    def test_early_peer_callbacks_bind_to_original_notice_after_post_confirmation(self):
        self.pm_delivery((BACKEND,QA));notice=self.claim()
        self.w.begin_turn(BACKEND,'early-backend',self.now+600,trigger_event_id=eid(1130))
        self.w.end_turn('early-backend','completed')
        self.w.begin_turn(QA,'early-qa',self.now+600,trigger_event_id=eid(1130))
        self.w.complete_notice(notice['notice_id'],eid(1130))
        state=json.loads(self.path.read_text());stored=state['notices'][notice['notice_id']]
        self.assertEqual(stored['handled_by'],[BACKEND]);self.assertNotIn('handled_at',stored)
        self.assertEqual(state['turns']['early-backend']['incident_ids'],[notice['incident_id']])
        self.assertEqual(state['turns']['early-qa']['incident_ids'],[notice['incident_id']])
        self.w.end_turn('early-qa','failed','timeout')
        retry=self.claim();self.assertEqual(retry['incident_id'],notice['incident_id'])
        self.assertEqual(retry['attempt'],2)
        self.assertEqual(len(json.loads(self.path.read_text())['incidents']),1)

    def test_tampered_pm_notice_target_cannot_gain_authority_on_restart(self):
        self.pm_delivery();notice=self.claim();self.w.complete_notice(notice['notice_id'],eid(1140))
        data=json.loads(self.path.read_text());data['notices'][notice['notice_id']]['recipient_ids']=[QA]
        self.path.write_text(json.dumps(data));before=self.path.read_bytes()
        with self.assertRaises(WorkflowError):WorkflowWatchdog(**self.kwargs)
        self.assertEqual(self.path.read_bytes(),before)

    def test_sdk_queue_defers_exhaustion_only_without_renewing_incident_or_turn(self):
        self.pm_delivery()
        for n in range(2):
            notice=self.claim();self.w.complete_notice(notice['notice_id'],eid(1150+n));self.now+=120
        before=self.path.read_bytes()
        self.assertEqual(self.w.queue_timeout_notices(execution_busy=True)['state'],'busy')
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(self.w.health(execution_busy=False)['state'],'blocked')
        self.assertEqual(self.path.read_bytes(),before)

    def test_sdk_queue_never_defers_conflicting_or_unknown_delivery(self):
        self.pm_delivery();notice=self.claim();self.w.unknown_notice(notice['notice_id'])
        self.assertEqual(self.w.health(execution_busy=True)['state'],'blocked')
        self.assertIsNone(self.w.due_notice(can_notify=True))


if __name__=='__main__':unittest.main()
