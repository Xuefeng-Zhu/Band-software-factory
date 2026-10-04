"""Supported SDK seams for workflow deadlines, receipts and bounded notifications.

Imports are inert. Model turns and room writes remain owned by the guarded runner;
this module never starts agents, creates identities or changes task requirements.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import re
import time
from uuid import UUID

from .runtime import AuditedTools, GateError


CLOCK_TOOL = {
    "type": "function",
    "function": {
        "name": "factory_turn_budget",
        "description": "Read this admitted turn's remaining time and handoff deadline. This does not renew a lease or extend any approved limit. Call before work and before expensive checks; reserve time for the full handoff.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


def protocol_header(content):
    first = content.splitlines()[0] if isinstance(content, str) and content.splitlines() else ""
    return first.startswith("HANDOFF-ACK") or bool(re.search(r"\bdelivery\s+\S+\s+part\b", first, re.I))


def normalize_header(content, roster):
    """Resolve only exact frozen handles on the protocol line; never alter payload."""
    lines = content.split("\n", 1)
    for seat in sorted(roster, key=lambda item: len(item.get("handle", "")), reverse=True):
        handle = "@" + seat.get("handle", "").lstrip("@")
        if handle != "@":
            lines[0] = re.sub(r"(?<![\w/])" + re.escape(handle) + r"(?![\w/-])",
                             "@[[" + seat["agent_id"] + "]]", lines[0])
    return "\n".join(lines)


def confirmed_message(response):
    """Use the maintained SDK's success/event/recipient schema, never text guesses."""
    data = response if isinstance(response, dict) else response.model_dump() if hasattr(response, "model_dump") else {}
    event_id = data.get("id")
    try:
        valid_id = isinstance(event_id, str) and str(UUID(event_id)) == event_id
    except ValueError:
        valid_id = False
    recipients = data.get("recipients")
    if data.get("success") is not True or not valid_id or not isinstance(recipients, list):
        raise GateError("Room message has no confirmed delivery identity; automatic retry is blocked.")
    ids = [recipient.get("id") for recipient in recipients if isinstance(recipient, dict)]
    if len(ids) != len(recipients) or not ids or len(set(ids)) != len(ids):
        raise GateError("Room message has no unambiguous confirmed recipients.")
    return event_id, ids


def canonical_mentions(mentions, roster):
    result = []
    for mention in mentions or []:
        identifier = mention.get("id") if isinstance(mention, dict) else mention
        seat = next((s for s in roster if identifier in {
            s["agent_id"], s["handle"], "@" + s["handle"].lstrip("@"), "@[[" + s["agent_id"] + "]]"}), None)
        if not seat or any(m["id"] == seat["agent_id"] for m in result):
            raise GateError("Tracked handoffs require distinct exact frozen roster recipients.")
        result.append({"id": seat["agent_id"], "handle": seat["handle"].lstrip("@")})
    if not result:
        raise GateError("Tracked handoffs require a frozen roster recipient.")
    return result


def send_window(ledger, deadline_at=None):
    """Remaining wall-time for a request; never adds time to approved limits."""
    now = time.time()
    deadlines = [] if deadline_at is None else [deadline_at]
    started = ledger.data.get("started_epoch")
    if started is not None:
        deadlines.append(started + ledger.limits["overall_timeout_seconds"])
    room_started = ledger.data.get("room_started_epochs", {}).get(ledger.room) if ledger.allowed_rooms else started
    if room_started is not None:
        deadlines.append(room_started + ledger.limits["stage_timeout_seconds"])
    return min([10.0, *(deadline - now for deadline in deadlines)])


def sdk_execution_activity(agents, room_id, participant_ids):
    """Read BAND 4.0's public local ingress before adapter callbacks start.

    Agent.runtime -> PlatformRuntime.runtime -> AgentRuntime.active_sessions
    exposes the default ExecutionContext's public queue/state properties. This
    covers queued WS callbacks and processing through durable mark_processed;
    it does not assert that a remote /next backlog is empty during an idle poll.
    Missing/custom/dead contexts fail closed rather than guessing an empty queue.
    No queue item is removed and no receipt or deadline is changed.
    """
    from band.runtime.execution import ExecutionContext, ExecutionState
    expected=list(participant_ids)
    if len(set(expected))!=len(expected):
        raise GateError("SDK execution roster contains duplicate identities.")
    contexts=[];seen=set()
    try:
        for agent in agents:
            platform=agent.runtime
            identity=platform.agent_id
            ctx=platform.runtime.active_sessions.get(room_id)
            if (identity not in expected or identity in seen or not isinstance(ctx,ExecutionContext)
                    or ctx.room_id!=room_id or ctx.agent_id!=identity
                    or not isinstance(ctx.queue,asyncio.Queue) or not ctx.is_running
                    or ctx.state not in (ExecutionState.STARTING,ExecutionState.IDLE,ExecutionState.PROCESSING)):
                raise GateError("Supported current-room SDK execution state is unavailable.")
            seen.add(identity)
            contexts.append(dict(agent_id=identity,room_id=room_id,queued_events=ctx.queue.qsize(),
                processing=ctx.is_processing,state=str(ctx.state),running=ctx.is_running))
    except (AttributeError,RuntimeError,TypeError):
        raise GateError("Supported current-room SDK execution state is unavailable.") from None
    if seen!=set(expected):
        raise GateError("Current-room SDK execution roster is incomplete.")
    return dict(busy=any(row['queued_events'] or row['processing'] or row['state']=='starting' for row in contexts),
                contexts=contexts)


