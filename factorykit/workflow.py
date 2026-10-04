"""Persistent operational watchdog; never calls BAND, a model, or product tools.

The caller observes confirmed outbound text only, supplies real lifecycle events,
and checks the shared budget before BOTH claiming and sending a notice. A complete
multipart record proves numbered sends with consistent declared digest and final
marker, not payload-digest correctness, recipient action, or product acceptance.
One owned supervisor constructs this object once; a new instance treats an
unfinished write-ahead send claim as unknown and never retries that delivery.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
import time
from uuid import UUID

from .common import canonical


class WorkflowError(ValueError):
    """Safe operational state/configuration error; never includes payload text."""


_UUID = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
_HEADER = re.compile(
    r"^(?:[A-Za-z0-9_.:/ -]+ )?delivery (?P<delivery>[A-Za-z0-9][A-Za-z0-9._-]{0,127}) "
    r"part (?P<index>[1-9][0-9]{0,2})/(?P<total>[1-9][0-9]{0,2}); SHA-256 (?P<digest>[0-9a-fA-F]{64}); "
    rf"recipient (?P<recipients>@\[\[{_UUID}\]\](?:,? @\[\[{_UUID}\]\])*)$"
)
_ACK = re.compile(rf"^HANDOFF-ACK delivery (?P<delivery>[A-Za-z0-9][A-Za-z0-9._-]{{0,127}}); SHA-256 (?P<digest>[0-9a-fA-F]{{64}}); sender @\[\[(?P<sender>{_UUID})\]\]$")
_CANDIDATE = re.compile(r"\bdelivery\s+\S+\s+part\b", re.I)


def _uuid(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except ValueError:
        return False


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def parse_header(content: str):
    """Return None for ordinary text; malformed protocol headers fail closed."""
    if not isinstance(content, str):
        raise WorkflowError("Outbound text must be a string.")
    first = content.splitlines()[0] if content.splitlines() else ""
    match = _HEADER.fullmatch(first)
    if not match:
        if _CANDIDATE.search(first):
            raise WorkflowError("Malformed multipart header; delivery completeness is unknown.")
        return None
    data = match.groupdict()
    data.update(index=int(data['index']), total=int(data['total']), digest=data['digest'].lower())
    data['recipients'] = re.findall(rf"@\[\[({_UUID})\]\]", data['recipients'])
    if (not 1 <= data['index'] <= data['total'] <= 128
            or len(set(data['recipients'])) != len(data['recipients'])):
        raise WorkflowError("Multipart numbering or recipient binding is invalid.")
    data['recipients'].sort()
    body = [line.strip() for line in content.splitlines()[1:] if line.strip()]
    data['final_marker'] = bool(body) and body[-1] == 'END OF HANDOFF'
    if data['index'] == data['total'] and not data['final_marker']:
        raise WorkflowError("Final multipart send is missing END OF HANDOFF.")
    return data


class WorkflowWatchdog:
    def __init__(self, path, room_id, pm_id, participant_ids, ack_timeout_seconds,
                 max_notices=2, clock=time.time):
        ids = list(participant_ids)
        if (not _uuid(room_id) or not _uuid(pm_id) or not ids or any(not _uuid(x) for x in ids)
                or len(set(ids)) != len(ids) or pm_id not in ids
                or type(ack_timeout_seconds) is not int or ack_timeout_seconds < 1
                or type(max_notices) is not int or not 1 <= max_notices <= 2):
            raise WorkflowError("Watchdog requires exact room/agent UUIDs and finite notice limits of one or two.")
        self.path, self.clock = Path(path), clock
        self.scope = dict(room_id=room_id, pm_id=pm_id, participant_ids=sorted(ids),
                          ack_timeout_seconds=ack_timeout_seconds, max_notices=max_notices)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self._transaction(create=True) as data:
            for notice in data['notices'].values():
                if notice['status'] == 'claimed':
                    notice['status'] = 'unknown'
                    data['incidents'][notice['incident_id']]['blocked'] = 'notice_delivery_unknown_after_restart'

    @contextmanager
    def _transaction(self, create=False):
        lock = self.path.with_suffix(self.path.suffix + '.lock')
        lock_existed = lock.exists()
        fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(fd)
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise WorkflowError("Watchdog lock must be privately owned.")
            fcntl.flock(fd, fcntl.LOCK_EX)
            if self.path.is_symlink():
                raise WorkflowError("Watchdog state cannot be a symlink.")
            if self.path.exists():
                info=self.path.stat()
                if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)&0o077:
                    raise WorkflowError('Watchdog state must be a privately owned regular file.')
                try:
                    data = json.loads(self.path.read_text())
                    if (data['version'] != 1 or data['scope'] != self.scope
                            or any(not isinstance(data[k], dict) for k in ('turns','deliveries','events','incidents','notices'))):
                        raise ValueError()
                    self._validate_state(data)
                except (ValueError, KeyError, TypeError):
                    raise WorkflowError("Watchdog state is malformed or its scope changed; no reset is allowed.") from None
            elif create and not lock_existed:
                data = dict(version=1, scope=self.scope, turns={}, deliveries={}, events={}, incidents={}, notices={})
            else:
                raise WorkflowError("Existing watchdog state is missing; no reset is allowed.")
            before = canonical(data)
            yield data
            if not self.path.exists() or canonical(data) != before:
                self._validate_state(data)
                self._durable_write(data)
        finally:
            os.close(fd)

    def _durable_write(self, data):
        fd, name=tempfile.mkstemp(prefix='.'+self.path.name,dir=self.path.parent)
        try:
            with os.fdopen(fd,'wb') as output:
                output.write(canonical(data));output.flush();os.fsync(output.fileno())
            os.replace(name,self.path)
            directory=os.open(self.path.parent,os.O_RDONLY)
            try:os.fsync(directory)
            finally:os.close(directory)
        finally:
            Path(name).unlink(missing_ok=True)

    def _validate_state(self, d):
        """Reject malformed retained authority before it can admit another notice."""
        def need(value):
            if not value:raise WorkflowError('Malformed retained workflow authority; preserve state for reconciliation.')
        def integer(v,low=0,high=None):return type(v) is int and v>=low and (high is None or v<=high)
        def unique(v):return isinstance(v,list) and all(isinstance(x,str) for x in v) and len(v)==len(set(v))
        def sha(v):return isinstance(v,str) and re.fullmatch(r'[0-9a-f]{64}',v)
        def moment(v):return _finite(v) and v>=0
        agents=set(self.scope['participant_ids']);cap=self.scope['max_notices']
        try:
            for event,b in d['events'].items():
                need(_uuid(event) and b['sender_id'] in agents and unique(b['recipient_ids']) and b['recipient_ids'] and set(b['recipient_ids'])<=agents and sha(b['content_sha256']))
                need(b['turn_id'] is None or (b['turn_id'] in d['turns'] and d['turns'][b['turn_id']]['agent_id']==b['sender_id']))
            for key,t in d['turns'].items():
                need(isinstance(key,str) and key and t['agent_id'] in agents and moment(t['started_at']) and moment(t['deadline_at']) and t['deadline_at']>t['started_at'])
                need(t['status'] in ('running','completed','failed','interrupted','unknown') and t['reason_code'] in ('','timeout','interrupted','unknown','provider_failure'))
                need(unique(t['incident_ids']) and set(t['incident_ids'])<=set(d['incidents']))
                need(t.get('trigger_event_id') is None or _uuid(t['trigger_event_id']))
                if t['status']!='running':need(moment(t['ended_at']) and t['ended_at']>=t['started_at'])
            for key,v in d['deliveries'].items():
                need(isinstance(key,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}',key))
                need(v['sender_id'] in agents and unique(v['recipient_ids']) and v['recipient_ids'] and set(v['recipient_ids'])<=agents and sha(v['digest']))
                need(integer(v['total'],1,128) and moment(v['first_at']) and v['incident_id'] in d['incidents'] and isinstance(v['parts'],dict) and isinstance(v['acks'],dict))
                for number,p in v['parts'].items():
                    need(isinstance(number,str) and re.fullmatch(r'[1-9][0-9]{0,2}',number) and int(number)<=v['total'] and sha(p['sha256']) and p['event_id'] in d['events'])
                    e=d['events'][p['event_id']]
                    need(e['sender_id']==v['sender_id'] and e['recipient_ids']==v['recipient_ids'] and e['content_sha256']==p['sha256'])
                need(type(v['complete']) is bool and v['complete']==(len(v['parts'])==v['total']))
                for recipient,event in v['acks'].items():
                    need(recipient in v['recipient_ids'] and event in d['events'])
                    e=d['events'][event];need(e['sender_id']==recipient and v['sender_id'] in e['recipient_ids'])
                need(type(v['acknowledged']) is bool and v['acknowledged']==(v['complete'] and set(v['acks'])==set(v['recipient_ids'])))
            for key,i in d['incidents'].items():
                need(isinstance(key,str) and key and i['sender_id'] in agents and integer(i['attempts'],0,cap) and moment(i['created_at']) and moment(i['next_at']))
                need(type(i['failed']) is bool and type(i['closed']) is bool and i['blocked'] in (None,'notice_delivery_unknown_after_restart','invalid_or_conflicting_multipart','notice_delivery_unknown','conflicting_duplicate_event','outbound_delivery_unknown','notice_trigger_binding_conflict'))
                need(unique(i['deliveries']) and all(x in d['deliveries'] and d['deliveries'][x]['incident_id']==key for x in i['deliveries']))
                attempts=[n['attempt'] for n in d['notices'].values() if n['incident_id']==key]
                need(sorted(attempts)==list(range(1,i['attempts']+1)))
            seen=set()
            for key,n in d['notices'].items():
                need(isinstance(key,str) and re.fullmatch(r'[0-9a-f]{32}',key) and n['incident_id'] in d['incidents'] and integer(n['attempt'],1,cap) and moment(n['claimed_at']))
                need(n['status'] in ('claimed','sent','unknown') and n['sender_id']==d['incidents'][n['incident_id']]['sender_id'] and n['recipient_ids']==[self.scope['pm_id']] and sha(n['content_sha256']))
                if n['status']=='sent':
                    need(_uuid(n['event_id']) and n['event_id'] not in seen and moment(n['sent_at']) and n['sent_at']>=n['claimed_at']);seen.add(n['event_id'])
                    if 'handled_at' in n:need(moment(n['handled_at']) and n['handled_at']>=n['sent_at'])
                if n['status']=='unknown':need(d['incidents'][n['incident_id']]['blocked'] is not None)
        except (KeyError,TypeError,ValueError,AttributeError):
            raise WorkflowError('Malformed retained workflow authority; preserve state for reconciliation.') from None

    def _now(self):
        now = self.clock()
        if not _finite(now):
            raise WorkflowError("Watchdog clock must be finite.")
        return now

    def _agent(self, agent):
        if agent not in self.scope['participant_ids']:
            raise WorkflowError("Unknown agent is outside the configured room roster.")

    def begin_turn(self, agent_id, turn_id, deadline_at, trigger_event_id=None):
        self._agent(agent_id)
        now = self._now()
        if not isinstance(turn_id, str) or not turn_id or not _finite(deadline_at) or deadline_at <= now:
            raise WorkflowError("Turn requires a real identity and future finite deadline.")
        with self._transaction() as d:
            old = d['turns'].get(turn_id)
            if old:
                if old['agent_id'] != agent_id or old['deadline_at'] != deadline_at or old.get('trigger_event_id') != trigger_event_id:
                    raise WorkflowError("Conflicting lifecycle identity; original turn is retained.")
                return
            linked=[]
            if trigger_event_id is not None:
                if not _uuid(trigger_event_id):
                    raise WorkflowError('Turn trigger must be an exact event UUID.')
                matches=[n for n in d['notices'].values() if n.get('event_id')==trigger_event_id and n['status']=='sent']
                if matches:
                    if len(matches)!=1 or agent_id!=self.scope['pm_id']:
                        raise WorkflowError('Operational notice trigger is bound to the coordinator only.')
                    linked=[matches[0]['incident_id']]
            d['turns'][turn_id] = dict(agent_id=agent_id, started_at=now, deadline_at=deadline_at,
                status='running', reason_code='', incident_ids=linked, trigger_event_id=trigger_event_id)

    def _incident(self, d, key, sender, now):
        value = d['incidents'].setdefault(key, dict(sender_id=sender, created_at=now, next_at=now,
            attempts=0, failed=False, blocked=None, deliveries=[], closed=False))
        if value['sender_id'] != sender:
            raise WorkflowError("Incident sender binding conflicts with retained history.")
        return value

    def end_turn(self, turn_id, status, reason_code=''):
        if status not in ('completed','failed','interrupted','unknown'):
            raise WorkflowError("Unsupported terminal turn status.")
        # Never copy raw provider exceptions into operational notices.
        if reason_code not in ('','timeout','interrupted','unknown','provider_failure'):
            raise WorkflowError("Use a fixed operational reason code, not provider text.")
        with self._transaction() as d:
            turn = d['turns'].get(turn_id)
            if not turn:
                raise WorkflowError("Cannot finish an unobserved turn.")
            if turn['status'] != 'running' and not (turn['status']=='unknown' and turn['reason_code']=='unknown'):
                if turn['status'] == status and turn['reason_code'] == reason_code:
                    return
                raise WorkflowError("Conflicting terminal lifecycle; original outcome is retained.")
            turn.update(status=status, reason_code=reason_code, ended_at=self._now())
            keys = turn['incident_ids'] or ['turn:'+turn_id]
            for key in keys:
                if status != 'completed':
                    inc = d['incidents'].get(key) or self._incident(d, key, turn['agent_id'], self._now())
                    inc.update(failed=True, closed=False, next_at=self._now())
                elif key in d['incidents'] and key=='turn:'+turn_id:
                    inc=d['incidents'][key]
                    inc['failed']=False
                    inc['closed']=not inc['deliveries']

    def observe_outbound(self, event_id, sender_id, recipient_ids, content, turn_id=None):
        self._agent(sender_id)
        recipients = list(recipient_ids)
        if (not _uuid(event_id) or not recipients or any(x not in self.scope['participant_ids'] for x in recipients)
                or len(set(recipients)) != len(recipients)):
            raise WorkflowError("Confirmed outbound event requires exact event and recipient identities.")
        recipients.sort()
        if not isinstance(content, str):
            raise WorkflowError('Outbound text must be a string.')
        message_hash = hashlib.sha256(content.encode()).hexdigest()
        binding = dict(sender_id=sender_id, recipient_ids=recipients, content_sha256=message_hash, turn_id=turn_id)
        with self._transaction() as d:
            if event_id in d['events']:
                if d['events'][event_id] != binding:
                    self._incident(d, 'event:'+event_id, sender_id, self._now())['blocked']='conflicting_duplicate_event'
                    return {'blocked':True}
                return {'duplicate': True}
            if turn_id is not None and (turn_id not in d['turns'] or d['turns'][turn_id]['agent_id'] != sender_id):
                raise WorkflowError("Outbound delivery does not match its observed sending turn.")
            d['events'][event_id] = binding
            now = self._now()
            linked=d['turns'][turn_id]['incident_ids'] if turn_id else []
            incident_id=linked[0] if linked else 'turn:'+turn_id if turn_id else 'event:'+event_id
            try:
                first=content.splitlines()[0] if content.splitlines() else ''
                if first.startswith('HANDOFF-ACK'):
                    ack=_ACK.fullmatch(content.strip())
                    value=d['deliveries'].get(ack['delivery']) if ack else None
                    if value:
                        incident_id=value['incident_id']
                    if (not ack or not value or not value['complete']
                            or ack['digest'].lower()!=value['digest'] or ack['sender']!=value['sender_id']
                            or sender_id not in value['recipient_ids'] or value['sender_id'] not in recipients):
                        raise WorkflowError('Receipt is incomplete or has a conflicting identity binding.')
                    value['acks'].setdefault(sender_id,event_id)
                    value['acknowledged']=set(value['acks'])==set(value['recipient_ids'])
                    return {'receipt':True,'delivery_id':ack['delivery'],'acknowledged':value['acknowledged']}
                header = parse_header(content)
                if header is None:
                    return {'multipart': False}
                if header['recipients'] != recipients:
                    raise WorkflowError("Header recipients differ from confirmed send recipients.")
                key = header['delivery']
                value = d['deliveries'].get(key)
                expected = dict(sender_id=sender_id, recipient_ids=recipients, digest=header['digest'], total=header['total'])
                if value:
                    incident_id = value['incident_id']
                    if any(value[k] != v for k,v in expected.items()):
                        raise WorkflowError("Conflicting multipart identity, digest or recipient binding.")
                else:
                    value = d['deliveries'][key] = dict(**expected, incident_id=incident_id, parts={}, acks={}, first_at=now, complete=False, acknowledged=False)
                    inc = d['incidents'].get(incident_id) or self._incident(d, incident_id, sender_id, now)
                    inc['deliveries'].append(key)
                    inc['next_at'] = now + self.scope['ack_timeout_seconds']
                if turn_id and incident_id not in d['turns'][turn_id]['incident_ids']:
                    d['turns'][turn_id]['incident_ids'].append(incident_id)
                part = str(header['index'])
                if part in value['parts'] and value['parts'][part]['sha256'] != message_hash:
                    raise WorkflowError("Conflicting multipart payload under an existing part identity.")
                value['parts'].setdefault(part, dict(sha256=message_hash, event_id=event_id))
                value['complete'] = len(value['parts']) == value['total']
                return {'multipart': True, 'delivery_id':key, 'complete':value['complete']}
            except WorkflowError:
                incident = d['incidents'].get(incident_id) or self._incident(d, incident_id, sender_id, now)
                incident['blocked'] = 'invalid_or_conflicting_multipart'
                # Persist a failed-closed operational outcome, without storing payloads.
                return {'multipart': True, 'blocked': True}

    def _refresh(self, d, now):
        for key, turn in d['turns'].items():
            if turn['status'] == 'running' and now >= turn['deadline_at']:
                turn.update(status='unknown', reason_code='unknown', ended_at=now)
                for incident in turn['incident_ids'] or ['turn:'+key]:
                    value=d['incidents'].get(incident) or self._incident(d, incident, turn['agent_id'], now)
                    value.update(failed=True, next_at=now)

    def queue_timeout_notices(self):
        with self._transaction() as d:
            self._refresh(d, self._now())
        return self.health()

    def _resolved(self, d, inc):
        return inc['closed'] or (bool(inc['deliveries']) and all(d['deliveries'][x]['acknowledged'] for x in inc['deliveries']))

    def _proposal(self, d, incident_id, inc, now):
        if (inc['blocked'] or self._resolved(d, inc) or now < inc['next_at']
                or inc['attempts'] >= self.scope['max_notices']
                or any(n['incident_id']==incident_id and n['status']=='claimed' for n in d['notices'].values())):
            return None
        if not inc['failed'] and not inc['deliveries']:
            return None
        number = inc['attempts'] + 1
        identity = hashlib.sha256(f"{self.scope['room_id']}:{incident_id}:{number}".encode()).hexdigest()[:32]
        facts = []
        for name in inc['deliveries']:
            delivery = d['deliveries'][name]
            missing = [str(i) for i in range(1,delivery['total']+1) if str(i) not in delivery['parts']]
            if missing:
                facts.append(f"Delivery {name}: observed {len(delivery['parts'])}/{delivery['total']} parts; missing {','.join(missing)}; declared SHA-256 {delivery['digest']}.")
            elif not delivery['acknowledged']:
                facts.append(f"Delivery {name}: all {delivery['total']} numbered parts observed; canonical recipient acknowledgment is still missing; declared SHA-256 {delivery['digest']}.")
        if inc['failed']:
            facts.append('The original turn failed, was interrupted, or has no confirmed outcome by its recorded deadline.')
        text = (f"@[[{self.scope['pm_id']}]] WORKFLOW NOTICE {identity}; incident {incident_id}; attempt {number}/{self.scope['max_notices']}.\n"
                + '\n'.join(facts) + '\nRequest bounded operational recovery of the existing task and delivery within remaining approved limits. Preserve original requirements, candidate and failure evidence. This notice is not a complete handoff or acceptance; do not execute from partial requirements.')
        return dict(notice_id=identity, incident_id=incident_id, sender_id=inc['sender_id'],
                    recipient_ids=[self.scope['pm_id']], content=text, attempt=number)

    def due_notice(self, can_notify=False):
        with self._transaction() as d:
            now=self._now();self._refresh(d,now)
            if (can_notify is not True or any(i['blocked'] for i in d['incidents'].values())
                    or any(n['status']=='claimed' for n in d['notices'].values())):
                return None
            for key,inc in d['incidents'].items():
                value=self._proposal(d,key,inc,now)
                if value:return value
        return None

    def claim_notice(self, notice_id, can_notify=False):
        with self._transaction() as d:
            now=self._now();self._refresh(d,now)
            if (can_notify is not True or any(i['blocked'] for i in d['incidents'].values())
                    or any(n['status']=='claimed' for n in d['notices'].values())):return None
            for key,inc in d['incidents'].items():
                proposal=self._proposal(d,key,inc,now)
                if proposal and proposal['notice_id']==notice_id:
                    inc['attempts']+=1
                    inc['next_at']=now+self.scope['ack_timeout_seconds']
                    d['notices'][notice_id]=dict(incident_id=key,status='claimed',claimed_at=now,attempt=inc['attempts'],
                        sender_id=proposal['sender_id'],recipient_ids=proposal['recipient_ids'],content_sha256=hashlib.sha256(proposal['content'].encode()).hexdigest())
                    return proposal
        return None

    def complete_notice(self, notice_id, event_id):
        if not _uuid(event_id):raise WorkflowError("Notice completion requires a confirmed event UUID.")
        with self._transaction() as d:
            notice=d['notices'][notice_id]
            if any(k!=notice_id and n.get('event_id')==event_id for k,n in d['notices'].items()):
                raise WorkflowError('One confirmed event cannot complete two different notice claims.')
            if notice['status']=='sent' and notice.get('event_id')==event_id:return
            if notice['status']!='claimed':raise WorkflowError("Unknown or terminal delivery cannot be automatically retried or relabeled.")
            notice.update(status='sent',event_id=event_id,sent_at=self._now())
            d['incidents'][notice['incident_id']]['next_at']=self._now()+self.scope['ack_timeout_seconds']
            # WS delivery can beat the POST response. Rebind an already observed
            # matching coordinator turn before it can open another notice budget.
            origin=notice['incident_id'];inc=d['incidents'][origin]
            for turn_id,turn in d['turns'].items():
                if turn.get('trigger_event_id')!=event_id:continue
                own='turn:'+turn_id
                if (turn['agent_id']!=self.scope['pm_id']
                        or any(key!=origin for key in turn['incident_ids'])
                        or (own in d['incidents'] and own!=origin)):
                    inc['blocked']='notice_trigger_binding_conflict'
                    if own in d['incidents']:d['incidents'][own]['blocked']='notice_trigger_binding_conflict'
                    continue
                turn['incident_ids']=[origin]
                if turn['status'] in ('failed','interrupted','unknown'):
                    inc.update(failed=True,closed=False,next_at=self._now())
                elif turn['status']=='completed':
                    notice.setdefault('handled_at',self._now())
                    if not inc['deliveries']:inc.update(closed=True,failed=False)


    def unknown_notice(self, notice_id):
        with self._transaction() as d:
            notice=d['notices'][notice_id]
            if notice['status']=='unknown':return
            if notice['status']!='claimed':raise WorkflowError("Only an in-flight notice can become unknown.")
            notice['status']='unknown'
            d['incidents'][notice['incident_id']]['blocked']='notice_delivery_unknown'

    def observe_notice_handled(self, event_id, agent_id):
        """Record a successful coordinator callback, never task acceptance."""
        if not _uuid(event_id):
            raise WorkflowError('Only the exact coordinator notice callback can be handled.')
        with self._transaction() as d:
            matches=[n for n in d['notices'].values() if n.get('event_id')==event_id and n['status']=='sent']
            if not matches:
                return False
            if len(matches)!=1 or agent_id != self.scope['pm_id']:
                raise WorkflowError('Ambiguous notice delivery or incorrect coordinator identity.')
            notice=matches[0]
            notice.setdefault('handled_at',self._now())
            incident=d['incidents'][notice['incident_id']]
            if not incident['deliveries']:
                incident.update(closed=True,failed=False)
            return True

    def block_turn_delivery(self, turn_id, reason_code='outbound_delivery_unknown'):
        """An unconfirmed protocol send is not a retryable failure or receipt."""
        if reason_code!='outbound_delivery_unknown':
            raise WorkflowError('Use the fixed outbound delivery uncertainty code.')
        with self._transaction() as d:
            turn=d['turns'].get(turn_id)
            if not turn:
                raise WorkflowError('Cannot bind uncertainty to an unobserved turn.')
            for key in turn['incident_ids'] or ['turn:'+turn_id]:
                incident=d['incidents'].get(key) or self._incident(d,key,turn['agent_id'],self._now())
                incident['blocked']=reason_code

    def health(self):
        with self._transaction() as d:
            now=self._now();self._refresh(d,now)
            unresolved=[(key,i) for key,i in d['incidents'].items() if i['blocked'] or not self._resolved(d,i)]
            running=[key for key,t in d['turns'].items() if t['status']=='running']
            # Receipt wait expiry cannot shorten an admitted turn's deadline.
            # Conflicts/unknown delivery still block immediately; exhausted
            # recovery is assessed after serialized active work has settled.
            blocked=any(i['blocked'] or (not running and i['attempts']>=self.scope['max_notices'] and now>=i['next_at']) for _,i in unresolved)
            stalled=any(self._proposal(d,key,i,now) for key,i in unresolved)
            state='blocked' if blocked else 'busy' if running else 'stalled' if stalled else 'waiting' if unresolved else 'idle'
            return dict(state=state,active_turn_ids=running,unresolved_incident_ids=[k for k,_ in unresolved],
                seconds_to_next_deadline=min((d['turns'][k]['deadline_at']-now for k in running),default=None),
                notice_attempts=sum(i['attempts'] for i in d['incidents'].values()),
                unknown_notices=[k for k,n in d['notices'].items() if n['status']=='unknown'])
