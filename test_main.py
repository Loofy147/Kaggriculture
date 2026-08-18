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

    def test_market_controller_calculated_fields(self):
        """Verify calculated field functions for market order management."""
        obs = {
            "player": 0,
            "farms": [{"money": 500, "tiles": []}, {"money": 500, "tiles": []}],
            "private": {"shed": {"MELON": 2, "WOOL": 1}, "inventories": []},
            "market": {"inventory": {"MELON": 10000, "WOOL": 10000}, "prices": {"MELON": 250, "WOOL": 200}},
            "town": {"unlocked_shops": ["BAKERY"]},
        }

        # Test cash needed calculation for seed and animal buys
        orders = [["BUY_SEED", "WHEAT", 2], ["BUY_ANIMAL", "COW", 1]]
        needed = main._cash_needed(orders, obs)
        self.assertEqual(needed, 2 * 10 + 400)

        # Test sell order priority calculation
        order_melon = ["SELL", "MELON", 2]
        order_wool = ["SELL", "WOOL", 1]
        p_melon = main._sell_priority(order_melon, obs, step=100)
        p_wool = main._sell_priority(order_wool, obs, step=100)
        self.assertIsInstance(p_melon, float)
        self.assertIsInstance(p_wool, float)

        # Test reserve price calculation with market/town drain
        r_melon = main._reserve_price("MELON", step=100, obs=obs, shops=["BAKERY"])
        self.assertGreater(r_melon, 0)

    def test_local_game_execution(self):
        """Run a short local game episode to ensure no exceptions or crashes."""
        env = make("kaggriculture", configuration={"episodeSteps": 48})
        env.run([main.agent, "starter"])
        final_step = env.steps[-1]
        self.assertGreater(final_step[0].reward, 0)
        self.assertIn("reward", final_step[0])


if __name__ == "__main__":
    unittest.main()
