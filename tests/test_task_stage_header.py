"""The operational instruction must name only the actually dispatched stages."""
from factorykit.tasks import _header, render_packet
from tests import test_toolkit as fixtures


class TaskStageHeaderTests(fixtures.Fixture):
    def test_two_stage_practice_instruction_and_payloads_match(self):
        raw, payloads = render_packet(self.config, "toy", [1, 2], "practice-all")
        self.assertIn(b"Execute stages 1 through 2 once in increasing order", raw)
        self.assertNotIn(b"Execute stages 1 through 4", raw)
        self.assertEqual(len(payloads), 2)
        self.assertIn(b"Official synthetic toy specification 1", raw)
        self.assertIn(b"Official synthetic toy specification 2", raw)
        self.assertNotIn(b"Official synthetic toy specification 3", raw)

    def test_default_four_and_separate_stage_instructions_keep_original_text(self):
        self.assertIn("Execute stages 1 through 4 once in increasing order, with an independent gate before advancing.",
                      _header(self.config, "toy", [1, 2, 3, 4], "practice-all"))
        self.assertIn("Execute only stage 2. Earlier specifications are inherited requirements, not new dispatches. "
                      "Do not execute a future stage until its own separate dispatch.",
                      _header(self.config, "toy", [2], "separate"))
        self.assertIn("Execute stages 1, 3 once in increasing order", _header(self.config, "toy", [1, 3], "practice-all"))
