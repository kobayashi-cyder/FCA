import unittest

from fca import OrganRegistry, OrganResult, ProviderHealth, ProviderHealthGate


class ProviderHealthGateTests(unittest.TestCase):
    def test_provider_backed_organ_fails_closed_without_probe(self):
        calls = {"n": 0}
        gate = ProviderHealthGate()
        reg = OrganRegistry(health_gate=gate)

        def image(goal, observation):
            calls["n"] += 1
            return OrganResult("rendered", terminal=True)

        reg.register("image", image, capability="image")
        result = reg.run("image", "draw", "state")
        self.assertTrue(result.blocked)
        self.assertEqual(result.reason, "provider_probe_required")
        self.assertEqual(calls["n"], 0)

    def test_healthy_declared_capability_executes(self):
        gate = ProviderHealthGate(ProviderHealth("healthy", frozenset({"image"}), "provider-a"))
        reg = OrganRegistry(health_gate=gate)
        reg.register("image", lambda goal, observation: OrganResult("rendered", terminal=True), capability="image")
        result = reg.run("image", "draw", "state")
        self.assertFalse(result.blocked)
        self.assertEqual(result.observation, "rendered")

    def test_healthy_provider_cannot_use_undeclared_capability(self):
        gate = ProviderHealthGate(ProviderHealth("healthy", frozenset({"chat"}), "provider-a"))
        reg = OrganRegistry(health_gate=gate)
        reg.register("image", lambda goal, observation: OrganResult("should not run"), capability="image")
        result = reg.run("image", "draw", "state")
        self.assertTrue(result.blocked)
        self.assertEqual(result.reason, "capability_not_declared")

    def test_local_organs_remain_ungated(self):
        reg = OrganRegistry(health_gate=ProviderHealthGate())
        reg.register("local", lambda goal, observation: OrganResult("ok"))
        self.assertEqual(reg.run("local", "goal", "state").observation, "ok")

    def test_unhealthy_reason_is_preserved(self):
        gate = ProviderHealthGate(ProviderHealth("unhealthy", frozenset({"image"}), reason="timeout"))
        reg = OrganRegistry(health_gate=gate)
        reg.register("image", lambda goal, observation: OrganResult("bad"), capability="image")
        result = reg.run("image", "draw", "state")
        self.assertTrue(result.blocked)
        self.assertEqual(result.reason, "timeout")


if __name__ == "__main__":
    unittest.main()
