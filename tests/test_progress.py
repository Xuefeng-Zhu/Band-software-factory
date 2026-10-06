"""Offline progress controls; real Git + commands, no model/provider execution."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from factorykit.common import FactoryError, run_command
from factorykit.progress import ProgressGuard, progress_policy


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.repo = self.root / "repo"; self.repo.mkdir()
        for args in (["init", "-q"], ["config", "user.email", "test@factory.invalid"], ["config", "user.name", "test"]):
            subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)
        (self.repo / "input").write_text("candidate")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "candidate"], cwd=self.repo, check=True)
        self.sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.repo, text=True).strip()
        self.now = 100.0
        self.policy = {"milestones": [{"id": "runnable", "max_turns": 2, "max_seconds": 60,
                     "command": [sys.executable, "-c", "from pathlib import Path; assert Path('input').read_text() == 'candidate'"],
                     "timeout_seconds": 5, "max_attempts": 2}]}
        self.path = self.root / "runtime/progress.json"
        self.guard = self.make()

    def make(self, **kwargs):
        return ProgressGuard(self.path, "room", self.repo, self.policy, clock=lambda:self.now, **kwargs)

    def verify(self):
        if json.loads(self.path.read_text())["started_at"] is None:
            self.guard.admit_turn("initial")
        return self.guard.verify_next(self.sha, remaining_seconds=20)

    def test_optional_policy_and_strict_validation(self):
        self.assertIsNone(progress_policy({}))
        for key, value in [("max_turns", True), ("max_seconds", 0), ("timeout_seconds", 61), ("max_attempts", 11), ("command", ["sh", "-c", "true"])]:
            policy = copy.deepcopy(self.policy); policy["milestones"][0][key] = value
            with self.assertRaises(FactoryError): progress_policy({"progress":policy})

    def test_turn_limit_last_turn_can_checkpoint_and_duplicates_do_not_count(self):
        self.assertTrue(self.guard.admit_turn("one")["admitted"])
        self.assertTrue(self.guard.admit_turn("one")["duplicate"])
        self.assertTrue(self.guard.admit_turn("two")["admitted"])
        self.assertEqual(self.guard.health()["reason"], "checkpoint_turns_exhausted")
        self.assertEqual(self.guard.health(execution_busy=True)["state"], "waiting")
        self.assertFalse(self.guard.admit_turn("three")["admitted"])
        self.assertEqual(self.verify()["outcome"], "passed")
        self.assertEqual(self.guard.health()["state"], "complete")

    def test_health_exposes_frozen_checkpoint_and_remaining_allowance(self):
        health = self.guard.health()
        self.assertEqual(health["next_checkpoint"], self.policy["milestones"][0])
        self.assertEqual((health["remaining_turns"], health["remaining_seconds"], health["remaining_attempts"]), (2, 60, 2))
        self.guard.admit_turn("one"); self.now += 12
        health = self.guard.health(execution_busy=True)
        self.assertEqual((health["remaining_turns"], health["remaining_seconds"], health["remaining_attempts"]), (1, 48, 2))
        self.verify()
        health = self.guard.health()
        self.assertIsNone(health["next_checkpoint"])
        self.assertIsNone(health["remaining_turns"])
        self.assertIsNone(health["remaining_seconds"])
        self.assertIsNone(health["remaining_attempts"])

    def test_elapsed_limit_survives_reconstruction(self):
        self.guard.admit_turn("initial")
        self.now += 60
        self.assertEqual(self.make().health()["reason"], "checkpoint_time_exhausted")
        with self.assertRaises(FactoryError): self.verify()

    def test_clock_regression_is_persisted_blocker(self):
        self.now -= 1
        self.assertEqual(self.guard.health()["reason"], "clock_regressed")
        self.now += 2
        self.assertEqual(self.make().health()["reason"], "clock_regressed")

    def test_failed_real_command_does_not_advance_and_attempts_are_bounded(self):
        self.policy["milestones"][0]["command"] = [sys.executable, "-c", "raise SystemExit(4)"]
        self.path.unlink(); self.guard = self.make()
        self.assertEqual(self.verify()["outcome"], "failed")
        self.assertEqual(self.verify()["progress"]["reason"], "checkpoint_attempts_exhausted")
        self.assertEqual(self.guard.health()["completed_milestones"], [])
        with self.assertRaises(FactoryError): self.verify()

    def test_success_is_candidate_bound_evidence_not_acceptance(self):
        result = self.verify()
        receipt = json.loads(Path(result["evidence_path"]).read_text())
        self.assertEqual(receipt["execution"]["exit_code"], 0)
        self.assertEqual(receipt["candidate_commit"], self.sha)
        self.assertEqual(result["progress"]["product_acceptance"], "not_established")

    def test_completed_milestone_loses_validity_when_machine_receipt_changes(self):
        result = self.verify()
        Path(result["evidence_path"]).write_text('{"claimed":"passed"}')
        with self.assertRaises(FactoryError): self.make()

    def test_non_commit_candidate_is_not_persisted_as_evidence(self):
        self.guard.admit_turn("initial")
        with self.assertRaises(FactoryError): self.guard.verify_next("untrusted note", remaining_seconds=10)
        self.assertNotIn("untrusted note", self.path.read_text())

    def test_cancellation_before_worker_entry_is_never_cleared_by_worker(self):
        self.guard.admit_turn("initial")
        self.guard.begin_verification()
        self.guard.cancel_verification()
        with self.assertRaises(FactoryError): self.verify()
        state = json.loads(self.path.read_text())
        self.assertEqual(state["attempts"], [])
        self.assertEqual(state["completed"], [])
        self.guard.begin_verification()
        self.assertEqual(self.verify()["outcome"], "passed")

    def test_second_scheduled_worker_cannot_clear_cancellation(self):
        self.guard.begin_verification()
        self.guard.cancel_verification()
        with self.assertRaises(FactoryError): self.guard.begin_verification()
        self.assertTrue(self.guard._cancelled.is_set())

    def test_dirty_or_wrong_candidate_is_rejected_without_advancing(self):
        self.guard.admit_turn("initial")
        self.assertEqual(self.guard.verify_next("a"*40, remaining_seconds=20)["outcome"], "candidate_rejected")
        (self.repo / "input").write_text("changed")
        self.assertEqual(self.verify()["outcome"], "candidate_rejected")
        self.assertEqual(json.loads(self.path.read_text())["completed"], [])

    def test_command_that_modifies_candidate_cannot_claim_progress(self):
        self.policy["milestones"][0]["command"] = [sys.executable, "-c", "from pathlib import Path; Path('input').write_text('changed')"]
        self.path.unlink(); self.guard = self.make()
        self.assertEqual(self.verify()["outcome"], "candidate_changed")

    def test_crash_after_claim_is_unknown_without_automatic_replay(self):
        def runner(argv, cwd, timeout):
            if argv[0] == sys.executable: raise RuntimeError("simulated interruption")
            return run_command(argv, cwd, timeout)
        self.guard = self.make(runner=runner)
        with self.assertRaises(RuntimeError): self.verify()
        self.assertEqual(self.make().health()["reason"], "checkpoint_execution_unknown")
        with self.assertRaises(FactoryError): self.make().verify_next(self.sha, remaining_seconds=20)

    def test_changed_frozen_policy_cannot_reset_limits(self):
        self.policy["milestones"][0]["max_turns"] = 100
        with self.assertRaises(FactoryError): self.make()

    def test_authorized_remaining_time_caps_every_command(self):
        timeouts = []
        def runner(argv, cwd, timeout):
            timeouts.append(timeout)
            return run_command(argv, cwd, timeout)
        self.guard = self.make(runner=runner)
        self.guard.admit_turn("initial")
        self.guard.verify_next(self.sha, remaining_seconds=0.8)
        self.assertTrue(timeouts); self.assertTrue(all(t <= 0.8 + 1e-9 for t in timeouts))

    def test_milestones_advance_in_order_and_restart_keeps_proof(self):
        second = copy.deepcopy(self.policy["milestones"][0]); second["id"] = "next"
        self.policy["milestones"].append(second); self.path.unlink(); self.guard = self.make()
        self.guard.admit_turn("one"); self.assertEqual(self.verify()["progress"]["next_milestone"], "next")
        self.guard = self.make(); self.assertEqual(self.guard.health()["turns_since_checkpoint"], 0)
        self.assertEqual(self.verify()["progress"]["completed_milestones"], ["runnable", "next"])

    def test_waiting_for_dispatch_does_not_spend_checkpoint_clock(self):
        self.now += 1000
        self.assertEqual(self.guard.health()["seconds_since_checkpoint"], 0)
        self.assertEqual(self.guard.admit_turn("first")["state"], "waiting")
        self.now += 60
        self.assertEqual(self.guard.health()["reason"], "checkpoint_time_exhausted")

    def test_verification_does_not_block_health_and_can_be_cancelled(self):
        self.policy["milestones"][0]["command"] = [sys.executable, "-c", "import time; time.sleep(4)"]
        self.path.unlink(); self.guard = self.make(); self.guard.admit_turn("initial")
        result = []
        thread = threading.Thread(target=lambda:result.append(self.verify()))
        thread.start()
        end = time.monotonic()+2
        while self.guard._active_claim is None and time.monotonic()<end: time.sleep(0.01)
        started = time.monotonic()
        self.assertEqual(self.guard.health()["state"], "verifying")
        self.assertLess(time.monotonic()-started, 0.5)
        self.assertEqual(self.make().health()["reason"], "checkpoint_execution_unknown")
        self.guard.cancel_verification(); thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result[0]["outcome"], "cancelled")


if __name__ == "__main__": unittest.main()
