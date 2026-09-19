import unittest

from fca import ExchangeCapsule, ExchangeEvidence, ExchangeRegistry, ExchangeState


class ExchangeRegistryTests(unittest.TestCase):
    def capsule(self):
        return ExchangeCapsule.from_dict({
            "schema": "fca-fap.exchange.v1",
            "source_project": "FAP",
            "source_commit": "a" * 40,
            "capability": "goal_loop",
            "mechanism": {"kind": "bounded"},
            "evidence": {"tests": "pass"},
            "constraints": ["shadow first"],
        })

    def test_receive_shadow_accept(self):
        cap = self.capsule()
        reg = ExchangeRegistry(shadow_after=1, accept_after=2)
        self.assertEqual(reg.receive(cap), ExchangeState.RECEIVED)
        self.assertEqual(reg.add_evidence(cap.digest, ExchangeEvidence("1", True)), ExchangeState.SHADOW)
        self.assertEqual(reg.add_evidence(cap.digest, ExchangeEvidence("2", True)), ExchangeState.ACCEPTED)
        self.assertEqual(reg.accepted_capabilities(), ("goal_loop",))

    def test_duplicate_evidence_does_not_promote_twice(self):
        cap = self.capsule()
        reg = ExchangeRegistry(shadow_after=1, accept_after=2)
        reg.receive(cap)
        reg.add_evidence(cap.digest, ExchangeEvidence("same", True))
        self.assertEqual(reg.add_evidence(cap.digest, ExchangeEvidence("same", True)), ExchangeState.SHADOW)

    def test_regression_rejects(self):
        cap = self.capsule()
        reg = ExchangeRegistry()
        reg.receive(cap)
        self.assertEqual(
            reg.add_evidence(cap.digest, ExchangeEvidence("bad", True, regression=True)),
            ExchangeState.REJECTED,
        )


if __name__ == "__main__":
    unittest.main()