def _execution_busy(snapshot):
    if snapshot is None:
        return False
    value=snapshot()
    if not isinstance(value,dict) or type(value.get('busy')) is not bool:
        raise GateError("SDK execution activity is unknown.")
    return value['busy']


async def post_once(tools, room_id, content, mentions, ledger, *, deadline_at=None, attachment_ids=None, budget_seat=None, budget_seats=()):
    """Use the maintained SDK's generated endpoint with retries explicitly off."""
    from band.client.rest import ChatMessageRequest, ChatMessageRequestMentionsItem
    kwargs = {"content": content, "mentions": [ChatMessageRequestMentionsItem(**m) for m in mentions]}
    if attachment_ids is not None:
        kwargs["attachment_ids"] = attachment_ids
    request = ChatMessageRequest(**kwargs)
    window = send_window(ledger, deadline_at)
    if tools.room_id != room_id or ledger.stop.is_set() or ledger.reason(budget_seat) or any(ledger.reason(seat) for seat in budget_seats) or window <= 0:
        raise GateError("Room binding or remaining budget prevents this send.")
    async with asyncio.timeout(window):
        response = await tools.rest.agent_api_messages.create_agent_chat_message(
            chat_id=room_id, message=request,
            request_options={"max_retries": 0, "timeout_in_seconds": window})
    if not response.data:
        raise GateError("Room message has no confirmed response; automatic retry is blocked.")
    return response.data


class WorkflowTools(AuditedTools):
    def __init__(self, *args, watchdog, actor_id, turn_id, deadline_at, clock=time.time, **kwargs):
        super().__init__(*args, **kwargs)
        self.watchdog, self.actor_id, self.turn_id = watchdog, actor_id, turn_id
        self.deadline_at, self.clock = deadline_at, clock
        self.terminal_status = None
        self.delivery_blocked = False
        self.handoff_reserve = min(60, self.ledger.limits["turn_timeout_seconds"] / 4)

    def get_openai_tool_schemas(self, **kwargs):
        from copy import deepcopy
        return [*self.tools.get_openai_tool_schemas(**kwargs), deepcopy(CLOCK_TOOL)]

    async def execute_tool_call_structured(self, tool_name, arguments):
        from band.runtime.tools.schema import ToolCallOutcome
        if tool_name == "factory_turn_budget":
            if arguments != {}:
                return ToolCallOutcome(value="This read-only clock takes no arguments.", ok=False,
                                       error_message="invalid_clock_arguments")
            now = self.clock()
            return ToolCallOutcome(value={
                "turn_id": self.turn_id,
                "remaining_seconds": max(0, self.deadline_at - now),
                "deadline_utc": datetime.fromtimestamp(self.deadline_at, timezone.utc).isoformat(),
                "finish_work_by_utc": datetime.fromtimestamp(self.deadline_at - self.handoff_reserve, timezone.utc).isoformat(),
                "handoff_reserve_seconds": self.handoff_reserve,
                "extends_limits": False,
            }, ok=True)
        return await super().execute_tool_call_structured(tool_name, arguments)

    async def send_message(self, content, mentions=None, *, attachment_ids=None):
        if self.delivery_blocked or self.ledger.stop.is_set():
            raise GateError("An uncertain delivery or stopped run blocks further sends.")
        tracked = protocol_header(content)
        canonical = canonical_mentions(mentions, self.roster) if tracked else None
        try:
            response = (await post_once(self.tools, self.watchdog.scope["room_id"], content, canonical,
                self.ledger, deadline_at=self.deadline_at, attachment_ids=attachment_ids)) if tracked else (
                await self.tools.send_message(content, mentions, attachment_ids=attachment_ids))
            if tracked:
                event_id, recipients = confirmed_message(response)
                observed = self.watchdog.observe_outbound(event_id, self.actor_id, recipients,
                                               normalize_header(content, self.roster), self.turn_id)
                if observed.get("blocked"):
                    self.delivery_blocked = True
                    self.ledger.stop.set()
            return response
        except BaseException:
            if tracked:
                # The request may already have reached BAND. Retain the uncertainty
                # even when the SDK converts a tool exception into a failed outcome.
                self.delivery_blocked = True
                self.watchdog.block_turn_delivery(self.turn_id)
                self.ledger.stop.set()
            raise

    async def send_event(self, content, message_type, metadata=None):
        metadata = metadata or {}
        if metadata.get("codex_event_type") == "turn_lifecycle":
            status = metadata.get("codex_turn_status")
            if status in {"completed", "failed", "interrupted"}:
                self.terminal_status = status
        return await super().send_event(content, message_type, metadata)


