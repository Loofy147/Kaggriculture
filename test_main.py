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


if __name__ == "__main__":
    unittest.main()
