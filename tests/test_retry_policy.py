import unittest

from fca.organs import OrganRegistry, OrganResult
from fca.retry_policy import OrganRetryPolicy


class OrganRetryPolicyTests(unittest.TestCase):
    def test_retry_is_fail_closed_without_idempotency(self):
        with self.assertRaises(ValueError): OrganRetryPolicy(max_attempts=2)
        with self.assertRaises(ValueError): OrganRetryPolicy(max_attempts=2, idempotent=True)
        with self.assertRaises(ValueError): OrganRetryPolicy(max_attempts=4, idempotent=True, justification="read only")
        with self.assertRaises(ValueError): OrganRetryPolicy(retryable_exceptions=(TimeoutError,))
        with self.assertRaises(ValueError): OrganRetryPolicy(2, True, "read only", retryable_exceptions=(str,))
        with self.assertRaises(ValueError): OrganRetryPolicy(2, True, "read only", retry_delay_seconds=-0.1)
        with self.assertRaises(ValueError): OrganRetryPolicy(2, True, "read only", retry_delay_seconds=60.1)
        with self.assertRaises(ValueError): OrganRetryPolicy(retry_delay_seconds=1)
        with self.assertRaises(ValueError): OrganRetryPolicy(2, True, "read only", retry_backoff_multiplier=0.9)
        with self.assertRaises(ValueError): OrganRetryPolicy(2, True, "read only", retry_backoff_multiplier=4.1)
        with self.assertRaises(ValueError): OrganRetryPolicy(2, True, "read only", retry_backoff_multiplier=2)
        with self.assertRaises(ValueError): OrganRetryPolicy(2, True, "read only", max_total_delay_seconds=-1)
        with self.assertRaises(ValueError): OrganRetryPolicy(2, True, "read only", max_total_delay_seconds=121)
        with self.assertRaises(ValueError): OrganRetryPolicy(2, True, "read only", retry_delay_seconds=1, max_total_delay_seconds=0)
        with self.assertRaises(ValueError): OrganRetryPolicy(2, True, "read only", retry_delay_seconds=1, retry_jitter_ratio=-0.1)
        with self.assertRaises(ValueError): OrganRetryPolicy(2, True, "read only", retry_delay_seconds=1, retry_jitter_ratio=0.6)
        with self.assertRaises(ValueError): OrganRetryPolicy(2, True, "read only", retry_jitter_ratio=0.1)

    def test_declared_timeout_retries_when_explicitly_safe(self):
        calls = []
        def organ(goal, observation):
            calls.append(1)
            if len(calls) == 1: raise TimeoutError("temporary")
            return OrganResult("recovered")
        reg = OrganRegistry()
        reg.register("read", organ, retry_policy=OrganRetryPolicy(2, True, "read-only lookup", retryable_exceptions=(TimeoutError,)))
        self.assertEqual(reg.run("read", "goal", "state").observation, "recovered")
        self.assertEqual(len(calls), 2)

    def test_retry_delay_runs_only_between_retryable_attempts(self):
        calls, delays = [], []
        def organ(goal, observation):
            calls.append(1)
            if len(calls) < 3: raise TimeoutError("temporary")
            return OrganResult("recovered")
        reg = OrganRegistry(sleeper=delays.append)
        reg.register("read", organ, retry_policy=OrganRetryPolicy(3, True, "read-only lookup", retryable_exceptions=(TimeoutError,), retry_delay_seconds=0.25))
        self.assertEqual(reg.run("read", "goal", "state").observation, "recovered")
        self.assertEqual(delays, [0.25, 0.25])

    def test_retry_backoff_progresses_with_fca_attempt_cap(self):
        calls, delays = [], []
        def organ(goal, observation):
            calls.append(1)
            if len(calls) < 3: raise TimeoutError("temporary")
            return OrganResult("recovered")
        reg = OrganRegistry(sleeper=delays.append)
        reg.register("read", organ, retry_policy=OrganRetryPolicy(3, True, "read-only lookup", retryable_exceptions=(TimeoutError,), retry_delay_seconds=10, retry_backoff_multiplier=2))
        self.assertEqual(reg.run("read", "goal", "state").observation, "recovered")
        self.assertEqual(delays, [10.0, 20.0])

    def test_backoff_delay_is_bounded(self):
        policy = OrganRetryPolicy(3, True, "read-only lookup", retry_delay_seconds=40, retry_backoff_multiplier=4)
        self.assertEqual(policy.delay_before_attempt(1), 40.0)
        self.assertEqual(policy.delay_before_attempt(2), 60.0)

    def test_jitter_is_bounded_and_deterministic_when_injected(self):
        policy = OrganRetryPolicy(2, True, "read-only lookup", retry_delay_seconds=10, retry_jitter_ratio=0.5)
        self.assertEqual(policy.delay_before_attempt(1, jitter_unit=0.0), 5.0)
        self.assertEqual(policy.delay_before_attempt(1, jitter_unit=1.0), 15.0)
        with self.assertRaises(ValueError): policy.delay_before_attempt(1, jitter_unit=1.1)
        calls, delays = [], []
        jitter = iter((0.0, 1.0))
        def organ(goal, observation):
            calls.append(1)
            if len(calls) < 3: raise TimeoutError("temporary")
            return OrganResult("recovered")
        reg = OrganRegistry(sleeper=delays.append, jitter_source=lambda: next(jitter))
        reg.register("read", organ, retry_policy=OrganRetryPolicy(3, True, "read-only lookup", retryable_exceptions=(TimeoutError,), retry_delay_seconds=10, retry_jitter_ratio=0.5))
        self.assertEqual(reg.run("read", "goal", "state").observation, "recovered")
        self.assertEqual(delays, [5.0, 15.0])

    def test_jitter_never_exceeds_total_delay_budget(self):
        calls, delays = [], []
        def organ(goal, observation):
            calls.append(1)
            raise TimeoutError("temporary")
        reg = OrganRegistry(sleeper=delays.append, jitter_source=lambda: 1.0)
        reg.register("read", organ, retry_policy=OrganRetryPolicy(3, True, "read-only lookup", retryable_exceptions=(TimeoutError,), retry_delay_seconds=20, retry_jitter_ratio=0.5, max_total_delay_seconds=25))
        with self.assertRaises(TimeoutError): reg.run("read", "goal", "state")
        self.assertEqual(delays, [25.0])
        self.assertEqual(len(calls), 2)

    def test_total_delay_budget_caps_and_stops_retries(self):
        calls, delays = [], []
        def organ(goal, observation):
            calls.append(1)
            raise TimeoutError("temporary")
        reg = OrganRegistry(sleeper=delays.append)
        reg.register("read", organ, retry_policy=OrganRetryPolicy(3, True, "read-only lookup", retryable_exceptions=(TimeoutError,), retry_delay_seconds=40, retry_backoff_multiplier=4, max_total_delay_seconds=50))
        with self.assertRaises(TimeoutError): reg.run("read", "goal", "state")
        self.assertEqual(delays, [40.0, 10.0])
        self.assertEqual(len(calls), 3)

    def test_zero_remaining_budget_prevents_another_attempt(self):
        calls, delays = [], []
        def organ(goal, observation):
            calls.append(1)
            raise TimeoutError("temporary")
        reg = OrganRegistry(sleeper=delays.append)
        reg.register("read", organ, retry_policy=OrganRetryPolicy(3, True, "read-only lookup", retryable_exceptions=(TimeoutError,), retry_delay_seconds=40, retry_backoff_multiplier=4, max_total_delay_seconds=40))
        with self.assertRaises(TimeoutError): reg.run("read", "goal", "state")
        self.assertEqual(delays, [40.0])
        self.assertEqual(len(calls), 2)

    def test_terminal_exception_never_sleeps(self):
        delays = []
        def organ(goal, observation): raise ValueError("bad input")
        reg = OrganRegistry(sleeper=delays.append)
        reg.register("read", organ, retry_policy=OrganRetryPolicy(3, True, "read-only lookup", retryable_exceptions=(TimeoutError,), retry_delay_seconds=1))
        with self.assertRaises(ValueError): reg.run("read", "goal", "state")
        self.assertEqual(delays, [])

    def test_unconfigured_organ_never_retries(self):
        calls = []
        def organ(goal, observation): calls.append(1); raise TimeoutError("temporary")
        reg = OrganRegistry(); reg.register("read", organ)
        with self.assertRaises(TimeoutError): reg.run("read", "goal", "state")
        self.assertEqual(len(calls), 1)

    def test_undeclared_transport_exception_is_never_retried(self):
        calls = []
        def organ(goal, observation): calls.append(1); raise ConnectionError("not declared retryable")
        reg = OrganRegistry(); reg.register("read", organ, retry_policy=OrganRetryPolicy(3, True, "read-only lookup", retryable_exceptions=(TimeoutError,)))
        with self.assertRaises(ConnectionError): reg.run("read", "goal", "state")
        self.assertEqual(len(calls), 1)

    def test_blocked_result_is_terminal_not_retried(self):
        calls = []
        def organ(goal, observation): calls.append(1); return OrganResult(observation, blocked=True, reason="approval_required")
        reg = OrganRegistry(); reg.register("write", organ, retry_policy=OrganRetryPolicy(3, True, "fixture", retryable_exceptions=(TimeoutError,), retry_delay_seconds=1))
        result = reg.run("write", "goal", "state")
        self.assertTrue(result.blocked); self.assertEqual(len(calls), 1)


if __name__ == "__main__": unittest.main()