async def observed_turn(callback, inp, wrapped, watchdog, *, actor_id, turn_id, deadline_at):
    """Persist local completion even when SDK best-effort lifecycle delivery fails."""
    from dataclasses import replace
    from band.core.protocols import TurnResultAlreadyReported
    watchdog.begin_turn(actor_id, turn_id, deadline_at, trigger_event_id=inp.msg.id)
    status, reason = "unknown", "unknown"
    try:
        result = await callback(replace(inp, tools=wrapped))
        status = wrapped.terminal_status or "completed"
        reason = "provider_failure" if status == "failed" else "interrupted" if status == "interrupted" else ""
        return result
    except TurnResultAlreadyReported:
        status, reason = "failed", "provider_failure"
        raise
    except asyncio.CancelledError:
        status, reason = "interrupted", "interrupted"
        raise
    except TimeoutError:
        status, reason = "failed", "timeout"
        raise
    except Exception:
        status, reason = "failed", "provider_failure"
        raise
    finally:
        watchdog.end_turn(turn_id, status, reason)
        if status == "completed":
            watchdog.observe_notice_handled(inp.msg.id, actor_id)


async def send_due_notice(watchdog, ledger, available_tools, roster, *, execution_activity=None):
    """Bounded original-sender notice after local SDK ingress and writer gates.

    PM-owned delivery incidents go to the original unacknowledged recipients for
    receipt/reassembly only. A recipient's real response can wake PM naturally;
    no self-message bypass, identity substitution or new inference loop is used.
    """
    if ledger.stop.is_set() or ledger.reason() or ledger.semaphore.locked():
        return "deferred"
    async with ledger.semaphore:
        if ledger.stop.is_set() or ledger.reason() or _execution_busy(execution_activity):
            return "deferred"
        notice = watchdog.due_notice(can_notify=True)
        if not notice:
            return "none"
        if notice["sender_id"] in notice["recipient_ids"]:
            # A failed PM without any original delivery recipient is still
            # unrouteable. Never post an ineffective self-notice or impersonate.
            return "blocked_coordinator_self_notice"
        original_tools = available_tools.get(notice["sender_id"])
        if original_tools is None:
            return "blocked_missing_sender_context"
        seats={seat['agent_id']:seat for seat in roster}
        required={notice['sender_id'],*notice['recipient_ids']}
        if not required<=seats.keys() or not notice['recipient_ids']:
            raise GateError("Workflow notice identities are outside the frozen roster.")
        budget_seats=sorted(seats[identity]['id'] for identity in required)
        if any(ledger.reason(seat) for seat in budget_seats):
            return "deferred"
        claim = watchdog.claim_notice(notice["notice_id"], can_notify=not ledger.stop.is_set()
            and not any(ledger.reason(seat) for seat in budget_seats))
        if not claim:
            return "deferred"
        try:
            if claim['sender_id']!=notice['sender_id'] or claim['recipient_ids']!=notice['recipient_ids']:
                raise GateError("Workflow notice recipient binding changed during its claim.")
            # Recheck every required seat after durable claim. No await occurs
            # between this check and post_once's final global/time/budget check.
            response = await post_once(original_tools, watchdog.scope["room_id"], claim["content"],
                [{'id':identity,'handle':seats[identity]['handle'].lstrip('@')} for identity in claim['recipient_ids']],
                ledger, budget_seats=budget_seats)
            event_id, recipients = confirmed_message(response)
            if sorted(recipients) != claim["recipient_ids"]:
                raise GateError("Workflow notice confirmation has unexpected recipients.")
            watchdog.complete_notice(claim["notice_id"], event_id)
        except BaseException:
            watchdog.unknown_notice(claim["notice_id"])
            raise
        return "sent"
