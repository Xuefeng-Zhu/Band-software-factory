"""Pinned SDK object tests; no agent starts, sockets or remote calls."""
import asyncio
import unittest
from unittest.mock import patch

from band import Agent
from band.client.streaming.client import WebSocketClient
from band.core import SimpleAdapter
from band.platform.link import BandLink
from band.runtime.platform_runtime import PlatformRuntime
from band.runtime.runtime import AgentRuntime
from band_sdk_core import AgentTopicKind
from phoenix_channels_python_client.client import PHXChannelsClient
from phoenix_channels_python_client.client_types import ClientState
from phoenix_channels_python_client.topic_subscription import TopicSubscription
from websockets import ClientConnection
from websockets.client import ClientProtocol
from websockets.protocol import State
from websockets.uri import parse_uri

from factorykit.membership_liveness import require_live_agents
from factorykit.runtime import GateError


class SilentAdapter(SimpleAdapter[list]):
    async def on_message(self, *args, **kwargs):
        raise AssertionError('No execution allowed in liveness tests')


class MembershipLivenessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tasks = []
        self.ids = [f'00000000-0000-4000-8000-{index:012d}' for index in range(1, 8)]
        self.agents = [self.make_agent(identity) for identity in self.ids]

    def task(self):
        async def wait():
            await asyncio.Future()
        task = asyncio.create_task(wait())
        self.tasks.append(task)
        return task

    def make_agent(self, identity):
        # Build the maintained concrete objects, setting transport lifecycle
        # state locally instead of calling Agent.start or opening any socket.
        platform = PlatformRuntime(identity, 'synthetic-test-key')
        link = BandLink(identity, 'synthetic-test-key')
        agent = Agent(platform, SilentAdapter())
        runtime = AgentRuntime(link, identity, agent._on_execute)
        platform._link, platform._runtime = link, runtime
        agent._started, link._is_connected = True, True
        runtime.presence._event_task = self.task()
        ws = WebSocketClient('ws://127.0.0.1/unused', 'synthetic-test-key', identity)
        client = PHXChannelsClient('ws://127.0.0.1/unused', 'synthetic-test-key')
        link._ws, ws.client = ws, client
        client._state, client._conn_generation = ClientState.CONNECTED, 1
        client._connected_event.set()
        client._supervisor_task, client._message_routing_task = self.task(), self.task()
        client.connection = ClientConnection(ClientProtocol(parse_uri('ws://127.0.0.1/unused'), state=State.OPEN))
        for topic in (AgentTopicKind.Control.topic(identity), AgentTopicKind.Rooms.topic(identity)):
            subscription = TopicSubscription(topic, self.noop, asyncio.Queue(), 'test-join', self.task(), conn_generation=1)
            subscription.current_join_ready.set_result(None)
            subscription.subscription_ready.set_result(None)
            client._topic_subscriptions[topic] = subscription
        return agent

    async def noop(self, *args):
        return None

    async def asyncTearDown(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        for agent in self.agents:
            # The REST wrappers allocate clients but the fixtures never use them.
            client = agent.runtime.link.rest._client_wrapper.httpx_client
            if hasattr(client, 'httpx_client'):
                client = client.httpx_client
            if hasattr(client, 'aclose'):
                await client.aclose()

    def test_live_default_sdk_objects_return_exact_mapping_without_room_context(self):
        self.assertEqual(require_live_agents(self.agents, self.ids), dict(zip(self.ids, self.agents)))
        self.assertTrue(all(not agent.runtime.runtime.active_sessions for agent in self.agents))

    def test_exact_seven_unique_canonical_identities_required(self):
        for agents, identities in ((self.agents[:-1], self.ids), (self.agents, self.ids[:-1]),
                                  (self.agents, [self.ids[0]] * 7), ([self.agents[0]] * 7, self.ids),
                                  (self.agents, ['invalid', *self.ids[1:]])):
            with self.subTest(identities=identities), self.assertRaises(GateError):
                require_live_agents(agents, identities)

    def test_disconnected_transport_cannot_hide_behind_started_and_connected_flags(self):
        agent = self.agents[0]
        self.assertTrue(agent.is_running and agent.runtime.link.is_connected)
        agent.runtime.link._ws.client.connection.protocol.state = State.CLOSED
        with self.assertRaises(GateError):
            require_live_agents(self.agents, self.ids)

    def test_lifecycle_identity_and_control_failures_fail_closed(self):
        agent = self.agents[0]
        platform, link = agent.runtime, agent.runtime.link
        runtime, ws = platform.runtime, link._ws
        client, presence = ws.client, runtime.presence
        room_subscription = client.get_current_subscriptions()[AgentTopicKind.Rooms.topic(self.ids[0])]
        mutations = [
            (agent, '_started', False), (platform, '_agent_id', self.ids[1]),
            (runtime, 'link', object()), (link, '_is_connected', False),
            (link, '_last_disconnect_reason', object()), (ws, 'agent_id', self.ids[1]),
            (ws, '_last_disconnect_reason', object()), (client, '_state', ClientState.RECONNECTING),
            (client, '_supervisor_task', None), (client, '_message_routing_task', None),
            (presence, '_event_task', None), (presence, 'on_room_joined', self.noop),
            (presence, 'on_room_left', self.noop), (room_subscription, 'conn_generation', 0),
            (room_subscription, 'process_topic_messages_task', None), (room_subscription, 'async_callback', None),
        ]
        for target, attribute, value in mutations:
            with self.subTest(attribute=attribute), patch.object(target, attribute, value), self.assertRaises(GateError):
                require_live_agents(self.agents, self.ids)

    async def test_failed_pending_cancelled_or_stale_join_is_not_live(self):
        client = self.agents[0].runtime.link._ws.client
        key = AgentTopicKind.Control.topic(self.ids[0])
        subscription = client.get_current_subscriptions()[key]
        for kind in ('pending', 'cancelled', 'failed'):
            future = asyncio.get_running_loop().create_future()
            if kind == 'cancelled':
                future.cancel()
            elif kind == 'failed':
                future.set_exception(RuntimeError('synthetic-secret-must-not-surface'))
            with self.subTest(kind=kind), patch.object(subscription, 'current_join_ready', future):
                with self.assertRaisesRegex(GateError, '^Supported live SDK membership control path is unavailable[.]$'):
                    require_live_agents(self.agents, self.ids)
        subscription.leave_requested.set()
        with self.assertRaises(GateError):
            require_live_agents(self.agents, self.ids)
        subscription.leave_requested.clear()
        client._topic_subscriptions.pop(key)
        with self.assertRaises(GateError):
            require_live_agents(self.agents, self.ids)

    async def test_cancelled_or_finished_presence_consumer_is_rejected(self):
        task = self.agents[0].runtime.runtime.presence._event_task
        task.cancel()
        with self.assertRaises(GateError):
            require_live_agents(self.agents, self.ids)
        await asyncio.gather(task, return_exceptions=True)
        with self.assertRaises(GateError):
            require_live_agents(self.agents, self.ids)

    def test_sdk_version_drift_is_rejected(self):
        with patch('factorykit.membership_liveness.version', return_value='4.0.1'), self.assertRaises(GateError):
            require_live_agents(self.agents, self.ids)


if __name__ == '__main__':
    unittest.main()
