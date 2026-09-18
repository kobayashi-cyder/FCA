import unittest

from fca import HotColdMemory, OrganBid, ValueScheduler


class MemorySchedulerTests(unittest.TestCase):
    def test_memory_pages_and_bounds(self):
        m = HotColdMemory(hot_capacity=2, cold_capacity=3, page_in=2)
        for i in range(6):
            m.remember(str(i), f"topic {i}", utility=i / 10)
        self.assertLessEqual(m.size, 5)
        self.assertLessEqual(len(m.hot), 2)
        self.assertLessEqual(len(m.cold), 3)

    def test_retrieval_pages_into_hot(self):
        m = HotColdMemory(hot_capacity=1, cold_capacity=4, page_in=1)
        m.remember("fly", "mushroom body kenyon cells", utility=1.0)
        m.remember("other", "unrelated weather", utility=0.0)
        got = m.retrieve("kenyon mushroom", limit=1)
        self.assertEqual(got[0].key, "fly")
        self.assertIn("fly", m.hot)

    def test_high_confidence_and_contradictions_are_retained_preferentially(self):
        m = HotColdMemory(hot_capacity=1, cold_capacity=2, page_in=1)
        m.remember("a", "fact a", confidence=0.95)
        m.remember("b", "fact b", contradiction_group="g")
        m.remember("c", "fact c", confidence=0.1)
        m.remember("d", "fact d", confidence=0.1)
        keys = set(m.hot) | set(m.cold)
        self.assertIn("a", keys)
        self.assertIn("b", keys)

    def test_scheduler_sparse_budget(self):
        s = ValueScheduler(budget=1.0, max_active=2)
        bids = [
            OrganBid("verify", 1.0, 0.8, 0.4, 0.4),
            OrganBid("search", 0.9, 0.5, 0.7, 0.5),
            OrganBid("media", 0.2, 0.2, 0.1, 0.8),
        ]
        selected = s.select(bids)
        self.assertEqual(set(selected), {"verify", "search"})


if __name__ == "__main__":
    unittest.main()
