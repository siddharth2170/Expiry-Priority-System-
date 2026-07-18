import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.data_structures.priority_queue import PriorityQueue


class TestPriorityQueue(unittest.TestCase):
    def test_pops_in_ascending_priority_order(self):
        pq = PriorityQueue()
        for value, priority in [("c", 3), ("a", 1), ("b", 2)]:
            pq.push(value, priority)
        self.assertEqual([pq.pop() for _ in range(3)], ["a", "b", "c"])

    def test_identical_priorities_keep_insertion_order(self):
        # Edge case: equal priorities must not raise and must be stable (FIFO),
        # which the internal sequence counter guarantees.
        pq = PriorityQueue()
        for value in ["first", "second", "third"]:
            pq.push(value, 5)
        self.assertEqual([pq.pop() for _ in range(3)], ["first", "second", "third"])

    def test_identical_priorities_with_unorderable_items(self):
        # Items themselves (dicts here) are not comparable; equal priorities must
        # still work because only (priority, seq) is ever compared.
        pq = PriorityQueue()
        a, b = {"id": 1}, {"id": 2}
        pq.push(a, 1)
        pq.push(b, 1)
        self.assertIs(pq.pop(), a)
        self.assertIs(pq.pop(), b)

    def test_peek_does_not_remove(self):
        pq = PriorityQueue()
        pq.push("x", 10)
        pq.push("y", 1)
        self.assertEqual(pq.peek(), "y")
        self.assertEqual(len(pq), 2)
        self.assertEqual(pq.peek(), "y")

    def test_is_empty_and_len(self):
        pq = PriorityQueue()
        self.assertTrue(pq.is_empty())
        self.assertEqual(len(pq), 0)
        pq.push("only", 1)
        self.assertFalse(pq.is_empty())
        self.assertEqual(len(pq), 1)
        pq.pop()
        self.assertTrue(pq.is_empty())

    def test_peek_on_empty_raises(self):
        with self.assertRaises(IndexError):
            PriorityQueue().peek()

    def test_pop_on_empty_raises(self):
        with self.assertRaises(IndexError):
            PriorityQueue().pop()

    def test_interleaved_push_and_pop(self):
        pq = PriorityQueue()
        pq.push("a", 5)
        pq.push("b", 2)
        self.assertEqual(pq.pop(), "b")
        pq.push("c", 1)
        pq.push("d", 8)
        self.assertEqual([pq.pop() for _ in range(3)], ["c", "a", "d"])


if __name__ == "__main__":
    unittest.main()
