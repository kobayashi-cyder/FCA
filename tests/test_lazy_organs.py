import unittest

from fca.lazy_organs import LazyOrganRegistry
from fca.organs import OrganResult


class LazyOrganTests(unittest.TestCase):
    def test_loads_only_selected_organ_and_caches_it(self):
        made = {"inspect": 0, "respond": 0}

        def factory(name):
            def make():
                made[name] += 1
                return lambda goal, observation: OrganResult(
                    observation=f"{name}:{observation}", reward=1.0
                )
            return make

        registry = LazyOrganRegistry()
        registry.register("inspect", factory("inspect"))
        registry.register("respond", factory("respond"))

        self.assertEqual(registry.loaded, ())
        out = registry.run("inspect", "g", "s")
        self.assertEqual(out.observation, "inspect:s")
        self.assertEqual(registry.loaded, ("inspect",))
        self.assertEqual(made, {"inspect": 1, "respond": 0})

        registry.run("inspect", "g", "s2")
        self.assertEqual(made["inspect"], 1)


if __name__ == "__main__":
    unittest.main()
