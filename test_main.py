import unittest
from kaggle_environments import make
import main
import hybrid_controller


class TestMainAgent(unittest.TestCase):
    def test_imports_and_entrypoints(self):
        """Verify agent functions are callable and exported."""
        self.assertTrue(callable(main.agent))
        self.assertTrue(callable(main.kaggle_submission_agent))

    def test_action_structure(self):
        """Verify action output structure across different steps."""
        env = make("kaggriculture", configuration={"episodeSteps": 720})
        env.reset()
        obs = env.state[0].observation

        # Early step
        obs["step"] = 0
        action = main.agent(obs)
        self.assertIn("farmer", action)
        self.assertIn("hands", action)
        self.assertIn("market", action)
        self.assertIsInstance(action["farmer"], list)
        self.assertIsInstance(action["hands"], list)
        self.assertIsInstance(action["market"], list)

        # Mid step
        obs["step"] = 300
        action = main.agent(obs)
        self.assertIn("farmer", action)
        self.assertIn("hands", action)
        self.assertIn("market", action)

        # Terminal step (>= 717)
        obs["step"] = 718
        obs["hour"] = 22
        obs["day"] = 29
        action = main.agent(obs)
        self.assertIn("farmer", action)
        self.assertIn("hands", action)
        self.assertIn("market", action)

    def test_pre_production_animal_harvest(self):
        """Verify pre-production harvest triggers HARVEST on scheduled day before production."""
        obs = {
            "player": 0,
            "day": 5,  # Cow placed_day=0, age=5 (5 % 2 == 1 -> harvest day before production)
            "farms": [
                {
                    "farmer": [0, 0],
                    "hands": [],
                    "tiles": [
                        [
                            {
                                "kind": "PASTURE",
                                "animal": "COW",
                                "placed_day": 0,
                                "yield_units": 2,
                            }
                        ]
                    ],
                }
            ],
        }
        action = {"farmer": ["PASS"], "hands": [], "market": []}
        modified = main._pre_production_animal_harvest(action, obs)
        self.assertEqual(modified["farmer"], ["HARVEST"])

    def test_hybrid_controller_modules(self):
        """Verify hybrid_controller pre-computation, action masking, macro controller, and fallbacks."""
        obs = {
            "player": 0,
            "farms": [
                {
                    "money": 30,  # low money
                    "tiles": [[{"kind": "PASTURE", "animal": "COW"}]],
                },
                {"money": 500, "tiles": []},
            ],
            "private": {
                "shed": {"WHEAT": 5},  # 1 animal -> wheat reserve = 2*1+5 = 7 wheat (only 5 in shed, so 0 wheat sellable)
                "inventories": [],
            },
            "market": {"prices": {"WHEAT": 25, "COW": 400}},
        }

        # Calculated field engine
        needed = hybrid_controller.CalculatedFieldEngine.calculate_cash_needed([["BUY_ANIMAL", "COW", 1]], obs)
        self.assertEqual(needed, 400)

        # Dynamic action masker: masks out unaffordable COW buy ($400 > $30) and wheat sell (holding 5 <= reserve 7)
        proposed_action = {
            "farmer": ["PASS"],
            "hands": [],
            "market": [["BUY_ANIMAL", "COW", 1], ["SELL", "WHEAT", 5]],
        }
        masked = hybrid_controller.DynamicActionMasker.mask_action(proposed_action, obs)
        self.assertEqual(masked["market"], [])

        # Macro controller: evaluate parameter shifts
        macro = hybrid_controller.MacroTemporalController()
        macro.evaluate_macro_state(obs, step=700)
        self.assertEqual(macro.early_terminal, 716)

        # Fallback monitor
        fallback_action = hybrid_controller.StateTriggeredFallback.audit_and_fallback(
            masked, proposed_action, confidence_score=0.2
        )
        self.assertEqual(fallback_action, proposed_action)

    def test_local_game_execution(self):
        """Run a short local game episode to ensure no exceptions or crashes."""
        env = make("kaggriculture", configuration={"episodeSteps": 48})
        env.run([main.agent, "starter"])
        final_step = env.steps[-1]
        self.assertGreater(final_step[0].reward, 0)
        self.assertIn("reward", final_step[0])


if __name__ == "__main__":
    unittest.main()
