import unittest

from fca.organs import OrganRegistry, OrganResult
from fca.retry_policy import OrganRetryPolicy


class RetryAfterTimeout(TimeoutError):
    def __init__(self, message: str, retry_after_seconds):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class RetryAfterHintTests(unittest.TestCase):
    def test_provider_hint_can_raise_delay_but_stays_bounded(self):
        policy = OrganRetryPolicy(2, True, "read-only lookup", retry_delay_seconds=2)
        self.assertEqual(policy.delay_before_attempt(1, retry_after_seconds=10), 10.0)
        self.assertEqual(policy.delay_before_attempt(1, retry_after_seconds=90), 60.0)
        self.assertEqual(
            policy.delay_before_attempt(1, elapsed_delay=115, retry_after_seconds=90),
            5.0,
        )

    def test_malformed_provider_hint_is_ignored(self):
        policy = OrganRetryPolicy(2, True, "read-only lookup", retry_delay_seconds=2)
        for hint in ("later", -1, float("inf"), float("nan")):
            self.assertEqual(policy.delay_before_attempt(1, retry_after_seconds=hint), 2.0)

    def test_registry_honors_retry_after_on_allow_listed_exception(self):
        calls, delays = [], []

        def organ(goal, observation):
            calls.append(1)
            if len(calls) == 1:
                raise RetryAfterTimeout("rate limited", 7)
            return OrganResult("recovered")

        registry = OrganRegistry(sleeper=delays.append)
        registry.register(
            "read",
            organ,
            retry_policy=OrganRetryPolicy(
                2,
                True,
                "read-only lookup",
                retryable_exceptions=(RetryAfterTimeout,),
                retry_delay_seconds=1,
                max_total_delay_seconds=20,
            ),
        )
        self.assertEqual(registry.run("read", "goal", "state").observation, "recovered")
        self.assertEqual(delays, [7.0])
        self.assertEqual(len(calls), 2)

    def test_hint_does_not_make_undeclared_exception_retryable(self):
        calls, delays = [], []

        def organ(goal, observation):
            calls.append(1)
            raise RetryAfterTimeout("not allow-listed", 7)

        registry = OrganRegistry(sleeper=delays.append)
        registry.register(
            "read",
            organ,
            retry_policy=OrganRetryPolicy(
                2,
                True,
                "read-only lookup",
                retryable_exceptions=(ConnectionError,),
                retry_delay_seconds=1,
            ),
        )
        with self.assertRaises(RetryAfterTimeout):
            registry.run("read", "goal", "state")
        self.assertEqual(delays, [])
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
