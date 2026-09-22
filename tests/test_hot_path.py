import unittest

from fca.hot_path import VerifiedHotPath


class HotPathTests(unittest.TestCase):
    def test_native_path_is_verified_then_used(self):
        hot = VerifiedHotPath(lambda x: x * 2, lambda x: x * 2)
        self.assertEqual(hot(3), 6)
        self.assertTrue(hot.status.native_verified)
        self.assertTrue(hot.status.native_enabled)
        self.assertEqual(hot(4), 8)

    def test_mismatch_falls_back_and_disables_native(self):
        hot = VerifiedHotPath(lambda x: x * 2, lambda x: x * 3)
        self.assertEqual(hot(3), 6)
        self.assertFalse(hot.status.native_enabled)
        self.assertEqual(hot.status.native_failures, 1)
        self.assertEqual(hot(4), 8)


if __name__ == "__main__":
    unittest.main()
