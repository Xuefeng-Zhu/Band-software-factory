import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch

from band.client.streaming import MessageCreatedPayload, MessageMetadata
from band.platform.event import MessageEvent, RoomAddedEvent
from band.platform.link import BandLink
from band.runtime.execution import ExecutionContext
from band.runtime.platform_runtime import PlatformRuntime
from band.runtime.types import PlatformMessage, SessionConfig
from band_rest.types import ChatMessage

from factorykit.common import FactoryError
from factorykit.continuation_platform import ReceiptPreservingBandLink, ReceiptPreservingPlatformRuntime

ROOM='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
OTHER_ROOM='aaaaaaaa-aaaa-4aaa-8aaa-bbbbbbbbbbbb'
AGENT='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
SENDER='cccccccc-cccc-4ccc-8ccc-cccccccccccc'
OLD='11111111-1111-4111-8111-111111111111'
NEW='22222222-2222-4222-8222-222222222222'
NOW=datetime(2026,10,5,3,tzinfo=timezone.utc)

def message(identifier, room=ROOM):
    return PlatformMessage(id=identifier,room_id=room,content='test',sender_id=SENDER,
        sender_type='Agent',sender_name='sender',message_type='text',metadata={},created_at=NOW)

def row(identifier, room=ROOM):
    return ChatMessage(id=identifier,chat_room_id=room,content='test',sender_id=SENDER,
        sender_type='Agent',message_type='text',inserted_at=NOW)

def page(rows, more=False, cursor=None):
    return NS(data=rows,metadata=NS(has_more=more,next_cursor=cursor))

def event(identifier,room=ROOM):
    return MessageEvent(room_id=room,payload=MessageCreatedPayload(id=identifier,
        content='test',sender_id=SENDER,sender_type='Agent',message_type='text',
        metadata=MessageMetadata(),chat_room_id=room,
        inserted_at=NOW.isoformat(),updated_at=NOW.isoformat()))

class IngressTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # No HTTP clients or live transports: exercise real link/filter methods
        # with a fake transport beneath the SDK boundary.
        self.link=object.__new__(ReceiptPreservingBandLink)
        self.link.continuation_room_id=ROOM
        self.link.excluded_event_ids=frozenset([OLD])
        self.link.on_filter_failure=Mock()
        self.link.agent_id=AGENT
        self.link._event_queue=asyncio.Queue()
        self.api=NS(list_agent_messages=AsyncMock())
        self.link.rest=NS(agent_api_messages=self.api)

    async def test_blocked_head_scans_read_only_to_next_page(self):
        self.api.list_agent_messages.side_effect=[page([row(OLD)],True,'p2'),page([row(NEW)])]
        with patch.object(BandLink,'get_next_message',AsyncMock(return_value=message(OLD))):
            found=await self.link.get_next_message(ROOM)
        self.assertEqual(found.id,NEW)
        calls=self.api.list_agent_messages.call_args_list
        self.assertNotIn('status',calls[0].kwargs)
        self.assertEqual(calls[1].kwargs['cursor'],'p2')
        self.assertEqual(calls[1].kwargs['sort_order'],'asc')
        self.link.on_filter_failure.assert_not_called()

    async def test_only_excluded_history_returns_empty_without_marking(self):
        self.api.list_agent_messages.return_value=page([row(OLD)])
        with patch.object(BandLink,'get_next_message',AsyncMock(return_value=message(OLD))):
            self.assertIsNone(await self.link.get_next_message(ROOM))

    async def test_regular_next_and_other_room_are_unchanged(self):
        for room,identifier in [(ROOM,NEW),(OTHER_ROOM,OLD)]:
            original=message(identifier,room)
            with patch.object(BandLink,'get_next_message',AsyncMock(return_value=original)):
                self.assertIs(await self.link.get_next_message(room),original)
        self.api.list_agent_messages.assert_not_called()

    async def test_incomplete_pagination_fails_closed(self):
        for response in [page([row(OLD)],True,None),page([row(OLD)],True,'repeat')]:
            self.api.list_agent_messages.return_value=response
            with patch.object(BandLink,'get_next_message',AsyncMock(return_value=message(OLD))):
                with self.assertRaises(FactoryError):await self.link.get_next_message(ROOM)
        self.assertEqual(self.link.on_filter_failure.call_count,2)

    async def test_pagination_limit_is_bounded(self):
        self.api.list_agent_messages.side_effect=[page([row(OLD)],True,str(i)) for i in range(10)]
        with patch.object(BandLink,'get_next_message',AsyncMock(return_value=message(OLD))):
            with self.assertRaises(FactoryError):await self.link.get_next_message(ROOM)
        self.assertEqual(self.api.list_agent_messages.await_count,10)

    async def test_wrong_room_and_missing_timestamp_fail_closed(self):
        missing=row(NEW).model_copy(update={'inserted_at':None})
        for bad in [row(NEW,OTHER_ROOM),missing]:
            self.api.list_agent_messages.return_value=page([bad])
            with patch.object(BandLink,'get_next_message',AsyncMock(return_value=message(OLD))):
                with self.assertRaises(FactoryError):await self.link.get_next_message(ROOM)

    async def test_get_failure_is_not_reported_as_empty(self):
        self.api.list_agent_messages.side_effect=RuntimeError('offline fixture')
        with patch.object(BandLink,'get_next_message',AsyncMock(return_value=message(OLD))):
            with self.assertRaises(FactoryError):await self.link.get_next_message(ROOM)
        self.link.on_filter_failure.assert_called_once()

    async def test_ws_filter_runs_before_default_execution_receipts(self):
        self.link._event_queue.put_nowait(event(OLD))
        self.link._event_queue.put_nowait(event(NEW))
        received=await self.link.__anext__()
        calls=[]
        ctx=self.context(calls)
        with patch.object(BandLink,'mark_processing',AsyncMock(return_value=True)) as processing, \
             patch.object(BandLink,'mark_processed',AsyncMock(return_value=True)) as processed, \
             patch.object(BandLink,'mark_failed',AsyncMock(return_value=True)) as failed:
            self.assertTrue(await ctx._process_event(received))
        self.assertEqual(calls,[NEW])
        processing.assert_awaited_once_with(ROOM,NEW)
        processed.assert_awaited_once_with(ROOM,NEW)
        failed.assert_not_awaited()

    async def test_stale_sweep_excludes_terminal_without_receipt_mutation(self):
        with patch.object(BandLink,'get_stale_processing_messages',AsyncMock(return_value=[message(OLD),message(NEW)])):
            self.assertEqual([m.id for m in await self.link.get_stale_processing_messages(ROOM)],[NEW])

    async def test_defensive_mark_guards_never_call_sdk_mutators(self):
        for name,args in [('mark_processing',()),('mark_processed',()),('mark_failed',('error',))]:
            with patch.object(BandLink,name,AsyncMock()) as method:
                with self.assertRaises(FactoryError):await getattr(self.link,name)(ROOM,OLD,*args)
                method.assert_not_awaited()

    async def test_real_sdk_startup_and_idle_resync_advance_past_failed_head(self):
        done=set(); calls=[]
        self.api.list_agent_messages.side_effect=lambda **kw:page([row(OLD)]+([] if NEW in done else [row(NEW)]))
        async def ack(room,identifier):done.add(identifier);return True
        ctx=self.context(calls)
        with patch.object(BandLink,'get_next_message',AsyncMock(return_value=message(OLD))), \
             patch.object(BandLink,'get_stale_processing_messages',AsyncMock(return_value=[])), \
             patch.object(BandLink,'mark_processing',AsyncMock(return_value=True)) as processing, \
             patch.object(BandLink,'mark_processed',AsyncMock(side_effect=ack)) as processed, \
             patch.object(BandLink,'mark_failed',AsyncMock(return_value=True)) as failed:
            self.assertTrue(await ctx._synchronize_with_next())
            self.assertTrue(await ctx._resync_pending_messages())
        self.assertEqual(calls,[NEW]);self.assertEqual(done,{NEW})
        processing.assert_awaited_once_with(ROOM,NEW)
        processed.assert_awaited_once_with(ROOM,NEW)
        failed.assert_not_awaited()

    async def test_ws_controls_and_other_room_unchanged(self):
        for item in [RoomAddedEvent(room_id=ROOM),event(OLD,OTHER_ROOM)]:
            self.link._event_queue.put_nowait(item)
            self.assertIs(await self.link.__anext__(),item)

    def context(self,calls):
        async def execute(ctx,event):calls.append(event.payload.id)
        ctx=ExecutionContext(ROOM,self.link,execute,agent_id=AGENT,
            config=SessionConfig(enable_working_state=False,enable_context_hydration=False,max_message_retries=1))
        ctx._ensure_fresh_context=AsyncMock()
        ctx._sync_complete=True
        return ctx

class RuntimeConstructionTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_initialization_is_overridden_and_precedes_processing(self):
        runtime=ReceiptPreservingPlatformRuntime(agent_id=AGENT,api_key='offline-placeholder',
            continuation_room_id=ROOM,excluded_event_ids=[OLD],on_filter_failure=Mock())
        fake=NS()
        with patch('factorykit.continuation_platform.ReceiptPreservingBandLink',return_value=fake) as build, \
             patch.object(runtime,'_fetch_agent_metadata',AsyncMock()) as metadata:
            await runtime.initialize();await runtime.initialize()
        build.assert_called_once();metadata.assert_awaited_once()
        self.assertIs(runtime.link,fake)
        self.assertIs(ReceiptPreservingPlatformRuntime.start,PlatformRuntime.start)
        self.assertIs(ReceiptPreservingPlatformRuntime.stop,PlatformRuntime.stop)
        self.assertEqual(build.call_args.kwargs['excluded_event_ids'],(OLD,))

    async def test_unreviewed_sdk_refused_before_link_or_transport(self):
        with patch('factorykit.continuation_platform.version',return_value='future'):
            with self.assertRaises(FactoryError):
                ReceiptPreservingPlatformRuntime(agent_id=AGENT,api_key='offline-placeholder',
                    continuation_room_id=ROOM,excluded_event_ids=[OLD],on_filter_failure=Mock())

if __name__=='__main__':unittest.main()
