import unittest

from fca import (
    ExchangeCapsule,
    ExchangeEvidence,
    ExchangeRegistry,
    ExchangeState,
    LazyOrganRegistry,
    OrganResult,
    RepositoryCodingHostBinding,
    RepositoryCodingHostResult,
    register_repository_coding_organ,
)


CAPABILITY = "repository_coding_verified_candidate"


def repository_capsule():
    return ExchangeCapsule.from_dict({
        "schema": "fca-fap.exchange.v1",
        "source_project": "FAP",
        "source_commit": "a" * 40,
        "capability": CAPABILITY,
        "mechanism": {
            "contract": "fap.repository.coding.v1",
            "plan_id": "1" * 64,
        },
        "evidence": {"status": "verified_candidate"},
        "constraints": ["provenance only"],
    })


class RepositoryCodingOrganTests(unittest.TestCase):
    def accepted_registry(self, *, accept_after=2):
        cap = repository_capsule()
        registry = ExchangeRegistry(shadow_after=1, accept_after=accept_after)
        self.assertEqual(registry.receive(cap), ExchangeState.RECEIVED)
        for index in range(accept_after):
            state = registry.add_evidence(
                cap.digest,
                ExchangeEvidence(
                    key=f"independent-{index}",
                    passed=True,
                    quality_delta=0.0,
                ),
            )
        self.assertEqual(state, ExchangeState.ACCEPTED)
        return cap, registry

    def test_registration_is_lazy_and_other_selection_does_not_load_runner(self):
        cap, registry = self.accepted_registry()
        calls = []

        def runner(goal, observation):
            calls.append((goal, observation))
            return RepositoryCodingHostResult(
                state="verified_candidate",
                observation="candidate ready",
                plan_id="2" * 64,
                repository_digest="3" * 64,
                progress=1.0,
            )

        organs = LazyOrganRegistry()
        register_repository_coding_organ(
            organs,
            registry,
            RepositoryCodingHostBinding(
                binding_id="host-repository-coder",
                capsule_digest=cap.digest,
                runner=runner,
            ),
        )
        organs.register(
            "conversation",
            lambda: (
                lambda goal, observation: OrganResult(
                    observation="conversation only",
                    progress=0.1,
                )
            ),
        )

        self.assertEqual(organs.loaded, ())
        self.assertEqual(calls, [])

        result = organs.run("conversation", "talk", "hello")
        self.assertEqual(result.observation, "conversation only")
        self.assertEqual(organs.loaded, ("conversation",))
        self.assertEqual(calls, [])

    def test_received_or_shadow_capsule_blocks_before_runner(self):
        cap = repository_capsule()
        registry = ExchangeRegistry(shadow_after=1, accept_after=2)
        registry.receive(cap)
        calls = []

        def runner(goal, observation):
            calls.append(True)
            raise AssertionError("runner must not execute before acceptance")

        organs = LazyOrganRegistry()
        register_repository_coding_organ(
            organs,
            registry,
            RepositoryCodingHostBinding(
                binding_id="host-repository-coder",
                capsule_digest=cap.digest,
                runner=runner,
            ),
        )

        received = organs.run("repository_coding", "fix repo", "state")
        self.assertTrue(received.blocked)
        self.assertEqual(
            received.reason,
            "repository_coding_evidence_not_accepted",
        )
        self.assertEqual(calls, [])

        self.assertEqual(
            registry.add_evidence(
                cap.digest,
                ExchangeEvidence("independent-1", True),
            ),
            ExchangeState.SHADOW,
        )
        shadow = organs.run("repository_coding", "fix repo", "state")
        self.assertTrue(shadow.blocked)
        self.assertEqual(calls, [])

    def test_accepted_exact_capsule_invokes_host_runner_after_selection(self):
        cap, registry = self.accepted_registry()
        calls = []

        def runner(goal, observation):
            calls.append((goal, observation))
            return RepositoryCodingHostResult(
                state="verified_candidate",
                observation="verified repository candidate",
                plan_id="4" * 64,
                repository_digest="5" * 64,
                progress=0.75,
            )

        organs = LazyOrganRegistry()
        register_repository_coding_organ(
            organs,
            registry,
            RepositoryCodingHostBinding(
                binding_id="host-repository-coder",
                capsule_digest=cap.digest,
                runner=runner,
            ),
        )

        self.assertEqual(calls, [])
        result = organs.run(
            "repository_coding",
            "repair repository",
            "repository observation",
        )

        self.assertEqual(calls, [("repair repository", "repository observation")])
        self.assertFalse(result.blocked)
        self.assertFalse(result.terminal)
        self.assertEqual(result.reward, 0.0)
        self.assertEqual(result.progress, 0.75)
        self.assertIn("repository_coding_verified_candidate", result.reason)
        self.assertEqual(
            result.observation,
            "verified repository candidate",
        )

    def test_registry_allows_is_exact_digest_and_capability(self):
        cap, registry = self.accepted_registry()

        self.assertTrue(registry.allows(cap.digest, CAPABILITY))
        self.assertFalse(registry.allows("0" * 64, CAPABILITY))
        self.assertFalse(registry.allows(cap.digest, "different_capability"))

    def test_duplicate_evidence_does_not_unlock_runner(self):
        cap = repository_capsule()
        registry = ExchangeRegistry(shadow_after=1, accept_after=2)
        registry.receive(cap)
        registry.add_evidence(cap.digest, ExchangeEvidence("same", True))
        registry.add_evidence(cap.digest, ExchangeEvidence("same", True))
        self.assertEqual(registry.state(cap.digest), ExchangeState.SHADOW)

        calls = []
        organs = LazyOrganRegistry()
        register_repository_coding_organ(
            organs,
            registry,
            RepositoryCodingHostBinding(
                binding_id="host-repository-coder",
                capsule_digest=cap.digest,
                runner=lambda goal, observation: calls.append(True),
            ),
        )

        result = organs.run("repository_coding", "goal", "observation")
        self.assertTrue(result.blocked)
        self.assertEqual(calls, [])

    def test_malformed_verified_result_fails_closed(self):
        cap, registry = self.accepted_registry()
        organs = LazyOrganRegistry()
        register_repository_coding_organ(
            organs,
            registry,
            RepositoryCodingHostBinding(
                binding_id="host-repository-coder",
                capsule_digest=cap.digest,
                runner=lambda goal, observation: RepositoryCodingHostResult(
                    state="verified_candidate",
                    observation="bad candidate",
                    plan_id="not-a-hash",
                    repository_digest="5" * 64,
                    progress=1.0,
                ),
            ),
        )

        result = organs.run("repository_coding", "goal", "observation")
        self.assertTrue(result.blocked)
        self.assertEqual(result.reward, 0.0)
        self.assertTrue(
            result.reason.startswith("repository_coding_result_rejected:")
        )

    def test_runner_exception_fails_closed_without_message_leak(self):
        cap, registry = self.accepted_registry()

        def runner(goal, observation):
            raise RuntimeError("secret provider details")

        organs = LazyOrganRegistry()
        register_repository_coding_organ(
            organs,
            registry,
            RepositoryCodingHostBinding(
                binding_id="host-repository-coder",
                capsule_digest=cap.digest,
                runner=runner,
            ),
        )

        result = organs.run("repository_coding", "goal", "observation")
        self.assertTrue(result.blocked)
        self.assertEqual(
            result.reason,
            "repository_coding_runner_failed:RuntimeError",
        )
        self.assertNotIn("secret provider details", result.reason)

    def test_binding_must_preserve_sandbox_and_promotion_boundaries(self):
        cap, registry = self.accepted_registry()
        organs = LazyOrganRegistry()
        register_repository_coding_organ(
            organs,
            registry,
            RepositoryCodingHostBinding(
                binding_id="unsafe-binding",
                capsule_digest=cap.digest,
                runner=lambda goal, observation: RepositoryCodingHostResult(
                    state="rejected",
                    observation=observation,
                ),
                sandbox_only=False,
            ),
        )

        with self.assertRaisesRegex(ValueError, "sandbox_only"):
            organs.run("repository_coding", "goal", "observation")


if __name__ == "__main__":
    unittest.main()
