from __future__ import annotations

import unittest

from fca.repository_host_adapter import (
    FAP_REPOSITORY_HOST_CONTRACT,
    RepositoryHostContractError,
    adapt_fap_repository_host,
    repository_host_runner_from_mapping,
)


class RepositoryHostAdapterTests(unittest.TestCase):
    def _payload(self):
        return {
            "contract": FAP_REPOSITORY_HOST_CONTRACT,
            "state": "verified_candidate",
            "observation": "repository candidate verified plan=abc",
            "plan_id": "a" * 64,
            "repository_digest": "b" * 64,
            "progress": 0.8,
            "reason": "repository_coding_verified_candidate",
            "attempts": 1,
            "repairs_used": 0,
        }

    def test_adapts_verified_candidate(self):
        result = adapt_fap_repository_host(self._payload())
        self.assertEqual(result.state, "verified_candidate")
        self.assertEqual(result.plan_id, "a" * 64)
        self.assertEqual(result.repository_digest, "b" * 64)
        self.assertEqual(result.progress, 0.8)

    def test_rejects_unknown_fields_to_block_content_smuggling(self):
        payload = self._payload()
        payload["diff"] = "SECRET SOURCE"
        with self.assertRaises(RepositoryHostContractError):
            adapt_fap_repository_host(payload)

    def test_rejects_invalid_verified_hashes_and_attempts(self):
        payload = self._payload()
        payload["plan_id"] = "bad"
        with self.assertRaises(RepositoryHostContractError):
            adapt_fap_repository_host(payload)

        payload = self._payload()
        payload["attempts"] = 0
        with self.assertRaises(RepositoryHostContractError):
            adapt_fap_repository_host(payload)

    def test_rejects_provider_text_in_reason_code(self):
        payload = self._payload()
        payload["state"] = "rejected"
        payload["reason"] = "provider failed SECRET=/tmp/key"
        with self.assertRaises(RepositoryHostContractError):
            adapt_fap_repository_host(payload)

    def test_rejected_payload_may_use_empty_hashes(self):
        payload = self._payload()
        payload.update({
            "state": "rejected",
            "plan_id": "",
            "repository_digest": "",
            "progress": 0.0,
            "attempts": 0,
            "repairs_used": 0,
            "reason": "proposal_provider_failed:RuntimeError",
        })
        result = adapt_fap_repository_host(payload)
        self.assertEqual(result.state, "rejected")
        self.assertEqual(result.plan_id, "")

    def test_mapping_runner_wraps_transport_without_fap_import(self):
        calls = []

        def raw(goal, observation):
            calls.append((goal, observation))
            return self._payload()

        runner = repository_host_runner_from_mapping(raw)
        result = runner("fix repository", "connectome selected repository_coding")

        self.assertEqual(result.state, "verified_candidate")
        self.assertEqual(calls, [("fix repository", "connectome selected repository_coding")])

    def test_bounds_numeric_and_text_fields(self):
        payload = self._payload()
        payload["progress"] = float("nan")
        with self.assertRaises(RepositoryHostContractError):
            adapt_fap_repository_host(payload)

        payload = self._payload()
        payload["repairs_used"] = 2
        payload["attempts"] = 1
        with self.assertRaises(RepositoryHostContractError):
            adapt_fap_repository_host(payload)

        payload = self._payload()
        payload["observation"] = "x" * 257
        with self.assertRaises(RepositoryHostContractError):
            adapt_fap_repository_host(payload, max_observation_chars=256)


if __name__ == "__main__":
    unittest.main()
