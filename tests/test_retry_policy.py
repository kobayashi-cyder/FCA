import unittest

from fca.organs import OrganRegistry, OrganResult
from fca.retry_policy import OrganRetryPolicy


class OrganRetryPolicyTests(unittest.TestCase):
    def test_retry_is_fail_closed_without_idempotency(self):
        with self.assertRaises(ValueError):
            OrganRetryPolicy(max_attempts=2)
        with self.assertRaises(ValueError):
            OrganRetryPolicy(max_attempts=2, idempotent=True)
        with self.assertRaises(ValueError):
            OrganRetryPolicy(max_attempts=4, idempotent=True, justification="read only")
        with self.assertRaises(ValueError):
            OrganRetryPolicy(retryable_exceptions=(TimeoutError,))
        with self.assertRaises(ValueError):
            OrganRetryPolicy(2, True, "read only", retryable_exceptions=(str,))

    def test_declared_timeout_retries_when_explicitly_safe(self):
        calls = []
        def organ(goal, observation):
            calls.append(1)
            if len(calls) == 1:
                raise TimeoutError("temporary")
            return OrganResult("recovered")
        reg = OrganRegistry()
        reg.register(
            "read",
            organ,
            retry_policy=OrganRetryPolicy(
                2, True, "read-only lookup", retryable_exceptions=(TimeoutError,)
            ),
        )
        self.assertEqual(reg.run("read", "goal", "state").observation, "recovered")
        self.assertEqual(len(calls), 2)

    def test_unconfigured_organ_never_retries(self):
        calls = []
        def organ(goal, observation):
            calls.append(1)
            raise TimeoutError("temporary")
        reg = OrganRegistry()
        reg.register("read", organ)
        with self.assertRaises(TimeoutError):
            reg.run("read", "goal", "state")
        self.assertEqual(len(calls), 1)

    def test_undeclared_transport_exception_is_never_retried(self):
        calls = []
        def organ(goal, observation):
            calls.append(1)
            raise ConnectionError("not declared retryable")
        reg = OrganRegistry()
        reg.register(
            "read",
            organ,
            retry_policy=OrganRetryPolicy(
                3, True, "read-only lookup", retryable_exceptions=(TimeoutError,)
            ),
        )
        with self.assertRaises(ConnectionError):
            reg.run("read", "goal", "state")
        self.assertEqual(len(calls), 1)

    def test_non_transient_exception_is_never_retried(self):
        calls = []
        def organ(goal, observation):
            calls.append(1)
            raise ValueError("bad input")
        reg = OrganRegistry()
        reg.register(
            "read",
            organ,
            retry_policy=OrganRetryPolicy(
                3, True, "read-only lookup", retryable_exceptions=(TimeoutError,)
            ),
        )
        with self.assertRaises(ValueError):
            reg.run("read", "goal", "state")
        self.assertEqual(len(calls), 1)

    def test_blocked_result_is_terminal_not_retried(self):
        calls = []
        def organ(goal, observation):
            calls.append(1)
            return OrganResult(observation, blocked=True, reason="approval_required")
        reg = OrganRegistry()
        reg.register(
            "write",
            organ,
            retry_policy=OrganRetryPolicy(
                3, True, "fixture", retryable_exceptions=(TimeoutError,)
            ),
        )
        result = reg.run("write", "goal", "state")
        self.assertTrue(result.blocked)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
