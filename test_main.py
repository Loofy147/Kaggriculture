import unittest
from kaggle_environments import make
import main


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

    def test_local_game_execution(self):
        """Run a short local game episode to ensure no exceptions or crashes."""
        env = make("kaggriculture", configuration={"episodeSteps": 48})
        env.run([main.agent, "starter"])
        final_step = env.steps[-1]
        self.assertGreater(final_step[0].reward, 0)
        self.assertIn("reward", final_step[0])


    def test_market_squeeze_agent(self):
        """Verify market squeeze triggers BUY_PRODUCT WHEAT when opponent has >3 animals and wheat market supply is low."""
        obs = {
            "step": 100,
            "player": 0,
            "farms": [
                {"money": 1000, "farmer": [0, 0], "hands": []},
                {
                    "money": 500,
                    "farmer": [0, 0],
                    "hands": [],
                    "tiles": [
                        [{"kind": "PASTURE", "animal": "COW"} for _ in range(4)]
                    ],
                },
            ],
            "market": {"inventory": {"WHEAT": 9500}},
        }
        action = {"farmer": ["PASS"], "hands": [], "market": []}
        res = main._market_squeeze_agent(obs, action)
        self.assertTrue(any(o == ["BUY_PRODUCT", "WHEAT", 5] for o in res["market"]))

    def test_collision_repair_agent(self):
        """Verify collision repair stalls movement when walking directly into opponent unit."""
        obs = {
            "player": 0,
            "farms": [
                {"farmer": [2, 2], "hands": []},
                {"farmer": [2, 1], "hands": []},
            ],
        }
        action = {"farmer": ["NORTH"], "hands": [], "market": []}
        main._weed_repair_pending = {}
        res = main._collision_repair_agent(obs, action)
        self.assertEqual(res["farmer"], ["PASS"])
        self.assertIn(0, main._weed_repair_pending)
        self.assertEqual(main._weed_repair_pending[0], [["NORTH"]])

    def test_buy_front_running(self):
        """Verify buy front-running adds BUY_ANIMAL/BUY_SEED from future trace step."""
        main._CLONE_CONFIDENCE = 5
        main._FRONT_RUN_HORIZON = 2
        step = 10
        original_trace_11 = main._TRACE[11] if len(main._TRACE) > 11 else None
        main._TRACE[11] = {"market": [["BUY_ANIMAL", "COW", 1]]}
        obs = {
            "player": 0,
            "farms": [{"money": 2000}],
            "private": {"shed": {}},
            "market": {"prices": {}},
        }
        action = {"market": []}
        main._front_run(action, obs, step)
        self.assertTrue(any(o == ["BUY_ANIMAL", "COW", 1] for o in action["market"]))
        if original_trace_11 is not None:
            main._TRACE[11] = original_trace_11

if __name__ == "__main__":
    unittest.main()
