"""Offline API-size and exact historical task-projection regressions."""
import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
from band_rest import AsyncRestClient
from band_rest.core.api_error import ApiError
from band_rest.core.parse_error import ParsingError

from factorykit.common import FactoryError, canonical, write_json
from factorykit.task_board import TaskBoard
from tests import test_task_board as fixtures


class TaskBoardProjectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.f = fixtures.TaskBoardTests(methodName="runTest")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    async def test_short_projection_remains_exact_and_is_stored(self):
        item = self.f.item()
        record = await self.f.publish(item)
        expected = dict(zip(("subject", "detail"), self.f.board._payload(item, record["projection_id"])))
        self.assertEqual(record["band_payload"], expected)
        self.assertEqual(record["item"], item)
        self.assertEqual(self.f.remote[record["task_id"]]["detail"], expected["detail"])

    async def test_compact_full_item_fits_without_losing_any_field(self):
        item = self.f.item()
        item["requirements"] = ["abc"] * 1000
        self.assertGreater(len(self.f.board._payload(item, fixtures.uid(200))[1]), 10000)
        record = await self.f.publish(item)
        detail = record["band_payload"]["detail"]
        self.assertLessEqual(len(detail), 10000)
        self.assertEqual(json.loads(detail.split("```json\n", 1)[1].rsplit("\n```", 1)[0]), item)
        self.assertEqual(record["item"], item)

    async def test_long_item_pointer_fits_actual_sdk_request_and_keeps_complete_record(self):
        item = self.f.item()
        item["requirements"] = ["é" * 11000]
        requests = []

        def handle(request):
            self.assertEqual(request.method, "POST")
            payload = json.loads(request.content)
            requests.append(payload)
            self.assertTrue(1 <= len(payload["subject"]) <= 500)
            self.assertLessEqual(len(payload["detail"]), 10000)
            pending = json.loads(self.f.path.read_text())["items"][item["id"]]["pending"]
            self.assertEqual(pending["item"], item)
            self.assertEqual(pending["band_payload"], payload)
            return httpx.Response(201, json={"data": dict(id=fixtures.uid(100), chat_room_id=fixtures.ROOM,
                number=1, **payload, state="active", created_by=self.f.actor(fixtures.PM), assignments=[],
                overall_status="pending", inserted_at=fixtures.DATE, updated_at=fixtures.DATE)})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            tools = SimpleNamespace(agent_id=fixtures.PM, room_id=fixtures.ROOM,
                                    rest=AsyncRestClient(api_key="offline-placeholder", httpx_client=http))
            record = await self.f.board.publish(tools, fixtures.PM, item, 0, self.f.window)
        self.assertEqual(len(requests), 1)
        self.assertIn(hashlib.sha256(canonical(item)).hexdigest(), record["band_payload"]["detail"])
        self.assertIn("factory_task_board", record["band_payload"]["detail"])
        self.assertEqual(self.f.board.snapshot()["items"][item["id"]]["item"], item)

    async def test_legacy_pending_uses_exact_old_pretty_json_and_never_retries(self):
        item = self.f.item()
        item["requirements"] = ["legacy payload " * 900]
        projection, operation, task_id = (fixtures.uid(i) for i in (200, 201, 100))
        subject, detail = self.f.board._payload(item, projection)
        self.assertGreater(len(detail), 10000)
        pending = dict(operation="create", item=deepcopy(item), actor_id=fixtures.PM, owner_status=None,
                       version=1, projection_id=projection, operation_id=operation)
        record = dict(version=0, task_id=None, projection_id=projection, pending=pending)
        write_json(self.f.path, dict(scope=self.f.board.scope, items={item["id"]: record}, messages={}))
        before = self.f.path.read_bytes()
        self.f.remote[task_id] = dict(id=task_id, chat_room_id=fixtures.ROOM, number=1, subject=subject,
            detail=self.f.board._new_payload(item, projection)["detail"], state="active",
            created_by=self.f.actor(fixtures.PM), assignments=[], overall_status="pending",
            inserted_at=fixtures.DATE, updated_at=fixtures.DATE)
        restarted = TaskBoard(self.f.path, fixtures.ROOM, fixtures.ROSTER)
        with self.assertRaises(FactoryError):
            await restarted.reconcile(self.f.tools(fixtures.PM), item["id"], task_id, self.f.window)
        self.assertEqual(self.f.path.read_bytes(), before)
        self.f.remote[task_id]["detail"] = detail
        confirmed = await restarted.reconcile(self.f.tools(fixtures.PM), item["id"], task_id, self.f.window)
        self.assertNotIn("band_payload", confirmed)
        self.assertEqual(confirmed["item"], item)
        self.assertEqual(self.f.mutations(), 0)
        # A status-only update of a successful legacy task keeps its exact text.
        await restarted.sync_owner(self.f.tools(fixtures.OWNER), fixtures.OWNER, self.f.window)
        kwargs = self.f.tools(fixtures.OWNER).rest.agent_api_chat_tasks.update_chat_task.await_args.kwargs
        self.assertEqual((kwargs["subject"], kwargs["detail"]), (subject, detail))

    async def test_new_pending_reconciles_stored_bytes_even_if_projection_policy_changes(self):
        item = self.f.item()
        item["requirements"] = ["long requirement " * 900]
        endpoint = self.f.tools(fixtures.PM).rest.agent_api_chat_tasks
        create = endpoint.create_chat_task.side_effect

        async def lost(**kwargs):
            await create(**kwargs)
            raise RuntimeError("sensitive raw response must not be retained")

        endpoint.create_chat_task.side_effect = lost
        with self.assertRaises(FactoryError):
            await self.f.publish(item)
        pending = self.f.board.snapshot()["items"][item["id"]]["pending"]
        restarted = TaskBoard(self.f.path, fixtures.ROOM, fixtures.ROSTER)
        with patch.object(restarted, "_new_payload", side_effect=AssertionError("must use stored bytes")):
            confirmed = await restarted.reconcile(self.f.tools(fixtures.PM), item["id"], next(iter(self.f.remote)), self.f.window)
        self.assertEqual(confirmed["band_payload"], pending["band_payload"])
        self.assertEqual(confirmed["item"], item)
        self.assertEqual(self.f.mutations(), 1)

    async def test_sdk_rejection_records_safe_class_status_and_keeps_claim_without_retry(self):
        requests = []

        def reject(request):
            requests.append(request)
            return httpx.Response(422, json={"error": "PRIVATE_SERVER_BODY"}, headers={"x-private": "PRIVATE_HEADER"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(reject)) as http:
            tools = SimpleNamespace(agent_id=fixtures.PM, room_id=fixtures.ROOM,
                                    rest=AsyncRestClient(api_key="offline-placeholder", httpx_client=http))
            with self.assertRaisesRegex(FactoryError, "BAND rejected.*UnprocessableEntityError.*HTTP 422") as caught:
                await self.f.board.publish(tools, fixtures.PM, self.f.item(), 0, self.f.window)
            before = self.f.path.read_bytes()
            with self.assertRaisesRegex(FactoryError, "unconfirmed"):
                await self.f.board.publish(tools, fixtures.PM, self.f.item(), 0, self.f.window)
            self.assertEqual(self.f.path.read_bytes(), before)
        self.assertEqual(len(requests), 1)
        diagnostic = self.f.board.snapshot()["items"]["WORK-1"]["pending"]["write_error"]
        self.assertEqual(diagnostic, dict(outcome="rejected", error_class="UnprocessableEntityError", http_status=422))
        self.assertNotIn("PRIVATE_", before.decode() + str(caught.exception))

    async def test_transport_and_response_parse_failures_remain_unknown_with_safe_metadata(self):
        errors = [RuntimeError("PRIVATE_TRANSPORT"), ApiError(status_code=503, body="PRIVATE_BODY"),
                  ParsingError(status_code=200, body="PRIVATE_PARSE"), ApiError(status_code=408, body="PRIVATE_TIMEOUT")]
        for index, error in enumerate(errors):
            with self.subTest(error=type(error).__name__, status=getattr(error, "status_code", None)):
                self.f.tools(fixtures.PM).rest.agent_api_chat_tasks.create_chat_task.side_effect = error
                with self.assertRaisesRegex(FactoryError, "outcome is unknown") as caught:
                    await self.f.publish(self.f.item(f"WORK-{index}"))
                record = self.f.board.snapshot()["items"][f"WORK-{index}"]
                self.assertEqual(record["pending"]["write_error"], dict(outcome="unknown",
                    error_class=type(error).__name__, http_status=getattr(error, "status_code", None)))
                self.assertNotIn("PRIVATE_", self.f.path.read_text() + str(caught.exception))

    async def test_changed_item_update_reads_saved_projection_and_keeps_full_new_item(self):
        item = self.f.item()
        item["requirements"] = ["requirement " * 1000]
        record = await self.f.publish(item)
        updated = dict(item, state="IN_PROGRESS")
        result = await self.f.publish(updated, record["version"], fixtures.OWNER)
        self.assertEqual(result["item"], updated)
        self.assertLessEqual(len(result["band_payload"]["detail"]), 10000)
        self.assertIn(hashlib.sha256(canonical(updated)).hexdigest(), result["band_payload"]["detail"])


if __name__ == "__main__":
    unittest.main()
